# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS - Family, Dependents & Medical Coverage',
    'version': '18.0.1.0.0',
    'summary': 'Employee Family Members, Tax/Welfare Dependents & Group Medical Insurance Coverage',
    'description': """
        Plug-and-Play Family & Dependents Registry for DSL HRMS:
        - Spouse, Children, Parents & Legal Dependents with Bengali & English names
        - Age auto-calculation, Blood Group, Birth Reg / NID & Emergency Contact flags
        - Group Health / Hospitalization Insurance coverage & Policy Card tracking
        - Full Multi-Company & Multi-Branch record isolation
    """,
    'category': 'Human Resources/Employees',
    'author': 'DSL Enterprise HRMS',
    'license': 'LGPL-3',
    'depends': ['DSL_HRMS_core', 'DSL_HRMS_employee', 'hr', 'mail'],
    'data': [
        'security/dsl_family_security.xml',
        'security/ir.model.access.csv',
        'views/dsl_family_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

