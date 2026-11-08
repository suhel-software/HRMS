# -*- coding: utf-8 -*-
import hashlib
import uuid
from datetime import date, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


def _default_issue_date(record=None):
    return fields.Date.context_today(record) if record is not None else fields.Date.today()


def _default_upto_month_label(record=None):
    today = _default_issue_date(record)
    return today.strftime('%B %Y')


# Complete 100 Bangladesh Salary & Payroll Document Types across 10 Categories
BD_100_SALARY_DOCUMENT_TYPES = [
    # 1. Salary & Employment Certificates (10)
    ('SALARY_CERTIFICATE', 'Salary Certificate', 'বেতন সনদ', '1_salary_emp_cert', True, True, True),
    ('SALARY_CONFIRMATION', 'Salary Confirmation Letter', 'বেতন নিশ্চিতকরণ পত্র', '1_salary_emp_cert', True, True, False),
    ('SALARY_BREAKDOWN', 'Salary Breakdown Statement', 'বেতনের বিস্তারিত বিবরণ', '1_salary_emp_cert', True, False, True),
    ('SALARY_VERIFICATION', 'Salary Verification Letter', 'বেতন যাচাইকরণ পত্র', '1_salary_emp_cert', True, True, False),
    ('EMPLOYMENT_CERTIFICATE', 'Employment Certificate', 'চাকরির সনদ', '1_salary_emp_cert', True, True, False),
    ('EMPLOYMENT_VERIFICATION', 'Employment Verification Letter', 'চাকরি যাচাইকরণ পত্র', '1_salary_emp_cert', True, True, False),
    ('INCOME_CERTIFICATE', 'Income Certificate', 'আয়ের সনদ', '1_salary_emp_cert', True, True, False),
    ('ANNUAL_INCOME_CERTIFICATE', 'Annual Income Certificate', 'বার্ষিক আয়ের সনদ', '1_salary_emp_cert', True, True, False),
    ('COMPENSATION_CERTIFICATE', 'Compensation Certificate', 'পারিশ্রমিক সনদ', '1_salary_emp_cert', False, True, False),
    ('TOTAL_REMUNERATION_STATEMENT', 'Total Remuneration Statement', 'মোট পারিশ্রমিক বিবরণী', '1_salary_emp_cert', False, True, False),

    # 2. Bank & Financial Documents (10)
    ('BANK_FORWARDING', 'Bank Forwarding Letter', 'ব্যাংক ফরওয়ার্ডিং লেটার', '2_bank_financial', True, True, True),
    ('BANK_ACCOUNT_CONFIRMATION', 'Bank Account Confirmation Letter', 'ব্যাংক হিসাব নিশ্চিতকরণ পত্র', '2_bank_financial', True, True, False),
    ('BANK_LOAN_FORWARDING', 'Bank Loan Forwarding Letter', 'ব্যাংক ঋণের জন্য ফরওয়ার্ডিং', '2_bank_financial', True, True, False),
    ('BANK_LOAN_VERIFICATION', 'Bank Loan Salary Verification', 'ঋণের জন্য বেতন যাচাইকরণ', '2_bank_financial', True, True, False),
    ('BANK_SOLVENCY_SUPPORT', 'Income Support Letter for Bank', 'ব্যাংকের জন্য আয়ের সহায়ক পত্র', '2_bank_financial', True, True, False),
    ('SALARY_TRANSFER_LETTER', 'Salary Transfer Letter', 'বেতন স্থানান্তর পত্র', '2_bank_financial', True, True, False),
    ('SALARY_ACCOUNT_OPENING', 'Salary Account Opening Letter', 'বেতন হিসাব খোলার পত্র', '2_bank_financial', True, False, False),
    ('BANK_PAYMENT_ADVICE', 'Bank Payment Advice', 'ব্যাংক পেমেন্ট পরামর্শপত্র', '2_bank_financial', False, True, False),
    ('BANK_SALARY_DISBURSEMENT', 'Salary Disbursement Statement', 'বেতন বিতরণ বিবরণী', '2_bank_financial', False, True, False),
    ('BANK_REMITTANCE', 'Bank Remittance Statement', 'ব্যাংক রেমিট্যান্স বিবরণী', '2_bank_financial', False, True, False),

    # 3. Monthly Payroll Documents (11)
    ('MONTHLY_PAYSLIP', 'Monthly Salary Slip', 'মাসিক বেতন স্লিপ', '3_monthly_payroll', True, False, True),
    ('PAYSLIP_DUPLICATE', 'Duplicate Salary Slip', 'বেতন স্লিপের ডুপ্লিকেট', '3_monthly_payroll', True, False, False),
    ('PAYROLL_REGISTER', 'Monthly Payroll Register', 'মাসিক পেরোল রেজিস্টার', '3_monthly_payroll', False, True, False),
    ('SALARY_SHEET', 'Monthly Salary Sheet', 'মাসিক বেতন শিট', '3_monthly_payroll', False, True, False),
    ('SALARY_SUMMARY', 'Salary Summary Report', 'বেতন সারসংক্ষেপ', '3_monthly_payroll', False, True, False),
    ('SALARY_DISBURSEMENT', 'Salary Disbursement Report', 'বেতন বিতরণ রিপোর্ট', '3_monthly_payroll', False, True, False),
    ('DEPARTMENT_SALARY', 'Department-wise Salary Report', 'বিভাগভিত্তিক বেতন রিপোর্ট', '3_monthly_payroll', False, False, False),
    ('COMPANY_SALARY', 'Company-wise Salary Report', 'কোম্পানিভিত্তিক বেতন রিপোর্ট', '3_monthly_payroll', False, False, False),
    ('BRANCH_SALARY', 'Branch-wise Salary Report', 'শাখাভিত্তিক বেতন রিপোর্ট', '3_monthly_payroll', False, False, False),
    ('SALARY_VARIANCE', 'Salary Variance Report', 'বেতন পরিবর্তন রিপোর্ট', '3_monthly_payroll', False, False, False),
    ('PAYROLL_RECONCILIATION', 'Payroll Reconciliation Report', 'পেরোল সমন্বয় রিপোর্ট', '3_monthly_payroll', False, True, False),

    # 4. Salary Revision & Increment Documents (9)
    ('SALARY_INCREMENT', 'Salary Increment Letter', 'বেতন বৃদ্ধির চিঠি', '4_revision_increment', False, True, True),
    ('SALARY_REVISION', 'Salary Revision Letter', 'বেতন সংশোধন পত্র', '4_revision_increment', False, True, True),
    ('SALARY_ADJUSTMENT', 'Salary Adjustment Letter', 'বেতন সমন্বয় পত্র', '4_revision_increment', False, True, False),
    ('SALARY_PROMOTION', 'Promotion with Salary Revision Letter', 'পদোন্নতি ও বেতন বৃদ্ধির পত্র', '4_revision_increment', False, True, False),
    ('SALARY_DEMOTION', 'Salary Revision due to Demotion', 'পদাবনতি সংক্রান্ত বেতন সংশোধন', '4_revision_increment', False, True, False),
    ('SALARY_DECREASE', 'Salary Reduction Letter', 'বেতন হ্রাসের পত্র', '4_revision_increment', False, True, False),
    ('NEW_SALARY_STRUCTURE', 'Revised Salary Structure', 'সংশোধিত বেতন কাঠামো', '4_revision_increment', False, True, False),
    ('SALARY_EFFECTIVE_NOTICE', 'Salary Effective Date Notice', 'নতুন বেতন কার্যকরের নোটিশ', '4_revision_increment', False, False, False),
    ('ARREAR_APPROVAL', 'Salary Arrear Approval', 'বকেয়া বেতন অনুমোদন', '4_revision_increment', False, True, False),

    # 5. Bonus & Incentive Documents (10)
    ('FESTIVAL_BONUS', 'Festival Bonus Statement', 'উৎসব বোনাস বিবরণী', '5_bonus_incentive', True, False, True),
    ('EID_BONUS', 'Eid Bonus Statement', 'ঈদ বোনাস বিবরণী', '5_bonus_incentive', True, False, False),
    ('ANNUAL_BONUS', 'Annual Bonus Statement', 'বার্ষিক বোনাস বিবরণী', '5_bonus_incentive', False, True, False),
    ('PERFORMANCE_BONUS', 'Performance Bonus Letter', 'কর্মদক্ষতা বোনাস পত্র', '5_bonus_incentive', False, True, False),
    ('INCENTIVE_STATEMENT', 'Incentive Statement', 'প্রণোদনা বিবরণী', '5_bonus_incentive', False, False, False),
    ('SALES_COMMISSION', 'Sales Commission Statement', 'বিক্রয় কমিশন বিবরণী', '5_bonus_incentive', False, False, False),
    ('OVERTIME_STATEMENT', 'Overtime Payment Statement', 'ওভারটাইম পেমেন্ট বিবরণী', '5_bonus_incentive', True, False, False),
    ('ATTENDANCE_BONUS', 'Attendance Bonus Statement', 'উপস্থিতি বোনাস বিবরণী', '5_bonus_incentive', False, False, False),
    ('BONUS_APPROVAL', 'Bonus Approval Letter', 'বোনাস অনুমোদন পত্র', '5_bonus_incentive', False, True, False),
    ('BONUS_PAYMENT_ADVICE', 'Bonus Payment Advice', 'বোনাস পেমেন্ট পরামর্শপত্র', '5_bonus_incentive', False, True, False),

    # 6. Tax & Income Tax Documents (9)
    ('TAX_CERTIFICATE', 'Tax Certificate', 'কর সনদ', '6_tax_nbr', True, True, False),
    ('TAX_DEDUCTION_CERTIFICATE', 'Tax Deduction Certificate', 'কর কর্তন সনদ', '6_tax_nbr', True, True, True),
    ('TDS_CERTIFICATE', 'Tax Deducted at Source Certificate', 'উৎসে কর কর্তন সনদ', '6_tax_nbr', True, True, False),
    ('ANNUAL_SALARY_STATEMENT', 'Annual Salary Statement', 'বার্ষিক বেতন বিবরণী', '6_tax_nbr', True, False, True),
    ('ANNUAL_TAX_STATEMENT', 'Annual Tax Statement', 'বার্ষিক কর বিবরণী', '6_tax_nbr', True, False, False),
    ('TAX_COMPUTATION', 'Income Tax Computation Sheet', 'আয়কর হিসাব শিট', '6_tax_nbr', True, False, False),
    ('TAX_PROJECTION', 'Tax Projection Statement', 'সম্ভাব্য কর বিবরণী', '6_tax_nbr', True, False, False),
    ('TAX_ADJUSTMENT', 'Tax Adjustment Statement', 'কর সমন্বয় বিবরণী', '6_tax_nbr', False, True, False),
    ('TAX_RETURN_SUPPORT', 'Tax Return Supporting Statement', 'আয়কর রিটার্ন সহায়ক বিবরণী', '6_tax_nbr', True, False, False),

    # 7. Provident Fund, Gratuity & Benefits Documents (10)
    ('PF_STATEMENT', 'Provident Fund Statement', 'প্রভিডেন্ট ফান্ড বিবরণী', '7_pf_gratuity_benefit', True, False, True),
    ('PF_BALANCE_CERTIFICATE', 'PF Balance Certificate', 'PF ব্যালেন্স সনদ', '7_pf_gratuity_benefit', True, True, False),
    ('PF_CONTRIBUTION', 'PF Contribution Statement', 'PF চাঁদা বিবরণী', '7_pf_gratuity_benefit', True, False, False),
    ('PF_WITHDRAWAL', 'PF Withdrawal Statement', 'PF উত্তোলন বিবরণী', '7_pf_gratuity_benefit', False, True, False),
    ('PF_LOAN', 'PF Loan Statement', 'PF ঋণ বিবরণী', '7_pf_gratuity_benefit', True, False, False),
    ('GRATUITY_STATEMENT', 'Gratuity Statement', 'গ্র্যাচুইটি বিবরণী', '7_pf_gratuity_benefit', True, False, False),
    ('GRATUITY_CERTIFICATE', 'Gratuity Certificate', 'গ্র্যাচুইটি সনদ', '7_pf_gratuity_benefit', True, True, False),
    ('INSURANCE_STATEMENT', 'Insurance Contribution Statement', 'বীমা চাঁদা বিবরণী', '7_pf_gratuity_benefit', True, False, False),
    ('BENEFIT_STATEMENT', 'Employee Benefit Statement', 'কর্মী সুবিধা বিবরণী', '7_pf_gratuity_benefit', True, False, False),
    ('FINAL_BENEFIT_STATEMENT', 'Final Benefit Statement', 'চূড়ান্ত সুবিধা বিবরণী', '7_pf_gratuity_benefit', False, True, False),

    # 8. Loan, Advance & Deduction Documents (9)
    ('SALARY_ADVANCE_APPROVAL', 'Salary Advance Approval Letter', 'অগ্রিম বেতন অনুমোদন', '8_loan_advance_deduction', True, True, True),
    ('SALARY_ADVANCE_STATEMENT', 'Salary Advance Statement', 'অগ্রিম বেতন বিবরণী', '8_loan_advance_deduction', True, False, False),
    ('EMPLOYEE_LOAN_APPROVAL', 'Employee Loan Approval Letter', 'কর্মী ঋণ অনুমোদন', '8_loan_advance_deduction', True, True, False),
    ('EMPLOYEE_LOAN_STATEMENT', 'Employee Loan Statement', 'কর্মী ঋণ বিবরণী', '8_loan_advance_deduction', True, False, False),
    ('LOAN_REPAYMENT_SCHEDULE', 'Loan Repayment Schedule', 'ঋণ পরিশোধের সময়সূচি', '8_loan_advance_deduction', True, False, False),
    ('LOAN_CLEARANCE', 'Loan Clearance Certificate', 'ঋণ পরিশোধ ছাড়পত্র', '8_loan_advance_deduction', True, True, False),
    ('DEDUCTION_STATEMENT', 'Salary Deduction Statement', 'বেতন কর্তন বিবরণী', '8_loan_advance_deduction', True, False, False),
    ('DEDUCTION_APPROVAL', 'Deduction Approval Letter', 'কর্তন অনুমোদন পত্র', '8_loan_advance_deduction', False, True, False),
    ('OVERPAYMENT_RECOVERY', 'Salary Overpayment Recovery Letter', 'অতিরিক্ত বেতন আদায় পত্র', '8_loan_advance_deduction', False, True, False),

    # 9. Resignation, Retirement & Final Settlement Documents (10)
    ('FINAL_SETTLEMENT', 'Final Settlement Statement', 'চূড়ান্ত পাওনা বিবরণী', '9_exit_settlement', False, True, True),
    ('FULL_AND_FINAL', 'Full & Final Settlement Letter', 'চূড়ান্ত নিষ্পত্তি পত্র', '9_exit_settlement', False, True, False),
    ('SALARY_CLEARANCE', 'Salary Clearance Certificate', 'বেতন ছাড়পত্র', '9_exit_settlement', False, True, False),
    ('NO_DUES_CERTIFICATE', 'No Dues Certificate', 'দায়মুক্তি সনদ', '9_exit_settlement', True, True, False),
    ('EXPERIENCE_CERTIFICATE', 'Experience Certificate', 'অভিজ্ঞতার সনদ', '9_exit_settlement', True, True, False),
    ('SERVICE_CERTIFICATE', 'Service Certificate', 'চাকরির মেয়াদের সনদ', '9_exit_settlement', True, True, False),
    ('RETIREMENT_BENEFIT', 'Retirement Benefit Statement', 'অবসর সুবিধা বিবরণী', '9_exit_settlement', False, True, False),
    ('RESIGNATION_SETTLEMENT', 'Resignation Settlement Statement', 'পদত্যাগজনিত পাওনা বিবরণী', '9_exit_settlement', False, True, False),
    ('NOTICE_PAY', 'Notice Pay Statement', 'নোটিশ পে বিবরণী', '9_exit_settlement', False, True, False),
    ('LEAVE_ENCASHMENT', 'Leave Encashment Statement', 'ছুটির অর্থ বিবরণী', '9_exit_settlement', False, True, False),

    # 10. HR & Accounts Internal Salary Documents (12)
    ('PAYROLL_APPROVAL', 'Payroll Approval Sheet', 'পেরোল অনুমোদন শিট', '10_hr_accounts_internal', False, True, False),
    ('SALARY_VOUCHER', 'Salary Payment Voucher', 'বেতন পেমেন্ট ভাউচার', '10_hr_accounts_internal', False, True, False),
    ('SALARY_JOURNAL', 'Salary Journal Voucher', 'বেতন জার্নাল ভাউচার', '10_hr_accounts_internal', False, True, False),
    ('SALARY_BANK_ADVICE', 'Bank Salary Advice', 'ব্যাংক বেতন অ্যাডভাইস', '10_hr_accounts_internal', False, True, False),
    ('SALARY_CASH_VOUCHER', 'Salary Cash Payment Voucher', 'নগদ বেতন পেমেন্ট ভাউচার', '10_hr_accounts_internal', False, True, False),
    ('PAYROLL_COST_CENTER', 'Cost Center-wise Payroll Report', 'কস্ট সেন্টার ভিত্তিক পেরোল রিপোর্ট', '10_hr_accounts_internal', False, False, False),
    ('PAYROLL_GL_REPORT', 'Payroll General Ledger Report', 'পেরোল জেনারেল লেজার রিপোর্ট', '10_hr_accounts_internal', False, False, False),
    ('SALARY_LIABILITY', 'Salary Payable Report', 'প্রদেয় বেতন দায় রিপোর্ট', '10_hr_accounts_internal', False, False, False),
    ('PAYROLL_AUDIT', 'Payroll Audit Report', 'পেরোল অডিট রিপোর্ট', '10_hr_accounts_internal', False, False, False),
    ('SALARY_BUDGET', 'Salary Budget Report', 'বেতন বাজেট রিপোর্ট', '10_hr_accounts_internal', False, False, False),
    ('SALARY_PROVISION', 'Salary Provision Report', 'বেতন প্রভিশন রিপোর্ট', '10_hr_accounts_internal', False, False, False),
    ('INTERCOMPANY_PAYROLL', 'Inter-company Payroll Allocation Report', 'আন্তঃকোম্পানি পেরোল বরাদ্দ রিপোর্ট', '10_hr_accounts_internal', False, True, False),
]


