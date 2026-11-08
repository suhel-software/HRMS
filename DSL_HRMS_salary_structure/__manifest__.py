# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS - Bangladesh Salary Structure & Compensation Package',
    'version': '18.0.1.0.0',
    'summary': 'BD Salary Heads (Basic, House Rent, Medical, Conveyance, Attendance Bonus), Corporate & RMG Templates & Employee Packages',
    'description': """
        Enterprise Salary Structure & Compensation Engine for DSL HRMS (Plug-and-Play):
        - Pre-seeded Bangladesh Salary Heads (Basic, House Rent, Medical, Conveyance, Food, Attendance Bonus, 2x OT, Night Shift, NBR TDS, LWP, Revenue Stamp ৳10)
        - Corporate Standard (50/25/10/10/5) & Garments/Industrial Minimum Wage Board Salary Templates
        - Employee Active Compensation Contract (`dsl.employee.compensation`) with increment history & automatic Overtime Basic sync
        - Dedicated `Payroll` Pill Tab on Executive Employee Profile
        - 100% Full-Width Forms with Mandatory Bottom Chatter & Multi-Company / Multi-Branch Isolation
    """,
    'category': 'Human Resources/Payroll',
    'author': 'DSL Enterprise HRMS',
    'license': 'LGPL-3',
    'depends': ['DSL_HRMS_core', 'DSL_HRMS_branch', 'DSL_HRMS_employee', 'hr', 'hr_contract', 'mail'],
    'data': [
        'security/dsl_salary_structure_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_salary_structure_data.xml',
        'views/dsl_salary_structure_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

