# -*- coding: utf-8 -*-
import odoo
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


ROLE_TEMPLATE_DEFINITIONS = [
    {
        'sequence': 10,
        'code': 'employee',
        'name': 'Employee (Self-Service / ESS)',
        'color': 4,
        'default_dashboard': 'ess',
        'description': 'Standard employee self-service access: My Portal (ESS), attendance punch, leave apply, payslips, tax, loans, PF & HR helpdesk.',
        'allow_organization': False,
        'allow_recruitment': False,
        'allow_employee_mgmt': False,
        'allow_attendance': False,
        'allow_leaves': False,
        'allow_performance': False,
        'allow_payroll': False,
        'allow_accounting': False,
        'allow_financial_reports': False,
        'allow_self_service': True,
        'allow_operations': False,
        'allow_settings': False,
        'allow_user_management': False,
        'allow_system_modules': False,
        'group_xmlids': 'base.group_user,DSL_HRMS_core.group_dsl_hrms_user',
    },
    {
        'sequence': 20,
        'code': 'manager',
        'name': 'Line Manager / Supervisor (MSS)',
        'color': 2,
        'default_dashboard': 'mss',
        'description': 'Team supervisor access: Manager Hub (MSS), team attendance, leave approvals, 360° KPI evaluation & increment recommendations.',
        'allow_organization': False,
        'allow_recruitment': False,
        'allow_employee_mgmt': False,
        'allow_attendance': True,
        'allow_leaves': True,
        'allow_performance': True,
        'allow_payroll': False,
        'allow_accounting': False,
        'allow_financial_reports': False,
        'allow_self_service': True,
        'allow_operations': False,
        'allow_settings': False,
        'allow_user_management': False,
        'allow_system_modules': False,
        'group_xmlids': (
            'base.group_user,DSL_HRMS_core.group_dsl_hrms_user,'
            'DSL_HRMS_core.group_dsl_hrms_officer,hr.group_hr_user,'
            'hr_holidays.group_hr_holidays_user,hr_attendance.group_hr_attendance_officer'
        ),
    },
    {
        'sequence': 30,
        'code': 'hr_officer',
        'name': 'HR Officer / Executive',
        'color': 3,
        'default_dashboard': 'hr',
        'description': 'Operational HR access: Organization, Recruitment & ATS, Employee Dossier, Attendance, Shift Roster, Leave & 360° Appraisals.',
        'allow_organization': True,
        'allow_recruitment': True,
        'allow_employee_mgmt': True,
        'allow_attendance': True,
        'allow_leaves': True,
        'allow_performance': True,
        'allow_payroll': False,
        'allow_accounting': False,
        'allow_financial_reports': False,
        'allow_self_service': True,
        'allow_operations': True,
        'allow_settings': False,
        'allow_user_management': False,
        'allow_system_modules': False,
        'group_xmlids': (
            'base.group_user,DSL_HRMS_core.group_dsl_hrms_user,'
            'DSL_HRMS_core.group_dsl_hrms_officer,hr.group_hr_user,'
            'hr_attendance.group_hr_attendance_officer,hr_holidays.group_hr_holidays_user,'
            'hr_recruitment.group_hr_recruitment_user'
        ),
    },
    {
        'sequence': 40,
        'code': 'hr_manager',
        'name': 'HR & Payroll Manager',
        'color': 10,
        'default_dashboard': 'hr',
        'description': 'Full HR & Payroll Management: All HR modules + Monthly Payroll, Salary Packages, Loans, PF, Gratuity, Bonus & HR/Payroll Policy Settings.',
        'allow_organization': True,
        'allow_recruitment': True,
        'allow_employee_mgmt': True,
        'allow_attendance': True,
        'allow_leaves': True,
        'allow_performance': True,
        'allow_payroll': True,
        'allow_accounting': False,
        'allow_financial_reports': False,
        'allow_self_service': True,
        'allow_operations': True,
        'allow_settings': True,
        'allow_user_management': False,
        'allow_system_modules': False,
        'group_xmlids': (
            'base.group_user,DSL_HRMS_core.group_dsl_hrms_user,'
            'DSL_HRMS_core.group_dsl_hrms_officer,DSL_HRMS_core.group_dsl_hrms_manager,'
            'hr.group_hr_user,hr.group_hr_manager,hr_attendance.group_hr_attendance_officer,'
            'hr_holidays.group_hr_holidays_user,hr_holidays.group_hr_holidays_manager,'
            'hr_recruitment.group_hr_recruitment_user,hr_recruitment.group_hr_recruitment_manager'
        ),
    },
    {
        'sequence': 50,
        'code': 'accounts',
        'name': 'Accounts & Finance',
        'color': 5,
        'default_dashboard': 'accounts',
        'description': 'Finance & Payroll Accounting: Payroll Batches, Vouchers, Tax (TDS), PF/Gratuity/Loans, GL Journals, Bills, Invoices & 16 Financial Reports.',
        'allow_organization': False,
        'allow_recruitment': False,
        'allow_employee_mgmt': False,
        'allow_attendance': False,
        'allow_leaves': False,
        'allow_performance': False,
        'allow_payroll': True,
        'allow_accounting': True,
        'allow_financial_reports': True,
        'allow_self_service': True,
        'allow_operations': False,
        'allow_settings': True,
        'allow_user_management': False,
        'allow_system_modules': False,
        'group_xmlids': (
            'base.group_user,DSL_HRMS_core.group_dsl_hrms_user,'
            'DSL_HRMS_core.group_dsl_hrms_officer,hr.group_hr_user,'
            'account.group_account_readonly,account.group_account_invoice,'
            'account.group_account_user,account.group_account_manager'
        ),
    },
    {
        'sequence': 60,
        'code': 'operations',
        'name': 'Operations & Factory Admin',
        'color': 6,
        'default_dashboard': 'hr',
        'description': 'Plant & Facility Operations: Canteen Meal Logs, Vehicle Requisitions & Fuel, Visitor Gate Pass, Garments Floor Lines & Compliance Audits.',
        'allow_organization': False,
        'allow_recruitment': False,
        'allow_employee_mgmt': False,
        'allow_attendance': True,
        'allow_leaves': False,
        'allow_performance': False,
        'allow_payroll': False,
        'allow_accounting': False,
        'allow_financial_reports': False,
        'allow_self_service': True,
        'allow_operations': True,
        'allow_settings': False,
        'allow_user_management': False,
        'allow_system_modules': False,
        'group_xmlids': (
            'base.group_user,DSL_HRMS_core.group_dsl_hrms_user,'
            'DSL_HRMS_core.group_dsl_hrms_officer,hr.group_hr_user,'
            'hr_attendance.group_hr_attendance_officer'
        ),
    },
    {
        'sequence': 70,
        'code': 'company_admin',
        'name': 'Company Administrator (Company-Scoped)',
        'color': 9,
        'default_dashboard': 'hr',
        'description': 'Full Administrator for Assigned Company Only: Accesses all modules, Settings, Policies, and User Creation strictly within their assigned Company.',
        'allow_organization': True,
        'allow_recruitment': True,
        'allow_employee_mgmt': True,
        'allow_attendance': True,
        'allow_leaves': True,
        'allow_performance': True,
        'allow_payroll': True,
        'allow_accounting': True,
        'allow_financial_reports': True,
        'allow_self_service': True,
        'allow_operations': True,
        'allow_settings': True,
        'allow_user_management': True,
        'allow_system_modules': False,
        'group_xmlids': (
            'base.group_user,DSL_HRMS_core.group_dsl_hrms_user,'
            'DSL_HRMS_core.group_dsl_hrms_officer,DSL_HRMS_core.group_dsl_hrms_manager,'
            'hr.group_hr_user,hr.group_hr_manager,hr_attendance.group_hr_attendance_officer,'
            'hr_holidays.group_hr_holidays_user,hr_holidays.group_hr_holidays_manager,'
            'hr_recruitment.group_hr_recruitment_user,hr_recruitment.group_hr_recruitment_manager,'
            'account.group_account_readonly,account.group_account_invoice,'
            'account.group_account_user,account.group_account_manager,base.group_erp_manager'
        ),
    },
    {
        'sequence': 80,
        'code': 'super_admin',
        'name': 'Super Administrator (Group HQ)',
        'color': 1,
        'default_dashboard': 'hr',
        'description': 'Unrestricted Group HQ System Administrator: Full control over all Companies, Branches, Modules, Users & Global System Settings.',
        'allow_organization': True,
        'allow_recruitment': True,
        'allow_employee_mgmt': True,
        'allow_attendance': True,
        'allow_leaves': True,
        'allow_performance': True,
        'allow_payroll': True,
        'allow_accounting': True,
        'allow_financial_reports': True,
        'allow_self_service': True,
        'allow_operations': True,
        'allow_settings': True,
        'allow_user_management': True,
        'allow_system_modules': True,
        'group_xmlids': (
            'base.group_user,DSL_HRMS_core.group_dsl_hrms_user,'
            'DSL_HRMS_core.group_dsl_hrms_officer,DSL_HRMS_core.group_dsl_hrms_manager,'
            'hr.group_hr_user,hr.group_hr_manager,hr_attendance.group_hr_attendance_officer,'
            'hr_holidays.group_hr_holidays_user,hr_holidays.group_hr_holidays_manager,'
            'hr_recruitment.group_hr_recruitment_user,hr_recruitment.group_hr_recruitment_manager,'
            'account.group_account_readonly,account.group_account_invoice,'
            'account.group_account_user,account.group_account_manager,'
            'base.group_erp_manager,base.group_system'
        ),
    },
]