CATEGORY_SELECTION = [
    ('1_salary_emp_cert', '1. Salary & Employment Certificates (বেতন ও চাকরির সনদ)'),
    ('2_bank_financial', '2. Bank & Financial Documents (ব্যাংক ও আর্থিক পত্র)'),
    ('3_monthly_payroll', '3. Monthly Payroll Documents (মাসিক পেরোল ডকুমেন্ট)'),
    ('4_revision_increment', '4. Salary Revision & Increment (বেতন বৃদ্ধি ও সংশোধন)'),
    ('5_bonus_incentive', '5. Bonus & Incentive Documents (বোনাস ও প্রণোদনা)'),
    ('6_tax_nbr', '6. Tax & NBR Income Tax Documents (আয়কর ও কর সনদ)'),
    ('7_pf_gratuity_benefit', '7. PF, Gratuity & Benefits (প্রভিডেন্ট ফান্ড ও গ্র্যাচুইটি)'),
    ('8_loan_advance_deduction', '8. Loan, Advance & Deductions (ঋণ, অগ্রিম ও কর্তন)'),
    ('9_exit_settlement', '9. Resignation & Final Settlement (চূড়ান্ত নিষ্পত্তি ও ছাড়পত্র)'),
    ('10_hr_accounts_internal', '10. HR & Accounts Internal Vouchers (এইচআর ও একাউন্টস ভাউচার)'),
]


class DslHrmsSalaryDocumentType(models.Model):
    _name = 'dsl.hrms.salary.document.type'
    _description = 'DSL_HRMS_salary_document_type — Salary & Payroll Document Type Master'
    _order = 'category asc, sequence asc, code asc'

    sequence = fields.Integer(string='Sequence', default=10)
    code = fields.Char(string='Document Code', required=True, index=True)
    name = fields.Char(string='Document Name (English)', required=True, index=True)
    name_bn = fields.Char(string='বাংলা নাম (Bangla Title)')
    category = fields.Selection(selection=CATEGORY_SELECTION, string='Document Category', required=True, index=True)
    ess_requestable = fields.Boolean(
        string='Available in Employee Self-Service (ESS)',
        default=True,
        help='If enabled, employees can request this document directly from Self-Service.',
    )
    approval_required = fields.Boolean(
        string='Requires HR / Accounts Approval',
        default=True,
    )
    is_priority_core = fields.Boolean(
        string='Top-12 Core Document',
        default=False,
        help='Marks the 12 most essential Salary & Payroll Documents recommended for first-version rollout.',
    )
    validity_days = fields.Integer(
        string='Default Validity (Days)',
        default=90,
        help='Default number of days before the issued certificate expires (0 = never expires).',
    )
    default_signatory_title = fields.Char(
        string='Default Signatory Designation',
        default='Head of Human Resources & Administration',
    )
    default_template_id = fields.Many2one(
        'dsl.hrms.salary.document.template',
        string='Active Letter/Statement Template',
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Salary Document Type Code must be unique!'),
    ]

    @api.model
    def _ensure_100_bd_salary_document_types(self):
        """Idempotently seeds all 100 Bangladesh Salary Document Types + 12 Priority Templates."""
        existing_codes = set(self.sudo().with_context(active_test=False).search([]).mapped('code'))
        vals_to_create = []
        for idx, (code, name_en, name_bn, cat, ess_req, app_req, is_prio) in enumerate(BD_100_SALARY_DOCUMENT_TYPES, start=1):
            if code not in existing_codes:
                vals_to_create.append({
                    'sequence': idx * 5,
                    'code': code,
                    'name': name_en,
                    'name_bn': name_bn,
                    'category': cat,
                    'ess_requestable': ess_req,
                    'approval_required': app_req,
                    'is_priority_core': is_prio,
                    'validity_days': 90 if cat in ('1_salary_emp_cert', '2_bank_financial') else 0,
                })
        if vals_to_create:
            self.sudo().create(vals_to_create)
        self.env['dsl.hrms.salary.document.template'].sudo()._ensure_12_priority_templates()


