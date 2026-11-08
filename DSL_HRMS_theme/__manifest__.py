# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS Modern Theme & Debranding',
    'version': '18.0.1.0.0',
    'category': 'Theme/Backend',
    'summary': 'Custom SaaS UI, Modern Left Sidebar, Clean Layout & Complete Debranding',
    'description': """
DSL HRMS Theme & Debranding
===========================
- Complete Debranding (Removes all Odoo logos, references, footers & metadata)
- Modern Left Navigation Sidebar (inspired by DORA and Meridian)
- Global Search Header & Quick Actions
- Custom Split-Screen Modern Login Page
- Clean Card Layouts, Soft Shadows, Rounded Pills & Status Badges
- Zero 3rd party dependencies
    """,
    'author': 'DSL Enterprise',
    'license': 'LGPL-3',
    'depends': ['web', 'mail', 'DSL_HRMS_core'],
    'data': [
        'views/webclient_templates.xml',
        'views/login_templates.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            'DSL_HRMS_theme/static/src/scss/variables.scss',
        ],
        'web.assets_backend': [
            'DSL_HRMS_theme/static/src/scss/variables.scss',
            'DSL_HRMS_theme/static/src/scss/theme.scss',
            'DSL_HRMS_theme/static/src/scss/sidebar.scss',
            'DSL_HRMS_theme/static/src/scss/employee_profile.scss',
            'DSL_HRMS_theme/static/src/js/debranding.js',
            'DSL_HRMS_theme/static/src/js/chatter_bottom.js',
            'DSL_HRMS_theme/static/src/js/theme_mode.js',
            'DSL_HRMS_theme/static/src/js/sidebar.js',
            'DSL_HRMS_theme/static/src/xml/sidebar.xml',
            'DSL_HRMS_theme/static/src/xml/theme_mode.xml',
        ],
        'web.assets_frontend': [
            'DSL_HRMS_theme/static/src/scss/login.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
