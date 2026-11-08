# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta
import pytz
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DslAttendancePolicy(models.Model):
    _name = 'dsl.attendance.policy'
    _description = 'Attendance & Late Grace Policy'
    _inherit = ['dsl.company.branch.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'company_id, sequence, name'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Policy Name', required=True, tracking=True)
    code = fields.Char(string='Policy Code', required=True, tracking=True)
    company_id = fields.Many2one(required=False, help='Leave empty to share across group companies.')
    active = fields.Boolean(default=True, tracking=True)

    work_start_hour = fields.Float(
        string='Scheduled In-Time',
        default=9.0,
        required=True,
        tracking=True,
        help='Default daily start time in 24h format (e.g. 9.0 = 09:00 AM) when Shift Roster is not assigned.',
    )
    work_end_hour = fields.Float(
        string='Scheduled Out-Time',
        default=18.0,
        required=True,
        tracking=True,
        help='Default daily end time in 24h format (e.g. 18.0 = 06:00 PM).',
    )
    break_hours = fields.Float(
        string='Lunch / Prayer Break (Hours)',
        default=1.0,
        help='Unpaid meal/rest interval per Bangladesh Labour Act Sec 101.',
    )
    standard_work_hours = fields.Float(
        string='Standard Daily Work Hours',
        default=8.0,
        required=True,
        help='Standard 8.0 net working hours per day per Bangladesh Labour Act Sec 100.',
    )
    late_grace_minutes = fields.Integer(
        string='Late In Grace (Minutes)',
        default=15,
        tracking=True,
        help='Check-in within these grace minutes after Scheduled In-Time is marked On-Time Present.',
    )
    early_out_grace_minutes = fields.Integer(
        string='Early Out Grace (Minutes)',
        default=15,
        tracking=True,
    )
    half_day_threshold_hours = fields.Float(
        string='Half-Day Minimum Hours',
        default=4.0,
        help='Worked hours below this threshold (when checked out) are flagged as Half Day.',
    )
    late_to_leave_count = fields.Integer(
        string='Late Count per 1 Day Deduction',
        default=3,
        help='Bangladesh corporate standard: e.g. every 3 late arrivals in a month = 1 day leave/wage deduction.',
    )
    weekly_off_weekday = fields.Selection(
        selection=[
            ('4', 'Friday (Bangladesh Standard)'),
            ('5', 'Saturday'),
            ('6', 'Sunday'),
            ('none', 'Roster / Custom Only'),
        ],
        string='Primary Weekly Holiday',
        default='4',
        required=True,
    )
    notes = fields.Text(string='Policy Guidelines')
    resource_calendar_id = fields.Many2one(
        'resource.calendar',
        string='Odoo Working Schedule',
        ondelete='set null',
        help='Optional linked Odoo native resource.calendar schedule.',
    )

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)', 'Attendance Policy Code must be unique per Company!'),
    ]


