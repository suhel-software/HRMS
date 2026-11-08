# -*- coding: utf-8 -*-
import base64
import calendar
import csv
import datetime
import io
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


def _default_month_start(record=None):
    today = fields.Date.context_today(record) if record is not None else fields.Date.today()
    return today.replace(day=1)


def _default_month_end(record=None):
    today = fields.Date.context_today(record) if record is not None else fields.Date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    return today.replace(day=last_day)


class DslPayslipRun(models.Model):
    _name = 'dsl.payslip.run'
    _description = 'Monthly Payroll Batch & Bank Advice Sheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    name = fields.Char(
        string='Batch Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
    )
    batch_title = fields.Char(
        string='Payroll Batch Title',
        required=True,
        default=lambda self: f"Monthly Salary Sheet — {fields.Date.today().strftime('%B %Y')}",
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
        string='Branch / Factory Plant (Optional)',
        domain="[('company_id', '=', company_id)]",
        index=True,
    )
    accounting_company_id = fields.Many2one(
        'res.company',
        string='COA / Books of Account Entity',
        compute='_compute_accounting_entity',
        store=True,
        help='Automatically resolves to the Branch Separate/Shared COA entity or Legal Company COA.',
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department Filter (Optional)',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        store=True,
        readonly=True,
    )

    date_from = fields.Date(
        string='Period Start',
        required=True,
        default=_default_month_start,
        tracking=True,
    )
    date_to = fields.Date(
        string='Period End',
        required=True,
        default=_default_month_end,
        tracking=True,
    )

    payslip_ids = fields.One2many(
        'dsl.payslip',
        'batch_id',
        string='Generated Employee Payslips',
    )
    payslip_count = fields.Integer(
        string='Employees',
        compute='_compute_batch_totals',
        store=True,
    )
    total_gross = fields.Monetary(
        string='Total Gross & Additions (৳)',
        currency_field='currency_id',
        compute='_compute_batch_totals',
        store=True,
    )
    total_tds = fields.Monetary(
        string='Total NBR TDS (৳)',
        currency_field='currency_id',
        compute='_compute_batch_totals',
        store=True,
    )
    total_deductions = fields.Monetary(
        string='Total Deductions (৳)',
        currency_field='currency_id',
        compute='_compute_batch_totals',
        store=True,
    )
    total_net_payable = fields.Monetary(
        string='Total Net Disbursement (৳)',
        currency_field='currency_id',
        compute='_compute_batch_totals',
        store=True,
    )
    total_employer_contributions = fields.Monetary(
        string='Employer Contributions (৳)',
        currency_field='currency_id',
        compute='_compute_batch_totals',
        store=True,
    )
    total_ctc_cost = fields.Monetary(
        string='Total Payroll CTC (৳)',
        currency_field='currency_id',
        compute='_compute_batch_totals',
        store=True,
    )

    bank_advice_csv_file = fields.Binary(string='BEFTN / MFS Advice Sheet (CSV)', readonly=True, attachment=True)
    bank_advice_csv_filename = fields.Char(string='Advice Filename', readonly=True)
    disbursement_bank_note = fields.Char(
        string='Source Bank Account / Ref.',
        help='e.g. City Bank Corporate A/C #1402938471 — Gulshan Avenue Branch',
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('computed', 'Computed'),
            ('approved', 'Approved'),
            ('paid', 'Disbursed / Paid'),
            ('cancelled', 'Cancelled'),
        ],
        string='Batch Status',
        default='draft',
        required=True,
        tracking=True,
    )
    notes = fields.Text(string='Payroll & Audit Remarks')

    @api.depends('company_id', 'branch_id', 'branch_id.accounting_company_id')
    def _compute_accounting_entity(self):
        for rec in self:
            if rec.branch_id and rec.branch_id.accounting_company_id:
                rec.accounting_company_id = rec.branch_id.accounting_company_id.id
            else:
                rec.accounting_company_id = rec.company_id.id if rec.company_id else False

    @api.depends(
        'payslip_ids.gross_payable',
        'payslip_ids.tds_deducted',
        'payslip_ids.total_deductions',
        'payslip_ids.net_payable',
        'payslip_ids.employer_contribution_total',
        'payslip_ids.total_ctc_cost',
        'payslip_ids.state',
    )
    def _compute_batch_totals(self):
        for rec in self:
            active_slips = rec.payslip_ids.filtered(lambda s: s.state != 'cancelled')
            rec.payslip_count = len(active_slips)
            rec.total_gross = round(sum(active_slips.mapped('gross_payable')), 2)
            rec.total_tds = round(sum(active_slips.mapped('tds_deducted')), 2)
            rec.total_deductions = round(sum(active_slips.mapped('total_deductions')), 2)
            rec.total_net_payable = round(sum(active_slips.mapped('net_payable')), 2)
            rec.total_employer_contributions = round(sum(active_slips.mapped('employer_contribution_total')), 2)
            rec.total_ctc_cost = round(sum(active_slips.mapped('total_ctc_cost')), 2)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.payslip.run') or _('New')
        return super().create(vals_list)

    def action_generate_batch_payslips(self):
        Payslip = self.env['dsl.payslip'].sudo()
        Comp = self.env['dsl.employee.compensation'].sudo()
        Employee = self.env['hr.employee'].sudo()

        for batch in self:
            emp_dom = [('active', '=', True), ('company_id', '=', batch.company_id.id)]
            if batch.branch_id:
                emp_dom.append(('branch_id', '=', batch.branch_id.id))
            if batch.department_id:
                emp_dom.append(('department_id', '=', batch.department_id.id))
            employees = Employee.search(emp_dom)
            if not employees:
                raise UserError(_('No active employees found for the selected Company / Branch / Department!'))

            for emp in employees:
                active_pkg = Comp.search([
                    ('employee_id', '=', emp.id),
                    ('state', '=', 'active'),
                ], order='effective_from desc, id desc', limit=1)
                if not active_pkg:
                    continue

                existing = Payslip.search([
                    ('employee_id', '=', emp.id),
                    ('date_from', '=', batch.date_from),
                    ('date_to', '=', batch.date_to),
                    ('state', '!=', 'cancelled'),
                ], limit=1)
                if existing:
                    existing.batch_id = batch.id
                    existing.action_compute_sheet()
                else:
                    slip = Payslip.create({
                        'employee_id': emp.id,
                        'company_id': emp.company_id.id,
                        'branch_id': emp.branch_id.id if emp.branch_id else False,
                        'compensation_id': active_pkg.id,
                        'batch_id': batch.id,
                        'date_from': batch.date_from,
                        'date_to': batch.date_to,
                    })
                    slip.action_compute_sheet()

            batch.write({'state': 'computed'})
            batch.message_post(
                body=_(
                    'Payroll Batch computed: %s payslip(s) generated, Total Net Payable: ৳%s.'
                ) % (batch.payslip_count, f"{batch.total_net_payable:,.2f}"),
                subtype_xmlid='mail.mt_note',
                email_from=self.env.user.email_formatted or f'"{self.env.user.name}" <noreply@dsl-hrms.local>',
            )

    def action_approve_batch(self):
        for batch in self:
            for slip in batch.payslip_ids.filtered(lambda s: s.state in ('draft', 'computed')):
                slip.action_approve()
            batch.write({'state': 'approved'})

    def action_mark_paid(self):
        for batch in self:
            for slip in batch.payslip_ids.filtered(lambda s: s.state in ('computed', 'approved')):
                slip.action_mark_paid()
            batch.write({'state': 'paid'})

    def action_export_bank_advice_csv(self):
        """Generates an Excel-ready UTF-8-BOM BEFTN & MFS Bank Advice CSV and triggers instant download."""
        self.ensure_one()
        slips = self.payslip_ids.filtered(lambda s: s.state != 'cancelled' and s.net_payable > 0)
        if not slips:
            raise UserError(_('Generate and compute payslips first before exporting the Bank Advice Sheet!'))

        buf = io.StringIO()
        # UTF-8 BOM so Microsoft Excel renders Bengali characters & Taka symbols cleanly
        buf.write('\ufeff')
        writer = csv.writer(buf)
        writer.writerow([
            'SL',
            'Payslip No',
            'Employee ID',
            'Employee Name',
            'Company',
            'Branch / Plant',
            'COA Entity',
            'Disbursement Channel',
            'Bank / MFS Provider',
            'Bank Branch',
            '9-Digit BEFTN Routing No',
            'Account / Wallet No',
            'Gross Payable (BDT)',
            'NBR TDS (BDT)',
            'Total Deductions (BDT)',
            'Net Salary Payable (BDT)',
            'Narration',
        ])

        month_lbl = self.date_from.strftime('%b %Y')
        for idx, sl in enumerate(slips, start=1):
            emp = sl.employee_id.sudo()
            provider = (
                sl.bank_name
                if sl.payment_method in ('bank', 'mixed')
                else (dict(emp._fields['mfs_provider'].selection).get(sl.mfs_provider, 'MFS') if sl.payment_method == 'mfs' else 'Cash')
            )
            acc_no = sl.bank_account_no if sl.payment_method in ('bank', 'mixed') else (sl.mfs_account_no or 'CASH')
            writer.writerow([
                idx,
                sl.name,
                emp.employee_code or '',
                emp.name or '',
                sl.company_id.name or '',
                sl.branch_id.name if sl.branch_id else '',
                sl.accounting_company_id.name if sl.accounting_company_id else '',
                sl.payment_method.upper() if sl.payment_method else 'BANK',
                provider or '',
                emp.salary_bank_branch or '',
                sl.bank_routing_no or '',
                acc_no,
                f"{sl.gross_payable:.2f}",
                f"{sl.tds_deducted:.2f}",
                f"{sl.total_deductions:.2f}",
                f"{sl.net_payable:.2f}",
                f"Salary {month_lbl} - {emp.employee_code or emp.name}",
            ])

        csv_bytes = buf.getvalue().encode('utf-8')
        fname = f"BEFTN_Bank_Advice_{self.name}_{self.date_from.strftime('%Y_%m')}.csv"
        self.write({
            'bank_advice_csv_file': base64.b64encode(csv_bytes),
            'bank_advice_csv_filename': fname,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=dsl.payslip.run&id={self.id}&field=bank_advice_csv_file&filename_field=bank_advice_csv_filename&download=true',
            'target': 'self',
        }


class DslPayslip(models.Model):
    _name = 'dsl.payslip'
    _description = 'Employee Monthly Digital Payslip (Bangladesh)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    name = fields.Char(
        string='Payslip No.',
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
    accounting_company_id = fields.Many2one(
        'res.company',
        string='COA / Books Entity',
        compute='_compute_accounting_entity',
        store=True,
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
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        store=True,
        readonly=True,
    )

    batch_id = fields.Many2one(
        'dsl.payslip.run',
        string='Payroll Batch',
        ondelete='set null',
        index=True,
    )
    compensation_id = fields.Many2one(
        'dsl.employee.compensation',
        string='Salary Package',
        domain="[('employee_id', '=', employee_id)]",
        tracking=True,
    )
    structure_id = fields.Many2one(
        'dsl.salary.structure',
        related='compensation_id.structure_id',
        string='Applied Structure',
        store=True,
        readonly=True,
    )
    odoo_contract_id = fields.Many2one(
        'hr.contract',
        string='Odoo HR Contract',
        ondelete='set null',
        help='Automatically linked native Odoo hr.contract record.',
    )

    date_from = fields.Date(
        string='Period From',
        required=True,
        default=_default_month_start,
        index=True,
        tracking=True,
    )
    date_to = fields.Date(
        string='Period To',
        required=True,
        default=_default_month_end,
        index=True,
        tracking=True,
    )
    payroll_month_label = fields.Char(
        string='Salary Month',
        compute='_compute_payroll_month_label',
        store=True,
    )

    # Attendance, Leave & Overtime Snapshot
    calendar_days = fields.Integer(string='Month Days', readonly=True, default=30)
    present_days = fields.Float(string='Present Days', readonly=True, default=0.0)
    paid_leave_days = fields.Float(string='Paid Leave Days', readonly=True, default=0.0)
    unpaid_lwp_days = fields.Float(string='Unpaid Leave (LWP)', readonly=True, default=0.0)
    absent_days = fields.Float(string='Absent Days', readonly=True, default=0.0)
    late_count = fields.Integer(string='Late Arrivals', readonly=True, default=0)
    late_deduction_days = fields.Float(string='Late Penalty Days', readonly=True, default=0.0)
    ot_hours = fields.Float(string='Approved OT Hours', readonly=True, default=0.0)
    ot_amount = fields.Monetary(string='2x OT Allowance (৳)', currency_field='currency_id', readonly=True, default=0.0)
    night_shift_days = fields.Integer(string='Night Shifts', readonly=True, default=0)
    night_shift_amount = fields.Monetary(string='Night Allowance (৳)', currency_field='currency_id', readonly=True, default=0.0)

    # Manual Adjustments
    arrear_addition = fields.Monetary(
        string='Arrear / Special Addition (৳)',
        currency_field='currency_id',
        default=0.0,
        tracking=True,
    )
    other_deduction = fields.Monetary(
        string='Other / Canteen Deduction (৳)',
        currency_field='currency_id',
        default=0.0,
        tracking=True,
    )
    manual_tds_override = fields.Monetary(
        string='Manual TDS Override (৳)',
        currency_field='currency_id',
        default=0.0,
        help='If > 0, overrides automatic NBR Income Tax calculation for this month.',
    )

    # Computed Totals from line_ids
    line_ids = fields.One2many(
        'dsl.payslip.line',
        'payslip_id',
        string='All Payslip & CTC Lines',
    )
    salary_line_ids = fields.One2many(
        'dsl.payslip.line',
        'payslip_id',
        domain=[('category', 'in', ('earning', 'variable_earning', 'deduction'))],
        string='Employee Earnings & Deductions',
    )
    employer_benefit_line_ids = fields.One2many(
        'dsl.payslip.line',
        'payslip_id',
        domain=[('category', 'in', ('employer_contribution', 'employer_benefit'))],
        string='Employer Contributions & Perquisites',
    )
    contract_gross = fields.Monetary(
        string='Contract Gross (৳)',
        currency_field='currency_id',
        compute='_compute_payslip_totals',
        store=True,
    )
    total_additions = fields.Monetary(
        string='Variable Additions (৳)',
        currency_field='currency_id',
        compute='_compute_payslip_totals',
        store=True,
    )
    gross_payable = fields.Monetary(
        string='Total Gross Payable (৳)',
        currency_field='currency_id',
        compute='_compute_payslip_totals',
        store=True,
    )
    tds_deducted = fields.Monetary(
        string='NBR Income Tax / TDS (৳)',
        currency_field='currency_id',
        compute='_compute_payslip_totals',
        store=True,
    )
    total_deductions = fields.Monetary(
        string='Total Employee Deductions (৳)',
        currency_field='currency_id',
        compute='_compute_payslip_totals',
        store=True,
    )
    net_payable = fields.Monetary(
        string='Net Salary Payable (৳)',
        currency_field='currency_id',
        compute='_compute_payslip_totals',
        store=True,
        tracking=True,
    )
    employer_contribution_total = fields.Monetary(
        string='Employer Contributions (৳)',
        currency_field='currency_id',
        compute='_compute_payslip_totals',
        store=True,
    )
    perquisite_benefit_total = fields.Monetary(
        string='Non-Cash Perquisites (৳)',
        currency_field='currency_id',
        compute='_compute_payslip_totals',
        store=True,
    )
    total_ctc_cost = fields.Monetary(
        string='Total Cost to Company / CTC (৳)',
        currency_field='currency_id',
        compute='_compute_payslip_totals',
        store=True,
    )

    # Disbursement Snapshot (Bank BEFTN / bKash / Nagad / Rocket / Cash)
    payment_method = fields.Selection(
        selection=[
            ('bank', 'Bank Transfer (BEFTN / NPSB)'),
            ('mfs', 'Mobile Banking (bKash / Nagad / Rocket)'),
            ('cash', 'Cash Disbursement'),
            ('mixed', 'Split (Bank + Cash)'),
        ],
        string='Payment Mode',
        default='bank',
        tracking=True,
    )
    bank_name = fields.Char(string='Bank Name')
    bank_routing_no = fields.Char(string='BEFTN Routing No.')
    bank_account_no = fields.Char(string='Bank A/C No.')
    mfs_provider = fields.Char(string='MFS Provider')
    mfs_account_no = fields.Char(string='MFS Wallet No.')

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('computed', 'Computed'),
            ('approved', 'Approved'),
            ('paid', 'Paid / Disbursed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )
    paid_date = fields.Date(string='Disbursed Date', readonly=True)
    notes = fields.Text(string='Payslip Remarks')

    @api.depends('company_id', 'branch_id', 'branch_id.accounting_company_id')
    def _compute_accounting_entity(self):
        for rec in self:
            if rec.branch_id and rec.branch_id.accounting_company_id:
                rec.accounting_company_id = rec.branch_id.accounting_company_id.id
            else:
                rec.accounting_company_id = rec.company_id.id if rec.company_id else False

    @api.depends('date_from')
    def _compute_payroll_month_label(self):
        for rec in self:
            rec.payroll_month_label = rec.date_from.strftime('%B %Y') if rec.date_from else ''

    @api.depends('line_ids.amount', 'line_ids.category', 'line_ids.code')
    def _compute_payslip_totals(self):
        for rec in self:
            earn = sum(rec.line_ids.filtered(lambda l: l.category == 'earning').mapped('amount'))
            var_add = sum(rec.line_ids.filtered(lambda l: l.category == 'variable_earning').mapped('amount'))
            ded = sum(rec.line_ids.filtered(lambda l: l.category == 'deduction').mapped('amount'))
            tds = sum(rec.line_ids.filtered(lambda l: l.code in ('INCOME_TAX', 'TDS')).mapped('amount'))
            emp_contrib = sum(rec.line_ids.filtered(lambda l: l.category == 'employer_contribution').mapped('amount'))
            perq = sum(rec.line_ids.filtered(lambda l: l.category == 'employer_benefit').mapped('amount'))
            rec.contract_gross = round(earn, 2)
            rec.total_additions = round(var_add, 2)
            rec.gross_payable = round(earn + var_add, 2)
            rec.tds_deducted = round(tds, 2)
            rec.total_deductions = round(ded, 2)
            rec.net_payable = round(max((earn + var_add) - ded, 0.0), 2)
            rec.employer_contribution_total = round(emp_contrib, 2)
            rec.perquisite_benefit_total = round(perq, 2)
            rec.total_ctc_cost = round((earn + var_add) + emp_contrib + perq, 2)

    @api.onchange('employee_id')
    def _onchange_employee_populate(self):
        if self.employee_id:
            emp = self.employee_id.sudo()
            self.company_id = emp.company_id.id
            self.branch_id = emp.branch_id.id if emp.branch_id else False
            pkg = self.env['dsl.employee.compensation'].sudo().search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'active'),
            ], order='effective_from desc, id desc', limit=1)
            if pkg:
                self.compensation_id = pkg.id
            self._snapshot_disbursement_profile()

    def _snapshot_disbursement_profile(self):
        for rec in self:
            emp = rec.employee_id.sudo()
            if not emp:
                continue
            rec.payment_method = emp.payment_method or 'bank'
            rec.bank_name = emp.salary_bank_name or False
            rec.bank_routing_no = emp.salary_bank_routing_no or False
            rec.bank_account_no = emp.salary_bank_account_no or False
            rec.mfs_provider = emp.mfs_provider or False
            rec.mfs_account_no = emp.mfs_account_no or False

    def _get_monthly_tds_deduction(self):
        """Plug-and-Play hook overridden by DSL_HRMS_tax_bd for automatic NBR Income Tax (AIT/TDS)."""
        self.ensure_one()
        if self.manual_tds_override and self.manual_tds_override > 0:
            return round(float(self.manual_tds_override), 2)
        if self.compensation_id and self.compensation_id.tds_monthly_estimate > 0:
            return round(float(self.compensation_id.tds_monthly_estimate), 2)
        return 0.0

    def _get_extra_benefit_lines(self):
        """Plug-and-Play hook for Phase 7 (Loan EMI, PF Contribution, Festival Bonus) & Phase 10 (Canteen).
        Returns list of dicts: {'sequence': int, 'code': str, 'name': str, 'category': str, 'amount': float}.
        """
        self.ensure_one()
        return []

    def action_compute_sheet(self):
        Comp = self.env['dsl.employee.compensation'].sudo()
        Head = self.env['dsl.salary.head'].sudo()
        head_map = {h.code: h for h in Head.search([])}

        for rec in self:
            emp = rec.employee_id.sudo()
            if not rec.compensation_id:
                pkg = Comp.search([
                    ('employee_id', '=', emp.id),
                    ('state', '=', 'active'),
                ], order='effective_from desc, id desc', limit=1)
                if not pkg:
                    raise UserError(_(
                        'No Active Salary Package found for %s! Please assign an Employee Salary Package first.'
                    ) % emp.name)
                rec.compensation_id = pkg.id

            rec._snapshot_disbursement_profile()
            pkg = rec.compensation_id
            structure = pkg.structure_id
            if not rec.odoo_contract_id and 'hr.contract' in self.env:
                if getattr(pkg, 'odoo_contract_id', False):
                    rec.odoo_contract_id = pkg.odoo_contract_id.id
                else:
                    oc = self.env['hr.contract'].sudo().search([
                        ('employee_id', '=', emp.id),
                    ], order='date_start desc, id desc', limit=1)
                    if oc:
                        rec.odoo_contract_id = oc.id

            cal_days = (rec.date_to - rec.date_from).days + 1
            present_cnt = 0.0
            absent_cnt = 0.0
            late_cnt = 0
            paid_lv_days = 0.0
            unpaid_lwp_days = 0.0
            ot_hrs = 0.0
            ot_amt = 0.0
            night_cnt = 0
            night_amt = 0.0

            # 1. Pull Leave Days from Phase 5 DSL_HRMS_leave (if installed)
            if 'dsl.leave.request' in self.env:
                leaves = self.env['dsl.leave.request'].sudo().search([
                    ('employee_id', '=', emp.id),
                    ('state', '=', 'approved'),
                    ('date_from', '<=', rec.date_to),
                    ('date_to', '>=', rec.date_from),
                ])
                for lv in leaves:
                    # Clip days strictly within [date_from, date_to]
                    eff_start = max(lv.date_from, rec.date_from)
                    eff_end = min(lv.date_to, rec.date_to)
                    if lv.is_half_day:
                        days_in_period = 0.5
                    else:
                        cnt = 0
                        cur = eff_start
                        while cur <= eff_end:
                            if lv.leave_type_id.allow_sandwich_rule or not lv._is_non_working_day(emp, cur):
                                cnt += 1
                            cur += datetime.timedelta(days=1)
                        days_in_period = float(cnt)
                    if lv.leave_type_id.is_paid:
                        paid_lv_days += days_in_period
                    else:
                        unpaid_lwp_days += days_in_period

            # 2. Pull Attendance Logs from Phase 4 DSL_HRMS_attendance (if installed)
            if 'dsl.attendance.log' in self.env:
                att_logs = self.env['dsl.attendance.log'].sudo().search([
                    ('employee_id', '=', emp.id),
                    ('attendance_date', '>=', rec.date_from),
                    ('attendance_date', '<=', rec.date_to),
                ])
                present_cnt = float(len(att_logs.filtered(lambda a: a.status in ('present', 'late'))))
                present_cnt += 0.5 * len(att_logs.filtered(lambda a: a.status == 'half_day'))
                absent_cnt = float(len(att_logs.filtered(lambda a: a.status == 'absent')))
                late_cnt = len(att_logs.filtered(lambda a: a.is_late))

            late_rule = structure.late_days_per_deduction if structure else 0
            late_ded_days = float(late_cnt // late_rule) if (late_rule and late_rule > 0) else 0.0

            # 3. Pull Approved 2x Basic Overtime from Phase 4 DSL_HRMS_overtime (if installed)
            if 'dsl.overtime.request' in self.env:
                ots = self.env['dsl.overtime.request'].sudo().search([
                    ('employee_id', '=', emp.id),
                    ('ot_date', '>=', rec.date_from),
                    ('ot_date', '<=', rec.date_to),
                    ('state', 'in', ('approved', 'paid')),
                ])
                ot_hrs = round(sum(ots.mapped('approved_hours')), 2)
                ot_amt = round(sum(ots.mapped('total_ot_amount')), 2)

            # 4. Pull Night Shift Allowance from Phase 4 DSL_HRMS_shift_roster (if installed)
            if 'dsl.shift.roster' in self.env and 'dsl.attendance.log' in self.env:
                rosters = self.env['dsl.shift.roster'].sudo().search([
                    ('employee_id', '=', emp.id),
                    ('roster_date', '>=', rec.date_from),
                    ('roster_date', '<=', rec.date_to),
                    ('is_off_day', '=', False),
                    ('shift_id.night_allowance_bdt', '>', 0),
                ])
                for rst in rosters:
                    attended = self.env['dsl.attendance.log'].sudo().search_count([
                        ('employee_id', '=', emp.id),
                        ('attendance_date', '=', rst.roster_date),
                        ('status', 'in', ('present', 'late')),
                    ])
                    if attended:
                        night_cnt += 1
                        night_amt += rst.shift_id.night_allowance_bdt

            rec.write({
                'calendar_days': cal_days,
                'present_days': present_cnt,
                'paid_leave_days': paid_lv_days,
                'unpaid_lwp_days': unpaid_lwp_days,
                'absent_days': absent_cnt,
                'late_count': late_cnt,
                'late_deduction_days': late_ded_days,
                'ot_hours': ot_hrs,
                'ot_amount': ot_amt,
                'night_shift_days': night_cnt,
                'night_shift_amount': round(night_amt, 2),
            })

            # 5. Build Payslip Breakdown Lines
            rec.line_ids.unlink()
            lines_vals = []

            def _add_line(seq, code, default_name, cat, amt, override_label=False):
                amt = round(float(amt or 0.0), 2)
                if amt <= 0:
                    return
                hd = head_map.get(code)
                lines_vals.append({
                    'payslip_id': rec.id,
                    'sequence': seq,
                    'head_id': hd.id if hd else False,
                    'code': code,
                    'name': default_name if (override_label or not hd) else hd.name,
                    'category': cat,
                    'amount': amt,
                })

            # Pillar 1: Core Gross Components
            _add_line(10, 'BASIC', 'Basic Salary', 'earning', pkg.basic_salary)
            _add_line(20, 'HRA', 'House Rent Allowance', 'earning', pkg.house_rent)
            _add_line(30, 'MEDICAL', 'Medical Allowance', 'earning', pkg.medical_allowance)
            _add_line(40, 'CONVEYANCE', 'Conveyance Allowance', 'earning', pkg.conveyance_allowance)
            fifth_code = 'SPECIAL' if (structure and structure.formula_mode == 'corporate_pct') else 'FOOD'
            _add_line(50, fifth_code, 'Food / Special Allowance', 'earning', pkg.food_special_allowance)

            # Package Additional Fixed & Custom Monthly Allowances
            if hasattr(pkg, '_get_package_additional_allowance_items'):
                for seq_a, code_a, label_a, amt_a in pkg._get_package_additional_allowance_items():
                    _add_line(seq_a, code_a, label_a, 'earning', amt_a, override_label=True)

            # Variable Additions (Bonus, Overtime, Night Shift, Arrear)
            if (
                structure
                and structure.enable_attendance_bonus
                and pkg.attendance_bonus_amount > 0
                and absent_cnt == 0
                and unpaid_lwp_days == 0
                and late_cnt == 0
            ):
                _add_line(65, 'ATTENDANCE_BONUS', 'Attendance Bonus (100% Punctuality)', 'variable_earning', pkg.attendance_bonus_amount, override_label=True)

            if ot_amt > 0:
                _add_line(70, 'OVERTIME', f'Overtime Allowance ({ot_hrs}h @ BD 2x Basic)', 'variable_earning', ot_amt, override_label=True)
            if night_amt > 0:
                _add_line(80, 'NIGHT_SHIFT', f'Night Shift Allowance ({night_cnt} Shifts)', 'variable_earning', night_amt, override_label=True)
            if rec.arrear_addition > 0:
                _add_line(90, 'ARREAR', 'Salary Arrear / Special Addition', 'variable_earning', rec.arrear_addition, override_label=True)

            # Pillar 2: Employee Salary Deductions
            eff_gross = pkg.total_gross_package if hasattr(pkg, 'total_gross_package') and pkg.total_gross_package else pkg.gross_salary
            if unpaid_lwp_days > 0:
                lwp_ded_amt = round((eff_gross / 30.0) * unpaid_lwp_days, 2)
                _add_line(108, 'UNPAID_LEAVE', f'Leave Without Pay / LWP ({unpaid_lwp_days}d)', 'deduction', lwp_ded_amt, override_label=True)
            if absent_cnt > 0:
                abs_ded_amt = round((eff_gross / 30.0) * absent_cnt, 2)
                _add_line(110, 'ABSENCE', f'Unauthorized Absence Deduction ({absent_cnt}d)', 'deduction', abs_ded_amt, override_label=True)

            if late_ded_days > 0:
                late_ded_amt = round((pkg.basic_salary / 30.0) * late_ded_days, 2)
                _add_line(120, 'LATE_ADJUSTMENT', f'Late Attendance Adjustment ({late_cnt} Lates = {late_ded_days}d Basic)', 'deduction', late_ded_amt, override_label=True)

            # NBR Monthly Income Tax (TDS / AIT) via Plug-and-Play Hook
            tds_amt = rec._get_monthly_tds_deduction()
            if tds_amt > 0:
                _add_line(130, 'INCOME_TAX', 'Income Tax at Source (NBR TDS / AIT)', 'deduction', tds_amt, override_label=True)

            # Phase 7 / Phase 10 Extra Hook Lines (PF, Loan EMI, Festival Bonus, Canteen)
            extra_hook_lines = rec._get_extra_benefit_lines()
            extra_codes = {e.get('code') for e in extra_hook_lines if e.get('code')}
            for extra in extra_hook_lines:
                _add_line(
                    extra.get('sequence', 150),
                    extra.get('code', 'ADJ'),
                    extra.get('name', 'Adjustment'),
                    extra.get('category', 'deduction'),
                    extra.get('amount', 0.0),
                    override_label=True,
                )

            # Package Recurring Monthly & Custom Deductions (PF, Welfare, Insurance, Transport, Loan, etc.)
            if hasattr(pkg, '_get_package_recurring_deduction_items'):
                for seq_d, code_d, label_d, amt_d in pkg._get_package_recurring_deduction_items():
                    if code_d not in extra_codes:
                        _add_line(seq_d, code_d, label_d, 'deduction', amt_d, override_label=True)

            if rec.other_deduction > 0:
                _add_line(175, 'OTHER_DEDUCTION', 'Other Authorized Deduction', 'deduction', rec.other_deduction, override_label=True)

            # Bangladesh Stamp Act Revenue Stamp (৳10 when Net Payable >= ৳400)
            pre_stamp_gross = sum(v['amount'] for v in lines_vals if v['category'] in ('earning', 'variable_earning'))
            pre_stamp_ded = sum(v['amount'] for v in lines_vals if v['category'] == 'deduction')
            stamp_enabled = pkg.apply_stamp_deduction if hasattr(pkg, 'apply_stamp_deduction') else (structure and structure.apply_revenue_stamp)
            if stamp_enabled and (pre_stamp_gross - pre_stamp_ded) >= 400.0:
                stamp_fee = (
                    pkg.stamp_deduction_amount
                    if (hasattr(pkg, 'stamp_deduction_amount') and pkg.stamp_deduction_amount > 0)
                    else ((structure.revenue_stamp_amount if structure else 10.0) or 10.0)
                )
                _add_line(190, 'STAMP', 'Revenue Stamp (BD Stamp Act)', 'deduction', stamp_fee, override_label=True)

            # Pillar 3: Employer Contributions & Non-Cash Perquisites (Tracked in CTC, NEVER deducted from Net Salary!)
            if hasattr(pkg, '_get_package_employer_and_benefit_items'):
                for seq_e, code_e, label_e, cat_e, amt_e in pkg._get_package_employer_and_benefit_items():
                    if code_e not in extra_codes:
                        _add_line(seq_e, code_e, label_e, cat_e, amt_e, override_label=True)

            if lines_vals:
                self.env['dsl.payslip.line'].sudo().create(lines_vals)

            if rec.state == 'draft':
                rec.state = 'computed'

    @api.model_create_multi
    def create(self, vals_list):
        Employee = self.env['hr.employee'].sudo()
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.payslip') or _('New')
            if vals.get('employee_id'):
                emp = Employee.browse(vals['employee_id'])
                if not vals.get('company_id') and emp.company_id:
                    vals['company_id'] = emp.company_id.id
                if not vals.get('branch_id') and emp.branch_id:
                    vals['branch_id'] = emp.branch_id.id
        return super().create(vals_list)

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_mark_paid(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.write({'state': 'paid', 'paid_date': today})
            if 'dsl.overtime.request' in self.env:
                ots = self.env['dsl.overtime.request'].sudo().search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('ot_date', '>=', rec.date_from),
                    ('ot_date', '<=', rec.date_to),
                    ('state', '=', 'approved'),
                ])
                if ots:
                    ots.write({'state': 'paid', 'payslip_settled': True})
            rec.message_post(
                body=_(
                    'Payslip %s disbursed (%s): Net Payable ৳%s.'
                ) % (rec.name, rec.payment_method, f"{rec.net_payable:,.2f}"),
                subtype_xmlid='mail.mt_note',
                email_from=self.env.user.email_formatted or f'"{self.env.user.name}" <noreply@dsl-hrms.local>',
            )

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_print_payslip(self):
        return self.env.ref('DSL_HRMS_payroll_bd.action_report_dsl_payslip').report_action(self)


