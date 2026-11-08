# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS: Factory, Garments Line & Compliance Audit',
    'summary': 'RMG Sewing Line Worker Allocation, Efficiency Tracking & BD Labour Act / RSC / BSCI Compliance Audit',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Manufacturing',
    'author': 'Daffodil Software Limited (DSL)',
    'website': 'https://daffodilsoft.com',
    'license': 'LGPL-3',
    'depends': [
        'DSL_HRMS_core',
        'DSL_HRMS_employee',
    ],
    'data': [
        'security/dsl_factory_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_factory_data.xml',
        'views/dsl_factory_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

