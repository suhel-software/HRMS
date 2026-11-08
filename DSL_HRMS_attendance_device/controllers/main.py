# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from odoo import http
from odoo.http import request


class DslBiometricAdmsController(http.Controller):
    """Native ZKTeco ADMS Cloud Push (`/dsl/biometric/iclock/cdata`) & JSON Webhook Receiver."""

    @http.route('/dsl/biometric/iclock/cdata', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def iclock_cdata(self, SN=None, table=None, **kw):
        serial = (SN or kw.get('sn') or '').strip()
        if not serial:
            return request.make_response('ERROR: Missing SN', headers=[('Content-Type', 'text/plain')])

        device = request.env['dsl.biometric.device'].sudo().search([('serial_number', '=', serial)], limit=1)
        if not device:
            return request.make_response('ERROR: Unknown Device SN', headers=[('Content-Type', 'text/plain')])

        if request.httprequest.method == 'GET':
            device.write({'state': 'online'})
            return request.make_response('OK', headers=[('Content-Type', 'text/plain')])

        body = (request.httprequest.data or b'').decode('utf-8', errors='ignore').strip()
        if not body:
            return request.make_response('OK: 0', headers=[('Content-Type', 'text/plain')])

        offset_hours = device.timezone_offset if device.timezone_offset is not None else 6.0
        verify_map = {
            '0': 'pin',
            '1': 'fingerprint',
            '4': 'rfid_card',
            '15': 'face',
        }
        status_map = {
            '0': 'check_in',
            '1': 'check_out',
        }

        batch = []
        for line in body.splitlines():
            parts = line.strip().split('\t')
            if len(parts) < 2:
                continue
            pin = parts[0].strip()
            dt_str = parts[1].strip()
            st_code = parts[2].strip() if len(parts) > 2 else ''
            vf_code = parts[3].strip() if len(parts) > 3 else '15'
            try:
                local_naive = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
                utc_dt = local_naive - timedelta(hours=offset_hours)
            except ValueError:
                continue
            batch.append({
                'enroll_id': pin,
                'punch_dt': utc_dt,
                'punch_type': status_map.get(st_code, 'auto'),
                'verify_mode': verify_map.get(vf_code, 'face'),
                'raw_payload': line.strip()[:250],
            })

        synced = device.ingest_punch_batch(batch)
        device.write({'state': 'online'})
        return request.make_response(f'OK: {len(synced)}', headers=[('Content-Type', 'text/plain')])

