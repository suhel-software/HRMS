# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


def _default_pf_policy(record=None):
    env = record.env if record is not None else None
    if not env:
        return False
    pol = env['dsl.pf.policy'].sudo().search([('active', '=', True)], order='id asc', limit=1)
    return pol.id if pol else False


class DslPfPolicy(models.Model):
    _name = 'dsl.pf.policy'
    _description = 'Recognized Provident Fund (PF) Trust Policy'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id asc'

    active = fields.Boolean(default=True)
    name = fields.Char(string='PF Trust Policy Name', required=True, tracking=True)
    code = fields.Char(string='Trust Code', required=True, default='BD-RPF-TRUST')
    company_id = fields.Many2one('res.company', string='Company (Blank = Group Trust)')
    employee_rate_pct = fields.Float(string='Employee Contribution (% of Basic)', default=10.0, required=True)
    employer_rate_pct = fields.Float(string='Employer Contribution (% of Basic)', default=10.0, required=True)
    partial_vesting_years = fields.Float(string='50% Employer Vesting After (Years)', default=2.0)
    full_vesting_years = fields.Float(string='100% Employer Vesting After (Years)', default=5.0)
    declared_profit_rate_pct = fields.Float(
        string='Annual Declared PF Profit / Return (%)',
        default=8.5,
        tracking=True,
    )
    notes = fields.Text(string='PF Trust Deed & NBR Recognition Notes')


