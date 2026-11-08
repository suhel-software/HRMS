/** @odoo-module **/

import { Component, onWillStart, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { loadJS } from "@web/core/assets";

export class DslHrmsDashboard extends Component {
    static template = "DSL_HRMS_dashboard.MainDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.user = user;

        this.payrollCanvasRef = useRef("payrollChart");
        this.attendanceCanvasRef = useRef("attendanceChart");

        this.state = useState({
            loading: true,
            data: {},
        });

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.loadData();
        });

        useEffect(
            () => {
                if (!this.state.loading) {
                    this.renderCharts();
                }
            },
            () => [this.state.loading]
        );
    }

    async loadData() {
        this.state.loading = true;
        try {
            const res = await this.orm.call("dsl_hrms.dashboard", "get_dashboard_data", []);
            this.state.data = res;
            const nav = res?.nav_profile || {};
            const forceHr = Boolean(this.props.action?.context?.force_hr_dashboard);
            if (!forceHr && nav.primary_dashboard === "ess") {
                await this.action.doAction("DSL_HRMS_ess.action_dsl_ess_portal", { clearBreadcrumbs: true });
                return;
            }
            if (!forceHr && nav.primary_dashboard === "mss") {
                await this.action.doAction("DSL_HRMS_mss.action_dsl_mss_portal", { clearBreadcrumbs: true });
                return;
            }
        } catch (e) {
            console.error("Error loading dashboard data:", e);
        } finally {
            this.state.loading = false;
        }
    }

    renderCharts() {
        // 1. Payroll 6-Month Trend Chart
        if (this.payrollCanvasRef.el && window.Chart) {
            const ctx = this.payrollCanvasRef.el.getContext("2d");
            const gradient = ctx.createLinearGradient(0, 0, 0, 250);
            gradient.addColorStop(0, "rgba(79, 70, 229, 0.35)");
            gradient.addColorStop(1, "rgba(79, 70, 229, 0.0)");

            new window.Chart(ctx, {
                type: "line",
                data: {
                    labels: this.state.data.payroll_trend?.labels || [],
                    datasets: [
                        {
                            label: "Payroll (BDT)",
                            data: this.state.data.payroll_trend?.data || [],
                            borderColor: "#4f46e5",
                            borderWidth: 3,
                            backgroundColor: gradient,
                            fill: true,
                            tension: 0.4,
                            pointBackgroundColor: "#ffffff",
                            pointBorderColor: "#4f46e5",
                            pointBorderWidth: 2,
                            pointRadius: 4,
                            pointHoverRadius: 6,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: "#0f172a",
                            padding: 10,
                            cornerRadius: 8,
                        },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { font: { size: 11, family: "inherit" }, color: "#94a3b8" },
                        },
                        y: {
                            grid: { color: "#f1f5f9" },
                            ticks: { font: { size: 11, family: "inherit" }, color: "#94a3b8" },
                        },
                    },
                },
            });
        }

        // 2. 7-Day Attendance Bar Chart
        if (this.attendanceCanvasRef.el && window.Chart) {
            const ctx = this.attendanceCanvasRef.el.getContext("2d");
            new window.Chart(ctx, {
                type: "bar",
                data: {
                    labels: this.state.data.attendance_trend?.labels || [],
                    datasets: [
                        {
                            label: "Present Staff",
                            data: this.state.data.attendance_trend?.data || [],
                            backgroundColor: "#3b82f6",
                            borderRadius: 6,
                            borderSkipped: false,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { font: { size: 11, family: "inherit" }, color: "#94a3b8" },
                        },
                        y: {
                            grid: { color: "#f1f5f9" },
                            ticks: { font: { size: 11, family: "inherit" }, color: "#94a3b8" },
                        },
                    },
                },
            });
        }
    }

    // Quick Action Handlers
    async onOpenEmployees() {
        await this.action.doAction("hr.open_view_employee_list_my");
    }

    async onOpenEmployee(empId) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.employee",
            res_id: empId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async onApplyLeave() {
        try {
            await this.action.doAction("DSL_HRMS_leave.action_dsl_leave_request");
        } catch (e) {
            await this.onOpenEmployees();
        }
    }

    async onMyAttendance() {
        try {
            await this.action.doAction("DSL_HRMS_attendance.action_dsl_attendance_log");
        } catch (e) {
            await this.onOpenEmployees();
        }
    }

    async onOpenEssPortal() {
        try {
            await this.action.doAction("DSL_HRMS_ess.action_dsl_ess_portal");
        } catch (e) {
            await this.onOpenEmployees();
        }
    }

    async onOpenMssPortal() {
        try {
            await this.action.doAction("DSL_HRMS_mss.action_dsl_mss_portal");
        } catch (e) {
            await this.onOpenEssPortal();
        }
    }

    async onOpenAccDashboard() {
        try {
            await this.action.doAction("account.open_account_journal_dashboard_kanban");
        } catch (e) {
            await this.onOpenEssPortal();
        }
    }

    async onOpenAnnouncements() {
        await this.action.doAction("DSL_HRMS_ess.action_dsl_hr_announcement");
    }

    async onPostAnnouncement() {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Post Official HR Announcement",
            res_model: "dsl.hr.announcement",
            views: [[false, "form"]],
            target: "current",
        });
    }

    async onOpenAnnouncementRecord(announcementId) {
        if (!announcementId) return;
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Official HR Announcement & Circular",
            res_model: "dsl.hr.announcement",
            res_id: announcementId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async onOpenSettings() {
        await this.action.doAction("DSL_HRMS_core.action_dsl_hrms_config_settings");
    }
}

// Register as client action
registry.category("actions").add("dsl_hrms_dashboard_main", DslHrmsDashboard);
