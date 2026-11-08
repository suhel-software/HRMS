# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


def _default_appraisal_cycle(record=None):
    env = record.env if record is not None else None
    if not env:
        return False
    cyc = env['dsl.appraisal.cycle'].sudo().search([('active', '=', True)], order='id desc', limit=1)
    return cyc.id if cyc else False


class DslAppraisalCycle(models.Model):
    _name = 'dsl.appraisal.cycle'
    _description = 'Annual / Half-Yearly Performance Appraisal Cycle'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'

    active = fields.Boolean(default=True)
    name = fields.Char(string='Appraisal Cycle Title', required=True, tracking=True)
    code = fields.Char(string='Cycle Code', required=True, default='FY-2026-27')
    company_id = fields.Many2one('res.company', string='Company (Blank = Group)')
    date_start = fields.Date(string='Review Period From', required=True, default=fields.Date.context_today)
    date_end = fields.Date(string='Review Period To', required=True, default=fields.Date.context_today)


class DslEmployeeAppraisal(models.Model):
    _name = 'dsl.employee.appraisal'
    _description = 'Employee KPI & Annual Performance Appraisal'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'final_weighted_score desc, id desc'

    name = fields.Char(
        string='Appraisal Ref.',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
    )
    cycle_id = fields.Many2one(
        'dsl.appraisal.cycle',
        string='Appraisal Cycle',
        required=True,
        default=_default_appraisal_cycle,
        tracking=True,
    )
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True, tracking=True)
    reviewer_id = fields.Many2one('hr.employee', string='Line Manager / Appraiser', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company, index=True)
    branch_id = fields.Many2one('dsl.branch', string='Branch / Plant', domain="[('company_id', '=', company_id)]")
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', store=True, readonly=True)
    job_id = fields.Many2one('hr.job', related='employee_id.job_id', store=True, readonly=True)

    kpi_line_ids = fields.One2many('dsl.appraisal.kpi.line', 'appraisal_id', string='KPI & Competency Matrix')
    total_weight = fields.Float(string='Total KPI Weight (%)', compute='_compute_scores', store=True)
    self_weighted_score = fields.Float(string='Self Score (/100)', compute='_compute_scores', store=True)
    final_weighted_score = fields.Float(string='Final Supervisor Score (/100)', compute='_compute_scores', store=True, tracking=True)

    performance_band = fields.Selection(
        selection=[
            ('A_plus', 'A+ (90–100) — Outstanding / Top Talent'),
            ('A', 'A (80–89) — Exceeds Expectations'),
            ('B', 'B (65–79) — Meets Expectations'),
            ('C', 'C (50–64) — Needs Improvement'),
            ('D', 'D (<50) — PIP / Unsatisfactory'),
        ],
        string='Bell-Curve Grade',
        compute='_compute_scores',
        store=True,
        tracking=True,
    )
    recommended_increment_pct = fields.Float(
        string='Suggested Increment (%)',
        compute='_compute_scores',
        store=True,
        readonly=False,
    )
    employee_comments = fields.Text(string='Employee Self-Reflection & Training Needs')
    manager_feedback = fields.Text(string='Appraiser Summary & Career Development Plan')
    badge_user_id = fields.Many2one(
        'gamification.badge.user',
        string='Odoo Gamification Badge Award',
        ondelete='set null',
        help='Linked Odoo native gamification.badge.user award on hr.employee.',
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Goal Setting'),
            ('self_review', 'Employee Self-Review'),
            ('manager_review', 'Supervisor Evaluation'),
            ('hr_calibrated', 'HR Finalized & Locked'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    @api.depends('kpi_line_ids.weight_pct', 'kpi_line_ids.self_rating', 'kpi_line_ids.manager_rating')
    def _compute_scores(self):
        for rec in self:
            tot_w = round(sum(rec.kpi_line_ids.mapped('weight_pct')), 2)
            self_sum = sum((ln.weight_pct / 100.0) * ln.self_rating for ln in rec.kpi_line_ids)
            mgr_sum = sum((ln.weight_pct / 100.0) * ln.manager_rating for ln in rec.kpi_line_ids)
            score = round(mgr_sum, 2)
            rec.total_weight = tot_w
            rec.self_weighted_score = round(self_sum, 2)
            rec.final_weighted_score = score
            if score >= 90.0:
                rec.performance_band = 'A_plus'
                rec.recommended_increment_pct = 15.0
            elif score >= 80.0:
                rec.performance_band = 'A'
                rec.recommended_increment_pct = 10.0
            elif score >= 65.0:
                rec.performance_band = 'B'
                rec.recommended_increment_pct = 6.0
            elif score >= 50.0:
                rec.performance_band = 'C'
                rec.recommended_increment_pct = 0.0
            else:
                rec.performance_band = 'D'
                rec.recommended_increment_pct = 0.0

    @api.onchange('employee_id')
    def _onchange_employee_sync(self):
        if self.employee_id:
            self.company_id = self.employee_id.company_id.id
            self.branch_id = self.employee_id.branch_id.id if self.employee_id.branch_id else False
            self.reviewer_id = self.employee_id.parent_id.id if self.employee_id.parent_id else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.employee.appraisal') or _('New')
        recs = super().create(vals_list)
        for rec in recs:
            if not rec.kpi_line_ids:
                rec.action_load_default_kpis()
            rec._sync_to_odoo_gamification_badge()
        return recs

    def _sync_to_odoo_gamification_badge(self):
        """Sync top-performing appraisals with Odoo's native hr_gamification badge awards on hr.employee."""
        if 'gamification.badge' not in self.env or 'gamification.badge.user' not in self.env:
            return
        Badge = self.env['gamification.badge'].sudo()
        BadgeUser = self.env['gamification.badge.user'].sudo()
        for rec in self:
            if not rec.employee_id or rec.badge_user_id:
                continue
            if rec.performance_band in ('A_plus', 'A') or rec.final_weighted_score >= 80.0:
                badge = Badge.search([('name', 'ilike', 'Top Performer')], limit=1)
                if not badge:
                    badge = Badge.search([], limit=1)
                if not badge:
                    badge = Badge.create({
                        'name': 'Star Performer — Excellence in KPI',
                        'description': 'Awarded via DSL Enterprise 360° Performance Appraisal',
                        'rule_auth': 'everyone',
                    })
                target_user = rec.employee_id.user_id or self.env.user
                bu = BadgeUser.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('badge_id', '=', badge.id),
                ], limit=1)
                if not bu:
                    bu = BadgeUser.create({
                        'user_id': target_user.id,
                        'employee_id': rec.employee_id.id,
                        'badge_id': badge.id,
                        'comment': f"{rec.name} ({rec.cycle_id.name or 'Annual Review'}) — Score: {rec.final_weighted_score}%",
                    })
                rec.with_context(skip_badge_sync=True).write({'badge_user_id': bu.id})

    def action_load_default_kpis(self):
        for rec in self:
            if rec.kpi_line_ids:
                continue
            defaults = [
                ('Core Job Deliverables & Project Output', 'On-time milestone completion & quality', 40.0, 85.0, 86.0),
                ('Operational Efficiency & Domain Mastery', 'Zero defect rate & process ownership', 25.0, 82.0, 84.0),
                ('Team Collaboration & Leadership', 'Cross-functional support & mentoring', 20.0, 88.0, 85.0),
                ('Punctuality, Discipline & Compliance', 'Attendance & company policy adherence', 15.0, 90.0, 90.0),
            ]
            self.env['dsl.appraisal.kpi.line'].create([{
                'appraisal_id': rec.id,
                'kpi_title': t,
                'target_metric': m,
                'weight_pct': w,
                'self_rating': sr,
                'manager_rating': mr,
            } for t, m, w, sr, mr in defaults])

    def action_send_self_review(self):
        self.action_load_default_kpis()
        self.write({'state': 'self_review'})

    def action_submit_to_manager(self):
        self.write({'state': 'manager_review'})

    def action_finalize_hr(self):
        for rec in self:
            if rec.kpi_line_ids and abs(rec.total_weight - 100.0) > 0.01:
                raise ValidationError(_('Total KPI Weight must equal 100%% (currently %s%%)!') % rec.total_weight)
            rec.state = 'hr_calibrated'
            rec._sync_to_odoo_gamification_badge()


