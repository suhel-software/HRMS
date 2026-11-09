/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class DslBankReconciliation extends Component {
    setup() {
        this.actionService = useService("action");
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            processing: false,
            mainMode: "bank_brs", // 'bank_brs' (Main Focus!) | 'party_settlement'
            
            // Common setup
            currencySymbol: "৳",
            bankJournals: [],
            allBankJournals: [],
            accounts: [],
            expenseAccounts: [],
            defaultChargeAccountId: null,

            // Quick Adjustment / Bank Charge Modal
            showQuickAdjModal: false,
            quickAdj: {
                type: "bank_charge",
                amount: "",
                date: "",
                accountId: "",
                chequeNo: "",
                bankDate: "",
                description: "",
            },

            // Confirm Bank Date Modal
            showConfirmDateModal: false,
            pendingDateChange: null,

            // Visibility controls
            showBankCards: true,
            showJournalSettings: false,

            // --- BRS (Bank Reconciliation Statement - Tally Style) ---
            selectedJournalId: null,
            brsFilterStatus: "uncleared", // 'uncleared' (Tally default) | 'all' | 'cleared'
            brsFlowFilter: "all", // 'all' | 'in' (deposits) | 'out' (withdrawals)
            datePreset: "all_time", // 'this_month' | 'last_month' | 'this_quarter' | 'this_year' | 'all_time' | 'custom'
            brsDateFrom: "",
            brsDateTo: "",
            brsSearch: "",
            brsItems: [],
            brsSummary: {
                book_balance: 0,
                uncleared_deposits: 0,
                uncleared_payments: 0,
                amounts_not_in_bank: 0,
                calculated_bank_balance: 0,
                uncleared_count: 0,
                total_shown_count: 0,
                period_total_count: 0,
                period_cleared_count: 0,
                period_uncleared_count: 0,
                period_cleared_debit: 0,
                period_cleared_credit: 0,
                period_uncleared_debit: 0,
                period_uncleared_credit: 0,
            },
            statementBalanceInput: "",
            selectedBrsIds: {},
            bulkBankDate: "",

            // --- Party Settlement State ---
            partnerSearch: "",
            partnerResults: [],
            showPartnerDropdown: false,
            selectedPartner: null,
            selectedAccountId: "",
            partySearchTerm: "",
            partyDebits: [],
            partyCredits: [],
            partySummary: {},
            selectedDebitIds: {},
            selectedCreditIds: {},
        });

        onWillStart(async () => {
            this.restorePersistentState();
            await this.loadInitialData();
            if (this.state.bankJournals.length > 0) {
                const journalExists = this.state.selectedJournalId && this.state.bankJournals.some(j => j.id === this.state.selectedJournalId);
                if (!journalExists) {
                    const firstBank = this.state.bankJournals.find(j => j.type === 'bank') || this.state.bankJournals[0];
                    this.state.selectedJournalId = firstBank.id;
                }
                await this.loadBrsData();
            } else {
                this.state.loading = false;
            }
        });
    }

    savePersistentState() {
        try {
            const dataToSave = {
                selectedJournalId: this.state.selectedJournalId,
                brsFilterStatus: this.state.brsFilterStatus,
                brsFlowFilter: this.state.brsFlowFilter,
                datePreset: this.state.datePreset,
                brsDateFrom: this.state.brsDateFrom,
                brsDateTo: this.state.brsDateTo,
                brsSearch: this.state.brsSearch,
                statementBalanceInput: this.state.statementBalanceInput,
                mainMode: this.state.mainMode,
            };
            sessionStorage.setItem("dsl_brs_bank_reconciliation_filter_state", JSON.stringify(dataToSave));
        } catch (e) {
            // ignore
        }
    }

    restorePersistentState() {
        try {
            const savedStr = sessionStorage.getItem("dsl_brs_bank_reconciliation_filter_state");
            if (savedStr) {
                const saved = JSON.parse(savedStr);
                if (saved.selectedJournalId) this.state.selectedJournalId = saved.selectedJournalId;
                if (saved.brsFilterStatus) this.state.brsFilterStatus = saved.brsFilterStatus;
                if (saved.brsFlowFilter) this.state.brsFlowFilter = saved.brsFlowFilter;
                if (saved.datePreset) this.state.datePreset = saved.datePreset;
                if (saved.brsDateFrom !== undefined) this.state.brsDateFrom = saved.brsDateFrom;
                if (saved.brsDateTo !== undefined) this.state.brsDateTo = saved.brsDateTo;
                if (saved.brsSearch !== undefined) this.state.brsSearch = saved.brsSearch;
                if (saved.statementBalanceInput !== undefined) this.state.statementBalanceInput = saved.statementBalanceInput;
                if (saved.mainMode) this.state.mainMode = saved.mainMode;
                return true;
            }
        } catch (e) {
            // ignore
        }
        return false;
    }

    get currentJournal() {
        if (!this.state.selectedJournalId) return null;
        return this.state.bankJournals.find(j => j.id === this.state.selectedJournalId) || null;
    }

    // -------------------------------------------------------------------------
    // INITIAL LOAD
    // -------------------------------------------------------------------------
    async loadInitialData() {
        try {
            const data = await this.orm.call("dsl.bank.reconciliation", "get_initial_data", []);
            this.state.currencySymbol = data.currency_symbol || "৳";
            this.state.bankJournals = data.bank_journals || [];
            this.state.allBankJournals = data.all_bank_journals || [];
            this.state.accounts = data.accounts || [];
            this.state.expenseAccounts = data.expense_accounts || [];
            this.state.defaultChargeAccountId = data.default_charge_account_id || null;

            // If selected journal was excluded, fallback to first available
            if (this.state.bankJournals.length > 0) {
                const exists = this.state.selectedJournalId && this.state.bankJournals.some(j => j.id === this.state.selectedJournalId);
                if (!exists) {
                    const firstBank = this.state.bankJournals.find(j => j.type === 'bank') || this.state.bankJournals[0];
                    this.state.selectedJournalId = firstBank.id;
                }
            } else {
                this.state.selectedJournalId = null;
            }
        } catch (err) {
            console.error("Error loading initial data", err);
        }
    }

    // -------------------------------------------------------------------------
    // QUICK BANK CHARGE / ADJUSTMENT MODAL
    // -------------------------------------------------------------------------
    openQuickAdjModal() {
        const todayIso = this.formatDateIso(new Date());
        this.state.quickAdj = {
            type: "bank_charge",
            amount: "",
            date: todayIso,
            accountId: this.state.defaultChargeAccountId || (this.state.expenseAccounts[0] ? this.state.expenseAccounts[0].id : ""),
            chequeNo: "",
            bankDate: todayIso,
            description: "",
            sourceMoveId: null,
            sourceMoveName: "",
            sourceGrossAmount: 0,
            sourceGrossAmountStr: "0.00",
            sourceIsReceipt: true,
        };
        this.state.showQuickAdjModal = true;
    }

    openQuickAdjModalForRow(row) {
        const todayIso = this.formatDateIso(new Date());
        let defaultType = "bank_charge";
        const jName = (this.currentJournal ? this.currentJournal.name : "").toLowerCase();
        if (jName.includes("bkash") || jName.includes("b-kash")) {
            defaultType = "bkash_charge";
        } else if (jName.includes("nagad")) {
            defaultType = "nagad_charge";
        } else if (jName.includes("card") || jName.includes("pos")) {
            defaultType = "pos_card_fee";
        }

        const typeLabels = {
            bkash_charge: "bKash charge",
            nagad_charge: "Nagad charge",
            mfs_charge: "MFS fee",
            pgw_fee: "Gateway fee",
            pos_card_fee: "POS card fee",
            bank_charge: "Bank charge",
        };
        const prefix = typeLabels[defaultType] || "Bank charge";
        const grossAmt = (row.debit > 0 ? row.debit : row.credit) || 0;

        this.state.quickAdj = {
            type: defaultType,
            amount: "",
            date: row.date || todayIso,
            accountId: this.state.defaultChargeAccountId || (this.state.expenseAccounts[0] ? this.state.expenseAccounts[0].id : ""),
            chequeNo: row.instrument_no || "",
            bankDate: row.bank_date || row.date || todayIso,
            description: `${prefix} for ${row.particulars || ''} (${row.move_name || ''})`.trim(),
            sourceMoveId: row.move_id,
            sourceMoveName: row.move_name || "",
            sourceParticulars: row.particulars || "",
            sourceLineId: row.id,
            sourceGrossAmount: grossAmt,
            sourceGrossAmountStr: grossAmt.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
            sourceIsReceipt: row.debit > 0,
            sourceIsCleared: row.is_cleared,
            reconcileSource: !row.is_cleared,
        };
        this.state.showQuickAdjModal = true;
    }

    get quickAdjNetCalc() {
        const adj = this.state.quickAdj;
        if (!adj || !adj.sourceGrossAmount) return null;
        const gross = parseFloat(adj.sourceGrossAmount) || 0;
        const fee = parseFloat(adj.amount) || 0;
        const isReceipt = adj.sourceIsReceipt;
        const net = isReceipt ? Math.max(0, gross - fee) : (gross + fee);
        return {
            gross: gross.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
            fee: fee.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
            net: net.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
            isReceipt: isReceipt,
            label: isReceipt ? "Net Bank Inflow" : "Total Bank Outflow",
        };
    }

    onQuickAdjTypeChange(ev) {
        const type = ev.target.value;
        const labels = {
            bkash_charge: "bKash charge",
            nagad_charge: "Nagad charge",
            mfs_charge: "MFS fee",
            pgw_fee: "Gateway fee",
            pos_card_fee: "POS card fee",
            bank_charge: "Bank charge",
            excise_duty: "Excise duty",
            cheque_bounce: "Cheque bounce fee",
            direct_debit: "Direct debit",
            mfs_commission: "MFS commission",
            bank_interest: "Bank interest",
            direct_credit: "Online deposit",
            rounding_loss: "Rounding diff",
            rounding_gain: "Rounding diff",
        };
        const prefix = labels[type] || "Bank charge";
        const adj = this.state.quickAdj;
        if (adj.sourceMoveName) {
            adj.description = `${prefix} for ${adj.sourceParticulars || adj.sourceMoveName} (${adj.sourceMoveName})`.trim();
        } else {
            adj.description = prefix;
        }
    }

    closeQuickAdjModal() {
        this.state.showQuickAdjModal = false;
    }

    async submitQuickAdjustment() {
        const adj = this.state.quickAdj;
        if (!adj.amount || parseFloat(adj.amount) <= 0) {
            this.notification.add("Please enter a valid amount greater than 0.", { type: "warning" });
            return;
        }
        if (!adj.accountId) {
            this.notification.add("Please select an Expense / Adjustment Account.", { type: "warning" });
            return;
        }
        if (!this.state.selectedJournalId) {
            this.notification.add("Please select an active Bank Journal first.", { type: "warning" });
            return;
        }

        this.state.processing = true;
        try {
            const res = await this.orm.call(
                "dsl.bank.reconciliation",
                "action_create_quick_adjustment",
                [],
                {
                    journal_id: parseInt(this.state.selectedJournalId),
                    date: adj.date,
                    adj_type: adj.type,
                    amount: parseFloat(adj.amount),
                    account_id: parseInt(adj.accountId),
                    description: adj.description,
                    cheque_no: adj.chequeNo,
                    bank_date: adj.bankDate || false,
                    source_move_id: adj.sourceMoveId || false,
                    source_line_id: adj.sourceLineId || false,
                    reconcile_source: Boolean(adj.reconcileSource),
                }
            );

            if (res.success) {
                this.notification.add(res.message, { type: "success" });
                this.closeQuickAdjModal();
                await this.loadInitialData();
                await this.loadBrsData();
            } else {
                this.notification.add(res.message || "Failed to create adjustment entry", { type: "danger" });
            }
        } catch (err) {
            console.error("Error creating quick adjustment", err);
            this.notification.add(err.message || "Error creating adjustment entry", { type: "danger" });
        } finally {
            this.state.processing = false;
        }
    }

    // -------------------------------------------------------------------------
    // BANK CARDS & JOURNAL VISIBILITY CONTROLS
    // -------------------------------------------------------------------------
    toggleBankCards() {
        this.state.showBankCards = !this.state.showBankCards;
    }

    toggleJournalSettings() {
        this.state.showJournalSettings = !this.state.showJournalSettings;
    }

    async toggleJournalBrs(journalId) {
        try {
            const res = await this.orm.call("dsl.bank.reconciliation", "action_toggle_journal_brs", [], { journal_id: journalId });
            if (res.success) {
                await this.loadInitialData();
                this.notification.add("Journal visibility updated.", { type: "info" });
                if (this.state.selectedJournalId) {
                    await this.loadBrsData();
                }
            }
        } catch (err) {
            console.error("Error toggling journal BRS visibility", err);
        }
    }

    // -------------------------------------------------------------------------
    // DATE PRESETS & PERIOD FILTERING
    // -------------------------------------------------------------------------
    formatDateIso(dateObj) {
        const year = dateObj.getFullYear();
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        const day = String(dateObj.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    setDatePreset(preset) {
        this.state.datePreset = preset;
        const now = new Date();
        const y = now.getFullYear();
        const m = now.getMonth();

        if (preset === 'today') {
            const todayStr = this.formatDateIso(now);
            this.state.brsDateFrom = todayStr;
            this.state.brsDateTo = todayStr;
        } else if (preset === 'this_month') {
            const firstDay = new Date(y, m, 1);
            const lastDay = new Date(y, m + 1, 0);
            this.state.brsDateFrom = this.formatDateIso(firstDay);
            this.state.brsDateTo = this.formatDateIso(lastDay);
        } else if (preset === 'last_month') {
            const firstDay = new Date(y, m - 1, 1);
            const lastDay = new Date(y, m, 0);
            this.state.brsDateFrom = this.formatDateIso(firstDay);
            this.state.brsDateTo = this.formatDateIso(lastDay);
        } else if (preset === 'this_quarter') {
            const q = Math.floor(m / 3);
            const firstDay = new Date(y, q * 3, 1);
            const lastDay = new Date(y, (q + 1) * 3, 0);
            this.state.brsDateFrom = this.formatDateIso(firstDay);
            this.state.brsDateTo = this.formatDateIso(lastDay);
        } else if (preset === 'this_year') {
            const firstDay = new Date(y, 0, 1);
            const lastDay = new Date(y, 11, 31);
            this.state.brsDateFrom = this.formatDateIso(firstDay);
            this.state.brsDateTo = this.formatDateIso(lastDay);
        } else if (preset === 'all_time') {
            this.state.brsDateFrom = '';
            this.state.brsDateTo = '';
        }
        this.savePersistentState();
        this.loadBrsData();
    }

    onDateFromInput(ev) {
        this.state.brsDateFrom = ev.target.value;
        this.state.datePreset = 'custom';
    }

    onDateToInput(ev) {
        this.state.brsDateTo = ev.target.value;
        this.state.datePreset = 'custom';
    }

    applyCustomDate() {
        this.savePersistentState();
        this.loadBrsData();
    }

    clearDates() {
        this.state.brsDateFrom = '';
        this.state.brsDateTo = '';
        this.state.datePreset = 'all_time';
        this.savePersistentState();
        this.loadBrsData();
    }

    async setRowTodayDate(lineId) {
        const todayIso = this.formatDateIso(new Date());
        await this.onBankDateChange(lineId, { target: { value: todayIso } });
    }

    openDatePicker(ev) {
        try {
            if (ev.target && typeof ev.target.showPicker === 'function') {
                ev.target.showPicker();
            }
        } catch (err) {
            // ignore
        }
    }

    // -------------------------------------------------------------------------
    // TALLY BANK RECONCILIATION (BRS) ACTIONS
    // -------------------------------------------------------------------------
    async selectBankJournal(journalId) {
        this.state.selectedJournalId = journalId;
        this.state.selectedBrsIds = {};
        this.savePersistentState();
        await this.loadBrsData();
    }

    async setBrsFilterStatus(status) {
        this.state.brsFilterStatus = status;
        this.state.selectedBrsIds = {};
        this.savePersistentState();
        await this.loadBrsData();
    }

    async loadBrsData() {
        if (!this.state.selectedJournalId) return;
        this.state.loading = true;
        try {
            const res = await this.orm.call(
                "dsl.bank.reconciliation",
                "get_bank_brs_data",
                [],
                {
                    journal_id: parseInt(this.state.selectedJournalId),
                    filter_status: this.state.brsFilterStatus,
                    date_from: this.state.brsDateFrom || false,
                    date_to: this.state.brsDateTo || false,
                    search_term: this.state.brsSearch,
                }
            );

            if (res.error) {
                this.notification.add(res.error, { type: "danger" });
                return;
            }

            this.state.brsItems = res.items || [];
            this.state.brsSummary = res.summary || {};
            if (res.currency_symbol) {
                this.state.currencySymbol = res.currency_symbol;
            }
            this.savePersistentState();
        } catch (err) {
            console.error("Error loading BRS data", err);
            this.notification.add("Could not load Bank BRS data: " + (err.message || err), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    onStatementBalanceInput(ev) {
        this.state.statementBalanceInput = ev.target.value;
    }

    onBrsSearchInput(ev) {
        this.state.brsSearch = ev.target.value;
    }

    onBrsSearchKeyup(ev) {
        if (ev.key === "Enter") {
            this.loadBrsData();
        }
    }

    // -------------------------------------------------------------------------
    // CONFIRM BANK CLEARING DATE POPUP
    // -------------------------------------------------------------------------
    openConfirmDateModal(line, newDate) {
        this.state.pendingDateChange = {
            lineId: line.id,
            particulars: line.particulars + (line.move_name ? ` (${line.move_name})` : ''),
            instrument_no: line.instrument_no,
            amount: line.debit > 0 ? line.debit : line.credit,
            isDebit: line.debit > 0,
            oldDate: line.bank_date,
            newDate: newDate,
        };
        this.state.showConfirmDateModal = true;
    }

    cancelConfirmDate() {
        if (this.state.pendingDateChange) {
            const line = this.state.brsItems.find(i => i.id === this.state.pendingDateChange.lineId);
            if (line) {
                line.bank_date = this.state.pendingDateChange.oldDate;
            }
        }
        this.state.showConfirmDateModal = false;
        this.state.pendingDateChange = null;
    }

    async executeConfirmedDateChange() {
        if (!this.state.pendingDateChange) return;
        const { lineId, newDate } = this.state.pendingDateChange;
        const line = this.state.brsItems.find(i => i.id === lineId);
        if (line) {
            line.bank_date = newDate;
            line.is_cleared = Boolean(newDate);
        }

        this.state.processing = true;
        try {
            const res = await this.orm.call(
                "dsl.bank.reconciliation",
                "action_update_single_bank_date",
                [],
                {
                    line_id: lineId,
                    bank_date: newDate,
                }
            );
            if (res.success) {
                this.notification.add(res.message, { type: "success" });
                this.state.showConfirmDateModal = false;
                this.state.pendingDateChange = null;
                await this.loadBrsData();
            } else {
                this.notification.add(res.message || "Failed to update Bank Date", { type: "danger" });
            }
        } catch (err) {
            console.error("Error updating Bank Date", err);
            this.notification.add(err.message || "Error updating Bank Date", { type: "danger" });
        } finally {
            this.state.processing = false;
        }
    }

    clearBankDate(lineId) {
        const line = this.state.brsItems.find(i => i.id === lineId);
        if (line) {
            this.openConfirmDateModal(line, "");
        }
    }

    onBulkBankDateInput(ev) {
        this.state.bulkBankDate = ev.target.value;
    }

    // Trigger confirmation popup when a user selects a date
    onBankDateChange(lineId, ev) {
        const newDate = ev.target.value;
        const line = this.state.brsItems.find(i => i.id === lineId);
        if (line) {
            this.openConfirmDateModal(line, newDate);
        }
    }

    // Bulk selection for BRS
    toggleBrsSelect(id) {
        if (this.state.selectedBrsIds[id]) {
            delete this.state.selectedBrsIds[id];
        } else {
            this.state.selectedBrsIds[id] = true;
        }
    }

    toggleAllBrsSelect(ev) {
        const checked = ev.target.checked;
        if (checked) {
            this.displayedBrsItems.forEach(i => {
                this.state.selectedBrsIds[i.id] = true;
            });
        } else {
            this.state.selectedBrsIds = {};
        }
    }

    get displayedBrsItems() {
        const items = this.state.brsItems || [];
        if (this.state.brsFlowFilter === "in") {
            return items.filter(i => (i.debit || 0) > 0);
        }
        if (this.state.brsFlowFilter === "out") {
            return items.filter(i => (i.credit || 0) > 0);
        }
        return items;
    }

    get countMoneyIn() {
        return (this.state.brsItems || []).filter(i => (i.debit || 0) > 0).length;
    }

    get countMoneyOut() {
        return (this.state.brsItems || []).filter(i => (i.credit || 0) > 0).length;
    }

    setBrsFlowFilter(flow) {
        this.state.brsFlowFilter = flow;
        this.state.selectedBrsIds = {};
        this.savePersistentState();
    }

    get selectedBrsCount() {
        return Object.keys(this.state.selectedBrsIds).length;
    }

    async applyBulkBankDate() {
        if (!this.state.bulkBankDate) {
            this.notification.add("Please enter a Bank Date to apply.", { type: "warning" });
            return;
        }
        const ids = Object.keys(this.state.selectedBrsIds).map(id => parseInt(id));
        if (ids.length === 0) {
            this.notification.add("Please select at least one transaction.", { type: "warning" });
            return;
        }

        this.state.processing = true;
        try {
            const res = await this.orm.call(
                "dsl.bank.reconciliation",
                "action_bulk_set_bank_date",
                [],
                { line_ids: ids, bank_date: this.state.bulkBankDate }
            );
            if (res.success) {
                this.notification.add(res.message, { type: "success" });
                this.state.selectedBrsIds = {};
                this.state.bulkBankDate = "";
                await this.loadBrsData();
            } else {
                this.notification.add(res.message, { type: "danger" });
            }
        } catch (err) {
            this.notification.add(err.message, { type: "danger" });
        } finally {
            this.state.processing = false;
        }
    }

    async clearBulkBrsDate() {
        const ids = Object.keys(this.state.selectedBrsIds).map(id => parseInt(id));
        if (ids.length === 0) return;

        this.state.processing = true;
        try {
            const res = await this.orm.call(
                "dsl.bank.reconciliation",
                "action_bulk_clear_bank_date",
                [],
                { line_ids: ids }
            );
            if (res.success) {
                this.notification.add(res.message, { type: "success" });
                this.state.selectedBrsIds = {};
                await this.loadBrsData();
            } else {
                this.notification.add(res.message, { type: "danger" });
            }
        } catch (err) {
            this.notification.add(err.message, { type: "danger" });
        } finally {
            this.state.processing = false;
        }
    }

    // BRS Mathematical Difference (Tally BRS verification)
    get brsDifference() {
        if (!this.state.statementBalanceInput || this.state.statementBalanceInput.trim() === "") {
            return null; // Not entered yet
        }
        const stmtBal = parseFloat(this.state.statementBalanceInput) || 0;
        const calcBal = this.state.brsSummary.calculated_bank_balance || 0;
        return Math.round(Math.abs(calcBal - stmtBal) * 100) / 100;
    }

    get isBrsBalanced() {
        return this.brsDifference !== null && this.brsDifference === 0;
    }

    // Switch between Bank BRS & Party Settlement
    switchMainMode(mode) {
        this.state.mainMode = mode;
        if (mode === "party_settlement" && this.state.partyDebits.length === 0) {
            this.loadPartyLines();
        } else if (mode === "bank_brs") {
            this.loadBrsData();
        }
    }

    // -------------------------------------------------------------------------
    // PARTY SETTLEMENT METHODS (AGST REF)
    // -------------------------------------------------------------------------
    async loadPartyLines() {
        this.state.loading = true;
        try {
            const res = await this.orm.call(
                "dsl.bank.reconciliation",
                "get_unreconciled_lines",
                [],
                {
                    partner_id: this.state.selectedPartner ? this.state.selectedPartner.id : false,
                    account_id: this.state.selectedAccountId ? parseInt(this.state.selectedAccountId) : false,
                    search_term: this.state.partySearchTerm,
                }
            );
            this.state.partyDebits = res.debits || [];
            this.state.partyCredits = res.credits || [];
            this.state.partySummary = res.summary || {};
        } catch (err) {
            console.error("Party line error", err);
        } finally {
            this.state.loading = false;
        }
    }

    async searchPartners(query) {
        this.state.partnerSearch = query;
        if (!query || query.trim().length < 1) {
            this.state.partnerResults = [];
            this.state.showPartnerDropdown = false;
            return;
        }
        try {
            const results = await this.orm.call(
                "dsl.bank.reconciliation",
                "search_partners",
                [],
                { query: query.trim(), limit: 20 }
            );
            this.state.partnerResults = results || [];
            this.state.showPartnerDropdown = true;
        } catch (err) {
            console.error(err);
        }
    }

    selectPartner(p) {
        this.state.selectedPartner = p;
        this.state.partnerSearch = p.name;
        this.state.showPartnerDropdown = false;
        this.loadPartyLines();
    }

    clearPartner() {
        this.state.selectedPartner = null;
        this.state.partnerSearch = "";
        this.state.partnerResults = [];
        this.state.showPartnerDropdown = false;
        this.loadPartyLines();
    }

    onPartnerFocus() {
        if (this.state.partnerResults && this.state.partnerResults.length) {
            this.state.showPartnerDropdown = true;
        }
    }

    // Open original Odoo entry
    openMove(moveId) {
        if (!moveId) return;
        this.savePersistentState();
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "account.move",
            res_id: moveId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    formatMoney(val) {
        const num = parseFloat(val) || 0;
        return this.state.currencySymbol + " " + num.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }
}

DslBankReconciliation.template = "DSL_HRMS_bank_reconciliation.Console";
registry.category("actions").add("DSL_HRMS_bank_reconciliation.Console", DslBankReconciliation);
