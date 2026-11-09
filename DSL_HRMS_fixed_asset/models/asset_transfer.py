# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DslAssetTransfer(models.Model):
    _name = 'dsl.asset.transfer'
    _description = 'Fixed Asset Transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'transfer_date desc, id desc'

    name = fields.Char('Transfer No.', readonly=True, copy=False, default=lambda self: _('New'))
    asset_id = fields.Many2one('account.asset', 'Asset', required=True, tracking=True,
                               domain="[('state', 'not in', ('model', 'cancelled', 'close')), ('parent_id', '=', False)]")
    asset_code = fields.Char(related='asset_id.asset_code')
    asset_image = fields.Image(related='asset_id.asset_image')
    transfer_type = fields.Selection([
        ('location', 'Location Change'),
        ('department', 'Inter-Department'),
        ('employee', 'Employee Custody Change'),
        ('branch', 'Inter-Branch / Unit'),
        ('company', 'Inter-Company'),
    ], string='Transfer Type', default='location', required=True, tracking=True)
    transfer_date = fields.Date('Transfer Date', default=fields.Date.context_today, required=True, tracking=True)

    from_location_id = fields.Many2one('dsl.asset.location', 'From Location', readonly=True)
    from_department_id = fields.Many2one('hr.department', 'From Department', readonly=True)
    from_employee_id = fields.Many2one('hr.employee', 'From Custodian', readonly=True)

    to_location_id = fields.Many2one('dsl.asset.location', 'To Location', tracking=True)
    to_department_id = fields.Many2one('hr.department', 'To Department', tracking=True)
    to_employee_id = fields.Many2one('hr.employee', 'To Custodian', tracking=True)

    reason = fields.Text('Reason for Transfer')
    requested_by_id = fields.Many2one('res.users', 'Requested By', default=lambda self: self.env.user, readonly=True)
    approved_by_id = fields.Many2one('res.users', 'Approved By', readonly=True, copy=False)
    approval_date = fields.Datetime('Approved On', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Waiting Approval'),
        ('approved', 'Approved'),
        ('done', 'Transferred'),
        ('rejected', 'Rejected'),
        ('cancel', 'Cancelled'),
    ], default='draft', tracking=True, string='Status')
    company_id = fields.Many2one('res.company', related='asset_id.company_id', store=True)

    @api.onchange('asset_id')
    def _onchange_asset_id(self):
        for rec in self:
            rec.from_location_id = rec.asset_id.dsl_location_id
            rec.from_department_id = rec.asset_id.dsl_department_id
            rec.from_employee_id = rec.asset_id.dsl_employee_id

    @api.onchange('to_employee_id')
    def _onchange_to_employee_id(self):
        if self.to_employee_id and self.to_employee_id.department_id and not self.to_department_id:
            self.to_department_id = self.to_employee_id.department_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('dsl.asset.transfer') or _('New')
            if vals.get('asset_id'):
                asset = self.env['account.asset'].browse(vals['asset_id'])
                vals.setdefault('from_location_id', asset.dsl_location_id.id)
                vals.setdefault('from_department_id', asset.dsl_department_id.id)
                vals.setdefault('from_employee_id', asset.dsl_employee_id.id)
        return super().create(vals_list)

    def _check_destination(self):
        for rec in self:
            if not (rec.to_location_id or rec.to_department_id or rec.to_employee_id):
                raise UserError(_('Please set at least one destination (location, department or custodian).'))

    def action_submit(self):
        self._check_destination()
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved', 'approved_by_id': self.env.uid, 'approval_date': fields.Datetime.now()})

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_done(self):
        self._check_destination()
        for rec in self:
            if rec.state not in ('approved', 'draft', 'submitted'):
                continue
            vals = {}
            if rec.to_location_id:
                vals['dsl_location_id'] = rec.to_location_id.id
            if rec.to_department_id:
                vals['dsl_department_id'] = rec.to_department_id.id
            if rec.to_employee_id and rec.to_employee_id != rec.asset_id.dsl_employee_id:
                running = rec.asset_id.assignment_ids.filtered(lambda a: a.state == 'assigned')
                running.action_return()
                assignment = self.env['dsl.asset.assignment'].create({
                    'asset_id': rec.asset_id.id,
                    'employee_id': rec.to_employee_id.id,
                    'department_id': (rec.to_department_id or rec.to_employee_id.department_id).id,
                    'location_id': (rec.to_location_id or rec.asset_id.dsl_location_id).id,
                    'date_assigned': rec.transfer_date,
                    'condition_out': rec.asset_id.asset_condition,
                    'purpose': _('Transfer %s', rec.name),
                })
                assignment.action_assign()
            if vals:
                rec.asset_id.write(vals)
            if not rec.approved_by_id:
                rec.write({'approved_by_id': self.env.uid, 'approval_date': fields.Datetime.now()})
            rec.state = 'done'
            rec.asset_id.message_post(body=_('Asset transferred via %s.', rec.name))
        return True

    def action_cancel(self):
        if any(r.state == 'done' for r in self):
            raise UserError(_('A completed transfer cannot be cancelled.'))
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.filtered(lambda r: r.state in ('cancel', 'rejected')).write({'state': 'draft'})

