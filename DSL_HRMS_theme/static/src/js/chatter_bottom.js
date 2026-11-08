/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";

/**
 * Globally enforce Bottom Chatter across ALL Form Views in DSL HRMS.
 * Disables right-hand side chatter (`SIDE_CHATTER` / `o-aside`) on all screen widths
 * so every form view spans full width and renders Activity Log / Chatter at the bottom.
 */
patch(FormRenderer.prototype, {
    mailLayout(hasAttachmentContainer) {
        if (!this.mailStore) {
            return "NONE";
        }
        return "BOTTOM_CHATTER";
    },
});

