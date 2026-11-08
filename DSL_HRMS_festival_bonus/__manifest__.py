# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS Festival, Eid, Puja & Performance Bonus',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Eid-ul-Fitr, Eid-ul-Adha, Durga Puja, Boishakhi & Performance Bonus Batch + BEFTN Advice',
    'description': """
DSL HRMS Festival & Performance Bonus Automation (Bangladesh)
=============================================================
- Two Eids, Durga Puja, Christmas, Buddha Purnima, Pohela Boishakh & Performance Bonus Batches
- Religion-Aware Filtering, Tenure Pro-Ration & Separate BEFTN / bKash Bank Advice CSV
- Optional Automatic Sync into Monthly Payslips (`EID_BONUS_1`, `EID_BONUS_2`, `DURGA_BONUS`, `BOISHAKHI`)
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
        'security/dsl_bonus_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_bonus_data.xml',
        'views/dsl_bonus_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

