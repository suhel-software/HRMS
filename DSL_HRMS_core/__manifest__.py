# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS Core',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Core foundation for DSL HRMS Enterprise Platform',
    'description': """
DSL HRMS Core Foundation
========================
- Centralized Menu Hierarchy for DSL HRMS
- Core Configuration Settings
- Base Security Roles & Permissions
- Plug-and-Play Architecture Backbone
    """,
    'author': 'DSL Enterprise',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'mail', 'hr'],
    'data': [
        'security/dsl_hrms_security.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
