# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class DslLeaveApprovalChain(models.Model):
    _name = 'dsl.leave.approval.chain'
    _description = 'Multi-Level Leave Approval Chain Policy'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    name = fields.Char(string='Approval Chain Name', required=True, tracking=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        help='Leave empty to apply across all Group companies.',
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Specific Branch / Plant',
        domain="[('company_id', '=', company_id)]",
    )
    leave_type_ids = fields.Many2many(
        'dsl.leave.type',
        string='Applicable Leave Policies',
        help='Leave empty to apply to all leave policies.',
    )
    min_days = fields.Float(string='Min Leave Days', default=0.0)
    max_days = fields.Float(
        string='Max Leave Days (0 = Unlimited)',
        default=0.0,
    )
    step_ids = fields.One2many(
        'dsl.leave.approval.chain.step',
        'chain_id',
        string='Sequential Approval Steps',
    )
    notes = fields.Text(string='Workflow Guidelines')

    @api.model
    def _resolve_chain_for_request(self, leave_req):
        """Finds the best-matching approval chain for the leave application."""
        chains = self.sudo().search([('active', '=', True)], order='sequence, id')
        req_days = leave_req.number_of_days or 0.0
        for ch in chains:
            if ch.company_id and ch.company_id.id != leave_req.company_id.id:
                continue
            if ch.branch_id and (not leave_req.branch_id or ch.branch_id.id != leave_req.branch_id.id):
                continue
            if ch.leave_type_ids and leave_req.leave_type_id.id not in ch.leave_type_ids.ids:
                continue
            if ch.min_days and req_days < ch.min_days:
                continue
            if ch.max_days > 0 and req_days > ch.max_days:
                continue
            return ch
        return self.browse()


class DslLeaveApprovalChainStep(models.Model):
    _name = 'dsl.leave.approval.chain.step'
    _description = 'Multi-Level Leave Approval Chain Step'
    _order = 'level asc, id asc'

    chain_id = fields.Many2one(
        'dsl.leave.approval.chain',
        string='Approval Chain',
        required=True,
        ondelete='cascade',
    )
    level = fields.Integer(string='Approval Level', required=True, default=1)
    name = fields.Char(string='Stage Title', required=True)
    approver_role = fields.Selection(
        selection=[
            ('line_manager', 'Line Manager / Supervisor'),
            ('dept_head', 'Department Head (HOD)'),
            ('branch_head', 'Branch / Plant Head'),
            ('hr_officer', 'HR Officer (Group)'),
            ('hr_manager', 'HR Manager / Director (Group)'),
            ('specific_user', 'Specific Named User'),
        ],
        string='Approver Role',
        required=True,
        default='line_manager',
    )
    specific_user_id = fields.Many2one('res.users', string='Specific Approver User')
    min_days_trigger = fields.Float(
        string='Trigger Only If Days >',
        default=0.0,
        help='If > 0, this approval level is included only when Net Leave Days exceeds this value.',
    )
    auto_skip_if_missing_or_same = fields.Boolean(
        string='Auto-Skip If Unassigned / Duplicate',
        default=True,
        help='Automatically skips intermediate manager steps if employee has no manager assigned or if identical to prior approver.',
    )

    def _resolve_target_user(self, employee):
        emp = employee.sudo()
        if self.approver_role == 'line_manager':
            return emp.parent_id.user_id if (emp.parent_id and emp.parent_id.user_id) else self.env['res.users']
        if self.approver_role == 'dept_head':
            dept_mgr = emp.department_id.manager_id if emp.department_id else False
            return dept_mgr.user_id if (dept_mgr and dept_mgr.user_id) else self.env['res.users']
        if self.approver_role == 'branch_head':
            br = emp.branch_id
            br_mgr = getattr(br, 'manager_id', False) if br else False
            if br_mgr and hasattr(br_mgr, 'user_id') and br_mgr.user_id:
                return br_mgr.user_id
            if br_mgr and br_mgr._name == 'res.users':
                return br_mgr
            return self.env['res.users']
        if self.approver_role == 'specific_user':
            return self.specific_user_id
        return self.env['res.users']


