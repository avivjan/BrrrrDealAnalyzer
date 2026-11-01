// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";

import OverdueTransactionsStrip from "./OverdueTransactionsStrip.vue";
import type { LiquidityTransaction } from "../../types/liquidity";

const row = (id: string, effective_date: string, amount_dollars: number, description = id): LiquidityTransaction =>
  ({ id, effective_date, amount_dollars, description });

const PROPS = {
  overdueMoneyOut: [row("hml", "2026-11-01", -1970.83, "HML interest for October 2026"), row("hoa", "2026-11-01", -450, "HOA dues")],
  expectedMoneyInNotCounted: [row("rent", "2026-11-01", 2600, "Rent collected")],
};

describe("OverdueTransactionsStrip", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 10, 4, 12));
  });
  afterEach(() => vi.useRealTimers());

  it("is hidden when nothing is overdue", () => {
    const wrapper = mount(OverdueTransactionsStrip, { props: { overdueMoneyOut: [], expectedMoneyInNotCounted: [] } });
    expect(wrapper.find('[data-testid="overdue.root"]').exists()).toBe(false);
  });

  it("says how many are overdue and how much is still owed", () => {
    const text = mount(OverdueTransactionsStrip, { props: PROPS }).find('[data-testid="overdue.root"]').text();
    expect(text).toContain("3 overdue");
    expect(text).toContain("$2,420.83 still owed, counted on today");
    expect(text).toContain("1 expected in, not counted");
  });

  it("lists money out as counted and money in as not counted until re-dated", async () => {
    const wrapper = mount(OverdueTransactionsStrip, { props: PROPS });
    await wrapper.find('[data-testid="overdue.toggle"]').trigger("click");
    expect(wrapper.find('[data-testid="overdue.row.hml"]').text()).toContain("overdue since Nov 1 · counted on today");
    expect(wrapper.find('[data-testid="overdue.row.rent"]').text()).toContain("not counted until you give it a new date");
    await wrapper.find('[data-testid="rowactions.rent.postpone.week"]').trigger("click");
    expect(wrapper.emitted("moveToDate")).toEqual([["rent", "2026-11-11"]]);
  });

  it("acts on the selected rows together", async () => {
    const wrapper = mount(OverdueTransactionsStrip, { props: PROPS });
    await wrapper.find('[data-testid="overdue.toggle"]').trigger("click");
    expect(wrapper.find('[data-testid="overdue.bulk"]').exists()).toBe(false);
    await wrapper.find('[data-testid="overdue.row.hml.select"]').setValue(true);
    await wrapper.find('[data-testid="overdue.row.hoa.select"]').setValue(true);
    await wrapper.find('[data-testid="overdue.bulk.postpone.first"]').trigger("click");
    expect(wrapper.emitted("bulkMoveToDate")).toEqual([[["hml", "hoa"], "2026-12-01"]]);
    await wrapper.find('[data-testid="overdue.row.rent.select"]').setValue(true);
    await wrapper.find('[data-testid="overdue.bulk.done"]').trigger("click");
    expect(wrapper.emitted("bulkMarkDone")).toEqual([[["rent"]]]);
  });
});
