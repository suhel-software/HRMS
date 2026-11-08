# -*- coding: utf-8 -*-
import json
import math
import urllib.parse
import urllib.request
from odoo import api, fields, models, _
from odoo.exceptions import UserError


# Offline Bangladesh Neighbourhood / Thana / Industrial Hub Gazetteer (Fallback when offline)
BD_AREA_GAZETTEER = [
    ("Gulshan-2, Dhaka", 23.7925, 90.4078),
    ("Gulshan-1, Dhaka", 23.7786, 90.4161),
    ("Banani, Dhaka", 23.7940, 90.4043),
    ("Baridhara, Dhaka", 23.8037, 90.4227),
    ("Bashundhara R/A, Dhaka", 23.8191, 90.4526),
    ("Vatara / Notun Bazar, Dhaka", 23.7979, 90.4256),
    ("Nikunja-2, Khilkhet, Dhaka", 23.8315, 90.4178),
    ("Airport / Dakshinkhan, Dhaka", 23.8513, 90.4089),
    ("Uttara Sector-7, Dhaka", 23.8728, 90.3984),
    ("Uttara Sector-11 / Diabari, Dhaka", 23.8759, 90.3795),
    ("Tongi Industrial Area, Gazipur", 23.8973, 90.4026),
    ("Badda, Dhaka", 23.7805, 90.4267),
    ("Rampura / Banasree, Dhaka", 23.7619, 90.4331),
    ("Aftabnagar, Dhaka", 23.7647, 90.4428),
    ("Mohakhali, Dhaka", 23.7778, 90.3977),
    ("Niketan, Gulshan, Dhaka", 23.7745, 90.4112),
    ("Tejgaon Industrial Area, Dhaka", 23.7639, 90.3995),
    ("Hatirjheel / Moghbazar, Dhaka", 23.7494, 90.4089),
    ("Malibagh / Shantinagar, Dhaka", 23.7453, 90.4148),
    ("Kakrail / Paltan, Dhaka", 23.7362, 90.4125),
    ("Motijheel Commercial Area, Dhaka", 23.7330, 90.4172),
    ("Wari / Tikatuli, Dhaka", 23.7176, 90.4178),
    ("Jatrabari, Dhaka", 23.7104, 90.4349),
    ("Demra, Dhaka", 23.7225, 90.4892),
    ("Shyampur / Kadamtali, Dhaka", 23.6922, 90.4354),
    ("Kotwali / Sadarghat, Old Dhaka", 23.7073, 90.4091),
    ("Lalbagh / Azimpur, Dhaka", 23.7231, 90.3854),
    ("Keraniganj, Dhaka", 23.6915, 90.3822),
    ("Shahbagh / Ramna, Dhaka", 23.7389, 90.3958),
    ("New Market / Nilkhet, Dhaka", 23.7331, 90.3847),
    ("Karwan Bazar, Dhaka", 23.7516, 90.3943),
    ("Farmgate / Panthapath, Dhaka", 23.7561, 90.3872),
    ("Dhanmondi, Dhaka", 23.7465, 90.3760),
    ("Kalabagan, Dhaka", 23.7486, 90.3831),
    ("Mohammadpur, Dhaka", 23.7662, 90.3589),
    ("Adabor / Shyamoli, Dhaka", 23.7748, 90.3654),
    ("Kalyanpur / Gabtoli, Dhaka", 23.7797, 90.3536),
    ("Agargaon, Sher-e-Bangla Nagar, Dhaka", 23.7776, 90.3775),
    ("Kafrul / Cantonment, Dhaka", 23.7975, 90.3879),
    ("Kazipara / Shewrapara, Mirpur, Dhaka", 23.7972, 90.3733),
    ("Mirpur-1, Dhaka", 23.7956, 90.3537),
    ("Mirpur-2, Dhaka", 23.8042, 90.3627),
    ("Mirpur-10, Dhaka", 23.8069, 90.3687),
    ("Mirpur-11 / Pallabi, Dhaka", 23.8191, 90.3654),
    ("Mirpur-12 / DOHS, Dhaka", 23.8342, 90.3679),
    ("Savar EPZ / Hemayetpur, Dhaka", 23.8483, 90.2674),
    ("Ashulia Industrial Zone, Dhaka", 23.9010, 90.3267),
    ("Gazipur Chowrasta / Sadar, Gazipur", 23.9999, 90.4203),
    ("Konabari Industrial Area, Gazipur", 24.0069, 90.3342),
    ("Sreepur / Mawna, Gazipur", 24.1996, 90.4810),
    ("Narayanganj Sadar / Chashara", 23.6238, 90.5000),
    ("Fatullah / Siddhirganj, Narayanganj", 23.6612, 90.4910),
    ("Rupganj / Bhulta, Narayanganj", 23.7885, 90.5620),
    ("Agrabad / Port Area, Chattogram", 22.3160, 91.8000),
    ("CEPZ / Patenga, Chattogram", 22.2889, 91.7782),
    ("GEC / Nasirabad, Chattogram", 22.3591, 91.8215),
    ("Mongla Sea Port, Bagerhat", 22.4716, 89.6011),
    ("Khulna Sadar, Khulna", 22.8456, 89.5403),
    ("Sylhet Sadar, Sylhet", 24.8949, 91.8687),
    ("Rajshahi Sadar, Rajshahi", 24.3745, 88.6042),
    ("Cumilla EPZ / Sadar, Cumilla", 23.4500, 91.1833),
    ("Mymensingh Sadar, Mymensingh", 24.7471, 90.4203),
    ("Rangpur Sadar, Rangpur", 25.7439, 89.2752),
    ("Barishal Sadar, Barishal", 22.7010, 90.3535),
]


