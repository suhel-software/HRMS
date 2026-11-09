# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DslAssetLocation(models.Model):
    _name = 'dsl.asset.location'
    _description = 'Fixed Asset Location'
    _parent_name = 'parent_id'
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'

    name = fields.Char('Location Name', required=True)
    code = fields.Char('Code')
    complete_name = fields.Char('Full Location', compute='_compute_complete_name', store=True, recursive=True)
    parent_id = fields.Many2one('dsl.asset.location', 'Parent Location', index=True, ondelete='restrict')
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('dsl.asset.location', 'parent_id', 'Sub Locations')
    location_type = fields.Selection([
        ('site', 'Site / Campus'),
        ('building', 'Building'),
        ('floor', 'Floor'),
        ('room', 'Room / Office'),
        ('warehouse', 'Warehouse / Store'),
        ('factory', 'Factory / Production Floor'),
        ('vehicle', 'Vehicle'),
        ('other', 'Other'),
    ], string='Location Type', default='room', required=True)
    address = fields.Text('Address / Description')
    manager_id = fields.Many2one('hr.employee', 'Location In-Charge')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    color = fields.Integer('Color')

    asset_ids = fields.One2many('account.asset', 'dsl_location_id', 'Asset Records')
    asset_count = fields.Integer('Assets', compute='_compute_asset_stats')
    asset_value = fields.Monetary('Gross Value', compute='_compute_asset_stats', currency_field='currency_id')
    asset_book_value = fields.Monetary('Net Book Value', compute='_compute_asset_stats', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', compute='_compute_currency')

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)', 'Location code must be unique per company!'),
    ]

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for loc in self:
            if loc.parent_id:
                loc.complete_name = '%s / %s' % (loc.parent_id.complete_name, loc.name)
            else:
                loc.complete_name = loc.name

    def _compute_currency(self):
        for loc in self:
            loc.currency_id = (loc.company_id or self.env.company).currency_id

    def _compute_asset_stats(self):
        Asset = self.env['account.asset']
        for loc in self:
            assets = Asset.search([
                ('dsl_location_id', 'child_of', loc.id),
                ('state', 'not in', ('model', 'cancelled')),
                ('parent_id', '=', False),
            ]) if loc.id else Asset
            loc.asset_count = len(assets)
            loc.asset_value = sum(assets.mapped('original_value'))
            loc.asset_book_value = sum(assets.mapped('book_value'))

    @api.constrains('parent_id')
    def _check_parent_recursion(self):
        if self._has_cycle():
            raise ValidationError(_('You cannot create recursive locations.'))

    def action_view_assets(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('DSL_HRMS_fixed_asset.action_dsl_fixed_asset_register')
        action['domain'] = [('dsl_location_id', 'child_of', self.id), ('state', '!=', 'model'), ('parent_id', '=', False)]
        action['context'] = {'default_dsl_location_id': self.id}
        action['name'] = _('Assets at %s', self.complete_name)
        return action

