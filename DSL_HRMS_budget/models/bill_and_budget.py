# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class AmountApproval(models.Model):
    _name = "amount.approval"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Budget & Bill Approval Authority Limit"
    _rec_name = "user"

    user = fields.Many2one('res.users', string="Approver User", required=True, tracking=True)
    amount = fields.Float(string="Max Approval Limit (BDT)", required=True, tracking=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_user_company', 'unique ("user", company_id)', 'This User already has an Approval Authority limit configured!')
    ]

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Approval limit amount must be greater than 0!'))


class JobCenter(models.Model):
    _name = "job.center"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Cost Center / Budget Center"

    name = fields.Char(string="Cost Center Name", required=True, tracking=True)
    code = fields.Char(string="Code", tracking=True)
    department_id = fields.Many2one('hr.department', string="Department")
    manager_id = fields.Many2one('res.users', string="Cost Center Manager")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_cost_center_name', 'unique (name, company_id)', 'This Cost Center already exists!')
    ]


class JobCreate(models.Model):
    _name = "job.create"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Budget Job / Project Activity"
    _rec_name = "job_no"
    _order = "id desc"

    job_no = fields.Char(
        string="Job / Project Code", required=True, readonly=True, copy=False,
        default=lambda self: _('New'), tracking=True
    )
    job_description = fields.Char(string="Job / Project Title", required=True, tracking=True)
    cost_center_id = fields.Many2one('job.center', string="Cost Center", tracking=True)
    department_id = fields.Many2one('hr.department', string="Department", tracking=True)
    crossovered_budget_id = fields.Many2one('crossovered.budget', string="Linked Financial Budget")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    ], string="Status", default='active', tracking=True)

    budget_count = fields.Integer(string="Budgets", compute="_compute_counts")
    advance_count = fields.Integer(string="Advances", compute="_compute_counts")
    bill_count = fields.Integer(string="Bill Adjustments", compute="_compute_counts")
    work_order_count = fields.Integer(string="Work Orders", compute="_compute_counts")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('job_no', _('New')) == _('New'):
                vals['job_no'] = self.env['ir.sequence'].next_by_code('job.create') or _('New')
        return super().create(vals_list)

    def _compute_counts(self):
        JobSummary = self.env['job.summary']
        CostAdvance = self.env['cost.advance']
        BillAdjustment = self.env['bill.adjustment']
        WorkOrder = self.env['work.order']
        for rec in self:
            rec.budget_count = JobSummary.search_count([('job_id', '=', rec.id)])
            rec.advance_count = CostAdvance.search_count([('job_id', '=', rec.id)])
            rec.bill_count = BillAdjustment.search_count([('job_id', '=', rec.id)])
            rec.work_order_count = WorkOrder.search_count([('job_id', '=', rec.id)])

    def action_open_job_budgets(self):
        self.ensure_one()
        return {
            'name': _('Job Budgets'),
            'type': 'ir.actions.act_window',
            'res_model': 'job.summary',
            'view_mode': 'list,form',
            'domain': [('job_id', '=', self.id)],
            'context': {'default_job_id': self.id, 'default_cost_center': self.cost_center_id.id},
        }

    def action_open_job_advances(self):
        self.ensure_one()
        return {
            'name': _('Advance Requests'),
            'type': 'ir.actions.act_window',
            'res_model': 'cost.advance',
            'view_mode': 'list,form',
            'domain': [('job_id', '=', self.id)],
            'context': {'default_job_id': self.id, 'default_cost_center': self.cost_center_id.id},
        }

    def action_open_job_bills(self):
        self.ensure_one()
        return {
            'name': _('Bill Adjustments'),
            'type': 'ir.actions.act_window',
            'res_model': 'bill.adjustment',
            'view_mode': 'list,form',
            'domain': [('job_id', '=', self.id)],
            'context': {'default_job_id': self.id, 'default_cost_center': self.cost_center_id.id},
        }

    def action_open_work_orders(self):
        self.ensure_one()
        return {
            'name': _('Work Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'work.order',
            'view_mode': 'list,form',
            'domain': [('job_id', '=', self.id)],
            'context': {'default_job_id': self.id},
        }


class JobSummary(models.Model):
    _name = "job.summary"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Cost Center / Project Job Budget & Re-Budget"
    _rec_name = "code"
    _order = "id desc"

    code = fields.Char(
        string="Budget Code", readonly=True, required=True, copy=False,
        default=lambda self: _('New'), tracking=True
    )
    job_id = fields.Many2one('job.create', string="Job / Project", required=True, tracking=True)
    job_description = fields.Char(related='job_id.job_description', string="Job Description", readonly=True)
    cost_center = fields.Many2one('job.center', string="Cost Center", required=True, tracking=True)
    department_id = fields.Many2one('hr.department', string="Department", tracking=True)
    crossovered_budget_id = fields.Many2one('crossovered.budget', string="Corporate Financial Budget")
    Date = fields.Date(string="Budget Date", default=fields.Date.context_today, required=True, tracking=True)
    start_date = fields.Date(string="Execution Start Date")
    end_date = fields.Date(string="Execution End Date")
    expected_revenue = fields.Float(string="Expected Revenue / Target Value")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)

    item_ids = fields.One2many('job.summary.items', 'item_id', string="Budget Items", copy=True)
    approver_ids = fields.One2many('job.summary.approver', 'item_id', string="Approval Chain")
    additional_item_ids = fields.One2many('job.summary.additional.item', 'budget_id', string="Re-Budget / Supplementary Items")
    additional_approver_ids = fields.One2many('job.summary.additional.approver', 'item_id', string="Re-Budget Approvers")

    total = fields.Float(string="Initial Budget Total", compute="_compute_totals", store=True)
    additional_total = fields.Float(string="Supplementary Re-Budget", compute="_compute_totals", store=True)
    grand_total = fields.Float(string="Total Approved Budget", compute="_compute_totals", store=True)
    remaining_budget = fields.Float(string="Remaining Available Budget", compute="_compute_totals", store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submitted'),
        ('approve', 'Approved'),
        ('re_budget', 'Re-Budget Draft'),
        ('re_budget_submit', 'Re-Budget Submitted'),
        ('cancel', 'Cancelled'),
    ], string="Status", default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('New')) == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code('job.summary') or _('New')
        return super().create(vals_list)

    @api.depends(
        'item_ids.total', 'item_ids.remaining_amount',
        'additional_item_ids.additional_total', 'additional_item_ids.state'
    )
    def _compute_totals(self):
        for rec in self:
            initial = sum(rec.item_ids.mapped('total'))
            add_approved = sum(
                rec.additional_item_ids.filtered(lambda a: a.state == 'approve').mapped('additional_total')
            )
            rec.total = initial
            rec.additional_total = add_approved
            rec.grand_total = initial + add_approved
            rec.remaining_budget = sum(rec.item_ids.mapped('remaining_amount'))

    def action_submit(self):
        for rec in self:
            if not rec.item_ids:
                raise ValidationError(_("Please add at least one Budget Line Item before submitting!"))
            rec.state = 'submit'

    def action_approve(self):
        for rec in self:
            rec.state = 'approve'
            rec.env['job.summary.approver'].create({
                'item_id': rec.id,
                'approver': self.env.user.id,
                'approval_status': 'approved',
                'date_time': fields.Datetime.now(),
            })

    def action_re_budget(self):
        self.write({'state': 're_budget'})

    def action_re_budget_submit(self):
        for rec in self:
            pending = rec.additional_item_ids.filtered(lambda l: l.state == 'draft')
            if not pending:
                raise ValidationError(_("Please add at least one Re-Budget / Supplementary item!"))
            rec.state = 're_budget_submit'

    def action_re_budget_approve(self):
        for rec in self:
            for add_line in rec.additional_item_ids.filtered(lambda l: l.state == 'draft'):
                # Merge supplementary quantity/amount into matching item or create a new item
                existing_line = rec.item_ids.filtered(lambda i: i.product_id == add_line.product_id)[:1]
                if existing_line:
                    existing_line.additional_quantity += add_line.additional_quantity
                    existing_line.additional_total += add_line.additional_total
                else:
                    self.env['job.summary.items'].create({
                        'item_id': rec.id,
                        'product_id': add_line.product_id.id,
                        'description': add_line.description,
                        'unit_price': add_line.unit_price,
                        'quantity': 0.0,
                        'additional_quantity': add_line.additional_quantity,
                        'additional_total': add_line.additional_total,
                    })
                add_line.state = 'approve'
            rec.state = 'approve'
            rec.env['job.summary.additional.approver'].create({
                'item_id': rec.id,
                'approver': self.env.user.id,
                'approval_status': 'approved',
                'date_time': fields.Datetime.now(),
            })

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class JobSummaryItems(models.Model):
    _name = "job.summary.items"
    _description = "Job Budget Line Item"
    _rec_name = "product_id"

    item_id = fields.Many2one('job.summary', string="Job Budget", ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Budget Head / Item", required=True)
    account_id = fields.Many2one(
        'account.account', string="Expense Account",
        related='product_id.property_account_expense_id', readonly=True
    )
    description = fields.Char(string="Specification / Remarks")
    unit_price = fields.Float(string="Unit Rate", required=True, default=0.0)
    quantity = fields.Float(string="Initial Qty", required=True, default=1.0)
    total = fields.Float(string="Initial Budget", compute="_compute_amounts", store=True)

    additional_quantity = fields.Float(string="Re-Budget Qty", default=0.0, readonly=True)
    additional_total = fields.Float(string="Re-Budget Amount", default=0.0, readonly=True)

    effective_total = fields.Float(string="Effective Budget", compute="_compute_amounts", store=True)
    spent_amount = fields.Float(string="Billed / Adjusted", default=0.0, readonly=True)
    remaining_quantity = fields.Float(string="Remaining Qty", compute="_compute_amounts", store=True)
    remaining_amount = fields.Float(string="Remaining Balance", compute="_compute_amounts", store=True)

    @api.depends('unit_price', 'quantity', 'additional_quantity', 'additional_total', 'spent_amount')
    def _compute_amounts(self):
        for rec in self:
            rec.total = rec.unit_price * rec.quantity
            rec.effective_total = rec.total + rec.additional_total
            rec.remaining_quantity = (rec.quantity + rec.additional_quantity)
            rec.remaining_amount = rec.effective_total - rec.spent_amount


class JobSummaryApprover(models.Model):
    _name = "job.summary.approver"
    _description = "Job Budget Approval Log"

    item_id = fields.Many2one('job.summary', string="Job Budget", ondelete='cascade')
    approver = fields.Many2one('res.users', string="Approved By", readonly=True)
    approval_status = fields.Selection([
        ('approved', 'Approved'),
        ('cancelled', 'Cancelled'),
    ], string="Decision", readonly=True)
    date_time = fields.Datetime(string="Timestamp", readonly=True)


class JobSummaryAdditionalItem(models.Model):
    _name = "job.summary.additional.item"
    _description = "Supplementary Re-Budget Item"

    budget_id = fields.Many2one('job.summary', string="Job Budget", ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Budget Head / Item", required=True)
    description = fields.Char(string="Reason for Re-Budget")
    unit_price = fields.Float(string="Unit Rate", required=True, default=0.0)
    additional_quantity = fields.Float(string="Additional Qty", required=True, default=1.0)
    additional_total = fields.Float(string="Additional Amount", compute="_compute_additional_total", store=True)
    state = fields.Selection([
        ('draft', 'Pending'),
        ('approve', 'Approved'),
    ], string="Status", default='draft', readonly=True)

    @api.depends('unit_price', 'additional_quantity')
    def _compute_additional_total(self):
        for rec in self:
            rec.additional_total = rec.unit_price * rec.additional_quantity


class JobSummaryAdditionalApprover(models.Model):
    _name = "job.summary.additional.approver"
    _description = "Re-Budget Approval Log"

    item_id = fields.Many2one('job.summary', string="Job Budget", ondelete='cascade')
    approver = fields.Many2one('res.users', string="Approved By", readonly=True)
    approval_status = fields.Selection([
        ('approved', 'Approved'),
        ('cancelled', 'Cancelled'),
    ], string="Decision", readonly=True)
    date_time = fields.Datetime(string="Timestamp", readonly=True)


class WorkOrder(models.Model):
    _name = "work.order"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Budget Work Order"
    _rec_name = "work_order"
    _order = "id desc"

    work_order = fields.Char(
        string="Work Order No", readonly=True, required=True, copy=False,
        default=lambda self: _('New'), tracking=True
    )
    budget_id = fields.Many2one(
        'job.summary', string="Job Budget", required=True,
        domain=[('state', '=', 'approve')], tracking=True
    )
    job_id = fields.Many2one(related='budget_id.job_id', string="Job / Project", store=True, readonly=True)
    vendor_id = fields.Many2one('res.partner', string="Contractor / Vendor", tracking=True)
    date = fields.Date(string="Order Date", default=fields.Date.context_today, required=True)
    subject = fields.Char(string="Subject", required=True)
    terms_conditions = fields.Text(string="Terms & Conditions")
    item_ids = fields.One2many('work.order.items', 'item_id', string="Work Order Items")
    total_amount = fields.Float(string="Total Order Value", compute="_compute_total_amount", store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Issued'),
        ('done', 'Completed'),
        ('cancel', 'Cancelled'),
    ], string="Status", default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('work_order', _('New')) == _('New'):
                vals['work_order'] = self.env['ir.sequence'].next_by_code('work.order') or _('New')
        return super().create(vals_list)

    @api.depends('item_ids.total')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(rec.item_ids.mapped('total'))

    def action_confirm(self):
        self.write({'state': 'confirm'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})


class WorkOrderItems(models.Model):
    _name = "work.order.items"
    _description = "Work Order Line Item"

    item_id = fields.Many2one('work.order', string="Work Order", ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Work / Item", required=True)
    description = fields.Char(string="Work Specification")
    unit_price = fields.Float(string="Unit Rate", required=True, default=0.0)
    quantity = fields.Float(string="Quantity", required=True, default=1.0)
    total = fields.Float(string="Total", compute="_compute_total", store=True)

    @api.depends('unit_price', 'quantity')
    def _compute_total(self):
        for rec in self:
            rec.total = rec.unit_price * rec.quantity


class CostAdvance(models.Model):
    _name = "cost.advance"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Budget Cost Advance Request"
    _rec_name = "advance_code"
    _order = "id desc"

    advance_code = fields.Char(
        string="Advance Ref", readonly=True, required=True, copy=False,
        default=lambda self: _('New'), tracking=True
    )
    advance_type = fields.Selection([
        ('job', 'Against Approved Job Budget'),
        ('other', 'General / Direct Advance'),
    ], string="Advance Type", default='job', required=True, tracking=True)
    budget_id = fields.Many2one(
        'job.summary', string="Job Budget",
        domain=[('state', '=', 'approve')], tracking=True
    )
    job_id = fields.Many2one('job.create', string="Job / Project", tracking=True)
    cost_center = fields.Many2one('job.center', string="Cost Center", required=True, tracking=True)
    employee_id = fields.Many2one('hr.employee', string="Requested By (Employee)", tracking=True)
    payee_name = fields.Many2one('res.partner', string="Payee / Vendor", tracking=True)
    date = fields.Date(string="Request Date", default=fields.Date.context_today, required=True)
    total = fields.Float(string="Total Advance Requested", compute="_compute_total", store=True)
    item_ids = fields.One2many('cost.advance.items', 'item_id', string="Advance Items")
    approver_ids = fields.One2many('cost.advance.approver', 'item_id', string="Approval Log")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submitted'),
        ('approve', 'Approved'),
        ('cancel', 'Cancelled'),
    ], string="Status", default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('advance_code', _('New')) == _('New'):
                vals['advance_code'] = self.env['ir.sequence'].next_by_code('cost.advance') or _('New')
        return super().create(vals_list)

    @api.onchange('budget_id')
    def _onchange_budget_id(self):
        if self.budget_id:
            self.job_id = self.budget_id.job_id
            self.cost_center = self.budget_id.cost_center

    @api.depends('item_ids.advance_amount')
    def _compute_total(self):
        for rec in self:
            rec.total = sum(rec.item_ids.mapped('advance_amount'))

    def action_submit(self):
        for rec in self:
            if rec.total <= 0:
                raise ValidationError(_("Total Advance amount must be greater than 0!"))
            rec.state = 'submit'

    def action_approve(self):
        for rec in self:
            rec.state = 'approve'
            self.env['cost.advance.approver'].create({
                'item_id': rec.id,
                'approver': self.env.user.id,
                'approval_status': 'approved',
                'date_time': fields.Datetime.now(),
            })
            # Auto-record in Approved Advance Summary
            self.env['approve.advance.summary'].create({
                'advance_id': rec.id,
                'job_id': rec.job_id.id,
                'budget_id': rec.budget_id.id,
                'cost_center': rec.cost_center.id,
                'approve_date': fields.Date.context_today(self),
                'total': rec.total,
            })

    def action_cancel(self):
        self.write({'state': 'cancel'})


class CostAdvanceItems(models.Model):
    _name = "cost.advance.items"
    _description = "Cost Advance Line Item"

    item_id = fields.Many2one('cost.advance', string="Advance Request", ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Expense Head / Item", required=True)
    description = fields.Char(string="Purpose / Remarks")
    budget_balance = fields.Float(string="Budget Balance", compute="_compute_budget_balance")
    advance_amount = fields.Float(string="Advance Amount", required=True, default=0.0)

    @api.depends('product_id', 'item_id.budget_id')
    def _compute_budget_balance(self):
        for rec in self:
            if rec.item_id.budget_id and rec.product_id:
                b_line = rec.item_id.budget_id.item_ids.filtered(lambda l: l.product_id == rec.product_id)[:1]
                rec.budget_balance = b_line.remaining_amount if b_line else 0.0
            else:
                rec.budget_balance = 0.0


class CostAdvanceApprover(models.Model):
    _name = "cost.advance.approver"
    _description = "Cost Advance Approval Log"

    item_id = fields.Many2one('cost.advance', string="Advance Request", ondelete='cascade')
    approver = fields.Many2one('res.users', string="Approved By", readonly=True)
    approval_status = fields.Selection([
        ('approved', 'Approved'),
        ('cancelled', 'Cancelled'),
    ], string="Decision", readonly=True)
    date_time = fields.Datetime(string="Timestamp", readonly=True)


class ApproveAdvanceSummary(models.Model):
    _name = "approve.advance.summary"
    _description = "Approved Advance Register"
    _rec_name = "advance_id"
    _order = "id desc"

    advance_id = fields.Many2one('cost.advance', string="Advance Reference", readonly=True)
    job_id = fields.Many2one('job.create', string="Job / Project", readonly=True)
    budget_id = fields.Many2one('job.summary', string="Job Budget", readonly=True)
    cost_center = fields.Many2one('job.center', string="Cost Center", readonly=True)
    approve_date = fields.Date(string="Approved Date", readonly=True)
    total = fields.Float(string="Approved Advance Amount", readonly=True)
    adjusted_amount = fields.Float(string="Adjusted in Bills", default=0.0, readonly=True)
    unadjusted_balance = fields.Float(string="Unadjusted Balance", compute="_compute_unadjusted", store=True)

    @api.depends('total', 'adjusted_amount')
    def _compute_unadjusted(self):
        for rec in self:
            rec.unadjusted_balance = rec.total - rec.adjusted_amount


class BillAdjustment(models.Model):
    _name = "bill.adjustment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Bill & Budget Adjustment (with Vendor Bill Generation)"
    _rec_name = "bill"
    _order = "id desc"

    bill = fields.Char(
        string="Bill Adjustment No", readonly=True, required=True, copy=False,
        default=lambda self: _('New'), tracking=True
    )
    bill_type = fields.Selection([
        ('with_budget', 'Against Approved Job Budget'),
        ('without_budget', 'Direct Expense / Without Job Budget'),
    ], string="Adjustment Mode", default='with_budget', required=True, tracking=True)
    budget_id = fields.Many2one(
        'job.summary', string="Job Budget",
        domain=[('state', '=', 'approve')], tracking=True
    )
    job_id = fields.Many2one('job.create', string="Job / Project", tracking=True)
    cost_center = fields.Many2one('job.center', string="Cost Center", required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string="Vendor / Payee", required=True, tracking=True)
    advance_summary_id = fields.Many2one(
        'approve.advance.summary', string="Adjust Against Advance"
    )
    date = fields.Date(string="Adjustment Date", default=fields.Date.context_today, required=True)
    item_ids = fields.One2many('bill.adjustment.items', 'item_id', string="Bill Line Items")
    approver_ids = fields.One2many('bill.adjustment.approver', 'item_id', string="Approval Log")
    total_amount = fields.Float(string="Total Bill Amount", compute="_compute_totals", store=True)
    advance_adjusted = fields.Float(string="Advance Adjusted", default=0.0)
    net_payable = fields.Float(string="Net Payable / Receivable", compute="_compute_totals", store=True)
    vendor_bill_id = fields.Many2one('account.move', string="Generated Vendor Bill", readonly=True, copy=False)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submitted'),
        ('approve', 'Approved'),
        ('billed', 'Vendor Bill Created'),
        ('cancel', 'Cancelled'),
    ], string="Status", default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('bill', _('New')) == _('New'):
                vals['bill'] = self.env['ir.sequence'].next_by_code('bill.adjustment') or _('New')
        return super().create(vals_list)

    @api.onchange('budget_id')
    def _onchange_budget_id(self):
        if self.budget_id:
            self.job_id = self.budget_id.job_id
            self.cost_center = self.budget_id.cost_center

    @api.depends('item_ids.total', 'advance_adjusted')
    def _compute_totals(self):
        for rec in self:
            total = sum(rec.item_ids.mapped('total'))
            rec.total_amount = total
            rec.net_payable = total - rec.advance_adjusted

    def action_submit(self):
        for rec in self:
            if not rec.item_ids:
                raise ValidationError(_("Please add at least one Bill Item before submitting!"))
            rec.state = 'submit'

    def action_approve(self):
        for rec in self:
            # Update spent_amount on linked Job Budget lines
            if rec.budget_id:
                for line in rec.item_ids:
                    b_line = rec.budget_id.item_ids.filtered(lambda b: b.product_id == line.product_id)[:1]
                    if b_line:
                        if line.total > b_line.remaining_amount:
                            raise ValidationError(
                                _("Bill item '%s' (%.2f) exceeds remaining budget balance (%.2f)! Please request a Re-Budget first.")
                                % (line.product_id.display_name, line.total, b_line.remaining_amount)
                            )
                        b_line.spent_amount += line.total

            if rec.advance_summary_id and rec.advance_adjusted > 0:
                rec.advance_summary_id.adjusted_amount += rec.advance_adjusted

            rec.state = 'approve'
            self.env['bill.adjustment.approver'].create({
                'item_id': rec.id,
                'approver': self.env.user.id,
                'approval_status': 'approved',
                'date_time': fields.Datetime.now(),
            })

    def action_create_vendor_bill(self):
        """Creates an Accounting Vendor Bill (`account.move` with `move_type='in_invoice'`) directly."""
        self.ensure_one()
        if self.vendor_bill_id:
            return {
                'name': _('Vendor Bill'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': self.vendor_bill_id.id,
                'view_mode': 'form',
            }

        invoice_lines = []
        for item in self.item_ids:
            account = item.account_id or item.product_id.property_account_expense_id
            line_vals = {
                'product_id': item.product_id.id,
                'name': item.description or item.product_id.display_name,
                'quantity': item.quantity,
                'price_unit': item.unit_price,
            }
            if account:
                line_vals['account_id'] = account.id
            invoice_lines.append((0, 0, line_vals))

        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': self.date,
            'date': self.date,
            'ref': self.bill,
            'bill_adjustment_id': self.id,
            'invoice_line_ids': invoice_lines,
        })
        self.vendor_bill_id = move.id
        self.state = 'billed'
        return {
            'name': _('Vendor Bill'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
        }

    def action_cancel(self):
        self.write({'state': 'cancel'})


class BillAdjustmentItems(models.Model):
    _name = "bill.adjustment.items"
    _description = "Bill Adjustment Line Item"

    item_id = fields.Many2one('bill.adjustment', string="Bill Adjustment", ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Expense Head / Item", required=True)
    account_id = fields.Many2one('account.account', string="GL Expense Account")
    description = fields.Char(string="Particulars / Invoice Ref")
    unit_price = fields.Float(string="Unit Price", required=True, default=0.0)
    quantity = fields.Float(string="Quantity", required=True, default=1.0)
    total = fields.Float(string="Total Amount", compute="_compute_total", store=True)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.account_id = self.product_id.property_account_expense_id

    @api.depends('unit_price', 'quantity')
    def _compute_total(self):
        for rec in self:
            rec.total = rec.unit_price * rec.quantity


class BillAdjustmentApprover(models.Model):
    _name = "bill.adjustment.approver"
    _description = "Bill Adjustment Approval Log"

    item_id = fields.Many2one('bill.adjustment', string="Bill Adjustment", ondelete='cascade')
    approver = fields.Many2one('res.users', string="Approved By", readonly=True)
    approval_status = fields.Selection([
        ('approved', 'Approved'),
        ('cancelled', 'Cancelled'),
    ], string="Decision", readonly=True)
    date_time = fields.Datetime(string="Timestamp", readonly=True)


class AccountMoveBudgetInherit(models.Model):
    _inherit = "account.move"

    bill_adjustment_id = fields.Many2one('bill.adjustment', string="Source Bill Adjustment", readonly=True)
