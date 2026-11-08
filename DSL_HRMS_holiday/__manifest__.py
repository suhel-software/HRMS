# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS - Govt Gazetted Holiday & Weekend Calendar (BD)',
    'version': '18.0.1.0.0',
    'summary': 'Bangladesh Govt Gazetted Holidays, Moon-Sighting Festivals, Corporate vs Factory Weekend Rules & Leave Integration',
    'description': """
        Enterprise Holiday & Weekend Calendar Management for DSL HRMS (Plug-and-Play):
        - Group, Company & Branch/Plant Weekend Calendars (e.g. Corporate Fri+Sat vs Factory Fri-only per BD Labour Act Sec 103)
        - Pre-seeded Bangladesh National, Cultural & Moon-Sighting Festival Holidays with Bengali titles
        - Seamless Leave Engine hook: automatically excludes Branch/Company weekends & Govt Holidays from net leave days
        - 1-Click Sync to Daily Attendance Register (`status = holiday`) when `DSL_HRMS_attendance` is installed
        - 100% Full-Width Forms with Mandatory Bottom Chatter & Multi-Company / Multi-Branch Isolation
    """,
    'category': 'Human Resources/Time Off',
    'author': 'DSL Enterprise HRMS',
    'license': 'LGPL-3',
    'depends': ['DSL_HRMS_core', 'DSL_HRMS_branch', 'DSL_HRMS_leave', 'hr', 'resource', 'calendar', 'mail'],
    'data': [
        'security/dsl_holiday_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_holiday_data.xml',
        'views/dsl_holiday_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

