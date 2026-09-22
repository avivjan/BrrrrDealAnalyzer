// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import PrimeVue from "primevue/config";

import MyDeals from "./MyDeals.vue";
import api from "../api";
import type { ActiveDealRes, CalcStep } from "../types";

/**
 * The deal modal's result tiles open a "how is this calculated" popup.
 *
 * The popup renders the `breakdowns` section the backend attached to the deal
 * (or to the latest re-analyze), teleported above the modal; pressing a tile
 * never triggers an analyze or a save, Escape closes the popup alone, and the
 * tile's own value element is exactly what it was.
 */

const routerPush = vi.fn();
const routerReplace = vi.fn();

vi.mock("vue-router", () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: routerPush, replace: routerReplace }),
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

const CASH_FLOW_STEPS_FROM_THE_LIST: CalcStep[] = [
  {
    label: "Net Operating Income (NOI)",
    value: 2065,
    unit: "money",
    formula: "Rent ($2,600) − Operating Expenses ($535) = $2,065",
    terms: [
      { label: "Rent", value: 2600, sign: "+" },
      { label: "Operating Expenses", value: 535, sign: "-" },
    ],
  },
  {
    label: "Monthly Cash Flow",
    value: 350,
    unit: "money",
    formula: "NOI ($2,065) − Mortgage ($1,715) = $350",
    terms: [
      { label: "NOI", value: 2065, sign: "+", step_label: "Net Operating Income (NOI)" },
      { label: "Mortgage", value: 1715, sign: "-" },
    ],
  },
];

const DEAL: ActiveDealRes = {
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
  daysUntilRefi: 180,
  ltv_as_precent: 75,
  interestRate: 7,
  rent: 2600,
  cash_flow: 350,
  breakdowns: { cash_flow: CASH_FLOW_STEPS_FROM_THE_LIST },
} as ActiveDealRes;

/** The mounted board, unmounted after each test so no closed popup keeps a document listener or a teleport anchor alive. */
let mountedBoard: VueWrapper | null = null;

const popup = () => document.querySelector('[data-testid="calculation-breakdown-popup"]');
const popupText = () => popup()?.textContent?.replace(/\s+/g, " ").trim() ?? "";

async function openTheDeal(deal: ActiveDealRes = DEAL) {
  getActiveDeals.mockResolvedValue([deal]);
  const wrapper = mount(MyDeals, {
    global: { plugins: [[PrimeVue, { unstyled: true }]] },
  });
  mountedBoard = wrapper;
  await flushPromises();
  await wrapper.find('[data-testid="mydeals.card.deal-1"]').trigger("click");
  await flushPromises();
  expect(wrapper.find('[data-testid="mydeals.modal"]').exists()).toBe(true);
  // Opening the modal schedules its own debounced analyze; let it fire so the tests below measure only what a press causes.
  await vi.advanceTimersByTimeAsync(600);
  await flushPromises();
  analyzeDeal.mockClear();
  updateActiveDeal.mockClear();
  return wrapper;
}

const pressCashFlowTile = (wrapper: Awaited<ReturnType<typeof openTheDeal>>) =>
  wrapper.find('[data-testid="result-tile.cash_flow.show-calculation"]').trigger("click");

