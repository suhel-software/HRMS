# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


def _default_mss_manager(record=None):
    env = record.env if record is not None else None
    if not env:
        return False
    emp = env['hr.employee'].sudo().search([('user_id', '=', env.uid)], limit=1)
    return emp.id if emp else False


class DslMssPortalService(models.AbstractModel):
    _name = 'dsl.mss.portal.service'
    _description = 'Manager Self-Service (MSS) Team Hub Data Service'

    @api.model
    def _resolve_manager_and_team(self):
        Employee = self.env['hr.employee'].sudo()
        mgr = Employee.search([('user_id', '=', self.env.uid)], limit=1)
        team = Employee.browse()
        if mgr:
            team = Employee.search([
                '|',
                ('parent_id', '=', mgr.id),
                ('department_id.manager_id', '=', mgr.id),
                ('active', '=', True),
            ], order='name asc')
        if not team and (
            self.env.user._is_admin()
            or self.env.user.has_group('DSL_HRMS_core.group_dsl_hrms_officer')
        ):
            team = Employee.search([
                ('company_id', '=', self.env.company.id),
                ('active', '=', True),
            ], order='name asc', limit=50)
        return mgr, team

    @api.model
    def get_mss_portal_data(self):
        mgr, team = self._resolve_manager_and_team()
        today = fields.Date.context_today(self)
        team_ids = team.ids

        # Today's attendance logs for team
        logs = self.env['dsl.attendance.log'].sudo().search([
            ('employee_id', 'in', team_ids),
            ('attendance_date', '=', today),
        ]) if team_ids else self.env['dsl.attendance.log'].browse()
        log_by_emp = {lg.employee_id.id: lg for lg in logs}

        # Approved leaves overlapping today
        leaves_today = self.env['dsl.leave.request'].sudo().search([
            ('employee_id', 'in', team_ids),
            ('state', '=', 'approved'),
            ('date_from', '<=', today),
            ('date_to', '>=', today),
        ]) if team_ids else self.env['dsl.leave.request'].browse()
        on_leave_emp_ids = set(leaves_today.mapped('employee_id').ids)

        present_today = 0
        late_today = 0
        team_roster = []
        for emp in team:
            lg = log_by_emp.get(emp.id)
            if lg and lg.status in ('present', 'late', 'half_day'):
                present_today += 1
                if lg.is_late:
                    late_today += 1
                status_label = 'Late' if lg.is_late else 'Present'
                status_badge = 'warning' if lg.is_late else 'success'
                in_str = fields.Datetime.context_timestamp(self, lg.check_in).strftime('%I:%M %p') if lg.check_in else '—'
                out_str = fields.Datetime.context_timestamp(self, lg.check_out).strftime('%I:%M %p') if lg.check_out else '—'
            elif emp.id in on_leave_emp_ids or (lg and lg.status == 'on_leave'):
                status_label = 'On Leave'
                status_badge = 'info'
                in_str = '—'
                out_str = '—'
            else:
                status_label = 'Not Checked-In'
                status_badge = 'secondary'
                in_str = '—'
                out_str = '—'

            team_roster.append({
                'id': emp.id,
                'name': emp.name,
                'code': emp.employee_code or 'EMP',
                'job': emp.job_id.name or 'Staff',
                'department': emp.department_id.name or 'General',
                'branch': emp.branch_id.name if emp.branch_id else emp.company_id.name,
                'status_label': status_label,
                'status_badge': status_badge,
                'check_in': in_str,
                'check_out': out_str,
            })

        # Pending approvals for team
        pending_leaves_recs = self.env['dsl.leave.request'].sudo().search([
            ('employee_id', 'in', team_ids),
            ('state', 'in', ['submitted', 'level1_approved', 'level2_approved']),
        ], order='date_from asc, id desc', limit=20) if team_ids else self.env['dsl.leave.request'].browse()

        pending_leaves = [{
            'id': lv.id,
            'name': lv.name,
            'employee': lv.employee_id.name,
            'leave_type': lv.leave_type_id.name,
            'dates': f"{lv.date_from} → {lv.date_to}",
            'days': lv.number_of_days,
            'stage': lv.current_approval_stage or lv.state,
        } for lv in pending_leaves_recs]

        pending_ot_count = self.env['dsl.overtime.request'].sudo().search_count([
            ('employee_id', 'in', team_ids),
            ('state', '=', 'submitted'),
        ]) if team_ids else 0

        pending_reg_count = self.env['dsl.attendance.regularization'].sudo().search_count([
            ('employee_id', 'in', team_ids),
            ('state', '=', 'submitted'),
        ]) if team_ids else 0

        # Active Corporate & Management HR Announcements
        announcements = []
        if 'dsl.hr.announcement' in self.env:
            announcements = self.env['dsl.hr.announcement'].sudo().get_active_announcements_for_user(
                audience_mode='manager', emp=mgr, limit=6
            )

        return {
            'manager_name': mgr.name if mgr else self.env.user.name,
            'company_name': self.env.company.name,
            'today_str': str(today),
            'kpis': {
                'team_count': len(team),
                'present_today': present_today,
                'late_today': late_today,
                'on_leave_today': len(on_leave_emp_ids),
                'pending_leaves_count': len(pending_leaves_recs),
                'pending_ot_count': pending_ot_count,
                'pending_reg_count': pending_reg_count,
                'announcements_count': len(announcements),
            },
            'announcements': announcements,
            'pending_leaves': pending_leaves,
            'team_roster': team_roster,
        }

    @api.model
    def action_mss_quick_approve_leave(self, leave_id):
        lv = self.env['dsl.leave.request'].browse(int(leave_id))
        if not lv.exists():
            raise UserError(_('Leave request not found!'))
        lv.action_approve()
        return {'id': lv.id, 'new_state': lv.state}


