// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import PrimeVue from "primevue/config";

import BoughtDeals from "./BoughtDeals.vue";
import api from "../api";
import type { BoughtDealRes } from "../types";

/** The BoughtDeals twin of `MyDeals.invalidInput.contract.test.ts`: the two modals stay identical. */

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
  lowestArv: 300,
  daysUntilRefi: 180,
  ltv_as_precent: 75,
  interestRate: 7,
  rent: 2600,
} as unknown as BoughtDealRes;

async function openTheDeal() {
  getBoughtDeals.mockResolvedValue([structuredClone(BOUGHT_DEAL)]);
  const wrapper = mount(BoughtDeals, { global: { plugins: [[PrimeVue, { unstyled: true }]] } });
  await flushPromises();
  await wrapper.find(`[data-testid="boughtdeals.card.${BOUGHT_DEAL.id}"]`).trigger("click");
  await flushPromises();
  expect(wrapper.find('[data-testid="boughtdeals.modal"]').exists()).toBe(true);
  await vi.advanceTimersByTimeAsync(600);
  await flushPromises();
  analyzeDeal.mockClear();
  updateBoughtDeal.mockClear();
  return wrapper;
}

type Board = Awaited<ReturnType<typeof openTheDeal>>;

async function typeMoney(wrapper: Board, fieldKey: string, dollars: string) {
  const input = wrapper.find(`[data-testid="form.field.${fieldKey}"] [data-part="input"]`);
  await input.trigger("focus");
  await input.setValue(dollars);
  await input.trigger("blur");
}

async function letTheDebouncesFire() {
  await vi.advanceTimersByTimeAsync(3000);
  await flushPromises();
}

const saveStatus = (wrapper: Board) => wrapper.find('[data-testid="boughtdeals.modal.save-status"]');

describe("BoughtDeals — an invalid input pauses the modal", () => {
  let quiet: ReturnType<typeof vi.spyOn>[];

  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    quiet = (["group", "groupEnd", "log", "warn", "error"] as const).map((m) => vi.spyOn(console, m).mockImplementation(() => {}));
    updateBoughtDeal.mockImplementation(async (deal) => ({ ...deal, cash_flow: 420, cash_out_routi_conservative: 999 }));
    analyzeDeal.mockResolvedValue({ cash_flow: 420, cash_out_routi_conservative: 999 });
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-01T09:00:00.000Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
    for (const spy of quiet) spy.mockRestore();
  });

  it("marks the field, replaces the tiles with the notice, and sends nothing", async () => {
    const wrapper = await openTheDeal();
    await typeMoney(wrapper, "lowestArv", "400000");
    await letTheDebouncesFire();

    expect(analyzeDeal).not.toHaveBeenCalled();
    expect(updateBoughtDeal).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="form.field.lowestArv"] [data-part="error-message"]').text()).toBe("Lowest ARV cannot exceed ARV.");
    expect(wrapper.find('[data-testid="form.field.lowestArv"] input').classes()).toContain("ui-input-invalid");
    expect(wrapper.find('[data-testid="form.tab.refinance.has-invalid-input"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="boughtdeals.modal.results-paused.lowestArv"]').text()).toContain("Lowest ARV cannot exceed ARV.");
    expect(wrapper.find('[data-testid="boughtdeals.modal.result.cash_flow"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="boughtdeals.modal.results"]').exists()).toBe(true);
    expect(saveStatus(wrapper).attributes("data-state")).toBe("error");
    expect(saveStatus(wrapper).text()).toBe("Not saved — fix the highlighted inputs");
  });

  it("resumes the analysis and the autosave once the value is fixed", async () => {
    const wrapper = await openTheDeal();
    await typeMoney(wrapper, "lowestArv", "400000");
    await letTheDebouncesFire();
    await typeMoney(wrapper, "lowestArv", "300000");
    await letTheDebouncesFire();

    expect(analyzeDeal).toHaveBeenCalledTimes(1);
    expect(updateBoughtDeal).toHaveBeenCalledTimes(1);
    expect(updateBoughtDeal.mock.calls[0]![0]).toMatchObject({ lowestArv: 300 });
    expect(wrapper.find('[data-testid="boughtdeals.modal.results-paused"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="boughtdeals.modal.result.cash_out_routi_conservative"]').text()).toBe("$999");
  });

  it("closing on an invalid input asks, and on OK puts only that field back before saving", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    const wrapper = await openTheDeal();
    await typeMoney(wrapper, "lowestArv", "400000");

    await wrapper.find('[data-testid="boughtdeals.modal.footer-close"]').trigger("click");
    await flushPromises();
    expect(wrapper.find('[data-testid="boughtdeals.modal"]').exists()).toBe(true);
    expect(updateBoughtDeal).not.toHaveBeenCalled();

    await wrapper.find('[data-testid="boughtdeals.modal.footer-close"]').trigger("click");
    await flushPromises();
    expect(confirmSpy).toHaveBeenCalledTimes(2);
    expect(confirmSpy.mock.calls[1]![0]).toContain("- Lowest ARV cannot exceed ARV. (Refinance tab)");
    expect(wrapper.find('[data-testid="boughtdeals.modal"]').exists()).toBe(false);
    expect(updateBoughtDeal).toHaveBeenCalledTimes(1);
    expect(updateBoughtDeal.mock.calls[0]![0]).toMatchObject({ lowestArv: 300 });
    confirmSpy.mockRestore();
  });
});
