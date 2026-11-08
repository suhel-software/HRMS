# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =============================================================================
# 1. APPROVAL WORKFLOW & APPROVAL LINES (#46, #47)
# =============================================================================
class DslHrmsAssessmentApproval(models.Model):
    _name = 'dsl.hrms.assessment.approval'
    _description = 'Assessment Multi-Level Approval Workflow (#46)'
    _order = 'id desc'

    assessment_id = fields.Many2one('dsl.hrms.assessment', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True)
    approval_type = fields.Selection(
        selection=[
            ('single_level', 'Single-Level HR Approval'),
            ('multi_level', 'Multi-Level (HR + Management Approval)'),
            ('committee', 'Calibration & Executive Committee Approval'),
        ],
        string='Approval Workflow Type',
        default='multi_level',
        required=True,
    )
    current_step = fields.Integer(string='Current Step', default=10)
    final_approver_id = fields.Many2one('res.users', string='Final Approver')
    approved_by_hr = fields.Boolean(string='Approved by HR', default=False)
    approved_by_management = fields.Boolean(string='Approved by Management', default=False)
    line_ids = fields.One2many(
        'dsl.hrms.assessment.approval.line',
        'approval_id',
        string='Approval Steps',
    )
    submitted_at = fields.Datetime(string='Submitted At', default=fields.Datetime.now)
    completed_at = fields.Datetime(string='Completed At')
    state = fields.Selection(
        selection=[
            ('pending', 'Pending Approval'),
            ('in_review', 'In Review'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected / Returned'),
        ],
        string='Status',
        default='pending',
        required=True,
    )


class DslHrmsAssessmentApprovalLine(models.Model):
    _name = 'dsl.hrms.assessment.approval.line'
    _description = 'Assessment Approval Step Line (#47)'
    _order = 'sequence asc, id asc'

    approval_id = fields.Many2one('dsl.hrms.assessment.approval', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(string='Step Sequence', default=10, required=True)
    approver_user_id = fields.Many2one('res.users', string='Approver User', required=True)
    approver_employee_id = fields.Many2one('hr.employee', string='Approver Employee')
    approver_role = fields.Selection(
        selection=[
            ('dept_head', 'Department Head'),
            ('hr_approval', 'Company / Group HR Approval'),
            ('final_management', 'Final Management / MD Approval'),
        ],
        string='Approval Role',
        default='hr_approval',
        required=True,
    )
    approval_action = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('returned', 'Returned for Revision'),
        ],
        string='Decision',
        default='pending',
    )
    comment = fields.Text(string='Approver Comment')
    action_date = fields.Datetime(string='Action Date')
    state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='pending',
        required=True,
    )


