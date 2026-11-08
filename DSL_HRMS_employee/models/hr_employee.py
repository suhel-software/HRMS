# -*- coding: utf-8 -*-
import re
from markupsafe import Markup, escape
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrEmployeeDossier(models.Model):
    _inherit = 'hr.employee'

    # 1. Employee ID & Bilingual Identity (Mirrored on hr.employee.public)
    employee_code = fields.Char(
        string='Employee ID',
        copy=False,
        index=True,
        tracking=True,
        help='Official Employee ID (auto-generated with company prefix if left blank).',
    )
    name_bn = fields.Char(
        string='নাম (বাংলায়)',
        tracking=True,
        help='Employee full name in Bengali for Bangladesh Labour Act Form-7 / ID Card.',
    )
    blood_group = fields.Selection(
        selection=[
            ('A+', 'A+'), ('A-', 'A-'),
            ('B+', 'B+'), ('B-', 'B-'),
            ('AB+', 'AB+'), ('AB-', 'AB-'),
            ('O+', 'O+'), ('O-', 'O-'),
        ],
        string='Blood Group',
        tracking=True,
    )
    religion = fields.Selection(
        selection=[
            ('islam', 'Islam'),
            ('hinduism', 'Hinduism'),
            ('buddhism', 'Buddhism'),
            ('christianity', 'Christianity'),
            ('other', 'Other'),
        ],
        string='Religion',
        default='islam',
        tracking=True,
    )

    # 2. Employment Lifecycle & Probation (Mirrored on hr.employee.public)
    employment_category = fields.Selection(
        selection=[
            ('permanent', 'Permanent'),
            ('probation', 'Probationary'),
            ('contractual', 'Contractual'),
            ('intern', 'Intern / Trainee'),
            ('casual', 'Casual / Piece-Rate'),
            ('consultant', 'Consultant / Advisor'),
        ],
        string='Employment Category',
        default='probation',
        required=True,
        tracking=True,
    )
    employment_status = fields.Selection(
        selection=[
            ('probation', 'On Probation'),
            ('confirmed', 'Confirmed / Active'),
            ('notice_period', 'Serving Notice'),
            ('suspended', 'Suspended'),
            ('separated', 'Separated'),
        ],
        string='Employment Status',
        default='probation',
        required=True,
        tracking=True,
    )
    joining_date = fields.Date(
        string='Date of Joining',
        default=fields.Date.context_today,
        tracking=True,
    )
    probation_months = fields.Integer(
        string='Probation Period (Months)',
        default=6,
        groups='hr.group_hr_user',
        help='Standard 6 months for clerical/executive or 3 months for skilled workers per BD Labour Act.',
    )
    probation_end_date = fields.Date(
        string='Probation End Date',
        compute='_compute_probation_end_date',
        store=True,
        readonly=False,
    )
    confirmation_date = fields.Date(
        string='Confirmation Date',
        tracking=True,
    )
    notice_period_days = fields.Integer(
        string='Notice Period (Days)',
        default=60,
        groups='hr.group_hr_user',
    )
    retirement_date = fields.Date(
        string='Expected Retirement Date',
        compute='_compute_retirement_date',
        store=True,
        readonly=False,
        groups='hr.group_hr_user',
    )
    age_years = fields.Integer(
        string='Age (Years)',
        compute='_compute_age_years',
        groups='hr.group_hr_user',
    )
    service_years = fields.Integer(
        string='Service Years',
        compute='_compute_service_length',
    )
    service_months = fields.Integer(
        string='Service Months',
        compute='_compute_service_length',
    )
    service_length_display = fields.Char(
        string='Length of Service',
        compute='_compute_service_length',
    )

    # 3. Private Bangladesh Statutory Identity & Family Lineage (HR Only)
    father_name = fields.Char(string="Father's Name", groups='hr.group_hr_user')
    father_name_bn = fields.Char(string='পিতার নাম (বাংলায়)', groups='hr.group_hr_user')
    mother_name = fields.Char(string="Mother's Name", groups='hr.group_hr_user')
    mother_name_bn = fields.Char(string='মাতার নাম (বাংলায়)', groups='hr.group_hr_user')
    spouse_name_bn = fields.Char(string='স্বামী/স্ত্রীর নাম (বাংলায়)', groups='hr.group_hr_user')

    nid_number = fields.Char(
        string='National ID (Smart NID)',
        groups='hr.group_hr_user',
        tracking=True,
        help='10-digit Smart NID, 13-digit, or 17-digit Bangladesh National ID number.',
    )
    birth_reg_no = fields.Char(
        string='Birth Registration No.',
        groups='hr.group_hr_user',
    )
    personal_tin = fields.Char(
        string='Personal e-TIN (12-Digit)',
        groups='hr.group_hr_user',
        tracking=True,
    )
    tax_zone_emp = fields.Char(string='Employee Tax Zone', groups='hr.group_hr_user')
    tax_circle_emp = fields.Char(string='Employee Tax Circle', groups='hr.group_hr_user')
    driving_license_no = fields.Char(string='Driving License No.', groups='hr.group_hr_user')
    passport_expiry_date = fields.Date(string='Passport Expiry Date', groups='hr.group_hr_user')

    # 4. Present & Permanent Address (Bangladesh Standard - HR Only)
    present_village_house = fields.Char(string='Present House / Road / Village', groups='hr.group_hr_user')
    present_post_office = fields.Char(string='Present Post Office', groups='hr.group_hr_user')
    present_thana_upazila = fields.Char(string='Present Thana / Upazila', groups='hr.group_hr_user')
    present_district = fields.Char(string='Present District', groups='hr.group_hr_user')
    present_postcode = fields.Char(string='Present Post Code', groups='hr.group_hr_user')

    same_as_present_address = fields.Boolean(
        string='Permanent Address Same as Present',
        default=False,
        groups='hr.group_hr_user',
    )
    permanent_village_house = fields.Char(string='Permanent House / Road / Village', groups='hr.group_hr_user')
    permanent_post_office = fields.Char(string='Permanent Post Office', groups='hr.group_hr_user')
    permanent_thana_upazila = fields.Char(string='Permanent Thana / Upazila', groups='hr.group_hr_user')
    permanent_district = fields.Char(string='Permanent District', groups='hr.group_hr_user')
    permanent_postcode = fields.Char(string='Permanent Post Code', groups='hr.group_hr_user')

    # 5. Salary Disbursement: Bank (BEFTN) & Mobile Financial Services (bKash/Nagad/Rocket)
    payment_method = fields.Selection(
        selection=[
            ('bank', 'Bank Transfer (BEFTN / NPSB)'),
            ('mfs', 'Mobile Banking (bKash / Nagad / Rocket)'),
            ('cash', 'Cash Disbursement'),
            ('mixed', 'Split (Bank + Cash)'),
        ],
        string='Salary Payment Mode',
        default='bank',
        groups='hr.group_hr_user',
        tracking=True,
    )
    salary_bank_name = fields.Char(string='Bank Name', groups='hr.group_hr_user')
    salary_bank_branch = fields.Char(string='Bank Branch', groups='hr.group_hr_user')
    salary_bank_routing_no = fields.Char(string='BEFTN Routing No. (9-Digit)', groups='hr.group_hr_user')
    salary_bank_account_no = fields.Char(string='Bank Account Number', groups='hr.group_hr_user')
    mfs_provider = fields.Selection(
        selection=[
            ('bkash', 'bKash'),
            ('nagad', 'Nagad'),
            ('rocket', 'Rocket (DBBL)'),
            ('upay', 'Upay'),
        ],
        string='MFS Provider',
        groups='hr.group_hr_user',
    )
    mfs_account_no = fields.Char(string='MFS Mobile Account No.', groups='hr.group_hr_user')

    # 6. Emergency Contact Details & Statutory Nominees
    emergency_relation = fields.Selection(
        selection=[
            ('spouse', 'Spouse'),
            ('father', 'Father'),
            ('mother', 'Mother'),
            ('sibling', 'Brother / Sister'),
            ('relative', 'Relative'),
            ('friend', 'Friend / Colleague'),
        ],
        string='Emergency Contact Relation',
        groups='hr.group_hr_user',
    )
    emergency_address = fields.Char(string='Emergency Contact Address', groups='hr.group_hr_user')

    nominee_ids = fields.One2many(
        'dsl.employee.nominee',
        'employee_id',
        string='Statutory Nominees (PF / Gratuity / Insurance)',
        groups='hr.group_hr_user',
    )
    nominee_count = fields.Integer(
        string='Nominees',
        compute='_compute_nominee_count',
        groups='hr.group_hr_user',
    )

    # 6B. Hardware Biometric / RFID, Work Location, NID Verification & BD Compliance
    biometric_device_id = fields.Char(
        string='Biometric Device / Enroll ID',
        index=True,
        tracking=True,
        help='Fingerprint / Face Recognition Terminal User ID (ZKTeco / Hikvision / Realtime)',
    )
    rfid_card_no = fields.Char(
        string='RFID / Proximity Card No.',
        index=True,
        tracking=True,
        help='Turnstile / Door Access Proximity Card Number',
    )
    duty_work_location = fields.Char(
        string='Work Location / Floor / Site',
        tracking=True,
        help='e.g. Corporate HQ Level-8 / Sewing Floor-B / Chattogram Hub',
    )
    nid_verification_status = fields.Selection(
        selection=[
            ('unverified', 'Unverified (যাচাইকৃত নয়)'),
            ('pending', 'Pending EC Check (অপেক্ষমাণ)'),
            ('verified', 'EC Verified ✓ (যাচাইকৃত)'),
            ('mismatch', 'Discrepancy Found (অমিল)'),
        ],
        string='NID Verification Status',
        default='unverified',
        groups='hr.group_hr_user',
        tracking=True,
    )
    nid_verified_by_id = fields.Many2one(
        'res.users',
        string='NID Verified By',
        readonly=True,
        groups='hr.group_hr_user',
    )
    nid_verified_date = fields.Date(
        string='NID Verified Date',
        readonly=True,
        groups='hr.group_hr_user',
    )
    present_address_bn = fields.Char(
        string='বর্তমান ঠিকানা (বাংলায়)',
        groups='hr.group_hr_user',
    )
    permanent_address_bn = fields.Char(
        string='স্থায়ী ঠিকানা (বাংলায়)',
        groups='hr.group_hr_user',
    )
    festival_bonus_eligible = fields.Boolean(
        string='Festival Bonus Eligible (Eid / Puja)',
        default=True,
        groups='hr.group_hr_user',
        tracking=True,
    )
    festival_bonus_eligible_from = fields.Date(
        string='Bonus Eligible From',
        groups='hr.group_hr_user',
    )
    tax_exemption_notes = fields.Text(
        string='Tax Exemption & Rebate Declaration',
        groups='hr.group_hr_user',
    )

    # 6C. Relational Dossier One2many Links (18-Tab Enterprise Profile)
    contact_line_ids = fields.One2many(
        'dsl.employee.contact',
        'employee_id',
        string='Address & Contact Directory',
        groups='hr.group_hr_user',
    )
    emergency_line_ids = fields.One2many(
        'dsl.employee.emergency',
        'employee_id',
        string='Emergency Contacts (ICE)',
        groups='hr.group_hr_user',
    )
    job_history_ids = fields.One2many(
        'dsl.employee.job.history',
        'employee_id',
        string='Organizational Placement & Job History',
        groups='hr.group_hr_user',
    )
    contract_history_ids = fields.One2many(
        'dsl.employee.contract',
        'employee_id',
        string='Employment Contracts',
        groups='hr.group_hr_user',
    )
    bank_account_line_ids = fields.One2many(
        'dsl.employee.bank',
        'employee_id',
        string='Bank (BEFTN) & MFS Accounts',
        groups='hr.group_hr_user',
    )
    training_line_ids = fields.One2many(
        'dsl.employee.training',
        'employee_id',
        string='Training & Capacity Building',
        groups='hr.group_hr_user',
    )
    promotion_line_ids = fields.One2many(
        'dsl.employee.promotion',
        'employee_id',
        string='Promotion History',
        groups='hr.group_hr_user',
    )
    transfer_line_ids = fields.One2many(
        'dsl.employee.transfer',
        'employee_id',
        string='Transfer & Deputation History',
        groups='hr.group_hr_user',
    )
    disciplinary_line_ids = fields.One2many(
        'dsl.employee.disciplinary',
        'employee_id',
        string='Disciplinary & Show Cause Records',
        groups='hr.group_hr_user',
    )

    # 7. Executive SaaS Profile Hero KPI & Overview Dashboard Fields
    joining_date_formatted = fields.Char(
        string='Working Since',
        compute='_compute_joining_date_formatted',
    )
    hero_attendance_ratio = fields.Char(
        string='Total Attendance',
        compute='_compute_overview_dashboard',
        groups='hr.group_hr_user',
    )
    hero_attendance_pct_label = fields.Char(
        string='Attendance Rate',
        compute='_compute_overview_dashboard',
        groups='hr.group_hr_user',
    )
    hero_leave_days_label = fields.Char(
        string='Leave Taken',
        compute='_compute_overview_dashboard',
        groups='hr.group_hr_user',
    )
    overview_mobile_display = fields.Char(
        string='Mobile Number',
        compute='_compute_overview_dashboard',
        groups='hr.group_hr_user',
    )
    overview_address_display = fields.Char(
        string='Formatted Address',
        compute='_compute_overview_dashboard',
        groups='hr.group_hr_user',
    )
    overview_present_days = fields.Char(
        string='Present Days',
        compute='_compute_overview_dashboard',
        groups='hr.group_hr_user',
    )
    overview_absent_days = fields.Char(
        string='Absent Days',
        compute='_compute_overview_dashboard',
        groups='hr.group_hr_user',
    )
    overview_leave_days = fields.Char(
        string='On Leave Days',
        compute='_compute_overview_dashboard',
        groups='hr.group_hr_user',
    )
    overview_attendance_ring_html = fields.Html(
        string='Attendance Ring',
        compute='_compute_overview_dashboard',
        sanitize=False,
        groups='hr.group_hr_user',
    )
    overview_recent_activities_html = fields.Html(
        string='Recent Activities',
        compute='_compute_overview_dashboard',
        sanitize=False,
        groups='hr.group_hr_user',
    )

    _sql_constraints = [
        (
            'employee_code_company_uniq',
            'unique(employee_code, company_id)',
            'Employee ID must be unique within the same Company!',
        ),
    ]

    @api.constrains('nid_number')
    def _check_bd_nid_number(self):
        for emp in self.sudo():
            if emp.nid_number:
                cleaned = re.sub(r'[\s\-]', '', emp.nid_number)
                if not cleaned.isdigit() or len(cleaned) not in (10, 13, 17):
                    raise ValidationError(_(
                        'Bangladesh National ID (NID) for %s must be 10, 13, or 17 digits (got %s digits).'
                    ) % (emp.name, len(cleaned)))

    @api.constrains('personal_tin')
    def _check_bd_personal_tin(self):
        for emp in self.sudo():
            if emp.personal_tin:
                cleaned = re.sub(r'[\s\-]', '', emp.personal_tin)
                if not cleaned.isdigit() or len(cleaned) != 12:
                    raise ValidationError(_(
                        'Personal e-TIN for %s must be a 12-digit numeric NBR TIN.'
                    ) % emp.name)

    @api.depends('joining_date', 'probation_months')
    def _compute_probation_end_date(self):
        for emp in self.sudo():
            if emp.joining_date and emp.probation_months and emp.probation_months > 0:
                emp.probation_end_date = emp.joining_date + relativedelta(months=emp.probation_months) - relativedelta(days=1)
            else:
                emp.probation_end_date = False

    @api.depends('birthday')
    def _compute_retirement_date(self):
        for emp in self.sudo():
            if emp.birthday:
                if not emp.retirement_date:
                    # Standard 60 years retirement age under Bangladesh Labour Act
                    emp.retirement_date = emp.birthday + relativedelta(years=60)
            else:
                emp.retirement_date = False

    @api.depends('birthday')
    def _compute_age_years(self):
        today = fields.Date.context_today(self)
        for emp in self.sudo():
            if emp.birthday:
                diff = relativedelta(today, emp.birthday)
                emp.age_years = max(diff.years, 0)
            else:
                emp.age_years = 0

    @api.depends('joining_date', 'departure_date', 'active')
    def _compute_service_length(self):
        today = fields.Date.context_today(self)
        for emp in self:
            if emp.joining_date:
                end_dt = emp.departure_date if (not emp.active and emp.departure_date) else today
                if end_dt >= emp.joining_date:
                    rd = relativedelta(end_dt, emp.joining_date)
                    emp.service_years = rd.years
                    emp.service_months = rd.months
                    parts = []
                    if rd.years:
                        parts.append(f"{rd.years} yr{'s' if rd.years > 1 else ''}")
                    if rd.months:
                        parts.append(f"{rd.months} mo{'s' if rd.months > 1 else ''}")
                    if not parts:
                        parts.append(f"{max(rd.days, 1)} day{'s' if rd.days != 1 else ''}")
                    emp.service_length_display = ' '.join(parts)
                else:
                    emp.service_years = 0
                    emp.service_months = 0
                    emp.service_length_display = 'Upcoming'
            else:
                emp.service_years = 0
                emp.service_months = 0
                emp.service_length_display = '—'

    def _compute_nominee_count(self):
        Nominee = self.env['dsl.employee.nominee'].sudo()
        for emp in self:
            emp.nominee_count = Nominee.search_count([('employee_id', '=', emp.id)])

    @api.depends('joining_date')
    def _compute_joining_date_formatted(self):
        for emp in self:
            emp.joining_date_formatted = emp.joining_date.strftime('%b %d, %Y') if emp.joining_date else 'Not Set'

    def _compute_overview_dashboard(self):
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)

        # Count working days in current month up to today (excluding Friday weekly holiday in BD)
        working_days = 0
        cursor_dt = month_start
        while cursor_dt <= today:
            if cursor_dt.weekday() != 4:  # 4 = Friday
                working_days += 1
            cursor_dt += relativedelta(days=1)
        working_days = max(working_days, 1)

        has_dsl_att = 'dsl.attendance.log' in self.env
        has_dsl_leave = 'dsl.leave.request' in self.env
        has_dsl_doc = 'dsl.employee.document' in self.env

        for emp in self.sudo():
            # 1. Attendance KPI (auto-hooks into Phase 4 when installed)
            present_cnt = working_days
            absent_cnt = 0
            leave_month_cnt = 0
            leave_year_cnt = 0

            if has_dsl_leave and emp.id:
                leaves_yr = self.env['dsl.leave.request'].sudo().search([
                    ('employee_id', '=', emp.id),
                    ('date_from', '>=', year_start),
                    ('state', '=', 'approved'),
                ])
                leave_year_cnt = round(sum(leaves_yr.mapped('number_of_days')), 1)
                leaves_mo = leaves_yr.filtered(lambda r: r.date_to >= month_start and r.date_from <= today)
                leave_month_cnt = round(sum(leaves_mo.mapped('number_of_days')), 1)

            if has_dsl_att and emp.id:
                present_cnt = self.env['dsl.attendance.log'].sudo().search_count([
                    ('employee_id', '=', emp.id),
                    ('attendance_date', '>=', month_start),
                    ('attendance_date', '<=', today),
                    ('status', 'in', ('present', 'late')),
                ])
                absent_cnt = max(int(working_days - present_cnt - leave_month_cnt), 0)

            att_pct = min(int(round((present_cnt / working_days) * 100)), 100) if working_days else 100
            yr_disp = int(leave_year_cnt) if leave_year_cnt == int(leave_year_cnt) else leave_year_cnt
            mo_disp = int(leave_month_cnt) if leave_month_cnt == int(leave_month_cnt) else leave_month_cnt
            emp.hero_attendance_ratio = f"{present_cnt} / {working_days}"
            emp.hero_attendance_pct_label = f"({att_pct}%)"
            emp.hero_leave_days_label = f"{yr_disp} Day{'s' if yr_disp != 1 else ''}"
            emp.overview_present_days = f"{present_cnt} Day{'s' if present_cnt != 1 else ''}"
            emp.overview_absent_days = f"{absent_cnt} Day{'s' if absent_cnt != 1 else ''}"
            emp.overview_leave_days = f"{mo_disp} Day{'s' if mo_disp != 1 else ''}"

            # 2. Contact & Formatted Bangladesh Address
            emp.overview_mobile_display = (
                emp.mobile_phone or emp.work_phone or emp.private_phone or emp.mfs_account_no or 'Not Provided'
            )
            addr_parts = [p for p in [
                emp.present_village_house,
                emp.present_thana_upazila,
                (f"{emp.present_district}-{emp.present_postcode}" if (emp.present_district and emp.present_postcode) else emp.present_district),
            ] if p]
            if addr_parts:
                addr_parts.append('Bangladesh')
                emp.overview_address_display = ', '.join(addr_parts)
            else:
                emp.overview_address_display = emp.private_street or (emp.branch_id.name if emp.branch_id else 'Bangladesh')

            # 3. Crisp SVG Attendance Donut Ring
            circumference = 213.6  # 2 * pi * 34
            dash_offset = round(circumference * (1.0 - att_pct / 100.0), 1)
            emp.overview_attendance_ring_html = Markup(f"""
                <svg width="84" height="84" viewBox="0 0 84 84">
                    <circle cx="42" cy="42" r="34" fill="none" stroke="rgba(148,163,184,0.22)" stroke-width="8"/>
                    <circle cx="42" cy="42" r="34" fill="none" stroke="#10b981" stroke-width="8"
                            stroke-linecap="round"
                            stroke-dasharray="{circumference}"
                            stroke-dashoffset="{dash_offset}"
                            transform="rotate(-90 42 42)"/>
                    <text x="42" y="47" text-anchor="middle" font-size="15" font-weight="800" fill="currentColor">{att_pct}%</text>
                </svg>
            """)

            # 4. Recent Activities Timeline (Milestones + Document Alerts)
            events = []
            if emp.employment_status == 'confirmed':
                conf_lbl = emp.confirmation_date.strftime('%b %d, %Y') if emp.confirmation_date else 'Active'
                events.append(('dot-green', 'Employment Confirmed', f"Permanent Staff · {emp.employee_code or ''}", conf_lbl))
            else:
                prob_lbl = emp.probation_end_date.strftime('Ends %b %d') if emp.probation_end_date else 'Active'
                events.append(('dot-blue', 'Probation Period Active', f"Category: {dict(emp._fields['employment_category'].selection).get(emp.employment_category, '')}", prob_lbl))

            if has_dsl_doc and emp.id:
                alert_doc = self.env['dsl.employee.document'].sudo().search([
                    ('employee_id', '=', emp.id),
                    ('expiry_status', 'in', ('expiring_soon', 'expired')),
                ], limit=1)
                if alert_doc:
                    st = 'Expired' if alert_doc.expiry_status == 'expired' else f'Expires in {alert_doc.days_to_expiry}d'
                    events.append(('dot-amber', f'Document Alert: {alert_doc.name}', f'Ref: {alert_doc.reference_no or "—"}', st))
                else:
                    ver_cnt = self.env['dsl.employee.document'].sudo().search_count([
                        ('employee_id', '=', emp.id),
                        ('verification_state', '=', 'verified'),
                    ])
                    if ver_cnt:
                        events.append(('dot-green', 'Digital Vault Verified', f'{ver_cnt} official HR document(s) verified', 'Verified'))

            branch_name = emp.branch_id.name if emp.branch_id else (emp.company_id.name or 'Group')
            join_lbl = emp.joining_date.strftime('%b %d, %Y') if emp.joining_date else 'Joined'
            events.append(('dot-blue', 'Assigned Duty Station', branch_name, join_lbl))

            rows_html = []
            for dot_cls, title, sub, time_str in events[:3]:
                rows_html.append(Markup("""
                    <div class="dsl-tl-item">
                        <div class="dsl-tl-left">
                            <span class="dsl-tl-dot %s"></span>
                            <div>
                                <div class="dsl-tl-title">%s</div>
                                <div class="dsl-tl-sub">%s</div>
                            </div>
                        </div>
                        <span class="dsl-tl-time">%s</span>
                    </div>
                """) % (dot_cls, escape(title), escape(sub), escape(time_str)))
            emp.overview_recent_activities_html = Markup('<div class="dsl-recent-timeline">%s</div>') % Markup('').join(rows_html)

    @api.onchange('same_as_present_address', 'present_village_house', 'present_post_office',
                  'present_thana_upazila', 'present_district', 'present_postcode')
    def _onchange_copy_present_to_permanent(self):
        if self.same_as_present_address:
            self.permanent_village_house = self.present_village_house
            self.permanent_post_office = self.present_post_office
            self.permanent_thana_upazila = self.present_thana_upazila
            self.permanent_district = self.present_district
            self.permanent_postcode = self.present_postcode

    @api.onchange('job_id')
    def _onchange_job_sync_grade_division(self):
        if self.job_id:
            if hasattr(self.job_id, 'grade_id') and self.job_id.grade_id and hasattr(self, 'grade_id') and not self.grade_id:
                self.grade_id = self.job_id.grade_id
            if hasattr(self.job_id, 'division_id') and self.job_id.division_id and hasattr(self, 'division_id') and not self.division_id:
                self.division_id = self.job_id.division_id

    def _generate_company_employee_code(self, company_id):
        comp = self.env['res.company'].sudo().browse(company_id) if company_id else self.env['res.company']
        short_code = getattr(comp, 'short_code', False) if comp else False
        for _ in range(50):
            seq = self.env['ir.sequence'].sudo().next_by_code('dsl.hr.employee.code') or 'EMP-0001'
            candidate = f"{short_code}-{seq[4:]}" if (short_code and seq.startswith('EMP-')) else seq
            exists = self.sudo().with_context(active_test=False).search_count([
                ('employee_code', '=', candidate),
                ('company_id', '=', company_id),
            ])
            if not exists:
                return candidate
        return seq

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('employee_code'):
                cid = vals.get('company_id') or self.env.company.id
                vals['employee_code'] = self._generate_company_employee_code(cid)
            if vals.get('nid_number') and not vals.get('identification_id'):
                vals['identification_id'] = vals['nid_number']
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('nid_number') and 'identification_id' not in vals:
            vals = dict(vals, identification_id=vals['nid_number'])
        return super().write(vals)

    def action_confirm_employment(self):
        today = fields.Date.context_today(self)
        for emp in self:
            emp.write({
                'employment_status': 'confirmed',
                'employment_category': 'permanent' if emp.employment_category == 'probation' else emp.employment_category,
                'confirmation_date': emp.confirmation_date or today,
            })

    def action_view_nominees(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Statutory Nominees',
            'res_model': 'dsl.employee.nominee',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

    def action_quick_open_documents(self):
        self.ensure_one()
        if hasattr(self, 'action_view_employee_documents'):
            return self.action_view_employee_documents()
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Document Vault'),
            'message': _('Install DSL_HRMS_document to manage Digital Document Vault.'),
            'type': 'info',
        }}

    def action_quick_open_skills(self):
        self.ensure_one()
        if hasattr(self, 'action_view_employee_skills'):
            return self.action_view_employee_skills()
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Skills Matrix'),
            'message': _('Install DSL_HRMS_experience to manage Skills Matrix.'),
            'type': 'info',
        }}

    def action_quick_open_family(self):
        self.ensure_one()
        if hasattr(self, 'action_view_family_members'):
            return self.action_view_family_members()
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Family & Dependents'),
            'message': _('Install DSL_HRMS_family to manage Family & Dependents.'),
            'type': 'info',
        }}

    def action_quick_open_nominees(self):
        self.ensure_one()
        return self.action_view_nominees()

    def action_verify_nid(self):
        today = fields.Date.context_today(self)
        for emp in self:
            emp.write({
                'nid_verification_status': 'verified',
                'nid_verified_by_id': self.env.uid,
                'nid_verified_date': today,
            })


