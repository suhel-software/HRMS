# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS Organization Structure, Grades & Org Chart',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Organization',
    'summary': 'Divisions, Departments, Sections, Designations, Pay Grades, Cost Centers & Interactive Organogram',
    'description': """
DSL HRMS Organization & Reporting Hierarchy
===========================================
- Corporate Divisions, Departments, Sections & Production Lines
- Designations (Job Positions), Pay Grades / Salary Scale Bands & Cost Centers
- Approved Manpower Budgeting vs Active Headcount & Vacancy Tracking
- Interactive SaaS Visual Organogram (Department Tree & Employee Reporting Tree)
- 100% Plug-and-Play Native Odoo 18 Module (Zero 3rd-party dependencies)
    """,
    'author': 'DSL Enterprise',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'mail', 'hr', 'hr_org_chart', 'analytic', 'web_hierarchy', 'DSL_HRMS_core'],
    'data': [
        'security/dsl_organization_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_org_grades_data.xml',
        'views/dsl_org_masters_views.xml',
        'views/hr_department_org_views.xml',
        'views/hr_job_org_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'DSL_HRMS_organization/static/src/scss/org_chart.scss',
            'DSL_HRMS_organization/static/src/js/org_chart.js',
            'DSL_HRMS_organization/static/src/xml/org_chart.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}

