# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class DslManpowerRequisition(models.Model):
    _name = 'dsl.manpower.requisition'
    _description = 'Departmental Manpower Requisition (MPR)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'

    name = fields.Char(
        string='MPR Ref.',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
    )
    job_title_display = fields.Char(string='Position / Hiring Title', required=True, tracking=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Branch / Plant',
        domain="[('company_id', '=', company_id)]",
    )
    department_id = fields.Many2one('hr.department', string='Department', required=True, tracking=True)
    job_id = fields.Many2one('hr.job', string='Designation', required=True, tracking=True)
    grade_id = fields.Many2one('dsl.hr.grade', string='Pay Grade')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    requested_by_id = fields.Many2one('res.users', string='Hiring Manager', default=lambda self: self.env.user)
    request_date = fields.Date(string='Requisition Date', default=fields.Date.context_today, required=True)
    target_join_date = fields.Date(string='Target Joining Date')
    vacancies = fields.Integer(string='Approved Headcount', default=1, required=True, tracking=True)
    hired_count = fields.Integer(string='Hired Count', compute='_compute_applicant_stats')
    applicant_count = fields.Integer(string='Applicants', compute='_compute_applicant_stats')

    employment_category = fields.Selection(
        selection=[
            ('permanent', 'Permanent (via Probation)'),
            ('contractual', 'Fixed-Term Contractual'),
            ('intern', 'Intern / Management Trainee'),
            ('casual', 'Factory / Piece-Rate Worker'),
        ],
        string='Employment Nature',
        default='permanent',
        required=True,
    )
    budgeted_min_gross = fields.Monetary(string='Budgeted Min Gross (৳)', currency_field='currency_id')
    budgeted_max_gross = fields.Monetary(string='Budgeted Max Gross (৳)', currency_field='currency_id')
    job_requirements = fields.Text(string='Key Skills, Experience & Qualification Requirements')

    applicant_ids = fields.One2many('dsl.job.applicant', 'requisition_id', string='Candidates')
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Pending Approval'),
            ('approved_open', 'Approved & Open'),
            ('fulfilled', 'Fulfilled / Closed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    def _compute_applicant_stats(self):
        for rec in self:
            rec.applicant_count = len(rec.applicant_ids)
            rec.hired_count = len(rec.applicant_ids.filtered(lambda a: a.stage == 'hired'))

    @api.constrains('vacancies')
    def _check_vacancies(self):
        for rec in self:
            if rec.vacancies <= 0:
                raise ValidationError(_('Requested headcount must be at least 1!'))

    @api.onchange('job_id')
    def _onchange_job_id_sync(self):
        if self.job_id and not self.job_title_display:
            self.job_title_display = self.job_id.name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.manpower.requisition') or _('New')
        return super().create(vals_list)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve_open(self):
        self.write({'state': 'approved_open'})
        for rec in self.sudo():
            if rec.job_id and 'no_of_recruitment' in rec.job_id._fields:
                try:
                    rec.job_id.sudo().write({'no_of_recruitment': rec.vacancies})
                except Exception:
                    pass

    def action_close_fulfilled(self):
        self.write({'state': 'fulfilled'})
        for rec in self.sudo():
            if rec.job_id and 'no_of_recruitment' in rec.job_id._fields:
                try:
                    rec.job_id.sudo().write({'no_of_recruitment': 0})
                except Exception:
                    pass

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class DslJobApplicant(models.Model):
    _name = 'dsl.job.applicant'
    _description = 'Candidate Application & ATS Pipeline'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'average_score desc, id desc'

    name = fields.Char(
        string='Application No.',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
    )
    candidate_name = fields.Char(string='Candidate Full Name', required=True, tracking=True)
    email = fields.Char(string='Email Address')
    mobile = fields.Char(string='Mobile Number (BD)', required=True)
    nid_number = fields.Char(string='NID / Smart Card No.')

    requisition_id = fields.Many2one(
        'dsl.manpower.requisition',
        string='Manpower Requisition',
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Branch / Plant',
        domain="[('company_id', '=', company_id)]",
    )
    department_id = fields.Many2one('hr.department', string='Department', required=True)
    job_id = fields.Many2one('hr.job', string='Applied Designation', required=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    source = fields.Selection(
        selection=[
            ('bdjobs', 'Bdjobs.com'),
            ('linkedin', 'LinkedIn'),
            ('career_portal', 'Company Career Portal'),
            ('referral', 'Employee Referral'),
            ('campus', 'University / Campus Drive'),
            ('walk_in', 'Factory Gate / Walk-In'),
        ],
        string='Application Source',
        default='bdjobs',
    )
    total_experience_years = fields.Float(string='Relevant Experience (Yrs)', default=0.0)
    expected_gross = fields.Monetary(string='Expected Gross (৳)', currency_field='currency_id')
    offered_gross = fields.Monetary(string='Offered Monthly Gross (৳)', currency_field='currency_id', tracking=True)
    proposed_joining_date = fields.Date(string='Proposed Joining Date', default=fields.Date.context_today)

    score_line_ids = fields.One2many(
        'dsl.applicant.interview.score',
        'applicant_id',
        string='Interview Panel Scores',
    )
    average_score = fields.Float(
        string='Panel Score (/100)',
        compute='_compute_average_score',
        store=True,
    )
    hired_employee_id = fields.Many2one('hr.employee', string='Created Employee Profile', readonly=True)
    resume_notes = fields.Text(string='CV Summary & HR Screening Notes')
    odoo_applicant_id = fields.Many2one(
        'hr.applicant',
        string='Odoo ATS Applicant',
        ondelete='set null',
        help='Automatically synchronized native Odoo hr.applicant record (hr_recruitment).',
    )

    stage = fields.Selection(
        selection=[
            ('applied', 'CV Received'),
            ('shortlisted', 'Shortlisted'),
            ('written_tech', 'Written / Technical Test'),
            ('viva_board', 'Panel Interview'),
            ('offered', 'Offer Letter Issued'),
            ('hired', 'Hired & Joined'),
            ('rejected', 'Not Selected'),
        ],
        string='ATS Stage',
        default='applied',
        required=True,
        tracking=True,
        index=True,
    )

    @api.depends('score_line_ids.total_score')
    def _compute_average_score(self):
        for rec in self:
            if rec.score_line_ids:
                rec.average_score = round(sum(rec.score_line_ids.mapped('total_score')) / len(rec.score_line_ids), 2)
            else:
                rec.average_score = 0.0

    @api.onchange('requisition_id')
    def _onchange_requisition_sync(self):
        if self.requisition_id:
            req = self.requisition_id
            self.company_id = req.company_id.id
            self.branch_id = req.branch_id.id if req.branch_id else False
            self.department_id = req.department_id.id
            self.job_id = req.job_id.id
            if req.budgeted_max_gross and not self.offered_gross:
                self.offered_gross = req.budgeted_max_gross

    def _sync_to_odoo_hr_applicant(self):
        if self.env.context.get('skip_dsl_app_sync') or 'hr.applicant' not in self.env:
            return
        HrApplicant = self.env['hr.applicant'].sudo().with_context(skip_dsl_app_sync=True)
        for rec in self.sudo():
            vals = {
                'partner_name': rec.candidate_name,
                'email_from': rec.email or False,
                'partner_phone': rec.mobile or False,
                'company_id': rec.company_id.id if rec.company_id else self.env.company.id,
                'department_id': rec.department_id.id if rec.department_id else False,
                'job_id': rec.job_id.id if rec.job_id else False,
                'salary_expected': rec.expected_gross or 0.0,
                'salary_proposed': rec.offered_gross or 0.0,
                'availability': rec.proposed_joining_date or False,
                'emp_id': rec.hired_employee_id.id if rec.hired_employee_id else False,
            }
            if 'dsl_applicant_id' in HrApplicant._fields:
                vals['dsl_applicant_id'] = rec.id
            if 'branch_id' in HrApplicant._fields and rec.branch_id:
                vals['branch_id'] = rec.branch_id.id
            if rec.odoo_applicant_id:
                try:
                    rec.odoo_applicant_id.sudo().with_context(skip_dsl_app_sync=True).write(vals)
                except Exception:
                    pass
            else:
                existing = HrApplicant.search([
                    ('partner_name', '=', rec.candidate_name),
                    ('job_id', '=', rec.job_id.id if rec.job_id else False),
                ], limit=1)
                if existing:
                    try:
                        existing.write(vals)
                    except Exception:
                        pass
                    rec.with_context(skip_dsl_app_sync=True).write({'odoo_applicant_id': existing.id})
                else:
                    try:
                        created = HrApplicant.create(vals)
                        rec.with_context(skip_dsl_app_sync=True).write({'odoo_applicant_id': created.id})
                    except Exception:
                        pass

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.job.applicant') or _('New')
        records = super().create(vals_list)
        records._sync_to_odoo_hr_applicant()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_dsl_app_sync'):
            self._sync_to_odoo_hr_applicant()
        return res

    def action_shortlist(self):
        self.write({'stage': 'shortlisted'})

    def action_move_interview(self):
        self.write({'stage': 'viva_board'})

    def action_issue_offer(self):
        for rec in self:
            if rec.offered_gross <= 0 and rec.expected_gross > 0:
                rec.offered_gross = rec.expected_gross
            rec.stage = 'offered'

    def action_hire_create_employee(self):
        self.ensure_one()
        if self.hired_employee_id:
            raise UserError(_('Employee profile %s is already created for this candidate!') % self.hired_employee_id.name)
        emp_vals = {
            'name': self.candidate_name,
            'company_id': self.company_id.id,
            'branch_id': self.branch_id.id if self.branch_id else False,
            'department_id': self.department_id.id,
            'job_id': self.job_id.id,
            'work_email': self.email or False,
            'mobile_phone': self.mobile or False,
            'joining_date': self.proposed_joining_date or fields.Date.context_today(self),
            'employment_category': 'probation',
            'employment_status': 'probation',
        }
        emp = self.env['hr.employee'].sudo().create(emp_vals)
        self.write({
            'hired_employee_id': emp.id,
            'stage': 'hired',
        })
        if self.requisition_id and self.requisition_id.hired_count >= self.requisition_id.vacancies:
            self.requisition_id.write({'state': 'fulfilled'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'res_id': emp.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_print_offer_letter(self):
        self.ensure_one()
        return self.env.ref('DSL_HRMS_recruitment.action_report_dsl_offer_letter').report_action(self)

    def action_reject(self):
        self.write({'stage': 'rejected'})


class DslApplicantInterviewScore(models.Model):
    _name = 'dsl.applicant.interview.score'
    _description = 'Candidate Interview Panel Evaluation Score'
    _order = 'id asc'

    applicant_id = fields.Many2one('dsl.job.applicant', required=True, ondelete='cascade', index=True)
    interviewer_id = fields.Many2one('res.users', string='Panelist', default=lambda self: self.env.user, required=True)
    round_name = fields.Char(string='Evaluation Round', default='Technical & Viva Assessment', required=True)
    technical_score = fields.Float(string='Technical (/40)', default=32.0)
    communication_score = fields.Float(string='Communication (/30)', default=24.0)
    culture_fit_score = fields.Float(string='Attitude & Fit (/30)', default=25.0)
    total_score = fields.Float(string='Total (/100)', compute='_compute_total', store=True)
    recommendation = fields.Selection(
        selection=[
            ('strong_hire', 'Strong Hire'),
            ('hire', 'Hire'),
            ('hold', 'Hold / Keep Warm'),
            ('no_hire', 'Do Not Hire'),
        ],
        string='Verdict',
        default='hire',
        required=True,
    )
    remarks = fields.Char(string='Interviewer Feedback')

    @api.depends('technical_score', 'communication_score', 'culture_fit_score')
    def _compute_total(self):
        for ln in self:
            ln.total_score = round(
                min(max((ln.technical_score or 0.0) + (ln.communication_score or 0.0) + (ln.culture_fit_score or 0.0), 0.0), 100.0),
                2,
            )


class HrApplicantDslExt(models.Model):
    _inherit = 'hr.applicant'

    dsl_applicant_id = fields.Many2one(
        'dsl.job.applicant',
        string='DSL Applicant Record',
        ondelete='set null',
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Branch / Duty Station',
    )


