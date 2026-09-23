// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import PrimeVue from "primevue/config";

import BoughtDeals from "./BoughtDeals.vue";
import api from "../api";
import type { BoughtDealRes } from "../types";

/**
 * "View Report" on a bought deal: the same branded PDF My Deals offers, built from
 * the bought deal sent whole to the report endpoint for its strategy, previewed in
 * the shared preview modal under the `boughtdeals.` test-id namespace.
 */

vi.mock("../api", () => ({
  default: {
    getBoughtDeals: vi.fn(),
    updateBoughtDeal: vi.fn(),
    deleteBoughtDeal: vi.fn(),
    analyzeDeal: vi.fn(),
    downloadDealPdf: vi.fn(),
    getPipelineTemplates: vi.fn().mockResolvedValue([]),
    getPipelineTemplateStats: vi.fn().mockResolvedValue({}),
  },
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const getBoughtDeals = vi.mocked(api.getBoughtDeals);
const updateBoughtDeal = vi.mocked(api.updateBoughtDeal);
const analyzeDeal = vi.mocked(api.analyzeDeal);
const downloadDealPdf = vi.mocked(api.downloadDealPdf);

const BOUGHT_DEAL = {
  deal_type: "BRRRR",
  id: "bought-1",
  created_at: "2026-01-01T00:00:00.000Z",
  updated_at: "2026-01-01T00:00:00.000Z",
  address: "55 Willow Way",
  section: 2,
  stage: 3,
  boughtStage: "rehab",
  completedSubstages: { purchase_agreement: true, emd: true },
  purchasePrice: 200,
  rehabCost: 50,
  arv_in_thousands: 320,
  rent: 2600,
} as unknown as BoughtDealRes;

let mountedBoard: VueWrapper | null = null;

async function openTheDeal() {
  getBoughtDeals.mockResolvedValue([structuredClone(BOUGHT_DEAL)]);
  const wrapper = mount(BoughtDeals, { global: { plugins: [[PrimeVue, { unstyled: true }]] } });
  mountedBoard = wrapper;
  await flushPromises();
  await wrapper.find(`[data-testid="boughtdeals.card.${BOUGHT_DEAL.id}"]`).trigger("click");
  await flushPromises();
  expect(wrapper.find('[data-testid="boughtdeals.modal"]').exists()).toBe(true);
  // Opening the modal schedules its own debounced analyze; let it fire first.
  await vi.advanceTimersByTimeAsync(600);
  await flushPromises();
  return wrapper;
}

describe("BoughtDeals — View Report", () => {
  let quiet: ReturnType<typeof vi.spyOn>[];

  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    quiet = (["group", "groupEnd", "log", "warn", "error"] as const).map((method) =>
      vi.spyOn(console, method).mockImplementation(() => {}),
    );
    updateBoughtDeal.mockImplementation(async (deal) => ({ ...deal }));
    analyzeDeal.mockResolvedValue({ cash_flow: 350 });
    URL.createObjectURL = vi.fn(() => "blob:bought-report");
    URL.revokeObjectURL = vi.fn();
    downloadDealPdf.mockResolvedValue(new Blob(["%PDF"], { type: "application/pdf" }));
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-01T09:00:00.000Z"));
  });

  afterEach(() => {
    mountedBoard?.unmount();
    mountedBoard = null;
    document.body.innerHTML = "";
    vi.useRealTimers();
    quiet.forEach((spy) => spy.mockRestore());
  });

  it("offers the report in the modal header and no preview until it is asked for", async () => {
    const wrapper = await openTheDeal();
    expect(wrapper.find('[data-testid="boughtdeals.modal.view-report"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="boughtdeals.pdf-modal"]').exists()).toBe(false);
  });

  it("sends the bought deal whole to the endpoint for its strategy and previews the blob", async () => {
    const wrapper = await openTheDeal();
    await wrapper.find('[data-testid="boughtdeals.modal.view-report"]').trigger("click");
    await flushPromises();

    expect(downloadDealPdf).toHaveBeenCalledTimes(1);
    const [payload, dealType, address] = downloadDealPdf.mock.calls[0]!;
    expect(dealType).toBe("BRRRR");
    expect(address).toBe("55 Willow Way");
    expect(payload).toMatchObject({ purchasePrice: 200, arv_in_thousands: 320, boughtStage: "rehab" });

    const preview = wrapper.find('[data-testid="boughtdeals.pdf-modal"]');
    expect(preview.exists()).toBe(true);
    expect(wrapper.find('[data-testid="boughtdeals.pdf-modal.iframe"]').attributes("src")).toBe("blob:bought-report");
    expect(preview.text()).toContain("55 Willow Way");
  });

  it("closes the preview and revokes the blob URL from the shared modal's close button", async () => {
    const wrapper = await openTheDeal();
    await wrapper.find('[data-testid="boughtdeals.modal.view-report"]').trigger("click");
    await flushPromises();
    await wrapper.find('[data-testid="boughtdeals.pdf-modal.close"]').trigger("click");
    await flushPromises();
    expect(wrapper.find('[data-testid="boughtdeals.pdf-modal"]').exists()).toBe(false);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:bought-report");
    // The deal modal itself stays open.
    expect(wrapper.find('[data-testid="boughtdeals.modal"]').exists()).toBe(true);
  });
});
