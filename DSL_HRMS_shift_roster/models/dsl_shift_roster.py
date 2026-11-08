# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DslHrShift(models.Model):
    _name = 'dsl.hr.shift'
    _description = 'Work Shift Definition (General / Morning / Evening / Night)'
    _inherit = ['dsl.company.branch.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'sequence, code'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Shift Name', required=True, tracking=True)
    code = fields.Char(string='Shift Code', required=True, tracking=True)
    company_id = fields.Many2one(required=False, help='Leave empty to share shift across group companies.')
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    shift_type = fields.Selection(
        selection=[
            ('general', 'General Day Shift'),
            ('morning', 'Morning Shift (A)'),
            ('evening', 'Evening Shift (B)'),
            ('night', 'Night Shift (C — Cross Midnight)'),
            ('rotational', 'Rotational / Split Shift'),
        ],
        string='Shift Category',
        default='general',
        required=True,
        tracking=True,
    )
    start_hour = fields.Float(string='Start Time (24h)', required=True, default=9.0, tracking=True)
    end_hour = fields.Float(string='End Time (24h)', required=True, default=18.0, tracking=True)
    break_duration = fields.Float(string='Break / Meal Interval (Hours)', default=1.0)
    is_night_shift = fields.Boolean(
        string='Crosses Midnight (Night Shift)',
        compute='_compute_shift_duration',
        store=True,
    )
    scheduled_work_hours = fields.Float(
        string='Net Duty Hours',
        compute='_compute_shift_duration',
        store=True,
    )
    grace_in_minutes = fields.Integer(string='Late In Grace (Mins)', default=15)
    grace_out_minutes = fields.Integer(string='Early Out Grace (Mins)', default=10)
    half_day_hours = fields.Float(string='Half-Day Minimum Hours', default=4.0)
    night_allowance_bdt = fields.Monetary(
        string='Night Shift Allowance (৳)',
        currency_field='currency_id',
        default=0.0,
        help='Optional night tiffin/shift allowance per attended night shift.',
    )
    color = fields.Integer(string='Calendar Color Index', default=1)
    active = fields.Boolean(default=True)
    resource_calendar_id = fields.Many2one(
        'resource.calendar',
        string='Odoo Working Schedule',
        ondelete='set null',
        help='Automatically synchronized native Odoo resource.calendar working schedule.',
    )

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)', 'Shift Code must be unique per Company!'),
    ]

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for s in self:
            s.display_name = f"[{s.code}] {s.name}" if s.code else (s.name or '')

    @api.depends('start_hour', 'end_hour', 'break_duration')
    def _compute_shift_duration(self):
        for s in self:
            if s.end_hour <= s.start_hour:
                gross = (24.0 - s.start_hour) + s.end_hour
                s.is_night_shift = True
            else:
                gross = s.end_hour - s.start_hour
                s.is_night_shift = False
            s.scheduled_work_hours = round(max(gross - (s.break_duration or 0.0), 0.0), 2)

    def _sync_to_odoo_resource_calendar(self):
        if self.env.context.get('skip_dsl_shift_sync') or 'resource.calendar' not in self.env:
            return
        Calendar = self.env['resource.calendar'].sudo().with_context(skip_dsl_shift_sync=True)
        for s in self.sudo():
            cal_name = f"[{s.code}] {s.name}" if s.code else s.name
            cal_vals = {
                'name': cal_name,
                'company_id': s.company_id.id if s.company_id else False,
                'hours_per_day': s.scheduled_work_hours or 8.0,
                'tz': 'Asia/Dhaka',
            }
            if 'dsl_shift_id' in Calendar._fields:
                cal_vals['dsl_shift_id'] = s.id

            if s.resource_calendar_id:
                s.resource_calendar_id.sudo().with_context(skip_dsl_shift_sync=True).write(cal_vals)
            else:
                existing_cal = Calendar.search([('name', '=', cal_name)], limit=1)
                if existing_cal:
                    existing_cal.write(cal_vals)
                    s.with_context(skip_dsl_shift_sync=True).write({'resource_calendar_id': existing_cal.id})
                else:
                    att_lines = []
                    h_from = s.start_hour if s.start_hour < s.end_hour else 9.0
                    h_to = s.end_hour if s.end_hour > s.start_hour else 18.0
                    # Bangladesh standard working days: Sat(5), Sun(6), Mon(0), Tue(1), Wed(2), Thu(3) — Fri(4) off
                    for dow, dlabel in [('5', 'Saturday'), ('6', 'Sunday'), ('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'), ('3', 'Thursday')]:
                        att_lines.append((0, 0, {
                            'name': f"{dlabel} ({s.code})",
                            'dayofweek': dow,
                            'hour_from': h_from,
                            'hour_to': h_to,
                            'day_period': 'morning',
                        }))
                    cal_vals['attendance_ids'] = att_lines
                    created_cal = Calendar.create(cal_vals)
                    s.with_context(skip_dsl_shift_sync=True).write({'resource_calendar_id': created_cal.id})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_to_odoo_resource_calendar()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_dsl_shift_sync') and any(
            k in vals for k in ('name', 'code', 'start_hour', 'end_hour', 'break_duration', 'company_id')
        ):
            self._sync_to_odoo_resource_calendar()
        return res


