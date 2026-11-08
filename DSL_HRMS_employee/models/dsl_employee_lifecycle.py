# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


# =============================================================================
# 1. EMPLOYEE CONTACT & ADDRESS DIRECTORY (`dsl.employee.contact`)
# =============================================================================
class DslEmployeeContact(models.Model):
    _name = 'dsl.employee.contact'
    _description = 'Employee Address & Contact Directory (Present, Permanent, Bangla)'
    _order = 'is_primary desc, address_type asc, id asc'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='employee_id.company_id',
        store=True,
        readonly=True,
    )
    address_type = fields.Selection(
        selection=[
            ('present', 'Present / Mailing Address (বর্তমান ঠিকানা)'),
            ('permanent', 'Permanent / NID Address (স্থায়ী ঠিকানা)'),
            ('overseas', 'Alternate / Hometown Address'),
        ],
        string='Address Type',
        default='present',
        required=True,
    )
    village_house = fields.Char(string='House / Road / Village (EN)', required=True)
    address_bn = fields.Char(string='ঠিকানা (বাংলায়)')
    post_office = fields.Char(string='Post Office')
    thana_upazila = fields.Char(string='Thana / Upazila')
    district = fields.Char(string='District')
    postcode = fields.Char(string='Post Code')
    mobile = fields.Char(string='Contact Mobile')
    email = fields.Char(string='Contact Email')
    is_primary = fields.Boolean(string='Primary', default=True)

    def _sync_to_odoo_employee_address(self):
        for rec in self.sudo():
            if not rec.employee_id or not rec.is_primary or rec.address_type != 'present':
                continue
            vals = {}
            if rec.village_house:
                vals['private_street'] = rec.village_house
            if rec.thana_upazila:
                vals['private_street2'] = rec.thana_upazila
            if rec.district:
                vals['private_city'] = rec.district
            if rec.postcode:
                vals['private_zip'] = rec.postcode
            if vals:
                try:
                    rec.employee_id.sudo().write(vals)
                except Exception:
                    pass

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_to_odoo_employee_address()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._sync_to_odoo_employee_address()
        return res


# =============================================================================
# 2. EMPLOYEE EMERGENCY CONTACTS (`dsl.employee.emergency`)
# =============================================================================
class DslEmployeeEmergency(models.Model):
    _name = 'dsl.employee.emergency'
    _description = 'Employee Emergency Contact Person (ICE)'
    _order = 'is_primary desc, id asc'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='employee_id.company_id',
        store=True,
        readonly=True,
    )
    name = fields.Char(string='Contact Person Name', required=True)
    name_bn = fields.Char(string='জরুরি যোগাযোগের নাম (বাংলায়)')
    relationship = fields.Selection(
        selection=[
            ('spouse', 'Spouse (স্বামী / স্ত্রী)'),
            ('father', 'Father (পিতা)'),
            ('mother', 'Mother (মাতা)'),
            ('sibling', 'Brother / Sister (ভাই / বোন)'),
            ('child', 'Son / Daughter (সন্তান)'),
            ('relative', 'Relative / Guardian (আত্মীয় / অভিভাবক)'),
            ('friend', 'Colleague / Friend'),
        ],
        string='Relationship',
        default='spouse',
        required=True,
    )
    phone = fields.Char(string='Primary Mobile', required=True)
    alt_phone = fields.Char(string='Alternate Phone')
    address = fields.Char(string='Address / Location')
    is_primary = fields.Boolean(string='Primary ICE', default=True)

    def _sync_to_odoo_emergency_fields(self):
        for rec in self.sudo():
            if rec.employee_id and rec.is_primary:
                try:
                    rec.employee_id.sudo().write({
                        'emergency_contact': rec.name,
                        'emergency_phone': rec.phone,
                    })
                except Exception:
                    pass

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_to_odoo_emergency_fields()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._sync_to_odoo_emergency_fields()
        return res


