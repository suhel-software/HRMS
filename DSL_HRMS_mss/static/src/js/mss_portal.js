/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class DslMssPortal extends Component {
    static template = "DSL_HRMS_mss.MssPortal";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            data: { kpis: {}, announcements: [], pending_leaves: [], team_roster: [] },
        });

        onWillStart(async () => {
            await this.loadMssData();
        });
    }

    async loadMssData() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call("dsl.mss.portal.service", "get_mss_portal_data", []);
        } finally {
            this.state.loading = false;
        }
    }

    async onQuickApproveLeave(leaveId) {
        await this.orm.call("dsl.mss.portal.service", "action_mss_quick_approve_leave", [leaveId]);
        this.notification.add("Leave application approved!", { type: "success" });
        await this.loadMssData();
    }

    openNewRecommendation() {
        this.action.doAction("DSL_HRMS_mss.action_dsl_mss_recommendation");
    }

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

    openNewAnnouncement() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Post New HR / Management Announcement",
            res_model: "dsl.hr.announcement",
            views: [[false, "form"]],
            target: "current",
        });
    }

    openPendingLeaves() {
        this.action.doAction("DSL_HRMS_leave.action_dsl_leave_request");
    }

    openPendingOvertime() {
        this.action.doAction("DSL_HRMS_overtime.action_dsl_overtime_request");
    }

    openPendingRegularization() {
        this.action.doAction("DSL_HRMS_attendance.action_dsl_attendance_regularization");
    }
}

registry.category("actions").add("dsl_hrms_mss_portal", DslMssPortal);
