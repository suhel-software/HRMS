# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

INSTRUMENT_TYPES = [
    ('cheque', 'Cheque'),
    ('pay_order', 'Pay Order'),
    ('demand_draft', 'Demand Draft (DD)'),
    ('beftn', 'BEFTN / EFT'),
    ('rtgs', 'RTGS'),
    ('npsb', 'NPSB'),
    ('online', 'Online / Internet Banking'),
    ('mfs', 'MFS (bKash / Nagad / Rocket)'),
    ('card', 'Debit / Credit Card'),
    ('cash_deposit', 'Cash Deposit'),
    ('standing', 'Standing Instruction / Auto Debit'),
]
CHEQUE_TYPES = [
    ('account_payee', 'Account Payee (A/C Payee)'),
    ('crossed', 'Crossed'),
    ('bearer', 'Bearer / Cash'),
    ('order', 'Order'),
]
CHEQUE_STATES = [
    ('draft', 'Draft'),
    ('issued', 'Issued / Handed Over'),
    ('received', 'Received'),
    ('deposited', 'Deposited to Bank'),
    ('cleared', 'Cleared'),
    ('bounced', 'Bounced / Dishonoured'),
    ('cancelled', 'Cancelled / Void'),
    ('stale', 'Stale (Expired)'),
]
VOUCHER_TYPES = [
    ('bank_payment', 'Bank Payment (BP)'),
    ('bank_receipt', 'Bank Receipt (BR)'),
    ('cash_payment', 'Cash Payment (CP)'),
    ('cash_receipt', 'Cash Receipt (CR)'),
    ('contra', 'Contra (Bank / Cash Transfer)'),
    ('journal', 'Journal (JV)'),
]
MFS_PROVIDERS = [('bkash', 'bKash'), ('nagad', 'Nagad'), ('rocket', 'Rocket'), ('upay', 'Upay'), ('other', 'Other')]

INSTRUMENT_FIELDS = [
    'dsl_voucher_type', 'instrument_type', 'cheque_number', 'cheque_date', 'cheque_type', 'cheque_status',
    'cheque_book_ref', 'bank_name', 'bank_branch', 'routing_number', 'party_bank_account', 'payee_name',
    'transaction_reference', 'mfs_provider', 'mfs_wallet_number', 'deposit_slip_number', 'cheque_handover_date',
    'cheque_deposit_date', 'bounce_reason', 'bank_charge_amount',
]


