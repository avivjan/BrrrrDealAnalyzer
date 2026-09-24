// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import PrimeVue from "primevue/config";

import BoughtDeals from "./BoughtDeals.vue";
import api from "../api";
import type { BoughtDealRes } from "../types";

/**
 * The bought-deal modal's result tiles open the same calculation breakdown
 * popup as My Deals: it shows the section the backend attached to the deal,
 * above the modal, and Escape closes the popup alone.
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
const analyzeDeal = vi.mocked(api.analyzeDeal);

const DEAL = {
  deal_type: "BRRRR",
  id: "bought-1",
  created_at: "2026-01-01T00:00:00.000Z",
  updated_at: "2026-01-01T00:00:00.000Z",
  address: "55 Willow Way",
  section: 2,
  stage: 3,
  boughtStage: "purchase",
  completedSubstages: {},
  purchasePrice: 200,
  rehabCost: 50,
  arv_in_thousands: 320,
  ltv_as_precent: 75,
  daysUntilRefi: 180,
  rent: 2600,
  cash_out_routi: 15400,
  breakdowns: {
    cash_out_routi: [
      {
        label: "Refi Loan Amount",
        value: 240000,
        unit: "money",
        formula: "ARV ($320,000) × LTV 75% = $240,000",
      },
      {
        label: "Cash-Out Wire (Refi)",
        value: 15400,
        unit: "money",
        formula: "Refi Loan ($240,000) − HML Payoff ($200,000) − Closing Costs (Refi) ($9,600) − Prepaid Interest (Refi) ($0) − Reserves ($15,000) = $15,400",
        terms: [
          { label: "Refi Loan", value: 240000, sign: "+", step_label: "Refi Loan Amount" },
          { label: "HML Payoff", value: 200000, sign: "-" },
          { label: "Closing Costs (Refi)", value: 9600, sign: "-" },
          { label: "Prepaid Interest (Refi)", value: 0, sign: "-" },
          { label: "Reserves", value: 15000, sign: "-" },
        ],
        note: "The cash received at the refi closing table, before subtracting what was invested.",
      },
    ],
  },
} as unknown as BoughtDealRes;

/** The mounted board, unmounted after each test so no closed popup keeps a document listener or a teleport anchor alive. */
let mountedBoard: VueWrapper | null = null;

const popup = () => document.querySelector('[data-testid="calculation-breakdown-popup"]');
const popupText = () => popup()?.textContent?.replace(/\s+/g, " ").trim() ?? "";

async function openTheDeal() {
  getBoughtDeals.mockResolvedValue([structuredClone(DEAL)]);
  const wrapper = mount(BoughtDeals, {
    global: { plugins: [[PrimeVue, { unstyled: true }]] },
  });
  mountedBoard = wrapper;
  await flushPromises();
  await wrapper.find('[data-testid="boughtdeals.card.bought-1"]').trigger("click");
  await flushPromises();
  expect(wrapper.find('[data-testid="boughtdeals.modal"]').exists()).toBe(true);
  // Opening the modal schedules its own debounced analyze; let it fire so the tests below measure only what a press causes.
  await vi.advanceTimersByTimeAsync(600);
  await flushPromises();
  analyzeDeal.mockClear();
  updateBoughtDeal.mockClear();
  return wrapper;
}

describe("BoughtDeals — result tiles open the calculation breakdown popup", () => {
  let quiet: ReturnType<typeof vi.spyOn>[];

  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    quiet = (["group", "groupEnd", "log", "warn", "error"] as const).map((m) =>
      vi.spyOn(console, m).mockImplementation(() => {}),
    );
    updateBoughtDeal.mockImplementation(async (deal) => ({ ...deal }));
    analyzeDeal.mockResolvedValue({ cash_flow: 350 });
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-01T09:00:00.000Z"));
  });

  afterEach(() => {
    mountedBoard?.unmount();
    mountedBoard = null;
    document.body.innerHTML = "";
    vi.useRealTimers();
    for (const spy of quiet) spy.mockRestore();
  });

  it("pressing the Cash-Out Routi tile opens the popup with the wire's stacked terms and note", async () => {
    const wrapper = await openTheDeal();
    await wrapper.find('[data-testid="result-tile.cash_out_routi.show-calculation"]').trigger("click");
    await flushPromises();

    expect(popup()).not.toBeNull();
    expect(popupText()).toContain("How Cash-Out Routi is calculated");
    expect(popupText()).toContain("ARV ($320,000) × LTV 75% = $240,000");
    const rowLabels = [...document.querySelectorAll('[data-part="tree"] [data-part="row-label"]')].map((el) => el.textContent!.trim());
    expect(rowLabels).toEqual(["Refi Loan", "HML Payoff", "Closing Costs (Refi)", "Prepaid Interest (Refi)", "Reserves"]);
    // Refi Loan is a computed operand, so it is open on its formula by default.
    expect(document.querySelector('[data-part="row-formula"]')!.textContent).toContain("ARV ($320,000) × LTV 75% = $240,000");
    expect(document.querySelector('[data-part="headline-note"]')!.textContent).toContain("refi closing table");
    expect(document.querySelector('[data-part="headline-value"]')!.textContent!.trim()).toBe("$15,400");

    expect(wrapper.find('[data-testid="boughtdeals.modal"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="boughtdeals.modal.result.cash_out_routi"]').text()).toBe("$15,400");
    await vi.advanceTimersByTimeAsync(3000);
    expect(analyzeDeal).not.toHaveBeenCalled();
    expect(updateBoughtDeal).not.toHaveBeenCalled();
  });

  it("Escape closes only the popup; the bought-deal modal stays open", async () => {
    const wrapper = await openTheDeal();
    await wrapper.find('[data-testid="result-tile.cash_out_routi.show-calculation"]').trigger("click");
    await flushPromises();
    expect(popup()).not.toBeNull();

    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
    await flushPromises();

    expect(popup()).toBeNull();
    expect(wrapper.find('[data-testid="boughtdeals.modal"]').exists()).toBe(true);
  });
});
