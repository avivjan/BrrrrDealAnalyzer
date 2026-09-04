// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";
import { mount } from "@vue/test-utils";

import DealCard from "./DealCard.vue";
import { formatDealForClipboard } from "../utils/dealUtils";
import type { ActiveDealRes, BrrrDealRes } from "../types";

/**
 * A saved BRRRR deal as `/active-deals` returns it. Only the fields the card
 * actually reads matter; the rest of the response shape is irrelevant here.
 */
function brrrDeal(overrides: Partial<BrrrDealRes> = {}): ActiveDealRes {
  return {
    deal_type: "BRRRR",
    id: "deal-1",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    address: "2286 Laurel Grove Ln W",
    section: 1,
    stage: 1,
    purchasePrice: 200,
    rehabCost: 50,
    cash_flow: 350,
    ...overrides,
  } as ActiveDealRes;
}

function mountCard(deal: ActiveDealRes = brrrDeal()) {
  return mount(DealCard, { props: { deal } });
}

/** The card inside a parent that also listens for clicks, as the board does. */
function mountInBoard(deal: ActiveDealRes, onParentClick: () => void) {
  const Board = defineComponent({
    setup: () => () =>
      h("div", { onClick: onParentClick }, [h(DealCard, { deal })]),
  });
  return mount(Board);
}

describe("DealCard", () => {
  // The card logs on every action; that noise is the component's, not the
  // suite's, so it is silenced per-test rather than globally.
  let log: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    log = vi.spyOn(console, "log").mockImplementation(() => {});
  });
  afterEach(() => {
    log.mockRestore();
    vi.useRealTimers();
  });

  describe("action buttons", () => {
    it("emits delete with the deal id", async () => {
      const wrapper = mountCard(brrrDeal({ id: "abc-123" }));
      await wrapper.find('[data-testid="dealcard.delete"]').trigger("click");
      expect(wrapper.emitted("delete")).toEqual([["abc-123"]]);
    });

    it("emits duplicate with the deal id", async () => {
      const wrapper = mountCard(brrrDeal({ id: "abc-123" }));
      await wrapper.find('[data-testid="dealcard.duplicate"]').trigger("click");
      expect(wrapper.emitted("duplicate")).toEqual([["abc-123"]]);
    });

    it("emits moveToBought with the deal id", async () => {
      const wrapper = mountCard(brrrDeal({ id: "abc-123", stage: 3 }));
      await wrapper
        .find('[data-testid="dealcard.move-to-bought"]')
        .trigger("click");
      expect(wrapper.emitted("moveToBought")).toEqual([["abc-123"]]);
    });

    it("offers Move to Bought only on the Brought stage", () => {
      for (const stage of [1, 2, 4, 5]) {
        const wrapper = mountCard(brrrDeal({ stage }));
        expect(
          wrapper.find('[data-testid="dealcard.move-to-bought"]').exists(),
          `stage ${stage} must not offer move-to-bought`,
        ).toBe(false);
      }
      expect(
        mountCard(brrrDeal({ stage: 3 }))
          .find('[data-testid="dealcard.move-to-bought"]')
          .exists(),
      ).toBe(true);
    });

    it.each([
      "dealcard.delete",
      "dealcard.duplicate",
      "dealcard.move-to-bought",
      "dealcard.copy",
    ])("keeps a %s click off the parent (which opens the deal)", async (id) => {
      const parentClick = vi.fn();
      const board = mountInBoard(brrrDeal({ stage: 3 }), parentClick);

      await board.find(`[data-testid="${id}"]`).trigger("click");

      expect(parentClick).not.toHaveBeenCalled();
    });

    it("still lets a click on the card body reach the parent", async () => {
      const parentClick = vi.fn();
      const board = mountInBoard(brrrDeal({ stage: 3 }), parentClick);

      await board.find("h3").trigger("click");

      expect(parentClick).toHaveBeenCalledTimes(1);
    });
  });

  describe("copy for AI", () => {
    it("writes the formatted summary to the clipboard", async () => {
      const writeText = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText },
        configurable: true,
      });
      const deal = brrrDeal();
      const wrapper = mountCard(deal);

      await wrapper.find('[data-testid="dealcard.copy"]').trigger("click");

      expect(writeText).toHaveBeenCalledWith(formatDealForClipboard(deal));
    });

    it("shows the copied state, then drops it after 2000 ms", async () => {
      vi.useFakeTimers();
      const writeText = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText },
        configurable: true,
      });
      const wrapper = mountCard();
      const button = () => wrapper.find('[data-testid="dealcard.copy"]');

      expect(button().attributes("title")).toBe("Copy Summary for AI");

      await button().trigger("click");
      // Flush the clipboard promise without moving the clock on.
      await vi.advanceTimersByTimeAsync(0);
      await wrapper.vm.$nextTick();
      expect(button().attributes("title")).toBe("Copied!");

      vi.advanceTimersByTime(1999);
      await wrapper.vm.$nextTick();
      expect(button().attributes("title")).toBe("Copied!");

      vi.advanceTimersByTime(1);
      await wrapper.vm.$nextTick();
      expect(button().attributes("title")).toBe("Copy Summary for AI");
    });

    it("survives a clipboard the browser refused", async () => {
      const error = vi.spyOn(console, "error").mockImplementation(() => {});
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
        configurable: true,
      });
      const wrapper = mountCard();

      await wrapper.find('[data-testid="dealcard.copy"]').trigger("click");
      await vi.waitFor(() => expect(error).toHaveBeenCalled());

      expect(wrapper.find('[data-testid="dealcard.copy"]').attributes("title")).toBe(
        "Copy Summary for AI",
      );
      error.mockRestore();
    });
  });

  describe("what the card shows", () => {
    it("labels a BRRRR and a FLIP deal differently", () => {
      expect(mountCard().text()).toContain("🏠 BRRRR");
      expect(
        mountCard({ ...brrrDeal(), deal_type: "FLIP" } as ActiveDealRes).text(),
      ).toContain("💰 FLIP");
    });

    it("falls back to 'No Address' for an unaddressed deal", () => {
      expect(mountCard(brrrDeal({ address: "" })).text()).toContain("No Address");
    });

    it("shows purchase and rehab in whole dollars", () => {
      const text = mountCard(brrrDeal({ purchasePrice: 200, rehabCost: 50 })).text();
      expect(text).toContain("$200,000");
      expect(text).toContain("$50,000");
    });
  });
});
