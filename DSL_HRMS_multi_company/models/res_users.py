# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResUsersGroupAccess(models.Model):
    _inherit = 'res.users'

    auto_group_company_access = fields.Boolean(
        string='Auto-Access All Sub-Companies',
        default=True,
        help='If enabled, when this user has access to a Mother / Holding Company, '
             'they automatically receive access to all its Subsidiary, Sister Concern, '
             'and Associate / Joint Venture companies (except Excluded Sub-Companies).',
    )
    excluded_company_ids = fields.Many2many(
        'res.company',
        'dsl_user_excluded_company_rel',
        'user_id',
        'company_id',
        string='Excluded Sub-Companies (Restricted)',
        help='Specific sub-companies revoked from this Mother Company user.',
    )
    has_mother_company_access = fields.Boolean(
        string='Has Mother Company Access',
        compute='_compute_has_mother_company_access',
    )

    @api.depends('company_id', 'company_ids', 'company_id.company_type', 'company_ids.company_type')
    def _compute_has_mother_company_access(self):
        for user in self:
            all_c = (user.company_id._origin | user.company_ids._origin).sudo()
            user.has_mother_company_access = any(c.company_type == 'holding' for c in all_c)

    @api.onchange('company_id')
    def _onchange_company_id_group_access(self):
        if not self.company_id:
            return
        comp = self.company_id._origin.sudo()
        if comp.company_type == 'holding':
            if self.auto_group_company_access:
                descendants = comp._get_all_group_descendants()
                excl = self.excluded_company_ids._origin.sudo()
                excl_all = excl | excl._get_all_group_descendants()
                allowed = (comp | descendants) - excl_all
                self.company_ids = allowed | comp
            else:
                self.company_ids = comp
        else:
            # Subsidiary, Sister Concern, or Associate / JV: strictly isolate to this single company by default
            self.excluded_company_ids = False
            self.company_ids = comp

    @api.onchange('company_ids')
    def _onchange_company_ids_sync_exclusions(self):
        """When an Admin clicks `×` on a company tag in `Allowed Companies` for a Mother Company user,
        immediately sync `excluded_company_ids` so live branch preview & save stay consistent."""
        if not self.company_id or not self.auto_group_company_access:
            return
        comp_main = self.company_id._origin.sudo()
        current_cids = self.company_ids._origin.sudo()
        holding_comps = (comp_main | current_cids).filtered(lambda c: c.company_type == 'holding')
        if not holding_comps:
            return
        descendants = holding_comps._get_all_group_descendants()
        curr_excl = self.excluded_company_ids._origin.sudo()
        expected_active = (holding_comps | descendants) - (curr_excl | curr_excl._get_all_group_descendants())
        removed_now = (expected_active - current_cids) - comp_main
        readded_now = current_cids & curr_excl
        if removed_now or readded_now:
            new_excl = ((curr_excl | removed_now) - readded_now) - comp_main
            self.excluded_company_ids = new_excl

    @api.onchange('auto_group_company_access', 'excluded_company_ids', 'dsl_excluded_branch_ids')
    def _onchange_group_exclusions(self):
        if not self.company_id:
            return
        comp_main = self.company_id._origin.sudo()
        all_c = (comp_main | self.company_ids._origin).sudo()
        holding_comps = all_c.filtered(lambda c: c.company_type == 'holding')
        if holding_comps and self.auto_group_company_access:
            descendants = holding_comps._get_all_group_descendants()
            excl = self.excluded_company_ids._origin.sudo() - comp_main
            excl_all = excl | excl._get_all_group_descendants()
            # Also exclude Separate Branch COA companies for any branch in `dsl_excluded_branch_ids`
            excl_branch_coas = self.env['res.company'].sudo()
            for b in self.dsl_excluded_branch_ids._origin.sudo():
                acc_c = getattr(b, 'accounting_company_id', False)
                if acc_c and getattr(b, 'coa_mode', 'shared') == 'separate' and acc_c != comp_main:
                    excl_branch_coas |= acc_c
            non_group_manual = all_c - holding_comps - descendants
            self.company_ids = (holding_comps | non_group_manual | (descendants - excl_all - excl_branch_coas)) | comp_main

    @api.model_create_multi
    def create(self, vals_list):
        Company = self.env['res.company'].sudo()
        for vals in vals_list:
            comp_id = vals.get('company_id') or self.env.company.id
            comp = Company.browse(comp_id)
            is_holding = comp.company_type == 'holding'
            if not is_holding:
                # If creating a user for a Subsidiary / Sister / JV without explicit multi-company override,
                # isolate strictly to `comp_id` instead of inheriting Admin's active Mother Company!
                if 'company_ids' not in vals:
                    vals['company_ids'] = [(6, 0, [comp_id])]
                else:
                    vals['company_ids'] = list(vals['company_ids']) + [(4, comp_id)]
            else:
                if 'company_ids' not in vals:
                    vals['company_ids'] = [(6, 0, [comp_id])]
                else:
                    vals['company_ids'] = list(vals['company_ids']) + [(4, comp_id)]

        users = super().create(vals_list)
        users._sync_group_company_access()
        return users

    def write(self, vals):
        if self.env.context.get('skip_dsl_user_sync'):
            return super().write(vals)

        # When a user edits their OWN `res.users` record to remove a company or exclude a branch,
        # Odoo's `base/models/res_users.py` evaluates `ir.rule` (`self.env.companies`) mid-`write`
        # right after removing the company from `user.company_ids`, which would fail if the old
        # `allowed_company_ids` context still contained the just-removed company!
        if (
            not self.env.su
            and 'allowed_company_ids' in self.env.context
            and (
                self.env.uid in self.ids
                or set(self.env.context['allowed_company_ids']) - set(self.env.user.sudo().company_ids.ids)
            )
        ):
            safe_cid = (
                (vals.get('company_id') if self.env.uid in self.ids else False)
                or self.env.user.sudo().company_id.id
            )
            if safe_cid:
                self = self.with_context(allowed_company_ids=[safe_cid])

        # Prevent Odoo `_check_company` ValidationError when changing `company_id` before `company_ids` syncs
        if 'company_id' in vals and vals['company_id'] and 'company_ids' not in vals:
            new_cid = vals['company_id']
            Company = self.env['res.company'].sudo()
            new_comp = Company.browse(new_cid)
            is_new_holding = new_comp.company_type == 'holding'
            for user in self:
                if not is_new_holding:
                    # Switching user to a Subsidiary / Sister / JV -> isolate to that company
                    super(ResUsersGroupAccess, user).write({
                        'company_ids': [(6, 0, [new_cid])],
                        'company_id': new_cid,
                        'excluded_company_ids': [(5, 0, 0)],
                    })
                else:
                    merged_ids = list(set(user.company_ids.ids + [new_cid]))
                    super(ResUsersGroupAccess, user).write({
                        'company_ids': [(6, 0, merged_ids)],
                        'company_id': new_cid,
                    })
            remaining_vals = {k: v for k, v in vals.items() if k != 'company_id'}
            res = super().write(remaining_vals) if remaining_vals else True
            self._sync_group_company_access()
            return res

        # Track direct tag removal/addition in `company_ids` when `excluded_company_ids` wasn't edited directly
        direct_company_ids_edit = 'company_ids' in vals and 'excluded_company_ids' not in vals
        before_map = {}
        if direct_company_ids_edit:
            for user in self.sudo():
                before_map[user.id] = set(user.company_ids.ids)

        res = super().write(vals)

        if direct_company_ids_edit:
            for user in self.sudo():
                if not user.auto_group_company_access or user.share:
                    continue
                old_ids = before_map.get(user.id, set())
                new_ids = set(user.company_ids.ids)
                all_c = user.company_id | user.company_ids
                holding_comps = all_c.filtered(lambda c: c.company_type == 'holding')
                if not holding_comps:
                    continue
                descendant_ids = set(holding_comps._get_all_group_descendants().ids)
                removed_descendants = (old_ids - new_ids) & descendant_ids
                readded_descendants = (new_ids & set(user.excluded_company_ids.ids)) & descendant_ids
                if removed_descendants or readded_descendants:
                    updated_excl = (set(user.excluded_company_ids.ids) | removed_descendants) - readded_descendants
                    updated_excl.discard(user.company_id.id)
                    user.with_context(skip_dsl_user_sync=True).write({
                        'excluded_company_ids': [(6, 0, list(updated_excl))]
                    })

        if any(k in vals for k in (
            'company_id', 'company_ids', 'auto_group_company_access',
            'excluded_company_ids', 'dsl_branch_id', 'dsl_branch_ids',
            'dsl_excluded_branch_ids'
        )):
            self._sync_group_company_access()

        return res

    def _sanitize_self_company_context(self):
        """Prevent Odoo `AccessError: Access to unauthorized or invalid companies.` when an Admin
        removes a company or branch COA from their OWN user record while their browser `cids`
        cookie still had that company active in the current RPC context."""
        ctx = dict(self.env.context)
        if 'allowed_company_ids' in ctx and not self.env.su:
            valid_user_cids = self.env.user.sudo().company_ids.ids
            sanitized = [cid for cid in ctx['allowed_company_ids'] if cid in valid_user_cids]
            if not sanitized and self.env.user.sudo().company_id:
                sanitized = [self.env.user.sudo().company_id.id]
            ctx['allowed_company_ids'] = sanitized
        return ctx

    def onchange(self, values, field_names, fields_spec):
        ctx = self._sanitize_self_company_context()
        self_ctx = self.with_context(ctx)
        if self_ctx:
            self_ctx.check_access('write')
        else:
            self_ctx.check_access('create')
        return super(ResUsersGroupAccess, self_ctx.sudo()).onchange(values, field_names, fields_spec)

    def web_save(self, vals, specification, next_id=None):
        if self:
            self.write(vals)
        else:
            self = self.create(vals)
        if next_id:
            self = self.browse(next_id)
        ctx = self._sanitize_self_company_context()
        ctx['bin_size'] = True
        return self.with_context(ctx).web_read(specification)

    def web_read(self, specification):
        ctx = self._sanitize_self_company_context()
        self_ctx = self.with_context(ctx)
        self_ctx.check_access('read')

        # Read `excluded_company_ids` & `dsl_excluded_branch_ids` cleanly so that even if an Admin
        # excluded a company or branch from their OWN user, the excluded tags remain readable & removable!
        special_specs = {}
        clean_spec = {}
        for k, v in (specification or {}).items():
            if k in ('excluded_company_ids', 'dsl_excluded_branch_ids', 'dsl_effective_branch_ids'):
                special_specs[k] = v
            else:
                clean_spec[k] = v

        rows = super(ResUsersGroupAccess, self_ctx).web_read(clean_spec)
        if special_specs and rows:
            rec_map = {r.id: r.sudo() for r in self_ctx}
            for row in rows:
                rec_sudo = rec_map.get(row['id'])
                if not rec_sudo:
                    continue
                for fname, fspec in special_specs.items():
                    target_recs = getattr(rec_sudo, fname)
                    if fspec and isinstance(fspec, dict) and fspec.get('fields'):
                        row[fname] = target_recs.web_read(fspec['fields'])
                    else:
                        row[fname] = target_recs.ids
        return rows

    def _sync_group_company_access(self):
        """Sync `company_ids` for:
        1. Mother Company users: Mother + All Descendants - Excluded Companies - Excluded Separate Branch COAs.
        2. Restricted Sub-Company / Branch users: also include any Separate Branch COA entity (`accounting_company_id`)
           belonging to their assigned `dsl_branch_ids`, while keeping strict isolation from all other companies!"""
        group_multi_company = self.env.ref('base.group_multi_company', raise_if_not_found=False)
        for user in self.sudo().filtered(lambda u: not u.share):
            all_c = user.company_id | user.company_ids
            holding_comps = all_c.filtered(
                lambda c: c.company_type == 'holding' or bool(c.group_child_ids and c.company_type == 'holding')
            )
            if holding_comps and user.auto_group_company_access:
                descendants = holding_comps._get_all_group_descendants()
                excluded_base = user.excluded_company_ids - user.company_id
                excluded_all = excluded_base | excluded_base._get_all_group_descendants()

                # If specific branches are excluded in `dsl_excluded_branch_ids` and own a Separate Branch COA,
                # automatically exclude those Separate Branch COA entities too!
                excl_branch_coas = self.env['res.company'].sudo()
                for b in getattr(user, 'dsl_excluded_branch_ids', self.env['res.company']):
                    acc_comp = getattr(b, 'accounting_company_id', False)
                    if acc_comp and getattr(b, 'coa_mode', 'shared') == 'separate' and acc_comp != user.company_id:
                        excl_branch_coas |= acc_comp

                non_descendant_manual = all_c - holding_comps - descendants - excluded_all - excl_branch_coas
                target_companies = (
                    holding_comps
                    | non_descendant_manual
                    | (descendants - excluded_all - excl_branch_coas)
                    | user.company_id
                )
                if set(target_companies.ids) != set(user.company_ids.ids):
                    user.with_context(skip_dsl_user_sync=True).write({
                        'company_ids': [(6, 0, target_companies.ids)]
                    })
                if user.company_id in user.excluded_company_ids:
                    user.with_context(skip_dsl_user_sync=True).write({
                        'excluded_company_ids': [(3, user.company_id.id)]
                    })
            else:
                # Non-Mother user: if any assigned branch has a Dedicated Separate COA entity (`accounting_company_id`),
                # grant access to that branch's COA books entity automatically without granting any other company!
                assigned_branches = getattr(user, 'dsl_branch_ids', self.env['res.company']) | getattr(user, 'dsl_branch_id', self.env['res.company'])
                branch_coa_comps = self.env['res.company'].sudo()
                for b in assigned_branches:
                    acc_comp = getattr(b, 'accounting_company_id', False)
                    if acc_comp and getattr(b, 'coa_mode', 'shared') == 'separate':
                        branch_coa_comps |= acc_comp
                # Also strip any stale branch_coa companies that are no longer in assigned_branches
                stale_branch_coas = user.company_ids.filtered(
                    lambda c: c.company_type == 'branch_coa' and c not in branch_coa_comps and c != user.company_id
                )
                target_companies = ((user.company_ids - stale_branch_coas) | user.company_id | branch_coa_comps)
                if set(target_companies.ids) != set(user.company_ids.ids):
                    user.with_context(skip_dsl_user_sync=True).write({
                        'company_ids': [(6, 0, target_companies.ids)]
                    })

            # Automatically grant `base.group_multi_company` to ANY internal employee/user who has >1 allowed company
            # (so regular Mother Company employees also get full multi-company visibility & switching without needing Admin!)
            if group_multi_company and len(user.company_ids) > 1 and group_multi_company not in user.groups_id:
                user.with_context(skip_dsl_user_sync=True).write({
                    'groups_id': [(4, group_multi_company.id)]
                })
        self.env.registry.clear_cache()

