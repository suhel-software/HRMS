/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { cookie } from "@web/core/browser/cookie";
import { router } from "@web/core/browser/router";
import { rpcBus } from "@web/core/network/rpc";
import { UPDATE_METHODS } from "@web/core/orm_service";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { companyService } from "@web/webclient/company_service";

// Ensure Mother / Holding Company employees & users automatically activate ALL allowed
// Group Companies & Separate Branch COAs on login/load (instead of Odoo's single-company default),
// while still allowing manual filtering from the top-right Company Switcher anytime.
patch(companyService, {
    start(env, deps) {
        try {
            if (session.is_dsl_mother_user && session.user_companies?.allowed_companies) {
                const allowedMap = session.user_companies.allowed_companies;
                const defaultCid = Number(session.user_companies.current_company);
                const sortedIds = Object.values(allowedMap)
                    .sort((a, b) => (a.sequence - b.sequence) || (a.id - b.id))
                    .map((c) => Number(c.id));
                const allAllowedIds = [
                    defaultCid,
                    ...sortedIds.filter((id) => id !== defaultCid),
                ].filter((id) => id in allowedMap);

                if (allAllowedIds.length > 1) {
                    const uid = user.userId || "anon";
                    const storageKey = `dsl_mother_cids_v1_${session.db || "db"}_${uid}`;
                    const rawCookie = cookie.get("cids");
                    const cookieIds = rawCookie
                        ? String(rawCookie).split("-").map(Number).filter((n) => n in allowedMap)
                        : [];
                    const hasDisallowedInCookie = rawCookie
                        ? String(rawCookie).split("-").map(Number).some((n) => !(n in allowedMap))
                        : false;

                    let prevKnown = null;
                    try {
                        const saved = browser.localStorage.getItem(storageKey);
                        prevKnown = saved ? JSON.parse(saved) : null;
                    } catch {
                        prevKnown = null;
                    }

                    if (!rawCookie || !cookieIds.length || hasDisallowedInCookie || !Array.isArray(prevKnown)) {
                        cookie.set("cids", allAllowedIds.join("-"));
                        if ("cids" in router.current) {
                            delete router.current.cids;
                        }
                    } else {
                        const newlyAdded = allAllowedIds.filter((id) => !prevKnown.includes(id));
                        if (newlyAdded.length) {
                            const merged = [...cookieIds];
                            for (const nid of newlyAdded) {
                                if (!merged.includes(nid)) {
                                    merged.push(nid);
                                }
                            }
                            cookie.set("cids", merged.join("-"));
                            if ("cids" in router.current) {
                                delete router.current.cids;
                            }
                        }
                    }
                    try {
                        browser.localStorage.setItem(storageKey, JSON.stringify(allAllowedIds));
                    } catch {
                        // ignore localStorage quota errors
                    }
                }
            }
        } catch (err) {
            console.warn("DSL Mother Company auto-cids sync skipped:", err);
        }

        const service = super.start(env, deps);

        // If the logged-in user edits their OWN `res.users` company/branch access, immediately
        // sync `cids` cookie & reload session context so no stale company ID triggers AccessError.
        rpcBus.addEventListener("RPC:RESPONSE", (ev) => {
            const { data, error, result } = ev.detail || {};
            if (error || !data?.params) {
                return;
            }
            const { model, method, args, kwargs } = data.params;
            if (model === "res.users" && UPDATE_METHODS.includes(method)) {
                const recordIds = Array.isArray(args?.[0])
                    ? args[0]
                    : typeof args?.[0] === "number"
                    ? [args[0]]
                    : [];
                if (user.userId && recordIds.includes(user.userId)) {
                    const vals = args?.[1] || kwargs?.vals || {};
                    const accessFields = [
                        "company_id",
                        "company_ids",
                        "auto_group_company_access",
                        "excluded_company_ids",
                        "dsl_excluded_branch_ids",
                        "dsl_branch_id",
                        "dsl_branch_ids",
                        "dsl_branch_access_mode",
                    ];
                    if (accessFields.some((f) => f in vals)) {
                        const savedRow = Array.isArray(result) ? result[0] : null;
                        if (savedRow && Array.isArray(savedRow.company_ids)) {
                            const allowedSet = new Set(
                                savedRow.company_ids.map((c) =>
                                    typeof c === "object" ? c.id : Number(c)
                                )
                            );
                            const rawCookie = cookie.get("cids");
                            const validCids = rawCookie
                                ? String(rawCookie)
                                      .split("-")
                                      .map(Number)
                                      .filter((id) => allowedSet.has(id))
                                : [];
                            const fallbackCid =
                                typeof savedRow.company_id === "object"
                                    ? savedRow.company_id?.id
                                    : Number(savedRow.company_id) || [...allowedSet][0];
                            const nextCids = validCids.length
                                ? validCids
                                : fallbackCid
                                ? [fallbackCid]
                                : [];
                            if (nextCids.length) {
                                cookie.set("cids", nextCids.join("-"));
                                user.updateContext({ allowed_company_ids: nextCids });
                            }
                        }
                        if (!browser.localStorage.getItem("running_tour")) {
                            deps.action.doAction("reload_context");
                        }
                    }
                }
            }
        });

        return service;
    },
});