class DslAttendanceLog(models.Model):
    _name = 'dsl.attendance.log'
    _description = 'Consolidated Daily Attendance Register'
    _inherit = ['dsl.company.branch.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'attendance_date desc, check_in desc, id desc'

    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        index=True,
        tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    employee_code = fields.Char(
        related='employee_id.employee_code',
        string='Employee ID',
        store=True,
        readonly=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        related='employee_id.department_id',
        string='Department',
        store=True,
        readonly=True,
    )
    job_id = fields.Many2one(
        'hr.job',
        related='employee_id.job_id',
        string='Designation',
        store=True,
        readonly=True,
    )
    attendance_date = fields.Date(
        string='Attendance Date',
        required=True,
        default=fields.Date.context_today,
        index=True,
        tracking=True,
    )
    policy_id = fields.Many2one(
        'dsl.attendance.policy',
        string='Attendance Policy',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    scheduled_in_hour = fields.Float(
        string='Expected In',
        compute='_compute_attendance_metrics',
        store=True,
    )
    scheduled_out_hour = fields.Float(
        string='Expected Out',
        compute='_compute_attendance_metrics',
        store=True,
    )
    schedule_label = fields.Char(
        string='Applied Shift / Schedule',
        compute='_compute_attendance_metrics',
        store=True,
    )

    check_in = fields.Datetime(
        string='First Check-In',
        tracking=True,
    )
    check_in_location = fields.Char(
        string='Check-In Area / Location',
        tracking=True,
        help='Detected GPS Area / Thana or Biometric Gate from where Check-In was recorded.',
    )
    check_out = fields.Datetime(
        string='Last Check-Out',
        tracking=True,
    )
    check_out_location = fields.Char(
        string='Check-Out Area / Location',
        tracking=True,
        help='Detected GPS Area / Thana or Biometric Gate from where Check-Out was recorded.',
    )
    source = fields.Selection(
        selection=[
            ('manual', 'HR Manual Entry'),
            ('web', 'Web Self Check-In'),
            ('biometric', 'Biometric Device Sync'),
            ('gps', 'Mobile GPS Geo-Fence'),
            ('regularization', 'Approved Regularization'),
        ],
        string='Capture Source',
        default='manual',
        required=True,
        tracking=True,
    )

    worked_hours = fields.Float(
        string='Gross Hours',
        compute='_compute_attendance_metrics',
        store=True,
    )
    net_worked_hours = fields.Float(
        string='Net Worked Hours',
        compute='_compute_attendance_metrics',
        store=True,
    )
    late_minutes = fields.Integer(
        string='Late In (Mins)',
        compute='_compute_attendance_metrics',
        store=True,
    )
    is_late = fields.Boolean(
        string='Late Arrival',
        compute='_compute_attendance_metrics',
        store=True,
    )
    early_out_minutes = fields.Integer(
        string='Early Out (Mins)',
        compute='_compute_attendance_metrics',
        store=True,
    )
    is_early_out = fields.Boolean(
        string='Early Exit',
        compute='_compute_attendance_metrics',
        store=True,
    )
    extra_hours = fields.Float(
        string='Extra / OT Hours',
        compute='_compute_attendance_metrics',
        store=True,
        help='Hours worked beyond scheduled standard daily work hours (feeds BD 2x Overtime).',
    )
    status = fields.Selection(
        selection=[
            ('present', 'Present (On-Time)'),
            ('late', 'Late Present'),
            ('half_day', 'Half Day'),
            ('absent', 'Absent'),
            ('on_leave', 'On Leave'),
            ('holiday', 'Weekly / Govt Holiday'),
            ('off_day', 'Roster Off Day'),
        ],
        string='Attendance Status',
        compute='_compute_attendance_status',
        store=True,
        readonly=False,
        tracking=True,
    )
    is_manual_status = fields.Boolean(
        string='Lock Status Manually',
        default=False,
        help='Enable to lock status as On Leave / Holiday / Absent without overriding from punches.',
    )
    verified_by_id = fields.Many2one('res.users', string='Verified By', readonly=True)
    remarks = fields.Text(string='HR / Supervisor Remarks')
    odoo_attendance_id = fields.Many2one(
        'hr.attendance',
        string='Odoo Attendance Record',
        ondelete='set null',
        help='Automatically synchronized native Odoo hr.attendance record.',
    )

    _sql_constraints = [
        (
            'emp_date_uniq',
            'unique(employee_id, attendance_date)',
            'Only one consolidated daily attendance record is allowed per Employee per Date!',
        ),
    ]

    @api.constrains('check_in', 'check_out')
    def _check_in_out_chronology(self):
        for rec in self:
            if rec.check_in and rec.check_out and rec.check_out < rec.check_in:
                raise ValidationError(_(
                    'Last Check-Out (%s) cannot be earlier than First Check-In (%s) for %s!'
                ) % (rec.check_out, rec.check_in, rec.employee_id.name))

    @api.depends('employee_id', 'employee_id.employee_code', 'attendance_date')
    def _compute_name(self):
        for rec in self:
            emp_lbl = rec.employee_id.employee_code or rec.employee_id.name or 'ATT'
            dt_lbl = rec.attendance_date.strftime('%Y-%m-%d') if rec.attendance_date else ''
            rec.name = f"{emp_lbl} / {dt_lbl}" if dt_lbl else emp_lbl

    @api.onchange('employee_id')
    def _onchange_employee_sync_org(self):
        if self.employee_id:
            self.company_id = self.employee_id.company_id or self.env.company
            self.branch_id = self.employee_id.branch_id
            if self.employee_id.attendance_policy_id:
                self.policy_id = self.employee_id.attendance_policy_id

    def _get_default_policy(self, employee):
        Policy = self.env['dsl.attendance.policy'].sudo()
        if employee and employee.attendance_policy_id:
            return employee.attendance_policy_id
        if employee and employee.branch_id:
            pol = Policy.search([
                ('company_id', 'in', [employee.company_id.id, False]),
                ('branch_id', '=', employee.branch_id.id),
            ], limit=1)
            if pol:
                return pol
        if employee and employee.company_id:
            pol = Policy.search([
                ('company_id', 'in', [employee.company_id.id, False]),
                ('branch_id', '=', False),
            ], limit=1)
            if pol:
                return pol
        return Policy.search([], limit=1)

    def _resolve_expected_schedule(self, employee, att_date, policy=None):
        """Pluggable hook: `DSL_HRMS_shift_roster` overrides this method when installed
        to return shift-specific start/end/grace/off_day values seamlessly!"""
        pol = policy or self._get_default_policy(employee)
        is_off = False
        if pol and pol.weekly_off_weekday != 'none' and att_date:
            is_off = (str(att_date.weekday()) == pol.weekly_off_weekday)
        elif att_date:
            is_off = (att_date.weekday() == 4)  # Friday in Bangladesh

        return {
            'label': pol.name if pol else 'General (09:00–18:00)',
            'start_hour': pol.work_start_hour if pol else 9.0,
            'end_hour': pol.work_end_hour if pol else 18.0,
            'break_hours': pol.break_hours if pol else 1.0,
            'standard_hours': pol.standard_work_hours if pol else 8.0,
            'grace_in_mins': pol.late_grace_minutes if pol else 15,
            'grace_out_mins': pol.early_out_grace_minutes if pol else 15,
            'half_day_hours': pol.half_day_threshold_hours if pol else 4.0,
            'is_off_day': is_off,
            'off_status': 'holiday' if is_off else False,
        }

    @staticmethod
    def _float_hour_to_local_dt(base_date, hour_float, tz):
        h = int(hour_float) % 24
        m = int(round((hour_float - int(hour_float)) * 60))
        if m == 60:
            h = (h + 1) % 24
            m = 0
        naive = datetime.combine(base_date, time(h, m, 0))
        return tz.localize(naive)

    @api.depends(
        'employee_id', 'attendance_date', 'policy_id',
        'check_in', 'check_out'
    )
    def _compute_attendance_metrics(self):
        tz = pytz.timezone('Asia/Dhaka')
        for rec in self:
            if not rec.attendance_date or not rec.employee_id:
                rec.scheduled_in_hour = 9.0
                rec.scheduled_out_hour = 18.0
                rec.schedule_label = 'General (09:00–18:00)'
                rec.worked_hours = 0.0
                rec.net_worked_hours = 0.0
                rec.late_minutes = 0
                rec.is_late = False
                rec.early_out_minutes = 0
                rec.is_early_out = False
                rec.extra_hours = 0.0
                continue

            sched = rec._resolve_expected_schedule(rec.employee_id, rec.attendance_date, rec.policy_id)
            start_h = sched['start_hour']
            end_h = sched['end_hour']
            rec.scheduled_in_hour = start_h
            rec.scheduled_out_hour = end_h
            rec.schedule_label = sched['label']

            if not rec.check_in:
                rec.worked_hours = 0.0
                rec.net_worked_hours = 0.0
                rec.late_minutes = 0
                rec.is_late = False
                rec.early_out_minutes = 0
                rec.is_early_out = False
                rec.extra_hours = 0.0
                continue

            # Convert UTC check_in / check_out to Asia/Dhaka local time
            local_in = pytz.utc.localize(rec.check_in).astimezone(tz)
            exp_in = self._float_hour_to_local_dt(rec.attendance_date, start_h, tz)
            exp_out_date = rec.attendance_date + timedelta(days=1) if end_h <= start_h else rec.attendance_date
            exp_out = self._float_hour_to_local_dt(exp_out_date, end_h, tz)

            diff_in_mins = int((local_in - exp_in).total_seconds() // 60)
            if diff_in_mins > sched['grace_in_mins'] and not sched['is_off_day']:
                rec.late_minutes = diff_in_mins
                rec.is_late = True
            else:
                rec.late_minutes = 0
                rec.is_late = False

            if rec.check_out and rec.check_out >= rec.check_in:
                gross_h = round((rec.check_out - rec.check_in).total_seconds() / 3600.0, 2)
                deduct_break = sched['break_hours'] if gross_h > (sched['half_day_hours'] + 1.0) else 0.0
                net_h = round(max(gross_h - deduct_break, 0.0), 2)
                rec.worked_hours = gross_h
                rec.net_worked_hours = net_h

                local_out = pytz.utc.localize(rec.check_out).astimezone(tz)
                diff_out_mins = int((exp_out - local_out).total_seconds() // 60)
                if diff_out_mins > sched['grace_out_mins'] and not sched['is_off_day']:
                    rec.early_out_minutes = diff_out_mins
                    rec.is_early_out = True
                else:
                    rec.early_out_minutes = 0
                    rec.is_early_out = False

                if sched['is_off_day']:
                    rec.extra_hours = net_h
                else:
                    rec.extra_hours = round(max(net_h - sched['standard_hours'], 0.0), 2)
            else:
                rec.worked_hours = 0.0
                rec.net_worked_hours = 0.0
                rec.early_out_minutes = 0
                rec.is_early_out = False
                rec.extra_hours = 0.0

    @api.depends(
        'employee_id', 'attendance_date', 'policy_id',
        'check_in', 'check_out', 'net_worked_hours', 'is_late', 'is_manual_status'
    )
    def _compute_attendance_status(self):
        for rec in self:
            if rec.is_manual_status and rec.status:
                continue
            if not rec.attendance_date or not rec.employee_id:
                rec.status = 'absent'
                continue
            sched = rec._resolve_expected_schedule(rec.employee_id, rec.attendance_date, rec.policy_id)
            if not rec.check_in:
                rec.status = sched['off_status'] or 'absent'
            elif rec.check_out and rec.net_worked_hours < sched['half_day_hours'] and not sched['is_off_day']:
                rec.status = 'half_day'
            elif rec.is_late:
                rec.status = 'late'
            else:
                rec.status = 'present'

    def _sync_to_odoo_hr_attendance(self):
        if self.env.context.get('skip_dsl_att_sync') or 'hr.attendance' not in self.env:
            return
        HrAtt = self.env['hr.attendance'].sudo().with_context(skip_dsl_att_sync=True)
        for rec in self.sudo():
            if not rec.employee_id or not rec.check_in:
                continue
            vals = {
                'employee_id': rec.employee_id.id,
                'check_in': rec.check_in,
                'check_out': rec.check_out if (rec.check_out and rec.check_out >= rec.check_in) else False,
            }
            if 'dsl_attendance_log_id' in HrAtt._fields:
                vals['dsl_attendance_log_id'] = rec.id
            if 'branch_id' in HrAtt._fields and rec.branch_id:
                vals['branch_id'] = rec.branch_id.id
            if 'punch_source' in HrAtt._fields and rec.source:
                vals['punch_source'] = rec.source

            if rec.odoo_attendance_id:
                try:
                    rec.odoo_attendance_id.sudo().with_context(skip_dsl_att_sync=True).write(vals)
                except Exception:
                    pass
            else:
                day_start = datetime.combine(rec.attendance_date, time(0, 0, 0))
                day_end = datetime.combine(rec.attendance_date, time(23, 59, 59))
                existing_att = HrAtt.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('check_in', '>=', day_start),
                    ('check_in', '<=', day_end),
                ], limit=1)
                if existing_att:
                    try:
                        existing_att.write(vals)
                    except Exception:
                        pass
                    rec.with_context(skip_dsl_att_sync=True).write({'odoo_attendance_id': existing_att.id})
                else:
                    try:
                        created_att = HrAtt.create(vals)
                        rec.with_context(skip_dsl_att_sync=True).write({'odoo_attendance_id': created_att.id})
                    except Exception:
                        pass

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
                if not vals.get('policy_id'):
                    pol = self._get_default_policy(emp)
                    if pol:
                        vals['policy_id'] = pol.id
        records = super().create(vals_list)
        records._sync_to_odoo_hr_attendance()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_dsl_att_sync') and any(
            k in vals for k in ('check_in', 'check_out', 'employee_id', 'source')
        ):
            self._sync_to_odoo_hr_attendance()
        return res

    def unlink(self):
        odoo_atts = self.sudo().mapped('odoo_attendance_id')
        res = super().unlink()
        if odoo_atts:
            try:
                odoo_atts.sudo().with_context(skip_dsl_att_sync=True).unlink()
            except Exception:
                pass
        return res

    @api.model
    def upsert_punch(self, employee, punch_dt, source='biometric', punch_hint='auto', remarks=False, location_name=False):
        """Universal consolidation API used by Biometric Machine Bridge & GPS Geo-Attendance:
        - Maps punch timestamp to Asia/Dhaka attendance_date
        - Updates earliest `check_in` (+ `check_in_location`) and latest `check_out` (+ `check_out_location`) cleanly!"""
        tz = pytz.timezone('Asia/Dhaka')
        local_dt = pytz.utc.localize(punch_dt).astimezone(tz)
        att_date = local_dt.date()
        loc_str = (location_name or '').strip() or False

        # Night-shift early morning check-out (e.g. 05:55 AM punch belongs to previous night's open log)
        if local_dt.hour < 7:
            prev_date = att_date - timedelta(days=1)
            prev_open = self.sudo().search([
                ('employee_id', '=', employee.id),
                ('attendance_date', '=', prev_date),
                ('check_in', '!=', False),
                ('check_out', '=', False),
            ], limit=1)
            if prev_open and prev_open.scheduled_out_hour <= prev_open.scheduled_in_hour:
                nw_vals = {
                    'check_out': punch_dt,
                    'source': source,
                }
                if loc_str:
                    nw_vals['check_out_location'] = loc_str
                prev_open.write(nw_vals)
                return prev_open

        existing = self.sudo().search([
            ('employee_id', '=', employee.id),
            ('attendance_date', '=', att_date),
        ], limit=1)

        if not existing:
            vals = {
                'employee_id': employee.id,
                'company_id': employee.company_id.id,
                'branch_id': employee.branch_id.id if employee.branch_id else False,
                'attendance_date': att_date,
                'check_in': punch_dt,
                'check_in_location': loc_str,
                'source': source,
                'remarks': remarks or False,
            }
            return self.sudo().create(vals)

        update_vals = {'source': source}
        if remarks and not existing.remarks:
            update_vals['remarks'] = remarks

        if punch_hint == 'check_in':
            if not existing.check_in or punch_dt < existing.check_in:
                update_vals['check_in'] = punch_dt
                if loc_str:
                    update_vals['check_in_location'] = loc_str
            elif loc_str and not existing.check_in_location:
                update_vals['check_in_location'] = loc_str
        elif punch_hint == 'check_out':
            if not existing.check_in:
                update_vals['check_in'] = punch_dt
                if loc_str:
                    update_vals['check_in_location'] = loc_str
            elif not existing.check_out or punch_dt > existing.check_out:
                if punch_dt > existing.check_in:
                    update_vals['check_out'] = punch_dt
                    if loc_str:
                        update_vals['check_out_location'] = loc_str
            elif loc_str and not existing.check_out_location:
                update_vals['check_out_location'] = loc_str
        else:
            # Auto First-In / Last-Out consolidation (ignores accidental double-taps within 3 minutes)
            if not existing.check_in:
                update_vals['check_in'] = punch_dt
                if loc_str:
                    update_vals['check_in_location'] = loc_str
            elif punch_dt < existing.check_in:
                if not existing.check_out and (existing.check_in - punch_dt).total_seconds() >= 180:
                    update_vals['check_out'] = existing.check_in
                    if existing.check_in_location and not existing.check_out_location:
                        update_vals['check_out_location'] = existing.check_in_location
                update_vals['check_in'] = punch_dt
                if loc_str:
                    update_vals['check_in_location'] = loc_str
            elif (punch_dt - existing.check_in).total_seconds() >= 180:
                if not existing.check_out or punch_dt > existing.check_out:
                    update_vals['check_out'] = punch_dt
                    if loc_str:
                        update_vals['check_out_location'] = loc_str

        existing.write(update_vals)
        return existing

    def action_mark_verified(self):
        self.write({'verified_by_id': self.env.user.id})


class DslAttendanceRegularization(models.Model):
    _name = 'dsl.attendance.regularization'
    _description = 'Attendance Reconciliation & Missed Punch Request'
    _inherit = ['dsl.company.branch.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'attendance_date desc, id desc'

    name = fields.Char(
        string='Request Ref',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        index=True,
        tracking=True,
        default=lambda self: self.env.user.employee_id,
    )
    department_id = fields.Many2one(
        'hr.department',
        related='employee_id.department_id',
        store=True,
        readonly=True,
    )
    attendance_date = fields.Date(
        string='Attendance Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    attendance_log_id = fields.Many2one(
        'dsl.attendance.log',
        string='Linked Attendance Log',
        readonly=True,
    )
    request_type = fields.Selection(
        selection=[
            ('missed_in', 'Missed Check-In Punch'),
            ('missed_out', 'Missed Check-Out Punch'),
            ('both_missed', 'Both In & Out Missed'),
            ('outdoor_duty', 'Client Visit / Outdoor Official Duty'),
            ('late_waiver', 'Official Late Arrival Waiver'),
        ],
        string='Reconciliation Type',
        default='missed_out',
        required=True,
        tracking=True,
    )
    requested_check_in = fields.Datetime(string='Requested Check-In', required=True, tracking=True)
    requested_check_out = fields.Datetime(string='Requested Check-Out', required=True, tracking=True)
    reason = fields.Text(string='Justification / Official Note', required=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Pending Approval'),
            ('approved', 'Approved & Synced'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )
    approved_by_id = fields.Many2one('res.users', string='Approved By', readonly=True, tracking=True)
    approved_date = fields.Datetime(string='Approved On', readonly=True)

    @api.constrains('requested_check_in', 'requested_check_out')
    def _check_requested_times(self):
        for rec in self:
            if rec.requested_check_in and rec.requested_check_out and rec.requested_check_out <= rec.requested_check_in:
                raise ValidationError(_('Requested Check-Out must be after Requested Check-In!'))

    @api.onchange('employee_id', 'attendance_date')
    def _onchange_employee_load_existing_log(self):
        if self.employee_id:
            self.company_id = self.employee_id.company_id or self.env.company
            self.branch_id = self.employee_id.branch_id
            if self.attendance_date:
                log = self.env['dsl.attendance.log'].sudo().search([
                    ('employee_id', '=', self.employee_id.id),
                    ('attendance_date', '=', self.attendance_date),
                ], limit=1)
                if log:
                    self.attendance_log_id = log.id
                    if log.check_in and not self.requested_check_in:
                        self.requested_check_in = log.check_in
                    if log.check_out and not self.requested_check_out:
                        self.requested_check_out = log.check_out

    @api.model_create_multi
    def create(self, vals_list):
        Employee = self.env['hr.employee'].sudo()
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.attendance.regularization') or _('New')
            if vals.get('employee_id'):
                emp = Employee.browse(vals['employee_id'])
                if not vals.get('company_id') and emp.company_id:
                    vals['company_id'] = emp.company_id.id
                if not vals.get('branch_id') and emp.branch_id:
                    vals['branch_id'] = emp.branch_id.id
        return super().create(vals_list)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        AttLog = self.env['dsl.attendance.log'].sudo()
        for rec in self:
            log = AttLog.search([
                ('employee_id', '=', rec.employee_id.id),
                ('attendance_date', '=', rec.attendance_date),
            ], limit=1)
            log_vals = {
                'check_in': rec.requested_check_in,
                'check_out': rec.requested_check_out,
                'source': 'regularization',
                'verified_by_id': self.env.user.id,
                'remarks': f"Regularized ({rec.name}): {rec.reason}",
            }
            if rec.request_type in ('late_waiver', 'outdoor_duty'):
                log_vals['status'] = 'present'
                log_vals['is_manual_status'] = True
            if log:
                log.write(log_vals)
            else:
                log_vals.update({
                    'employee_id': rec.employee_id.id,
                    'company_id': rec.company_id.id,
                    'branch_id': rec.branch_id.id if rec.branch_id else False,
                    'attendance_date': rec.attendance_date,
                })
                log = AttLog.create(log_vals)

            rec.write({
                'state': 'approved',
                'attendance_log_id': log.id,
                'approved_by_id': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class HrEmployeeAttendanceExt(models.Model):
    _inherit = 'hr.employee'

    attendance_policy_id = fields.Many2one(
        'dsl.attendance.policy',
        string='Attendance Policy',
        groups='hr.group_hr_user',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    dsl_attendance_log_ids = fields.One2many(
        'dsl.attendance.log',
        'employee_id',
        string='Daily Attendance Logs',
        groups='hr.group_hr_user',
    )
    dsl_attendance_count = fields.Integer(
        string='Attendance Logs',
        compute='_compute_dsl_attendance_count',
        groups='hr.group_hr_user',
    )

    def _compute_dsl_attendance_count(self):
        AttLog = self.env['dsl.attendance.log'].sudo()
        for emp in self:
            emp.dsl_attendance_count = AttLog.search_count([('employee_id', '=', emp.id)])

    def action_view_dsl_attendance_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Attendance Register',
            'res_model': 'dsl.attendance.log',
            'view_mode': 'list,calendar,pivot,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {
                'default_employee_id': self.id,
                'default_company_id': self.company_id.id,
                'default_branch_id': self.branch_id.id if self.branch_id else False,
            },
        }


class HrAttendanceDslExt(models.Model):
    _inherit = 'hr.attendance'

    dsl_attendance_log_id = fields.Many2one(
        'dsl.attendance.log',
        string='DSL Daily Attendance Log',
        ondelete='set null',
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Branch / Duty Station',
    )
    punch_source = fields.Char(
        string='Punch Source',
        default='odoo_native',
    )

    def _sync_to_dsl_attendance_log(self):
        if self.env.context.get('skip_dsl_att_sync') or 'dsl.attendance.log' not in self.env:
            return
        AttLog = self.env['dsl.attendance.log'].sudo().with_context(skip_dsl_att_sync=True)
        for att in self.sudo():
            if not att.employee_id or not att.check_in:
                continue
            daily = AttLog.upsert_punch(
                employee=att.employee_id,
                punch_dt=att.check_in,
                source=att.punch_source or 'web',
                punch_hint='check_in',
                remarks='Synced from Odoo Native Attendance',
            )
            if att.check_out and att.check_out >= att.check_in:
                daily = AttLog.upsert_punch(
                    employee=att.employee_id,
                    punch_dt=att.check_out,
                    source=att.punch_source or 'web',
                    punch_hint='check_out',
                )
            if daily:
                daily.with_context(skip_dsl_att_sync=True).write({'odoo_attendance_id': att.id})
                att.with_context(skip_dsl_att_sync=True).write({
                    'dsl_attendance_log_id': daily.id,
                    'branch_id': att.employee_id.branch_id.id if att.employee_id.branch_id else False,
                })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_to_dsl_attendance_log()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_dsl_att_sync') and any(
            k in vals for k in ('check_in', 'check_out', 'employee_id')
        ):
            self._sync_to_dsl_attendance_log()
        return res

