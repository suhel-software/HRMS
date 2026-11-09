# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

CONDITIONS = [
    ('new', 'New'),
    ('good', 'Good'),
    ('fair', 'Fair'),
    ('poor', 'Poor'),
    ('damaged', 'Damaged'),
    ('scrap', 'Scrap'),
]


class DslAssetAssignment(models.Model):
    _name = 'dsl.asset.assignment'
    _description = 'Fixed Asset Custody / Assignment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_assigned desc, id desc'

    name = fields.Char('Reference', readonly=True, copy=False, default=lambda self: _('New'))
    asset_id = fields.Many2one('account.asset', 'Asset', required=True, tracking=True,
                               domain="[('state', 'not in', ('model', 'cancelled', 'close')), ('parent_id', '=', False)]")
    asset_code = fields.Char(related='asset_id.asset_code', string='Asset Code')
    asset_image = fields.Image(related='asset_id.asset_image')
    employee_id = fields.Many2one('hr.employee', 'Assigned To', required=True, tracking=True)
    department_id = fields.Many2one('hr.department', 'Department', tracking=True)
    location_id = fields.Many2one('dsl.asset.location', 'Location', tracking=True)
    date_assigned = fields.Date('Handover Date', required=True, default=fields.Date.context_today, tracking=True)
    expected_return_date = fields.Date('Expected Return')
    date_returned = fields.Date('Returned On', readonly=True, tracking=True)
    condition_out = fields.Selection(CONDITIONS, 'Condition at Handover', default='good')
    condition_in = fields.Selection(CONDITIONS, 'Condition at Return')
    handover_by_id = fields.Many2one('res.users', 'Handed Over By', default=lambda self: self.env.user)
    purpose = fields.Char('Purpose')
    notes = fields.Text('Remarks')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('returned', 'Returned'),
        ('cancel', 'Cancelled'),
    ], default='draft', tracking=True, string='Status')
    company_id = fields.Many2one('res.company', related='asset_id.company_id', store=True)
    is_overdue = fields.Boolean(compute='_compute_is_overdue')

    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_overdue = bool(rec.state == 'assigned' and rec.expected_return_date and rec.expected_return_date < today)

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id and self.employee_id.department_id:
            self.department_id = self.employee_id.department_id

    @api.constrains('date_assigned', 'expected_return_date')
    def _check_dates(self):
        for rec in self:
            if rec.expected_return_date and rec.expected_return_date < rec.date_assigned:
                raise ValidationError(_('Expected return date cannot be before the handover date.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('dsl.asset.assignment') or _('New')
        return super().create(vals_list)

    def action_assign(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            # auto-close any running custody of the same asset
            running = rec.asset_id.assignment_ids.filtered(lambda a: a.state == 'assigned' and a != rec)
            running.action_return()
            vals = {'dsl_employee_id': rec.employee_id.id}
            if rec.department_id:
                vals['dsl_department_id'] = rec.department_id.id
            if rec.location_id:
                vals['dsl_location_id'] = rec.location_id.id
            rec.asset_id.write(vals)
            rec.state = 'assigned'
            rec.asset_id.message_post(body=_('Asset handed over to %(emp)s (%(ref)s).',
                                             emp=rec.employee_id.name, ref=rec.name))
        return True

    def action_return(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state != 'assigned':
                continue
            rec.write({'state': 'returned', 'date_returned': today,
                       'condition_in': rec.condition_in or rec.asset_id.asset_condition})
            if rec.asset_id.dsl_employee_id == rec.employee_id:
                vals = {'dsl_employee_id': False}
                if rec.condition_in:
                    vals['asset_condition'] = rec.condition_in
                rec.asset_id.write(vals)
            rec.asset_id.message_post(body=_('Asset returned by %(emp)s (%(ref)s).',
                                             emp=rec.employee_id.name, ref=rec.name))
        return True

    def action_cancel(self):
        if any(r.state == 'assigned' for r in self):
            raise UserError(_('Return the asset before cancelling an active assignment.'))
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.filtered(lambda r: r.state == 'cancel').write({'state': 'draft'})

    def action_print_handover(self):
        return self.env.ref('DSL_HRMS_fixed_asset.action_report_asset_handover').report_action(self)

