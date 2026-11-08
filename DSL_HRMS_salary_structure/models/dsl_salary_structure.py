# -*- coding: utf-8 -*-
import ast
import math
import operator
import re
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING, ROUND_FLOOR
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

# =============================================================================
# 1. SAFE PURE-PYTHON FORMULA EVALUATOR & ROUNDING ENGINE (ZERO EXEC/EVAL RISK)
# =============================================================================
_ALLOWED_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}
_ALLOWED_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_ALLOWED_FUNCS = {
    'min': min,
    'max': max,
    'round': round,
    'abs': abs,
    'ceil': math.ceil,
    'floor': math.floor,
}


def safe_eval_salary_formula(expr, variables):
    """Safely evaluates arithmetic salary formulas like `(GROSS - 2450) / 1.5` or `min(BASIC * 0.10, 5000)`."""
    if not expr or not str(expr).strip():
        return 0.0
    try:
        tree = ast.parse(str(expr).strip(), mode='eval')
    except SyntaxError as exc:
        raise ValidationError(_('Invalid salary formula syntax "%s": %s') % (expr, exc))

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id in variables:
                return float(variables[node.id] or 0.0)
            raise ValidationError(_('Unknown variable "%s" in salary formula "%s".') % (node.id, expr))
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BIN_OPS:
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
                return 0.0
            return float(_ALLOWED_BIN_OPS[type(node.op)](left, right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY_OPS:
            return float(_ALLOWED_UNARY_OPS[type(node.op)](_eval(node.operand)))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_FUNCS:
            args = [_eval(a) for a in node.args]
            return float(_ALLOWED_FUNCS[node.func.id](*args))
        raise ValidationError(_('Unsupported expression inside salary formula: "%s"') % expr)

    return float(_eval(tree))


def apply_salary_bounds_and_rounding(value, min_amount=0.0, max_amount=0.0, rounding_method='two_decimals'):
    """Applies min/max ceilings and exact rounding rule to any computed component value."""
    val = float(value or 0.0)
    if min_amount and min_amount > 0 and val > 0:
        val = max(val, float(min_amount))
    if max_amount and max_amount > 0:
        val = min(val, float(max_amount))

    d = Decimal(str(val))
    if rounding_method == 'nearest_taka':
        return float(d.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    if rounding_method == 'round_up':
        return float(d.quantize(Decimal('1'), rounding=ROUND_CEILING))
    if rounding_method == 'round_down':
        return float(d.quantize(Decimal('1'), rounding=ROUND_FLOOR))
    if rounding_method == 'none':
        return val
    return float(d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


COMPONENT_CATEGORY_SELECTION = [
    ('basic', 'Basic Salary (মূল বেতন)'),
    ('allowance', 'Regular Allowance (নিয়মিত ভাতা)'),
    ('bonus_incentive', 'Bonus & Incentive (বোনাস ও প্রণোদনা)'),
    ('overtime_variable', 'Overtime & Variable Pay (অতিরিক্ত কাজ ও পরিবর্তনশীল আয়)'),
    ('employer_benefit', 'Employer Benefits & Perquisites (কোম্পানির প্রদত্ত সুবিধা)'),
    ('deduction', 'Employee Deductions (কর্মীর বেতন থেকে কর্তন)'),
    ('employer_contribution', 'Employer Contributions (কোম্পানির অতিরিক্ত অবদান)'),
]

CALCULATION_TYPE_SELECTION = [
    ('fixed', 'Fixed Amount (নির্দিষ্ট পরিমাণ ৳)'),
    ('percentage', 'Percentage (% হার)'),
    ('formula', 'Formula (কাস্টম ফর্মুলা)'),
    ('attendance_based', 'Attendance / Prorated Based (উপস্থিতি ভিত্তিক)'),
]

BASED_ON_SELECTION = [
    ('gross', 'Gross Salary (মোট গ্রস বেতন)'),
    ('basic', 'Basic Salary (মূল বেতন)'),
    ('other_component', 'Other Salary Component (অন্য কম্পোনেন্ট)'),
]

ROUNDING_METHOD_SELECTION = [
    ('two_decimals', '2 Decimals (০.০১ পয়সা)'),
    ('nearest_taka', 'Nearest Taka (পূর্ণ টাকায় রাউন্ড)'),
    ('round_up', 'Round Up / Ceiling (উপরের পূর্ণ টাকা)'),
    ('round_down', 'Round Down / Floor (নিচের পূর্ণ টাকা)'),
    ('none', 'No Rounding'),
]


def _category_to_head_type(category):
    if category in ('basic', 'allowance'):
        return 'earning'
    if category in ('bonus_incentive', 'overtime_variable'):
        return 'variable_earning'
    if category == 'deduction':
        return 'deduction'
    if category == 'employer_benefit':
        return 'employer_benefit'
    if category == 'employer_contribution':
        return 'employer_contribution'
    return 'earning'


# =============================================================================
# 2. SALARY COMPONENT MASTER (`dsl.salary.head`) — ALL 7 CATEGORIES & RULES
# =============================================================================
class DslSalaryHead(models.Model):
    _name = 'dsl.salary.head'
    _description = 'Bangladesh Salary Component Master (Allowance, Deduction, Benefit & Employer Contribution)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence asc, id asc'

    sequence = fields.Integer(string='Payslip Sequence', default=10)
    active = fields.Boolean(string='Record Active', default=True)
    is_active = fields.Boolean(string='Enabled in Policy', default=True, tracking=True)

    name = fields.Char(string='Salary Component Name', required=True, tracking=True)
    name_bn = fields.Char(string='বাংলা নাম (Bengali Name)', tracking=True)
    code = fields.Char(
        string='Unique Component Code',
        required=True,
        tracking=True,
        index=True,
        help='Unique uppercase code (e.g. BASIC, HRA, DEARNESS_ALLOWANCE, DAILY_ALLOWANCE, PF_EMPLOYEE, PF_EMPLOYER).',
    )

    # 7 Recommended Database Categories + Mapped Payroll Pillar (`head_type`)
    category = fields.Selection(
        selection=COMPONENT_CATEGORY_SELECTION,
        string='Structure Category',
        default='allowance',
        required=True,
        tracking=True,
        index=True,
    )
    head_type = fields.Selection(
        selection=[
            ('earning', 'Earnings / Regular Allowances'),
            ('variable_earning', 'Bonus, Overtime & Variable Pay'),
            ('deduction', 'Employee Salary Deductions'),
            ('employer_contribution', 'Employer Contributions & Provisions'),
            ('employer_benefit', 'Employer Non-Cash Benefits & Perquisites'),
        ],
        string='Payroll Pillar',
        compute='_compute_head_type',
        store=True,
        readonly=False,
    )
    sub_group = fields.Char(
        string='Section / Industry Group',
        help='e.g. Basic & Regular, Food & Daily, Festival & Annual, Performance, Shift & OT, Travel & Field, Factory/NGO, Perquisite, Deduction, Employer Contribution.',
    )

    # Calculation Engine Configuration (Section 14)
    calculation_type = fields.Selection(
        selection=CALCULATION_TYPE_SELECTION,
        string='Calculation Type',
        default='fixed',
        required=True,
        tracking=True,
    )
    amount = fields.Float(string='Default Fixed Amount (৳)', default=0.0)
    percentage = fields.Float(string='Default Percentage (%)', default=0.0)
    based_on = fields.Selection(
        selection=BASED_ON_SELECTION,
        string='Percentage Based On',
        default='basic',
    )
    based_on_head_id = fields.Many2one(
        'dsl.salary.head',
        string='Reference Component',
        help='Used when Based On = Other Salary Component.',
    )
    formula = fields.Char(
        string='Calculation Formula',
        help='Python math expression using GROSS, BASIC, HRA, MEDICAL, PRESENT_DAYS, CALENDAR_DAYS, OT_HOURS (e.g. `(GROSS - 2450) / 1.5`).',
    )

    # Backwards-compatible aliases
    default_calc_type = fields.Selection(
        selection=[
            ('fixed', 'Fixed Monthly Amount (৳)'),
            ('pct_basic', 'Percentage of Basic (%)'),
            ('pct_gross', 'Percentage of Gross (%)'),
        ],
        string='Quick Calc Basis',
        default='fixed',
    )
    default_value = fields.Float(string='Quick Default Value', default=0.0)

    # Statutory, Tax, PF, OT, Bonus & Compliance Flags (Section 14)
    is_taxable = fields.Boolean(string='Taxable (NBR)', default=True, tracking=True)
    tax_treatment = fields.Selection(
        selection=[
            ('fully_taxable', 'Fully Taxable Salary (1/3rd Pool under Income Tax Act 2023)'),
            ('non_taxable_reimbursement', 'Non-Taxable Official Reimbursement / Exempt'),
            ('perquisite_valuation', 'Non-Cash Perquisite Valuation (NBR Paripatra Rule)'),
            ('employer_non_salary', 'Employer Provision (Outside Employee Taxable Cash)'),
        ],
        string='NBR Tax Treatment',
        default='fully_taxable',
    )
    is_pf_applicable = fields.Boolean(string='Included in PF Base', default=False)
    is_ot_applicable = fields.Boolean(string='Included in OT Base', default=False)
    is_bonus_applicable = fields.Boolean(string='Included in Festival Bonus Base', default=False)

    is_recurring = fields.Boolean(string='Monthly Recurring', default=True)
    is_prorated = fields.Boolean(string='Attendance Prorated (LWP/Joining)', default=True)
    min_amount = fields.Float(string='Minimum Limit (৳)', default=0.0)
    max_amount = fields.Float(string='Maximum Ceiling (৳)', default=0.0)
    rounding_method = fields.Selection(
        selection=ROUNDING_METHOD_SELECTION,
        string='Rounding Method',
        default='two_decimals',
        required=True,
    )
    approval_required = fields.Boolean(
        string='Explicit Approval / Consent Required',
        default=False,
        help='Mandatory under Bangladesh Labour Act 2006 (Sec 125) for Late Adjustment, Damage Recovery, Court Order & Other Deductions.',
    )

    # Effective Dates, Entity Scope & COA Accounting Mapping (Section 14)
    effective_from = fields.Date(string='Effective From')
    effective_to = fields.Date(string='Effective To')
    company_id = fields.Many2one('res.company', string='Legal Entity (Blank = All Group Companies)')
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Specific Branch / Plant',
        domain="[('company_id', '=', company_id)]",
    )
    account_code = fields.Char(string='GL Expense / Liability Code', help='e.g. 510100 - Basic Salary Expense')
    debit_account_code = fields.Char(string='COA Debit Account', help='e.g. 510100 Salary & Allowances')
    credit_account_code = fields.Char(string='COA Credit Account', help='e.g. 210300 Accrued Payroll / Payable')
    notes = fields.Text(string='Statutory / Policy Notes')

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)', 'Component Code must be unique per Legal Entity / Company!'),
    ]

    @api.depends('category')
    def _compute_head_type(self):
        for rec in self:
            rec.head_type = _category_to_head_type(rec.category)

    @api.onchange('name')
    def _onchange_name_suggest_code(self):
        if self.name and not self.code:
            slug = re.sub(r'[^A-Z0-9]+', '_', self.name.upper()).strip('_')
            self.code = slug[:32] if slug else 'CUSTOM_COMP'

    @api.onchange('calculation_type', 'amount', 'percentage', 'based_on')
    def _onchange_sync_quick_defaults(self):
        if self.calculation_type == 'percentage':
            self.default_calc_type = 'pct_gross' if self.based_on == 'gross' else 'pct_basic'
            self.default_value = self.percentage
        else:
            self.default_calc_type = 'fixed'
            self.default_value = self.amount

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code') and vals.get('name'):
                base_slug = re.sub(r'[^A-Z0-9]+', '_', str(vals['name']).upper()).strip('_')[:28] or 'CUSTOM_HEAD'
                candidate = base_slug
                suffix = 1
                comp_id = vals.get('company_id') or False
                while self.sudo().with_context(active_test=False).search_count([
                    ('code', '=', candidate),
                    ('company_id', '=', comp_id),
                ]):
                    suffix += 1
                    candidate = f"{base_slug}_{suffix}"
                vals['code'] = candidate
            if 'amount' in vals and 'default_value' not in vals and vals.get('calculation_type', 'fixed') == 'fixed':
                vals['default_value'] = vals['amount']
            elif 'percentage' in vals and 'default_value' not in vals and vals.get('calculation_type') == 'percentage':
                vals['default_value'] = vals['percentage']
        return super().create(vals_list)

    def _evaluate_component_value(
        self,
        calc_type=None,
        amount=0.0,
        percentage=0.0,
        based_on='basic',
        based_on_code=None,
        formula=None,
        context_vars=None,
        min_amt=None,
        max_amt=None,
        rounding=None,
    ):
        """Evaluates exact BDT value for Fixed / Percentage / Formula / Attendance-Based rules."""
        self.ensure_one()
        vars_map = dict(context_vars or {})
        ctype = calc_type or self.calculation_type or 'fixed'
        raw_val = 0.0

        if ctype == 'fixed':
            raw_val = float(amount if amount is not None else self.amount)
        elif ctype == 'percentage':
            pct = float(percentage if percentage is not None else self.percentage)
            b_mode = based_on or self.based_on or 'basic'
            if b_mode == 'gross':
                base_val = float(vars_map.get('GROSS', 0.0))
            elif b_mode == 'other_component':
                ref_code = based_on_code or (self.based_on_head_id.code if self.based_on_head_id else '')
                base_val = float(vars_map.get(ref_code, 0.0))
            else:
                base_val = float(vars_map.get('BASIC', 0.0))
            raw_val = base_val * (pct / 100.0)
        elif ctype == 'formula':
            expr = formula if formula is not None else self.formula
            raw_val = safe_eval_salary_formula(expr, vars_map)
        elif ctype == 'attendance_based':
            cal_days = max(float(vars_map.get('CALENDAR_DAYS', 30.0)), 1.0)
            payable_days = float(vars_map.get('PAYABLE_DAYS', cal_days))
            base_fixed = float(amount if amount is not None else self.amount)
            if not base_fixed and (percentage or self.percentage):
                pct = float(percentage if percentage is not None else self.percentage)
                b_val = float(vars_map.get('GROSS' if (based_on or self.based_on) == 'gross' else 'BASIC', 0.0))
                base_fixed = b_val * (pct / 100.0)
            raw_val = base_fixed * (payable_days / cal_days)

        eff_min = self.min_amount if min_amt is None else min_amt
        eff_max = self.max_amount if max_amt is None else max_amt
        eff_rnd = self.rounding_method if rounding is None else rounding
        return apply_salary_bounds_and_rounding(raw_val, eff_min, eff_max, eff_rnd)


# =============================================================================
# 3. SALARY STRUCTURE TEMPLATE (`dsl.salary.structure`) & RULES (`dsl.salary.structure.rule`)
# =============================================================================
class DslSalaryStructure(models.Model):
    _name = 'dsl.salary.structure'
    _description = 'Company / Grade / Designation Salary Structure Template'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    name = fields.Char(string='Structure Template Name', required=True, tracking=True)
    code = fields.Char(string='Structure Code', required=True, tracking=True)
    sector_type = fields.Selection(
        selection=[
            ('corporate', 'Corporate / Head Office'),
            ('software_it', 'Software / IT & Tech'),
            ('garments_rmg', 'Garments / RMG & Textile'),
            ('factory_mfg', 'Factory / Industrial Manufacturing'),
            ('ngo_dev', 'NGO / Development & Project'),
            ('healthcare', 'Hospital / Healthcare & Pharma'),
        ],
        string='Industry / Policy Sector',
        default='corporate',
        required=True,
    )
    company_id = fields.Many2one('res.company', string='Legal Entity (Blank = Group Template)')
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Specific Branch / Plant',
        domain="[('company_id', '=', company_id)]",
    )
    job_id = fields.Many2one('hr.job', string='Target Designation (Optional)')
    effective_from = fields.Date(string='Effective From')
    effective_to = fields.Date(string='Effective To')
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )

    formula_mode = fields.Selection(
        selection=[
            ('corporate_pct', 'Corporate Percentage Split (% of Gross)'),
            ('rmg_wage_board', 'BD Garments / Factory Wage Board ((Gross - Fixed) / 1.5 = Basic)'),
            ('rule_engine', '100% Custom Rule-Driven Template (Rule Lines)'),
        ],
        string='Core Gross Formula',
        default='corporate_pct',
        required=True,
        tracking=True,
    )

    # Corporate Percentage Defaults (Total = 100% of Gross)
    basic_pct = fields.Float(string='Basic (%)', default=50.0, tracking=True)
    house_rent_pct = fields.Float(string='House Rent (%)', default=25.0, tracking=True)
    medical_pct = fields.Float(string='Medical (%)', default=10.0, tracking=True)
    conveyance_pct = fields.Float(string='Conveyance (%)', default=10.0, tracking=True)
    food_special_pct = fields.Float(string='Special / Food (%)', default=5.0, tracking=True)

    # Garments / Industrial Minimum Wage Board Fixed Allowances
    rmg_medical_fixed = fields.Monetary(string='Fixed Medical (৳)', currency_field='currency_id', default=750.0)
    rmg_conveyance_fixed = fields.Monetary(string='Fixed Conveyance (৳)', currency_field='currency_id', default=450.0)
    rmg_food_fixed = fields.Monetary(string='Fixed Food Subsidy (৳)', currency_field='currency_id', default=1250.0)
    rmg_hra_of_basic_pct = fields.Float(string='House Rent (% of Basic)', default=50.0)

    # Default Provident Fund, Employer Contribution, Attendance Bonus & Stamp
    default_pf_applicable = fields.Boolean(string='Enable Employee PF by Default', default=False)
    default_pf_pct = fields.Float(string='Employee PF (% of Basic)', default=10.0)
    default_employer_pf_pct = fields.Float(string='Employer PF (% of Basic)', default=10.0)
    default_gratuity_provision_pct = fields.Float(string='Employer Gratuity Provision (% of Basic)', default=0.0)

    enable_attendance_bonus = fields.Boolean(
        string='Grant Monthly Attendance Bonus (Zero Absent/Late)',
        default=False,
        tracking=True,
    )
    default_attendance_bonus = fields.Monetary(
        string='Attendance Bonus Amount (৳)',
        currency_field='currency_id',
        default=750.0,
    )
    apply_revenue_stamp = fields.Boolean(
        string='Deduct BD Revenue Stamp (৳10 when Net ≥ ৳400)',
        default=True,
    )
    revenue_stamp_amount = fields.Monetary(
        string='Revenue Stamp Fee (৳)',
        currency_field='currency_id',
        default=10.0,
    )
    late_days_per_deduction = fields.Integer(
        string='Late Count per 1-Day Deduction (0 = Disabled)',
        default=3,
        help='Standard BD HR Rule: 3 unexcused late arrivals deduct 1 day Basic wage (set 0 to disable).',
    )

    # Configurable Component Rules attached to this Structure Template!
    rule_ids = fields.One2many(
        'dsl.salary.structure.rule',
        'structure_id',
        string='Configurable Allowance, Deduction, Benefit & Contribution Rules',
    )
    notes = fields.Text(string='Structure Policy Notes')

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)', 'Salary Structure Code must be unique per Company!'),
    ]

    @api.constrains('formula_mode', 'basic_pct', 'house_rent_pct', 'medical_pct', 'conveyance_pct', 'food_special_pct')
    def _check_corporate_pct_sum(self):
        for rec in self:
            if rec.formula_mode == 'corporate_pct':
                total = round(
                    rec.basic_pct + rec.house_rent_pct + rec.medical_pct + rec.conveyance_pct + rec.food_special_pct, 2
                )
                if abs(total - 100.0) > 0.05:
                    raise ValidationError(_(
                        'Corporate percentage components for %s must sum to 100%% of Gross (currently %s%%)!'
                    ) % (rec.name, total))

    def _compute_breakdown_dict(self, gross_amount):
        """Pure helper returning exact core component dictionary for any Gross BDT amount."""
        self.ensure_one()
        gross = float(gross_amount or 0.0)
        if gross <= 0:
            return {
                'basic': 0.0,
                'hra': 0.0,
                'medical': 0.0,
                'conveyance': 0.0,
                'food_special': 0.0,
                'att_bonus': float(self.default_attendance_bonus if self.enable_attendance_bonus else 0.0),
            }

        if self.formula_mode == 'rmg_wage_board':
            med = float(self.rmg_medical_fixed or 0.0)
            conv = float(self.rmg_conveyance_fixed or 0.0)
            food = float(self.rmg_food_fixed or 0.0)
            fixed_sum = med + conv + food
            rem = max(gross - fixed_sum, 0.0)
            factor = 1.0 + ((self.rmg_hra_of_basic_pct or 50.0) / 100.0)
            basic = round(rem / factor, 2) if factor > 0 else rem
            hra = round(rem - basic, 2)
            return {
                'basic': basic,
                'hra': hra,
                'medical': med,
                'conveyance': conv,
                'food_special': food,
                'att_bonus': float(self.default_attendance_bonus if self.enable_attendance_bonus else 0.0),
            }

        if self.formula_mode == 'rule_engine' and self.rule_ids:
            vars_map = {'GROSS': gross, 'BASIC': 0.0, 'HRA': 0.0, 'MEDICAL': 0.0, 'CONVEYANCE': 0.0, 'FOOD': 0.0}
            for rl in self.rule_ids.filtered(lambda r: r.is_active).sorted(lambda r: r.sequence):
                val = rl._evaluate_rule(vars_map)
                vars_map[rl.code] = val
                if rl.code == 'BASIC':
                    vars_map['BASIC'] = val
            return {
                'basic': vars_map.get('BASIC', 0.0),
                'hra': vars_map.get('HRA', 0.0),
                'medical': vars_map.get('MEDICAL', vars_map.get('MED', 0.0)),
                'conveyance': vars_map.get('CONVEYANCE', vars_map.get('CONV', 0.0)),
                'food_special': vars_map.get('SPECIAL', vars_map.get('FOOD', 0.0)),
                'att_bonus': vars_map.get('ATTENDANCE_BONUS', vars_map.get('ATT_BON', 0.0)),
            }

        basic = round(gross * (self.basic_pct / 100.0), 2)
        hra = round(gross * (self.house_rent_pct / 100.0), 2)
        med = round(gross * (self.medical_pct / 100.0), 2)
        conv = round(gross * (self.conveyance_pct / 100.0), 2)
        food_spec = round(gross - (basic + hra + med + conv), 2)
        return {
            'basic': basic,
            'hra': hra,
            'medical': med,
            'conveyance': conv,
            'food_special': max(food_spec, 0.0),
            'att_bonus': float(self.default_attendance_bonus if self.enable_attendance_bonus else 0.0),
        }

    def action_open_salary_component_master(self):
        return self.env.ref('DSL_HRMS_salary_structure.action_dsl_salary_head').read()[0]


