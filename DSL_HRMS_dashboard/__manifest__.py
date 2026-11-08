# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS Executive Dashboard',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Interactive HR & Executive Dashboard inspired by DORA and MavionTech',
    'description': """
DSL HRMS Executive Dashboard
============================
- Live KPI Metrics (Total Employees, Turnout, Monthly Payroll, Active Departments)
- Payroll & Compensation 6-Month Trend Curve Chart
- 7-Day Attendance Trend Analysis
- Recent Workforce Directory Roster
- Quick Operations & Action Pills
    """,
    'author': 'DSL Enterprise',
    'license': 'LGPL-3',
    'depends': ['web', 'DSL_HRMS_core', 'hr'],
    'data': [
        'views/dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'DSL_HRMS_dashboard/static/src/scss/dashboard.scss',
            'DSL_HRMS_dashboard/static/src/js/dashboard.js',
            'DSL_HRMS_dashboard/static/src/xml/dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}

