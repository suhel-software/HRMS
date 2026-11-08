/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";

const STORAGE_KEY = "dsl_hrms_dark_mode";

function applyBodyTheme(isDark) {
    if (typeof document !== "undefined" && document.body) {
        document.body.classList.toggle("dsl_dark_mode", Boolean(isDark));
    }
}

// Apply persisted theme preference immediately on boot
const initialDark = browser.localStorage.getItem(STORAGE_KEY) === "1";
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => applyBodyTheme(initialDark));
} else {
    applyBodyTheme(initialDark);
}

export class DslThemeModeSystray extends Component {
    static template = "DSL_HRMS_theme.ThemeModeSystray";
    static props = {};

    setup() {
        this.state = useState({
            isDark: browser.localStorage.getItem(STORAGE_KEY) === "1",
        });
        applyBodyTheme(this.state.isDark);
    }

    toggleTheme() {
        this.state.isDark = !this.state.isDark;
        browser.localStorage.setItem(STORAGE_KEY, this.state.isDark ? "1" : "0");
        applyBodyTheme(this.state.isDark);
    }
}

registry.category("systray").add(
    "DSL_HRMS_theme.ThemeModeSystray",
    { Component: DslThemeModeSystray },
    { sequence: 25 }
);