class DslPfAccount(models.Model):
    _name = 'dsl.pf.account'
    _description = 'Employee Recognized Provident Fund Member Account'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'membership_date desc, id desc'

    name = fields.Char(
        string='PF Account No.',
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
    department_id = fields.Many2one(
        'hr.department',
        related='employee_id.department_id',
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
        'dsl.pf.policy',
        string='PF Trust Policy',
        required=True,
        default=_default_pf_policy,
        tracking=True,
    )
    membership_date = fields.Date(
        string='PF Membership Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )

    membership_years = fields.Float(
        string='PF Membership Tenure (Yrs)',
        compute='_compute_vesting_and_balances',
    )
    vested_employer_pct = fields.Float(
        string='Vested Employer Share (%)',
        compute='_compute_vesting_and_balances',
    )

    employee_contribution_total = fields.Monetary(
        string='Employee Contribution (৳)',
        currency_field='currency_id',
        compute='_compute_pf_totals',
        store=True,
    )
    employer_contribution_total = fields.Monetary(
        string='Employer 50-50 Contribution (৳)',
        currency_field='currency_id',
        compute='_compute_pf_totals',
        store=True,
    )
    profit_credited_total = fields.Monetary(
        string='Accumulated Trust Profit (৳)',
        currency_field='currency_id',
        compute='_compute_pf_totals',
        store=True,
    )
    payout_settled_total = fields.Monetary(
        string='Settled / Paid Out (৳)',
        currency_field='currency_id',
        compute='_compute_pf_totals',
        store=True,
    )
    total_fund_balance = fields.Monetary(
        string='Total Accumulated PF Balance (৳)',
        currency_field='currency_id',
        compute='_compute_pf_totals',
        store=True,
        tracking=True,
    )
    vested_payable_balance = fields.Monetary(
        string='Net Vested Payable Balance (৳)',
        currency_field='currency_id',
        compute='_compute_vesting_and_balances',
    )

    ledger_line_ids = fields.One2many(
        'dsl.pf.ledger.line',
        'pf_account_id',
        string='PF Contribution & Profit Ledger',
    )
    state = fields.Selection(
        selection=[
            ('active', 'Active Member'),
            ('frozen', 'Frozen'),
            ('settled', 'Final Settled & Closed'),
        ],
        string='Account Status',
        default='active',
        required=True,
        tracking=True,
    )
    notes = fields.Text(string='Nominee & Trust Remarks')

    _sql_constraints = [
        ('emp_pf_uniq', 'unique(employee_id, company_id)', 'Each employee can have only one PF Member Account per Company!'),
    ]

    @api.depends(
        'ledger_line_ids.entry_type',
        'ledger_line_ids.employee_amount',
        'ledger_line_ids.employer_amount',
        'ledger_line_ids.profit_amount',
    )
    def _compute_pf_totals(self):
        for rec in self:
            inflows = rec.ledger_line_ids.filtered(lambda l: l.entry_type != 'settlement_payout')
            payouts = rec.ledger_line_ids.filtered(lambda l: l.entry_type == 'settlement_payout')
            emp_sum = round(sum(inflows.mapped('employee_amount')), 2)
            empr_sum = round(sum(inflows.mapped('employer_amount')), 2)
            prof_sum = round(sum(inflows.mapped('profit_amount')), 2)
            paid_out = round(sum(payouts.mapped('total_amount')), 2)
            rec.employee_contribution_total = emp_sum
            rec.employer_contribution_total = empr_sum
            rec.profit_credited_total = prof_sum
            rec.payout_settled_total = paid_out
            rec.total_fund_balance = round(max((emp_sum + empr_sum + prof_sum) - paid_out, 0.0), 2)

    @api.depends(
        'membership_date',
        'policy_id',
        'employee_contribution_total',
        'employer_contribution_total',
        'profit_credited_total',
        'payout_settled_total',
    )
    def _compute_vesting_and_balances(self):
        today = fields.Date.context_today(self)
        for rec in self:
            yrs = ((today - rec.membership_date).days / 365.25) if rec.membership_date else 0.0
            yrs = max(round(yrs, 2), 0.0)
            pol = rec.policy_id
            if pol:
                if yrs >= (pol.full_vesting_years or 5.0):
                    vest_pct = 100.0
                elif yrs >= (pol.partial_vesting_years or 2.0):
                    vest_pct = 50.0
                else:
                    vest_pct = 0.0
            else:
                vest_pct = 100.0
            rec.membership_years = yrs
            rec.vested_employer_pct = vest_pct
            vested_empr = round((rec.employer_contribution_total or 0.0) * (vest_pct / 100.0), 2)
            vested_prof = round((rec.profit_credited_total or 0.0) * (0.5 + 0.5 * (vest_pct / 100.0)), 2)
            rec.vested_payable_balance = round(
                max((rec.employee_contribution_total or 0.0) + vested_empr + vested_prof - (rec.payout_settled_total or 0.0), 0.0),
                2,
            )

    @api.onchange('employee_id')
    def _onchange_employee_populate(self):
        if self.employee_id:
            self.company_id = self.employee_id.company_id.id
            self.branch_id = self.employee_id.branch_id.id if self.employee_id.branch_id else False
            if getattr(self.employee_id, 'joining_date', False):
                self.membership_date = self.employee_id.joining_date

    @api.model_create_multi
    def create(self, vals_list):
        Employee = self.env['hr.employee'].sudo()
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.pf.account') or _('New')
            if vals.get('employee_id'):
                emp = Employee.browse(vals['employee_id'])
                if not vals.get('company_id') and emp.company_id:
                    vals['company_id'] = emp.company_id.id
                if not vals.get('branch_id') and emp.branch_id:
                    vals['branch_id'] = emp.branch_id.id
        return super().create(vals_list)


class DslPfLedgerLine(models.Model):
    _name = 'dsl.pf.ledger.line'
    _description = 'PF Member Contribution & Profit Ledger Line'
    _order = 'entry_date desc, id desc'

    pf_account_id = fields.Many2one(
        'dsl.pf.account',
        string='PF Account',
        required=True,
        ondelete='cascade',
        index=True,
    )
    entry_date = fields.Date(string='Date', required=True, default=fields.Date.context_today, index=True)
    entry_type = fields.Selection(
        selection=[
            ('opening', 'Opening Balance'),
            ('monthly_payroll', 'Monthly Payroll Contribution (50-50)'),
            ('annual_profit', 'Annual Trust Profit Distribution'),
            ('settlement_payout', 'Final Settlement Payout'),
        ],
        string='Entry Type',
        default='monthly_payroll',
        required=True,
    )
    description = fields.Char(string='Narration', required=True)
    currency_id = fields.Many2one(
        'res.currency',
        related='pf_account_id.currency_id',
        readonly=True,
    )
    employee_amount = fields.Monetary(string='Employee Share (৳)', currency_field='currency_id', default=0.0)
    employer_amount = fields.Monetary(string='Employer Share (৳)', currency_field='currency_id', default=0.0)
    profit_amount = fields.Monetary(string='Profit / Interest (৳)', currency_field='currency_id', default=0.0)
    total_amount = fields.Monetary(
        string='Total Entry (৳)',
        currency_field='currency_id',
        compute='_compute_total_amount',
        store=True,
    )
    payslip_id = fields.Many2one('dsl.payslip', string='Source Payslip', readonly=True)
    profit_batch_id = fields.Many2one('dsl.pf.profit.distribution', string='Profit Batch', readonly=True)

    @api.depends('employee_amount', 'employer_amount', 'profit_amount')
    def _compute_total_amount(self):
        for ln in self:
            ln.total_amount = round(
                (ln.employee_amount or 0.0) + (ln.employer_amount or 0.0) + (ln.profit_amount or 0.0), 2
            )


class DslPfProfitDistribution(models.Model):
    _name = 'dsl.pf.profit.distribution'
    _description = 'Annual PF Trust Profit / Return Distribution Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'distribution_date desc, id desc'

    name = fields.Char(
        string='Batch Ref.',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    fiscal_year_label = fields.Char(string='Fiscal Year', required=True, default='FY 2026-2027')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    policy_id = fields.Many2one('dsl.pf.policy', string='PF Trust Policy', required=True, default=_default_pf_policy)
    profit_rate_pct = fields.Float(string='Declared Annual Return (%)', required=True, default=8.5, tracking=True)
    distribution_date = fields.Date(string='Distribution Date', required=True, default=fields.Date.context_today)
    ledger_line_ids = fields.One2many('dsl.pf.ledger.line', 'profit_batch_id', string='Credited Member Profit Entries')
    member_count = fields.Integer(string='Credited Members', compute='_compute_summary', store=True)
    total_profit_distributed = fields.Monetary(
        string='Total Profit Distributed (৳)',
        currency_field='currency_id',
        compute='_compute_summary',
        store=True,
    )
    state = fields.Selection(
        selection=[('draft', 'Draft'), ('posted', 'Credited to Member Accounts')],
        default='draft',
        required=True,
        tracking=True,
    )

    @api.depends('ledger_line_ids.profit_amount')
    def _compute_summary(self):
        for rec in self:
            rec.member_count = len(rec.ledger_line_ids)
            rec.total_profit_distributed = round(sum(rec.ledger_line_ids.mapped('profit_amount')), 2)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.pf.profit.distribution') or _('New')
        return super().create(vals_list)

    def action_distribute_profit(self):
        Account = self.env['dsl.pf.account'].sudo()
        Ledger = self.env['dsl.pf.ledger.line'].sudo()
        for rec in self:
            if rec.state == 'posted':
                raise UserError(_('This PF Profit Distribution batch has already been credited!'))
            accounts = Account.search([
                ('company_id', '=', rec.company_id.id),
                ('state', '=', 'active'),
                ('total_fund_balance', '>', 0),
            ])
            if not accounts:
                raise UserError(_('No active PF Member Accounts with positive balance found!'))
            vals_list = []
            for acc in accounts:
                prof = round(acc.total_fund_balance * (rec.profit_rate_pct / 100.0), 2)
                if prof > 0:
                    vals_list.append({
                        'pf_account_id': acc.id,
                        'entry_date': rec.distribution_date,
                        'entry_type': 'annual_profit',
                        'description': f"Annual PF Trust Return ({rec.profit_rate_pct:g}%) — {rec.fiscal_year_label}",
                        'profit_amount': prof,
                        'profit_batch_id': rec.id,
                    })
            if vals_list:
                Ledger.create(vals_list)
            rec.write({'state': 'posted'})


class DslPayslipPfHook(models.Model):
    _inherit = 'dsl.payslip'

    def action_mark_paid(self):
        res = super().action_mark_paid()
        Account = self.env['dsl.pf.account'].sudo()
        Ledger = self.env['dsl.pf.ledger.line'].sudo()
        Policy = self.env['dsl.pf.policy'].sudo()
        default_pol = Policy.search([('active', '=', True)], limit=1)

        for rec in self:
            emp_pf = sum(rec.line_ids.filtered(lambda l: l.code == 'PF_EMPLOYEE').mapped('amount'))
            empr_pf = sum(rec.line_ids.filtered(lambda l: l.code == 'PF_EMPLOYER').mapped('amount'))
            if emp_pf <= 0 and empr_pf <= 0:
                continue
            existing_entry = Ledger.search([('payslip_id', '=', rec.id)], limit=1)
            if existing_entry:
                continue

            acc = Account.search([
                ('employee_id', '=', rec.employee_id.id),
                ('company_id', '=', rec.company_id.id),
            ], limit=1)
            if not acc and default_pol:
                join_dt = getattr(rec.employee_id, 'joining_date', False) or rec.date_from
                acc = Account.create({
                    'employee_id': rec.employee_id.id,
                    'company_id': rec.company_id.id,
                    'branch_id': rec.branch_id.id if rec.branch_id else False,
                    'policy_id': default_pol.id,
                    'membership_date': join_dt,
                    'state': 'active',
                })
            if acc:
                Ledger.create({
                    'pf_account_id': acc.id,
                    'entry_date': rec.paid_date or rec.date_to,
                    'entry_type': 'monthly_payroll',
                    'description': f"Monthly PF Contribution — {rec.payroll_month_label} ({rec.name})",
                    'employee_amount': round(emp_pf, 2),
                    'employer_amount': round(empr_pf, 2),
                    'payslip_id': rec.id,
                })
        return res

