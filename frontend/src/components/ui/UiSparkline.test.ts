// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiSparkline from "./UiSparkline.vue";

describe("UiSparkline", () => {
  it("is a decorative svg drawn to its own scale", () => {
    const wrapper = mount(UiSparkline, { props: { points: [1, 3, 2, 5] } });
    expect(wrapper.element.tagName).toBe("svg");
    expect(wrapper.attributes("aria-hidden")).toBe("true");
    expect(wrapper.attributes("data-ui")).toBe("sparkline");
    const d = wrapper.get('[data-part="line"]').attributes("d")!;
    // First point at x=0, last at x=100; max (5) sits at the top pad, min (1) at the bottom pad.
    expect(d.startsWith("M0.00,26.00")).toBe(true);
    expect(d).toContain("L100.00,2.00");
    expect(wrapper.get('[data-part="end"]').attributes("cx")).toBe("100");
  });

  it("fills by default and can be turned off", () => {
    expect(mount(UiSparkline, { props: { points: [1, 2] } }).find('[data-part="area"]').exists()).toBe(true);
    expect(mount(UiSparkline, { props: { points: [1, 2], filled: false } }).find('[data-part="area"]').exists()).toBe(false);
  });

  it("draws a flat line for a single point and nothing for none", () => {
    const one = mount(UiSparkline, { props: { points: [7] } });
    expect(one.get('[data-part="line"]').attributes("d")).toBe("M0.00,26.00 L100.00,26.00");
    const none = mount(UiSparkline, { props: { points: [] } });
    expect(none.find('[data-part="line"]').exists()).toBe(false);
    expect(none.find('[data-part="end"]').exists()).toBe(false);
  });

  it("takes its colour from a token tone class via currentColor", () => {
    const wrapper = mount(UiSparkline, { props: { points: [1, 2], tone: "negative" } });
    expect(wrapper.classes()).toContain("text-negative");
    expect(wrapper.get('[data-part="line"]').attributes("stroke")).toBe("currentColor");
    expect(mount(UiSparkline, { props: { points: [1, 2] } }).classes()).toContain("text-accent");
  });
});
