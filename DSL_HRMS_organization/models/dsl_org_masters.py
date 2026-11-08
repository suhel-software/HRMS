# -*- coding: utf-8 -*-
from odoo import api, fields, models


class DslHrDivision(models.Model):
    _name = 'dsl.hr.division'
    _description = 'Corporate Division / Business Wing'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Division / Wing Name', required=True, tracking=True)
    code = fields.Char(string='Division Code', required=True, tracking=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Branch / Location',
        domain="[('company_id', '=', company_id)]",
        index=True,
    )
    head_id = fields.Many2one(
        'hr.employee',
        string='Division Head',
        tracking=True,
    )
    department_ids = fields.One2many(
        'hr.department',
        'division_id',
        string='Departments',
    )
    department_count = fields.Integer(compute='_compute_division_counts', string='Department Count')
    employee_count = fields.Integer(compute='_compute_division_counts', string='Employee Count')
    description = fields.Text(string='Mandate & Scope')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)', 'Division Code must be unique per Company!'),
    ]

    def _compute_division_counts(self):
        Employee = self.env['hr.employee'].sudo()
        for rec in self:
            rec.department_count = len(rec.department_ids)
            rec.employee_count = Employee.search_count([('division_id', '=', rec.id)])


class DslHrGrade(models.Model):
    _name = 'dsl.hr.grade'
    _description = 'Job Grade & Pay Scale Band'
    _order = 'sequence, code'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Grade Title', required=True)
    code = fields.Char(string='Grade Code', required=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        help='Leave empty to share across all group companies.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    min_salary = fields.Monetary(string='Minimum Gross Salary', currency_field='currency_id')
    max_salary = fields.Monetary(string='Maximum Gross Salary', currency_field='currency_id')
    basic_pct = fields.Float(string='Basic % of Gross', default=50.0)
    house_rent_pct = fields.Float(string='House Rent % of Basic', default=50.0)
    medical_pct = fields.Float(string='Medical % of Basic', default=10.0)
    conveyance_pct = fields.Float(string='Conveyance % of Basic', default=10.0)
    benefit_notes = fields.Text(string='Grade Entitlements & Perks')
    job_count = fields.Integer(compute='_compute_grade_counts', string='Designations')
    employee_count = fields.Integer(compute='_compute_grade_counts', string='Employees')
    active = fields.Boolean(default=True)

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for grade in self:
            grade.display_name = f"[{grade.code}] {grade.name}" if grade.code else grade.name

    def _compute_grade_counts(self):
        Job = self.env['hr.job'].sudo()
        Employee = self.env['hr.employee'].sudo()
        for rec in self:
            rec.job_count = Job.search_count([('grade_id', '=', rec.id)])
            rec.employee_count = Employee.search_count([('grade_id', '=', rec.id)])


class DslCostCenter(models.Model):
    _name = 'dsl.cost.center'
    _description = 'HR & Payroll Cost Center'
    _order = 'code, name'

    name = fields.Char(string='Cost Center Name', required=True)
    code = fields.Char(string='Cost Center Code', required=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Branch / Location',
        domain="[('company_id', '=', company_id)]",
        index=True,
    )
    department_id = fields.Many2one('hr.department', string='Primary Department')
    manager_id = fields.Many2one('hr.employee', string='Budget Owner')
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True,
    )
    annual_budget = fields.Monetary(string='Annual Manpower Budget', currency_field='currency_id')
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Odoo Analytic Account',
        ondelete='set null',
        help='Automatically linked Odoo native Analytic Account for cost center financial tracking.',
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)', 'Cost Center Code must be unique per Company!'),
    ]

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for cc in self:
            cc.display_name = f"[{cc.code}] {cc.name}" if cc.code else cc.name

    def _sync_to_odoo_analytic_account(self):
        if self.env.context.get('skip_dsl_analytic_sync') or 'account.analytic.account' not in self.env:
            return
        AnalyticAccount = self.env['account.analytic.account'].sudo().with_context(skip_dsl_analytic_sync=True)
        AnalyticPlan = self.env['account.analytic.plan'].sudo()
        default_plan = AnalyticPlan.search([], limit=1)
        if not default_plan:
            default_plan = AnalyticPlan.create({'name': 'HR & Payroll Cost Centers'})
        for cc in self.sudo():
            vals = {
                'name': cc.name,
                'code': cc.code,
                'company_id': cc.company_id.id if cc.company_id else False,
                'plan_id': default_plan.id,
            }
            if 'dsl_cost_center_id' in AnalyticAccount._fields:
                vals['dsl_cost_center_id'] = cc.id
            if cc.analytic_account_id:
                cc.analytic_account_id.sudo().with_context(skip_dsl_analytic_sync=True).write(vals)
            else:
                existing = AnalyticAccount.search([
                    ('code', '=', cc.code),
                    ('company_id', 'in', [cc.company_id.id, False]),
                ], limit=1)
                if existing:
                    existing.write(vals)
                    cc.with_context(skip_dsl_analytic_sync=True).write({'analytic_account_id': existing.id})
                else:
                    created = AnalyticAccount.create(vals)
                    cc.with_context(skip_dsl_analytic_sync=True).write({'analytic_account_id': created.id})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_to_odoo_analytic_account()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_dsl_analytic_sync') and any(k in vals for k in ('name', 'code', 'company_id')):
            self._sync_to_odoo_analytic_account()
        return res


class AccountAnalyticAccountDslExt(models.Model):
    _inherit = 'account.analytic.account'

    dsl_cost_center_id = fields.Many2one(
        'dsl.cost.center',
        string='DSL HR Cost Center',
        ondelete='set null',
    )

