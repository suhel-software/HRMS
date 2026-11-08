# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class DslTaxFiscalPolicy(models.Model):
    _name = 'dsl.tax.fiscal.policy'
    _description = 'Bangladesh NBR Fiscal Year Income Tax Slab & Rebate Policy'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id desc'

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    name = fields.Char(string='Fiscal Year Policy Name', required=True, tracking=True)
    fiscal_year = fields.Char(string='Income Year (FY)', required=True, default='2026-2027', tracking=True)
    assessment_year = fields.Char(string='Assessment Year (AY)', required=True, default='2027-2028', tracking=True)
    company_id = fields.Many2one('res.company', string='Company')
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )

    # 1. Bangladesh 1/3rd Exemption Rule (Income Tax Act 2023 - 6th Schedule)
    exemption_divisor = fields.Float(
        string='Salary Exemption Divisor (1/3 = 3.0)',
        default=3.0,
        required=True,
        help='Exempted Salary = min(Annual Gross / 3.0, Max Exemption Cap).',
    )
    max_exemption_cap = fields.Monetary(
        string='Max 1/3rd Exemption Cap (৳)',
        currency_field='currency_id',
        default=450000.0,
        required=True,
        tracking=True,
    )

    # 2. Category-Based Zero-Tax Thresholds (0% First Slab)
    threshold_general = fields.Monetary(
        string='General Male Threshold (৳)',
        currency_field='currency_id',
        default=350000.0,
        required=True,
    )
    threshold_female_senior = fields.Monetary(
        string='Female / Senior (65+) Threshold (৳)',
        currency_field='currency_id',
        default=400000.0,
        required=True,
    )
    threshold_disabled = fields.Monetary(
        string='Physically Challenged / 3rd Gender (৳)',
        currency_field='currency_id',
        default=475000.0,
        required=True,
    )
    threshold_freedom_fighter = fields.Monetary(
        string='War-Wounded Freedom Fighter (৳)',
        currency_field='currency_id',
        default=500000.0,
        required=True,
    )

    # 3. Section 78 Investment Rebate Parameters
    rebate_taxable_pct = fields.Float(string='Rebate Cap (% of Taxable Income)', default=3.0)
    rebate_investment_pct = fields.Float(string='Rebate Rate (% of Eligible Investment)', default=15.0)
    rebate_max_cap = fields.Monetary(
        string='Maximum Tax Rebate Ceiling (৳)',
        currency_field='currency_id',
        default=1000000.0,
    )
    dps_annual_cap = fields.Monetary(
        string='NBR Max Eligible DPS / Year (৳)',
        currency_field='currency_id',
        default=120000.0,
    )
    sanchaypatra_annual_cap = fields.Monetary(
        string='NBR Max Eligible Sanchaypatra / Year (৳)',
        currency_field='currency_id',
        default=500000.0,
    )

    # 4. City Corporation Location-Based Minimum Tax Floor
    min_tax_dhaka_ctg = fields.Monetary(
        string='Min Tax: Dhaka & Chattogram City Corp (৳)',
        currency_field='currency_id',
        default=5000.0,
    )
    min_tax_other_city = fields.Monetary(
        string='Min Tax: Other City Corporations (৳)',
        currency_field='currency_id',
        default=4000.0,
    )
    min_tax_non_city = fields.Monetary(
        string='Min Tax: Outside City Corporation (৳)',
        currency_field='currency_id',
        default=3000.0,
    )

    slab_ids = fields.One2many(
        'dsl.tax.slab.line',
        'policy_id',
        string='Progressive NBR Tax Slabs (Above 0% Threshold)',
    )
    notes = fields.Text(string='Finance Act / NBR SRO Reference')

    def _get_zero_threshold(self, category):
        self.ensure_one()
        if category == 'female_senior':
            return self.threshold_female_senior
        if category == 'disabled':
            return self.threshold_disabled
        if category == 'freedom_fighter':
            return self.threshold_freedom_fighter
        return self.threshold_general

    def _get_min_tax_floor(self, location_zone):
        self.ensure_one()
        if location_zone == 'other_city':
            return self.min_tax_other_city
        if location_zone == 'non_city':
            return self.min_tax_non_city
        return self.min_tax_dhaka_ctg

    def _calculate_nbr_tax_dict(
        self,
        annual_gross,
        category='general',
        location_zone='dhaka_ctg_city',
        eligible_investment=0.0,
    ):
        """Pure statutory NBR Income Tax Act 2023 calculator."""
        self.ensure_one()
        gross = max(float(annual_gross or 0.0), 0.0)
        div = self.exemption_divisor if self.exemption_divisor > 0 else 3.0
        exempt = min(round(gross / div, 2), float(self.max_exemption_cap or 450000.0))
        taxable = max(round(gross - exempt, 2), 0.0)
        threshold = float(self._get_zero_threshold(category))

        if taxable <= threshold:
            return {
                'exempted_income': exempt,
                'taxable_income': taxable,
                'zero_threshold': threshold,
                'gross_tax': 0.0,
                'rebate': 0.0,
                'min_tax': 0.0,
                'net_annual_tax': 0.0,
            }

        remaining = taxable - threshold
        gross_tax = 0.0
        for slab in self.slab_ids.sorted(lambda s: s.sequence):
            if remaining <= 0:
                break
            band = slab.slab_amount if slab.slab_amount > 0 else remaining
            slice_amt = min(remaining, band)
            gross_tax += slice_amt * (slab.rate_pct / 100.0)
            remaining -= slice_amt

        gross_tax = round(gross_tax, 2)

        inv = max(float(eligible_investment or 0.0), 0.0)
        rebate = 0.0
        if inv > 0:
            r1 = taxable * ((self.rebate_taxable_pct or 3.0) / 100.0)
            r2 = inv * ((self.rebate_investment_pct or 15.0) / 100.0)
            r3 = float(self.rebate_max_cap or 1000000.0)
            rebate = round(min(r1, r2, r3, gross_tax), 2)

        min_floor = float(self._get_min_tax_floor(location_zone))
        net_tax = round(max(gross_tax - rebate, min_floor), 2) if gross_tax > 0 else 0.0
        return {
            'exempted_income': exempt,
            'taxable_income': taxable,
            'zero_threshold': threshold,
            'gross_tax': gross_tax,
            'rebate': rebate,
            'min_tax': min_floor,
            'net_annual_tax': net_tax,
        }