class DslAccessRoleTemplate(models.Model):
    _name = 'dsl.access.role.template'
    _description = 'DSL HRMS Access Role Template (Multi-Role Plug-and-Play)'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Role Template Name', required=True)
    code = fields.Selection(
        selection=[
            ('employee', 'Employee (Self-Service / ESS)'),
            ('manager', 'Line Manager / Supervisor (MSS)'),
            ('hr_officer', 'HR Officer / Executive'),
            ('hr_manager', 'HR & Payroll Manager'),
            ('accounts', 'Accounts & Finance'),
            ('operations', 'Operations & Factory Admin'),
            ('company_admin', 'Company Administrator (Company-Scoped)'),
            ('super_admin', 'Super Administrator (Group HQ)'),
        ],
        string='Template Code',
        required=True,
        index=True,
    )
    color = fields.Integer(string='Badge Color', default=4)
    description = fields.Char(string='Access Scope Summary')
    default_dashboard = fields.Selection(
        selection=[
            ('ess', 'My Portal (ESS)'),
            ('mss', 'Manager Hub (MSS)'),
            ('accounts', 'Accounting & Finance Dashboard'),
            ('hr', 'HR Executive Dashboard'),
        ],
        string='Default Dashboard',
        default='ess',
        required=True,
    )

    # Sidebar & Module Section Access Flags
    allow_organization = fields.Boolean(string='Organization & Structure', default=False)
    allow_recruitment = fields.Boolean(string='Recruitment & ATS', default=False)
    allow_employee_mgmt = fields.Boolean(string='Employee Management', default=False)
    allow_attendance = fields.Boolean(string='Attendance & Shift', default=False)
    allow_leaves = fields.Boolean(string='Leave Management', default=False)
    allow_performance = fields.Boolean(string='Performance & 360°', default=False)
    allow_payroll = fields.Boolean(string='Payroll & Benefits', default=False)
    allow_accounting = fields.Boolean(string='Accounting & Finance', default=False)
    allow_financial_reports = fields.Boolean(string='Financial Reports', default=False)
    allow_self_service = fields.Boolean(string='Self-Service (ESS / MSS)', default=True)
    allow_operations = fields.Boolean(string='Operations & Factory', default=False)
    allow_settings = fields.Boolean(string='Settings Menu Access', default=False)
    allow_user_management = fields.Boolean(string='Can Create & Manage Company Users', default=False)
    allow_system_modules = fields.Boolean(string='Can Manage System Modules (Super Admin)', default=False)

    group_xmlids = fields.Char(
        string='Mapped Security Group XMLIDs',
        help='Comma-separated Odoo res.groups XML IDs granted automatically when this role template is assigned.',
    )
    user_ids = fields.Many2many(
        'res.users',
        'dsl_user_role_template_rel',
        'template_id',
        'user_id',
        string='Assigned Users',
    )
    user_count = fields.Integer(
        string='Assigned Users Count',
        compute='_compute_user_count',
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Each Role Template code must be unique!'),
    ]

    @api.depends('user_ids')
    def _compute_user_count(self):
        for rec in self:
            rec.user_count = len(rec.sudo().user_ids.filtered(lambda u: u.active))

    @api.model
    def _ensure_default_role_templates(self):
        """Ensure all 8 standard Role Templates exist."""
        Template = self.sudo()
        for defn in ROLE_TEMPLATE_DEFINITIONS:
            existing = Template.search([('code', '=', defn['code'])], limit=1)
            if not existing:
                Template.create(defn)
        return True

    def _resolve_odoo_groups(self):
        """Return `res.groups` recordset corresponding to `self.mapped('group_xmlids')`."""
        groups = self.env['res.groups'].sudo()
        for tpl in self.sudo():
            for xmlid in (tpl.group_xmlids or '').split(','):
                xmlid = xmlid.strip()
                if not xmlid:
                    continue
                grp = self.env.ref(xmlid, raise_if_not_found=False)
                if grp and grp._name == 'res.groups':
                    groups |= grp.sudo()
        return groups

    def write(self, vals):
        res = super().write(vals)
        perm_fields = {
            'default_dashboard', 'allow_organization', 'allow_recruitment',
            'allow_employee_mgmt', 'allow_attendance', 'allow_leaves',
            'allow_performance', 'allow_payroll', 'allow_accounting',
            'allow_financial_reports', 'allow_self_service', 'allow_operations',
            'allow_settings', 'allow_user_management', 'allow_system_modules',
            'group_xmlids',
        }
        if perm_fields & set(vals.keys()):
            users = self.sudo().mapped('user_ids')
            if users:
                users._compute_dsl_role_summary()
                users._sync_dsl_role_templates_to_groups()
        return res


