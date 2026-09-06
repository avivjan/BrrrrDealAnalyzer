// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import LiquiditySidebar from "./LiquiditySidebar.vue";
import { addDays, todayISO } from "../../utils/liquidityEngine";
import type {
  LiquidityRecurringTransaction,
  LiquiditySeries,
  LiquiditySettings,
  LiquidityTransaction,
  MercuryBalanceResponse,
} from "../../types/liquidity";

const TODAY = todayISO();

/** The sidebar's own short-date vocabulary. */
const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const SETTINGS: LiquiditySettings = {
  opening_balance_k: 49,
  opening_balance_date: TODAY,
  reserve_k: 5,
};

function series(over: Partial<LiquiditySeries> = {}): LiquiditySeries {
  return {
    days: [
      { date: TODAY, transactions: [], net_k: 0, balance_k: 42.5 },
      { date: addDays(TODAY, 10), transactions: [], net_k: 0, balance_k: 8.25 },
    ],
    globalMin: 8.25,
    globalMinDates: [addDays(TODAY, 10)],
    firstNegativeDate: null,
    ...over,
  };
}

const rule = (
  over: Partial<LiquidityRecurringTransaction> = {},
): LiquidityRecurringTransaction => ({
  id: "rule-1",
  description: "HM interest",
  amount_k: -2.4,
  start_date: TODAY,
  end_date: null,
  occurrences: null,
  frequency: "monthly",
  interval: 1,
  ...over,
});

function mountSidebar(props: Record<string, unknown> = {}) {
  return mount(LiquiditySidebar, {
    props: {
      series: series(),
      settings: SETTINGS,
      transactions: [] as LiquidityTransaction[],
      ...props,
    },
  });
}

const mercury = (
  over: Partial<MercuryBalanceResponse> = {},
): MercuryBalanceResponse => ({
  total_balance_k: 42.5,
  total_available_k: 42.5,
  account_count: 2,
  workspace_count: 1,
  workspaces: [
    {
      workspace: "brrrr",
      total_balance_k: 42.5,
      total_available_k: 42.5,
      account_count: 2,
      accounts: [
        {
          id: "acc-1",
          name: "Operating",
          type: "checking",
          status: "active",
          current_balance_k: 30,
          available_balance_k: 30,
          workspace: "brrrr",
        },
      ],
    },
  ],
  workspace_errors: [],
  accounts: [],
  ...over,
});

