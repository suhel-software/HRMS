# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


# =============================================================================
# 1. GOAL & KEY RESULTS MASTER (`dsl.hrms.goal` & `dsl.hrms.goal.key.result` / #21, #22)
# =============================================================================
class DslHrmsGoal(models.Model):
    _name = 'dsl.hrms.goal'
    _description = 'Strategic OKR / Performance Goal Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, id desc'

    name = fields.Char(string='Goal Title', required=True, tracking=True)
    code = fields.Char(string='Goal Code', required=True, index=True, default='GOAL-NEW')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    parent_goal_id = fields.Many2one('dsl.hrms.goal', string='Parent Strategic Goal')
    goal_level = fields.Selection(
        selection=[
            ('company', 'Company-Wide OKR'),
            ('department', 'Department Goal'),
            ('team', 'Team Objective'),
            ('employee', 'Individual Employee Goal'),
        ],
        string='Goal Level',
        default='department',
        required=True,
        tracking=True,
    )
    owner_employee_id = fields.Many2one('hr.employee', string='Goal Champion / Owner')
    department_id = fields.Many2one('hr.department', string='Department')
    branch_id = fields.Many2one('dsl.branch', string='Branch / Plant')
    description = fields.Text(string='Objective Scope & Success Criteria')
    measurement_type = fields.Selection(
        selection=[
            ('percentage', 'Percentage (%)'),
            ('number', 'Numeric Count'),
            ('amount', 'Financial Amount (৳)'),
            ('milestone', 'Milestone Completion'),
        ],
        string='Measurement Type',
        default='percentage',
        required=True,
    )
    target_value = fields.Float(string='Target Value', default=100.0)
    unit = fields.Char(string='Unit', default='%')
    start_date = fields.Date(string='Start Date', default=fields.Date.context_today)
    end_date = fields.Date(string='Target End Date')
    weightage = fields.Float(string='Default Weightage (%)', default=25.0)
    priority = fields.Selection(
        selection=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
        string='Priority',
        default='high',
    )
    key_result_ids = fields.One2many(
        'dsl.hrms.goal.key.result',
        'goal_id',
        string='Key Results (KRs)',
    )
    active = fields.Boolean(default=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='active',
        required=True,
        tracking=True,
    )


class DslHrmsGoalKeyResult(models.Model):
    _name = 'dsl.hrms.goal.key.result'
    _description = 'Goal Measurable Key Result (KR)'
    _order = 'id asc'

    goal_id = fields.Many2one(
        'dsl.hrms.goal',
        string='Parent Goal',
        required=True,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(string='Key Result Description', required=True)
    description = fields.Text(string='Details')
    measurement_type = fields.Selection(
        selection=[
            ('percentage', 'Percentage (%)'),
            ('number', 'Numeric Count'),
            ('amount', 'Amount (৳)'),
        ],
        string='Metric Type',
        default='percentage',
    )
    baseline_value = fields.Float(string='Baseline', default=0.0)
    target_value = fields.Float(string='Target', required=True, default=100.0)
    actual_value = fields.Float(string='Actual Achieved', default=0.0)
    unit = fields.Char(string='Unit', default='%')
    weightage = fields.Float(string='KR Weight (%)', default=50.0)
    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='Due Date')
    progress_percentage = fields.Float(
        string='Progress (%)',
        compute='_compute_progress_percentage',
        store=True,
    )
    state = fields.Selection(
        selection=[('on_track', 'On Track'), ('at_risk', 'At Risk'), ('achieved', 'Achieved')],
        string='Status',
        default='on_track',
    )

    @api.depends('baseline_value', 'target_value', 'actual_value')
    def _compute_progress_percentage(self):
        for rec in self:
            span = rec.target_value - rec.baseline_value
            if abs(span) > 0.0001:
                pct = ((rec.actual_value - rec.baseline_value) / span) * 100.0
                rec.progress_percentage = round(max(0.0, min(pct, 100.0)), 2)
            else:
                rec.progress_percentage = 0.0


