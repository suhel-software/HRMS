# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class DslContraVoucher(models.Model):
    _name = 'dsl.contra.voucher'
    _description = 'Contra Voucher (Bank & Cash Fund Transfer)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Contra Voucher No.',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    date = fields.Date(
        string='Transfer Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        store=True,
        readonly=True,
    )

    # ── 1. Contra Transfer Type ──
    contra_type = fields.Selection([
        ('cash_to_bank', 'Cash Deposit to Bank (নগদ টাকা ব্যাংকে জমা)'),
        ('bank_to_cash', 'Cash Withdrawal from Bank (ব্যাংক থেকে নগদ উত্তোলন)'),
        ('bank_to_bank', 'Bank to Bank Transfer (ব্যাংক টু ব্যাংক ট্রান্সফার)'),
        ('cash_to_cash', 'Cash to Petty Cash Transfer (ক্যাশ টু পেটি ক্যাশ)'),
    ], string='Transfer Type', required=True, default='cash_to_bank', tracking=True)

    # ── 2. Source (From) Side ──
    source_journal_domain = fields.Char(compute='_compute_journal_domains')
    dest_journal_domain = fields.Char(compute='_compute_journal_domains')

    source_journal_id = fields.Many2one(
        'account.journal',
        string='From Journal (Source)',
        required=True,
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]",
        tracking=True,
    )
    source_account_id = fields.Many2one(
        'account.account',
        string='From GL Account (Credit)',
        required=True,
        tracking=True,
    )
    source_current_balance = fields.Monetary(
        string='Source Current Balance',
        currency_field='currency_id',
        compute='_compute_account_balances',
    )
    source_balance_after = fields.Monetary(
        string='Source Balance After Transfer',
        currency_field='currency_id',
        compute='_compute_account_balances',
    )

    # ── 3. Destination (To) Side ──
    dest_journal_id = fields.Many2one(
        'account.journal',
        string='To Journal (Destination)',
        required=True,
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]",
        tracking=True,
    )
    dest_account_id = fields.Many2one(
        'account.account',
        string='To GL Account (Debit)',
        required=True,
        tracking=True,
    )
    dest_current_balance = fields.Monetary(
        string='Destination Current Balance',
        currency_field='currency_id',
        compute='_compute_account_balances',
    )
    dest_balance_after = fields.Monetary(
        string='Destination Balance After Transfer',
        currency_field='currency_id',
        compute='_compute_account_balances',
    )

    # ── 4. Amount & Bank Charges ──
    amount = fields.Monetary(
        string='Transfer Amount',
        currency_field='currency_id',
        required=True,
        tracking=True,
    )
    has_bank_charge = fields.Boolean(
        string='Include Bank Transfer / RTGS Charge?',
        default=False,
    )
    bank_charge_amount = fields.Monetary(
        string='Bank Charge / Fee',
        currency_field='currency_id',
        default=0.0,
        tracking=True,
    )
    bank_charge_account_id = fields.Many2one(
        'account.account',
        string='Bank Charge Expense A/C',
        default=lambda self: self._default_bank_charge_account(),
    )
    total_deducted_amount = fields.Monetary(
        string='Total Credit from Source',
        currency_field='currency_id',
        compute='_compute_total_deducted',
        store=True,
    )
    amount_in_words = fields.Char(
        string='Amount in Words',
        compute='_compute_amount_in_words',
    )

    # ── 5. Instrument / Cheque / Deposit Slip / Bearer Info ──
    instrument_type = fields.Selection([
        ('cash_deposit', 'Direct Cash Deposit'),
        ('cheque', 'Cheque (Bearer / Self / Crossed)'),
        ('beftn', 'BEFTN / EFT'),
        ('rtgs', 'RTGS (Instant Transfer)'),
        ('npsb', 'NPSB'),
        ('online', 'Online / Internet Banking'),
        ('pay_order', 'Pay Order (PO)'),
        ('demand_draft', 'Demand Draft (DD)'),
        ('mfs', 'MFS (bKash / Nagad / Rocket)'),
        ('standing', 'Standing Instruction / Auto Transfer'),
    ], string='Instrument / Mode', default='cash_deposit', required=True, tracking=True)

    cheque_number = fields.Char(
        string='Cheque / Instrument No.',
        tracking=True,
        index=True,
        help='Cheque No for Cash Withdrawal / Bank Transfer, or Slip / Trx Ref for Deposit.',
    )
    cheque_date = fields.Date(
        string='Cheque / Instrument Date',
        default=fields.Date.context_today,
        tracking=True,
    )
    is_post_dated = fields.Boolean(
        string='Post-Dated (PDC)',
        compute='_compute_is_post_dated',
        store=True,
    )
    cheque_type = fields.Selection([
        ('bearer', 'Bearer / Self Cheque (নগদ উত্তোলন)'),
        ('account_payee', 'A/C Payee Only'),
        ('crossed', 'Crossed (& Co.)'),
        ('order', 'Order Cheque'),
    ], string='Cheque Crossing', default='bearer')
    cheque_book_ref = fields.Char(
        string='Cheque Book / Leaf Ref.',
        help='e.g. CB-2026-A (Leaf #47)',
    )
    deposit_slip_number = fields.Char(
        string='Deposit Slip No.',
        tracking=True,
    )
    transaction_reference = fields.Char(
        string='UTR / TrxID / Reference',
        tracking=True,
    )
    bank_name = fields.Char(
        string='Bank Name',
        tracking=True,
    )
    bank_branch = fields.Char(
        string='Bank Branch',
    )
    routing_number = fields.Char(
        string='Routing Number (9-Digit)',
    )

    # Bearer / Depositor / Withdrawer Person
    bearer_employee_id = fields.Many2one(
        'hr.employee',
        string='Deposited / Withdrawn By (Employee)',
        tracking=True,
    )
    bearer_name = fields.Char(
        string='Bearer / Messenger Name',
        tracking=True,
    )
    bearer_mobile = fields.Char(
        string='Bearer Mobile No.',
    )
    bearer_nid = fields.Char(
        string='Bearer NID / ID Card No.',
    )

    # ── 6. Cash Denomination Breakdown (টাকার নোটের হিসাব) ──
    use_denomination = fields.Boolean(
        string='Use Cash Denomination Breakdown (নোটের হিসাব)',
        default=False,
    )
    denomination_line_ids = fields.One2many(
        'dsl.contra.denomination',
        'contra_id',
        string='Cash Note Denominations',
        copy=True,
    )
    denomination_total = fields.Monetary(
        string='Total from Notes',
        currency_field='currency_id',
        compute='_compute_denomination_total',
        store=True,
    )

    # ── 7. Accounting & Workflow Integration ──
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('posted', 'Posted (GL & BRS)'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True)

    move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True,
        copy=False,
        tracking=True,
    )
    is_bank_cleared = fields.Boolean(
        string='Cleared in BRS',
        related='move_id.is_bank_cleared',
        readonly=True,
    )
    bank_clearance_date = fields.Date(
        string='Bank Clearance Date',
        related='move_id.bank_clearance_date',
        readonly=True,
    )
    narration = fields.Text(
        string='Purpose / Narration',
        required=True,
        default='Internal Fund Transfer (Contra)',
    )

    prepared_by_id = fields.Many2one(
        'res.users',
        string='Prepared By',
        default=lambda self: self.env.user,
        readonly=True,
    )
    verified_by_id = fields.Many2one(
        'res.users',
        string='Verified By',
        readonly=True,
    )
    approved_by_id = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
    )
    posted_by_id = fields.Many2one(
        'res.users',
        string='Posted By',
        readonly=True,
    )

    # ── Defaults & Computes ──
    @api.model
    def _default_bank_charge_account(self):
        acc = self.env['account.account'].search([
            ('name', 'ilike', 'Bank'),
            ('account_type', 'in', ('expense', 'expense_direct_cost')),
        ], limit=1)
        if not acc:
            acc = self.env['account.account'].search([
                ('account_type', '=', 'expense'),
            ], limit=1)
        return acc

    @api.depends('contra_type', 'company_id')
    def _compute_journal_domains(self):
        for rec in self:
            rec.source_journal_domain = '[]'
            rec.dest_journal_domain = '[]'

    @api.depends('amount', 'has_bank_charge', 'bank_charge_amount')
    def _compute_total_deducted(self):
        for rec in self:
            charge = rec.bank_charge_amount if rec.has_bank_charge else 0.0
            rec.total_deducted_amount = (rec.amount or 0.0) + charge

    @api.depends('amount', 'currency_id')
    def _compute_amount_in_words(self):
        for rec in self:
            if rec.currency_id and rec.amount:
                try:
                    rec.amount_in_words = rec.currency_id.amount_to_text(rec.amount)
                except Exception:
                    rec.amount_in_words = False
            else:
                rec.amount_in_words = False

    @api.depends('cheque_date', 'date')
    def _compute_is_post_dated(self):
        for rec in self:
            if rec.cheque_date and rec.date:
                rec.is_post_dated = rec.cheque_date > rec.date
            else:
                rec.is_post_dated = False

    @api.depends('denomination_line_ids.subtotal')
    def _compute_denomination_total(self):
        for rec in self:
            rec.denomination_total = sum(rec.denomination_line_ids.mapped('subtotal'))

    @api.depends('source_account_id', 'dest_account_id', 'amount', 'total_deducted_amount', 'state')
    def _compute_account_balances(self):
        AccountMoveLine = self.env['account.move.line']
        for rec in self:
            src_bal = 0.0
            dst_bal = 0.0
            if rec.source_account_id:
                lines = AccountMoveLine.search([
                    ('account_id', '=', rec.source_account_id.id),
                    ('parent_state', '=', 'posted'),
                ])
                src_bal = sum(lines.mapped('debit')) - sum(lines.mapped('credit'))
            if rec.dest_account_id:
                lines = AccountMoveLine.search([
                    ('account_id', '=', rec.dest_account_id.id),
                    ('parent_state', '=', 'posted'),
                ])
                dst_bal = sum(lines.mapped('debit')) - sum(lines.mapped('credit'))

            rec.source_current_balance = src_bal
            rec.dest_current_balance = dst_bal
            if rec.state == 'posted':
                rec.source_balance_after = src_bal
                rec.dest_balance_after = dst_bal
            else:
                rec.source_balance_after = src_bal - (rec.total_deducted_amount or 0.0)
                rec.dest_balance_after = dst_bal + (rec.amount or 0.0)

    # ── Onchange Helpers ──
    @api.onchange('contra_type')
    def _onchange_contra_type(self):
        Journal = self.env['account.journal']
        bank_journals = Journal.search([('type', '=', 'bank'), ('company_id', '=', self.company_id.id)])
        cash_journals = Journal.search([('type', '=', 'cash'), ('company_id', '=', self.company_id.id)])

        if self.contra_type == 'cash_to_bank':
            self.instrument_type = 'cash_deposit'
            if cash_journals:
                self.source_journal_id = cash_journals[0]
            if bank_journals:
                self.dest_journal_id = bank_journals[0]
            self.narration = 'Cash deposited to Bank Account'
        elif self.contra_type == 'bank_to_cash':
            self.instrument_type = 'cheque'
            self.cheque_type = 'bearer'
            if bank_journals:
                self.source_journal_id = bank_journals[0]
            if cash_journals:
                self.dest_journal_id = cash_journals[0]
            self.narration = 'Cash withdrawn from Bank for Office / Factory Cash'
        elif self.contra_type == 'bank_to_bank':
            self.instrument_type = 'rtgs'
            self.cheque_type = 'account_payee'
            if bank_journals:
                self.source_journal_id = bank_journals[0]
                if len(bank_journals) > 1:
                    self.dest_journal_id = bank_journals[1]
            self.narration = 'Inter-Bank Fund Transfer'
        elif self.contra_type == 'cash_to_cash':
            self.instrument_type = 'cash_deposit'
            if cash_journals:
                self.source_journal_id = cash_journals[0]
                if len(cash_journals) > 1:
                    self.dest_journal_id = cash_journals[1]
            self.narration = 'Cash transferred to Petty Cash / Branch Cash'

    @api.onchange('source_journal_id')
    def _onchange_source_journal_id(self):
        if self.source_journal_id and self.source_journal_id.default_account_id:
            self.source_account_id = self.source_journal_id.default_account_id
            if self.source_journal_id.type == 'bank' and not self.bank_name:
                self.bank_name = self.source_journal_id.name

    @api.onchange('dest_journal_id')
    def _onchange_dest_journal_id(self):
        if self.dest_journal_id and self.dest_journal_id.default_account_id:
            self.dest_account_id = self.dest_journal_id.default_account_id
            if self.dest_journal_id.type == 'bank' and not self.bank_name:
                self.bank_name = self.dest_journal_id.name

    @api.onchange('bearer_employee_id')
    def _onchange_bearer_employee_id(self):
        if self.bearer_employee_id:
            self.bearer_name = self.bearer_employee_id.name
            self.bearer_mobile = self.bearer_employee_id.mobile_phone or self.bearer_employee_id.work_phone or False
            self.bearer_nid = getattr(self.bearer_employee_id, 'identification_id', False)

    # ── Denomination Helper Buttons ──
    def action_load_bd_notes(self):
        """Populate standard Bangladesh Taka note denominations (1000, 500, 200, 100, 50, 20, 10, 5, 2)."""
        self.ensure_one()
        existing_notes = set(self.denomination_line_ids.mapped('note_value'))
        bd_notes = [1000, 500, 200, 100, 50, 20, 10, 5, 2]
        vals_list = []
        for idx, note in enumerate(bd_notes, start=1):
            if note not in existing_notes:
                vals_list.append((0, 0, {
                    'sequence': idx * 10,
                    'note_value': note,
                    'quantity': 0,
                }))
        if vals_list:
            self.write({
                'use_denomination': True,
                'denomination_line_ids': vals_list,
            })

    def action_apply_denomination_amount(self):
        """Copy computed denomination total into the Transfer Amount field."""
        for rec in self:
            if rec.denomination_total <= 0:
                raise UserError(_('Please enter note quantities in the Denomination table first.'))
            rec.amount = rec.denomination_total

    # ── CRUD & Constraints ──
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('dsl.contra.voucher') or _('New')
        return super().create(vals_list)

    @api.constrains('source_account_id', 'dest_account_id', 'amount')
    def _check_contra_accounts_and_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Transfer Amount must be greater than zero (0.00).'))
            if rec.source_account_id and rec.dest_account_id and rec.source_account_id == rec.dest_account_id:
                raise ValidationError(_('Source GL Account and Destination GL Account cannot be the same! Please select two different accounts or journals.'))

    # ── Workflow Actions ──
    def action_submit(self):
        for rec in self:
            rec._check_contra_accounts_and_amount()
            rec.write({
                'state': 'submitted',
                'verified_by_id': self.env.user.id,
            })

    def action_approve(self):
        for rec in self:
            rec._check_contra_accounts_and_amount()
            rec.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
            })

    def action_post(self):
        """Create and post the corresponding Journal Entry (`account.move`) with full BRS & Cheque Register sync."""
        for rec in self:
            rec._check_contra_accounts_and_amount()
            if rec.move_id and rec.move_id.state == 'posted':
                rec.state = 'posted'
                continue

            # Determine which journal should host the Journal Entry (prefer Bank journal so BRS picks it up cleanly)
            posting_journal = rec.source_journal_id
            if rec.dest_journal_id.type == 'bank' and rec.source_journal_id.type != 'bank':
                posting_journal = rec.dest_journal_id

            inst_ref = rec.cheque_number or rec.deposit_slip_number or rec.transaction_reference or rec.name
            type_label = dict(self._fields['contra_type'].selection).get(rec.contra_type, 'Contra Transfer')
            ref_str = f"{rec.name} | {type_label}"
            if inst_ref and inst_ref != rec.name:
                ref_str += f" ({inst_ref})"

            line_vals = [
                # 1. Credit Source Account (Total Deducted = Amount + Bank Charge)
                (0, 0, {
                    'name': f"Contra Transfer From {rec.source_journal_id.name} -> {rec.dest_journal_id.name} [{rec.name}]",
                    'account_id': rec.source_account_id.id,
                    'debit': 0.0,
                    'credit': rec.total_deducted_amount,
                }),
                # 2. Debit Destination Account (Transfer Amount)
                (0, 0, {
                    'name': f"Contra Transfer To {rec.dest_journal_id.name} <- {rec.source_journal_id.name} [{rec.name}]",
                    'account_id': rec.dest_account_id.id,
                    'debit': rec.amount,
                    'credit': 0.0,
                }),
            ]

            # 3. Optional Bank Transfer Charge Debit Line
            if rec.has_bank_charge and rec.bank_charge_amount > 0:
                if not rec.bank_charge_account_id:
                    raise UserError(_('Please select a Bank Charge Expense Account for the transfer charge.'))
                line_vals.append((0, 0, {
                    'name': f"Bank Transfer Charge - {rec.name}",
                    'account_id': rec.bank_charge_account_id.id,
                    'debit': rec.bank_charge_amount,
                    'credit': 0.0,
                }))

            # Map instrument_type to account.move instrument_type
            move_inst_type = rec.instrument_type
            if move_inst_type not in ('cheque', 'pay_order', 'demand_draft', 'beftn', 'rtgs', 'npsb', 'online', 'mfs', 'card', 'cash_deposit', 'standing'):
                move_inst_type = 'cash_deposit'

            move_vals = {
                'move_type': 'entry',
                'journal_id': posting_journal.id,
                'date': rec.date,
                'ref': ref_str,
                'narration': rec.narration,
                'dsl_voucher_type': 'contra',
                'instrument_type': move_inst_type,
                'cheque_number': rec.cheque_number or rec.deposit_slip_number or rec.transaction_reference or rec.name,
                'cheque_date': rec.cheque_date or rec.date,
                'cheque_type': rec.cheque_type if rec.cheque_type in ('account_payee', 'crossed', 'bearer', 'order') else 'bearer',
                'cheque_status': 'deposited' if rec.contra_type == 'cash_to_bank' else 'issued',
                'cheque_book_ref': rec.cheque_book_ref,
                'deposit_slip_number': rec.deposit_slip_number,
                'transaction_reference': rec.transaction_reference,
                'bank_name': rec.bank_name or posting_journal.name,
                'bank_branch': rec.bank_branch,
                'routing_number': rec.routing_number,
                'payee_name': rec.bearer_name or ('Self / Cash Deposit' if rec.contra_type == 'cash_to_bank' else 'Self / Cash Withdrawal'),
                'bank_charge_amount': rec.bank_charge_amount if rec.has_bank_charge else 0.0,
                'contra_voucher_id': rec.id,
                'line_ids': line_vals,
            }

            if rec.move_id and rec.move_id.state == 'draft':
                rec.move_id.line_ids.unlink()
                rec.move_id.write(move_vals)
                move = rec.move_id
            else:
                move = self.env['account.move'].create(move_vals)

            move.action_post()
            rec.write({
                'move_id': move.id,
                'state': 'posted',
                'approved_by_id': rec.approved_by_id.id or self.env.user.id,
                'posted_by_id': self.env.user.id,
            })

    def action_cancel(self):
        for rec in self:
            if rec.move_id:
                if rec.move_id.state == 'posted':
                    rec.move_id.button_draft()
                rec.move_id.button_cancel()
            rec.state = 'cancelled'

    def action_draft(self):
        for rec in self:
            if rec.move_id and rec.move_id.state == 'posted':
                rec.move_id.button_draft()
            rec.state = 'draft'

    def action_open_journal_entry(self):
        self.ensure_one()
        if not self.move_id:
            return False
        return {
            'name': _('Contra Journal Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class DslContraDenomination(models.Model):
    _name = 'dsl.contra.denomination'
    _description = 'Contra Cash Denomination Line (Bangladesh Taka Notes)'
    _order = 'note_value desc, sequence asc'

    sequence = fields.Integer(default=10)
    contra_id = fields.Many2one(
        'dsl.contra.voucher',
        string='Contra Voucher',
        required=True,
        ondelete='cascade',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='contra_id.currency_id',
        store=True,
        readonly=True,
    )
    note_value = fields.Integer(
        string='Note / Coin Denomination (৳)',
        required=True,
        default=1000,
    )
    quantity = fields.Integer(
        string='Number of Notes / Coins',
        required=True,
        default=0,
    )
    subtotal = fields.Monetary(
        string='Subtotal (৳)',
        currency_field='currency_id',
        compute='_compute_subtotal',
        store=True,
    )
    remarks = fields.Char(string='Bundle / Note Remarks')

    @api.depends('note_value', 'quantity')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = float(line.note_value or 0) * float(line.quantity or 0)


class AccountMoveContraExtend(models.Model):
    _inherit = 'account.move'

    contra_voucher_id = fields.Many2one(
        'dsl.contra.voucher',
        string='Contra Voucher',
        readonly=True,
        copy=False,
    )

    def action_open_contra_voucher(self):
        self.ensure_one()
        if not self.contra_voucher_id:
            return False
        return {
            'name': _('Contra Voucher'),
            'type': 'ir.actions.act_window',
            'res_model': 'dsl.contra.voucher',
            'res_id': self.contra_voucher_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

