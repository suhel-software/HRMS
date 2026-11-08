# -*- coding: utf-8 -*-
import odoo
from odoo import api, fields, models


class DslBranchCore(models.Model):
    """Lightweight core Branch model in `DSL_HRMS_core` so all 80–85 HRMS features across
    Phases 2–10 have native `branch_id` & strict branch isolation without cross-module dependencies.
    Extended with full UI, Geofencing & Separate/Shared COA engine in `DSL_HRMS_branch`."""
    _name = 'dsl.branch'
    _description = 'Company Branch / Operational Location'
    _order = 'company_id, sequence, name'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Branch / Location Name', required=True)
    code = fields.Char(string='Branch Code', required=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company / Entity',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'code_company_uniq',
            'unique(code, company_id)',
            'Branch Code must be unique within the same Company!',
        )
    ]

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for branch in self:
            branch.display_name = f"[{branch.code}] {branch.name}" if branch.code else (branch.name or '')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.registry.clear_cache()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ('company_id', 'active')):
            self.env.registry.clear_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self.env.registry.clear_cache()
        return res


class DslCompanyBranchMixin(models.AbstractModel):
    """Universal Mixin to be inherited by all operational HRMS models (Attendance, Shift,
    Overtime, Leave, Payroll, PF, Gratuity, Loan, Bonus, Recruitment, Appraisal, Assets, etc.)
    guaranteeing Company + Branch separation out of the box."""
    _name = 'dsl.company.branch.mixin'
    _description = 'DSL Multi-Company & Multi-Branch Isolation Mixin'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Branch / Duty Station',
        domain="[('company_id', '=', company_id)]",
        default=lambda self: self.env.user.dsl_branch_id,
        index=True,
    )

    @api.onchange('company_id')
    def _onchange_dsl_mixin_company_id(self):
        if self.branch_id and self.company_id and self.branch_id.company_id != self.company_id:
            self.branch_id = False


class HrDepartmentCoreBranch(models.Model):
    _inherit = 'hr.department'

    branch_id = fields.Many2one(
        'dsl.branch',
        string='Branch / Location',
        domain="[('company_id', '=', company_id)]",
        index=True,
    )


class HrJobCoreBranch(models.Model):
    _inherit = 'hr.job'

    branch_id = fields.Many2one(
        'dsl.branch',
        string='Branch / Location',
        domain="[('company_id', '=', company_id)]",
        index=True,
    )


class HrEmployeeCoreBranch(models.Model):
    _inherit = 'hr.employee'

    branch_id = fields.Many2one(
        'dsl.branch',
        string='Branch / Duty Station',
        domain="[('company_id', '=', company_id)]",
        default=lambda self: self.env.user.dsl_branch_id,
        index=True,
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees._sync_linked_user_company_branch()
        return employees

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ('user_id', 'company_id', 'branch_id')):
            self._sync_linked_user_company_branch()
        return res

    def _sync_linked_user_company_branch(self):
        """Ensure that when an Employee (Mother Company or Sub-Company) has a linked User account:
        - Mother Company employee's user automatically gets Mother Company + all Group Sub-Companies & All Branches.
        - Sub-Company employee's user gets their assigned Company & Duty Branch without leaking other companies."""
        admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
        skip_ids = {odoo.SUPERUSER_ID}
        if admin_user:
            skip_ids.add(admin_user.id)

        for emp in self.sudo().filtered(lambda e: e.user_id and not e.user_id.share):
            user = emp.user_id
            if user.id in skip_ids:
                # For Administrator, only backfill optional home branch if empty without altering admin company setup
                if emp.branch_id and not user.dsl_branch_id:
                    user.with_context(skip_dsl_user_sync=True).write({'dsl_branch_id': emp.branch_id.id})
                continue

            comp = emp.company_id
            if not comp:
                continue

            is_holding = getattr(comp, 'company_type', 'holding') == 'holding'
            update_vals = {}
            if is_holding:
                if comp not in user.company_ids or user.company_id != comp:
                    merged_cids = list(set(user.company_ids.ids + [comp.id]))
                    update_vals['company_ids'] = [(6, 0, merged_cids)]
                    update_vals['company_id'] = comp.id
                if emp.branch_id and not user.dsl_branch_id:
                    update_vals['dsl_branch_id'] = emp.branch_id.id
            else:
                if user.company_id != comp and not user._is_mother_holding_user():
                    update_vals['company_ids'] = [(6, 0, [comp.id])]
                    update_vals['company_id'] = comp.id
                if emp.branch_id and not user.dsl_branch_id:
                    update_vals['dsl_branch_id'] = emp.branch_id.id
                    if emp.branch_id not in user.dsl_branch_ids:
                        update_vals['dsl_branch_ids'] = [(4, emp.branch_id.id)]

            if update_vals:
                user.write(update_vals)
            elif hasattr(user, '_sync_group_company_access'):
                user._sync_group_company_access()


