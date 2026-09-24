// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import PrimeVue from "primevue/config";

import MyDeals from "./MyDeals.vue";
import api from "../api";
import type { ActiveDealRes } from "../types";

/**
 * A wrong input pauses the modal: no analyze request, no autosave, the tiles
 * replaced by a notice, the chip saying why. Fixing it resumes everything on
 * its own. Closing on a wrong input asks first and puts only that field back.
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
const duplicateActiveDeal = vi.mocked(api.duplicateActiveDeal);
const moveToBought = vi.mocked(api.moveToBought);

const DEAL: ActiveDealRes = {
  deal_type: "BRRRR",
  id: "deal-1",
  created_at: "2026-01-01T00:00:00.000Z",
  updated_at: "2026-01-01T00:00:00.000Z",
  address: "2286 Laurel Grove Ln W",
  section: 1,
  stage: 3,
  purchasePrice: 200,
  rehabCost: 50,
  arv_in_thousands: 320,
  lowestArv: 300,
  daysUntilRefi: 180,
  ltv_as_precent: 75,
  interestRate: 7,
  rent: 2600,
  cash_flow: 350,
} as ActiveDealRes;

async function openTheDeal() {
  const wrapper = mount(MyDeals, { global: { plugins: [[PrimeVue, { unstyled: true }]] } });
  await flushPromises();
  await wrapper.find('[data-testid="mydeals.card.deal-1"]').trigger("click");
  await flushPromises();
  expect(wrapper.find('[data-testid="mydeals.modal"]').exists()).toBe(true);
  // Opening the modal schedules its own debounced analyze; let it fire first.
  await vi.advanceTimersByTimeAsync(600);
  await flushPromises();
  analyzeDeal.mockClear();
  updateActiveDeal.mockClear();
  return wrapper;
}

type Board = Awaited<ReturnType<typeof openTheDeal>>;

/** Type a real-dollar amount into a money field of the modal's form and leave it. */
async function typeMoney(wrapper: Board, fieldKey: string, dollars: string) {
  const input = wrapper.find(`[data-testid="form.field.${fieldKey}"] [data-part="input"]`);
  await input.trigger("focus");
  await input.setValue(dollars);
  await input.trigger("blur");
}

/** Let the 500 ms analyze debounce and the 2 s autosave debounce both fire. */
async function letTheDebouncesFire() {
  await vi.advanceTimersByTimeAsync(3000);
  await flushPromises();
}

const lowestArvField = (wrapper: Board) => wrapper.find('[data-testid="form.field.lowestArv"]');
const saveState = (wrapper: Board) => wrapper.find('[data-testid="mydeals.modal.save-status"]').attributes("data-state");

