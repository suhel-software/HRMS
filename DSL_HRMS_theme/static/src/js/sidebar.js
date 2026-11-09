/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { WebClient } from "@web/webclient/webclient";
import { patch } from "@web/core/utils/patch";

const GROUP_ITEMS = {
    organization: ["companies", "branches", "departments", "designations", "grades", "org_chart"],
    employee_mgmt: [
        "employees",
        "education",
        "experience",
        "skills_matrix",
        "family",
        "nominees",
        "emp_assets",
        "document_vault",
        "doc_types_emp",
    ],
    attendance: [
        "attendance",
        "attendance_reg",
        "biometric_devices",
        "gps_attendance",
        "shift_roster",
        "overtime",
        "att_policies_mod",
        "shift_defs_mod",
    ],
    leaves: [
        "leaves",
        "leave_approvals",
        "leave_quotas",
        "leave_batch",
        "holidays",
        "leave_policies_mod",
        "holiday_calendars_mod",
        "approval_chains_mod",
    ],
    payroll: [
        "payroll_batches",
        "payroll",
        "salary_doc_center",
        "payroll_vouchers",
        "salary_packages",
        "salary_structures_pay",
        "salary_heads_pay",
        "tax_bd",
        "loans",
        "provident_fund",
        "pf_profit",
        "gratuity",
        "festival_bonus",
        "nbr_tax_slabs_mod",
        "loan_policies_mod",
        "pf_policies_mod",
        "gratuity_policies_mod",
        "salary_doc_types_mod",
        "salary_doc_tpls_mod",
    ],
    accounting: [
        "acc_dashboard",
        "acc_payroll_vouchers",
        "acc_journal_entries",
        "acc_journal_items",
        "acc_invoices",
        "acc_bills",
        "acc_payments",
        "acc_contra",
        "acc_reconcile",
        "acc_bank_brs",
        "acc_cheque_register",
        "acc_assets",
        "acc_budgets",
        "acc_budget_analysis",
        "acc_budget_positions",
        "acc_job_budgets",
        "acc_cost_advances",
        "acc_bill_adjustments",
    ],
    fixed_assets: [
        "fa_dashboard",
        "fa_register",
        "fa_assignment",
        "fa_transfer",
        "fa_maintenance",
        "fa_verification",
        "fa_disposed",
        "fa_depr_schedule",
        "fa_models",
        "fa_groups",
        "fa_locations",
    ],
    financial_reports: [
        "rep_balance_sheet",
        "rep_profit_loss",
        "rep_cash_flow",
        "rep_exec_summary",
        "rep_tax_return",
        "rep_general_ledger",
        "rep_trial_balance",
        "rep_journal_audit",
        "rep_partner_ledger",
        "rep_aged_receivable",
        "rep_aged_payable",
        "rep_bank_reconciliation",
        "rep_depreciation",
        "rep_deferred_expense",
        "rep_deferred_revenue",
        "rep_multicurrency",
    ],
    self_service: [
        "ess_portal",
        "mss_portal",
        "hr_announcements",
        "mss_recommendations",
        "salary_doc_requests",
        "hr_letters",
        "hr_helpdesk",
        "separations",
    ],
    performance: [
        "assessments_all",
        "assessment_cycles",
        "reviewer_inbox",
        "employee_kpis",
        "hr_calibration",
        "assessment_appeals",
        "employee_pips",
        "increment_recs",
        "appraisals",
        "assessment_policies_mod",
        "assessment_templates_mod",
        "rating_scales_mod",
        "master_kpis_mod",
    ],
    talent: [
        "mpr",
        "ats_pipeline",
        "onboarding",
        "emp_assets",
    ],
    operations: [
        "canteen",
        "fleet_req",
        "fleet_fuel",
        "visitors",
        "factory_lines",
        "factory_audits",
    ],
    settings: [
        "apps",
        "users_access",
        "settings",
        "doc_types",
        "att_policies",
        "shift_defs",
        "leave_policies",
        "holiday_calendars",
        "approval_chains",
        "salary_structures",
        "salary_heads",
        "nbr_tax_slabs",
        "loan_policies",
        "pf_policies",
        "gratuity_policies",
        "salary_doc_types_cfg",
        "salary_doc_tpls_cfg",
        "assessment_policies_cfg",
        "assessment_templates_cfg",
        "rating_scales_cfg",
        "master_kpis_cfg",
        "corporate_goals_cfg",
        "acc_coa_cfg",
        "acc_journals_cfg",
        "acc_taxes_cfg",
        "acc_fiscal_years_cfg",
        "acc_asset_models_cfg",
    ],
};

export class DslSidebar extends Component {
    static template = "DSL_HRMS_theme.DslSidebar";
    static props = {
        isCollapsed: { type: Boolean, optional: true },
        onToggle: { type: Function, optional: true },
    };

