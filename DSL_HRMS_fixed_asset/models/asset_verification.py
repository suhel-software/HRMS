# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DslAssetVerification(models.Model):
    _name = 'dsl.asset.verification'
    _description = 'Fixed Asset Physical Verification (Audit)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char('Audit No.', readonly=True, copy=False, default=lambda self: _('New'))
    title = fields.Char('Audit Title', required=True, default=lambda self: _('Physical Asset Verification'))
    date = fields.Date('Verification Date', default=fields.Date.context_today, required=True)
    location_id = fields.Many2one('dsl.asset.location', 'Location (incl. sub-locations)')
    department_id = fields.Many2one('hr.department', 'Department')
    asset_group_id = fields.Many2one('account.asset.group', 'Asset Group')
    auditor_ids = fields.Many2many('hr.employee', string='Audit Team')
    responsible_user_id = fields.Many2one('res.users', 'Lead Auditor', default=lambda self: self.env.user)
    line_ids = fields.One2many('dsl.asset.verification.line', 'verification_id', 'Assets')
    notes = fields.Html('Audit Observations')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Completed'),
        ('cancel', 'Cancelled'),
    ], default='draft', tracking=True, string='Status')

    total_count = fields.Integer('Total', compute='_compute_summary')
    found_count = fields.Integer('Found', compute='_compute_summary')
    missing_count = fields.Integer('Missing', compute='_compute_summary')
    damaged_count = fields.Integer('Damaged', compute='_compute_summary')
    relocated_count = fields.Integer('Relocated', compute='_compute_summary')
    pending_count = fields.Integer('Pending', compute='_compute_summary')
    completion_rate = fields.Float('Progress (%)', compute='_compute_summary')

    @api.depends('line_ids.result')
    def _compute_summary(self):
        for rec in self:
            lines = rec.line_ids
            rec.total_count = len(lines)
            rec.found_count = len(lines.filtered(lambda l: l.result == 'found'))
            rec.missing_count = len(lines.filtered(lambda l: l.result == 'missing'))
            rec.damaged_count = len(lines.filtered(lambda l: l.result == 'damaged'))
            rec.relocated_count = len(lines.filtered(lambda l: l.result == 'relocated'))
            rec.pending_count = len(lines.filtered(lambda l: l.result == 'pending'))
            rec.completion_rate = round((rec.total_count - rec.pending_count) / rec.total_count * 100.0, 1) \
                if rec.total_count else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('dsl.asset.verification') or _('New')
        return super().create(vals_list)

    def action_load_assets(self):
        for rec in self:
            domain = [('state', 'in', ('draft', 'open', 'paused')), ('parent_id', '=', False),
                      ('company_id', '=', rec.company_id.id)]
            if rec.location_id:
                domain.append(('dsl_location_id', 'child_of', rec.location_id.id))
            if rec.department_id:
                domain.append(('dsl_department_id', '=', rec.department_id.id))
            if rec.asset_group_id:
                domain.append(('asset_group_id', '=', rec.asset_group_id.id))
            existing = rec.line_ids.mapped('asset_id')
            assets = self.env['account.asset'].search(domain) - existing
            rec.write({'line_ids': [(0, 0, {
                'asset_id': a.id,
                'expected_location_id': a.dsl_location_id.id,
                'expected_employee_id': a.dsl_employee_id.id,
                'found_location_id': a.dsl_location_id.id,
                'condition': a.asset_condition,
            }) for a in assets]})
        return True

    def action_start(self):
        for rec in self:
            if not rec.line_ids:
                rec.action_load_assets()
            if not rec.line_ids:
                raise UserError(_('No assets match the selected scope.'))
        self.write({'state': 'in_progress'})

    def action_mark_all_found(self):
        self.mapped('line_ids').filtered(lambda l: l.result == 'pending').write({'result': 'found'})

    def action_done(self):
        for rec in self:
            if rec.pending_count:
                raise UserError(_('%s asset(s) are still pending verification.', rec.pending_count))
            for line in rec.line_ids:
                vals = {'last_verified_date': rec.date}
                if line.result == 'relocated' and line.found_location_id:
                    vals['dsl_location_id'] = line.found_location_id.id
                if line.condition:
                    vals['asset_condition'] = line.condition
                if line.result == 'damaged':
                    vals['asset_condition'] = 'damaged'
                line.asset_id.write(vals)
                if line.result == 'missing':
                    line.asset_id.message_post(body=_('Reported MISSING in physical verification %s.', rec.name))
            rec.state = 'done'
        return True

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})


class DslAssetVerificationLine(models.Model):
    _name = 'dsl.asset.verification.line'
    _description = 'Physical Verification Line'
    _order = 'result, id'

    verification_id = fields.Many2one('dsl.asset.verification', required=True, ondelete='cascade')
    asset_id = fields.Many2one('account.asset', 'Asset', required=True)
    asset_code = fields.Char(related='asset_id.asset_code')
    serial_number = fields.Char(related='asset_id.serial_number')
    book_value = fields.Monetary(related='asset_id.book_value')
    currency_id = fields.Many2one(related='asset_id.currency_id')
    expected_location_id = fields.Many2one('dsl.asset.location', 'Expected Location')
    expected_employee_id = fields.Many2one('hr.employee', 'Expected Custodian')
    found_location_id = fields.Many2one('dsl.asset.location', 'Found At')
    result = fields.Selection([
        ('pending', 'Pending'),
        ('found', 'Found OK'),
        ('relocated', 'Found - Relocated'),
        ('damaged', 'Found - Damaged'),
        ('missing', 'Missing'),
    ], default='pending', required=True, string='Result')
    condition = fields.Selection([
        ('new', 'New'), ('good', 'Good'), ('fair', 'Fair'),
        ('poor', 'Poor'), ('damaged', 'Damaged'), ('scrap', 'Scrap'),
    ], string='Condition')
    remarks = fields.Char('Remarks')
    state = fields.Selection(related='verification_id.state')
    date = fields.Date(related='verification_id.date', store=True)

    @api.onchange('found_location_id')
    def _onchange_found_location(self):
        if self.found_location_id and self.expected_location_id and self.found_location_id != self.expected_location_id:
            self.result = 'relocated'

