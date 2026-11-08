# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DslEmployeeEducation(models.Model):
    _name = 'dsl.employee.education'
    _description = 'Employee Academic Qualification'
    _order = 'passing_year desc, id desc'

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
    degree_level = fields.Selection(
        selection=[
            ('psc_jsc', 'JSC / JDC / Equivalent'),
            ('ssc', 'SSC / Dakhil / O-Level'),
            ('hsc', 'HSC / Alim / A-Level'),
            ('diploma', 'Diploma in Engineering / Technical'),
            ('bachelor', 'Bachelor / Honours (B.Sc / BBA / BA / B.Tech)'),
            ('master', 'Masters (M.Sc / MBA / MA / MSS)'),
            ('phd', 'PhD / Doctorate'),
            ('professional', 'Professional (CA / CMA / ACCA / PGDHRM / LLB)'),
        ],
        string='Education Level',
        required=True,
        default='bachelor',
    )
    degree_title = fields.Char(
        string='Exam / Degree Title',
        required=True,
        help='e.g. B.Sc. in Computer Science & Engineering, MBA in HRM, HSC',
    )
    major_group = fields.Char(
        string='Major / Concentration / Group',
        help='e.g. CSE, Textile Engineering, Finance, Science, Business Studies',
    )
    institute_name = fields.Char(
        string='Institution / University / College',
        required=True,
    )
    board_or_university = fields.Char(
        string='Education Board / University',
        help='e.g. Dhaka Board, BUET, University of Dhaka, National University, BTEB',
    )
    result_type = fields.Selection(
        selection=[
            ('cgpa_4', 'CGPA (Scale of 4.00)'),
            ('gpa_5', 'GPA (Scale of 5.00)'),
            ('division', 'Division / Class'),
            ('pass', 'Pass / Appeared'),
        ],
        string='Result Scale',
        default='cgpa_4',
        required=True,
    )
    cgpa_score = fields.Float(string='CGPA / GPA Score', digits=(4, 2))
    division_class = fields.Selection(
        selection=[
            ('first', '1st Division / Class'),
            ('second', '2nd Division / Class'),
            ('third', '3rd Division / Class'),
        ],
        string='Division / Class',
    )
    result_display = fields.Char(
        string='Result',
        compute='_compute_result_display',
    )
    passing_year = fields.Char(string='Passing Year', size=4, required=True)
    duration_years = fields.Char(string='Duration', help='e.g. 4 Years')
    is_highest_degree = fields.Boolean(string='Highest Degree', default=False)
    verification_status = fields.Selection(
        selection=[
            ('pending', 'Pending Verification'),
            ('verified', 'Verified by HR'),
            ('discrepancy', 'Discrepancy Found'),
        ],
        string='Verification',
        default='pending',
        required=True,
    )
    certificate_file = fields.Binary(string='Certificate Attachment', attachment=True)
    certificate_filename = fields.Char(string='Certificate Filename')
    notes = fields.Text(string='Remarks')
    odoo_resume_line_id = fields.Many2one(
        'hr.resume.line',
        string='Odoo Resume Line',
        ondelete='set null',
        help='Automatically synchronized native Odoo hr.resume.line record (hr_skills).',
    )
    odoo_degree_id = fields.Many2one(
        'hr.recruitment.degree',
        string='Odoo Recruitment Degree',
        ondelete='set null',
        help='Automatically synchronized native Odoo hr.recruitment.degree record (hr_recruitment).',
    )

    @api.constrains('passing_year')
    def _check_passing_year(self):
        for rec in self:
            if rec.passing_year and (not rec.passing_year.isdigit() or len(rec.passing_year) != 4):
                raise ValidationError(_('Passing Year must be a 4-digit year (e.g. 2020).'))

    @api.depends('result_type', 'cgpa_score', 'division_class')
    def _compute_result_display(self):
        div_map = {'first': '1st Class', 'second': '2nd Class', 'third': '3rd Class'}
        for rec in self:
            if rec.result_type == 'cgpa_4':
                rec.result_display = f"{rec.cgpa_score:.2f} / 4.00" if rec.cgpa_score else '—'
            elif rec.result_type == 'gpa_5':
                rec.result_display = f"{rec.cgpa_score:.2f} / 5.00" if rec.cgpa_score else '—'
            elif rec.result_type == 'division':
                rec.result_display = div_map.get(rec.division_class, '—')
            else:
                rec.result_display = 'Passed'

    def _sync_to_odoo_resume_and_degree(self):
        if self.env.context.get('skip_dsl_edu_sync'):
            return
        has_resume = 'hr.resume.line' in self.env
        has_degree = 'hr.recruitment.degree' in self.env
        ResumeLine = self.env['hr.resume.line'].sudo().with_context(skip_dsl_edu_sync=True) if has_resume else None
        LineType = self.env['hr.resume.line.type'].sudo() if has_resume else None
        Degree = self.env['hr.recruitment.degree'].sudo() if has_degree else None

        edu_type = False
        if LineType is not None:
            edu_type = LineType.search([('name', 'ilike', 'Education')], limit=1)
            if not edu_type:
                edu_type = LineType.create({'name': 'Education', 'sequence': 2})

        cert_map = {
            'psc_jsc': 'other',
            'ssc': 'other',
            'hsc': 'graduate',
            'diploma': 'graduate',
            'bachelor': 'bachelor',
            'master': 'master',
            'phd': 'doctor',
            'professional': 'master',
        }

        for rec in self.sudo():
            if not rec.employee_id:
                continue
            # 1. Sync hr.recruitment.degree
            if Degree is not None and rec.degree_title and not rec.odoo_degree_id:
                deg = Degree.search([('name', '=ilike', rec.degree_title.strip())], limit=1)
                if not deg:
                    deg = Degree.create({'name': rec.degree_title.strip()})
                rec.with_context(skip_dsl_edu_sync=True).write({'odoo_degree_id': deg.id})

            # 2. Sync hr.resume.line (hr_skills)
            if ResumeLine is not None:
                yr = int(rec.passing_year) if (rec.passing_year and rec.passing_year.isdigit()) else 2020
                dur = 4
                if rec.degree_level in ('ssc', 'hsc', 'master'):
                    dur = 2
                date_end = f"{yr}-12-31"
                date_start = f"{max(yr - dur, 1970)}-01-01"
                desc_parts = [p for p in [rec.institute_name, rec.board_or_university, rec.major_group, rec.result_display] if p and p != '—']
                r_vals = {
                    'employee_id': rec.employee_id.id,
                    'name': f"{rec.degree_title} — {rec.institute_name}",
                    'date_start': date_start,
                    'date_end': date_end,
                    'description': ' | '.join(desc_parts),
                    'line_type_id': edu_type.id if edu_type else False,
                }
                if rec.odoo_resume_line_id:
                    rec.odoo_resume_line_id.sudo().with_context(skip_dsl_edu_sync=True).write(r_vals)
                else:
                    existing_rl = ResumeLine.search([
                        ('employee_id', '=', rec.employee_id.id),
                        ('name', '=', r_vals['name']),
                    ], limit=1)
                    if existing_rl:
                        existing_rl.write(r_vals)
                        rec.with_context(skip_dsl_edu_sync=True).write({'odoo_resume_line_id': existing_rl.id})
                    else:
                        created_rl = ResumeLine.create(r_vals)
                        rec.with_context(skip_dsl_edu_sync=True).write({'odoo_resume_line_id': created_rl.id})

            # 3. Sync native hr.employee education fields (`certificate`, `study_field`, `study_school`)
            if rec.is_highest_degree or not rec.employee_id.study_school:
                try:
                    rec.employee_id.sudo().with_context(skip_dsl_edu_sync=True).write({
                        'certificate': cert_map.get(rec.degree_level, 'bachelor'),
                        'study_field': rec.major_group or rec.degree_title,
                        'study_school': rec.institute_name,
                    })
                except Exception:
                    pass

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_to_odoo_resume_and_degree()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_dsl_edu_sync'):
            self._sync_to_odoo_resume_and_degree()
        return res

    def unlink(self):
        rl_ids = self.sudo().mapped('odoo_resume_line_id')
        res = super().unlink()
        if rl_ids:
            rl_ids.sudo().unlink()
        return res


