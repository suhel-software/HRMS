/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class DslFixedAssetDashboard extends Component {
    static template = "DSL_HRMS_fixed_asset.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loading: true, data: null, breakdown: "by_group" });
        onWillStart(async () => {
            await this.load();
        });
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("account.asset", "get_fixed_asset_dashboard", []);
        this.state.loading = false;
    }

    // ---------- formatting ----------
    fmt(value) {
        const v = Number(value || 0);
        const abs = Math.abs(v);
        let txt;
        if (abs >= 10000000) {
            txt = (v / 10000000).toFixed(2) + " Cr";
        } else if (abs >= 100000) {
            txt = (v / 100000).toFixed(2) + " Lac";
        } else {
            txt = v.toLocaleString(undefined, { maximumFractionDigits: 0 });
        }
        const cur = this.state.data?.currency || {};
        return cur.position === "before" ? `${cur.symbol || ""} ${txt}` : `${txt} ${cur.symbol || ""}`;
    }

    fmtFull(value) {
        const v = Number(value || 0);
        const cur = this.state.data?.currency || {};
        const txt = v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return cur.position === "before" ? `${cur.symbol || ""} ${txt}` : `${txt} ${cur.symbol || ""}`;
    }

    get statusTotal() {
        return (this.state.data?.status || []).reduce((s, x) => s + x.count, 0) || 0;
    }

    get donutStyle() {
        const items = this.state.data?.status || [];
        const total = this.statusTotal;
        if (!total) {
            return "background: conic-gradient(#e2e8f0 0 100%);";
        }
        let acc = 0;
        const parts = items.map((s) => {
            const start = (acc / total) * 100;
            acc += s.count;
            const end = (acc / total) * 100;
            return `${s.color} ${start}% ${end}%`;
        });
        return `background: conic-gradient(${parts.join(", ")});`;
    }

    get breakdownRows() {
        return this.state.data?.[this.state.breakdown] || [];
    }

    setBreakdown(key) {
        this.state.breakdown = key;
    }

    // ---------- navigation ----------
    openAssets(domain = [], name = "Assets", context = {}) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: "account.asset",
            views: [
                [false, "list"],
                [false, "kanban"],
                [false, "form"],
            ],
            domain: [["state", "!=", "model"], ["parent_id", "=", false], ...domain],
            context,
        });
    }

    openAsset(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "account.asset",
            res_id: id,
            views: [[false, "form"]],
        });
    }

    openMaintenance(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "dsl.asset.maintenance",
            res_id: id,
            views: [[false, "form"]],
        });
    }

    openXml(xmlid) {
        this.action.doAction(xmlid);
    }

    openState(key) {
        this.openAssets([["state", "=", key]], "Assets");
    }

    newAsset() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "account.asset",
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("dsl_fixed_asset_dashboard", DslFixedAssetDashboard);

