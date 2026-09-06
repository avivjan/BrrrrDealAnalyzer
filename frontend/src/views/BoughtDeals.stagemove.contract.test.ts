// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import PrimeVue from "primevue/config";

import BoughtDeals from "./BoughtDeals.vue";
import api from "../api";
import { useBoughtDealStore } from "../stores/boughtDealStore";
import type { BoughtDealRes } from "../types";

/**
 * UI v3 (4.0): a stage move keeps every tick.
 *
 * Every stage's checklist is on the card, so a task ticked ahead of time has
 * to survive the move that reaches it. The frozen store actions reset the map;
 * the view routes moves through `updateBoughtDeal` instead. This pins that
 * contract: the PUT carries `completedSubstages` untouched, a failed PUT
 * reverts the stage, and the ±1 / checklist gates still hold with their copy.
 */

vi.mock("../api", () => ({
  default: {
    getBoughtDeals: vi.fn(),
    updateBoughtDeal: vi.fn(),
    deleteBoughtDeal: vi.fn(),
    analyzeDeal: vi.fn(),
    getPipelineTemplates: vi.fn().mockResolvedValue([]),
    getPipelineTemplateStats: vi.fn().mockResolvedValue({}),
  },
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const getBoughtDeals = vi.mocked(api.getBoughtDeals);
const updateBoughtDeal = vi.mocked(api.updateBoughtDeal);

/** Purchase stage done, and one Prepare-for-Closing task ticked ahead of time. */
const DEAL = {
  deal_type: "BRRRR",
  id: "bought-1",
  created_at: "2026-01-01T00:00:00.000Z",
  updated_at: "2026-01-01T00:00:00.000Z",
  address: "55 Willow Way",
  section: 2,
  stage: 3,
  boughtStage: "purchase",
  completedSubstages: { purchase_agreement: true, emd: true, lender_approval: true },
  purchasePrice: 200,
  rehabCost: 50,
} as unknown as BoughtDealRes;

async function mountBoard(deal: BoughtDealRes) {
  // A fresh copy per test: the board mutates the very object the store holds.
  getBoughtDeals.mockResolvedValue([structuredClone(deal)]);
  const wrapper = mount(BoughtDeals, {
    global: { plugins: [[PrimeVue, { unstyled: true }]] },
  });
  await flushPromises();
  const stored = useBoughtDealStore().boughtDeals[0]!;
  // `<script setup>` bindings are reachable on `vm` in tests.
  const vm = wrapper.vm as unknown as {
    onDrop: (event: unknown, stageId: string) => Promise<void>;
    advanceDeal: (deal: BoughtDealRes) => Promise<void>;
  };
  return { wrapper, stored, vm };
}

describe("BoughtDeals — stage moves keep ticks", () => {
  let quiet: ReturnType<typeof vi.spyOn>[];
  let alertSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    quiet = (["group", "groupEnd", "log", "warn", "error"] as const).map((m) =>
      vi.spyOn(console, m).mockImplementation(() => {}),
    );
    alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    updateBoughtDeal.mockImplementation(async (deal) => ({ ...deal }));
  });

  afterEach(() => {
    for (const spy of quiet) spy.mockRestore();
    alertSpy.mockRestore();
  });

  it("a forward drag sends the same PUT autosave uses, with every tick intact", async () => {
    const { stored, vm } = await mountBoard(DEAL);
    await vm.onDrop({ added: { element: stored } }, "prepare_for_closing");

    expect(updateBoughtDeal).toHaveBeenCalledTimes(1);
    const body = updateBoughtDeal.mock.calls[0]![0];
    expect(body.boughtStage).toBe("prepare_for_closing");
    expect(body.completedSubstages).toEqual({
      purchase_agreement: true,
      emd: true,
      lender_approval: true,
    });
  });

  it("a move back keeps the stage just left ticked", async () => {
    const { stored, vm } = await mountBoard({ ...DEAL, boughtStage: "prepare_for_closing" });
    await vm.onDrop({ added: { element: stored } }, "purchase");

    const body = updateBoughtDeal.mock.calls[0]![0];
    expect(body.boughtStage).toBe("purchase");
    expect(body.completedSubstages).toEqual(DEAL.completedSubstages);
  });

  it("reverts the stage when the PUT fails", async () => {
    updateBoughtDeal.mockRejectedValueOnce(new Error("offline"));
    const { stored, vm } = await mountBoard(DEAL);
    await vm.onDrop({ added: { element: stored } }, "prepare_for_closing");

    expect(stored.boughtStage).toBe("purchase");
    expect(stored.completedSubstages).toEqual(DEAL.completedSubstages);
  });

  it("still refuses a forward move while the current checklist is incomplete", async () => {
    const { stored, vm } = await mountBoard({
      ...DEAL,
      completedSubstages: { purchase_agreement: true, lender_approval: true },
    });
    await vm.onDrop({ added: { element: stored } }, "prepare_for_closing");

    expect(updateBoughtDeal).not.toHaveBeenCalled();
    expect(alertSpy).toHaveBeenCalledWith(
      "Cannot advance: complete these sub-stages first:\n- EMD",
    );
  });

  it("still refuses a jump of more than one stage", async () => {
    const { stored, vm } = await mountBoard(DEAL);
    await vm.onDrop({ added: { element: stored } }, "closed");

    expect(updateBoughtDeal).not.toHaveBeenCalled();
    expect(alertSpy).toHaveBeenCalledWith("You can only move deals one stage at a time.");
  });

  it("the card's advance goes one stage forward through the same path", async () => {
    const { stored, vm } = await mountBoard(DEAL);
    await vm.advanceDeal(stored);

    const body = updateBoughtDeal.mock.calls[0]![0];
    expect(body.boughtStage).toBe("prepare_for_closing");
    expect(body.completedSubstages).toEqual(DEAL.completedSubstages);
  });
});
