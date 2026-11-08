# -*- coding: utf-8 -*-
import json
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# 1. EMPLOYEE ASSESSMENT (`dsl.hrms.assessment` / #33)
#    Single Configurable Engine for Standard, Advanced, 360° & Probation
# =============================================================================
class DslHrmsAssessment(models.Model):
    _name = 'dsl.hrms.assessment'
    _description = 'Employee Configurable Performance Assessment (Standard / Advanced / 360°)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Assessment Ref.',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
    )
    code = fields.Char(string='Unique Reference', related='name', store=True, readonly=True)

    # Historical Organizational Snapshot (Never mutates when Employee Transfers!)
    company_id = fields.Many2one(
        'res.company',
        string='Assessment Company (Snapshot)',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Subject Employee',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )
    branch_id = fields.Many2one('dsl.branch', string='Historical Branch / Plant', index=True)
    department_id = fields.Many2one('hr.department', string='Historical Department', index=True)
    designation_id = fields.Many2one('hr.job', string='Historical Designation')
    manager_id = fields.Many2one('hr.employee', string='Historical Reporting Manager')

    cycle_id = fields.Many2one(
        'dsl.hrms.assessment.cycle',
        string='Assessment Cycle',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )
    assessment_scope = fields.Selection(
        selection=[
            ('annual', 'Annual / Half-Yearly'),
            ('quarterly', 'Quarterly'),
            ('probation', 'Probation Confirmation'),
            ('project', 'Project Review'),
        ],
        string='Assessment Scope',
        default='annual',
        required=True,
        index=True,
    )
    policy_version_id = fields.Many2one(
        'dsl.hrms.assessment.policy.version',
        string='Policy Version Snapshot',
        ondelete='restrict',
    )
    template_id = fields.Many2one(
        'dsl.hrms.assessment.template',
        string='Assessment Template',
        ondelete='restrict',
    )
    template_version_id = fields.Many2one(
        'dsl.hrms.assessment.template.version',
        string='Template Version Snapshot',
        ondelete='restrict',
    )
    rating_scale_id = fields.Many2one(
        'dsl.hrms.assessment.rating.scale',
        string='Rating Scale Snapshot',
        ondelete='restrict',
    )
    assessment_type_id = fields.Many2one(
        'dsl.hrms.assessment.type',
        string='Process Type',
        ondelete='restrict',
    )
    date_from = fields.Date(string='Period From', index=True)
    date_to = fields.Date(string='Period To', index=True)

    # Relational Execution Lines
    participant_ids = fields.One2many(
        'dsl.hrms.assessment.participant',
        'assessment_id',
        string='Participants',
    )
    phase_instance_ids = fields.One2many(
        'dsl.hrms.assessment.phase.instance',
        'assessment_id',
        string='Phase Execution Instances',
    )
    reviewer_ids = fields.One2many(
        'dsl.hrms.assessment.reviewer',
        'assessment_id',
        string='Assigned Reviewers',
    )
    assignment_ids = fields.One2many(
        'dsl.hrms.assessment.assignment',
        'assessment_id',
        string='Reviewer Inbox Tasks',
    )
    response_ids = fields.One2many(
        'dsl.hrms.assessment.response',
        'assessment_id',
        string='Submitted Responses',
    )
    score_ids = fields.One2many(
        'dsl.hrms.assessment.score',
        'assessment_id',
        string='Phase & Reviewer Score Breakdown',
    )
    comment_ids = fields.One2many(
        'dsl.hrms.assessment.comment',
        'assessment_id',
        string='Feedback & Comments',
    )
    attachment_ids = fields.One2many(
        'dsl.hrms.assessment.attachment',
        'assessment_id',
        string='Evidence Documents',
    )
    result_id = fields.Many2one(
        'dsl.hrms.assessment.result',
        string='Final Assessment Result',
        ondelete='restrict',
    )
    self_score_display = fields.Float(
        related='result_id.self_score',
        string='Self Score (/100)',
        store=True,
        readonly=True,
    )
    manager_score_display = fields.Float(
        related='result_id.manager_score',
        string='Manager Score (/100)',
        store=True,
        readonly=True,
    )
    peer_score_display = fields.Float(
        related='result_id.peer_score',
        string='360° Peer Score (/100)',
        store=True,
        readonly=True,
    )
    final_score = fields.Float(
        related='result_id.final_score',
        string='Final Score (/100)',
        store=True,
        readonly=True,
    )
    rating_level_id = fields.Many2one(
        'dsl.hrms.assessment.rating.level',
        related='result_id.rating_level_id',
        string='Final Rating Band',
        store=True,
        readonly=True,
    )
    approval_ids = fields.One2many(
        'dsl.hrms.assessment.approval',
        'assessment_id',
        string='Approval Chain',
    )
    acknowledgment_ids = fields.One2many(
        'dsl.hrms.assessment.acknowledgment',
        'assessment_id',
        string='Employee Acknowledgments',
    )
    appeal_ids = fields.One2many(
        'dsl.hrms.assessment.appeal',
        'assessment_id',
        string='Employee Appeals',
    )
    reopen_request_ids = fields.One2many(
        'dsl.hrms.assessment.reopen.request',
        'assessment_id',
        string='Reopen Requests',
    )
    audit_log_ids = fields.One2many(
        'dsl.hrms.assessment.audit.log',
        'assessment_id',
        string='Immutable Audit Trail',
    )

    started_at = fields.Datetime(string='Started At')
    completed_at = fields.Datetime(string='Completed At')
    published_at = fields.Datetime(string='Published At')
    locked = fields.Boolean(string='Locked', default=False, tracking=True)
    cancel_reason = fields.Text(string='Cancellation Reason')

    # Part 8.2 Full 13-State Assessment Machine
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('pending_assignment', 'Pending Assignment'),
            ('in_progress', 'In Progress'),
            ('submitted', 'Responses Submitted'),
            ('under_review', 'Under Review'),
            ('calibration', 'HR Calibration'),
            ('pending_approval', 'Pending Approval'),
            ('approved', 'Approved'),
            ('published', 'Published'),
            ('acknowledged', 'Employee Acknowledged'),
            ('appealed', 'Appealed'),
            ('reopened', 'Reopened'),
            ('cancelled', 'Cancelled'),
        ],
        string='Assessment Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )

    _sql_constraints = [
        (
            'cycle_emp_scope_uniq',
            'unique(cycle_id, employee_id, assessment_scope)',
            'Duplicate Assessment for the same Employee, Cycle & Scope is blocked (Part 5.3 / 9.1)!',
        ),
    ]

    @api.onchange('employee_id')
    def _onchange_employee_snapshot(self):
        if self.employee_id:
            self.company_id = self.employee_id.company_id
            self.branch_id = self.employee_id.branch_id
            self.department_id = self.employee_id.department_id
            self.designation_id = self.employee_id.job_id
            self.manager_id = self.employee_id.parent_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.hrms.assessment') or _('ASM-NEW')
            if vals.get('employee_id') and not vals.get('department_id'):
                emp = self.env['hr.employee'].sudo().browse(vals['employee_id'])
                vals.setdefault('company_id', emp.company_id.id)
                vals.setdefault('branch_id', emp.branch_id.id if emp.branch_id else False)
                vals.setdefault('department_id', emp.department_id.id if emp.department_id else False)
                vals.setdefault('designation_id', emp.job_id.id if emp.job_id else False)
                vals.setdefault('manager_id', emp.parent_id.id if emp.parent_id else False)
        recs = super().create(vals_list)
        for rec in recs:
            rec._log_audit('create', 'state', '', rec.state, 'Assessment initialized with historical employee snapshot')
        return recs

    def _log_audit(self, action_type, field_name, old_val, new_val, reason=''):
        Audit = self.env['dsl.hrms.assessment.audit.log'].sudo()
        for rec in self:
            Audit.create({
                'company_id': rec.company_id.id,
                'assessment_id': rec.id,
                'model_name': self._name,
                'record_id': rec.id,
                'action_type': action_type,
                'field_name': field_name,
                'old_value': str(old_val or ''),
                'new_value': str(new_val or ''),
                'reason': reason or f'{action_type} on {rec.name}',
                'actor_user_id': self.env.uid,
            })

    def _initialize_runtime_phases_and_reviewers(self):
        """Creates runtime Phase Instances, default Reviewers & Reviewer Inbox Tasks."""
        PhaseInst = self.env['dsl.hrms.assessment.phase.instance'].sudo()
        Reviewer = self.env['dsl.hrms.assessment.reviewer'].sudo()
        Participant = self.env['dsl.hrms.assessment.participant'].sudo()

        for rec in self:
            if rec.phase_instance_ids:
                continue
            Participant.create({
                'assessment_id': rec.id,
                'employee_id': rec.employee_id.id,
                'participant_role': 'subject',
                'is_subject_employee': True,
                'participation_status': 'active',
            })
            if not rec.cycle_id.cycle_phase_ids:
                rec.cycle_id.action_sync_phases_from_policy()

            for cp in rec.cycle_id.cycle_phase_ids.filtered(lambda p: p.enabled):
                pi = PhaseInst.create({
                    'assessment_id': rec.id,
                    'cycle_phase_id': cp.id,
                    'phase_id': cp.phase_id.id,
                    'sequence': cp.sequence,
                    'reviewer_type': cp.reviewer_type,
                    'template_version_id': cp.template_version_id.id if cp.template_version_id else False,
                    'weightage_snapshot': cp.weightage,
                    'required': cp.required,
                    'is_enabled': cp.enabled,
                    'start_date': cp.start_date,
                    'deadline': cp.deadline,
                    'state': 'in_progress',
                })

                # Auto-assign Reviewer based on Reviewer Role
                rev_emp = False
                if cp.reviewer_type == 'self':
                    rev_emp = rec.employee_id
                elif cp.reviewer_type == 'manager':
                    if rec.manager_id and rec.manager_id.id != rec.employee_id.id:
                        rev_emp = rec.manager_id
                elif cp.reviewer_type == 'dept_head':
                    dept_mgr = rec.department_id.manager_id if rec.department_id else False
                    if dept_mgr and dept_mgr.id != rec.employee_id.id:
                        rev_emp = dept_mgr
                elif cp.reviewer_type == 'peer':
                    peers = self.env['hr.employee'].sudo().search([
                        ('company_id', '=', rec.company_id.id),
                        ('id', '!=', rec.employee_id.id),
                    ], limit=2)
                    for peer_emp in peers:
                        Reviewer.create({
                            'assessment_id': rec.id,
                            'phase_instance_id': pi.id,
                            'subject_employee_id': rec.employee_id.id,
                            'reviewer_employee_id': peer_emp.id,
                            'reviewer_user_id': peer_emp.user_id.id if peer_emp.user_id else self.env.uid,
                            'reviewer_role': 'peer',
                            'assignment_method': 'nomination',
                            'is_anonymous': True,
                            'due_date': cp.deadline,
                            'state': 'in_progress',
                        })
                    continue
                elif cp.reviewer_type == 'subordinate':
                    subs = self.env['hr.employee'].sudo().search([
                        ('parent_id', '=', rec.employee_id.id),
                        ('id', '!=', rec.employee_id.id),
                    ], limit=2)
                    for sub_emp in subs:
                        Reviewer.create({
                            'assessment_id': rec.id,
                            'phase_instance_id': pi.id,
                            'subject_employee_id': rec.employee_id.id,
                            'reviewer_employee_id': sub_emp.id,
                            'reviewer_user_id': sub_emp.user_id.id if sub_emp.user_id else self.env.uid,
                            'reviewer_role': 'subordinate',
                            'assignment_method': 'auto',
                            'is_anonymous': True,
                            'due_date': cp.deadline,
                            'state': 'in_progress',
                        })
                    continue
                elif cp.reviewer_type == 'hr':
                    hr_emp = self.env['hr.employee'].sudo().search([
                        ('company_id', '=', rec.company_id.id),
                        ('id', '!=', rec.employee_id.id),
                    ], order='id asc', limit=1)
                    rev_emp = hr_emp or rec.manager_id

                if rev_emp:
                    Reviewer.create({
                        'assessment_id': rec.id,
                        'phase_instance_id': pi.id,
                        'subject_employee_id': rec.employee_id.id,
                        'reviewer_employee_id': rev_emp.id,
                        'reviewer_user_id': rev_emp.user_id.id if rev_emp.user_id else self.env.uid,
                        'reviewer_role': cp.reviewer_type,
                        'assignment_method': 'auto',
                        'is_anonymous': cp.anonymous,
                        'due_date': cp.deadline,
                        'state': 'in_progress',
                    })

    def action_initialize_assessment(self):
        self._initialize_runtime_phases_and_reviewers()
        self.write({'state': 'in_progress', 'started_at': fields.Datetime.now()})

    def action_calculate_final_score(self):
        """
        Part 7.1–7.6 Versioned Scoring Engine:
        1. Validates that all Required Phases have at least 1 submitted response.
        2. Computes Reviewer Group Average for each Phase Instance.
        3. Applies Phase Weightage with Optional Phase Renormalization (or Zero Contribution per Policy).
        4. Creates/updates `dsl.hrms.assessment.result` without overwriting calibrated score history.
        """
        Score = self.env['dsl.hrms.assessment.score'].sudo()
        Result = self.env['dsl.hrms.assessment.result'].sudo()

        for rec in self:
            if rec.locked and rec.state in ('published', 'acknowledged'):
                raise UserError(_('Published Assessment "%s" is locked and cannot be recalculated without an approved Reopen!') % rec.name)

            # Check required phases
            for pi in rec.phase_instance_ids.filtered(lambda p: p.is_enabled and p.required):
                submitted_resps = rec.response_ids.filtered(
                    lambda r: r.phase_instance_id.id == pi.id and r.state in ('submitted', 'locked')
                )
                if not submitted_resps:
                    raise ValidationError(_(
                        'Cannot finalize score: Mandatory Phase "%s" has no submitted response yet!'
                    ) % pi.phase_id.name)

            rec.score_ids.unlink()
            completed_phases = []
            role_scores = {
                'self': 0.0,
                'manager': 0.0,
                'dept_head': 0.0,
                'peer': 0.0,
                'subordinate': 0.0,
                'hr': 0.0,
            }

            for pi in rec.phase_instance_ids.filtered(lambda p: p.is_enabled):
                resps = rec.response_ids.filtered(
                    lambda r: r.phase_instance_id.id == pi.id and r.state in ('submitted', 'locked')
                )
                if not resps:
                    continue
                avg_phase_score = round(sum(resps.mapped('total_score')) / len(resps), 2)
                role_scores[pi.reviewer_type] = avg_phase_score
                completed_phases.append((pi, avg_phase_score))

            if not completed_phases:
                raise ValidationError(_('No submitted responses found to calculate score!'))

            opt_mode = rec.cycle_id.policy_id.optional_phase_mode or 'renormalize'
            total_completed_weight = sum(pi.weightage_snapshot for pi, _ in completed_phases) or 100.0

            final_weighted_sum = 0.0
            for pi, raw_sc in completed_phases:
                if opt_mode == 'renormalize' and total_completed_weight > 0:
                    eff_weight = round((pi.weightage_snapshot / total_completed_weight) * 100.0, 4)
                else:
                    eff_weight = pi.weightage_snapshot
                w_sc = round((raw_sc * eff_weight) / 100.0, 2)
                final_weighted_sum += w_sc
                Score.create({
                    'assessment_id': rec.id,
                    'phase_instance_id': pi.id,
                    'score_type': 'phase_aggregate',
                    'raw_score': raw_sc,
                    'normalized_score': raw_sc,
                    'weightage_snapshot': round(eff_weight, 2),
                    'weighted_score': w_sc,
                    'calculation_version': 'v1.0-PART7',
                })
                pi.write({'state': 'completed', 'completion_percentage': 100.0, 'completed_at': fields.Datetime.now()})

            final_sc = round(min(max(final_weighted_sum, 0.0), 100.0), 2)

            # Incorporate Employee KPI score if assigned for this cycle
            emp_kpis = self.env['dsl.hrms.employee.kpi'].sudo().search([
                ('cycle_id', '=', rec.cycle_id.id),
                ('employee_id', '=', rec.employee_id.id),
            ])
            kpi_sc = round(sum(emp_kpis.mapped('calculated_score')), 2) if emp_kpis else final_sc

            scale = rec.rating_scale_id or rec.cycle_id.rating_scale_id
            lvl = scale.match_rating_level_by_score(final_sc) if scale else False

            rec_action = 'none'
            if final_sc >= 90.0:
                rec_action = 'promotion_increment'
            elif final_sc >= 75.0:
                rec_action = 'increment'
            elif final_sc < 50.0:
                rec_action = 'pip'

            if rec.result_id:
                rec.result_id.write({
                    'self_score': role_scores['self'],
                    'manager_score': role_scores['manager'],
                    'department_head_score': role_scores['dept_head'],
                    'peer_score': role_scores['peer'],
                    'subordinate_score': role_scores['subordinate'],
                    'hr_score': role_scores['hr'],
                    'kpi_score': kpi_sc,
                    'original_final_score': final_sc,
                    'final_score': rec.result_id.calibrated_score or final_sc,
                    'rating_level_id': lvl.id if lvl else False,
                    'recommendation': rec_action,
                    'finalized_at': fields.Datetime.now(),
                    'state': 'calculated',
                })
            else:
                res = Result.create({
                    'assessment_id': rec.id,
                    'employee_id': rec.employee_id.id,
                    'company_id': rec.company_id.id,
                    'calculation_version': 'v1.0-PART7',
                    'self_score': role_scores['self'],
                    'manager_score': role_scores['manager'],
                    'department_head_score': role_scores['dept_head'],
                    'peer_score': role_scores['peer'],
                    'subordinate_score': role_scores['subordinate'],
                    'hr_score': role_scores['hr'],
                    'kpi_score': kpi_sc,
                    'original_final_score': final_sc,
                    'final_score': final_sc,
                    'rating_level_id': lvl.id if lvl else False,
                    'recommendation': rec_action,
                    'finalized_at': fields.Datetime.now(),
                    'state': 'calculated',
                })
                rec.result_id = res.id

            old_st = rec.state
            rec.state = 'under_review'
            rec._log_audit('calculate', 'final_score', old_st, str(final_sc), 'Calculated weighted phase score')

    def action_submit_for_approval(self):
        Approval = self.env['dsl.hrms.assessment.approval'].sudo()
        ApprovalLine = self.env['dsl.hrms.assessment.approval.line'].sudo()
        for rec in self:
            if not rec.result_id:
                rec.action_calculate_final_score()
            if not rec.approval_ids:
                app = Approval.create({
                    'assessment_id': rec.id,
                    'company_id': rec.company_id.id,
                    'approval_type': 'multi_level',
                    'state': 'pending',
                })
                ApprovalLine.create([
                    {
                        'approval_id': app.id,
                        'sequence': 10,
                        'approver_user_id': self.env.uid,
                        'approver_role': 'hr_approval',
                        'state': 'pending',
                    },
                    {
                        'approval_id': app.id,
                        'sequence': 20,
                        'approver_user_id': self.env.uid,
                        'approver_role': 'final_management',
                        'state': 'pending',
                    },
                ])
            rec.state = 'pending_approval'
            rec._log_audit('submit_approval', 'state', 'under_review', 'pending_approval', 'Submitted for multi-level approval')

    def action_approve_assessment(self):
        now = fields.Datetime.now()
        for rec in self:
            for app in rec.approval_ids:
                app.line_ids.write({
                    'approval_action': 'approved',
                    'action_date': now,
                    'state': 'approved',
                })
                app.write({
                    'state': 'approved',
                    'completed_at': now,
                    'final_approver_id': self.env.uid,
                })
            if rec.result_id:
                rec.result_id.state = 'approved'
            rec.state = 'approved'
            rec._log_audit('approve', 'state', 'pending_approval', 'approved', 'Final management approval granted')

    def action_publish_result(self):
        for rec in self:
            if rec.state != 'approved':
                raise ValidationError(_('Assessment "%s" must be Approved before publishing results (Part 9.3)!') % rec.name)
            rec.result_id.state = 'published'
            rec.write({
                'state': 'published',
                'published_at': fields.Datetime.now(),
                'locked': True,
            })
            rec._log_audit('publish', 'state', 'approved', 'published', 'Result published and locked')

    def action_acknowledge_result(self):
        Ack = self.env['dsl.hrms.assessment.acknowledgment'].sudo()
        for rec in self:
            if rec.state != 'published':
                raise UserError(_('Only Published results can be acknowledged!'))
            Ack.create({
                'assessment_id': rec.id,
                'employee_id': rec.employee_id.id,
                'result_id': rec.result_id.id,
                'acknowledged': True,
                'acknowledged_at': fields.Datetime.now(),
                'employee_comment': 'Acknowledged receipt of performance assessment result.',
                'state': 'acknowledged',
            })
            rec.state = 'acknowledged'
            rec._log_audit('acknowledge', 'state', 'published', 'acknowledged', 'Employee acknowledged result')