# =============================================================================
# 2. KRA, KPI & COMPETENCY MASTERS (#23, #24, #25, #26)
# =============================================================================
class DslHrmsKra(models.Model):
    _name = 'dsl.hrms.kra'
    _description = 'Key Result Area (KRA) Master'
    _order = 'code asc, id asc'

    name = fields.Char(string='KRA Title', required=True)
    code = fields.Char(string='KRA Code', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    department_id = fields.Many2one('hr.department', string='Department')
    designation_id = fields.Many2one('hr.job', string='Designation')
    description = fields.Text(string='KRA Scope')
    measurement_method = fields.Char(string='Measurement Approach')
    default_weightage = fields.Float(string='Default Weightage (%)', default=25.0)
    kpi_ids = fields.One2many('dsl.hrms.kpi', 'kra_id', string='Linked KPIs')
    active = fields.Boolean(default=True)


class DslHrmsKpi(models.Model):
    _name = 'dsl.hrms.kpi'
    _description = 'Key Performance Indicator (KPI) Master (#24)'
    _order = 'code asc, id asc'

    name = fields.Char(string='KPI Name', required=True)
    code = fields.Char(string='KPI Code', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    department_id = fields.Many2one('hr.department', string='Department')
    designation_id = fields.Many2one('hr.job', string='Designation')
    kra_id = fields.Many2one('dsl.hrms.kra', string='Parent KRA')
    description = fields.Text(string='KPI Definition & Formula Notes')
    measurement_type = fields.Selection(
        selection=[
            ('percentage', 'Percentage (%)'),
            ('number', 'Numeric Count'),
            ('amount', 'Financial Amount (৳)'),
            ('rating', 'Supervisor Rating (1-5)'),
            ('boolean', 'Boolean (Pass / Fail)'),
        ],
        string='Measurement Type',
        default='percentage',
        required=True,
    )
    calculation_method = fields.Selection(
        selection=[
            ('higher_is_better', 'Higher is Better (e.g. Sales, Output, On-Time %)'),
            ('lower_is_better', 'Lower is Better (e.g. Defect Rate, Bug Count, Downtime)'),
            ('exact_target', 'Exact Target Match'),
            ('range_target', 'Within Target Band'),
            ('boolean', '100% if Achieved else 0%'),
            ('manual_rating', 'Manual Evaluator Score'),
        ],
        string='Scoring Direction (Part 7.5)',
        default='higher_is_better',
        required=True,
    )
    unit = fields.Char(string='Unit', default='%')
    default_target = fields.Float(string='Default Target', default=100.0)
    default_weightage = fields.Float(string='Default Weightage (%)', default=25.0)
    higher_is_better = fields.Boolean(
        string='Higher is Better',
        compute='_compute_higher_flag',
        store=True,
    )
    active = fields.Boolean(default=True)

    @api.depends('calculation_method')
    def _compute_higher_flag(self):
        for rec in self:
            rec.higher_is_better = rec.calculation_method != 'lower_is_better'

    def compute_kpi_achievement_pct(self, target_val, actual_val):
        """
        Part 7.5 KPI Calculation Engine:
        - Higher is Better: (actual / target) * 100 capped at 0..100
        - Lower is Better (e.g. Bug/Defect ceiling):
          If actual <= target: 100%. If actual > target: max(0, (1 - (actual - target)/max(target, 1)) * 100)
        - Boolean: 100% if actual >= 1 else 0%
        """
        self.ensure_one()
        t = float(target_val or 0.0)
        a = float(actual_val or 0.0)
        if self.calculation_method == 'boolean':
            return 100.0 if a >= 1.0 else 0.0
        if self.calculation_method == 'lower_is_better':
            if a <= t:
                return 100.0
            denom = max(t, 1.0)
            penalty = ((a - t) / denom) * 100.0
            return round(max(0.0, 100.0 - penalty), 2)
        if self.calculation_method == 'exact_target':
            if abs(a - t) < 0.001:
                return 100.0
            denom = max(abs(t), 1.0)
            return round(max(0.0, (1.0 - abs(a - t) / denom) * 100.0), 2)
        if t <= 0:
            return 0.0
        return round(max(0.0, min((a / t) * 100.0, 100.0)), 2)


class DslHrmsCompetency(models.Model):
    _name = 'dsl.hrms.competency'
    _description = 'Competency Master (Core, Functional, Leadership, Technical) (#25)'
    _order = 'competency_type asc, code asc'

    name = fields.Char(string='Competency Title', required=True)
    code = fields.Char(string='Competency Code', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    category_id = fields.Many2one('dsl.hrms.assessment.category', string='Assessment Category')
    competency_type = fields.Selection(
        selection=[
            ('core', 'Core Organizational Value'),
            ('functional', 'Functional / Domain Competency'),
            ('leadership', 'Leadership & Managerial Competency'),
            ('technical', 'Technical / Engineering Skill'),
        ],
        string='Competency Pillar',
        default='core',
        required=True,
    )
    description = fields.Text(string='Behavioral Definition')
    level_ids = fields.One2many(
        'dsl.hrms.competency.level',
        'competency_id',
        string='Proficiency Levels',
    )
    active = fields.Boolean(default=True)


class DslHrmsCompetencyLevel(models.Model):
    _name = 'dsl.hrms.competency.level'
    _description = 'Competency Proficiency Level (#26)'
    _order = 'sequence asc, level asc'

    sequence = fields.Integer(default=10)
    competency_id = fields.Many2one(
        'dsl.hrms.competency',
        string='Competency',
        required=True,
        ondelete='cascade',
        index=True,
    )
    level = fields.Integer(string='Proficiency Tier (1-5)', required=True, default=3)
    name = fields.Char(string='Level Name (e.g. L3 - Proficient)', required=True)
    description = fields.Text(string='Description')
    expected_behaviour = fields.Text(string='Observable Behavioural Indicators')


# =============================================================================
# 3. EMPLOYEE GOAL, KPI, KRA, COMPETENCY, CHECK-IN & EVIDENCE (#27 to #32)
# =============================================================================
class DslHrmsEmployeeGoal(models.Model):
    _name = 'dsl.hrms.employee.goal'
    _description = 'Employee Assigned Goal (#27)'
    _order = 'start_date desc, id desc'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True)
    company_id = fields.Many2one('res.company', related='employee_id.company_id', store=True, readonly=True)
    goal_id = fields.Many2one('dsl.hrms.goal', string='Strategic Goal', required=True)
    cycle_id = fields.Many2one('dsl.hrms.assessment.cycle', string='Assessment Cycle', index=True)
    assigned_by = fields.Many2one('res.users', string='Assigned By', default=lambda self: self.env.user)
    target_value = fields.Float(string='Target', default=100.0)
    actual_value = fields.Float(string='Actual Achieved', default=0.0)
    progress = fields.Float(string='Progress (%)', compute='_compute_progress', store=True)
    weightage = fields.Float(string='Weightage (%)', default=25.0)
    start_date = fields.Date(string='Start Date', default=fields.Date.context_today)
    end_date = fields.Date(string='End Date')
    state = fields.Selection(
        selection=[('assigned', 'Assigned'), ('in_progress', 'In Progress'), ('completed', 'Completed')],
        string='Status',
        default='in_progress',
    )

    _sql_constraints = [
        ('cycle_emp_goal_uniq', 'unique(cycle_id, employee_id, goal_id)', 'Duplicate Goal assignment for the same Employee & Cycle is not allowed!'),
    ]

    @api.depends('target_value', 'actual_value')
    def _compute_progress(self):
        for rec in self:
            rec.progress = round(min(max((rec.actual_value / rec.target_value) * 100.0, 0.0), 100.0), 2) if rec.target_value > 0 else 0.0


class DslHrmsEmployeeKpi(models.Model):
    _name = 'dsl.hrms.employee.kpi'
    _description = 'Employee Assigned KPI & Achievement Calculation (#28)'
    _order = 'id asc'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True)
    company_id = fields.Many2one('res.company', related='employee_id.company_id', store=True, readonly=True)
    cycle_id = fields.Many2one('dsl.hrms.assessment.cycle', string='Assessment Cycle', required=True, index=True)
    kpi_id = fields.Many2one('dsl.hrms.kpi', string='KPI', required=True)
    kra_id = fields.Many2one('dsl.hrms.kra', related='kpi_id.kra_id', store=True, readonly=True)
    target_value = fields.Float(string='Target Value', required=True, default=100.0)
    actual_value = fields.Float(string='Actual Value', default=0.0)
    unit = fields.Char(related='kpi_id.unit', readonly=True)
    weightage = fields.Float(string='Weightage (%)', required=True, default=25.0)
    achievement_percentage = fields.Float(
        string='Achievement (%)',
        compute='_compute_kpi_scores',
        store=True,
    )
    calculated_score = fields.Float(
        string='Weighted KPI Score',
        compute='_compute_kpi_scores',
        store=True,
    )
    overlap_warning = fields.Char(
        string='Concurrent Cycle Overlap Check',
        compute='_compute_overlap_warning',
    )
    verified_by = fields.Many2one('res.users', string='Verified By')
    verified_at = fields.Datetime(string='Verified At')
    state = fields.Selection(
        selection=[('draft', 'Assigned'), ('submitted', 'Actuals Submitted'), ('verified', 'Verified')],
        string='Status',
        default='draft',
    )

    _sql_constraints = [
        ('cycle_emp_kpi_uniq', 'unique(cycle_id, employee_id, kpi_id)', 'Duplicate KPI for the same Employee in the same Cycle is blocked!'),
    ]

    @api.depends('kpi_id', 'target_value', 'actual_value', 'weightage')
    def _compute_kpi_scores(self):
        for rec in self:
            if rec.kpi_id:
                ach = rec.kpi_id.compute_kpi_achievement_pct(rec.target_value, rec.actual_value)
            else:
                ach = 0.0
            rec.achievement_percentage = ach
            rec.calculated_score = round((ach * (rec.weightage or 0.0)) / 100.0, 2)

    @api.depends('employee_id', 'kpi_id', 'cycle_id.date_from', 'cycle_id.date_to')
    def _compute_overlap_warning(self):
        for rec in self:
            rec.overlap_warning = False
            if not (rec.employee_id and rec.kpi_id and rec.cycle_id and rec.cycle_id.date_from and rec.cycle_id.date_to):
                continue
            dom = [
                ('id', '!=', rec.id),
                ('employee_id', '=', rec.employee_id.id),
                ('kpi_id', '=', rec.kpi_id.id),
                ('cycle_id.date_from', '<=', rec.cycle_id.date_to),
                ('cycle_id.date_to', '>=', rec.cycle_id.date_from),
            ]
            other = self.sudo().search(dom, limit=1)
            if other:
                rec.overlap_warning = _('Warning: KPI "%s" overlaps with concurrent cycle "%s"!') % (
                    rec.kpi_id.name, other.cycle_id.name
                )


class DslHrmsEmployeeKra(models.Model):
    _name = 'dsl.hrms.employee.kra'
    _description = 'Employee Assigned Key Result Area (#29)'
    _order = 'id asc'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True)
    company_id = fields.Many2one('res.company', related='employee_id.company_id', store=True, readonly=True)
    cycle_id = fields.Many2one('dsl.hrms.assessment.cycle', string='Assessment Cycle', required=True, index=True)
    kra_id = fields.Many2one('dsl.hrms.kra', string='KRA', required=True)
    description = fields.Text(string='KRA Deliverables')
    target_description = fields.Char(string='Expected Outcome')
    weightage = fields.Float(string='Weightage (%)', default=25.0)
    actual_result = fields.Char(string='Actual Result Summary')
    score = fields.Float(string='Score (/100)', default=85.0)
    state = fields.Selection(
        selection=[('assigned', 'Assigned'), ('evaluated', 'Evaluated')],
        string='Status',
        default='assigned',
    )


