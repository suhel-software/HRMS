# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS: Manager Self-Service (MSS) & Career Proposals',
    'summary': 'Live Team Attendance Roster, 1-Click Approvals & Promotion / Increment / Confirmation Proposals',
    'description': """
DSL Enterprise HRMS — Phase 8: Manager Self-Service (MSS) Workspace
===================================================================
* OWL 2 Live Manager Hub: Real-time Team Attendance Roster, Late/Leave Pulse, Pending Approvals Queue
* 1-Click Quick Leave Approval directly from MSS Team Hub
* Formal Career Proposals (`dsl.mss.recommendation`): Promotion, Annual Increment, Probation Confirmation & Branch Transfer
    """,
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Self Service',
    'author': 'Daffodil Software Limited (DSL)',
    'website': 'https://daffodilsoft.com',
    'license': 'LGPL-3',
    'depends': [
        'web',
        'DSL_HRMS_core',
        'DSL_HRMS_employee',
        'DSL_HRMS_salary_structure',
        'DSL_HRMS_attendance',
        'DSL_HRMS_leave',
        'DSL_HRMS_leave_approval',
        'DSL_HRMS_overtime',
    ],
    'data': [
        'security/dsl_mss_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_mss_data.xml',
        'views/dsl_mss_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'DSL_HRMS_mss/static/src/scss/mss_portal.scss',
            'DSL_HRMS_mss/static/src/js/mss_portal.js',
            'DSL_HRMS_mss/static/src/xml/mss_portal.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}