# =============================================================================
# 2. PARTICIPANT & PHASE INSTANCE (#34, #35)
# =============================================================================
class DslHrmsAssessmentParticipant(models.Model):
    _name = 'dsl.hrms.assessment.participant'
    _description = 'Assessment Participant (#34)'
    _order = 'id asc'

    assessment_id = fields.Many2one('dsl.hrms.assessment', required=True, ondelete='cascade', index=True)
    employee_id = fields.Many2one('hr.employee', string='Participant Employee', required=True)
    participant_role = fields.Selection(
        selection=[('subject', 'Subject Employee'), ('reviewer', 'Reviewer'), ('approver', 'Approver')],
        string='Role',
        default='subject',
        required=True,
    )
    is_subject_employee = fields.Boolean(string='Is Subject Employee', default=False)
    participation_status = fields.Selection(
        selection=[('active', 'Active'), ('removed', 'Removed')],
        string='Status',
        default='active',
    )
    joined_at = fields.Datetime(string='Joined At', default=fields.Datetime.now)
    removed_at = fields.Datetime(string='Removed At')
    removal_reason = fields.Char(string='Removal Reason')


class DslHrmsAssessmentPhaseInstance(models.Model):
    _name = 'dsl.hrms.assessment.phase.instance'
    _description = 'Assessment Runtime Phase Instance (#35)'
    _order = 'sequence asc, id asc'

    assessment_id = fields.Many2one('dsl.hrms.assessment', required=True, ondelete='cascade', index=True)
    cycle_phase_id = fields.Many2one('dsl.hrms.assessment.cycle.phase', string='Cycle Phase')
    phase_id = fields.Many2one('dsl.hrms.assessment.phase', string='Phase', required=True)
    sequence = fields.Integer(string='Order', default=10)
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
    template_version_id = fields.Many2one('dsl.hrms.assessment.template.version', string='Template Snapshot')
    weightage_snapshot = fields.Float(string='Frozen Weightage (%)', default=25.0)
    required = fields.Boolean(string='Mandatory', default=True)
    is_enabled = fields.Boolean(string='Enabled', default=True)
    start_date = fields.Date(string='Start Date')
    deadline = fields.Date(string='Deadline')
    completed_at = fields.Datetime(string='Completed At')
    completion_percentage = fields.Float(string='Completion (%)', default=0.0)
    state = fields.Selection(
        selection=[('pending', 'Pending'), ('in_progress', 'In Progress'), ('completed', 'Completed')],
        string='Status',
        default='in_progress',
    )


