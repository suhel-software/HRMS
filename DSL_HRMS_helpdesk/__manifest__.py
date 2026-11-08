# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS Internal Helpdesk & Grievance Redressal',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Internal HR Ticketing, SLA Tracking & Confidential Workplace Grievance Redressal',
    'description': """
DSL HRMS Internal Helpdesk & Grievance Redressal
================================================
- Employee HR Support Tickets (Payroll, PF/Tax, ID/Access, Admin & IT)
- Confidential Labour Act Grievance & Harassment Redressal Queue
- Automatic SLA Deadline Calculation, Breach Monitoring & Employee Rating
    """,
    'author': 'DSL Enterprise',
    'license': 'LGPL-3',
    'depends': [
        'DSL_HRMS_core',
        'DSL_HRMS_employee',
    ],
    'data': [
        'security/dsl_helpdesk_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_helpdesk_data.xml',
        'views/dsl_helpdesk_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

