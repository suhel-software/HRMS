# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


def _default_lwd_60(record=None):
    today = fields.Date.context_today(record) if record is not None else fields.Date.today()
    return today + timedelta(days=60)


class DslEmployeeSeparation(models.Model):
    _name = 'dsl.employee.separation'
    _description = 'Employee Resignation, Exit Clearance & Full-and-Final Settlement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'submission_date desc, id desc'

    name = fields.Char(
        string='Separation Ref.',
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
        index=True,
    )
    accounting_company_id = fields.Many2one(
        'res.company',
        string='COA / Books Entity',
        compute='_compute_accounting_entity',
        store=True,
    )
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', store=True, readonly=True)
    job_id = fields.Many2one('hr.job', related='employee_id.job_id', store=True, readonly=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True, readonly=True)

    separation_type = fields.Selection(
        selection=[
            ('resignation', 'Voluntary Resignation — স্বেচ্ছায় পদত্যাগ (Sec 27)'),
            ('retirement', 'Retirement / Superannuation — অবসর গ্রহণ (Sec 28)'),
            ('end_of_contract', 'End of Fixed-Term Contract — চুক্তির মেয়াদ শেষ'),
            ('retrenchment', 'Retrenchment / Redundancy — ছাঁটাই (Sec 20)'),
            ('termination', 'Termination Simpliciter — চাকরি অবসান (Sec 26)'),
            ('mutual', 'Mutual Separation — পারস্পরিক সমঝোতা'),
        ],
        string='Separation Category',
        default='resignation',
        required=True,
        tracking=True,
    )

    joining_date = fields.Date(string='Date of Joining', required=True, default=fields.Date.context_today)
    submission_date = fields.Date(string='Notice / Resignation Date', required=True, default=fields.Date.context_today, tracking=True)
    notice_period_days = fields.Integer(
        string='Required Notice (Days)',
        default=60,
        required=True,
        help='Bangladesh Labour Act Sec 27: 60 days notice for permanent employees (or 30 days per contract).',
    )
    expected_last_working_day = fields.Date(
        string='Expected Last Working Day',
        compute='_compute_notice_metrics',
        store=True,
    )
    actual_last_working_day = fields.Date(
        string='Approved Last Working Day',
        required=True,
        default=_default_lwd_60,
        tracking=True,
    )
    served_notice_days = fields.Integer(
        string='Served Notice (Days)',
        compute='_compute_notice_metrics',
        store=True,
    )
    notice_shortfall_days = fields.Integer(
        string='Notice Shortfall (Days)',
        compute='_compute_notice_metrics',
        store=True,
    )
    waive_notice_shortfall = fields.Boolean(
        string='Waive Notice Shortfall Recovery',
        default=False,
        tracking=True,
    )
    released_date = fields.Date(string='Final Release Date', readonly=True)
    departure_reason_id = fields.Many2one(
        'hr.departure.reason',
        string='Odoo Departure Reason',
        ondelete='set null',
        help='Linked Odoo native hr.departure.reason record.',
    )

    reason = fields.Text(string='Reason for Separation', required=True)
    exit_interview_summary = fields.Text(string='HR Exit Interview Notes')

    # Clearance Checklist
    clearance_line_ids = fields.One2many(
        'dsl.separation.clearance.line',
        'separation_id',
        string='Multi-Department Exit Clearance Checklist',
    )
    all_cleared = fields.Boolean(string='100% Clearance Completed', compute='_compute_all_cleared', store=True)

    # Full & Final (F&F) Settlement Fields
    last_gross_salary = fields.Monetary(string='Last Monthly Gross (৳)', currency_field='currency_id')
    last_basic_salary = fields.Monetary(string='Last Monthly Basic (৳)', currency_field='currency_id')

    unpaid_salary_days = fields.Float(string='Unpaid Worked Days (Final Month)', default=0.0)
    unpaid_salary_amount = fields.Monetary(string='Unpaid Salary Payable (৳)', currency_field='currency_id')

    encashable_el_days = fields.Float(string='Unused Earned Leave Days (EL)', default=0.0)
    leave_encashment_amount = fields.Monetary(string='Earned Leave Encashment (৳)', currency_field='currency_id')

    vested_pf_payable = fields.Monetary(string='Vested Provident Fund Payable (৳)', currency_field='currency_id')
    gratuity_payable = fields.Monetary(string='Statutory Gratuity Payable (৳)', currency_field='currency_id')
    other_addition_amount = fields.Monetary(string='Other Dues / Arrear / Bonus (৳)', currency_field='currency_id')

    notice_shortfall_recovery = fields.Monetary(string='Notice Shortfall Recovery (৳)', currency_field='currency_id')
    outstanding_loan_recovery = fields.Monetary(string='Active Loan / Advance Recovery (৳)', currency_field='currency_id')
    asset_damage_recovery = fields.Monetary(string='Unreturned Asset / IOU Recovery (৳)', currency_field='currency_id')
    tax_or_other_deduction = fields.Monetary(string='Final TDS / Other Deduction (৳)', currency_field='currency_id')

    total_fnf_additions = fields.Monetary(
        string='Total Final Payables (৳)',
        currency_field='currency_id',
        compute='_compute_fnf_totals',
        store=True,
    )
    total_fnf_deductions = fields.Monetary(
        string='Total Final Recoveries (৳)',
        currency_field='currency_id',
        compute='_compute_fnf_totals',
        store=True,
    )
    net_settlement_payable = fields.Monetary(
        string='Net Full & Final Payable (৳)',
        currency_field='currency_id',
        compute='_compute_fnf_totals',
        store=True,
        tracking=True,
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Notice Submitted'),
            ('notice_clearance', 'Exit Clearance in Progress'),
            ('fnf_computed', 'F&F Calculated'),
            ('approved', 'Management Approved'),
            ('settled_released', 'Settled & Released'),
            ('cancelled', 'Withdrawn / Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )

    @api.depends('company_id', 'branch_id', 'branch_id.accounting_company_id')
    def _compute_accounting_entity(self):
        for rec in self:
            if rec.branch_id and rec.branch_id.accounting_company_id:
                rec.accounting_company_id = rec.branch_id.accounting_company_id.id
            else:
                rec.accounting_company_id = rec.company_id.id if rec.company_id else False

    @api.depends('submission_date', 'notice_period_days', 'actual_last_working_day')
    def _compute_notice_metrics(self):
        for rec in self:
            req = max(rec.notice_period_days or 0, 0)
            if rec.submission_date:
                rec.expected_last_working_day = rec.submission_date + timedelta(days=req)
            else:
                rec.expected_last_working_day = False
            if rec.submission_date and rec.actual_last_working_day:
                served = max((rec.actual_last_working_day - rec.submission_date).days, 0)
                rec.served_notice_days = served
                rec.notice_shortfall_days = max(req - served, 0)
            else:
                rec.served_notice_days = 0
                rec.notice_shortfall_days = 0

    @api.depends('clearance_line_ids', 'clearance_line_ids.is_cleared')
    def _compute_all_cleared(self):
        for rec in self:
            rec.all_cleared = bool(rec.clearance_line_ids) and all(rec.clearance_line_ids.mapped('is_cleared'))

    @api.depends(
        'unpaid_salary_amount', 'leave_encashment_amount', 'vested_pf_payable',
        'gratuity_payable', 'other_addition_amount',
        'notice_shortfall_recovery', 'outstanding_loan_recovery',
        'asset_damage_recovery', 'tax_or_other_deduction',
    )
    def _compute_fnf_totals(self):
        for rec in self:
            adds = round(
                (rec.unpaid_salary_amount or 0.0)
                + (rec.leave_encashment_amount or 0.0)
                + (rec.vested_pf_payable or 0.0)
                + (rec.gratuity_payable or 0.0)
                + (rec.other_addition_amount or 0.0),
                2,
            )
            deds = round(
                (rec.notice_shortfall_recovery or 0.0)
                + (rec.outstanding_loan_recovery or 0.0)
                + (rec.asset_damage_recovery or 0.0)
                + (rec.tax_or_other_deduction or 0.0),
                2,
            )
            rec.total_fnf_additions = adds
            rec.total_fnf_deductions = deds
            rec.net_settlement_payable = round(adds - deds, 2)

    @api.constrains('joining_date', 'actual_last_working_day')
    def _check_dates(self):
        for rec in self:
            if rec.joining_date and rec.actual_last_working_day and rec.actual_last_working_day < rec.joining_date:
                raise ValidationError(_('Approved Last Working Day cannot be earlier than Joining Date!'))

    @api.onchange('employee_id')
    def _onchange_employee_sync_profile(self):
        if self.employee_id:
            emp = self.employee_id.sudo()
            self.company_id = emp.company_id.id
            self.branch_id = emp.branch_id.id if emp.branch_id else False
            if emp.joining_date:
                self.joining_date = emp.joining_date
            if emp.notice_period_days:
                self.notice_period_days = emp.notice_period_days
            if self.submission_date:
                self.actual_last_working_day = self.submission_date + timedelta(days=self.notice_period_days or 60)
            pkg = self.env['dsl.employee.compensation'].sudo().search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'active'),
            ], order='effective_from desc, id desc', limit=1)
            if pkg:
                self.last_gross_salary = pkg.total_gross_package or pkg.gross_salary
                self.last_basic_salary = pkg.basic_salary

    @api.model_create_multi
    def create(self, vals_list):
        Employee = self.env['hr.employee'].sudo()
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.employee.separation') or _('New')
            if vals.get('employee_id'):
                emp = Employee.browse(vals['employee_id'])
                vals.setdefault('company_id', emp.company_id.id)
                if emp.branch_id and not vals.get('branch_id'):
                    vals['branch_id'] = emp.branch_id.id
                if emp.joining_date and not vals.get('joining_date'):
                    vals['joining_date'] = emp.joining_date
        return super().create(vals_list)

    def action_generate_clearance_checklist(self):
        for rec in self:
            if rec.clearance_line_ids:
                continue
            mgr_user = rec.employee_id.parent_id.user_id.id if (rec.employee_id.parent_id and rec.employee_id.parent_id.user_id) else self.env.uid
            default_items = [
                ('line_manager', 'Complete Knowledge Transfer, Project Handover & Team Files'),
                ('it_security', 'Return Laptop/Peripherals & Revoke ERP, VPN, Official Email Access'),
                ('admin_assets', 'Surrender ID Card, Access Badge, Corporate SIM & Vehicle/Desk Keys'),
                ('finance_accounts', 'Settle Pending Cash IOU, Imprest, Corporate Card & Travel Advances'),
                ('hr_exit', 'Conduct Exit Interview, Verify Nominee/PF/Gratuity Dossier & Tax Slip'),
            ]
            self.env['dsl.separation.clearance.line'].create([{
                'separation_id': rec.id,
                'department_area': area,
                'checklist_item': item,
                'responsible_user_id': mgr_user if area == 'line_manager' else self.env.uid,
            } for area, item in default_items])

    def action_mark_all_cleared(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.clearance_line_ids:
                rec.action_generate_clearance_checklist()
            rec.clearance_line_ids.write({
                'is_cleared': True,
                'cleared_date': today,
            })

    def action_submit(self):
        for rec in self:
            rec.action_generate_clearance_checklist()
            rec.employee_id.sudo().write({'employment_status': 'notice_period'})
            rec.state = 'submitted'

    def action_start_clearance(self):
        for rec in self:
            rec.action_generate_clearance_checklist()
            rec.state = 'notice_clearance'

    def action_compute_final_settlement(self):
        Comp = self.env['dsl.employee.compensation'].sudo()
        Alloc = self.env['dsl.leave.allocation'].sudo()
        PfAcc = self.env['dsl.pf.account'].sudo()
        GratPol = self.env['dsl.gratuity.policy'].sudo()
        Loan = self.env['dsl.employee.loan'].sudo()

        for rec in self:
            emp = rec.employee_id.sudo()
            pkg = Comp.search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'active'),
            ], order='effective_from desc, id desc', limit=1)
            gross = (pkg.total_gross_package or pkg.gross_salary) if pkg else (rec.last_gross_salary or 0.0)
            basic = pkg.basic_salary if pkg else (rec.last_basic_salary or round(gross * 0.50, 2))

            # 1. Unpaid Salary Days (default to day of actual_last_working_day if 0)
            unpaid_days = rec.unpaid_salary_days
            if unpaid_days <= 0 and rec.actual_last_working_day:
                unpaid_days = float(min(rec.actual_last_working_day.day, 30))
            unpaid_amt = round(unpaid_days * (gross / 30.0), 2) if gross > 0 else 0.0

            # 2. Earned Leave Encashment (BD Labour Act Sec 117 — up to unused EL balance)
            yr_str = str((rec.actual_last_working_day or fields.Date.context_today(self)).year)
            el_allocs = Alloc.search([
                ('employee_id', '=', emp.id),
                ('leave_year', '=', yr_str),
                ('state', '=', 'active'),
            ]).filtered(lambda a: a.leave_type_id.allow_encashment or a.leave_type_id.code == 'EL')
            el_days = sum(el_allocs.mapped('remaining_days')) if el_allocs else rec.encashable_el_days
            el_days = max(el_days, 0.0)
            el_amt = round(el_days * (gross / 30.0), 2) if gross > 0 else 0.0

            # 3. Vested Provident Fund Balance
            pf_acc = PfAcc.search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'active'),
            ], limit=1)
            pf_amt = round(pf_acc.vested_payable_balance, 2) if pf_acc else 0.0

            # 4. Statutory Gratuity Payable
            grat_pol = GratPol.search([
                '|', ('company_id', '=', False), ('company_id', '=', rec.company_id.id),
                ('active', '=', True),
            ], order='company_id desc, id asc', limit=1)
            grat_amt = 0.0
            if grat_pol and rec.joining_date and rec.actual_last_working_day and basic > 0:
                g_dict = grat_pol._calculate_gratuity_dict(rec.joining_date, rec.actual_last_working_day, basic)
                grat_amt = g_dict['gross_gratuity']

            # 5. Notice Shortfall Recovery (on Basic unless waived)
            shortfall_amt = 0.0
            if not rec.waive_notice_shortfall and rec.notice_shortfall_days > 0 and basic > 0:
                shortfall_amt = round(rec.notice_shortfall_days * (basic / 30.0), 2)

            # 6. Active Loan / Salary Advance Outstanding Recovery
            active_loans = Loan.search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'disbursed'),
            ])
            loan_rec_amt = round(sum(active_loans.mapped('balance_amount')), 2)

            rec.write({
                'last_gross_salary': gross,
                'last_basic_salary': basic,
                'unpaid_salary_days': unpaid_days,
                'unpaid_salary_amount': unpaid_amt,
                'encashable_el_days': el_days,
                'leave_encashment_amount': el_amt,
                'vested_pf_payable': pf_amt,
                'gratuity_payable': grat_amt,
                'notice_shortfall_recovery': shortfall_amt,
                'outstanding_loan_recovery': loan_rec_amt,
                'state': 'fnf_computed',
            })

    def action_approve_fnf(self):
        self.write({'state': 'approved'})

    def action_settle_and_release(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.clearance_line_ids and not rec.all_cleared:
                raise UserError(_(
                    'All Multi-Department Exit Clearance items must be marked Cleared before issuing Final Release for %s!'
                ) % rec.employee_id.name)

            # Settle PF account if paid out in F&F
            if rec.vested_pf_payable > 0:
                pf_acc = self.env['dsl.pf.account'].sudo().search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('state', '=', 'active'),
                ], limit=1)
                if pf_acc:
                    self.env['dsl.pf.ledger.line'].sudo().create({
                        'pf_account_id': pf_acc.id,
                        'entry_date': today,
                        'entry_type': 'settlement_payout',
                        'description': f"{rec.name} — Final Exit Settlement",
                        'employee_amount': rec.vested_pf_payable,
                    })
                    pf_acc.write({'state': 'settled'})

            # Mark active loans settled if recovered in F&F
            if rec.outstanding_loan_recovery > 0:
                active_loans = self.env['dsl.employee.loan'].sudo().search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('state', '=', 'disbursed'),
                ])
                for ln in active_loans:
                    unpaid_insts = ln.installment_ids.filtered(lambda i: not i.is_paid)
                    unpaid_insts.write({
                        'is_paid': True,
                        'paid_date': today,
                    })
                    ln.write({'state': 'settled'})

            rec.employee_id.sudo().write({'employment_status': 'separated'})
            rec.write({
                'state': 'settled_released',
                'released_date': today,
            })
            rec._sync_to_odoo_departure()

    def _sync_to_odoo_departure(self):
        """Sync separation with Odoo's native hr.departure.reason, hr.employee departure fields, and hr.contract."""
        if 'hr.departure.reason' not in self.env:
            return
        DepReason = self.env['hr.departure.reason'].sudo()
        reason_map = {
            'resignation': 'Resigned',
            'retirement': 'Retired',
            'end_of_contract': 'Fired',
            'retrenchment': 'Fired',
            'termination': 'Fired',
            'mutual': 'Resigned',
        }
        for rec in self:
            if not rec.employee_id:
                continue
            dep_reason = rec.departure_reason_id
            if not dep_reason:
                target_name = reason_map.get(rec.separation_type, 'Resigned')
                dep_reason = DepReason.search([('name', 'ilike', target_name)], limit=1)
                if not dep_reason:
                    dep_reason = DepReason.search([], limit=1)
                if dep_reason:
                    rec.with_context(skip_odoo_dep_sync=True).write({'departure_reason_id': dep_reason.id})
            emp_vals = {
                'departure_description': rec.reason or rec.exit_interview_summary or rec.name,
                'departure_date': rec.actual_last_working_day or rec.released_date or fields.Date.context_today(self),
            }
            if dep_reason:
                emp_vals['departure_reason_id'] = dep_reason.id
            rec.employee_id.sudo().write(emp_vals)
            if rec.state == 'settled_released' and 'hr.contract' in self.env:
                active_contracts = self.env['hr.contract'].sudo().search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('state', 'in', ('draft', 'open')),
                ])
                if active_contracts:
                    active_contracts.write({
                        'state': 'close',
                        'date_end': rec.actual_last_working_day or rec.released_date or fields.Date.context_today(self),
                    })

    def action_print_release_certificate(self):
        self.ensure_one()
        return self.env.ref('DSL_HRMS_separation.action_report_dsl_separation_pack').report_action(self)

    def action_cancel(self):
        for rec in self:
            if rec.employee_id.employment_status == 'notice_period':
                rec.employee_id.sudo().write({'employment_status': 'confirmed'})
            rec.state = 'cancelled'


