# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS: Biometric Device Bridge (ZKTeco / Face / RFID)',
    'summary': 'ZKTeco TCP/ADMS Biometric Machine Bridge, Raw Punch Queue & Auto Daily Consolidation',
    'description': """
DSL Enterprise HRMS - Biometric Machine Connection Bridge (Phase 4)
===================================================================
* Native Python TCP/Socket & ZKTeco ADMS Push (`/dsl/biometric/iclock/cdata`) bridge — zero 3rd-party packages
* Multi-Company & Multi-Branch Biometric Terminal Registry (`dsl.biometric.device`)
* Employee Biometric Enroll ID & RFID Proximity Card mapping (`biometric_id_no`, `rfid_card_no`)
* Immutable Raw Machine Punch Log (`dsl.biometric.punch.log`) with automatic First-In / Last-Out consolidation
* Scheduled 15-Minute Auto-Sync Cron + Full-Width Executive Forms with Bottom Chatter
    """,
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'author': 'DSL Enterprise HRMS',
    'website': 'https://dsl-hrms.local',
    'license': 'LGPL-3',
    'depends': [
        'DSL_HRMS_core',
        'DSL_HRMS_attendance',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/dsl_biometric_security.xml',
        'data/dsl_biometric_cron.xml',
        'views/dsl_biometric_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

