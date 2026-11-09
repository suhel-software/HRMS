# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS - Bank Reconciliation (BRS)',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'sequence': 3,
    'summary': 'Bank Reconciliation Statement console: bank clearing dates, 1-click clearance, combined fee '
               'adjustment journals, bKash/MFS next-day sweeps, IN/OUT flow filters and bill-by-bill matching',
    'description': """
DSL HRMS - Bank Reconciliation (BRS)
====================================
Built on top of DSL_HRMS_accounting (based on DCL Bank Reconciliation Pro).

* Enter the bank clearing date on each book entry to clear it with one click (single or bulk)
* Uncleared / Cleared / All filters, date range and search, IN (deposit) / OUT (withdrawal) flow filters
* Live period summary: opening, inflow, outflow, net movement, closing, balance as per bank vs books
* Single combined adjustment journal (net bank, gateway / bank fee, gross clearance) with optional
  auto-reconcile against the source voucher
* bKash / MFS next-day settlement to bank (clearing journal per transaction)
* Bill-by-bill customer / vendor matching (Agst Ref) with 1-click FIFO auto reconcile
* Per-journal "Show in Bank Reconciliation" toggle, bank clearance date column on journal items
""",
    'author': 'DSL Enterprise HRMS',
    'license': 'LGPL-3',
    'depends': ['DSL_HRMS_accounting'],
    'data': [
        'security/ir.model.access.csv',
        'views/bank_reconciliation_views.xml',
        'views/bank_instrument_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'DSL_HRMS_bank_reconciliation/static/src/reconciliation_app/bank_reconciliation.js',
            'DSL_HRMS_bank_reconciliation/static/src/reconciliation_app/bank_reconciliation.xml',
            'DSL_HRMS_bank_reconciliation/static/src/reconciliation_app/bank_reconciliation.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
