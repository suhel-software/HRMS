# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class DslLeaveType(models.Model):
    _name = 'dsl.leave.type'
    _description = 'DSL HRMS Statutory & Corporate Leave Policy'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    name = fields.Char(string='Leave Type Name', required=True, tracking=True)
    name_bn = fields.Char(string='ছুটির নাম (বাংলায়)', tracking=True)
    code = fields.Char(string='Short Code', required=True, tracking=True, help='e.g. CL, SL, EL, ML, PL, CPL, LWP')

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        help='Leave blank to share across all Group companies, or select a specific company.',
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Specific Branch / Plant',
        domain="[('company_id', '=', company_id)]",
        help='Optional branch-specific leave rule.',
    )

    statutory_section = fields.Char(
        string='BD Labour Act Reference',
        help='e.g. Bangladesh Labour Act 2006 - Section 115 (Casual Leave)',
    )
    leave_category = fields.Selection(
        selection=[
            ('casual', 'Casual Leave (CL - Sec 115)'),
            ('sick', 'Sick / Medical Leave (SL - Sec 116)'),
            ('earned', 'Earned / Annual Leave (EL - Sec 117)'),
            ('maternity', 'Maternity Leave (ML - Sec 46)'),
            ('paternity', 'Paternity Leave (Corporate)'),
            ('compensatory', 'Compensatory / Festival Off'),
            ('unpaid', 'Leave Without Pay (LWP)'),
            ('special', 'Special / Study / Pilgrimage Leave'),
        ],
        string='Statutory Category',
        default='casual',
        required=True,
        tracking=True,
    )

    is_paid = fields.Boolean(string='Paid Leave (Full Pay)', default=True, tracking=True)
    requires_allocation = fields.Boolean(
        string='Enforce Yearly Quota Balance',
        default=True,
        tracking=True,
        help='If enabled, leave requests validate against allocated yearly entitlement.',
    )
    default_annual_days = fields.Float(
        string='Default Yearly Quota (Days)',
        default=10.0,
        tracking=True,
    )
    allow_half_day = fields.Boolean(string='Allow Half-Day Leave (0.5d)', default=True)
    allow_sandwich_rule = fields.Boolean(
        string='Apply Sandwich Rule (Count Weekends/Holidays Inside Leave)',
        default=False,
        help='If disabled, weekly offs & gazetted holidays falling within the leave range are excluded from leave deduction. '
             'Enable for continuous statutory leaves like 112-Day Maternity Leave.',
    )

    # Carry-Forward & Encashment (BD Labour Act Sec 117 Earned Leave)
    allow_carry_forward = fields.Boolean(
        string='Allow Yearly Carry-Forward',
        default=False,
        tracking=True,
    )
    max_carry_forward_days = fields.Float(
        string='Max Carry-Forward Cap (Days)',
        default=40.0,
        help='BD Labour Act Sec 117: 40 days for shop/commercial/industrial staff, up to 60 days for factory workers.',
    )
    allow_encashment = fields.Boolean(
        string='Allow Leave Encashment',
        default=False,
        help='Feeds Phase 6/8 Annual Leave Encashment & Final Settlement.',
    )

    # Policy Safeguards & Eligibility
    max_consecutive_days = fields.Float(
        string='Max Consecutive Days per Request',
        default=0.0,
        help='Set > 0 to cap single-stretch applications (e.g. 3 days for Casual Leave unless HR overrides).',
    )
    requires_medical_doc = fields.Boolean(
        string='Require Medical Certificate Above Threshold',
        default=False,
    )
    medical_doc_after_days = fields.Float(
        string='Medical Doc Required After (Days)',
        default=3.0,
    )
    gender_restriction = fields.Selection(
        selection=[
            ('all', 'All Employees'),
            ('female', 'Female Employees Only (e.g. Maternity)'),
            ('male', 'Male Employees Only (e.g. Paternity)'),
        ],
        string='Gender Eligibility',
        default='all',
        required=True,
    )
    probation_eligible = fields.Boolean(
        string='Allowed During Probation',
        default=True,
        help='Uncheck if only Confirmed / Permanent employees can avail this leave type.',
    )
    color = fields.Integer(string='Color Index', default=4)
    policy_notes = fields.Text(string='HR Policy Guidelines')
    odoo_leave_type_id = fields.Many2one(
        'hr.leave.type',
        string='Odoo Time Off Type',
        ondelete='set null',
        help='Automatically synchronized native Odoo hr.leave.type record (hr_holidays).',
    )

    _sql_constraints = [
        (
            'code_company_uniq',
            'unique(code, company_id)',
            'Leave Type Short Code must be unique per Company!',
        ),
    ]

    def _ensure_odoo_leave_type(self):
        if self.env.context.get('skip_dsl_leave_sync') or 'hr.leave.type' not in self.env:
            return
        HrLeaveType = self.env['hr.leave.type'].sudo().with_context(skip_dsl_leave_sync=True)
        for rec in self.sudo():
            vals = {
                'name': rec.name,
                'company_id': rec.company_id.id if rec.company_id else False,
                'requires_allocation': 'no',
                'leave_validation_type': 'no_validation',
                'request_unit': 'half_day' if rec.allow_half_day else 'day',
                'color': rec.color or 4,
            }
            if 'dsl_leave_type_id' in HrLeaveType._fields:
                vals['dsl_leave_type_id'] = rec.id
            if rec.odoo_leave_type_id:
                try:
                    rec.odoo_leave_type_id.sudo().with_context(skip_dsl_leave_sync=True).write(vals)
                except Exception:
                    pass
            else:
                existing = HrLeaveType.search([('name', '=ilike', rec.name.strip())], limit=1)
                if existing:
                    try:
                        existing.write(vals)
                    except Exception:
                        pass
                    rec.with_context(skip_dsl_leave_sync=True).write({'odoo_leave_type_id': existing.id})
                else:
                    try:
                        created = HrLeaveType.create(vals)
                        rec.with_context(skip_dsl_leave_sync=True).write({'odoo_leave_type_id': created.id})
                    except Exception:
                        pass

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_odoo_leave_type()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_dsl_leave_sync') and any(k in vals for k in ('name', 'color', 'company_id')):
            self._ensure_odoo_leave_type()
        return res