class DslAppraisalKpiLine(models.Model):
    _name = 'dsl.appraisal.kpi.line'
    _description = 'Appraisal KPI Goal & Score Line'
    _order = 'id asc'

    appraisal_id = fields.Many2one('dsl.employee.appraisal', required=True, ondelete='cascade', index=True)
    kpi_title = fields.Char(string='KPI / Objective', required=True)
    target_metric = fields.Char(string='Target / Measure')
    weight_pct = fields.Float(string='Weight (%)', default=25.0, required=True)
    self_rating = fields.Float(string='Self Score (/100)', default=80.0)
    manager_rating = fields.Float(string='Supervisor Score (/100)', default=80.0)
    weighted_points = fields.Float(string='Weighted Pts', compute='_compute_weighted_pts', store=True)

    @api.depends('weight_pct', 'manager_rating')
    def _compute_weighted_pts(self):
        for ln in self:
            ln.weighted_points = round((ln.weight_pct / 100.0) * ln.manager_rating, 2)


class HrEmployeeAppraisalExt(models.Model):
    _inherit = 'hr.employee'

    dsl_appraisal_ids = fields.One2many(
        'dsl.employee.appraisal',
        'employee_id',
        string='KPI & Performance Appraisals',
        groups='hr.group_hr_user',
    )


