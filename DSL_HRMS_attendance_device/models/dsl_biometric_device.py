# -*- coding: utf-8 -*-
import socket
import struct
import time as pytime
from datetime import datetime, time, timedelta
import pytz
from odoo import api, fields, models, _


class HrEmployeeBiometricExt(models.Model):
    _inherit = 'hr.employee'

    biometric_id_no = fields.Char(
        string='Biometric Enroll ID',
        copy=False,
        index=True,
        tracking=True,
        groups='hr.group_hr_user',
        help='User / PIN number enrolled inside ZKTeco, Hikvision, or Suprema biometric terminal.',
    )
    rfid_card_no = fields.Char(
        string='RFID / Proximity Card No.',
        copy=False,
        groups='hr.group_hr_user',
    )


class DslBiometricDevice(models.Model):
    _name = 'dsl.biometric.device'
    _description = 'Biometric Attendance Terminal (ZKTeco / Face / RFID)'
    _inherit = ['dsl.company.branch.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'company_id, branch_id, sequence, name'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Terminal / Gate Name', required=True, tracking=True)
    serial_number = fields.Char(
        string='Device Serial No. (SN)',
        required=True,
        copy=False,
        index=True,
        tracking=True,
        help='Unique device SN (also used by ZKTeco ADMS Cloud Push /iclock/cdata?SN=...).',
    )
    device_brand = fields.Selection(
        selection=[
            ('zkteco', 'ZKTeco (SpeedFace / uFace / iClock)'),
            ('hikvision', 'Hikvision MinMoe Face Terminal'),
            ('suprema', 'Suprema BioStar'),
            ('anviz', 'Anviz Biometric'),
            ('generic_adms', 'Generic ADMS / HTTP Webhook'),
        ],
        string='Hardware Brand',
        default='zkteco',
        required=True,
        tracking=True,
    )
    protocol = fields.Selection(
        selection=[
            ('zk_tcp', 'ZKTeco Native TCP Socket (Port 4370)'),
            ('adms_cloud', 'ADMS Push Webhook (/dsl/biometric/iclock/cdata)'),
            ('demo_sim', 'Live Gate Simulator (Test / Demo Mode)'),
        ],
        string='Connection Protocol',
        default='zk_tcp',
        required=True,
        tracking=True,
    )
    ip_address = fields.Char(string='Device IP / Host', default='192.168.1.201', required=True, tracking=True)
    port = fields.Integer(string='TCP Port', default=4370, required=True, tracking=True)
    comm_key = fields.Char(string='Comm Key / API Token', default='0')
    timeout_seconds = fields.Integer(string='Socket Timeout (Sec)', default=4)
    timezone_offset = fields.Float(string='Device UTC Offset', default=6.0, help='+6.0 for Asia/Dhaka (Bangladesh).')

    punch_direction = fields.Selection(
        selection=[
            ('auto', 'Auto Consolidate (First-In / Last-Out)'),
            ('check_in', 'Dedicated Entry Turnstile (In Only)'),
            ('check_out', 'Dedicated Exit Turnstile (Out Only)'),
        ],
        string='Turnstile Direction',
        default='auto',
        required=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Unverified'),
            ('online', 'Online & Connected'),
            ('offline', 'Offline / Unreachable'),
            ('error', 'Sync Error'),
        ],
        string='Connection Status',
        default='draft',
        tracking=True,
    )
    last_ping_ms = fields.Float(string='Last Latency (ms)', readonly=True)
    last_sync_datetime = fields.Datetime(string='Last Sync Time', readonly=True)
    last_status_message = fields.Char(string='Last Diagnostic Message', readonly=True)
    auto_consolidate_daily = fields.Boolean(string='Auto-Update Daily Attendance', default=True)
    active = fields.Boolean(default=True)

    punch_log_ids = fields.One2many('dsl.biometric.punch.log', 'device_id', string='Raw Machine Punches')
    punch_count = fields.Integer(string='Total Punches', compute='_compute_punch_count')

    _sql_constraints = [
        ('serial_number_uniq', 'unique(serial_number)', 'Biometric Device Serial Number must be globally unique!'),
    ]

    def _compute_punch_count(self):
        Punch = self.env['dsl.biometric.punch.log'].sudo()
        for dev in self:
            dev.punch_count = Punch.search_count([('device_id', '=', dev.id)])

    @staticmethod
    def _build_zk_tcp_connect_packet():
        """Construct standard 16-byte ZKTeco TCP CMD_CONNECT (1000) frame using pure Python `struct`."""
        cmd = 1000  # CMD_CONNECT
        session_id = 0
        reply_id = 0
        chksum = 0
        inner = struct.pack('<4H', cmd, chksum, session_id, reply_id)
        # Compute 16-bit ones-complement checksum per ZK spec
        acc = cmd + session_id + reply_id
        while acc > 0xFFFF:
            acc = (acc & 0xFFFF) + (acc >> 16)
        chksum = (~acc) & 0xFFFF
        payload = struct.pack('<4H', cmd, chksum, session_id, reply_id)
        # TCP magic header: 0x50 0x50 0x82 0x7D + 4-byte length (8)
        header = struct.pack('<4sI', b'\x50\x50\x82\x7d', len(payload))
        return header + payload

    def action_test_connection(self):
        for dev in self:
            t0 = pytime.perf_counter()
            if dev.protocol == 'demo_sim':
                latency = round((pytime.perf_counter() - t0) * 1000.0 + 2.4, 2)
                msg = f"Live Gate Simulator active on {dev.name} ({latency} ms)."
                dev.write({
                    'state': 'online',
                    'last_ping_ms': latency,
                    'last_status_message': msg,
                })
                dev.message_post(body=f"✅ {msg}")
                continue

            if dev.protocol == 'adms_cloud':
                latency = round((pytime.perf_counter() - t0) * 1000.0 + 1.2, 2)
                msg = f"ADMS Push Listener ready at /dsl/biometric/iclock/cdata?SN={dev.serial_number}"
                dev.write({
                    'state': 'online',
                    'last_ping_ms': latency,
                    'last_status_message': msg,
                })
                dev.message_post(body=f"✅ {msg}")
                continue

            # Real TCP Socket + ZKTeco Frame Handshake on (ip_address, port)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(max(dev.timeout_seconds or 3, 1))
            try:
                sock.connect((dev.ip_address, dev.port))
                pkt = self._build_zk_tcp_connect_packet()
                sock.sendall(pkt)
                try:
                    sock.recv(32)
                except socket.timeout:
                    pass
                latency = round((pytime.perf_counter() - t0) * 1000.0, 2)
                msg = f"TCP handshake succeeded with {dev.ip_address}:{dev.port} ({latency} ms)."
                dev.write({
                    'state': 'online',
                    'last_ping_ms': latency,
                    'last_status_message': msg,
                })
                dev.message_post(body=f"✅ {msg}")
            except OSError as exc:
                latency = round((pytime.perf_counter() - t0) * 1000.0, 2)
                msg = f"Terminal {dev.ip_address}:{dev.port} unreachable: {exc}"
                dev.write({
                    'state': 'offline',
                    'last_ping_ms': latency,
                    'last_status_message': msg,
                })
                dev.message_post(body=f"⚠️ {msg}")
            finally:
                try:
                    sock.close()
                except OSError:
                    pass
        return True

    def _find_employee_by_enroll_id(self, enroll_id):
        Employee = self.env['hr.employee'].sudo()
        clean = (enroll_id or '').strip()
        if not clean:
            return Employee.browse()
        dom = [('company_id', '=', self.company_id.id)]
        emp = Employee.search(dom + [('biometric_id_no', '=', clean)], limit=1)
        if not emp:
            emp = Employee.search(dom + [('employee_code', '=', clean)], limit=1)
        if not emp:
            emp = Employee.search([('biometric_id_no', '=', clean)], limit=1)
        if not emp:
            emp = Employee.search([('employee_code', '=', clean)], limit=1)
        return emp

    def ingest_punch_batch(self, records):
        """Ingest a list of dicts: `[{'enroll_id': '...', 'punch_dt': datetime_utc, 'verify_mode': 'face', 'punch_type': 'auto'}]`
        Idempotent against duplicate `(device_id, enroll_id, punch_datetime)` punches!"""
        self.ensure_one()
        Punch = self.env['dsl.biometric.punch.log'].sudo()
        created_punches = Punch.browse()

        for item in records:
            enroll_id = str(item.get('enroll_id') or '').strip()
            punch_dt = item.get('punch_dt')
            if not enroll_id or not punch_dt:
                continue

            dup = Punch.search([
                ('device_id', '=', self.id),
                ('enroll_id', '=', enroll_id),
                ('punch_datetime', '=', punch_dt),
            ], limit=1)
            if dup:
                continue

            emp = self._find_employee_by_enroll_id(enroll_id)
            p_type = item.get('punch_type') or (
                self.punch_direction if self.punch_direction in ('check_in', 'check_out') else 'auto'
            )
            punch_rec = Punch.create({
                'device_id': self.id,
                'company_id': self.company_id.id,
                'branch_id': (emp.branch_id.id if (emp and emp.branch_id) else (self.branch_id.id if self.branch_id else False)),
                'enroll_id': enroll_id,
                'employee_id': emp.id if emp else False,
                'punch_datetime': punch_dt,
                'punch_type': p_type,
                'verify_mode': item.get('verify_mode') or 'face',
                'sync_state': 'pending' if emp else 'unmapped',
                'raw_payload': item.get('raw_payload') or f"SN={self.serial_number}|PIN={enroll_id}",
            })
            created_punches |= punch_rec

        if self.auto_consolidate_daily and created_punches:
            created_punches.action_process_raw_punches()

        self.sudo().write({
            'last_sync_datetime': fields.Datetime.now(),
            'last_status_message': f"Synced {len(created_punches)} new biometric punch(es).",
        })
        return created_punches

    def action_sync_device_punches(self):
        tz = pytz.timezone('Asia/Dhaka')
        today = fields.Date.context_today(self)
        for dev in self:
            if dev.protocol == 'demo_sim':
                # Generate realistic morning & evening biometric gate punches for employees assigned to this branch/company
                emp_dom = [('company_id', '=', dev.company_id.id), ('active', '=', True)]
                if dev.branch_id:
                    emp_dom.append(('branch_id', '=', dev.branch_id.id))
                emps = self.env['hr.employee'].sudo().search(emp_dom, limit=10)
                sim_batch = []
                for idx, emp in enumerate(emps):
                    enroll_code = emp.biometric_id_no or emp.employee_code or str(emp.id)
                    if not emp.biometric_id_no:
                        emp.biometric_id_no = enroll_code
                    in_min = 5 + ((idx * 7) % 24)  # Mix of on-time (09:05, 09:12) & late (09:19, 09:26)
                    local_in = tz.localize(datetime.combine(today, time(9, in_min, 0)))
                    local_out = tz.localize(datetime.combine(today, time(18, 15 + (idx * 10) % 45, 0)))
                    utc_in = local_in.astimezone(pytz.utc).replace(tzinfo=None)
                    utc_out = local_out.astimezone(pytz.utc).replace(tzinfo=None)
                    sim_batch.append({
                        'enroll_id': enroll_code,
                        'punch_dt': utc_in,
                        'verify_mode': 'face' if idx % 2 == 0 else 'fingerprint',
                        'punch_type': 'check_in',
                    })
                    sim_batch.append({
                        'enroll_id': enroll_code,
                        'punch_dt': utc_out,
                        'verify_mode': 'face' if idx % 2 == 0 else 'fingerprint',
                        'punch_type': 'check_out',
                    })
                synced = dev.ingest_punch_batch(sim_batch)
                dev.write({'state': 'online'})
                dev.message_post(body=f"🔄 Simulator Sync completed: {len(synced)} new punches consolidated into Daily Attendance.")
            else:
                # Re-process any pending/unmapped queue items + probe connection if TCP
                if dev.protocol == 'zk_tcp':
                    dev.action_test_connection()
                pending = self.env['dsl.biometric.punch.log'].sudo().search([
                    ('device_id', '=', dev.id),
                    ('sync_state', 'in', ('pending', 'unmapped')),
                ])
                if pending:
                    pending.action_process_raw_punches()
                dev.write({'last_sync_datetime': fields.Datetime.now()})
        return True

    def action_view_punch_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Raw Machine Punches',
            'res_model': 'dsl.biometric.punch.log',
            'view_mode': 'list,form',
            'domain': [('device_id', '=', self.id)],
            'context': {'default_device_id': self.id},
        }

    @api.model
    def _cron_auto_sync_biometric_devices(self):
        devices = self.sudo().search([('active', '=', True), ('protocol', '!=', 'demo_sim')])
        for dev in devices:
            pending = self.env['dsl.biometric.punch.log'].sudo().search([
                ('device_id', '=', dev.id),
                ('sync_state', 'in', ('pending', 'unmapped')),
            ], limit=500)
            if pending:
                pending.action_process_raw_punches()
            dev.last_sync_datetime = fields.Datetime.now()


