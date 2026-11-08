/** @odoo-module **/

import { registry } from "@web/core/registry";

async function dslGpsBrowserPunchAction(env, action) {
    const punchType = (action.params && action.params.punch_type) || "check_in";
    const orm = env.services.orm;
    const notification = env.services.notification;

    const getCoords = () =>
        new Promise((resolve) => {
            if (!navigator.geolocation) {
                resolve({ lat: 0.0, lng: 0.0, acc: 25.0, fallback: true });
                return;
            }
            navigator.geolocation.getCurrentPosition(
                (pos) =>
                    resolve({
                        lat: pos.coords.latitude,
                        lng: pos.coords.longitude,
                        acc: pos.coords.accuracy || 12.0,
                        fallback: false,
                    }),
                () => resolve({ lat: 0.0, lng: 0.0, acc: 25.0, fallback: true }),
                { enableHighAccuracy: true, timeout: 4500, maximumAge: 0 }
            );
        });

    const geo = await getCoords();
    const res = await orm.call(
        "dsl.gps.attendance.log",
        "rpc_submit_browser_gps_punch",
        [punchType, geo.lat, geo.lng, geo.acc, geo.fallback]
    );

    const pLabel = punchType === "check_in" ? "Check-In" : "Check-Out";
    const areaTxt = res.area ? ` from ${res.area}` : "";
    notification.add(
        res.within_geofence
            ? `${pLabel}${areaTxt} Auto-Verified (${res.distance_m}m from branch)!`
            : `${pLabel}${areaTxt} Recorded (${res.distance_m}m — Outside Geofence / Pending Approval).`,
        {
            title: `${res.name} · ${res.area || "GPS Captured"}`,
            type: res.within_geofence ? "success" : "warning",
        }
    );

    return env.services.action.doAction("DSL_HRMS_gps_attendance.action_dsl_gps_attendance", {
        clearBreadcrumbs: true,
    });
}

registry.category("actions").add("dsl_gps_browser_punch", dslGpsBrowserPunchAction);
