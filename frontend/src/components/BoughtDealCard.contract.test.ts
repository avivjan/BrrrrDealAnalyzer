// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { defineComponent, h } from "vue";
import { mount } from "@vue/test-utils";

import BoughtDealCard from "./BoughtDealCard.vue";
import { useBoughtDealStore } from "../stores/boughtDealStore";
import { brrrPipeline } from "../config/boughtDealStages";
import type { BoughtDealRes } from "../types";

vi.mock("../api", () => ({
  default: {
    getBoughtDeals: vi.fn().mockResolvedValue([]),
    updateBoughtDeal: vi.fn().mockResolvedValue({}),
    deleteBoughtDeal: vi.fn().mockResolvedValue(undefined),
    getPipelineTemplates: vi.fn().mockResolvedValue([]),
  },
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

/** The BRRRR "Purchase" stage, which has two substages in the default template. */
const PURCHASE_SUBSTAGES = brrrPipeline.stages[0]!.subStages;

function boughtDeal(overrides: Partial<BoughtDealRes> = {}): BoughtDealRes {
  return {
    deal_type: "BRRRR",
    id: "bought-1",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    address: "2286 Laurel Grove Ln W",
    section: 1,
    stage: 3,
    boughtStage: "purchase",
    completedSubstages: {},
    purchasePrice: 200,
    rehabCost: 50,
    ...overrides,
  } as BoughtDealRes;
}

function mountCard(deal: BoughtDealRes = boughtDeal()) {
  return mount(BoughtDealCard, { props: { deal } });
}

describe("BoughtDealCard", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("emits delete with the deal id", async () => {
    const wrapper = mountCard(boughtDeal({ id: "xyz-9" }));
    await wrapper.find('[data-testid="boughtcard.delete"]').trigger("click");
    expect(wrapper.emitted("delete")).toEqual([["xyz-9"]]);
  });

  describe("the substage checklist", () => {
    it("renders one checkbox per substage of the deal's stage", () => {
      const wrapper = mountCard();
      for (const sub of PURCHASE_SUBSTAGES) {
        expect(
          wrapper.find(`[data-testid="boughtcard.substage.${sub.id}.input"]`).exists(),
          `missing checkbox for ${sub.id}`,
        ).toBe(true);
        expect(wrapper.text()).toContain(sub.label);
      }
    });

    it("shows no checklist for a stage that has no substages", () => {
      // "rehab" is a bare stage in the default BRRRR template.
      const wrapper = mountCard(boughtDeal({ boughtStage: "rehab" }));
      expect(wrapper.find('input[type="checkbox"]').exists()).toBe(false);
    });

    it("reflects which substages are already complete", () => {
      const [first, second] = PURCHASE_SUBSTAGES;
      const wrapper = mountCard(
        boughtDeal({ completedSubstages: { [first!.id]: true } }),
      );
      const box = (id: string) =>
        wrapper.find<HTMLInputElement>(
          `[data-testid="boughtcard.substage.${id}.input"]`,
        ).element;

      expect(box(first!.id).checked).toBe(true);
      expect(box(second!.id).checked).toBe(false);
    });

    it("asks the store to toggle the clicked substage", async () => {
      const store = useBoughtDealStore();
      const toggle = vi
        .spyOn(store, "toggleSubstage")
        .mockResolvedValue(undefined);
      const sub = PURCHASE_SUBSTAGES[1]!;
      const wrapper = mountCard(boughtDeal({ id: "bought-7" }));

      await wrapper
        .find(`[data-testid="boughtcard.substage.${sub.id}.input"]`)
        .trigger("click");

      expect(toggle).toHaveBeenCalledWith("bought-7", sub.id);
    });

    it("keeps a checkbox click off the parent (which opens the deal)", async () => {
      const store = useBoughtDealStore();
      vi.spyOn(store, "toggleSubstage").mockResolvedValue(undefined);
      const parentClick = vi.fn();
      const deal = boughtDeal();
      const Board = defineComponent({
        setup: () => () =>
          h("div", { onClick: parentClick }, [h(BoughtDealCard, { deal })]),
      });
      const board = mount(Board);

      await board
        .find(`[data-testid="boughtcard.substage.${PURCHASE_SUBSTAGES[0]!.id}.input"]`)
        .trigger("click");
      expect(parentClick).not.toHaveBeenCalled();

      await board.find('[data-testid="boughtcard.delete"]').trigger("click");
      expect(parentClick).not.toHaveBeenCalled();
    });
  });

  describe("progress", () => {
    /**
     * The bar tracks position in the pipeline, not the substage checklist:
     * stage index / (stage count - 1).
     */
    const bar = (wrapper: ReturnType<typeof mountCard>) => {
      const filled = wrapper
        .findAll("div")
        .filter((el) => (el.attributes("style") ?? "").includes("width:"));
      expect(filled, "no progress bar fill found").toHaveLength(1);
      return filled[0]!.attributes("style")!;
    };

    it("is empty on the first stage and full on the last", () => {
      expect(bar(mountCard(boughtDeal({ boughtStage: "purchase" })))).toContain(
        "width: 0%",
      );
      expect(bar(mountCard(boughtDeal({ boughtStage: "refinanced" })))).toContain(
        "width: 100%",
      );
    });

    it("is part-way through in the middle of the pipeline", () => {
      // "closed" is index 2 of 7 BRRRR stages -> 2/6 -> 33.33…%.
      expect(bar(mountCard(boughtDeal({ boughtStage: "closed" })))).toContain(
        "width: 33.333",
      );
    });

    it("does not move when substages are ticked", () => {
      const all = Object.fromEntries(PURCHASE_SUBSTAGES.map((s) => [s.id, true]));
      expect(bar(mountCard(boughtDeal({ completedSubstages: all })))).toContain(
        "width: 0%",
      );
    });
  });

  describe("what the card shows", () => {
    it("names the deal's current stage", () => {
      expect(mountCard().text()).toContain("Stage: Purchase");
      expect(mountCard(boughtDeal({ boughtStage: "rehab" })).text()).toContain(
        "Stage: Rehab",
      );
    });

    it("shows purchase and rehab in whole dollars", () => {
      const text = mountCard().text();
      expect(text).toContain("$200,000");
      expect(text).toContain("$50,000");
    });
  });
});