export class DslCompanyHierarchyStudio extends Component {
    static template = "DSL_HRMS_multi_company.CompanyHierarchyStudio";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            loading: true,
            viewMode: "tree",
            searchQuery: "",
            roots: [],
            flatList: [],
            summary: {},
            hasBranchModule: false,
            canManageCompanies: false,
        });

        onWillStart(async () => {
            await this.loadHierarchy();
        });
    }

    async loadHierarchy() {
        this.state.loading = true;
        try {
            const res = await this.orm.call("res.company", "get_company_hierarchy_data", []);
            this.state.roots = res.roots || [];
            this.state.flatList = res.flat_list || [];
            this.state.summary = res.summary || {};
            this.state.hasBranchModule = Boolean(res.has_branch_module);
            this.state.canManageCompanies = Boolean(res.can_manage_companies);
        } catch (err) {
            console.error("Failed to load company hierarchy:", err);
        } finally {
            this.state.loading = false;
        }
    }

    get filteredCompanies() {
        const q = (this.state.searchQuery || "").trim().toLowerCase();
        if (!q) {
            return this.state.flatList;
        }
        return this.state.flatList.filter(
            (c) =>
                c.name.toLowerCase().includes(q) ||
                (c.short_code && c.short_code.toLowerCase().includes(q)) ||
                (c.tin_number && c.tin_number.toLowerCase().includes(q)) ||
                (c.country_name && c.country_name.toLowerCase().includes(q))
        );
    }

    setViewMode(mode) {
        this.state.viewMode = mode;
    }

    async openCompanyForm(companyId) {
        await this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: "Company Configuration & COA",
                res_model: "res.company",
                res_id: companyId,
                views: [[false, "form"]],
                target: "current",
            },
            {
                onClose: () => this.loadHierarchy(),
            }
        );
    }

    async openUsersAccess() {
        await this.action.doAction("DSL_HRMS_multi_company.action_dsl_company_users_access", {
            onClose: () => this.loadHierarchy(),
        });
    }

    async openBranchForm(branchId) {
        await this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: "Branch Configuration & COA",
                res_model: "dsl.branch",
                res_id: branchId,
                views: [[false, "form"]],
                target: "current",
            },
            {
                onClose: () => this.loadHierarchy(),
            }
        );
    }

    async createCompanyBranch(companyId) {
        await this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: "New Branch / Plant (Shared or Separate COA)",
                res_model: "dsl.branch",
                views: [[false, "form"]],
                target: "new",
                context: {
                    default_company_id: companyId,
                },
            },
            {
                onClose: () => this.loadHierarchy(),
            }
        );
    }

    async createNewCompany() {
        await this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: "New Company (Separate COA)",
                res_model: "res.company",
                views: [[false, "form"]],
                target: "new",
                context: {
                    default_company_type: "holding",
                },
            },
            {
                onClose: () => this.loadHierarchy(),
            }
        );
    }

    async createChildCompany(parentId) {
        await this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: "New Sub-Company / Sister Concern / Joint Venture",
                res_model: "res.company",
                views: [[false, "form"]],
                target: "new",
                context: {
                    default_group_parent_id: parentId,
                    default_company_type: "subsidiary",
                },
            },
            {
                onClose: () => this.loadHierarchy(),
            }
        );
    }
}

registry.category("actions").add("dsl_hrms_company_hierarchy_studio", DslCompanyHierarchyStudio);
