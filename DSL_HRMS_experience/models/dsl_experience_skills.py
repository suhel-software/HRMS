# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DslHrSkillCategory(models.Model):
    _name = 'dsl.hr.skill.category'
    _description = 'HR Competency & Skill Category'
    _order = 'sequence, name'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Category Name', required=True)
    color = fields.Integer(string='Color Index', default=4)
    skill_ids = fields.One2many('dsl.hr.skill', 'category_id', string='Skills')
    odoo_skill_type_id = fields.Many2one(
        'hr.skill.type',
        string='Odoo Skill Type',
        ondelete='set null',
        help='Automatically synchronized native Odoo hr.skill.type record (hr_skills).',
    )

    def _ensure_odoo_skill_type(self):
        if self.env.context.get('skip_dsl_skill_sync') or 'hr.skill.type' not in self.env:
            return
        SkillType = self.env['hr.skill.type'].sudo().with_context(skip_dsl_skill_sync=True)
        SkillLevel = self.env['hr.skill.level'].sudo()
        level_specs = [
            ('Beginner', 25, False),
            ('Intermediate', 50, False),
            ('Advanced', 75, True),
            ('Expert', 90, False),
            ('Master / Authority', 100, False),
        ]
        for rec in self.sudo():
            st = rec.odoo_skill_type_id
            if not st:
                st = SkillType.search([('name', '=ilike', rec.name.strip())], limit=1)
                if not st:
                    st = SkillType.create({'name': rec.name.strip()})
                rec.with_context(skip_dsl_skill_sync=True).write({'odoo_skill_type_id': st.id})
            else:
                st.write({'name': rec.name.strip()})
            if not st.skill_level_ids:
                for l_name, l_prog, l_def in level_specs:
                    SkillLevel.create({
                        'skill_type_id': st.id,
                        'name': l_name,
                        'level_progress': l_prog,
                        'default_level': l_def,
                    })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_odoo_skill_type()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_dsl_skill_sync') and 'name' in vals:
            self._ensure_odoo_skill_type()
        return res


class DslHrSkill(models.Model):
    _name = 'dsl.hr.skill'
    _description = 'HR Skill / Competency'
    _order = 'category_id, name'

    name = fields.Char(string='Skill / Competency', required=True)
    category_id = fields.Many2one(
        'dsl.hr.skill.category',
        string='Skill Category',
        required=True,
        ondelete='cascade',
    )
    color = fields.Integer(related='category_id.color', store=True)
    odoo_skill_id = fields.Many2one(
        'hr.skill',
        string='Odoo Skill',
        ondelete='set null',
        help='Automatically synchronized native Odoo hr.skill record (hr_skills).',
    )

    def _ensure_odoo_skill(self):
        if self.env.context.get('skip_dsl_skill_sync') or 'hr.skill' not in self.env:
            return
        HrSkill = self.env['hr.skill'].sudo().with_context(skip_dsl_skill_sync=True)
        for rec in self.sudo():
            if not rec.category_id:
                continue
            rec.category_id._ensure_odoo_skill_type()
            st = rec.category_id.odoo_skill_type_id
            if not st:
                continue
            if rec.odoo_skill_id:
                rec.odoo_skill_id.sudo().with_context(skip_dsl_skill_sync=True).write({
                    'name': rec.name.strip(),
                    'skill_type_id': st.id,
                })
            else:
                sk = HrSkill.search([
                    ('name', '=ilike', rec.name.strip()),
                    ('skill_type_id', '=', st.id),
                ], limit=1)
                if not sk:
                    sk = HrSkill.create({
                        'name': rec.name.strip(),
                        'skill_type_id': st.id,
                    })
                rec.with_context(skip_dsl_skill_sync=True).write({'odoo_skill_id': sk.id})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_odoo_skill()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_dsl_skill_sync') and ('name' in vals or 'category_id' in vals):
            self._ensure_odoo_skill()
        return res


