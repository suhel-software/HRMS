# -*- coding: utf-8 -*-
from odoo import models


class IrHttpDslMultiCompany(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        res = super().session_info()
        if not res.get('is_internal_user') or 'user_companies' not in res:
            return res

        user = self.env.user.sudo()
        Company = self.env['res.company'].sudo()
        if 'group_parent_id' not in Company._fields:
            return res

        allowed_comps = user.company_ids
        # Find any corporate group ancestors not in `allowed_companies` (e.g. if a sub-company user views switcher)
        disallowed_ancestors = Company
        for comp in allowed_comps:
            curr = comp.group_parent_id
            visited = {comp.id}
            while curr and curr.id not in visited:
                visited.add(curr.id)
                if curr not in allowed_comps:
                    disallowed_ancestors |= curr
                curr = curr.group_parent_id

        all_hierarchy = allowed_comps | disallowed_ancestors

        allowed_dict = res['user_companies'].get('allowed_companies', {})
        for comp in allowed_comps:
            if comp.id in allowed_dict:
                group_children = (comp.group_child_ids & all_hierarchy).sorted(key=lambda c: (c.sequence, c.id))
                allowed_dict[comp.id]['child_ids'] = group_children.ids
                allowed_dict[comp.id]['parent_id'] = comp.group_parent_id.id or False

        disallowed_dict = res['user_companies'].get('disallowed_ancestor_companies', {})
        for comp in disallowed_ancestors:
            group_children = (comp.group_child_ids & all_hierarchy).sorted(key=lambda c: (c.sequence, c.id))
            disallowed_dict[comp.id] = {
                'id': comp.id,
                'name': comp.name,
                'sequence': comp.sequence,
                'child_ids': group_children.ids,
                'parent_id': comp.group_parent_id.id or False,
            }

        res['user_companies']['disallowed_ancestor_companies'] = disallowed_dict
        res['display_switch_company_menu'] = len(allowed_comps) > 1
        res['is_dsl_mother_user'] = bool(
            getattr(user, 'has_mother_company_access', False)
            and getattr(user, 'auto_group_company_access', True)
            and len(allowed_comps) > 1
        )
        return res

