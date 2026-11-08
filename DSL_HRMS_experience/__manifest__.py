# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS - Prior Experience & Skills Matrix',
    'version': '18.0.1.0.0',
    'summary': 'Previous Employment History, Reference Checks & Enterprise Competency / Skills Matrix',
    'description': """
        Plug-and-Play Work Experience & Skills Matrix for DSL HRMS:
        - Prior employment history with duration calculation, reference verification & experience certificate upload
        - Enterprise Skills & Competency Matrix with 5-tier proficiency progress bars
        - Pre-seeded Bangladesh IT, RMG/Garments, HR/Finance, Language & Leadership competencies
        - Full Multi-Company & Multi-Branch record isolation
    """,
    'category': 'Human Resources/Employees',
    'author': 'DSL Enterprise HRMS',
    'license': 'LGPL-3',
    'depends': ['DSL_HRMS_core', 'DSL_HRMS_employee', 'hr', 'hr_skills', 'mail'],
    'data': [
        'security/dsl_experience_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_skills_data.xml',
        'views/dsl_experience_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