class DslEmployeeSkill(models.Model):
    _name = 'dsl.employee.skill'
    _description = 'Employee Skill & Proficiency Level'
    _order = 'is_primary_skill desc, progress_pct desc, id'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='employee_id.company_id',
        store=True,
        index=True,
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Branch',
        related='employee_id.branch_id',
        store=True,
        index=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        related='employee_id.department_id',
        store=True,
    )
    category_id = fields.Many2one(
        'dsl.hr.skill.category',
        string='Category',
        required=True,
    )
    skill_id = fields.Many2one(
        'dsl.hr.skill',
        string='Skill',
        required=True,
        domain="[('category_id', '=', category_id)]",
    )
    proficiency_level = fields.Selection(
        selection=[
            ('1', 'Beginner (25%)'),
            ('2', 'Intermediate (50%)'),
            ('3', 'Advanced (75%)'),
            ('4', 'Expert (90%)'),
            ('5', 'Master / Authority (100%)'),
        ],
        string='Proficiency Level',
        default='3',
        required=True,
    )
    progress_pct = fields.Integer(
        string='Mastery (%)',
        compute='_compute_progress_pct',
        store=True,
    )
    years_used = fields.Float(string='Years Applied', digits=(4, 1), default=1.0)
    is_primary_skill = fields.Boolean(string='Core Competency', default=False)
    odoo_emp_skill_id = fields.Many2one(
        'hr.employee.skill',
        string='Odoo Employee Skill',
        ondelete='set null',
        help='Automatically synchronized native Odoo hr.employee.skill record (hr_skills).',
    )

    _sql_constraints = [
        (
            'emp_skill_uniq',
            'unique(employee_id, skill_id)',
            'This skill is already assigned to this employee!',
        ),
    ]

    @api.depends('proficiency_level')
    def _compute_progress_pct(self):
        pct_map = {'1': 25, '2': 50, '3': 75, '4': 90, '5': 100}
        for rec in self:
            rec.progress_pct = pct_map.get(rec.proficiency_level, 50)

    @api.onchange('skill_id')
    def _onchange_skill_set_category(self):
        if self.skill_id and not self.category_id:
            self.category_id = self.skill_id.category_id

    def _sync_to_odoo_employee_skill(self):
        if self.env.context.get('skip_dsl_skill_sync') or 'hr.employee.skill' not in self.env:
            return
        EmpSkill = self.env['hr.employee.skill'].sudo().with_context(skip_dsl_skill_sync=True)
        for rec in self.sudo():
            if not rec.employee_id or not rec.skill_id:
                continue
            rec.skill_id._ensure_odoo_skill()
            odoo_skill = rec.skill_id.odoo_skill_id
            odoo_st = rec.skill_id.category_id.odoo_skill_type_id
            if not odoo_skill or not odoo_st:
                continue
            target_pct = rec.progress_pct or 75
            levels = odoo_st.skill_level_ids
            if not levels:
                rec.skill_id.category_id._ensure_odoo_skill_type()
                levels = odoo_st.skill_level_ids
            best_level = False
            best_diff = 999
            for lv in levels:
                diff = abs((lv.level_progress or 0) - target_pct)
                if diff < best_diff:
                    best_diff = diff
                    best_level = lv
            if not best_level:
                continue

            es_vals = {
                'employee_id': rec.employee_id.id,
                'skill_type_id': odoo_st.id,
                'skill_id': odoo_skill.id,
                'skill_level_id': best_level.id,
            }
            if rec.odoo_emp_skill_id:
                try:
                    rec.odoo_emp_skill_id.sudo().with_context(skip_dsl_skill_sync=True).write(es_vals)
                except Exception:
                    pass
            else:
                existing_es = EmpSkill.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('skill_id', '=', odoo_skill.id),
                ], limit=1)
                if existing_es:
                    try:
                        existing_es.write(es_vals)
                    except Exception:
                        pass
                    rec.with_context(skip_dsl_skill_sync=True).write({'odoo_emp_skill_id': existing_es.id})
                else:
                    try:
                        created_es = EmpSkill.create(es_vals)
                        rec.with_context(skip_dsl_skill_sync=True).write({'odoo_emp_skill_id': created_es.id})
                    except Exception:
                        pass

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_to_odoo_employee_skill()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_dsl_skill_sync'):
            self._sync_to_odoo_employee_skill()
        return res

    def unlink(self):
        es_ids = self.sudo().mapped('odoo_emp_skill_id')
        res = super().unlink()
        if es_ids:
            es_ids.sudo().unlink()
        return res


