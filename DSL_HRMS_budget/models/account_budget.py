# -*- coding: utf-8 -*-
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class AccountBudgetPost(models.Model):
    _name = "account.budget.post"
    _order = "code, name"
    _description = "Budgetary Position"
    _inherit = ['mail.thread']

    name = fields.Char('Name', required=True, tracking=True)
    code = fields.Char('Code', tracking=True)
    type = fields.Selection([
        ('expense', 'Expense'),
        ('income', 'Income'),
        ('profit_loss', 'Profit & Loss / Both'),
    ], string='Position Type', default='expense', required=True, tracking=True)
    account_ids = fields.Many2many(
        'account.account', 'account_budget_rel', 'budget_id', 'account_id',
        string='Accounts',
        domain=[('deprecated', '=', False)]
    )
    company_id = fields.Many2one(
        'res.company', 'Company', required=True,
        default=lambda self: self.env.company
    )
    active = fields.Boolean('Active', default=True)
    account_count = fields.Integer('Accounts Count', compute='_compute_account_count')
    notes = fields.Text('Description / Notes')

    @api.depends('account_ids')
    def _compute_account_count(self):
        for post in self:
            post.account_count = len(post.account_ids)

    @api.constrains('account_ids')
    def _check_account_ids(self):
        for post in self:
            if not post.account_ids:
                raise ValidationError(_("The Budgetary Position '%s' must have at least one financial account linked!") % post.name)