describe("LiquiditySidebar", () => {
  describe("the summary tiles", () => {
    it("shows today's balance from the series", () => {
      expect(mountSidebar().text()).toContain("42.5k");
    });

    it("shows an em dash when the series has no bucket for today", () => {
      const wrapper = mountSidebar({
        series: series({ days: [], globalMinDates: [] }),
      });
      expect(wrapper.text()).toContain("—");
    });

    it("shows the window minimum, rounded to one decimal, and its date", () => {
      const minDate = addDays(TODAY, 10);
      const [, month, day] = minDate.split("-") as [string, string, string];
      const label = MONTHS[Number(month) - 1] + " " + Number(day);

      const text = mountSidebar().text();
      expect(text).toContain("Window Min");
      expect(text).toContain("8.3k"); // 8.25 -> toFixed(1)
      expect(text).toContain("on " + label);
    });

    it("shows the reserve threshold", () => {
      expect(mountSidebar().text()).toContain("Reserve Threshold");
      expect(mountSidebar().text()).toContain("5.0k");
    });

    it("picks the soonest future outflow and inflow", () => {
      const wrapper = mountSidebar({
        transactions: [
          {
            id: "a",
            effective_date: addDays(TODAY, 20),
            description: "Later draw",
            amount_k: -5,
          },
          {
            id: "b",
            effective_date: addDays(TODAY, 3),
            description: "Sooner draw",
            amount_k: -9,
          },
          {
            id: "c",
            effective_date: addDays(TODAY, 5),
            description: "Rent",
            amount_k: 2,
          },
        ] as LiquidityTransaction[],
      });

      expect(wrapper.text()).toContain("Sooner draw");
      expect(wrapper.text()).not.toContain("Later draw");
      expect(wrapper.text()).toContain("Rent");
    });

    it("ignores past transactions when picking the next flow", () => {
      const wrapper = mountSidebar({
        transactions: [
          {
            id: "past",
            effective_date: addDays(TODAY, -5),
            description: "Old draw",
            amount_k: -5,
          },
        ] as LiquidityTransaction[],
      });

      expect(wrapper.text()).not.toContain("Next Outflow");
    });
  });

  describe("the Mercury status line", () => {
    it("says 'syncing' while a sync is running", () => {
      expect(
        mountSidebar({ mercurySyncing: true, mercuryError: "boom" }).text(),
      ).toContain("syncing");
    });

    it("says 'mercury offline' when the sync failed with nothing to show", () => {
      const wrapper = mountSidebar({ mercuryError: "401 unauthorised" });
      expect(wrapper.text()).toContain("mercury offline");
    });

    it("says 'partial sync' when the sync failed but some workspaces landed", () => {
      const wrapper = mountSidebar({
        mercuryError: "one workspace failed",
        mercuryBalance: mercury(),
      });
      expect(wrapper.text()).toContain("partial sync");
    });

    it("counts the synced workspaces when everything is fine", () => {
      const wrapper = mountSidebar({ mercuryBalance: mercury() });
      expect(wrapper.text()).toContain("mercury · 1");
      expect(wrapper.find('[data-testid="sidebar.workspace.brrrr"]').text()).toContain(
        "42.5k",
      );
      expect(wrapper.find('[data-testid="sidebar.account.acc-1"]').text()).toContain(
        "Operating",
      );
    });

    it("lists per-workspace errors alongside the balances", () => {
      const wrapper = mountSidebar({
        mercuryBalance: mercury({
          workspace_errors: [{ workspace: "flip", error: "token expired" }],
        }),
      });
      expect(
        wrapper.find('[data-testid="sidebar.workspace-error.flip"]').text(),
      ).toContain("token expired");
    });
  });

  describe("the recurring series list", () => {
    it("is absent when there are no rules", () => {
      expect(mountSidebar().text()).not.toContain("Recurring");
    });

    it("sorts outflows above inflows", () => {
      const wrapper = mountSidebar({
        recurringRules: [
          rule({ id: "in", description: "Rent in", amount_k: 3 }),
          rule({ id: "out", description: "HM interest", amount_k: -2.4 }),
        ],
      });

      const ids = wrapper
        .findAll('[data-testid^="sidebar.recurring."]')
        .map((el) => el.attributes("data-testid"))
        .filter((id) => id === "sidebar.recurring.in" || id === "sidebar.recurring.out");
      expect(ids).toEqual(["sidebar.recurring.out", "sidebar.recurring.in"]);
    });

    it.each([
      [rule({ end_date: "2026-12-31" }), "until Dec 31"],
      [rule({ occurrences: 6 }), "6x"],
      [rule(), "no end"],
    ])("summarises when the series ends", (r, expected) => {
      const wrapper = mountSidebar({ recurringRules: [r] });
      expect(
        wrapper.find('[data-testid="sidebar.recurring.rule-1"]').text(),
      ).toContain(expected);
    });

    it("emits editRecurring with the rule id", async () => {
      const wrapper = mountSidebar({ recurringRules: [rule({ id: "rule-7" })] });
      await wrapper
        .find('[data-testid="sidebar.recurring.rule-7.edit"]')
        .trigger("click");
      expect(wrapper.emitted("editRecurring")).toEqual([["rule-7"]]);
    });

    it("emits deleteRecurring with the rule id", async () => {
      const wrapper = mountSidebar({ recurringRules: [rule({ id: "rule-7" })] });
      await wrapper
        .find('[data-testid="sidebar.recurring.rule-7.delete"]')
        .trigger("click");
      expect(wrapper.emitted("deleteRecurring")).toEqual([["rule-7"]]);
    });
  });
});
