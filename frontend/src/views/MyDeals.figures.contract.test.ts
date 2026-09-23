// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import PrimeVue from "primevue/config";

import MyDeals from "./MyDeals.vue";
import api from "../api";
import type { ActiveDealRes } from "../types";

/**
 * Characterizes the board header's "Avg cash on cash": only BRRRR deals with a
 * real, positive cash-on-cash take part. The calculators encode an unbounded
 * return as -1 (∞) and -2 (-∞); averaging those as percentages made the header
 * lie, and a 0 is "no return", not a data point.
 */

vi.mock("vue-router", () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("../api", () => ({
  default: {
    getActiveDeals: vi.fn(),
    updateActiveDeal: vi.fn(),
    analyzeDeal: vi.fn(),
    getBoughtDeals: vi.fn().mockResolvedValue([]),
    getPipelineTemplates: vi.fn().mockResolvedValue([]),
    downloadDealPdf: vi.fn(),
    deleteActiveDeal: vi.fn(),
    duplicateActiveDeal: vi.fn(),
    moveToBought: vi.fn(),
  },
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const getActiveDeals = vi.mocked(api.getActiveDeals);

function brrrDealWithCashOnCash(id: string, cashOnCash: number): ActiveDealRes {
  return {
    deal_type: "BRRRR",
    id,
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-01T00:00:00.000Z",
    address: `${id} Laurel Grove Ln W`,
    section: 1,
    stage: 1,
    purchasePrice: 200,
    rehabCost: 50,
    cash_on_cash: cashOnCash,
  } as ActiveDealRes;
}

function flipDealWithRoi(id: string, roi: number): ActiveDealRes {
  return {
    deal_type: "FLIP",
    id,
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-01T00:00:00.000Z",
    address: `${id} Flip St`,
    section: 1,
    stage: 1,
    purchasePrice: 200,
    rehabCost: 50,
    roi,
    cash_on_cash: roi,
    // Only the fields the header reads; the rest of the flip response shape is irrelevant here.
  } as unknown as ActiveDealRes;
}

async function mountBoardWith(deals: ActiveDealRes[]) {
  getActiveDeals.mockResolvedValue(deals);
  const wrapper = mount(MyDeals, {
    global: { plugins: [[PrimeVue, { unstyled: true }]] },
  });
  await flushPromises();
  return wrapper;
}

const averageCashOnCashText = (wrapper: Awaited<ReturnType<typeof mountBoardWith>>) =>
  wrapper.find('[data-testid="mydeals.figures.avg-coc"]').text();

describe("MyDeals — header average cash on cash", () => {
  let quiet: ReturnType<typeof vi.spyOn>[];

  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    quiet = (["group", "groupEnd", "log", "warn"] as const).map((m) =>
      vi.spyOn(console, m).mockImplementation(() => {}),
    );
  });

  afterEach(() => {
    for (const spy of quiet) spy.mockRestore();
  });

  it("averages only the positive BRRRR cash-on-cash values, skipping the ∞ / -∞ sentinels, zeros and flips", async () => {
    const wrapper = await mountBoardWith([
      brrrDealWithCashOnCash("deal-12", 12),
      brrrDealWithCashOnCash("deal-8", 8),
      brrrDealWithCashOnCash("deal-infinite", -1),
      brrrDealWithCashOnCash("deal-negative-infinite", -2),
      brrrDealWithCashOnCash("deal-zero", 0),
      flipDealWithRoi("flip-40", 40),
    ]);

    expect(averageCashOnCashText(wrapper)).toBe("10.00%");
  });

  it("shows a dash when no deal has a positive cash-on-cash", async () => {
    const wrapper = await mountBoardWith([
      brrrDealWithCashOnCash("deal-infinite", -1),
      brrrDealWithCashOnCash("deal-negative-infinite", -2),
      brrrDealWithCashOnCash("deal-zero", 0),
    ]);

    expect(averageCashOnCashText(wrapper)).toBe("—");
  });
});