    setup() {
        const rawAction = useService("action");
        this.action = {
            ...rawAction,
            doAction: (actionRequest, options = {}) =>
                rawAction.doAction(actionRequest, {
                    clearBreadcrumbs: true,
                    ...options,
                }),
        };
        this.menu = useService("menu");
        this.orm = useService("orm");
        this.user = user;
        // Start with openGroup: "" so no menu group auto-expands on login/Dashboard!
        this.state = useState({
            currentSection: "dashboard",
            openGroup: "",
            installed: {},
            navProfile: {},
        });

        onWillStart(async () => {
            await this.refreshInstalledModules();
        });
    }

    async refreshInstalledModules() {
        try {
            const mods = await this.orm.call("dsl.hrms.nav.helper", "get_installed_dsl_modules", []);
            this.state.installed = mods || {};
            this.state.navProfile = mods?.__nav_profile__ || {};
        } catch (e) {
            this.state.installed = {};
            this.state.navProfile = {};
        }
    }

    hasModule(modName) {
        return Boolean(this.state.installed[modName]);
    }

    canAccess(accessKey) {
        if (!this.state.navProfile || Object.keys(this.state.navProfile).length === 0) {
            return true;
        }
        const hidden = this.state.navProfile.hidden_menu_codes || [];
        if (hidden.includes(accessKey)) {
            return false;
        }
        if ("allow_" + accessKey in this.state.navProfile) {
            return Boolean(this.state.navProfile["allow_" + accessKey]);
        }
        return true;
    }

    canAccessMss() {
        if (!this.state.navProfile || Object.keys(this.state.navProfile).length === 0) {
            return true;
        }
        const hidden = this.state.navProfile.hidden_menu_codes || [];
        if (hidden.includes("mss_portal") || hidden.includes("self_service")) {
            return false;
        }
        const codes = this.state.navProfile.role_codes || [];
        return Boolean(
            this.state.navProfile.is_super_admin ||
            codes.some((c) => ["super_admin", "company_admin", "hr_manager", "hr_officer", "manager"].includes(c))
        );
    }

    get roleBadgeLabel() {
        return this.state.navProfile?.short_role_label || "Administrator";
    }

    get fullRoleTooltip() {
        return this.state.navProfile?.role_badge_label || "DSL Enterprise HRMS";
    }

    isCurrentSection(section) {
        return this.state.currentSection === section;
    }

    isGroupOpen(groupKey) {
        return !this.props.isCollapsed && this.state.openGroup === groupKey;
    }

    isGroupActive(groupKey) {
        const items = GROUP_ITEMS[groupKey] || [];
        return items.includes(this.state.currentSection);
    }

    toggleGroup(groupKey) {
        if (this.props.isCollapsed) {
            if (this.props.onToggle) {
                this.props.onToggle();
            }
            this.state.openGroup = groupKey;
            return;
        }
        // Accordion behavior: opening a group collapses others
        this.state.openGroup = this.state.openGroup === groupKey ? "" : groupKey;
    }

    setSection(section, groupKey = null) {
        this.state.currentSection = section;
        if (groupKey) {
            this.state.openGroup = groupKey;
        } else if (section === "dashboard") {
            this.state.openGroup = "";
        }
    }

    // 1. Dashboard (Routes dynamically based on user's assigned Role Template)
    async openDashboard() {
        this.setSection("dashboard");
        const primary = this.state.navProfile?.primary_dashboard || "hr";
        try {
            if (primary === "ess" && this.hasModule("DSL_HRMS_ess")) {
                await this.action.doAction("DSL_HRMS_ess.action_dsl_ess_portal");
                return;
            }
            if (primary === "mss" && this.hasModule("DSL_HRMS_mss")) {
                await this.action.doAction("DSL_HRMS_mss.action_dsl_mss_portal");
                return;
            }
            await this.action.doAction("DSL_HRMS_dashboard.action_dsl_hrms_dashboard");
        } catch (e) {
            const apps = this.menu.getApps();
            const hrmsApp = apps.find((a) => a.xmlid && a.xmlid.includes("dsl_hrms"));
            if (hrmsApp) {
                await this.menu.selectMenu(hrmsApp);
            }
        }
    }

    // 2. Organization Group
    async openCompanies() {
        this.setSection("companies", "organization");
        await this.action.doAction("DSL_HRMS_multi_company.action_dsl_hrms_company_tree_studio");
    }

    async openBranches() {
        this.setSection("branches", "organization");
        await this.action.doAction("DSL_HRMS_branch.action_dsl_branch");
    }

    async openDepartments() {
        this.setSection("departments", "organization");
        await this.action.doAction("hr.hr_department_tree_action");
    }

    async openDesignations() {
        this.setSection("designations", "organization");
        await this.action.doAction("DSL_HRMS_organization.action_dsl_designations");
    }

