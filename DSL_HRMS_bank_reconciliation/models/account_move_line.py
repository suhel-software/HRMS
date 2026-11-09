# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_bank_clearing_entry = fields.Boolean(
        string='Is Bank Clearing Entry',
        default=False,
        copy=False,
        index=True,
        help='True if this entry was automatically created by DSL Bank Reconciliation to clear interim balances into the bank account.'
    )
    cleared_source_line_ids = fields.One2many(
        'account.move.line',
        'clearing_move_id',
        string='Cleared Source Lines'
    )


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    bank_date = fields.Date(
        string='Bank Clearance Date',
        copy=False,
        index=True,
        help='Date when this transaction appeared/cleared in the bank statement.'
    )
    clearing_move_id = fields.Many2one(
        'account.move',
        string='Clearing Journal Entry',
        readonly=True,
        copy=False,
        index=True,
        help='The clearing journal entry generated when this transaction was reconciled with the bank.'
    )
    is_bank_clearing_line = fields.Boolean(
        related='move_id.is_bank_clearing_entry',
        store=True,
        index=True,
    )
