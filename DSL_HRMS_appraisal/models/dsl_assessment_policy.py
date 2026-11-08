# -*- coding: utf-8 -*-
import json
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# 1. ASSESSMENT TYPE MASTER (`dsl.hrms.assessment.type` / #1)
#    Standard, Advanced, 360° Feedback, Probation, Custom
# =============================================================================
class DslHrmsAssessmentType(models.Model):
    _name = 'dsl.hrms.assessment.type'
    _description = 'DSL HRMS Assessment Process Type (Standard, Advanced, 360, Probation)'
    _order = 'sequence asc, id asc'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Assessment Type Name', required=True)
    code = fields.Char(string='Type Code', required=True, index=True)
    description = fields.Text(string='Process Description')
    is_system_type = fields.Boolean(string='Built-in System Type', default=False)
    default_phase_ids = fields.Many2many(
        'dsl.hrms.assessment.phase',
        'dsl_assessment_type_phase_rel',
        'type_id',
        'phase_id',
        string='Default Phases',
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Assessment Type Code must be unique!'),
    ]


# =============================================================================
# 2. ASSESSMENT PHASE MASTER (`dsl.hrms.assessment.phase` / #5)
#    SELF, MANAGER, DEPT_HEAD, PEER, SUBORDINATE, HR
# =============================================================================
class DslHrmsAssessmentPhase(models.Model):
    _name = 'dsl.hrms.assessment.phase'
    _description = 'DSL HRMS Assessment Review Phase Master'
    _order = 'sequence asc, id asc'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Phase Name', required=True)
    code = fields.Char(string='Phase Code', required=True, index=True)
    reviewer_role = fields.Selection(
        selection=[
            ('self', 'Self Review (নিজস্ব মূল্যায়ন)'),
            ('manager', 'Reporting Manager Review (লাইন ম্যানেজার)'),
            ('dept_head', 'Department Head / HOD Review (বিভাগীয় প্রধান)'),
            ('peer', 'Peer / Colleague Review (সহকর্মী - 360°)'),
            ('subordinate', 'Subordinate / Upward Review (অধস্তন - 360°)'),
            ('hr', 'HR / Calibration Review (এইচআর মূল্যায়ন)'),
        ],
        string='Reviewer Role',
        required=True,
        default='self',
    )
    default_weightage = fields.Float(string='Suggested Weightage (%)', default=25.0)
    default_anonymous = fields.Boolean(string='Default Anonymous (360°)', default=False)
    description = fields.Text(string='Phase Guidelines')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Assessment Phase Code must be unique!'),
    ]


