# -*- coding: utf-8 -*-
import json
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


# =============================================================================
# 1. RATING SCALE & RATING LEVELS (`dsl.hrms.assessment.rating.scale` / #17, #18)
# =============================================================================
class DslHrmsAssessmentRatingScale(models.Model):
    _name = 'dsl.hrms.assessment.rating.scale'
    _description = 'Assessment Rating Scale (1-5, 1-10, 0-100 Percentage)'
    _order = 'id asc'

    name = fields.Char(string='Rating Scale Name', required=True)
    code = fields.Char(string='Scale Code', required=True, index=True)
    owner_company_id = fields.Many2one(
        'res.company',
        string='Owner Company',
        default=lambda self: self.env.company,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='owner_company_id',
        store=True,
        readonly=True,
    )
    scope_type = fields.Selection(
        selection=[
            ('group', 'Group-Wide Scale'),
            ('company', 'Company-Specific Scale'),
        ],
        string='Scope',
        default='group',
        required=True,
    )
    scale_type = fields.Selection(
        selection=[
            ('point_5', '5-Point Scale (1 to 5)'),
            ('point_10', '10-Point Scale (1 to 10)'),
            ('percentage', 'Percentage Scale (0 to 100)'),
            ('band_range', 'Configured Score Range per Level'),
        ],
        string='Scale Type',
        default='point_5',
        required=True,
    )
    minimum_value = fields.Float(string='Minimum Value', required=True, default=1.0)
    maximum_value = fields.Float(string='Maximum Value', required=True, default=5.0)
    decimal_precision = fields.Integer(string='Decimal Precision', default=2)
    rounding_method = fields.Selection(
        selection=[
            ('half_up', 'Round Half Up (Standard)'),
            ('nearest_int', 'Nearest Whole Number'),
        ],
        string='Rounding Rule',
        default='half_up',
        required=True,
    )
    rating_level_ids = fields.One2many(
        'dsl.hrms.assessment.rating.level',
        'rating_scale_id',
        string='Rating Levels & Score Bands',
    )
    active = fields.Boolean(default=True)
    state = fields.Selection(
        selection=[('draft', 'Draft'), ('active', 'Active'), ('archived', 'Archived')],
        string='Status',
        default='active',
        required=True,
    )

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Rating Scale Code must be unique!'),
    ]

    def normalize_rating_to_100(self, rating_val):
        """
        Part 7.1 Normalization Engine:
        - If scale_type == 'band_range' and a matching level has score_to > 0, uses level score band.
        - Otherwise applies ((Rating - Min) / (Max - Min)) * 100.
        """
        self.ensure_one()
        val = float(rating_val or 0.0)
        if val < self.minimum_value:
            val = self.minimum_value
        if val > self.maximum_value:
            val = self.maximum_value

        if self.scale_type == 'band_range' and self.rating_level_ids:
            lvl = self.rating_level_ids.filtered(lambda l: abs(l.rating_value - val) < 0.01)[:1]
            if lvl and lvl.score_to > 0:
                return round((lvl.score_from + lvl.score_to) / 2.0, self.decimal_precision or 2)

        span = float(self.maximum_value - self.minimum_value)
        if span <= 0:
            return 0.0
        norm = ((val - float(self.minimum_value)) / span) * 100.0
        if self.rounding_method == 'nearest_int':
            return float(round(norm))
        return round(norm, self.decimal_precision or 2)

    def match_rating_level_by_score(self, score_100):
        self.ensure_one()
        sc = float(score_100 or 0.0)
        for lvl in self.rating_level_ids.sorted(key=lambda l: l.score_from, reverse=True):
            if sc >= lvl.score_from:
                return lvl
        return self.rating_level_ids[:1]


class DslHrmsAssessmentRatingLevel(models.Model):
    _name = 'dsl.hrms.assessment.rating.level'
    _description = 'Assessment Rating Level & Bell-Curve Band'
    _order = 'sequence asc, rating_value desc'

    sequence = fields.Integer(default=10)
    rating_scale_id = fields.Many2one(
        'dsl.hrms.assessment.rating.scale',
        string='Rating Scale',
        required=True,
        ondelete='restrict',
        index=True,
    )
    name = fields.Char(string='Level Name', related='rating_label', store=True)
    rating_value = fields.Float(string='Rating Point', required=True, default=5.0)
    rating_label = fields.Char(string='Rating Label (e.g. A+ / Outstanding)', required=True)
    description = fields.Text(string='Behavioral Benchmark')
    score_from = fields.Float(string='Score From (%)', required=True, default=90.0)
    score_to = fields.Float(string='Score To (%)', required=True, default=100.0)
    recommended_increment_pct = fields.Float(string='Suggested Increment (%)', default=10.0)
    display_color = fields.Selection(
        selection=[
            ('success', 'Green (Outstanding / Exceeds)'),
            ('info', 'Blue (Meets Expectations)'),
            ('warning', 'Amber (Needs Improvement)'),
            ('danger', 'Red (Unsatisfactory / PIP)'),
        ],
        string='Badge Color',
        default='success',
    )


