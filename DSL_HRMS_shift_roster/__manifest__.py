# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS: Shift Master & Rotational Roster Calendar',
    'summary': 'Morning, Evening, Night & General Shift Scheduling, Bulk Roster Batch & Cross-Midnight Attendance',
    'description': """
DSL Enterprise HRMS - Shift & Roster Management (Phase 4)
=========================================================
* Shift Master (`dsl.hr.shift`) supporting General, Morning (A), Evening (B), Cross-Midnight Night (C) & Night Allowance
* Interactive Monthly Shift Roster Calendar (`dsl.shift.roster`) with Multi-Company & Multi-Branch isolation
* Bulk Department / Branch Roster Batch Generator (`dsl.shift.roster.batch`) with Friday/Custom Off-Day automation
* Automatic schedule injection into `dsl.attendance.log` for exact shift-wise Late, Early & Overtime calculation
* Full-Width Executive Forms with Mandatory Bottom Chatter
    """,
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'author': 'DSL Enterprise HRMS',
    'website': 'https://dsl-hrms.local',
    'license': 'LGPL-3',
    'depends': [
        'DSL_HRMS_core',
        'DSL_HRMS_attendance',
        'hr',
        'resource',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/dsl_shift_security.xml',
        'data/dsl_shift_data.xml',
        'views/dsl_shift_roster_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