class DslSeparationClearanceLine(models.Model):
    _name = 'dsl.separation.clearance.line'
    _description = 'Multi-Department Exit Clearance Item'
    _order = 'id asc'

    separation_id = fields.Many2one(
        'dsl.employee.separation',
        string='Separation Case',
        required=True,
        ondelete='cascade',
        index=True,
    )
    department_area = fields.Selection(
        selection=[
            ('line_manager', 'Line Manager / Department Handover'),
            ('it_security', 'IT, InfoSec & ERP Access'),
            ('admin_assets', 'Admin, Logistics & Physical Assets'),
            ('finance_accounts', 'Finance, Treasury & IOU Clearance'),
            ('hr_exit', 'HR Operations & Final Dossier'),
        ],
        string='Clearance Wing',
        required=True,
        default='line_manager',
    )
    checklist_item = fields.Char(string='Handover / Asset Verification Item', required=True)
    responsible_user_id = fields.Many2one('res.users', string='Clearance Sign-Off Officer')
    is_cleared = fields.Boolean(string='Cleared', default=False)
    cleared_date = fields.Date(string='Cleared Date')
    remarks = fields.Char(string='Asset / Handover Remarks')

    @api.onchange('is_cleared')
    def _onchange_is_cleared(self):
        if self.is_cleared and not self.cleared_date:
            self.cleared_date = fields.Date.context_today(self)


class HrEmployeeSeparationExt(models.Model):
    _inherit = 'hr.employee'

    dsl_separation_ids = fields.One2many(
        'dsl.employee.separation',
        'employee_id',
        string='Resignation, Clearance & Final Settlement',
        groups='hr.group_hr_user',
    )