# =============================================================================
# 2. ASSESSMENT CATEGORY (`dsl.hrms.assessment.category` / #19)
#    KPI / KRA / Competency / Behaviour / Goal
# =============================================================================
class DslHrmsAssessmentCategory(models.Model):
    _name = 'dsl.hrms.assessment.category'
    _description = 'Assessment Evaluation Category (KPI, KRA, Competency, Behaviour, Goal)'
    _order = 'sequence asc, id asc'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Category Name', required=True)
    code = fields.Char(string='Category Code', required=True, index=True)
    category_type = fields.Selection(
        selection=[
            ('kpi', 'KPI (Key Performance Indicator)'),
            ('kra', 'KRA (Key Result Area)'),
            ('competency', 'Competency (Core / Functional / Leadership)'),
            ('behaviour', 'Behavioural & Cultural Values'),
            ('goal', 'OKR / Strategic Goal Achievement'),
        ],
        string='Category Type',
        required=True,
        default='kpi',
    )
    parent_category_id = fields.Many2one('dsl.hrms.assessment.category', string='Parent Category')
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)


# =============================================================================
# 3. ASSESSMENT TEMPLATE & VERSION (`dsl.hrms.assessment.template` / #11, #12)
# =============================================================================
class DslHrmsAssessmentTemplate(models.Model):
    _name = 'dsl.hrms.assessment.template'
    _description = 'Configurable Assessment Form Template'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Template Title', required=True, tracking=True)
    code = fields.Char(string='Template Code', required=True, index=True, tracking=True)
    owner_company_id = fields.Many2one(
        'res.company',
        string='Owner Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='owner_company_id',
        store=True,
        readonly=True,
    )
    scope_type = fields.Selection(
        selection=[
            ('group', 'Group-Wide Template'),
            ('company', 'Company-Specific Template'),
        ],
        string='Scope',
        default='group',
        required=True,
    )
    template_type = fields.Selection(
        selection=[
            ('general', 'General Multi-Phase Template'),
            ('self', 'Self-Review Template'),
            ('manager', 'Manager / HOD Evaluation Template'),
            ('peer', '360° Peer & Subordinate Template'),
            ('probation', 'Probation Confirmation Scorecard'),
            ('hr', 'HR Calibration & Final Review Template'),
        ],
        string='Template Purpose',
        default='general',
        required=True,
    )
    rating_scale_id = fields.Many2one(
        'dsl.hrms.assessment.rating.scale',
        string='Default Rating Scale',
        required=True,
    )
    department_ids = fields.Many2many(
        'hr.department',
        'dsl_ass_tpl_dept_rel',
        'template_id',
        'department_id',
        string='Target Departments',
    )
    designation_ids = fields.Many2many(
        'hr.job',
        'dsl_ass_tpl_job_rel',
        'template_id',
        'job_id',
        string='Target Designations',
    )
    section_ids = fields.One2many(
        'dsl.hrms.assessment.template.section',
        'template_id',
        string='Form Sections & Questions',
    )
    version = fields.Integer(string='Active Version No.', default=1, readonly=True)
    version_ids = fields.One2many(
        'dsl.hrms.assessment.template.version',
        'template_id',
        string='Template Versions',
    )
    total_section_weightage = fields.Float(
        string='Total Scored Section Weight (%)',
        compute='_compute_total_section_weightage',
        store=True,
    )
    description = fields.Text(string='Instructions for Reviewers')
    effective_from = fields.Date(string='Effective From', default=fields.Date.context_today)
    effective_to = fields.Date(string='Effective To')
    active = fields.Boolean(default=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('published', 'Published & Ready'),
            ('archived', 'Archived'),
        ],
        string='Status',
        default='published',
        required=True,
        tracking=True,
    )

    @api.depends('section_ids.scored', 'section_ids.weightage')
    def _compute_total_section_weightage(self):
        for rec in self:
            scored_secs = rec.section_ids.filtered(lambda s: s.scored)
            rec.total_section_weightage = round(sum(scored_secs.mapped('weightage')), 2)

    def action_publish_template_version(self):
        Ver = self.env['dsl.hrms.assessment.template.version'].sudo()
        for rec in self:
            if rec.section_ids and abs(rec.total_section_weightage - 100.0) > 0.05:
                raise ValidationError(_(
                    'Total Scored Section Weightage in Template "%s" must equal 100%% (currently %s%%)!'
                ) % (rec.name, rec.total_section_weightage))
            next_v = len(rec.version_ids) + 1
            snap = {
                'template_code': rec.code,
                'version': next_v,
                'sections': [
                    {
                        'code': s.code,
                        'name': s.name,
                        'weightage': s.weightage,
                        'questions': [
                            {
                                'code': q.code,
                                'text': q.question_text,
                                'type': q.question_type,
                                'weightage': q.weightage,
                            }
                            for q in s.question_ids
                        ],
                    }
                    for s in rec.section_ids
                ],
            }
            Ver.create({
                'template_id': rec.id,
                'version_number': next_v,
                'change_summary': f'Published template version v{next_v}.0',
                'template_snapshot': json.dumps(snap, indent=2),
                'published_by': self.env.uid,
                'published_at': fields.Datetime.now(),
                'state': 'published',
            })
            rec.write({'version': next_v, 'state': 'published'})


