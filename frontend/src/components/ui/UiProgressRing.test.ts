// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiProgressRing from "./UiProgressRing.vue";

describe("UiProgressRing", () => {
  it("is an image with the given name, sized by the prop", () => {
    const wrapper = mount(UiProgressRing, { props: { value: 0.6, label: "3 of 5 substages done", size: 48 } });
    expect(wrapper.attributes("role")).toBe("img");
    expect(wrapper.attributes("aria-label")).toBe("3 of 5 substages done");
    expect(wrapper.attributes("style")).toContain("width: 48px");
    expect(wrapper.get("svg").attributes("viewBox")).toBe("0 0 48 48");
  });

  it("draws the arc as a dash offset of the circumference", () => {
    const wrapper = mount(UiProgressRing, { props: { value: 0.25, label: "x", size: 40, thickness: 4 } });
    const arc = wrapper.get('[data-part="arc"]');
    const r = (40 - 4) / 2;
    const c = 2 * Math.PI * r;
    expect(Number(arc.attributes("stroke-dasharray"))).toBeCloseTo(c, 5);
    expect(Number(arc.attributes("stroke-dashoffset"))).toBeCloseTo(c * 0.75, 5);
  });

  it("prints the percentage as text and clamps the value", () => {
    expect(mount(UiProgressRing, { props: { value: 0.6, label: "x" } }).get('[data-part="text"]').text()).toBe("60%");
    expect(mount(UiProgressRing, { props: { value: 1.7, label: "x" } }).get('[data-part="text"]').text()).toBe("100%");
    expect(mount(UiProgressRing, { props: { value: -2, label: "x" } }).get('[data-part="text"]').text()).toBe("0%");
    expect(mount(UiProgressRing, { props: { value: Number.NaN, label: "x" } }).get('[data-part="text"]').text()).toBe("0%");
  });

  it("lets the slot replace the centre text and colours by tone token", () => {
    const wrapper = mount(UiProgressRing, { props: { value: 0.5, label: "x", tone: "positive" }, slots: { default: "3/5" } });
    expect(wrapper.get('[data-part="text"]').text()).toBe("3/5");
    expect(wrapper.classes()).toContain("text-positive");
  });
});