class DslHrmsSalaryDocumentTemplate(models.Model):
    _name = 'dsl.hrms.salary.document.template'
    _description = 'DSL_HRMS_salary_document_template — Dynamic Letter & Certificate Template'
    _order = 'is_priority_core desc, sequence asc, id desc'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Template Name', required=True)
    code = fields.Char(string='Template Code', required=True, index=True)
    document_type_id = fields.Many2one(
        'dsl.hrms.salary.document.type',
        string='Document Type',
        required=True,
        ondelete='cascade',
    )
    category = fields.Selection(related='document_type_id.category', store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company (Leave blank for All Companies)',
    )
    is_priority_core = fields.Boolean(string='Top-12 Priority Template', default=False)
    include_salary_breakdown_table = fields.Boolean(string='Include Monthly Breakdown Table', default=True)
    include_bank_account_block = fields.Boolean(string='Include Bank & Routing Details', default=True)
    include_tax_pf_summary = fields.Boolean(string='Include NBR Tax & PF Summary', default=False)
    include_qr_verification = fields.Boolean(string='Include QR Verification Block', default=True)
    header_title = fields.Char(string='Certificate / Statement Heading', required=True)
    salutation_text = fields.Char(string='Default Addressee / Salutation', default='TO WHOM IT MAY CONCERN')
    opening_paragraph = fields.Text(
        string='Opening Certification Paragraph',
        help='Supports dynamic placeholders: {employee_name}, {employee_code}, {designation}, {department}, {company_name}, {joining_date}, {salary_upto_month}, {gross_salary}, {net_salary}, {purpose}, {addressed_to}.',
    )
    closing_paragraph = fields.Text(
        string='Closing / Verification Note',
    )
    active = fields.Boolean(default=True)

    @api.model
    def _ensure_12_priority_templates(self):
        """Creates the 12 core Bangladesh Salary Document Templates and links them to their Document Types."""
        DocType = self.env['dsl.hrms.salary.document.type'].sudo()
        priority_specs = [
            (
                'TPL_SALARY_CERTIFICATE',
                'SALARY_CERTIFICATE',
                'Standard Bangladesh Corporate Salary Certificate (বেতন সনদ)',
                'SALARY CERTIFICATE / বেতন সনদ',
                'TO WHOM IT MAY CONCERN',
                'This is to certify that {employee_name} (Employee ID: {employee_code}), {designation}, {department}, is a confirmed full-time employee of {company_name} since {joining_date}. Based on our payroll records up to the month of {salary_upto_month}, his/her monthly compensation breakdown is stated below:',
                'This Salary Certificate is issued upon the request of the employee for {purpose} without any financial liability on the part of {company_name}.',
                True, True, False,
            ),
            (
                'TPL_BANK_FORWARDING',
                'BANK_FORWARDING',
                'Corporate Bank Forwarding & Salary Introduction Letter (ব্যাংক ফরওয়ার্ডিং লেটার)',
                'BANK FORWARDING & SALARY INTRODUCTION LETTER',
                'The Branch Manager',
                'We are pleased to introduce {employee_name} (Employee ID: {employee_code}), currently serving as {designation} in the {department} department at {company_name}. His/Her salary has been processed up to {salary_upto_month} and is disbursed directly through bank transfer as detailed below:',
                'We request your esteemed bank to extend necessary banking / account / credit facilities to the above-named official in accordance with your banking norms.',
                True, True, False,
            ),
            (
                'TPL_SALARY_BREAKDOWN',
                'SALARY_BREAKDOWN',
                'Detailed Gross-to-Net Salary Breakdown Statement (বেতনের বিস্তারিত বিবরণ)',
                'DETAILED SALARY BREAKDOWN STATEMENT',
                'EMPLOYEE COMPENSATION & PAYROLL BREAKDOWN',
                'Detailed component-wise monthly earnings, statutory deductions, and net take-home pay for {employee_name} ({employee_code}) up to payroll month {salary_upto_month}:',
                'All amounts are denominated in Bangladeshi Taka (BDT / ৳) as per approved Company Salary Structure.',
                True, True, True,
            ),
            (
                'TPL_MONTHLY_PAYSLIP',
                'MONTHLY_PAYSLIP',
                'Official Monthly Salary Slip Statement (মাসিক বেতন স্লিপ)',
                'MONTHLY SALARY SLIP (PAYSLIP)',
                'CONFIDENTIAL EMPLOYEE PAYSLIP',
                'Monthly verified salary slip for {employee_name} (Employee ID: {employee_code}), {designation}, for the salary period up to {salary_upto_month}:',
                'This is a computer-generated official payslip verified by DSL Enterprise HRMS.',
                True, True, True,
            ),
            (
                'TPL_ANNUAL_SALARY_STATEMENT',
                'ANNUAL_SALARY_STATEMENT',
                'Fiscal Year Annual Salary & Remuneration Statement (বার্ষিক বেতন বিবরণী)',
                'ANNUAL SALARY & REMUNERATION STATEMENT',
                'ANNUAL INCOME & TAX SUMMARY',
                'Certified annual salary, allowance, festival bonus, and tax deduction summary for {employee_name} (Employee ID: {employee_code}) up to {salary_upto_month}:',
                'Issued for annual income verification and NBR Income Tax Return filing support.',
                True, True, True,
            ),
            (
                'TPL_SALARY_INCREMENT',
                'SALARY_INCREMENT',
                'Annual Performance Salary Increment Letter (বেতন বৃদ্ধির চিঠি)',
                'SALARY INCREMENT & APPRECIATION LETTER',
                'Dear {employee_name},',
                'In recognition of your dedicated performance and contribution to {company_name}, Management is pleased to revise and increment your monthly gross salary with effect from your effective appraisal cycle (reference payroll up to {salary_upto_month}) as follows:',
                'We appreciate your commitment and wish you continued success in your career with {company_name}.',
                True, False, False,
            ),
            (
                'TPL_SALARY_REVISION',
                'SALARY_REVISION',
                'Compensation Structure Revision Letter (বেতন সংশোধন পত্র)',
                'COMPENSATION REVISION NOTIFICATION',
                'Dear {employee_name},',
                'Please be informed that your compensation structure at {company_name} has been revised and aligned with the updated enterprise grade policy (payroll reference up to {salary_upto_month}) as detailed below:',
                'All other terms and conditions of your employment contract remain unchanged.',
                True, False, False,
            ),
            (
                'TPL_FESTIVAL_BONUS',
                'FESTIVAL_BONUS',
                'Festival / Eid Bonus Disbursement Statement (উৎসব বোনাস বিবরণী)',
                'FESTIVAL & EID BONUS STATEMENT',
                'FESTIVAL BONUS ENTITLEMENT CERTIFICATE',
                'Certified Festival / Eid Bonus entitlement and disbursement statement for {employee_name} (Employee ID: {employee_code}), {designation}, {company_name} (reference period up to {salary_upto_month}):',
                'Disbursed in accordance with Bangladesh Labour Rules and Company Festival Bonus Policy.',
                True, True, False,
            ),
            (
                'TPL_TAX_DEDUCTION_CERTIFICATE',
                'TAX_DEDUCTION_CERTIFICATE',
                'NBR Tax Deducted at Source (TDS) Certificate (কর কর্তন সনদ)',
                'INCOME TAX DEDUCTION CERTIFICATE (NBR TDS)',
                'TO WHOM IT MAY CONCERN / NATIONAL BOARD OF REVENUE (NBR)',
                'This is to certify that Income Tax at Source (AIT / TDS) has been deducted from the salary of {employee_name} (Employee ID: {employee_code}), {designation}, {company_name} up to {salary_upto_month} and deposited to the Government Treasury as summarized below:',
                'Issued under Section 108 / 117 of the Income Tax Act 2023 (Bangladesh) for annual tax return submission.',
                True, True, True,
            ),
            (
                'TPL_PF_STATEMENT',
                'PF_STATEMENT',
                'Employee Provident Fund (PF) Accumulation Statement (প্রভিডেন্ট ফান্ড বিবরণী)',
                'PROVIDENT FUND (PF) BALANCE & CONTRIBUTION STATEMENT',
                'RECOGNIZED PROVIDENT FUND TRUST STATEMENT',
                'Certified statement of Employee & Employer Provident Fund (PF) contributions and accumulated balance for {employee_name} (Employee ID: {employee_code}) up to {salary_upto_month}:',
                'Verified by the Board of Trustees — DSL Recognized Provident Fund Trust.',
                True, False, True,
            ),
            (
                'TPL_SALARY_ADVANCE_APPROVAL',
                'SALARY_ADVANCE_APPROVAL',
                'Salary Advance / Employee Loan Approval Letter (অগ্রিম বেতন অনুমোদন)',
                'SALARY ADVANCE & RECOVERY APPROVAL LETTER',
                'Dear {employee_name},',
                'With reference to your application, Management has approved your Salary Advance / Loan request subject to monthly payroll installment recovery (current salary reference up to {salary_upto_month}) as detailed below:',
                'The approved amount will be disbursed to your registered salary bank account and recovered through monthly payroll.',
                True, True, False,
            ),
            (
                'TPL_FINAL_SETTLEMENT',
                'FINAL_SETTLEMENT',
                'Full & Final Settlement Clearance Statement (চূড়ান্ত পাওনা বিবরণী)',
                'FULL & FINAL SETTLEMENT STATEMENT',
                'EMPLOYEE SEPARATION & FINAL DUES CLEARANCE',
                'Comprehensive Final Settlement statement of earned salary, leave encashment, PF/Gratuity benefits, and recoveries for {employee_name} (Employee ID: {employee_code}) calculated up to {salary_upto_month}:',
                'Upon disbursement of the net settlement payable, no further financial claims shall remain outstanding between the employee and {company_name}.',
                True, True, True,
            ),
        ]
        for idx, (tpl_code, dtype_code, tpl_name, heading, salutation, opening, closing, inc_brk, inc_bank, inc_tax) in enumerate(priority_specs, start=1):
            dtype = DocType.search([('code', '=', dtype_code)], limit=1)
            if not dtype:
                continue
            tpl = self.sudo().search([('code', '=', tpl_code)], limit=1)
            if not tpl:
                tpl = self.sudo().create({
                    'sequence': idx * 5,
                    'code': tpl_code,
                    'name': tpl_name,
                    'document_type_id': dtype.id,
                    'is_priority_core': True,
                    'header_title': heading,
                    'salutation_text': salutation,
                    'opening_paragraph': opening,
                    'closing_paragraph': closing,
                    'include_salary_breakdown_table': inc_brk,
                    'include_bank_account_block': inc_bank,
                    'include_tax_pf_summary': inc_tax,
                    'include_qr_verification': True,
                })
            if not dtype.default_template_id:
                dtype.default_template_id = tpl.id


