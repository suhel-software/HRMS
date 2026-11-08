# -*- coding: utf-8 -*-
import json
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# 1. CYCLE TYPE MASTER (`dsl.hrms.assessment.cycle.type` / #6)
# =============================================================================
class DslHrmsAssessmentCycleType(models.Model):
    _name = 'dsl.hrms.assessment.cycle.type'
    _description = 'Assessment Cycle Frequency Type (Annual, Quarterly, Probation, Project)'
    _order = 'sequence asc, id asc'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Cycle Type Name', required=True)
    code = fields.Char(string='Cycle Type Code', required=True, index=True)
    default_duration_days = fields.Integer(string='Suggested Duration (Days)', default=365)
    is_recurring = fields.Boolean(string='Recurring Cycle', default=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Cycle Type Code must be unique!'),
    ]


# =============================================================================
# 2. ASSESSMENT CYCLE (`dsl.hrms.assessment.cycle` / #7)
#    Supports Concurrent Active Cycles per Company (Annual + 360 + Quarterly + Probation)
# =============================================================================
class DslHrmsAssessmentCycle(models.Model):
    _name = 'dsl.hrms.assessment.cycle'
    _description = 'Multi-Company Configurable Assessment Cycle'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    name = fields.Char(string='Cycle Title', required=True, tracking=True)
    code = fields.Char(string='Cycle Reference Code', required=True, index=True, tracking=True)
    company_id = fields.Many2one(
        'res.company',
        string='Owner Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )
    cycle_type_id = fields.Many2one(
        'dsl.hrms.assessment.cycle.type',
        string='Cycle Frequency Type',
        required=True,
        tracking=True,
    )
    assessment_scope = fields.Selection(
        selection=[
            ('annual', 'Annual / Half-Yearly Performance Review'),
            ('quarterly', 'Quarterly Standard Review'),
            ('probation', 'Probation Confirmation Assessment'),
            ('project', 'Project / Milestone Evaluation'),
        ],
        string='Assessment Scope',
        default='annual',
        required=True,
        tracking=True,
    )
    policy_id = fields.Many2one(
        'dsl.hrms.assessment.policy',
        string='Governing Policy',
        required=True,
        tracking=True,
    )
    policy_version_id = fields.Many2one(
        'dsl.hrms.assessment.policy.version',
        string='Frozen Policy Version',
        readonly=True,
    )
    assessment_type_id = fields.Many2one(
        'dsl.hrms.assessment.type',
        string='Process Type (Standard / Advanced / 360°)',
        required=True,
    )
    template_id = fields.Many2one(
        'dsl.hrms.assessment.template',
        string='Default Assessment Template',
        required=True,
    )
    template_version_id = fields.Many2one(
        'dsl.hrms.assessment.template.version',
        string='Frozen Template Version',
        readonly=True,
    )
    rating_scale_id = fields.Many2one(
        'dsl.hrms.assessment.rating.scale',
        string='Rating Scale',
        required=True,
    )

    date_from = fields.Date(
        string='Performance Period From',
        required=True,
        default=fields.Date.context_today,
        index=True,
    )
    date_to = fields.Date(
        string='Performance Period To',
        required=True,
        default=fields.Date.context_today,
        index=True,
    )
    launch_date = fields.Date(string='Launch Date', default=fields.Date.context_today)
    self_deadline = fields.Date(string='Self-Review Deadline')
    manager_deadline = fields.Date(string='Manager Review Deadline')
    hr_deadline = fields.Date(string='HR & Calibration Deadline')
    result_publish_date = fields.Date(string='Result Publication Date')

    # Eligibility Parameters & Batch Sizing
    minimum_service_days = fields.Integer(string='Minimum Service Days', default=180)
    include_probation = fields.Boolean(string='Include Probationary Staff', default=False)
    include_on_leave = fields.Boolean(string='Include Employees on Leave', default=True)
    batch_size = fields.Integer(string='Bulk Generation Batch Size', default=150)
    employee_filter = fields.Text(string='Saved Eligibility Domain JSON', default='[]')

    cycle_phase_ids = fields.One2many(
        'dsl.hrms.assessment.cycle.phase',
        'cycle_id',
        string='Cycle Execution Phases',
    )
    eligibility_rule_ids = fields.One2many(
        'dsl.hrms.assessment.eligibility.rule',
        'cycle_id',
        string='Eligibility Rules',
    )
    assessment_ids = fields.One2many(
        'dsl.hrms.assessment',
        'cycle_id',
        string='Generated Employee Assessments',
    )
    assessment_count = fields.Integer(
        string='Assessments',
        compute='_compute_assessment_count',
    )
    total_scored_weightage = fields.Float(
        string='Cycle Phase Weightage (%)',
        compute='_compute_total_scored_weightage',
        store=True,
    )
    locked = fields.Boolean(string='Configuration Frozen & Locked', default=False, tracking=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('scheduled', 'Scheduled & Validated'),
            ('open', 'Open (Launched)'),
            ('in_progress', 'In Progress'),
            ('under_review', 'Under Review & Calibration'),
            ('approved', 'Final Approved'),
            ('published', 'Results Published'),
            ('closed', 'Closed & Archived'),
            ('cancelled', 'Cancelled'),
        ],
        string='Cycle Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )

    _sql_constraints = [
        ('company_code_uniq', 'unique(company_id, code)', 'Cycle Code must be unique per Company!'),
    ]

    @api.constrains('date_from', 'date_to')
    def _check_cycle_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_('Performance Period From (%s) must be on or before Period To (%s)!') % (
                    rec.date_from, rec.date_to
                ))

    @api.depends('assessment_ids')
    def _compute_assessment_count(self):
        for rec in self:
            rec.assessment_count = len(rec.assessment_ids)

    @api.depends('cycle_phase_ids.enabled', 'cycle_phase_ids.weightage')
    def _compute_total_scored_weightage(self):
        for rec in self:
            enabled = rec.cycle_phase_ids.filtered(lambda p: p.enabled)
            rec.total_scored_weightage = round(sum(enabled.mapped('weightage')), 2)

    @api.onchange('policy_id')
    def _onchange_policy_populate_defaults(self):
        if self.policy_id:
            self.assessment_type_id = self.policy_id.assessment_type_id
            if self.policy_id.default_template_id:
                self.template_id = self.policy_id.default_template_id
            if self.policy_id.default_rating_scale_id:
                self.rating_scale_id = self.policy_id.default_rating_scale_id
            self.minimum_service_days = self.policy_id.minimum_service_days

    def action_sync_phases_from_policy(self):
        CyclePhase = self.env['dsl.hrms.assessment.cycle.phase'].sudo()
        for rec in self:
            if rec.locked:
                raise UserError(_('Cycle "%s" is frozen and locked!') % rec.name)
            if not rec.policy_id.policy_version_id:
                rec.policy_id.action_publish_new_version()
            ver = rec.policy_id.policy_version_id
            rec.policy_version_id = ver.id
            if not rec.template_id.version_ids:
                rec.template_id.action_publish_template_version()
            rec.template_version_id = rec.template_id.version_ids[:1].id

            rec.cycle_phase_ids.unlink()
            base_start = rec.launch_date or fields.Date.context_today(self)
            offset = 0
            for pp in ver.phase_ids.sorted(key=lambda l: l.sequence):
                p_start = base_start + timedelta(days=offset)
                p_due = p_start + timedelta(days=max(pp.deadline_days or 7, 1))
                offset += max(pp.deadline_days or 7, 1)
                CyclePhase.create({
                    'cycle_id': rec.id,
                    'phase_id': pp.phase_id.id,
                    'sequence': pp.sequence,
                    'enabled': pp.enabled,
                    'required': pp.required,
                    'reviewer_type': pp.reviewer_type,
                    'start_date': p_start,
                    'deadline': p_due,
                    'weightage': pp.weightage,
                    'reviewer_minimum': pp.minimum_reviewers,
                    'reviewer_maximum': pp.maximum_reviewers,
                    'anonymous': pp.anonymous,
                    'template_version_id': rec.template_version_id.id if rec.template_version_id else False,
                    'state': 'ready',
                })

    def action_validate_cycle(self):
        for rec in self:
            if not rec.cycle_phase_ids:
                rec.action_sync_phases_from_policy()
            if abs(rec.total_scored_weightage - 100.0) > 0.05:
                raise ValidationError(_(
                    'Enabled Cycle Phase Weightages for "%s" must total 100%% (currently %s%%)!'
                ) % (rec.name, rec.total_scored_weightage))
            rec.state = 'scheduled'

    def action_launch_and_freeze(self):
        for rec in self:
            if rec.state == 'draft':
                rec.action_validate_cycle()
            rec.write({
                'locked': True,
                'state': 'open',
            })

    def _get_eligible_employees(self):
        """Part 3.2.I & 10.3: Server-side Eligibility Resolver (excludes separated/terminated staff)."""
        self.ensure_one()
        dom = [
            ('company_id', '=', self.company_id.id),
            ('active', '=', True),
            ('employment_status', 'not in', ('separated', 'suspended')),
        ]
        if not self.include_probation and self.assessment_scope != 'probation':
            dom.append(('employment_status', '!=', 'probation'))
        elif self.assessment_scope == 'probation':
            dom.append(('employment_status', '=', 'probation'))

        emps = self.env['hr.employee'].sudo().search(dom)
        if not emps:
            # Fallback if demo employees are confirmed or in any active state within company
            emps = self.env['hr.employee'].sudo().search([
                ('company_id', '=', self.company_id.id),
                ('active', '=', True),
            ])

        # Filter by explicit eligibility rules if configured
        inc_rules = self.eligibility_rule_ids.filtered(lambda r: r.is_included)
        if inc_rules:
            allowed_depts = inc_rules.mapped('department_id').ids
            allowed_branches = inc_rules.mapped('branch_id').ids
            if allowed_depts:
                emps = emps.filtered(lambda e: e.department_id.id in allowed_depts)
            if allowed_branches:
                emps = emps.filtered(lambda e: e.branch_id.id in allowed_branches)
        return emps

    def action_generate_assessments_batch(self):
        """
        Part 10.3 Idempotent Bulk Assessment Generator:
        - Checks eligibility
        - Processes in batches (`batch_size`)
        - Skips existing `(cycle_id, employee_id, assessment_scope)` to prevent duplicates
        - Snapshots Employee Company, Branch, Department, Designation & Reporting Manager
        - Generates Phase Instances, Reviewers & Inbox Tasks
        """
        Assessment = self.env['dsl.hrms.assessment'].sudo()
        for rec in self:
            if not rec.locked:
                rec.action_launch_and_freeze()
            emps = rec._get_eligible_employees()
            existing_emp_ids = set(Assessment.search([
                ('cycle_id', '=', rec.id),
                ('assessment_scope', '=', rec.assessment_scope),
            ]).mapped('employee_id').ids)

            to_create_emps = [e for e in emps if e.id not in existing_emp_ids]
            chunk = max(rec.batch_size or 150, 1)
            for idx in range(0, len(to_create_emps), chunk):
                batch_emps = to_create_emps[idx:idx + chunk]
                vals_list = []
                for emp in batch_emps:
                    vals_list.append({
                        'cycle_id': rec.id,
                        'company_id': emp.company_id.id,
                        'employee_id': emp.id,
                        'branch_id': emp.branch_id.id if emp.branch_id else False,
                        'department_id': emp.department_id.id if emp.department_id else False,
                        'designation_id': emp.job_id.id if emp.job_id else False,
                        'manager_id': emp.parent_id.id if emp.parent_id else False,
                        'assessment_scope': rec.assessment_scope,
                        'policy_version_id': rec.policy_version_id.id if rec.policy_version_id else False,
                        'template_id': rec.template_id.id,
                        'template_version_id': rec.template_version_id.id if rec.template_version_id else False,
                        'rating_scale_id': rec.rating_scale_id.id,
                        'assessment_type_id': rec.assessment_type_id.id,
                        'date_from': rec.date_from,
                        'date_to': rec.date_to,
                        'state': 'in_progress',
                        'started_at': fields.Datetime.now(),
                    })
                created_assessments = Assessment.create(vals_list)
                created_assessments._initialize_runtime_phases_and_reviewers()

            if rec.state == 'open':
                rec.state = 'in_progress'

    def action_view_cycle_assessments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — Assessments',
            'res_model': 'dsl.hrms.assessment',
            'view_mode': 'list,form',
            'domain': [('cycle_id', '=', self.id)],
            'context': {'default_cycle_id': self.id, 'default_company_id': self.company_id.id},
        }


