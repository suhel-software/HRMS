# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS Multi-Company & Group Hierarchy',
    'version': '18.0.1.1.0',
    'category': 'Human Resources/Organization',
    'summary': 'Mother Company, Sister Concerns, Separate COA, Group User Access Control & Visual Group Tree',
    'description': """
DSL HRMS Multi-Company & Corporate Hierarchy
============================================
- Interactive Visual Corporate Hierarchy Tree (Mother Company -> Subsidiaries / Sister Concerns / JVs)
- 100% Independent Chart of Accounts (COA) & Currency per Legal Entity
- Smart Corporate Group User Access: Mother Company users auto-access all sub-companies with granular Sub-Company Exclusion (`excluded_company_ids`), while Subsidiary / Sister / JV users stay strictly isolated
- Bangladesh Legal & Statutory Compliance (TIN, BIN, Tax Zone/Circle, RJSC, Trade License Expiry Alerts)
- 100% Plug-and-Play Native Odoo 18 Architecture (Zero 3rd-party dependencies)
    """,
    'author': 'DSL Enterprise',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'hr', 'web_hierarchy', 'DSL_HRMS_core'],
    'data': [
        'security/dsl_multi_company_security.xml',
        'views/res_company_views.xml',
        'views/res_users_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'DSL_HRMS_multi_company/static/src/scss/company_hierarchy.scss',
            'DSL_HRMS_multi_company/static/src/js/company_hierarchy.js',
            'DSL_HRMS_multi_company/static/src/xml/company_hierarchy.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
