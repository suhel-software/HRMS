# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS: Multi-Company Configurable Assessment Engine & Performance Management',
    'summary': '63-Model Unified Assessment Engine: Mother/Sub-Company Policy Override, Concurrent Cycles, Standard/Advanced/360°/Probation, KPI/KRA/OKR/Competency, Calibration, Appeal & PIP',
    'version': '18.0.2.0.0',
    'category': 'Human Resources/Appraisals',
    'author': 'Daffodil Software Limited (DSL)',
    'website': 'https://daffodilsoft.com',
    'license': 'LGPL-3',
    'depends': [
        'DSL_HRMS_core',
        'DSL_HRMS_branch',
        'DSL_HRMS_organization',
        'DSL_HRMS_employee',
        'hr',
        'hr_gamification',
        'survey',
        'mail',
    ],
    'data': [
        'security/dsl_appraisal_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_appraisal_data.xml',
        'views/dsl_appraisal_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