class DslEmployeeExperience(models.Model):
    _name = 'dsl.employee.experience'
    _description = 'Employee Previous Work Experience'
    _order = 'date_from desc, id desc'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='employee_id.company_id',
        store=True,
        index=True,
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Branch',
        related='employee_id.branch_id',
        store=True,
        index=True,
    )
    employer_name = fields.Char(string='Previous Employer / Organization', required=True)
    industry_sector = fields.Selection(
        selection=[
            ('rmg_textile', 'RMG, Apparel & Textiles'),
            ('it_software', 'IT, Software & Telecom'),
            ('logistics_port', 'Shipping, Port & Logistics'),
            ('pharma', 'Pharmaceuticals & Healthcare'),
            ('banking_fin', 'Banking, NBFI & FinTech'),
            ('fmcg_mfg', 'FMCG & Industrial Manufacturing'),
            ('ngo_dev', 'NGO / Development / Education'),
            ('other', 'Other Corporate Sector'),
        ],
        string='Industry Sector',
        default='other',
    )
    designation = fields.Char(string='Job Title / Designation', required=True)
    department_name = fields.Char(string='Department')
    location = fields.Char(string='City / Country', default='Dhaka, Bangladesh')
    date_from = fields.Date(string='Start Date', required=True)
    date_to = fields.Date(string='End Date', required=True)
    duration_years = fields.Float(
        string='Experience (Years)',
        compute='_compute_duration',
        store=True,
        digits=(5, 2),
    )
    duration_display = fields.Char(
        string='Tenure',
        compute='_compute_duration',
        store=True,
    )
    last_drawn_salary = fields.Float(string='Last Gross Salary (BDT)')
    leaving_reason = fields.Char(string='Reason for Leaving')
    responsibilities = fields.Text(string='Key Responsibilities & Achievements')
    reference_person = fields.Char(string='Reference Contact Name')
    reference_phone = fields.Char(string='Reference Phone / Email')
    is_verified = fields.Boolean(string='Background Verified', default=False)
    experience_letter_file = fields.Binary(string='Experience / Release Letter', attachment=True)
    experience_letter_filename = fields.Char(string='Filename')
    odoo_resume_line_id = fields.Many2one(
        'hr.resume.line',
        string='Odoo Resume Line',
        ondelete='set null',
        help='Automatically synchronized native Odoo hr.resume.line record (hr_skills).',
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_('End Date cannot be earlier than Start Date in Work Experience!'))

    @api.depends('date_from', 'date_to')
    def _compute_duration(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to >= rec.date_from:
                rd = relativedelta(rec.date_to + relativedelta(days=1), rec.date_from)
                rec.duration_years = round(rd.years + (rd.months / 12.0) + (rd.days / 365.0), 2)
                parts = []
                if rd.years:
                    parts.append(f"{rd.years} yr{'s' if rd.years > 1 else ''}")
                if rd.months:
                    parts.append(f"{rd.months} mo{'s' if rd.months > 1 else ''}")
                if not parts:
                    parts.append(f"{max(rd.days, 1)} days")
                rec.duration_display = ' '.join(parts)
            else:
                rec.duration_years = 0.0
                rec.duration_display = '—'

    def _sync_to_odoo_resume_line(self):
        if self.env.context.get('skip_dsl_exp_sync') or 'hr.resume.line' not in self.env:
            return
        ResumeLine = self.env['hr.resume.line'].sudo().with_context(skip_dsl_exp_sync=True)
        LineType = self.env['hr.resume.line.type'].sudo()
        exp_type = LineType.search([('name', 'ilike', 'Experience')], limit=1)
        if not exp_type:
            exp_type = LineType.create({'name': 'Experience', 'sequence': 1})

        for rec in self.sudo():
            if not rec.employee_id:
                continue
            r_vals = {
                'employee_id': rec.employee_id.id,
                'name': f"{rec.designation} — {rec.employer_name}",
                'date_start': rec.date_from or fields.Date.context_today(self),
                'date_end': rec.date_to or False,
                'description': rec.responsibilities or rec.department_name or rec.location or '',
                'line_type_id': exp_type.id,
            }
            if rec.odoo_resume_line_id:
                rec.odoo_resume_line_id.sudo().with_context(skip_dsl_exp_sync=True).write(r_vals)
            else:
                existing_rl = ResumeLine.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('name', '=', r_vals['name']),
                ], limit=1)
                if existing_rl:
                    existing_rl.write(r_vals)
                    rec.with_context(skip_dsl_exp_sync=True).write({'odoo_resume_line_id': existing_rl.id})
                else:
                    created_rl = ResumeLine.create(r_vals)
                    rec.with_context(skip_dsl_exp_sync=True).write({'odoo_resume_line_id': created_rl.id})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_to_odoo_resume_line()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_dsl_exp_sync'):
            self._sync_to_odoo_resume_line()
        return res

    def unlink(self):
        rl_ids = self.sudo().mapped('odoo_resume_line_id')
        res = super().unlink()
        if rl_ids:
            rl_ids.sudo().unlink()
        return res


class HrEmployeeExperienceInherit(models.Model):
    _inherit = 'hr.employee'

    dsl_experience_ids = fields.One2many(
        'dsl.employee.experience',
        'employee_id',
        string='Previous Employment History',
        groups='hr.group_hr_user',
    )
    dsl_skill_ids = fields.One2many(
        'dsl.employee.skill',
        'employee_id',
        string='Competencies & Skills Matrix',
        groups='hr.group_hr_user',
    )
    prior_experience_years = fields.Float(
        string='Prior Experience (Years)',
        compute='_compute_experience_metrics',
        digits=(5, 1),
        groups='hr.group_hr_user',
    )
    dsl_experience_count = fields.Integer(
        string='Past Jobs',
        compute='_compute_experience_metrics',
        groups='hr.group_hr_user',
    )
    dsl_skill_count = fields.Integer(
        string='HRMS Skills Count',
        compute='_compute_experience_metrics',
        groups='hr.group_hr_user',
    )

    def _compute_experience_metrics(self):
        Exp = self.env['dsl.employee.experience'].sudo()
        Skill = self.env['dsl.employee.skill'].sudo()
        for emp in self:
            exps = Exp.search([('employee_id', '=', emp.id)])
            emp.dsl_experience_count = len(exps)
            emp.prior_experience_years = round(sum(exps.mapped('duration_years')), 1)
            emp.dsl_skill_count = Skill.search_count([('employee_id', '=', emp.id)])

    def action_view_experience_records(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Prior Employment History',
            'res_model': 'dsl.employee.experience',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

    def action_view_employee_skills(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Skills Matrix',
            'res_model': 'dsl.employee.skill',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
