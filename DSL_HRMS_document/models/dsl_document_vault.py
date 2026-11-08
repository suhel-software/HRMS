# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import api, fields, models, _


class DslDocumentType(models.Model):
    _name = 'dsl.document.type'
    _description = 'HR Document Checklist Type'
    _order = 'sequence, name'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Document Type', required=True)
    code = fields.Char(string='Short Code', required=True)
    category = fields.Selection(
        selection=[
            ('identity', 'Identity & Citizenship'),
            ('employment', 'Employment & Contracts'),
            ('statutory', 'Tax, Visa & Statutory'),
            ('compliance', 'Medical, Safety & Background'),
            ('other', 'Other Dossier File'),
        ],
        string='Category',
        default='identity',
        required=True,
    )
    is_mandatory = fields.Boolean(string='Mandatory Onboarding Doc', default=False)
    requires_expiry = fields.Boolean(string='Track Expiry Date', default=False)
    alert_days_before = fields.Integer(string='Alert Before (Days)', default=30)
    active = fields.Boolean(default=True)
    document_count = fields.Integer(compute='_compute_document_count', string='Archived Files')

    def _compute_document_count(self):
        Doc = self.env['dsl.employee.document'].sudo()
        for rec in self:
            rec.document_count = Doc.search_count([('document_type_id', '=', rec.id)])