# =============================================================================
# 3. IMMUTABLE EMPLOYMENT & PLACEMENT HISTORY (`dsl.employee.job.history`)
#    Preserves historical Company, Branch, Department, Designation & Grade
# =============================================================================
class DslEmployeeJobHistory(models.Model):
    _name = 'dsl.employee.job.history'
    _description = 'Employee Organizational Placement & Job History'
    _order = 'is_current desc, effective_from desc, id desc'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company / Legal Entity',
        required=True,
        default=lambda self: self.env.company,
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Branch / Plant',
        domain="[('company_id', '=', company_id)]",
    )
    department_id = fields.Many2one('hr.department', string='Department')
    job_id = fields.Many2one('hr.job', string='Designation')
    grade_id = fields.Many2one('dsl.hr.grade', string='Pay Grade')
    employment_category = fields.Selection(
        selection=[
            ('permanent', 'Permanent (স্থায়ী)'),
            ('probation', 'Probationary (শিক্ষানবিশ)'),
            ('contractual', 'Contractual (চুক্তিভিত্তিক)'),
            ('intern', 'Intern / Apprentice (ইন্টার্ন)'),
            ('casual', 'Casual / Daily Basis (দৈনিক ভিত্তিক)'),
            ('consultant', 'Consultant / Advisor (পরামর্শক)'),
        ],
        string='Job Type',
        default='permanent',
    )
    manager_id = fields.Many2one('hr.employee', string='Reporting Manager')
    cost_center_id = fields.Many2one('dsl.cost.center', string='Cost Center')
    effective_from = fields.Date(
        string='Effective From',
        required=True,
        default=fields.Date.context_today,
    )
    effective_to = fields.Date(string='Effective Until')
    change_reason = fields.Selection(
        selection=[
            ('joining', 'Initial Joining (প্রথম যোগদান)'),
            ('confirmation', 'Post-Probation Confirmation (স্থায়ীকরণ)'),
            ('promotion', 'Promotion / Elevation (পদোন্নতি)'),
            ('transfer', 'Transfer / Deputation (বদলি)'),
            ('redesignation', 'Redesignation / Restructure'),
        ],
        string='Event Type',
        default='joining',
        required=True,
    )
    is_current = fields.Boolean(string='Current Placement', default=True)
    remarks = fields.Char(string='Order Ref / Notes')


# =============================================================================
# 4. EMPLOYMENT CONTRACT HISTORY (`dsl.employee.contract`)
# =============================================================================
class DslEmployeeContract(models.Model):
    _name = 'dsl.employee.contract'
    _description = 'Employee Employment Contract & Probation History'
    _order = 'date_start desc, id desc'

    name = fields.Char(
        string='Contract Ref.',
        required=True,
        default=lambda self: _('CNT-NEW'),
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='employee_id.company_id',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True,
    )
    contract_type = fields.Selection(
        selection=[
            ('probation', 'Probationary Appointment (Sec 4)'),
            ('permanent', 'Confirmed Permanent Employment'),
            ('fixed_term', 'Fixed-Term Contractual Agreement'),
            ('consultant', 'Retainer / Advisory Contract'),
            ('intern', 'Internship / Apprenticeship'),
        ],
        string='Contract Type',
        default='permanent',
        required=True,
    )
    date_start = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.context_today,
    )
    date_end = fields.Date(string='End Date')
    probation_months = fields.Integer(string='Probation (Months)', default=6)
    confirmation_date = fields.Date(string='Confirmation Date')
    notice_period_days = fields.Integer(string='Notice Period (Days)', default=60)
    contract_gross = fields.Monetary(
        string='Contract Gross (৳)',
        currency_field='currency_id',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active / Running'),
            ('expired', 'Completed / Renewed'),
            ('terminated', 'Terminated'),
        ],
        string='Status',
        default='active',
        required=True,
    )
    notes = fields.Char(string='Key Terms / Clauses')
    odoo_contract_id = fields.Many2one(
        'hr.contract',
        string='Odoo HR Contract',
        ondelete='set null',
        help='Automatically synchronized native Odoo hr.contract record.',
    )

    def _sync_to_odoo_hr_contract(self):
        if self.env.context.get('skip_dsl_contract_sync') or 'hr.contract' not in self.env:
            return
        HrContract = self.env['hr.contract'].sudo().with_context(skip_dsl_contract_sync=True)
        state_map = {
            'draft': 'draft',
            'active': 'open',
            'expired': 'close',
            'terminated': 'cancel',
        }
        for rec in self.sudo():
            if not rec.employee_id:
                continue
            emp = rec.employee_id
            comp_id = (emp.company_id or self.env.company).id
            vals = {
                'name': rec.name or f"Contract - {emp.name}",
                'employee_id': emp.id,
                'company_id': comp_id,
                'department_id': emp.department_id.id if emp.department_id else False,
                'job_id': emp.job_id.id if emp.job_id else False,
                'date_start': rec.date_start or fields.Date.context_today(self),
                'date_end': rec.date_end or False,
                'trial_date_end': rec.confirmation_date or False,
                'wage': rec.contract_gross or getattr(emp, 'ot_gross_reference', 0.0) or 0.0,
                'state': state_map.get(rec.state, 'open'),
                'notes': rec.notes or False,
            }
            if 'dsl_contract_id' in HrContract._fields:
                vals['dsl_contract_id'] = rec.id
            if 'branch_id' in HrContract._fields and emp.branch_id:
                vals['branch_id'] = emp.branch_id.id

            if rec.odoo_contract_id:
                rec.odoo_contract_id.sudo().with_context(skip_dsl_contract_sync=True).write(vals)
            else:
                existing = HrContract.search([
                    ('employee_id', '=', emp.id),
                    ('date_start', '=', vals['date_start']),
                ], limit=1)
                if not existing and rec.state == 'active':
                    existing = HrContract.search([
                        ('employee_id', '=', emp.id),
                        ('state', '=', 'open'),
                    ], limit=1)
                if existing:
                    existing.write(vals)
                    rec.with_context(skip_dsl_contract_sync=True).write({'odoo_contract_id': existing.id})
                else:
                    created = HrContract.create(vals)
                    rec.with_context(skip_dsl_contract_sync=True).write({'odoo_contract_id': created.id})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_to_odoo_hr_contract()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_dsl_contract_sync'):
            self._sync_to_odoo_hr_contract()
        return res


