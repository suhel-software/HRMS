# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS: Employee Onboarding & Asset Handover',
    'summary': 'New Joiner Onboarding Checklist & Corporate IT / Admin Asset Handover Register',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Onboarding',
    'author': 'Daffodil Software Limited (DSL)',
    'website': 'https://daffodilsoft.com',
    'license': 'LGPL-3',
    'depends': [
        'DSL_HRMS_core',
        'DSL_HRMS_employee',
        'hr',
        'mail',
    ],
    'data': [
        'security/dsl_onboarding_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_onboarding_data.xml',
        'views/dsl_onboarding_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

