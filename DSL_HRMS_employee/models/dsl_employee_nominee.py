# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DslEmployeeNominee(models.Model):
    _name = 'dsl.employee.nominee'
    _description = 'Employee Statutory Nominee (PF / Gratuity / Group Insurance)'
    _order = 'benefit_scope, share_percentage desc, id'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='employee_id.company_id',
        store=True,
        index=True,
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Branch',
        related='employee_id.branch_id',
        store=True,
        index=True,
    )
    name = fields.Char(string='Nominee Full Name', required=True)
    name_bn = fields.Char(string='নমিনির নাম (বাংলায়)')
    relationship = fields.Selection(
        selection=[
            ('spouse', 'Spouse'),
            ('son', 'Son'),
            ('daughter', 'Daughter'),
            ('father', 'Father'),
            ('mother', 'Mother'),
            ('brother', 'Brother'),
            ('sister', 'Sister'),
            ('other', 'Other Legal Heir'),
        ],
        string='Relationship',
        required=True,
        default='spouse',
    )
    benefit_scope = fields.Selection(
        selection=[
            ('all', 'All Statutory Benefits (PF, Gratuity & Insurance)'),
            ('pf', 'Provident Fund (PF) Only'),
            ('gratuity', 'Gratuity / Service Benefit Only'),
            ('insurance', 'Group Life / Medical Insurance Only'),
        ],
        string='Benefit Coverage',
        default='all',
        required=True,
    )
    share_percentage = fields.Float(
        string='Share (%)',
        default=100.0,
        required=True,
    )
    nid_or_birth_reg = fields.Char(string='NID / Birth Reg. No.')
    date_of_birth = fields.Date(string='Date of Birth')
    phone = fields.Char(string='Contact Phone')
    address = fields.Char(string='Address')
    is_minor = fields.Boolean(string='Minor (Under 18)', default=False)
    guardian_name = fields.Char(string='Legal Guardian (If Minor)')
    guardian_nid = fields.Char(string='Guardian NID')
    photo = fields.Binary(string='Nominee Photo', attachment=True)

    @api.constrains('share_percentage', 'benefit_scope', 'employee_id')
    def _check_nominee_share_percentage(self):
        for rec in self.sudo():
            if rec.share_percentage <= 0 or rec.share_percentage > 100:
                raise ValidationError(_('Nominee share percentage must be between 0.01% and 100%!'))

        for emp in self.sudo().mapped('employee_id'):
            nominees = emp.nominee_ids
            for scope in ('pf', 'gratuity', 'insurance'):
                applicable = nominees.filtered(lambda n: n.benefit_scope in ('all', scope))
                total_pct = sum(applicable.mapped('share_percentage'))
                if total_pct > 100.001:
                    raise ValidationError(_(
                        'Total nominee share for %s (%s) cannot exceed 100%% (currently %.2f%%)!'
                    ) % (emp.name, scope.upper(), total_pct))