class HrContractDslExt(models.Model):
    _inherit = 'hr.contract'

    dsl_contract_id = fields.Many2one(
        'dsl.employee.contract',
        string='DSL Employment Contract',
        ondelete='set null',
    )
    branch_id = fields.Many2one(
        'dsl.branch',
        string='Branch / Duty Station',
        domain="[('company_id', '=', company_id)]",
    )

    def _sync_to_dsl_contract(self):
        if self.env.context.get('skip_dsl_contract_sync') or 'dsl.employee.contract' not in self.env:
            return
        DslContract = self.env['dsl.employee.contract'].sudo().with_context(skip_dsl_contract_sync=True)
        rev_state_map = {
            'draft': 'draft',
            'open': 'active',
            'close': 'expired',
            'cancel': 'terminated',
        }
        for c in self.sudo():
            if not c.employee_id:
                continue
            vals = {
                'name': c.name or 'CNT-ODOO',
                'employee_id': c.employee_id.id,
                'date_start': c.date_start or fields.Date.context_today(self),
                'date_end': c.date_end or False,
                'confirmation_date': c.trial_date_end or False,
                'contract_gross': c.wage or 0.0,
                'state': rev_state_map.get(c.state, 'active'),
                'odoo_contract_id': c.id,
            }
            if c.dsl_contract_id:
                c.dsl_contract_id.sudo().with_context(skip_dsl_contract_sync=True).write(vals)
            else:
                existing = DslContract.search([('odoo_contract_id', '=', c.id)], limit=1)
                if not existing:
                    existing = DslContract.search([
                        ('employee_id', '=', c.employee_id.id),
                        ('state', '=', 'active'),
                    ], limit=1)
                if existing:
                    existing.write(vals)
                    c.with_context(skip_dsl_contract_sync=True).write({'dsl_contract_id': existing.id})
                else:
                    created = DslContract.create(vals)
                    c.with_context(skip_dsl_contract_sync=True).write({'dsl_contract_id': created.id})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_to_dsl_contract()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_dsl_contract_sync') and any(
            k in vals for k in ('name', 'date_start', 'date_end', 'trial_date_end', 'wage', 'state')
        ):
            self._sync_to_dsl_contract()
        return res