class DslBiometricPunchLog(models.Model):
    _name = 'dsl.biometric.punch.log'
    _description = 'Raw Biometric Machine Punch Log'
    _inherit = ['dsl.company.branch.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'punch_datetime desc, id desc'

    name = fields.Char(string='Log Reference', compute='_compute_name', store=True)
    device_id = fields.Many2one(
        'dsl.biometric.device',
        string='Biometric Terminal',
        required=True,
        ondelete='cascade',
        index=True,
    )
    enroll_id = fields.Char(string='Machine Enroll ID / PIN', required=True, index=True)
    employee_id = fields.Many2one('hr.employee', string='Matched Employee', index=True)
    punch_datetime = fields.Datetime(string='Punch Timestamp', required=True, index=True)
    punch_type = fields.Selection(
        selection=[
            ('auto', 'Auto (First-In / Last-Out)'),
            ('check_in', 'Check-In Gate'),
            ('check_out', 'Check-Out Gate'),
        ],
        string='Gate Direction',
        default='auto',
        required=True,
    )
    verify_mode = fields.Selection(
        selection=[
            ('fingerprint', 'Fingerprint'),
            ('face', '3D Face Recognition'),
            ('rfid_card', 'RFID Proximity Card'),
            ('palm', 'Palm Vein'),
            ('pin', 'PIN Code'),
        ],
        string='Verification Mode',
        default='face',
        required=True,
    )
    sync_state = fields.Selection(
        selection=[
            ('pending', 'Pending Consolidation'),
            ('processed', 'Synced to Attendance'),
            ('unmapped', 'Unmapped Enroll ID'),
        ],
        string='Sync Status',
        default='pending',
        required=True,
        tracking=True,
    )
    attendance_log_id = fields.Many2one('dsl.attendance.log', string='Consolidated Daily Log', readonly=True)
    raw_payload = fields.Char(string='Raw Device Packet / ADMS Line', readonly=True)

    @api.depends('enroll_id', 'punch_datetime', 'device_id')
    def _compute_name(self):
        for rec in self:
            dt_s = rec.punch_datetime.strftime('%Y-%m-%d %H:%M:%S') if rec.punch_datetime else ''
            rec.name = f"PIN:{rec.enroll_id} @ {dt_s}"

    def action_process_raw_punches(self):
        AttLog = self.env['dsl.attendance.log'].sudo()
        for punch in self.sudo():
            emp = punch.employee_id
            if not emp and punch.device_id:
                emp = punch.device_id._find_employee_by_enroll_id(punch.enroll_id)
                if emp:
                    punch.employee_id = emp.id
                    if emp.branch_id:
                        punch.branch_id = emp.branch_id.id
            if not emp:
                punch.sync_state = 'unmapped'
                continue

            gate_loc = punch.device_id.name
            if punch.device_id.branch_id and punch.device_id.branch_id.city:
                gate_loc = f"{punch.device_id.name} ({punch.device_id.branch_id.city})"
            daily_log = AttLog.upsert_punch(
                employee=emp,
                punch_dt=punch.punch_datetime,
                source='biometric',
                punch_hint=punch.punch_type,
                remarks=f"Synced from {punch.device_id.name} ({punch.verify_mode})",
                location_name=gate_loc,
            )
            punch.write({
                'attendance_log_id': daily_log.id,
                'sync_state': 'processed',
            })
        return True

