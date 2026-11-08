# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS: Canteen Meal Booking & Payroll Recovery',
    'summary': 'Daily/Monthly Meal Booking, Employer Subsidy Split & Automated Monthly Payslip Deduction',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Facility',
    'author': 'Daffodil Software Limited (DSL)',
    'website': 'https://daffodilsoft.com',
    'license': 'LGPL-3',
    'depends': [
        'DSL_HRMS_core',
        'DSL_HRMS_employee',
        'DSL_HRMS_payroll_bd',
    ],
    'data': [
        'security/dsl_canteen_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_canteen_data.xml',
        'views/dsl_canteen_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