MAIN_MENU_DEFINITIONS = [
    {'sequence': 10, 'code': 'dashboard', 'name': '01 · Dashboard (Main Workspace)', 'color': 1},
    {'sequence': 20, 'code': 'organization', 'name': '02 · Organization (Companies, Branches, Depts, Org Chart)', 'color': 2},
    {'sequence': 30, 'code': 'recruitment', 'name': '03 · Recruitment & ATS (Requisitions, Pipeline, Onboarding)', 'color': 3},
    {'sequence': 40, 'code': 'employee_mgmt', 'name': '04 · Employee Management (Directory, Education, Skills, Docs)', 'color': 4},
    {'sequence': 50, 'code': 'attendance', 'name': '05 · Attendance & Shift (Attendance, Biometric, GPS, Roster, OT)', 'color': 5},
    {'sequence': 60, 'code': 'leaves', 'name': '06 · Leave Management (Leaves, Approvals, Quotas, Holidays)', 'color': 6},
    {'sequence': 70, 'code': 'performance', 'name': '07 · Performance & 360° (Assessments, KPIs, Calibration, PIP)', 'color': 7},
    {'sequence': 80, 'code': 'payroll', 'name': '08 · Payroll & Benefits (Payslips, Tax, Loans, PF, Gratuity, Bonus)', 'color': 8},
    {'sequence': 90, 'code': 'accounting', 'name': '09 · Accounting & Finance (GL Vouchers, Journals, Bills, Assets)', 'color': 9},
    {'sequence': 100, 'code': 'financial_reports', 'name': '10 · Financial Reports (Balance Sheet, P&L, Cash Flow, Ledgers)', 'color': 10},
    {'sequence': 110, 'code': 'self_service', 'name': '11 · Self-Service & Exit (My Portal ESS, Letters, Helpdesk, Exit)', 'color': 11},
    {'sequence': 120, 'code': 'operations', 'name': '12 · Operations & Factory (Canteen, Fleet, Visitor, Garments Floor)', 'color': 1},
    {'sequence': 130, 'code': 'settings', 'name': '13 · Settings (All System, HR, Payroll & Accounting Settings)', 'color': 2},
    {'sequence': 140, 'code': 'mss_portal', 'name': '14 · Manager Hub (MSS Sub-Menu)', 'color': 3},
    {'sequence': 150, 'code': 'hr_announcements', 'name': '15 · HR Announcements (Notice Board Sub-Menu)', 'color': 4},
]