class ResourceCalendarDslShiftExt(models.Model):
    _inherit = 'resource.calendar'

    dsl_shift_id = fields.Many2one(
        'dsl.hr.shift',
        string='DSL Shift Definition',
        ondelete='set null',
    )


class DslShiftRoster(models.Model):
    _name = 'dsl.shift.roster'
    _description = 'Employee Daily Shift Roster Schedule'
    _inherit = ['dsl.company.branch.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'roster_date desc, employee_id'

    name = fields.Char(string='Roster Slot', compute='_compute_name', store=True)
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        index=True,
        tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    department_id = fields.Many2one(
        'hr.department',
        related='employee_id.department_id',
        store=True,
        readonly=True,
    )
    shift_id = fields.Many2one(
        'dsl.hr.shift',
        string='Assigned Shift',
        required=True,
        tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    roster_date = fields.Date(
        string='Roster Date',
        required=True,
        default=fields.Date.context_today,
        index=True,
        tracking=True,
    )
    is_off_day = fields.Boolean(string='Weekly Rest / Off Day', default=False, tracking=True)
    batch_id = fields.Many2one('dsl.shift.roster.batch', string='Roster Batch', ondelete='set null')
    color = fields.Integer(related='shift_id.color', readonly=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('published', 'Published'),
            ('swapped', 'Shift Swapped'),
        ],
        string='Status',
        default='published',
        required=True,
        tracking=True,
    )
    notes = fields.Char(string='Supervisor Note')

    _sql_constraints = [
        (
            'emp_roster_date_uniq',
            'unique(employee_id, roster_date)',
            'An employee can only have one shift roster assignment per date!',
        ),
    ]

    @api.depends('employee_id', 'shift_id', 'roster_date', 'is_off_day')
    def _compute_name(self):
        for rec in self:
            emp_name = rec.employee_id.name or ''
            sh_code = 'OFF' if rec.is_off_day else (rec.shift_id.code or rec.shift_id.name or '')
            dt_s = rec.roster_date.strftime('%d %b %Y') if rec.roster_date else ''
            rec.name = f"{emp_name} — {sh_code} ({dt_s})"

    @api.onchange('employee_id')
    def _onchange_employee_sync(self):
        if self.employee_id:
            self.company_id = self.employee_id.company_id or self.env.company
            self.branch_id = self.employee_id.branch_id
            if self.employee_id.default_shift_id and not self.shift_id:
                self.shift_id = self.employee_id.default_shift_id

    @api.model_create_multi
    def create(self, vals_list):
        Employee = self.env['hr.employee'].sudo()
        for vals in vals_list:
            if vals.get('employee_id'):
                emp = Employee.browse(vals['employee_id'])
                if not vals.get('company_id') and emp.company_id:
                    vals['company_id'] = emp.company_id.id
                if not vals.get('branch_id') and emp.branch_id:
                    vals['branch_id'] = emp.branch_id.id
        records = super().create(vals_list)
        records._recompute_linked_attendance()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ('shift_id', 'is_off_day', 'state', 'roster_date')):
            self._recompute_linked_attendance()
        return res

    def _recompute_linked_attendance(self):
        AttLog = self.env['dsl.attendance.log'].sudo()
        for rec in self.sudo():
            logs = AttLog.search([
                ('employee_id', '=', rec.employee_id.id),
                ('attendance_date', '=', rec.roster_date),
            ])
            if logs:
                logs._compute_attendance_metrics()
                logs._compute_attendance_status()

    def action_publish(self):
        self.write({'state': 'published'})