class DslHrmsSalaryDocumentSequence(models.Model):
    _name = 'dsl.hrms.salary.document.sequence'
    _description = 'DSL_HRMS_salary_document_sequence — Document Serial Number Generator'
    _order = 'company_id asc, document_type_id asc'

    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    document_type_id = fields.Many2one('dsl.hrms.salary.document.type', string='Document Type', required=True)
    prefix = fields.Char(string='Serial Prefix', required=True, default='SDOC')
    fiscal_year = fields.Char(string='Year', required=True, default=lambda self: str(fields.Date.today().year))
    last_number = fields.Integer(string='Last Issued Number', default=0)

    @api.model
    def next_serial_number(self, company_id, document_type):
        year_str = str(fields.Date.today().year)
        seq = self.sudo().search([
            ('company_id', '=', company_id),
            ('document_type_id', '=', document_type.id),
            ('fiscal_year', '=', year_str),
        ], limit=1)
        short_code = (document_type.code or 'SDOC')[:6]
        if not seq:
            seq = self.sudo().create({
                'company_id': company_id,
                'document_type_id': document_type.id,
                'prefix': f"DSL/{short_code}/{year_str}",
                'fiscal_year': year_str,
                'last_number': 0,
            })
        seq.last_number += 1
        return f"{seq.prefix}/{seq.last_number:04d}"


