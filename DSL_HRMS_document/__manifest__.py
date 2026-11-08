# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS - Digital Document Vault & Expiry Alerts',
    'version': '18.0.1.0.0',
    'summary': 'Employee Digital Document Archive, Verification Workflow & Automated Passport/Visa/Contract Expiry Alerts',
    'description': """
        Plug-and-Play Employee Document Vault for DSL HRMS:
        - Pre-configured Bangladesh HR document checklist (Smart NID, Passport, Appointment Letter, TIN, Police Verification, Medical Fitness, Work Permit)
        - Verification workflow (Pending Review -> Verified by HR / Re-upload Requested) with audit trail
        - Automated daily scheduled cron for Expiring Soon & Expired document alerts
        - Rich Kanban, List & SearchPanel isolated strictly by Company & Branch
    """,
    'category': 'Human Resources/Employees',
    'author': 'DSL Enterprise HRMS',
    'license': 'LGPL-3',
    'depends': ['DSL_HRMS_core', 'DSL_HRMS_employee', 'hr', 'mail'],
    'data': [
        'security/dsl_document_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_document_data.xml',
        'views/dsl_document_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

