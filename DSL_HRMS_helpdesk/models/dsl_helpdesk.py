# -*- coding: utf-8 -*-
import datetime
from odoo import api, fields, models, _


def _default_current_employee(record=None):
    env = record.env if record is not None else None
    if not env:
        return False
    emp = env['hr.employee'].sudo().search([('user_id', '=', env.uid)], limit=1)
    return emp.id if emp else False


class DslHrTicketCategory(models.Model):
    _name = 'dsl.hr.ticket.category'
    _description = 'HR Helpdesk & Grievance Category'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    name = fields.Char(string='Category Name', required=True)
    code = fields.Char(string='Code', required=True)
    default_nature = fields.Selection(
        selection=[
            ('helpdesk', 'General HR Helpdesk Query'),
            ('grievance', 'Confidential Workplace Grievance (BD Labour Rules)'),
        ],
        string='Default Nature',
        default='helpdesk',
        required=True,
    )
    sla_hours = fields.Integer(string='Target SLA (Hours)', default=48, required=True)
    default_handler_id = fields.Many2one('res.users', string='Default Assigned HR Officer')


class DslHrTicket(models.Model):
    _name = 'dsl.hr.ticket'
    _description = 'Internal HR Helpdesk & Confidential Grievance Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Ticket No.',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
    )
    subject = fields.Char(string='Subject / Issue Summary', required=True, tracking=True)
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        default=_default_current_employee,
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Branch / Plant',
        domain="[('company_id', '=', company_id)]",
        index=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        related='employee_id.department_id',
        store=True,
        readonly=True,
    )
    category_id = fields.Many2one(
        'dsl.hr.ticket.category',
        string='Category',
        required=True,
        tracking=True,
    )
    ticket_nature = fields.Selection(
        selection=[
            ('helpdesk', 'HR Helpdesk Support'),
            ('grievance', 'Confidential Grievance / Complaint'),
        ],
        string='Ticket Nature',
        default='helpdesk',
        required=True,
        tracking=True,
    )
    priority = fields.Selection(
        selection=[
            ('0', 'Normal'),
            ('1', 'Medium'),
            ('2', 'High'),
            ('3', 'Urgent / Critical'),
        ],
        string='Priority',
        default='1',
        tracking=True,
    )
    assigned_to_id = fields.Many2one('res.users', string='Assigned HR Officer', tracking=True)
    sla_hours = fields.Integer(string='SLA Target (Hours)', default=48)
    sla_deadline = fields.Datetime(string='SLA Target Deadline', compute='_compute_sla_deadline', store=True)
    sla_status = fields.Selection(
        selection=[
            ('on_track', 'Within SLA'),
            ('breached', 'SLA Overdue'),
            ('met', 'Resolved Within SLA'),
        ],
        string='SLA Status',
        compute='_compute_sla_status',
    )

    description = fields.Text(string='Detailed Issue / Grievance Statement', required=True)
    resolution_summary = fields.Text(string='HR Resolution / Action Taken')
    resolved_at = fields.Datetime(string='Resolved Timestamp', readonly=True)
    satisfaction_rating = fields.Selection(
        selection=[
            ('5', '★★★★★ Excellent'),
            ('4', '★★★★☆ Good'),
            ('3', '★★★☆☆ Satisfactory'),
            ('2', '★★☆☆☆ Needs Improvement'),
            ('1', '★☆☆☆☆ Unresolved'),
        ],
        string='Employee Feedback',
    )

    state = fields.Selection(
        selection=[
            ('new', 'New'),
            ('in_progress', 'In Progress'),
            ('waiting_employee', 'Waiting Employee Info'),
            ('resolved', 'Resolved'),
            ('closed', 'Closed'),
        ],
        string='Status',
        default='new',
        required=True,
        tracking=True,
        index=True,
    )

    @api.depends('create_date', 'sla_hours')
    def _compute_sla_deadline(self):
        for rec in self:
            base_dt = rec.create_date or fields.Datetime.now()
            rec.sla_deadline = base_dt + datetime.timedelta(hours=max(rec.sla_hours or 48, 1))

    def _compute_sla_status(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.state in ('resolved', 'closed'):
                finish = rec.resolved_at or now
                rec.sla_status = 'met' if (not rec.sla_deadline or finish <= rec.sla_deadline) else 'breached'
            else:
                rec.sla_status = 'breached' if (rec.sla_deadline and now > rec.sla_deadline) else 'on_track'

    @api.onchange('category_id')
    def _onchange_category_defaults(self):
        if self.category_id:
            self.ticket_nature = self.category_id.default_nature
            self.sla_hours = self.category_id.sla_hours
            if self.category_id.default_handler_id:
                self.assigned_to_id = self.category_id.default_handler_id

    @api.onchange('employee_id')
    def _onchange_employee_org(self):
        if self.employee_id:
            self.company_id = self.employee_id.company_id.id
            self.branch_id = self.employee_id.branch_id.id if self.employee_id.branch_id else False

    @api.model_create_multi
    def create(self, vals_list):
        Employee = self.env['hr.employee'].sudo()
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.hr.ticket') or _('New')
            if vals.get('employee_id'):
                emp = Employee.browse(vals['employee_id'])
                if not vals.get('company_id') and emp.company_id:
                    vals['company_id'] = emp.company_id.id
                if not vals.get('branch_id') and emp.branch_id:
                    vals['branch_id'] = emp.branch_id.id
        return super().create(vals_list)

    def action_start_progress(self):
        for rec in self:
            vals = {'state': 'in_progress'}
            if not rec.assigned_to_id:
                vals['assigned_to_id'] = self.env.user.id
            rec.write(vals)

    def action_wait_employee(self):
        self.write({'state': 'waiting_employee'})

    def action_resolve(self):
        self.write({'state': 'resolved', 'resolved_at': fields.Datetime.now()})

    def action_close(self):
        self.write({'state': 'closed'})

