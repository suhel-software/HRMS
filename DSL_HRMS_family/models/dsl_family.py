# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models


class DslEmployeeFamily(models.Model):
    _name = 'dsl.employee.family'
    _description = 'Employee Family Member & Dependent'
    _order = 'is_dependent desc, relationship, id'

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
    name = fields.Char(string='Member Full Name', required=True)
    name_bn = fields.Char(string='সদস্যের নাম (বাংলায়)')
    relationship = fields.Selection(
        selection=[
            ('spouse', 'Spouse (Husband / Wife)'),
            ('son', 'Son'),
            ('daughter', 'Daughter'),
            ('father', 'Father'),
            ('mother', 'Mother'),
            ('brother', 'Brother'),
            ('sister', 'Sister'),
            ('other', 'Other Dependent'),
        ],
        string='Relationship',
        required=True,
        default='spouse',
    )
    gender = fields.Selection(
        selection=[
            ('male', 'Male'),
            ('female', 'Female'),
            ('other', 'Other'),
        ],
        string='Gender',
    )
    date_of_birth = fields.Date(string='Date of Birth')
    age_years = fields.Integer(
        string='Age (Yrs)',
        compute='_compute_age_years',
    )
    blood_group = fields.Selection(
        selection=[
            ('A+', 'A+'), ('A-', 'A-'),
            ('B+', 'B+'), ('B-', 'B-'),
            ('AB+', 'AB+'), ('AB-', 'AB-'),
            ('O+', 'O+'), ('O-', 'O-'),
        ],
        string='Blood Group',
    )
    occupation = fields.Char(string='Occupation / Student Class')
    nid_or_birth_reg = fields.Char(string='NID / Birth Reg. No.')
    phone = fields.Char(string='Contact Phone')

    is_dependent = fields.Boolean(string='Dependent', default=True)
    is_medical_insured = fields.Boolean(
        string='Group Health Insured',
        default=False,
        help='Covered under Company Group Hospitalization / Maternity Insurance Policy.',
    )
    insurance_card_no = fields.Char(string='Health Card / Policy ID')
    is_emergency_contact = fields.Boolean(string='Emergency Contact', default=False)
    photo = fields.Binary(string='Member Photo', attachment=True)
    notes = fields.Text(string='Special Medical / Welfare Notes')

    @api.depends('date_of_birth')
    def _compute_age_years(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.date_of_birth and rec.date_of_birth <= today:
                rec.age_years = relativedelta(today, rec.date_of_birth).years
            else:
                rec.age_years = 0


class HrEmployeeFamilyInherit(models.Model):
    _inherit = 'hr.employee'

    family_member_ids = fields.One2many(
        'dsl.employee.family',
        'employee_id',
        string='Family & Dependents',
        groups='hr.group_hr_user',
    )
    family_member_count = fields.Integer(
        string='Dependents',
        compute='_compute_family_counts',
        groups='hr.group_hr_user',
    )
    insured_dependent_count = fields.Integer(
        string='Insured Family',
        compute='_compute_family_counts',
        groups='hr.group_hr_user',
    )

    def _compute_family_counts(self):
        Fam = self.env['dsl.employee.family'].sudo()
        for emp in self:
            emp.family_member_count = Fam.search_count([('employee_id', '=', emp.id)])
            emp.insured_dependent_count = Fam.search_count([
                ('employee_id', '=', emp.id),
                ('is_medical_insured', '=', True),
            ])

    def action_view_family_members(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Family & Dependents',
            'res_model': 'dsl.employee.family',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

