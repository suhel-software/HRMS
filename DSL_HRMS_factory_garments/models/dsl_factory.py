# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class DslFactoryLineRoster(models.Model):
    _name = 'dsl.factory.line.roster'
    _description = 'Factory Floor & Garments Sewing Line Daily Worker Sheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'production_date desc, id desc'

    name = fields.Char(string='Floor Sheet Ref.', required=True, copy=False, readonly=True, default=lambda self: _('New'), index=True)
    production_date = fields.Date(string='Production Date', default=fields.Date.context_today, required=True, index=True)
    company_id = fields.Many2one('res.company', string='Factory Entity', required=True, default=lambda self: self.env.company, index=True)
    branch_id = fields.Many2one('dsl.branch', string='Plant / Unit', domain="[('company_id', '=', company_id)]")
    floor_line_id = fields.Many2one('hr.department', string='Floor / Sewing Line', required=True, tracking=True)
    line_supervisor_id = fields.Many2one('hr.employee', string='Line Chief / Supervisor')

    style_buyer_ref = fields.Char(string='Buyer / Style Order (e.g. H&M / Zara Knit Polo)')
    operators_present = fields.Integer(string='Operators Present', default=42)
    helpers_present = fields.Integer(string='Helpers / Ironmen Present', default=14)
    total_manpower = fields.Integer(string='Total Line Manpower', compute='_compute_efficiency', store=True)

    daily_target_pcs = fields.Integer(string='Daily Target (Pcs)', default=1200)
    actual_output_pcs = fields.Integer(string='Actual Output (Pcs)', default=1140)
    line_efficiency_pct = fields.Float(string='Line Efficiency (%)', compute='_compute_efficiency', store=True, tracking=True)

    @api.depends('operators_present', 'helpers_present', 'daily_target_pcs', 'actual_output_pcs')
    def _compute_efficiency(self):
        for rec in self:
            rec.total_manpower = max((rec.operators_present or 0) + (rec.helpers_present or 0), 0)
            if rec.daily_target_pcs and rec.daily_target_pcs > 0:
                rec.line_efficiency_pct = round((rec.actual_output_pcs / rec.daily_target_pcs) * 100.0, 2)
            else:
                rec.line_efficiency_pct = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.factory.line.roster') or _('New')
        return super().create(vals_list)


class DslFactoryComplianceAudit(models.Model):
    _name = 'dsl.factory.compliance.audit'
    _description = 'BD Labour Act, RSC (Accord), BSCI & SEDEX Compliance Audit Checklist'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'audit_date desc, id desc'

    name = fields.Char(string='Audit Ref.', required=True, copy=False, readonly=True, default=lambda self: _('New'), index=True)
    audit_title = fields.Char(string='Compliance Audit Title', required=True, tracking=True)
    audit_standard = fields.Selection(
        selection=[
            ('bd_labour_dife', 'BD Labour Act 2006 / DIFE Inspection'),
            ('rsc_accord', 'RMG Sustainability Council (RSC / Accord) Fire & Safety'),
            ('amfori_bsci', 'amfori BSCI Social Compliance'),
            ('sedex_smeta', 'SEDEX / SMETA 4-Pillar Audit'),
            ('wrap_iso', 'WRAP / ISO 45001 OHS'),
        ],
        string='Audit Framework',
        default='bd_labour_dife',
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company, index=True)
    branch_id = fields.Many2one('dsl.branch', string='Factory / Plant', domain="[('company_id', '=', company_id)]")
    auditor_name = fields.Char(string='Lead Auditor / Agency', default='Internal Welfare & Compliance Team')
    audit_date = fields.Date(string='Audit Date', default=fields.Date.context_today, required=True)

    line_ids = fields.One2many('dsl.factory.audit.line', 'audit_id', string='Compliance Checkpoints')
    compliance_score_pct = fields.Float(string='Compliance Score (%)', compute='_compute_compliance_score', store=True, tracking=True)

    state = fields.Selection(
        selection=[
            ('draft', 'Scheduled'),
            ('in_progress', 'Inspection Active'),
            ('capa_open', 'CAPA Remediation'),
            ('certified_closed', 'Compliant & Closed'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    @api.depends('line_ids.status')
    def _compute_compliance_score(self):
        for rec in self:
            applicable = rec.line_ids.filtered(lambda l: l.status != 'na')
            if applicable:
                passed = len(applicable.filtered(lambda l: l.status == 'compliant'))
                rec.compliance_score_pct = round((passed / len(applicable)) * 100.0, 2)
            else:
                rec.compliance_score_pct = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.factory.compliance.audit') or _('New')
        recs = super().create(vals_list)
        for rec in recs:
            if not rec.line_ids:
                rec.action_load_bd_compliance_checklist()
        return recs

    def action_load_bd_compliance_checklist(self):
        for rec in self:
            if rec.line_ids:
                continue
            items = [
                ('Fire & Exit Safety', 'Unobstructed fire exits, illuminated exit signage & valid fire extinguishers (Sec 62)'),
                ('Working Hours & 2x OT', 'Daily OT <= 2 hours, weekly <= 60 hours & 2x Basic OT register verified (Sec 100-108)'),
                ('Minimum Wage & Timely Pay', 'Minimum Wage Board grade compliance & wage paid within 7 working days (Sec 123)'),
                ('Childcare, Medical & Canteen', 'In-plant medical room, daycare room (>40 female workers) & pure drinking water (Sec 89-94)'),
                ('Zero Child / Forced Labour', '100% age verification (NID/Birth Cert >= 18 yrs) & Participation Committee active'),
            ]
            self.env['dsl.factory.audit.line'].create([{
                'audit_id': rec.id,
                'section': sec,
                'checkpoint': chk,
                'status': 'compliant',
            } for sec, chk in items])

    def action_start_audit(self):
        self.action_load_bd_compliance_checklist()
        self.write({'state': 'in_progress'})

    def action_close_compliant(self):
        self.write({'state': 'certified_closed'})


class DslFactoryAuditLine(models.Model):
    _name = 'dsl.factory.audit.line'
    _description = 'Factory Compliance Audit Checkpoint Line'
    _order = 'id asc'

    audit_id = fields.Many2one('dsl.factory.compliance.audit', required=True, ondelete='cascade', index=True)
    section = fields.Char(string='Compliance Pillar', required=True)
    checkpoint = fields.Char(string='Statutory / Buyer Checkpoint', required=True)
    status = fields.Selection(
        selection=[
            ('compliant', 'Compliant (Pass)'),
            ('minor_nc', 'Minor Non-Compliance (CAPA)'),
            ('critical_nc', 'Critical Finding'),
            ('na', 'Not Applicable'),
        ],
        string='Finding',
        default='compliant',
        required=True,
    )
    capa_note = fields.Char(string='Corrective Action Plan (CAPA)')