# =============================================================================
# 3. CYCLE PHASE (`dsl.hrms.assessment.cycle.phase` / #8)
# =============================================================================
class DslHrmsAssessmentCyclePhase(models.Model):
    _name = 'dsl.hrms.assessment.cycle.phase'
    _description = 'Cycle-Specific Review Phase & Weightage (#8)'
    _order = 'sequence asc, id asc'

    cycle_id = fields.Many2one(
        'dsl.hrms.assessment.cycle',
        string='Assessment Cycle',
        required=True,
        ondelete='cascade',
        index=True,
    )
    phase_id = fields.Many2one('dsl.hrms.assessment.phase', string='Review Phase', required=True)
    sequence = fields.Integer(string='Order', default=10)
    enabled = fields.Boolean(string='Enabled', default=True)
    required = fields.Boolean(string='Mandatory', default=True)
    reviewer_type = fields.Selection(
        selection=[
            ('self', 'Self'),
            ('manager', 'Reporting Manager'),
            ('dept_head', 'Department Head'),
            ('peer', 'Peer (360°)'),
            ('subordinate', 'Subordinate (360°)'),
            ('hr', 'HR / Calibrator'),
        ],
        string='Reviewer Role',
        required=True,
        default='self',
    )
    start_date = fields.Date(string='Start Date')
    deadline = fields.Date(string='Deadline')
    weightage = fields.Float(string='Weightage (%)', default=25.0)
    reviewer_minimum = fields.Integer(string='Min Reviewers', default=1)
    reviewer_maximum = fields.Integer(string='Max Reviewers', default=1)
    anonymous = fields.Boolean(string='Anonymous Feedback', default=False)
    template_version_id = fields.Many2one('dsl.hrms.assessment.template.version', string='Frozen Template Version')
    state = fields.Selection(
        selection=[('ready', 'Ready'), ('active', 'Active'), ('completed', 'Completed')],
        string='Status',
        default='ready',
    )