class HrLeaveTypeDslExt(models.Model):
    _inherit = 'hr.leave.type'

    dsl_leave_type_id = fields.Many2one(
        'dsl.leave.type',
        string='DSL Leave Policy',
        ondelete='set null',
    )


class DslLeaveAllocation(models.Model):
    _name = 'dsl.leave.allocation'
    _description = 'Employee Yearly Leave Quota & Balance Ledger'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'leave_year desc, employee_id, leave_type_id'

    name = fields.Char(
        string='Ledger Reference',
        compute='_compute_name',
        store=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
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
        index=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        related='employee_id.department_id',
        string='Department',
        store=True,
        readonly=True,
    )
    leave_type_id = fields.Many2one(
        'dsl.leave.type',
        string='Leave Policy / Type',
        required=True,
        index=True,
        tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    leave_year = fields.Char(
        string='Leave Year',
        required=True,
        default=lambda self: str(fields.Date.today().year),
        index=True,
        tracking=True,
    )

    opening_carry_forward = fields.Float(
        string='Carry-Forward (Prev Year)',
        default=0.0,
        tracking=True,
    )
    allocated_days = fields.Float(
        string='Current Year Quota',
        required=True,
        default=10.0,
        tracking=True,
    )
    total_entitled_days = fields.Float(
        string='Total Entitled Days',
        compute='_compute_balance_metrics',
        store=True,
    )
    taken_days = fields.Float(
        string='Approved / Taken Days',
        compute='_compute_balance_metrics',
        store=True,
    )
    pending_days = fields.Float(
        string='Pending Approval Days',
        compute='_compute_balance_metrics',
        store=True,
    )
    remaining_days = fields.Float(
        string='Available Balance',
        compute='_compute_balance_metrics',
        store=True,
    )

    leave_request_ids = fields.One2many(
        'dsl.leave.request',
        'allocation_id',
        string='Linked Leave Applications',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active Quota'),
            ('closed', 'Year Closed'),
        ],
        string='Quota Status',
        default='active',
        required=True,
        tracking=True,
    )
    notes = fields.Text(string='Allocation Notes')
    odoo_allocation_id = fields.Many2one(
        'hr.leave.allocation',
        string='Odoo Leave Allocation',
        ondelete='set null',
        help='Optional linked Odoo native hr.leave.allocation record.',
    )

    _sql_constraints = [
        (
            'emp_type_year_uniq',
            'unique(employee_id, leave_type_id, leave_year)',
            'Only one Leave Quota record is allowed per Employee, Leave Type, and Year!',
        ),
    ]

    @api.depends('employee_id', 'employee_id.name', 'leave_type_id', 'leave_type_id.code', 'leave_year')
    def _compute_name(self):
        for rec in self:
            emp_name = rec.employee_id.name or _('Employee')
            code = rec.leave_type_id.code or _('LV')
            yr = rec.leave_year or str(fields.Date.today().year)
            rec.name = f"[{yr}] {emp_name} — {code}"

    @api.depends(
        'opening_carry_forward',
        'allocated_days',
        'leave_request_ids.state',
        'leave_request_ids.number_of_days',
    )
    def _compute_balance_metrics(self):
        for rec in self:
            entitled = (rec.opening_carry_forward or 0.0) + (rec.allocated_days or 0.0)
            approved_reqs = rec.leave_request_ids.filtered(lambda r: r.state == 'approved')
            pending_reqs = rec.leave_request_ids.filtered(
                lambda r: r.state not in ('draft', 'approved', 'rejected', 'cancelled')
            )
            taken = sum(approved_reqs.mapped('number_of_days'))
            pending = sum(pending_reqs.mapped('number_of_days'))
            rec.total_entitled_days = round(entitled, 2)
            rec.taken_days = round(taken, 2)
            rec.pending_days = round(pending, 2)
            rec.remaining_days = round(entitled - taken, 2)

    @api.onchange('employee_id')
    def _onchange_employee_sync_org(self):
        if self.employee_id:
            self.company_id = self.employee_id.company_id.id
            self.branch_id = self.employee_id.branch_id.id if self.employee_id.branch_id else False

    @api.onchange('leave_type_id')
    def _onchange_leave_type_default_quota(self):
        if self.leave_type_id and not self.allocated_days:
            self.allocated_days = self.leave_type_id.default_annual_days

    @api.model_create_multi
    def create(self, vals_list):
        Employee = self.env['hr.employee'].sudo()
        for vals in vals_list:
            if vals.get('employee_id'):
                emp = Employee.browse(vals['employee_id'])
                if not vals.get('company_id') and emp.company_id:
                    vals['company_id'] = emp.company_id.id
                if not vals.get('branch_id') and emp.branch_id:
                    vals['branch_id'] = emp.branch_id.id
        return super().create(vals_list)

    def action_activate_quota(self):
        self.write({'state': 'active'})

    def action_close_year(self):
        self.write({'state': 'closed'})