class DslShiftRosterBatch(models.Model):
    _name = 'dsl.shift.roster.batch'
    _description = 'Bulk Shift Roster Generator'
    _inherit = ['dsl.company.branch.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    name = fields.Char(string='Batch Title', required=True, tracking=True)
    department_id = fields.Many2one(
        'hr.department',
        string='Filter Department (Optional)',
        domain="[('company_id', '=', company_id)]",
    )
    shift_id = fields.Many2one(
        'dsl.hr.shift',
        string='Shift to Assign',
        required=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    date_from = fields.Date(string='From Date', required=True, default=fields.Date.context_today)
    date_to = fields.Date(
        string='To Date',
        required=True,
        default=lambda self: fields.Date.context_today(self) + timedelta(days=6),
    )
    off_weekday = fields.Selection(
        selection=[
            ('4', 'Friday (Bangladesh Weekly Off)'),
            ('5', 'Saturday'),
            ('6', 'Sunday'),
            ('none', 'No Automatic Off Day'),
        ],
        string='Auto Weekly Off Day',
        default='4',
        required=True,
    )
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Selected Employees (Leave empty for entire Branch/Dept)',
        domain="[('company_id', '=', company_id)]",
    )
    roster_line_ids = fields.One2many('dsl.shift.roster', 'batch_id', string='Generated Roster Slots')
    generated_count = fields.Integer(string='Generated Slots', compute='_compute_generated_count')
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('generated', 'Generated & Published'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_('End Date cannot be earlier than From Date!'))

    def _compute_generated_count(self):
        Roster = self.env['dsl.shift.roster'].sudo()
        for rec in self:
            rec.generated_count = Roster.search_count([('batch_id', '=', rec.id)])

    def action_generate_roster(self):
        Roster = self.env['dsl.shift.roster'].sudo()
        Employee = self.env['hr.employee'].sudo()
        for batch in self:
            emps = batch.employee_ids
            if not emps:
                dom = [('company_id', '=', batch.company_id.id), ('active', '=', True)]
                if batch.branch_id:
                    dom.append(('branch_id', '=', batch.branch_id.id))
                if batch.department_id:
                    dom.append(('department_id', '=', batch.department_id.id))
                emps = Employee.search(dom)

            cur = batch.date_from
            created_or_updated = 0
            while cur <= batch.date_to:
                is_off = (batch.off_weekday != 'none' and str(cur.weekday()) == batch.off_weekday)
                for emp in emps:
                    existing = Roster.search([
                        ('employee_id', '=', emp.id),
                        ('roster_date', '=', cur),
                    ], limit=1)
                    vals = {
                        'employee_id': emp.id,
                        'company_id': emp.company_id.id,
                        'branch_id': emp.branch_id.id if emp.branch_id else False,
                        'shift_id': batch.shift_id.id,
                        'roster_date': cur,
                        'is_off_day': is_off,
                        'batch_id': batch.id,
                        'state': 'published',
                    }
                    if existing:
                        existing.write(vals)
                    else:
                        Roster.create(vals)
                    created_or_updated += 1
                cur += timedelta(days=1)

            batch.write({'state': 'generated'})
            batch.message_post(body=f"✅ Generated & published {created_or_updated} shift roster slots.")
        return True


class HrEmployeeShiftExt(models.Model):
    _inherit = 'hr.employee'

    default_shift_id = fields.Many2one(
        'dsl.hr.shift',
        string='Default Work Shift',
        groups='hr.group_hr_user',
        tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    def _sync_default_shift_to_resource_calendar(self):
        for emp in self.sudo():
            if emp.default_shift_id:
                if not emp.default_shift_id.resource_calendar_id:
                    emp.default_shift_id._sync_to_odoo_resource_calendar()
                if emp.default_shift_id.resource_calendar_id and emp.resource_calendar_id != emp.default_shift_id.resource_calendar_id:
                    emp.with_context(skip_dsl_emp_shift_sync=True).write({
                        'resource_calendar_id': emp.default_shift_id.resource_calendar_id.id
                    })

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees._sync_default_shift_to_resource_calendar()
        return employees

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_dsl_emp_shift_sync') and 'default_shift_id' in vals:
            self._sync_default_shift_to_resource_calendar()
        return res


class DslAttendanceLogShiftExt(models.Model):
    _inherit = 'dsl.attendance.log'

    shift_id = fields.Many2one(
        'dsl.hr.shift',
        string='Assigned Shift',
        compute='_compute_assigned_shift',
        store=True,
    )

    @api.depends('employee_id', 'attendance_date')
    def _compute_assigned_shift(self):
        Roster = self.env['dsl.shift.roster'].sudo()
        for rec in self:
            if rec.employee_id and rec.attendance_date:
                slot = Roster.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('roster_date', '=', rec.attendance_date),
                ], limit=1)
                rec.shift_id = slot.shift_id if slot else rec.employee_id.default_shift_id
            else:
                rec.shift_id = False

    def _resolve_expected_schedule(self, employee, att_date, policy=None):
        """Plug into `dsl.attendance.log` so Rostered Shift or Employee Default Shift drives
        exact In/Out times, Cross-Midnight Night Shift handling, Grace Minutes, and Extra OT Hours!"""
        Roster = self.env['dsl.shift.roster'].sudo()
        slot = False
        if employee and att_date:
            slot = Roster.search([
                ('employee_id', '=', employee.id),
                ('roster_date', '=', att_date),
            ], limit=1)

        shift = slot.shift_id if slot else (employee.default_shift_id if employee else False)
        if not shift:
            return super()._resolve_expected_schedule(employee, att_date, policy=policy)

        if slot:
            is_off = bool(slot.is_off_day)
            off_status = 'off_day' if is_off else False
        else:
            is_off = bool(att_date and att_date.weekday() == 4)
            off_status = 'holiday' if is_off else False

        return {
            'label': f"[{shift.code}] {shift.name}" + (' (OFF)' if is_off else ''),
            'start_hour': shift.start_hour,
            'end_hour': shift.end_hour,
            'break_hours': shift.break_duration,
            'standard_hours': shift.scheduled_work_hours or 8.0,
            'grace_in_mins': shift.grace_in_minutes,
            'grace_out_mins': shift.grace_out_minutes,
            'half_day_hours': shift.half_day_hours or 4.0,
            'is_off_day': is_off,
            'off_status': off_status,
        }
