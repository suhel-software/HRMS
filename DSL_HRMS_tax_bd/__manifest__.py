# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS - Bangladesh NBR Income Tax (TDS / AIT) Engine',
    'version': '18.0.1.0.0',
    'summary': 'NBR Income Tax Act 2023 (1/3rd Exemption, Progressive Slabs, DPS/Sanchaypatra Rebate, Min Tax Floor & Auto Payslip TDS)',
    'description': """
        Enterprise Bangladesh NBR Income Tax (TDS / AIT) Engine for DSL HRMS (Plug-and-Play):
        - Bangladesh Income Tax Act 2023 (আয়কর আইন, ২০২৩): 1/3rd Salary Exemption capped at ৳4,50,000
        - Category-based Zero-Tax Thresholds (Male ৳3.5L, Female/65+ ৳4.0L, Disabled/3rd Gender ৳4.75L, Freedom Fighter ৳5.0L)
        - Progressive NBR Tax Slabs (5%, 10%, 15%, 20%, 25%, 30%) + City Corporation Minimum Tax Floor (৳5,000 / ৳4,000 / ৳3,000)
        - Section 78 Investment Tax Rebate (`min(3% Taxable, 15% Eligible Investment, ৳10L)`) with DPS ৳1.2L & Sanchaypatra ৳5L caps
        - Automatic Monthly AIT / TDS injection into `DSL_HRMS_payroll_bd` Payslips + Printable Salary Tax Certificate
        - 100% Full-Width Forms with Mandatory Bottom Chatter & Multi-Company / Multi-Branch Isolation
    """,
    'category': 'Human Resources/Payroll',
    'author': 'DSL Enterprise HRMS',
    'license': 'LGPL-3',
    'depends': [
        'DSL_HRMS_core',
        'DSL_HRMS_branch',
        'DSL_HRMS_employee',
        'DSL_HRMS_salary_structure',
        'DSL_HRMS_payroll_bd',
        'hr',
        'mail',
    ],
    'data': [
        'security/dsl_tax_bd_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_tax_bd_data.xml',
        'views/dsl_tax_bd_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

