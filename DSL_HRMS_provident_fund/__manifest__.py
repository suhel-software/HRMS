# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS Provident Fund (PF) Trust',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Recognized Provident Fund Trust, 50-50 Employee/Employer Ledger, Vesting & Profit Distribution',
    'description': """
DSL HRMS Recognized Provident Fund Trust (Bangladesh)
=====================================================
- Employee & Employer Equal Contribution (10% + 10% of Basic) Ledger
- Trust Deed Vesting Rules (0% / 50% / 100% Employer Share by Tenure)
- Annual PF Trust Profit / Interest Pro-Rata Distribution Batch
- Automatic Monthly Sync from Disbursed Payslips (`PF_EMPLOYEE` & `PF_EMPLOYER`)
    """,
    'author': 'DSL Enterprise',
    'license': 'LGPL-3',
    'depends': [
        'DSL_HRMS_core',
        'DSL_HRMS_employee',
        'DSL_HRMS_salary_structure',
        'DSL_HRMS_payroll_bd',
    ],
    'data': [
        'security/dsl_pf_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_pf_data.xml',
        'views/dsl_pf_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

