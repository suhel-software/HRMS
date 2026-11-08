# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DslOvertimePolicy(models.Model):
    _name = 'dsl.overtime.policy'
    _description = 'Bangladesh Labour Act Overtime Policy'
    _inherit = ['dsl.company.branch.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Overtime Policy Name', required=True, tracking=True)
    code = fields.Char(string='Policy Code', required=True, tracking=True)
    company_id = fields.Many2one(required=False, help='Leave empty to share across group companies.')
    active = fields.Boolean(default=True)

    monthly_hours_divisor = fields.Float(
        string='Monthly Hours Divisor',
        default=208.0,
        required=True,
        tracking=True,
        help='Bangladesh Labour Rules 2015 standard: 208 hours (26 working days × 8 hours).',
    )
    weekday_multiplier = fields.Float(
        string='Regular OT Multiplier (x Basic)',
        default=2.0,
        required=True,
        tracking=True,
        help='Section 108 of Bangladesh Labour Act 2006 mandates 2.0x (Double) of Basic Salary.',
    )
    holiday_multiplier = fields.Float(
        string='Weekend / Festival Multiplier (x Basic)',
        default=2.0,
        required=True,
        tracking=True,
    )
    min_ot_minutes = fields.Integer(
        string='Minimum Qualifying OT (Minutes)',
        default=30,
        help='Extra duty below this threshold is treated as routine wrap-up rather than billable OT.',
    )
    statutory_daily_cap_hours = fields.Float(
        string='Statutory Daily OT Cap (Hours)',
        default=2.0,
        help='BD Labour Act Sec 100/102: Standard 8h + 2h OT = 10h daily limit (flags audit warning if exceeded).',
    )
    statutory_weekly_cap_hours = fields.Float(
        string='Statutory Weekly OT Cap (Hours)',
        default=12.0,
        help='BD Labour Act Sec 102: 48h normal + 12h OT = 60h weekly ceiling.',
    )
    notes = fields.Text(string='Statutory & Audit Notes')

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)', 'Overtime Policy Code must be unique per Company!'),
    ]