describe("MyDeals — result tiles open the calculation breakdown popup", () => {
  let quiet: ReturnType<typeof vi.spyOn>[];

  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    quiet = (["group", "groupEnd", "log", "warn"] as const).map((m) =>
      vi.spyOn(console, m).mockImplementation(() => {}),
    );
    updateActiveDeal.mockImplementation(async (deal) => deal);
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

  it("pressing a tile opens the popup with that result's steps and formulas, above the still-open modal", async () => {
    const wrapper = await openTheDeal();
    expect(popup()).toBeNull();

    await pressCashFlowTile(wrapper);
    await flushPromises();

    expect(popup()).not.toBeNull();
    expect(popup()!.getAttribute("data-metric-key")).toBe("cash_flow");
    expect(document.querySelector('[data-testid="calculation-breakdown-popup"] h2')!.textContent!.trim()).toBe(
      "How Cash Flow is calculated",
    );
    // The answer first: the headline's operands are the rows, and NOI, a computed one, is already open on its own operands.
    const rowLabels = [...document.querySelectorAll('[data-part="tree"] [data-part="row-label"]')].map((el) => el.textContent!.trim());
    expect(rowLabels).toEqual(["NOI", "Rent", "Operating Expenses", "Mortgage"]);
    expect(popupText()).toContain("$2,065");
    expect(document.querySelector('[data-part="headline-value"]')!.textContent!.trim()).toBe("$350");

    // The deal modal and the tile's own value element are untouched underneath.
    expect(wrapper.find('[data-testid="mydeals.modal"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="mydeals.modal.result.cash_flow"]').text()).toBe("$350");
  });

  it("every BRRRR result tile is pressable and opens its own section", async () => {
    const wrapper = await openTheDeal();
    const tileKeys = [
      "cash_flow", "cash_out", "cash_out_routi", "cash_on_cash", "dscr", "equity", "roi", "net_profit",
      "total_cash_needed_for_deal", "cash_to_close_buy", "cash_out_routi_conservative", "stolen_money",
    ];
    for (const key of tileKeys) {
      expect(wrapper.find(`[data-testid="result-tile.${key}.show-calculation"]`).exists(), key).toBe(true);
    }
    await wrapper.find('[data-testid="result-tile.equity.show-calculation"]').trigger("click");
    await flushPromises();
    expect(popup()!.getAttribute("data-metric-key")).toBe("equity");
    expect(popupText()).toContain("How Equity is calculated");
  });

  it("Escape closes only the popup; the deal modal stays open", async () => {
    const wrapper = await openTheDeal();
    await pressCashFlowTile(wrapper);
    await flushPromises();
    expect(popup()).not.toBeNull();

    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
    await flushPromises();

    expect(popup()).toBeNull();
    expect(wrapper.find('[data-testid="mydeals.modal"]').exists()).toBe(true);
  });

  it("pressing a tile triggers neither an analyze nor a save", async () => {
    const wrapper = await openTheDeal();
    await pressCashFlowTile(wrapper);
    await flushPromises();
    await vi.advanceTimersByTimeAsync(3000);
    expect(analyzeDeal).not.toHaveBeenCalled();
    expect(updateActiveDeal).not.toHaveBeenCalled();
  });

  it("a deal response without breakdowns opens the popup with the empty message", async () => {
    const { breakdowns: _omitted, ...dealWithoutBreakdowns } = DEAL;
    const wrapper = await openTheDeal(dealWithoutBreakdowns as ActiveDealRes);
    await pressCashFlowTile(wrapper);
    await flushPromises();
    expect(document.querySelector('[data-part="empty"]')!.textContent).toContain("No breakdown available");
  });

  it("after a re-analyze the open popup shows the fresh breakdown", async () => {
    const wrapper = await openTheDeal();
    await pressCashFlowTile(wrapper);
    await flushPromises();
    expect(popupText()).toContain("$2,065");

    analyzeDeal.mockResolvedValue({
      cash_flow: 420,
      breakdowns: {
        cash_flow: [
          { label: "Monthly Cash Flow", value: 420, unit: "money", formula: "NOI ($2,135) − Mortgage ($1,715) = $420" },
        ],
      },
    });
    // An edit, then the 500 ms debounced re-analyze.
    await wrapper.find('[data-testid="mydeals.modal.task"]').setValue("call the seller");
    await vi.advanceTimersByTimeAsync(500);
    await flushPromises();

    expect(analyzeDeal).toHaveBeenCalledTimes(1);
    expect(popupText()).toContain("NOI ($2,135) − Mortgage ($1,715) = $420");
    expect(popupText()).not.toContain("$2,065");
    expect(document.querySelector('[data-part="headline-value"]')!.textContent!.trim()).toBe("$420");
  });
});