    async openGrades() {
        this.setSection("grades", "organization");
        await this.action.doAction("DSL_HRMS_organization.action_dsl_hr_grade");
    }

    async openOrgChart() {
        this.setSection("org_chart", "organization");
        await this.action.doAction("DSL_HRMS_organization.action_dsl_org_chart_studio");
    }

    // 3. Employee Management Group
    async openEmployees() {
        this.setSection("employees", "employee_mgmt");
        await this.action.doAction("hr.open_view_employee_list_my");
    }

    async openEducation() {
        this.setSection("education", "employee_mgmt");
        await this.action.doAction("DSL_HRMS_education.action_dsl_employee_education");
    }

    async openExperience() {
        this.setSection("experience", "employee_mgmt");
        await this.action.doAction("DSL_HRMS_experience.action_dsl_employee_experience");
    }

    async openSkillsMatrix() {
        this.setSection("skills_matrix", "employee_mgmt");
        await this.action.doAction("DSL_HRMS_experience.action_dsl_skills_matrix");
    }

    async openFamily() {
        this.setSection("family", "employee_mgmt");
        await this.action.doAction("DSL_HRMS_family.action_dsl_employee_family");
    }

    async openNominees() {
        this.setSection("nominees", "employee_mgmt");
        await this.action.doAction("DSL_HRMS_employee.action_dsl_employee_nominee");
    }

    async openDocumentVault() {
        this.setSection("document_vault", "employee_mgmt");
        await this.action.doAction("DSL_HRMS_document.action_dsl_document_vault");
    }

    async openDocumentTypesFromEmp() {
        this.setSection("doc_types_emp", "employee_mgmt");
        await this.action.doAction("DSL_HRMS_document.action_dsl_document_types");
    }

    // 4. Attendance & Shift Group
    async openAttendance() {
        this.setSection("attendance", "attendance");
        try {
            if (this.hasModule("DSL_HRMS_attendance")) {
                await this.action.doAction("DSL_HRMS_attendance.action_dsl_attendance_log");
                return;
            }
            await this.action.doAction("hr_attendance.hr_attendance_action");
        } catch (e) {
            await this.openEmployees();
        }
    }

    async openAttendanceRegularization() {
        this.setSection("attendance_reg", "attendance");
        await this.action.doAction("DSL_HRMS_attendance.action_dsl_attendance_regularization");
    }

    async openBiometricDevices() {
        this.setSection("biometric_devices", "attendance");
        await this.action.doAction("DSL_HRMS_attendance_device.action_dsl_biometric_device");
    }

    async openGpsAttendance() {
        this.setSection("gps_attendance", "attendance");
        await this.action.doAction("DSL_HRMS_gps_attendance.action_dsl_gps_attendance");
    }

    async openShiftRoster() {
        this.setSection("shift_roster", "attendance");
        await this.action.doAction("DSL_HRMS_shift_roster.action_dsl_shift_roster");
    }

    async openOvertime() {
        this.setSection("overtime", "attendance");
        await this.action.doAction("DSL_HRMS_overtime.action_dsl_overtime_request");
    }

    async openAttendancePoliciesFromMod() {
        this.setSection("att_policies_mod", "attendance");
        await this.action.doAction("DSL_HRMS_attendance.action_dsl_attendance_policy");
    }

    async openShiftDefsFromMod() {
        this.setSection("shift_defs_mod", "attendance");
        await this.action.doAction("DSL_HRMS_shift_roster.action_dsl_hr_shift");
    }

    // 5. Leave Management Group
    async openLeaves() {
        this.setSection("leaves", "leaves");
        try {
            if (this.hasModule("DSL_HRMS_leave")) {
                await this.action.doAction("DSL_HRMS_leave.action_dsl_leave_request");
                return;
            }
            await this.action.doAction("hr_holidays.hr_leave_action_action_approve_department");
        } catch (e) {
            await this.openEmployees();
        }
    }

    async openLeaveApprovals() {
        this.setSection("leave_approvals", "leaves");
        await this.action.doAction("DSL_HRMS_leave_approval.action_dsl_leave_pending_approvals");
    }

    async openLeaveQuotas() {
        this.setSection("leave_quotas", "leaves");
        await this.action.doAction("DSL_HRMS_leave.action_dsl_leave_allocation");
    }

    async openLeaveBatch() {
        this.setSection("leave_batch", "leaves");
        await this.action.doAction("DSL_HRMS_leave.action_dsl_leave_allocation_batch");
    }

    async openHolidays() {
        this.setSection("holidays", "leaves");
        await this.action.doAction("DSL_HRMS_holiday.action_dsl_holiday_line");
    }

    async openLeavePoliciesFromMod() {
        this.setSection("leave_policies_mod", "leaves");
        await this.action.doAction("DSL_HRMS_leave.action_dsl_leave_type");
    }

