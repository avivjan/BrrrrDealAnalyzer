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

/** The stage after Purchase, and one of its substages — a *future* task. */
const NEXT_STAGE = brrrPipeline.stages[1]!;
const FUTURE_SUB = NEXT_STAGE.subStages[0]!;

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

const stageHeader = (wrapper: ReturnType<typeof mountCard>, id: string) =>
  wrapper.find(`[data-testid="boughtcard.stage.${id}"]`);

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

    it("renders a header for every stage of the template, in order", () => {
      const wrapper = mountCard();
      const headers = wrapper.findAll('[data-part="stages"] button[data-testid^="boughtcard.stage."]');
      expect(headers.map((h) => h.attributes("data-testid"))).toEqual(
        brrrPipeline.stages.map((s) => `boughtcard.stage.${s.id}`),
      );
      for (const stage of brrrPipeline.stages) {
        expect(wrapper.text()).toContain(stage.name);
      }
    });

    it("gives a stage with no substages a header, a dash, and no body", () => {
      // "rehab" is a bare stage in the default BRRRR template.
      const wrapper = mountCard(boughtDeal({ boughtStage: "rehab" }));
      const header = stageHeader(wrapper, "rehab");
      expect(header.exists()).toBe(true);
      expect(header.text()).toContain("—");
      expect(header.attributes("aria-expanded")).toBeUndefined();
      // Its row holds nothing to tick.
      expect(header.element.parentElement!.querySelector('input[type="checkbox"]')).toBeNull();
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

    it("lets a future stage's task be ticked today, through the same hook and store call", async () => {
      const store = useBoughtDealStore();
      const toggle = vi.spyOn(store, "toggleSubstage").mockResolvedValue(undefined);
      const wrapper = mountCard(boughtDeal({ id: "bought-7" }));

      const box = wrapper.find(`[data-testid="boughtcard.substage.${FUTURE_SUB.id}.input"]`);
      expect(box.exists(), `no checkbox for future task ${FUTURE_SUB.id}`).toBe(true);
      expect(box.attributes("aria-label")).toBe(FUTURE_SUB.label);

      await stageHeader(wrapper, NEXT_STAGE.id).trigger("click");
      await box.trigger("click");

      expect(toggle).toHaveBeenCalledWith("bought-7", FUTURE_SUB.id);
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

      await board.find(`[data-testid="boughtcard.stage.${NEXT_STAGE.id}"]`).trigger("click");
      expect(parentClick).not.toHaveBeenCalled();
    });
  });

  describe("the stage accordion", () => {
    it("opens the current stage by default and the others on a click, one at a time", async () => {
      const wrapper = mountCard();
      expect(stageHeader(wrapper, "purchase").attributes("aria-expanded")).toBe("true");
      expect(stageHeader(wrapper, NEXT_STAGE.id).attributes("aria-expanded")).toBe("false");

      await stageHeader(wrapper, NEXT_STAGE.id).trigger("click");
      expect(stageHeader(wrapper, NEXT_STAGE.id).attributes("aria-expanded")).toBe("true");
      expect(stageHeader(wrapper, "purchase").attributes("aria-expanded")).toBe("false");

      // A second click on the open row closes it.
      await stageHeader(wrapper, NEXT_STAGE.id).trigger("click");
      expect(stageHeader(wrapper, NEXT_STAGE.id).attributes("aria-expanded")).toBe("false");
    });

    it("follows the deal when its stage changes", async () => {
      const wrapper = mountCard();
      await stageHeader(wrapper, NEXT_STAGE.id).trigger("click");
      await wrapper.setProps({ deal: boughtDeal({ boughtStage: "closed" }) });
      expect(stageHeader(wrapper, "closed").attributes("aria-expanded")).toBe("true");
      expect(stageHeader(wrapper, NEXT_STAGE.id).attributes("aria-expanded")).toBe("false");
    });

    it("shows done/total per stage and tints a future stage that has already started", () => {
      const wrapper = mountCard(boughtDeal({ completedSubstages: { [FUTURE_SUB.id]: true } }));
      const pill = (id: string) => stageHeader(wrapper, id).find(".rounded-full");

      expect(pill("purchase").text()).toBe(`0/${PURCHASE_SUBSTAGES.length}`);
      expect(pill("purchase").classes()).toContain("text-primary");

      expect(pill(NEXT_STAGE.id).text()).toBe(`1/${NEXT_STAGE.subStages.length}`);
      expect(pill(NEXT_STAGE.id).classes()).toContain("text-primary");

      // An untouched future stage stays muted.
      expect(pill("rent").classes()).toContain("text-fg-muted");
    });
  });

  describe("progress", () => {
    const railStates = (wrapper: ReturnType<typeof mountCard>) =>
      wrapper.findAll('[data-ui="timeline-rail"] li').map((li) => li.attributes("data-state"));

    it("draws every stage on the rail, marking past, active and to-come", () => {
      // "closed" is index 2 of 7 BRRRR stages.
      expect(railStates(mountCard(boughtDeal({ boughtStage: "closed" })))).toEqual([
        "done",
        "done",
        "active",
        "todo",
        "todo",
        "todo",
        "todo",
      ]);
      expect(railStates(mountCard(boughtDeal({ boughtStage: "purchase" })))[0]).toBe("active");
      const last = railStates(mountCard(boughtDeal({ boughtStage: "refinanced" })));
      expect(last[last.length - 1]).toBe("active");
    });

    it("does not move the rail when substages are ticked", () => {
      const all = Object.fromEntries(PURCHASE_SUBSTAGES.map((s) => [s.id, true]));
      expect(railStates(mountCard(boughtDeal({ completedSubstages: all })))[0]).toBe("active");
    });

    it("rings the current stage's ticks", () => {
      const [first] = PURCHASE_SUBSTAGES;
      const ring = (deal: BoughtDealRes) => mountCard(deal).find('[data-ui="progress-ring"]');
      expect(ring(boughtDeal()).attributes("aria-label")).toBe("0 of 2 tasks done in Purchase");
      expect(ring(boughtDeal({ completedSubstages: { [first!.id]: true } })).text()).toBe("50%");
      // A stage with no tasks is simply done.
      expect(ring(boughtDeal({ boughtStage: "rehab" })).text()).toBe("100%");
    });

    it("glows when the stage's checklist is complete", () => {
      const all = Object.fromEntries(PURCHASE_SUBSTAGES.map((s) => [s.id, true]));
      expect(mountCard(boughtDeal({ completedSubstages: all })).classes()).toContain("ring-positive/50");
      expect(mountCard().classes()).not.toContain("ring-positive/50");
    });
  });

  describe("advance", () => {
    const advance = (wrapper: ReturnType<typeof mountCard>) =>
      wrapper.find('[data-testid="boughtcard.advance"]');

    it("is offered only once every task of the current stage is ticked", () => {
      expect(advance(mountCard()).exists()).toBe(false);
      const all = Object.fromEntries(PURCHASE_SUBSTAGES.map((s) => [s.id, true]));
      expect(advance(mountCard(boughtDeal({ completedSubstages: all }))).exists()).toBe(true);
    });

    it("is never offered on the last stage", () => {
      const last = brrrPipeline.stages[brrrPipeline.stages.length - 1]!;
      const all = Object.fromEntries(last.subStages.map((s) => [s.id, true]));
      expect(
        advance(mountCard(boughtDeal({ boughtStage: last.id, completedSubstages: all }))).exists(),
      ).toBe(false);
    });

    it("emits advance with the deal id and never touches the store", async () => {
      const store = useBoughtDealStore();
      const advanceStage = vi.spyOn(store, "advanceStage");
      const all = Object.fromEntries(PURCHASE_SUBSTAGES.map((s) => [s.id, true]));
      const wrapper = mountCard(boughtDeal({ id: "bought-3", completedSubstages: all }));

      await advance(wrapper).trigger("click");

      expect(wrapper.emitted("advance")).toEqual([["bought-3"]]);
      expect(advanceStage).not.toHaveBeenCalled();
    });
  });

  describe("what the card shows", () => {
    it("names the deal's current step and stage", () => {
      expect(mountCard().text()).toContain("Step 1 of 7");
      expect(mountCard().text()).toContain("Purchase");
      const rehab = mountCard(boughtDeal({ boughtStage: "rehab" })).text();
      expect(rehab).toContain("Step 4 of 7");
      expect(rehab).toContain("Rehab");
    });

    it("shows purchase and rehab in whole dollars", () => {
      const text = mountCard().text();
      expect(text).toContain("$200,000");
      expect(text).toContain("$50,000");
    });

    it("shows cash in and the refi target for a BRRRR deal", () => {
      const text = mountCard(
        boughtDeal({
          total_cash_needed_for_deal: 61234.4,
          arv_in_thousands: 300,
          ltv_as_precent: 75,
        } as Partial<BoughtDealRes>),
      ).text();
      expect(text).toContain("Cash in");
      expect(text).toContain("$61,234");
      expect(text).toContain("Refi target");
      expect(text).toContain("$225,000");
    });

    it("shows a dash for the refi target until ARV and LTV are known", () => {
      const metrics = mountCard().find('[data-part="metrics"]').text();
      expect(metrics).toContain("Refi target");
      expect(metrics).toContain("-");
    });

    it("shows the sale target for a FLIP deal", () => {
      const text = mountCard(
        boughtDeal({
          deal_type: "FLIP",
          salePrice: 300,
          total_cash_needed: 40000,
        } as Partial<BoughtDealRes>),
      ).text();
      expect(text).toContain("FLIP");
      expect(text).toContain("Sale target");
      expect(text).toContain("$300,000");
      expect(text).toContain("$40,000");
    });

    it("keeps the footer's sqft and bed/bath fallbacks", () => {
      expect(mountCard().text()).toContain("- sqft");
      expect(mountCard().text()).toContain("-bd / -ba");
      expect(mountCard(boughtDeal({ sqft: 1450, bedrooms: 3, bathrooms: 2 })).text()).toContain("3bd / 2ba");
    });
  });
});
