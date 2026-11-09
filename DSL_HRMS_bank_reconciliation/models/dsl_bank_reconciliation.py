# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class DslBankReconciliation(models.TransientModel):
    _name = 'dsl.bank.reconciliation'
    _description = 'DSL Bank Reconciliation'

    name = fields.Char(string='Reference', default='Bank Reconciliation Console')

    # -------------------------------------------------------------------------
    # 1. INITIAL SETUP & BANK JOURNALS (FOR BANK RECONCILIATION)
    # -------------------------------------------------------------------------
    @api.model
    def get_initial_data(self):
        """ Returns initial setup data for the frontend console """
        company = self.env.company

        # 1. Fetch Bank & Cash Journals that have show_in_bank_reconciliation enabled
        bank_journals = self.env['account.journal'].search([
            ('company_id', '=', company.id),
            ('type', 'in', ['bank', 'cash']),
            ('show_in_bank_reconciliation', '=', True)
        ], order='sequence asc, id asc')

        journals_data = []
        for j in bank_journals:
            acc = j.default_account_id
            if not acc:
                continue

            # Compute current book balance
            self.env.cr.execute("""
                SELECT COALESCE(SUM(debit - credit), 0.0)
                FROM account_move_line
                WHERE account_id = %s AND parent_state = 'posted'
            """, (acc.id,))
            res = self.env.cr.fetchone()
            book_balance = res[0] if res else 0.0

            # Count uncleared items (direct bank lines + interim lines)
            in_accs = j.inbound_payment_method_line_ids.mapped('payment_account_id').ids
            out_accs = j.outbound_payment_method_line_ids.mapped('payment_account_id').ids
            interim_acc_ids = [aid for aid in set(in_accs + out_accs) if aid and aid != acc.id]

            uncl_domain = [
                ('company_id', '=', company.id),
                ('parent_state', '=', 'posted'),
                ('bank_date', '=', False),
            ]
            if interim_acc_ids:
                uncl_domain += [
                    ('is_bank_clearing_line', '=', False),
                    '|',
                    ('account_id', '=', acc.id),
                    '&', ('account_id', 'in', interim_acc_ids), ('journal_id', '=', j.id),
                ]
            else:
                uncl_domain += [
                    ('account_id', '=', acc.id),
                    ('is_bank_clearing_line', '=', False),
                ]

            uncl_lines = self.env['account.move.line'].search(uncl_domain)
            uncleared_count = len(uncl_lines)
            uncleared_debit = sum(uncl_lines.mapped('debit'))
            uncleared_credit = sum(uncl_lines.mapped('credit'))

            journals_data.append({
                'id': j.id,
                'name': j.name,
                'type': j.type,
                'code': j.code,
                'account_id': acc.id,
                'account_code': acc.code,
                'account_name': acc.name,
                'currency_symbol': j.currency_id.symbol or company.currency_id.symbol or '$',
                'book_balance': round(book_balance, 2),
                'uncleared_count': uncleared_count,
                'uncleared_debit': round(uncleared_debit, 2),
                'uncleared_credit': round(uncleared_credit, 2),
                'show_in_bank_reconciliation': bool(getattr(j, 'show_in_bank_reconciliation', True)),
                'show_in_tally_brs': bool(getattr(j, 'show_in_bank_reconciliation', True)),
            })

        # All bank journals (for journal visibility manager modal)
        all_bank_journals = self.env['account.journal'].search([
            ('company_id', '=', company.id),
            ('type', 'in', ['bank', 'cash'])
        ], order='sequence asc, id asc')
        all_journals_data = [{
            'id': j.id,
            'name': j.name,
            'code': j.code,
            'type': j.type,
            'show_in_bank_reconciliation': bool(getattr(j, 'show_in_bank_reconciliation', True)),
            'show_in_tally_brs': bool(getattr(j, 'show_in_bank_reconciliation', True)),
        } for j in all_bank_journals]

        # 2. Fetch Reconcilable Accounts (for Party / Bill Settlement)
        domain = [('reconcile', '=', True)]
        if 'company_ids' in self.env['account.account']._fields:
            domain.append(('company_ids', 'in', [company.id]))
        elif 'company_id' in self.env['account.account']._fields:
            domain.append(('company_id', '=', company.id))

        accounts = self.env['account.account'].search_read(
            domain,
            ['id', 'code', 'name', 'account_type'],
            order='code asc'
        )

        # 3. Fetch Expense & Charge Accounts (for Quick Bank Charge / Adjustment)
        charge_domain = [
            ('account_type', 'in', ['expense', 'expense_depreciation', 'expense_direct_cost', 'income', 'income_other'])
        ]
        if 'company_ids' in self.env['account.account']._fields:
            charge_domain.append(('company_ids', 'in', [company.id]))
        elif 'company_id' in self.env['account.account']._fields:
            charge_domain.append(('company_id', '=', company.id))

        expense_accounts = self.env['account.account'].search_read(
            charge_domain,
            ['id', 'code', 'name', 'account_type'],
            order='code asc'
        )

        default_charge_account_id = False
        for acc in expense_accounts:
            name_lower = acc['name'].lower()
            if 'charge' in name_lower or 'commission' in name_lower:
                default_charge_account_id = acc['id']
                break

        return {
            'company_id': company.id,
            'company_name': company.name,
            'currency_symbol': company.currency_id.symbol or '$',
            'currency_position': company.currency_id.position or 'before',
            'bank_journals': journals_data,
            'all_bank_journals': all_journals_data,
            'accounts': accounts,
            'expense_accounts': expense_accounts,
            'default_charge_account_id': default_charge_account_id,
        }

    @api.model
    def action_create_quick_adjustment(self, journal_id, date, adj_type, amount, account_id, description, cheque_no=False, bank_date=False, partner_id=False, source_move_id=False, source_line_id=False, reconcile_source=True):
        """
        Creates a standard Odoo journal entry (account.move) for bank charges, interest, or difference adjustment.
        SINGLE COMBINED JOURNAL ENTRY ARCHITECTURE:
        - When adjusting for an uncleared voucher:
          Posts ONE SINGLE COMBINED journal entry containing:
          1) Real Bank Account (Net amount after fee deduction, with Bank Date set)
          2) Bank Charge / Commission / bKash Expense Account (Fee amount)
          3) Interim Outstanding Account (Gross voucher amount, clearing original voucher line)
          Reconciles the interim line atomically in 1 transaction.
        - For standalone adjustments:
          Posts a single 2-line adjustment entry between Expense and Real Bank.
        """
        company = self.env.company
        journal = self.env['account.journal'].browse(int(journal_id))
        if not journal or not journal.default_account_id:
            return {'success': False, 'message': _('Selected bank journal does not have a default account.')}

        bank_account = journal.default_account_id
        adj_account = self.env['account.account'].browse(int(account_id))
        if not adj_account:
            return {'success': False, 'message': _('Please select an adjustment/expense account.')}

        try:
            amt = round(float(amount), 2)
        except (ValueError, TypeError):
            return {'success': False, 'message': _('Invalid amount.')}

        if amt <= 0:
            return {'success': False, 'message': _('Amount must be greater than zero.')}

        if not date:
            date = fields.Date.today()
        clr_date = bank_date or date

        source_move = self.env['account.move'].browse(int(source_move_id)) if source_move_id else False

        source_line = False
        if source_line_id:
            source_line = self.env['account.move.line'].browse(int(source_line_id))
        elif source_move and source_move.exists():
            source_line = self.env['account.move.line'].search([
                ('move_id', '=', source_move.id),
                ('bank_date', '=', False),
                ('parent_state', '=', 'posted')
            ], limit=1)

        if source_line and not source_move:
            source_move = source_line.move_id

        # Determine if source line is an interim account line
        is_interim = False
        if source_line and source_line.exists() and bank_account and source_line.account_id.id != bank_account.id:
            in_accs = journal.inbound_payment_method_line_ids.mapped('payment_account_id').ids
            out_accs = journal.outbound_payment_method_line_ids.mapped('payment_account_id').ids
            if source_line.account_id.id in (in_accs + out_accs) or source_line.account_id.reconcile:
                is_interim = True

        # Comprehensive BRS adjustment types:
        deduction_types = [
            'bank_charge',
            'bkash_charge',
            'nagad_charge',
            'mfs_charge',
            'pgw_fee',
            'pos_card_fee',
            'excise_duty',
            'cheque_bounce',
            'direct_debit',
            'rounding_loss',
        ]
        is_money_out = adj_type in deduction_types

        type_labels = {
            'bank_charge': _('Bank Charge & Commission'),
            'bkash_charge': _('bKash Payment / Cash Out Charge'),
            'nagad_charge': _('Nagad Payment / Merchant Charge'),
            'mfs_charge': _('Rocket / Upay / MFS Gateway Fee'),
            'pgw_fee': _('Online Payment Gateway Fee (SSLCommerz / Shurjopay)'),
            'pos_card_fee': _('Card POS Swiping / MDR Charge'),
            'mfs_commission': _('MFS Commission / Cash-in Income'),
            'bank_interest': _('Bank Interest Earned'),
            'excise_duty': _('Govt. Excise Duty & Bank Tax'),
            'cheque_bounce': _('Cheque Return / Dishonour Charges'),
            'direct_debit': _('Direct Bank Debit / Loan EMI'),
            'direct_credit': _('Direct Customer Online Deposit / Transfer In'),
            'rounding_loss': _('Rounding Off Difference (Expense)'),
            'rounding_gain': _('Rounding Off Difference (Income)'),
        }

        label = (description or '').strip()
        if not label:
            label = type_labels.get(adj_type, _('Bank Adjustment'))

        partner = int(partner_id) if partner_id else (
            source_line.partner_id.id if (source_line and source_line.partner_id) else (
                source_move.partner_id.id if (source_move and source_move.partner_id) else False
            )
        )
        voucher_name = source_move.name if (source_move and source_move.exists()) else (source_line.move_id.name if source_line else '/')

        # Determine if we can do a SINGLE COMBINED 1-JOURNAL clearance + adjustment
        combined_clearance = False
        if reconcile_source and source_line and source_line.exists() and not source_line.bank_date and is_interim and bank_account:
            combined_clearance = True

        net_bank_amount = 0.0
        total_bank_withdrawal = 0.0

        if combined_clearance:
            is_receipt = source_line.debit > 0
            voucher_amount = round(source_line.debit if is_receipt else source_line.credit, 2)

            if is_money_out:
                # Standard business case: bKash/Nagad/Bank Charge deduction
                if is_receipt:
                    # e.g., Customer paid 62,500 Taka, bKash charge 500 Taka => Net bank inflow = 62,000 Taka
                    net_bank_amount = round(voucher_amount - amt, 2)
                    if net_bank_amount <= 0:
                        return {
                            'success': False,
                            'message': _('Charge amount (%s) cannot be greater than or equal to voucher gross amount (%s).') % (amt, voucher_amount)
                        }

                    line_vals = [
                        (0, 0, {
                            'account_id': bank_account.id,
                            'name': f"Net Bank Inflow: {voucher_name}",
                            'debit': net_bank_amount,
                            'credit': 0.0,
                            'partner_id': partner,
                            'bank_date': clr_date,
                        }),
                        (0, 0, {
                            'account_id': adj_account.id,
                            'name': f"{label}: {voucher_name}",
                            'debit': amt,
                            'credit': 0.0,
                            'partner_id': partner,
                        }),
                        (0, 0, {
                            'account_id': source_line.account_id.id,
                            'name': f"Clearing: {voucher_name}",
                            'debit': 0.0,
                            'credit': voucher_amount,
                            'partner_id': partner,
                        }),
                    ]
                else:
                    # Supplier Payment / Withdrawal with Bank Transfer Fee
                    total_bank_withdrawal = round(voucher_amount + amt, 2)
                    line_vals = [
                        (0, 0, {
                            'account_id': source_line.account_id.id,
                            'name': f"Clearing: {voucher_name}",
                            'debit': voucher_amount,
                            'credit': 0.0,
                            'partner_id': partner,
                        }),
                        (0, 0, {
                            'account_id': adj_account.id,
                            'name': f"{label}: {voucher_name}",
                            'debit': amt,
                            'credit': 0.0,
                            'partner_id': partner,
                        }),
                        (0, 0, {
                            'account_id': bank_account.id,
                            'name': f"Net Bank Outflow: {voucher_name}",
                            'debit': 0.0,
                            'credit': total_bank_withdrawal,
                            'partner_id': partner,
                            'bank_date': clr_date,
                        }),
                    ]
            else:
                # Commission / Income addition
                if is_receipt:
                    total_bank_inflow = round(voucher_amount + amt, 2)
                    line_vals = [
                        (0, 0, {
                            'account_id': bank_account.id,
                            'name': f"Bank Inflow (+ Commission): {voucher_name}",
                            'debit': total_bank_inflow,
                            'credit': 0.0,
                            'partner_id': partner,
                            'bank_date': clr_date,
                        }),
                        (0, 0, {
                            'account_id': adj_account.id,
                            'name': f"{label}: {voucher_name}",
                            'debit': 0.0,
                            'credit': amt,
                            'partner_id': partner,
                        }),
                        (0, 0, {
                            'account_id': source_line.account_id.id,
                            'name': f"Clearing: {voucher_name}",
                            'debit': 0.0,
                            'credit': voucher_amount,
                            'partner_id': partner,
                        }),
                    ]
                else:
                    net_bank_withdrawal = round(voucher_amount - amt, 2)
                    line_vals = [
                        (0, 0, {
                            'account_id': source_line.account_id.id,
                            'name': f"Clearing: {voucher_name}",
                            'debit': voucher_amount,
                            'credit': 0.0,
                            'partner_id': partner,
                        }),
                        (0, 0, {
                            'account_id': adj_account.id,
                            'name': f"{label}: {voucher_name}",
                            'debit': 0.0,
                            'credit': amt,
                            'partner_id': partner,
                        }),
                        (0, 0, {
                            'account_id': bank_account.id,
                            'name': f"Net Bank Outflow: {voucher_name}",
                            'debit': 0.0,
                            'credit': net_bank_withdrawal,
                            'partner_id': partner,
                            'bank_date': clr_date,
                        }),
                    ]

            ref_str = f"BRS-ADJ: {voucher_name}" + (f": {cheque_no}" if cheque_no else f": {label}")
            narration_text = f"Combined Bank Clearance & Fee Adjustment for {voucher_name} cleared on {clr_date}. Fee: {label} ({amt})."
            move_vals = {
                'journal_id': journal.id,
                'date': clr_date,
                'ref': ref_str,
                'narration': narration_text,
                'move_type': 'entry',
                'is_bank_clearing_entry': True,
                'line_ids': line_vals,
            }
        else:
            # Standalone adjustment or source voucher already cleared
            if source_move and source_move.exists():
                ref_str = f"Adj for {source_move.name}" + (f": {cheque_no}" if cheque_no else f": {label}")
                narration_text = f"Bank Reconciliation Adjustment for original voucher: {source_move.name} ({source_move.partner_id.name or ''}). Reason: {label}."
            else:
                ref_str = cheque_no or label
                narration_text = f"Bank Reconciliation Adjustment: {label}."

            if is_money_out:
                line_vals = [
                    (0, 0, {
                        'account_id': adj_account.id,
                        'name': label,
                        'debit': amt,
                        'credit': 0.0,
                        'partner_id': partner,
                    }),
                    (0, 0, {
                        'account_id': bank_account.id,
                        'name': label,
                        'debit': 0.0,
                        'credit': amt,
                        'partner_id': partner,
                        'bank_date': clr_date if clr_date else False,
                    }),
                ]
            else:
                line_vals = [
                    (0, 0, {
                        'account_id': bank_account.id,
                        'name': label,
                        'debit': amt,
                        'credit': 0.0,
                        'partner_id': partner,
                        'bank_date': clr_date if clr_date else False,
                    }),
                    (0, 0, {
                        'account_id': adj_account.id,
                        'name': label,
                        'debit': 0.0,
                        'credit': amt,
                        'partner_id': partner,
                    }),
                ]

            move_vals = {
                'journal_id': journal.id,
                'date': clr_date,
                'ref': ref_str,
                'narration': narration_text,
                'move_type': 'entry',
                'line_ids': line_vals,
            }

        if hasattr(self.env['account.move'], 'cheque_number') and cheque_no:
            move_vals['cheque_number'] = cheque_no
        elif hasattr(self.env['account.move'], 'cheque_number') and source_move and getattr(source_move, 'cheque_number', False):
            move_vals['cheque_number'] = source_move.cheque_number

        try:
            move = self.env['account.move'].create(move_vals)
            move.action_post()

            source_cleared = False
            source_clr_move_name = ''

            if combined_clearance:
                # Reconcile interim line against original voucher interim line
                clr_interim = move.line_ids.filtered(lambda l: l.account_id == source_line.account_id)
                if clr_interim and source_line.account_id.reconcile:
                    try:
                        (source_line + clr_interim).reconcile()
                    except Exception as e:
                        _logger.warning("Could not reconcile interim lines: %s", e)

                source_line.write({
                    'bank_date': clr_date,
                    'clearing_move_id': move.id,
                })
                source_cleared = True
                source_clr_move_name = move.name
            elif source_line and source_line.exists() and not source_line.bank_date:
                source_line.write({'bank_date': clr_date})
                source_cleared = True

            # Audit Trail Logging:
            curr_sym = move.currency_id.symbol or company.currency_id.symbol or '৳'
            if source_move and source_move.exists() and hasattr(source_move, 'message_post'):
                try:
                    source_body = Markup(
                        f"<b>Bank Reconciliation Combined Adjustment:</b> Journal entry "
                        f"<a href='#id={move.id}&amp;model=account.move'><b>{move.name}</b></a> "
                        f"of <b>{curr_sym} {amt:,.2f}</b> was posted for <i>{label}</i> on {clr_date}."
                    )
                    source_move.message_post(body=source_body)
                except Exception as e:
                    _logger.warning("Could not post message on source move: %s", e)

            if hasattr(move, 'message_post'):
                try:
                    src_link = Markup(f"<a href='#id={source_move.id}&amp;model=account.move'><b>{source_move.name}</b></a>") if (source_move and source_move.exists()) else "original transaction"
                    adj_body = Markup(f"<b>Bank Reconciliation:</b> Combined clearance and fee adjustment against {src_link} for <i>{label}</i>.")
                    move.message_post(body=adj_body)
                except Exception as e:
                    _logger.warning("Could not post message on adjustment move: %s", e)

            if combined_clearance:
                if is_receipt:
                    msg = _('Combined Entry %s posted! Real Bank received net %s (Voucher %s - Fee %s).') % (
                        move.name,
                        f"{curr_sym} {net_bank_amount:,.2f}",
                        f"{curr_sym} {voucher_amount:,.2f}",
                        f"{curr_sym} {amt:,.2f}"
                    )
                else:
                    msg = _('Combined Entry %s posted! Real Bank deducted total %s (Voucher %s + Fee %s).') % (
                        move.name,
                        f"{curr_sym} {total_bank_withdrawal:,.2f}",
                        f"{curr_sym} {voucher_amount:,.2f}",
                        f"{curr_sym} {amt:,.2f}"
                    )
            else:
                msg = _('Adjustment Entry %s posted successfully!') % move.name

            return {
                'success': True,
                'move_id': move.id,
                'move_name': move.name,
                'source_cleared': source_cleared,
                'source_clr_move_name': source_clr_move_name,
                'message': msg,
            }
        except Exception as e:
            _logger.exception("Error creating quick adjustment entry: %s", e)
            return {'success': False, 'message': str(e)}

    @api.model
    def action_toggle_journal_brs(self, journal_id):
        """ Quick toggle journal visibility in Bank Reconciliation """
        journal = self.env['account.journal'].browse(int(journal_id))
        if journal.exists():
            val = not getattr(journal, 'show_in_bank_reconciliation', True)
            journal.show_in_bank_reconciliation = val
            return {'success': True, 'show_in_bank_reconciliation': val, 'show_in_tally_brs': val}
        return {'error': _('Journal not found')}

    # -------------------------------------------------------------------------
    # 2. TALLY BANK RECONCILIATION STATEMENT (BRS) CORE API
    # -------------------------------------------------------------------------
    @api.model
    def get_bank_brs_data(self, journal_id, filter_status='uncleared', date_from=False, date_to=False, search_term=''):
        """
        Fetch bank transactions in true Tally BRS format:
        - Date
        - Particulars (Party / Description)
        - Vch Type
        - Instrument / Cheque No
        - Debit
        - Credit
        - Bank Date (Clearing Date)
        - Balance as per Books, Amounts not reflected in Bank, Balance as per Bank
        """
        company = self.env.company
        journal = self.env['account.journal'].browse(int(journal_id))
        if not journal or not journal.default_account_id:
            return {'error': _('Selected bank journal does not have a default account.')}

        acc = journal.default_account_id
        curr_sym = journal.currency_id.symbol or company.currency_id.symbol or '$'

        # Determine interim accounts for this journal (e.g. Outstanding Receipts / Payments)
        in_accs = journal.inbound_payment_method_line_ids.mapped('payment_account_id').ids
        out_accs = journal.outbound_payment_method_line_ids.mapped('payment_account_id').ids
        interim_acc_ids = [aid for aid in set(in_accs + out_accs) if aid and aid != acc.id]

        # Base domain: includes direct bank lines (excluding clearing entries) and interim voucher lines
        if interim_acc_ids:
            domain = [
                ('company_id', '=', company.id),
                ('parent_state', '=', 'posted'),
                ('is_bank_clearing_line', '=', False),
                '|',
                ('account_id', '=', acc.id),
                '&', ('account_id', 'in', interim_acc_ids), ('journal_id', '=', journal.id),
            ]
        else:
            domain = [
                ('company_id', '=', company.id),
                ('account_id', '=', acc.id),
                ('parent_state', '=', 'posted'),
                ('is_bank_clearing_line', '=', False),
            ]

        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))

        if search_term:
            term = search_term.strip()
            search_leaves = [
                ('move_id.name', 'ilike', term),
                ('ref', 'ilike', term),
                ('name', 'ilike', term),
                ('partner_id.name', 'ilike', term),
            ]
            # cheque number only exists when a cheque-management module adds it
            if 'cheque_number' in self.env['account.move']._fields:
                search_leaves.append(('move_id.cheque_number', 'ilike', term))
            domain += ['|'] * (len(search_leaves) - 1) + search_leaves

        # Filter by status: 'uncleared' (default in Tally), 'cleared', or 'all'
        lines_domain = list(domain)
        if filter_status == 'uncleared':
            lines_domain.append(('bank_date', '=', False))
        elif filter_status == 'cleared':
            lines_domain.append(('bank_date', '!=', False))

        lines = self.env['account.move.line'].search(lines_domain, order='date desc, id desc', limit=500)

        # -------------------------------------------------------------------------
        # Tally BRS & General Ledger Balance Calculation
        # -------------------------------------------------------------------------
        # 1. Total GL Book Balance of the real Bank Account (acc.id)
        gl_domain = [
            ('company_id', '=', company.id),
            ('account_id', '=', acc.id),
            ('parent_state', '=', 'posted'),
        ]
        if date_to:
            gl_domain.append(('date', '<=', date_to))
        gl_lines = self.env['account.move.line'].search(gl_domain)
        total_book_balance = sum(gl_lines.mapped(lambda l: l.debit - l.credit))

        # 2. Uncleared amounts (Vouchers waiting to clear into bank)
        uncl_calc_domain = [
            ('company_id', '=', company.id),
            ('parent_state', '=', 'posted'),
            ('bank_date', '=', False),
        ]
        if interim_acc_ids:
            uncl_calc_domain += [
                ('is_bank_clearing_line', '=', False),
                '|',
                ('account_id', '=', acc.id),
                '&', ('account_id', 'in', interim_acc_ids), ('journal_id', '=', journal.id),
            ]
        else:
            uncl_calc_domain += [
                ('account_id', '=', acc.id),
                ('is_bank_clearing_line', '=', False),
            ]
        if date_to:
            uncl_calc_domain.append(('date', '<=', date_to))

        uncl_lines = self.env['account.move.line'].search(uncl_calc_domain)
        uncleared_deposits = sum(uncl_lines.mapped('debit'))
        uncleared_payments = sum(uncl_lines.mapped('credit'))
        uncleared_count = len(uncl_lines)

        # 3. Direct uncleared bank entries vs. interim entries
        direct_uncl = uncl_lines.filtered(lambda l: l.account_id.id == acc.id)
        direct_uncleared_deposits = sum(direct_uncl.mapped('debit'))
        direct_uncleared_payments = sum(direct_uncl.mapped('credit'))

        # Balance as per Bank Statement:
        # Book Balance - Direct Uncleared Deposits + Direct Uncleared Payments
        calculated_bank_balance = total_book_balance - direct_uncleared_deposits + direct_uncleared_payments

        # 4. Period Statistics (based on active date filter)
        period_domain = [
            ('company_id', '=', company.id),
            ('parent_state', '=', 'posted'),
        ]
        if interim_acc_ids:
            period_domain += [
                ('is_bank_clearing_line', '=', False),
                '|',
                ('account_id', '=', acc.id),
                '&', ('account_id', 'in', interim_acc_ids), ('journal_id', '=', journal.id),
            ]
        else:
            period_domain += [
                ('account_id', '=', acc.id),
                ('is_bank_clearing_line', '=', False),
            ]
        if date_from:
            period_domain.append(('date', '>=', date_from))
        if date_to:
            period_domain.append(('date', '<=', date_to))

        all_period_lines = self.env['account.move.line'].search(period_domain)
        cleared_p_lines = all_period_lines.filtered(lambda l: bool(l.bank_date))
        uncleared_p_lines = all_period_lines.filtered(lambda l: not l.bank_date)

        period_stats = (
            len(all_period_lines),
            len(cleared_p_lines),
            len(uncleared_p_lines),
            sum(cleared_p_lines.mapped('debit')),
            sum(cleared_p_lines.mapped('credit')),
            sum(uncleared_p_lines.mapped('debit')),
            sum(uncleared_p_lines.mapped('credit'))
        )

        # Format items for the UI
        items = []
        for line in lines:
            move = line.move_id
            cheque_no = ''

            # 1. Direct Cheque Number on this move (Journal Entry or Bill)
            if getattr(move, 'cheque_number', False):
                cheque_no = move.cheque_number
            elif getattr(move, 'cheque', False):
                cheque_no = move.cheque

            # 2. Check payment move or payment reconciled bills
            if not cheque_no and line.payment_id:
                if getattr(line.payment_id.move_id, 'cheque_number', False):
                    cheque_no = line.payment_id.move_id.cheque_number
                elif getattr(line.payment_id, 'reconciled_bill_ids', False):
                    for bill in line.payment_id.reconciled_bill_ids:
                        if getattr(bill, 'cheque_number', False):
                            cheque_no = bill.cheque_number
                            break
                elif getattr(line.payment_id, 'reconciled_invoice_ids', False):
                    for inv in line.payment_id.reconciled_invoice_ids:
                        if getattr(inv, 'cheque_number', False):
                            cheque_no = inv.cheque_number
                            break

            # 3. Check matched/reconciled lines for this move (e.g. payment reconciled with a vendor bill)
            if not cheque_no:
                for l_item in move.line_ids:
                    for partial in (l_item.matched_debit_ids | l_item.matched_credit_ids):
                        other = partial.debit_move_id if partial.credit_move_id == l_item else partial.credit_move_id
                        if other.move_id and getattr(other.move_id, 'cheque_number', False):
                            cheque_no = other.move_id.cheque_number
                            break
                    if cheque_no:
                        break

            # 4. Check if move.ref refers to a bill/invoice with cheque number
            if not cheque_no and move.ref:
                ref_move = self.env['account.move'].search([('name', '=', move.ref.strip())], limit=1)
                if ref_move and getattr(ref_move, 'cheque_number', False):
                    cheque_no = ref_move.cheque_number

            # 5. Standard fallbacks: payment reference, line.ref, move.ref
            if not cheque_no and line.payment_id and line.payment_id.payment_reference:
                cheque_no = line.payment_id.payment_reference
            if not cheque_no:
                candidate = (line.ref or move.ref or '').strip()
                # Do not put long descriptions, adjustments, or full sentences into cheque_no
                if candidate and len(candidate) <= 25 and 'Adj for' not in candidate and 'Adjustment' not in candidate and not candidate.startswith('Bank charge'):
                    cheque_no = candidate
                else:
                    cheque_no = ''

            # Description / Particulars
            particulars = line.partner_id.name if line.partner_id else (line.name or line.move_id.name)
            vch_type = line.move_id.move_type or 'entry'
            if line.payment_id:
                vch_type = 'Payment' if line.payment_id.payment_type == 'outbound' else 'Receipt'
            elif line.move_id.move_type == 'entry':
                vch_type = 'Contra / Transfer'

            # Check if this move is an adjustment entry
            is_adj = False
            ref_val = move.ref or ''
            narration_val = getattr(move, 'narration', '') or ''
            if 'Adj for ' in ref_val or 'Bank Reconciliation Adjustment' in narration_val:
                is_adj = True

            items.append({
                'id': line.id,
                'move_id': line.move_id.id,
                'move_name': line.move_id.name or '/',
                'date': str(line.date),
                'particulars': particulars,
                'partner_name': line.partner_id.name if line.partner_id else '',
                'vch_type': vch_type,
                'instrument_no': cheque_no,
                'label': line.name or '',
                'debit': line.debit,
                'credit': line.credit,
                'flow_type': 'in' if line.debit > 0 else 'out',
                'flow_label': 'Debit / Deposit (IN)' if line.debit > 0 else 'Credit / Withdrawal (OUT)',
                'bank_date': str(line.bank_date) if line.bank_date else '',
                'is_cleared': bool(line.bank_date),
                'is_adjustment': is_adj,
                'clearing_move_id': line.clearing_move_id.id if line.clearing_move_id else False,
                'clearing_move_name': line.clearing_move_id.name if line.clearing_move_id else '',
                'is_interim': bool(line.account_id.id != acc.id),
            })

        return {
            'journal_id': journal.id,
            'journal_name': journal.name,
            'account_code': acc.code,
            'account_name': acc.name,
            'currency_symbol': curr_sym,
            'summary': {
                'book_balance': round(total_book_balance, 2),
                'uncleared_deposits': round(uncleared_deposits, 2),
                'uncleared_payments': round(uncleared_payments, 2),
                'amounts_not_in_bank': round(uncleared_deposits - uncleared_payments, 2),
                'calculated_bank_balance': round(calculated_bank_balance, 2),
                'uncleared_count': uncleared_count,
                'total_shown_count': len(items),
                'period_total_count': period_stats[0],
                'period_cleared_count': period_stats[1],
                'period_uncleared_count': period_stats[2],
                'period_cleared_debit': round(period_stats[3], 2),
                'period_cleared_credit': round(period_stats[4], 2),
                'period_uncleared_debit': round(period_stats[5], 2),
                'period_uncleared_credit': round(period_stats[6], 2),
            },
            'items': items,
        }

    @api.model
    def action_update_single_bank_date(self, line_id, bank_date):
        """
        Updates Bank Clearance Date on a single bank move line.
        PROCESS 1 IMPLEMENTATION:
        - When setting a Bank Date on an Interim Voucher (Outstanding Receipts / Payments):
          Automatically creates and posts a Clearing Journal Entry (account.move) on bank_date,
          transferring the balance from Interim Account into the real Bank Account.
          Reconciles the interim lines together so outstanding balances zero out.
        - When removing Bank Date:
          Safely cancels and unlinks the clearing journal entry, resets line.
        - For legacy/direct bank lines (already in bank account):
          Directly marks bank_date without creating duplicate bank lines.
        """
        line = self.env['account.move.line'].browse(int(line_id))
        if not line or not line.exists():
            return {'success': False, 'message': _('Transaction line not found.')}

        date_val = bank_date.strip() if (bank_date and str(bank_date).strip()) else False

        # Identify bank journal and bank liquidity account
        journal = line.journal_id
        if journal.type not in ('bank', 'cash'):
            # If line came from MISC or other journal, search bank journal matching payment or default account
            journal = self.env['account.journal'].search([
                ('company_id', '=', line.company_id.id),
                ('type', 'in', ('bank', 'cash')),
                ('default_account_id', '=', line.account_id.id)
            ], limit=1) or line.journal_id

        bank_acc = journal.default_account_id if journal else False
        is_interim = False
        if bank_acc and line.account_id.id != bank_acc.id:
            in_accs = journal.inbound_payment_method_line_ids.mapped('payment_account_id').ids
            out_accs = journal.outbound_payment_method_line_ids.mapped('payment_account_id').ids
            if line.account_id.id in (in_accs + out_accs) or line.account_id.reconcile:
                is_interim = True

        clearing_move_name = ''
        clearing_move_id = False

        if date_val:
            if is_interim and bank_acc:
                clearing_move = line.clearing_move_id
                if clearing_move and clearing_move.exists():
                    # Update existing clearing move date
                    clearing_move.write({'date': date_val})
                    bank_lines = clearing_move.line_ids.filtered(lambda l: l.account_id == bank_acc)
                    bank_lines.write({'bank_date': date_val})
                    line.write({'bank_date': date_val})
                    clearing_move_id = clearing_move.id
                    clearing_move_name = clearing_move.name
                else:
                    # Create new Clearing Journal Entry
                    is_receipt = line.debit > 0
                    amount = line.debit if is_receipt else line.credit
                    partner = line.partner_id or line.move_id.partner_id or False
                    voucher_name = line.move_id.name or '/'
                    label = f"Clearing: {voucher_name}"

                    if is_receipt:
                        # Deposit into Bank: Debit Bank Account, Credit Outstanding Receipts
                        line_vals = [
                            (0, 0, {
                                'account_id': bank_acc.id,
                                'name': label,
                                'debit': amount,
                                'credit': 0.0,
                                'partner_id': partner.id if partner else False,
                                'bank_date': date_val,
                            }),
                            (0, 0, {
                                'account_id': line.account_id.id,
                                'name': label,
                                'debit': 0.0,
                                'credit': amount,
                                'partner_id': partner.id if partner else False,
                            }),
                        ]
                    else:
                        # Withdrawal / Payment from Bank: Debit Outstanding Payments, Credit Bank Account
                        line_vals = [
                            (0, 0, {
                                'account_id': line.account_id.id,
                                'name': label,
                                'debit': amount,
                                'credit': 0.0,
                                'partner_id': partner.id if partner else False,
                            }),
                            (0, 0, {
                                'account_id': bank_acc.id,
                                'name': label,
                                'debit': 0.0,
                                'credit': amount,
                                'partner_id': partner.id if partner else False,
                                'bank_date': date_val,
                            }),
                        ]

                    move_vals = {
                        'journal_id': journal.id,
                        'date': date_val,
                        'ref': f"BRS-CLR: {voucher_name}",
                        'narration': f"Auto Clearing Entry for {voucher_name} cleared on {date_val}.",
                        'move_type': 'entry',
                        'is_bank_clearing_entry': True,
                        'line_ids': line_vals,
                    }
                    if hasattr(self.env['account.move'], 'cheque_number') and getattr(line.move_id, 'cheque_number', False):
                        move_vals['cheque_number'] = line.move_id.cheque_number

                    clearing_move = self.env['account.move'].create(move_vals)
                    clearing_move.action_post()

                    # Reconcile interim lines together
                    clr_interim = clearing_move.line_ids.filtered(lambda l: l.account_id == line.account_id)
                    if clr_interim and line.account_id.reconcile:
                        try:
                            (line + clr_interim).reconcile()
                        except Exception as e:
                            _logger.warning("Could not reconcile interim lines: %s", e)

                    line.write({
                        'bank_date': date_val,
                        'clearing_move_id': clearing_move.id,
                    })
                    clearing_move_id = clearing_move.id
                    clearing_move_name = clearing_move.name

                    if hasattr(line.move_id, 'message_post'):
                        try:
                            line.move_id.message_post(
                                body=Markup(_("<b>Bank Reconciliation Cleared:</b> Bank clearing date <b>%s</b> applied. Generated Clearing Journal Entry: <a href='#' data-oe-model='account.move' data-oe-id='%d'>%s</a>") % (date_val, clearing_move.id, clearing_move.name))
                            )
                        except Exception:
                            pass
            else:
                line.write({'bank_date': date_val})
        else:
            # Un-clearing / removing Bank Date
            if line.clearing_move_id:
                clearing_move = line.clearing_move_id
                try:
                    line.remove_move_reconcile()
                except Exception as e:
                    _logger.warning("Error removing reconcile: %s", e)

                line.write({'bank_date': False, 'clearing_move_id': False})
                if clearing_move.state == 'posted':
                    clearing_move.button_draft()
                clearing_move.unlink()

                if hasattr(line.move_id, 'message_post'):
                    try:
                        line.move_id.message_post(
                            body=Markup(_("<b>Bank Reconciliation:</b> Clearance removed and clearing entry deleted."))
                        )
                    except Exception:
                        pass
            else:
                line.write({'bank_date': False})

        return {
            'success': True,
            'bank_date': date_val or '',
            'is_cleared': bool(date_val),
            'clearing_move_id': clearing_move_id,
            'clearing_move_name': clearing_move_name,
            'message': _('Bank Date updated & Clearing Journal created: %s') % clearing_move_name if clearing_move_id else (_('Bank Date updated!') if date_val else _('Cleared status removed.'))
        }

    @api.model
    def action_bulk_set_bank_date(self, line_ids, bank_date):
        """
        Set Bank Date for all selected transactions at once.
        Creates clearing entries for interim transactions.
        """
        if not line_ids:
            return {'success': False, 'message': _('Please select at least one transaction.')}
        if not bank_date:
            return {'success': False, 'message': _('Please provide a valid Bank Clearance Date.')}

        count = 0
        for lid in line_ids:
            res = self.action_update_single_bank_date(lid, bank_date)
            if res.get('success'):
                count += 1

        return {
            'success': True,
            'count': count,
            'message': _('%d transaction(s) marked cleared on %s!') % (count, bank_date)
        }

    @api.model
    def action_bulk_clear_bank_date(self, line_ids):
        """
        Un-reconcile / remove Bank Date for selected transactions.
        Safely removes associated clearing entries.
        """
        if not line_ids:
            return {'success': False, 'message': _('Please select at least one transaction.')}

        count = 0
        for lid in line_ids:
            res = self.action_update_single_bank_date(lid, False)
            if res.get('success'):
                count += 1

        return {
            'success': True,
            'count': count,
            'message': _('Bank Date removed for %d transaction(s).') % count
        }

    # -------------------------------------------------------------------------
    # 3. PARTY & BILL-BY-BILL SETTLEMENT (AGST REF)
    # -------------------------------------------------------------------------
    @api.model
    def search_partners(self, query='', limit=50):
        domain = [('active', '=', True)]
        if query:
            domain += ['|', ('name', 'ilike', query), ('ref', 'ilike', query)]
        partners = self.env['res.partner'].search_read(
            domain,
            ['id', 'name', 'ref', 'email', 'phone'],
            limit=limit,
            order='name asc'
        )
        return partners

    @api.model
    def get_unreconciled_lines(self, partner_id=False, account_id=False, search_term='', date_from=False, date_to=False):
        company = self.env.company
        domain = [
            ('company_id', '=', company.id),
            ('parent_state', '=', 'posted'),
            ('reconciled', '=', False),
            ('amount_residual', '!=', 0),
        ]

        if partner_id:
            domain.append(('partner_id', '=', int(partner_id)))

        if account_id:
            domain.append(('account_id', '=', int(account_id)))
        else:
            domain.append(('account_id.reconcile', '=', True))

        if search_term:
            term = search_term.strip()
            domain += [
                '|', '|', '|',
                ('move_id.name', 'ilike', term),
                ('ref', 'ilike', term),
                ('name', 'ilike', term),
                ('partner_id.name', 'ilike', term)
            ]

        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))

        lines = self.env['account.move.line'].search(
            domain,
            order='date asc, id asc',
            limit=300
        )

        debit_items = []
        credit_items = []
        total_debit_residual = 0.0
        total_credit_residual = 0.0

        for line in lines:
            currency = line.currency_id or line.company_currency_id
            curr_sym = currency.symbol or company.currency_id.symbol or ''
            residual = line.amount_residual
            residual_abs = abs(residual)

            item = {
                'id': line.id,
                'move_id': line.move_id.id,
                'move_name': line.move_id.name or '/',
                'date': str(line.date),
                'date_maturity': str(line.date_maturity) if line.date_maturity else '',
                'ref': line.ref or line.move_id.ref or '',
                'name': line.name or '',
                'partner_id': line.partner_id.id if line.partner_id else False,
                'partner_name': line.partner_id.name if line.partner_id else '—',
                'account_id': line.account_id.id,
                'account_code': line.account_id.code,
                'account_name': line.account_id.name,
                'debit': line.debit,
                'credit': line.credit,
                'original_amount': line.debit if line.debit > 0 else line.credit,
                'amount_residual': residual_abs,
                'currency_symbol': curr_sym,
            }

            if residual > 0:
                debit_items.append(item)
                total_debit_residual += residual_abs
            else:
                credit_items.append(item)
                total_credit_residual += residual_abs

        net_balance = total_debit_residual - total_credit_residual

        return {
            'debits': debit_items,
            'credits': credit_items,
            'summary': {
                'total_debit_residual': round(total_debit_residual, 2),
                'total_credit_residual': round(total_credit_residual, 2),
                'net_balance': round(net_balance, 2),
                'debit_count': len(debit_items),
                'credit_count': len(credit_items),
                'currency_symbol': company.currency_id.symbol or '$',
            }
        }

    @api.model
    def action_reconcile_selected(self, line_ids):
        if not line_ids or len(line_ids) < 2:
            return {'success': False, 'message': _('Please select at least one Debit and one Credit line.')}
        lines = self.env['account.move.line'].browse(line_ids)
        try:
            lines.reconcile()
            return {'success': True, 'message': _('Selected vouchers successfully reconciled!')}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    @api.model
    def action_auto_reconcile_fifo(self, partner_id=False, account_id=False):
        company = self.env.company
        domain = [
            ('company_id', '=', company.id),
            ('parent_state', '=', 'posted'),
            ('reconciled', '=', False),
            ('amount_residual', '!=', 0),
        ]
        if partner_id:
            domain.append(('partner_id', '=', int(partner_id)))
        if account_id:
            domain.append(('account_id', '=', int(account_id)))
        else:
            domain.append(('account_id.reconcile', '=', True))

        lines = self.env['account.move.line'].search(domain, order='date asc, id asc')
        groups = {}
        for line in lines:
            key = (line.partner_id.id, line.account_id.id)
            if key not in groups:
                groups[key] = {'debits': [], 'credits': []}
            if line.amount_residual > 0:
                groups[key]['debits'].append(line)
            else:
                groups[key]['credits'].append(line)

        count = 0
        for (p, a), item in groups.items():
            d_lines = item['debits']
            c_lines = item['credits']
            d_i, c_i = 0, 0
            while d_i < len(d_lines) and c_i < len(c_lines):
                d = d_lines[d_i]
                c = c_lines[c_i]
                if d.reconciled or d.amount_residual == 0:
                    d_i += 1
                    continue
                if c.reconciled or c.amount_residual == 0:
                    c_i += 1
                    continue
                try:
                    (d + c).reconcile()
                    count += 1
                except Exception:
                    d_i += 1
                    c_i += 1
                if d.reconciled or d.amount_residual == 0:
                    d_i += 1
                if c.reconciled or c.amount_residual == 0:
                    c_i += 1

        return {'success': True, 'message': _('%d match(es) processed via FIFO!') % count}

