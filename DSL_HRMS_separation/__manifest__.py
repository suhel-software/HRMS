# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS: Resignation, Exit Clearance & Full-and-Final Settlement',
    'summary': 'BD Labour Act Notice Period, 5-Dept Exit Clearance, Automated F&F Settlement & Experience Certificate',
    'description': """
DSL Enterprise HRMS — Phase 8: Separation & Full-and-Final (F&F) Settlement
===========================================================================
* Resignation, Retirement, Retrenchment & Termination under Bangladesh Labour Act 2006 (Sec 20, 26, 27)
* Multi-Department Exit Clearance Checklist (Line Manager, IT Security, Admin/Assets, Finance, HR)
* 1-Click Automated Full & Final Settlement pulling Unpaid Salary, Earned Leave Encashment, Vested PF, Statutory Gratuity, Notice Shortfall & Outstanding Loan Recovery
* Printable QWeb Experience & Release Certificate + Full & Final Statement
    """,
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Lifecycle',
    'author': 'Daffodil Software Limited (DSL)',
    'website': 'https://daffodilsoft.com',
    'license': 'LGPL-3',
    'depends': [
        'DSL_HRMS_core',
        'DSL_HRMS_employee',
        'DSL_HRMS_salary_structure',
        'DSL_HRMS_leave',
        'DSL_HRMS_loan',
        'DSL_HRMS_provident_fund',
        'DSL_HRMS_gratuity',
        'hr',
        'hr_contract',
        'mail',
    ],
    'data': [
        'security/dsl_separation_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_separation_data.xml',
        'views/dsl_separation_views.xml',
        'reports/dsl_separation_reports.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

