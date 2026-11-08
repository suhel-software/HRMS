# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DslHolidayCalendar(models.Model):
    _name = 'dsl.holiday.calendar'
    _description = 'DSL HRMS Weekend & Gazetted Holiday Calendar'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'calendar_year desc, sequence, id'

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    name = fields.Char(string='Calendar Name', required=True, tracking=True)
    calendar_year = fields.Char(
        string='Calendar Year',
        required=True,
        default=lambda self: str(fields.Date.today().year),
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        help='Leave empty to apply across all Group companies as the default statutory calendar.',
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Specific Branch / Factory Plant',
        domain="[('company_id', '=', company_id)]",
        help='Optional: assign a dedicated calendar to a Branch/Plant (e.g. HQ Fri+Sat vs Factory Fri-only).',
    )

    # Weekly Off Days (Python weekday(): Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6)
    mon_off = fields.Boolean(string='Monday Off', default=False)
    tue_off = fields.Boolean(string='Tuesday Off', default=False)
    wed_off = fields.Boolean(string='Wednesday Off', default=False)
    thu_off = fields.Boolean(string='Thursday Off', default=False)
    fri_off = fields.Boolean(string='Friday Off (BD Statutory)', default=True, tracking=True)
    sat_off = fields.Boolean(string='Saturday Off (Corporate HQ)', default=False, tracking=True)
    sun_off = fields.Boolean(string='Sunday Off', default=False)

    weekend_summary = fields.Char(
        string='Weekly Holidays',
        compute='_compute_calendar_totals',
        store=True,
    )
    total_holiday_events = fields.Integer(
        string='Holiday Occasions',
        compute='_compute_calendar_totals',
        store=True,
    )
    total_gazetted_days = fields.Integer(
        string='Total Gazetted Days',
        compute='_compute_calendar_totals',
        store=True,
    )

    line_ids = fields.One2many(
        'dsl.holiday.line',
        'calendar_id',
        string='Gazetted & Institutional Holidays',
    )
    notes = fields.Text(string='Circular / Gazette Notes')

    @api.depends(
        'mon_off', 'tue_off', 'wed_off', 'thu_off', 'fri_off', 'sat_off', 'sun_off',
        'line_ids.day_count',
    )
    def _compute_calendar_totals(self):
        day_labels = [
            ('mon_off', 'Monday'),
            ('tue_off', 'Tuesday'),
            ('wed_off', 'Wednesday'),
            ('thu_off', 'Thursday'),
            ('fri_off', 'Friday'),
            ('sat_off', 'Saturday'),
            ('sun_off', 'Sunday'),
        ]
        for rec in self:
            offs = [label for fname, label in day_labels if getattr(rec, fname)]
            rec.weekend_summary = ', '.join(offs) if offs else _('No Weekly Off')
            rec.total_holiday_events = len(rec.line_ids)
            rec.total_gazetted_days = sum(rec.line_ids.mapped('day_count'))

    def _is_weekly_off_date(self, check_date):
        self.ensure_one()
        wd = check_date.weekday()
        mapping = {
            0: self.mon_off,
            1: self.tue_off,
            2: self.wed_off,
            3: self.thu_off,
            4: self.fri_off,
            5: self.sat_off,
            6: self.sun_off,
        }
        return bool(mapping.get(wd, False))

    @api.model
    def _resolve_calendar_for_employee(self, employee, check_date):
        """Priority: 1) Branch-specific -> 2) Company-specific -> 3) Group Default."""
        target_year = str(check_date.year)
        emp = employee.sudo() if employee else False
        branch_id = emp.branch_id.id if (emp and emp.branch_id) else False
        company_id = emp.company_id.id if (emp and emp.company_id) else self.env.company.id

        if branch_id:
            cal = self.sudo().search([
                ('active', '=', True),
                ('calendar_year', '=', target_year),
                ('branch_id', '=', branch_id),
            ], order='sequence, id desc', limit=1)
            if cal:
                return cal

        if company_id:
            cal = self.sudo().search([
                ('active', '=', True),
                ('calendar_year', '=', target_year),
                ('company_id', '=', company_id),
                ('branch_id', '=', False),
            ], order='sequence, id desc', limit=1)
            if cal:
                return cal

        return self.sudo().search([
            ('active', '=', True),
            ('calendar_year', '=', target_year),
            ('company_id', '=', False),
            ('branch_id', '=', False),
        ], order='sequence, id desc', limit=1)


