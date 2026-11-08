# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResCompanyBranches(models.Model):
    _inherit = 'res.company'

    dsl_branch_ids = fields.One2many(
        'dsl.branch',
        'company_id',
        string='Operational Branches & Plants',
    )
    dsl_branch_total = fields.Integer(
        string='Total Branches',
        compute='_compute_dsl_branch_total',
    )

    def _compute_dsl_branch_total(self):
        Branch = self.env['dsl.branch'].sudo()
        for comp in self:
            comp.dsl_branch_total = Branch.search_count([('company_id', '=', comp.id)])


class HrEmployeeBranchDefaults(models.Model):
    _inherit = 'hr.employee'

    @api.onchange('department_id')
    def _onchange_department_set_branch(self):
        if self.department_id and self.department_id.branch_id and not self.branch_id:
            self.branch_id = self.department_id.branch_id
