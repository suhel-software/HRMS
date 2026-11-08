# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    short_code = fields.Char(
        string='Entity Short Code',
        help='Short identifier for payroll & employee ID prefixes (e.g. DSL-HQ, DSL-TEX)',
    )
    company_type = fields.Selection(
        selection=[
            ('holding', 'Mother / Holding Company'),
            ('subsidiary', 'Subsidiary Company'),
            ('sister', 'Sister Concern'),
            ('associate', 'Associate / Joint Venture'),
            ('branch_coa', 'Branch / Unit (Separate COA)'),
        ],
        string='Entity Classification',
        default='holding',
        required=True,
    )
    # Dedicated Corporate Group Link so each entity stays a 100% standalone Root Company
    # (`parent_id = False`) with its own separate Chart of Accounts (COA), Currency & Balance Sheet!
    group_parent_id = fields.Many2one(
        'res.company',
        string='Mother / Holding Company',
        index=True,
        ondelete='set null',
        help='Corporate Group Parent. Unlike Odoo tax branches, linking here keeps a 100% separate Chart of Accounts (COA) and Currency.',
    )
    group_child_ids = fields.One2many(
        'res.company',
        'group_parent_id',
        string='Sub-Companies, Sister Concerns & JVs',
    )
    is_mother_company = fields.Boolean(
        string='Is Mother Company',
        compute='_compute_is_mother_company',
        store=True,
        readonly=False,
    )
    independent_coa = fields.Boolean(
        string='Separate Chart of Accounts (COA)',
        compute='_compute_independent_coa',
        help='True when this company is a standalone legal root entity with its own independent Chart of Accounts.',
    )

    # Bangladesh Legal & Statutory Compliance
    tin_number = fields.Char(string='e-TIN Number')
    bin_number = fields.Char(string='BIN / VAT Reg. No.')
    tax_zone = fields.Char(string='Tax Zone')
    tax_circle = fields.Char(string='Tax Circle')
    trade_license_no = fields.Char(string='Trade License No.')
    trade_license_expiry = fields.Date(string='Trade License Expiry')
    trade_license_status = fields.Selection(
        selection=[
            ('valid', 'Valid'),
            ('expiring_soon', 'Expiring Soon'),
            ('expired', 'Expired'),
            ('not_set', 'Not Set'),
        ],
        string='License Status',
        compute='_compute_trade_license_status',
    )
    incorporation_no = fields.Char(string='RJSC Registration No.')
    incorporation_date = fields.Date(string='Date of Incorporation')
    factory_license_no = fields.Char(string='DIFE Establishment / Factory License')

    # Key Corporate Leadership
    managing_director_id = fields.Many2one(
        'hr.employee',
        string='Managing Director / CEO',
    )
    hr_head_id = fields.Many2one(
        'hr.employee',
        string='Head of HR',
    )

    # Organizational Counters
    employee_count = fields.Integer(
        string='Employees',
        compute='_compute_hrms_counts',
    )
    subsidiary_count = fields.Integer(
        string='Sub-Companies',
        compute='_compute_hrms_counts',
    )
    department_count = fields.Integer(
        string='Departments',
        compute='_compute_hrms_counts',
    )
    user_access_count = fields.Integer(
        string='Authorized Users',
        compute='_compute_hrms_counts',
    )
    has_branch_module = fields.Boolean(
        compute='_compute_hrms_counts',
    )
    dsl_company_branch_count = fields.Integer(
        string='Operational Branches',
        compute='_compute_hrms_counts',
    )

    @api.constrains('group_parent_id')
    def _check_group_parent_recursion(self):
        for company in self.sudo():
            visited = {company.id}
            curr = company.group_parent_id
            while curr:
                if curr.id in visited:
                    raise ValidationError(_('Error! You cannot create a circular Mother / Sub-Company hierarchy.'))
                visited.add(curr.id)
                curr = curr.group_parent_id

    @api.depends('group_parent_id', 'company_type')
    def _compute_is_mother_company(self):
        for company in self:
            company.is_mother_company = (
                company.company_type == 'holding' or not bool(company.group_parent_id)
            )

    @api.depends('parent_id')
    def _compute_independent_coa(self):
        for company in self:
            company.independent_coa = not bool(company.parent_id)

    @api.onchange('group_parent_id')
    def _onchange_group_parent_id_entity_type(self):
        if self.group_parent_id and self.company_type == 'holding':
            self.company_type = 'subsidiary'
        elif not self.group_parent_id:
            self.company_type = 'holding'

    def _get_all_group_descendants(self):
        """Return all recursive Subsidiary, Sister Concern, and JV companies under `self`."""
        descendants = self.env['res.company'].sudo()
        visited = set(self.ids)
        queue = list(self.sudo().mapped('group_child_ids'))
        while queue:
            child = queue.pop(0)
            if child.id not in visited:
                visited.add(child.id)
                descendants |= child
                queue.extend(child.group_child_ids)
        return descendants

    def _get_all_group_ancestors(self):
        """Return all ancestor Holding / Mother companies above `self`."""
        ancestors = self.env['res.company'].sudo()
        visited = set(self.ids)
        for comp in self.sudo():
            curr = comp.group_parent_id
            while curr and curr.id not in visited:
                visited.add(curr.id)
                ancestors |= curr
                curr = curr.group_parent_id
        return ancestors

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Ensure standalone Root COA (`parent_id = False`) for all corporate entities
            if vals.get('parent_id') and not vals.get('group_parent_id'):
                vals['group_parent_id'] = vals['parent_id']
            vals['parent_id'] = False
        companies = super().create(vals_list)
        companies._sync_mother_company_users_access()
        return companies

    def write(self, vals):
        if vals.get('parent_id') and not vals.get('group_parent_id'):
            vals = dict(vals, group_parent_id=vals['parent_id'], parent_id=False)
        res = super().write(vals)
        if any(k in vals for k in ('group_parent_id', 'company_type')):
            self._sync_mother_company_users_access()
        return res

    def _sync_mother_company_users_access(self):
        """Whenever group hierarchy changes, auto-grant new sub-companies to Mother Company users
        (while strictly respecting each user's `excluded_company_ids`)."""
        if self.env.context.get('skip_dsl_group_sync'):
            return
        ancestors_and_self = self | self._get_all_group_ancestors()
        holding_ids = ancestors_and_self.filtered(lambda c: c.company_type == 'holding').ids
        if not holding_ids:
            return
        users = self.env['res.users'].sudo().with_context(active_test=False).search([
            ('share', '=', False),
            ('auto_group_company_access', '=', True),
            '|',
            ('company_id', 'in', holding_ids),
            ('company_ids', 'in', holding_ids),
        ])
        if users:
            users._sync_group_company_access()

    @api.depends('trade_license_expiry')
    def _compute_trade_license_status(self):
        today = fields.Date.context_today(self)
        soon = today + timedelta(days=30)
        for company in self:
            if not company.trade_license_expiry:
                company.trade_license_status = 'not_set'
            elif company.trade_license_expiry < today:
                company.trade_license_status = 'expired'
            elif company.trade_license_expiry <= soon:
                company.trade_license_status = 'expiring_soon'
            else:
                company.trade_license_status = 'valid'

    def _compute_hrms_counts(self):
        Employee = self.env['hr.employee'].sudo()
        Department = self.env['hr.department'].sudo()
        Users = self.env['res.users'].sudo()
        has_branch = 'dsl.branch' in self.env
        Branch = self.env['dsl.branch'].sudo() if has_branch else None

        for company in self:
            company.employee_count = Employee.search_count([('company_id', '=', company.id)])
            company.subsidiary_count = len(company.sudo().group_child_ids)
            company.department_count = Department.search_count([('company_id', '=', company.id)])
            company.user_access_count = Users.search_count([
                ('share', '=', False),
                ('company_ids', 'in', [company.id]),
            ])
            company.has_branch_module = has_branch
            company.dsl_company_branch_count = (
                Branch.search_count([('company_id', '=', company.id)]) if has_branch else 0
            )

    # Smart Button Actions
    def action_view_company_employees(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Employees',
            'res_model': 'hr.employee',
            'view_mode': 'kanban,list,form',
            'domain': [('company_id', '=', self.id)],
            'context': {'default_company_id': self.id},
        }

    def action_view_subsidiaries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Sub-Companies, Sister Concerns & JVs',
            'res_model': 'res.company',
            'view_mode': 'kanban,list,form',
            'domain': [('group_parent_id', '=', self.id)],
            'context': {
                'default_group_parent_id': self.id,
                'default_company_type': 'subsidiary',
            },
        }

    def action_view_company_users(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Authorized Users & Access',
            'res_model': 'res.users',
            'view_mode': 'list,form',
            'domain': [('share', '=', False), ('company_ids', 'in', [self.id])],
            'context': {
                'default_company_id': self.id,
                'default_company_ids': [self.id],
                'search_default_no_share': 1,
            },
        }

    def action_view_company_departments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Departments',
            'res_model': 'hr.department',
            'view_mode': 'kanban,list,form',
            'domain': [('company_id', '=', self.id)],
            'context': {'default_company_id': self.id},
        }

    def action_view_company_branches(self):
        self.ensure_one()
        if 'dsl.branch' not in self.env:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Branches & Locations',
            'res_model': 'dsl.branch',
            'view_mode': 'kanban,list,form',
            'domain': [('company_id', '=', self.id)],
            'context': {'default_company_id': self.id},
        }

    @api.model
    def get_company_hierarchy_data(self):
        """Return structured group tree data strictly scoped to the current user's
        allowed companies AND allowed branches (`_get_effective_branch_ids`)."""
        user = self.env.user.sudo()
        allowed_ids = user.company_ids.ids
        # Show main corporate entities in tree (branch_coa ledger books are surfaced via their Branch pills)
        companies = self.sudo().search([
            ('id', 'in', allowed_ids),
            ('company_type', '!=', 'branch_coa'),
        ], order='sequence, id')

        has_branch = 'dsl.branch' in self.env
        Branch = self.env['dsl.branch'].sudo() if has_branch else None
        allowed_branch_ids = user._get_effective_branch_ids() if hasattr(user, '_get_effective_branch_ids') else []
        strict_branch = user._has_strict_branch_lock() if hasattr(user, '_has_strict_branch_lock') else False

        Employee = self.env['hr.employee'].sudo()
        Department = self.env['hr.department'].sudo()
        Users = self.env['res.users'].sudo()

        can_manage_companies = (
            self.env.user.has_group('base.group_erp_manager')
            or self.env.user.has_group('DSL_HRMS_core.group_dsl_hrms_manager')
        )

        type_labels = dict(self._fields['company_type'].selection)
        nodes_by_id = {}

        for comp in companies:
            country_code = (comp.country_id.code or 'BD').lower()
            flag_url = (
                getattr(comp.country_id, 'image_url', False)
                or f'/base/static/img/country_flags/{country_code}.png'
            )
            emp_dom = [('company_id', '=', comp.id)]
            dept_dom = [('company_id', '=', comp.id)]
            if strict_branch:
                emp_dom.append(('branch_id', 'in', allowed_branch_ids))
                dept_dom.append(('branch_id', 'in', allowed_branch_ids))

            emp_count = Employee.search_count(emp_dom)
            dept_count = Department.search_count(dept_dom)

            comp_branches_data = []
            if has_branch:
                b_dom = [('company_id', '=', comp.id)]
                if strict_branch:
                    b_dom.append(('id', 'in', allowed_branch_ids))
                comp_branches = Branch.search(b_dom, order='sequence, id')
                for b in comp_branches:
                    coa_mode = getattr(b, 'coa_mode', 'shared') or 'shared'
                    comp_branches_data.append({
                        'id': b.id,
                        'code': b.code,
                        'name': b.name,
                        'coa_mode': coa_mode,
                        'coa_label': 'Separate COA' if coa_mode == 'separate' else 'Shared COA',
                    })
            branch_count = len(comp_branches_data)
            user_count = Users.search_count([('share', '=', False), ('company_ids', 'in', [comp.id])])

            g_parent = comp.group_parent_id
            c_type = comp.company_type or ('holding' if not g_parent else 'subsidiary')
            nodes_by_id[comp.id] = {
                'id': comp.id,
                'name': comp.name,
                'short_code': comp.short_code or f'COMP-{comp.id:02d}',
                'parent_id': g_parent.id or False,
                'parent_name': g_parent.name or '',
                'company_type': c_type,
                'company_type_label': type_labels.get(c_type, 'Company'),
                'is_mother': c_type == 'holding' or not bool(g_parent),
                'independent_coa': not bool(comp.parent_id),
                'country_name': comp.country_id.name or 'Bangladesh',
                'country_code': (comp.country_id.code or 'BD').upper(),
                'flag_url': flag_url,
                'currency_name': comp.currency_id.name or 'BDT',
                'city': comp.city or 'Dhaka',
                'tin_number': comp.tin_number or '',
                'bin_number': comp.bin_number or '',
                'trade_license_no': comp.trade_license_no or '',
                'trade_license_expiry': str(comp.trade_license_expiry) if comp.trade_license_expiry else '',
                'trade_license_status': comp.trade_license_status,
                'employee_count': emp_count,
                'department_count': dept_count,
                'branch_count': branch_count,
                'branches': comp_branches_data,
                'user_count': user_count,
                'has_branch_module': has_branch,
                'email': comp.email or '',
                'phone': comp.phone or '',
                'children': [],
            }

        roots = []
        for comp_id, node in nodes_by_id.items():
            pid = node['parent_id']
            if pid and pid in nodes_by_id:
                nodes_by_id[pid]['children'].append(node)
            else:
                roots.append(node)

        all_nodes = list(nodes_by_id.values())
        return {
            'roots': roots,
            'flat_list': all_nodes,
            'has_branch_module': has_branch,
            'can_manage_companies': can_manage_companies,
            'summary': {
                'total_entities': len(all_nodes),
                'mother_count': sum(1 for n in all_nodes if n['is_mother']),
                'subsidiary_count': sum(1 for n in all_nodes if not n['is_mother']),
                'total_employees': sum(n['employee_count'] for n in all_nodes),
                'total_branches': sum(n['branch_count'] for n in all_nodes),
                'expiring_licenses': sum(
                    1 for n in all_nodes if n['trade_license_status'] in ('expired', 'expiring_soon')
                ),
            },
        }
