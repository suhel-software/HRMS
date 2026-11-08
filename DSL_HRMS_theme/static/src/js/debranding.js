/** @odoo-module **/

import { registry } from "@web/core/registry";

// 1. Remove Odoo support & documentation from user menu
const userMenuRegistry = registry.category("user_menuitems");
if (userMenuRegistry.contains("documentation")) {
    userMenuRegistry.remove("documentation");
}
if (userMenuRegistry.contains("support")) {
    userMenuRegistry.remove("support");
}
if (userMenuRegistry.contains("odoo_account")) {
    userMenuRegistry.remove("odoo_account");
}

// 2. Set document title initially
if (typeof document !== "undefined") {
    document.title = "DSL Enterprise HRMS";
}
