# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS: Mobile & Browser Geo-Fenced GPS Attendance',
    'summary': 'Haversine Branch Geofencing, Field Client Visit GPS Check-In & Live Browser Geo-Punch',
    'description': """
DSL Enterprise HRMS - Geo-Fenced GPS Attendance (Phase 4)
=========================================================
* Exact Haversine distance calculation against `dsl.branch` GPS coordinates & Geofence Radius
* Automatic verification inside branch geofence + Supervisor approval workflow for Field / Client Visits
* One-click Browser Geolocation Check-In / Check-Out (`navigator.geolocation`)
* Selfie / Site Photo proof & clickable Map verification link
* Full-Width Executive Forms with Mandatory Bottom Chatter
    """,
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'author': 'DSL Enterprise HRMS',
    'website': 'https://dsl-hrms.local',
    'license': 'LGPL-3',
    'depends': [
        'DSL_HRMS_core',
        'DSL_HRMS_branch',
        'DSL_HRMS_attendance',
        'web',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/dsl_gps_security.xml',
        'data/dsl_gps_sequence.xml',
        'views/dsl_gps_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'DSL_HRMS_gps_attendance/static/src/js/gps_punch_action.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}

