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

    it("still lets a click on the card itself reach the parent", async () => {
      // DealCard has no root/address `data-testid` today, so this anchors on
      // the component's own root element rather than a tag name: a click that
      // misses the four `@click.stop` buttons must open the deal.
      const parentClick = vi.fn();
      const board = mountInBoard(brrrDeal({ stage: 3 }), parentClick);

      await board.findComponent(DealCard).trigger("click");

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
      expect(mountCard().text()).toContain("BRRRR");
      expect(
        mountCard({ ...brrrDeal(), deal_type: "FLIP" } as ActiveDealRes).text(),
      ).toContain("FLIP");
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

  /**
   * The frozen `<script setup>` still hands `UiCard` the baseline's
   * `border-gray-100` inside `stageColors`, and G3 forbids editing it. The
   * template settles the question instead: Vue normalises `:class` before the
   * static `class`, so `border-line` reaches `cn()` *after* the legacy class
   * and tailwind-merge drops the loser. These assertions are what makes that
   * ordering a contract rather than an accident — reorder the two attributes on
   * the root and the card silently goes back to a hard-coded grey.
   */
  describe("the card border is on the token, not the baseline grey", () => {
    it.each([1, 2, 3, 4, 5])("resolves to border-line on stage %i", (stage) => {
      const root = mountCard(brrrDeal({ stage })).element as HTMLElement;
      const classes = (root.getAttribute("class") ?? "").split(/\s+/);
      expect(classes).toContain("border-line");
      expect(classes).not.toContain("border-gray-100");
    });

    it("keeps the stage accent off the class list, where the scoped CSS owns it", () => {
      const wrapper = mountCard(brrrDeal({ stage: 1 }));
      const root = wrapper.element as HTMLElement;
      const classes = (root.getAttribute("class") ?? "").split(/\s+/);
      // The accent is a top strip coloured by `[data-stage]` in the scoped
      // block, not a left border on the root's class list.
      expect(classes).not.toContain("border-l-4");
      expect(root.getAttribute("data-stage")).toBe("1");
      expect(wrapper.find('[data-part="stage-strip"]').exists()).toBe(true);
    });
  });

  describe("the verdict", () => {
    const ring = (wrapper: ReturnType<typeof mountCard>) =>
      wrapper.findComponent({ name: "UiProgressRing" });

    it("leads a BRRRR with cash-on-cash", () => {
      const hero = mountCard(brrrDeal({ cash_on_cash: 8.5 })).find('[data-part="hero"]');
      expect(hero.text()).toContain("8.5%");
      expect(hero.text()).toContain("Cash on cash");
    });

    it("leads a FLIP with net profit", () => {
      const hero = mountCard({
        ...brrrDeal(),
        deal_type: "FLIP",
        net_profit: 42000,
        roi: 10,
      } as ActiveDealRes).find('[data-part="hero"]');
      expect(hero.text()).toContain("$42,000");
      expect(hero.text()).toContain("Net profit");
      expect(hero.text()).not.toContain("Cash on cash");
    });

    it.each([
      [25, 1], // over the 10 % target: the ring is full, never past it
      [5, 0.5],
      [-3, 0], // a losing deal shows an empty ring, never a negative arc
      [undefined, 0],
    ])("fills the ring with CoC %s against a 10 %% target, clamped to 0–1", (coc, value) => {
      expect(ring(mountCard(brrrDeal({ cash_on_cash: coc }))).props("value")).toBe(value);
    });

    it("fills a FLIP's ring with ROI against a 20 % target", () => {
      const wrapper = mountCard({ ...brrrDeal(), deal_type: "FLIP", roi: 10 } as ActiveDealRes);
      expect(ring(wrapper).props("value")).toBe(0.5);
    });

    it.each([
      [12, "positive"],
      [6, "warning"],
      [2, "negative"],
    ])("tones the ring for CoC %s as %s", (coc, tone) => {
      expect(ring(mountCard(brrrDeal({ cash_on_cash: coc }))).props("tone")).toBe(tone);
    });

    it("draws the solid cash segment as needed ÷ with-buffer of the track", () => {
      const wrapper = mountCard(
        brrrDeal({
          total_cash_needed_for_deal: 63525,
          total_cash_needed_for_deal_with_buffer: 76638,
        }),
      );
      const solid = wrapper.find('[data-part="cash-needed"]').element as HTMLElement;
      expect(solid.style.width).toBe(`${(63525 / 76638) * 100}%`);
      const bar = wrapper.find('[data-part="cash-bar"]').text();
      expect(bar).toContain("$63,525 needed");
      expect(bar).toContain("w/ buffer $76,638");
    });

    it("shows the next action only when the deal has one", () => {
      expect(mountCard(brrrDeal({ task: "Call the lender" })).find('[data-part="task"]').text()).toContain(
        "Call the lender",
      );
      expect(mountCard(brrrDeal({ task: "" })).find('[data-part="task"]').exists()).toBe(false);
    });

    it("keeps the footer's sqft and bd/ba fallbacks", () => {
      const footer = mountCard(brrrDeal()).find('[data-part="footer"]').text();
      expect(footer).toContain("- sqft");
      expect(footer).toContain("-bd / -ba");
    });
  });
});