# =============================================================================
# 2. HR CALIBRATION SESSION & CALIBRATION LINES (#48, #49)
#    Preserves original_final_score & logs dsl.hrms.assessment.result.history
# =============================================================================
class DslHrmsAssessmentCalibration(models.Model):
    _name = 'dsl.hrms.assessment.calibration'
    _description = 'HR Bell-Curve & Score Calibration Session (#48)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'session_date desc, id desc'

    name = fields.Char(string='Calibration Session Title', required=True, tracking=True)
    code = fields.Char(string='Session Code', required=True, copy=False, default='New', index=True)
    cycle_id = fields.Many2one('dsl.hrms.assessment.cycle', string='Assessment Cycle', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one('res.company', string='Company', related='cycle_id.company_id', store=True, readonly=True)
    branch_id = fields.Many2one('dsl.branch', string='Branch Filter')
    department_id = fields.Many2one('hr.department', string='Department Filter')
    calibrator_user_id = fields.Many2one('res.users', string='Lead Calibrator', default=lambda self: self.env.user, tracking=True)
    session_date = fields.Date(string='Calibration Date', default=lambda self: fields.Date.context_today(self), required=True)
    calibration_method = fields.Selection(
        selection=[
            ('bell_curve', 'Bell-Curve Distribution Alignment'),
            ('panel_moderation', 'Cross-Department Panel Moderation'),
            ('direct_adjustment', 'Direct HR / Executive Moderation'),
        ],
        string='Calibration Method',
        default='bell_curve',
        required=True,
    )
    notes = fields.Text(string='Calibration Committee Minutes & Rationale')
    line_ids = fields.One2many(
        'dsl.hrms.assessment.calibration.line',
        'calibration_id',
        string='Employee Score Calibrations',
    )
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approved_at = fields.Datetime(string='Approved At', readonly=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('in_review', 'Panel In Review'),
            ('applied', 'Calibrated & Applied'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('dsl.hrms.assessment.calibration') or 'CAL-2026-001'
        return super().create(vals_list)

    def action_apply_calibration(self):
        """Part 8.4 / Part 16 Rule #6:
        Updates result_id.calibrated_score & result_id.final_score WITHOUT overwriting
        result_id.original_final_score, and logs dsl.hrms.assessment.result.history!
        """
        History = self.env['dsl.hrms.assessment.result.history'].sudo()
        now = fields.Datetime.now()
        for session in self:
            if not session.line_ids:
                raise UserError(_('Please add at least one Calibration Line before applying calibration.'))
            for ln in session.line_ids:
                if not ln.justification:
                    raise ValidationError(_('Calibration Justification is mandatory for employee "%s" (Part 8.4)!') % ln.employee_id.name)
                ass = ln.assessment_id
                res = ass.result_id
                if not res:
                    ass.action_calculate_final_score()
                    res = ass.result_id
                prev_score = res.final_score
                prev_rating = res.rating_level_id.rating_label if res.rating_level_id else ''
                scale = ass.rating_scale_id
                new_lvl = scale.match_rating_level_by_score(ln.calibrated_score) if scale else ln.calibrated_rating_id

                # Preserve original_final_score intact!
                if not res.original_final_score:
                    res.original_final_score = prev_score

                res.write({
                    'calibrated_score': ln.calibrated_score,
                    'final_score': ln.calibrated_score,
                    'rating_level_id': new_lvl.id if new_lvl else False,
                    'state': 'calibrated',
                })
                ln.write({
                    'original_score': res.original_final_score,
                    'original_rating_id': res.rating_level_id.id if not ln.original_rating_id else ln.original_rating_id.id,
                    'calibrated_rating_id': new_lvl.id if new_lvl else False,
                    'changed_by': self.env.uid,
                    'changed_at': now,
                })
                ver_no = len(res.history_ids) + 1
                History.create({
                    'result_id': res.id,
                    'version_number': ver_no,
                    'previous_score': prev_score,
                    'new_score': ln.calibrated_score,
                    'previous_rating': prev_rating,
                    'new_rating': new_lvl.rating_label if new_lvl else '',
                    'change_reason': f"[{session.code}] {ln.justification}",
                    'changed_by': self.env.uid,
                    'changed_at': now,
                })
                ass.state = 'calibration'
                ass._log_audit('calibrate', 'final_score', str(prev_score), str(ln.calibrated_score), ln.justification)

            session.write({
                'state': 'applied',
                'approved_by': self.env.uid,
                'approved_at': now,
            })


class DslHrmsAssessmentCalibrationLine(models.Model):
    _name = 'dsl.hrms.assessment.calibration.line'
    _description = 'Employee Score Calibration Line (#49)'
    _order = 'id asc'

    calibration_id = fields.Many2one('dsl.hrms.assessment.calibration', required=True, ondelete='cascade', index=True)
    assessment_id = fields.Many2one('dsl.hrms.assessment', string='Assessment', required=True, ondelete='restrict')
    employee_id = fields.Many2one('hr.employee', string='Employee', related='assessment_id.employee_id', store=True, readonly=True)
    original_score = fields.Float(string='Original Score (/100)', readonly=True)
    calibrated_score = fields.Float(string='Calibrated Score (/100)', required=True)
    adjustment_delta = fields.Float(
        string='Delta (+/-)',
        compute='_compute_delta',
        store=True,
    )
    original_rating_id = fields.Many2one('dsl.hrms.assessment.rating.level', string='Original Rating')
    calibrated_rating_id = fields.Many2one('dsl.hrms.assessment.rating.level', string='Calibrated Rating')
    justification = fields.Text(string='Calibration Justification (Mandatory)', required=True)
    changed_by = fields.Many2one('res.users', string='Calibrated By', default=lambda self: self.env.user)
    changed_at = fields.Datetime(string='Calibrated At', default=fields.Datetime.now)

    @api.depends('original_score', 'calibrated_score')
    def _compute_delta(self):
        for rec in self:
            rec.adjustment_delta = round((rec.calibrated_score or 0.0) - (rec.original_score or 0.0), 2)

    @api.onchange('assessment_id')
    def _onchange_assessment_id(self):
        for rec in self:
            if rec.assessment_id and rec.assessment_id.result_id:
                res = rec.assessment_id.result_id
                rec.original_score = res.original_final_score or res.final_score
                rec.original_rating_id = res.rating_level_id.id
                if not rec.calibrated_score:
                    rec.calibrated_score = rec.original_score


# =============================================================================
# 3. EMPLOYEE APPEAL, REOPEN REQUEST & IMMUTABLE AUDIT LOG (#50, #51, #52)
# =============================================================================
class DslHrmsAssessmentAppeal(models.Model):
    _name = 'dsl.hrms.assessment.appeal'
    _description = 'Employee Assessment Result Appeal / Dispute (#50)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'submitted_at desc, id desc'

    name = fields.Char(string='Appeal Reference', required=True, copy=False, default='New', index=True)
    assessment_id = fields.Many2one('dsl.hrms.assessment', string='Assessment', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one('res.company', string='Company', related='assessment_id.company_id', store=True, readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Appellant Employee', required=True, index=True)
    result_id = fields.Many2one('dsl.hrms.assessment.result', string='Contested Result', related='assessment_id.result_id', store=True, readonly=True)
    appeal_reason = fields.Selection(
        selection=[
            ('kpi_calculation', 'KPI / Target Achievement Calculation Error'),
            ('unfair_bias', 'Perceived Reviewer Bias / Missing Context'),
            ('missing_evidence', 'New Project / Achievement Evidence Omitted'),
            ('other', 'Other Substantive Grounds'),
        ],
        string='Primary Appeal Ground',
        default='kpi_calculation',
        required=True,
    )
    detailed_explanation = fields.Text(string='Detailed Appeal Statement', required=True)
    requested_outcome = fields.Char(string='Requested Score / Rating Review')
    supporting_attachment_ids = fields.Many2many(
        'dsl.hrms.assessment.attachment',
        'dsl_appeal_att_rel',
        'appeal_id',
        'attachment_id',
        string='Supporting Evidence Documents',
    )
    submitted_at = fields.Datetime(string='Submitted At', default=fields.Datetime.now)
    assigned_reviewer_id = fields.Many2one('res.users', string='Appeal Adjudicator (HR / Committee)', default=lambda self: self.env.user)
    resolution_notes = fields.Text(string='Adjudication Findings & Resolution')
    revised_score = fields.Float(string='Revised Score (/100, if upheld)')
    revised_rating_id = fields.Many2one('dsl.hrms.assessment.rating.level', string='Revised Rating Level')
    resolved_at = fields.Datetime(string='Resolved At')
    state = fields.Selection(
        selection=[
            ('submitted', 'Submitted'),
            ('under_review', 'Under Appeal Investigation'),
            ('upheld', 'Appeal Upheld (Score Revised)'),
            ('rejected', 'Appeal Dismissed (Original Stands)'),
        ],
        string='Appeal Status',
        default='submitted',
        required=True,
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('dsl.hrms.assessment.appeal') or 'APL-2026-001'
        recs = super().create(vals_list)
        for rec in recs:
            if rec.assessment_id:
                rec.assessment_id.state = 'appealed'
                rec.assessment_id._log_audit('appeal', 'state', 'published', 'appealed', rec.detailed_explanation)
        return recs

    def action_resolve_appeal(self, uphold=True):
        History = self.env['dsl.hrms.assessment.result.history'].sudo()
        now = fields.Datetime.now()
        for rec in self:
            ass = rec.assessment_id
            res = ass.result_id
            if uphold and res and rec.revised_score > 0:
                prev_sc = res.final_score
                prev_rt = res.rating_level_id.rating_label if res.rating_level_id else ''
                scale = ass.rating_scale_id
                new_lvl = scale.match_rating_level_by_score(rec.revised_score) if scale else rec.revised_rating_id
                res.write({
                    'calibrated_score': rec.revised_score,
                    'final_score': rec.revised_score,
                    'rating_level_id': new_lvl.id if new_lvl else False,
                })
                History.create({
                    'result_id': res.id,
                    'version_number': len(res.history_ids) + 1,
                    'previous_score': prev_sc,
                    'new_score': rec.revised_score,
                    'previous_rating': prev_rt,
                    'new_rating': new_lvl.rating_label if new_lvl else '',
                    'change_reason': f"Appeal Upheld [{rec.name}]: {rec.resolution_notes or rec.detailed_explanation}",
                    'changed_by': self.env.uid,
                    'changed_at': now,
                })
                rec.write({
                    'state': 'upheld',
                    'revised_rating_id': new_lvl.id if new_lvl else False,
                    'resolved_at': now,
                })
            else:
                rec.write({
                    'state': 'rejected',
                    'resolved_at': now,
                })
            ass.state = 'published'
            ass._log_audit('appeal_resolved', 'state', 'appealed', 'closed', rec.resolution_notes or 'Appeal resolved')


class DslHrmsAssessmentReopenRequest(models.Model):
    _name = 'dsl.hrms.assessment.reopen.request'
    _description = 'Assessment Controlled Reopen Request (#51)'
    _order = 'requested_at desc, id desc'

    assessment_id = fields.Many2one('dsl.hrms.assessment', string='Assessment', required=True, ondelete='restrict', index=True)
    phase_instance_id = fields.Many2one('dsl.hrms.assessment.phase.instance', string='Target Phase')
    reviewer_id = fields.Many2one('dsl.hrms.assessment.reviewer', string='Target Reviewer Assignment')
    requested_by = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user, required=True)
    request_reason = fields.Text(string='Reason for Reopening', required=True)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    requested_at = fields.Datetime(string='Requested At', default=fields.Datetime.now)
    approved_at = fields.Datetime(string='Approved At', readonly=True)
    reopen_until = fields.Date(string='Extended Submission Deadline')
    state = fields.Selection(
        selection=[
            ('pending', 'Pending HR Approval'),
            ('approved', 'Approved & Reopened'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='pending',
        required=True,
    )

    def action_approve_reopen(self):
        """Part 8.3 Controlled Reopen:
        Unlocks assessment & creates a new versioned response without deleting prior responses!
        """
        Response = self.env['dsl.hrms.assessment.response'].sudo()
        now = fields.Datetime.now()
        for rec in self:
            ass = rec.assessment_id
            ass.write({'locked': False, 'state': 'in_progress'})
            if rec.reviewer_id:
                rec.reviewer_id.state = 'in_progress'
                old_resps = Response.search([('reviewer_id', '=', rec.reviewer_id.id)], order='response_version desc')
                next_ver = (old_resps[0].response_version + 1) if old_resps else 2
                if old_resps:
                    old_resps[0].state = 'reopened'
                new_resp = Response.create({
                    'assessment_id': ass.id,
                    'phase_instance_id': rec.reviewer_id.phase_instance_id.id,
                    'reviewer_id': rec.reviewer_id.id,
                    'response_version': next_ver,
                    'template_version_id': ass.template_version_id.id,
                    'submitted_by': rec.reviewer_id.reviewer_user_id.id or self.env.uid,
                    'state': 'draft',
                })
                new_resp.action_load_template_questions()
            rec.write({
                'state': 'approved',
                'approved_by': self.env.uid,
                'approved_at': now,
            })
            ass._log_audit('reopen', 'locked', 'True', 'False', rec.request_reason)


class DslHrmsAssessmentAuditLog(models.Model):
    _name = 'dsl.hrms.assessment.audit.log'
    _description = 'Immutable Assessment Security & Score Audit Log (#52)'
    _order = 'action_timestamp desc, id desc'

    company_id = fields.Many2one('res.company', string='Company', required=True, index=True)
    assessment_id = fields.Many2one('dsl.hrms.assessment', string='Assessment', ondelete='restrict', index=True)
    model_name = fields.Char(string='Model Name', required=True, index=True)
    record_id = fields.Integer(string='Record ID', required=True, index=True)
    action_type = fields.Char(string='Action Type', required=True, index=True)
    field_name = fields.Char(string='Changed Field')
    old_value = fields.Text(string='Old Value')
    new_value = fields.Text(string='New Value')
    reason = fields.Text(string='Reason / Context')
    actor_user_id = fields.Many2one('res.users', string='Actor User', default=lambda self: self.env.user, required=True)
    actor_ip = fields.Char(string='Actor IP', default='127.0.0.1')
    action_timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now, required=True, index=True)

    def write(self, vals):
        raise UserError(_('Immutable Audit Log (Part 16 Rule #7): Assessment Audit Logs cannot be modified!'))

    def unlink(self):
        raise UserError(_('Immutable Audit Log (Part 16 Rule #7): Assessment Audit Logs cannot be deleted!'))


# =============================================================================
# 4. POST-ASSESSMENT OUTCOMES: PIP, IDP, TRAINING, PROMOTION, INCREMENT, REWARD
#    Models #53 to #59
# =============================================================================
class DslHrmsEmployeePip(models.Model):
    _name = 'dsl.hrms.employee.pip'
    _description = 'Employee Performance Improvement Plan - PIP (#53)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, id desc'

    name = fields.Char(string='PIP Reference', required=True, copy=False, default='New', index=True)
    assessment_id = fields.Many2one('dsl.hrms.assessment', string='Source Assessment', ondelete='restrict', index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one('res.company', string='Company', related='employee_id.company_id', store=True, readonly=True)
    manager_id = fields.Many2one('hr.employee', string='Supervising Manager')
    hr_owner_id = fields.Many2one('res.users', string='HR Advisor', default=lambda self: self.env.user)
    start_date = fields.Date(string='PIP Start Date', required=True, default=lambda self: fields.Date.context_today(self))
    end_date = fields.Date(string='PIP Target End Date', required=True)
    reason = fields.Text(string='Performance Gap Summary', required=True)
    expected_improvement = fields.Text(string='Required Improvement Benchmarks', required=True)
    support_plan = fields.Text(string='Coaching & Resource Support Plan')
    review_frequency = fields.Selection(
        selection=[('weekly', 'Weekly'), ('biweekly', 'Bi-Weekly'), ('monthly', 'Monthly')],
        string='Check-In Frequency',
        default='biweekly',
    )
    action_ids = fields.One2many('dsl.hrms.employee.pip.action', 'pip_id', string='PIP Action Milestones')
    final_outcome = fields.Selection(
        selection=[
            ('pending', 'In Progress'),
            ('successful', 'Successfully Completed (Retained)'),
            ('extended', 'PIP Extended'),
            ('reassigned', 'Role Reassignment / Demotion'),
            ('terminated', 'Unsuccessful (Separation Initiated)'),
        ],
        string='Final PIP Outcome',
        default='pending',
        tracking=True,
    )
    closed_at = fields.Datetime(string='Closed At')
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active Coaching'),
            ('review', 'Final Evaluation'),
            ('closed', 'Closed'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('dsl.hrms.employee.pip') or 'PIP-2026-001'
        return super().create(vals_list)


class DslHrmsEmployeePipAction(models.Model):
    _name = 'dsl.hrms.employee.pip.action'
    _description = 'PIP Action Milestone Item (#54)'
    _order = 'target_date asc, id asc'

    pip_id = fields.Many2one('dsl.hrms.employee.pip', required=True, ondelete='cascade', index=True)
    action_title = fields.Char(string='Milestone Action Title', required=True)
    target_metric = fields.Char(string='Success Metric / Deliverable', required=True)
    target_date = fields.Date(string='Target Completion Date', required=True)
    progress_notes = fields.Text(string='Employee Progress Notes')
    manager_feedback = fields.Text(string='Manager Evaluation Feedback')
    completion_percentage = fields.Float(string='Completion (%)', default=0.0)
    status = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('on_track', 'On Track'),
            ('at_risk', 'At Risk'),
            ('completed', 'Completed'),
        ],
        string='Status',
        default='pending',
        required=True,
    )


class DslHrmsEmployeeDevelopmentPlan(models.Model):
    _name = 'dsl.hrms.employee.development.plan'
    _description = 'Individual Career Development Plan - IDP (#55)'
    _order = 'target_date asc, id desc'

    assessment_id = fields.Many2one('dsl.hrms.assessment', string='Linked Assessment', index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True)
    development_area = fields.Char(string='Competency / Career Growth Area', required=True)
    action_plan = fields.Text(string='Concrete Development Actions', required=True)
    mentor_id = fields.Many2one('hr.employee', string='Assigned Mentor / Coach')
    target_date = fields.Date(string='Target Date')
    progress_percentage = fields.Float(string='Progress (%)', default=0.0)
    status = fields.Selection(
        selection=[('planned', 'Planned'), ('in_progress', 'In Progress'), ('completed', 'Completed')],
        string='Status',
        default='planned',
        required=True,
    )


class DslHrmsEmployeeTrainingNeed(models.Model):
    _name = 'dsl.hrms.employee.training.need'
    _description = 'Assessment-Driven Employee Training Need - TNA (#56)'
    _order = 'priority desc, id desc'

    assessment_id = fields.Many2one('dsl.hrms.assessment', string='Source Assessment', index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True)
    competency_id = fields.Many2one('dsl.hrms.competency', string='Target Competency')
    training_topic = fields.Char(string='Recommended Training Program', required=True)
    priority = fields.Selection(
        selection=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High / Critical')],
        string='Priority',
        default='medium',
        required=True,
    )
    recommended_by = fields.Many2one('res.users', string='Recommended By', default=lambda self: self.env.user)
    target_quarter = fields.Char(string='Target Quarter (e.g. Q2-2026)', default='Q1-2027')
    approval_status = fields.Selection(
        selection=[('proposed', 'Proposed'), ('approved', 'Approved for L&D'), ('enrolled', 'Enrolled'), ('completed', 'Completed')],
        string='L&D Status',
        default='proposed',
        required=True,
    )


class DslHrmsEmployeePromotionRecommendation(models.Model):
    _name = 'dsl.hrms.employee.promotion.recommendation'
    _description = 'Assessment-Linked Promotion Recommendation (#57)'
    _order = 'effective_date desc, id desc'

    assessment_id = fields.Many2one('dsl.hrms.assessment', string='Source Assessment', required=True, index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True)
    current_designation_id = fields.Many2one('hr.job', string='Current Designation')
    proposed_designation_id = fields.Many2one('hr.job', string='Proposed Designation', required=True)
    current_grade_id = fields.Many2one('dsl.hr.grade', string='Current Pay Grade')
    proposed_grade_id = fields.Many2one('dsl.hr.grade', string='Proposed Pay Grade')
    recommended_by = fields.Many2one('res.users', string='Recommended By', default=lambda self: self.env.user)
    justification = fields.Text(string='Promotion Justification & Readiness', required=True)
    effective_date = fields.Date(string='Proposed Effective Date', required=True, default=lambda self: fields.Date.context_today(self))
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft Recommendation'),
            ('submitted', 'Submitted to HR'),
            ('approved', 'Approved by Management'),
            ('executed', 'Applied to Employee Job Profile'),
            ('rejected', 'Deferred / Rejected'),
        ],
        string='Status',
        default='draft',
        required=True,
    )


class DslHrmsEmployeeIncrementRecommendation(models.Model):
    _name = 'dsl.hrms.employee.increment.recommendation'
    _description = 'Assessment-Linked Salary Increment Recommendation (#58)'
    _order = 'effective_date desc, id desc'

    assessment_id = fields.Many2one('dsl.hrms.assessment', string='Source Assessment', required=True, index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', related='employee_id.company_id', store=True, readonly=True)
    # Part 6.2 Field-Level Security: Salary fields restricted to HR Officer / Payroll / Manager
    current_salary = fields.Float(
        string='Current Gross Salary (BDT)',
        groups='DSL_HRMS_core.group_dsl_hrms_officer',
    )
    proposed_increment_percentage = fields.Float(
        string='Proposed Increment (%)',
        required=True,
        default=10.0,
        groups='DSL_HRMS_core.group_dsl_hrms_officer',
    )
    proposed_increment_amount = fields.Float(
        string='Increment Amount (BDT)',
        compute='_compute_proposed_salary',
        store=True,
        groups='DSL_HRMS_core.group_dsl_hrms_officer',
    )
    proposed_salary = fields.Float(
        string='Proposed New Gross Salary (BDT)',
        compute='_compute_proposed_salary',
        store=True,
        groups='DSL_HRMS_core.group_dsl_hrms_officer',
    )
    effective_date = fields.Date(string='Effective Date', required=True, default=lambda self: fields.Date.context_today(self))
    recommended_by = fields.Many2one('res.users', string='Recommended By', default=lambda self: self.env.user)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    payroll_sync_status = fields.Selection(
        selection=[('not_synced', 'Not Synced'), ('synced', 'Synced to Salary Structure')],
        string='Payroll Sync Status',
        default='not_synced',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('synced', 'Synced to Payroll'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='draft',
        required=True,
    )

    @api.depends('current_salary', 'proposed_increment_percentage')
    def _compute_proposed_salary(self):
        for rec in self.sudo():
            inc = round((rec.current_salary or 0.0) * (rec.proposed_increment_percentage or 0.0) / 100.0, 2)
            rec.proposed_increment_amount = inc
            rec.proposed_salary = round((rec.current_salary or 0.0) + inc, 2)


class DslHrmsEmployeeRewardRecommendation(models.Model):
    _name = 'dsl.hrms.employee.reward.recommendation'
    _description = 'Assessment Performance Bonus & Spot Reward Recommendation (#59)'
    _order = 'id desc'

    assessment_id = fields.Many2one('dsl.hrms.assessment', string='Source Assessment', required=True, index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True)
    reward_type = fields.Selection(
        selection=[
            ('performance_bonus', 'One-Time Performance Bonus'),
            ('star_award', 'Chairman / MD Excellence Award'),
            ('spot_recognition', 'Certificate of Appreciation'),
        ],
        string='Reward Category',
        default='performance_bonus',
        required=True,
    )
    reward_title = fields.Char(string='Award / Bonus Title', required=True)
    amount = fields.Float(
        string='Bonus Amount (BDT)',
        groups='DSL_HRMS_core.group_dsl_hrms_officer',
    )
    reason = fields.Text(string='Citation / Justification', required=True)
    recommended_by = fields.Many2one('res.users', string='Recommended By', default=lambda self: self.env.user)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    state = fields.Selection(
        selection=[('draft', 'Draft'), ('approved', 'Approved'), ('disbursed', 'Disbursed / Awarded')],
        string='Status',
        default='draft',
        required=True,
    )


# =============================================================================
# 5. NOTIFICATIONS, REMINDER LOGS, SEQUENCES & INTEGRATION LOGS (#60..#63)
# =============================================================================
class DslHrmsAssessmentNotification(models.Model):
    _name = 'dsl.hrms.assessment.notification'
    _description = 'Assessment Event Notification Queue (#60)'
    _order = 'sent_at desc, id desc'

    assessment_id = fields.Many2one('dsl.hrms.assessment', string='Assessment', ondelete='cascade', index=True)
    recipient_user_id = fields.Many2one('res.users', string='Recipient User', required=True, index=True)
    notification_type = fields.Selection(
        selection=[
            ('cycle_launch', 'Assessment Cycle Launched'),
            ('review_assigned', 'Reviewer Task Assigned'),
            ('deadline_reminder', 'Upcoming Deadline Reminder'),
            ('overdue_escalation', 'Overdue Review Escalation'),
            ('result_published', 'Assessment Result Published'),
            ('appeal_update', 'Appeal / Calibration Update'),
        ],
        string='Notification Event',
        default='review_assigned',
        required=True,
    )
    channel = fields.Selection(
        selection=[('in_app', 'In-App Inbox'), ('email', 'Email'), ('both', 'In-App + Email')],
        string='Channel',
        default='both',
    )
    subject = fields.Char(string='Subject', required=True)
    message_body = fields.Text(string='Message Content', required=True)
    sent_at = fields.Datetime(string='Sent At', default=fields.Datetime.now)
    read_at = fields.Datetime(string='Read At')
    status = fields.Selection(
        selection=[('queued', 'Queued'), ('sent', 'Sent'), ('read', 'Read'), ('failed', 'Failed')],
        string='Delivery Status',
        default='sent',
        required=True,
    )


class DslHrmsAssessmentReminderLog(models.Model):
    _name = 'dsl.hrms.assessment.reminder.log'
    _description = 'Automated Assessment Deadline Reminder Log (#61)'
    _order = 'sent_at desc, id desc'

    cycle_id = fields.Many2one('dsl.hrms.assessment.cycle', string='Cycle', index=True)
    assessment_id = fields.Many2one('dsl.hrms.assessment', string='Assessment', index=True)
    reviewer_id = fields.Many2one('dsl.hrms.assessment.reviewer', string='Reviewer Assignment')
    reminder_stage = fields.Selection(
        selection=[
            ('3_days_before', '3 Days Before Deadline'),
            ('due_today', 'Due Today Alert'),
            ('overdue_escalation', 'Overdue Manager/HR Escalation'),
        ],
        string='Reminder Stage',
        default='3_days_before',
        required=True,
    )
    sent_to_user_id = fields.Many2one('res.users', string='Sent To User', required=True)
    sent_at = fields.Datetime(string='Sent At', default=fields.Datetime.now)
    delivery_status = fields.Selection(
        selection=[('delivered', 'Delivered'), ('failed', 'Failed')],
        string='Status',
        default='delivered',
    )


class DslHrmsAssessmentSequence(models.Model):
    _name = 'dsl.hrms.assessment.sequence'
    _description = 'Multi-Company Assessment Document Numbering Sequence (#62)'
    _order = 'company_id asc, sequence_type asc'

    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    sequence_type = fields.Selection(
        selection=[
            ('policy', 'Assessment Policy (POL)'),
            ('cycle', 'Assessment Cycle (CYC)'),
            ('assessment', 'Employee Assessment (ASS)'),
            ('calibration', 'Calibration Session (CAL)'),
            ('appeal', 'Assessment Appeal (APL)'),
            ('pip', 'Performance Improvement Plan (PIP)'),
        ],
        string='Document Type',
        required=True,
        default='assessment',
    )
    prefix = fields.Char(string='Prefix', required=True, default='ASS-')
    padding = fields.Integer(string='Digit Padding', default=4)
    current_number = fields.Integer(string='Current Number', default=1)
    fiscal_year = fields.Char(string='Fiscal / Calendar Year', default='2026')
    active = fields.Boolean(string='Active', default=True)


class DslHrmsAssessmentIntegrationLog(models.Model):
    _name = 'dsl.hrms.assessment.integration.log'
    _description = 'Cross-Module Assessment Integration Sync Log (#63)'
    _order = 'synced_at desc, id desc'

    assessment_id = fields.Many2one('dsl.hrms.assessment', string='Assessment', required=True, ondelete='cascade', index=True)
    target_module = fields.Selection(
        selection=[
            ('employee_profile', 'DSL_HRMS_employee (Employee Dossier)'),
            ('salary_structure', 'DSL_HRMS_salary_structure (Increment Sync)'),
            ('training', 'DSL_HRMS_employee (Training History)'),
            ('promotion', 'DSL_HRMS_employee (Promotion History)'),
        ],
        string='Target HRMS Module',
        required=True,
        default='employee_profile',
    )
    target_model = fields.Char(string='Target Model', required=True)
    target_record_id = fields.Integer(string='Target Record ID')
    sync_action = fields.Char(string='Sync Action', required=True)
    payload_snapshot = fields.Text(string='Synced Payload JSON')
    sync_status = fields.Selection(
        selection=[('success', 'Success'), ('failed', 'Failed')],
        string='Sync Status',
        default='success',
        required=True,
    )
    error_message = fields.Text(string='Error Details')
    synced_by = fields.Many2one('res.users', string='Synced By', default=lambda self: self.env.user)
    synced_at = fields.Datetime(string='Synced At', default=fields.Datetime.now)


# =============================================================================
# 6. EXTEND HR.EMPLOYEE WITH UNIFIED ASSESSMENT ENGINE LINKS
# =============================================================================
class HrEmployeeAssessmentExtension(models.Model):
    _inherit = 'hr.employee'

    dsl_assessment_ids = fields.One2many(
        'dsl.hrms.assessment',
        'employee_id',
        string='Enterprise Assessments (Standard / Advanced / 360° / Probation)',
    )
    dsl_assessment_count = fields.Integer(
        string='Assessments Count',
        compute='_compute_dsl_assessment_counts',
    )
    dsl_emp_goal_ids = fields.One2many(
        'dsl.hrms.employee.goal',
        'employee_id',
        string='Assigned Performance Goals & OKRs',
    )
    dsl_emp_kpi_ids = fields.One2many(
        'dsl.hrms.employee.kpi',
        'employee_id',
        string='Assigned Employee KPIs',
    )
    dsl_pip_ids = fields.One2many(
        'dsl.hrms.employee.pip',
        'employee_id',
        string='Performance Improvement Plans (PIP)',
    )
    dsl_increment_rec_ids = fields.One2many(
        'dsl.hrms.employee.increment.recommendation',
        'employee_id',
        string='Increment Recommendations',
    )

    def _compute_dsl_assessment_counts(self):
        Assessment = self.env['dsl.hrms.assessment'].sudo()
        for emp in self:
            emp.dsl_assessment_count = Assessment.search_count([('employee_id', '=', emp.id)])