class DslEmployeeDocument(models.Model):
    _name = 'dsl.employee.document'
    _description = 'Employee Digital Document Vault'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'expiry_date asc, id desc'

    doc_number = fields.Char(
        string='Vault ID',
        readonly=True,
        copy=False,
        default=lambda self: _('New'),
    )
    name = fields.Char(
        string='Document Title',
        required=True,
        tracking=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='employee_id.company_id',
        store=True,
        index=True,
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Branch',
        related='employee_id.branch_id',
        store=True,
        index=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        related='employee_id.department_id',
        store=True,
    )
    document_type_id = fields.Many2one(
        'dsl.document.type',
        string='Document Type',
        required=True,
        tracking=True,
    )
    reference_no = fields.Char(
        string='Document / ID Number',
        tracking=True,
        help='Passport No., Smart NID No., License No., or Contract Ref.',
    )
    issue_date = fields.Date(string='Issue Date')
    expiry_date = fields.Date(string='Expiry Date', tracking=True)
    alert_days_before = fields.Integer(
        string='Alert Window (Days)',
        default=30,
    )
    days_to_expiry = fields.Integer(
        string='Days Remaining',
        compute='_compute_days_to_expiry',
    )
    expiry_status = fields.Selection(
        selection=[
            ('lifetime', 'No Expiry / Lifetime'),
            ('valid', 'Valid'),
            ('expiring_soon', 'Expiring Soon'),
            ('expired', 'Expired'),
        ],
        string='Validity Status',
        compute='_compute_expiry_status',
        store=True,
    )
    verification_state = fields.Selection(
        selection=[
            ('pending', 'Pending HR Review'),
            ('verified', 'Verified'),
            ('rejected', 'Re-upload Needed'),
        ],
        string='Verification Status',
        default='pending',
        required=True,
        tracking=True,
    )
    verified_by = fields.Many2one('res.users', string='Verified By', readonly=True)
    verified_date = fields.Date(string='Verified On', readonly=True)

    attachment_file = fields.Binary(string='Digital File / Scan', attachment=True)
    attachment_filename = fields.Char(string='File Name')
    is_confidential = fields.Boolean(string='Confidential HR File', default=False)
    notes = fields.Text(string='HR Notes & Remarks')

    @api.onchange('document_type_id')
    def _onchange_document_type_defaults(self):
        if self.document_type_id:
            if not self.name:
                self.name = self.document_type_id.name
            self.alert_days_before = self.document_type_id.alert_days_before or 30

    @api.depends('expiry_date')
    def _compute_days_to_expiry(self):
        today = fields.Date.context_today(self)
        for doc in self:
            if not doc.expiry_date:
                doc.days_to_expiry = 0
            else:
                doc.days_to_expiry = (doc.expiry_date - today).days

    @api.depends('expiry_date', 'alert_days_before')
    def _compute_expiry_status(self):
        today = fields.Date.context_today(self)
        for doc in self:
            if not doc.expiry_date:
                doc.expiry_status = 'lifetime'
            else:
                delta = (doc.expiry_date - today).days
                window = doc.alert_days_before or 30
                if delta < 0:
                    doc.expiry_status = 'expired'
                elif delta <= window:
                    doc.expiry_status = 'expiring_soon'
                else:
                    doc.expiry_status = 'valid'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('doc_number') or vals.get('doc_number') == _('New'):
                vals['doc_number'] = self.env['ir.sequence'].sudo().next_by_code('dsl.employee.document') or 'DOC-00001'
        return super().create(vals_list)

    def action_verify_document(self):
        today = fields.Date.context_today(self)
        for doc in self:
            doc.write({
                'verification_state': 'verified',
                'verified_by': self.env.user.id,
                'verified_date': today,
            })

    def action_reject_document(self):
        for doc in self:
            doc.write({'verification_state': 'rejected'})

    def action_reset_pending(self):
        for doc in self:
            doc.write({'verification_state': 'pending'})

    @api.model
    def _cron_check_document_expiry_alerts(self):
        """Daily cron: refresh stored `expiry_status` on dated documents and create HR follow-up
        activities for documents entering their alert window or expired."""
        dated_docs = self.sudo().search([('expiry_date', '!=', False), ('employee_id.active', '=', True)])
        dated_docs._compute_expiry_status()

        todo_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        hr_mgr_group = self.env.ref('DSL_HRMS_core.group_dsl_hrms_manager', raise_if_not_found=False)
        fallback_user = (
            hr_mgr_group.users[:1] if (hr_mgr_group and hr_mgr_group.users) else self.env.ref('base.user_admin', raise_if_not_found=False)
        )

        alert_docs = dated_docs.filtered(lambda d: d.expiry_status in ('expiring_soon', 'expired'))
        for doc in alert_docs:
            existing_act = self.env['mail.activity'].sudo().search_count([
                ('res_model', '=', 'dsl.employee.document'),
                ('res_id', '=', doc.id),
            ])
            if existing_act or not todo_type:
                continue
            target_user = doc.employee_id.parent_id.user_id or fallback_user
            if target_user:
                status_word = 'HAS EXPIRED' if doc.expiry_status == 'expired' else f'expires in {doc.days_to_expiry} days'
                doc.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=target_user.id,
                    date_deadline=max(doc.expiry_date, fields.Date.context_today(self)),
                    summary=f'Document Alert: {doc.name} ({doc.employee_id.name}) {status_word}',
                )


class HrEmployeeDocumentInherit(models.Model):
    _inherit = 'hr.employee'

    dsl_document_ids = fields.One2many(
        'dsl.employee.document',
        'employee_id',
        string='Digital Document Vault',
        groups='hr.group_hr_user',
    )
    dsl_document_count = fields.Integer(
        string='Documents',
        compute='_compute_dsl_document_counts',
        groups='hr.group_hr_user',
    )
    dsl_expiring_doc_count = fields.Integer(
        string='Expiring / Expired Docs',
        compute='_compute_dsl_document_counts',
        groups='hr.group_hr_user',
    )

    def _compute_dsl_document_counts(self):
        Doc = self.env['dsl.employee.document'].sudo()
        for emp in self:
            emp.dsl_document_count = Doc.search_count([('employee_id', '=', emp.id)])
            emp.dsl_expiring_doc_count = Doc.search_count([
                ('employee_id', '=', emp.id),
                ('expiry_status', 'in', ('expiring_soon', 'expired')),
            ])

    def action_view_employee_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Digital Document Vault',
            'res_model': 'dsl.employee.document',
            'view_mode': 'kanban,list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
