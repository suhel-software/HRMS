# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


def _default_ess_employee(record=None):
    env = record.env if record is not None else None
    if not env:
        return False
    emp = env['hr.employee'].sudo().search([('user_id', '=', env.uid)], limit=1)
    if not emp:
        emp = env['hr.employee'].sudo().search([('company_id', '=', env.company.id)], limit=1)
    return emp.id if emp else False


class DslEssPortalService(models.AbstractModel):
    _name = 'dsl.ess.portal.service'
    _description = 'Employee Self-Service (ESS) Live Workspace Data Service'

    @api.model
    def _resolve_active_employee(self):
        Employee = self.env['hr.employee'].sudo()
        emp = Employee.search([('user_id', '=', self.env.uid)], limit=1)
        if not emp:
            emp = Employee.search([('company_id', '=', self.env.company.id)], order='id asc', limit=1)
        return emp

    @api.model
    def get_ess_portal_data(self):
        emp = self._resolve_active_employee()
        today = fields.Date.context_today(self)
        if not emp:
            return {'has_employee': False}

        # Helper for initials
        words = [w for w in (emp.name or 'E').replace('(', ' ').replace(')', ' ').split() if w.isalpha()]
        initials = ''.join(w[0].upper() for w in words[:2]) or 'EM'

        # 1. Today's Attendance & Monthly Attendance Logs
        att_log = self.env['dsl.attendance.log'].sudo().search([
            ('employee_id', '=', emp.id),
            ('attendance_date', '=', today),
        ], limit=1)
        month_start = today.replace(day=1)
        month_logs = self.env['dsl.attendance.log'].sudo().search([
            ('employee_id', '=', emp.id),
            ('attendance_date', '>=', month_start),
            ('attendance_date', '<=', today),
        ], order='attendance_date desc, id desc')
        present_month = len(month_logs.filtered(lambda l: l.status in ('present', 'late', 'half_day')))
        absent_month = len(month_logs.filtered(lambda l: l.status == 'absent'))
        late_month = len(month_logs.filtered(lambda l: l.is_late))

        recent_att_logs = []
        all_emp_logs = self.env['dsl.attendance.log'].sudo().search([
            ('employee_id', '=', emp.id),
        ], order='attendance_date desc, id desc', limit=7)
        for lg in all_emp_logs:
            cin = fields.Datetime.context_timestamp(self, lg.check_in).strftime('%I:%M %p') if lg.check_in else '—'
            cout = fields.Datetime.context_timestamp(self, lg.check_out).strftime('%I:%M %p') if lg.check_out else '—'
            hrs = f"{getattr(lg, 'worked_hours', 0.0):.1f}h" if getattr(lg, 'worked_hours', 0.0) else '—'
            recent_att_logs.append({
                'id': lg.id,
                'date': lg.attendance_date.strftime('%d %b %Y') if lg.attendance_date else '',
                'check_in': cin,
                'check_out': cout,
                'hours': hrs,
                'status': (lg.status or 'present').replace('_', ' ').title(),
                'is_late': bool(lg.is_late),
            })

        # Overtime hours this month
        ot_hours_month = 0.0
        if 'dsl.overtime.request' in self.env:
            ot_recs = self.env['dsl.overtime.request'].sudo().search([
                ('employee_id', '=', emp.id),
                ('state', 'in', ('approved', 'paid')),
            ])
            ot_hours_month = round(sum(getattr(r, 'overtime_hours', 0.0) or getattr(r, 'approved_hours', 0.0) for r in ot_recs), 1)

        # Shift label
        shift_label = 'General Shift (09:00 AM - 06:00 PM)'
        if att_log and getattr(att_log, 'schedule_label', False):
            shift_label = att_log.schedule_label

        # 2. Leave Balances (Current Year) & Recent Leave Requests
        allocs = self.env['dsl.leave.allocation'].sudo().search([
            ('employee_id', '=', emp.id),
            ('leave_year', '=', str(today.year)),
            ('state', '=', 'active'),
        ])
        leave_cards = []
        total_leave_remaining = 0.0
        for al in allocs:
            ent = al.total_entitled_days or 0.0
            tkn = al.taken_days or 0.0
            rem = al.remaining_days or 0.0
            total_leave_remaining += rem
            pct = min(int(round((tkn / ent) * 100)), 100) if ent > 0 else 0
            leave_cards.append({
                'id': al.id,
                'code': al.leave_type_id.code,
                'name': al.leave_type_id.name,
                'entitled': ent,
                'taken': tkn,
                'remaining': rem,
                'usage_pct': pct,
            })

        recent_leaves = []
        lv_reqs = self.env['dsl.leave.request'].sudo().search([
            ('employee_id', '=', emp.id),
        ], order='date_from desc, id desc', limit=5)
        for lr in lv_reqs:
            recent_leaves.append({
                'id': lr.id,
                'name': lr.name,
                'leave_type': lr.leave_type_id.name,
                'code': lr.leave_type_id.code,
                'date_from': lr.date_from.strftime('%d %b %Y') if lr.date_from else '',
                'date_to': lr.date_to.strftime('%d %b %Y') if lr.date_to else '',
                'days': getattr(lr, 'number_of_days', 1.0),
                'state': lr.state,
                'state_label': (lr.state or 'draft').replace('_', ' ').title(),
            })

        upcoming_holidays = []
        if 'dsl.holiday.line' in self.env:
            Hol = self.env['dsl.holiday.line'].sudo()
            dt_fld = 'holiday_date' if 'holiday_date' in Hol._fields else ('date_from' if 'date_from' in Hol._fields else 'date')
            hols = Hol.search([(dt_fld, '>=', today)], order=f'{dt_fld} asc', limit=4) if dt_fld in Hol._fields else Hol.search([], limit=4)
            if not hols:
                hols = Hol.search([], limit=4)
            for h in hols:
                h_dt = getattr(h, dt_fld, False)
                upcoming_holidays.append({
                    'id': h.id,
                    'name': h.name,
                    'date': h_dt.strftime('%d %b %Y') if h_dt else '',
                    'type': (getattr(h, 'holiday_type', 'National') or 'Holiday').replace('_', ' ').title(),
                })

        # 3. Active Compensation Package & Payslips
        comp_pkg = None
        if 'dsl.employee.compensation' in self.env:
            pkg = self.env['dsl.employee.compensation'].sudo().search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'active'),
            ], order='effective_from desc, id desc', limit=1)
            if pkg:
                gross_val = getattr(pkg, 'total_gross_package', 0.0) or getattr(pkg, 'gross_salary', 0.0)
                comp_pkg = {
                    'id': pkg.id,
                    'name': pkg.name,
                    'structure': pkg.structure_id.name if pkg.structure_id else 'Standard BD Structure',
                    'basic': f"{getattr(pkg, 'basic_salary', 0.0):,.2f}",
                    'house_rent': f"{getattr(pkg, 'house_rent', 0.0):,.2f}",
                    'medical': f"{getattr(pkg, 'medical_allowance', 0.0):,.2f}",
                    'conveyance': f"{getattr(pkg, 'conveyance_allowance', 0.0):,.2f}",
                    'gross': f"{gross_val:,.2f}",
                    'effective_from': pkg.effective_from.strftime('%d %b %Y') if pkg.effective_from else 'Active',
                }

        slips = self.env['dsl.payslip'].sudo().search([
            ('employee_id', '=', emp.id),
            ('state', '!=', 'cancelled'),
        ], order='date_from desc, id desc', limit=6)
        slip = slips[0] if slips else None
        latest_payslip = {
            'id': slip.id,
            'name': slip.name,
            'month': slip.payroll_month_label,
            'gross': f"{slip.gross_payable:,.2f}",
            'deductions': f"{slip.total_deductions:,.2f}",
            'net': f"{slip.net_payable:,.2f}",
            'state': (slip.state or 'paid').title(),
        } if slip else None

        recent_payslips = [{
            'id': s.id,
            'name': s.name,
            'month': s.payroll_month_label,
            'gross': f"{s.gross_payable:,.2f}",
            'deductions': f"{s.total_deductions:,.2f}",
            'net': f"{s.net_payable:,.2f}",
            'state': (s.state or 'paid').title(),
        } for s in slips]

        # 4. Active Loan, PF & Gratuity Balance
        all_loans = self.env['dsl.employee.loan'].sudo().search([
            ('employee_id', '=', emp.id),
        ], order='request_date desc, id desc', limit=5)
        active_loans = all_loans.filtered(lambda l: l.state == 'disbursed')
        loan_balance = round(sum(active_loans.mapped('balance_amount')), 2)
        loans_list = [{
            'id': ln.id,
            'name': ln.name,
            'type': (ln.loan_type or 'loan').replace('_', ' ').title(),
            'principal': f"{ln.principal_amount:,.2f}",
            'balance': f"{ln.balance_amount:,.2f}",
            'emi': f"{getattr(ln, 'monthly_installment', 0.0):,.2f}",
            'state': (ln.state or 'draft').replace('_', ' ').title(),
        } for ln in all_loans]

        pf_balance = 0.0
        pf_summary = {
            'has_pf': False,
            'emp_contrib': '0.00',
            'co_contrib': '0.00',
            'profit': '0.00',
            'total': '0.00',
            'vested_pct': 100,
        }
        if 'dsl.pf.account' in self.env:
            pf_acc = self.env['dsl.pf.account'].sudo().search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'active'),
            ], limit=1)
            if pf_acc:
                pf_balance = pf_acc.total_fund_balance
                pf_summary = {
                    'has_pf': True,
                    'name': pf_acc.name,
                    'emp_contrib': f"{pf_acc.employee_contribution_total:,.2f}",
                    'co_contrib': f"{pf_acc.employer_contribution_total:,.2f}",
                    'profit': f"{pf_acc.profit_credited_total:,.2f}",
                    'total': f"{pf_acc.total_fund_balance:,.2f}",
                    'vested_pct': int(pf_acc.vested_employer_pct or 100),
                }

        # Tax Summary
        tax_summary = {'has_tax': False, 'fy': 'FY 2026-2027', 'monthly_tds': '0.00', 'annual_tax': '0.00'}
        if 'dsl.emp.tax.assessment' in self.env:
            tx = self.env['dsl.emp.tax.assessment'].sudo().search([
                ('employee_id', '=', emp.id),
            ], order='id desc', limit=1)
            if tx:
                tax_summary = {
                    'has_tax': True,
                    'fy': tx.fiscal_policy_id.name if getattr(tx, 'fiscal_policy_id', False) else 'FY 2026-2027',
                    'monthly_tds': f"{getattr(tx, 'monthly_tds_amount', 0.0):,.2f}",
                    'annual_tax': f"{getattr(tx, 'net_payable_tax', 0.0):,.2f}",
                }

        # 5. Performance, KPIs & 360° Reviewer Inbox
        kpis_list = []
        if 'dsl.hrms.employee.kpi' in self.env:
            emp_kpis = self.env['dsl.hrms.employee.kpi'].sudo().search([
                ('employee_id', '=', emp.id),
            ], limit=6)
            for kp in emp_kpis:
                kpis_list.append({
                    'id': kp.id,
                    'name': kp.kpi_id.name if getattr(kp, 'kpi_id', False) else kp.display_name,
                    'weight': getattr(kp, 'weightage', 0.0),
                    'target': getattr(kp, 'target_value', 0.0),
                    'actual': getattr(kp, 'actual_value', 0.0),
                    'achievement_pct': round(getattr(kp, 'achievement_percentage', 0.0) or getattr(kp, 'weighted_score', 0.0), 1),
                })

        assessments_list = []
        if 'dsl.hrms.assessment' in self.env:
            asms = self.env['dsl.hrms.assessment'].sudo().search([
                ('employee_id', '=', emp.id),
            ], order='id desc', limit=4)
            for a in asms:
                assessments_list.append({
                    'id': a.id,
                    'name': a.name,
                    'cycle': a.cycle_id.name if getattr(a, 'cycle_id', False) else 'Annual Cycle',
                    'score': round(getattr(a, 'final_weighted_score', 0.0), 1),
                    'grade': getattr(a, 'final_rating_band', '') or 'A (Outstanding)',
                    'state': (a.state or 'draft').replace('_', ' ').title(),
                })

        pending_reviews_count = 0
        if 'dsl.hrms.assessment.response' in self.env:
            Resp = self.env['dsl.hrms.assessment.response'].sudo()
            rev_fld = 'reviewer_id' if 'reviewer_id' in Resp._fields else ('reviewer_employee_id' if 'reviewer_employee_id' in Resp._fields else None)
            if rev_fld:
                pending_reviews_count = Resp.search_count([
                    (rev_fld, '=', emp.id),
                    ('state', '!=', 'submitted'),
                ])

        # 6. Assets, Digital Documents, Salary Doc Requests, HR Letters & Helpdesk Tickets
        assets_list = []
        if 'dsl.employee.asset' in self.env:
            ast_recs = self.env['dsl.employee.asset'].sudo().search([
                ('employee_id', '=', emp.id),
            ], limit=5)
            for ar in ast_recs:
                assets_list.append({
                    'id': ar.id,
                    'name': getattr(ar, 'asset_name', False) or ar.display_name,
                    'code': getattr(ar, 'asset_code', False) or getattr(ar, 'serial_number', 'AST'),
                    'category': (getattr(ar, 'asset_category', 'IT Equipment') or 'Equipment').replace('_', ' ').title(),
                    'state': (getattr(ar, 'state', 'allocated') or 'Allocated').replace('_', ' ').title(),
                })

        docs_list = []
        if 'dsl.employee.document' in self.env:
            doc_recs = self.env['dsl.employee.document'].sudo().search([
                ('employee_id', '=', emp.id),
            ], limit=5)
            for dr in doc_recs:
                docs_list.append({
                    'id': dr.id,
                    'name': dr.name,
                    'type': dr.document_type_id.name if dr.document_type_id else 'Official Document',
                    'ref': dr.reference_no or dr.doc_number or '—',
                    'status': (dr.verification_state or 'verified').title(),
                })

        salary_doc_reqs = []
        if 'dsl.hrms.salary.document.request' in self.env:
            sreqs = self.env['dsl.hrms.salary.document.request'].sudo().search([
                ('employee_id', '=', emp.id),
            ], order='id desc', limit=4)
            for sr in sreqs:
                salary_doc_reqs.append({
                    'id': sr.id,
                    'name': sr.name,
                    'doc_type': sr.document_type_id.name if getattr(sr, 'document_type_id', False) else 'Salary Certificate',
                    'date': sr.request_date.strftime('%d %b %Y') if getattr(sr, 'request_date', False) else '',
                    'state': (sr.state or 'draft').replace('_', ' ').title(),
                })

        hr_letters_list = []
        lreqs = self.env['dsl.hr.letter.request'].sudo().search([
            ('employee_id', '=', emp.id),
        ], order='id desc', limit=4)
        for lrq in lreqs:
            hr_letters_list.append({
                'id': lrq.id,
                'name': lrq.name,
                'type': dict(lrq._fields['letter_type'].selection).get(lrq.letter_type, 'Certificate'),
                'purpose': lrq.purpose or 'Official',
                'date': lrq.request_date.strftime('%d %b %Y') if lrq.request_date else '',
                'state': (lrq.state or 'draft').replace('_', ' ').title(),
            })

        tickets_list = []
        if 'dsl.hr.ticket' in self.env:
            tks = self.env['dsl.hr.ticket'].sudo().search([
                ('employee_id', '=', emp.id),
            ], order='id desc', limit=4)
            for tk in tks:
                tickets_list.append({
                    'id': tk.id,
                    'name': tk.name,
                    'subject': tk.subject,
                    'priority': (tk.priority or 'medium').title(),
                    'state': (getattr(tk, 'state', 'open') or 'Open').replace('_', ' ').title(),
                })

        # Unified Recent Self-Service Activity Feed (Top 5 items)
        recent_feed = []
        for lv in recent_leaves[:2]:
            recent_feed.append({
                'icon': 'fa-calendar-check-o',
                'color': 'emerald',
                'title': f"Leave: {lv['leave_type']} ({lv['days']}d)",
                'sub': f"{lv['date_from']} → {lv['date_to']}",
                'badge': lv['state_label'],
            })
        for sd in salary_doc_reqs[:2]:
            recent_feed.append({
                'icon': 'fa-file-text-o',
                'color': 'blue',
                'title': sd['doc_type'],
                'sub': f"Ref: {sd['name']} · {sd['date']}",
                'badge': sd['state'],
            })
        for hl in hr_letters_list[:1]:
            recent_feed.append({
                'icon': 'fa-certificate',
                'color': 'purple',
                'title': hl['type'],
                'sub': f"Purpose: {hl['purpose']}",
                'badge': hl['state'],
            })
        for tk in tickets_list[:1]:
            recent_feed.append({
                'icon': 'fa-headphones',
                'color': 'amber',
                'title': f"Ticket: {tk['subject']}",
                'sub': f"Ref: {tk['name']} · Priority: {tk['priority']}",
                'badge': tk['state'],
            })

        announcements_list = []
        if 'dsl.hr.announcement' in self.env:
            announcements_list = self.env['dsl.hr.announcement'].sudo().get_active_announcements_for_user(
                audience_mode='employee', emp=emp, limit=5
            )

        return {
            'has_employee': True,
            'announcements': announcements_list,
            'employee': {
                'id': emp.id,
                'name': emp.name,
                'name_bn': getattr(emp, 'name_bn', '') or '',
                'initials': initials,
                'code': emp.employee_code or 'EMP',
                'job': emp.job_id.name or 'Team Member',
                'department': emp.department_id.name or 'General',
                'branch': emp.branch_id.name if emp.branch_id else emp.company_id.name,
                'company': emp.company_id.name,
                'manager': emp.parent_id.name if emp.parent_id else 'Board / Management',
                'joining_date': getattr(emp, 'joining_date_formatted', '') or str(emp.joining_date or ''),
                'service_length': getattr(emp, 'service_length_display', '') or 'Active',
                'blood_group': getattr(emp, 'blood_group', '') or 'O+',
                'mobile': getattr(emp, 'overview_mobile_display', '') or emp.mobile_phone or emp.work_phone or '—',
                'email': emp.work_email or '—',
                'nid': getattr(emp, 'nid_number', '') or '—',
                'tin': getattr(emp, 'personal_tin', '') or '—',
                'bank_name': getattr(emp, 'salary_bank_name', '') or 'Corporate Bank BEFTN',
                'bank_acc': getattr(emp, 'salary_bank_account_no', '') or '—',
                'status_label': 'Confirmed / Active' if getattr(emp, 'employment_status', 'confirmed') == 'confirmed' else 'On Probation',
                'shift_label': shift_label,
                'degrees_count': getattr(emp, 'education_count', 0),
                'skills_count': getattr(emp, 'skill_count', 0),
                'prior_exp_years': getattr(emp, 'total_prior_experience_years', 0.0),
            },
            'attendance': {
                'checked_in': bool(att_log and att_log.check_in),
                'checked_out': bool(att_log and att_log.check_out),
                'check_in_str': fields.Datetime.context_timestamp(self, att_log.check_in).strftime('%I:%M %p') if (att_log and att_log.check_in) else '—',
                'check_out_str': fields.Datetime.context_timestamp(self, att_log.check_out).strftime('%I:%M %p') if (att_log and att_log.check_out) else '—',
                'status': att_log.status if att_log else 'not_checked_in',
                'present_month': present_month,
                'absent_month': absent_month,
                'late_month': late_month,
                'ot_hours_month': ot_hours_month,
                'recent_logs': recent_att_logs,
            },
            'leave_cards': leave_cards,
            'total_leave_remaining': round(total_leave_remaining, 1),
            'recent_leaves': recent_leaves,
            'upcoming_holidays': upcoming_holidays,
            'compensation': comp_pkg,
            'latest_payslip': latest_payslip,
            'recent_payslips': recent_payslips,
            'loan_balance': f"{loan_balance:,.2f}",
            'loans_list': loans_list,
            'pf_balance': f"{pf_balance:,.2f}",
            'pf_summary': pf_summary,
            'tax_summary': tax_summary,
            'kpis_list': kpis_list,
            'assessments_list': assessments_list,
            'pending_reviews_count': pending_reviews_count,
            'assets_list': assets_list,
            'docs_list': docs_list,
            'salary_doc_reqs': salary_doc_reqs,
            'hr_letters_list': hr_letters_list,
            'tickets_list': tickets_list,
            'recent_feed': recent_feed[:5],
            'has_helpdesk': 'dsl.hr.ticket' in self.env,
        }

    @api.model
    def action_ess_web_punch(self):
        emp = self._resolve_active_employee()
        if not emp:
            raise UserError(_('No employee profile linked to current user!'))
        today = fields.Date.context_today(self)
        now = fields.Datetime.now()
        Att = self.env['dsl.attendance.log'].sudo()
        log = Att.search([
            ('employee_id', '=', emp.id),
            ('attendance_date', '=', today),
        ], limit=1)
        area = f"{emp.branch_id.name} (ESS Web)" if emp.branch_id else "Corporate ESS Portal"
        if not log:
            Att.create({
                'employee_id': emp.id,
                'company_id': emp.company_id.id,
                'branch_id': emp.branch_id.id if emp.branch_id else False,
                'attendance_date': today,
                'check_in': now,
                'check_in_location': area,
            })
            return {'status': 'checked_in'}
        if not log.check_out:
            log.write({
                'check_out': now,
                'check_out_location': area,
            })
            return {'status': 'checked_out'}
        return {'status': 'already_completed'}


