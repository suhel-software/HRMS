# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DslAssetMaintenance(models.Model):
    _name = 'dsl.asset.maintenance'
    _description = 'Fixed Asset Maintenance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scheduled_date desc, id desc'

    name = fields.Char('Reference', readonly=True, copy=False, default=lambda self: _('New'))
    title = fields.Char('Subject', required=True, tracking=True)
    asset_id = fields.Many2one('account.asset', 'Asset', required=True, tracking=True,
                               domain="[('state', 'not in', ('model', 'cancelled')), ('parent_id', '=', False)]")
    asset_code = fields.Char(related='asset_id.asset_code')
    asset_location_id = fields.Many2one(related='asset_id.dsl_location_id', string='Location', store=True)
    maintenance_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective / Breakdown'),
        ('calibration', 'Calibration'),
        ('inspection', 'Inspection / Safety Check'),
        ('upgrade', 'Upgrade / Overhaul'),
    ], string='Type', default='preventive', required=True, tracking=True)
    priority = fields.Selection([
        ('0', 'Normal'), ('1', 'Important'), ('2', 'Urgent'), ('3', 'Critical'),
    ], default='0', string='Priority')
    scheduled_date = fields.Date('Scheduled Date', default=fields.Date.context_today, tracking=True)
    start_date = fields.Date('Started On', readonly=True, copy=False)
    completion_date = fields.Date('Completed On', readonly=True, copy=False, tracking=True)
    downtime_hours = fields.Float('Downtime (Hours)')

    vendor_id = fields.Many2one('res.partner', 'Service Vendor')
    technician_id = fields.Many2one('hr.employee', 'Technician')
    responsible_user_id = fields.Many2one('res.users', 'Responsible', default=lambda self: self.env.user)
    under_warranty = fields.Boolean('Covered by Warranty', compute='_compute_under_warranty', store=True, readonly=False)

    currency_id = fields.Many2one('res.currency', related='asset_id.currency_id')
    labour_cost = fields.Monetary('Labour Cost', currency_field='currency_id')
    parts_cost = fields.Monetary('Spare Parts Cost', currency_field='currency_id')
    other_cost = fields.Monetary('Other Cost', currency_field='currency_id')
    cost = fields.Monetary('Total Cost', compute='_compute_cost', store=True, currency_field='currency_id')
    vendor_bill_id = fields.Many2one('account.move', 'Vendor Bill', readonly=True, copy=False)

    description = fields.Html('Problem / Work Description')
    resolution = fields.Html('Work Done / Resolution')

    recurring = fields.Boolean('Recurring Maintenance')
    interval_number = fields.Integer('Repeat Every', default=3)
    interval_type = fields.Selection([
        ('days', 'Days'), ('weeks', 'Weeks'), ('months', 'Months'), ('years', 'Years'),
    ], default='months', string='Interval Unit')
    next_maintenance_id = fields.Many2one('dsl.asset.maintenance', 'Next Maintenance', readonly=True, copy=False)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('done', 'Completed'),
        ('cancel', 'Cancelled'),
    ], default='draft', tracking=True, string='Status')
    company_id = fields.Many2one('res.company', related='asset_id.company_id', store=True)
    is_overdue = fields.Boolean(compute='_compute_is_overdue')
    color = fields.Integer(compute='_compute_is_overdue')

    @api.depends('labour_cost', 'parts_cost', 'other_cost')
    def _compute_cost(self):
        for rec in self:
            rec.cost = (rec.labour_cost or 0.0) + (rec.parts_cost or 0.0) + (rec.other_cost or 0.0)

    @api.depends('asset_id.warranty_end_date', 'scheduled_date')
    def _compute_under_warranty(self):
        for rec in self:
            end = rec.asset_id.warranty_end_date
            rec.under_warranty = bool(end and rec.scheduled_date and rec.scheduled_date <= end)

    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_overdue = bool(rec.state in ('draft', 'scheduled') and rec.scheduled_date and rec.scheduled_date < today)
            rec.color = 1 if rec.is_overdue else (10 if rec.state == 'done' else 0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('dsl.asset.maintenance') or _('New')
        return super().create(vals_list)

    def action_schedule(self):
        self.write({'state': 'scheduled'})

    def action_start(self):
        self.write({'state': 'in_progress', 'start_date': fields.Date.context_today(self)})

    def _next_date(self):
        self.ensure_one()
        from dateutil.relativedelta import relativedelta
        base = self.completion_date or self.scheduled_date or fields.Date.context_today(self)
        n = max(self.interval_number or 1, 1)
        return base + relativedelta(**{self.interval_type or 'months': n})

    def action_done(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.write({'state': 'done', 'completion_date': today, 'start_date': rec.start_date or today})
            if rec.recurring and not rec.next_maintenance_id:
                nxt = rec.copy({
                    'scheduled_date': rec._next_date(),
                    'state': 'scheduled',
                    'labour_cost': 0.0, 'parts_cost': 0.0, 'other_cost': 0.0,
                    'resolution': False,
                })
                rec.next_maintenance_id = nxt.id
            rec.asset_id.message_post(body=_('Maintenance %(ref)s completed. Cost: %(cost).2f',
                                             ref=rec.name, cost=rec.cost))
        return True

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_create_vendor_bill(self):
        self.ensure_one()
        if self.vendor_bill_id:
            return self.action_open_vendor_bill()
        if not self.vendor_id:
            raise UserError(_('Please set the Service Vendor before creating a bill.'))
        if not self.cost:
            raise UserError(_('Maintenance cost is zero; nothing to bill.'))
        lines = []
        for label, amount in ((_('Labour'), self.labour_cost), (_('Spare Parts'), self.parts_cost),
                              (_('Other Charges'), self.other_cost)):
            if amount:
                lines.append((0, 0, {'name': '%s - %s (%s)' % (self.name, label, self.asset_id.display_name),
                                     'quantity': 1, 'price_unit': amount}))
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor_id.id,
            'invoice_date': self.completion_date or fields.Date.context_today(self),
            'ref': self.name,
            'invoice_line_ids': lines,
        })
        self.vendor_bill_id = bill.id
        return self.action_open_vendor_bill()

    def action_open_vendor_bill(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.vendor_bill_id.id,
            'view_mode': 'form',
            'name': _('Vendor Bill'),
        }
