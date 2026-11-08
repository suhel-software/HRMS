# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS: Recruitment, ATS Pipeline & Offer Letter',
    'summary': 'Manpower Requisition, Applicant Tracking (ATS), Interview Scoring, 1-Click Hire & Offer Letter',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Recruitment',
    'author': 'Daffodil Software Limited (DSL)',
    'website': 'https://daffodilsoft.com',
    'license': 'LGPL-3',
    'depends': [
        'DSL_HRMS_core',
        'DSL_HRMS_organization',
        'DSL_HRMS_employee',
        'hr',
        'hr_recruitment',
        'hr_skills',
        'mail',
    ],
    'data': [
        'security/dsl_recruitment_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_recruitment_data.xml',
        'views/dsl_recruitment_views.xml',
        'reports/dsl_recruitment_reports.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

