/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class DslEssPortal extends Component {
    static template = "DSL_HRMS_ess.EssPortal";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            activeTab: "overview",
            data: {},
        });

        onWillStart(async () => {
            await this.loadEssData();
        });
    }

    setTab(tabKey) {
        this.state.activeTab = tabKey;
    }

    async loadEssData() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call("dsl.ess.portal.service", "get_ess_portal_data", []);
        } finally {
            this.state.loading = false;
        }
    }

    async onWebPunch() {
        const res = await this.orm.call("dsl.ess.portal.service", "action_ess_web_punch", []);
        this.notification.add(
            res.status === "checked_in"
                ? "Checked In successfully!"
                : res.status === "checked_out"
                ? "Checked Out successfully!"
                : "Today's attendance is already completed.",
            { type: "success" }
        );
        await this.loadEssData();
    }

    // Open Logged-In Employee's Own Full Dossier Form
    openMyProfile() {
        const empId = this.state.data?.employee?.id;
        if (!empId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "My Employee Dossier",
            res_model: "hr.employee",
            res_id: empId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // Time, Shift & Leave Actions
    openApplyLeave() {
        this.action.doAction("DSL_HRMS_leave.action_dsl_leave_request");
    }

    openLeaveQuotas() {
        this.action.doAction("DSL_HRMS_leave.action_dsl_leave_allocation");
    }

    openHolidays() {
        this.action.doAction("DSL_HRMS_holiday.action_dsl_holiday_line");
    }

    openRegularize() {
        this.action.doAction("DSL_HRMS_attendance.action_dsl_attendance_regularization");
    }

    openAttendanceLogs() {
        this.action.doAction("DSL_HRMS_attendance.action_dsl_attendance_log");
    }

    openGpsAttendance() {
        this.action.doAction("DSL_HRMS_gps_attendance.action_dsl_gps_attendance");
    }

    openOvertime() {
        this.action.doAction("DSL_HRMS_overtime.action_dsl_overtime_request");
    }

    openShiftRoster() {
        this.action.doAction("DSL_HRMS_shift_roster.action_dsl_shift_roster");
    }

    // Pay, PF, Loan & Tax Actions
    openMyPayslips() {
        this.action.doAction("DSL_HRMS_payroll_bd.action_dsl_payslip");
    }

    openSalaryPackage() {
        this.action.doAction("DSL_HRMS_salary_structure.action_dsl_employee_compensation");
    }

    openSalaryDocRequests() {
        this.action.doAction("DSL_HRMS_payroll_bd.action_dsl_hrms_salary_document_request");
    }

    openApplyLoan() {
        this.action.doAction("DSL_HRMS_loan.action_dsl_employee_loan");
    }

    openProvidentFund() {
        this.action.doAction("DSL_HRMS_provident_fund.action_dsl_pf_account");
    }

    openGratuity() {
        this.action.doAction("DSL_HRMS_gratuity.action_dsl_gratuity_settlement");
    }

    openTaxAssessment() {
        this.action.doAction("DSL_HRMS_tax_bd.action_dsl_emp_tax_assessment");
    }

    // KPI, 360° & Career Actions
    openMyKpis() {
        this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_employee_kpi");
    }

    openMyAssessments() {
        this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_assessment");
    }

    openReviewerInbox() {
        this.action.doAction("DSL_HRMS_appraisal.action_dsl_hrms_assessment_response");
    }

    openEducation() {
        this.action.doAction("DSL_HRMS_education.action_dsl_employee_education");
    }

    openSkills() {
        this.action.doAction("DSL_HRMS_experience.action_dsl_skills_matrix");
    }

    openFamily() {
        this.action.doAction("DSL_HRMS_family.action_dsl_employee_family");
    }

    openNominees() {
        this.action.doAction("DSL_HRMS_employee.action_dsl_employee_nominee");
    }

    // Corporate HR Announcements & Notice Board Actions
    openAnnouncements() {
        this.action.doAction("DSL_HRMS_ess.action_dsl_hr_announcement");
    }

    openAnnouncementRecord(announcementId) {
        if (!announcementId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Official HR Announcement & Circular",
            res_model: "dsl.hr.announcement",
            res_id: announcementId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // Letters, Vault, Assets, Operations & Helpdesk Actions
    openRequestLetter() {
        this.action.doAction("DSL_HRMS_ess.action_dsl_hr_letter_request");
    }

    openDocumentVault() {
        this.action.doAction("DSL_HRMS_document.action_dsl_document_vault");
    }

    openMyAssets() {
        this.action.doAction("DSL_HRMS_onboarding.action_dsl_employee_asset");
    }

    openHelpdesk() {
        this.action.doAction("DSL_HRMS_helpdesk.action_dsl_hr_ticket");
    }

    openCanteen() {
        this.action.doAction("DSL_HRMS_canteen.action_dsl_canteen_meal_log");
    }

    openVehicleReq() {
        this.action.doAction("DSL_HRMS_fleet.action_dsl_vehicle_requisition");
    }

    openSeparation() {
        this.action.doAction("DSL_HRMS_separation.action_dsl_employee_separation");
    }
}

registry.category("actions").add("dsl_hrms_ess_portal", DslEssPortal);
