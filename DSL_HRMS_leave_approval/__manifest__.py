# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS - Multi-Level Leave Approval Chain Engine',
    'version': '18.0.1.0.0',
    'summary': 'Configurable Multi-Tier Approval Workflow (Line Manager -> Dept Head -> HR Manager) for Leave Applications',
    'description': """
        Enterprise Multi-Level Leave Approval Chain for DSL HRMS (Plug-and-Play):
        - Dynamic Approval Chains (`dsl.leave.approval.chain`) by Company, Branch, Leave Policy, and Duration Threshold
        - Multi-stage sequential routing: Level 1 (Line Manager) -> Level 2 (Department Head / Branch Head) -> Level 3 (HR Validation)
        - Smart Auto-Skip when Line Manager & Dept Head are identical or unassigned so requests never stall
        - Step-by-step approval ledger embedded on Leave Application + HR Executive Override
        - 100% Full-Width Forms with Mandatory Bottom Chatter & Multi-Company / Multi-Branch Isolation
    """,
    'category': 'Human Resources/Time Off',
    'author': 'DSL Enterprise HRMS',
    'license': 'LGPL-3',
    'depends': ['DSL_HRMS_core', 'DSL_HRMS_branch', 'DSL_HRMS_leave', 'hr', 'mail'],
    'data': [
        'security/dsl_leave_approval_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_leave_approval_data.xml',
        'views/dsl_leave_approval_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