    async openHolidayCalendarsFromMod() {
        this.setSection("holiday_calendars_mod", "leaves");
        await this.action.doAction("DSL_HRMS_holiday.action_dsl_holiday_calendar");
    }

    async openApprovalChainsFromMod() {
        this.setSection("approval_chains_mod", "leaves");
        await this.action.doAction("DSL_HRMS_leave_approval.action_dsl_leave_approval_chain");
    }

    // 6. Payroll & Benefits Group
    async openPayrollBatches() {
        this.setSection("payroll_batches", "payroll");
        await this.action.doAction("DSL_HRMS_payroll_bd.action_dsl_payslip_run");
    }

    async openPayroll() {
        this.setSection("payroll", "payroll");
        if (this.hasModule("DSL_HRMS_payroll_bd")) {
            await this.action.doAction("DSL_HRMS_payroll_bd.action_dsl_payslip");
            return;
        }
        await this.openEmployees();
    }

    async openSalaryPackages() {
        this.setSection("salary_packages", "payroll");
        await this.action.doAction("DSL_HRMS_salary_structure.action_dsl_employee_compensation");
    }

    async openSalaryStructuresFromPayroll() {
        this.setSection("salary_structures_pay", "payroll");
        await this.action.doAction("DSL_HRMS_salary_structure.action_dsl_salary_structure");
    }

    async openSalaryHeadsFromPayroll() {
        this.setSection("salary_heads_pay", "payroll");
        await this.action.doAction("DSL_HRMS_salary_structure.action_dsl_salary_head");
    }

    async openTaxBd() {
        this.setSection("tax_bd", "payroll");
        await this.action.doAction("DSL_HRMS_tax_bd.action_dsl_emp_tax_assessment");
    }

    async openLoans() {
        this.setSection("loans", "payroll");
        await this.action.doAction("DSL_HRMS_loan.action_dsl_employee_loan");
    }

    async openProvidentFund() {
        this.setSection("provident_fund", "payroll");
        await this.action.doAction("DSL_HRMS_provident_fund.action_dsl_pf_account");
    }

    async openPfProfit() {
        this.setSection("pf_profit", "payroll");
        await this.action.doAction("DSL_HRMS_provident_fund.action_dsl_pf_profit_dist");
    }

    async openGratuity() {
        this.setSection("gratuity", "payroll");
        await this.action.doAction("DSL_HRMS_gratuity.action_dsl_gratuity_settlement");
    }

    async openFestivalBonus() {
        this.setSection("festival_bonus", "payroll");
        await this.action.doAction("DSL_HRMS_festival_bonus.action_dsl_festival_bonus_run");
    }

    async openNbrTaxSlabsFromMod() {
        this.setSection("nbr_tax_slabs_mod", "payroll");
        await this.action.doAction("DSL_HRMS_tax_bd.action_dsl_tax_fiscal_policy");
    }

    async openLoanPoliciesFromMod() {
        this.setSection("loan_policies_mod", "payroll");
        await this.action.doAction("DSL_HRMS_loan.action_dsl_loan_policy");
    }

    async openPfPoliciesFromMod() {
        this.setSection("pf_policies_mod", "payroll");
        await this.action.doAction("DSL_HRMS_provident_fund.action_dsl_pf_policy");
    }

    async openGratuityPoliciesFromMod() {
        this.setSection("gratuity_policies_mod", "payroll");
        await this.action.doAction("DSL_HRMS_gratuity.action_dsl_gratuity_policy");
    }

    async openSalaryDocumentCenter() {
        this.setSection("salary_doc_center", "payroll");
        await this.action.doAction("DSL_HRMS_payroll_bd.action_dsl_hrms_salary_document");
    }

    async openSalaryDocRequests() {
        this.setSection("salary_doc_requests", "self_service");
        await this.action.doAction("DSL_HRMS_payroll_bd.action_dsl_hrms_salary_document_request");
    }

    async openPayrollVouchers() {
        this.setSection("payroll_vouchers", "payroll");
        await this.action.doAction("DSL_HRMS_payroll_bd.action_dsl_hrms_payroll_voucher");
    }

    async openSalaryDocTypesMod() {
        this.setSection("salary_doc_types_mod", "payroll");
        await this.action.doAction("DSL_HRMS_payroll_bd.action_dsl_hrms_salary_document_type");
    }

    async openSalaryDocTemplatesMod() {
        this.setSection("salary_doc_tpls_mod", "payroll");
        await this.action.doAction("DSL_HRMS_payroll_bd.action_dsl_hrms_salary_document_template");
    }

    async openSalaryDocTypesCfg() {
        this.setSection("salary_doc_types_cfg", "settings");
        await this.action.doAction("DSL_HRMS_payroll_bd.action_dsl_hrms_salary_document_type");
    }

    async openSalaryDocTemplatesCfg() {
        this.setSection("salary_doc_tpls_cfg", "settings");
        await this.action.doAction("DSL_HRMS_payroll_bd.action_dsl_hrms_salary_document_template");
    }