class DslLeaveAllocationBatch(models.Model):
    _name = 'dsl.leave.allocation.batch'
    _description = 'Bulk Annual Leave Quota & Carry-Forward Generator'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Batch Title',
        required=True,
        default=lambda self: f"Annual Leave Quota Allocation — {fields.Date.today().year}",
        tracking=True,
    )
    leave_year = fields.Char(
        string='Target Leave Year',
        required=True,
        default=lambda self: str(fields.Date.today().year),
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Target Company',
        required=True,
        default=lambda self: self.env.company,
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Filter by Branch (Optional)',
        domain="[('company_id', '=', company_id)]",
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Filter by Department (Optional)',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    leave_type_ids = fields.Many2many(
        'dsl.leave.type',
        string='Leave Policies to Allocate',
        required=True,
        domain="[('requires_allocation', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    auto_carry_forward = fields.Boolean(
        string='Auto-Calculate Carry-Forward from Previous Year (Earned Leave)',
        default=True,
        help='Automatically carries forward unused previous-year balance for eligible policies up to max cap.',
    )
    generated_count = fields.Integer(string='Quotas Generated / Updated', readonly=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('generated', 'Allocated'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )

    def action_generate_allocations(self):
        Allocation = self.env['dsl.leave.allocation'].sudo()
        Employee = self.env['hr.employee'].sudo()
        for batch in self:
            emp_domain = [('active', '=', True), ('company_id', '=', batch.company_id.id)]
            if batch.branch_id:
                emp_domain.append(('branch_id', '=', batch.branch_id.id))
            if batch.department_id:
                emp_domain.append(('department_id', '=', batch.department_id.id))
            employees = Employee.search(emp_domain)
            if not employees:
                raise UserError(_('No active employees matched the selected Company / Branch / Department filter!'))

            prev_year = str(int(batch.leave_year) - 1) if batch.leave_year.isdigit() else False
            created_or_updated = 0

            for emp in employees:
                for ltype in batch.leave_type_ids:
                    # Respect gender eligibility (e.g. skip Maternity for male employees)
                    if ltype.gender_restriction == 'female' and emp.gender and emp.gender != 'female':
                        continue
                    if ltype.gender_restriction == 'male' and emp.gender and emp.gender != 'male':
                        continue

                    carry_fwd = 0.0
                    if batch.auto_carry_forward and ltype.allow_carry_forward and prev_year:
                        prev_alloc = Allocation.search([
                            ('employee_id', '=', emp.id),
                            ('leave_type_id', '=', ltype.id),
                            ('leave_year', '=', prev_year),
                        ], limit=1)
                        if prev_alloc and prev_alloc.remaining_days > 0:
                            cap = ltype.max_carry_forward_days or prev_alloc.remaining_days
                            carry_fwd = min(prev_alloc.remaining_days, cap)

                    existing = Allocation.search([
                        ('employee_id', '=', emp.id),
                        ('leave_type_id', '=', ltype.id),
                        ('leave_year', '=', batch.leave_year),
                    ], limit=1)
                    if existing:
                        existing.write({
                            'allocated_days': ltype.default_annual_days,
                            'opening_carry_forward': carry_fwd if carry_fwd else existing.opening_carry_forward,
                            'state': 'active',
                        })
                    else:
                        Allocation.create({
                            'employee_id': emp.id,
                            'company_id': emp.company_id.id,
                            'branch_id': emp.branch_id.id if emp.branch_id else False,
                            'leave_type_id': ltype.id,
                            'leave_year': batch.leave_year,
                            'opening_carry_forward': carry_fwd,
                            'allocated_days': ltype.default_annual_days,
                            'state': 'active',
                        })
                    created_or_updated += 1

            batch.write({
                'generated_count': created_or_updated,
                'state': 'generated',
            })
            batch.message_post(
                body=_(
                    'Bulk Leave Quota Allocation completed for %s: %s quota ledger(s) generated/updated.'
                ) % (batch.leave_year, created_or_updated),
                subtype_xmlid='mail.mt_note',
                email_from=self.env.user.email_formatted or f'"{self.env.user.name}" <noreply@dsl-hrms.local>',
            )


class DslLeaveRequest(models.Model):
    _name = 'dsl.leave.request'
    _description = 'Employee Leave Application'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    name = fields.Char(
        string='Application No.',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        index=True,
        tracking=True,
        default=lambda self: self.env.user.employee_id,
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
        index=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        related='employee_id.department_id',
        string='Department',
        store=True,
        readonly=True,
    )
    job_id = fields.Many2one(
        'hr.job',
        related='employee_id.job_id',
        string='Designation',
        store=True,
        readonly=True,
    )

    leave_type_id = fields.Many2one(
        'dsl.leave.type',
        string='Leave Type',
        required=True,
        tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    leave_category = fields.Selection(
        related='leave_type_id.leave_category',
        string='Statutory Category',
        readonly=True,
    )
    allocation_id = fields.Many2one(
        'dsl.leave.allocation',
        string='Linked Quota Ledger',
        ondelete='set null',
        index=True,
    )

    date_from = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.context_today,
        index=True,
        tracking=True,
    )
    date_to = fields.Date(
        string='End Date',
        required=True,
        default=fields.Date.context_today,
        index=True,
        tracking=True,
    )
    is_half_day = fields.Boolean(
        string='Half-Day Leave (0.5 Day)',
        default=False,
        tracking=True,
    )
    half_day_period = fields.Selection(
        selection=[
            ('first_half', 'First Half (Morning)'),
            ('second_half', 'Second Half (Afternoon)'),
        ],
        string='Half-Day Session',
        default='first_half',
    )

    holiday_excluded_days = fields.Float(
        string='Excluded Weekends / Holidays',
        compute='_compute_duration_days',
        store=True,
    )
    number_of_days = fields.Float(
        string='Net Leave Days',
        compute='_compute_duration_days',
        store=True,
        tracking=True,
    )

    # Non-stored live balance preview (strictly separated from stored compute!)
    available_balance = fields.Float(
        string='Current Available Balance',
        compute='_compute_live_balance',
    )
    balance_after_request = fields.Float(
        string='Projected Balance After Leave',
        compute='_compute_live_balance',
    )

    reason = fields.Text(
        string='Reason / Purpose of Leave',
        required=True,
        tracking=True,
    )
    handover_employee_id = fields.Many2one(
        'hr.employee',
        string='Reliever / Duty Handover To',
        domain="[('company_id', '=', company_id), ('id', '!=', employee_id)]",
        tracking=True,
    )
    emergency_contact_during_leave = fields.Char(
        string='Contact Phone During Leave',
    )
    supporting_document = fields.Binary(
        string='Medical Certificate / Attachment',
        attachment=True,
    )
    supporting_document_name = fields.Char(string='Attachment Filename')

    allow_hr_balance_override = fields.Boolean(
        string='HR Special Quota Override',
        default=False,
        groups='DSL_HRMS_core.group_dsl_hrms_manager',
        help='Allows HR Manager to approve special advance leave even if quota balance is insufficient.',
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Pending Approval'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
        ],
        string='Approval Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )
    approved_by_id = fields.Many2one('res.users', string='Final Approved By', readonly=True, tracking=True)
    approved_date = fields.Datetime(string='Approved On', readonly=True)
    rejection_reason = fields.Char(string='Rejection / Cancellation Note', tracking=True)
    attendance_synced = fields.Boolean(string='Synced to Attendance Register', readonly=True, default=False)
    odoo_leave_id = fields.Many2one(
        'hr.leave',
        string='Odoo Time Off Request',
        ondelete='set null',
        help='Automatically synchronized native Odoo hr.leave record (hr_holidays).',
    )
    odoo_calendar_leave_id = fields.Many2one(
        'resource.calendar.leaves',
        string='Odoo Resource Time Off',
        ondelete='set null',
        help='Automatically synchronized native Odoo resource.calendar.leaves entry.',
    )

    def _is_non_working_day(self, employee, check_date):
        """Hook overridden by DSL_HRMS_holiday for full Branch/Company Weekend & Govt Holiday exclusion.
        Standalone fallback excludes Friday (BD statutory weekly holiday under Sec 103).
        """
        return check_date.weekday() == 4

    @api.depends(
        'date_from',
        'date_to',
        'is_half_day',
        'leave_type_id',
        'leave_type_id.allow_sandwich_rule',
        'employee_id',
        'company_id',
        'branch_id',
    )
    def _compute_duration_days(self):
        for rec in self:
            if not rec.date_from or not rec.date_to or rec.date_to < rec.date_from:
                rec.holiday_excluded_days = 0.0
                rec.number_of_days = 0.0
                continue

            if rec.is_half_day:
                rec.holiday_excluded_days = 0.0
                rec.number_of_days = 0.5
                continue

            total_span = (rec.date_to - rec.date_from).days + 1
            if rec.leave_type_id and rec.leave_type_id.allow_sandwich_rule:
                rec.holiday_excluded_days = 0.0
                rec.number_of_days = float(total_span)
                continue

            excluded = 0
            cursor_dt = rec.date_from
            while cursor_dt <= rec.date_to:
                if rec._is_non_working_day(rec.employee_id, cursor_dt):
                    excluded += 1
                cursor_dt += timedelta(days=1)

            rec.holiday_excluded_days = float(excluded)
            rec.number_of_days = float(max(total_span - excluded, 0))

    @api.depends('employee_id', 'leave_type_id', 'date_from', 'number_of_days', 'state')
    def _compute_live_balance(self):
        Allocation = self.env['dsl.leave.allocation'].sudo()
        for rec in self:
            if not rec.employee_id or not rec.leave_type_id or not rec.leave_type_id.requires_allocation:
                rec.available_balance = 0.0
                rec.balance_after_request = 0.0
                continue
            target_year = str((rec.date_from or fields.Date.today()).year)
            alloc = Allocation.search([
                ('employee_id', '=', rec.employee_id.id),
                ('leave_type_id', '=', rec.leave_type_id.id),
                ('leave_year', '=', target_year),
            ], limit=1)
            avail = alloc.remaining_days if alloc else 0.0
            rec.available_balance = avail
            if rec.state == 'approved':
                rec.balance_after_request = avail
            else:
                rec.balance_after_request = round(avail - (rec.number_of_days or 0.0), 2)

    @api.onchange('employee_id')
    def _onchange_employee_sync_org(self):
        if self.employee_id:
            self.company_id = self.employee_id.company_id.id
            self.branch_id = self.employee_id.branch_id.id if self.employee_id.branch_id else False
            if not self.emergency_contact_during_leave:
                self.emergency_contact_during_leave = self.employee_id.mobile_phone or self.employee_id.work_phone or False

    @api.onchange('is_half_day', 'date_from')
    def _onchange_half_day_sync_dates(self):
        if self.is_half_day and self.date_from:
            self.date_to = self.date_from

    def _find_or_link_allocation(self):
        Allocation = self.env['dsl.leave.allocation'].sudo()
        for rec in self:
            if not rec.employee_id or not rec.leave_type_id or not rec.leave_type_id.requires_allocation:
                rec.allocation_id = False
                continue
            target_year = str((rec.date_from or fields.Date.today()).year)
            alloc = Allocation.search([
                ('employee_id', '=', rec.employee_id.id),
                ('leave_type_id', '=', rec.leave_type_id.id),
                ('leave_year', '=', target_year),
            ], limit=1)
            if not alloc:
                # Auto-provision standard yearly quota ledger for seamless plug-and-play UX
                alloc = Allocation.create({
                    'employee_id': rec.employee_id.id,
                    'company_id': rec.company_id.id,
                    'branch_id': rec.branch_id.id if rec.branch_id else False,
                    'leave_type_id': rec.leave_type_id.id,
                    'leave_year': target_year,
                    'allocated_days': rec.leave_type_id.default_annual_days,
                    'state': 'active',
                })
            rec.allocation_id = alloc.id

    @api.constrains('date_from', 'date_to', 'is_half_day', 'employee_id', 'leave_type_id', 'state')
    def _check_leave_validity_and_overlaps(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_('Leave End Date (%s) cannot be earlier than Start Date (%s)!') % (
                    rec.date_to, rec.date_from
                ))
            if rec.is_half_day:
                if rec.leave_type_id and not rec.leave_type_id.allow_half_day:
                    raise ValidationError(_('Half-day leave is not permitted for %s!') % rec.leave_type_id.name)
                if rec.date_from != rec.date_to:
                    raise ValidationError(_('Half-Day Leave must have the same Start Date and End Date!'))

            if rec.state in ('rejected', 'cancelled'):
                continue

            # Gender eligibility check
            emp = rec.employee_id.sudo()
            ltype = rec.leave_type_id
            if ltype and emp:
                if ltype.gender_restriction == 'female' and emp.gender and emp.gender != 'female':
                    raise ValidationError(_('%s is restricted to Female employees only!') % ltype.name)
                if ltype.gender_restriction == 'male' and emp.gender and emp.gender != 'male':
                    raise ValidationError(_('%s is restricted to Male employees only!') % ltype.name)
                if not ltype.probation_eligible and getattr(emp, 'employment_status', False) == 'probation':
                    raise ValidationError(_(
                        '%s cannot be availed during Probation Period for %s!'
                    ) % (ltype.name, emp.name))

            # Overlapping leave check
            if rec.employee_id and rec.date_from and rec.date_to:
                overlapping = self.sudo().search([
                    ('id', '!=', rec.id),
                    ('employee_id', '=', rec.employee_id.id),
                    ('state', 'not in', ('rejected', 'cancelled')),
                    ('date_from', '<=', rec.date_to),
                    ('date_to', '>=', rec.date_from),
                ], limit=1)
                if overlapping:
                    raise ValidationError(_(
                        'Employee %s already has an overlapping leave application (%s: %s to %s)!'
                    ) % (rec.employee_id.name, overlapping.name, overlapping.date_from, overlapping.date_to))

    def _validate_policy_and_quota_before_submit(self):
        for rec in self:
            if rec.number_of_days <= 0:
                raise ValidationError(_(
                    'Net Leave Days for %s is 0 (selected dates fall entirely on weekly offs or holidays)!'
                ) % rec.name)

            ltype = rec.leave_type_id
            if (
                ltype.max_consecutive_days > 0
                and rec.number_of_days > ltype.max_consecutive_days
                and not rec.allow_hr_balance_override
            ):
                raise ValidationError(_(
                    '%s allows at most %s consecutive day(s) per application (requested %s days). '
                    'Please split the leave or request HR Special Override.'
                ) % (ltype.name, ltype.max_consecutive_days, rec.number_of_days))

            if (
                ltype.requires_medical_doc
                and rec.number_of_days > ltype.medical_doc_after_days
                and not rec.supporting_document
            ):
                raise ValidationError(_(
                    'A Medical Certificate / Supporting Attachment is mandatory for %s exceeding %s days!'
                ) % (ltype.name, ltype.medical_doc_after_days))

            if ltype.requires_allocation:
                rec._find_or_link_allocation()
                if rec.allocation_id and not rec.allow_hr_balance_override:
                    avail = rec.allocation_id.remaining_days
                    if rec.number_of_days > avail:
                        raise ValidationError(_(
                            'Insufficient %s quota for %s! Available: %s day(s), Requested: %s day(s).'
                        ) % (ltype.name, rec.employee_id.name, avail, rec.number_of_days))

    @api.model_create_multi
    def create(self, vals_list):
        Employee = self.env['hr.employee'].sudo()
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.leave.request') or _('New')
            if vals.get('employee_id'):
                emp = Employee.browse(vals['employee_id'])
                if not vals.get('company_id') and emp.company_id:
                    vals['company_id'] = emp.company_id.id
                if not vals.get('branch_id') and emp.branch_id:
                    vals['branch_id'] = emp.branch_id.id
            if vals.get('is_half_day') and vals.get('date_from'):
                vals['date_to'] = vals['date_from']
        records = super().create(vals_list)
        records._find_or_link_allocation()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ('employee_id', 'leave_type_id', 'date_from')):
            self._find_or_link_allocation()
        return res

    def action_submit(self):
        self._validate_policy_and_quota_before_submit()
        self.write({'state': 'submitted'})
        for rec in self:
            rec.message_post(
                body=_(
                    'Leave application submitted for %s day(s) of %s (%s to %s).'
                ) % (rec.number_of_days, rec.leave_type_id.name, rec.date_from, rec.date_to),
                subtype_xmlid='mail.mt_note',
                email_from=self.env.user.email_formatted or f'"{self.env.user.name}" <noreply@dsl-hrms.local>',
            )

    def _sync_to_odoo_hr_leave(self):
        """Sync approved leave applications to Odoo's native `resource.calendar.leaves` & `hr.leave` (`hr_holidays`)."""
        if self.env.context.get('skip_dsl_leave_sync'):
            return
        CalLeaves = self.env['resource.calendar.leaves'].sudo().with_context(skip_dsl_leave_sync=True) if 'resource.calendar.leaves' in self.env else None
        HrLeave = self.env['hr.leave'].sudo().with_context(skip_dsl_leave_sync=True) if 'hr.leave' in self.env else None
        for rec in self.sudo():
            if rec.state != 'approved' or not rec.employee_id or not rec.date_from or not rec.date_to:
                continue
            dt_from = datetime.combine(rec.date_from, time(3, 0, 0))
            dt_to = datetime.combine(rec.date_to, time(12, 0, 0))
            if CalLeaves is not None and rec.employee_id.resource_id:
                cal_vals = {
                    'name': f"{rec.leave_type_id.name}: {rec.reason or rec.name}",
                    'company_id': rec.company_id.id if rec.company_id else self.env.company.id,
                    'resource_id': rec.employee_id.resource_id.id,
                    'calendar_id': rec.employee_id.resource_calendar_id.id if rec.employee_id.resource_calendar_id else False,
                    'date_from': dt_from,
                    'date_to': dt_to,
                    'time_type': 'leave',
                }
                if rec.odoo_calendar_leave_id:
                    try:
                        rec.odoo_calendar_leave_id.sudo().write(cal_vals)
                    except Exception:
                        pass
                else:
                    try:
                        cl = CalLeaves.create(cal_vals)
                        rec.with_context(skip_dsl_leave_sync=True).write({'odoo_calendar_leave_id': cl.id})
                    except Exception:
                        pass

            if HrLeave is not None and rec.leave_type_id:
                rec.leave_type_id._ensure_odoo_leave_type()
                olt = rec.leave_type_id.odoo_leave_type_id
                if olt and not rec.odoo_leave_id:
                    try:
                        hl = HrLeave.create({
                            'name': rec.reason or rec.name,
                            'employee_id': rec.employee_id.id,
                            'holiday_status_id': olt.id,
                            'request_date_from': rec.date_from,
                            'request_date_to': rec.date_to,
                        })
                        rec.with_context(skip_dsl_leave_sync=True).write({'odoo_leave_id': hl.id})
                    except Exception:
                        pass

    def _sync_approved_leave_to_attendance(self):
        """Automatically marks Daily Attendance Register as On Leave / Half Day when DSL_HRMS_attendance is installed."""
        self._sync_to_odoo_hr_leave()
        if 'dsl.attendance.log' not in self.env:
            return
        AttLog = self.env['dsl.attendance.log'].sudo()
        for rec in self:
            if rec.state != 'approved':
                continue
            target_status = 'half_day' if rec.is_half_day else 'on_leave'
            cursor_dt = rec.date_from
            while cursor_dt <= rec.date_to:
                if rec.is_half_day or rec.leave_type_id.allow_sandwich_rule or not rec._is_non_working_day(rec.employee_id, cursor_dt):
                    existing_log = AttLog.search([
                        ('employee_id', '=', rec.employee_id.id),
                        ('attendance_date', '=', cursor_dt),
                    ], limit=1)
                    note_txt = f"Approved Leave: {rec.name} ({rec.leave_type_id.code})"
                    if existing_log:
                        if not existing_log.check_in:
                            existing_log.write({
                                'status': target_status,
                                'is_manual_status': True,
                                'remarks': note_txt,
                            })
                    else:
                        AttLog.create({
                            'employee_id': rec.employee_id.id,
                            'company_id': rec.company_id.id,
                            'branch_id': rec.branch_id.id if rec.branch_id else False,
                            'attendance_date': cursor_dt,
                            'status': target_status,
                            'is_manual_status': True,
                            'remarks': note_txt,
                        })
                cursor_dt += timedelta(days=1)
            rec.attendance_synced = True

    def _cleanup_cancelled_leave_from_attendance(self):
        for rec in self.sudo():
            if rec.odoo_calendar_leave_id:
                try:
                    rec.odoo_calendar_leave_id.sudo().unlink()
                except Exception:
                    pass
            if rec.odoo_leave_id:
                try:
                    rec.odoo_leave_id.sudo().action_refuse()
                except Exception:
                    pass
        if 'dsl.attendance.log' not in self.env:
            return
        AttLog = self.env['dsl.attendance.log'].sudo()
        for rec in self:
            logs = AttLog.search([
                ('employee_id', '=', rec.employee_id.id),
                ('attendance_date', '>=', rec.date_from),
                ('attendance_date', '<=', rec.date_to),
                ('check_in', '=', False),
                ('status', 'in', ('on_leave', 'half_day')),
            ])
            if logs:
                logs.unlink()
            rec.attendance_synced = False

    def _finalize_leave_approval(self):
        """Final approval hook called directly or by the final step of DSL_HRMS_leave_approval."""
        for rec in self:
            rec._validate_policy_and_quota_before_submit()
            rec.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            rec._sync_approved_leave_to_attendance()
            rec.message_post(
                body=_(
                    'Leave application FINAL APPROVED by %s (%s day(s) deducted from %s).'
                ) % (self.env.user.name, rec.number_of_days, rec.leave_type_id.name),
                subtype_xmlid='mail.mt_note',
                email_from=self.env.user.email_formatted or f'"{self.env.user.name}" <noreply@dsl-hrms.local>',
            )

    def action_approve(self):
        self._finalize_leave_approval()

    def action_reject(self):
        for rec in self:
            if rec.state == 'approved':
                rec._cleanup_cancelled_leave_from_attendance()
            rec.write({'state': 'rejected'})

    def action_cancel(self):
        for rec in self:
            if rec.state == 'approved':
                rec._cleanup_cancelled_leave_from_attendance()
            rec.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft', 'rejection_reason': False})


