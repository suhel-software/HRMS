# DSL Bank Reconciliation — Complete User Manual & Documentation
**Enterprise Edition • Odoo 18 Ready**  
*Author: Imran Hoque | Daffodil Computers PLC*

---

## Table of Contents
1. [Overview & Core Value Proposition](#1-overview--core-value-proposition)
2. [How to Open the Reconciliation Console](#2-how-to-open-the-reconciliation-console)
3. [Bank & MFS Account Workspace](#3-bank--mfs-account-workspace)
4. [Date Period Controls & Quick Presets (New!)](#4-date-period-controls--quick-presets)
5. [Tally BRS Formula & Real-Time Statement Verification](#5-tally-brs-formula--real-time-statement-verification)
6. [Visual Flow Segregation (IN vs OUT)](#6-visual-flow-segregation-in-vs-out)
7. [Process 1 Automated 1-Click Statement Clearing](#7-process-1-automated-1-click-statement-clearing)
8. [MFS & Bank Charge Adjustment (Combined Entry)](#8-mfs--bank-charge-adjustment-combined-entry)
9. [Smart Filter Memory (Session Persistence)](#9-smart-filter-memory-session-persistence)
10. [Interim Account Safety & Ghost Entry Exclusion](#10-interim-account-safety--ghost-entry-exclusion)
11. [Troubleshooting & Frequently Asked Questions (FAQ)](#11-troubleshooting--frequently-asked-questions-faq)

---

## 1. Overview & Core Value Proposition

**DSL Bank Reconciliation** is a high-performance, single-screen bank reconciliation and clearing workspace developed for Odoo 18. It replaces cumbersome multi-step statement imports with a fast, intuitive, and mathematically rigorous workflow modeled on universal Tally BRS standards and Odoo Process 1 automated clearing.

### Key Highlights:
- **Zero Horizontal Scroll Guarantee:** Proportionally fitted across all desktop and laptop resolutions (1366×768 to 4K).
- **Process 1 Automated Clearing:** Moves in-transit vouchers from Interim Accounts (`Outstanding Receipts`/`Outstanding Payments`) to the Real Bank Account on the exact date they clear the bank statement.
- **Combined 2-in-1 MFS & Fee Adjustments:** Handles merchant deductions (bKash, Nagad, POS card fees, bank charges) in a single balanced journal entry with zero orphan lines.
- **Smart Session Persistence:** Never lose your active journal, date filters, or tab state when navigating into a transaction and clicking back.

---

## 2. How to Open the Reconciliation Console

To access the console in Odoo:
1. Open the main **Accounting** application.
2. In the top navigation bar, click on **Bank Reconciliation**.
3. Select **DSL Bank Reconciliation**.

Shortcut menu:  
`Accounting ➔ Bank Reconciliation ➔ DSL Bank Reconciliation`

---

## 3. Bank & MFS Account Workspace

At the top of the console, all active corporate bank accounts, mobile financial wallets (bKash, Nagad), card terminals, and cash desks are displayed as interactive cards.

- **Active Card Highlight:** Clicking any account card instantly switches the console to that account and loads its ledger balance and pending transactions.
- **Book Balance:** Displays the live General Ledger (GL) balance of the real bank account.
- **Pending Badges:** Visual counter showing how many cheques or deposits remain uncleared for each account.
- **⚙ Manage Journals:** Customize which bank or cash journals appear on the console without changing chart of accounts configuration.

---

## 4. Date Period Controls & Quick Presets

The dedicated **Date Period Bar** allows accountants to filter transactions by date range with instant visual confirmation:

```
[ Today ]  [ This Month ]  [ Last Month ]  [ This Quarter ]  [ This Year ]  [ All Time ]  |  [ From Date ] to [ To Date ]  [ ⚡ Filter ]  [ ↺ Reset ]
```

### Quick Preset Buttons:
- **`Today` (New!):** Instantly sets both `From Date` and `To Date` to today's date, loading all collections and disbursements received or paid today.
- **`This Month`:** Automatically selects from the 1st day of the current month to the last day of the current month.
- **`Last Month`:** Sets the range to the entirety of the previous calendar month.
- **`This Quarter`:** Sets the range to the current financial quarter (Q1, Q2, Q3, or Q4).
- **`This Year`:** Selects January 1st through December 31st of the current year.
- **`All Time`:** Clears date boundaries and displays all historical and current transactions.

### Custom Date Range & Controls:
- **Custom Pickers:** Enter any custom date range using standard browser date pickers.
- **`⚡ Filter` Button:** Re-computes period statistics and queries transactions matching the date boundary.
- **`↺ Reset` Button:** Instantly clears any active date range, resets presets to `All Time`, and reloads all records in a single click.

### Period Statistics Badges:
Next to the date controls, real-time counters summarize the selected period:
- **Total Vouchers:** Total transaction count falling within the date range.
- **Cleared:** Vouchers that cleared the bank during this date range.
- **Pending:** Vouchers created during this date range that remain unpresented or uncleared.

---

## 5. Tally BRS Formula & Real-Time Statement Verification

The KPI bar calculates and verifies the classic Bank Reconciliation Statement (BRS) formula:

$$\text{Balance as per Books} - \text{Uncleared Deposits} + \text{Uncleared Payments} = \text{Calculated Bank Balance}$$

### KPI Stat Cards:
1. **Balance as per Company Books:** Current ledger book balance of the real bank account as of the selected period.
2. **Amounts not Reflected in Bank:** Total monetary sum of pending cheques and deposits yet to clear. Displays:
   - When date filter is active: `X pending in period (Y total)`
   - When all time: `Y cheques / deposits pending`
3. **Balance as per Bank (Calculated):** The exact balance your bank statement should show if all uncleared items are excluded.
4. **Actual Statement Closing Balance:** Input field to type your physical bank statement closing balance.
   - **Green Badge:** `100% Balanced with Bank!` appears when the difference is zero.
   - **Amber Badge:** Shows `Difference: ৳ ...` if there is a discrepancy to investigate.

---

## 6. Visual Flow Segregation (IN vs OUT)

Every transaction row features clear visual cues ensuring complete clarity on cash direction:

### Filter Toolbar:
- **Clearance Tabs:**
  - **`Uncleared Only (Count)`:** Focus exclusively on pending vouchers awaiting bank clearance. Shows exact period count (e.g., `0` when no pending items exist in the selected period).
  - **`Cleared Only (Count)`:** Review historical cleared transactions.
  - **`All Transactions (Count)`:** Combined chronological view.
- **Flow Filter Toggle:**
  - **`All Flows`:** Shows all transactions.
  - **`↓ IN`:** Filters only collections, receipts, and deposits entering the bank.
  - **`↑ OUT`:** Filters only supplier disbursements, transfers, and withdrawals exiting the bank.

### Row-Level Direction Indicators:
- **`Receipt / ↓ IN` Badge:** Accompanied by emerald green text and `+ ৳ ...` indicating cash inflow.
- **`Payment / ↑ OUT` Badge:** Accompanied by crimson red text and `- ৳ ...` indicating cash outflow.
- **Left Border Accent:** Green left border for inflows, red left border for outflows.

---

## 7. Process 1 Automated 1-Click Statement Clearing

When a cheque or bank collection reflects on your official bank statement:

### To Clear a Single Voucher:
1. Locate the pending voucher in the table.
2. Under the **Bank Clearing Date** column:
   - Click the blue **`Today`** button to clear on today's date, OR
   - Pick the exact date from the calendar input.
3. **Automated Result:**
   - The voucher is instantly marked **Cleared** with a green checkmark.
   - An automated **Clearing Journal Entry (`account.move`)** is generated and posted on the clearing date.
   - Funds are transferred from `Outstanding Receipts` or `Outstanding Payments` to your Real Bank GL Account (`account_id`).
   - The interim move lines are reconciled together, keeping the interim ledger clean.

### To Rollback / Undo a Clearance:
- If a voucher was cleared on the wrong date or in error, click the red **`↺ Clear`** button on that row.
- DCL Pro automatically un-reconciles the interim lines, safely cancels and deletes the clearing journal entry, and restores the voucher to pending with zero orphan records.

---

## 8. MFS & Bank Charge Adjustment (Combined Entry)

When collecting funds through payment gateways or mobile wallets (bKash, Nagad, POS Terminals), merchant commission is deducted at source:

*Example:* Customer pays **৳ 25,300**, bKash deducts **৳ 300** charge, and your bank receives net **৳ 25,000**.

### How to Record:
1. Click the **`⚡ Adjust`** button on the voucher row (or the top **`+ Bank Charge / Adjustment`** button).
2. The modal pre-fills the voucher particulars, gross amount, and suggested charge type.
3. Enter the fee amount (e.g. `300`).
4. Select the Expense Account (`Bank Charges & Commission`).
5. Confirm that **"Clear Voucher & Record Fee in 1 Single Combined Journal Entry"** is checked.
6. Click **Confirm & Post Combined Entry**.

### Accounting Impact of the Combined Entry:
| Account | Type | Debit | Credit | Description |
| :--- | :---: | :---: | :---: | :--- |
| **Real Bank Account** (e.g. City Bank) | Asset (Bank) | **৳ 25,000.00** | ৳ 0.00 | Net amount deposited into bank |
| **Bank Charges & Commission** | Expense | **৳ 300.00** | ৳ 0.00 | Gateway / MFS fee recorded |
| **Outstanding Receipts** | Interim | ৳ 0.00 | **৳ 25,300.00** | Customer payment fully cleared |
| **Total** | | **৳ 25,300.00** | **৳ 25,300.00** | **100% Balanced** |

---

## 9. Smart Filter Memory (Session Persistence)

Accountants frequently need to open a voucher or invoice form view to check particulars or print reports, then return to the reconciliation console.

### How It Works:
- DCL Pro automatically saves your complete console state to browser `sessionStorage`:
  1. Active Bank / MFS Account Card
  2. Selected Date Preset (`Today`, `This Month`, etc.) or Custom Date Range
  3. Active Clearance Tab (`Uncleared Only`, `Cleared Only`, `All Transactions`)
  4. Flow Filter (`IN`, `OUT`, `All Flows`)
  5. Search queries
- When you click on any voucher link (e.g., `PBNK4/2026/00031`) to inspect it and then click the breadcrumbs or browser back button, **all your filters remain 100% active and preserved**. You never have to re-enter your dates or re-select your bank.

---

## 10. Interim Account Safety & Ghost Entry Exclusion

Under Odoo's Process 1 architecture, clearing entries use the interim account to offset the original payment.

### Protection Logic:
- Clearing and adjustment journal entries are stamped with `is_bank_clearing_line = True`.
- DCL Pro's query engine strictly excludes `is_bank_clearing_line = True` across both bank accounts and interim accounts.
- This prevents the credit clearing line (e.g., Credit 25,300 in `Outstanding Receipts`) from erroneously appearing as a phantom pending withdrawal (`OUT`).
- The pending list only contains genuine original business transactions waiting for bank realization.

---

## 11. Troubleshooting & Frequently Asked Questions (FAQ)

### Q1: Why does my Real Bank GL Account balance not change when I register payment on an invoice?
**Answer:** This is standard Process 1 behavior. When an invoice payment is registered, funds sit in `Outstanding Receipts` (in-transit). Your Real Bank Account balance only updates when the payment actually clears your bank statement and is cleared in DCL Pro.

### Q2: Why did `Uncleared Only` previously show 42 when my date filter had 0 pending records?
**Answer:** This was due to a JavaScript falsy fallback (`0 || 42`). It has been resolved. The button now displays the exact count for the selected date range (`Uncleared Only (0)`).

### Q3: How do I view all historical transactions after using a date filter?
**Answer:** Click the **`↺ Reset`** button next to the Date Filter input, or click the **`All Time`** preset pill.

### Q4: Can I adjust bank interest or unexpected direct bank debits?
**Answer:** Yes. Click the top **`+ Bank Charge / Adjustment`** button, select the adjustment type (Direct Debit, Bank Interest, Excise Duty, Rounding), and submit. The entry will post directly to your selected bank journal.
