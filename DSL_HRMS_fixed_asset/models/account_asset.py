# -*- coding: utf-8 -*-
from datetime import timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountAsset(models.Model):
    _inherit = 'account.asset'

    # ------------------------------------------------------------------
    # Identification
    # ------------------------------------------------------------------
    asset_code = fields.Char('Asset Code', copy=False, readonly=True, index=True, tracking=True,
                             help='Unique asset tag number, generated automatically (e.g. FA/2026/00001).')
    asset_barcode = fields.Char('Barcode / RFID', copy=False, tracking=True)
    asset_image = fields.Image('Asset Photo', max_width=1024, max_height=1024)
    serial_number = fields.Char('Serial Number', copy=False, tracking=True)
    model_number = fields.Char('Model Number')
    brand = fields.Char('Brand / Make')
    manufacturer = fields.Char('Manufacturer')
    asset_category_type = fields.Selection([
        ('land', 'Land'),
        ('building', 'Building & Civil Works'),
        ('machinery', 'Plant & Machinery'),
        ('vehicle', 'Vehicle'),
        ('furniture', 'Furniture & Fixture'),
        ('it', 'IT & Computer Equipment'),
        ('office', 'Office Equipment'),
        ('electrical', 'Electrical Equipment'),
        ('intangible', 'Intangible / Software'),
        ('other', 'Other'),
    ], string='Asset Class', default='other', tracking=True)

    # Purchase
    vendor_id = fields.Many2one('res.partner', 'Vendor / Supplier', tracking=True)
    purchase_reference = fields.Char('Purchase / PO Reference')
    purchase_date = fields.Date('Purchase Date')
    in_service_date = fields.Date('Put in Service On')

    # ------------------------------------------------------------------
    # Custody & Location
    # ------------------------------------------------------------------
    dsl_location_id = fields.Many2one('dsl.asset.location', 'Location', tracking=True, index=True)
    dsl_department_id = fields.Many2one('hr.department', 'Department', tracking=True, index=True)
    dsl_employee_id = fields.Many2one('hr.employee', 'Custodian (Employee)', tracking=True, index=True)
    dsl_responsible_user_id = fields.Many2one('res.users', 'Asset Manager', default=lambda self: self.env.user, tracking=True)
    asset_condition = fields.Selection([
        ('new', 'New'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('damaged', 'Damaged'),
        ('scrap', 'Scrap'),
    ], string='Condition', default='new', tracking=True)
    asset_criticality = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], string='Criticality', default='medium')
    custody_state = fields.Selection([
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('maintenance', 'Under Maintenance'),
        ('disposed', 'Disposed'),
    ], string='Availability', compute='_compute_custody_state', store=True)

    # ------------------------------------------------------------------
    # Warranty & Insurance
    # ------------------------------------------------------------------
    warranty_start_date = fields.Date('Warranty Start')
    warranty_end_date = fields.Date('Warranty Expiry', tracking=True)
    warranty_provider_id = fields.Many2one('res.partner', 'Warranty Provider')
    warranty_terms = fields.Text('Warranty Terms')
    warranty_status = fields.Selection([
        ('none', 'No Warranty'),
        ('active', 'Under Warranty'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Expired'),
    ], compute='_compute_warranty_status', string='Warranty Status')

    insurance_policy_no = fields.Char('Insurance Policy No.')
    insurer_id = fields.Many2one('res.partner', 'Insurance Company')
    insured_value = fields.Monetary('Insured Value', currency_field='currency_id')
    insurance_premium = fields.Monetary('Annual Premium', currency_field='currency_id')
    insurance_start_date = fields.Date('Insurance Start')
    insurance_end_date = fields.Date('Insurance Expiry', tracking=True)
    insurance_status = fields.Selection([
        ('none', 'Not Insured'),
        ('active', 'Insured'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Expired'),
    ], compute='_compute_warranty_status', string='Insurance Status')

    # ------------------------------------------------------------------
    # Financial KPIs
    # ------------------------------------------------------------------
    accumulated_depreciation = fields.Monetary(
        'Accumulated Depreciation', compute='_compute_depreciation_kpis', store=True, currency_field='currency_id')
    depreciation_progress = fields.Float('Depreciated (%)', compute='_compute_depreciation_kpis', store=True)
    next_depreciation_date = fields.Date('Next Depreciation', compute='_compute_next_depreciation')
    next_depreciation_amount = fields.Monetary('Next Depreciation Amount', compute='_compute_next_depreciation',
                                               currency_field='currency_id')
    asset_age_display = fields.Char('Asset Age', compute='_compute_asset_age')
    last_verified_date = fields.Date('Last Physically Verified', readonly=True, copy=False)
    asset_notes = fields.Html('Internal Notes')

    # ------------------------------------------------------------------
    # Lifecycle relations
    # ------------------------------------------------------------------
    assignment_ids = fields.One2many('dsl.asset.assignment', 'asset_id', 'Custody History')
    transfer_ids = fields.One2many('dsl.asset.transfer', 'asset_id', 'Transfers')
    maintenance_ids = fields.One2many('dsl.asset.maintenance', 'asset_id', 'Maintenance')
    verification_line_ids = fields.One2many('dsl.asset.verification.line', 'asset_id', 'Verification History')

    assignment_count = fields.Integer(compute='_compute_lifecycle_counts')
    transfer_count = fields.Integer(compute='_compute_lifecycle_counts')
    maintenance_count = fields.Integer(compute='_compute_lifecycle_counts')
    maintenance_cost_total = fields.Monetary('Total Maintenance Cost', compute='_compute_lifecycle_counts',
                                             currency_field='currency_id')
    next_maintenance_date = fields.Date('Next Maintenance', compute='_compute_lifecycle_counts')

    _sql_constraints = [
        ('dsl_asset_code_uniq', 'unique(asset_code, company_id)', 'Asset Code must be unique per company!'),
    ]

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('depreciation_move_ids.state', 'depreciation_move_ids.depreciation_value',
                 'original_value', 'salvage_value', 'already_depreciated_amount_import')
    def _compute_depreciation_kpis(self):
        for asset in self:
            posted = asset.depreciation_move_ids.filtered(lambda m: m.state == 'posted')
            accumulated = sum(posted.mapped('depreciation_value')) + (asset.already_depreciated_amount_import or 0.0)
            asset.accumulated_depreciation = accumulated
            depreciable = (asset.original_value or 0.0) - (asset.salvage_value or 0.0)
            asset.depreciation_progress = round(min(100.0, accumulated / depreciable * 100.0), 2) if depreciable else 0.0

    def _compute_next_depreciation(self):
        for asset in self:
            drafts = asset.depreciation_move_ids.filtered(lambda m: m.state == 'draft').sorted('date')
            asset.next_depreciation_date = drafts[:1].date
            asset.next_depreciation_amount = drafts[:1].depreciation_value if drafts else 0.0

    def _compute_asset_age(self):
        today = fields.Date.context_today(self)
        for asset in self:
            start = asset.in_service_date or asset.acquisition_date
            if not start:
                asset.asset_age_display = False
                continue
            delta = relativedelta(today, start)
            parts = []
            if delta.years:
                parts.append(_('%s yr', delta.years))
            if delta.months:
                parts.append(_('%s mo', delta.months))
            if not parts:
                parts.append(_('%s days', max(delta.days, 0)))
            asset.asset_age_display = ' '.join(parts)

    def _compute_warranty_status(self):
        today = fields.Date.context_today(self)
        soon = today + timedelta(days=30)
        for asset in self:
            for end_field, status_field in (('warranty_end_date', 'warranty_status'),
                                            ('insurance_end_date', 'insurance_status')):
                end = asset[end_field]
                if not end:
                    asset[status_field] = 'none'
                elif end < today:
                    asset[status_field] = 'expired'
                elif end <= soon:
                    asset[status_field] = 'expiring'
                else:
                    asset[status_field] = 'active'

    @api.depends('state', 'dsl_employee_id', 'maintenance_ids.state')
    def _compute_custody_state(self):
        for asset in self:
            if asset.state in ('close', 'cancelled'):
                asset.custody_state = 'disposed'
            elif any(m.state == 'in_progress' for m in asset.maintenance_ids):
                asset.custody_state = 'maintenance'
            elif asset.dsl_employee_id:
                asset.custody_state = 'assigned'
            else:
                asset.custody_state = 'available'

    def _compute_lifecycle_counts(self):
        for asset in self:
            asset.assignment_count = len(asset.assignment_ids)
            asset.transfer_count = len(asset.transfer_ids)
            asset.maintenance_count = len(asset.maintenance_ids)
            asset.maintenance_cost_total = sum(asset.maintenance_ids.filtered(lambda m: m.state == 'done').mapped('cost'))
            upcoming = asset.maintenance_ids.filtered(
                lambda m: m.state in ('draft', 'scheduled') and m.scheduled_date).sorted('scheduled_date')
            asset.next_maintenance_date = upcoming[:1].scheduled_date

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._dsl_assign_asset_code()
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get('state') and vals.get('state') != 'model':
            self._dsl_assign_asset_code()
        return res

    def _dsl_assign_asset_code(self):
        Seq = self.env['ir.sequence'].sudo()
        for asset in self.filtered(lambda a: not a.asset_code and a.state != 'model' and not a.parent_id):
            code = Seq.with_company(asset.company_id).next_by_code('dsl.fixed.asset') or False
            if code:
                super(AccountAsset, asset).write({'asset_code': code})

    @api.model
    def _dsl_backfill_asset_codes(self):
        assets = self.with_context(active_test=False).search(
            [('asset_code', '=', False), ('state', '!=', 'model'), ('parent_id', '=', False)], order='acquisition_date, id')
        assets._dsl_assign_asset_code()
        for asset in assets.filtered(lambda a: a.state in ('open', 'paused') and not a.in_service_date):
            super(AccountAsset, asset).write({'in_service_date': asset.prorata_date or asset.acquisition_date})
        return True

    @api.depends('name', 'asset_code', 'state')
    def _compute_display_name(self):
        super()._compute_display_name()
        for asset in self:
            if asset.asset_code and asset.state != 'model':
                asset.display_name = '[%s] %s' % (asset.asset_code, asset.name or '')

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        if value and operator in ('ilike', 'like', '=', '=like', '=ilike'):
            domain = ['|', '|', '|', ('asset_code', operator, value), ('serial_number', operator, value),
                      ('asset_barcode', operator, value)] + list(domain)
        return domain

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _dsl_open(self, model, name, extra_ctx=None):
        self.ensure_one()
        ctx = {'default_asset_id': self.id}
        ctx.update(extra_ctx or {})
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': model,
            'view_mode': 'list,form',
            'domain': [('asset_id', '=', self.id)],
            'context': ctx,
        }

    def action_view_assignments(self):
        return self._dsl_open('dsl.asset.assignment', _('Custody History'))

    def action_view_transfers(self):
        return self._dsl_open('dsl.asset.transfer', _('Asset Transfers'))

    def action_view_maintenance(self):
        return self._dsl_open('dsl.asset.maintenance', _('Maintenance'))

    def action_assign_custodian(self):
        self.ensure_one()
        return {
            'name': _('Assign Asset'),
            'type': 'ir.actions.act_window',
            'res_model': 'dsl.asset.assignment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_asset_id': self.id,
                'default_department_id': self.dsl_department_id.id,
                'default_location_id': self.dsl_location_id.id,
                'default_condition_out': self.asset_condition,
            },
        }

    def action_return_custody(self):
        for asset in self:
            asset.assignment_ids.filtered(lambda a: a.state == 'assigned').action_return()
        return True

    def action_new_transfer(self):
        self.ensure_one()
        return {
            'name': _('Transfer Asset'),
            'type': 'ir.actions.act_window',
            'res_model': 'dsl.asset.transfer',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_asset_id': self.id},
        }

    def action_new_maintenance(self):
        self.ensure_one()
        return {
            'name': _('Schedule Maintenance'),
            'type': 'ir.actions.act_window',
            'res_model': 'dsl.asset.maintenance',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_asset_id': self.id, 'default_vendor_id': self.warranty_provider_id.id or self.vendor_id.id},
        }

    def action_sell_dispose(self):
        self.ensure_one()
        if self.state not in ('open', 'paused'):
            raise UserError(_('Only running or paused assets can be sold or disposed.'))
        return self.action_asset_modify()

    def action_print_asset_tag(self):
        return self.env.ref('DSL_HRMS_fixed_asset.action_report_asset_tag').report_action(self)

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    @api.model
    def get_fixed_asset_dashboard(self):
        company_ids = self.env.companies.ids
        today = fields.Date.context_today(self)
        base = [('state', 'not in', ('model', 'cancelled')), ('parent_id', '=', False),
                ('company_id', 'in', company_ids)]
        assets = self.search(base)
        live = assets.filtered(lambda a: a.state in ('draft', 'open', 'paused'))
        currency = self.env.company.currency_id

        gross = sum(live.mapped('original_value'))
        accumulated = sum(live.mapped('accumulated_depreciation'))
        nbv = sum(live.mapped('book_value'))

        month_start = today.replace(day=1)
        month_end = month_start + relativedelta(months=1, days=-1)
        Move = self.env['account.move']
        month_moves = Move.search([
            ('asset_id', 'in', assets.ids), ('date', '>=', month_start), ('date', '<=', month_end),
            ('state', 'in', ('draft', 'posted')),
        ])
        year_start = today.replace(month=1, day=1)
        ytd_moves = Move.search([
            ('asset_id', 'in', assets.ids), ('date', '>=', year_start), ('date', '<=', today), ('state', '=', 'posted'),
        ])

        def _breakdown(key_func, label_func):
            data = {}
            for a in live:
                key = key_func(a)
                entry = data.setdefault(key, {'label': label_func(a), 'count': 0, 'value': 0.0, 'nbv': 0.0})
                entry['count'] += 1
                entry['value'] += a.original_value
                entry['nbv'] += a.book_value
            rows = sorted(data.values(), key=lambda r: r['value'], reverse=True)
            top = max([r['value'] for r in rows] or [0.0]) or 1.0
            for r in rows:
                r['pct'] = round(r['value'] / top * 100.0, 1)
            return rows[:8]

        class_labels = dict(self._fields['asset_category_type'].selection)
        by_group = _breakdown(lambda a: a.asset_group_id.id or a.model_id.id or 0,
                              lambda a: a.asset_group_id.name or a.model_id.name or _('Ungrouped'))
        by_class = _breakdown(lambda a: a.asset_category_type or 'other',
                              lambda a: class_labels.get(a.asset_category_type or 'other'))
        by_location = _breakdown(lambda a: a.dsl_location_id.id or 0,
                                 lambda a: a.dsl_location_id.complete_name or _('No Location'))
        by_department = _breakdown(lambda a: a.dsl_department_id.id or 0,
                                   lambda a: a.dsl_department_id.name or _('No Department'))

        state_labels = dict(self._fields['state'].selection)
        status = []
        for st, color in (('open', '#10b981'), ('draft', '#3b82f6'), ('paused', '#f59e0b'), ('close', '#94a3b8')):
            cnt = len(assets.filtered(lambda a, s=st: a.state == s))
            status.append({'key': st, 'label': state_labels.get(st), 'count': cnt, 'color': color})

        soon = today + timedelta(days=30)
        warranty_soon = live.filtered(lambda a: a.warranty_end_date and today <= a.warranty_end_date <= soon)
        insurance_soon = live.filtered(lambda a: a.insurance_end_date and today <= a.insurance_end_date <= soon)

        Maint = self.env['dsl.asset.maintenance']
        upcoming_maint = Maint.search([('state', 'in', ('draft', 'scheduled')), ('company_id', 'in', company_ids),
                                       ('scheduled_date', '!=', False)], order='scheduled_date', limit=6)
        in_progress = Maint.search_count([('state', '=', 'in_progress'), ('company_id', 'in', company_ids)])
        maint_cost_ytd = sum(Maint.search([('state', '=', 'done'), ('company_id', 'in', company_ids),
                                           ('completion_date', '>=', year_start)]).mapped('cost'))

        # 12 month depreciation trend (posted + planned)
        trend = []
        trend_start = month_start - relativedelta(months=5)
        all_moves = Move.search([('asset_id', 'in', assets.ids), ('date', '>=', trend_start),
                                 ('date', '<', trend_start + relativedelta(months=12)),
                                 ('state', 'in', ('draft', 'posted'))])
        for i in range(12):
            m_start = trend_start + relativedelta(months=i)
            m_end = m_start + relativedelta(months=1)
            mv = all_moves.filtered(lambda m, s=m_start, e=m_end: s <= m.date < e)
            trend.append({
                'label': m_start.strftime('%b %y'),
                'posted': sum(mv.filtered(lambda m: m.state == 'posted').mapped('depreciation_value')),
                'planned': sum(mv.filtered(lambda m: m.state == 'draft').mapped('depreciation_value')),
                'current': m_start == month_start,
            })
        trend_max = max([t['posted'] + t['planned'] for t in trend] or [0.0]) or 1.0
        for t in trend:
            t['pct_posted'] = round(t['posted'] / trend_max * 100.0, 1)
            t['pct_planned'] = round(t['planned'] / trend_max * 100.0, 1)

        recent = assets.sorted(lambda a: a.create_date or fields.Datetime.now(), reverse=True)[:6]

        return {
            'currency': {'symbol': currency.symbol, 'position': currency.position},
            'kpi': {
                'total_assets': len(assets),
                'running': len(assets.filtered(lambda a: a.state == 'open')),
                'draft': len(assets.filtered(lambda a: a.state == 'draft')),
                'closed': len(assets.filtered(lambda a: a.state == 'close')),
                'gross': gross,
                'accumulated': accumulated,
                'nbv': nbv,
                'dep_pct': round(accumulated / gross * 100.0, 1) if gross else 0.0,
                'month_depr': sum(month_moves.mapped('depreciation_value')),
                'ytd_depr': sum(ytd_moves.mapped('depreciation_value')),
                'assigned': len(live.filtered(lambda a: a.custody_state == 'assigned')),
                'available': len(live.filtered(lambda a: a.custody_state == 'available')),
                'maintenance': in_progress,
                'maint_cost_ytd': maint_cost_ytd,
                'warranty_soon': len(warranty_soon),
                'insurance_soon': len(insurance_soon),
                'no_location': len(live.filtered(lambda a: not a.dsl_location_id)),
                'locations': self.env['dsl.asset.location'].search_count([]),
            },
            'status': status,
            'by_group': by_group,
            'by_class': by_class,
            'by_location': by_location,
            'by_department': by_department,
            'trend': trend,
            'upcoming_maintenance': [{
                'id': m.id, 'name': m.name, 'asset': m.asset_id.display_name,
                'date': fields.Date.to_string(m.scheduled_date),
                'type': dict(m._fields['maintenance_type'].selection).get(m.maintenance_type),
                'overdue': bool(m.scheduled_date and m.scheduled_date < today),
            } for m in upcoming_maint],
            'expiring': [{
                'id': a.id, 'asset': a.display_name,
                'kind': _('Warranty') if a in warranty_soon else _('Insurance'),
                'date': fields.Date.to_string(a.warranty_end_date if a in warranty_soon else a.insurance_end_date),
            } for a in (warranty_soon | insurance_soon)[:6]],
            'recent': [{
                'id': a.id, 'name': a.name, 'code': a.asset_code or '',
                'value': a.original_value, 'nbv': a.book_value, 'state': a.state,
                'state_label': state_labels.get(a.state), 'progress': a.depreciation_progress,
            } for a in recent],
        }

    # ------------------------------------------------------------------
    # Cron: reminders
    # ------------------------------------------------------------------
    @api.model
    def _cron_dsl_asset_reminders(self):
        today = fields.Date.context_today(self)
        soon = today + timedelta(days=30)
        todo = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not todo:
            return True
        live = self.search([('state', 'in', ('open', 'paused', 'draft')), ('parent_id', '=', False)])

        def _schedule(asset, summary, deadline):
            if asset.activity_ids.filtered(lambda act: act.summary == summary):
                return
            asset.activity_schedule(
                activity_type_id=todo.id, summary=summary, date_deadline=deadline,
                user_id=(asset.dsl_responsible_user_id or self.env.user).id)

        for asset in live:
            if asset.warranty_end_date and today <= asset.warranty_end_date <= soon:
                _schedule(asset, _('Warranty expires on %s', asset.warranty_end_date), asset.warranty_end_date)
            if asset.insurance_end_date and today <= asset.insurance_end_date <= soon:
                _schedule(asset, _('Insurance expires on %s', asset.insurance_end_date), asset.insurance_end_date)

        Maint = self.env['dsl.asset.maintenance']
        for m in Maint.search([('state', 'in', ('draft', 'scheduled')),
                               ('scheduled_date', '<=', today + timedelta(days=7))]):
            summary = _('Maintenance due: %s', m.name)
            if not m.asset_id.activity_ids.filtered(lambda act: act.summary == summary):
                m.asset_id.activity_schedule(
                    activity_type_id=todo.id, summary=summary, date_deadline=m.scheduled_date,
                    user_id=(m.responsible_user_id or m.asset_id.dsl_responsible_user_id or self.env.user).id)
        return True