class DslSalaryStructureRule(models.Model):
    _name = 'dsl.salary.structure.rule'
    _description = 'Salary Structure Component Calculation Rule'
    _order = 'sequence asc, id asc'

    sequence = fields.Integer(string='Sequence', default=10)
    is_active = fields.Boolean(string='Enabled', default=True)
    structure_id = fields.Many2one(
        'dsl.salary.structure',
        string='Salary Structure',
        required=True,
        ondelete='cascade',
        index=True,
    )
    head_id = fields.Many2one(
        'dsl.salary.head',
        string='Salary Component',
        required=True,
    )
    code = fields.Char(related='head_id.code', string='Code', store=True, readonly=True)
    category = fields.Selection(related='head_id.category', string='Category', store=True, readonly=True)
    calculation_type = fields.Selection(
        selection=CALCULATION_TYPE_SELECTION,
        string='Calculation Type',
        default='percentage',
        required=True,
    )
    amount = fields.Float(string='Fixed Amount (৳)', default=0.0)
    percentage = fields.Float(string='Percentage (%)', default=0.0)
    based_on = fields.Selection(
        selection=BASED_ON_SELECTION,
        string='Based On',
        default='basic',
    )
    based_on_head_id = fields.Many2one('dsl.salary.head', string='Ref. Component')
    formula = fields.Char(string='Formula')
    is_recurring = fields.Boolean(string='Recurring', default=True)
    is_prorated = fields.Boolean(string='Prorated', default=True)
    min_amount = fields.Float(string='Min (৳)', default=0.0)
    max_amount = fields.Float(string='Max (৳)', default=0.0)
    rounding_method = fields.Selection(
        selection=ROUNDING_METHOD_SELECTION,
        string='Rounding',
        default='two_decimals',
        required=True,
    )
    approval_required = fields.Boolean(string='Approval Req.', default=False)
    notes = fields.Char(string='Rule Note')

    @api.onchange('head_id')
    def _onchange_head_copy_defaults(self):
        if self.head_id:
            self.sequence = self.head_id.sequence
            self.calculation_type = self.head_id.calculation_type
            self.amount = self.head_id.amount
            self.percentage = self.head_id.percentage
            self.based_on = self.head_id.based_on
            self.based_on_head_id = self.head_id.based_on_head_id
            self.formula = self.head_id.formula
            self.is_recurring = self.head_id.is_recurring
            self.is_prorated = self.head_id.is_prorated
            self.min_amount = self.head_id.min_amount
            self.max_amount = self.head_id.max_amount
            self.rounding_method = self.head_id.rounding_method
            self.approval_required = self.head_id.approval_required

    def _evaluate_rule(self, context_vars):
        self.ensure_one()
        return self.head_id._evaluate_component_value(
            calc_type=self.calculation_type,
            amount=self.amount,
            percentage=self.percentage,
            based_on=self.based_on,
            based_on_code=self.based_on_head_id.code if self.based_on_head_id else None,
            formula=self.formula,
            context_vars=context_vars,
            min_amt=self.min_amount,
            max_amt=self.max_amount,
            rounding=self.rounding_method,
        )