class DslHrmsEmployeeCompetency(models.Model):
    _name = 'dsl.hrms.employee.competency'
    _description = 'Employee Competency Assessment (#30)'
    _order = 'id asc'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True)
    company_id = fields.Many2one('res.company', related='employee_id.company_id', store=True, readonly=True)
    cycle_id = fields.Many2one('dsl.hrms.assessment.cycle', string='Assessment Cycle', required=True, index=True)
    competency_id = fields.Many2one('dsl.hrms.competency', string='Competency', required=True)
    expected_level_id = fields.Many2one('dsl.hrms.competency.level', string='Expected Level')
    actual_level_id = fields.Many2one('dsl.hrms.competency.level', string='Assessed Level')
    weightage = fields.Float(string='Weightage (%)', default=25.0)
    score = fields.Float(string='Score (/100)', default=85.0)
    reviewer_comment = fields.Char(string='Evaluator Remarks')


class DslHrmsPerformanceCheckin(models.Model):
    _name = 'dsl.hrms.performance.checkin'
    _description = 'Continuous Performance 1-on-1 Check-In (#31)'
    _order = 'checkin_date desc, id desc'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True)
    company_id = fields.Many2one('res.company', related='employee_id.company_id', store=True, readonly=True)
    cycle_id = fields.Many2one('dsl.hrms.assessment.cycle', string='Assessment Cycle', index=True)
    checkin_date = fields.Date(string='Check-In Date', required=True, default=fields.Date.context_today)
    reviewer_id = fields.Many2one('hr.employee', string='Manager / Coach')
    progress_summary = fields.Text(string='Key Progress & Wins', required=True)
    challenges = fields.Text(string='Blockers / Challenges')
    support_required = fields.Text(string='Support Needed from Manager')
    next_action = fields.Text(string='Agreed Next Steps')
    state = fields.Selection(
        selection=[('scheduled', 'Scheduled'), ('logged', 'Completed & Logged')],
        string='Status',
        default='logged',
    )