class DslHolidayLine(models.Model):
    _name = 'dsl.holiday.line'
    _description = 'Gazetted Government, Festival & Institutional Holiday'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from asc, id asc'

    calendar_id = fields.Many2one(
        'dsl.holiday.calendar',
        string='Holiday Calendar',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='calendar_id.company_id',
        string='Company',
        store=True,
        readonly=True,
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        related='calendar_id.branch_id',
        string='Branch / Plant',
        store=True,
        readonly=True,
    )
    calendar_year = fields.Char(
        related='calendar_id.calendar_year',
        string='Year',
        store=True,
        readonly=True,
    )

    name = fields.Char(string='Holiday Title (English)', required=True, tracking=True)
    name_bn = fields.Char(string='ছুটির নাম (বাংলায়)', tracking=True)
    holiday_category = fields.Selection(
        selection=[
            ('national', 'National / Statutory Holiday'),
            ('religious_moon', 'Moon-Sighting Religious Festival (Eid / Shab-e-Barat)'),
            ('festival', 'Cultural / Traditional Festival (Pahela Baishakh / Puja)'),
            ('company', 'Institutional / Company Special Holiday'),
        ],
        string='Holiday Category',
        default='national',
        required=True,
        tracking=True,
    )
    is_moon_dependent = fields.Boolean(
        string='Subject to Moon Sighting (চাঁদ দেখার ওপর নির্ভরশীল)',
        default=False,
        tracking=True,
    )
    date_from = fields.Date(string='Start Date', required=True, index=True, tracking=True)
    date_to = fields.Date(string='End Date', required=True, index=True, tracking=True)
    day_count = fields.Integer(
        string='Total Days',
        compute='_compute_day_count',
        store=True,
    )
    gazette_ref = fields.Char(string='Ministry / HR Circular Ref.')
    odoo_calendar_leave_id = fields.Many2one(
        'resource.calendar.leaves',
        string='Odoo Public Holiday Entry',
        ondelete='set null',
        help='Automatically synchronized native Odoo resource.calendar.leaves public holiday record.',
    )

    @api.depends('date_from', 'date_to')
    def _compute_day_count(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to >= rec.date_from:
                rec.day_count = (rec.date_to - rec.date_from).days + 1
            else:
                rec.day_count = 0

    @api.constrains('date_from', 'date_to')
    def _check_holiday_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_(
                    'Holiday End Date (%s) cannot be earlier than Start Date (%s)!'
                ) % (rec.date_to, rec.date_from))

    def _sync_to_odoo_public_holiday(self):
        if self.env.context.get('skip_dsl_holiday_sync') or 'resource.calendar.leaves' not in self.env:
            return
        CalLeaves = self.env['resource.calendar.leaves'].sudo().with_context(skip_dsl_holiday_sync=True)
        for rec in self.sudo():
            if not rec.date_from or not rec.date_to:
                continue
            dt_from = datetime.combine(rec.date_from, time(0, 0, 0))
            dt_to = datetime.combine(rec.date_to, time(23, 59, 59))
            vals = {
                'name': rec.name,
                'company_id': rec.company_id.id if rec.company_id else self.env.company.id,
                'resource_id': False,  # Global Public Holiday in Odoo
                'date_from': dt_from,
                'date_to': dt_to,
                'time_type': 'leave',
            }
            if 'dsl_holiday_line_id' in CalLeaves._fields:
                vals['dsl_holiday_line_id'] = rec.id
            if rec.odoo_calendar_leave_id:
                try:
                    rec.odoo_calendar_leave_id.sudo().with_context(skip_dsl_holiday_sync=True).write(vals)
                except Exception:
                    pass
            else:
                existing = CalLeaves.search([
                    ('resource_id', '=', False),
                    ('calendar_id', '=', False),
                    ('date_from', '<=', dt_to),
                    ('date_to', '>=', dt_from),
                ], limit=1)
                if existing:
                    rec.with_context(skip_dsl_holiday_sync=True).write({'odoo_calendar_leave_id': existing.id})
                else:
                    try:
                        created = CalLeaves.create(vals)
                        rec.with_context(skip_dsl_holiday_sync=True).write({'odoo_calendar_leave_id': created.id})
                    except Exception:
                        pass

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_to_odoo_public_holiday()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_dsl_holiday_sync') and any(
            k in vals for k in ('name', 'date_from', 'date_to', 'calendar_id')
        ):
            self._sync_to_odoo_public_holiday()
        return res

    def unlink(self):
        cal_leaves = self.sudo().mapped('odoo_calendar_leave_id')
        res = super().unlink()
        if cal_leaves:
            try:
                cal_leaves.sudo().with_context(skip_dsl_holiday_sync=True).unlink()
            except Exception:
                pass
        return res

    def action_sync_holiday_to_attendance(self):
        """Marks active employees in the calendar scope as Weekly/Govt Holiday on Daily Attendance Register."""
        if 'dsl.attendance.log' not in self.env:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Attendance Module Not Installed'),
                    'message': _('Install DSL_HRMS_attendance to sync holidays to Daily Attendance Register.'),
                    'type': 'warning',
                },
            }

        AttLog = self.env['dsl.attendance.log'].sudo()
        Employee = self.env['hr.employee'].sudo()
        synced_count = 0

        for hol in self:
            emp_dom = [('active', '=', True)]
            if hol.company_id:
                emp_dom.append(('company_id', '=', hol.company_id.id))
            if hol.branch_id:
                emp_dom.append(('branch_id', '=', hol.branch_id.id))
            employees = Employee.search(emp_dom)

            cursor_dt = hol.date_from
            while cursor_dt <= hol.date_to:
                for emp in employees:
                    existing = AttLog.search([
                        ('employee_id', '=', emp.id),
                        ('attendance_date', '=', cursor_dt),
                    ], limit=1)
                    if not existing:
                        AttLog.create({
                            'employee_id': emp.id,
                            'company_id': emp.company_id.id,
                            'branch_id': emp.branch_id.id if emp.branch_id else False,
                            'attendance_date': cursor_dt,
                            'status': 'holiday',
                            'is_manual_status': True,
                            'remarks': f"Gazetted Holiday: {hol.name}",
                        })
                        synced_count += 1
                cursor_dt += timedelta(days=1)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Holiday Attendance Synced'),
                'message': _('%s employee holiday attendance log(s) created.') % synced_count,
                'type': 'success',
            },
        }


class ResourceCalendarLeavesDslHolidayExt(models.Model):
    _inherit = 'resource.calendar.leaves'

    dsl_holiday_line_id = fields.Many2one(
        'dsl.holiday.line',
        string='DSL Gazetted Holiday',
        ondelete='set null',
    )


class DslLeaveRequestHolidayExt(models.Model):
    _inherit = 'dsl.leave.request'

    def _is_non_working_day(self, employee, check_date):
        Calendar = self.env['dsl.holiday.calendar'].sudo()
        cal = Calendar._resolve_calendar_for_employee(employee, check_date)
        if cal:
            if cal._is_weekly_off_date(check_date):
                return True
            is_gazetted = any(
                line.date_from <= check_date <= line.date_to
                for line in cal.line_ids
            )
            if is_gazetted:
                return True
            return False
        return super()._is_non_working_day(employee, check_date)

