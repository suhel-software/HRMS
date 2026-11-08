# -*- coding: utf-8 -*-
import math
from odoo import api, fields, models, _


def _default_gratuity_policy(record=None):
    env = record.env if record is not None else None
    if not env:
        return False
    pol = env['dsl.gratuity.policy'].sudo().search([('active', '=', True)], order='id asc', limit=1)
    return pol.id if pol else False


class DslGratuityPolicy(models.Model):
    _name = 'dsl.gratuity.policy'
    _description = 'Bangladesh Labour Act Gratuity & Service Benefit Policy'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id asc'

    active = fields.Boolean(default=True)
    name = fields.Char(string='Gratuity Policy Name', required=True, tracking=True)
    code = fields.Char(string='Policy Code', required=True, default='BD-GRAT-BLA')
    company_id = fields.Many2one('res.company', string='Company (Blank = Group Policy)')

    min_qualifying_years = fields.Float(
        string='Minimum Qualifying Service (Years)',
        default=1.0,
        required=True,
        help='Bangladesh Labour Act 2006 Sec 2(10): 1.0 year continuous service (or corporate 5.0-year trust rule).',
    )
    round_over_six_months = fields.Boolean(
        string='Round Part > 6 Months as Full Year (BD Labour Act)',
        default=True,
    )
    rate_under_10_yrs = fields.Float(
        string='Multiplier < 10 Yrs (x Basic / Year)',
        default=1.0,
        required=True,
        help='1.0 = 30 days Basic Salary per qualifying year.',
    )
    rate_10_yrs_and_above = fields.Float(
        string='Multiplier >= 10 Yrs (x Basic / Year)',
        default=1.5,
        required=True,
        help='1.5 = 45 days Basic Salary per qualifying year after 10 years of service.',
    )
    nbr_tax_exempt_cap = fields.Float(
        string='NBR Tax-Exempt Gratuity Cap (৳)',
        default=25000000.0,
        help='Up to ৳2.5 Crore (2,50,00,000 BDT) from Approved Gratuity Fund is tax-exempt under Income Tax Act 2023.',
    )
    notes = fields.Text(string='Statutory Policy Notes')

    def _calculate_gratuity_dict(self, joining_date, cutoff_date, last_basic):
        self.ensure_one()
        if not joining_date or not cutoff_date or cutoff_date <= joining_date or last_basic <= 0:
            return {
                'exact_years': 0.0,
                'qualifying_years': 0,
                'rate_multiplier': 0.0,
                'gross_gratuity': 0.0,
                'exempt_amount': 0.0,
                'taxable_amount': 0.0,
            }
        days = (cutoff_date - joining_date).days
        exact_yrs = round(days / 365.25, 2)
        if exact_yrs < (self.min_qualifying_years or 0.0):
            return {
                'exact_years': exact_yrs,
                'qualifying_years': 0,
                'rate_multiplier': 0.0,
                'gross_gratuity': 0.0,
                'exempt_amount': 0.0,
                'taxable_amount': 0.0,
            }

        whole_yrs = int(math.floor(days / 365.25))
        rem_days = days - (whole_yrs * 365.25)
        qual_yrs = whole_yrs + (1 if (self.round_over_six_months and rem_days > 182.6) else 0)
        mult = self.rate_10_yrs_and_above if exact_yrs >= 10.0 else self.rate_under_10_yrs
        gross_grat = round(float(last_basic) * mult * qual_yrs, 2)
        cap = float(self.nbr_tax_exempt_cap or 25000000.0)
        exempt = round(min(gross_grat, cap), 2)
        taxable = round(max(gross_grat - exempt, 0.0), 2)
        return {
            'exact_years': exact_yrs,
            'qualifying_years': qual_yrs,
            'rate_multiplier': mult,
            'gross_gratuity': gross_grat,
            'exempt_amount': exempt,
            'taxable_amount': taxable,
        }


