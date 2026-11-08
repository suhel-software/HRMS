# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS - Leave Policy, Balance & Statutory Leave Engine',
    'version': '18.0.1.0.0',
    'summary': 'Bangladesh Labour Act 2006 Leave Types (CL, SL, EL, Maternity 112d), Yearly Quota, Carry-Forward & Leave Applications',
    'description': """
        Enterprise Leave Management Engine for DSL HRMS (Plug-and-Play):
        - Bangladesh Labour Act 2006 Statutory Leave Policies (Sec 115 Casual 10d, Sec 116 Sick 14d, Sec 117 Earned 18d w/ Carry-Forward, Sec 46 Maternity 112d, Paternity, Comp-Off, LWP)
        - Annual Leave Quota & Carry-Forward Ledger (`dsl.leave.allocation`) + 1-Click Bulk Yearly Allocation Generator (`dsl.leave.allocation.batch`)
        - Employee Leave Application (`dsl.leave.request`) with Half-Day support, Reliever Handover, Medical Certificate rules & Sandwich Policy
        - Automatic Daily Attendance Register synchronization (`status = on_leave / half_day`) when `DSL_HRMS_attendance` is installed
        - Dedicated `Leave` Pill Tab & Quick Action on Executive Employee Profile
        - 100% Full-Width Forms with Mandatory Bottom Chatter & Multi-Company / Multi-Branch Isolation
    """,
    'category': 'Human Resources/Time Off',
    'author': 'DSL Enterprise HRMS',
    'license': 'LGPL-3',
    'depends': ['DSL_HRMS_core', 'DSL_HRMS_branch', 'DSL_HRMS_employee', 'hr', 'hr_holidays', 'resource', 'mail'],
    'data': [
        'security/dsl_leave_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_leave_data.xml',
        'views/dsl_leave_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

