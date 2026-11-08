# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS: Visitor Gate Pass & Security Log',
    'summary': 'Visitor Pre-Registration, Host Approval, Security Gate Check-In/Out & Printable Badge',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Security',
    'author': 'Daffodil Software Limited (DSL)',
    'website': 'https://daffodilsoft.com',
    'license': 'LGPL-3',
    'depends': [
        'DSL_HRMS_core',
        'DSL_HRMS_employee',
    ],
    'data': [
        'security/dsl_visitor_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_visitor_data.xml',
        'views/dsl_visitor_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