class DslGratuitySettlement(models.Model):
    _name = 'dsl.gratuity.settlement'
    _description = 'Employee Gratuity & Service Benefit Valuation / Settlement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'cutoff_date desc, id desc'

    name = fields.Char(
        string='Gratuity Ref.',
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
    policy_id = fields.Many2one(
        'dsl.gratuity.policy',
        string='Gratuity Policy',
        required=True,
        default=_default_gratuity_policy,
        tracking=True,
    )
    settlement_purpose = fields.Selection(
        selection=[
            ('accrual_valuation', 'Actuarial / Provision Valuation'),
            ('resignation', 'Resignation Settlement'),
            ('retirement', 'Retirement Benefit'),
            ('retrenchment_death', 'Retrenchment / Death Benefit'),
        ],
        string='Valuation Type',
        default='resignation',
        required=True,
        tracking=True,
    )

    joining_date = fields.Date(string='Joining Date', required=True, default=fields.Date.context_today, tracking=True)
    cutoff_date = fields.Date(string='Last Working / Valuation Date', required=True, default=fields.Date.context_today, tracking=True)
    last_drawn_basic = fields.Monetary(
        string='Last Drawn Monthly Basic (৳)',
        currency_field='currency_id',
        required=True,
        default=0.0,
        tracking=True,
    )

    service_years = fields.Float(string='Exact Service (Years)', compute='_compute_gratuity_amounts', store=True)
    completed_qualifying_years = fields.Integer(string='Qualifying Years (Rounded)', compute='_compute_gratuity_amounts', store=True)
    applicable_multiplier = fields.Float(string='Applicable Rate (x Basic/Yr)', compute='_compute_gratuity_amounts', store=True)
    gross_gratuity_amount = fields.Monetary(
        string='Gross Gratuity Payable (৳)',
        currency_field='currency_id',
        compute='_compute_gratuity_amounts',
        store=True,
        tracking=True,
    )
    tax_exempt_amount = fields.Monetary(
        string='NBR Tax-Exempt Portion (৳)',
        currency_field='currency_id',
        compute='_compute_gratuity_amounts',
        store=True,
    )
    taxable_gratuity_amount = fields.Monetary(
        string='Taxable Excess Over Cap (৳)',
        currency_field='currency_id',
        compute='_compute_gratuity_amounts',
        store=True,
    )

    paid_date = fields.Date(string='Disbursed Date', readonly=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft / Valuation'),
            ('verified', 'HR Verified'),
            ('approved', 'Approved'),
            ('paid', 'Disbursed / Settled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )
    remarks = fields.Text(string='Audit & Calculation Remarks')

    @api.depends('policy_id', 'joining_date', 'cutoff_date', 'last_drawn_basic')
    def _compute_gratuity_amounts(self):
        for rec in self:
            if not rec.policy_id:
                rec.service_years = 0.0
                rec.completed_qualifying_years = 0
                rec.applicable_multiplier = 0.0
                rec.gross_gratuity_amount = 0.0
                rec.tax_exempt_amount = 0.0
                rec.taxable_gratuity_amount = 0.0
                continue
            res = rec.policy_id._calculate_gratuity_dict(rec.joining_date, rec.cutoff_date, rec.last_drawn_basic)
            rec.service_years = res['exact_years']
            rec.completed_qualifying_years = res['qualifying_years']
            rec.applicable_multiplier = res['rate_multiplier']
            rec.gross_gratuity_amount = res['gross_gratuity']
            rec.tax_exempt_amount = res['exempt_amount']
            rec.taxable_gratuity_amount = res['taxable_amount']

    @api.onchange('employee_id')
    def _onchange_employee_sync_tenure_and_basic(self):
        if self.employee_id:
            emp = self.employee_id.sudo()
            self.company_id = emp.company_id.id
            self.branch_id = emp.branch_id.id if emp.branch_id else False
            if getattr(emp, 'joining_date', False):
                self.joining_date = emp.joining_date
            pkg = self.env['dsl.employee.compensation'].sudo().search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'active'),
            ], order='effective_from desc, id desc', limit=1)
            if pkg:
                self.last_drawn_basic = pkg.basic_salary

    def action_sync_employee_data(self):
        for rec in self:
            rec._onchange_employee_sync_tenure_and_basic()

    @api.model_create_multi
    def create(self, vals_list):
        Employee = self.env['hr.employee'].sudo()
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.gratuity.settlement') or _('New')
            if vals.get('employee_id'):
                emp = Employee.browse(vals['employee_id'])
                if not vals.get('company_id') and emp.company_id:
                    vals['company_id'] = emp.company_id.id
                if not vals.get('branch_id') and emp.branch_id:
                    vals['branch_id'] = emp.branch_id.id
        return super().create(vals_list)

    def action_verify(self):
        self.write({'state': 'verified'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_mark_paid(self):
        self.write({'state': 'paid', 'paid_date': fields.Date.context_today(self)})