# =============================================================================
# 5. EMPLOYEE BANK & MFS DISBURSEMENT ACCOUNTS (`dsl.employee.bank`)
# =============================================================================
class DslEmployeeBank(models.Model):
    _name = 'dsl.employee.bank'
    _description = 'Employee Salary Bank (BEFTN) & Mobile Banking (MFS) Account'
    _order = 'is_primary desc, id asc'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='employee_id.company_id',
        store=True,
        readonly=True,
    )
    account_type = fields.Selection(
        selection=[
            ('bank_beftn', 'Bank Account (BEFTN / RTGS)'),
            ('mfs', 'Mobile Financial Service (bKash / Nagad / Rocket)'),
        ],
        string='Channel',
        default='bank_beftn',
        required=True,
    )
    bank_name = fields.Char(
        string='Bank / MFS Provider',
        required=True,
        help='e.g. BRAC Bank PLC, The City Bank, Dutch-Bangla Bank, bKash',
    )
    branch_name = fields.Char(string='Branch Name')
    account_holder_name = fields.Char(string='Account Holder Name', required=True)
    account_number = fields.Char(string='Account / Wallet Number', required=True)
    routing_number = fields.Char(string='9-Digit Routing No.')
    split_percentage = fields.Float(string='Disbursement Split (%)', default=100.0)
    is_primary = fields.Boolean(string='Primary Account', default=True)
    is_verified = fields.Boolean(string='Verified by Payroll', default=True)
    partner_bank_id = fields.Many2one(
        'res.partner.bank',
        string='Odoo Partner Bank Account',
        ondelete='set null',
        help='Automatically synchronized native Odoo res.partner.bank record.',
    )

    def _sync_to_odoo_partner_bank(self):
        if self.env.context.get('skip_dsl_bank_sync') or 'res.partner.bank' not in self.env:
            return
        ResBank = self.env['res.bank'].sudo()
        PartnerBank = self.env['res.partner.bank'].sudo().with_context(skip_dsl_bank_sync=True)
        Partner = self.env['res.partner'].sudo()
        for rec in self.sudo():
            emp = rec.employee_id
            if not emp or not rec.account_number:
                continue
            partner = emp.work_contact_id
            if not partner:
                partner = Partner.create({
                    'name': emp.name,
                    'email': emp.work_email or False,
                    'phone': emp.mobile_phone or emp.work_phone or False,
                    'company_id': emp.company_id.id if emp.company_id else False,
                })
                emp.with_context(skip_dsl_bank_sync=True).write({'work_contact_id': partner.id})

            bank_rec = False
            if rec.bank_name:
                bank_rec = ResBank.search([('name', '=ilike', rec.bank_name.strip())], limit=1)
                if not bank_rec:
                    bank_rec = ResBank.create({
                        'name': rec.bank_name.strip(),
                        'bic': rec.routing_number or False,
                    })

            pb_vals = {
                'acc_number': rec.account_number.strip(),
                'partner_id': partner.id,
                'acc_holder_name': rec.account_holder_name or emp.name,
                'bank_id': bank_rec.id if bank_rec else False,
                'company_id': emp.company_id.id if emp.company_id else False,
            }
            if rec.partner_bank_id:
                try:
                    rec.partner_bank_id.sudo().with_context(skip_dsl_bank_sync=True).write(pb_vals)
                except Exception:
                    pass
            else:
                existing_pb = PartnerBank.search([
                    ('acc_number', '=', rec.account_number.strip()),
                    ('partner_id', '=', partner.id),
                ], limit=1)
                if existing_pb:
                    rec.with_context(skip_dsl_bank_sync=True).write({'partner_bank_id': existing_pb.id})
                else:
                    try:
                        created_pb = PartnerBank.create(pb_vals)
                        rec.with_context(skip_dsl_bank_sync=True).write({'partner_bank_id': created_pb.id})
                    except Exception:
                        pass

            if rec.is_primary and rec.partner_bank_id:
                try:
                    emp.with_context(skip_dsl_bank_sync=True).write({'bank_account_id': rec.partner_bank_id.id})
                except Exception:
                    pass

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_to_odoo_partner_bank()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_dsl_bank_sync'):
            self._sync_to_odoo_partner_bank()
        return res


