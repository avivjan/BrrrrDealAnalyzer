// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import PrimeVue from "primevue/config";

import MyDeals from "./MyDeals.vue";
import api from "../api";
import type { ActiveDealRes } from "../types";

/**
 * Characterizes MyDeals' modal autosave: the 250 ms settle window that swallows
 * the churn of the inputs mounting, the 500 ms debounced re-analyze, the
 * 2000 ms debounced save, and the flush on close.
 *
 * `vi.useFakeTimers()` fakes `Date` as well as the timers, which is what makes
 * the settle window (a `Date.now()` comparison) observable at all.
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
} as ActiveDealRes;

/** Mount the board and open the one deal's modal. */
async function openTheDeal() {
  const wrapper = mount(MyDeals, {
    global: { plugins: [[PrimeVue, { unstyled: true }]] },
  });
  await flushPromises();

  await wrapper.find('[data-testid="mydeals.card.deal-1"]').trigger("click");
  await flushPromises();
  expect(wrapper.find('[data-testid="mydeals.modal"]').exists()).toBe(true);

  // The modal's own mount churn settles inside the window; clear the counters
  // so each test measures only what its own edit caused.
  analyzeDeal.mockClear();
  updateActiveDeal.mockClear();
  return wrapper;
}

/** A user edit: type into the modal's task box. */
async function editTask(
  wrapper: Awaited<ReturnType<typeof openTheDeal>>,
  text: string,
) {
  await wrapper.find('[data-testid="mydeals.modal.task"]').setValue(text);
}

const saveState = (wrapper: Awaited<ReturnType<typeof openTheDeal>>) =>
  wrapper.find('[data-testid="mydeals.modal.save-status"]').attributes("data-state");