class DslTaxSlabLine(models.Model):
    _name = 'dsl.tax.slab.line'
    _description = 'NBR Progressive Income Tax Slab Tier'
    _order = 'sequence asc, id asc'

    policy_id = fields.Many2one(
        'dsl.tax.fiscal.policy',
        string='Fiscal Policy',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Slab Description', required=True, help='e.g. Next ৳1,00,000 @ 5%')
    currency_id = fields.Many2one('res.currency', related='policy_id.currency_id', readonly=True)
    slab_amount = fields.Monetary(
        string='Slab Band Width (৳) (0 = Balance)',
        currency_field='currency_id',
        required=True,
        default=100000.0,
    )
    rate_pct = fields.Float(string='Tax Rate (%)', required=True, default=5.0)


class DslEmployeeTaxAssessment(models.Model):
    _name = 'dsl.employee.tax.assessment'
    _description = 'Employee Annual NBR Tax Assessment & Investment Rebate Sheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Assessment Ref.',
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
    personal_tin = fields.Char(
        related='employee_id.personal_tin',
        string='12-Digit NBR e-TIN',
        readonly=True,
    )

    fiscal_policy_id = fields.Many2one(
        'dsl.tax.fiscal.policy',
        string='NBR Fiscal Policy',
        required=True,
        default=lambda self: self.env['dsl.tax.fiscal.policy'].sudo().search([('active', '=', True)], limit=1),
        tracking=True,
    )
    taxpayer_category = fields.Selection(
        selection=[
            ('general', 'General Taxpayer (৳3,50,000 Threshold)'),
            ('female_senior', 'Female / Senior Citizen 65+ (৳4,00,000 Threshold)'),
            ('disabled', 'Physically Challenged / 3rd Gender (৳4,75,000 Threshold)'),
            ('freedom_fighter', 'Gazetted Freedom Fighter (৳5,00,000 Threshold)'),
        ],
        string='Taxpayer Category',
        default='general',
        required=True,
        tracking=True,
    )
    location_zone = fields.Selection(
        selection=[
            ('dhaka_ctg_city', 'Dhaka / Chattogram City Corp (Min ৳5,000)'),
            ('other_city', 'Other City Corporations (Min ৳4,000)'),
            ('non_city', 'Outside City Corporation (Min ৳3,000)'),
        ],
        string='Minimum Tax Zone',
        default='dhaka_ctg_city',
        required=True,
        tracking=True,
    )

    # Annual Salary & Bonus Projection
    monthly_gross_salary = fields.Monetary(
        string='Monthly Gross Salary (৳)',
        currency_field='currency_id',
        required=True,
        default=0.0,
        tracking=True,
    )
    projected_festival_bonus = fields.Monetary(
        string='Annual Festival Bonuses (2 Eids / Puja) (৳)',
        currency_field='currency_id',
        default=0.0,
        tracking=True,
    )
    other_taxable_income = fields.Monetary(
        string='Other Taxable Allowances / Overtime (৳)',
        currency_field='currency_id',
        default=0.0,
    )

    # Section 78 Investment Declarations
    dps_deposit = fields.Monetary(
        string='Annual DPS / BSP Deposit (৳)',
        currency_field='currency_id',
        default=0.0,
    )
    sanchaypatra_investment = fields.Monetary(
        string='Sanchaypatra / Govt Securities (৳)',
        currency_field='currency_id',
        default=0.0,
    )
    life_insurance_premium = fields.Monetary(
        string='Life Insurance Premium (৳)',
        currency_field='currency_id',
        default=0.0,
    )
    pf_annual_contribution = fields.Monetary(
        string='Recognized PF Contribution (Employee + Employer) (৳)',
        currency_field='currency_id',
        default=0.0,
    )
    listed_shares_investment = fields.Monetary(
        string='DSE / CSE Listed Securities (৳)',
        currency_field='currency_id',
        default=0.0,
    )

    tds_already_deducted = fields.Monetary(
        string='AIT / TDS Already Deducted in FY (৳)',
        currency_field='currency_id',
        default=0.0,
    )
    remaining_months = fields.Integer(
        string='Remaining Months in FY',
        default=12,
        required=True,
    )

    # Stored NBR Tax Calculation Outputs (Strictly no `default=` or `required=True`!)
    annual_gross_income = fields.Monetary(
        string='Projected Annual Gross (৳)',
        currency_field='currency_id',
        compute='_compute_nbr_tax_sheet',
        store=True,
    )
    exempted_income = fields.Monetary(
        string='1/3rd Exempted Salary (Max ৳4.5L)',
        currency_field='currency_id',
        compute='_compute_nbr_tax_sheet',
        store=True,
    )
    annual_taxable_income = fields.Monetary(
        string='Net Taxable Income (৳)',
        currency_field='currency_id',
        compute='_compute_nbr_tax_sheet',
        store=True,
    )
    zero_tax_threshold = fields.Monetary(
        string='0% Tax-Free Slab (৳)',
        currency_field='currency_id',
        compute='_compute_nbr_tax_sheet',
        store=True,
    )
    eligible_investment_total = fields.Monetary(
        string='NBR Eligible Investment (৳)',
        currency_field='currency_id',
        compute='_compute_nbr_tax_sheet',
        store=True,
    )
    gross_slab_tax = fields.Monetary(
        string='Gross Slab Tax Liability (৳)',
        currency_field='currency_id',
        compute='_compute_nbr_tax_sheet',
        store=True,
    )
    investment_tax_rebate = fields.Monetary(
        string='Section 78 Investment Rebate (৳)',
        currency_field='currency_id',
        compute='_compute_nbr_tax_sheet',
        store=True,
    )
    net_annual_tax = fields.Monetary(
        string='Net Annual Payable Tax (৳)',
        currency_field='currency_id',
        compute='_compute_nbr_tax_sheet',
        store=True,
        tracking=True,
    )
    monthly_tds_amount = fields.Monetary(
        string='Monthly Payroll TDS (৳)',
        currency_field='currency_id',
        compute='_compute_nbr_tax_sheet',
        store=True,
        tracking=True,
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active for Payroll TDS'),
            ('closed', 'FY Closed'),
        ],
        string='Status',
        default='active',
        required=True,
        tracking=True,
    )
    notes = fields.Text(string='Tax Return / Challan Remarks')

    @api.depends(
        'fiscal_policy_id',
        'fiscal_policy_id.max_exemption_cap',
        'fiscal_policy_id.slab_ids.rate_pct',
        'fiscal_policy_id.slab_ids.slab_amount',
        'taxpayer_category',
        'location_zone',
        'monthly_gross_salary',
        'projected_festival_bonus',
        'other_taxable_income',
        'dps_deposit',
        'sanchaypatra_investment',
        'life_insurance_premium',
        'pf_annual_contribution',
        'listed_shares_investment',
        'tds_already_deducted',
        'remaining_months',
    )
    def _compute_nbr_tax_sheet(self):
        for rec in self:
            pol = rec.fiscal_policy_id
            ann_gross = round(
                (rec.monthly_gross_salary or 0.0) * 12.0
                + (rec.projected_festival_bonus or 0.0)
                + (rec.other_taxable_income or 0.0),
                2,
            )
            if not pol:
                rec.annual_gross_income = ann_gross
                rec.exempted_income = 0.0
                rec.annual_taxable_income = 0.0
                rec.zero_tax_threshold = 0.0
                rec.eligible_investment_total = 0.0
                rec.gross_slab_tax = 0.0
                rec.investment_tax_rebate = 0.0
                rec.net_annual_tax = 0.0
                rec.monthly_tds_amount = 0.0
                continue

            dps_elig = min(rec.dps_deposit or 0.0, pol.dps_annual_cap or 120000.0)
            sanch_elig = min(rec.sanchaypatra_investment or 0.0, pol.sanchaypatra_annual_cap or 500000.0)
            total_elig_inv = round(
                dps_elig
                + sanch_elig
                + (rec.life_insurance_premium or 0.0)
                + (rec.pf_annual_contribution or 0.0)
                + (rec.listed_shares_investment or 0.0),
                2,
            )

            res = pol._calculate_nbr_tax_dict(
                annual_gross=ann_gross,
                category=rec.taxpayer_category,
                location_zone=rec.location_zone,
                eligible_investment=total_elig_inv,
            )
            rem_tax = max(res['net_annual_tax'] - (rec.tds_already_deducted or 0.0), 0.0)
            months = max(rec.remaining_months or 12, 1)

            rec.annual_gross_income = ann_gross
            rec.exempted_income = res['exempted_income']
            rec.annual_taxable_income = res['taxable_income']
            rec.zero_tax_threshold = res['zero_threshold']
            rec.eligible_investment_total = total_elig_inv
            rec.gross_slab_tax = res['gross_tax']
            rec.investment_tax_rebate = res['rebate']
            rec.net_annual_tax = res['net_annual_tax']
            rec.monthly_tds_amount = round(rem_tax / months, 2)

    @api.onchange('employee_id')
    def _onchange_employee_populate_salary_and_category(self):
        if self.employee_id:
            emp = self.employee_id.sudo()
            self.company_id = emp.company_id.id
            self.branch_id = emp.branch_id.id if emp.branch_id else False
            if emp.gender == 'female' or getattr(emp, 'age_years', 0) >= 65:
                self.taxpayer_category = 'female_senior'
            else:
                self.taxpayer_category = 'general'
            pkg = self.env['dsl.employee.compensation'].sudo().search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'active'),
            ], order='effective_from desc, id desc', limit=1)
            if pkg:
                self.monthly_gross_salary = pkg.total_gross_package or pkg.gross_salary
                self.projected_festival_bonus = pkg.basic_salary * 2.0
                if pkg.pf_applicable and pkg.pf_deduction_amount > 0 and not self.pf_annual_contribution:
                    # Recognized PF Employee + Employer (10% + 10%) annual eligible investment!
                    self.pf_annual_contribution = pkg.pf_deduction_amount * 24.0

    def action_sync_from_compensation(self):
        Comp = self.env['dsl.employee.compensation'].sudo()
        for rec in self:
            pkg = Comp.search([
                ('employee_id', '=', rec.employee_id.id),
                ('state', '=', 'active'),
            ], order='effective_from desc, id desc', limit=1)
            if pkg:
                vals = {
                    'monthly_gross_salary': pkg.total_gross_package or pkg.gross_salary,
                    'projected_festival_bonus': pkg.basic_salary * 2.0,
                }
                if pkg.pf_applicable and pkg.pf_deduction_amount > 0 and not rec.pf_annual_contribution:
                    vals['pf_annual_contribution'] = pkg.pf_deduction_amount * 24.0
                rec.write(vals)
                rec._sync_tds_to_active_package()

    def _sync_tds_to_active_package(self):
        Comp = self.env['dsl.employee.compensation'].sudo()
        for rec in self.filtered(lambda r: r.state == 'active' and r.employee_id):
            pkg = Comp.search([
                ('employee_id', '=', rec.employee_id.id),
                ('state', '=', 'active'),
            ], order='effective_from desc, id desc', limit=1)
            if pkg and 'tds_monthly_estimate' in pkg._fields:
                pkg.write({'tds_monthly_estimate': rec.monthly_tds_amount})

    @api.model_create_multi
    def create(self, vals_list):
        Employee = self.env['hr.employee'].sudo()
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.employee.tax.assessment') or _('New')
            if vals.get('employee_id'):
                emp = Employee.browse(vals['employee_id'])
                if not vals.get('company_id') and emp.company_id:
                    vals['company_id'] = emp.company_id.id
                if not vals.get('branch_id') and emp.branch_id:
                    vals['branch_id'] = emp.branch_id.id
        records = super().create(vals_list)
        records._sync_tds_to_active_package()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'tds_monthly_estimate' not in self.env.context:
            self.with_context(tds_monthly_estimate=True)._sync_tds_to_active_package()
        return res