class DslHrmsPerformanceEvidence(models.Model):
    _name = 'dsl.hrms.performance.evidence'
    _description = 'Employee Performance Proof & Achievement Evidence (#32)'
    _order = 'id desc'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True)
    company_id = fields.Many2one('res.company', related='employee_id.company_id', store=True, readonly=True)
    cycle_id = fields.Many2one('dsl.hrms.assessment.cycle', string='Assessment Cycle', index=True)
    goal_id = fields.Many2one('dsl.hrms.goal', string='Linked Goal')
    kpi_id = fields.Many2one('dsl.hrms.kpi', string='Linked KPI')
    evidence_type = fields.Selection(
        selection=[
            ('project_delivery', 'Project Milestone / Release'),
            ('client_commendation', 'Client / Management Commendation'),
            ('metric_report', 'Audit / Production Metric Sheet'),
            ('certification', 'Certification / Patent / Award'),
        ],
        string='Evidence Type',
        default='project_delivery',
        required=True,
    )
    description = fields.Text(string='Achievement Summary', required=True)
    attachment_filename = fields.Char(string='File Name')
    attachment_file = fields.Binary(string='Supporting Document')
    submitted_by = fields.Many2one('res.users', string='Submitted By', default=lambda self: self.env.user)
    verified_by = fields.Many2one('res.users', string='Verified By')
    verified_at = fields.Datetime(string='Verified At')
    state = fields.Selection(
        selection=[('submitted', 'Submitted'), ('verified', 'Verified'), ('rejected', 'Rejected')],
        string='Status',
        default='verified',
    )

