// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount, RouterLinkStub } from "@vue/test-utils";

import DealLegendPanel from "./DealLegendPanel.vue";
import type { ImportedLiquidityDeal, LiquidityTransaction } from "../../../types/liquidity";

const deal = (deal_id: string, deal_address: string, over: Partial<ImportedLiquidityDeal> = {}): ImportedLiquidityDeal => ({
  deal_board: "my_deals", deal_id, deal_address, my_deals_deal_id_it_was_moved_from: null, liquidity_rows_out_of_date: false,
  open_row_count: 2, done_row_count: 0, overdue_open_row_count: 1, late_refi_row_count: 0, refi_is_late: false, milestones: [], ...over,
});
const row = (id: string, source_deal_id: string | null, amount_dollars = -100): LiquidityTransaction => ({
  id, effective_date: "2026-09-01", description: `Row ${id}`, amount_dollars,
  source_deal_board: source_deal_id ? "my_deals" : null, source_deal_id,
});

const DEALS = [deal("d1", "4431 Victor St, Jacksonville, FL 32207"), deal("d2", "88 Ocean Ave"), deal("d3", "Done Deal Rd", { open_row_count: 0, done_row_count: 3 })];
const OVERDUE_MONEY_OUT = [row("a", "d1"), row("b", "d1"), row("c", "d2"), row("m", null)];

function mountLegend() {
  return mount(DealLegendPanel, {
    props: {
      importedDeals: DEALS,
      overdueMoneyOut: OVERDUE_MONEY_OUT,
      expectedMoneyInNotCounted: [row("rent", "d2", 2600)],
      transactions: [...OVERDUE_MONEY_OUT, { ...row("future", null), effective_date: "2026-10-01" }],
      recurringRules: [{ id: "r1", description: "Misc", amount_dollars: -1500, start_date: "2026-09-01", end_date: null, occurrences: null, frequency: "monthly", interval: 1 }],
    },
    global: { stubs: { RouterLink: RouterLinkStub } },
  });
}