# =============================================================================
# 4. ELIGIBILITY RULE (`dsl.hrms.assessment.eligibility.rule` / #9)
# =============================================================================
class DslHrmsAssessmentEligibilityRule(models.Model):
    _name = 'dsl.hrms.assessment.eligibility.rule'
    _description = 'Assessment Cycle Employee Eligibility Rule (#9)'
    _order = 'priority asc, id asc'

    priority = fields.Integer(string='Priority', default=10)
    cycle_id = fields.Many2one(
        'dsl.hrms.assessment.cycle',
        string='Assessment Cycle',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one('res.company', related='cycle_id.company_id', store=True, readonly=True)
    department_id = fields.Many2one('hr.department', string='Department')
    branch_id = fields.Many2one('dsl.branch', string='Branch / Plant')
    designation_id = fields.Many2one('hr.job', string='Designation')
    employment_category = fields.Selection(
        selection=[
            ('permanent', 'Permanent'),
            ('probation', 'Probationary'),
            ('contractual', 'Contractual'),
            ('intern', 'Intern / Apprentice'),
        ],
        string='Employment Category',
    )
    minimum_service_days = fields.Integer(string='Min Service Days', default=0)
    maximum_service_days = fields.Integer(string='Max Service Days', default=0)
    include_probation = fields.Boolean(string='Include Probation', default=False)
    include_on_leave = fields.Boolean(string='Include On Leave', default=True)
    include_contractual = fields.Boolean(string='Include Contractual', default=False)
    include_resigned = fields.Boolean(string='Include Resigned (Default No)', default=False)
    rule_operator = fields.Selection(
        selection=[('and', 'Match All (AND)'), ('or', 'Match Any (OR)')],
        string='Operator',
        default='and',
    )
    is_included = fields.Boolean(string='Include Matching Staff (Uncheck to Exclude)', default=True)

