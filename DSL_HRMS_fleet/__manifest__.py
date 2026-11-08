# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS: Vehicle Requisition & Fuel Log',
    'summary': 'Corporate Vehicle Pool, Employee Transport Requisition & Octane/CNG/Diesel Fuel Log',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Fleet',
    'author': 'Daffodil Software Limited (DSL)',
    'website': 'https://daffodilsoft.com',
    'license': 'LGPL-3',
    'depends': [
        'DSL_HRMS_core',
        'DSL_HRMS_employee',
    ],
    'data': [
        'security/dsl_fleet_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_fleet_data.xml',
        'views/dsl_fleet_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