# =============================================================================
# 3. REVIEWER ASSIGNMENT & INBOX TASK (#36, #37)
#    Enforces Conflict Rules & Retains Replacement History
# =============================================================================
class DslHrmsAssessmentReviewer(models.Model):
    _name = 'dsl.hrms.assessment.reviewer'
    _description = 'Assessment Reviewer Assignment (#36)'
    _order = 'id asc'

    assessment_id = fields.Many2one('dsl.hrms.assessment', required=True, ondelete='restrict', index=True)
    phase_instance_id = fields.Many2one('dsl.hrms.assessment.phase.instance', string='Phase Instance', required=True, index=True)
    subject_employee_id = fields.Many2one('hr.employee', string='Subject Employee', required=True, index=True)
    reviewer_employee_id = fields.Many2one('hr.employee', string='Reviewer Employee', required=True, index=True)
    reviewer_user_id = fields.Many2one('res.users', string='Reviewer User', index=True)
    display_reviewer_name = fields.Char(
        string='Reviewer Identity',
        compute='_compute_display_reviewer_name',
    )
    reviewer_role = fields.Selection(
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
    assignment_method = fields.Selection(
        selection=[('auto', 'Auto'), ('nomination', 'Nomination'), ('hr', 'HR Assigned')],
        string='Assignment Method',
        default='auto',
    )
    is_anonymous = fields.Boolean(string='Anonymous Feedback (360°)', default=False)
    is_confidential = fields.Boolean(string='Confidential Manager/HR View', default=False)
    is_external_reviewer = fields.Boolean(string='External Reviewer', default=False)
    assigned_by = fields.Many2one('res.users', string='Assigned By', default=lambda self: self.env.user)
    assigned_at = fields.Datetime(string='Assigned At', default=fields.Datetime.now)
    due_date = fields.Date(string='Due Date')
    submitted_at = fields.Datetime(string='Submitted At')
    replacement_reviewer_id = fields.Many2one('dsl.hrms.assessment.reviewer', string='Replaced By Reviewer')
    replacement_reason = fields.Char(string='Replacement Reason')
    state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('in_progress', 'In Progress'),
            ('submitted', 'Submitted'),
            ('overdue', 'Overdue'),
            ('reassigned', 'Reassigned (History Retained)'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='in_progress',
        required=True,
        index=True,
    )

    _sql_constraints = [
        (
            'phase_reviewer_role_uniq',
            'unique(phase_instance_id, reviewer_employee_id, reviewer_role)',
            'Duplicate Reviewer Assignment in the same Phase Instance is blocked (Part 9.1)!',
        ),
    ]

    @api.depends('reviewer_employee_id', 'is_anonymous')
    def _compute_display_reviewer_name(self):
        is_hr_admin = self.env.user.has_group('DSL_HRMS_core.group_dsl_hrms_manager')
        for rec in self:
            if rec.is_anonymous and not is_hr_admin:
                rec.display_reviewer_name = _('Anonymous 360° Reviewer (Identity Protected)')
            else:
                rec.display_reviewer_name = rec.sudo().reviewer_employee_id.name or '—'

    @api.constrains('subject_employee_id', 'reviewer_employee_id', 'reviewer_role')
    def _check_reviewer_conflict(self):
        """Part 9.3 Mandatory Reviewer Conflict Validations."""
        for rec in self:
            if rec.reviewer_role != 'self' and rec.subject_employee_id.id == rec.reviewer_employee_id.id:
                raise ValidationError(_(
                    'Conflict Blocked (Part 9.3): Employee "%s" cannot be assigned as their own "%s" reviewer!'
                ) % (rec.subject_employee_id.name, rec.reviewer_role))

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        Task = self.env['dsl.hrms.assessment.assignment'].sudo()
        for rec in recs:
            Task.create({
                'assessment_id': rec.assessment_id.id,
                'phase_instance_id': rec.phase_instance_id.id,
                'reviewer_id': rec.id,
                'assigned_user_id': rec.reviewer_user_id.id or self.env.uid,
                'task_type': f'{rec.reviewer_role}_review',
                'due_date': rec.due_date,
                'state': 'pending',
            })
        return recs

    def action_replace_reviewer(self, new_employee_id, reason='Reviewer workload / reassignment'):
        """Part 8.2 / 13.C: Retains old reviewer record as 'reassigned' and creates new reviewer."""
        self.ensure_one()
        new_emp = self.env['hr.employee'].sudo().browse(new_employee_id)
        new_rev = self.create({
            'assessment_id': self.assessment_id.id,
            'phase_instance_id': self.phase_instance_id.id,
            'subject_employee_id': self.subject_employee_id.id,
            'reviewer_employee_id': new_emp.id,
            'reviewer_user_id': new_emp.user_id.id if new_emp.user_id else self.env.uid,
            'reviewer_role': self.reviewer_role,
            'assignment_method': 'hr',
            'is_anonymous': self.is_anonymous,
            'due_date': self.due_date,
            'state': 'in_progress',
        })
        self.write({
            'state': 'reassigned',
            'replacement_reviewer_id': new_rev.id,
            'replacement_reason': reason,
        })
        return new_rev


class DslHrmsAssessmentAssignment(models.Model):
    _name = 'dsl.hrms.assessment.assignment'
    _description = 'Reviewer Inbox Review Task (#37)'
    _order = 'due_date asc, id desc'

    assessment_id = fields.Many2one('dsl.hrms.assessment', required=True, ondelete='cascade', index=True)
    phase_instance_id = fields.Many2one('dsl.hrms.assessment.phase.instance', string='Phase Instance', required=True)
    reviewer_id = fields.Many2one('dsl.hrms.assessment.reviewer', string='Reviewer Assignment', required=True)
    assigned_user_id = fields.Many2one('res.users', string='Assigned User', required=True, index=True)
    task_type = fields.Char(string='Task Type', required=True, default='review')
    assigned_at = fields.Datetime(string='Assigned At', default=fields.Datetime.now)
    due_date = fields.Date(string='Due Date', index=True)
    priority = fields.Selection(
        selection=[('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')],
        string='Priority',
        default='normal',
    )
    completed_at = fields.Datetime(string='Completed At')
    reminder_count = fields.Integer(string='Reminders Sent', default=0)
    state = fields.Selection(
        selection=[('pending', 'Pending'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('cancelled', 'Cancelled')],
        string='Status',
        default='pending',
        required=True,
    )


# =============================================================================
# 4. SUBMITTED RESPONSE & QUESTION-WISE RESPONSE LINES (#38, #39)
# =============================================================================
class DslHrmsAssessmentResponse(models.Model):
    _name = 'dsl.hrms.assessment.response'
    _description = 'Submitted Reviewer Assessment Response (#38)'
    _order = 'id desc'

    assessment_id = fields.Many2one('dsl.hrms.assessment', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one('res.company', string='Company', related='assessment_id.company_id', store=True, readonly=True)
    phase_instance_id = fields.Many2one('dsl.hrms.assessment.phase.instance', string='Phase', required=True, index=True)
    reviewer_id = fields.Many2one('dsl.hrms.assessment.reviewer', string='Reviewer', required=True, ondelete='restrict')
    response_version = fields.Integer(string='Response Version', default=1, required=True)
    template_version_id = fields.Many2one('dsl.hrms.assessment.template.version', string='Template Version')
    submitted_by = fields.Many2one('res.users', string='Submitted By', default=lambda self: self.env.user)
    display_submitted_by = fields.Char(
        string='Reviewer Name',
        compute='_compute_display_submitted_by',
    )
    response_date = fields.Datetime(string='Submitted At', default=fields.Datetime.now)
    line_ids = fields.One2many(
        'dsl.hrms.assessment.response.line',
        'response_id',
        string='Question-wise Answers',
    )
    total_score = fields.Float(
        string='Normalized Response Score (/100)',
        compute='_compute_response_scores',
        store=True,
    )
    weighted_score = fields.Float(
        string='Phase Weighted Contribution',
        compute='_compute_response_scores',
        store=True,
    )
    overall_comment = fields.Text(string='Overall Evaluation Summary')
    strengths = fields.Text(string='Key Strengths Demonstrated')
    improvement_areas = fields.Text(string='Areas for Improvement')
    recommendations = fields.Text(string='Training / Career Recommendations')
    is_anonymous = fields.Boolean(string='Anonymous 360° Response', related='reviewer_id.is_anonymous', store=True)
    is_locked = fields.Boolean(string='Response Locked', default=False)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('locked', 'Locked'),
            ('reopened', 'Reopened'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
    )

    _sql_constraints = [
        (
            'reviewer_version_uniq',
            'unique(reviewer_id, response_version)',
            'Duplicate Response for the same Reviewer Assignment & Version is blocked (Part 9.1)!',
        ),
    ]

    @api.depends('reviewer_id', 'is_anonymous')
    def _compute_display_submitted_by(self):
        is_hr_admin = self.env.user.has_group('DSL_HRMS_core.group_dsl_hrms_manager')
        for rec in self:
            if rec.is_anonymous and not is_hr_admin:
                rec.display_submitted_by = _('Anonymous 360° Reviewer')
            else:
                rec.display_submitted_by = rec.sudo().reviewer_id.reviewer_employee_id.name or '—'

    @api.depends('line_ids.normalized_score', 'line_ids.question_weightage_snapshot', 'phase_instance_id.weightage_snapshot')
    def _compute_response_scores(self):
        """Part 7.2 Category / Response Weighted Score Calculation."""
        for rec in self:
            scored_lines = rec.line_ids.filtered(lambda l: l.question_weightage_snapshot > 0)
            tot_w = sum(scored_lines.mapped('question_weightage_snapshot'))
            if tot_w > 0:
                cat_sc = sum(l.normalized_score * l.question_weightage_snapshot for l in scored_lines) / tot_w
            elif rec.line_ids:
                cat_sc = sum(rec.line_ids.mapped('normalized_score')) / len(rec.line_ids)
            else:
                cat_sc = 0.0
            rec.total_score = round(cat_sc, 2)
            ph_w = rec.phase_instance_id.weightage_snapshot if rec.phase_instance_id else 0.0
            rec.weighted_score = round((rec.total_score * ph_w) / 100.0, 2)

    def action_load_template_questions(self):
        Line = self.env['dsl.hrms.assessment.response.line'].sudo()
        for rec in self:
            if rec.line_ids:
                continue
            tpl = rec.assessment_id.template_id
            if not tpl:
                continue
            for sec in tpl.section_ids:
                for q in sec.question_ids:
                    snap = json.dumps({
                        'section': sec.name,
                        'question_code': q.code,
                        'question_text': q.question_text,
                        'question_type': q.question_type,
                        'weightage': q.weightage,
                    })
                    Line.create({
                        'response_id': rec.id,
                        'question_id': q.id,
                        'question_version_data': snap,
                        'answer_type': q.question_type,
                        'rating_value': 4.0 if q.question_type == 'rating' else 0.0,
                        'question_weightage_snapshot': q.weightage if q.scored else 0.0,
                    })

    def action_submit_and_lock(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.assessment_id.cycle_id.state == 'closed':
                raise ValidationError(_('Closed Cycle "%s" cannot accept new responses!') % rec.assessment_id.cycle_id.name)
            if not rec.line_ids:
                rec.action_load_template_questions()
            rec._compute_response_scores()
            rec.write({
                'state': 'locked',
                'is_locked': True,
                'response_date': now,
            })
            rec.reviewer_id.write({
                'state': 'submitted',
                'submitted_at': now,
            })
            tasks = self.env['dsl.hrms.assessment.assignment'].sudo().search([
                ('reviewer_id', '=', rec.reviewer_id.id),
            ])
            tasks.write({'state': 'completed', 'completed_at': now})


class DslHrmsAssessmentResponseLine(models.Model):
    _name = 'dsl.hrms.assessment.response.line'
    _description = 'Question-Wise Assessment Answer & Normalized Score (#39)'
    _order = 'id asc'

    response_id = fields.Many2one('dsl.hrms.assessment.response', required=True, ondelete='cascade', index=True)
    question_id = fields.Many2one('dsl.hrms.assessment.question', string='Question', required=True, ondelete='restrict')
    question_version_data = fields.Text(string='Frozen Question Snapshot JSON', readonly=True)
    answer_type = fields.Selection(
        selection=[
            ('rating', 'Rating Scale'),
            ('percentage', 'Percentage'),
            ('goal_achievement', 'Goal Achievement'),
            ('numeric', 'Numeric'),
            ('yes_no', 'Yes / No'),
            ('single_choice', 'Single Choice'),
            ('multiple_choice', 'Multiple Choice'),
            ('text', 'Text'),
            ('date', 'Date'),
            ('attachment', 'Attachment'),
        ],
        string='Answer Type',
        default='rating',
    )
    text_answer = fields.Text(string='Text Response')
    numeric_answer = fields.Float(string='Numeric / % Answer')
    boolean_answer = fields.Boolean(string='Yes / No Answer')
    date_answer = fields.Date(string='Date Answer')
    selected_option_ids = fields.Many2many(
        'dsl.hrms.assessment.question.option',
        'dsl_resp_line_opt_rel',
        'line_id',
        'option_id',
        string='Selected Options',
    )
    rating_value = fields.Float(string='Rating Point', default=4.0)
    rating_level_id = fields.Many2one('dsl.hrms.assessment.rating.level', string='Rating Band')
    question_weightage_snapshot = fields.Float(string='Question Weight (%)', default=25.0)
    normalized_score = fields.Float(
        string='Normalized Score (/100)',
        compute='_compute_line_score',
        store=True,
    )
    calculated_score = fields.Float(
        string='Weighted Question Score',
        compute='_compute_line_score',
        store=True,
    )
    comment = fields.Char(string='Reviewer Remark')

    @api.depends('answer_type', 'rating_value', 'numeric_answer', 'boolean_answer', 'question_weightage_snapshot', 'question_id.rating_scale_id', 'response_id.assessment_id.rating_scale_id')
    def _compute_line_score(self):
        for ln in self:
            scale = ln.question_id.rating_scale_id or ln.response_id.assessment_id.rating_scale_id
            if ln.answer_type == 'rating' and scale:
                norm = scale.normalize_rating_to_100(ln.rating_value)
            elif ln.answer_type in ('percentage', 'goal_achievement', 'numeric'):
                norm = min(max(float(ln.numeric_answer or 0.0), 0.0), 100.0)
            elif ln.answer_type == 'yes_no':
                norm = 100.0 if ln.boolean_answer else 0.0
            else:
                norm = 100.0
            ln.normalized_score = round(norm, 2)
            ln.calculated_score = round((norm * (ln.question_weightage_snapshot or 0.0)) / 100.0, 2)


# =============================================================================
# 5. COMMENTS, ATTACHMENTS, SCORES, RESULT, HISTORY & ACKNOWLEDGMENT (#40..#45)
# =============================================================================
class DslHrmsAssessmentComment(models.Model):
    _name = 'dsl.hrms.assessment.comment'
    _description = 'Assessment Feedback & Confidential Comment (#40)'
    _order = 'created_at desc, id desc'

    assessment_id = fields.Many2one('dsl.hrms.assessment', required=True, ondelete='cascade', index=True)
    response_id = fields.Many2one('dsl.hrms.assessment.response', string='Linked Response')
    comment_type = fields.Selection(
        selection=[('general', 'General Feedback'), ('coaching', 'Coaching Note'), ('hr_confidential', 'HR Confidential')],
        string='Comment Type',
        default='general',
    )
    author_user_id = fields.Many2one('res.users', string='Author User', default=lambda self: self.env.user)
    author_employee_id = fields.Many2one('hr.employee', string='Author Employee')
    comment = fields.Text(string='Comment', required=True)
    visibility = fields.Selection(
        selection=[('all', 'Subject & Reviewers'), ('managers_hr', 'Manager & HR Only'), ('hr_only', 'HR Only')],
        string='Visibility',
        default='all',
    )
    is_confidential = fields.Boolean(string='Confidential', default=False)
    created_at = fields.Datetime(string='Created At', default=fields.Datetime.now)


class DslHrmsAssessmentScore(models.Model):
    _name = 'dsl.hrms.assessment.score'
    _description = 'Versioned Phase & Reviewer Score Calculation Breakdown (#41)'
    _order = 'id asc'

    assessment_id = fields.Many2one('dsl.hrms.assessment', required=True, ondelete='cascade', index=True)
    phase_instance_id = fields.Many2one('dsl.hrms.assessment.phase.instance', string='Phase Instance')
    reviewer_id = fields.Many2one('dsl.hrms.assessment.reviewer', string='Reviewer')
    response_id = fields.Many2one('dsl.hrms.assessment.response', string='Response')
    score_type = fields.Selection(
        selection=[('reviewer_score', 'Reviewer Score'), ('phase_aggregate', 'Phase Aggregate Score')],
        string='Score Type',
        default='phase_aggregate',
    )
    raw_score = fields.Float(string='Raw Phase Score (/100)')
    normalized_score = fields.Float(string='Normalized Score (/100)')
    weightage_snapshot = fields.Float(string='Effective Weightage (%)')
    weighted_score = fields.Float(string='Weighted Contribution (/100)')
    calculation_version = fields.Char(string='Engine Version', default='v1.0-PART7')
    calculated_at = fields.Datetime(string='Calculated At', default=fields.Datetime.now)


class DslHrmsAssessmentResult(models.Model):
    _name = 'dsl.hrms.assessment.result'
    _description = 'Final Assessment Result & Bell-Curve Rating (#42)'
    _order = 'final_score desc, id desc'

    name = fields.Char(string='Result Ref.', compute='_compute_name', store=True)
    assessment_id = fields.Many2one(
        'dsl.hrms.assessment',
        string='Assessment',
        required=True,
        ondelete='restrict',
        index=True,
    )
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True)
    calculation_version = fields.Char(string='Calculation Formula Version', default='v1.0-PART7')

    self_score = fields.Float(string='Self Review Score (/100)')
    manager_score = fields.Float(string='Manager Score (/100)')
    department_head_score = fields.Float(string='Department Head Score (/100)')
    peer_score = fields.Float(string='360° Peer Average (/100)')
    subordinate_score = fields.Float(string='360° Subordinate Average (/100)')
    hr_score = fields.Float(string='HR Score (/100)')

    kpi_score = fields.Float(string='KPI Achievement Score (/100)')
    kra_score = fields.Float(string='KRA Score (/100)')
    competency_score = fields.Float(string='Competency Score (/100)')

    # Part 16 Rule #6: Original Score is NEVER overwritten by Calibration!
    original_final_score = fields.Float(string='Original Uncalibrated Score (/100)', readonly=True)
    calibrated_score = fields.Float(string='HR Calibrated Score (/100)', readonly=True)
    final_score = fields.Float(string='Final Effective Score (/100)', required=True, default=0.0)
    rating_level_id = fields.Many2one('dsl.hrms.assessment.rating.level', string='Final Rating Level')

    strengths = fields.Text(string='Consolidated Strengths')
    improvement_areas = fields.Text(string='Development Areas')
    recommendation = fields.Selection(
        selection=[
            ('promotion_increment', 'Promotion + Annual Increment (Top Talent)'),
            ('increment', 'Annual Salary Increment'),
            ('confirmation', 'Confirm Permanent Employment'),
            ('training', 'Targeted Skill / Leadership Training'),
            ('pip', 'Place on Performance Improvement Plan (PIP)'),
            ('none', 'Maintain Current Band'),
        ],
        string='HR Outcome Recommendation',
        default='increment',
    )
    history_ids = fields.One2many(
        'dsl.hrms.assessment.result.history',
        'result_id',
        string='Result Calibration & Reopen Version History',
    )
    finalized_at = fields.Datetime(string='Finalized At', default=fields.Datetime.now)
    state = fields.Selection(
        selection=[
            ('calculated', 'Calculated'),
            ('calibrated', 'Calibrated'),
            ('approved', 'Approved'),
            ('published', 'Published & Locked'),
        ],
        string='Result Status',
        default='calculated',
        required=True,
    )

    _sql_constraints = [
        ('assessment_uniq', 'unique(assessment_id)', 'Each Assessment can have only one primary Result record (Part 9.1)!'),
    ]

    @api.depends('assessment_id.name', 'final_score')
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.assessment_id.name or 'RES'} ({rec.final_score:.1f}%)"


class DslHrmsAssessmentResultHistory(models.Model):
    _name = 'dsl.hrms.assessment.result.history'
    _description = 'Assessment Result Calibration & Version History (#43)'
    _order = 'version_number desc, id desc'

    result_id = fields.Many2one('dsl.hrms.assessment.result', required=True, ondelete='restrict', index=True)
    assessment_id = fields.Many2one('dsl.hrms.assessment', related='result_id.assessment_id', store=True, readonly=True)
    version_number = fields.Integer(string='Version No.', required=True, default=1)
    previous_score = fields.Float(string='Previous Score (/100)')
    new_score = fields.Float(string='New Score (/100)')
    previous_rating = fields.Char(string='Previous Rating')
    new_rating = fields.Char(string='New Rating')
    change_reason = fields.Text(string='Calibration / Reopen Reason', required=True)
    changed_by = fields.Many2one('res.users', string='Changed By', default=lambda self: self.env.user)
    changed_at = fields.Datetime(string='Changed At', default=fields.Datetime.now)


class DslHrmsAssessmentAcknowledgment(models.Model):
    _name = 'dsl.hrms.assessment.acknowledgment'
    _description = 'Employee Assessment Result Acknowledgment (#44)'
    _order = 'id desc'

    assessment_id = fields.Many2one('dsl.hrms.assessment', required=True, ondelete='restrict', index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    result_id = fields.Many2one('dsl.hrms.assessment.result', string='Result', required=True)
    acknowledged = fields.Boolean(string='Result Viewed & Acknowledged', default=True)
    acknowledged_at = fields.Datetime(string='Acknowledged At', default=fields.Datetime.now)
    employee_comment = fields.Text(string='Employee Sign-Off Comment')
    disagreement_flag = fields.Boolean(
        string='Acknowledged with Disagreement (Wishes to Appeal)',
        default=False,
    )
    state = fields.Selection(
        selection=[('pending', 'Pending'), ('acknowledged', 'Acknowledged'), ('disputed', 'Disputed / Appealed')],
        string='Status',
        default='acknowledged',
    )


class DslHrmsAssessmentAttachment(models.Model):
    _name = 'dsl.hrms.assessment.attachment'
    _description = 'Assessment Supporting Document & Evidence Attachment (#45)'
    _order = 'id desc'

    assessment_id = fields.Many2one('dsl.hrms.assessment', required=True, ondelete='cascade', index=True)
    response_id = fields.Many2one('dsl.hrms.assessment.response', string='Linked Response')
    employee_id = fields.Many2one('hr.employee', related='assessment_id.employee_id', store=True, readonly=True)
    attachment_name = fields.Char(string='Document Title', required=True)
    file_reference = fields.Binary(string='File Content')
    attachment_type = fields.Selection(
        selection=[('evidence', 'KPI / Goal Evidence'), ('certificate', 'Certificate'), ('other', 'Other')],
        string='Document Type',
        default='evidence',
    )
    uploaded_by = fields.Many2one('res.users', string='Uploaded By', default=lambda self: self.env.user)
    uploaded_at = fields.Datetime(string='Uploaded At', default=fields.Datetime.now)
    visibility = fields.Selection(
        selection=[('all', 'All Participants'), ('hr_only', 'HR Confidential')],
        string='Visibility',
        default='all',
    )
    confidentiality_level = fields.Selection(
        selection=[('standard', 'Standard'), ('restricted', 'Restricted')],
        string='Confidentiality',
        default='standard',
    )