    // 6A. Accounting & Finance (DSL_HRMS_accounting / at_accounting)
    async openAccDashboard() {
        this.setSection("acc_dashboard", "accounting");
        await this.action.doAction("account.open_account_journal_dashboard_kanban");
    }

    async openAccPayrollVouchers() {
        this.setSection("acc_payroll_vouchers", "accounting");
        await this.action.doAction("DSL_HRMS_payroll_bd.action_dsl_hrms_payroll_voucher");
    }

    async openAccJournalEntries() {
        this.setSection("acc_journal_entries", "accounting");
        await this.action.doAction("account.action_move_journal_line");
    }

    async openAccJournalItems() {
        this.setSection("acc_journal_items", "accounting");
        await this.action.doAction("account.action_account_moves_all");
    }

    async openAccInvoices() {
        this.setSection("acc_invoices", "accounting");
        await this.action.doAction("account.action_move_out_invoice_type");
    }

    async openAccBills() {
        this.setSection("acc_bills", "accounting");
        await this.action.doAction("account.action_move_in_invoice_type");
    }

    async openAccPayments() {
        this.setSection("acc_payments", "accounting");
        await this.action.doAction("account.action_account_payments");
    }

    async openAccContra() {
        this.setSection("acc_contra", "accounting");
        await this.action.doAction("DSL_HRMS_contra.action_dsl_contra_voucher");
    }

    async openAccChequeRegister() {
        this.setSection("acc_cheque_register", "accounting");
        await this.action.doAction("DSL_HRMS_bank_reconciliation.action_dsl_cheque_register");
    }

    async openAccBankBrs() {
        this.setSection("acc_bank_brs", "accounting");
        await this.action.doAction("DSL_HRMS_bank_reconciliation.action_dsl_bank_reconciliation");
    }

    async openAccReconcile() {
        this.setSection("acc_reconcile", "accounting");
        await this.action.doAction("DSL_HRMS_accounting.action_move_line_posted_unreconciled");
    }

    async openAccAssets() {
        this.setSection("acc_assets", "accounting");
        await this.action.doAction("DSL_HRMS_fixed_asset.action_account_asset_form");
    }

    // 6B. Fixed Asset Management (DSL_HRMS_fixed_asset)
    async _openFa(section, xmlid) {
        this.setSection(section, "fixed_assets");
        await this.action.doAction(xmlid);
    }

    openFaDashboard() { return this._openFa("fa_dashboard", "DSL_HRMS_fixed_asset.action_dsl_fixed_asset_dashboard"); }
    openFaRegister() { return this._openFa("fa_register", "DSL_HRMS_fixed_asset.action_dsl_fixed_asset_register"); }
    openFaAssignment() { return this._openFa("fa_assignment", "DSL_HRMS_fixed_asset.action_dsl_asset_assignment"); }
    openFaTransfer() { return this._openFa("fa_transfer", "DSL_HRMS_fixed_asset.action_dsl_asset_transfer"); }
    openFaMaintenance() { return this._openFa("fa_maintenance", "DSL_HRMS_fixed_asset.action_dsl_asset_maintenance"); }
    openFaVerification() { return this._openFa("fa_verification", "DSL_HRMS_fixed_asset.action_dsl_asset_verification"); }
    openFaDisposed() { return this._openFa("fa_disposed", "DSL_HRMS_fixed_asset.action_dsl_fixed_asset_disposed"); }
    openFaDeprSchedule() { return this._openFa("fa_depr_schedule", "DSL_HRMS_fixed_asset.action_account_report_assets"); }
    openFaModels() { return this._openFa("fa_models", "DSL_HRMS_fixed_asset.action_account_asset_model_form"); }
    openFaGroups() { return this._openFa("fa_groups", "DSL_HRMS_fixed_asset.action_dsl_asset_group"); }
    openFaLocations() { return this._openFa("fa_locations", "DSL_HRMS_fixed_asset.action_dsl_asset_location"); }

    async openAccBudgets() {
        this.setSection("acc_budgets", "accounting");
        if (this.hasModule("DSL_HRMS_budget")) {
            await this.action.doAction("DSL_HRMS_budget.act_crossovered_budget_view");
            return;
        }
        await this.action.doAction("DSL_HRMS_accounting.action_account_report_budget_tree");
    }

    async openAccBudgetAnalysis() {
        this.setSection("acc_budget_analysis", "accounting");
        await this.action.doAction("DSL_HRMS_budget.act_crossovered_budget_lines_view");
    }

    async openAccBudgetPositions() {
        this.setSection("acc_budget_positions", "accounting");
        await this.action.doAction("DSL_HRMS_budget.open_budget_post_form");
    }

    async openAccJobBudgets() {
        this.setSection("acc_job_budgets", "accounting");
        await this.action.doAction("DSL_HRMS_budget.action_dsl_job_summary");
    }