def _default_salary_structure(record=None):
    env = record.env if record is not None else None
    if not env:
        return False
    struct = env['dsl.salary.structure'].sudo().search(
        [('active', '=', True)], order='sequence asc, id asc', limit=1
    )
    return struct.id if struct else False


# =============================================================================
# 4. EMPLOYEE COMPENSATION PACKAGE (`dsl.employee.compensation`)
#    Separating: 1. Earnings/Allowances | 2. Employee Deductions | 3. Employer Contributions & Benefits
# =============================================================================
class DslEmployeeCompensation(models.Model):
    _name = 'dsl.employee.compensation'
    _description = 'Employee Salary Package (Earnings, Deductions, Employer Contributions & Perquisites)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'effective_from desc, id desc'

    name = fields.Char(
        string='Package Ref.',
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

    structure_id = fields.Many2one(
        'dsl.salary.structure',
        string='Salary Structure',
        required=True,
        default=_default_salary_structure,
        tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    revision_type = fields.Selection(
        selection=[
            ('joining', 'Initial Joining Package'),
            ('confirmation', 'Post-Probation Confirmation Increment'),
            ('annual_increment', 'Annual Increment'),
            ('promotion', 'Promotion / Grade Revision'),
            ('adjustment', 'Special / Market Adjustment'),
        ],
        string='Package Type',
        default='joining',
        required=True,
        tracking=True,
    )
    effective_from = fields.Date(
        string='Effective From',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    effective_to = fields.Date(string='Effective Until', tracking=True)

    # -------------------------------------------------------------------------
    # PILLAR 1: EARNINGS & ALLOWANCES (কর্মী যে টাকা পাবেন)
    # -------------------------------------------------------------------------
    gross_salary = fields.Monetary(
        string='Base Contract Gross (৳)',
        currency_field='currency_id',
        required=True,
        default=30000.0,
        tracking=True,
    )
    basic_salary = fields.Monetary(
        string='Basic Salary (৳)',
        currency_field='currency_id',
        compute='_compute_salary_breakdown',
        store=True,
        readonly=False,
        tracking=True,
    )
    house_rent = fields.Monetary(
        string='House Rent Allowance (৳)',
        currency_field='currency_id',
        compute='_compute_salary_breakdown',
        store=True,
        readonly=False,
    )
    medical_allowance = fields.Monetary(
        string='Medical Allowance (৳)',
        currency_field='currency_id',
        compute='_compute_salary_breakdown',
        store=True,
        readonly=False,
    )
    conveyance_allowance = fields.Monetary(
        string='Conveyance Allowance (৳)',
        currency_field='currency_id',
        compute='_compute_salary_breakdown',
        store=True,
        readonly=False,
    )
    food_special_allowance = fields.Monetary(
        string='Food / Special Allowance (৳)',
        currency_field='currency_id',
        compute='_compute_salary_breakdown',
        store=True,
        readonly=False,
    )
    attendance_bonus_amount = fields.Monetary(
        string='Attendance Bonus (৳)',
        currency_field='currency_id',
        compute='_compute_salary_breakdown',
        store=True,
        readonly=False,
    )

    # Quick Regular Allowance Fields + Unlimited Dynamic Allowance Lines
    mobile_internet_allowance = fields.Monetary(string='Mobile & Internet Allowance (৳)', currency_field='currency_id', default=0.0)
    car_fuel_allowance = fields.Monetary(string='Transport / Car & Fuel Allowance (৳)', currency_field='currency_id', default=0.0)
    dearness_allowance = fields.Monetary(string='Dearness / Cost of Living (৳)', currency_field='currency_id', default=0.0)
    technical_charge_allowance = fields.Monetary(string='Technical / Responsibility / Charge (৳)', currency_field='currency_id', default=0.0)
    tiffin_meal_allowance = fields.Monetary(string='Lunch / Tiffin / Meal Allowance (৳)', currency_field='currency_id', default=0.0)
    education_allowance = fields.Monetary(string='Qualification / Education Allowance (৳)', currency_field='currency_id', default=0.0)
    entertainment_utility_allowance = fields.Monetary(string='Utility / Housekeeping Allowance (৳)', currency_field='currency_id', default=0.0)
    hardship_site_allowance = fields.Monetary(string='Field / Site / Risk / Hardship (৳)', currency_field='currency_id', default=0.0)
    performance_fixed_incentive = fields.Monetary(string='Performance / Production Bonus (৳)', currency_field='currency_id', default=0.0)

    allowance_line_ids = fields.One2many(
        'dsl.compensation.line',
        'compensation_id',
        domain=[('line_type', '=', 'allowance')],
        string='Configurable Allowance & Bonus Components',
    )

    # -------------------------------------------------------------------------
    # PILLAR 2: EMPLOYEE SALARY DEDUCTIONS (বেতন থেকে যে টাকা কাটা হবে)
    # -------------------------------------------------------------------------
    pf_applicable = fields.Boolean(string='Enable Employee Provident Fund (PF_EMPLOYEE)', default=False, tracking=True)
    pf_employee_pct = fields.Float(string='Employee PF Rate (% of Basic)', default=10.0, tracking=True)
    pf_deduction_amount = fields.Monetary(
        string='Employee PF Deduction (৳)',
        currency_field='currency_id',
        compute='_compute_pf_employer_and_stamp',
        store=True,
        readonly=False,
        tracking=True,
    )
    tds_monthly_estimate = fields.Monetary(
        string='Income Tax / TDS (INCOME_TAX) (৳)',
        currency_field='currency_id',
        default=0.0,
        tracking=True,
    )
    welfare_fund_deduction = fields.Monetary(string='Welfare Fund (WELFARE_FUND) (৳)', currency_field='currency_id', default=0.0)
    group_insurance_deduction = fields.Monetary(string='Employee Insurance (INSURANCE_EMPLOYEE) (৳)', currency_field='currency_id', default=0.0)
    transport_deduction = fields.Monetary(string='Transport Recovery (TRANSPORT_RECOVERY) (৳)', currency_field='currency_id', default=0.0)
    lunch_canteen_deduction = fields.Monetary(string='Food / Meal Recovery (FOOD_RECOVERY) (৳)', currency_field='currency_id', default=0.0)
    accommodation_utility_deduction = fields.Monetary(string='Accommodation / Utility Recovery (৳)', currency_field='currency_id', default=0.0)
    security_deposit_deduction = fields.Monetary(string='Cooperative / Security Deposit (৳)', currency_field='currency_id', default=0.0)
    union_club_subscription = fields.Monetary(string='Club / Association Fee (৳)', currency_field='currency_id', default=0.0)
    apply_stamp_deduction = fields.Boolean(string='Deduct Revenue Stamp (৳10)', default=True)
    stamp_deduction_amount = fields.Monetary(
        string='Revenue Stamp (STAMP) (৳)',
        currency_field='currency_id',
        compute='_compute_pf_employer_and_stamp',
        store=True,
        readonly=False,
    )

    deduction_line_ids = fields.One2many(
        'dsl.compensation.line',
        'compensation_id',
        domain=[('line_type', '=', 'deduction')],
        string='Configurable Employee Deduction Components',
    )

    # -------------------------------------------------------------------------
    # PILLAR 3: EMPLOYER CONTRIBUTIONS & NON-CASH PERQUISITES (NOT DEDUCTED!)
    # -------------------------------------------------------------------------
    employer_pf_applicable = fields.Boolean(
        string='Enable Employer PF Contribution (PF_EMPLOYER)',
        default=False,
    )
    employer_pf_pct = fields.Float(string='Employer PF Rate (% of Basic)', default=10.0)
    employer_pf_amount = fields.Monetary(
        string='Employer PF Contribution (৳)',
        currency_field='currency_id',
        compute='_compute_pf_employer_and_stamp',
        store=True,
        readonly=False,
    )
    gratuity_provision_pct = fields.Float(
        string='Gratuity Provision (% of Basic)',
        default=0.0,
        help='e.g. 8.33% (1 Basic per year) or 12.5% (1.5 Basic per year after 10 yrs).',
    )
    gratuity_provision_amount = fields.Monetary(
        string='Monthly Gratuity Provision (৳)',
        currency_field='currency_id',
        compute='_compute_pf_employer_and_stamp',
        store=True,
        readonly=False,
    )
    employer_insurance_contribution = fields.Monetary(
        string='Employer Insurance Contribution (৳)',
        currency_field='currency_id',
        default=0.0,
    )
    employer_welfare_contribution = fields.Monetary(
        string='Employer Welfare / Pension Contribution (৳)',
        currency_field='currency_id',
        default=0.0,
    )

    employer_line_ids = fields.One2many(
        'dsl.compensation.line',
        'compensation_id',
        domain=[('line_type', '=', 'employer_contribution')],
        string='Employer Contributions & Provisions',
    )
    benefit_line_ids = fields.One2many(
        'dsl.compensation.line',
        'compensation_id',
        domain=[('line_type', '=', 'employer_benefit')],
        string='Employer-Provided Non-Cash Benefits & Perquisites',
    )

    # -------------------------------------------------------------------------
    # SUMMARY TOTALS: GROSS, DEDUCTIONS, ILLUSTRATIVE NET, EMPLOYER COST & CTC
    # -------------------------------------------------------------------------
    total_other_allowances = fields.Monetary(
        string='Additional Allowances (৳)',
        currency_field='currency_id',
        compute='_compute_package_summary_totals',
        store=True,
    )
    total_gross_package = fields.Monetary(
        string='Total Gross Salary (৳)',
        currency_field='currency_id',
        compute='_compute_package_summary_totals',
        store=True,
        tracking=True,
    )
    total_recurring_deductions = fields.Monetary(
        string='Total Employee Deductions (৳)',
        currency_field='currency_id',
        compute='_compute_package_summary_totals',
        store=True,
        tracking=True,
    )
    estimated_net_take_home = fields.Monetary(
        string='Illustrative Net Salary (৳)',
        currency_field='currency_id',
        compute='_compute_package_summary_totals',
        store=True,
        tracking=True,
    )
    total_employer_contributions = fields.Monetary(
        string='Employer Contributions (৳)',
        currency_field='currency_id',
        compute='_compute_package_summary_totals',
        store=True,
    )
    total_perquisite_valuation = fields.Monetary(
        string='Non-Cash Perquisite Value (৳)',
        currency_field='currency_id',
        compute='_compute_package_summary_totals',
        store=True,
    )
    total_ctc_monthly = fields.Monetary(
        string='Total Cost to Company / CTC (৳)',
        currency_field='currency_id',
        compute='_compute_package_summary_totals',
        store=True,
        tracking=True,
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active Package'),
            ('superseded', 'Superseded (History)'),
            ('closed', 'Closed'),
        ],
        string='Status',
        default='active',
        required=True,
        tracking=True,
        index=True,
    )
    remarks = fields.Text(string='Increment / Approval Remarks')
    odoo_contract_id = fields.Many2one(
        'hr.contract',
        string='Linked Odoo Contract',
        ondelete='set null',
        help='Automatically synchronized native Odoo hr.contract record (hr_contract).',
    )

    @api.depends(
        'gross_salary',
        'structure_id',
        'structure_id.formula_mode',
        'structure_id.basic_pct',
        'structure_id.house_rent_pct',
        'structure_id.medical_pct',
        'structure_id.conveyance_pct',
        'structure_id.food_special_pct',
        'structure_id.rmg_medical_fixed',
        'structure_id.rmg_conveyance_fixed',
        'structure_id.rmg_food_fixed',
        'structure_id.enable_attendance_bonus',
        'structure_id.default_attendance_bonus',
    )
    def _compute_salary_breakdown(self):
        for rec in self:
            if not rec.structure_id or not rec.gross_salary:
                rec.basic_salary = 0.0
                rec.house_rent = 0.0
                rec.medical_allowance = 0.0
                rec.conveyance_allowance = 0.0
                rec.food_special_allowance = 0.0
                rec.attendance_bonus_amount = 0.0
                continue
            bd = rec.structure_id._compute_breakdown_dict(rec.gross_salary)
            rec.basic_salary = bd['basic']
            rec.house_rent = bd['hra']
            rec.medical_allowance = bd['medical']
            rec.conveyance_allowance = bd['conveyance']
            rec.food_special_allowance = bd['food_special']
            rec.attendance_bonus_amount = bd['att_bonus']

    @api.depends(
        'basic_salary',
        'pf_applicable',
        'pf_employee_pct',
        'employer_pf_applicable',
        'employer_pf_pct',
        'gratuity_provision_pct',
        'apply_stamp_deduction',
        'structure_id',
        'structure_id.revenue_stamp_amount',
    )
    def _compute_pf_employer_and_stamp(self):
        for rec in self:
            basic = rec.basic_salary or 0.0
            rec.pf_deduction_amount = (
                round(basic * (rec.pf_employee_pct / 100.0), 2)
                if (rec.pf_applicable and basic > 0 and rec.pf_employee_pct > 0)
                else 0.0
            )
            rec.employer_pf_amount = (
                round(basic * (rec.employer_pf_pct / 100.0), 2)
                if (rec.employer_pf_applicable and basic > 0 and rec.employer_pf_pct > 0)
                else 0.0
            )
            rec.gratuity_provision_amount = (
                round(basic * (rec.gratuity_provision_pct / 100.0), 2)
                if (basic > 0 and rec.gratuity_provision_pct > 0)
                else 0.0
            )
            rec.stamp_deduction_amount = (
                (rec.structure_id.revenue_stamp_amount if (rec.structure_id and rec.structure_id.apply_revenue_stamp) else 10.0)
                if rec.apply_stamp_deduction
                else 0.0
            )

    @api.depends(
        'basic_salary',
        'house_rent',
        'medical_allowance',
        'conveyance_allowance',
        'food_special_allowance',
        'mobile_internet_allowance',
        'car_fuel_allowance',
        'dearness_allowance',
        'technical_charge_allowance',
        'tiffin_meal_allowance',
        'education_allowance',
        'entertainment_utility_allowance',
        'hardship_site_allowance',
        'performance_fixed_incentive',
        'allowance_line_ids.monthly_amount',
        'allowance_line_ids.is_active',
        'pf_deduction_amount',
        'tds_monthly_estimate',
        'welfare_fund_deduction',
        'group_insurance_deduction',
        'transport_deduction',
        'lunch_canteen_deduction',
        'accommodation_utility_deduction',
        'security_deposit_deduction',
        'union_club_subscription',
        'stamp_deduction_amount',
        'deduction_line_ids.monthly_amount',
        'deduction_line_ids.is_active',
        'employer_pf_amount',
        'gratuity_provision_amount',
        'employer_insurance_contribution',
        'employer_welfare_contribution',
        'employer_line_ids.monthly_amount',
        'employer_line_ids.is_active',
        'benefit_line_ids.monthly_amount',
        'benefit_line_ids.is_active',
    )
    def _compute_package_summary_totals(self):
        for rec in self:
            core_gross = round(
                (rec.basic_salary or 0.0)
                + (rec.house_rent or 0.0)
                + (rec.medical_allowance or 0.0)
                + (rec.conveyance_allowance or 0.0)
                + (rec.food_special_allowance or 0.0),
                2,
            )
            std_extra = (
                (rec.mobile_internet_allowance or 0.0)
                + (rec.car_fuel_allowance or 0.0)
                + (rec.dearness_allowance or 0.0)
                + (rec.technical_charge_allowance or 0.0)
                + (rec.tiffin_meal_allowance or 0.0)
                + (rec.education_allowance or 0.0)
                + (rec.entertainment_utility_allowance or 0.0)
                + (rec.hardship_site_allowance or 0.0)
                + (rec.performance_fixed_incentive or 0.0)
            )
            custom_extra = sum(rec.allowance_line_ids.filtered(lambda l: l.is_active).mapped('monthly_amount'))
            other_allow = round(std_extra + custom_extra, 2)
            tot_earn = round(core_gross + other_allow, 2)

            std_ded = (
                (rec.pf_deduction_amount or 0.0)
                + (rec.tds_monthly_estimate or 0.0)
                + (rec.welfare_fund_deduction or 0.0)
                + (rec.group_insurance_deduction or 0.0)
                + (rec.transport_deduction or 0.0)
                + (rec.lunch_canteen_deduction or 0.0)
                + (rec.accommodation_utility_deduction or 0.0)
                + (rec.security_deposit_deduction or 0.0)
                + (rec.union_club_subscription or 0.0)
                + (rec.stamp_deduction_amount or 0.0)
            )
            custom_ded = sum(rec.deduction_line_ids.filtered(lambda l: l.is_active).mapped('monthly_amount'))
            tot_ded = round(std_ded + custom_ded, 2)

            emp_contrib = round(
                (rec.employer_pf_amount or 0.0)
                + (rec.gratuity_provision_amount or 0.0)
                + (rec.employer_insurance_contribution or 0.0)
                + (rec.employer_welfare_contribution or 0.0)
                + sum(rec.employer_line_ids.filtered(lambda l: l.is_active).mapped('monthly_amount')),
                2,
            )
            perq_val = round(
                sum(rec.benefit_line_ids.filtered(lambda l: l.is_active).mapped('monthly_amount')),
                2,
            )

            rec.total_other_allowances = other_allow
            rec.total_gross_package = tot_earn
            rec.total_recurring_deductions = tot_ded
            rec.estimated_net_take_home = round(max(tot_earn - tot_ded, 0.0), 2)
            rec.total_employer_contributions = emp_contrib
            rec.total_perquisite_valuation = perq_val
            rec.total_ctc_monthly = round(tot_earn + emp_contrib + perq_val, 2)

    @api.onchange('structure_id')
    def _onchange_structure_apply_defaults(self):
        if self.structure_id:
            self.pf_applicable = self.structure_id.default_pf_applicable
            self.employer_pf_applicable = self.structure_id.default_pf_applicable
            if self.structure_id.default_pf_pct:
                self.pf_employee_pct = self.structure_id.default_pf_pct
            if self.structure_id.default_employer_pf_pct:
                self.employer_pf_pct = self.structure_id.default_employer_pf_pct
            if self.structure_id.default_gratuity_provision_pct:
                self.gratuity_provision_pct = self.structure_id.default_gratuity_provision_pct
            self.apply_stamp_deduction = self.structure_id.apply_revenue_stamp

    @api.onchange('employee_id')
    def _onchange_employee_sync_org(self):
        if self.employee_id:
            self.company_id = self.employee_id.company_id.id
            self.branch_id = self.employee_id.branch_id.id if self.employee_id.branch_id else False
            if 'dsl.employee.tax.assessment' in self.env:
                sheet = self.env['dsl.employee.tax.assessment'].sudo().search([
                    ('employee_id', '=', self.employee_id.id),
                    ('state', '=', 'active'),
                ], order='id desc', limit=1)
                if sheet and sheet.monthly_tds_amount:
                    self.tds_monthly_estimate = sheet.monthly_tds_amount

    def action_load_structure_rules(self):
        """1-Click Action: Copies non-core Allowance, Deduction, Benefit & Employer Contribution rules from Structure Template."""
        core_codes = {'BASIC', 'HRA', 'MEDICAL', 'MED', 'CONVEYANCE', 'CONV', 'FOOD', 'SPECIAL', 'ATTENDANCE_BONUS', 'ATT_BON', 'STAMP', 'INCOME_TAX', 'TDS'}
        for rec in self:
            if not rec.structure_id or not rec.structure_id.rule_ids:
                continue
            existing_codes = set(
                (rec.allowance_line_ids | rec.deduction_line_ids | rec.employer_line_ids | rec.benefit_line_ids).mapped('code')
            )
            new_vals = []
            for rl in rec.structure_id.rule_ids.filtered(lambda r: r.is_active and r.code not in core_codes):
                if rl.code in existing_codes:
                    continue
                if rl.code == 'PF_EMPLOYEE' and rec.pf_applicable:
                    continue
                if rl.code == 'PF_EMPLOYER' and rec.employer_pf_applicable:
                    continue
                if rl.code == 'GRATUITY' and rec.gratuity_provision_pct > 0:
                    continue

                l_type = 'allowance'
                if rl.category == 'deduction':
                    l_type = 'deduction'
                elif rl.category == 'employer_contribution':
                    l_type = 'employer_contribution'
                elif rl.category == 'employer_benefit':
                    l_type = 'employer_benefit'

                c_basis = 'fixed'
                r_val = rl.amount
                if rl.calculation_type == 'percentage':
                    c_basis = 'pct_gross' if rl.based_on == 'gross' else 'pct_basic'
                    r_val = rl.percentage
                elif rl.calculation_type == 'formula':
                    c_basis = 'formula'

                new_vals.append({
                    'compensation_id': rec.id,
                    'sequence': rl.sequence,
                    'is_active': True,
                    'line_type': l_type,
                    'head_id': rl.head_id.id,
                    'description': rl.head_id.name,
                    'calc_type': c_basis,
                    'rate_or_amount': r_val,
                    'formula': rl.formula,
                    'is_prorated': rl.is_prorated,
                    'min_amount': rl.min_amount,
                    'max_amount': rl.max_amount,
                    'rounding_method': rl.rounding_method,
                    'is_authorized': not rl.approval_required,
                })
            if new_vals:
                self.env['dsl.compensation.line'].sudo().create(new_vals)

    def _get_package_additional_allowance_items(self):
        """Returns ordered list of (seq, code, default_name, amount, is_prorated) for all active extra allowances."""
        self.ensure_one()
        items = [
            (52, 'MOBILE', 'Mobile & Internet Allowance', self.mobile_internet_allowance, False),
            (53, 'TRANSPORT', 'Transport / Car & Fuel Allowance', self.car_fuel_allowance, False),
            (54, 'DEARNESS_ALLOWANCE', 'Dearness / Cost of Living Allowance', self.dearness_allowance, True),
            (55, 'TECHNICAL', 'Technical / Responsibility / Charge Allowance', self.technical_charge_allowance, True),
            (56, 'TIFFIN', 'Lunch / Tiffin / Meal Allowance', self.tiffin_meal_allowance, True),
            (57, 'QUALIFICATION', 'Qualification / Education Allowance', self.education_allowance, False),
            (58, 'UTILITY', 'Utility & Housekeeping Allowance', self.entertainment_utility_allowance, False),
            (59, 'HARD_TO_REACH', 'Field / Site / Risk / Hardship Allowance', self.hardship_site_allowance, False),
            (62, 'PERFORMANCE', 'Performance / Production Bonus', self.performance_fixed_incentive, False),
        ]
        res = [(seq, code, label, amt) for seq, code, label, amt, _pro in items if amt and amt > 0]
        for idx, line in enumerate(self.allowance_line_ids.filtered(lambda l: l.is_active), start=1):
            if line.monthly_amount > 0:
                res.append((
                    line.sequence or (65 + idx),
                    line.head_id.code or f'ALLOW_{idx}',
                    line.description or line.head_id.name,
                    line.monthly_amount,
                ))
        return res

    def _get_package_recurring_deduction_items(self):
        """Returns ordered list of (seq, code, default_name, amount) for authorized recurring employee deductions."""
        self.ensure_one()
        items = [
            (135, 'PF_EMPLOYEE', f'Employee Provident Fund ({self.pf_employee_pct:g}% Basic)', self.pf_deduction_amount if self.pf_applicable else 0.0),
            (140, 'WELFARE_FUND', 'Welfare Fund Contribution', self.welfare_fund_deduction),
            (142, 'INSURANCE_EMPLOYEE', 'Employee Insurance Contribution', self.group_insurance_deduction),
            (144, 'TRANSPORT_RECOVERY', 'Transport Recovery', self.transport_deduction),
            (146, 'FOOD_RECOVERY', 'Food / Meal Recovery', self.lunch_canteen_deduction),
            (148, 'HOUSE_RENT_RECOVERY', 'Accommodation & Utility Recovery', self.accommodation_utility_deduction),
            (150, 'COOPERATIVE', 'Cooperative / Security Deposit', self.security_deposit_deduction),
            (152, 'UNION_CLUB_FEE', 'Club / Association Contribution', self.union_club_subscription),
        ]
        res = [(seq, code, label, amt) for seq, code, label, amt in items if amt and amt > 0]
        for idx, line in enumerate(self.deduction_line_ids.filtered(lambda l: l.is_active), start=1):
            if line.monthly_amount <= 0:
                continue
            if line.head_id.approval_required and not line.is_authorized:
                raise ValidationError(_(
                    'Statutory Compliance Check (Bangladesh Labour Act 2006): Deduction "%s (%s)" on %s requires explicit HR/Legal Authorization ("Authorized / Approved" checkbox) before deducting from wages!'
                ) % (line.head_id.name, line.head_id.code, self.employee_id.name))
            res.append((
                line.sequence or (155 + idx),
                line.head_id.code or f'DED_{idx}',
                line.description or line.head_id.name,
                line.monthly_amount,
            ))
        return res

    def _get_package_employer_and_benefit_items(self):
        """Returns ordered list of (seq, code, label, category_type, amount) for Employer Contributions & Perquisites (NOT deducted from employee!)."""
        self.ensure_one()
        res = []
        if self.employer_pf_applicable and self.employer_pf_amount > 0:
            res.append((210, 'PF_EMPLOYER', f'Employer Provident Fund ({self.employer_pf_pct:g}% Basic)', 'employer_contribution', self.employer_pf_amount))
        if self.gratuity_provision_amount > 0:
            res.append((215, 'GRATUITY', f'Gratuity Provision ({self.gratuity_provision_pct:g}% Basic)', 'employer_contribution', self.gratuity_provision_amount))
        if self.employer_insurance_contribution > 0:
            res.append((220, 'INSURANCE_EMPLOYER', 'Employer Insurance Contribution', 'employer_contribution', self.employer_insurance_contribution))
        if self.employer_welfare_contribution > 0:
            res.append((225, 'WELFARE_EMPLOYER', 'Employer Welfare / Pension Contribution', 'employer_contribution', self.employer_welfare_contribution))

        for idx, line in enumerate(self.employer_line_ids.filtered(lambda l: l.is_active and l.monthly_amount > 0), start=1):
            res.append((
                line.sequence or (230 + idx),
                line.head_id.code or f'EMP_CONTRIB_{idx}',
                line.description or line.head_id.name,
                'employer_contribution',
                line.monthly_amount,
            ))
        for idx, line in enumerate(self.benefit_line_ids.filtered(lambda l: l.is_active and l.monthly_amount > 0), start=1):
            res.append((
                line.sequence or (260 + idx),
                line.head_id.code or f'PERQ_{idx}',
                line.description or line.head_id.name,
                'employer_benefit',
                line.monthly_amount,
            ))
        return res

    def _sync_employee_salary_references(self):
        """Syncs active package Gross & Basic onto hr.employee and Odoo native hr.contract."""
        has_hr_contract = 'hr.contract' in self.env
        HrContract = self.env['hr.contract'].sudo().with_context(skip_dsl_contract_sync=True) if has_hr_contract else None
        for rec in self.filtered(lambda r: r.state == 'active' and r.employee_id):
            older = self.sudo().search([
                ('id', '!=', rec.id),
                ('employee_id', '=', rec.employee_id.id),
                ('state', '=', 'active'),
            ])
            if older:
                older.write({'state': 'superseded'})

            emp_vals = {}
            emp = rec.employee_id.sudo()
            gross_pkg = rec.total_gross_package or rec.gross_salary
            if 'ot_gross_reference' in emp._fields:
                emp_vals['ot_gross_reference'] = gross_pkg
            if 'ot_basic_reference' in emp._fields:
                emp_vals['ot_basic_reference'] = rec.basic_salary
            if emp_vals:
                emp.write(emp_vals)

            # Sync to Odoo Native hr.contract (hr_contract addon)
            if HrContract is not None:
                c_vals = {
                    'wage': gross_pkg,
                    'basic_wage': rec.basic_salary or 0.0,
                    'hra_allowance': rec.house_rent or 0.0,
                    'medical_allowance': rec.medical_allowance or 0.0,
                    'conveyance_allowance': rec.conveyance_allowance or 0.0,
                    'food_allowance': rec.food_special_allowance or 0.0,
                    'other_allowance': rec.total_other_allowances or 0.0,
                    'dsl_compensation_id': rec.id,
                }
                contract = rec.odoo_contract_id
                if not contract:
                    contract = HrContract.search([
                        ('employee_id', '=', emp.id),
                        ('state', '=', 'open'),
                    ], order='date_start desc, id desc', limit=1)
                if not contract:
                    contract = HrContract.search([
                        ('employee_id', '=', emp.id),
                    ], order='date_start desc, id desc', limit=1)
                if contract:
                    try:
                        contract.write(c_vals)
                        if rec.odoo_contract_id != contract:
                            super(DslEmployeeCompensation, rec.sudo()).write({'odoo_contract_id': contract.id})
                    except Exception:
                        pass
                else:
                    try:
                        c_vals.update({
                            'name': f"Contract - {emp.name}",
                            'employee_id': emp.id,
                            'company_id': (emp.company_id or self.env.company).id,
                            'department_id': emp.department_id.id if emp.department_id else False,
                            'job_id': emp.job_id.id if emp.job_id else False,
                            'date_start': rec.effective_from or getattr(emp, 'joining_date', False) or fields.Date.context_today(self),
                            'state': 'open',
                        })
                        created_c = HrContract.create(c_vals)
                        super(DslEmployeeCompensation, rec.sudo()).write({'odoo_contract_id': created_c.id})
                    except Exception:
                        pass

    @api.model_create_multi
    def create(self, vals_list):
        Employee = self.env['hr.employee'].sudo()
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.employee.compensation') or _('New')
            if vals.get('employee_id'):
                emp = Employee.browse(vals['employee_id'])
                if not vals.get('company_id') and emp.company_id:
                    vals['company_id'] = emp.company_id.id
                if not vals.get('branch_id') and emp.branch_id:
                    vals['branch_id'] = emp.branch_id.id
        records = super().create(vals_list)
        records._sync_employee_salary_references()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ('state', 'gross_salary', 'basic_salary', 'structure_id', 'mobile_internet_allowance', 'car_fuel_allowance')):
            self._sync_employee_salary_references()
        return res

    def action_activate(self):
        self.write({'state': 'active'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_open_salary_component_master(self):
        return self.env.ref('DSL_HRMS_salary_structure.action_dsl_salary_head').read()[0]


# =============================================================================
# 5. EMPLOYEE PACKAGE COMPONENT LINE (`dsl.compensation.line`)
# =============================================================================
class DslCompensationLine(models.Model):
    _name = 'dsl.compensation.line'
    _description = 'Employee Configurable Allowance, Deduction, Benefit or Contribution Line'
    _order = 'sequence asc, id asc'

    sequence = fields.Integer(default=10)
    is_active = fields.Boolean(string='Active', default=True)
    compensation_id = fields.Many2one(
        'dsl.employee.compensation',
        string='Compensation Package',
        required=True,
        ondelete='cascade',
        index=True,
    )
    line_type = fields.Selection(
        selection=[
            ('allowance', 'Allowance / Earning'),
            ('deduction', 'Employee Deduction'),
            ('employer_contribution', 'Employer Contribution'),
            ('employer_benefit', 'Non-Cash Benefit / Perquisite'),
        ],
        string='Pillar',
        default='allowance',
        required=True,
    )
    head_id = fields.Many2one(
        'dsl.salary.head',
        string='Component',
        required=True,
    )
    code = fields.Char(related='head_id.code', string='Code', store=True, readonly=True)
    category = fields.Selection(related='head_id.category', string='Category', readonly=True)
    approval_required = fields.Boolean(related='head_id.approval_required', readonly=True)
    is_authorized = fields.Boolean(
        string='Authorized / Consent',
        default=True,
        help='Confirms legal/employee consent for statutory deductions (BD Labour Act Sec 125).',
    )
    description = fields.Char(string='Label / Details')
    calc_type = fields.Selection(
        selection=[
            ('fixed', 'Fixed Amount (৳)'),
            ('pct_basic', '% of Basic'),
            ('pct_gross', '% of Base Gross'),
            ('formula', 'Custom Formula'),
        ],
        string='Calculation Basis',
        default='fixed',
        required=True,
    )
    rate_or_amount = fields.Float(
        string='Amount (৳) / Rate (%)',
        required=True,
        default=0.0,
    )
    formula = fields.Char(string='Formula', help='e.g. min(BASIC * 0.15, 10000)')
    is_prorated = fields.Boolean(string='Prorated', default=True)
    min_amount = fields.Float(string='Min (৳)', default=0.0)
    max_amount = fields.Float(string='Max (৳)', default=0.0)
    rounding_method = fields.Selection(
        selection=ROUNDING_METHOD_SELECTION,
        string='Rounding',
        default='two_decimals',
        required=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='compensation_id.currency_id',
        readonly=True,
    )
    monthly_amount = fields.Monetary(
        string='Monthly Amount (৳)',
        currency_field='currency_id',
        compute='_compute_monthly_amount',
        store=True,
    )

    @api.onchange('head_id')
    def _onchange_head_populate_defaults(self):
        if self.head_id:
            self.sequence = self.head_id.sequence
            self.description = (
                f"{self.head_id.name} ({self.head_id.name_bn})"
                if self.head_id.name_bn
                else self.head_id.name
            )
            self.is_prorated = self.head_id.is_prorated
            self.min_amount = self.head_id.min_amount
            self.max_amount = self.head_id.max_amount
            self.rounding_method = self.head_id.rounding_method
            self.is_authorized = not self.head_id.approval_required

            if self.head_id.calculation_type == 'formula' and self.head_id.formula:
                self.calc_type = 'formula'
                self.formula = self.head_id.formula
            elif self.head_id.calculation_type == 'percentage' and self.head_id.percentage:
                self.calc_type = 'pct_gross' if self.head_id.based_on == 'gross' else 'pct_basic'
                self.rate_or_amount = self.head_id.percentage
            elif self.head_id.amount:
                self.calc_type = 'fixed'
                self.rate_or_amount = self.head_id.amount
            elif self.head_id.default_value:
                self.calc_type = self.head_id.default_calc_type or 'fixed'
                self.rate_or_amount = self.head_id.default_value

    @api.depends(
        'is_active',
        'calc_type',
        'rate_or_amount',
        'formula',
        'min_amount',
        'max_amount',
        'rounding_method',
        'compensation_id.basic_salary',
        'compensation_id.gross_salary',
        'compensation_id.house_rent',
        'compensation_id.medical_allowance',
    )
    def _compute_monthly_amount(self):
        for ln in self:
            if not ln.is_active:
                ln.monthly_amount = 0.0
                continue
            val = float(ln.rate_or_amount or 0.0)
            basic = float(ln.compensation_id.basic_salary or 0.0)
            gross = float(ln.compensation_id.gross_salary or 0.0)
            if ln.calc_type == 'pct_basic':
                raw = basic * (val / 100.0)
            elif ln.calc_type == 'pct_gross':
                raw = gross * (val / 100.0)
            elif ln.calc_type == 'formula':
                raw = safe_eval_salary_formula(ln.formula, {
                    'GROSS': gross,
                    'BASIC': basic,
                    'HRA': float(ln.compensation_id.house_rent or 0.0),
                    'MEDICAL': float(ln.compensation_id.medical_allowance or 0.0),
                })
            else:
                raw = val
            ln.monthly_amount = apply_salary_bounds_and_rounding(
                raw, ln.min_amount, ln.max_amount, ln.rounding_method
            )


class HrEmployeeSalaryExt(models.Model):
    _inherit = 'hr.employee'

    dsl_compensation_ids = fields.One2many(
        'dsl.employee.compensation',
        'employee_id',
        string='Compensation & Increment History',
        groups='hr.group_hr_user',
    )
    active_compensation_id = fields.Many2one(
        'dsl.employee.compensation',
        string='Active Salary Package',
        compute='_compute_active_compensation',
        groups='hr.group_hr_user',
    )
    current_gross_salary = fields.Monetary(
        string='Total Monthly Gross (৳)',
        currency_field='company_currency_id',
        compute='_compute_active_compensation',
        groups='hr.group_hr_user',
    )
    current_basic_salary = fields.Monetary(
        string='Monthly Basic (৳)',
        currency_field='company_currency_id',
        compute='_compute_active_compensation',
        groups='hr.group_hr_user',
    )
    current_monthly_deductions = fields.Monetary(
        string='Employee Deductions (৳)',
        currency_field='company_currency_id',
        compute='_compute_active_compensation',
        groups='hr.group_hr_user',
    )
    current_net_take_home = fields.Monetary(
        string='Illustrative Net Salary (৳)',
        currency_field='company_currency_id',
        compute='_compute_active_compensation',
        groups='hr.group_hr_user',
    )
    current_ctc_monthly = fields.Monetary(
        string='Total Company CTC (৳)',
        currency_field='company_currency_id',
        compute='_compute_active_compensation',
        groups='hr.group_hr_user',
    )
    company_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Compensation Currency',
        readonly=True,
    )

    def _compute_active_compensation(self):
        Comp = self.env['dsl.employee.compensation'].sudo()
        for emp in self:
            pkg = Comp.search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'active'),
            ], order='effective_from desc, id desc', limit=1)
            emp.active_compensation_id = pkg.id if pkg else False
            emp.current_gross_salary = (pkg.total_gross_package or pkg.gross_salary) if pkg else 0.0
            emp.current_basic_salary = pkg.basic_salary if pkg else 0.0
            emp.current_monthly_deductions = pkg.total_recurring_deductions if pkg else 0.0
            emp.current_net_take_home = pkg.estimated_net_take_home if pkg else 0.0
            emp.current_ctc_monthly = pkg.total_ctc_monthly if pkg else 0.0

    def action_open_compensation_packages(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Salary Packages',
            'res_model': 'dsl.employee.compensation',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {
                'default_employee_id': self.id,
                'default_company_id': self.company_id.id,
                'default_branch_id': self.branch_id.id if self.branch_id else False,
            },
        }


class HrContractSalaryBreakdownExt(models.Model):
    _inherit = 'hr.contract'

    dsl_compensation_id = fields.Many2one(
        'dsl.employee.compensation',
        string='DSL Compensation Package',
        ondelete='set null',
    )
    basic_wage = fields.Monetary(string='Basic Salary (BDT)', currency_field='currency_id')
    hra_allowance = fields.Monetary(string='House Rent Allowance (BDT)', currency_field='currency_id')
    medical_allowance = fields.Monetary(string='Medical Allowance (BDT)', currency_field='currency_id')
    conveyance_allowance = fields.Monetary(string='Conveyance Allowance (BDT)', currency_field='currency_id')
    food_allowance = fields.Monetary(string='Food / Special Allowance (BDT)', currency_field='currency_id')
    other_allowance = fields.Monetary(string='Other Fixed Allowances (BDT)', currency_field='currency_id')