describe("MyDeals — modal autosave", () => {
  let quiet: ReturnType<typeof vi.spyOn>[];

  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    // The view narrates itself through console.group/log on every action.
    quiet = (["group", "groupEnd", "log", "warn"] as const).map((m) =>
      vi.spyOn(console, m).mockImplementation(() => {}),
    );

    getActiveDeals.mockResolvedValue([DEAL]);
    updateActiveDeal.mockImplementation(async (deal) => deal);
    analyzeDeal.mockResolvedValue({ cash_flow: 420, cash_out: 12 });

    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-01T09:00:00.000Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
    for (const spy of quiet) spy.mockRestore();
  });

  it("renders the board with the fetched deal", async () => {
    const wrapper = mount(MyDeals, {
      global: { plugins: [[PrimeVue, { unstyled: true }]] },
    });
    await flushPromises();

    expect(getActiveDeals).toHaveBeenCalledTimes(1);
    expect(wrapper.find('[data-testid="mydeals.card.deal-1"]').exists()).toBe(true);
    expect(wrapper.text()).toContain("2286 Laurel Grove Ln W");
  });

  it("seeds the modal from a deep clone, leaving the board's deal untouched", async () => {
    const wrapper = await openTheDeal();

    await editTask(wrapper, "Call the lender");
    await vi.advanceTimersByTimeAsync(3000);

    // The card behind the modal still shows the original task.
    expect(wrapper.find('[data-testid="mydeals.card.deal-1"]').text()).not.toContain(
      "Call the lender",
    );
  });

  describe("the 250 ms settle window", () => {
    it("does not schedule a save for an edit made inside it", async () => {
      const wrapper = await openTheDeal();

      // Still inside the window opened by `openDeal`.
      await vi.advanceTimersByTimeAsync(100);
      await editTask(wrapper, "typed while the inputs were still mounting");

      await vi.advanceTimersByTimeAsync(5000);

      expect(updateActiveDeal).not.toHaveBeenCalled();
      expect(saveState(wrapper)).toBe("idle");
    });

    it("still re-analyzes for that same edit", async () => {
      const wrapper = await openTheDeal();

      await vi.advanceTimersByTimeAsync(100);
      await editTask(wrapper, "typed inside the window");
      await vi.advanceTimersByTimeAsync(500);

      expect(analyzeDeal).toHaveBeenCalledTimes(1);
    });

    it("schedules a save for an edit made after it closes", async () => {
      const wrapper = await openTheDeal();

      await vi.advanceTimersByTimeAsync(300);
      await editTask(wrapper, "typed after the modal settled");
      await vi.advanceTimersByTimeAsync(2000);

      expect(updateActiveDeal).toHaveBeenCalledTimes(1);
      expect(updateActiveDeal.mock.calls[0]![0]).toMatchObject({
        id: "deal-1",
        task: "typed after the modal settled",
      });
    });
  });

  describe("the debounces", () => {
    it("re-analyzes 500 ms after an edit, and only once", async () => {
      const wrapper = await openTheDeal();
      await vi.advanceTimersByTimeAsync(300);

      await editTask(wrapper, "one");
      await vi.advanceTimersByTimeAsync(499);
      expect(analyzeDeal).not.toHaveBeenCalled();

      await vi.advanceTimersByTimeAsync(1);
      expect(analyzeDeal).toHaveBeenCalledTimes(1);
      expect(analyzeDeal.mock.calls[0]![1]).toBe("BRRRR");
    });

    it("saves 2000 ms after an edit, and only once", async () => {
      const wrapper = await openTheDeal();
      await vi.advanceTimersByTimeAsync(300);

      await editTask(wrapper, "one");
      await vi.advanceTimersByTimeAsync(1999);
      expect(updateActiveDeal).not.toHaveBeenCalled();

      await vi.advanceTimersByTimeAsync(1);
      expect(updateActiveDeal).toHaveBeenCalledTimes(1);
    });

    it("coalesces a burst of keystrokes into one save", async () => {
      const wrapper = await openTheDeal();
      await vi.advanceTimersByTimeAsync(300);

      for (const text of ["C", "Ca", "Cal", "Call"]) {
        await editTask(wrapper, text);
        await vi.advanceTimersByTimeAsync(100);
      }
      await vi.advanceTimersByTimeAsync(2000);

      expect(updateActiveDeal).toHaveBeenCalledTimes(1);
      expect(updateActiveDeal.mock.calls[0]![0]).toMatchObject({ task: "Call" });
    });

    it("shows Saving then Saved, and drops back to idle after 2000 ms", async () => {
      const wrapper = await openTheDeal();
      await vi.advanceTimersByTimeAsync(300);
      await editTask(wrapper, "status check");

      await vi.advanceTimersByTimeAsync(2000);
      expect(saveState(wrapper)).toBe("saved");

      await vi.advanceTimersByTimeAsync(2000);
      expect(saveState(wrapper)).toBe("idle");
    });

    it("reports an error and keeps the edit pending when the save fails", async () => {
      const error = vi.spyOn(console, "error").mockImplementation(() => {});
      updateActiveDeal.mockRejectedValue(new Error("500"));
      const wrapper = await openTheDeal();
      await vi.advanceTimersByTimeAsync(300);

      await editTask(wrapper, "will fail");
      await vi.advanceTimersByTimeAsync(2000);

      expect(saveState(wrapper)).toBe("error");
      error.mockRestore();
    });
  });

  describe("closing the modal", () => {
    it("flushes a save that has not fired yet", async () => {
      const wrapper = await openTheDeal();
      await vi.advanceTimersByTimeAsync(300);
      await editTask(wrapper, "unsaved when closed");

      // Well short of the 2000 ms debounce.
      await vi.advanceTimersByTimeAsync(100);
      expect(updateActiveDeal).not.toHaveBeenCalled();

      await wrapper.find('[data-testid="mydeals.modal.close"]').trigger("click");
      await flushPromises();

      expect(updateActiveDeal).toHaveBeenCalledTimes(1);
      expect(updateActiveDeal.mock.calls[0]![0]).toMatchObject({
        task: "unsaved when closed",
      });
      expect(wrapper.find('[data-testid="mydeals.modal"]').exists()).toBe(false);
    });

    it("saves nothing when nothing was edited", async () => {
      const wrapper = await openTheDeal();
      await vi.advanceTimersByTimeAsync(300);

      await wrapper.find('[data-testid="mydeals.modal.close"]').trigger("click");
      await flushPromises();

      expect(updateActiveDeal).not.toHaveBeenCalled();
      expect(wrapper.find('[data-testid="mydeals.modal"]').exists()).toBe(false);
    });

    it("does not double-save when the debounce had already fired", async () => {
      const wrapper = await openTheDeal();
      await vi.advanceTimersByTimeAsync(300);
      await editTask(wrapper, "already saved");
      await vi.advanceTimersByTimeAsync(2000);
      expect(updateActiveDeal).toHaveBeenCalledTimes(1);

      await wrapper.find('[data-testid="mydeals.modal.close"]').trigger("click");
      await flushPromises();

      expect(updateActiveDeal).toHaveBeenCalledTimes(1);
    });
  });

  it("merges the analysis result into the displayed figures", async () => {
    const wrapper = await openTheDeal();
    await vi.advanceTimersByTimeAsync(300);

    await editTask(wrapper, "re-analyze me");
    await vi.advanceTimersByTimeAsync(500);
    await flushPromises();

    expect(
      wrapper.find('[data-testid="mydeals.modal.result.cash_flow"]').text(),
    ).toBe("$420");
  });
});
