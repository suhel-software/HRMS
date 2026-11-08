# -*- coding: utf-8 -*-
from odoo import api, fields, models


class DslHrmsNavHelper(models.AbstractModel):
    _name = 'dsl.hrms.nav.helper'
    _description = 'DSL HRMS Plug-and-Play Navigation Helper'

    @api.model
    def get_installed_dsl_modules(self):
        """Return map of installed DSL_HRMS_* modules AND current user's Role Template navigation access."""
        mods = self.env['ir.module.module'].sudo().search_read(
            [('name', 'like', 'DSL_HRMS_%'), ('state', '=', 'installed')],
            ['name'],
        )
        res = {m['name']: True for m in mods}
        res['__nav_profile__'] = self.get_user_navigation_profile()
        return res

    @api.model
    def get_user_navigation_profile(self):
        """Compute exact sidebar menu visibility, role badge, and dashboard routing for the logged-in user
        based on their assigned `dsl_role_template_ids` (supports single or multiple templates per user)."""
        user = self.env.user.sudo()
        if 'dsl.access.role.template' in self.env:
            self.env['dsl.access.role.template'].sudo()._ensure_default_role_templates()
        if 'dsl.hrms.main.menu' in self.env:
            self.env['dsl.hrms.main.menu'].sudo()._ensure_default_main_menus()

        tpls = getattr(user, 'dsl_role_template_ids', self.env['dsl.access.role.template'].sudo()).sorted('sequence')
        is_super = user._is_unrestricted_super_admin() if hasattr(user, '_is_unrestricted_super_admin') else (user.id == 1 or user.has_group('base.group_system'))

        # If user has no explicit role template yet, infer sensible defaults
        if not tpls:
            if is_super:
                super_tpl = self.env['dsl.access.role.template'].sudo().search([('code', '=', 'super_admin')], limit=1)
                if super_tpl:
                    user.with_context(skip_dsl_role_sync=True, skip_dsl_user_sync=True).write({
                        'dsl_role_template_ids': [(4, super_tpl.id)]
                    })
                    tpls = super_tpl
            else:
                emp_tpl = self.env['dsl.access.role.template'].sudo().search([('code', '=', 'employee')], limit=1)
                if emp_tpl:
                    user.with_context(skip_dsl_role_sync=True, skip_dsl_user_sync=True).write({
                        'dsl_role_template_ids': [(4, emp_tpl.id)]
                    })
                    tpls = emp_tpl

        codes = set(tpls.mapped('code'))
        # Determine primary landing dashboard (respect per-user override if set)
        if getattr(user, 'dsl_primary_dashboard', False):
            primary_dashboard = user.dsl_primary_dashboard
        elif codes & {'super_admin', 'company_admin', 'hr_manager', 'hr_officer', 'operations'} or is_super:
            primary_dashboard = 'hr'
        elif 'accounts' in codes:
            primary_dashboard = 'accounts'
        elif 'manager' in codes:
            primary_dashboard = 'mss'
        else:
            primary_dashboard = 'ess'

        # Read per-user effective access flags (auto-filled by Role Templates, customizable per user)
        allow_org = is_super or bool(getattr(user, 'user_allow_organization', False))
        allow_rec = is_super or bool(getattr(user, 'user_allow_recruitment', False))
        allow_emp = is_super or bool(getattr(user, 'user_allow_employee_mgmt', False))
        allow_att = is_super or bool(getattr(user, 'user_allow_attendance', False))
        allow_lv = is_super or bool(getattr(user, 'user_allow_leaves', False))
        allow_perf = is_super or bool(getattr(user, 'user_allow_performance', False))
        allow_pay = is_super or bool(getattr(user, 'user_allow_payroll', False))
        allow_acc = is_super or bool(getattr(user, 'user_allow_accounting', False))
        allow_frep = is_super or bool(getattr(user, 'user_allow_financial_reports', False))
        allow_ess = is_super or bool(getattr(user, 'user_allow_self_service', True))
        allow_ops = is_super or bool(getattr(user, 'user_allow_operations', False))
        allow_set = is_super or bool(getattr(user, 'dsl_can_manage_settings', False))
        allow_usr = is_super or bool(getattr(user, 'dsl_can_manage_company_users', False))
        allow_sys_mods = is_super or bool(getattr(user, 'user_allow_system_modules', False))

        # Apply Force-Hidden Main Menus (`dsl_hidden_menu_ids`) — hides menu even if user has access!
        hidden_menus = getattr(user, 'dsl_hidden_menu_ids', self.env['dsl.hrms.main.menu'].sudo())
        hidden_codes = set(hidden_menus.mapped('code'))
        allow_dashboard = 'dashboard' not in hidden_codes
        allow_mss_portal = 'mss_portal' not in hidden_codes
        allow_hr_announcements = 'hr_announcements' not in hidden_codes
        if 'organization' in hidden_codes:
            allow_org = False
        if 'recruitment' in hidden_codes:
            allow_rec = False
        if 'employee_mgmt' in hidden_codes:
            allow_emp = False
        if 'attendance' in hidden_codes:
            allow_att = False
        if 'leaves' in hidden_codes:
            allow_lv = False
        if 'performance' in hidden_codes:
            allow_perf = False
        if 'payroll' in hidden_codes:
            allow_pay = False
        if 'accounting' in hidden_codes:
            allow_acc = False
        if 'financial_reports' in hidden_codes:
            allow_frep = False
        if 'self_service' in hidden_codes:
            allow_ess = False
        if 'operations' in hidden_codes:
            allow_ops = False
        if 'settings' in hidden_codes:
            allow_set = False

        # Available dashboards for the Multi-Role Workspace Switcher
        available_dashboards = []
        if is_super or primary_dashboard == 'hr' or allow_emp or allow_ops or (codes & {'super_admin', 'company_admin', 'hr_manager', 'hr_officer', 'operations'}):
            available_dashboards.append({'key': 'hr', 'label': 'HR & Executive Dashboard', 'icon': 'fa-th-large'})
        if is_super or primary_dashboard == 'accounts' or allow_acc or allow_frep or (codes & {'super_admin', 'company_admin', 'accounts', 'hr_manager'}):
            available_dashboards.append({'key': 'accounts', 'label': 'Accounts & Finance', 'icon': 'fa-balance-scale'})
        if allow_mss_portal and (is_super or primary_dashboard == 'mss' or (codes & {'super_admin', 'company_admin', 'hr_manager', 'hr_officer', 'manager'})):
            available_dashboards.append({'key': 'mss', 'label': 'Manager Hub (MSS)', 'icon': 'fa-users'})
        # Every internal user also has access to their personal ESS portal
        if allow_ess:
            available_dashboards.append({'key': 'ess', 'label': 'My Portal (ESS)', 'icon': 'fa-user-circle-o'})

        allow_hr_settings = allow_set and (is_super or allow_emp or allow_att or allow_lv or bool(codes & {'super_admin', 'company_admin', 'hr_manager'}))
        allow_payroll_settings = allow_set and (is_super or allow_pay or allow_acc or bool(codes & {'super_admin', 'company_admin', 'hr_manager', 'accounts'}))
        allow_accounting_settings = allow_set and (is_super or allow_acc or allow_frep or bool(codes & {'super_admin', 'company_admin', 'accounts'}))

        role_badge_label = ' · '.join(tpls.mapped('name')) if tpls else ('Super Administrator' if is_super else 'Employee (ESS)')
        short_role_label = tpls[0].name if len(tpls) == 1 else (f"{tpls[0].name.split(' (')[0]} +{len(tpls) - 1} Role(s)" if len(tpls) > 1 else 'Employee')

        return {
            'user_id': user.id,
            'user_name': user.name,
            'is_super_admin': is_super,
            'role_codes': list(codes),
            'role_names': tpls.mapped('name'),
            'role_badge_label': role_badge_label,
            'short_role_label': short_role_label,
            'primary_dashboard': primary_dashboard,
            'available_dashboards': available_dashboards,
            'allowed_company_ids': user.company_ids.ids,
            'allowed_company_names': user.company_ids.mapped('name'),
            'hidden_menu_codes': list(hidden_codes),
            'allow_dashboard': allow_dashboard,
            'allow_mss_portal': allow_mss_portal,
            'allow_hr_announcements': allow_hr_announcements,
            'allow_organization': allow_org,
            'allow_recruitment': allow_rec,
            'allow_employee_mgmt': allow_emp,
            'allow_attendance': allow_att,
            'allow_leaves': allow_lv,
            'allow_performance': allow_perf,
            'allow_payroll': allow_pay,
            'allow_accounting': allow_acc,
            'allow_financial_reports': allow_frep,
            'allow_self_service': allow_ess,
            'allow_operations': allow_ops,
            'allow_settings': allow_set,
            'allow_user_management': allow_usr,
            'allow_system_modules': allow_sys_mods,
            'allow_hr_settings': allow_hr_settings,
            'allow_payroll_settings': allow_payroll_settings,
            'allow_accounting_settings': allow_accounting_settings,
        }


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    @api.model
    def default_get(self, fields_list):
        user = self.env.user.sudo()
        if not self.env.su and getattr(user, 'dsl_can_manage_settings', False):
            res = super(ResConfigSettings, self.sudo()).default_get(fields_list)
            allowed_cids = user.company_ids.ids
            if 'company_id' in res and allowed_cids and res['company_id'] not in allowed_cids:
                res['company_id'] = user.company_id.id if user.company_id.id in allowed_cids else allowed_cids[0]
            return res
        return super().default_get(fields_list)

    @api.model_create_multi
    def create(self, vals_list):
        user = self.env.user.sudo()
        if not self.env.su and getattr(user, 'dsl_can_manage_settings', False):
            allowed_cids = set(user.company_ids.ids)
            for vals in vals_list:
                if vals.get('company_id') and allowed_cids and vals['company_id'] not in allowed_cids:
                    vals['company_id'] = user.company_id.id
            return super(ResConfigSettings, self.sudo()).create(vals_list)
        return super().create(vals_list)

    def execute(self):
        user = self.env.user.sudo()
        if not self.env.su and getattr(user, 'dsl_can_manage_settings', False):
            return super(ResConfigSettings, self.sudo()).execute()
        return super().execute()

    dsl_hrms_system_name = fields.Char(
        string='System Name',
        default='DSL Enterprise HRMS',
        config_parameter='dsl_hrms.system_name'
    )
    dsl_hrms_enable_gps = fields.Boolean(
        string='Enable GPS Attendance',
        config_parameter='dsl_hrms.enable_gps'
    )
    dsl_hrms_enable_multi_level_approval = fields.Boolean(
        string='Enable Multi-Level Approval',
        default=True,
        config_parameter='dsl_hrms.enable_multi_level_approval'
    )
    dsl_hrms_default_currency_symbol = fields.Char(
        string='Currency Symbol',
        default='৳',
        config_parameter='dsl_hrms.currency_symbol'
    )
    # Fallback guard in case an orphan product view is cached before cleanup
    product_weight_in_lbs = fields.Selection(
        [('0', 'Kilograms'), ('1', 'Pounds')],
        string='Weight unit of measure',
        default='0',
        config_parameter='product.weight_in_lbs',
    )

    def _register_hook(self):
        res = super()._register_hook()
        try:
            # Deactivate any orphaned ir.ui.view on res.config.settings belonging to uninstalled modules
            self.env.cr.execute("""
                UPDATE ir_ui_view v
                   SET active = FALSE
                  FROM ir_model_data imd
                  JOIN ir_module_module imm ON imm.name = imd.module
                 WHERE imd.model = 'ir.ui.view'
                   AND imd.res_id = v.id
                   AND v.model = 'res.config.settings'
                   AND v.active = TRUE
                   AND imm.state != 'installed'
            """)
        except Exception:
            pass
        return res