class HrEmployeeLeaveExt(models.Model):
    _inherit = 'hr.employee'

    dsl_leave_allocation_ids = fields.One2many(
        'dsl.leave.allocation',
        'employee_id',
        string='Yearly Leave Quotas',
        groups='hr.group_hr_user',
    )
    dsl_leave_request_ids = fields.One2many(
        'dsl.leave.request',
        'employee_id',
        string='Leave Applications',
        groups='hr.group_hr_user',
    )
    dsl_leave_count = fields.Integer(
        string='Leaves',
        compute='_compute_dsl_leave_count',
        groups='hr.group_hr_user',
    )

    def _compute_dsl_leave_count(self):
        LeaveReq = self.env['dsl.leave.request'].sudo()
        for emp in self:
            emp.dsl_leave_count = LeaveReq.search_count([
                ('employee_id', '=', emp.id),
                ('state', '=', 'approved'),
            ])

    def action_view_dsl_leaves(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Leave Applications',
            'res_model': 'dsl.leave.request',
            'view_mode': 'list,calendar,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {
                'default_employee_id': self.id,
                'default_company_id': self.company_id.id,
                'default_branch_id': self.branch_id.id if self.branch_id else False,
            },
        }

    def action_quick_apply_leave(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Apply Leave — {self.name}',
            'res_model': 'dsl.leave.request',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_employee_id': self.id,
                'default_company_id': self.company_id.id,
                'default_branch_id': self.branch_id.id if self.branch_id else False,
            },
        }
