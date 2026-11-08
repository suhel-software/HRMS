# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS: Bangladesh 2x Basic Overtime Engine',
    'summary': 'BD Labour Act Sec 108 Double Basic Rate ((Basic / 208) x 2.0) Overtime & Statutory Compliance',
    'description': """
DSL Enterprise HRMS - Bangladesh Statutory Overtime Engine (Phase 4)
====================================================================
* Strictly implements Bangladesh Labour Act 2006 (Sec 108) & Rules 2015: `(Monthly Basic / 208) * 2.0`
* Tracks Section 100 & 102 statutory daily (2h) / weekly (12h) compliance flags for DIFE / Accord / Buyer audits
* Auto-pulls Extra Worked Hours from `dsl.attendance.log` in 1 click
* Payroll-ready (`payslip_settled` & `total_ot_amount`) for Phase 6 `DSL_HRMS_payroll_bd`
* Full-Width Executive Forms with Mandatory Bottom Chatter
    """,
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'author': 'DSL Enterprise HRMS',
    'website': 'https://dsl-hrms.local',
    'license': 'LGPL-3',
    'depends': [
        'DSL_HRMS_core',
        'DSL_HRMS_organization',
        'DSL_HRMS_attendance',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/dsl_overtime_security.xml',
        'data/dsl_overtime_data.xml',
        'views/dsl_overtime_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

