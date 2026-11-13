// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

import DealImportPreviewModal from "../DealImportPreviewModal.vue";
import { useLiquidityStore } from "../../../stores/liquidityStore";
import type { DealCashRowChange, DealCashRowChanges } from "../../../types/liquidity";

function change(over: Partial<DealCashRowChange>): DealCashRowChange {
  return {
    change_kind: "added", item_key: "cash_to_close_buy", occurrence_number: 1, description: "Cash to close", transaction_id: null,
    date_before: null, date_after: "2026-11-10", amount_dollars_before: null, amount_dollars_after: -80_000,
    deal_date_not_applied_because_you_changed_it: null, deal_amount_dollars_not_applied_because_you_changed_it: null,
    created_because_refi_is_late: false, ...over,
  };
}

function preview(changes: DealCashRowChange[], counts: Partial<DealCashRowChanges["change_counts"]> = {}): DealCashRowChanges {
  return {
    deal_board: "my_deals", deal_id: "d1", deal_address: "2897 10th Str", changes,
    change_counts: { added: changes.length, updated: 0, removed: 0, unchanged: 0, kept_done: 0, kept_no_longer_in_the_deal: 0, conflicts_with_your_changes: 0, ...counts },
    milestone_date_changes: [],
    key_dates: [{ key: "refi_closed", date: "2027-01-05", description: "Refi closing" }],
  };
}

async function mountView(previewResult: DealCashRowChanges, openingBalanceDollars = 52_033,
  transactions: ReturnType<typeof useLiquidityStore>["transactions"] = [{ id: "rent", effective_date: "2027-06-01", description: "Rent", amount_dollars: 100 }]) {
  const store = useLiquidityStore();
  store.settings = { opening_balance_dollars: openingBalanceDollars, opening_balance_date: "2026-11-03", reserve_dollars: 5_000 };
  store.transactions = transactions;
  vi.spyOn(store, "fetchAll").mockResolvedValue();
  vi.spyOn(store, "previewDealImport").mockResolvedValue(previewResult);
  const importDeal = vi.spyOn(store, "importDeal").mockResolvedValue(previewResult);
  const wrapper = mount(DealImportPreviewModal, {
    props: { dealBoard: "my_deals", dealId: "d1", dealAddress: "2897 10th Str, St. Augustine, FL 32084" },
    global: { stubs: { teleport: true } },
    attachTo: document.body,
  });
  await flushPromises();
  return { wrapper, importDeal };
}

enableAutoUnmount(afterEach);

describe("DealImpactView", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 10, 3, 12));
  });
  afterEach(() => vi.useRealTimers());

  it("leads with the verdict when the deal goes negative, and the primary says Import anyway", async () => {
    const { wrapper } = await mountView(preview([change({}), change({ item_key: "construction_account_balance_returned_at_rehab_end", description: "Construction account balance returned at rehab end (cushion + draw spread)", date_after: "2027-01-05", amount_dollars_after: 10_000 })]));
    const verdict = wrapper.get('[data-testid="deal-impact.verdict"]');
    expect(verdict.attributes("data-risk-level")).toBe("goes_negative");
    expect(verdict.get('[data-testid="deal-impact.verdict.headline"]').text()).toBe(
      "This deal takes you $27,967 below zero on Nov 10, 2026, and you don't recover in the timeline.");
    expect(verdict.get('[data-testid="deal-impact.verdict.follow-up"]').text()).toContain("Bring $32,967 by Nov 10, 2026 to keep your reserve");
    expect(wrapper.get('[data-testid="deal-import-preview.confirm"]').text()).toBe("Import anyway · 2 rows");
    const crunch = wrapper.get('[data-insight="crunch"]');
    expect(crunch.text()).toContain("-$27,967");
    expect(crunch.text()).toContain("Current: $52,033");
    expect(wrapper.get('[data-insight="cash-to-stay-above-zero"]').text()).toContain("$27,967");
  });

  it("says it stays safe with plenty of cash, and keeps the rows collapsed for an import", async () => {
    const { wrapper } = await mountView(preview([change({ amount_dollars_after: -20_000 })]), 400_000);
    expect(wrapper.get('[data-testid="deal-impact.verdict"]').attributes("data-risk-level")).toBe("stays_above_reserve");
    expect(wrapper.get('[data-testid="deal-import-preview.confirm"]').text()).toBe("Import 1 rows");
    expect(wrapper.get('[data-testid="deal-impact.rows.toggle"]').attributes("aria-expanded")).toBe("false");
    expect(wrapper.get('[data-insight="crunch"]').text()).toContain("No extra cash needed.");
    expect(wrapper.text()).toContain("With this deal");
  });

  it("reviews a re-sync as Now vs After these changes, worded as applying them, with the rows open", async () => {
    const resyncChanges = [change({ change_kind: "updated", transaction_id: "t1", date_before: "2026-11-10", amount_dollars_before: -80_000, amount_dollars_after: -70_000 })];
    const { wrapper } = await mountView(preview(resyncChanges, { added: 0, updated: 1 }), 400_000,
      [{ id: "t1", effective_date: "2026-11-10", description: "Cash to close", amount_dollars: -80_000, source_deal_board: "my_deals", source_deal_id: "d1" }]);
    expect(wrapper.get('[data-testid="deal-import-preview"]').attributes("data-mode")).toBe("resync");
    expect(wrapper.get("h2").text()).toBe("Re-sync with liquidity");
    expect(wrapper.text()).toContain("After these changes");
    expect(wrapper.get('[data-testid="deal-impact.verdict.headline"]').text()).toMatch(/^These changes improve your lowest point by \$10,000/);
    expect(wrapper.get('[data-testid="deal-impact.rows.toggle"]').attributes("aria-expanded")).toBe("true");
    expect(wrapper.get('[data-testid="deal-import-preview.confirm"]').text()).toBe("Re-sync 1 row");
  });

  it("imports on the primary, then closes", async () => {
    const { wrapper, importDeal } = await mountView(preview([change({ amount_dollars_after: -20_000 })]), 400_000);
    await wrapper.get('[data-testid="deal-import-preview.confirm"]').trigger("click");
    await flushPromises();
    expect(importDeal).toHaveBeenCalledWith("my_deals", "d1", []);
    expect(wrapper.emitted("imported")).toHaveLength(1);
    expect(wrapper.emitted("close")).toHaveLength(1);
  });

  it("closes on × and on Esc, before anything underneath does", async () => {
    const { wrapper } = await mountView(preview([change({})]));
    await wrapper.get('[data-testid="deal-impact.close"]').trigger("click");
    const underneath = vi.fn();
    window.addEventListener("keydown", underneath);
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
    window.removeEventListener("keydown", underneath);
    expect(wrapper.emitted("close")).toHaveLength(2);
    expect(underneath).not.toHaveBeenCalled();
  });
});