    async openAccCostAdvances() {
        this.setSection("acc_cost_advances", "accounting");
        await this.action.doAction("DSL_HRMS_budget.action_dsl_cost_advance");
    }

    async openAccBillAdjustments() {
        this.setSection("acc_bill_adjustments", "accounting");
        await this.action.doAction("DSL_HRMS_budget.action_dsl_bill_adjustment");
    }

    // Financial Statements (at_accounting)
    async openRepBalanceSheet() {
        this.setSection("rep_balance_sheet", "financial_reports");
        await this.action.doAction("DSL_HRMS_account_reports.action_account_report_bs");
    }

    async openRepProfitLoss() {
        this.setSection("rep_profit_loss", "financial_reports");
        await this.action.doAction("DSL_HRMS_account_reports.action_account_report_pl");
    }

    async openRepCashFlow() {
        this.setSection("rep_cash_flow", "financial_reports");
        await this.action.doAction("DSL_HRMS_account_reports.action_account_report_cs");
    }

    async openRepExecSummary() {
        this.setSection("rep_exec_summary", "financial_reports");
        await this.action.doAction("DSL_HRMS_account_reports.action_account_report_exec_summary");
    }

    async openRepTaxReturn() {
        this.setSection("rep_tax_return", "financial_reports");
        await this.action.doAction("DSL_HRMS_account_reports.action_account_report_gt");
    }

    // Ledger, Audit & Aged Reports (at_accounting)
    async openRepGeneralLedger() {
        this.setSection("rep_general_ledger", "financial_reports");
        await this.action.doAction("DSL_HRMS_account_reports.action_account_report_general_ledger");
    }

    async openRepTrialBalance() {
        this.setSection("rep_trial_balance", "financial_reports");
        await this.action.doAction("DSL_HRMS_account_reports.action_account_report_coa");
    }

    async openRepJournalAudit() {
        this.setSection("rep_journal_audit", "financial_reports");
        await this.action.doAction("DSL_HRMS_account_reports.action_account_report_ja");
    }

    async openRepPartnerLedger() {
        this.setSection("rep_partner_ledger", "financial_reports");
        await this.action.doAction("DSL_HRMS_account_reports.action_account_report_partner_ledger");
    }

    async openRepAgedReceivable() {
        this.setSection("rep_aged_receivable", "financial_reports");
        await this.action.doAction("DSL_HRMS_account_reports.action_account_report_ar");
    }

    async openRepAgedPayable() {
        this.setSection("rep_aged_payable", "financial_reports");
        await this.action.doAction("DSL_HRMS_account_reports.action_account_report_ap");
    }

    async openRepBankReconciliation() {
        this.setSection("rep_bank_reconciliation", "financial_reports");
        await this.action.doAction("DSL_HRMS_account_reports.action_account_report_bank_reconciliation");
    }

    async openRepDepreciation() {
        this.setSection("rep_depreciation", "financial_reports");
        await this.action.doAction("DSL_HRMS_fixed_asset.action_account_report_assets");
    }

    async openRepDeferredExpense() {
        this.setSection("rep_deferred_expense", "financial_reports");
        await this.action.doAction("DSL_HRMS_account_reports.action_account_report_deferred_expense");
    }

    async openRepDeferredRevenue() {
        this.setSection("rep_deferred_revenue", "financial_reports");
        await this.action.doAction("DSL_HRMS_account_reports.action_account_report_deferred_revenue");
    }

    async openRepMulticurrency() {
        this.setSection("rep_multicurrency", "financial_reports");
        await this.action.doAction("DSL_HRMS_account_reports.action_account_report_multicurrency_revaluation");
    }

    // Accounting Config
    async openAccCoaMod() {
        this.setSection("acc_coa_mod", "accounting");
        await this.action.doAction("account.action_account_form");
    }

    async openAccJournalsMod() {
        this.setSection("acc_journals_mod", "accounting");
        await this.action.doAction("account.action_account_journal_form");
    }

    async openAccTaxesMod() {
        this.setSection("acc_taxes_mod", "accounting");
        await this.action.doAction("account.action_tax_form");
    }

    async openAccFiscalYearsMod() {
        this.setSection("acc_fiscal_years_mod", "accounting");
        await this.action.doAction("DSL_HRMS_accounting.actions_account_fiscal_year");
    }

    async openAccAssetModelsMod() {
        this.setSection("acc_asset_models_mod", "accounting");
        await this.action.doAction("DSL_HRMS_fixed_asset.action_account_asset_model_form");
    }

    // 6B. Self-Service & HR Desk Group
    async openEssPortal() {
        this.setSection("ess_portal", "self_service");
        await this.action.doAction("DSL_HRMS_ess.action_dsl_ess_portal");
    }