class DslHrmsMainMenu(models.Model):
    _name = 'dsl.hrms.main.menu'
    _description = 'DSL HRMS Main Sidebar Menu Item (For Per-User Menu Hiding)'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Main Menu Name', required=True)
    code = fields.Char(string='Menu Key', required=True, index=True)
    color = fields.Integer(string='Badge Color', default=1)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('menu_code_uniq', 'unique(code)', 'Each Main Menu code must be unique!'),
    ]

    @api.model
    def _ensure_default_main_menus(self):
        Menu = self.sudo()
        for defn in MAIN_MENU_DEFINITIONS:
            existing = Menu.search([('code', '=', defn['code'])], limit=1)
            if existing:
                existing.write({'name': defn['name'], 'sequence': defn['sequence'], 'color': defn['color']})
            else:
                Menu.create(defn)
        return True

    def _register_hook(self):
        res = super()._register_hook()
        try:
            self._ensure_default_main_menus()
            self.env['dsl.access.role.template'].sudo()._ensure_default_role_templates()
        except Exception:
            pass
        return res


class ResUsersRoleTemplateExt(models.Model):
    _inherit = 'res.users'

    dsl_hidden_menu_ids = fields.Many2many(
        'dsl.hrms.main.menu',
        'dsl_user_hidden_main_menu_rel',
        'user_id',
        'menu_id',
        string='Force-Hidden Main Menus',
        help='Select any Main Menus here to strictly hide them from this user — even if the user has Role Template or Module access!',
    )

    dsl_role_template_ids = fields.Many2many(
        'dsl.access.role.template',
        'dsl_user_role_template_rel',
        'user_id',
        'template_id',
        string='Access Role Templates',
        help='Select one or multiple Role Templates (e.g., Employee + Accounts, or HR Officer + Line Manager). '
             'All required permissions and dashboards are configured automatically.',
    )
    dsl_primary_dashboard = fields.Selection(
        selection=[
            ('ess', 'My Portal (ESS)'),
            ('mss', 'Manager Hub (MSS)'),
            ('accounts', 'Accounting & Finance Dashboard'),
            ('hr', 'HR Executive Dashboard'),
        ],
        string='Primary Landing Dashboard',
        compute='_compute_dsl_role_summary',
        store=True,
        readonly=False,
    )
    dsl_role_badge_label = fields.Char(
        string='Active Role Summary',
        compute='_compute_dsl_role_summary',
        store=True,
    )
    dsl_can_manage_settings = fields.Boolean(
        string='Can Access Settings',
        compute='_compute_dsl_role_summary',
        store=True,
        readonly=False,
    )
    dsl_can_manage_company_users = fields.Boolean(
        string='Can Create & Manage Company Users',
        compute='_compute_dsl_role_summary',
        store=True,
        readonly=False,
    )

    # Per-User Granular Module & Menu Access Checkboxes (Auto-filled by Role Template, Editable per User!)
    user_allow_organization = fields.Boolean(
        string='Organization & Structure',
        compute='_compute_dsl_role_summary',
        store=True,
        readonly=False,
    )
    user_allow_recruitment = fields.Boolean(
        string='Recruitment & ATS',
        compute='_compute_dsl_role_summary',
        store=True,
        readonly=False,
    )
    user_allow_employee_mgmt = fields.Boolean(
        string='Employee Management',
        compute='_compute_dsl_role_summary',
        store=True,
        readonly=False,
    )
    user_allow_attendance = fields.Boolean(
        string='Attendance & Shift',
        compute='_compute_dsl_role_summary',
        store=True,
        readonly=False,
    )
    user_allow_leaves = fields.Boolean(
        string='Leave Management',
        compute='_compute_dsl_role_summary',
        store=True,
        readonly=False,
    )
    user_allow_performance = fields.Boolean(
        string='Performance & 360°',
        compute='_compute_dsl_role_summary',
        store=True,
        readonly=False,
    )
    user_allow_payroll = fields.Boolean(
        string='Payroll & Benefits',
        compute='_compute_dsl_role_summary',
        store=True,
        readonly=False,
    )
    user_allow_accounting = fields.Boolean(
        string='Accounting & Finance',
        compute='_compute_dsl_role_summary',
        store=True,
        readonly=False,
    )
    user_allow_financial_reports = fields.Boolean(
        string='Financial Reports (16)',
        compute='_compute_dsl_role_summary',
        store=True,
        readonly=False,
    )
    user_allow_self_service = fields.Boolean(
        string='Self-Service (ESS / MSS)',
        compute='_compute_dsl_role_summary',
        store=True,
        readonly=False,
        default=True,
    )
    user_allow_operations = fields.Boolean(
        string='Operations & Factory',
        compute='_compute_dsl_role_summary',
        store=True,
        readonly=False,
    )
    user_allow_system_modules = fields.Boolean(
        string='HRMS Modules (App Installer)',
        compute='_compute_dsl_role_summary',
        store=True,
        readonly=False,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Default new users to the current creator's active company and 'Employee (ESS)' role template
        if not self.env.user._is_unrestricted_super_admin():
            allowed_cids = self.env.user.sudo().company_ids.ids
            active_cid = self.env.company.id if self.env.company.id in allowed_cids else (allowed_cids[0] if allowed_cids else False)
            if active_cid:
                res['company_id'] = active_cid
                res['company_ids'] = [(6, 0, [active_cid])]
            res['auto_group_company_access'] = False
        if 'dsl_role_template_ids' in fields_list and not res.get('dsl_role_template_ids'):
            emp_tpl = self.env['dsl.access.role.template'].sudo().search([('code', '=', 'employee')], limit=1)
            if emp_tpl:
                res['dsl_role_template_ids'] = [(6, 0, [emp_tpl.id])]
        return res

    def _is_unrestricted_super_admin(self):
        """Return True ONLY if this user is Odoo SUPERUSER, base.user_admin, or has 'super_admin' role template
        AND has Mother / Holding Company access."""
        self.ensure_one()
        real_id = self._origin.id or (self.id if isinstance(self.id, int) else False)
        if real_id == odoo.SUPERUSER_ID:
            return True
        admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
        if admin_user and real_id == admin_user.id:
            return True
        user_sudo = self.sudo()
        codes = set(user_sudo.dsl_role_template_ids.mapped('code'))
        if 'super_admin' in codes and user_sudo._is_mother_holding_user():
            return True
        return False

    @api.depends(
        'dsl_role_template_ids',
        'dsl_role_template_ids.code',
        'dsl_role_template_ids.name',
        'dsl_role_template_ids.allow_organization',
        'dsl_role_template_ids.allow_recruitment',
        'dsl_role_template_ids.allow_employee_mgmt',
        'dsl_role_template_ids.allow_attendance',
        'dsl_role_template_ids.allow_leaves',
        'dsl_role_template_ids.allow_performance',
        'dsl_role_template_ids.allow_payroll',
        'dsl_role_template_ids.allow_accounting',
        'dsl_role_template_ids.allow_financial_reports',
        'dsl_role_template_ids.allow_self_service',
        'dsl_role_template_ids.allow_operations',
        'dsl_role_template_ids.allow_settings',
        'dsl_role_template_ids.allow_user_management',
        'dsl_role_template_ids.allow_system_modules',
    )
    def _compute_dsl_role_summary(self):
        for user in self:
            tpls = user.sudo().dsl_role_template_ids.sorted('sequence')
            codes = set(tpls.mapped('code'))
            if not tpls:
                is_sys = user.id == odoo.SUPERUSER_ID or user.has_group('base.group_system')
                user.dsl_primary_dashboard = 'hr' if is_sys else 'ess'
                user.dsl_role_badge_label = 'Super Administrator' if is_sys else 'Employee (ESS)'
                user.dsl_can_manage_settings = is_sys
                user.dsl_can_manage_company_users = is_sys
                user.user_allow_organization = is_sys
                user.user_allow_recruitment = is_sys
                user.user_allow_employee_mgmt = is_sys
                user.user_allow_attendance = is_sys
                user.user_allow_leaves = is_sys
                user.user_allow_performance = is_sys
                user.user_allow_payroll = is_sys
                user.user_allow_accounting = is_sys
                user.user_allow_financial_reports = is_sys
                user.user_allow_self_service = True
                user.user_allow_operations = is_sys
                user.user_allow_system_modules = is_sys
                continue

            if codes & {'super_admin', 'company_admin', 'hr_manager', 'hr_officer', 'operations'}:
                primary_dash = 'hr'
            elif 'accounts' in codes:
                primary_dash = 'accounts'
            elif 'manager' in codes:
                primary_dash = 'mss'
            else:
                primary_dash = 'ess'

            user.dsl_primary_dashboard = primary_dash
            user.dsl_role_badge_label = ' + '.join(tpls.mapped('name'))
            user.dsl_can_manage_settings = any(tpls.mapped('allow_settings'))
            user.dsl_can_manage_company_users = any(tpls.mapped('allow_user_management'))
            user.user_allow_organization = any(tpls.mapped('allow_organization'))
            user.user_allow_recruitment = any(tpls.mapped('allow_recruitment'))
            user.user_allow_employee_mgmt = any(tpls.mapped('allow_employee_mgmt'))
            user.user_allow_attendance = any(tpls.mapped('allow_attendance'))
            user.user_allow_leaves = any(tpls.mapped('allow_leaves'))
            user.user_allow_performance = any(tpls.mapped('allow_performance'))
            user.user_allow_payroll = any(tpls.mapped('allow_payroll'))
            user.user_allow_accounting = any(tpls.mapped('allow_accounting'))
            user.user_allow_financial_reports = any(tpls.mapped('allow_financial_reports'))
            user.user_allow_self_service = True
            user.user_allow_operations = any(tpls.mapped('allow_operations'))
            user.user_allow_system_modules = any(tpls.mapped('allow_system_modules'))

    @api.onchange('dsl_role_template_ids')
    def _onchange_dsl_role_template_ids(self):
        self._compute_dsl_role_summary()

    def action_open_role_templates_matrix(self):
        """Open the Role Templates & Permissions Matrix so Admin can see/edit what each template contains."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Access Role Templates & Permission Matrix'),
            'res_model': 'dsl.access.role.template',
            'view_mode': 'list,form',
            'target': 'current',
        }

    def _sync_dsl_role_templates_to_groups(self):
        """Automatically synchronize `user.groups_id` whenever `dsl_role_template_ids` changes."""
        if self.env.context.get('skip_dsl_role_sync'):
            return
        all_templates = self.env['dsl.access.role.template'].sudo().search([])
        all_managed_groups = all_templates._resolve_odoo_groups()
        base_user_group = self.env.ref('base.group_user', raise_if_not_found=False)
        hrms_user_group = self.env.ref('DSL_HRMS_core.group_dsl_hrms_user', raise_if_not_found=False)
        admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
        protected_uids = {odoo.SUPERUSER_ID}
        if admin_user:
            protected_uids.add(admin_user.id)

        for user in self.sudo().filtered(lambda u: not u.share):
            tpls = user.dsl_role_template_ids
            if not tpls:
                continue
            target_managed_groups = tpls._resolve_odoo_groups()
            if base_user_group:
                target_managed_groups |= base_user_group.sudo()
            if hrms_user_group:
                target_managed_groups |= hrms_user_group.sudo()

            # Also honor per-user custom checkbox overrides (kom-beshi access customization):
            extra_xmlids = []
            if user.user_allow_employee_mgmt or user.user_allow_organization or user.user_allow_attendance or user.user_allow_leaves:
                extra_xmlids.extend(['DSL_HRMS_core.group_dsl_hrms_officer', 'hr.group_hr_user'])
            if user.user_allow_payroll or user.dsl_can_manage_settings:
                extra_xmlids.extend(['DSL_HRMS_core.group_dsl_hrms_manager', 'hr.group_hr_manager'])
            if user.user_allow_accounting or user.user_allow_financial_reports:
                extra_xmlids.extend([
                    'account.group_account_readonly', 'account.group_account_invoice',
                    'account.group_account_user', 'account.group_account_manager',
                ])
            if user.dsl_can_manage_company_users:
                extra_xmlids.extend(['DSL_HRMS_core.group_dsl_hrms_manager', 'base.group_erp_manager'])
            for xid in extra_xmlids:
                g = self.env.ref(xid, raise_if_not_found=False)
                if g:
                    target_managed_groups |= g.sudo()

            current_groups = user.groups_id
            if user.id in protected_uids:
                # Never strip groups from root / main admin, only add missing ones
                new_groups = current_groups | target_managed_groups
            else:
                # Replace managed HRMS/Accounting/Admin groups with exact union of selected Role Templates
                unmanaged_groups = current_groups - all_managed_groups
                new_groups = unmanaged_groups | target_managed_groups

            if set(new_groups.ids) != set(current_groups.ids):
                user.with_context(skip_dsl_role_sync=True, skip_dsl_user_sync=True).write({
                    'groups_id': [(6, 0, new_groups.ids)]
                })
        self.env.registry.clear_cache()

    def _enforce_company_scoped_user_admin(self, vals):
        """Ensure that a Company Administrator (who is not an unrestricted Super Admin)
        can ONLY create or edit users within their own allowed `company_ids`, and cannot grant `super_admin`."""
        if self.env.su or self.env.user._is_unrestricted_super_admin():
            return vals
        actor = self.env.user.sudo()
        allowed_cids = set(actor.company_ids.ids)
        if not allowed_cids:
            return vals

        vals = dict(vals)
        # 1. Restrict company_id to actor's allowed companies
        if vals.get('company_id') and vals['company_id'] not in allowed_cids:
            vals['company_id'] = actor.company_id.id if actor.company_id.id in allowed_cids else list(allowed_cids)[0]

        # 2. Restrict company_ids commands to actor's allowed companies
        if 'company_ids' in vals and isinstance(vals['company_ids'], list):
            sanitized_cmds = []
            for cmd in vals['company_ids']:
                if isinstance(cmd, (list, tuple)) and len(cmd) >= 3 and cmd[0] == 6:
                    filtered_ids = [cid for cid in cmd[2] if cid in allowed_cids]
                    if not filtered_ids:
                        filtered_ids = [vals.get('company_id') or actor.company_id.id]
                    sanitized_cmds.append((6, 0, filtered_ids))
                elif isinstance(cmd, (list, tuple)) and len(cmd) >= 2 and cmd[0] == 4:
                    if cmd[1] in allowed_cids:
                        sanitized_cmds.append(cmd)
                else:
                    sanitized_cmds.append(cmd)
            vals['company_ids'] = sanitized_cmds
        elif not self and 'company_ids' not in vals:
            cid = vals.get('company_id') or actor.company_id.id
            vals['company_ids'] = [(6, 0, [cid])]

        # 3. Prevent non-Super-Admin from assigning 'super_admin' role template
        if 'dsl_role_template_ids' in vals and isinstance(vals['dsl_role_template_ids'], list):
            super_tpl = self.env['dsl.access.role.template'].sudo().search([('code', '=', 'super_admin')], limit=1)
            if super_tpl:
                clean_tpl_cmds = []
                for cmd in vals['dsl_role_template_ids']:
                    if isinstance(cmd, (list, tuple)) and len(cmd) >= 3 and cmd[0] == 6:
                        clean_ids = [tid for tid in cmd[2] if tid != super_tpl.id]
                        clean_tpl_cmds.append((6, 0, clean_ids))
                    elif isinstance(cmd, (list, tuple)) and len(cmd) >= 2 and cmd[0] == 4:
                        if cmd[1] != super_tpl.id:
                            clean_tpl_cmds.append(cmd)
                    else:
                        clean_tpl_cmds.append(cmd)
                vals['dsl_role_template_ids'] = clean_tpl_cmds

        return vals

    @api.model_create_multi
    def create(self, vals_list):
        emp_tpl = self.env['dsl.access.role.template'].sudo().search([('code', '=', 'employee')], limit=1)
        clean_vals_list = []
        for vals in vals_list:
            v = self._enforce_company_scoped_user_admin(vals)
            if emp_tpl and not v.get('dsl_role_template_ids') and not v.get('share'):
                v['dsl_role_template_ids'] = [(6, 0, [emp_tpl.id])]
            clean_vals_list.append(v)
        target_self = self.sudo() if (self.env.su or getattr(self.env.user.sudo(), 'dsl_can_manage_company_users', False)) else self
        users = super(ResUsersRoleTemplateExt, target_self).create(clean_vals_list)
        users._sync_dsl_role_templates_to_groups()
        return users.with_env(self.env)

    def write(self, vals):
        if not self.env.su and not self.env.user._is_unrestricted_super_admin():
            allowed_cids = set(self.env.user.sudo().company_ids.ids)
            for u in self.sudo():
                if u.id != self.env.uid and not (set(u.company_ids.ids) & allowed_cids):
                    raise AccessError(_("You can only manage users belonging to your assigned company."))
        vals = self._enforce_company_scoped_user_admin(vals)
        target_self = self.sudo() if (self.env.su or getattr(self.env.user.sudo(), 'dsl_can_manage_company_users', False)) else self
        res = super(ResUsersRoleTemplateExt, target_self).write(vals)
        role_or_flag_keys = {
            'dsl_role_template_ids', 'user_allow_organization', 'user_allow_recruitment',
            'user_allow_employee_mgmt', 'user_allow_attendance', 'user_allow_leaves',
            'user_allow_performance', 'user_allow_payroll', 'user_allow_accounting',
            'user_allow_financial_reports', 'user_allow_operations',
            'dsl_can_manage_settings', 'dsl_can_manage_company_users',
        }
        if (set(vals.keys()) & role_or_flag_keys) and not self.env.context.get('skip_dsl_role_sync'):
            self._sync_dsl_role_templates_to_groups()
        return res

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        """Strict Company Isolation on `res.users`:
        When a Company Administrator (or any non-Super-Admin user) opens Settings -> Users & Access,
        they can ONLY see users belonging to their own allowed `company_ids` (and never see other companies' users)."""
        if not self.env.su and not self.env.user._is_unrestricted_super_admin():
            allowed_cids = self.env.user.sudo().company_ids.ids
            if allowed_cids:
                admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
                excl_uids = [odoo.SUPERUSER_ID]
                if admin_user and self.env.uid != admin_user.id:
                    excl_uids.append(admin_user.id)
                domain = list(domain or []) + [
                    ('company_ids', 'in', allowed_cids),
                    ('id', 'not in', excl_uids),
                ]
        return super()._search(domain, offset=offset, limit=limit, order=order)


class ResCompanyStrictScopeExt(models.Model):
    _inherit = 'res.company'

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        """Strict Company Isolation on `res.company`:
        When a user is assigned to specific Company(ies), even if they have Settings / Company Admin access,
        they can ONLY see their own allowed `company_ids` in Settings, Company Directory, Dropdowns & User Creation!"""
        if not self.env.su and not self.env.user._is_unrestricted_super_admin():
            allowed_cids = self.env.user.sudo().company_ids.ids
            if allowed_cids:
                domain = list(domain or []) + [('id', 'in', allowed_cids)]
        return super()._search(domain, offset=offset, limit=limit, order=order)

    def write(self, vals):
        if not self.env.su and not self.env.user._is_unrestricted_super_admin():
            allowed_cids = set(self.env.user.sudo().company_ids.ids)
            for comp in self:
                if comp.id not in allowed_cids:
                    raise AccessError(_("You can only modify settings for your assigned company (%s).") % comp.name)
        return super().write(vals)
