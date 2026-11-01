// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";

import TransactionRowActions from "./TransactionRowActions.vue";
import InlineAmountEditor from "./InlineAmountEditor.vue";
import type { LiquidityTransaction } from "../../types/liquidity";

const txn = (over: Partial<LiquidityTransaction> = {}): LiquidityTransaction => ({
  id: "t1", effective_date: "2026-11-20", description: "HML interest for October 2026", amount_dollars: -1970.83, ...over,
});

describe("TransactionRowActions", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 10, 4, 12));
  });
  afterEach(() => vi.useRealTimers());

  it("marks done in one tap", async () => {
    const wrapper = mount(TransactionRowActions, { props: { txn: txn() } });
    await wrapper.find('[data-testid="rowactions.t1.done"]').trigger("click");
    expect(wrapper.emitted("markDone")).toEqual([["t1"]]);
  });

  it("postpones from the row's own date when it is ahead", async () => {
    const wrapper = mount(TransactionRowActions, { props: { txn: txn() } });
    for (const chip of ["day", "week", "first"]) await wrapper.find(`[data-testid="rowactions.t1.postpone.${chip}"]`).trigger("click");
    expect(wrapper.emitted("moveToDate")).toEqual([["t1", "2026-11-21"], ["t1", "2026-11-27"], ["t1", "2026-12-01"]]);
  });

  it("postpones an overdue row from today, so it is no longer overdue", async () => {
    const wrapper = mount(TransactionRowActions, { props: { txn: txn({ effective_date: "2026-11-04", overdue_since_date: "2026-11-01" }) } });
    await wrapper.find('[data-testid="rowactions.t1.postpone.day"]').trigger("click");
    expect(wrapper.emitted("moveToDate")).toEqual([["t1", "2026-11-05"]]);
  });

  it("moves to a picked date", async () => {
    const wrapper = mount(TransactionRowActions, { props: { txn: txn() } });
    await wrapper.find('[data-testid="rowactions.t1.date"]').setValue("2026-12-15");
    expect(wrapper.emitted("moveToDate")).toEqual([["t1", "2026-12-15"]]);
  });

  it("offers nothing on a recurring occurrence", () => {
    const wrapper = mount(TransactionRowActions, { props: { txn: txn({ recurring_rule_id: "rule-1" }) } });
    expect(wrapper.find('[data-testid="rowactions.t1"]').exists()).toBe(false);
  });
});

describe("InlineAmountEditor", () => {
  it("opens on a tap and saves the new amount on Enter, keeping the sign", async () => {
    const wrapper = mount(InlineAmountEditor, { props: { txn: txn() } });
    expect(wrapper.find('[data-testid="amount.t1"]').text()).toBe("-$1,970.83");
    await wrapper.find('[data-testid="amount.t1"]').trigger("click");
    const box = wrapper.find('[data-testid="amount.t1.input"]');
    expect((box.element as HTMLInputElement).value).toBe("1970.83");
    await box.setValue("2100");
    await box.trigger("keydown", { key: "Enter" });
    expect(wrapper.emitted("changeAmount")).toEqual([["t1", -2100]]);
  });

  it("keeps money in positive, and Escape or an unchanged value saves nothing", async () => {
    const wrapper = mount(InlineAmountEditor, { props: { txn: txn({ amount_dollars: 2600 }) } });
    await wrapper.find('[data-testid="amount.t1"]').trigger("click");
    await wrapper.find('[data-testid="amount.t1.input"]').trigger("keydown", { key: "Escape" });
    await wrapper.find('[data-testid="amount.t1"]').trigger("click");
    await wrapper.find('[data-testid="amount.t1.input"]').trigger("keydown", { key: "Enter" });
    expect(wrapper.emitted("changeAmount")).toBeUndefined();
    await wrapper.find('[data-testid="amount.t1"]').trigger("click");
    await wrapper.find('[data-testid="amount.t1.input"]').setValue("2700.5");
    await wrapper.find('[data-testid="amount.t1.input"]').trigger("blur");
    expect(wrapper.emitted("changeAmount")).toEqual([["t1", 2700.5]]);
  });
});
