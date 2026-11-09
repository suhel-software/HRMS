# -*- coding: utf-8 -*-
{
    'name': 'DSL HRMS: Contra Voucher (Bank & Cash Transfer)',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Enterprise Contra Voucher for Cash Deposit, Cash Withdrawal, Bank-to-Bank & Petty Cash Transfers with Cash Denomination & BRS Sync',
    'description': """
DSL HRMS Contra Voucher (Bank & Cash Fund Transfer)
===================================================
Complete Bangladesh-compliant Contra Voucher & Internal Fund Transfer management:
- **4 Transfer Modes:**
  1. Cash Deposit to Bank (নগদ টাকা ব্যাংকে জমা)
  2. Cash Withdrawal from Bank (ব্যাংক থেকে নগদ উত্তোলন)
  3. Bank to Bank Transfer (এক ব্যাংক থেকে অন্য ব্যাংকে ট্রান্সফার - Cheque / BEFTN / RTGS / NPSB)
  4. Cash to Petty Cash Transfer (মূল ক্যাশ থেকে পেটি ক্যাশে ট্রান্সফার)
- **Live GL Balance Preview:** Shows current & projected balance of both Source and Destination Bank/Cash accounts.
- **Instrument & Bearer Tracking:** Cheque No, Cheque Date, Deposit Slip No, UTR/TrxID, Routing No, and Bearer/Depositor Employee details.
- **Cash Denomination Breakdown:** Built-in Bangladesh Taka Note Counter (৳1000, ৳500, ৳200, ৳100, ৳50, ৳20, ৳10, etc.).
- **Bank Transfer Charges:** Optional automatic debit line for RTGS / Bank Transfer / Excise charges.
- **Seamless BRS & Cheque Register Sync:** Automatically creates posted Journal Entries (`account.move`) with `dsl_voucher_type = 'contra'` that appear in Bank Reconciliation (BRS) and Cheque Register.
    """,
    'author': 'DSL Enterprise HRMS',
    'depends': [
        'DSL_HRMS_accounting',
        'DSL_HRMS_bank_reconciliation',
        'hr',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/contra_sequence_data.xml',
        'views/contra_voucher_views.xml',
        'reports/contra_voucher_report.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