class DslHrLetterRequest(models.Model):
    _name = 'dsl.hr.letter.request'
    _description = 'Employee Official HR Certificate, Salary Certificate & NOC Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'

    name = fields.Char(
        string='Certificate Ref.',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        default=_default_ess_employee,
        index=True,
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
        string='Branch / Plant',
        domain="[('company_id', '=', company_id)]",
    )
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', store=True, readonly=True)
    job_id = fields.Many2one('hr.job', related='employee_id.job_id', store=True, readonly=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    letter_type = fields.Selection(
        selection=[
            ('salary_certificate', 'Salary Certificate (বেতন প্রত্যয়নপত্র)'),
            ('visa_noc', 'Visa / Passport No-Objection Certificate (NOC)'),
            ('bank_intro', 'Bank Account / Loan Introduction Letter'),
            ('employment_cert', 'To Whom It May Concern — Employment Confirmation'),
        ],
        string='Document Type',
        default='salary_certificate',
        required=True,
        tracking=True,
    )
    addressed_to = fields.Char(
        string='Addressed To',
        default='To Whom It May Concern',
        required=True,
    )
    purpose = fields.Char(string='Purpose (e.g. Tourist Visa / Bank Account / Tax Return)', required=True)
    request_date = fields.Date(string='Request Date', default=fields.Date.context_today, required=True)
    issued_date = fields.Date(string='Issued Date', readonly=True)
    monthly_gross_snapshot = fields.Monetary(string='Certified Monthly Gross (৳)', currency_field='currency_id')
    joining_date_snapshot = fields.Date(string='Joining Date')
    hr_remarks = fields.Text(string='HR Verification / Custom Body Notes')

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('requested', 'Submitted to HR'),
            ('approved', 'HR Approved'),
            ('issued', 'Issued & Printable'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    @api.onchange('employee_id')
    def _onchange_employee_snapshot(self):
        if self.employee_id:
            emp = self.employee_id.sudo()
            self.company_id = emp.company_id.id
            self.branch_id = emp.branch_id.id if emp.branch_id else False
            self.joining_date_snapshot = emp.joining_date
            pkg = self.env['dsl.employee.compensation'].sudo().search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'active'),
            ], order='effective_from desc, id desc', limit=1)
            if pkg:
                self.monthly_gross_snapshot = pkg.total_gross_package or pkg.gross_salary

    @api.model_create_multi
    def create(self, vals_list):
        Employee = self.env['hr.employee'].sudo()
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.hr.letter.request') or _('New')
            if vals.get('employee_id'):
                emp = Employee.browse(vals['employee_id'])
                if not vals.get('company_id') and emp.company_id:
                    vals['company_id'] = emp.company_id.id
                if not vals.get('branch_id') and emp.branch_id:
                    vals['branch_id'] = emp.branch_id.id
        return super().create(vals_list)

    def action_submit(self):
        for rec in self:
            if not rec.monthly_gross_snapshot:
                rec._onchange_employee_snapshot()
            rec.write({'state': 'requested'})

    def action_approve_issue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.monthly_gross_snapshot:
                rec._onchange_employee_snapshot()
            rec.write({'state': 'issued', 'issued_date': today})

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_print_letter(self):
        return self.env.ref('DSL_HRMS_ess.action_report_dsl_hr_letter').report_action(self)