describe("MyDeals — an invalid input pauses the modal", () => {
  let quiet: ReturnType<typeof vi.spyOn>[];

  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    quiet = (["group", "groupEnd", "log", "warn", "error"] as const).map((m) => vi.spyOn(console, m).mockImplementation(() => {}));
    getActiveDeals.mockResolvedValue([DEAL]);
    updateActiveDeal.mockImplementation(async (deal) => ({ ...deal, cash_flow: 420, cash_out_routi_conservative: 999 }));
    analyzeDeal.mockResolvedValue({ cash_flow: 420, cash_out: 12, cash_out_routi_conservative: 999 });
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-01T09:00:00.000Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
    for (const spy of quiet) spy.mockRestore();
  });

  it("marks the field, names the reason, replaces the tiles, and sends nothing", async () => {
    const wrapper = await openTheDeal();
    expect(wrapper.find('[data-testid="mydeals.modal.result.cash_flow"]').exists()).toBe(true);

    await typeMoney(wrapper, "lowestArv", "400000");
    await letTheDebouncesFire();

    expect(analyzeDeal).not.toHaveBeenCalled();
    expect(updateActiveDeal).not.toHaveBeenCalled();
    const input = lowestArvField(wrapper).find("input");
    expect(input.classes()).toContain("ui-input-invalid");
    expect(input.attributes("aria-invalid")).toBe("true");
    expect(lowestArvField(wrapper).find('[data-part="error-message"]').text()).toBe("Lowest ARV cannot exceed ARV.");
    expect(wrapper.find('[data-testid="form.tab.refinance.has-invalid-input"]').exists()).toBe(true);

    const paused = wrapper.find('[data-testid="mydeals.modal.results-paused"]');
    expect(paused.exists()).toBe(true);
    expect(paused.text()).toContain("Results paused until the highlighted inputs are fixed.");
    expect(wrapper.find('[data-testid="mydeals.modal.results-paused.lowestArv"]').text()).toContain("Lowest ARV cannot exceed ARV.");
    expect(wrapper.find('[data-testid="mydeals.modal.results-paused.lowestArv"]').text()).toContain("Refinance tab");
    expect(wrapper.find('[data-testid="mydeals.modal.result.cash_flow"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="mydeals.modal.results"]').exists()).toBe(true);

    expect(saveState(wrapper)).toBe("error");
    expect(wrapper.find('[data-testid="mydeals.modal.save-status"]').text()).toBe("Not saved — fix the highlighted inputs");
  });

  it("resumes the analysis and the autosave on its own once the value is fixed", async () => {
    const wrapper = await openTheDeal();
    await typeMoney(wrapper, "lowestArv", "400000");
    await letTheDebouncesFire();
    expect(updateActiveDeal).not.toHaveBeenCalled();

    await typeMoney(wrapper, "lowestArv", "300000");
    await letTheDebouncesFire();

    expect(analyzeDeal).toHaveBeenCalledTimes(1);
    expect(updateActiveDeal).toHaveBeenCalledTimes(1);
    expect(updateActiveDeal.mock.calls[0]![0]).toMatchObject({ lowestArv: 300 });
    expect(lowestArvField(wrapper).find('[data-part="error-message"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="mydeals.modal.results-paused"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="mydeals.modal.result.cash_out_routi_conservative"]').text()).toBe("$999");
    expect(saveState(wrapper)).toBe("saved");
  });

  it("keeps the earlier valid edits pending, and saves them with the fix", async () => {
    const wrapper = await openTheDeal();
    await wrapper.find('[data-testid="mydeals.modal.task"]').setValue("call the seller");
    await typeMoney(wrapper, "lowestArv", "400000");
    await letTheDebouncesFire();
    expect(updateActiveDeal).not.toHaveBeenCalled();

    await typeMoney(wrapper, "lowestArv", "290000");
    await letTheDebouncesFire();
    expect(updateActiveDeal).toHaveBeenCalledTimes(1);
    expect(updateActiveDeal.mock.calls[0]![0]).toMatchObject({ task: "call the seller", lowestArv: 290 });
  });

  describe("closing on an invalid input", () => {
    it("keeps the modal open on Cancel", async () => {
      const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
      const wrapper = await openTheDeal();
      await typeMoney(wrapper, "lowestArv", "400000");

      await wrapper.find('[data-testid="mydeals.modal.footer-close"]').trigger("click");
      await flushPromises();

      expect(confirmSpy).toHaveBeenCalledWith(
        "These inputs are invalid and were not saved:\n- Lowest ARV cannot exceed ARV. (Refinance tab)\n\nClose anyway? They go back to their last saved values; your other changes are saved.",
      );
      expect(wrapper.find('[data-testid="mydeals.modal"]').exists()).toBe(true);
      expect(updateActiveDeal).not.toHaveBeenCalled();
      confirmSpy.mockRestore();
    });

    it("on OK puts only that field back to its saved value and saves the rest", async () => {
      const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
      const wrapper = await openTheDeal();
      await wrapper.find('[data-testid="mydeals.modal.task"]').setValue("call the seller");
      await typeMoney(wrapper, "lowestArv", "400000");

      await wrapper.find('[data-testid="mydeals.modal.footer-close"]').trigger("click");
      await flushPromises();

      expect(wrapper.find('[data-testid="mydeals.modal"]').exists()).toBe(false);
      expect(updateActiveDeal).toHaveBeenCalledTimes(1);
      expect(updateActiveDeal.mock.calls[0]![0]).toMatchObject({ task: "call the seller", lowestArv: 300 });
      confirmSpy.mockRestore();
    });
  });

  it("refuses to move or duplicate the deal while an input is invalid", async () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const wrapper = await openTheDeal();
    await typeMoney(wrapper, "lowestArv", "400000");

    await wrapper.find('[data-testid="mydeals.modal.move-to-bought"]').trigger("click");
    await wrapper.find('[data-testid="mydeals.modal.duplicate"]').trigger("click");
    await flushPromises();

    expect(alertSpy).toHaveBeenCalledWith("Fix the highlighted inputs before moving this deal to Bought Deals.");
    expect(alertSpy).toHaveBeenCalledWith("Fix the highlighted inputs before duplicating this deal.");
    expect(moveToBought).not.toHaveBeenCalled();
    expect(duplicateActiveDeal).not.toHaveBeenCalled();
    expect(updateActiveDeal).not.toHaveBeenCalled();
    alertSpy.mockRestore();
    confirmSpy.mockRestore();
  });

  it("pauses the analysis, but not the save, while a required field is still blank", async () => {
    const wrapper = await openTheDeal();
    await typeMoney(wrapper, "rent", "");
    await letTheDebouncesFire();

    expect(analyzeDeal).not.toHaveBeenCalled();
    expect(updateActiveDeal).toHaveBeenCalledTimes(1);
    const paused = wrapper.find('[data-testid="mydeals.modal.results-paused"]');
    expect(paused.text()).toContain("Still needed:");
    expect(paused.text()).toContain("Rent must be greater than 0.");
    expect(wrapper.find('[data-testid="form.field.rent"] [data-part="error-message"]').exists()).toBe(false);
    expect(saveState(wrapper)).toBe("saved");
  });
});