class HrEmployeeOvertimeExt(models.Model):
    _inherit = 'hr.employee'

    dsl_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Payroll Currency',
        readonly=True,
    )
    ot_eligible = fields.Boolean(
        string='Eligible for Overtime (BD 2x Basic)',
        default=True,
        groups='hr.group_hr_user',
        tracking=True,
    )
    ot_policy_id = fields.Many2one(
        'dsl.overtime.policy',
        string='Overtime Policy',
        groups='hr.group_hr_user',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    ot_gross_reference = fields.Monetary(
        string='Current Gross Salary (৳)',
        currency_field='dsl_currency_id',
        groups='hr.group_hr_user',
        tracking=True,
        help='Reference monthly Gross Salary; Basic Salary auto-calculates per Pay Grade % (or syncs with Phase 6 Salary Structure).',
    )
    ot_basic_reference = fields.Monetary(
        string='Current Basic Salary (৳)',
        currency_field='dsl_currency_id',
        compute='_compute_ot_basic_reference',
        store=True,
        readonly=False,
        groups='hr.group_hr_user',
        tracking=True,
        help='Monthly Basic Wage used for statutory `(Basic / 208) * 2.0` Overtime calculation.',
    )
    ot_hourly_rate_display = fields.Monetary(
        string='2x OT Rate / Hour (৳)',
        currency_field='dsl_currency_id',
        compute='_compute_ot_hourly_rate_display',
        groups='hr.group_hr_user',
    )

    @api.depends('ot_gross_reference', 'grade_id', 'grade_id.basic_pct')
    def _compute_ot_basic_reference(self):
        for emp in self.sudo():
            if emp.ot_gross_reference and emp.ot_gross_reference > 0:
                pct = emp.grade_id.basic_pct if (emp.grade_id and emp.grade_id.basic_pct > 0) else 50.0
                emp.ot_basic_reference = round(emp.ot_gross_reference * (pct / 100.0), 2)
            elif not emp.ot_basic_reference:
                emp.ot_basic_reference = 0.0

    def _compute_ot_hourly_rate_display(self):
        Policy = self.env['dsl.overtime.policy'].sudo()
        default_pol = Policy.search([], limit=1)
        for emp in self.sudo():
            pol = emp.ot_policy_id or default_pol
            divisor = pol.monthly_hours_divisor if (pol and pol.monthly_hours_divisor > 0) else 208.0
            mult = pol.weekday_multiplier if (pol and pol.weekday_multiplier > 0) else 2.0
            if emp.ot_eligible and emp.ot_basic_reference > 0:
                emp.ot_hourly_rate_display = round((emp.ot_basic_reference / divisor) * mult, 2)
            else:
                emp.ot_hourly_rate_display = 0.0


class DslOvertimeRequest(models.Model):
    _name = 'dsl.overtime.request'
    _description = 'Bangladesh Statutory Overtime Register (2x Basic)'
    _inherit = ['dsl.company.branch.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'ot_date desc, id desc'

    name = fields.Char(
        string='OT Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        index=True,
        tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    employee_code = fields.Char(related='employee_id.employee_code', store=True, readonly=True)
    department_id = fields.Many2one(
        'hr.department',
        related='employee_id.department_id',
        store=True,
        readonly=True,
    )
    job_id = fields.Many2one(
        'hr.job',
        related='employee_id.job_id',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        store=True,
        readonly=True,
    )

    ot_date = fields.Date(
        string='Overtime Date',
        required=True,
        default=fields.Date.context_today,
        index=True,
        tracking=True,
    )
    ot_type = fields.Selection(
        selection=[
            ('regular', 'Weekday Overtime (2.0x Basic)'),
            ('weekend', 'Weekly Holiday Duty (2.0x Basic)'),
            ('festival', 'Govt / Festival Holiday Duty'),
        ],
        string='Overtime Category',
        default='regular',
        required=True,
        tracking=True,
    )
    policy_id = fields.Many2one(
        'dsl.overtime.policy',
        string='Applied OT Policy',
        required=True,
        default=lambda self: self.env['dsl.overtime.policy'].sudo().search([], limit=1),
    )
    attendance_log_id = fields.Many2one(
        'dsl.attendance.log',
        string='Linked Attendance Record',
        readonly=True,
    )
    attendance_extra_hours = fields.Float(
        string='Logged Extra Hours',
        readonly=True,
        help='Actual extra worked hours detected in Daily Attendance Register.',
    )
    requested_hours = fields.Float(
        string='Requested OT Hours',
        required=True,
        default=2.0,
        tracking=True,
    )
    approved_hours = fields.Float(
        string='Approved Payable Hours',
        default=2.0,
        tracking=True,
    )

    basic_salary_snapshot = fields.Monetary(
        string='Monthly Basic Wage (৳)',
        currency_field='currency_id',
        required=True,
        default=0.0,
        tracking=True,
    )
    divisor_hours = fields.Float(
        string='Divisor Hours',
        compute='_compute_ot_financials',
        store=True,
    )
    ot_multiplier = fields.Float(
        string='Multiplier (x Basic)',
        compute='_compute_ot_financials',
        store=True,
    )
    hourly_basic_rate = fields.Monetary(
        string='1x Basic / Hour (৳)',
        currency_field='currency_id',
        compute='_compute_ot_financials',
        store=True,
    )
    ot_hourly_rate = fields.Monetary(
        string='2x OT Rate / Hour (৳)',
        currency_field='currency_id',
        compute='_compute_ot_financials',
        store=True,
    )
    total_ot_amount = fields.Monetary(
        string='Payable OT Allowance (৳)',
        currency_field='currency_id',
        compute='_compute_ot_financials',
        store=True,
        tracking=True,
    )

    compliance_status = fields.Selection(
        selection=[
            ('compliant', 'Compliant (≤ 2h Daily / ≤ 12h Weekly)'),
            ('extended_compliance', 'Extended OT (> Statutory Cap — Audit Waiver)'),
        ],
        string='BD Labour Act Compliance',
        compute='_compute_ot_financials',
        store=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved for Payroll'),
            ('paid', 'Settled in Payroll'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )
    payslip_settled = fields.Boolean(string='Settled in Payslip', default=False, readonly=True)
    approved_by_id = fields.Many2one('res.users', string='Approved By', readonly=True)
    reason = fields.Text(string='Production / Shipment / Duty Reason')

    _sql_constraints = [
        (
            'emp_ot_date_uniq',
            'unique(employee_id, ot_date)',
            'Only one Overtime Sheet is allowed per Employee per Date!',
        ),
    ]

    @api.constrains('requested_hours', 'approved_hours')
    def _check_positive_hours(self):
        for rec in self:
            if rec.requested_hours <= 0 or rec.approved_hours < 0:
                raise ValidationError(_('Overtime hours must be greater than zero!'))

    @api.onchange('employee_id', 'ot_date')
    def _onchange_employee_populate_ot(self):
        if self.employee_id:
            emp = self.employee_id.sudo()
            self.company_id = emp.company_id or self.env.company
            self.branch_id = emp.branch_id
            if emp.ot_policy_id:
                self.policy_id = emp.ot_policy_id
            if emp.ot_basic_reference:
                self.basic_salary_snapshot = emp.ot_basic_reference
            if self.ot_date:
                log = self.env['dsl.attendance.log'].sudo().search([
                    ('employee_id', '=', emp.id),
                    ('attendance_date', '=', self.ot_date),
                ], limit=1)
                if log:
                    self.attendance_log_id = log.id
                    self.attendance_extra_hours = log.extra_hours
                    if log.extra_hours > 0:
                        self.requested_hours = log.extra_hours
                        self.approved_hours = log.extra_hours

    @api.onchange('requested_hours')
    def _onchange_requested_sync_approved(self):
        if self.state == 'draft' and self.requested_hours > 0:
            self.approved_hours = self.requested_hours

    @api.depends(
        'basic_salary_snapshot', 'approved_hours', 'ot_type',
        'policy_id', 'policy_id.monthly_hours_divisor',
        'policy_id.weekday_multiplier', 'policy_id.holiday_multiplier',
        'policy_id.statutory_daily_cap_hours'
    )
    def _compute_ot_financials(self):
        for rec in self:
            pol = rec.policy_id
            divisor = pol.monthly_hours_divisor if (pol and pol.monthly_hours_divisor > 0) else 208.0
            mult = (
                (pol.holiday_multiplier if rec.ot_type in ('weekend', 'festival') else pol.weekday_multiplier)
                if pol else 2.0
            )
            daily_cap = pol.statutory_daily_cap_hours if (pol and pol.statutory_daily_cap_hours > 0) else 2.0

            base_hr = round((rec.basic_salary_snapshot or 0.0) / divisor, 2)
            ot_hr = round(base_hr * mult, 2)
            amt = round((rec.approved_hours or 0.0) * ot_hr, 2)

            rec.divisor_hours = divisor
            rec.ot_multiplier = mult
            rec.hourly_basic_rate = base_hr
            rec.ot_hourly_rate = ot_hr
            rec.total_ot_amount = amt

            if rec.ot_type == 'regular' and (rec.approved_hours or 0.0) > daily_cap:
                rec.compliance_status = 'extended_compliance'
            else:
                rec.compliance_status = 'compliant'

    @api.model_create_multi
    def create(self, vals_list):
        Employee = self.env['hr.employee'].sudo()
        AttLog = self.env['dsl.attendance.log'].sudo()
        default_pol = self.env['dsl.overtime.policy'].sudo().search([], limit=1)

        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.overtime.request') or _('New')
            if vals.get('employee_id'):
                emp = Employee.browse(vals['employee_id'])
                if not vals.get('company_id') and emp.company_id:
                    vals['company_id'] = emp.company_id.id
                if not vals.get('branch_id') and emp.branch_id:
                    vals['branch_id'] = emp.branch_id.id
                if not vals.get('policy_id'):
                    vals['policy_id'] = (emp.ot_policy_id or default_pol).id
                if not vals.get('basic_salary_snapshot') and emp.ot_basic_reference:
                    vals['basic_salary_snapshot'] = emp.ot_basic_reference
                if vals.get('ot_date') and not vals.get('attendance_log_id'):
                    log = AttLog.search([
                        ('employee_id', '=', emp.id),
                        ('attendance_date', '=', vals['ot_date']),
                    ], limit=1)
                    if log:
                        vals['attendance_log_id'] = log.id
                        vals['attendance_extra_hours'] = log.extra_hours
            if 'approved_hours' not in vals and vals.get('requested_hours'):
                vals['approved_hours'] = vals['requested_hours']
        return super().create(vals_list)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_by_id': self.env.user.id,
        })

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    @api.model
    def action_auto_extract_from_attendance(self):
        """Scan recent 30 days of `dsl.attendance.log` (within user's accessible companies & branches)
        and auto-create Draft 2x Overtime Requests for qualifying extra hours!"""
        cutoff = fields.Date.context_today(self) - timedelta(days=30)
        AttLog = self.env['dsl.attendance.log']  # Respects current user's Multi-Company & Branch ir.rule!
        logs = AttLog.search([
            ('attendance_date', '>=', cutoff),
            ('extra_hours', '>=', 0.5),
        ])
        created = 0
        for log in logs:
            emp = log.employee_id.sudo()
            if not emp.ot_eligible:
                continue
            pol = emp.ot_policy_id or self.env['dsl.overtime.policy'].sudo().search([], limit=1)
            min_hrs = ((pol.min_ot_minutes if pol else 30) / 60.0)
            if log.extra_hours < min_hrs:
                continue
            exists = self.sudo().search([
                ('employee_id', '=', emp.id),
                ('ot_date', '=', log.attendance_date),
            ], limit=1)
            if exists:
                continue
            is_holiday_ot = (log.status in ('holiday', 'off_day') or log.attendance_date.weekday() == 4)
            self.create({
                'employee_id': emp.id,
                'company_id': log.company_id.id,
                'branch_id': log.branch_id.id if log.branch_id else False,
                'ot_date': log.attendance_date,
                'ot_type': 'weekend' if is_holiday_ot else 'regular',
                'attendance_log_id': log.id,
                'attendance_extra_hours': log.extra_hours,
                'requested_hours': log.extra_hours,
                'approved_hours': log.extra_hours,
                'basic_salary_snapshot': emp.ot_basic_reference or 15000.0,
                'reason': f"Auto-detected {log.extra_hours}h extra duty from Daily Attendance ({log.name}).",
            })
            created += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('BD 2x Overtime Extraction'),
                'message': _('Generated %s new Overtime Sheet(s) from Daily Attendance logs.') % created,
                'type': 'success' if created else 'info',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

