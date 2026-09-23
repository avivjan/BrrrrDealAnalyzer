// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import PrimeVue from "primevue/config";

import MyDeals from "./MyDeals.vue";
import api from "../api";
import type { ActiveDealRes } from "../types";
import { BRRRR_REPORT_RESULT_TILES, FLIP_REPORT_RESULT_TILES } from "../components/deal/reportResultTiles";

/**
 * "Generate Report" in the My Deals modal: the button opens the result picker
 * (the modal's tiles, all checked, each with the analysis value); Generate sends
 * the deal and the checked result keys to the report endpoint for the deal's
 * strategy and opens the PDF in the preview.
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
const updateActiveDeal = vi.mocked(api.updateActiveDeal);
const analyzeDeal = vi.mocked(api.analyzeDeal);
const downloadDealPdf = vi.mocked(api.downloadDealPdf);

const BRRRR_DEAL = {
  deal_type: "BRRRR",
  id: "deal-1",
  created_at: "2026-01-01T00:00:00.000Z",
  updated_at: "2026-01-01T00:00:00.000Z",
  address: "2286 Laurel Grove Ln W",
  section: 1,
  stage: 1,
  purchasePrice: 200,
  rehabCost: 50,
  arv_in_thousands: 320,
  rent: 2600,
  cash_flow: 350,
  dscr: 1.3647,
} as unknown as ActiveDealRes;

let mountedBoard: VueWrapper | null = null;

const resultPicker = () => document.querySelector('[data-testid="generate-report-result-picker"]');
const pickerPart = (name: string) =>
  document.querySelector(`[data-testid="generate-report-result-picker"] [data-part="${name}"]`) as HTMLButtonElement;
const pickerResultKeys = () =>
  [...document.querySelectorAll('[data-part="result-option"]')].map((option) => (option as HTMLElement).dataset.resultKey);
const checkedPickerResultKeys = () =>
  [...document.querySelectorAll('[data-part="result-option"]')]
    .filter((option) => (option.querySelector("input") as HTMLInputElement).checked)
    .map((option) => (option as HTMLElement).dataset.resultKey);

async function openTheDeal(deal: ActiveDealRes = BRRRR_DEAL) {
  getActiveDeals.mockResolvedValue([deal]);
  const wrapper = mount(MyDeals, { global: { plugins: [[PrimeVue, { unstyled: true }]] } });
  mountedBoard = wrapper;
  await flushPromises();
  await wrapper.find('[data-testid="mydeals.card.deal-1"]').trigger("click");
  await flushPromises();
  await vi.advanceTimersByTimeAsync(600);
  await flushPromises();
  return wrapper;
}

describe("MyDeals — Generate Report", () => {
  let quiet: ReturnType<typeof vi.spyOn>[];

  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    quiet = (["group", "groupEnd", "log", "warn", "error"] as const).map((method) =>
      vi.spyOn(console, method).mockImplementation(() => {}),
    );
    updateActiveDeal.mockImplementation(async (deal) => deal);
    analyzeDeal.mockResolvedValue({ cash_flow: 350, dscr: 1.3647 });
    URL.createObjectURL = vi.fn(() => "blob:my-deal-report");
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

  it("the header button reads 'Generate Report' and opens the picker with every BRRRR result checked", async () => {
    const wrapper = await openTheDeal();
    const button = wrapper.find('[data-testid="mydeals.modal.view-report"]');
    expect(button.text()).toBe("Generate Report");
    await button.trigger("click");
    await flushPromises();
    expect(resultPicker()).not.toBeNull();
    expect(pickerResultKeys()).toEqual(BRRRR_REPORT_RESULT_TILES.map((tile) => tile.resultKey));
    expect(checkedPickerResultKeys()).toEqual(pickerResultKeys());
    expect(document.querySelector('[data-result-key="dscr"] [data-part="result-option-value"]')!.textContent!.trim()).toBe("1.36x");
    expect(downloadDealPdf).not.toHaveBeenCalled();
    // The deal modal stays open underneath.
    expect(wrapper.find('[data-testid="mydeals.modal"]').exists()).toBe(true);
  });

  it("Generate sends the deal with only the checked results and previews the PDF", async () => {
    const wrapper = await openTheDeal();
    await wrapper.find('[data-testid="mydeals.modal.view-report"]').trigger("click");
    await flushPromises();
    (document.querySelector('[data-result-key="roi"] input') as HTMLInputElement).click();
    await flushPromises();
    pickerPart("generate").click();
    await flushPromises();

    expect(resultPicker()).toBeNull();
    expect(downloadDealPdf).toHaveBeenCalledTimes(1);
    const [payload, dealType, address, selectedResultKeys] = downloadDealPdf.mock.calls[0]!;
    expect(dealType).toBe("BRRRR");
    expect(address).toBe("2286 Laurel Grove Ln W");
    expect(payload).toMatchObject({ purchasePrice: 200, arv_in_thousands: 320 });
    expect(selectedResultKeys).toEqual(BRRRR_REPORT_RESULT_TILES.map((tile) => tile.resultKey).filter((key) => key !== "roi"));
    expect(wrapper.find('[data-testid="mydeals.pdf-modal.iframe"]').attributes("src")).toBe("blob:my-deal-report");
  });

  it("a flip deal is offered the flip results", async () => {
    const wrapper = await openTheDeal({ ...BRRRR_DEAL, deal_type: "FLIP", salePrice: 400 } as unknown as ActiveDealRes);
    await wrapper.find('[data-testid="mydeals.modal.view-report"]').trigger("click");
    await flushPromises();
    expect(pickerResultKeys()).toEqual(FLIP_REPORT_RESULT_TILES.map((tile) => tile.resultKey));
    pickerPart("generate").click();
    await flushPromises();
    expect(downloadDealPdf.mock.calls[0]![1]).toBe("FLIP");
  });
});