class DslHrmsAssessmentTemplateVersion(models.Model):
    _name = 'dsl.hrms.assessment.template.version'
    _description = 'Immutable Assessment Template Version Snapshot'
    _order = 'version_number desc, id desc'

    name = fields.Char(string='Version Label', compute='_compute_name', store=True)
    template_id = fields.Many2one(
        'dsl.hrms.assessment.template',
        string='Template',
        required=True,
        ondelete='restrict',
        index=True,
    )
    version_number = fields.Integer(string='Version No.', required=True, default=1)
    change_summary = fields.Text(string='Change Summary')
    template_snapshot = fields.Text(string='Frozen Template Snapshot JSON', readonly=True)
    published_by = fields.Many2one('res.users', string='Published By', readonly=True)
    published_at = fields.Datetime(string='Published At', readonly=True)
    state = fields.Selection(
        selection=[('draft', 'Draft'), ('published', 'Published'), ('superseded', 'Superseded')],
        string='Status',
        default='published',
    )

    @api.depends('template_id.code', 'version_number')
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.template_id.code or 'TPL'} — v{rec.version_number}.0"


# =============================================================================
# 4. TEMPLATE SECTIONS, QUESTIONS, OPTIONS & CONDITIONAL RULES (#13, #14, #15, #16, #20)
# =============================================================================
class DslHrmsAssessmentTemplateSection(models.Model):
    _name = 'dsl.hrms.assessment.template.section'
    _description = 'Assessment Template Section (KPI / Competency / Behaviour)'
    _order = 'sequence asc, id asc'

    template_id = fields.Many2one(
        'dsl.hrms.assessment.template',
        string='Assessment Template',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(string='Order', default=10)
    name = fields.Char(string='Section Title', required=True)
    code = fields.Char(string='Section Code', required=True)
    category_id = fields.Many2one('dsl.hrms.assessment.category', string='Category')
    description = fields.Text(string='Section Guidelines')
    weightage = fields.Float(string='Section Weightage (%)', default=50.0)
    required = fields.Boolean(string='Mandatory Section', default=True)
    scored = fields.Boolean(string='Scored Section', default=True)
    question_ids = fields.One2many(
        'dsl.hrms.assessment.question',
        'section_id',
        string='Evaluation Questions / Criteria',
    )


class DslHrmsAssessmentQuestion(models.Model):
    _name = 'dsl.hrms.assessment.question'
    _description = 'Assessment Template Question & Evaluation Criterion'
    _order = 'sequence asc, id asc'

    section_id = fields.Many2one(
        'dsl.hrms.assessment.template.section',
        string='Template Section',
        required=True,
        ondelete='cascade',
        index=True,
    )
    template_id = fields.Many2one(
        'dsl.hrms.assessment.template',
        related='section_id.template_id',
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(string='Order', default=10)
    code = fields.Char(string='Question Code', required=True)
    question_text = fields.Text(string='Question / Evaluation Criterion', required=True)
    question_type = fields.Selection(
        selection=[
            ('rating', 'Rating Scale (1-5 / 1-10)'),
            ('percentage', 'Percentage Achievement (0-100%)'),
            ('goal_achievement', 'KPI / Goal Achievement'),
            ('numeric', 'Numeric Value'),
            ('yes_no', 'Yes / No (Boolean)'),
            ('single_choice', 'Single Choice Option'),
            ('multiple_choice', 'Multiple Choice Options'),
            ('text', 'Descriptive Text Feedback'),
            ('date', 'Date'),
            ('attachment', 'Evidence Document Upload'),
        ],
        string='Question Type',
        default='rating',
        required=True,
    )
    rating_scale_id = fields.Many2one(
        'dsl.hrms.assessment.rating.scale',
        string='Rating Scale',
    )
    weightage = fields.Float(string='Question Weightage (%)', default=25.0)
    required = fields.Boolean(string='Mandatory', default=True)
    scored = fields.Boolean(string='Scored', default=True)
    help_text = fields.Char(string='Guidance / Benchmark Hint')
    option_ids = fields.One2many(
        'dsl.hrms.assessment.question.option',
        'question_id',
        string='Multiple Choice Options',
    )
    rule_ids = fields.One2many(
        'dsl.hrms.assessment.question.rule',
        'question_id',
        string='Conditional Visibility Rules',
    )
    active = fields.Boolean(default=True)


class DslHrmsAssessmentQuestionOption(models.Model):
    _name = 'dsl.hrms.assessment.question.option'
    _description = 'Assessment Multiple-Choice Question Option'
    _order = 'sequence asc, id asc'

    sequence = fields.Integer(default=10)
    question_id = fields.Many2one(
        'dsl.hrms.assessment.question',
        string='Question',
        required=True,
        ondelete='cascade',
        index=True,
    )
    label = fields.Char(string='Option Label', required=True)
    value = fields.Char(string='Option Code / Value', required=True)
    score = fields.Float(string='Normalized Score (0-100)', default=100.0)
    active = fields.Boolean(default=True)


class DslHrmsAssessmentQuestionRule(models.Model):
    _name = 'dsl.hrms.assessment.question.rule'
    _description = 'Conditional Question Visibility Rule'
    _order = 'sequence asc, id asc'

    sequence = fields.Integer(default=10)
    question_id = fields.Many2one(
        'dsl.hrms.assessment.question',
        string='Source Question',
        required=True,
        ondelete='cascade',
    )
    condition_question_id = fields.Many2one(
        'dsl.hrms.assessment.question',
        string='If Question',
    )
    operator = fields.Selection(
        selection=[
            ('equals', 'Equals (=)'),
            ('not_equals', 'Not Equals (!=)'),
            ('greater_than', 'Greater Than (>)'),
        ],
        string='Condition Operator',
        default='equals',
        required=True,
    )
    condition_value = fields.Char(string='Expected Answer (e.g. Yes)', required=True)
    action_type = fields.Selection(
        selection=[
            ('show', 'Show Target Question / Section'),
            ('require', 'Make Target Question Mandatory'),
            ('hide', 'Hide Target Question'),
        ],
        string='Action',
        default='show',
        required=True,
    )
    target_question_id = fields.Many2one(
        'dsl.hrms.assessment.question',
        string='Target Question',
    )


class DslHrmsAssessmentWeightageRule(models.Model):
    _name = 'dsl.hrms.assessment.weightage.rule'
    _description = 'Category & Phase Weightage Normalization Rule (#20)'
    _order = 'sequence asc, id asc'

    sequence = fields.Integer(default=10)
    policy_version_id = fields.Many2one('dsl.hrms.assessment.policy.version', string='Policy Version')
    template_version_id = fields.Many2one('dsl.hrms.assessment.template.version', string='Template Version')
    category_id = fields.Many2one('dsl.hrms.assessment.category', string='Category (KPI/KRA/Competency)', required=True)
    phase_id = fields.Many2one('dsl.hrms.assessment.phase', string='Review Phase')
    weightage = fields.Float(string='Category Weightage (%)', required=True, default=50.0)
    calculation_method = fields.Selection(
        selection=[
            ('weighted_avg', 'Weighted Average of Questions'),
            ('simple_avg', 'Simple Arithmetic Mean'),
        ],
        string='Calculation Method',
        default='weighted_avg',
        required=True,
    )
    normalization_method = fields.Selection(
        selection=[
            ('scale_100', 'Normalize to 0–100 Scale'),
            ('raw', 'Keep Raw Score'),
        ],
        string='Normalization',
        default='scale_100',
        required=True,
    )
    minimum_score = fields.Float(string='Min Score Floor', default=0.0)
    maximum_score = fields.Float(string='Max Score Cap', default=100.0)
