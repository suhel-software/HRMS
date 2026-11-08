/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class DslOrgChartStudio extends Component {
    static template = "DSL_HRMS_organization.OrgChartStudio";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            loading: true,
            chartType: "dept",
            selectedCompanyId: "",
            companies: [],
            deptRoots: [],
            empRoots: [],
            stats: {},
        });

        onWillStart(async () => {
            await this.loadOrgData();
        });
    }

    async loadOrgData() {
        this.state.loading = true;
        try {
            const compId = this.state.selectedCompanyId ? parseInt(this.state.selectedCompanyId, 10) : false;
            const res = await this.orm.call("hr.department", "get_organization_chart_data", [compId]);
            this.state.companies = res.companies || [];
            this.state.deptRoots = res.dept_roots || [];
            this.state.empRoots = res.emp_roots || [];
            this.state.stats = res.stats || {};
        } catch (err) {
            console.error("Failed to load organization chart:", err);
        } finally {
            this.state.loading = false;
        }
    }

    setChartType(type) {
        this.state.chartType = type;
    }

    async onCompanyChange(ev) {
        this.state.selectedCompanyId = ev.target.value;
        await this.loadOrgData();
    }

    async openDepartment(deptId) {
        await this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "hr.department",
                res_id: deptId,
                views: [[false, "form"]],
                target: "current",
            },
            { onClose: () => this.loadOrgData() }
        );
    }

    async openEmployee(empId) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.employee",
            res_id: empId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async createNewDepartment() {
        await this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: "New Department / Section",
                res_model: "hr.department",
                views: [[false, "form"]],
                target: "new",
            },
            { onClose: () => this.loadOrgData() }
        );
    }

    async openAllDepartments() {
        await this.action.doAction("hr.hr_department_tree_action");
    }

    async openDesignations() {
        await this.action.doAction("DSL_HRMS_organization.action_dsl_designations");
    }

    async openGrades() {
        await this.action.doAction("DSL_HRMS_organization.action_dsl_hr_grade");
    }
}

registry.category("actions").add("dsl_hrms_org_chart_studio", DslOrgChartStudio);

