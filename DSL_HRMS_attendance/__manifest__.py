# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS: Daily Attendance, Late Policy & Regularization',
    'summary': 'Daily Attendance Register, BD Grace Rules, Late/Early Tracking & Missed Punch Regularization',
    'description': """
DSL Enterprise HRMS - Core Attendance Engine (Phase 4)
======================================================
* Consolidated Daily Attendance Register (`dsl.attendance.log`) with Company & Branch isolation
* Configurable Grace Minutes, Half-Day Thresholds & Late-to-Leave Policies (`dsl.attendance.policy`)
* Missed Punch & Outdoor Duty Regularization Workflow (`dsl.attendance.regularization`)
* Pluggable schedule resolver for Shift Roster, Biometric Sync, Mobile GPS & Overtime (2x Basic)
* Full-Width Executive Forms with Mandatory Bottom Chatter
    """,
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'author': 'DSL Enterprise HRMS',
    'website': 'https://dsl-hrms.local',
    'license': 'LGPL-3',
    'depends': [
        'DSL_HRMS_core',
        'DSL_HRMS_employee',
        'hr',
        'hr_attendance',
        'resource',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/dsl_attendance_security.xml',
        'data/dsl_attendance_data.xml',
        'views/dsl_attendance_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

