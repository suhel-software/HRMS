# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS Gratuity & Service Benefit (BD)',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Bangladesh Labour Act Sec 2(10) Gratuity (30d / 45d Basic) & NBR Tax Exemption Engine',
    'description': """
DSL HRMS Gratuity & Service Benefit (Bangladesh)
================================================
- Bangladesh Labour Act 2006 Sec 2(10): 1.0x Basic (<10 yrs) & 1.5x Basic (>=10 yrs) per year
- 6+ Months Fractional Year Rounding Rule & Minimum Qualifying Service Check
- NBR Income Tax Act 2023 Gratuity Exemption Cap (৳2.5 Crore)
- Live Valuation & Settlement Workflow
    """,
    'author': 'DSL Enterprise',
    'license': 'LGPL-3',
    'depends': [
        'DSL_HRMS_core',
        'DSL_HRMS_employee',
        'DSL_HRMS_salary_structure',
    ],
    'data': [
        'security/dsl_gratuity_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_gratuity_data.xml',
        'views/dsl_gratuity_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