class DslPayslipLine(models.Model):
    _name = 'dsl.payslip.line'
    _description = 'Payslip Earning / Deduction Component Line'
    _order = 'sequence asc, id asc'

    payslip_id = fields.Many2one(
        'dsl.payslip',
        string='Payslip',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)
    head_id = fields.Many2one('dsl.salary.head', string='Salary Head')
    code = fields.Char(string='Code', required=True)
    name = fields.Char(string='Description', required=True)
    category = fields.Selection(
        selection=[
            ('earning', 'Gross Earning'),
            ('variable_earning', 'Variable Addition'),
            ('deduction', 'Employee Deduction'),
            ('employer_contribution', 'Employer Contribution (CTC)'),
            ('employer_benefit', 'Non-Cash Benefit / Perquisite'),
        ],
        string='Category',
        required=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='payslip_id.currency_id',
        readonly=True,
    )
    amount = fields.Monetary(string='Amount (৳)', currency_field='currency_id', required=True)


class HrEmployeePayslipExt(models.Model):
    _inherit = 'hr.employee'

    dsl_payslip_ids = fields.One2many(
        'dsl.payslip',
        'employee_id',
        string='Monthly Payslips',
        groups='hr.group_hr_user',
    )
    dsl_payslip_count = fields.Integer(
        string='Payslips',
        compute='_compute_dsl_payslip_count',
        groups='hr.group_hr_user',
    )

    def _compute_dsl_payslip_count(self):
        Payslip = self.env['dsl.payslip'].sudo()
        for emp in self:
            emp.dsl_payslip_count = Payslip.search_count([
                ('employee_id', '=', emp.id),
                ('state', '!=', 'cancelled'),
            ])

    def action_view_dsl_payslips(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Payslips',
            'res_model': 'dsl.payslip',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {
                'default_employee_id': self.id,
                'default_company_id': self.company_id.id,
                'default_branch_id': self.branch_id.id if self.branch_id else False,
            },
        }