class DslPayslipNbrTaxExt(models.Model):
    _inherit = 'dsl.payslip'

    tax_assessment_id = fields.Many2one(
        'dsl.employee.tax.assessment',
        string='Linked NBR Tax Sheet',
        readonly=True,
    )

    def _detect_employee_tax_zone(self, emp):
        city_txt = ' '.join(filter(None, [
            emp.branch_id.name if emp.branch_id else '',
            emp.branch_id.city if emp.branch_id else '',
            emp.present_district or '',
        ])).lower()
        if any(k in city_txt for k in ('gazipur', 'narayanganj', 'khulna', 'rajshahi', 'sylhet', 'barishal', 'rangpur', 'cumilla', 'mymensingh')):
            return 'other_city'
        if any(k in city_txt for k in ('dhaka', 'gulshan', 'banani', 'uttara', 'motijheel', 'chattogram', 'chittagong')):
            return 'dhaka_ctg_city'
        return 'dhaka_ctg_city'

    def _get_monthly_tds_deduction(self):
        self.ensure_one()
        if self.manual_tds_override and self.manual_tds_override > 0:
            return round(float(self.manual_tds_override), 2)

        emp = self.employee_id.sudo()
        Assessment = self.env['dsl.employee.tax.assessment'].sudo()
        sheet = Assessment.search([
            ('employee_id', '=', emp.id),
            ('state', '=', 'active'),
        ], order='id desc', limit=1)
        if sheet:
            self.tax_assessment_id = sheet.id
            return round(float(sheet.monthly_tds_amount or 0.0), 2)

        if self.compensation_id and self.compensation_id.tds_monthly_estimate > 0:
            return round(float(self.compensation_id.tds_monthly_estimate), 2)

        # On-the-fly statutory NBR calculation when no manual investment declaration sheet exists yet
        pol = self.env['dsl.tax.fiscal.policy'].sudo().search([('active', '=', True)], order='sequence, id desc', limit=1)
        if not pol or not self.compensation_id:
            return 0.0

        pkg = self.compensation_id
        eff_monthly_gross = pkg.total_gross_package if hasattr(pkg, 'total_gross_package') and pkg.total_gross_package else pkg.gross_salary
        ann_gross = (eff_monthly_gross * 12.0) + (pkg.basic_salary * 2.0)
        cat = 'female_senior' if (emp.gender == 'female' or getattr(emp, 'age_years', 0) >= 65) else 'general'
        zone = self._detect_employee_tax_zone(emp)
        res = pol._calculate_nbr_tax_dict(
            annual_gross=ann_gross,
            category=cat,
            location_zone=zone,
            eligible_investment=0.0,
        )
        return round(res['net_annual_tax'] / 12.0, 2)


class HrEmployeeTaxExt(models.Model):
    _inherit = 'hr.employee'

    dsl_tax_assessment_ids = fields.One2many(
        'dsl.employee.tax.assessment',
        'employee_id',
        string='NBR Tax Assessments & Rebate Declarations',
        groups='hr.group_hr_user',
    )


