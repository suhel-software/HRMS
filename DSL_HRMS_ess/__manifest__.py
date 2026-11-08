# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS Employee Self-Service (ESS) Portal',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Interactive Employee Self-Service Workspace, Live Attendance Punch, Payslips, Leave Quotas & HR Letters/NOC',
    'description': """
DSL HRMS Employee Self-Service (ESS)
====================================
- Modern Interactive ESS Workspace (Today's Attendance Check-In/Out, Leave Quotas, Latest Payslips, Loan & PF Balance)
- Official HR Certificate, Salary Certificate, Bank Introduction & Visa NOC Request Workflow + Printable Letter
- 1-Click Self-Service Shortcuts for Leaves, Regularization, Loans & HR Helpdesk
    """,
    'author': 'DSL Enterprise',
    'license': 'LGPL-3',
    'depends': [
        'web',
        'DSL_HRMS_core',
        'DSL_HRMS_employee',
        'DSL_HRMS_attendance',
        'DSL_HRMS_leave',
        'DSL_HRMS_payroll_bd',
        'DSL_HRMS_loan',
    ],
    'data': [
        'security/dsl_ess_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_ess_data.xml',
        'views/dsl_ess_views.xml',
        'reports/dsl_ess_reports.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'DSL_HRMS_ess/static/src/scss/ess_portal.scss',
            'DSL_HRMS_ess/static/src/js/ess_portal.js',
            'DSL_HRMS_ess/static/src/xml/ess_portal.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}