class HrEmployeePublicDossier(models.Model):
    _inherit = 'hr.employee.public'

    employee_code = fields.Char(string='Employee ID', readonly=True)
    name_bn = fields.Char(string='নাম (বাংলায়)', readonly=True)
    biometric_device_id = fields.Char(string='Biometric Device / Enroll ID', readonly=True)
    rfid_card_no = fields.Char(string='RFID / Proximity Card No.', readonly=True)
    duty_work_location = fields.Char(string='Work Location / Floor / Site', readonly=True)
    blood_group = fields.Selection(
        selection=[
            ('A+', 'A+'), ('A-', 'A-'),
            ('B+', 'B+'), ('B-', 'B-'),
            ('AB+', 'AB+'), ('AB-', 'AB-'),
            ('O+', 'O+'), ('O-', 'O-'),
        ],
        string='Blood Group',
        readonly=True,
    )
    religion = fields.Selection(
        selection=[
            ('islam', 'Islam'),
            ('hinduism', 'Hinduism'),
            ('buddhism', 'Buddhism'),
            ('christianity', 'Christianity'),
            ('other', 'Other'),
        ],
        string='Religion',
        readonly=True,
    )
    employment_category = fields.Selection(
        selection=[
            ('permanent', 'Permanent'),
            ('probation', 'Probationary'),
            ('contractual', 'Contractual'),
            ('intern', 'Intern / Trainee'),
            ('casual', 'Casual / Piece-Rate'),
            ('consultant', 'Consultant / Advisor'),
        ],
        string='Employment Category',
        readonly=True,
    )
    employment_status = fields.Selection(
        selection=[
            ('probation', 'On Probation'),
            ('confirmed', 'Confirmed / Active'),
            ('notice_period', 'Serving Notice'),
            ('suspended', 'Suspended'),
            ('separated', 'Separated'),
        ],
        string='Employment Status',
        readonly=True,
    )
    joining_date = fields.Date(string='Date of Joining', readonly=True)
    joining_date_formatted = fields.Char(compute='_compute_public_service_length', readonly=True)
    probation_end_date = fields.Date(string='Probation End Date', readonly=True)
    confirmation_date = fields.Date(string='Confirmation Date', readonly=True)
    service_years = fields.Integer(compute='_compute_public_service_length', readonly=True)
    service_months = fields.Integer(compute='_compute_public_service_length', readonly=True)
    service_length_display = fields.Char(compute='_compute_public_service_length', readonly=True)

    def _compute_public_service_length(self):
        today = fields.Date.context_today(self)
        for pub in self:
            pub.joining_date_formatted = pub.joining_date.strftime('%b %d, %Y') if pub.joining_date else 'Not Set'
            if pub.joining_date:
                rd = relativedelta(today, pub.joining_date)
                pub.service_years = max(rd.years, 0)
                pub.service_months = max(rd.months, 0)
                parts = []
                if rd.years > 0:
                    parts.append(f"{rd.years} yr{'s' if rd.years > 1 else ''}")
                if rd.months > 0:
                    parts.append(f"{rd.months} mo{'s' if rd.months > 1 else ''}")
                if not parts:
                    parts.append(f"{max(rd.days, 1)} d")
                pub.service_length_display = ' '.join(parts)
            else:
                pub.service_years = 0
                pub.service_months = 0
                pub.service_length_display = '—'
