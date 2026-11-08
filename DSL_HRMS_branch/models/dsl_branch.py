# -*- coding: utf-8 -*-
from odoo import api, fields, models


class DslBranch(models.Model):
    _name = 'dsl.branch'
    _description = 'Company Branch / Operational Location'
    _inherit = ['dsl.branch', 'mail.thread', 'mail.activity.mixin']
    _order = 'company_id, sequence, name'

    name = fields.Char(tracking=True)
    code = fields.Char(tracking=True)
    company_id = fields.Many2one(tracking=True)
    active = fields.Boolean(tracking=True)

    parent_branch_id = fields.Many2one(
        'dsl.branch',
        string='Parent / Regional Hub',
        domain="[('company_id', '=', company_id), ('id', '!=', id)]",
    )
    child_branch_ids = fields.One2many(
        'dsl.branch',
        'parent_branch_id',
        string='Sub-Branches',
    )
    branch_type = fields.Selection(
        selection=[
            ('hq', 'Corporate Head Office'),
            ('regional', 'Regional Office'),
            ('factory', 'Factory / Industrial Plant'),
            ('warehouse', 'Warehouse / Distribution Hub'),
            ('showroom', 'Showroom / Sales Center'),
            ('project', 'Project / Site Office'),
        ],
        string='Location Type',
        default='regional',
        required=True,
        tracking=True,
    )

    # Branch Accounting & Chart of Accounts (COA) Engine:
    # Supports BOTH "2–3 Branches Sharing 1 COA/Account" (`shared`) AND "Dedicated Separate Branch COA" (`separate`)!
    coa_mode = fields.Selection(
        selection=[
            ('shared', 'Shared / Grouped COA (1 Account for Company or 2–3 Branches)'),
            ('separate', 'Dedicated Separate COA (Standalone Branch Books & Ledgers)'),
        ],
        string='COA & Accounting Mode',
        default='shared',
        required=True,
        tracking=True,
        help="Choose 'Shared / Grouped COA' so 2–3+ branches share one Chart of Accounts, "
             "or 'Dedicated Separate COA' to give this branch its own 100% standalone Chart of Accounts.",
    )
    accounting_company_id = fields.Many2one(
        'res.company',
        string='COA / Books of Account Entity',
        tracking=True,
        help='The standalone legal COA entity where financial/payroll ledgers of this branch are maintained. '
             '2–3 branches can select the same COA entity to share 1 account.',
    )
    branch_bank_name = fields.Char(string='Salary Disbursement Bank')
    branch_bank_acc = fields.Char(string='Branch Bank A/C No.')
    branch_tin_bin = fields.Char(string='Branch BIN / Tax Unit No.')

    manager_id = fields.Many2one(
        'hr.employee',
        string='Branch / Plant Head',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        tracking=True,
    )
    hr_incharge_id = fields.Many2one(
        'hr.employee',
        string='HR In-Charge',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    working_hours_id = fields.Many2one(
        'resource.calendar',
        string='Default Work Schedule',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    # Contact & Address
    phone = fields.Char(string='Phone')
    mobile = fields.Char(string='Mobile')
    email = fields.Char(string='Official Email')
    website = fields.Char(string='Location URL / Map Link')
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Area / Industrial Zone')
    city = fields.Char(string='City / District')
    state_id = fields.Many2one('res.country.state', string='Division / State')
    zip = fields.Char(string='Postal Code')
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        default=lambda self: self.env.ref('base.bd', raise_if_not_found=False),
    )

    # Operations, Compliance & Geofence Coordinates
    establishment_date = fields.Date(string='Establishment Date')
    factory_reg_no = fields.Char(string='DIFE / Local License No.')
    capacity = fields.Integer(string='Approved Headcount Capacity', default=100)
    latitude = fields.Float(string='GPS Latitude', digits=(10, 7))
    longitude = fields.Float(string='GPS Longitude', digits=(10, 7))
    geofence_radius = fields.Float(
        string='Geofence Radius (Meters)',
        default=150.0,
        help='Allowed radius in meters for mobile GPS attendance check-in',
    )

    color = fields.Integer(string='Color Index')

    employee_count = fields.Integer(
        string='Employees',
        compute='_compute_branch_counts',
    )
    department_count = fields.Integer(
        string='Departments',
        compute='_compute_branch_counts',
    )

    @api.onchange('company_id', 'coa_mode')
    def _onchange_coa_mode_default(self):
        if self.coa_mode == 'shared' and not self.accounting_company_id and self.company_id:
            self.accounting_company_id = self.company_id

    @api.model_create_multi
    def create(self, vals_list):
        branches = super().create(vals_list)
        branches._ensure_branch_coa_entity()
        return branches

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_branch_coa_sync') and any(
            k in vals for k in ('coa_mode', 'accounting_company_id', 'company_id')
        ):
            self._ensure_branch_coa_entity()
        return res

    def _ensure_branch_coa_entity(self):
        """Ensure every branch has a valid `accounting_company_id`:
        - If `coa_mode == 'separate'`: automatically provision a dedicated standalone Root COA entity (`parent_id = False`)
          if not already linked to a separate COA entity.
        - If `coa_mode == 'shared'`: default to `company_id` unless the admin linked a shared cluster COA entity."""
        Company = self.env['res.company'].sudo()
        for branch in self.sudo():
            if branch.coa_mode == 'separate':
                if not branch.accounting_company_id or branch.accounting_company_id.id == branch.company_id.id:
                    coa_code = f"{branch.code}-COA"
                    coa_name = f"{branch.name} ({branch.code} COA)"
                    existing_coa = Company.search([
                        '|', ('name', '=', coa_name),
                        ('short_code', '=', coa_code) if 'short_code' in Company._fields else ('name', '=', coa_name)
                    ], limit=1)
                    if not existing_coa:
                        comp_vals = {
                            'name': coa_name,
                            'parent_id': False,  # 100% Standalone Root Chart of Accounts!
                            'currency_id': branch.company_id.currency_id.id,
                            'country_id': (branch.country_id or branch.company_id.country_id).id,
                            'city': branch.city or branch.company_id.city,
                        }
                        if 'short_code' in Company._fields:
                            comp_vals['short_code'] = coa_code
                        if 'company_type' in Company._fields:
                            comp_vals['company_type'] = 'branch_coa'
                        if 'group_parent_id' in Company._fields:
                            comp_vals['group_parent_id'] = branch.company_id.id
                        existing_coa = Company.create(comp_vals)
                    branch.with_context(skip_branch_coa_sync=True).write({
                        'accounting_company_id': existing_coa.id
                    })
            else:
                if not branch.accounting_company_id and branch.company_id:
                    branch.with_context(skip_branch_coa_sync=True).write({
                        'accounting_company_id': branch.company_id.id
                    })

    def _compute_branch_counts(self):
        Employee = self.env['hr.employee'].sudo()
        Department = self.env['hr.department'].sudo()
        for branch in self:
            branch.employee_count = Employee.search_count([('branch_id', '=', branch.id)])
            branch.department_count = Department.search_count([('branch_id', '=', branch.id)])

    def action_view_employees(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Employees',
            'res_model': 'hr.employee',
            'view_mode': 'kanban,list,form',
            'domain': [('branch_id', '=', self.id)],
            'context': {
                'default_branch_id': self.id,
                'default_company_id': self.company_id.id,
            },
        }

    def action_view_departments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Departments',
            'res_model': 'hr.department',
            'view_mode': 'kanban,list,form',
            'domain': [('branch_id', '=', self.id)],
            'context': {
                'default_branch_id': self.id,
                'default_company_id': self.company_id.id,
            },
        }
