# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class DslVisitorPass(models.Model):
    _name = 'dsl.visitor.pass'
    _description = 'Corporate & Factory Gate Visitor Pass & Security Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'visit_date desc, id desc'

    name = fields.Char(string='Gate Pass No.', required=True, copy=False, readonly=True, default=lambda self: _('New'), index=True)
    visitor_name = fields.Char(string='Visitor Full Name', required=True, tracking=True)
    visitor_mobile = fields.Char(string='Mobile No.', required=True)
    visitor_org = fields.Char(string='Organization / Buyer / Vendor')
    nid_or_passport = fields.Char(string='NID / Passport / Driving License')
    badge_card_no = fields.Char(string='Physical Visitor Card #')

    host_employee_id = fields.Many2one('hr.employee', string='Host Employee', required=True, index=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company, index=True)
    branch_id = fields.Many2one('dsl.branch', string='Premises / Factory Gate', domain="[('company_id', '=', company_id)]")

    visit_date = fields.Date(string='Visit Date', default=fields.Date.context_today, required=True)
    purpose = fields.Selection(
        selection=[
            ('business_meeting', 'Business / Buyer Meeting'),
            ('interview', 'Candidate Interview'),
            ('vendor_delivery', 'Vendor / Material Delivery'),
            ('audit_inspection', 'Compliance / Govt Inspection'),
            ('personal', 'Official Guest'),
        ],
        string='Visit Category',
        default='business_meeting',
        required=True,
    )
    carried_items = fields.Char(string='Carried Devices / Laptop Serial')
    check_in_time = fields.Datetime(string='Gate Check-In', readonly=True)
    check_out_time = fields.Datetime(string='Gate Check-Out', readonly=True)

    state = fields.Selection(
        selection=[
            ('pre_registered', 'Pre-Registered'),
            ('checked_in', 'Inside Premises'),
            ('checked_out', 'Checked Out'),
            ('denied', 'Entry Denied'),
        ],
        string='Security Status',
        default='pre_registered',
        required=True,
        tracking=True,
    )

    @api.onchange('host_employee_id')
    def _onchange_host_sync(self):
        if self.host_employee_id:
            self.company_id = self.host_employee_id.company_id.id
            self.branch_id = self.host_employee_id.branch_id.id if self.host_employee_id.branch_id else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.visitor.pass') or _('New')
        return super().create(vals_list)

    def action_gate_check_in(self):
        self.write({'state': 'checked_in', 'check_in_time': fields.Datetime.now()})

    def action_gate_check_out(self):
        self.write({'state': 'checked_out', 'check_out_time': fields.Datetime.now()})

    def action_deny_entry(self):
        self.write({'state': 'denied'})

