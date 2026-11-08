# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS - Core Employee Dossier & BD Profile',
    'version': '18.0.1.0.0',
    'summary': 'Bangladesh Employee Master Profile, NID, TIN, Bilingual Name, Probation, Bank/MFS & Statutory Nominees',
    'description': """
        Enterprise Employee Dossier for DSL HRMS (Plug-and-Play):
        - Auto-sequenced Employee ID (`employee_code`) with company prefix support
        - Bilingual Bengali & English identity, NID (10/13/17-digit), Birth Reg, Personal e-TIN, Blood Group, Religion
        - Present & Permanent Bangladesh address with one-click copy
        - Employment Category, Probation & Confirmation lifecycle, Service Length & Age calculation
        - Bank (BEFTN/Routing) & Mobile Financial Services (bKash/Nagad/Rocket) disbursement profile
        - Statutory Nominee distribution (PF / Gratuity / Group Insurance) with 100% share validation
        - Full Multi-Company & Multi-Branch record isolation
    """,
    'category': 'Human Resources/Employees',
    'author': 'DSL Enterprise HRMS',
    'license': 'LGPL-3',
    'depends': ['DSL_HRMS_core', 'DSL_HRMS_branch', 'DSL_HRMS_organization', 'hr', 'hr_contract', 'contacts', 'mail'],
    'data': [
        'security/dsl_employee_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/hr_employee_dossier_views.xml',
        'views/dsl_employee_nominee_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

