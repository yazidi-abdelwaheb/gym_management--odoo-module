/** @odoo-module */

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const MODEL = "gym.member";
const ACTIVE_TEST_CONTEXT = { context: { active_test: false } };

function toDateString(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function getMonthRanges() {
    const now = new Date();
    const months = [];
    for (let offset = 5; offset >= 0; offset--) {
        const start = new Date(now.getFullYear(), now.getMonth() - offset, 1);
        const end = new Date(start.getFullYear(), start.getMonth() + 1, 1);
        months.push({
            start: toDateString(start),
            end: toDateString(end),
            label: start.toLocaleDateString(undefined, { month: "short" }),
        });
    }
    return months;
}

export class GymDashboard extends Component {
    static template = "gym_management.GymDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            error: null,
            metrics: { total: 0, active: 0, inactive: 0, newThisMonth: 0 },
            gender: { male: 0, female: 0, other: 0 },
            months: [],
            recentMembers: [],
        });
        this.monthRanges = getMonthRanges();
        onWillStart(() => this.loadDashboard());
    }

    async loadDashboard() {
        this.state.loading = true;
        this.state.error = null;
        const currentMonth = this.monthRanges[this.monthRanges.length - 1];
        const monthDomains = this.monthRanges.map((month) => [
            ["registration_date", ">=", month.start],
            ["registration_date", "<", month.end],
        ]);

        try {
            const [
                total,
                active,
                inactive,
                newThisMonth,
                male,
                female,
                ...results
            ] = await Promise.all([
                this.orm.searchCount(MODEL, [], ACTIVE_TEST_CONTEXT),
                this.orm.searchCount(MODEL, [["active", "=", true]], ACTIVE_TEST_CONTEXT),
                this.orm.searchCount(MODEL, [["active", "=", false]], ACTIVE_TEST_CONTEXT),
                this.orm.searchCount(MODEL, [
                    ["registration_date", ">=", currentMonth.start],
                    ["registration_date", "<", currentMonth.end],
                ], ACTIVE_TEST_CONTEXT),
                this.orm.searchCount(MODEL, [["gender", "=", "male"]], ACTIVE_TEST_CONTEXT),
                this.orm.searchCount(MODEL, [["gender", "=", "female"]], ACTIVE_TEST_CONTEXT),
                ...monthDomains.map((domain) =>
                    this.orm.searchCount(MODEL, domain, ACTIVE_TEST_CONTEXT)
                ),
                this.orm.searchRead(
                    MODEL,
                    [],
                    ["name", "email", "registration_date", "gender", "active"],
                    { ...ACTIVE_TEST_CONTEXT, limit: 5, order: "registration_date desc, id desc" }
                ),
            ]);

            const monthlyCounts = results.slice(0, this.monthRanges.length);
            const recentMembers = results[this.monthRanges.length];
            this.state.metrics = {
                total,
                active,
                inactive,
                newThisMonth,
            };
            this.state.gender = {
                male,
                female,
                other: Math.max(total - male - female, 0),
            };
            this.state.months = this.monthRanges.map((month, index) => ({
                ...month,
                count: monthlyCounts[index],
                height: `${Math.max((monthlyCounts[index] / Math.max(...monthlyCounts, 1)) * 100, 4)}%`,
            }));
            this.state.recentMembers = recentMembers;
        } catch (error) {
            this.state.error = error.message || String(error);
        } finally {
            this.state.loading = false;
        }
    }

    get activePercentage() {
        const { total, active } = this.state.metrics;
        return total ? Math.round((active / total) * 100) : 0;
    }

    get genderTotal() {
        return Object.values(this.state.gender).reduce((sum, count) => sum + count, 0);
    }

    genderPercentage(count) {
        return this.genderTotal ? Math.round((count / this.genderTotal) * 100) : 0;
    }

    formatDate(value) {
        if (!value) {
            return "—";
        }
        return new Date(`${value}T00:00:00`).toLocaleDateString();
    }

    openMembers(domain = []) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: "Gym Members",
            res_model: MODEL,
            views: [[false, "list"], [false, "form"]],
            domain,
            context: { active_test: false },
        });
    }

    openActiveMembers() {
        return this.openMembers([["active", "=", true]]);
    }

    openInactiveMembers() {
        return this.openMembers([["active", "=", false]]);
    }

    openNewThisMonth() {
        const currentMonth = this.monthRanges[this.monthRanges.length - 1];
        return this.openMembers([
            ["registration_date", ">=", currentMonth.start],
            ["registration_date", "<", currentMonth.end],
        ]);
    }

    openMonth(month) {
        return this.openMembers([
            ["registration_date", ">=", month.start],
            ["registration_date", "<", month.end],
        ]);
    }

    openMember(member) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: MODEL,
            res_id: member.id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("gym_management.dashboard", GymDashboard);
