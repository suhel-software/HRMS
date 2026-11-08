# -*- coding: utf-8 -*-
import base64
import csv
import io
from odoo import api, fields, models, _
from odoo.exceptions import UserError

BONUS_TYPE_TO_CODE = {
    'eid_ul_fitr': ('EID_BONUS_1', 'First Eid Bonus (Eid-ul-Fitr)'),
    'eid_ul_adha': ('EID_BONUS_2', 'Second Eid Bonus (Eid-ul-Adha)'),
    'durga_puja': ('DURGA_BONUS', 'Durga Puja Festival Bonus'),
    'christmas_buddha': ('FESTIVAL_BONUS', 'Religious Festival Bonus'),
    'boishakhi': ('BOISHAKHI', 'Pohela Boishakh Allowance'),
    'performance': ('PERFORMANCE', 'Performance / KPI Bonus'),
    'profit_sharing': ('PROFIT_SHARING', 'Annual Profit Sharing (WPPF)'),
}


class DslFestivalBonusRun(models.Model):
    _name = 'dsl.festival.bonus.run'
    _description = 'Bangladesh Festival, Eid, Puja & Performance Bonus Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'effective_date desc, id desc'

    name = fields.Char(
        string='Bonus Batch Ref.',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
    )
    title = fields.Char(
        string='Bonus Sheet Title',
        required=True,
        default='Eid-ul-Fitr Festival Bonus Sheet',
        tracking=True,
    )
    bonus_type = fields.Selection(
        selection=[
            ('eid_ul_fitr', 'Eid-ul-Fitr Bonus (প্রথম ঈদ বোনাস)'),
            ('eid_ul_adha', 'Eid-ul-Adha Bonus (দ্বিতীয় ঈদ বোনাস)'),
            ('durga_puja', 'Durga Puja Bonus (দুর্গাপূজা বোনাস)'),
            ('christmas_buddha', 'Christmas / Buddha Purnima Bonus'),
            ('boishakhi', 'Pohela Boishakh Allowance (বৈশাখী ভাতা — ২০% বেসিক)'),
            ('performance', 'Annual / Quarterly Performance Bonus'),
            ('profit_sharing', 'Profit Sharing / WPPF Bonus'),
        ],
        string='Bonus Type',
        default='eid_ul_fitr',
        required=True,
        tracking=True,
    )
    religion_filter = fields.Selection(
        selection=[
            ('all', 'All Active Employees (সকল ধর্মের কর্মী)'),
            ('islam', 'Islam (শুধুমাত্র মুসলিম কর্মী)'),
            ('hinduism', 'Hinduism (শুধুমাত্র সনাতন ধর্মাবলম্বী)'),
            ('christianity', 'Christianity (খ্রিস্টান ধর্মাবলম্বী)'),
            ('buddhism', 'Buddhism (বৌদ্ধ ধর্মাবলম্বী)'),
        ],
        string='Eligible Religion Filter',
        default='islam',
        required=True,
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
        string='Branch / Plant (Optional)',
        domain="[('company_id', '=', company_id)]",
    )
    department_id = fields.Many2one('hr.department', string='Department Filter (Optional)')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    effective_date = fields.Date(
        string='Disbursement / Cutoff Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    calculation_basis = fields.Selection(
        selection=[
            ('pct_basic', '% of Basic Salary (স্ট্যান্ডার্ড ১০০% বেসিক)'),
            ('pct_gross', '% of Gross Salary (গ্রস বেতনের %)'),
            ('fixed', 'Fixed Flat Amount (নির্দিষ্ট পরিমাণ ৳)'),
        ],
        string='Calculation Formula',
        default='pct_basic',
        required=True,
    )
    rate_or_amount = fields.Float(string='Rate (%) / Fixed Amount (৳)', default=100.0, required=True)
    min_full_bonus_months = fields.Integer(
        string='Months for 100% Eligibility',
        default=6,
        help='Employees with >= this many months receive 100%; newer staff can be pro-rated below.',
    )
    prorate_under_tenure = fields.Boolean(
        string='Pro-Rate Newer / Probation Staff',
        default=True,
    )
    payout_mode = fields.Selection(
        selection=[
            ('separate_advice', 'Separate Bonus Bank Advice Sheet (BEFTN / bKash)'),
            ('attach_payslip', 'Include in Monthly Payslip (`EID_BONUS_1` / `DURGA_BONUS` etc.)'),
        ],
        string='Disbursement Mode',
        default='separate_advice',
        required=True,
        tracking=True,
    )

    line_ids = fields.One2many('dsl.festival.bonus.line', 'bonus_run_id', string='Employee Bonus Lines')
    employee_count = fields.Integer(string='Eligible Employees', compute='_compute_totals', store=True)
    total_bonus_amount = fields.Monetary(
        string='Total Bonus Payable (৳)',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
        tracking=True,
    )
    advice_csv_file = fields.Binary(string='BEFTN / MFS Bonus Advice CSV', readonly=True, attachment=True)
    advice_csv_filename = fields.Char(readonly=True)

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('computed', 'Computed'),
            ('approved', 'Approved'),
            ('paid', 'Disbursed / Paid'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    @api.depends('line_ids.bonus_amount')
    def _compute_totals(self):
        for rec in self:
            rec.employee_count = len(rec.line_ids)
            rec.total_bonus_amount = round(sum(rec.line_ids.mapped('bonus_amount')), 2)

    @api.onchange('bonus_type')
    def _onchange_bonus_type_defaults(self):
        if self.bonus_type in ('eid_ul_fitr', 'eid_ul_adha'):
            self.religion_filter = 'islam'
            self.calculation_basis = 'pct_basic'
            self.rate_or_amount = 100.0
        elif self.bonus_type == 'durga_puja':
            self.religion_filter = 'hinduism'
            self.calculation_basis = 'pct_basic'
            self.rate_or_amount = 100.0
        elif self.bonus_type == 'boishakhi':
            self.religion_filter = 'all'
            self.calculation_basis = 'pct_basic'
            self.rate_or_amount = 20.0
        elif self.bonus_type in ('performance', 'profit_sharing'):
            self.religion_filter = 'all'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.festival.bonus.run') or _('New')
        return super().create(vals_list)

    def action_generate_bonus_sheet(self):
        Employee = self.env['hr.employee'].sudo()
        Comp = self.env['dsl.employee.compensation'].sudo()
        Line = self.env['dsl.festival.bonus.line'].sudo()

        for rec in self:
            dom = [('active', '=', True), ('company_id', '=', rec.company_id.id)]
            if rec.branch_id:
                dom.append(('branch_id', '=', rec.branch_id.id))
            if rec.department_id:
                dom.append(('department_id', '=', rec.department_id.id))
            if rec.religion_filter != 'all':
                dom.append(('religion', '=', rec.religion_filter))

            emps = Employee.search(dom)
            if not emps:
                raise UserError(_('No eligible employees matched the selected Company / Branch / Religion filter!'))

            rec.line_ids.unlink()
            vals_list = []
            for emp in emps:
                pkg = Comp.search([
                    ('employee_id', '=', emp.id),
                    ('state', '=', 'active'),
                ], order='effective_from desc, id desc', limit=1)
                if not pkg:
                    continue
                join_dt = emp.joining_date or rec.effective_date
                srv_months = max(round((rec.effective_date - join_dt).days / 30.4375, 1), 0.0)
                min_m = max(rec.min_full_bonus_months or 0, 0)
                if min_m > 0 and srv_months < min_m:
                    if not rec.prorate_under_tenure:
                        continue
                    elig_pct = round((srv_months / float(min_m)) * 100.0, 2)
                else:
                    elig_pct = 100.0

                basic = pkg.basic_salary or 0.0
                gross = pkg.total_gross_package or pkg.gross_salary or 0.0
                if rec.calculation_basis == 'pct_basic':
                    full_amt = basic * (rec.rate_or_amount / 100.0)
                elif rec.calculation_basis == 'pct_gross':
                    full_amt = gross * (rec.rate_or_amount / 100.0)
                else:
                    full_amt = rec.rate_or_amount

                final_amt = round(full_amt * (elig_pct / 100.0), 2)
                if final_amt <= 0:
                    continue

                vals_list.append({
                    'bonus_run_id': rec.id,
                    'employee_id': emp.id,
                    'joining_date': join_dt,
                    'service_months': srv_months,
                    'basic_salary': basic,
                    'gross_salary': gross,
                    'eligibility_pct': elig_pct,
                    'bonus_amount': final_amt,
                    'payment_method': emp.payment_method or 'bank',
                    'bank_name': emp.salary_bank_name or False,
                    'bank_routing_no': emp.salary_bank_routing_no or False,
                    'bank_account_no': emp.salary_bank_account_no or emp.mfs_account_no or False,
                })
            if vals_list:
                Line.create(vals_list)
            rec.write({'state': 'computed'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_mark_paid(self):
        self.write({'state': 'paid'})

    def action_export_bonus_advice_csv(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Compute bonus lines first before exporting BEFTN / MFS Advice!'))
        buf = io.StringIO()
        buf.write('\ufeff')
        writer = csv.writer(buf)
        writer.writerow([
            'SL', 'Employee ID', 'Employee Name', 'Bonus Type', 'Mode',
            'Bank / MFS', 'Routing No', 'Account / Wallet No', 'Bonus Payable (BDT)'
        ])
        for idx, ln in enumerate(self.line_ids, start=1):
            writer.writerow([
                idx,
                ln.employee_id.employee_code or '',
                ln.employee_id.name or '',
                self.title,
                (ln.payment_method or 'bank').upper(),
                ln.bank_name or 'MFS/Cash',
                ln.bank_routing_no or '',
                ln.bank_account_no or '',
                f"{ln.bonus_amount:.2f}",
            ])
        fname = f"Bonus_Advice_{self.name}.csv"
        self.write({
            'advice_csv_file': base64.b64encode(buf.getvalue().encode('utf-8')),
            'advice_csv_filename': fname,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=dsl.festival.bonus.run&id={self.id}&field=advice_csv_file&filename_field=advice_csv_filename&download=true',
            'target': 'self',
        }


class DslFestivalBonusLine(models.Model):
    _name = 'dsl.festival.bonus.line'
    _description = 'Employee Festival / Performance Bonus Line'
    _order = 'id asc'

    bonus_run_id = fields.Many2one('dsl.festival.bonus.run', required=True, ondelete='cascade', index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True)
    currency_id = fields.Many2one('res.currency', related='bonus_run_id.currency_id', readonly=True)
    joining_date = fields.Date(string='Joining Date')
    service_months = fields.Float(string='Tenure (Months)')
    basic_salary = fields.Monetary(string='Basic (৳)', currency_field='currency_id')
    gross_salary = fields.Monetary(string='Gross (৳)', currency_field='currency_id')
    eligibility_pct = fields.Float(string='Eligible (%)', default=100.0)
    bonus_amount = fields.Monetary(string='Bonus Payable (৳)', currency_field='currency_id', required=True)
    payment_method = fields.Char(string='Mode')
    bank_name = fields.Char(string='Bank')
    bank_routing_no = fields.Char(string='Routing No.')
    bank_account_no = fields.Char(string='Account / Wallet')
    payslip_id = fields.Many2one('dsl.payslip', string='Paid via Payslip', readonly=True)


class DslPayslipFestivalBonusHook(models.Model):
    _inherit = 'dsl.payslip'

    def _get_extra_benefit_lines(self):
        res = super()._get_extra_benefit_lines()
        BonusLine = self.env['dsl.festival.bonus.line'].sudo()
        matched = BonusLine.search([
            ('employee_id', '=', self.employee_id.id),
            ('bonus_run_id.payout_mode', '=', 'attach_payslip'),
            ('bonus_run_id.state', 'in', ('approved', 'paid')),
            ('bonus_run_id.effective_date', '>=', self.date_from),
            ('bonus_run_id.effective_date', '<=', self.date_to),
        ])
        for idx, bl in enumerate(matched, start=1):
            code, label = BONUS_TYPE_TO_CODE.get(bl.bonus_run_id.bonus_type, ('FESTIVAL_BONUS', 'Festival Bonus'))
            res.append({
                'sequence': 62 + idx,
                'code': code,
                'name': f"{bl.bonus_run_id.title} ({label})",
                'category': 'variable_earning',
                'amount': round(bl.bonus_amount, 2),
            })
        return res