class DslGpsAttendanceLog(models.Model):
    _name = 'dsl.gps.attendance.log'
    _description = 'Geo-Fenced Mobile & Browser GPS Attendance'
    _inherit = ['dsl.company.branch.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'punch_datetime desc, id desc'

    name = fields.Char(
        string='GPS Ref',
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
    punch_type = fields.Selection(
        selection=[
            ('check_in', 'Check-In'),
            ('check_out', 'Check-Out'),
        ],
        string='Punch Type',
        default='check_in',
        required=True,
        tracking=True,
    )
    work_mode = fields.Selection(
        selection=[
            ('office_geofence', 'Branch / Plant Geofence'),
            ('field_duty', 'Field / Client Site Visit'),
            ('wfh', 'Authorized Remote / WFH'),
        ],
        string='Duty Location Mode',
        default='office_geofence',
        required=True,
        tracking=True,
    )
    punch_datetime = fields.Datetime(
        string='Punch Timestamp',
        default=fields.Datetime.now,
        required=True,
        index=True,
        tracking=True,
    )

    latitude = fields.Float(string='Captured Latitude', digits=(10, 7), required=True)
    longitude = fields.Float(string='Captured Longitude', digits=(10, 7), required=True)
    accuracy_meters = fields.Float(string='GPS Accuracy (±m)', default=12.0)

    detected_area = fields.Char(
        string='Check-In / Out Area',
        index=True,
        tracking=True,
        help='Automatically detected Neighbourhood, Thana & City from GPS coordinates.',
    )
    full_geo_address = fields.Char(
        string='Full Street / Map Address',
        help='Complete street & locality address resolved from map reverse geocoding.',
    )

    branch_latitude = fields.Float(
        string='Branch Center Lat',
        compute='_compute_geofence_metrics',
        store=True,
        digits=(10, 7),
    )
    branch_longitude = fields.Float(
        string='Branch Center Lng',
        compute='_compute_geofence_metrics',
        store=True,
        digits=(10, 7),
    )
    allowed_radius_m = fields.Float(
        string='Allowed Geofence Radius (m)',
        compute='_compute_geofence_metrics',
        store=True,
    )
    distance_from_branch_m = fields.Float(
        string='Distance from Branch (m)',
        compute='_compute_geofence_metrics',
        store=True,
    )
    within_geofence = fields.Boolean(
        string='Inside Geofence',
        compute='_compute_geofence_metrics',
        store=True,
    )
    map_url = fields.Char(
        string='OpenStreetMap Link',
        compute='_compute_map_url',
    )

    client_or_site_name = fields.Char(string='Client / Project Site Name')
    location_note = fields.Char(string='Field Location / Landmark Note')
    selfie_image = fields.Image(string='Verification Selfie / Site Photo', max_width=512, max_height=512)

    validation_state = fields.Selection(
        selection=[
            ('auto_verified', 'Auto-Verified (Inside Geofence)'),
            ('pending_approval', 'Outside Geofence / Pending Approval'),
            ('approved', 'Approved Field Punch'),
            ('rejected', 'Rejected'),
        ],
        string='Geofence Status',
        default='pending_approval',
        required=True,
        tracking=True,
    )
    approved_by_id = fields.Many2one('res.users', string='Reviewed By', readonly=True)
    attendance_log_id = fields.Many2one('dsl.attendance.log', string='Synced Daily Attendance', readonly=True)

    @staticmethod
    def _haversine_meters(lat1, lon1, lat2, lon2):
        """Pure-Python Haversine spherical distance in meters."""
        r_earth = 6371000.0
        p1 = math.radians(lat1)
        p2 = math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * (math.sin(dl / 2.0) ** 2)
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(1.0 - a, 0.0)))
        return round(r_earth * c, 1)

    @classmethod
    def _resolve_area_from_coords(cls, lat, lng):
        """Resolve `(lat, lng)` into `(short_area_name, full_street_address)`:
        1. Live OpenStreetMap Nominatim Reverse Geocoding (zero API key, native `urllib.request`)
        2. Instant Offline Bangladesh Gazetteer nearest-area Haversine fallback!"""
        if not lat and not lng:
            return ('Unknown Location', '')

        # 1. Try Live Nominatim Reverse Geocoding
        try:
            params = urllib.parse.urlencode({
                'format': 'jsonv2',
                'lat': f'{lat:.6f}',
                'lon': f'{lng:.6f}',
                'zoom': 18,
                'addressdetails': 1,
                'accept-language': 'en',
            })
            url = f"https://nominatim.openstreetmap.org/reverse?{params}"
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'DSL-Enterprise-HRMS/18.0 (Bangladesh-GeoAttendance)',
                    'Accept': 'application/json',
                },
            )
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                payload = json.loads(resp.read().decode('utf-8', errors='ignore'))

            addr = payload.get('address') or {}
            display_name = (payload.get('display_name') or '').strip()

            # Build crisp 2–3 part Area Name: [Road/Neighbourhood/Suburb] + [Thana/Sub-district] + [City/District]
            local_part = (
                addr.get('neighbourhood')
                or addr.get('suburb')
                or addr.get('quarter')
                or addr.get('residential')
                or addr.get('road')
                or addr.get('commercial')
                or addr.get('industrial')
                or addr.get('village')
            )
            thana_part = (
                addr.get('city_district')
                or addr.get('borough')
                or addr.get('municipality')
                or addr.get('town')
                or addr.get('subdistrict')
            )
            city_part = (
                addr.get('city')
                or addr.get('state_district')
                or addr.get('county')
                or addr.get('state')
            )

            parts = []
            for p in (local_part, thana_part, city_part):
                if p:
                    clean_p = p.replace(' District', '').replace(' Division', '').strip()
                    if clean_p and all(clean_p.lower() not in existing.lower() and existing.lower() not in clean_p.lower() for existing in parts):
                        parts.append(clean_p)

            if parts:
                return (', '.join(parts[:3]), display_name or ', '.join(parts))
            if display_name:
                short_disp = ', '.join([seg.strip() for seg in display_name.split(',')[:3]])
                return (short_disp, display_name)
        except Exception:
            pass

        # 2. Offline Bangladesh Gazetteer Fallback (works 100% without internet!)
        best_name = None
        best_dist = float('inf')
        for area_label, g_lat, g_lng in BD_AREA_GAZETTEER:
            d = cls._haversine_meters(lat, lng, g_lat, g_lng)
            if d < best_dist:
                best_dist = d
                best_name = area_label

        if best_name:
            if best_dist <= 3000.0:
                return (best_name, f"{best_name}, Bangladesh ({lat:.5f}, {lng:.5f})")
            if best_dist <= 25000.0:
                km = round(best_dist / 1000.0, 1)
                return (f"Near {best_name} (~{km} km)", f"Near {best_name} ({lat:.5f}, {lng:.5f})")

        return (f"Lat {lat:.4f}, Lng {lng:.4f}", f"GPS Coordinates: {lat:.6f}, {lng:.6f}")

    @api.depends('latitude', 'longitude', 'branch_id', 'branch_id.latitude', 'branch_id.longitude', 'branch_id.geofence_radius')
    def _compute_geofence_metrics(self):
        for rec in self:
            b = rec.branch_id
            b_lat = b.latitude if (b and 'latitude' in b._fields) else 0.0
            b_lng = b.longitude if (b and 'longitude' in b._fields) else 0.0
            radius = (b.geofence_radius if (b and 'geofence_radius' in b._fields and b.geofence_radius > 0) else 150.0)

            rec.branch_latitude = b_lat
            rec.branch_longitude = b_lng
            rec.allowed_radius_m = radius

            if b_lat and b_lng and (rec.latitude or rec.longitude):
                dist = self._haversine_meters(rec.latitude, rec.longitude, b_lat, b_lng)
                rec.distance_from_branch_m = dist
                rec.within_geofence = (dist <= radius)
            else:
                rec.distance_from_branch_m = 0.0
                rec.within_geofence = True if not (b_lat and b_lng) else False

    @api.depends('latitude', 'longitude')
    def _compute_map_url(self):
        for rec in self:
            if rec.latitude or rec.longitude:
                rec.map_url = f"https://www.openstreetmap.org/?mlat={rec.latitude:.6f}&mlon={rec.longitude:.6f}#map=17/{rec.latitude:.6f}/{rec.longitude:.6f}"
            else:
                rec.map_url = False

    @api.onchange('employee_id')
    def _onchange_employee_branch_coords(self):
        if self.employee_id:
            self.company_id = self.employee_id.company_id or self.env.company
            self.branch_id = self.employee_id.branch_id
            if self.branch_id and not self.latitude and not self.longitude:
                self.latitude = self.branch_id.latitude or 23.7925
                self.longitude = self.branch_id.longitude or 90.4078

    @api.onchange('latitude', 'longitude')
    def _onchange_coords_detect_area(self):
        if self.latitude or self.longitude:
            area_s, full_s = self._resolve_area_from_coords(self.latitude, self.longitude)
            self.detected_area = area_s
            self.full_geo_address = full_s

    def _sync_to_daily_attendance(self):
        AttLog = self.env['dsl.attendance.log'].sudo()
        for rec in self.sudo():
            if rec.validation_state not in ('auto_verified', 'approved') or not rec.employee_id:
                continue
            area_lbl = rec.detected_area or rec.client_or_site_name or ''
            note = f"GPS {dict(rec._fields['punch_type'].selection).get(rec.punch_type)}"
            if area_lbl:
                note += f" from {area_lbl}"
            note += f" ({rec.distance_from_branch_m}m)"
            daily = AttLog.upsert_punch(
                employee=rec.employee_id,
                punch_dt=rec.punch_datetime,
                source='gps',
                punch_hint=rec.punch_type,
                remarks=note,
                location_name=area_lbl,
            )
            rec.attendance_log_id = daily.id

    @api.model_create_multi
    def create(self, vals_list):
        Employee = self.env['hr.employee'].sudo()
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.gps.attendance.log') or _('New')
            if vals.get('employee_id'):
                emp = Employee.browse(vals['employee_id'])
                if not vals.get('company_id') and emp.company_id:
                    vals['company_id'] = emp.company_id.id
                if not vals.get('branch_id') and emp.branch_id:
                    vals['branch_id'] = emp.branch_id.id
            lat = vals.get('latitude', 0.0)
            lng = vals.get('longitude', 0.0)
            if (lat or lng) and not vals.get('detected_area'):
                area_s, full_s = self._resolve_area_from_coords(float(lat), float(lng))
                vals['detected_area'] = area_s
                if not vals.get('full_geo_address'):
                    vals['full_geo_address'] = full_s

        records = super().create(vals_list)
        for rec in records:
            if rec.within_geofence and rec.work_mode == 'office_geofence':
                rec.validation_state = 'auto_verified'
            else:
                rec.validation_state = 'pending_approval'
        records._sync_to_daily_attendance()
        return records

    def write(self, vals):
        res = super().write(vals)
        if ('latitude' in vals or 'longitude' in vals) and 'detected_area' not in vals:
            for rec in self:
                if rec.latitude or rec.longitude:
                    area_s, full_s = self._resolve_area_from_coords(rec.latitude, rec.longitude)
                    super(DslGpsAttendanceLog, rec).write({
                        'detected_area': area_s,
                        'full_geo_address': full_s,
                    })
        return res

    def action_refresh_area_name(self):
        for rec in self:
            area_s, full_s = self._resolve_area_from_coords(rec.latitude, rec.longitude)
            rec.write({
                'detected_area': area_s,
                'full_geo_address': full_s,
            })
            if rec.attendance_log_id:
                rec._sync_to_daily_attendance()
        return True

    def action_approve_field_punch(self):
        self.write({
            'validation_state': 'approved',
            'approved_by_id': self.env.user.id,
        })
        self._sync_to_daily_attendance()

    def action_reject_field_punch(self):
        self.write({
            'validation_state': 'rejected',
            'approved_by_id': self.env.user.id,
        })

    @api.model
    def rpc_submit_browser_gps_punch(self, punch_type='check_in', latitude=0.0, longitude=0.0, accuracy=15.0, fallback_used=False):
        """RPC endpoint called by One-Click Browser Geolocation Punch Client Action."""
        emp = self.env.user.employee_id
        if not emp:
            emp = self.env['hr.employee'].sudo().search([
                ('company_id', 'in', self.env.companies.ids),
                ('active', '=', True),
            ], limit=1)
        if not emp:
            raise UserError(_('No active Employee profile is linked to your user account!'))

        branch = emp.branch_id
        lat = float(latitude or 0.0)
        lng = float(longitude or 0.0)
        if not lat and not lng:
            lat = (branch.latitude if (branch and branch.latitude) else 23.7925)
            lng = (branch.longitude if (branch and branch.longitude) else 90.4078)

        rec = self.create({
            'employee_id': emp.id,
            'company_id': emp.company_id.id,
            'branch_id': branch.id if branch else False,
            'punch_type': punch_type,
            'work_mode': 'office_geofence',
            'latitude': lat,
            'longitude': lng,
            'accuracy_meters': float(accuracy or 15.0),
            'location_note': 'Browser GPS Check-In (Branch Fallback)' if fallback_used else 'Live Browser HTML5 Geolocation',
        })
        return {
            'id': rec.id,
            'name': rec.name,
            'area': rec.detected_area or '',
            'distance_m': rec.distance_from_branch_m,
            'within_geofence': rec.within_geofence,
            'state': rec.validation_state,
        }