# =============================================================================
# 3. ASSESSMENT POLICY (`dsl.hrms.assessment.policy` / #2)
#    Mother Company Group Policy + Sub-Company Selective Override Engine
# =============================================================================
class DslHrmsAssessmentPolicy(models.Model):
    _name = 'dsl.hrms.assessment.policy'
    _description = 'Multi-Company Configurable Assessment Policy & Inheritance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scope_type asc, id desc'

    name = fields.Char(string='Policy Name', required=True, tracking=True)
    code = fields.Char(string='Policy Code', required=True, index=True, tracking=True)
    owner_company_id = fields.Many2one(
        'res.company',
        string='Owner Company (Mother / Sub)',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='owner_company_id',
        store=True,
        readonly=True,
    )
    consumer_company_ids = fields.Many2many(
        'res.company',
        'dsl_assessment_policy_consumer_company_rel',
        'policy_id',
        'company_id',
        string='Applicable Group / Sub-Companies',
    )
    scope_type = fields.Selection(
        selection=[
            ('group', 'Mother Company Group Policy (গ্রুপ পলিসি)'),
            ('company', 'Sub-Company Policy (কোম্পানি পলিসি)'),
        ],
        string='Policy Scope',
        default='group',
        required=True,
        tracking=True,
    )
    parent_policy_id = fields.Many2one(
        'dsl.hrms.assessment.policy',
        string='Parent Group Policy',
        index=True,
        tracking=True,
    )
    parent_policy_version_id = fields.Many2one(
        'dsl.hrms.assessment.policy.version',
        string='Inherited Parent Version',
    )
    inheritance_mode = fields.Selection(
        selection=[
            ('inherit', 'Full Inherit (হুবহু প্যারেন্ট পলিসি অনুসরণ)'),
            ('selective', 'Selective Override (অনুমোদিত ফিল্ড পরিবর্তন)'),
            ('independent', 'Independent Policy (স্বতন্ত্র পলিসি)'),
        ],
        string='Inheritance Mode',
        default='inherit',
        required=True,
        tracking=True,
    )
    override_allowed = fields.Boolean(
        string='Allow Sub-Company Selective Override',
        default=True,
        tracking=True,
    )
    mandatory_group_policy = fields.Boolean(
        string='Mandatory Group Policy',
        default=False,
        tracking=True,
    )

    # Selective Override Permission Flags (Controlled by Mother Company)
    allow_override_frequency = fields.Boolean(string='Allow Frequency Override', default=True)
    allow_override_rating_scale = fields.Boolean(string='Allow Rating Scale Override', default=True)
    allow_override_self_review = fields.Boolean(string='Allow Self-Review Override', default=True)
    allow_override_peer_review = fields.Boolean(string='Allow Peer/360° Override', default=True)
    allow_override_min_service = fields.Boolean(string='Allow Min Service Days Override', default=True)
    allow_override_hr_review = fields.Boolean(string='Allow HR Review Override (Default Locked)', default=False)
    allow_override_final_approval = fields.Boolean(string='Allow Final Approval Override (Default Locked)', default=False)

    # Core Configurable Policy Values
    assessment_type_id = fields.Many2one(
        'dsl.hrms.assessment.type',
        string='Default Assessment Process',
        required=True,
        tracking=True,
    )
    default_cycle_type_id = fields.Many2one(
        'dsl.hrms.assessment.cycle.type',
        string='Default Cycle Frequency',
    )
    default_template_id = fields.Many2one(
        'dsl.hrms.assessment.template',
        string='Default Template',
    )
    default_rating_scale_id = fields.Many2one(
        'dsl.hrms.assessment.rating.scale',
        string='Default Rating Scale',
    )
    minimum_service_days = fields.Integer(string='Minimum Service Eligibility (Days)', default=180)
    self_review_enabled = fields.Boolean(string='Enable Self Review', default=True)
    peer_review_enabled = fields.Boolean(string='Enable Peer / 360° Review', default=False)
    hr_review_mandatory = fields.Boolean(string='Mandatory HR Calibration / Review', default=True)
    final_approval_authority = fields.Selection(
        selection=[
            ('group_hr', 'Group HR & Management'),
            ('company_head', 'Company Head / MD'),
            ('dept_head', 'Department Head'),
        ],
        string='Final Approval Authority',
        default='group_hr',
        required=True,
    )
    optional_phase_mode = fields.Selection(
        selection=[
            ('renormalize', 'Renormalize Completed Phases to 100% (প্রস্তাবিত)'),
            ('zero_contribution', 'Zero Contribution for Skipped Optional Phase'),
        ],
        string='Optional Phase Scoring Rule',
        default='renormalize',
        required=True,
    )
    allow_multi_phase_same_reviewer = fields.Boolean(
        string='Allow Reviewer in Multiple Phases',
        default=False,
    )
    min_anonymous_reviewers = fields.Integer(
        string='Min Anonymous Reviewers to Reveal Aggregate',
        default=2,
    )

    policy_version_id = fields.Many2one(
        'dsl.hrms.assessment.policy.version',
        string='Active Policy Version',
        readonly=True,
    )
    version_ids = fields.One2many(
        'dsl.hrms.assessment.policy.version',
        'policy_id',
        string='Policy Version History',
    )
    override_log_ids = fields.One2many(
        'dsl.hrms.assessment.policy.override.log',
        'child_policy_id',
        string='Selective Override Audit Logs',
    )
    effective_from = fields.Date(string='Effective From', default=fields.Date.context_today)
    effective_to = fields.Date(string='Effective Until')
    notes = fields.Text(string='Policy Governance Notes')
    active = fields.Boolean(default=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active & Published'),
            ('archived', 'Archived'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    @api.constrains(
        'parent_policy_id',
        'inheritance_mode',
        'hr_review_mandatory',
        'final_approval_authority',
        'default_rating_scale_id',
        'minimum_service_days',
    )
    def _check_selective_override_permissions(self):
        for rec in self:
            parent = rec.parent_policy_id
            if not parent or rec.inheritance_mode == 'independent':
                continue
            if not parent.override_allowed and rec.inheritance_mode != 'inherit':
                raise ValidationError(_(
                    'Parent Policy "%s" does not permit Sub-Company overrides!'
                ) % parent.name)
            if not parent.allow_override_hr_review and rec.hr_review_mandatory != parent.hr_review_mandatory:
                raise ValidationError(_(
                    'Override Blocked: Mother Company Policy "%s" locks "Mandatory HR Review".'
                ) % parent.name)
            if not parent.allow_override_final_approval and rec.final_approval_authority != parent.final_approval_authority:
                raise ValidationError(_(
                    'Override Blocked: Mother Company Policy "%s" locks "Final Approval Authority".'
                ) % parent.name)
            if not parent.allow_override_rating_scale and rec.default_rating_scale_id != parent.default_rating_scale_id:
                raise ValidationError(_(
                    'Override Blocked: Mother Company Policy "%s" locks "Default Rating Scale".'
                ) % parent.name)
            if not parent.allow_override_min_service and rec.minimum_service_days != parent.minimum_service_days:
                raise ValidationError(_(
                    'Override Blocked: Mother Company Policy "%s" locks "Minimum Service Days".'
                ) % parent.name)

    def action_publish_new_version(self):
        """Creates an immutable frozen Policy Version snapshot without mutating running cycles."""
        Version = self.env['dsl.hrms.assessment.policy.version'].sudo()
        PhaseLine = self.env['dsl.hrms.assessment.policy.phase'].sudo()
        for rec in self:
            next_ver = len(rec.version_ids) + 1
            if rec.version_ids:
                rec.version_ids.filtered(lambda v: v.state == 'active').write({'state': 'superseded'})

            snapshot = {
                'policy_code': rec.code,
                'owner_company_id': rec.owner_company_id.id,
                'scope_type': rec.scope_type,
                'inheritance_mode': rec.inheritance_mode,
                'assessment_type': rec.assessment_type_id.code,
                'minimum_service_days': rec.minimum_service_days,
                'hr_review_mandatory': rec.hr_review_mandatory,
                'final_approval_authority': rec.final_approval_authority,
                'optional_phase_mode': rec.optional_phase_mode,
            }
            ver = Version.create({
                'policy_id': rec.id,
                'version_number': next_ver,
                'version_name': f'{rec.code} — v{next_ver}.0',
                'change_summary': f'Published version v{next_ver}.0 of {rec.name}',
                'configuration_snapshot': json.dumps(snapshot, indent=2),
                'effective_from': rec.effective_from or fields.Date.context_today(self),
                'approved_by': self.env.uid,
                'approved_at': fields.Datetime.now(),
                'state': 'active',
            })

            # Seed default phases from Assessment Type if not already populated
            phases = rec.assessment_type_id.default_phase_ids
            if not phases:
                phases = self.env['dsl.hrms.assessment.phase'].sudo().search([], limit=3)
            total_def = sum(phases.mapped('default_weightage')) or 100.0
            seq = 10
            for ph in phases:
                norm_w = round((ph.default_weightage / total_def) * 100.0, 2) if total_def else 0.0
                PhaseLine.create({
                    'policy_version_id': ver.id,
                    'phase_id': ph.id,
                    'sequence': seq,
                    'enabled': True,
                    'required': ph.reviewer_role in ('self', 'manager', 'hr'),
                    'reviewer_type': ph.reviewer_role,
                    'minimum_reviewers': 2 if ph.reviewer_role in ('peer', 'subordinate') else 1,
                    'maximum_reviewers': 5 if ph.reviewer_role in ('peer', 'subordinate') else 1,
                    'reviewer_selection_method': 'nomination' if ph.reviewer_role in ('peer', 'subordinate') else 'auto',
                    'template_id': rec.default_template_id.id if rec.default_template_id else False,
                    'weightage': norm_w,
                    'is_scored': True,
                    'anonymous': ph.default_anonymous,
                    'deadline_days': 7,
                })
                seq += 10

            rec.write({
                'policy_version_id': ver.id,
                'state': 'active',
            })


# =============================================================================
# 4. POLICY VERSION (`dsl.hrms.assessment.policy.version` / #3)
# =============================================================================
class DslHrmsAssessmentPolicyVersion(models.Model):
    _name = 'dsl.hrms.assessment.policy.version'
    _description = 'Immutable Assessment Policy Version & Phase Configuration'
    _order = 'version_number desc, id desc'

    name = fields.Char(string='Version Label', related='version_name', store=True)
    policy_id = fields.Many2one(
        'dsl.hrms.assessment.policy',
        string='Assessment Policy',
        required=True,
        ondelete='restrict',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='policy_id.owner_company_id',
        store=True,
        readonly=True,
    )
    version_number = fields.Integer(string='Version No.', required=True, default=1)
    version_name = fields.Char(string='Version Name', required=True)
    change_summary = fields.Text(string='Change Summary')
    configuration_snapshot = fields.Text(string='Frozen Configuration JSON', readonly=True)
    phase_ids = fields.One2many(
        'dsl.hrms.assessment.policy.phase',
        'policy_version_id',
        string='Configured Review Phases',
    )
    total_scored_weightage = fields.Float(
        string='Total Scored Weightage (%)',
        compute='_compute_total_scored_weightage',
        store=True,
    )
    effective_from = fields.Date(string='Effective From', default=fields.Date.context_today)
    effective_to = fields.Date(string='Effective To')
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approved_at = fields.Datetime(string='Approved At', readonly=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('approved', 'Approved'),
            ('active', 'Active'),
            ('superseded', 'Superseded'),
        ],
        string='Status',
        default='active',
        required=True,
    )

    @api.depends('phase_ids.enabled', 'phase_ids.is_scored', 'phase_ids.weightage')
    def _compute_total_scored_weightage(self):
        for rec in self:
            scored_lines = rec.phase_ids.filtered(lambda l: l.enabled and l.is_scored)
            rec.total_scored_weightage = round(sum(scored_lines.mapped('weightage')), 2)

    def action_validate_phase_weightage(self):
        for rec in self:
            if rec.phase_ids and abs(rec.total_scored_weightage - 100.0) > 0.05:
                raise ValidationError(_(
                    'Enabled & Scored Phase Weightages for Policy Version "%s" must total 100%% (currently %s%%)!'
                ) % (rec.version_name, rec.total_scored_weightage))


# =============================================================================
# 5. POLICY PHASE CONFIGURATION (`dsl.hrms.assessment.policy.phase` / #4)
# =============================================================================
class DslHrmsAssessmentPolicyPhase(models.Model):
    _name = 'dsl.hrms.assessment.policy.phase'
    _description = 'Assessment Policy Phase & Weightage Configuration'
    _order = 'sequence asc, id asc'

    policy_version_id = fields.Many2one(
        'dsl.hrms.assessment.policy.version',
        string='Policy Version',
        required=True,
        ondelete='cascade',
        index=True,
    )
    phase_id = fields.Many2one(
        'dsl.hrms.assessment.phase',
        string='Review Phase',
        required=True,
        ondelete='restrict',
    )
    sequence = fields.Integer(string='Order', default=10)
    enabled = fields.Boolean(string='Enabled', default=True)
    required = fields.Boolean(string='Mandatory Phase', default=True)
    reviewer_type = fields.Selection(
        selection=[
            ('self', 'Self'),
            ('manager', 'Reporting Manager'),
            ('dept_head', 'Department Head'),
            ('peer', 'Peer (360°)'),
            ('subordinate', 'Subordinate (360°)'),
            ('hr', 'HR / Calibrator'),
        ],
        string='Reviewer Type',
        required=True,
        default='self',
    )
    minimum_reviewers = fields.Integer(string='Min Reviewers', default=1)
    maximum_reviewers = fields.Integer(string='Max Reviewers', default=1)
    reviewer_selection_method = fields.Selection(
        selection=[
            ('auto', 'Auto by Reporting Hierarchy'),
            ('nomination', 'Employee / Manager Nomination'),
            ('hr', 'HR Assigned'),
        ],
        string='Selection Method',
        default='auto',
        required=True,
    )
    template_id = fields.Many2one('dsl.hrms.assessment.template', string='Phase Template')
    weightage = fields.Float(string='Phase Weightage (%)', default=25.0)
    is_scored = fields.Boolean(string='Contributes to Final Score', default=True)
    anonymous = fields.Boolean(string='Anonymous Reviewer Identity', default=False)
    deadline_days = fields.Integer(string='Due Offset (Days)', default=7)
    approval_required = fields.Boolean(string='Requires Phase Sign-Off', default=False)
    allow_comment = fields.Boolean(string='Allow Comments', default=True)
    allow_attachment = fields.Boolean(string='Allow Evidence Upload', default=True)


# =============================================================================
# 6. POLICY OVERRIDE LOG (`dsl.hrms.assessment.policy.override.log` / #10)
# =============================================================================
class DslHrmsAssessmentPolicyOverrideLog(models.Model):
    _name = 'dsl.hrms.assessment.policy.override.log'
    _description = 'Sub-Company Policy Selective Override Approval & Audit Log'
    _order = 'id desc'

    parent_policy_id = fields.Many2one('dsl.hrms.assessment.policy', string='Parent Group Policy', required=True)
    child_policy_id = fields.Many2one('dsl.hrms.assessment.policy', string='Sub-Company Policy', required=True)
    policy_version_id = fields.Many2one('dsl.hrms.assessment.policy.version', string='Policy Version')
    company_id = fields.Many2one('res.company', string='Sub-Company', required=True, default=lambda self: self.env.company)
    override_category = fields.Selection(
        selection=[
            ('frequency', 'Assessment Frequency'),
            ('rating_scale', 'Rating Scale'),
            ('phase_weightage', 'Phase & Weightage'),
            ('peer_360', 'Peer / 360° Configuration'),
            ('eligibility', 'Minimum Service / Eligibility'),
        ],
        string='Override Category',
        default='phase_weightage',
        required=True,
    )
    field_name = fields.Char(string='Overridden Field', required=True)
    parent_value = fields.Char(string='Group Default Value')
    override_value = fields.Char(string='Sub-Company Value', required=True)
    reason = fields.Text(string='Business Justification', required=True)
    requested_by = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user)
    approved_by = fields.Many2one('res.users', string='Mother Company Approver')
    approved_at = fields.Datetime(string='Approved At')
    state = fields.Selection(
        selection=[
            ('pending', 'Pending Group HR Approval'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='approved',
        required=True,
    )