# =============================================================================
# 6. EMPLOYEE TRAINING & DEVELOPMENT (`dsl.employee.training`)
# =============================================================================
class DslEmployeeTraining(models.Model):
    _name = 'dsl.employee.training'
    _description = 'Employee Training, Workshop & Capacity Building Record'
    _order = 'date_start desc, id desc'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='employee_id.company_id',
        store=True,
        readonly=True,
    )
    name = fields.Char(string='Training / Program Title', required=True)
    institute_name = fields.Char(string='Institute / Organizer', required=True)
    training_type = fields.Selection(
        selection=[
            ('internal', 'In-House / On-the-Job Training'),
            ('external', 'Local External Institute (BIM / Bdjobs / BIBM)'),
            ('foreign', 'Overseas / International Training'),
            ('compliance', 'OSH, Fire Safety & Labour Law Compliance'),
        ],
        string='Training Category',
        default='external',
        required=True,
    )
    date_start = fields.Date(string='Start Date', default=fields.Date.context_today)
    date_end = fields.Date(string='End Date')
    duration_hours = fields.Float(string='Duration (Hours)', default=16.0)
    evaluation_score = fields.Char(string='Result / Score', default='Certified')
    certificate_filename = fields.Char(string='Certificate Filename')
    certificate_file = fields.Binary(string='Certificate File')


# =============================================================================
# 7. EMPLOYEE PROMOTION & GRADE ELEVATION (`dsl.employee.promotion`)
#    Automatically updates `hr.employee` & preserves `dsl.employee.job.history`
# =============================================================================
class DslEmployeePromotion(models.Model):
    _name = 'dsl.employee.promotion'
    _description = 'Employee Promotion & Designation Elevation History'
    _order = 'effective_date desc, id desc'

    name = fields.Char(
        string='Order Ref.',
        required=True,
        default=lambda self: _('PROMO-NEW'),
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='employee_id.company_id',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True,
    )
    previous_job_id = fields.Many2one('hr.job', string='Previous Designation')
    new_job_id = fields.Many2one('hr.job', string='New Designation', required=True)
    previous_grade_id = fields.Many2one('dsl.hr.grade', string='Previous Grade')
    new_grade_id = fields.Many2one('dsl.hr.grade', string='New Grade')
    previous_gross = fields.Monetary(string='Previous Gross (৳)', currency_field='currency_id')
    new_gross = fields.Monetary(string='New Gross (৳)', currency_field='currency_id')
    effective_date = fields.Date(
        string='Effective Date',
        required=True,
        default=fields.Date.context_today,
    )
    remarks = fields.Char(string='Board Resolution / Remarks')
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('approved', 'Approved & Applied'),
        ],
        string='Status',
        default='draft',
        required=True,
    )

    @api.onchange('employee_id')
    def _onchange_employee_snapshot(self):
        if self.employee_id:
            self.previous_job_id = self.employee_id.job_id
            self.previous_grade_id = self.employee_id.grade_id
            if hasattr(self.employee_id, 'current_gross_salary'):
                self.previous_gross = self.employee_id.current_gross_salary

    def action_approve_promotion(self):
        JobHist = self.env['dsl.employee.job.history'].sudo()
        for rec in self:
            emp = rec.employee_id
            if not rec.previous_job_id and emp.job_id:
                rec.previous_job_id = emp.job_id.id
            if not rec.previous_grade_id and emp.grade_id:
                rec.previous_grade_id = emp.grade_id.id

            prev_end = rec.effective_date - timedelta(days=1) if rec.effective_date else fields.Date.context_today(self)
            active_hist = JobHist.search([
                ('employee_id', '=', emp.id),
                ('is_current', '=', True),
            ])
            if active_hist:
                active_hist.write({
                    'is_current': False,
                    'effective_to': prev_end,
                })
            elif rec.previous_job_id:
                # Preserve baseline joining job history before applying promotion
                JobHist.create({
                    'employee_id': emp.id,
                    'company_id': emp.company_id.id,
                    'branch_id': emp.branch_id.id if emp.branch_id else False,
                    'department_id': emp.department_id.id if emp.department_id else False,
                    'job_id': rec.previous_job_id.id,
                    'grade_id': rec.previous_grade_id.id if rec.previous_grade_id else False,
                    'employment_category': emp.employment_category or 'permanent',
                    'manager_id': emp.parent_id.id if emp.parent_id else False,
                    'cost_center_id': emp.cost_center_id.id if emp.cost_center_id else False,
                    'effective_from': emp.joining_date or (prev_end - timedelta(days=365)),
                    'effective_to': prev_end,
                    'change_reason': 'joining',
                    'is_current': False,
                    'remarks': 'Historical baseline preserved prior to promotion',
                })

            JobHist.create({
                'employee_id': emp.id,
                'company_id': emp.company_id.id,
                'branch_id': emp.branch_id.id if emp.branch_id else False,
                'department_id': emp.department_id.id if emp.department_id else False,
                'job_id': rec.new_job_id.id,
                'grade_id': rec.new_grade_id.id if rec.new_grade_id else (emp.grade_id.id if emp.grade_id else False),
                'employment_category': emp.employment_category or 'permanent',
                'manager_id': emp.parent_id.id if emp.parent_id else False,
                'cost_center_id': emp.cost_center_id.id if emp.cost_center_id else False,
                'effective_from': rec.effective_date,
                'change_reason': 'promotion',
                'is_current': True,
                'remarks': f'{rec.name}: Promoted to {rec.new_job_id.name}',
            })

            emp_vals = {'job_id': rec.new_job_id.id}
            if rec.new_grade_id:
                emp_vals['grade_id'] = rec.new_grade_id.id
            emp.sudo().write(emp_vals)
            rec.state = 'approved'


