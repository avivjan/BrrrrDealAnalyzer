// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { enableAutoUnmount, mount, RouterLinkStub } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

import LiquidityTheaterMode from "./LiquidityTheaterMode.vue";
import { useLiquidityStore } from "../../../stores/liquidityStore";

const HEADLINE_FIGURES = {
  balance: "$42,106", balanceTone: "neutral", min: "$6,470", minTone: "positive", minDate: "2028-12-01",
  daysToNegative: "None", daysTone: "positive", reserve: "$5,000",
};

function mountTheater(props: Partial<{ isAnotherDialogOpen: boolean }> = {}) {
  return mount(LiquidityTheaterMode, {
    props: { headlineFigures: HEADLINE_FIGURES, isAnotherDialogOpen: false, ...props },
    global: { stubs: { teleport: true, RouterLink: RouterLinkStub } },
    attachTo: document.body,
  });
}

function pressKey(key: string, target: EventTarget = window) {
  const event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true });
  target.dispatchEvent(event);
  return event;
}

const sheetToggle = (wrapper: ReturnType<typeof mountTheater>) => wrapper.get('[data-testid="theater.sheet.toggle"]');

// A test that fails must not leave its window key listener behind for the next one.
enableAutoUnmount(afterEach);

describe("LiquidityTheaterMode", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 10, 3, 12));
    try { localStorage.removeItem("bw.liquidity.theater.legend-open"); } catch { /* none */ }
  });
  afterEach(() => vi.useRealTimers());

  it("is the full-screen frame from the first render", () => {
    const wrapper = mountTheater();
    expect(wrapper.get('[data-testid="theater.root"]').attributes("aria-modal")).toBe("true");
    expect(wrapper.get('[data-testid="theater.figure.balance"]').text()).toContain("$42,106");
  });

  it("leaves the page on × and on Esc", async () => {
    const wrapper = mountTheater();
    await wrapper.get('[data-testid="theater.close"]').trigger("click");
    pressKey("Escape");
    expect(wrapper.emitted("leave")).toHaveLength(2);
  });

  it("closes the deals sheet with Esc before leaving", async () => {
    const wrapper = mountTheater();
    await sheetToggle(wrapper).trigger("click");
    expect(sheetToggle(wrapper).attributes("aria-expanded")).toBe("true");
    pressKey("Escape");
    await wrapper.vm.$nextTick();
    expect(sheetToggle(wrapper).attributes("aria-expanded")).toBe("false");
    expect(wrapper.emitted("leave")).toBeUndefined();
    pressKey("Escape");
    expect(wrapper.emitted("leave")).toHaveLength(1);
  });

  it("leaves Esc and the shortcuts to another open dialog", async () => {
    const wrapper = mountTheater({ isAnotherDialogOpen: true });
    pressKey("Escape");
    pressKey("d");
    await wrapper.vm.$nextTick();
    expect(wrapper.emitted("leave")).toBeUndefined();
    expect(sheetToggle(wrapper).attributes("aria-expanded")).toBe("false");
  });

  it("ignores a shortcut typed into a field", async () => {
    const wrapper = mountTheater();
    const input = document.createElement("input");
    document.body.appendChild(input);
    pressKey("d", input);
    await wrapper.vm.$nextTick();
    expect(sheetToggle(wrapper).attributes("aria-expanded")).toBe("false");
    input.remove();
  });

  it("has no T shortcut: the theater is the page", () => {
    const wrapper = mountTheater();
    pressKey("t");
    expect(wrapper.emitted("leave")).toBeUndefined();
  });

  it("toggles the legend on L and the deals sheet on D", async () => {
    const wrapper = mountTheater();
    const legendOpenAtFirst = wrapper.find('[data-testid="theater.legend"]').exists();
    pressKey("l");
    await wrapper.vm.$nextTick();
    expect(wrapper.find('[data-testid="theater.legend"]').exists()).toBe(!legendOpenAtFirst);
    pressKey("d");
    await wrapper.vm.$nextTick();
    expect(sheetToggle(wrapper).attributes("aria-expanded")).toBe("true");
  });

  it("shows a spinner during the first load only", async () => {
    const store = useLiquidityStore();
    store.loading = true;
    const wrapper = mountTheater();
    expect(wrapper.find('[data-testid="liquidity.loading"]').exists()).toBe(true);
    store.transactions = [{ id: "u", effective_date: "2026-11-10", description: "Plumber", amount_dollars: -80 }];
    await wrapper.vm.$nextTick();
    expect(wrapper.find('[data-testid="liquidity.loading"]').exists()).toBe(false);
  });

  it("shows when Mercury last synced in the balance popover", async () => {
    const store = useLiquidityStore();
    store.mercuryBalance = {
      total_balance_dollars: 42106, total_available_dollars: 42106, account_count: 3, workspace_count: 1,
      workspaces: [], workspace_errors: [], accounts: [], counted_as_cash_balance_dollars: 42106, mercury_account_ids_counted_as_cash: null,
    };
    store.mercuryLastSyncedAt = new Date(2026, 10, 3, 9, 5).toISOString();
    const wrapper = mountTheater();
    await wrapper.get('[data-testid="theater.figure.balance"]').trigger("click");
    expect(wrapper.get('[data-testid="theater.balance-popover.sync"]').text()).toBe("mercury · 3 accounts across 1 workspace · synced 09:05");
  });

  it("shows the overdue chip and its popover from the store's overdue rows", async () => {
    const store = useLiquidityStore();
    store.transactions = [{ id: "u", effective_date: "2026-11-01", description: "Utilities", amount_dollars: -80 }];
    store.settings = { opening_balance_dollars: 42106, opening_balance_date: "2026-11-03", reserve_dollars: 5000 };
    const wrapper = mountTheater();
    const chip = wrapper.get('[data-testid="theater.figure.overdue"]');
    expect(chip.text()).toContain("1 overdue");
    await chip.trigger("click");
    expect(wrapper.get('[data-testid="theater.overdue-popover"]').text()).toContain("Utilities");
  });

  it("passes an Undo of Done from the day modal on to the view", async () => {
    const store = useLiquidityStore();
    store.settings = { opening_balance_dollars: 42106, opening_balance_date: "2026-11-03", reserve_dollars: 5000 };
    store.transactions = [
      { id: "plumber", effective_date: "2026-11-05", description: "Plumber", amount_dollars: -100 },
      { id: "paid", effective_date: "2026-11-05", description: "Survey", amount_dollars: -385, done_at: "2026-11-05T10:00:00Z" },
    ];
    const wrapper = mountTheater();
    await wrapper.vm.$nextTick();
    // Open the day through the legend-less path: the chart's openDay.
    wrapper.findComponent({ name: "TimelineChart" }).vm.$emit("openDay", "2026-11-05");
    await wrapper.vm.$nextTick();
    const doneRow = wrapper.get('[data-testid="theater.day-modal.done-row.paid"]');
    await doneRow.get('[data-testid="theater.day-modal.done-row.paid.undo"]').trigger("click");
    expect(wrapper.emitted("markNotDone")).toEqual([["paid"]]);
  });

  it("brings the lowest balance into view with its tooltip from the Lowest button", async () => {
    const store = useLiquidityStore();
    store.settings = { opening_balance_dollars: 10_000, opening_balance_date: "2026-11-03", reserve_dollars: 5000 };
    store.transactions = [
      { id: "closing", effective_date: "2026-11-20", description: "Closing", amount_dollars: -9_000 },
      { id: "refi", effective_date: "2026-12-10", description: "Refi", amount_dollars: 6_000 },
    ];
    const wrapper = mountTheater();
    await wrapper.vm.$nextTick();
    const lowest = wrapper.get('[data-testid="theater.lowest"]');
    expect(lowest.attributes("title")).toBe("Lowest balance: $1,000 on Nov 20");
    await lowest.trigger("click");
    expect(wrapper.get('[data-testid="chart.tooltip"]').text()).toContain("Nov 20");
  });
});
