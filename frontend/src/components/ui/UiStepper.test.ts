// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiStepper from "./UiStepper.vue";

const STEPS =
  '<li data-step="done">Buy</li><li data-step="active">Rehab</li><li data-step="todo">Rent</li>';

function mountStepper(
  props: { count: number; compact?: boolean } = { count: 3 },
  slots: Record<string, string> = { default: STEPS },
  attrs: Record<string, unknown> = {},
) {
  return mount(UiStepper, { props, slots, attrs });
}

describe("UiStepper", () => {
  describe("what it announces", () => {
    it("is an ordered list, and says so even with its markers removed", () => {
      const wrapper = mountStepper();
      expect(wrapper.element.tagName).toBe("OL");
      expect(wrapper.attributes("role")).toBe("list");
      expect(wrapper.attributes("data-ui")).toBe("stepper");
    });
  });

  describe("the grid it lays the steps on", () => {
    it("publishes the step count as a custom property", () => {
      expect(mountStepper({ count: 4 }).attributes("style")).toContain("--steps: 4");
    });

    it("splits the row into equal columns driven by that property", () => {
      expect(mountStepper().classes().join(" ")).toContain(
        "grid-cols-[repeat(var(--steps),minmax(0,1fr))]",
      );
    });
  });

  describe("what it holds", () => {
    it("renders the steps the caller passes, untouched", () => {
      const steps = mountStepper().findAll("li");
      expect(steps).toHaveLength(3);
      expect(steps.map((step) => step.attributes("data-step"))).toEqual([
        "done",
        "active",
        "todo",
      ]);
    });

    it("hard-codes no copy of its own", () => {
      expect(mountStepper().text()).toBe("BuyRehabRent");
    });
  });

  describe("presentation", () => {
    it("tightens the type when compact", () => {
      expect(mountStepper({ count: 3, compact: true }).classes()).not.toEqual(
        mountStepper().classes(),
      );
      expect(mountStepper({ count: 3, compact: true }).attributes("data-compact")).toBe("true");
      expect(mountStepper().attributes("data-compact")).toBeUndefined();
    });

    it("uses tokens for every colour it sets", () => {
      expect(mountStepper().html()).not.toMatch(
        /\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/,
      );
    });

    it("passes attrs through to the root and merges class through cn()", () => {
      const wrapper = mountStepper(
        { count: 3 },
        { default: STEPS },
        { "data-testid": "deal.steps", class: "mt-4" },
      );
      expect(wrapper.attributes("data-testid")).toBe("deal.steps");
      expect(wrapper.classes()).toContain("mt-4");
    });
  });
});