# =============================================================================
# 8. EMPLOYEE TRANSFER & DEPUTATION (`dsl.employee.transfer`)
#    Preserves previous Company/Branch/Department in `dsl.employee.job.history`
# =============================================================================
class DslEmployeeTransfer(models.Model):
    _name = 'dsl.employee.transfer'
    _description = 'Employee Inter-Company, Inter-Branch & Inter-Department Transfer'
    _order = 'effective_date desc, id desc'

    name = fields.Char(
        string='Transfer Order Ref.',
        required=True,
        default=lambda self: _('TRF-NEW'),
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
    )
    transfer_type = fields.Selection(
        selection=[
            ('branch', 'Inter-Branch / Factory Transfer'),
            ('department', 'Inter-Department Transfer'),
            ('company', 'Group Inter-Company Deputation / Transfer'),
        ],
        string='Transfer Scope',
        default='branch',
        required=True,
    )
    previous_company_id = fields.Many2one('res.company', string='From Company')
    new_company_id = fields.Many2one(
        'res.company',
        string='To Company',
        required=True,
        default=lambda self: self.env.company,
    )
    previous_branch_id = fields.Many2one('dsl.branch', string='From Branch / Plant')
    new_branch_id = fields.Many2one(
        'dsl.branch',
        string='To Branch / Plant',
        domain="[('company_id', '=', new_company_id)]",
    )
    previous_department_id = fields.Many2one('hr.department', string='From Department')
    new_department_id = fields.Many2one('hr.department', string='To Department')
    effective_date = fields.Date(
        string='Effective Date',
        required=True,
        default=fields.Date.context_today,
    )
    remarks = fields.Char(string='Transfer Order Remarks')
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('approved', 'Approved & Applied'),
        ],
        string='Status',
        default='draft',
        required=True,
    )

    @api.onchange('employee_id')
    def _onchange_employee_transfer_snapshot(self):
        if self.employee_id:
            self.previous_company_id = self.employee_id.company_id
            self.new_company_id = self.employee_id.company_id
            self.previous_branch_id = self.employee_id.branch_id
            self.previous_department_id = self.employee_id.department_id

    def action_approve_transfer(self):
        JobHist = self.env['dsl.employee.job.history'].sudo()
        for rec in self:
            emp = rec.employee_id
            if not rec.previous_company_id:
                rec.previous_company_id = emp.company_id.id
            if not rec.previous_branch_id and emp.branch_id:
                rec.previous_branch_id = emp.branch_id.id
            if not rec.previous_department_id and emp.department_id:
                rec.previous_department_id = emp.department_id.id

            prev_end = rec.effective_date - timedelta(days=1) if rec.effective_date else fields.Date.context_today(self)
            active_hist = JobHist.search([
                ('employee_id', '=', emp.id),
                ('is_current', '=', True),
            ])
            if active_hist:
                active_hist.write({
                    'is_current': False,
                    'effective_to': prev_end,
                })
            else:
                # Preserve old Company/Branch/Department history before applying transfer
                JobHist.create({
                    'employee_id': emp.id,
                    'company_id': rec.previous_company_id.id or emp.company_id.id,
                    'branch_id': rec.previous_branch_id.id if rec.previous_branch_id else False,
                    'department_id': rec.previous_department_id.id if rec.previous_department_id else False,
                    'job_id': emp.job_id.id if emp.job_id else False,
                    'grade_id': emp.grade_id.id if emp.grade_id else False,
                    'employment_category': emp.employment_category or 'permanent',
                    'manager_id': emp.parent_id.id if emp.parent_id else False,
                    'cost_center_id': emp.cost_center_id.id if emp.cost_center_id else False,
                    'effective_from': emp.joining_date or (prev_end - timedelta(days=365)),
                    'effective_to': prev_end,
                    'change_reason': 'joining',
                    'is_current': False,
                    'remarks': 'Historical placement preserved prior to transfer',
                })

            JobHist.create({
                'employee_id': emp.id,
                'company_id': rec.new_company_id.id,
                'branch_id': rec.new_branch_id.id if rec.new_branch_id else (emp.branch_id.id if emp.branch_id else False),
                'department_id': rec.new_department_id.id if rec.new_department_id else (emp.department_id.id if emp.department_id else False),
                'job_id': emp.job_id.id if emp.job_id else False,
                'grade_id': emp.grade_id.id if emp.grade_id else False,
                'employment_category': emp.employment_category or 'permanent',
                'manager_id': emp.parent_id.id if emp.parent_id else False,
                'cost_center_id': emp.cost_center_id.id if emp.cost_center_id else False,
                'effective_from': rec.effective_date,
                'change_reason': 'transfer',
                'is_current': True,
                'remarks': rec.remarks or f'Transferred via {rec.name}',
            })

            emp_vals = {'company_id': rec.new_company_id.id}
            if rec.new_branch_id:
                emp_vals['branch_id'] = rec.new_branch_id.id
            if rec.new_department_id:
                emp_vals['department_id'] = rec.new_department_id.id
            emp.sudo().write(emp_vals)
            rec.state = 'approved'


