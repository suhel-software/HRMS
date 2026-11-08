# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS - Bangladesh Monthly Payroll, Payslip & Bank Advice Engine',
    'version': '18.0.1.0.0',
    'summary': 'Monthly Payroll Batch, Digital Payslips, Auto OT/LWP/Late/Stamp Sync, BEFTN & bKash/Nagad Advice (Excel CSV & PDF)',
    'description': """
        Enterprise Bangladesh Payroll & Disbursement Engine for DSL HRMS (Plug-and-Play):
        - Individual & Batch Monthly Payroll Processing (`dsl.payslip` & `dsl.payslip.run`)
        - Multi-Company & Multi-Branch Shared/Separate COA Ledger stamping (`accounting_company_id`)
        - Auto-integrates Attendance, Unpaid Leave (LWP), 3-Late=1-Day Rule, 2x Basic Overtime, Night Allowance & ৳10 Revenue Stamp
        - Plug-and-Play hook for `DSL_HRMS_tax_bd` (Automatic NBR Monthly TDS) & Phase 7 Benefits (Loan, PF, Bonus)
        - 1-Click Excel-Ready BEFTN & MFS (bKash/Nagad/Rocket) Bank Advice CSV Export + Printable Digital Payslip & Bank Forwarding Sheet
        - 100% Full-Width Forms with Mandatory Bottom Chatter & Multi-Company / Multi-Branch Isolation
    """,
    'category': 'Human Resources/Payroll',
    'author': 'DSL Enterprise HRMS',
    'license': 'LGPL-3',
    'depends': ['DSL_HRMS_core', 'DSL_HRMS_branch', 'DSL_HRMS_employee', 'DSL_HRMS_salary_structure', 'hr', 'hr_contract', 'account', 'mail'],
    'data': [
        'security/dsl_payroll_security.xml',
        'security/ir.model.access.csv',
        'data/dsl_payroll_data.xml',
        'views/dsl_payroll_views.xml',
        'reports/dsl_payroll_reports.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