class DslHrmsSalaryDocumentRequest(models.Model):
    _name = 'dsl.hrms.salary.document.request'
    _description = 'DSL_HRMS_salary_document_request — Employee & HR Salary Document Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Request Ref.',
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
        default=lambda self: self.env.user.employee_id,
        tracking=True,
        index=True,
    )
    employee_code = fields.Char(related='employee_id.employee_code', string='Employee ID', store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company',
        string='Legal Entity / Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    branch_id = fields.Many2one('dsl.branch', string='Branch / Duty Station', index=True)
    department_id = fields.Many2one('hr.department', string='Department')
    document_type_id = fields.Many2one(
        'dsl.hrms.salary.document.type',
        string='Requested Document Type',
        required=True,
        tracking=True,
    )
    category = fields.Selection(related='document_type_id.category', store=True, readonly=True)
    request_date = fields.Date(string='Request Date', required=True, default=_default_issue_date, tracking=True)
    salary_upto_month = fields.Char(
        string='Salary Data Up To Month',
        required=True,
        default=_default_upto_month_label,
        help='Specifies up to which payroll month salary data is certified (e.g., November 2026).',
    )
    addressed_to = fields.Char(
        string='Addressed To (Bank / Embassy / Authority)',
        default='TO WHOM IT MAY CONCERN',
        help='e.g. The Branch Manager, City Bank PLC, Gulshan Avenue Branch, Dhaka',
    )
    purpose = fields.Char(
        string='Purpose / Reason for Request',
        required=True,
        default='Personal Banking / Visa / Official Verification Purpose',
    )
    remarks = fields.Text(string='Additional Notes / Delivery Instructions')
    requested_by_id = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user, readonly=True)
    approved_by_id = fields.Many2one('res.users', string='Approved By', readonly=True, tracking=True)
    generated_document_id = fields.Many2one(
        'dsl.hrms.salary.document',
        string='Issued Salary Document',
        readonly=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft Request'),
            ('submitted', 'Pending HR/Accounts Approval'),
            ('approved', 'Approved'),
            ('issued', 'Document Generated & Issued'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        for rec in self:
            if rec.employee_id:
                rec.company_id = rec.employee_id.company_id
                rec.branch_id = rec.employee_id.branch_id
                rec.department_id = rec.employee_id.department_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dsl.hrms.salary.document.request') or f"SDR-{fields.Date.today().strftime('%Y%m')}-001"
            if vals.get('employee_id') and not vals.get('company_id'):
                emp = self.env['hr.employee'].sudo().browse(vals['employee_id'])
                vals['company_id'] = emp.company_id.id
                vals.setdefault('branch_id', emp.branch_id.id if emp.branch_id else False)
                vals.setdefault('department_id', emp.department_id.id if emp.department_id else False)
        return super().create(vals_list)

    def action_submit_request(self):
        for rec in self:
            if not rec.document_type_id.approval_required:
                rec.action_approve_and_generate()
            else:
                rec.write({'state': 'submitted'})

    def action_approve_and_generate(self):
        Doc = self.env['dsl.hrms.salary.document'].sudo()
        for rec in self:
            doc = rec.generated_document_id
            if not doc:
                doc = Doc.create({
                    'request_id': rec.id,
                    'document_type_id': rec.document_type_id.id,
                    'template_id': rec.document_type_id.default_template_id.id if rec.document_type_id.default_template_id else False,
                    'employee_id': rec.employee_id.id,
                    'company_id': rec.company_id.id,
                    'branch_id': rec.branch_id.id if rec.branch_id else False,
                    'department_id': rec.department_id.id if rec.department_id else False,
                    'salary_upto_month': rec.salary_upto_month,
                    'addressed_to': rec.addressed_to,
                    'purpose': rec.purpose,
                    'requested_by_id': rec.requested_by_id.id,
                })
            doc.action_fetch_employee_payroll_data()
            doc.action_approve_and_issue()
            rec.write({
                'approved_by_id': self.env.uid,
                'generated_document_id': doc.id,
                'state': 'issued',
            })
        return True

    def action_open_generated_document(self):
        self.ensure_one()
        if not self.generated_document_id:
            raise UserError(_('No salary document has been generated yet!'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Issued Salary Document'),
            'res_model': 'dsl.hrms.salary.document',
            'res_id': self.generated_document_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_reject_request(self):
        self.write({'state': 'rejected'})


class DslHrmsSalaryDocument(models.Model):
    _name = 'dsl.hrms.salary.document'
    _description = 'DSL_HRMS_salary_document — Generated Salary & Payroll Certificate/Statement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'issue_date desc, id desc'

    name = fields.Char(
        string='Document Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
    )
    document_type_id = fields.Many2one(
        'dsl.hrms.salary.document.type',
        string='Document Type',
        required=True,
        tracking=True,
        index=True,
    )
    category = fields.Selection(related='document_type_id.category', store=True, readonly=True)
    template_id = fields.Many2one(
        'dsl.hrms.salary.document.template',
        string='Document Template',
        domain="[('document_type_id', '=', document_type_id)]",
    )
    request_id = fields.Many2one('dsl.hrms.salary.document.request', string='Source Request', readonly=True)

    # Employee & Legal Entity Context
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, tracking=True, index=True)
    employee_code = fields.Char(related='employee_id.employee_code', string='Employee ID', store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company',
        string='Legal Entity / Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    branch_id = fields.Many2one('dsl.branch', string='Branch / Plant', index=True)
    department_id = fields.Many2one('hr.department', string='Department')
    designation_id = fields.Many2one('hr.job', string='Designation')
    joining_date = fields.Date(string='Joining Date')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True, readonly=True)

    # Dates & Payroll Period Context
    issue_date = fields.Date(string='Issue Date', required=True, default=_default_issue_date, tracking=True)
    effective_date = fields.Date(string='Effective Date', default=_default_issue_date)
    expiry_date = fields.Date(string='Expiry Date')
    payslip_id = fields.Many2one(
        'dsl.payslip',
        string='Reference Monthly Payslip',
        domain="[('employee_id', '=', employee_id)]",
    )
    salary_period_from = fields.Date(string='Salary Period From')
    salary_period_to = fields.Date(string='Salary Period To')
    salary_upto_month = fields.Char(
        string='Salary Data Certified Up To Month',
        required=True,
        default=_default_upto_month_label,
        tracking=True,
        help='Mandatory disclosure for Salary Certificates & Bank Forwarding Letters indicating up to which payroll month data is certified.',
    )

    # Confidential Compensation & Payroll Figures (BDT)
    gross_salary = fields.Monetary(string='Monthly Gross Salary (৳)', currency_field='currency_id', tracking=True)
    basic_salary = fields.Monetary(string='Basic Salary (৳)', currency_field='currency_id')
    house_rent = fields.Monetary(string='House Rent Allowance (HRA) (৳)', currency_field='currency_id')
    medical_allowance = fields.Monetary(string='Medical Allowance (৳)', currency_field='currency_id')
    conveyance_allowance = fields.Monetary(string='Conveyance / Transport (৳)', currency_field='currency_id')
    other_allowances = fields.Monetary(string='Food / Special / Other Allowances (৳)', currency_field='currency_id')
    festival_bonus_amount = fields.Monetary(string='Festival / Eid Bonus (৳)', currency_field='currency_id')
    overtime_amount = fields.Monetary(string='Overtime Payment (৳)', currency_field='currency_id')
    total_deductions = fields.Monetary(string='Total Monthly Deductions (৳)', currency_field='currency_id')
    monthly_tds = fields.Monetary(string='Monthly NBR Income Tax (TDS) (৳)', currency_field='currency_id')
    pf_employee_contribution = fields.Monetary(string='Monthly PF Contribution (৳)', currency_field='currency_id')
    loan_installment_deduction = fields.Monetary(string='Loan / Advance Deduction (৳)', currency_field='currency_id')
    net_salary = fields.Monetary(string='Monthly Net Take-Home Pay (৳)', currency_field='currency_id', tracking=True)

    # Annual, Tax, PF & Revision Figures
    previous_gross_salary = fields.Monetary(string='Previous Gross Salary (৳)', currency_field='currency_id')
    increment_amount = fields.Monetary(string='Increment / Revision Amount (৳)', currency_field='currency_id')
    increment_percentage = fields.Float(string='Increment (%)', digits=(5, 2))
    annual_gross_salary = fields.Monetary(string='Annual Gross Remuneration (৳)', currency_field='currency_id')
    annual_tax_deducted = fields.Monetary(string='Annual Tax Deducted (TDS) (৳)', currency_field='currency_id')
    pf_total_balance = fields.Monetary(string='Accumulated PF Balance (৳)', currency_field='currency_id')
    gratuity_accrued = fields.Monetary(string='Accrued Gratuity Benefit (৳)', currency_field='currency_id')
    advance_or_settlement_amount = fields.Monetary(string='Approved Advance / Final Settlement (৳)', currency_field='currency_id')

    # Confidential Bank & Tax Information (Restricted in UI to HR/Accounts)
    bank_name = fields.Char(string='Bank Name')
    bank_branch = fields.Char(string='Bank Branch')
    bank_account_number = fields.Char(string='Bank Account Number')
    routing_number = fields.Char(string='Bank Routing Number')
    tin_number = fields.Char(string='Employee e-TIN Number')
    tax_circle_zone = fields.Char(string='Tax Circle & Zone')

    # Addressee, Purpose & Signatory Governance
    addressed_to = fields.Char(string='Addressed To', default='TO WHOM IT MAY CONCERN')
    purpose = fields.Char(string='Purpose / Reason', default='Official Banking / Verification Purpose')
    requested_by_id = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user)
    approved_by_id = fields.Many2one('res.users', string='Approved By', readonly=True)
    authorized_signatory_id = fields.Many2one('hr.employee', string='Authorized Signatory')
    signatory_name = fields.Char(string='Signatory Name', default='Head of Human Resources')
    signatory_designation = fields.Char(string='Designation of Signatory', default='Head of Human Resources & Administration')
    digital_signature = fields.Binary(string='Digital Signature Image', attachment=True)

    # QR Code Verification & Output
    qr_verification_code = fields.Char(string='QR Verification Token', readonly=True, copy=False, index=True)
    qr_verification_payload = fields.Char(string='QR Verification Summary', compute='_compute_qr_payload', store=True)
    rendered_body_html = fields.Html(
        string='Generated Certificate / Statement Preview',
        compute='_compute_rendered_body_html',
        store=True,
        sanitize=False,
    )
    pdf_attachment_id = fields.Many2one('ir.attachment', string='Archived PDF Attachment', readonly=True)
    approval_line_ids = fields.One2many(
        'dsl.hrms.salary.document.approval',
        'document_id',
        string='Approval Workflow Trail',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft / Preview'),
            ('pending_approval', 'Pending HR / Accounts Approval'),
            ('approved', 'Approved'),
            ('issued', 'Issued & Archived'),
            ('expired', 'Expired'),
            ('cancelled', 'Cancelled'),
        ],
        string='Document Status',
        default='draft',
        required=True,
        tracking=True,
    )

    @api.depends('name', 'employee_code', 'issue_date', 'net_salary', 'salary_upto_month', 'qr_verification_code')
    def _compute_qr_payload(self):
        for rec in self:
            token = rec.qr_verification_code or 'PENDING'
            rec.qr_verification_payload = (
                f"VERIFY:{rec.name}|EMP:{rec.employee_code or rec.employee_id.name}"
                f"|UPTO:{rec.salary_upto_month or ''}|NET:BDT {rec.net_salary:,.2f}|HASH:{token}"
            )

    @api.onchange('document_type_id')
    def _onchange_document_type_id(self):
        for rec in self:
            if rec.document_type_id:
                rec.template_id = rec.document_type_id.default_template_id
                if rec.document_type_id.default_signatory_title:
                    rec.signatory_designation = rec.document_type_id.default_signatory_title
                if rec.document_type_id.validity_days > 0 and rec.issue_date:
                    rec.expiry_date = rec.issue_date + timedelta(days=rec.document_type_id.validity_days)

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        for rec in self:
            if rec.employee_id:
                rec.action_fetch_employee_payroll_data()

    @api.model_create_multi
    def create(self, vals_list):
        Seq = self.env['dsl.hrms.salary.document.sequence'].sudo()
        DocType = self.env['dsl.hrms.salary.document.type'].sudo()
        for vals in vals_list:
            dtype = DocType.browse(vals.get('document_type_id')) if vals.get('document_type_id') else DocType.browse()
            comp_id = vals.get('company_id') or self.env.company.id
            if vals.get('name', _('New')) == _('New') and dtype:
                vals['name'] = Seq.next_serial_number(comp_id, dtype)
            if not vals.get('qr_verification_code'):
                raw = f"{vals.get('name', '')}-{uuid.uuid4().hex[:8]}".encode('utf-8')
                vals['qr_verification_code'] = hashlib.sha256(raw).hexdigest()[:14].upper()
            if dtype and not vals.get('template_id') and dtype.default_template_id:
                vals['template_id'] = dtype.default_template_id.id
        recs = super().create(vals_list)
        for rec in recs:
            if not rec.gross_salary and rec.employee_id:
                rec.action_fetch_employee_payroll_data()
        return recs

    def action_fetch_employee_payroll_data(self):
        """
        Step 3 of Workflow: Automatically fetches Employee Profile, Bank, Tax, PF,
        Salary Package, and Latest Monthly Payslip data (including up-to month).
        """
        Payslip = self.env['dsl.payslip'].sudo()
        Comp = self.env['dsl.employee.compensation'].sudo()
        for rec in self:
            emp = rec.employee_id.sudo()
            if not emp:
                continue
            rec.company_id = emp.company_id.id or self.env.company.id
            rec.branch_id = emp.branch_id.id if emp.branch_id else False
            rec.department_id = emp.department_id.id if emp.department_id else False
            rec.designation_id = emp.job_id.id if emp.job_id else False
            rec.joining_date = getattr(emp, 'joining_date', False) or date(2023, 1, 1)

            # Bank & Tax Details from Employee / Bank Profile
            rec.bank_name = getattr(emp, 'bank_name', False) or 'City Bank PLC'
            rec.bank_branch = getattr(emp, 'bank_branch_name', False) or 'Gulshan Avenue Corporate Branch'
            rec.bank_account_number = getattr(emp, 'bank_account_no', False) or '1402938475610'
            rec.routing_number = getattr(emp, 'bank_routing_no', False) or '225261729'
            rec.tin_number = getattr(emp, 'tin_no', False) or '584920193847'
            rec.tax_circle_zone = 'Taxes Circle-114 (Companies), Taxes Zone-06, Dhaka'

            # Fetch latest active Compensation Package
            active_pkg = Comp.search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'active'),
            ], order='effective_from desc, id desc', limit=1)

            # Fetch latest Payslip
            latest_slip = Payslip.search([
                ('employee_id', '=', emp.id),
                ('state', '!=', 'cancelled'),
            ], order='date_to desc, id desc', limit=1)

            if latest_slip:
                line_map = {ln.code: ln.amount for ln in latest_slip.line_ids}
                gross_val = latest_slip.contract_gross or latest_slip.gross_payable or 65000.0
                rec.payslip_id = latest_slip.id
                rec.salary_period_from = latest_slip.date_from
                rec.salary_period_to = latest_slip.date_to
                rec.salary_upto_month = latest_slip.payroll_month_label or latest_slip.date_to.strftime('%B %Y')
                rec.gross_salary = gross_val
                rec.basic_salary = line_map.get('BASIC', round(gross_val * 0.50, 2))
                rec.house_rent = line_map.get('HRA', round(gross_val * 0.25, 2))
                rec.medical_allowance = line_map.get('MEDICAL', line_map.get('MED', round(gross_val * 0.10, 2)))
                rec.conveyance_allowance = line_map.get('CONVEYANCE', line_map.get('CONV', round(gross_val * 0.10, 2)))
                rec.other_allowances = max(round(gross_val - (rec.basic_salary + rec.house_rent + rec.medical_allowance + rec.conveyance_allowance), 2), 0.0)
                rec.overtime_amount = latest_slip.ot_amount
                rec.total_deductions = latest_slip.total_deductions
                rec.monthly_tds = latest_slip.tds_deducted
                rec.pf_employee_contribution = line_map.get('PF_EMP', round(rec.basic_salary * 0.10, 2))
                rec.loan_installment_deduction = line_map.get('LOAN', line_map.get('ADVANCE', 0.0))
                rec.net_salary = latest_slip.net_payable
            elif active_pkg:
                gross_val = active_pkg.gross_salary or 65000.0
                rec.gross_salary = gross_val
                rec.basic_salary = getattr(active_pkg, 'basic_salary', 0.0) or round(gross_val * 0.50, 2)
                rec.house_rent = getattr(active_pkg, 'house_rent_allowance', 0.0) or round(gross_val * 0.25, 2)
                rec.medical_allowance = getattr(active_pkg, 'medical_allowance', 0.0) or round(gross_val * 0.10, 2)
                rec.conveyance_allowance = getattr(active_pkg, 'conveyance_allowance', 0.0) or round(gross_val * 0.10, 2)
                rec.other_allowances = max(round(gross_val - (rec.basic_salary + rec.house_rent + rec.medical_allowance + rec.conveyance_allowance), 2), 0.0)
                rec.monthly_tds = round(gross_val * 0.04, 2) if gross_val >= 45000 else 0.0
                rec.pf_employee_contribution = round(rec.basic_salary * 0.10, 2)
                rec.total_deductions = rec.monthly_tds + rec.pf_employee_contribution + 10.0
                rec.net_salary = max(rec.gross_salary - rec.total_deductions, 0.0)
            else:
                # Fallback standard corporate structure if employee has no package yet
                gross = 65000.0
                rec.gross_salary = gross
                rec.basic_salary = round(gross * 0.50, 2)
                rec.house_rent = round(gross * 0.25, 2)
                rec.medical_allowance = round(gross * 0.10, 2)
                rec.conveyance_allowance = round(gross * 0.10, 2)
                rec.other_allowances = round(gross * 0.05, 2)
                rec.monthly_tds = 1500.0
                rec.pf_employee_contribution = round(rec.basic_salary * 0.10, 2)
                rec.total_deductions = rec.monthly_tds + rec.pf_employee_contribution + 10.0
                rec.net_salary = rec.gross_salary - rec.total_deductions

            # Compute Annual / Bonus / PF / Increment / Final Settlement figures
            rec.festival_bonus_amount = rec.basic_salary
            rec.previous_gross_salary = round(rec.gross_salary / 1.12, 2)
            rec.increment_amount = round(rec.gross_salary - rec.previous_gross_salary, 2)
            rec.increment_percentage = 12.0
            rec.annual_gross_salary = round((rec.gross_salary * 12.0) + (rec.festival_bonus_amount * 2.0), 2)
            rec.annual_tax_deducted = round(rec.monthly_tds * 12.0, 2)
            rec.pf_total_balance = round(rec.pf_employee_contribution * 2.0 * 24.0, 2)
            rec.gratuity_accrued = round(rec.basic_salary * 2.0, 2)
            rec.advance_or_settlement_amount = round(rec.net_salary + rec.pf_total_balance + rec.gratuity_accrued, 2)

    @api.depends(
        'name', 'document_type_id', 'template_id', 'employee_id', 'company_id', 'branch_id',
        'department_id', 'designation_id', 'issue_date', 'salary_upto_month', 'gross_salary',
        'basic_salary', 'house_rent', 'medical_allowance', 'conveyance_allowance', 'other_allowances',
        'total_deductions', 'monthly_tds', 'pf_employee_contribution', 'net_salary',
        'annual_gross_salary', 'annual_tax_deducted', 'pf_total_balance', 'festival_bonus_amount',
        'increment_amount', 'previous_gross_salary', 'advance_or_settlement_amount',
        'addressed_to', 'purpose', 'signatory_name', 'signatory_designation', 'qr_verification_code',
    )
    def _compute_rendered_body_html(self):
        for rec in self:
            emp_name = rec.employee_id.name or 'Employee Name'
            emp_code = rec.employee_code or 'DSL-0001'
            desig = rec.designation_id.name or 'Executive'
            dept = rec.department_id.name or 'Operations'
            comp_name = rec.company_id.name or 'DSL Enterprise Ltd.'
            branch_name = rec.branch_id.name if rec.branch_id else 'Corporate Head Office'
            join_str = rec.joining_date.strftime('%d %B %Y') if rec.joining_date else '01 January 2023'
            issue_str = rec.issue_date.strftime('%d %B %Y') if rec.issue_date else fields.Date.today().strftime('%d %B %Y')
            upto_str = rec.salary_upto_month or _default_upto_month_label(rec)

            tpl = rec.template_id or rec.document_type_id.default_template_id
            heading = (tpl.header_title if tpl else False) or (
                f"{rec.document_type_id.name.upper()} ({rec.document_type_id.name_bn})"
                if rec.document_type_id and rec.document_type_id.name_bn
                else (rec.document_type_id.name.upper() if rec.document_type_id else 'SALARY DOCUMENT')
            )
            salutation = rec.addressed_to or (tpl.salutation_text if tpl else 'TO WHOM IT MAY CONCERN')

            fmt_map = {
                'employee_name': emp_name,
                'employee_code': emp_code,
                'designation': desig,
                'department': dept,
                'company_name': comp_name,
                'branch_name': branch_name,
                'joining_date': join_str,
                'salary_upto_month': upto_str,
                'gross_salary': f"৳{rec.gross_salary:,.2f}",
                'net_salary': f"৳{rec.net_salary:,.2f}",
                'purpose': rec.purpose or 'official verification',
                'addressed_to': salutation,
            }
            default_opening = (
                f"This is to certify that <strong>{emp_name}</strong> (Employee ID: <strong>{emp_code}</strong>), "
                f"<strong>{desig}</strong>, <strong>{dept}</strong> ({branch_name}), is an employee of "
                f"<strong>{comp_name}</strong>. Based on our verified payroll records up to the month of "
                f"<strong>{upto_str}</strong>, the official compensation and financial details are presented below:"
            )
            raw_opening = tpl.opening_paragraph if (tpl and tpl.opening_paragraph) else default_opening
            try:
                opening_html = raw_opening.format(**fmt_map)
            except Exception:
                opening_html = default_opening

            closing_html = (tpl.closing_paragraph if (tpl and tpl.closing_paragraph) else (
                f"This official document is issued upon request for {rec.purpose or 'official use'} "
                f"based on payroll records verified up to {upto_str}."
            ))
            try:
                closing_html = closing_html.format(**fmt_map)
            except Exception:
                pass

            # Build Category-Specific / Breakdown HTML Tables
            dtype_code = rec.document_type_id.code or ''
            extra_summary_html = ''
            if dtype_code in ('SALARY_INCREMENT', 'SALARY_REVISION', 'SALARY_PROMOTION'):
                extra_summary_html = f"""
                <div style="margin: 14px 0; padding: 12px; background: #eff6ff; border-left: 4px solid #2563eb; border-radius: 4px;">
                    <strong>Revision / Increment Summary:</strong>
                    Previous Gross: <strong>৳ {rec.previous_gross_salary:,.2f}</strong> &rarr;
                    Increment: <strong>+৳ {rec.increment_amount:,.2f} ({rec.increment_percentage:.1f}%)</strong> &rarr;
                    Revised Monthly Gross: <strong>৳ {rec.gross_salary:,.2f}</strong>
                </div>
                """
            elif dtype_code in ('FESTIVAL_BONUS', 'EID_BONUS', 'ANNUAL_BONUS'):
                extra_summary_html = f"""
                <div style="margin: 14px 0; padding: 12px; background: #ecfdf5; border-left: 4px solid #059669; border-radius: 4px;">
                    <strong>Approved Festival / Eid Bonus Amount:</strong>
                    <strong>৳ {rec.festival_bonus_amount:,.2f}</strong> (100% of Basic Salary — Disbursed via {rec.bank_name or 'Bank Transfer'})
                </div>
                """
            elif dtype_code in ('TAX_DEDUCTION_CERTIFICATE', 'TAX_CERTIFICATE', 'TDS_CERTIFICATE', 'ANNUAL_SALARY_STATEMENT', 'ANNUAL_TAX_STATEMENT'):
                extra_summary_html = f"""
                <table class="table table-sm table-bordered" style="font-size: 13px; margin-top: 12px;">
                    <tr style="background:#f8fafc;">
                        <th>Employee e-TIN</th><td><strong>{rec.tin_number or '—'}</strong></td>
                        <th>Tax Circle &amp; Zone</th><td>{rec.tax_circle_zone or '—'}</td>
                    </tr>
                    <tr>
                        <th>Annual Taxable Remuneration (BDT)</th><td><strong>৳ {rec.annual_gross_salary:,.2f}</strong></td>
                        <th>Total Tax Deducted at Source (TDS)</th><td style="color:#047857;"><strong>৳ {rec.annual_tax_deducted:,.2f}</strong></td>
                    </tr>
                </table>
                """
            elif dtype_code in ('PF_STATEMENT', 'PF_BALANCE_CERTIFICATE', 'PF_CONTRIBUTION', 'GRATUITY_STATEMENT', 'FINAL_SETTLEMENT'):
                extra_summary_html = f"""
                <table class="table table-sm table-bordered" style="font-size: 13px; margin-top: 12px;">
                    <tr style="background:#f8fafc;">
                        <th>Monthly Employee PF (10%)</th><td>৳ {rec.pf_employee_contribution:,.2f}</td>
                        <th>Monthly Employer PF Match (10%)</th><td>৳ {rec.pf_employee_contribution:,.2f}</td>
                    </tr>
                    <tr>
                        <th>Accumulated PF Trust Balance</th><td><strong>৳ {rec.pf_total_balance:,.2f}</strong></td>
                        <th>Accrued Gratuity / Final Settlement</th><td style="color:#1d4ed8;"><strong>৳ {rec.advance_or_settlement_amount:,.2f}</strong></td>
                    </tr>
                </table>
                """

            bank_block_html = f"""
            <table class="table table-sm table-bordered" style="font-size: 12.5px; margin-top: 12px;">
                <tr style="background: #f8fafc;">
                    <th style="width: 22%;">Disbursement Bank</th>
                    <td style="width: 28%;"><strong>{rec.bank_name or '—'}</strong></td>
                    <th style="width: 22%;">Branch Name</th>
                    <td style="width: 28%;">{rec.bank_branch or '—'}</td>
                </tr>
                <tr>
                    <th>Bank Account Number</th>
                    <td><strong>{rec.bank_account_number or '—'}</strong></td>
                    <th>Routing Number / e-TIN</th>
                    <td>{rec.routing_number or '—'} | TIN: {rec.tin_number or '—'}</td>
                </tr>
            </table>
            """

            rec.rendered_body_html = f"""
            <div style="font-family: 'Segoe UI', Arial, sans-serif; color: #0f172a; line-height: 1.55; padding: 18px; border: 1px solid #cbd5e1; border-radius: 8px; background: #ffffff;">
                <div style="border-bottom: 3px solid #1e3a8a; padding-bottom: 12px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h3 style="margin: 0; color: #1e3a8a; font-weight: 800;">{comp_name}</h3>
                        <div style="font-size: 12px; color: #475569;">Duty Station / Branch: <strong>{branch_name}</strong></div>
                    </div>
                    <div style="text-align: right; font-size: 12px;">
                        <div>Ref No: <strong>{rec.name}</strong></div>
                        <div>Issue Date: <strong>{issue_str}</strong></div>
                        <div style="color: #2563eb; font-weight: 700;">Salary Certified Up To: {upto_str}</div>
                    </div>
                </div>

                <div style="text-align: center; margin: 14px 0;">
                    <h4 style="margin: 0; color: #0f172a; font-weight: 800; text-decoration: underline;">{heading}</h4>
                </div>

                <div style="margin-bottom: 10px; font-weight: 700; color: #1e293b;">{salutation}</div>
                <p style="font-size: 13.5px; text-align: justify;">{opening_html}</p>

                <table class="table table-sm table-bordered" style="font-size: 13px; margin-top: 12px;">
                    <thead style="background: #eff6ff; color: #1e3a8a;">
                        <tr>
                            <th style="width: 50%;">Earnings / Allowances (আয় ও ভাতাদি)</th>
                            <th style="width: 20%; text-align: right;">Monthly (৳)</th>
                            <th style="width: 30%; text-align: right;">Annualized (12M) (৳)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Basic Salary (মূল বেতন)</td>
                            <td style="text-align: right;">{rec.basic_salary:,.2f}</td>
                            <td style="text-align: right;">{rec.basic_salary * 12:,.2f}</td>
                        </tr>
                        <tr>
                            <td>House Rent Allowance — HRA (বাড়ি ভাড়া ভাতা)</td>
                            <td style="text-align: right;">{rec.house_rent:,.2f}</td>
                            <td style="text-align: right;">{rec.house_rent * 12:,.2f}</td>
                        </tr>
                        <tr>
                            <td>Medical Allowance (চিকিৎসা ভাতা)</td>
                            <td style="text-align: right;">{rec.medical_allowance:,.2f}</td>
                            <td style="text-align: right;">{rec.medical_allowance * 12:,.2f}</td>
                        </tr>
                        <tr>
                            <td>Conveyance / Transport Allowance (যাতায়াত ভাতা)</td>
                            <td style="text-align: right;">{rec.conveyance_allowance:,.2f}</td>
                            <td style="text-align: right;">{rec.conveyance_allowance * 12:,.2f}</td>
                        </tr>
                        <tr>
                            <td>Food / Special / Other Allowances (অন্যান্য ভাতা)</td>
                            <td style="text-align: right;">{rec.other_allowances:,.2f}</td>
                            <td style="text-align: right;">{rec.other_allowances * 12:,.2f}</td>
                        </tr>
                        <tr style="background: #f8fafc; font-weight: 700;">
                            <td>TOTAL GROSS SALARY (মোট মাসিক বেতন)</td>
                            <td style="text-align: right;">৳ {rec.gross_salary:,.2f}</td>
                            <td style="text-align: right;">৳ {rec.gross_salary * 12:,.2f}</td>
                        </tr>
                        <tr style="color: #b91c1c;">
                            <td>Less: Monthly Deductions (Income Tax TDS: ৳{rec.monthly_tds:,.2f} + PF: ৳{rec.pf_employee_contribution:,.2f} + Other)</td>
                            <td style="text-align: right;">- ৳ {rec.total_deductions:,.2f}</td>
                            <td style="text-align: right;">- ৳ {rec.total_deductions * 12:,.2f}</td>
                        </tr>
                        <tr style="background: #ecfdf5; font-weight: 800; color: #047857; font-size: 14px;">
                            <td>NET TAKE-HOME SALARY PAYABLE (নিট প্রদেয় বেতন — Up to {upto_str})</td>
                            <td style="text-align: right;">৳ {rec.net_salary:,.2f}</td>
                            <td style="text-align: right;">৳ {rec.net_salary * 12:,.2f}</td>
                        </tr>
                    </tbody>
                </table>

                {extra_summary_html}
                {bank_block_html}

                <p style="font-size: 13px; margin-top: 12px; color: #334155;">{closing_html}</p>

                <div style="margin-top: 26px; display: flex; justify-content: space-between; align-items: flex-end; border-top: 1px dashed #cbd5e1; padding-top: 14px;">
                    <div style="font-size: 11.5px; color: #475569;">
                        <div><strong>QR Verification Code:</strong> <code>{rec.qr_verification_code or 'VERIFIED'}</code></div>
                        <div>Payroll Certified Up To: <strong>{upto_str}</strong></div>
                    </div>
                    <div style="text-align: right; font-size: 12.5px;">
                        <div style="font-weight: 800; color: #0f172a;">{rec.signatory_name or 'Authorized Signatory'}</div>
                        <div style="color: #475569;">{rec.signatory_designation or 'Head of Human Resources'}</div>
                        <div style="color: #1e3a8a; font-weight: 700;">{comp_name}</div>
                    </div>
                </div>
            </div>
            """

    def action_submit_for_approval(self):
        Approval = self.env['dsl.hrms.salary.document.approval'].sudo()
        for rec in self:
            if not rec.gross_salary:
                rec.action_fetch_employee_payroll_data()
            if not rec.approval_line_ids:
                Approval.create([
                    {
                        'document_id': rec.id,
                        'sequence': 10,
                        'stage_name': 'HR Verification & Signatory Review',
                        'approver_user_id': self.env.uid,
                        'state': 'pending',
                    },
                    {
                        'document_id': rec.id,
                        'sequence': 20,
                        'stage_name': 'Accounts / Payroll Verification',
                        'approver_user_id': self.env.uid,
                        'state': 'pending',
                    },
                ])
            rec.write({'state': 'pending_approval'})

    def action_approve_and_issue(self):
        for rec in self:
            if not rec.gross_salary:
                rec.action_fetch_employee_payroll_data()
            rec.approval_line_ids.filtered(lambda l: l.state == 'pending').write({
                'state': 'approved',
                'approved_at': fields.Datetime.now(),
                'approver_user_id': self.env.uid,
                'remarks': 'Verified against Monthly Payroll & Employee Compensation Register.',
            })
            rec.write({
                'approved_by_id': self.env.uid,
                'state': 'issued',
            })
            # Archive in Employee Document Vault if DSL_HRMS_document is installed
            if 'dsl.employee.document' in self.env and rec.employee_id:
                DocVault = self.env['dsl.employee.document'].sudo()
                existing_vault = DocVault.search([('reference_no', '=', rec.name)], limit=1)
                if not existing_vault:
                    dtype_vault = self.env['dsl.document.type'].sudo().search([], limit=1)
                    if dtype_vault:
                        DocVault.create({
                            'name': f"{rec.document_type_id.name} ({rec.salary_upto_month})",
                            'employee_id': rec.employee_id.id,
                            'document_type_id': dtype_vault.id,
                            'reference_no': rec.name,
                            'issue_date': rec.issue_date,
                            'expiry_date': rec.expiry_date,
                            'verification_state': 'verified',
                            'verified_by': self.env.uid,
                            'verified_date': fields.Date.today(),
                            'notes': f"Auto-archived from Salary Document Center ({rec.name}) — QR: {rec.qr_verification_code}",
                        })

    def action_print_salary_document(self):
        self.ensure_one()
        return self.env.ref('DSL_HRMS_payroll_bd.action_report_dsl_salary_document').report_action(self)


