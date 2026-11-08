# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS Multi-Branch & Factory Locations',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Organization',
    'summary': 'Head Office, Regional Hubs, Factories, Showrooms & Geofence-Ready Branch Directory',
    'description': """
DSL HRMS Multi-Branch & Location Management
===========================================
- Manage Multiple Branches, Factories, Regional Hubs, Depots & Showrooms under each Company
- Branch-wise Employee & Department Assignment with Multi-Company Data Isolation
- Branch Working Schedule, Manpower Capacity & GPS Geofence Coordinates Ready
- 100% Plug-and-Play Native Odoo 18 Module (Zero 3rd-party dependencies)
    """,
    'author': 'DSL Enterprise',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'mail', 'hr', 'DSL_HRMS_core'],
    'data': [
        'security/dsl_branch_security.xml',
        'security/ir.model.access.csv',
        'views/dsl_branch_views.xml',
        'views/hr_employee_branch_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