class DslMssRecommendation(models.Model):
    _name = 'dsl.mss.recommendation'
    _description = 'Manager Career Recommendation (Promotion / Increment / Confirmation / Transfer)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'effective_date desc, id desc'

    name = fields.Char(
        string='Proposal Ref.',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Team Member',
        required=True,
        index=True,
        tracking=True,
    )
    recommending_manager_id = fields.Many2one(
        'hr.employee',
        string='Recommending Manager',
        default=_default_mss_manager,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Current Branch / Plant',
        domain="[('company_id', '=', company_id)]",
    )
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', store=True, readonly=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    proposal_type = fields.Selection(
        selection=[
            ('probation_confirmation', 'Probation Confirmation (চাকরি স্থায়ীকরণ)'),
            ('annual_increment', 'Salary Increment Proposal (বেতন বৃদ্ধি)'),
            ('promotion', 'Promotion & Grade Elevation (পদোন্নতি)'),
            ('branch_transfer', 'Branch / Department Transfer (বদলি)'),
        ],
        string='Recommendation Type',
        default='annual_increment',
        required=True,
        tracking=True,
    )
    effective_date = fields.Date(
        string='Proposed Effective Date',
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )

    current_job_id = fields.Many2one('hr.job', string='Current Designation')
    proposed_job_id = fields.Many2one('hr.job', string='Proposed Designation')
    proposed_branch_id = fields.Many2one(
        'dsl.branch',
        string='Proposed Branch / Plant',
        domain="[('company_id', '=', company_id)]",
    )
    current_gross = fields.Monetary(string='Current Monthly Gross (৳)', currency_field='currency_id')
    proposed_gross = fields.Monetary(string='Proposed Monthly Gross (৳)', currency_field='currency_id', tracking=True)
    increment_pct = fields.Float(string='Proposed Increment (%)', compute='_compute_increment_pct', store=True)

    kpi_rating = fields.Selection(
        selection=[
            ('5_outstanding', '5 — Outstanding (অসাধারণ)'),
            ('4_exceeds', '4 — Exceeds Expectations (প্রত্যাশার চেয়ে ভালো)'),
            ('3_meets', '3 — Meets Expectations (সন্তোষজনক)'),
            ('2_needs_improvement', '2 — Needs Improvement'),
        ],
        string='Supervisor Appraisal Rating',
        default='4_exceeds',
        required=True,
    )
    justification = fields.Text(string='Manager Justification & Achievements', required=True)
    hr_decision_notes = fields.Text(string='HR & Management Board Remarks')

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted to HR'),
            ('hr_reviewed', 'HR Reviewed'),
            ('approved', 'Board Approved & Applied'),
            ('rejected', 'Declined'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    @api.depends('current_gross', 'proposed_gross')
    def _compute_increment_pct(self):
        for rec in self:
            if rec.current_gross and rec.current_gross > 0 and rec.proposed_gross:
                rec.increment_pct = round(((rec.proposed_gross - rec.current_gross) / rec.current_gross) * 100.0, 2)
            else:
                rec.increment_pct = 0.0

    @api.constrains('proposed_gross')
    def _check_non_negative_gross(self):
        for rec in self:
            if rec.proposed_gross < 0:
                raise ValidationError(_('Proposed Monthly Gross cannot be negative!'))

    @api.onchange('employee_id')
    def _onchange_employee_snapshot(self):
        if self.employee_id:
            emp = self.employee_id.sudo()
            self.company_id = emp.company_id.id
            self.branch_id = emp.branch_id.id if emp.branch_id else False
            self.current_job_id = emp.job_id.id if emp.job_id else False
            self.proposed_job_id = emp.job_id.id if emp.job_id else False
            if emp.parent_id and not self.recommending_manager_id:
                self.recommending_manager_id = emp.parent_id.id
            pkg = self.env['dsl.employee.compensation'].sudo().search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'active'),
            ], order='effective_from desc, id desc', limit=1)
            if pkg:
                gross = pkg.total_gross_package or pkg.gross_salary
                self.current_gross = gross
                if not self.proposed_gross:
                    self.proposed_gross = round(gross * 1.10, 2)

    @api.model_create_multi
    def create(self, vals_list):
        Employee = self.env['hr.employee'].sudo()
        Comp = self.env['dsl.employee.compensation'].sudo()
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.mss.recommendation') or _('New')
            if vals.get('employee_id'):
                emp = Employee.browse(vals['employee_id'])
                vals.setdefault('company_id', emp.company_id.id)
                if emp.branch_id and not vals.get('branch_id'):
                    vals['branch_id'] = emp.branch_id.id
                if emp.job_id and not vals.get('current_job_id'):
                    vals['current_job_id'] = emp.job_id.id
                if not vals.get('current_gross'):
                    pkg = Comp.search([('employee_id', '=', emp.id), ('state', '=', 'active')], limit=1)
                    if pkg:
                        vals['current_gross'] = pkg.total_gross_package or pkg.gross_salary
        return super().create(vals_list)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_hr_review(self):
        self.write({'state': 'hr_reviewed'})

    def action_approve_and_apply(self):
        for rec in self:
            emp = rec.employee_id.sudo()
            emp_updates = {}
            if rec.proposal_type == 'probation_confirmation':
                emp_updates['employment_status'] = 'confirmed'
                emp_updates['employment_category'] = 'permanent'
                emp_updates['confirmation_date'] = rec.effective_date
            if rec.proposed_job_id and rec.proposed_job_id != emp.job_id:
                emp_updates['job_id'] = rec.proposed_job_id.id
            if rec.proposed_branch_id and rec.proposed_branch_id != emp.branch_id:
                emp_updates['branch_id'] = rec.proposed_branch_id.id
            if emp_updates:
                emp.write(emp_updates)
            rec.state = 'approved'

    def action_reject(self):
        self.write({'state': 'rejected'})