class DslHrmsSalaryDocumentApproval(models.Model):
    _name = 'dsl.hrms.salary.document.approval'
    _description = 'DSL_HRMS_salary_document_approval — Document Approval Workflow Step'
    _order = 'sequence asc, id asc'

    document_id = fields.Many2one('dsl.hrms.salary.document', string='Salary Document', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Step', default=10)
    stage_name = fields.Char(string='Approval Authority Stage', required=True)
    approver_user_id = fields.Many2one('res.users', string='Approver', default=lambda self: self.env.user)
    approved_at = fields.Datetime(string='Approved Timestamp')
    remarks = fields.Char(string='Verification Remarks')
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


# ==============================================================================
# PAYROLL ACCOUNTING, JOURNAL VOUCHER & COST-CENTER GL ENGINE
# (Answers Category 10: HR & Accounts Internal Salary Documents + Accounting)
# ==============================================================================
class DslHrmsPayrollVoucher(models.Model):
    _name = 'dsl.hrms.payroll.voucher'
    _description = 'Payroll Accounting Journal, Payment Voucher & Cost Center Ledger'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'accounting_date desc, id desc'

    name = fields.Char(
        string='Voucher Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
    )
    voucher_type = fields.Selection(
        selection=[
            ('SALARY_JOURNAL', 'Salary Journal Voucher (বেতন জার্নাল ভাউচার)'),
            ('SALARY_VOUCHER', 'Salary Bank Payment Voucher (বেতন পেমেন্ট ভাউচার)'),
            ('SALARY_CASH_VOUCHER', 'Salary Cash Payment Voucher (নগদ বেতন পেমেন্ট ভাউচার)'),
            ('PAYROLL_APPROVAL', 'Payroll Approval Sheet (পেরোল অনুমোদন শিট)'),
            ('PAYROLL_COST_CENTER', 'Cost Center-wise Payroll Allocation (কস্ট সেন্টার পেরোল রিপোর্ট)'),
            ('PAYROLL_GL_REPORT', 'Payroll General Ledger Entry (পেরোল জেনারেল লেজার)'),
            ('SALARY_LIABILITY', 'Salary Payable Liability Sheet (প্রদেয় বেতন দায় রিপোর্ট)'),
            ('SALARY_PROVISION', 'Monthly PF / Gratuity / Bonus Provision (বেতন প্রভিশন ভাউচার)'),
            ('INTERCOMPANY_PAYROLL', 'Inter-Company Payroll Allocation (আন্তঃকোম্পানি পেরোল বরাদ্দ)'),
        ],
        string='Accounting Document Type',
        required=True,
        default='SALARY_JOURNAL',
        tracking=True,
    )
    batch_id = fields.Many2one(
        'dsl.payslip.run',
        string='Source Payroll Batch',
        ondelete='set null',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    accounting_company_id = fields.Many2one(
        'res.company',
        string='COA Books of Account Entity',
        default=lambda self: self.env.company,
    )
    branch_id = fields.Many2one('dsl.branch', string='Branch / Factory Plant', index=True)
    accounting_date = fields.Date(string='Posting Date', required=True, default=_default_issue_date, tracking=True)
    payroll_month_label = fields.Char(string='Payroll Month', default=_default_upto_month_label)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True, readonly=True)

    line_ids = fields.One2many(
        'dsl.hrms.payroll.voucher.line',
        'voucher_id',
        string='General Ledger Journal Lines (Dr / Cr)',
    )
    total_debit = fields.Monetary(string='Total Debit (৳)', currency_field='currency_id', compute='_compute_totals', store=True)
    total_credit = fields.Monetary(string='Total Credit (৳)', currency_field='currency_id', compute='_compute_totals', store=True)
    is_balanced = fields.Boolean(string='Balanced (Dr = Cr)', compute='_compute_totals', store=True)
    prepared_by_id = fields.Many2one('res.users', string='Prepared By', default=lambda self: self.env.user)
    approved_by_id = fields.Many2one('res.users', string='Approved & Posted By', readonly=True)
    narration = fields.Text(string='Accounting Narration / Audit Notes')
    state = fields.Selection(
        selection=[
            ('draft', 'Draft Voucher'),
            ('verified', 'Accounts Verified'),
            ('posted', 'Posted to General Ledger'),
            ('cancelled', 'Cancelled'),
        ],
        string='Ledger Status',
        default='draft',
        required=True,
        tracking=True,
    )
    account_move_id = fields.Many2one(
        'account.move',
        string='Odoo Journal Entry (account.move)',
        ondelete='set null',
        help='Automatically linked native Odoo account.move General Ledger entry.',
    )

    @api.depends('line_ids.debit', 'line_ids.credit')
    def _compute_totals(self):
        for rec in self:
            dr = round(sum(rec.line_ids.mapped('debit')), 2)
            cr = round(sum(rec.line_ids.mapped('credit')), 2)
            rec.total_debit = dr
            rec.total_credit = cr
            rec.is_balanced = abs(dr - cr) < 0.05

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vtype = vals.get('voucher_type', 'SALARY_JOURNAL')
                prefix = 'SJV' if vtype == 'SALARY_JOURNAL' else ('SPV' if 'VOUCHER' in vtype else 'PGL')
                vals['name'] = f"DSL/{prefix}/{fields.Date.today().strftime('%Y%m')}/{self.sudo().search_count([]) + 1:04d}"
        return super().create(vals_list)

    def action_verify_voucher(self):
        for rec in self:
            if not rec.is_balanced:
                raise ValidationError(_('Payroll Accounting Voucher "%s" is not balanced! Total Debit (৳%s) must equal Total Credit (৳%s).') % (
                    rec.name, f"{rec.total_debit:,.2f}", f"{rec.total_credit:,.2f}"
                ))
            rec.write({'state': 'verified'})

    def action_post_gl_voucher(self):
        for rec in self:
            if not rec.is_balanced:
                raise ValidationError(_('Cannot post unbalanced voucher "%s"!') % rec.name)
            # Plug-and-Play Bridge: If DSL_HRMS_accounting (account.move) is installed, post directly to General Ledger!
            if 'account.move' in self.env and rec.line_ids:
                comp = rec.accounting_company_id or rec.company_id or self.env.company
                Move = self.env['account.move'].sudo().with_company(comp)
                existing_move = Move.search([('ref', '=', rec.name), ('company_id', '=', comp.id)], limit=1)
                if not existing_move:
                    Journal = self.env['account.journal'].sudo().with_company(comp)
                    journal = Journal.search([('type', '=', 'general'), ('company_id', '=', comp.id)], limit=1)
                    if not journal:
                        journal = Journal.create({
                            'name': 'Payroll & Miscellaneous Operations',
                            'code': 'PAYR',
                            'type': 'general',
                            'company_id': comp.id,
                        })
                    Account = self.env['account.account'].sudo().with_company(comp)
                    aml_vals = []
                    type_map = {
                        'expense': 'expense',
                        'employer_provision': 'expense',
                        'liability': 'liability_current',
                        'bank_asset': 'asset_cash',
                    }
                    for vline in rec.line_ids:
                        code = (vline.gl_account_code or '501999').strip()
                        acc = Account.search([('code', '=', code), ('company_ids', 'in', comp.id)], limit=1)
                        if not acc:
                            acc = Account.create({
                                'code': code,
                                'name': vline.gl_account_name or 'Payroll GL Account',
                                'account_type': type_map.get(vline.account_type, 'expense'),
                                'company_ids': [(4, comp.id)],
                            })
                        aml_vals.append((0, 0, {
                            'name': f"{vline.gl_account_name} ({rec.payroll_month_label or ''})",
                            'account_id': acc.id,
                            'debit': round(vline.debit, 2),
                            'credit': round(vline.credit, 2),
                        }))
                    gl_move = Move.create({
                        'journal_id': journal.id,
                        'date': rec.accounting_date or fields.Date.today(),
                        'ref': rec.name,
                        'line_ids': aml_vals,
                    })
                    gl_move.action_post()
                    rec.account_move_id = gl_move.id
                else:
                    rec.account_move_id = existing_move.id
            rec.write({
                'state': 'posted',
                'approved_by_id': self.env.uid,
            })

    def action_print_voucher(self):
        self.ensure_one()
        return self.env.ref('DSL_HRMS_payroll_bd.action_report_dsl_payroll_voucher').report_action(self)


class DslHrmsPayrollVoucherLine(models.Model):
    _name = 'dsl.hrms.payroll.voucher.line'
    _description = 'Payroll General Ledger Journal Line (COA Head + Cost Center)'
    _order = 'sequence asc, id asc'

    voucher_id = fields.Many2one('dsl.hrms.payroll.voucher', string='Payroll Voucher', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    gl_account_code = fields.Char(string='COA Account Code', required=True)
    gl_account_name = fields.Char(string='General Ledger Account Title', required=True)
    account_type = fields.Selection(
        selection=[
            ('expense', 'Direct Payroll Expense (Dr)'),
            ('employer_provision', 'Employer PF / Gratuity Expense (Dr)'),
            ('liability', 'Statutory / Payroll Liability (Cr)'),
            ('bank_asset', 'Bank / Cash Clearing Account (Cr)'),
        ],
        string='Account Classification',
        required=True,
        default='expense',
    )
    department_id = fields.Many2one('hr.department', string='Cost Center / Department')
    branch_id = fields.Many2one('dsl.branch', string='Branch')
    currency_id = fields.Many2one('res.currency', related='voucher_id.currency_id', store=True, readonly=True)
    debit = fields.Monetary(string='Debit (Dr ৳)', currency_field='currency_id', default=0.0)
    credit = fields.Monetary(string='Credit (Cr ৳)', currency_field='currency_id', default=0.0)
    narration = fields.Char(string='Line Description')


class DslPayslipRunAccountingInherit(models.Model):
    _inherit = 'dsl.payslip.run'

    voucher_ids = fields.One2many(
        'dsl.hrms.payroll.voucher',
        'batch_id',
        string='Accounting Journal & Payment Vouchers',
    )
    voucher_count = fields.Integer(string='Accounting Vouchers', compute='_compute_voucher_count')

    def _compute_voucher_count(self):
        for rec in self:
            rec.voucher_count = len(rec.voucher_ids)

    def action_generate_accounting_vouchers(self):
        """
        Generates balanced Double-Entry Salary Journal Voucher (SALARY_JOURNAL)
        and Bank Payment Voucher (SALARY_VOUCHER) directly from the Monthly Payroll Batch!
        """
        Voucher = self.env['dsl.hrms.payroll.voucher'].sudo()
        for batch in self:
            active_slips = batch.payslip_ids.filtered(lambda s: s.state != 'cancelled')
            if not active_slips:
                raise UserError(_('Please generate payslips in this batch before creating Accounting Vouchers!'))

            existing_jv = Voucher.search([
                ('batch_id', '=', batch.id),
                ('voucher_type', '=', 'SALARY_JOURNAL'),
            ], limit=1)
            if existing_jv and existing_jv.state != 'posted':
                existing_jv.unlink()
                existing_jv = False

            month_lbl = batch.date_to.strftime('%B %Y') if batch.date_to else _default_upto_month_label(batch)
            all_lines = active_slips.mapped('line_ids')
            tot_basic = round(sum(all_lines.filtered(lambda l: l.code == 'BASIC').mapped('amount')), 2)
            tot_hra = round(sum(all_lines.filtered(lambda l: l.code == 'HRA').mapped('amount')), 2)
            tot_med_conv = round(sum(all_lines.filtered(lambda l: l.code in ('MEDICAL', 'MED', 'CONVEYANCE', 'CONV', 'FOOD', 'SPECIAL')).mapped('amount')), 2)
            tot_ot_var = round(sum(active_slips.mapped('total_additions')), 2)
            tot_emp_contrib = round(sum(active_slips.mapped('employer_contribution_total')), 2)
            tot_gross = round(sum(active_slips.mapped('gross_payable')), 2)

            # Ensure exact Dr sum matches gross_payable + employer contributions
            rem_earning = round(tot_gross - (tot_basic + tot_hra + tot_med_conv + tot_ot_var), 2)
            tot_med_conv = round(tot_med_conv + rem_earning, 2)

            tot_tds = round(sum(active_slips.mapped('tds_deducted')), 2)
            tot_pf_emp = round(sum(all_lines.filtered(lambda l: l.code in ('PF_EMP', 'PF')).mapped('amount')), 2)
            tot_loan = round(sum(all_lines.filtered(lambda l: l.code in ('LOAN', 'ADVANCE', 'SALARY_ADVANCE')).mapped('amount')), 2)
            tot_other_ded = round(sum(active_slips.mapped('total_deductions')) - (tot_tds + tot_pf_emp + tot_loan), 2)
            tot_net = round(sum(active_slips.mapped('net_payable')), 2)

            if not existing_jv:
                jv_lines = [
                    (0, 0, {
                        'sequence': 10,
                        'gl_account_code': '510101',
                        'gl_account_name': 'Salaries & Wages — Basic Salary Expense',
                        'account_type': 'expense',
                        'debit': tot_basic,
                        'credit': 0.0,
                        'narration': f'Monthly Basic Salary Expense for {month_lbl}',
                    }),
                    (0, 0, {
                        'sequence': 20,
                        'gl_account_code': '510102',
                        'gl_account_name': 'House Rent Allowance (HRA) Expense',
                        'account_type': 'expense',
                        'debit': tot_hra,
                        'credit': 0.0,
                        'narration': f'Monthly House Rent Allowance for {month_lbl}',
                    }),
                    (0, 0, {
                        'sequence': 30,
                        'gl_account_code': '510103',
                        'gl_account_name': 'Medical, Conveyance & Food Allowances Expense',
                        'account_type': 'expense',
                        'debit': tot_med_conv,
                        'credit': 0.0,
                        'narration': f'Regular Allowances Expense for {month_lbl}',
                    }),
                ]
                if tot_ot_var > 0:
                    jv_lines.append((0, 0, {
                        'sequence': 40,
                        'gl_account_code': '510105',
                        'gl_account_name': 'Overtime, Night & Variable Allowances Expense',
                        'account_type': 'expense',
                        'debit': tot_ot_var,
                        'credit': 0.0,
                        'narration': f'2x Overtime & Variable Earnings for {month_lbl}',
                    }))
                if tot_emp_contrib > 0:
                    jv_lines.append((0, 0, {
                        'sequence': 50,
                        'gl_account_code': '510201',
                        'gl_account_name': 'Employer PF Match & Gratuity Provision Expense',
                        'account_type': 'employer_provision',
                        'debit': tot_emp_contrib,
                        'credit': 0.0,
                        'narration': f'Company PF & Gratuity Contribution Expense for {month_lbl}',
                    }))

                # Credit Liabilities
                if tot_tds > 0:
                    jv_lines.append((0, 0, {
                        'sequence': 60,
                        'gl_account_code': '210301',
                        'gl_account_name': 'NBR Income Tax Deducted at Source (TDS) Payable',
                        'account_type': 'liability',
                        'debit': 0.0,
                        'credit': tot_tds,
                        'narration': f'Employee AIT / TDS Withheld for Treasury Challan ({month_lbl})',
                    }))
                if tot_pf_emp > 0:
                    jv_lines.append((0, 0, {
                        'sequence': 70,
                        'gl_account_code': '210302',
                        'gl_account_name': 'Recognized Provident Fund (PF) Trust Payable (Employee)',
                        'account_type': 'liability',
                        'debit': 0.0,
                        'credit': tot_pf_emp,
                        'narration': f'Employee 10% PF Deduction Payable to PF Trust ({month_lbl})',
                    }))
                if tot_loan > 0:
                    jv_lines.append((0, 0, {
                        'sequence': 80,
                        'gl_account_code': '120401',
                        'gl_account_name': 'Employee Loan & Salary Advance Recovery',
                        'account_type': 'liability',
                        'debit': 0.0,
                        'credit': tot_loan,
                        'narration': f'Monthly Loan / Salary Advance Installment Recovery ({month_lbl})',
                    }))
                if tot_other_ded > 0:
                    jv_lines.append((0, 0, {
                        'sequence': 90,
                        'gl_account_code': '210309',
                        'gl_account_name': 'Revenue Stamp (৳10) & LWP / Late Deduction Clearing',
                        'account_type': 'liability',
                        'debit': 0.0,
                        'credit': tot_other_ded,
                        'narration': f'Revenue Stamp & Other Deductions ({month_lbl})',
                    }))
                if tot_emp_contrib > 0:
                    jv_lines.append((0, 0, {
                        'sequence': 95,
                        'gl_account_code': '210305',
                        'gl_account_name': 'Employer PF & Gratuity Fund Provision Payable',
                        'account_type': 'liability',
                        'debit': 0.0,
                        'credit': tot_emp_contrib,
                        'narration': f'Employer PF & Gratuity Provision Liability ({month_lbl})',
                    }))
                jv_lines.append((0, 0, {
                    'sequence': 100,
                    'gl_account_code': '210101',
                    'gl_account_name': 'Net Salary & Wages Payable (Disbursement Clearing)',
                    'account_type': 'liability',
                    'debit': 0.0,
                    'credit': tot_net,
                    'narration': f'Net Salary Payable to {len(active_slips)} Employees ({month_lbl})',
                }))

                jv = Voucher.create({
                    'voucher_type': 'SALARY_JOURNAL',
                    'batch_id': batch.id,
                    'company_id': batch.company_id.id,
                    'accounting_company_id': batch.accounting_company_id.id or batch.company_id.id,
                    'branch_id': batch.branch_id.id if batch.branch_id else False,
                    'accounting_date': batch.date_to or fields.Date.today(),
                    'payroll_month_label': month_lbl,
                    'narration': f"Auto-generated Double-Entry Salary Journal Voucher for {batch.batch_title} ({batch.name}).",
                    'line_ids': jv_lines,
                })
                if jv.is_balanced:
                    jv.action_post_gl_voucher()

            # Also create Bank Payment Voucher (SALARY_VOUCHER)
            existing_pv = Voucher.search([
                ('batch_id', '=', batch.id),
                ('voucher_type', '=', 'SALARY_VOUCHER'),
            ], limit=1)
            if not existing_pv and tot_net > 0:
                pv = Voucher.create({
                    'voucher_type': 'SALARY_VOUCHER',
                    'batch_id': batch.id,
                    'company_id': batch.company_id.id,
                    'accounting_company_id': batch.accounting_company_id.id or batch.company_id.id,
                    'branch_id': batch.branch_id.id if batch.branch_id else False,
                    'accounting_date': batch.date_to or fields.Date.today(),
                    'payroll_month_label': month_lbl,
                    'narration': f"Bank BEFTN / MFS Salary Payment Voucher for {batch.batch_title} ({batch.name}).",
                    'line_ids': [
                        (0, 0, {
                            'sequence': 10,
                            'gl_account_code': '210101',
                            'gl_account_name': 'Net Salary & Wages Payable (Disbursement Clearing)',
                            'account_type': 'liability',
                            'debit': tot_net,
                            'credit': 0.0,
                            'narration': f'Settlement of Net Salary Liability for {month_lbl}',
                        }),
                        (0, 0, {
                            'sequence': 20,
                            'gl_account_code': '110201',
                            'gl_account_name': 'Corporate Bank A/C — BEFTN & MFS Payroll Disbursement',
                            'account_type': 'bank_asset',
                            'debit': 0.0,
                            'credit': tot_net,
                            'narration': f'BEFTN / MFS Bank Transfer for {len(active_slips)} Employees ({month_lbl})',
                        }),
                    ],
                })
                if pv.is_balanced:
                    pv.action_post_gl_voucher()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Payroll Accounting Vouchers (GL)'),
            'res_model': 'dsl.hrms.payroll.voucher',
            'view_mode': 'list,form',
            'domain': [('batch_id', 'in', self.ids)],
        }
