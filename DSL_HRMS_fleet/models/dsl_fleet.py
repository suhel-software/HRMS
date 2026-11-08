# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class DslHrVehicle(models.Model):
    _name = 'dsl.hr.vehicle'
    _description = 'Corporate Pool Vehicle & Staff Transport'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    active = fields.Boolean(default=True)
    name = fields.Char(string='Registration Plate (e.g. Dhaka Metro-Ga-35-8821)', required=True, tracking=True)
    vehicle_model = fields.Char(string='Make & Model (e.g. Toyota Noah / HiAce)', required=True)
    vehicle_type = fields.Selection(
        selection=[
            ('sedan_suv', 'Executive Sedan / SUV'),
            ('microbus', 'Microbus / Staff Pool'),
            ('coaster_bus', 'Staff Bus / Coaster'),
            ('pickup_van', 'Delivery / Factory Pickup'),
        ],
        string='Category',
        default='microbus',
        required=True,
    )
    driver_employee_id = fields.Many2one('hr.employee', string='Assigned Driver')
    driver_mobile = fields.Char(string='Driver Contact')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    odometer_km = fields.Float(string='Current Odometer (KM)', default=12500.0)


class DslVehicleRequisition(models.Model):
    _name = 'dsl.vehicle.requisition'
    _description = 'Employee Official Vehicle Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'trip_date desc, id desc'

    name = fields.Char(string='Req. No.', required=True, copy=False, readonly=True, default=lambda self: _('New'), index=True)
    employee_id = fields.Many2one('hr.employee', string='Requesting Employee', required=True, index=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company, index=True)
    branch_id = fields.Many2one('dsl.branch', string='Branch / Plant', domain="[('company_id', '=', company_id)]")
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', store=True, readonly=True)

    trip_date = fields.Date(string='Trip Date', default=fields.Date.context_today, required=True, tracking=True)
    pickup_location = fields.Char(string='Pickup Point', default='Corporate Head Office (Gulshan)', required=True)
    destination = fields.Char(string='Destination / Client / Plant', required=True)
    passengers = fields.Integer(string='Passengers', default=1)
    purpose = fields.Char(string='Official Trip Purpose', required=True)

    vehicle_id = fields.Many2one('dsl.hr.vehicle', string='Allocated Pool Vehicle', tracking=True)
    distance_km = fields.Float(string='Logged Trip Distance (KM)', default=0.0)

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('requested', 'Pending Transport Desk'),
            ('allocated', 'Vehicle Allocated'),
            ('completed', 'Trip Completed'),
            ('rejected', 'Declined'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    @api.onchange('employee_id')
    def _onchange_emp_sync(self):
        if self.employee_id:
            self.company_id = self.employee_id.company_id.id
            self.branch_id = self.employee_id.branch_id.id if self.employee_id.branch_id else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.vehicle.requisition') or _('New')
        return super().create(vals_list)

    def action_submit(self):
        self.write({'state': 'requested'})

    def action_allocate(self):
        for rec in self:
            if not rec.vehicle_id:
                veh = self.env['dsl.hr.vehicle'].sudo().search([('company_id', '=', rec.company_id.id)], limit=1)
                if veh:
                    rec.vehicle_id = veh.id
            rec.state = 'allocated'

    def action_complete(self):
        for rec in self:
            if rec.vehicle_id and rec.distance_km > 0:
                rec.vehicle_id.sudo().odometer_km += rec.distance_km
            rec.state = 'completed'


class DslVehicleFuelLog(models.Model):
    _name = 'dsl.vehicle.fuel.log'
    _description = 'Corporate Vehicle Fuel (Octane / Diesel / CNG / LPG) Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'refuel_date desc, id desc'

    name = fields.Char(string='Fuel Voucher', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    vehicle_id = fields.Many2one('dsl.hr.vehicle', string='Vehicle', required=True, index=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    refuel_date = fields.Date(string='Date', default=fields.Date.context_today, required=True)
    fuel_type = fields.Selection(
        selection=[
            ('octane', 'Octane (Liters)'),
            ('diesel', 'Diesel (Liters)'),
            ('cng', 'CNG (Cubic Meters)'),
            ('lpg', 'Autogas / LPG (Liters)'),
        ],
        string='Fuel Type',
        default='octane',
        required=True,
    )
    quantity = fields.Float(string='Quantity (L / m³)', default=25.0, required=True)
    unit_price = fields.Float(string='Rate (৳)', default=130.0, required=True)
    total_cost = fields.Monetary(string='Total Fuel Bill (৳)', currency_field='currency_id', compute='_compute_cost', store=True, tracking=True)
    odometer_reading = fields.Float(string='Odometer Reading (KM)')
    station_name = fields.Char(string='Filling Station / Vendor')

    @api.depends('quantity', 'unit_price')
    def _compute_cost(self):
        for rec in self:
            rec.total_cost = round((rec.quantity or 0.0) * (rec.unit_price or 0.0), 2)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.vehicle.fuel.log') or _('New')
        return super().create(vals_list)

