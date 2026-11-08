# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class DslEmployeeOnboarding(models.Model):
    _name = 'dsl.employee.onboarding'
    _description = 'New Joiner Onboarding Plan & Asset Handover'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'joining_date desc, id desc'

    name = fields.Char(
        string='Onboarding Ref.',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
    )
    employee_id = fields.Many2one('hr.employee', string='New Joiner', required=True, index=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company, index=True)
    branch_id = fields.Many2one('dsl.branch', string='Branch / Plant', domain="[('company_id', '=', company_id)]")
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', store=True, readonly=True)
    job_id = fields.Many2one('hr.job', related='employee_id.job_id', store=True, readonly=True)
    buddy_employee_id = fields.Many2one('hr.employee', string='Onboarding Buddy / Mentor')
    joining_date = fields.Date(string='Joining Date', default=fields.Date.context_today, required=True)
    mail_activity_plan_id = fields.Many2one(
        'mail.activity.plan',
        string='Odoo Activity Plan',
        domain="[('res_model', '=', 'hr.employee')]",
        ondelete='set null',
        help='Linked Odoo native HR Onboarding Activity Plan.',
    )

    task_ids = fields.One2many('dsl.onboarding.task', 'onboarding_id', string='Onboarding Checklist')
    asset_ids = fields.One2many('dsl.employee.asset.assignment', 'onboarding_id', string='Handed-Over Assets')
    completion_pct = fields.Float(string='Completion (%)', compute='_compute_completion_pct', store=True)

    state = fields.Selection(
        selection=[
            ('draft', 'Pre-Boarding'),
            ('in_progress', 'Onboarding Active'),
            ('completed', '100% Inducted'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    @api.depends('task_ids.is_done')
    def _compute_completion_pct(self):
        for rec in self:
            total = len(rec.task_ids)
            done = len(rec.task_ids.filtered(lambda t: t.is_done))
            rec.completion_pct = round((done / total) * 100.0, 1) if total else 0.0

    @api.onchange('employee_id')
    def _onchange_employee_sync(self):
        if self.employee_id:
            self.company_id = self.employee_id.company_id.id
            self.branch_id = self.employee_id.branch_id.id if self.employee_id.branch_id else False
            if self.employee_id.joining_date:
                self.joining_date = self.employee_id.joining_date

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.employee.onboarding') or _('New')
        recs = super().create(vals_list)
        for rec in recs:
            if not rec.task_ids:
                rec.action_load_standard_checklist()
            rec._sync_to_odoo_activity_plan()
        return recs

    def _sync_to_odoo_activity_plan(self):
        """Link onboarding checklist with Odoo's native mail.activity.plan (hr onboarding plan)."""
        if 'mail.activity.plan' not in self.env:
            return
        Plan = self.env['mail.activity.plan'].sudo()
        for rec in self:
            if rec.mail_activity_plan_id:
                continue
            plan = Plan.search([
                ('res_model', '=', 'hr.employee'),
                '|', ('company_id', '=', False), ('company_id', '=', rec.company_id.id),
            ], limit=1)
            if not plan:
                plan = Plan.create({
                    'name': 'Standard HR Onboarding Plan',
                    'res_model': 'hr.employee',
                    'company_id': False,
                })
            if plan:
                rec.write({'mail_activity_plan_id': plan.id})

    def action_load_standard_checklist(self):
        for rec in self:
            if rec.task_ids:
                continue
            defaults = [
                ('hr_docs', 'Collect Signed Appointment Letter, NID, TIN, Academic Certs & Nominee Form-7'),
                ('it_setup', 'Create Official Email, ERP Login, Biometric Face/Finger Enrollment & Laptop'),
                ('admin_kit', 'Issue ID Card, Access Badge, Workstation Desk & Welcome Kit'),
                ('finance_bank', 'Open / Verify Salary Bank Account (BEFTN) or Corporate bKash/Nagad'),
                ('dept_orient', 'Department Orientation, 30-60-90 Day Probation Goals & Safety Briefing'),
            ]
            self.env['dsl.onboarding.task'].create([{
                'onboarding_id': rec.id,
                'category': cat,
                'task_title': title,
                'owner_id': self.env.uid,
            } for cat, title in defaults])

    def action_start(self):
        self.action_load_standard_checklist()
        self.write({'state': 'in_progress'})

    def action_complete_all(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.task_ids.write({'is_done': True, 'completed_date': today})
            rec.state = 'completed'


class DslOnboardingTask(models.Model):
    _name = 'dsl.onboarding.task'
    _description = 'Employee Onboarding Checklist Task'
    _order = 'id asc'

    onboarding_id = fields.Many2one('dsl.employee.onboarding', required=True, ondelete='cascade', index=True)
    category = fields.Selection(
        selection=[
            ('hr_docs', 'HR Dossier & Statutory Forms'),
            ('it_setup', 'IT, Email & Biometric'),
            ('admin_kit', 'Admin, ID Card & Desk'),
            ('finance_bank', 'Payroll Bank / MFS'),
            ('dept_orient', 'Team & Probation Induction'),
        ],
        string='Wing',
        default='hr_docs',
        required=True,
    )
    task_title = fields.Char(string='Checklist Task', required=True)
    owner_id = fields.Many2one('res.users', string='Responsible Officer')
    is_done = fields.Boolean(string='Completed', default=False)
    completed_date = fields.Date(string='Done Date')


class DslEmployeeAssetAssignment(models.Model):
    _name = 'dsl.employee.asset.assignment'
    _description = 'Employee Official IT & Admin Asset Handover Register'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'issue_date desc, id desc'

    name = fields.Char(string='Asset Tag / Serial', required=True, tracking=True)
    asset_name = fields.Char(string='Asset Description (e.g. MacBook / ThinkPad / SIM)', required=True, tracking=True)
    asset_category = fields.Selection(
        selection=[
            ('laptop_pc', 'Laptop / Workstation PC'),
            ('mobile_sim', 'Mobile Handset / Corporate SIM'),
            ('id_access', 'RFID Access Card / Security Key'),
            ('vehicle_tool', 'Vehicle / Field Equipment'),
            ('other', 'Other Company Property'),
        ],
        string='Asset Type',
        default='laptop_pc',
        required=True,
    )
    employee_id = fields.Many2one('hr.employee', string='Custodian Employee', required=True, index=True, tracking=True)
    onboarding_id = fields.Many2one('dsl.employee.onboarding', string='Onboarding Ref.', ondelete='set null')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    asset_value = fields.Monetary(string='Book Value (৳)', currency_field='currency_id', default=0.0)
    issue_date = fields.Date(string='Handover Date', default=fields.Date.context_today, required=True)
    return_date = fields.Date(string='Returned Date')
    state = fields.Selection(
        selection=[
            ('assigned', 'In Employee Custody'),
            ('returned', 'Returned & Verified'),
            ('damaged_lost', 'Damaged / Lost'),
        ],
        string='Status',
        default='assigned',
        required=True,
        tracking=True,
    )
    remarks = fields.Text(string='Condition & Accessories Notes')

    def action_mark_returned(self):
        self.write({'state': 'returned', 'return_date': fields.Date.context_today(self)})


class HrEmployeeAssetExt(models.Model):
    _inherit = 'hr.employee'

    dsl_asset_assignment_ids = fields.One2many(
        'dsl.employee.asset.assignment',
        'employee_id',
        string='Assigned Company Assets',
        groups='hr.group_hr_user',
    )


