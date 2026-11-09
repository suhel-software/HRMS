{
    'name': 'DSL HRMS - Enterprise Budget & Cost Control Suite',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'sequence': 12,
    'summary': 'Complete Financial Budgets, Budgetary Positions, Practical vs Theoretical Analysis, Re-Budgeting, Cost Center & Bill/Advance Approval Suite integrated with DSL_HRMS_accounting',
    'description': """
DSL Enterprise Budget & Cost Control Suite for Odoo 18
======================================================
A unified, enterprise-grade Budget Management module built on top of `DSL_HRMS_accounting` (`at_accounting`), combining:
1. **Financial Budgets (`crossovered.budget` & `crossovered.budget.lines`)**:
   - Multi-step workflow (`Draft -> Confirmed -> Approved -> Done / Cancelled`)
   - Planned Amount, Revised/Supplementary Budget (`revised_amount`), Effective Budget, Practical Amount (auto-computed from posted GL & Analytic entries), Theoretical Amount, Variance, and Achievement (%)
   - Direct drill-down (`Entries...`) to General Ledger (`account.move.line`) & Analytic Items (`account.analytic.line`)
   - Automatic synchronization with `DSL_HRMS_accounting` (`account.report.budget`) for P&L and Balance Sheet Budget comparison
2. **Budgetary Positions (`account.budget.post`)**:
   - Group multiple Chart of Accounts heads into Income/Expense Budgetary Positions
3. **Budgets Analysis (List, Pivot & Graph)**:
   - Multi-dimensional budget vs. actual performance analysis
4. **Cost Center, Project Job Budget, Work Order, Advance Request & Bill Adjustment Approval**:
   - User-wise Approval Authority Limits (`amount.approval`)
   - Cost Centers (`job.center`) & Project/Department Jobs (`job.create`)
   - Itemized Budget Summary & Re-Budgeting (`job.summary`)
   - Work Orders (`work.order`), Cost Advance Requests (`cost.advance`), Approved Advance Summary (`approve.advance.summary`), and Bill Adjustments (`bill.adjustment`) with 1-click Vendor Bill creation
    """,
    'author': 'DSL Enterprise HRMS',
    'depends': [
        'base',
        'mail',
        'product',
        'account',
        'analytic',
        'hr',
        'DSL_HRMS_core',
        'DSL_HRMS_accounting',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/budget_sequence.xml',
        'views/account_budget_views.xml',
        'views/account_analytic_account_views.xml',
        'views/bill_and_budget_views.xml',
        'data/budget_default_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