class DslLeaveRequestApprovalStep(models.Model):
    _name = 'dsl.leave.request.approval.step'
    _description = 'Leave Application Multi-Level Approval Step Log'
    _order = 'level asc, id asc'

    leave_request_id = fields.Many2one(
        'dsl.leave.request',
        string='Leave Application',
        required=True,
        ondelete='cascade',
        index=True,
    )
    level = fields.Integer(string='Level', required=True)
    step_name = fields.Char(string='Stage', required=True)
    approver_role = fields.Selection(
        selection=[
            ('line_manager', 'Line Manager / Supervisor'),
            ('dept_head', 'Department Head (HOD)'),
            ('branch_head', 'Branch / Plant Head'),
            ('hr_officer', 'HR Officer'),
            ('hr_manager', 'HR Manager / Director'),
            ('specific_user', 'Specific User'),
        ],
        string='Role',
        required=True,
    )
    assigned_user_id = fields.Many2one('res.users', string='Assigned Approver')
    state = fields.Selection(
        selection=[
            ('pending', 'Pending Action'),
            ('waiting', 'Waiting Prior Level'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('skipped', 'Auto-Skipped'),
        ],
        string='Step Status',
        default='waiting',
        required=True,
    )
    action_by_id = fields.Many2one('res.users', string='Actioned By', readonly=True)
    action_date = fields.Datetime(string='Timestamp', readonly=True)
    remarks = fields.Char(string='Approver Note')

    def _can_user_approve_step(self, user):
        self.ensure_one()
        if user._is_admin() or user.has_group('DSL_HRMS_core.group_dsl_hrms_manager'):
            return True
        if self.assigned_user_id and self.assigned_user_id.id == user.id:
            return True
        if self.approver_role == 'hr_officer' and user.has_group('DSL_HRMS_core.group_dsl_hrms_officer'):
            return True
        return False


class DslLeaveRequestApprovalExt(models.Model):
    _inherit = 'dsl.leave.request'

    state = fields.Selection(
        selection_add=[
            ('level1_approved', 'L1 Approved (Pending Next)'),
            ('level2_approved', 'L2 Approved (Pending Final)'),
            ('approved',),
        ],
        ondelete={
            'level1_approved': 'set default',
            'level2_approved': 'set default',
        },
    )
    approval_chain_id = fields.Many2one(
        'dsl.leave.approval.chain',
        string='Applied Approval Chain',
        readonly=True,
    )
    approval_step_ids = fields.One2many(
        'dsl.leave.request.approval.step',
        'leave_request_id',
        string='Multi-Level Approval Steps',
    )
    next_approver_id = fields.Many2one(
        'res.users',
        string='Current Assigned Approver',
        readonly=True,
        index=True,
        tracking=True,
    )
    current_approval_stage = fields.Char(
        string='Current Approval Stage',
        compute='_compute_approval_permissions',
    )
    can_approve_current_step = fields.Boolean(
        string='Can Current User Approve',
        compute='_compute_approval_permissions',
    )

    @api.depends('state', 'approval_step_ids.state', 'approval_step_ids.assigned_user_id', 'approval_step_ids.approver_role')
    def _compute_approval_permissions(self):
        curr_user = self.env.user
        for rec in self:
            pending_step = rec.approval_step_ids.filtered(lambda s: s.state == 'pending')[:1]
            if pending_step:
                rec.current_approval_stage = f"Level {pending_step.level}: {pending_step.step_name}"
                rec.can_approve_current_step = pending_step._can_user_approve_step(curr_user)
            elif rec.state == 'submitted' and not rec.approval_step_ids:
                rec.current_approval_stage = _('Single-Step HR Approval')
                rec.can_approve_current_step = (
                    curr_user._is_admin()
                    or curr_user.has_group('DSL_HRMS_core.group_dsl_hrms_officer')
                )
            elif rec.state == 'approved':
                rec.current_approval_stage = _('Completed (Final Approved)')
                rec.can_approve_current_step = False
            else:
                rec.current_approval_stage = False
                rec.can_approve_current_step = False

    def _build_approval_steps(self):
        Chain = self.env['dsl.leave.approval.chain'].sudo()
        StepLog = self.env['dsl.leave.request.approval.step'].sudo()
        for rec in self:
            rec.approval_step_ids.sudo().unlink()
            chain = Chain._resolve_chain_for_request(rec)
            rec.approval_chain_id = chain.id if chain else False
            if not chain or not chain.step_ids:
                rec.next_approver_id = False
                continue

            seen_user_ids = set()
            created_steps = self.env['dsl.leave.request.approval.step']
            for cfg in chain.step_ids:
                if cfg.min_days_trigger > 0 and rec.number_of_days <= cfg.min_days_trigger:
                    continue

                target_user = cfg._resolve_target_user(rec.employee_id)
                is_group_role = cfg.approver_role in ('hr_officer', 'hr_manager')

                step_state = 'waiting'
                note = False
                if not is_group_role:
                    if not target_user and cfg.auto_skip_if_missing_or_same:
                        step_state = 'skipped'
                        note = _('Auto-skipped (role not assigned on employee profile)')
                    elif target_user and target_user.id in seen_user_ids and cfg.auto_skip_if_missing_or_same:
                        step_state = 'skipped'
                        note = _('Auto-skipped (same approver as previous level)')
                    elif target_user:
                        seen_user_ids.add(target_user.id)

                created_steps |= StepLog.create({
                    'leave_request_id': rec.id,
                    'level': cfg.level,
                    'step_name': cfg.name,
                    'approver_role': cfg.approver_role,
                    'assigned_user_id': target_user.id if target_user else False,
                    'state': step_state,
                    'remarks': note,
                })

            waiting_steps = created_steps.filtered(lambda s: s.state == 'waiting')
            if waiting_steps:
                first_step = waiting_steps[0]
                first_step.state = 'pending'
                rec.next_approver_id = first_step.assigned_user_id.id if first_step.assigned_user_id else False
            else:
                # Ensure at least one HR validation step if all manager steps were skipped
                fallback = StepLog.create({
                    'leave_request_id': rec.id,
                    'level': 1,
                    'step_name': _('HR Officer Final Validation'),
                    'approver_role': 'hr_officer',
                    'state': 'pending',
                })
                rec.next_approver_id = fallback.assigned_user_id.id if fallback.assigned_user_id else False

    def action_submit(self):
        super().action_submit()
        self._build_approval_steps()

    def action_approve(self):
        for rec in self:
            pending_step = rec.approval_step_ids.filtered(lambda s: s.state == 'pending')[:1]
            if not pending_step:
                # Fallback if no approval chain configured
                super(DslLeaveRequestApprovalExt, rec).action_approve()
                continue

            if not pending_step._can_user_approve_step(self.env.user):
                raise AccessError(_(
                    'You are not authorized to approve %s! Assigned role/user: %s.'
                ) % (pending_step.step_name, pending_step.assigned_user_id.name or pending_step.approver_role))

            pending_step.sudo().write({
                'state': 'approved',
                'action_by_id': self.env.user.id,
                'action_date': fields.Datetime.now(),
                'remarks': pending_step.remarks or _('Approved'),
            })

            next_waiting = rec.approval_step_ids.filtered(lambda s: s.state == 'waiting')[:1]
            if next_waiting:
                next_waiting.sudo().write({'state': 'pending'})
                new_state = 'level1_approved' if pending_step.level == 1 else 'level2_approved'
                rec.write({
                    'state': new_state,
                    'next_approver_id': next_waiting.assigned_user_id.id if next_waiting.assigned_user_id else False,
                })
                rec.message_post(
                    body=_(
                        'Step Approved — Level %s (%s) approved by %s. Routed to Level %s (%s).'
                    ) % (
                        pending_step.level,
                        pending_step.step_name,
                        self.env.user.name,
                        next_waiting.level,
                        next_waiting.step_name,
                    ),
                    subtype_xmlid='mail.mt_note',
                    email_from=self.env.user.email_formatted or f'"{self.env.user.name}" <noreply@dsl-hrms.local>',
                )
            else:
                rec.next_approver_id = False
                rec._finalize_leave_approval()

    def action_hr_executive_override(self):
        if not (self.env.user._is_admin() or self.env.user.has_group('DSL_HRMS_core.group_dsl_hrms_manager')):
            raise UserError(_('Only HR Managers can execute Executive Override Approval!'))
        now_dt = fields.Datetime.now()
        for rec in self:
            open_steps = rec.approval_step_ids.filtered(lambda s: s.state in ('pending', 'waiting'))
            if open_steps:
                open_steps.sudo().write({
                    'state': 'approved',
                    'action_by_id': self.env.user.id,
                    'action_date': now_dt,
                    'remarks': _('Approved via HR Executive Override'),
                })
            rec.next_approver_id = False
            rec._finalize_leave_approval()

    def action_reject(self):
        now_dt = fields.Datetime.now()
        for rec in self:
            pending_step = rec.approval_step_ids.filtered(lambda s: s.state == 'pending')[:1]
            if pending_step:
                pending_step.sudo().write({
                    'state': 'rejected',
                    'action_by_id': self.env.user.id,
                    'action_date': now_dt,
                    'remarks': rec.rejection_reason or _('Rejected'),
                })
            rec.next_approver_id = False
        return super().action_reject()

    def action_reset_draft(self):
        for rec in self:
            rec.approval_step_ids.sudo().unlink()
            rec.next_approver_id = False
        return super().action_reset_draft()
