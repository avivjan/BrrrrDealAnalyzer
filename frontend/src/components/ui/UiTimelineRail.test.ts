// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiTimelineRail from "./UiTimelineRail.vue";

const items = [
  { id: "purchase", label: "Purchase", state: "done" as const },
  { id: "rehab", label: "Rehab", state: "active" as const },
  { id: "rent", label: "Rent", state: "todo" as const },
];

describe("UiTimelineRail", () => {
  it("renders a list of steps with their state and the active one marked current", () => {
    const wrapper = mount(UiTimelineRail, { props: { items } });
    expect(wrapper.element.tagName).toBe("OL");
    expect(wrapper.attributes("role")).toBe("list");
    const steps = wrapper.findAll("li");
    expect(steps.map((s) => s.attributes("data-state"))).toEqual(["done", "active", "todo"]);
    expect(steps.map((s) => s.attributes("aria-current"))).toEqual([undefined, "step", undefined]);
    expect(steps.map((s) => s.get('[data-part="label"]').text())).toEqual(["Purchase", "Rehab", "Rent"]);
  });

  it("draws a connector after every step but the last, solid only after a done step", () => {
    const steps = mount(UiTimelineRail, { props: { items } }).findAll("li");
    expect(steps[0]!.get('[data-part="connector"]').classes()).toContain("bg-primary");
    expect(steps[1]!.get('[data-part="connector"]').classes()).toContain("bg-line");
    expect(steps[2]!.find('[data-part="connector"]').exists()).toBe(false);
  });

  it("switches layout with orientation and hides labels visually when compact", () => {
    const vertical = mount(UiTimelineRail, { props: { items, orientation: "vertical", compact: true } });
    expect(vertical.attributes("data-orientation")).toBe("vertical");
    expect(vertical.classes()).toContain("flex-col");
    expect(vertical.get('[data-part="label"]').classes()).toContain("sr-only");
    expect(vertical.text()).toContain("Rehab"); // still in the DOM for assistive tech
  });

  it("uses tokens only and forwards attrs", () => {
    const wrapper = mount(UiTimelineRail, { props: { items }, attrs: { "data-testid": "pipeline.rail" } });
    expect(wrapper.attributes("data-testid")).toBe("pipeline.rail");
    expect(wrapper.html()).not.toMatch(/\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/);
  });
});