    async openMssPortal() {
        this.setSection("mss_portal", "self_service");
        await this.action.doAction("DSL_HRMS_mss.action_dsl_mss_portal");
    }

    async openHrAnnouncements() {
        this.setSection("hr_announcements", "self_service");
        await this.action.doAction("DSL_HRMS_ess.action_dsl_hr_announcement");
    }

    async openMssRecommendations() {
        this.setSection("mss_recommendations", "self_service");
        await this.action.doAction("DSL_HRMS_mss.action_dsl_mss_recommendation");
    }

    async openHrLetters() {
        this.setSection("hr_letters", "self_service");
        await this.action.doAction("DSL_HRMS_ess.action_dsl_hr_letter_request");
    }

    async openHrHelpdesk() {
        this.setSection("hr_helpdesk", "self_service");
        await this.action.doAction("DSL_HRMS_helpdesk.action_dsl_hr_ticket");
    }

    async openSeparations() {
        this.setSection("separations", "self_service");
        await this.action.doAction("DSL_HRMS_separation.action_dsl_employee_separation");
    }

    // 6C. Performance & 360° Assessment Engine Group
    async openAssessmentsAll() {
        this.setSection("assessments_all", "performance");
        await this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_assessment");
    }

    async openAssessmentCycles() {
        this.setSection("assessment_cycles", "performance");
        await this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_assessment_cycle");
    }

    async openReviewerInbox() {
        this.setSection("reviewer_inbox", "performance");
        await this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_assessment_response");
    }

    async openEmployeeKpis() {
        this.setSection("employee_kpis", "performance");
        await this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_employee_kpi");
    }

    async openHrCalibration() {
        this.setSection("hr_calibration", "performance");
        await this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_assessment_calibration");
    }

    async openAssessmentAppeals() {
        this.setSection("assessment_appeals", "performance");
        await this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_assessment_appeal");
    }

    async openEmployeePips() {
        this.setSection("employee_pips", "performance");
        await this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_employee_pip");
    }

    async openIncrementRecs() {
        this.setSection("increment_recs", "performance");
        await this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_increment_recommendation");
    }

    async openAppraisals() {
        this.setSection("appraisals", "performance");
        await this.action.doAction("DSL_HRMS_appraisal.action_dsl_employee_appraisal");
    }

    async openAssessmentPoliciesFromMod() {
        this.setSection("assessment_policies_mod", "performance");
        await this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_assessment_policy");
    }

    async openAssessmentTemplatesFromMod() {
        this.setSection("assessment_templates_mod", "performance");
        await this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_assessment_template");
    }

    async openRatingScalesFromMod() {
        this.setSection("rating_scales_mod", "performance");
        await this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_assessment_rating_scale");
    }

    async openMasterKpisFromMod() {
        this.setSection("master_kpis_mod", "performance");
        await this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_kpi");
    }

    // 6D. Recruitment & Onboarding Group
    async openManpowerRequisitions() {
        this.setSection("mpr", "talent");
        await this.action.doAction("DSL_HRMS_recruitment.action_dsl_manpower_requisition");
    }

    async openAtsPipeline() {
        this.setSection("ats_pipeline", "talent");
        await this.action.doAction("DSL_HRMS_recruitment.action_dsl_job_applicant");
    }

    async openOnboarding() {
        this.setSection("onboarding", "talent");
        await this.action.doAction("DSL_HRMS_onboarding.action_dsl_employee_onboarding");
    }

    async openEmployeeAssets() {
        this.setSection("emp_assets", "employee_mgmt");
        await this.action.doAction("DSL_HRMS_onboarding.action_dsl_employee_asset");
    }

    // 6E. Operations, Facility & Factory Group
    async openCanteen() {
        this.setSection("canteen", "operations");
        await this.action.doAction("DSL_HRMS_canteen.action_dsl_canteen_meal_log");
    }

    async openFleetRequisitions() {
        this.setSection("fleet_req", "operations");
        await this.action.doAction("DSL_HRMS_fleet.action_dsl_vehicle_requisition");
    }

    async openFleetFuel() {
        this.setSection("fleet_fuel", "operations");
        await this.action.doAction("DSL_HRMS_fleet.action_dsl_vehicle_fuel_log");
    }

    async openVisitors() {
        this.setSection("visitors", "operations");
        await this.action.doAction("DSL_HRMS_visitor.action_dsl_visitor_pass");
    }

    async openFactoryLines() {
        this.setSection("factory_lines", "operations");
        await this.action.doAction("DSL_HRMS_factory_garments.action_dsl_factory_line_roster");
    }

    async openFactoryAudits() {
        this.setSection("factory_audits", "operations");
        await this.action.doAction("DSL_HRMS_factory_garments.action_dsl_factory_compliance_audit");
    }

    // 7. System & Module-Grouped Settings
    async openApps() {
        this.setSection("apps", "settings");
        await this.action.doAction("base.open_module_tree");
    }

