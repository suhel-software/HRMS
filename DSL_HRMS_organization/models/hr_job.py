# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrJobOrg(models.Model):
    _inherit = 'hr.job'

    job_code = fields.Char(string='Designation Code', index=True)
    division_id = fields.Many2one(
        'dsl.hr.division',
        string='Division / Wing',
    )
    grade_id = fields.Many2one(
        'dsl.hr.grade',
        string='Pay Grade / Band',
    )
    grade_level = fields.Selection(
        selection=[
            ('entry', 'Entry / Junior Level'),
            ('officer', 'Officer / Executive'),
            ('senior_officer', 'Senior Officer / Specialist'),
            ('assistant_manager', 'Assistant / Deputy Manager'),
            ('manager', 'Manager'),
            ('senior_manager', 'Senior / AGM / DGM'),
            ('general_manager', 'General Manager / VP'),
            ('director', 'C-Suite / Director'),
        ],
        string='Hierarchy Tier',
        default='officer',
    )
    employee_category = fields.Selection(
        selection=[
            ('management', 'Management Cadre'),
            ('staff', 'Non-Management Staff'),
            ('worker', 'Factory / Floor Worker'),
            ('contractual', 'Contractual / Consultant'),
            ('intern', 'Intern / Apprentice'),
        ],
        string='Workforce Cadre',
        default='staff',
    )
    is_ot_eligible = fields.Boolean(
        string='Overtime (OT) Eligible',
        default=False,
        help='Eligible for double-basic overtime calculation per Bangladesh Labour Act',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    min_salary = fields.Monetary(string='Min Gross Salary', currency_field='currency_id')
    max_salary = fields.Monetary(string='Max Gross Salary', currency_field='currency_id')

    @api.onchange('grade_id')
    def _onchange_grade_id_salary_band(self):
        if self.grade_id:
            self.min_salary = self.grade_id.min_salary
            self.max_salary = self.grade_id.max_salary


class HrEmployeeOrg(models.Model):
    _inherit = 'hr.employee'

    division_id = fields.Many2one(
        'dsl.hr.division',
        string='Division / Wing',
        tracking=True,
    )
    grade_id = fields.Many2one(
        'dsl.hr.grade',
        string='Pay Grade',
        tracking=True,
    )
    cost_center_id = fields.Many2one(
        'dsl.cost.center',
        string='Cost Center',
        domain="[('company_id', '=', company_id)]",
    )
    dotted_manager_id = fields.Many2one(
        'hr.employee',
        string='Functional / Dotted Manager',
        domain="[('id', '!=', id)]",
    )

    @api.onchange('department_id')
    def _onchange_department_org_defaults(self):
        if self.department_id:
            if self.department_id.division_id and not self.division_id:
                self.division_id = self.department_id.division_id
            if self.department_id.cost_center_id and not self.cost_center_id:
                self.cost_center_id = self.department_id.cost_center_id

    @api.onchange('job_id')
    def _onchange_job_org_defaults(self):
        if self.job_id and self.job_id.grade_id and not self.grade_id:
            self.grade_id = self.job_id.grade_id


class HrEmployeePublicOrg(models.Model):
    _inherit = 'hr.employee.public'

    division_id = fields.Many2one('dsl.hr.division', string='Division / Wing', readonly=True)
    grade_id = fields.Many2one('dsl.hr.grade', string='Pay Grade', readonly=True)
    cost_center_id = fields.Many2one('dsl.cost.center', string='Cost Center', readonly=True)
    dotted_manager_id = fields.Many2one('hr.employee.public', string='Functional / Dotted Manager', readonly=True)

