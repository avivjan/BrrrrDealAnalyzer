// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { mount } from "@vue/test-utils";

import RepsTimer from "./RepsTimer.vue";
import { useRepsStore } from "../../stores/repsStore";
import type { RepsUser } from "../../types/reps";

vi.mock("../../api", () => ({
  default: {
    getRepsConfigStatus: vi.fn().mockResolvedValue({}),
    getRepsEntries: vi.fn().mockResolvedValue({ entries: [] }),
    getRepsProperties: vi.fn().mockResolvedValue([]),
    getRepsPeople: vi.fn().mockResolvedValue([]),
    getRepsActivityCategories: vi.fn().mockResolvedValue([]),
  },
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const USER: RepsUser = "Aviv2026";

const mountTimer = (user: RepsUser = USER) =>
  mount(RepsTimer, { props: { user } });

describe("RepsTimer", () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  describe("which controls are offered", () => {
    it("offers only Start before a session exists", () => {
      const wrapper = mountTimer();
      expect(wrapper.find('[data-testid="repstimer.start"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="repstimer.stop"]').exists()).toBe(false);
      expect(wrapper.find('[data-testid="repstimer.finish"]').exists()).toBe(false);
      expect(wrapper.find('[data-testid="repstimer.pin-gps"]').exists()).toBe(false);
    });

    it("swaps Start for Stop once the clock is running", async () => {
      const wrapper = mountTimer();
      await wrapper.find('[data-testid="repstimer.start"]').trigger("click");

      expect(wrapper.find('[data-testid="repstimer.start"]').exists()).toBe(false);
      expect(wrapper.find('[data-testid="repstimer.stop"]').exists()).toBe(true);
      expect(wrapper.text()).toContain("running");
    });

    it("offers Resume, Finish and Discard once paused", async () => {
      const wrapper = mountTimer();
      await wrapper.find('[data-testid="repstimer.start"]').trigger("click");
      await wrapper.find('[data-testid="repstimer.stop"]').trigger("click");

      expect(wrapper.find('[data-testid="repstimer.resume"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="repstimer.finish"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="repstimer.discard"]').exists()).toBe(true);
      expect(wrapper.text()).toContain("paused");
    });
  });

  it("starts the store's clock for its own user", async () => {
    const store = useRepsStore();
    const startTimer = vi.spyOn(store, "startTimer");
    const wrapper = mountTimer("Yarden2026");

    await wrapper.find('[data-testid="repstimer.start"]').trigger("click");

    expect(startTimer).toHaveBeenCalledWith("Yarden2026");
    expect(store.timers.Yarden2026.running).toBe(true);
    expect(store.timers.Aviv2026.running).toBe(false);
  });

  it("stops the store's clock without ending the session", async () => {
    const store = useRepsStore();
    const wrapper = mountTimer();
    await wrapper.find('[data-testid="repstimer.start"]').trigger("click");

    await wrapper.find('[data-testid="repstimer.stop"]').trigger("click");

    expect(store.timers[USER].running).toBe(false);
    expect(store.timers[USER].sessionStartedAt).not.toBeNull();
  });

  describe("the elapsed readout", () => {
    it("starts at zero", () => {
      const wrapper = mountTimer();
      expect(wrapper.text()).toContain("00:00:00");
      expect(wrapper.text()).toContain("= 0.00 h");
    });

    it("ticks once a second while running", async () => {
      vi.useFakeTimers();
      const wrapper = mountTimer();
      await wrapper.find('[data-testid="repstimer.start"]').trigger("click");

      await vi.advanceTimersByTimeAsync(90_000);

      expect(wrapper.text()).toContain("00:01:30");
      expect(wrapper.text()).toContain("= 0.03 h");
    });
  });

  describe("finishing", () => {
    /** Jump the clock without firing 5,400 one-second ticks. */
    const jumpMinutes = (from: string, minutes: number) =>
      vi.setSystemTime(new Date(new Date(from).getTime() + minutes * 60_000));

    it("emits the session bounds and the accumulated hours", async () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date("2026-05-01T09:00:00.000Z"));
      const wrapper = mountTimer();

      await wrapper.find('[data-testid="repstimer.start"]').trigger("click");
      jumpMinutes("2026-05-01T09:00:00.000Z", 90); // an hour and a half
      await wrapper.find('[data-testid="repstimer.stop"]').trigger("click");
      await wrapper.find('[data-testid="repstimer.finish"]').trigger("click");

      expect(wrapper.emitted("finish")).toEqual([
        [
          {
            startIso: "2026-05-01T09:00:00.000Z",
            endIso: "2026-05-01T10:30:00.000Z",
            totalHours: 1.5,
          },
        ],
      ]);
    });

    it("stops a clock that resumed under it, so no time is lost", async () => {
      // Finish is only rendered while paused, so the running branch inside
      // `finish()` is reachable only if the clock restarts between render and
      // click. Held here by grabbing the button first and resuming without
      // letting Vue re-render.
      vi.useFakeTimers();
      vi.setSystemTime(new Date("2026-05-01T09:00:00.000Z"));
      const store = useRepsStore();
      const wrapper = mountTimer();

      await wrapper.find('[data-testid="repstimer.start"]').trigger("click");
      jumpMinutes("2026-05-01T09:00:00.000Z", 30);
      await wrapper.find('[data-testid="repstimer.stop"]').trigger("click");

      const finish = wrapper.find('[data-testid="repstimer.finish"]');
      store.resumeTimer(USER);
      jumpMinutes("2026-05-01T09:00:00.000Z", 60);
      await finish.trigger("click");

      expect(store.timers[USER].running).toBe(false);
      // 30 minutes before the pause + 30 minutes after the resume.
      expect(wrapper.emitted("finish")![0]![0]).toMatchObject({ totalHours: 1 });
    });

    it("emits nothing when there is no session to finish", async () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date("2026-05-01T09:00:00.000Z"));
      const store = useRepsStore();
      const wrapper = mountTimer();
      await wrapper.find('[data-testid="repstimer.start"]').trigger("click");
      await wrapper.find('[data-testid="repstimer.stop"]').trigger("click");
      // A reset between rendering the button and clicking it.
      store.resetTimer(USER);

      await wrapper.find('[data-testid="repstimer.finish"]').trigger("click");

      expect(wrapper.emitted("finish")).toBeUndefined();
    });
  });

  describe("discarding", () => {
    const COPY =
      "Discard this stopwatch session? Timer, GPS breadcrumbs, and queued evidence will reset.";

    async function pausedTimer() {
      const wrapper = mountTimer();
      await wrapper.find('[data-testid="repstimer.start"]').trigger("click");
      await wrapper.find('[data-testid="repstimer.stop"]').trigger("click");
      return wrapper;
    }

    it("asks first and keeps the session on cancel", async () => {
      const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
      const store = useRepsStore();
      const reset = vi.spyOn(store, "resetTimer");
      const wrapper = await pausedTimer();

      await wrapper.find('[data-testid="repstimer.discard"]').trigger("click");

      expect(confirmSpy).toHaveBeenCalledWith(COPY);
      expect(reset).not.toHaveBeenCalled();
      expect(store.timers[USER].sessionStartedAt).not.toBeNull();
      confirmSpy.mockRestore();
    });

    it("resets the store's timer on accept", async () => {
      const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
      const store = useRepsStore();
      const reset = vi.spyOn(store, "resetTimer");
      const wrapper = await pausedTimer();

      await wrapper.find('[data-testid="repstimer.discard"]').trigger("click");

      expect(reset).toHaveBeenCalledWith(USER);
      expect(store.timers[USER].sessionStartedAt).toBeNull();
      expect(wrapper.find('[data-testid="repstimer.start"]').exists()).toBe(true);
      confirmSpy.mockRestore();
    });
  });

  it("stops ticking once unmounted", async () => {
    vi.useFakeTimers();
    const wrapper = mountTimer();
    expect(vi.getTimerCount()).toBe(1);

    wrapper.unmount();

    expect(vi.getTimerCount()).toBe(0);
  });

  describe("queued evidence", () => {
    it("counts the files staged for this session", async () => {
      const store = useRepsStore();
      const wrapper = mountTimer();
      await wrapper.find('[data-testid="repstimer.start"]').trigger("click");

      store.addInFlightFile(USER, new File(["x"], "photo.jpg"));
      await wrapper.vm.$nextTick();
      expect(wrapper.text()).toContain("1 file queued");

      store.addInFlightFile(USER, new File(["y"], "deed.pdf"));
      await wrapper.vm.$nextTick();
      expect(wrapper.text()).toContain("2 files queued");
    });

    it("counts the GPS pins captured for this session", async () => {
      const store = useRepsStore();
      const wrapper = mountTimer();
      await wrapper.find('[data-testid="repstimer.start"]').trigger("click");

      store.pushSnapshot(USER, {
        kind: "bookmark",
        captured_at: "2026-05-01T09:10:00.000Z",
      });
      await wrapper.vm.$nextTick();

      expect(wrapper.text()).toContain("1 GPS pin");
    });
  });
});