    async openDocumentTypes() {
        this.setSection("doc_types", "settings");
        await this.action.doAction("DSL_HRMS_document.action_dsl_document_types");
    }

    async openAttendancePolicies() {
        this.setSection("att_policies", "settings");
        await this.action.doAction("DSL_HRMS_attendance.action_dsl_attendance_policy");
    }

    async openShiftDefinitions() {
        this.setSection("shift_defs", "settings");
        await this.action.doAction("DSL_HRMS_shift_roster.action_dsl_hr_shift");
    }

    async openLeavePolicies() {
        this.setSection("leave_policies", "settings");
        await this.action.doAction("DSL_HRMS_leave.action_dsl_leave_type");
    }

    async openHolidayCalendars() {
        this.setSection("holiday_calendars", "settings");
        await this.action.doAction("DSL_HRMS_holiday.action_dsl_holiday_calendar");
    }

    async openApprovalChains() {
        this.setSection("approval_chains", "settings");
        await this.action.doAction("DSL_HRMS_leave_approval.action_dsl_leave_approval_chain");
    }

    async openSalaryStructures() {
        this.setSection("salary_structures", "settings");
        await this.action.doAction("DSL_HRMS_salary_structure.action_dsl_salary_structure");
    }

    async openSalaryHeads() {
        this.setSection("salary_heads", "settings");
        await this.action.doAction("DSL_HRMS_salary_structure.action_dsl_salary_head");
    }

    async openNbrTaxSlabs() {
        this.setSection("nbr_tax_slabs", "settings");
        await this.action.doAction("DSL_HRMS_tax_bd.action_dsl_tax_fiscal_policy");
    }

    async openLoanPolicies() {
        this.setSection("loan_policies", "settings");
        await this.action.doAction("DSL_HRMS_loan.action_dsl_loan_policy");
    }

    async openPfPolicies() {
        this.setSection("pf_policies", "settings");
        await this.action.doAction("DSL_HRMS_provident_fund.action_dsl_pf_policy");
    }

    async openGratuityPolicies() {
        this.setSection("gratuity_policies", "settings");
        await this.action.doAction("DSL_HRMS_gratuity.action_dsl_gratuity_policy");
    }

    async openAssessmentPoliciesCfg() {
        this.setSection("assessment_policies_cfg", "settings");
        await this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_assessment_policy");
    }

    async openAssessmentTemplatesCfg() {
        this.setSection("assessment_templates_cfg", "settings");
        await this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_assessment_template");
    }

    async openRatingScalesCfg() {
        this.setSection("rating_scales_cfg", "settings");
        await this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_assessment_rating_scale");
    }

    async openMasterKpisCfg() {
        this.setSection("master_kpis_cfg", "settings");
        await this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_kpi");
    }

    async openCorporateGoalsCfg() {
        this.setSection("corporate_goals_cfg", "settings");
        await this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_goal");
    }

    async openAccCoaCfg() {
        this.setSection("acc_coa_cfg", "settings");
        await this.action.doAction("account.action_account_form");
    }

    async openAccJournalsCfg() {
        this.setSection("acc_journals_cfg", "settings");
        await this.action.doAction("account.action_account_journal_form");
    }

    async openAccTaxesCfg() {
        this.setSection("acc_taxes_cfg", "settings");
        await this.action.doAction("account.action_tax_form");
    }

    async openAccFiscalYearsCfg() {
        this.setSection("acc_fiscal_years_cfg", "settings");
        await this.action.doAction("DSL_HRMS_accounting.actions_account_fiscal_year");
    }

    async openAccAssetModelsCfg() {
        this.setSection("acc_asset_models_cfg", "settings");
        await this.action.doAction("DSL_HRMS_fixed_asset.action_account_asset_model_form");
    }

    async openUsersAccess() {
        this.setSection("users_access", "settings");
        if (this.hasModule("DSL_HRMS_multi_company")) {
            await this.action.doAction("DSL_HRMS_multi_company.action_dsl_company_users_access");
            return;
        }
        await this.action.doAction("base.action_res_users");
    }

    async openRoleTemplates() {
        this.setSection("role_templates", "settings");
        if (this.hasModule("DSL_HRMS_multi_company")) {
            await this.action.doAction("DSL_HRMS_multi_company.action_dsl_access_role_template");
            return;
        }
    }

    async openSettings() {
        this.setSection("settings", "settings");
        await this.action.doAction("DSL_HRMS_core.action_dsl_hrms_config_settings");
    }

    logout() {
        window.location.href = "/web/session/logout";
    }
}

// Patch WebClient to include DslSidebar and sidebar collapse state
WebClient.components = {
    ...WebClient.components,
    DslSidebar,
};

patch(WebClient.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.sidebarCollapsed = false;
    },
    toggleSidebar() {
        this.state.sidebarCollapsed = !this.state.sidebarCollapsed;
    },
});