class DslEmployeeCertification(models.Model):
    _name = 'dsl.employee.certification'
    _description = 'Employee Professional Certification & Training'
    _order = 'issue_date desc, id desc'

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
    name = fields.Char(string='Certification / Training Title', required=True)
    issuing_authority = fields.Char(string='Issuing Organization', required=True)
    credential_id = fields.Char(string='Credential / License ID')
    issue_date = fields.Date(string='Issue Date')
    expiry_date = fields.Date(string='Expiry Date')
    cert_status = fields.Selection(
        selection=[
            ('active', 'Active / Lifetime'),
            ('expired', 'Expired'),
        ],
        string='Status',
        compute='_compute_cert_status',
    )
    attachment_file = fields.Binary(string='Certificate Copy', attachment=True)
    attachment_filename = fields.Char(string='Filename')

    @api.depends('expiry_date')
    def _compute_cert_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.expiry_date and rec.expiry_date < today:
                rec.cert_status = 'expired'
            else:
                rec.cert_status = 'active'


class HrEmployeeEducationInherit(models.Model):
    _inherit = 'hr.employee'

    education_ids = fields.One2many(
        'dsl.employee.education',
        'employee_id',
        string='Academic Qualifications',
        groups='hr.group_hr_user',
    )
    certification_ids = fields.One2many(
        'dsl.employee.certification',
        'employee_id',
        string='Professional Certifications',
        groups='hr.group_hr_user',
    )
    education_count = fields.Integer(
        string='Degrees',
        compute='_compute_education_counts',
        groups='hr.group_hr_user',
    )
    certification_count = fields.Integer(
        string='Certifications',
        compute='_compute_education_counts',
        groups='hr.group_hr_user',
    )

    def _compute_education_counts(self):
        Edu = self.env['dsl.employee.education'].sudo()
        Cert = self.env['dsl.employee.certification'].sudo()
        for emp in self:
            emp.education_count = Edu.search_count([('employee_id', '=', emp.id)])
            emp.certification_count = Cert.search_count([('employee_id', '=', emp.id)])

    def action_view_education_records(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Academic Qualifications',
            'res_model': 'dsl.employee.education',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

