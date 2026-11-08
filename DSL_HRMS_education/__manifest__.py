# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS - Academic Qualifications & Certifications',
    'version': '18.0.1.0.0',
    'summary': 'Employee Academic Degrees (SSC/HSC/BSc/MBA), CGPA/Division, Certificates & Professional Training',
    'description': """
        Plug-and-Play Academic & Certification Registry for DSL HRMS:
        - Bangladesh & International degree levels (SSC/Dakhil, HSC/Alim, Diploma, Bachelor, Masters, PhD, CA/CMA/PGDHRM)
        - Board / University, Major / Group, CGPA (4.00 / 5.00) or Division, Passing Year & Certificate Upload
        - Professional Certifications & License tracking with expiry status
        - Full Multi-Company & Multi-Branch record isolation
    """,
    'category': 'Human Resources/Employees',
    'author': 'DSL Enterprise HRMS',
    'license': 'LGPL-3',
    'depends': ['DSL_HRMS_core', 'DSL_HRMS_employee', 'hr', 'hr_skills', 'hr_recruitment', 'mail'],
    'data': [
        'security/dsl_education_security.xml',
        'security/ir.model.access.csv',
        'views/dsl_education_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