class HrEmployeePublicCoreBranch(models.Model):
    _inherit = 'hr.employee.public'

    branch_id = fields.Many2one('dsl.branch', string='Branch / Duty Station', readonly=True)


class ResUsersBranchCore(models.Model):
    _inherit = 'res.users'

    dsl_branch_access_mode = fields.Selection(
        selection=[
            ('selected', 'Restricted to Assigned Branch(es) Only'),
            ('all_company', 'All Branches of Allowed Company'),
        ],
        string='Branch Access Scope',
        default='selected',
        required=True,
        help="Strict Branch Isolation: 'Restricted' locks this user strictly to their 1 (or 2–3 shared) assigned branches.",
    )
    dsl_branch_id = fields.Many2one(
        'dsl.branch',
        string='Primary Branch',
        domain="[('company_id', 'in', company_ids)]",
    )
    dsl_branch_ids = fields.Many2many(
        'dsl.branch',
        'dsl_user_allowed_branch_rel',
        'user_id',
        'branch_id',
        string='Allowed Branches (1 or 2–3 Shared)',
        domain="[('company_id', 'in', company_ids)]",
        help='Assign 1 branch for single-branch lock, or 2–3 branches to share one user account across those branches.',
    )
    dsl_excluded_branch_ids = fields.Many2many(
        'dsl.branch',
        'dsl_user_excluded_branch_rel',
        'user_id',
        'branch_id',
        string='Excluded Branches (Restricted)',
        help='Optional for Mother / Holding Company users: revoke access to specific branches.',
    )
    dsl_effective_branch_ids = fields.Many2many(
        'dsl.branch',
        string='Effective Accessible Branches',
        compute='_compute_dsl_effective_branch_ids',
    )
    dsl_effective_branch_count = fields.Integer(
        string='Accessible Branch Count',
        compute='_compute_dsl_effective_branch_ids',
    )

    @api.depends(
        'company_id', 'company_ids', 'dsl_branch_access_mode',
        'dsl_branch_id', 'dsl_branch_ids', 'dsl_excluded_branch_ids'
    )
    def _compute_dsl_effective_branch_ids(self):
        Branch = self.env['dsl.branch'].sudo()
        for user in self:
            eff_ids = user._get_effective_branch_ids()
            user.dsl_effective_branch_ids = Branch.browse(eff_ids)
            user.dsl_effective_branch_count = len(eff_ids)

    def _is_mother_holding_user(self):
        self.ensure_one()
        real_id = self._origin.id or (self.id if isinstance(self.id, int) else False)
        if real_id == odoo.SUPERUSER_ID:
            return True
        Company = self.env['res.company'].sudo()
        # If Multi-Company module is uninstalled (Single-Company mode), treat root company user as full access
        if 'company_type' not in Company._fields:
            return True
        all_c = (self.company_id._origin | self.company_ids._origin).sudo()
        for c in all_c:
            if c.company_type == 'holding':
                return True
        return False

    def _has_strict_branch_lock(self):
        self.ensure_one()
        real_id = self._origin.id or (self.id if isinstance(self.id, int) else False)
        if real_id == odoo.SUPERUSER_ID:
            return False
        Branch = self.env['dsl.branch'].sudo()
        comp_ids = self.company_ids._origin.sudo().ids
        excl_branches = self.dsl_excluded_branch_ids._origin.sudo()
        # If Branch module (`DSL_HRMS_branch`) is uninstalled OR user's allowed companies have ZERO branches configured,
        # never apply strict branch lock — single-company / zero-branch mode works seamlessly!
        if 'coa_mode' not in Branch._fields:
            return False
        if not comp_ids or Branch.search_count([('company_id', 'in', comp_ids)]) == 0:
            return False
        if self._is_mother_holding_user():
            # Mother HQ user sees everything across all companies & branches unless specific branches are excluded
            return bool(excl_branches)
        # Subsidiary, Sister Concern, Associate / JV user:
        if self.dsl_branch_access_mode == 'all_company' and not excl_branches:
            return False
        return True

    def _get_effective_branch_ids(self):
        self.ensure_one()
        Branch = self.env['dsl.branch'].sudo()
        real_id = self._origin.id or (self.id if isinstance(self.id, int) else False)
        if real_id == odoo.SUPERUSER_ID:
            return Branch.search([]).ids

        allowed_comp_ids = (self.company_ids._origin | self.company_id._origin).sudo().ids
        excl_branches = self.dsl_excluded_branch_ids._origin.sudo()
        if not allowed_comp_ids:
            return []

        if self._is_mother_holding_user() or self.dsl_branch_access_mode == 'all_company':
            all_b = Branch.search([('company_id', 'in', allowed_comp_ids)])
            return (all_b - excl_branches).ids

        # Strict Selected Branch(es) Mode (1 branch OR 2–3 shared branches)
        assigned = (self.dsl_branch_ids._origin | self.dsl_branch_id._origin).sudo().filtered(
            lambda b: b.company_id.id in allowed_comp_ids
        )
        return (assigned - excl_branches).ids

    @api.onchange('dsl_branch_id')
    def _onchange_dsl_branch_id_include(self):
        if self.dsl_branch_id and self.dsl_branch_id not in self.dsl_branch_ids:
            self.dsl_branch_ids |= self.dsl_branch_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('dsl_branch_id') and 'dsl_branch_ids' not in vals:
                vals['dsl_branch_ids'] = [(4, vals['dsl_branch_id'])]
        users = super().create(vals_list)
        self.env.registry.clear_cache()
        return users

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in (
            'company_id', 'company_ids', 'dsl_branch_id', 'dsl_branch_ids',
            'dsl_excluded_branch_ids', 'dsl_branch_access_mode'
        )):
            for u in self.sudo():
                if u.dsl_branch_id and u.dsl_branch_id not in u.dsl_branch_ids:
                    super(ResUsersBranchCore, u).write({'dsl_branch_ids': [(4, u.dsl_branch_id.id)]})
            self.env.registry.clear_cache()
        return res


class IrRuleDslBranch(models.Model):
    _inherit = 'ir.rule'

    def _eval_context(self):
        ctx = super()._eval_context()
        user = self.env.user.sudo()
        is_admin_user_config = bool(
            self.env.context.get('dsl_user_access_config')
            and (
                self.env.user.has_group('base.group_erp_manager')
                or self.env.user.has_group('DSL_HRMS_core.group_dsl_hrms_manager')
            )
        )
        ctx['dsl_branch_ids'] = user._get_effective_branch_ids()
        ctx['dsl_strict_branch'] = False if is_admin_user_config else user._has_strict_branch_lock()
        ctx['dsl_is_mother_user'] = user._is_mother_holding_user()
        return ctx

    def _compute_domain_keys(self):
        return super()._compute_domain_keys() + ['allowed_branch_ids', 'dsl_user_access_config']
