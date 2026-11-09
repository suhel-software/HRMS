# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    show_in_bank_reconciliation = fields.Boolean(
        string='Show in Bank Reconciliation',
        default=True,
        help='If checked, this bank/cash journal will appear in the Bank Reconciliation Console.'
    )
    show_in_tally_brs = fields.Boolean(
        string='Show in Bank Reconciliation (Legacy)',
        related='show_in_bank_reconciliation',
        readonly=False,
        store=True,
    )

    def action_toggle_bank_reconciliation(self):
        for rec in self:
            rec.show_in_bank_reconciliation = not rec.show_in_bank_reconciliation
        return True