class CrossoveredBudget(models.Model):
    _name = "crossovered.budget"
    _description = "Financial Budget"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "date_from desc, id desc"

    name = fields.Char('Budget Name', required=True, tracking=True)
    code = fields.Char(
        'Budget Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'), tracking=True
    )
    user_id = fields.Many2one(
        'res.users', 'Responsible',
        default=lambda self: self.env.user, tracking=True
    )
    department_id = fields.Many2one(
        'hr.department', 'Department / Division', tracking=True
    )
    date_from = fields.Date('Start Date', required=True, tracking=True)
    date_to = fields.Date('End Date', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('validate', 'Approved'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], 'Status', default='draft', index=True, required=True, readonly=True, copy=False, tracking=True)
    crossovered_budget_line = fields.One2many(
        'crossovered.budget.lines', 'crossovered_budget_id', 'Budget Lines', copy=True
    )
    company_id = fields.Many2one(
        'res.company', 'Company', required=True,
        default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True
    )
    report_budget_id = fields.Many2one(
        'account.report.budget',
        string='Linked Financial Report Budget (P&L Sync)',
        readonly=True, copy=False,
        help="Automatically synced monthly budget used in P&L and Balance Sheet Dynamic Financial Reports."
    )
    notes = fields.Html('Budget Notes & Policy')

    # Summary KPI Totals
    total_planned_amount = fields.Monetary(
        'Total Planned Budget', currency_field='currency_id',
        compute='_compute_budget_totals', store=True
    )
    total_revised_amount = fields.Monetary(
        'Total Revision / Re-Budget', currency_field='currency_id',
        compute='_compute_budget_totals', store=True
    )
    total_effective_amount = fields.Monetary(
        'Total Effective Budget', currency_field='currency_id',
        compute='_compute_budget_totals', store=True
    )
    total_practical_amount = fields.Monetary(
        'Total Practical (Actual)', currency_field='currency_id',
        compute='_compute_budget_runtime_totals'
    )
    total_theoretical_amount = fields.Monetary(
        'Total Theoretical (To Date)', currency_field='currency_id',
        compute='_compute_budget_runtime_totals'
    )
    total_variance_amount = fields.Monetary(
        'Total Variance (Remaining)', currency_field='currency_id',
        compute='_compute_budget_runtime_totals'
    )
    overall_achievement = fields.Float(
        'Overall Utilization (%)',
        compute='_compute_budget_runtime_totals'
    )
    above_budget_count = fields.Integer(
        'Exceeded Lines',
        compute='_compute_budget_runtime_totals'
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('New')) == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code('crossovered.budget') or _('New')
        return super().create(vals_list)

    @api.depends('crossovered_budget_line.planned_amount', 'crossovered_budget_line.revised_amount')
    def _compute_budget_totals(self):
        for budget in self:
            planned = sum(budget.crossovered_budget_line.mapped('planned_amount'))
            revised = sum(budget.crossovered_budget_line.mapped('revised_amount'))
            budget.total_planned_amount = planned
            budget.total_revised_amount = revised
            budget.total_effective_amount = planned + revised

    def _compute_budget_runtime_totals(self):
        for budget in self:
            lines = budget.crossovered_budget_line
            effective = sum(lines.mapped('effective_amount'))
            practical = sum(lines.mapped('practical_amount'))
            theoretical = sum(lines.mapped('theoritical_amount'))
            budget.total_practical_amount = practical
            budget.total_theoretical_amount = theoretical
            budget.total_variance_amount = effective - practical
            if effective:
                budget.overall_achievement = round((abs(practical) / abs(effective)) * 100.0, 2)
            else:
                budget.overall_achievement = 0.0
            budget.above_budget_count = len(lines.filtered(lambda l: l.is_above_budget))

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for budget in self:
            if budget.date_from and budget.date_to and budget.date_to < budget.date_from:
                raise ValidationError(_("The Budget End Date cannot be earlier than the Start Date!"))

    def action_budget_confirm(self):
        self.write({'state': 'confirm'})
        self.action_sync_to_report_budget()

    def action_budget_draft(self):
        self.write({'state': 'draft'})

    def action_budget_validate(self):
        self.write({'state': 'validate'})
        self.action_sync_to_report_budget()

    def action_budget_cancel(self):
        self.write({'state': 'cancel'})

    def action_budget_done(self):
        self.write({'state': 'done'})
        self.action_sync_to_report_budget()

    def action_sync_to_report_budget(self):
        """
        Synchronizes this Financial Budget (`crossovered.budget`) with
        `DSL_HRMS_accounting`'s `account.report.budget` and `account.report.budget.item`
        so that P&L and Balance Sheet reports can compare Actual vs. Budget monthly.
        """
        ReportBudget = self.env['account.report.budget'].sudo()
        ReportBudgetItem = self.env['account.report.budget.item'].sudo()

        for budget in self:
            if not budget.report_budget_id:
                existing = ReportBudget.search([('name', '=', budget.name)], limit=1)
                if existing:
                    budget.report_budget_id = existing.id
                else:
                    rep_bdg = ReportBudget.create({
                        'name': budget.name,
                        'company_id': budget.company_id.id,
                    })
                    budget.report_budget_id = rep_bdg.id
            else:
                budget.report_budget_id.write({
                    'name': budget.name,
                    'company_id': budget.company_id.id,
                })

            # Clear previous synced items and regenerate monthly items
            budget.report_budget_id.item_ids.unlink()
            items_to_create = []

            for line in budget.crossovered_budget_line:
                accounts = line.general_budget_id.account_ids
                if not accounts or not line.date_from or not line.date_to:
                    continue

                # Determine months between date_from and date_to
                months = []
                cur = date(line.date_from.year, line.date_from.month, 1)
                end_month = date(line.date_to.year, line.date_to.month, 1)
                while cur <= end_month:
                    months.append(cur)
                    cur += relativedelta(months=1)

                if not months:
                    months = [date(line.date_from.year, line.date_from.month, 1)]

                total_amount = line.effective_amount
                per_month_per_account = total_amount / (len(months) * len(accounts))

                for m_date in months:
                    for acc in accounts:
                        items_to_create.append({
                            'budget_id': budget.report_budget_id.id,
                            'account_id': acc.id,
                            'date': m_date,
                            'amount': round(per_month_per_account, 2),
                        })

            if items_to_create:
                ReportBudgetItem.create(items_to_create)
        return True

    def action_open_report_budget(self):
        self.ensure_one()
        if not self.report_budget_id:
            self.action_sync_to_report_budget()
        return {
            'name': _('P&L Monthly Report Budget Sync'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.report.budget',
            'res_id': self.report_budget_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def _seed_default_budget_data(self):
        """
        Seeds realistic Budgetary Positions (`account.budget.post`),
        a Master Corporate Financial Budget (`crossovered.budget`),
        Cost Centers (`job.center`), and a sample Project Job Budget (`job.summary`)
        if none exist yet.
        """
        company = self.env.company
        Account = self.env['account.account'].sudo()
        BudgetPost = self.env['account.budget.post'].sudo()

        expense_accounts = Account.search([
            ('account_type', 'in', ('expense', 'expense_direct_cost', 'expense_depreciation')),
        ], limit=10)
        income_accounts = Account.search([
            ('account_type', 'in', ('income', 'income_other')),
        ], limit=5)
        any_accounts = Account.search([], limit=5)

        exp_accs = expense_accounts or any_accounts
        inc_accs = income_accounts or any_accounts

        if not exp_accs:
            return True

        positions_spec = [
            ('BP-REV-01', 'Operating Revenue & Export Sales', 'income', inc_accs[:2] or exp_accs[:1]),
            ('BP-EXP-01', 'Salaries, Wages & Employee Benefits (HR & Payroll)', 'expense', exp_accs[:2] or exp_accs[:1]),
            ('BP-EXP-02', 'Factory Operations, Utilities & Maintenance', 'expense', exp_accs[1:3] or exp_accs[:1]),
            ('BP-EXP-03', 'Administrative, IT & Office Expenses', 'expense', exp_accs[2:4] or exp_accs[:1]),
            ('BP-EXP-04', 'Asset Depreciation & Capital Overheads', 'expense', exp_accs[3:5] or exp_accs[:1]),
        ]

        created_posts = {}
        for code, name, btype, accs in positions_spec:
            post = BudgetPost.search([('code', '=', code)], limit=1)
            if not post and accs:
                post = BudgetPost.create({
                    'code': code,
                    'name': name,
                    'type': btype,
                    'company_id': company.id,
                    'account_ids': [(6, 0, accs.ids)],
                    'notes': f'Standard {name} budgetary position linked to GL accounts.',
                })
            if post:
                created_posts[code] = post

        if not self.sudo().search([], limit=1) and created_posts:
            d_from = date(2026, 1, 1)
            d_to = date(2026, 12, 31)
            master_budget = self.sudo().create({
                'name': 'DSL Enterprise Master Corporate Budget — FY 2026',
                'date_from': d_from,
                'date_to': d_to,
                'user_id': self.env.user.id,
                'company_id': company.id,
                'notes': '<p>Approved Annual Corporate Financial Budget covering Revenue, HR &amp; Payroll, Factory Operations, Administrative Overheads, and Asset Depreciation.</p>',
                'crossovered_budget_line': [
                    (0, 0, {
                        'general_budget_id': created_posts['BP-REV-01'].id,
                        'type': 'income',
                        'date_from': d_from,
                        'date_to': d_to,
                        'planned_amount': 120000000.0,
                        'revised_amount': 5000000.0,
                        'notes': 'Annual Export & Domestic Revenue Target',
                    }),
                    (0, 0, {
                        'general_budget_id': created_posts['BP-EXP-01'].id,
                        'type': 'expense',
                        'date_from': d_from,
                        'date_to': d_to,
                        'planned_amount': -48000000.0,
                        'revised_amount': -2000000.0,
                        'notes': 'Payroll, Festival Bonus, PF & Gratuity Allocation',
                    }),
                    (0, 0, {
                        'general_budget_id': created_posts['BP-EXP-02'].id,
                        'type': 'expense',
                        'date_from': d_from,
                        'date_to': d_to,
                        'planned_amount': -24000000.0,
                        'revised_amount': 0.0,
                        'notes': 'Gazipur Unit 1 & 2 Utilities, Fuel & Maintenance',
                    }),
                    (0, 0, {
                        'general_budget_id': created_posts['BP-EXP-03'].id,
                        'type': 'expense',
                        'date_from': d_from,
                        'date_to': d_to,
                        'planned_amount': -9600000.0,
                        'revised_amount': -400000.0,
                        'notes': 'HQ Admin, ERP/IT Infrastructure & Office Operations',
                    }),
                    (0, 0, {
                        'general_budget_id': created_posts['BP-EXP-04'].id,
                        'type': 'expense',
                        'date_from': d_from,
                        'date_to': d_to,
                        'planned_amount': -6000000.0,
                        'revised_amount': 0.0,
                        'notes': 'Monthly Fixed Asset Depreciation Provision',
                    }),
                ]
            })
            master_budget.action_budget_confirm()
            master_budget.action_budget_validate()

        # Seed Cost Centers & Sample Job Budget
        JobCenter = self.env['job.center'].sudo()
        centers_spec = [
            ('CC-HQ-01', 'Group HQ — Corporate & Finance'),
            ('CC-HR-02', 'Human Resources & Payroll Division'),
            ('CC-FAC-03', 'Gazipur Factory Unit 1 & 2 Operations'),
            ('CC-IT-04', 'IT & Digital Transformation Center'),
        ]
        first_center = False
        for c_code, c_name in centers_spec:
            center = JobCenter.search([('name', '=', c_name)], limit=1)
            if not center:
                center = JobCenter.create({
                    'code': c_code,
                    'name': c_name,
                    'manager_id': self.env.user.id,
                    'company_id': company.id,
                })
            if not first_center:
                first_center = center

        AmountApproval = self.env['amount.approval'].sudo()
        if not AmountApproval.search([('user', '=', self.env.user.id)], limit=1):
            AmountApproval.create({
                'user': self.env.user.id,
                'amount': 50000000.0,
                'company_id': company.id,
            })

        JobCreate = self.env['job.create'].sudo()
        JobSummary = self.env['job.summary'].sudo()
        Product = self.env['product.product'].sudo()
        sample_product = Product.search([], limit=1)
        if not sample_product:
            sample_product = Product.create({
                'name': 'Factory Machinery & Civil Setup Service',
                'type': 'service',
                'standard_price': 250000.0,
            })

        if first_center and not JobCreate.search([], limit=1):
            m_bdg = self.sudo().search([], limit=1)
            job = JobCreate.create({
                'job_description': 'Gazipur Unit-2 Production Line Modernization & Civil Setup',
                'cost_center_id': first_center.id,
                'crossovered_budget_id': m_bdg.id if m_bdg else False,
                'state': 'active',
            })
            job_bdg = JobSummary.create({
                'job_id': job.id,
                'cost_center': first_center.id,
                'crossovered_budget_id': m_bdg.id if m_bdg else False,
                'Date': date(2026, 1, 15),
                'start_date': date(2026, 1, 15),
                'end_date': date(2026, 6, 30),
                'item_ids': [
                    (0, 0, {
                        'product_id': sample_product.id,
                        'description': 'Phase-1 Industrial Wiring, Switchgear & Line Installation',
                        'unit_price': 250000.0,
                        'quantity': 4.0,
                    })
                ]
            })
            job_bdg.action_submit()
            job_bdg.action_approve()
        return True


class CrossoveredBudgetLines(models.Model):
    _name = "crossovered.budget.lines"
    _description = "Budget Line"
    _order = "crossovered_budget_id desc, date_from, id"

    name = fields.Char(compute='_compute_line_name', store=True)
    crossovered_budget_id = fields.Many2one(
        'crossovered.budget', 'Budget', ondelete='cascade', index=True, required=True
    )
    crossovered_budget_state = fields.Selection(
        related='crossovered_budget_id.state', string='Budget State', store=True, readonly=True
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account', 'Analytic Account'
    )
    department_id = fields.Many2one(
        'hr.department', 'Department',
        default=lambda self: self.env.context.get('default_department_id')
    )
    general_budget_id = fields.Many2one(
        'account.budget.post', 'Budgetary Position'
    )
    type = fields.Selection([
        ('expense', 'Expense'),
        ('income', 'Income'),
        ('profit_loss', 'Profit & Loss / Both'),
    ], string='Type', compute='_compute_line_type', store=True, readonly=False)
    date_from = fields.Date('Start Date', required=True)
    date_to = fields.Date('End Date', required=True)
    paid_date = fields.Date('Paid Date')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True
    )
    planned_amount = fields.Monetary(
        'Planned Amount', required=True, currency_field='currency_id', default=0.0,
        help="Initial planned amount. Use negative values for Expenses and positive values for Income, or positive values with Position Type = Expense."
    )
    revised_amount = fields.Monetary(
        'Revised / Supplementary', currency_field='currency_id', default=0.0,
        help="Additional budget allocation (+) or budget reduction (-) approved during the period."
    )
    effective_amount = fields.Monetary(
        'Effective Budget', compute='_compute_effective_amount', store=True,
        currency_field='currency_id',
        help="Total Effective Budget = Planned Amount + Revised Amount."
    )
    practical_amount = fields.Monetary(
        compute='_compute_practical_amount', string='Practical Amount',
        currency_field='currency_id',
        help="Actual amount spent/earned from posted Journal Entries and Analytic Lines."
    )
    theoritical_amount = fields.Monetary(
        compute='_compute_theoritical_amount', string='Theoretical Amount',
        currency_field='currency_id',
        help="Expected pro-rata amount up to today based on the budget period."
    )
    variance_amount = fields.Monetary(
        compute='_compute_percentage', string='Variance / Balance',
        currency_field='currency_id',
        help="Difference between Effective Budget and Practical Amount."
    )
    percentage = fields.Float(
        compute='_compute_percentage', string='Achievement (%)',
        help="Percentage of Practical Amount vs Effective Budget."
    )
    company_id = fields.Many2one(
        related='crossovered_budget_id.company_id', comodel_name='res.company',
        string='Company', store=True, readonly=True
    )
    is_above_budget = fields.Boolean(compute='_compute_is_above_budget', string='Exceeded Budget')
    notes = fields.Char('Remarks')

    @api.depends('general_budget_id', 'general_budget_id.type')
    def _compute_line_type(self):
        for line in self:
            if line.general_budget_id and line.general_budget_id.type:
                line.type = line.general_budget_id.type
            elif not line.type:
                line.type = 'expense'

    @api.depends('planned_amount', 'revised_amount')
    def _compute_effective_amount(self):
        for line in self:
            line.effective_amount = (line.planned_amount or 0.0) + (line.revised_amount or 0.0)

    @api.depends('crossovered_budget_id', 'general_budget_id', 'analytic_account_id')
    def _compute_line_name(self):
        for record in self:
            parts = []
            if record.crossovered_budget_id:
                parts.append(record.crossovered_budget_id.name)
            if record.general_budget_id:
                parts.append(record.general_budget_id.name)
            if record.analytic_account_id:
                parts.append(record.analytic_account_id.name)
            record.name = ' - '.join(parts) if parts else _('Budget Line')

    def _compute_is_above_budget(self):
        for line in self:
            if line.theoritical_amount >= 0:
                line.is_above_budget = line.practical_amount > line.theoritical_amount
            else:
                line.is_above_budget = line.practical_amount < line.theoritical_amount

    def _compute_practical_amount(self):
        """
        Odoo 18 compliant computation of `practical_amount` from:
        1) `account.analytic.line` when `analytic_account_id` is set on the budget line
        2) Posted `account.move.line` records for the accounts in `general_budget_id.account_ids`
           within `[date_from, date_to]`.
        Sign convention matches `effective_amount`:
        - In standard Odoo budgets, Expense planned amounts are negative (e.g. -100,000) and
          credit - debit on expense accounts is negative.
        - If a user enters a positive planned amount for an Expense budgetary position, we
          normalize the practical amount sign to match so comparison is always intuitive.
        """
        AnalyticLine = self.env['account.analytic.line']
        MoveLine = self.env['account.move.line']

        for line in self:
            date_from = line.date_from
            date_to = line.date_to
            acc_ids = line.general_budget_id.account_ids.ids
            if not date_from or not date_to:
                line.practical_amount = 0.0
                continue

            raw_amount = 0.0
            if line.analytic_account_id:
                domain = [
                    ('account_id', '=', line.analytic_account_id.id),
                    ('date', '>=', date_from),
                    ('date', '<=', date_to),
                ]
                if acc_ids:
                    domain.append(('general_account_id', 'in', acc_ids))
                analytic_lines = AnalyticLine.search(domain)
                raw_amount = sum(analytic_lines.mapped('amount'))
            elif acc_ids:
                domain = [
                    ('account_id', 'in', acc_ids),
                    ('date', '>=', date_from),
                    ('date', '<=', date_to),
                    ('parent_state', '=', 'posted'),
                    ('company_id', '=', line.company_id.id or self.env.company.id),
                ]
                move_lines = MoveLine.search(domain)
                # credit - debit: negative for expenses (debit > credit), positive for income (credit > debit)
                raw_amount = sum(move_lines.mapped('credit')) - sum(move_lines.mapped('debit'))

            # If user entered positive planned amount on an expense line, flip sign of net expense (debit - credit)
            if line.type == 'expense' and line.effective_amount > 0 and raw_amount < 0:
                line.practical_amount = abs(raw_amount)
            else:
                line.practical_amount = raw_amount

    def _compute_theoritical_amount(self):
        today = fields.Date.context_today(self)
        for line in self:
            if not line.date_from or not line.date_to:
                line.theoritical_amount = 0.0
                continue

            effective = line.effective_amount
            if line.paid_date:
                if today <= line.paid_date:
                    theo_amt = 0.0
                else:
                    theo_amt = effective
            else:
                line_timedelta = line.date_to - line.date_from
                elapsed_timedelta = today - line.date_from

                if elapsed_timedelta.days < 0:
                    theo_amt = 0.0
                elif line_timedelta.days > 0 and today < line.date_to:
                    ratio = (elapsed_timedelta.days + 1) / (line_timedelta.days + 1)
                    theo_amt = ratio * effective
                else:
                    theo_amt = effective
            line.theoritical_amount = round(theo_amt, 2)

    def _compute_percentage(self):
        for line in self:
            line.variance_amount = line.effective_amount - line.practical_amount
            if line.effective_amount != 0.0:
                line.percentage = round(float((line.practical_amount or 0.0) / line.effective_amount) * 100.0, 2)
            else:
                line.percentage = 0.0

    @api.constrains('general_budget_id', 'analytic_account_id')
    def _must_have_analytical_or_budgetary_or_both(self):
        for record in self:
            if not record.analytic_account_id and not record.general_budget_id:
                raise ValidationError(
                    _("You have to enter at least a Budgetary Position or an Analytic Account on a budget line.")
                )

    @api.constrains('date_from', 'date_to')
    def _line_dates_between_budget_dates(self):
        for rec in self:
            budget_date_from = rec.crossovered_budget_id.date_from
            budget_date_to = rec.crossovered_budget_id.date_to
            if rec.date_from and budget_date_from and rec.date_from < budget_date_from:
                raise ValidationError(
                    _('"Start Date" of the budget line should be included in the Period of the budget')
                )
            if rec.date_to and budget_date_to and rec.date_to > budget_date_to:
                raise ValidationError(
                    _('"End Date" of the budget line should be included in the Period of the budget')
                )

    def action_open_budget_entries(self):
        self.ensure_one()
        if self.analytic_account_id:
            action = self.env['ir.actions.act_window']._for_xml_id('analytic.account_analytic_line_action_entries')
            action['domain'] = [
                ('account_id', '=', self.analytic_account_id.id),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to)
            ]
            if self.general_budget_id:
                action['domain'] += [('general_account_id', 'in', self.general_budget_id.account_ids.ids)]
        else:
            action = self.env['ir.actions.act_window']._for_xml_id('account.action_account_moves_all_a')
            action['domain'] = [
                ('account_id', 'in', self.general_budget_id.account_ids.ids),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to)
            ]
        return action


class AccountAnalyticAccountInherit(models.Model):
    _inherit = "account.analytic.account"

    crossovered_budget_line = fields.One2many(
        'crossovered.budget.lines', 'analytic_account_id', 'Budget Lines'
    )