class DslHrAnnouncement(models.Model):
    _name = 'dsl.hr.announcement'
    _description = 'Corporate HR Announcement & Notice Board Circular'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'is_pinned desc, publish_date desc, id desc'
    _rec_name = 'title'

    name = fields.Char(
        string='Circular Ref.',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
    )
    title = fields.Char(
        string='Announcement Title (শিরোনাম)',
        required=True,
        tracking=True,
    )
    category = fields.Selection(
        selection=[
            ('general', 'General Notice (সাধারণ বিজ্ঞপ্তি)'),
            ('policy', 'HR Policy Update (নীতিমালা)'),
            ('holiday', 'Holiday & Festival (ছুটি ও উৎসব)'),
            ('payroll', 'Payroll & Bonus (বেতন ও বোনাস)'),
            ('event', 'Townhall & Event (ইভেন্ট)'),
            ('urgent', 'Urgent Alert (জরুরি নির্দেশনা)'),
        ],
        string='Notice Category',
        default='general',
        required=True,
        tracking=True,
    )
    priority = fields.Selection(
        selection=[
            ('normal', 'Normal'),
            ('high', 'Important'),
            ('urgent', 'Urgent / Critical'),
        ],
        string='Priority',
        default='normal',
        required=True,
        tracking=True,
    )
    is_pinned = fields.Boolean(
        string='Pin to Top of Dashboards',
        default=False,
        tracking=True,
    )
    audience_type = fields.Selection(
        selection=[
            ('all', 'All Employees (সকল কর্মী)'),
            ('company', 'Specific Company'),
            ('branch', 'Specific Branch / Factory'),
            ('department', 'Specific Department'),
            ('managers_only', 'Managers & Supervisors Only'),
        ],
        string='Target Audience',
        default='all',
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Target Branch / Plant',
        domain="[('company_id', '=', company_id)]",
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Target Department',
    )
    publish_date = fields.Date(
        string='Publish Date',
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )
    expiry_date = fields.Date(
        string='Valid Until (Expiry Date)',
        tracking=True,
    )
    published_by_id = fields.Many2one(
        'res.users',
        string='Published By',
        default=lambda self: self.env.user,
        readonly=True,
    )
    summary = fields.Text(
        string='Dashboard Summary (১-২ লাইনের সারসংক্ষেপ)',
        required=True,
        help='Concise 1-2 line summary displayed on Employee (ESS), Manager (MSS) and HR Dashboards.',
    )
    body_html = fields.Html(
        string='Full Official Circular / Notice Details',
        sanitize_style=True,
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'dsl_hr_announcement_attachment_rel',
        'announcement_id',
        'attachment_id',
        string='Official Circular PDF / Attachments',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('published', 'Published & Live'),
            ('archived', 'Archived / Expired'),
        ],
        string='Status',
        default='published',
        required=True,
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                seq = self.env['ir.sequence'].sudo().next_by_code('dsl.hr.announcement')
                if not seq:
                    cnt = self.sudo().search_count([]) + 1
                    seq = f"ANN-2026-{cnt:04d}"
                vals['name'] = seq
        return super().create(vals_list)

    def action_publish(self):
        self.write({'state': 'published', 'publish_date': fields.Date.context_today(self)})

    def action_archive_notice(self):
        self.write({'state': 'archived'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    @api.model
    def get_active_announcements_for_user(self, audience_mode='employee', emp=None, limit=5):
        today = fields.Date.context_today(self)
        domain = [
            ('state', '=', 'published'),
            '|', ('expiry_date', '=', False), ('expiry_date', '>=', today),
        ]
        if audience_mode == 'employee':
            domain.append(('audience_type', '!=', 'managers_only'))

        recs = self.sudo().search(domain, order='is_pinned desc, publish_date desc, id desc', limit=limit * 2)
        cat_labels = {
            'general': 'General Notice',
            'policy': 'HR Policy',
            'holiday': 'Holiday & Festival',
            'payroll': 'Payroll & Bonus',
            'event': 'Event / Townhall',
            'urgent': 'Urgent Alert',
        }
        cat_colors = {
            'general': 'blue',
            'policy': 'indigo',
            'holiday': 'emerald',
            'payroll': 'purple',
            'event': 'amber',
            'urgent': 'rose',
        }
        result = []
        for r in recs:
            if emp:
                if r.audience_type == 'company' and r.company_id and r.company_id != emp.company_id:
                    continue
                if r.audience_type == 'branch' and r.branch_id and emp.branch_id and r.branch_id != emp.branch_id:
                    continue
                if r.audience_type == 'department' and r.department_id and emp.department_id and r.department_id != emp.department_id:
                    continue
            result.append({
                'id': r.id,
                'name': r.name,
                'title': r.title,
                'category': r.category,
                'category_label': cat_labels.get(r.category, 'Notice'),
                'color': cat_colors.get(r.category, 'blue'),
                'priority': r.priority,
                'is_pinned': bool(r.is_pinned),
                'audience': dict(r._fields['audience_type'].selection).get(r.audience_type, 'All Employees'),
                'date': r.publish_date.strftime('%d %b %Y') if r.publish_date else '',
                'summary': r.summary or '',
                'author': r.published_by_id.name if r.published_by_id else 'HR Department',
            })
            if len(result) >= limit:
                break
        return result