class DslBankInstrumentMixin(models.AbstractModel):
    _name = 'dsl.bank.instrument.mixin'
    _description = 'Bank / Cheque Instrument Details'

    dsl_voucher_type = fields.Selection(VOUCHER_TYPES, string='Voucher Type', tracking=True)
    instrument_type = fields.Selection(INSTRUMENT_TYPES, string='Payment Mode', tracking=True)
    cheque_number = fields.Char('Cheque / Instrument No.', copy=False, tracking=True, index=True)
    cheque_date = fields.Date('Cheque Date', copy=False, tracking=True,
                              help='Date written on the cheque (post-dated cheques use a future date).')
    cheque_type = fields.Selection(CHEQUE_TYPES, string='Cheque Type', default='account_payee')
    cheque_status = fields.Selection(CHEQUE_STATES, string='Cheque Status', copy=False, tracking=True)
    cheque_book_ref = fields.Char('Cheque Book / Leaf Ref.', copy=False)
    bank_name = fields.Char('Bank Name', help='Drawee bank (received cheque) or our bank (issued cheque).')
    bank_branch = fields.Char('Branch')
    routing_number = fields.Char('Routing No.', size=9, help='9-digit Bangladesh Bank routing number of the branch.')
    party_bank_account = fields.Char('Party Bank A/C No.')
    payee_name = fields.Char('Payee / Drawer Name', help='Name written on the cheque.')
    transaction_reference = fields.Char('Transaction / UTR / TrxID', copy=False, index=True,
                                        help='BEFTN / RTGS / NPSB reference or MFS transaction ID.')
    mfs_provider = fields.Selection(MFS_PROVIDERS, string='MFS Provider')
    mfs_wallet_number = fields.Char('MFS Wallet No.')
    deposit_slip_number = fields.Char('Deposit Slip No.', copy=False)
    cheque_handover_date = fields.Date('Handed Over / Received On', copy=False)
    cheque_deposit_date = fields.Date('Deposited On', copy=False)
    bounce_reason = fields.Char('Bounce / Return Reason', copy=False)

    @api.onchange('instrument_type')
    def _onchange_instrument_type(self):
        for rec in self:
            if rec.instrument_type in ('cheque', 'pay_order', 'demand_draft') and not rec.cheque_status:
                rec.cheque_status = 'draft'
            if rec.instrument_type != 'mfs':
                rec.mfs_provider = False
                rec.mfs_wallet_number = False

    def _instrument_values(self):
        self.ensure_one()
        vals = {}
        for fname in INSTRUMENT_FIELDS:
            value = self[fname]
            vals[fname] = value.id if isinstance(value, models.BaseModel) else value
        return vals


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'dsl.bank.instrument.mixin']

    bank_charge_amount = fields.Monetary('Bank Charge', currency_field='currency_id', copy=False)
    is_post_dated = fields.Boolean('Post-dated Cheque', compute='_compute_is_post_dated')

    @api.depends('cheque_date', 'date')
    def _compute_is_post_dated(self):
        for rec in self:
            rec.is_post_dated = bool(rec.cheque_date and rec.date and rec.cheque_date > rec.date)

    bank_clearance_date = fields.Date('Bank Clearance Date', compute='_compute_bank_clearance', store=True,
                                      help='Date the bank line of this entry was cleared in Bank Reconciliation.')
    is_bank_cleared = fields.Boolean('Cleared in Bank', compute='_compute_bank_clearance', store=True)
    amount_in_words = fields.Char('Amount in Words', compute='_compute_amount_in_words')

    @api.depends('line_ids.bank_date')
    def _compute_bank_clearance(self):
        for move in self:
            dates = [d for d in move.line_ids.mapped('bank_date') if d]
            move.bank_clearance_date = max(dates) if dates else False
            move.is_bank_cleared = bool(dates)

    @api.depends('amount_total', 'line_ids.debit', 'currency_id')
    def _compute_amount_in_words(self):
        for move in self:
            amount = move.amount_total or sum(move.line_ids.mapped('debit'))
            currency = move.currency_id or move.company_id.currency_id
            move.amount_in_words = currency.amount_to_text(amount) if amount and currency else False

    @api.onchange('journal_id')
    def _onchange_journal_voucher_type(self):
        for move in self:
            if move.move_type == 'entry' and not move.dsl_voucher_type:
                move.dsl_voucher_type = {'bank': 'bank_payment', 'cash': 'cash_payment'}.get(
                    move.journal_id.type, 'journal')

    def action_cheque_mark_deposited(self):
        self.write({'cheque_status': 'deposited', 'cheque_deposit_date': fields.Date.context_today(self)})

    def action_cheque_mark_bounced(self):
        self.write({'cheque_status': 'bounced'})
        for move in self:
            move.message_post(body=_('Cheque %s marked as BOUNCED. Reason: %s') % (move.cheque_number or '', move.bounce_reason or '-'))

    def action_cheque_mark_cancelled(self):
        self.write({'cheque_status': 'cancelled'})


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    cheque_number = fields.Char(related='move_id.cheque_number', string='Cheque No.', store=True, index=True)
    instrument_type = fields.Selection(related='move_id.instrument_type', string='Payment Mode', store=True)

    def write(self, vals):
        res = super().write(vals)
        if 'bank_date' in vals:
            moves = self.mapped('move_id').filtered(lambda m: m.instrument_type in ('cheque', 'pay_order', 'demand_draft'))
            for move in moves:
                if any(move.line_ids.mapped('bank_date')):
                    if move.cheque_status != 'cleared':
                        move.cheque_status = 'cleared'
                elif move.cheque_status == 'cleared':
                    move.cheque_status = 'deposited' if move.cheque_deposit_date else 'issued'
        return res


class AccountPayment(models.Model):
    _name = 'account.payment'
    _inherit = ['account.payment', 'dsl.bank.instrument.mixin']

    bank_charge_amount = fields.Monetary('Bank Charge', currency_field='currency_id', copy=False)
    is_post_dated = fields.Boolean('Post-dated Cheque', compute='_compute_is_post_dated')

    @api.depends('cheque_date', 'date')
    def _compute_is_post_dated(self):
        for rec in self:
            rec.is_post_dated = bool(rec.cheque_date and rec.date and rec.cheque_date > rec.date)

    @api.onchange('payment_type', 'journal_id')
    def _onchange_payment_voucher_type(self):
        for pay in self:
            kind = 'bank' if pay.journal_id.type == 'bank' else 'cash'
            pay.dsl_voucher_type = '%s_%s' % (kind, 'receipt' if pay.payment_type == 'inbound' else 'payment')
            if pay.instrument_type in ('cheque', 'pay_order', 'demand_draft') and pay.cheque_status in (False, 'draft', 'issued', 'received'):
                pay.cheque_status = 'received' if pay.payment_type == 'inbound' else 'issued'

    def _dsl_sync_instrument_to_move(self):
        for pay in self.filtered('move_id'):
            pay.move_id.with_context(skip_readonly_check=True).write(pay._instrument_values())

    def action_post(self):
        res = super().action_post()
        self._dsl_sync_instrument_to_move()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        pays = super().create(vals_list)
        pays._dsl_sync_instrument_to_move()
        return pays

    def write(self, vals):
        res = super().write(vals)
        if set(vals) & set(INSTRUMENT_FIELDS):
            self._dsl_sync_instrument_to_move()
        return res
