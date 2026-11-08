# -*- coding: utf-8 -*-
import calendar
import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


def _default_next_month_first(record=None):
    today = fields.Date.context_today(record) if record is not None else fields.Date.today()
    if today.month == 12:
        return datetime.date(today.year + 1, 1, 1)
    return datetime.date(today.year, today.month + 1, 1)


def _add_months(dt, months):
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


class DslLoanPolicy(models.Model):
    _name = 'dsl.loan.policy'
    _description = 'Employee Loan & Salary Advance Policy'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    name = fields.Char(string='Loan / Advance Policy Name', required=True, tracking=True)
    code = fields.Char(string='Policy Code', required=True, tracking=True)
    loan_type = fields.Selection(
        selection=[
            ('salary_advance', 'Monthly Salary Advance (অগ্রিম বেতন)'),
            ('personal_loan', 'Employee Personal Loan (ব্যক্তিগত ঋণ)'),
            ('pf_loan', 'Provident Fund Loan (পিএফ ঋণ)'),
            ('festival_advance', 'Festival / Eid Advance (উৎসব অগ্রিম)'),
            ('emergency_medical', 'Emergency Medical / Family Loan (জরুরি চিকিৎসা ঋণ)'),
        ],
        string='Facility Category',
        default='personal_loan',
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one('res.company', string='Company (Blank = Group Policy)')
    max_basic_multiple = fields.Float(
        string='Max Multiple of Basic Salary (x)',
        default=3.0,
        help='Maximum loan cap as a multiple of Employee Monthly Basic Salary (e.g. 3.0 = up to 3x Basic). Set 0 for no multiple cap.',
    )
    max_fixed_cap = fields.Float(string='Maximum Fixed Ceiling (৳)', default=500000.0)
    max_installments = fields.Integer(string='Max Installment Months', default=24, required=True)
    annual_interest_pct = fields.Float(
        string='Annual Service / Interest Rate (%)',
        default=0.0,
        help='0% for interest-free Shariah/HR benevolent loans or advances; >0% for flat annual rate.',
    )
    notes = fields.Text(string='Eligibility & Policy Terms')


def _default_loan_policy(record=None):
    env = record.env if record is not None else None
    if not env:
        return False
    pol = env['dsl.loan.policy'].sudo().search(
        [('active', '=', True), ('loan_type', '=', 'personal_loan')],
        order='sequence, id',
        limit=1,
    )
    if not pol:
        pol = env['dsl.loan.policy'].sudo().search([('active', '=', True)], order='sequence, id', limit=1)
    return pol.id if pol else False


class DslEmployeeLoan(models.Model):
    _name = 'dsl.employee.loan'
    _description = 'Employee Loan & Salary Advance Application'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'

    name = fields.Char(
        string='Loan Ref.',
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
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        store=True,
        readonly=True,
    )

    policy_id = fields.Many2one(
        'dsl.loan.policy',
        string='Loan / Advance Policy',
        required=True,
        default=_default_loan_policy,
        tracking=True,
    )
    loan_type = fields.Selection(
        related='policy_id.loan_type',
        string='Loan Category',
        store=True,
        readonly=True,
    )
    request_date = fields.Date(
        string='Application Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    deduction_start_date = fields.Date(
        string='EMI Start Month',
        required=True,
        default=_default_next_month_first,
        tracking=True,
    )
    disbursed_date = fields.Date(string='Disbursed Date', readonly=True)

    current_basic_ref = fields.Monetary(
        string='Employee Current Basic (৳)',
        currency_field='currency_id',
        compute='_compute_employee_basic_ref',
    )
    principal_amount = fields.Monetary(
        string='Loan / Advance Principal (৳)',
        currency_field='currency_id',
        required=True,
        default=20000.0,
        tracking=True,
    )
    interest_rate_pct = fields.Float(
        string='Annual Interest (%)',
        default=0.0,
        tracking=True,
    )
    installment_months = fields.Integer(
        string='Number of Installments (Months)',
        required=True,
        default=10,
        tracking=True,
    )

    total_interest_amount = fields.Monetary(
        string='Total Interest (৳)',
        currency_field='currency_id',
        compute='_compute_loan_financials',
        store=True,
    )
    total_payable = fields.Monetary(
        string='Total Repayable (৳)',
        currency_field='currency_id',
        compute='_compute_loan_financials',
        store=True,
    )
    emi_amount = fields.Monetary(
        string='Monthly Installment / EMI (৳)',
        currency_field='currency_id',
        compute='_compute_loan_financials',
        store=True,
    )
    total_paid = fields.Monetary(
        string='Total Recovered (৳)',
        currency_field='currency_id',
        compute='_compute_repayment_balance',
        store=True,
    )
    balance_amount = fields.Monetary(
        string='Outstanding Balance (৳)',
        currency_field='currency_id',
        compute='_compute_repayment_balance',
        store=True,
    )

    installment_ids = fields.One2many(
        'dsl.loan.installment',
        'loan_id',
        string='Monthly EMI Amortization Schedule',
    )
    reason = fields.Text(string='Purpose / Justification')
    approved_by_id = fields.Many2one('res.users', string='Approved By', readonly=True)

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'HR / Finance Approved'),
            ('disbursed', 'Active / Disbursed'),
            ('settled', 'Fully Settled'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )

    @api.depends('company_id', 'branch_id', 'branch_id.accounting_company_id')
    def _compute_accounting_entity(self):
        for rec in self:
            if rec.branch_id and rec.branch_id.accounting_company_id:
                rec.accounting_company_id = rec.branch_id.accounting_company_id.id
            else:
                rec.accounting_company_id = rec.company_id.id if rec.company_id else False

    @api.depends('employee_id')
    def _compute_employee_basic_ref(self):
        Comp = self.env['dsl.employee.compensation'].sudo()
        for rec in self:
            if rec.employee_id:
                pkg = Comp.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('state', '=', 'active'),
                ], order='effective_from desc, id desc', limit=1)
                rec.current_basic_ref = pkg.basic_salary if pkg else 0.0
            else:
                rec.current_basic_ref = 0.0

    @api.depends('principal_amount', 'interest_rate_pct', 'installment_months')
    def _compute_loan_financials(self):
        for rec in self:
            months = max(rec.installment_months or 1, 1)
            principal = max(rec.principal_amount or 0.0, 0.0)
            interest = round(principal * ((rec.interest_rate_pct or 0.0) / 100.0) * (months / 12.0), 2)
            tot = round(principal + interest, 2)
            rec.total_interest_amount = interest
            rec.total_payable = tot
            rec.emi_amount = round(tot / months, 2)

    @api.depends('total_payable', 'installment_ids.emi_amount', 'installment_ids.is_paid')
    def _compute_repayment_balance(self):
        for rec in self:
            paid = round(sum(rec.installment_ids.filtered(lambda i: i.is_paid).mapped('emi_amount')), 2)
            rec.total_paid = paid
            rec.balance_amount = round(max((rec.total_payable or 0.0) - paid, 0.0), 2)

    @api.onchange('policy_id')
    def _onchange_policy_defaults(self):
        if self.policy_id:
            self.interest_rate_pct = self.policy_id.annual_interest_pct
            if self.installment_months > self.policy_id.max_installments:
                self.installment_months = self.policy_id.max_installments

    @api.onchange('employee_id')
    def _onchange_employee_org(self):
        if self.employee_id:
            self.company_id = self.employee_id.company_id.id
            self.branch_id = self.employee_id.branch_id.id if self.employee_id.branch_id else False

    @api.constrains('principal_amount', 'installment_months', 'policy_id')
    def _check_policy_limits(self):
        for rec in self:
            if rec.principal_amount <= 0:
                raise ValidationError(_('Loan / Advance Principal Amount must be greater than zero!'))
            if rec.installment_months <= 0:
                raise ValidationError(_('Installment Months must be at least 1!'))
            if rec.policy_id:
                if rec.installment_months > rec.policy_id.max_installments:
                    raise ValidationError(_(
                        'Installment tenure (%s months) exceeds policy maximum (%s months) for %s!'
                    ) % (rec.installment_months, rec.policy_id.max_installments, rec.policy_id.name))
                if rec.policy_id.max_fixed_cap > 0 and rec.principal_amount > rec.policy_id.max_fixed_cap:
                    raise ValidationError(_(
                        'Requested amount (৳%s) exceeds maximum fixed ceiling (৳%s) for %s!'
                    ) % (rec.principal_amount, rec.policy_id.max_fixed_cap, rec.policy_id.name))

    @api.model_create_multi
    def create(self, vals_list):
        Employee = self.env['hr.employee'].sudo()
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.employee.loan') or _('New')
            if vals.get('employee_id'):
                emp = Employee.browse(vals['employee_id'])
                if not vals.get('company_id') and emp.company_id:
                    vals['company_id'] = emp.company_id.id
                if not vals.get('branch_id') and emp.branch_id:
                    vals['branch_id'] = emp.branch_id.id
        return super().create(vals_list)

    def action_compute_installments(self):
        Installment = self.env['dsl.loan.installment'].sudo()
        for rec in self:
            if rec.installment_ids.filtered(lambda i: i.is_paid):
                raise UserError(_('Cannot regenerate full schedule after installments have already been recovered!'))
            rec.installment_ids.unlink()
            months = max(rec.installment_months or 1, 1)
            start_dt = rec.deduction_start_date or _default_next_month_first(rec)
            prin_each = round(rec.principal_amount / months, 2)
            int_each = round(rec.total_interest_amount / months, 2)
            rem_prin = rec.principal_amount
            rem_int = rec.total_interest_amount

            lines = []
            for idx in range(months):
                due_dt = _add_months(start_dt, idx)
                if idx == months - 1:
                    p_part = round(rem_prin, 2)
                    i_part = round(rem_int, 2)
                else:
                    p_part = prin_each
                    i_part = int_each
                    rem_prin -= p_part
                    rem_int -= i_part
                lines.append({
                    'loan_id': rec.id,
                    'sequence': idx + 1,
                    'due_date': due_dt,
                    'principal_part': p_part,
                    'interest_part': i_part,
                    'emi_amount': round(p_part + i_part, 2),
                })
            if lines:
                Installment.create(lines)

    def action_submit(self):
        for rec in self:
            if not rec.installment_ids:
                rec.action_compute_installments()
            rec.write({'state': 'submitted'})

    def action_approve(self):
        for rec in self:
            if not rec.installment_ids:
                rec.action_compute_installments()
            rec.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
            })

    def action_disburse(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.installment_ids:
                rec.action_compute_installments()
            rec.write({
                'state': 'disbursed',
                'disbursed_date': today,
            })

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class DslLoanInstallment(models.Model):
    _name = 'dsl.loan.installment'
    _description = 'Employee Loan Monthly Installment (EMI)'
    _order = 'due_date asc, sequence asc, id asc'

    sequence = fields.Integer(string='#', default=1)
    loan_id = fields.Many2one(
        'dsl.employee.loan',
        string='Loan Reference',
        required=True,
        ondelete='cascade',
        index=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        related='loan_id.employee_id',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='loan_id.currency_id',
        readonly=True,
    )
    due_date = fields.Date(string='Deduction Date', required=True, index=True)
    principal_part = fields.Monetary(string='Principal (৳)', currency_field='currency_id', default=0.0)
    interest_part = fields.Monetary(string='Interest (৳)', currency_field='currency_id', default=0.0)
    emi_amount = fields.Monetary(string='Installment EMI (৳)', currency_field='currency_id', required=True)
    skip_month = fields.Boolean(
        string='Defer / Skip Month',
        default=False,
        help='Check to defer this month\'s deduction (e.g. during Eid month or approved hardship).',
    )
    is_paid = fields.Boolean(string='Recovered', default=False, readonly=True)
    payslip_id = fields.Many2one('dsl.payslip', string='Recovered in Payslip', readonly=True)
    paid_date = fields.Date(string='Recovered Date', readonly=True)


class DslPayslipLoanHook(models.Model):
    _inherit = 'dsl.payslip'

    loan_installment_ids = fields.Many2many(
        'dsl.loan.installment',
        string='Linked Loan Installments',
        readonly=True,
        copy=False,
    )

    def _get_extra_benefit_lines(self):
        res = super()._get_extra_benefit_lines()
        Installment = self.env['dsl.loan.installment'].sudo()
        due_lines = Installment.search([
            ('loan_id.employee_id', '=', self.employee_id.id),
            ('loan_id.state', '=', 'disbursed'),
            ('is_paid', '=', False),
            ('skip_month', '=', False),
            ('due_date', '>=', self.date_from),
            ('due_date', '<=', self.date_to),
        ])
        self.loan_installment_ids = [(6, 0, due_lines.ids)]
        if due_lines:
            adv_lines = due_lines.filtered(lambda d: d.loan_id.loan_type == 'salary_advance')
            reg_lines = due_lines - adv_lines
            if adv_lines:
                res.append({
                    'sequence': 162,
                    'code': 'ADVANCE',
                    'name': f"Salary Advance Recovery ({', '.join(adv_lines.mapped('loan_id.name'))})",
                    'category': 'deduction',
                    'amount': round(sum(adv_lines.mapped('emi_amount')), 2),
                })
            if reg_lines:
                res.append({
                    'sequence': 164,
                    'code': 'LOAN',
                    'name': f"Loan Installment / EMI ({', '.join(reg_lines.mapped('loan_id.name'))})",
                    'category': 'deduction',
                    'amount': round(sum(reg_lines.mapped('emi_amount')), 2),
                })
        return res

    def action_mark_paid(self):
        res = super().action_mark_paid()
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.loan_installment_ids:
                unpaid = rec.loan_installment_ids.sudo().filtered(lambda i: not i.is_paid)
                if unpaid:
                    unpaid.write({
                        'is_paid': True,
                        'payslip_id': rec.id,
                        'paid_date': today,
                    })
                    for ln in unpaid.mapped('loan_id'):
                        ln._compute_repayment_balance()
                        if ln.balance_amount <= 0.01:
                            ln.write({'state': 'settled'})
        return res


class HrEmployeeLoanExt(models.Model):
    _inherit = 'hr.employee'

    dsl_loan_count = fields.Integer(
        string='Loans & Advances',
        compute='_compute_dsl_loan_count',
        groups='hr.group_hr_user',
    )

    def _compute_dsl_loan_count(self):
        Loan = self.env['dsl.employee.loan'].sudo()
        for emp in self:
            emp.dsl_loan_count = Loan.search_count([('employee_id', '=', emp.id)])

    def action_view_dsl_loans(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Loans & Advances',
            'res_model': 'dsl.employee.loan',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