# =============================================================================
# 9. EMPLOYEE DISCIPLINARY RECORDS (`dsl.employee.disciplinary`)
#    Bangladesh Labour Act 2006 Sections 23, 24 & 25
# =============================================================================
class DslEmployeeDisciplinary(models.Model):
    _name = 'dsl.employee.disciplinary'
    _description = 'Employee Disciplinary Action, Show Cause & Enquiry Record'
    _order = 'incident_date desc, id desc'

    name = fields.Char(
        string='Case Ref.',
        required=True,
        default=lambda self: _('DISC-NEW'),
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='employee_id.company_id',
        store=True,
        readonly=True,
    )
    action_type = fields.Selection(
        selection=[
            ('verbal_warning', 'Verbal Warning (মৌখিক সতর্কীকরণ)'),
            ('written_warning', 'Written Warning Letter (লিখিত সতর্কপত্র)'),
            ('show_cause', 'Show Cause Notice — কারণ দর্শানো নোটিশ (Sec 24)'),
            ('enquiry', 'Domestic Enquiry Committee (তদন্ত কমিটি)'),
            ('suspension', 'Suspension Pending Enquiry (সাময়িক বরখাস্ত)'),
            ('fine', 'Monetary Fine / Increment Withheld (Sec 25)'),
            ('dismissal', 'Dismissal for Misconduct (বরখাস্ত - Sec 23)'),
        ],
        string='Disciplinary Type',
        default='show_cause',
        required=True,
    )
    incident_date = fields.Date(
        string='Incident Date',
        required=True,
        default=fields.Date.context_today,
    )
    notice_date = fields.Date(
        string='Notice / Order Date',
        default=fields.Date.context_today,
    )
    violation_summary = fields.Char(string='Allegation / Violation Summary', required=True)
    employee_explanation = fields.Char(string='Show Cause Explanation')
    action_taken = fields.Char(string='Action Taken / Decision', required=True)
    remarks = fields.Char(string='Remarks / Reference')
    state = fields.Selection(
        selection=[
            ('open', 'Show Cause Issued'),
            ('hearing', 'Enquiry in Progress'),
            ('closed', 'Action Finalized'),
        ],
        string='Status',
        default='closed',
        required=True,
    )

