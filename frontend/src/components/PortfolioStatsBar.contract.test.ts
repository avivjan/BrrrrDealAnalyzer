// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { mount } from "@vue/test-utils";

import PortfolioStatsBar from "./PortfolioStatsBar.vue";
import { useDealStore } from "../stores/dealStore";
import type { ActiveDealRes } from "../types";

vi.mock("../api", () => ({
  default: { getActiveDeals: vi.fn().mockResolvedValue([]) },
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

function deal(over: Partial<ActiveDealRes> = {}): ActiveDealRes {
  return {
    deal_type: "BRRRR",
    id: "d1",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    address: "1 Main St",
    section: 1,
    stage: 3,
    arv_in_thousands: 320,
    ltv_as_precent: 75,
    ...over,
  } as ActiveDealRes;
}

/**
 * Mount with the store already seeded and let the mount tick settle:
 * `onMounted` assigns the current stats straight onto the animated values, so
 * the first painted figure is the real one rather than a tween from zero.
 */
/**
 * The doors figure, read out of the tile that labels it — the bar's text is
 * full of other digits, so a substring match would not pin anything.
 */
const doorsShown = (wrapper: { text(): string }) =>
  wrapper.text().match(/Doors\s*(\d+)/)?.[1];

async function mountBar(deals: ActiveDealRes[]) {
  const store = useDealStore();
  store.deals = deals;
  const wrapper = mount(PortfolioStatsBar);
  await wrapper.vm.$nextTick();
  return { wrapper, store };
}

describe("PortfolioStatsBar", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  describe("when it appears at all", () => {
    it("stays hidden with no deals", async () => {
      const { wrapper } = await mountBar([]);
      expect(wrapper.find('[data-testid="statsbar.root"]').exists()).toBe(false);
    });

    it("stays hidden when no BRRRR deal has reached the Brought stage", async () => {
      const { wrapper } = await mountBar([
        deal({ stage: 1 }),
        deal({ id: "d2", stage: 2 }),
      ]);
      expect(wrapper.find('[data-testid="statsbar.root"]').exists()).toBe(false);
    });

    it("stays hidden for a bought FLIP — the bar counts doors, not deals", async () => {
      const { wrapper } = await mountBar([
        deal({ deal_type: "FLIP", stage: 3 } as Partial<ActiveDealRes>),
      ]);
      expect(wrapper.find('[data-testid="statsbar.root"]').exists()).toBe(false);
    });

    it("appears once a BRRRR deal reaches the Brought stage", async () => {
      const { wrapper } = await mountBar([deal()]);
      expect(wrapper.find('[data-testid="statsbar.root"]').exists()).toBe(true);
    });

    it("appears when a deal moves to Brought after mount", async () => {
      const { wrapper, store } = await mountBar([deal({ stage: 1 })]);
      expect(wrapper.find('[data-testid="statsbar.root"]').exists()).toBe(false);

      store.deals = [deal({ stage: 3 })];
      await wrapper.vm.$nextTick();

      expect(wrapper.find('[data-testid="statsbar.root"]').exists()).toBe(true);
    });
  });

  describe("the numbers it shows on mount", () => {
    /**
     * The counters tween on change, but `onMounted` snaps them to the current
     * stats — so the very first paint is the real figure, never a run-up
     * from zero.
     */
    it("shows the door count without tweening from zero", async () => {
      const { wrapper } = await mountBar([deal(), deal({ id: "d2" })]);
      expect(wrapper.text()).toContain("Doors");
      expect(doorsShown(wrapper)).toBe("2");
    });

    it("shows value, debt and equity straight away", async () => {
      // One deal: ARV 320k at 75% LTV -> $320K value, $240K debt, $80K equity.
      const { wrapper } = await mountBar([deal()]);
      const text = wrapper.text();

      expect(text).toContain("$320K");
      expect(text).toContain("$240K");
      expect(text).toContain("$80.0K");
    });

    it("snaps rather than tweening: no animation frame is scheduled on mount", async () => {
      const raf = vi.spyOn(globalThis, "requestAnimationFrame");
      const { wrapper } = await mountBar([deal()]);

      expect(raf).not.toHaveBeenCalled();
      expect(wrapper.text()).toContain("$320K");
      raf.mockRestore();
    });

    it("does tween once the numbers change under it", async () => {
      const { wrapper, store } = await mountBar([deal()]);
      // Swallow the frame so the tween cannot chain on into later tests; the
      // spy still records that one was requested, which is the whole point.
      const raf = vi
        .spyOn(globalThis, "requestAnimationFrame")
        .mockImplementation(() => 0);

      store.deals = [deal(), deal({ id: "d2" })];
      await wrapper.vm.$nextTick();

      expect(raf).toHaveBeenCalled();
      raf.mockRestore();
      wrapper.unmount();
    });

    it("sums across every Brought BRRRR deal", async () => {
      const { wrapper } = await mountBar([
        deal({ arv_in_thousands: 320, ltv_as_precent: 75 }),
        deal({ id: "d2", arv_in_thousands: 680, ltv_as_precent: 75 }),
      ]);
      // 1,000k total value at 75% LTV.
      expect(wrapper.text()).toContain("$1.00M");
      expect(wrapper.text()).toContain("$750K");
      expect(wrapper.text()).toContain("$250K");
    });
  });

  describe("its own money formatter", () => {
    const shown = async (arv: number, ltv = 0) =>
      (await mountBar([deal({ arv_in_thousands: arv, ltv_as_precent: ltv })])).wrapper.text();

    it("writes millions with two decimals below ten million", async () => {
      expect(await shown(2_500)).toContain("$2.50M");
    });

    it("drops to one decimal at ten million and up", async () => {
      expect(await shown(12_000)).toContain("$12.0M");
    });

    it("writes thousands with one decimal below a hundred thousand", async () => {
      expect(await shown(45.5)).toContain("$45.5K");
    });

    it("drops the decimal at a hundred thousand and up", async () => {
      expect(await shown(320)).toContain("$320K");
    });

    it("writes sub-thousand amounts in whole dollars", async () => {
      // ARV 0.5k -> $500.
      expect(await shown(0.5)).toContain("$500");
    });
  });

  it("reads a deal whose numbers arrived from the API as strings", async () => {
    const { wrapper } = await mountBar([
      deal({
        arv_in_thousands: "320.00",
        ltv_as_precent: "75.00",
        stage: "3",
      } as unknown as Partial<ActiveDealRes>),
    ]);

    expect(wrapper.find('[data-testid="statsbar.root"]').exists()).toBe(true);
    expect(wrapper.text()).toContain("$320K");
  });
});
