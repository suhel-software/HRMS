# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


def _default_meal_item(record=None):
    env = record.env if record is not None else None
    if not env:
        return False
    it = env['dsl.canteen.meal.item'].sudo().search([('active', '=', True)], order='id asc', limit=1)
    return it.id if it else False


class DslCanteenMealItem(models.Model):
    _name = 'dsl.canteen.meal.item'
    _description = 'Canteen Meal Package & Subsidy Policy'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id asc'

    active = fields.Boolean(default=True)
    name = fields.Char(string='Meal Item / Package', required=True, tracking=True)
    meal_slot = fields.Selection(
        selection=[
            ('breakfast', 'Breakfast / Tiffin'),
            ('lunch', 'Corporate / Factory Lunch'),
            ('evening_snacks', 'Evening / OT Snacks'),
            ('dinner', 'Night Shift Dinner'),
            ('sehri_iftar', 'Ramadan Iftar / Sehri'),
        ],
        string='Meal Slot',
        default='lunch',
        required=True,
    )
    unit_cost = fields.Float(string='Full Cost per Meal (৳)', default=140.0, required=True)
    company_subsidy = fields.Float(string='Employer Subsidy (৳)', default=80.0)
    employee_payable = fields.Float(string='Employee Share (৳)', compute='_compute_emp_share', store=True)

    @api.depends('unit_cost', 'company_subsidy')
    def _compute_emp_share(self):
        for rec in self:
            rec.employee_payable = round(max((rec.unit_cost or 0.0) - (rec.company_subsidy or 0.0), 0.0), 2)


class DslCanteenMealLog(models.Model):
    _name = 'dsl.canteen.meal.log'
    _description = 'Employee Canteen Meal Booking & Consumption Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'meal_date desc, id desc'

    name = fields.Char(string='Token Ref.', required=True, copy=False, readonly=True, default=lambda self: _('New'), index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company, index=True)
    branch_id = fields.Many2one('dsl.branch', string='Branch / Canteen', domain="[('company_id', '=', company_id)]")
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    meal_item_id = fields.Many2one('dsl.canteen.meal.item', string='Meal Package', required=True, default=_default_meal_item)
    meal_date = fields.Date(string='Date', default=fields.Date.context_today, required=True, index=True)
    meal_count = fields.Integer(string='Meals / Days Count', default=1, required=True)

    employer_subsidy_total = fields.Monetary(string='Company Subsidy (৳)', currency_field='currency_id', compute='_compute_amounts', store=True)
    employee_deduction_total = fields.Monetary(string='Employee Deduction (৳)', currency_field='currency_id', compute='_compute_amounts', store=True, tracking=True)
    payslip_id = fields.Many2one('dsl.payslip', string='Deducted in Payslip', readonly=True)
    is_deducted = fields.Boolean(string='Recovered in Payroll', default=False, readonly=True)

    state = fields.Selection(
        selection=[
            ('booked', 'Booked / Consumed'),
            ('settled', 'Deducted in Payroll'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='booked',
        required=True,
        tracking=True,
    )

    @api.depends('meal_item_id', 'meal_count')
    def _compute_amounts(self):
        for rec in self:
            cnt = max(rec.meal_count or 0, 0)
            sub = (rec.meal_item_id.company_subsidy or 0.0) if rec.meal_item_id else 0.0
            emp_p = (rec.meal_item_id.employee_payable or 0.0) if rec.meal_item_id else 0.0
            rec.employer_subsidy_total = round(cnt * sub, 2)
            rec.employee_deduction_total = round(cnt * emp_p, 2)

    @api.onchange('employee_id')
    def _onchange_emp_sync(self):
        if self.employee_id:
            self.company_id = self.employee_id.company_id.id
            self.branch_id = self.employee_id.branch_id.id if self.employee_id.branch_id else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.canteen.meal.log') or _('New')
        return super().create(vals_list)

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class DslPayslipCanteenHook(models.Model):
    _inherit = 'dsl.payslip'

    canteen_log_ids = fields.Many2many('dsl.canteen.meal.log', string='Canteen Meal Logs', readonly=True, copy=False)

    def _get_extra_benefit_lines(self):
        res = super()._get_extra_benefit_lines()
        logs = self.env['dsl.canteen.meal.log'].sudo().search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'booked'),
            ('is_deducted', '=', False),
            ('meal_date', '>=', self.date_from),
            ('meal_date', '<=', self.date_to),
        ])
        self.canteen_log_ids = [(6, 0, logs.ids)]
        emp_total = round(sum(logs.mapped('employee_deduction_total')), 2)
        if emp_total > 0:
            total_meals = sum(logs.mapped('meal_count'))
            res.append({
                'sequence': 168,
                'code': 'FOOD_RECOVERY',
                'name': f"Canteen Meal Charge ({total_meals} Meals)",
                'category': 'deduction',
                'amount': emp_total,
            })
        return res

    def action_mark_paid(self):
        res = super().action_mark_paid()
        for rec in self:
            if rec.canteen_log_ids:
                rec.canteen_log_ids.sudo().write({
                    'is_deducted': True,
                    'payslip_id': rec.id,
                    'state': 'settled',
                })
        return res