describe("DealLegendPanel", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 8, 4, 12));
  });
  afterEach(() => vi.useRealTimers());

  it("lists only the deals still in the timeline, with a live overdue pill each", () => {
    const entries = mountLegend().findAll('[data-testid="theater.legend.deal"]');
    expect(entries.map((entry) => entry.text())).toEqual([expect.stringContaining("4431 Victor St"), expect.stringContaining("88 Ocean Ave")]);
    expect(entries[0]!.get('[data-testid="theater.legend.deal.overdue"]').text()).toBe("2 overdue");
    expect(entries[1]!.get('[data-testid="theater.legend.deal.overdue"]').text()).toBe("2 overdue");
  });

  it("opens a deal's own overdue rows inline, with their actions", async () => {
    const wrapper = mountLegend();
    await wrapper.findAll('[data-testid="theater.legend.deal.toggle"]')[0]!.trigger("click");
    const drawer = wrapper.get('[data-testid="theater.legend.deal.drawer"]');
    expect(drawer.findAll('[data-testid^="theater.legend.overdue-row."]').map((item) => item.attributes("data-testid"))).toEqual([
      "theater.legend.overdue-row.a", "theater.legend.overdue-row.b",
    ]);
    await drawer.get('[data-testid="rowactions.a.done"]').trigger("click");
    expect(wrapper.emitted("markDone")).toEqual([["a"]]);
  });

  it("asks the view to take a deal out of the timeline", async () => {
    const wrapper = mountLegend();
    await wrapper.findAll('[data-testid="theater.legend.deal.remove"]')[1]!.trigger("click");
    expect(wrapper.emitted("removeDealFromTimeline")?.[0]?.[0]).toMatchObject({ deal_id: "d2" });
  });

  it("highlights a deal on hover and clears it on leave", async () => {
    const wrapper = mountLegend();
    const entry = wrapper.findAll('[data-testid="theater.legend.deal"]')[0]!;
    await entry.trigger("mouseenter");
    await entry.trigger("mouseleave");
    expect(wrapper.emitted("highlightDeal")).toEqual([["my_deals:d1"], [null]]);
  });

  it("lists a deal's transactions by month, collapsed until asked, and an open row opens its day", async () => {
    const wrapper = mountLegend();
    await wrapper.findAll('[data-testid="theater.legend.deal.toggle"]')[0]!.trigger("click");
    const section = wrapper.get('[data-testid="theater.legend.deal.transactions-section"]');
    expect(section.text()).toContain("Transactions (2)");
    expect(wrapper.find('[data-testid="theater.legend.deal.transactions"]').exists()).toBe(false);
    await section.trigger("click");
    const months = wrapper.findAll('[data-testid="theater.legend.transactions-month"]');
    expect(months.map((month) => month.attributes("data-month"))).toEqual(["2026-09"]);
    expect(months[0]!.text()).toContain("Sep 2026");
    expect(months[0]!.text()).toContain("2 rows");
    await wrapper.get('[data-testid="theater.legend.transaction.a"]').trigger("click");
    expect(wrapper.emitted("openDay")).toEqual([["2026-09-01"]]);
  });

  it("collapses a month and the overdue section on a click", async () => {
    const wrapper = mountLegend();
    await wrapper.findAll('[data-testid="theater.legend.deal.toggle"]')[0]!.trigger("click");
    await wrapper.get('[data-testid="theater.legend.deal.overdue-section"]').trigger("click");
    expect(wrapper.find('[data-testid="theater.legend.overdue-row.a"]').exists()).toBe(false);
    await wrapper.get('[data-testid="theater.legend.deal.transactions-section"]').trigger("click");
    await wrapper.get('[data-testid="theater.legend.transactions-month.toggle"]').trigger("click");
    expect(wrapper.find('[data-testid="theater.legend.transaction.a"]').exists()).toBe(false);
  });

  it("shows a done row greyed out and struck through, and Undo reopens it", async () => {
    const doneRow = { ...row("paid", "d1"), effective_date: "2026-09-02", done_at: "2026-09-03T10:00:00Z" };
    const wrapper = mount(DealLegendPanel, {
      props: {
        importedDeals: [deal("d1", "4431 Victor St")], overdueMoneyOut: [row("a", "d1")], expectedMoneyInNotCounted: [],
        transactions: [row("a", "d1"), doneRow], recurringRules: [],
      },
      global: { stubs: { RouterLink: RouterLinkStub } },
    });
    await wrapper.get('[data-testid="theater.legend.deal.toggle"]').trigger("click");
    const section = wrapper.get('[data-testid="theater.legend.deal.transactions-section"]');
    expect(section.text()).toContain("Transactions (2) · 1 done");
    await section.trigger("click");
    const done = wrapper.get('[data-testid="theater.legend.transaction.paid"]');
    expect(done.attributes("data-done")).toBe("true");
    expect(done.classes()).toContain("opacity-60");
    expect(done.find(".line-through").text()).toBe("Sep 2");
    await done.get('[data-testid="theater.legend.transaction.paid.undo"]').trigger("click");
    expect(wrapper.emitted("markNotDone")).toEqual([["paid"]]);
  });

  it("puts the key dates among the transactions, with each milestone's state", async () => {
    const wrapper = mount(DealLegendPanel, {
      props: {
        importedDeals: [deal("d1", "4431 Victor St", {
          milestones: [{ milestone: "purchase_closed", planned_date: "2026-09-01", approved_at: "2026-09-01T12:00:00Z", is_overdue: false }],
          key_dates: [
            { key: "purchase_closed", date: "2026-09-01", description: "Purchase closing" },
            { key: "property_tax_bill_paid_on_november_30", date: "2026-11-30", description: "Property tax bill paid from the tax bucket (Nov 30)" },
          ],
        })],
        overdueMoneyOut: [], expectedMoneyInNotCounted: [], transactions: [row("a", "d1")], recurringRules: [],
      },
      global: { stubs: { RouterLink: RouterLinkStub } },
    });
    await wrapper.get('[data-testid="theater.legend.deal.toggle"]').trigger("click");
    await wrapper.get('[data-testid="theater.legend.deal.transactions-section"]').trigger("click");
    const septemberItems = wrapper.get('[data-testid="theater.legend.transactions-month"]').findAll("li");
    expect(septemberItems[0]!.text()).toContain("Purchase closing");
    expect(septemberItems[0]!.text()).toContain("done");
    expect(septemberItems[1]!.text()).toContain("Row a");
    const novemberToggle = wrapper.findAll('[data-testid="theater.legend.transactions-month.toggle"]')[1]!;
    await novemberToggle.trigger("click");
    const taxBill = wrapper.get('[data-testid="theater.legend.key-date"][data-key-date="property_tax_bill_paid_on_november_30"]');
    await taxBill.trigger("click");
    expect(wrapper.emitted("openDay")).toEqual([["2026-11-30"]]);
  });

  it("keeps a deal whose rows are all done under Finished deals, its transactions open at once", async () => {
    const wrapper = mount(DealLegendPanel, {
      props: {
        importedDeals: [deal("d9", "9 Done Rd", { open_row_count: 0, done_row_count: 1, overdue_open_row_count: 0 })],
        overdueMoneyOut: [], expectedMoneyInNotCounted: [],
        transactions: [{ ...row("x", "d9"), done_at: "2026-09-02T00:00:00Z" }], recurringRules: [],
      },
      global: { stubs: { RouterLink: RouterLinkStub } },
    });
    expect(wrapper.find('[data-testid="theater.legend.deal"]').exists()).toBe(false);
    await wrapper.get('[data-testid="theater.legend.finished-deals"]').trigger("click");
    const finished = wrapper.get('[data-testid="theater.legend.deal"]');
    expect(finished.attributes("data-finished")).toBe("true");
    expect(finished.find('[data-testid="theater.legend.deal.remove"]').exists()).toBe(false);
    await finished.get('[data-testid="theater.legend.deal.toggle"]').trigger("click");
    expect(wrapper.find('[data-testid="theater.legend.transaction.x.undo"]').exists()).toBe(true);
  });

  it("says how many rows a late refi added", async () => {
    const wrapper = mount(DealLegendPanel, {
      props: {
        importedDeals: [deal("d1", "1 Main St", { refi_is_late: true, late_refi_row_count: 3 })],
        overdueMoneyOut: [], expectedMoneyInNotCounted: [], transactions: [], recurringRules: [],
      },
      global: { stubs: { RouterLink: RouterLinkStub } },
    });
    await wrapper.get('[data-testid="theater.legend.deal.toggle"]').trigger("click");
    expect(wrapper.get('[data-testid="theater.legend.deal.refi-late"]').text()).toBe("Refi late · 3 added rows");
  });

  it("flags an out-of-date deal on its collapsed row, and opens its review from there", async () => {
    const wrapper = mount(DealLegendPanel, {
      props: {
        importedDeals: [deal("d1", "1 Main St", { liquidity_rows_out_of_date: true }), deal("d2", "2 Main St")],
        overdueMoneyOut: [], expectedMoneyInNotCounted: [], transactions: [], recurringRules: [],
      },
      global: { stubs: { RouterLink: RouterLinkStub } },
    });
    const buttons = wrapper.findAll('[data-testid="theater.legend.deal.review-changes-collapsed"]');
    expect(buttons).toHaveLength(1);
    await buttons[0]!.trigger("click");
    expect(wrapper.emitted("reviewChanges")?.[0]?.[0]).toMatchObject({ deal_id: "d1" });
  });

  it("counts the open manual rows as Other flows and lists the recurring series", () => {
    const wrapper = mountLegend();
    expect(wrapper.get('[data-testid="theater.legend.other-flows"]').text()).toContain("2 open");
    expect(wrapper.get('[data-testid="theater.legend.recurring.r1"]').text()).toContain("Misc");
  });
});
