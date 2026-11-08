# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS Employee Loan & Salary Advance',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Employee Loans, Salary Advances, Automated Monthly EMI Schedule & Payslip Deduction',
    'description': """
DSL HRMS Employee Loan & Salary Advance (Bangladesh)
====================================================
- Personal Loan, Salary Advance, PF Loan, Festival & Medical Advance Policies
- Automated Monthly EMI Amortization Schedule with Eid/Emergency Month Skip Support
- Automatic Monthly Payslip Deduction (`LOAN` / `ADVANCE`) & Paid Settlement Sync
- Strict Multi-Company & Multi-Branch Isolation
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
        'security/dsl_loan_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_loan_data.xml',
        'views/dsl_loan_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

