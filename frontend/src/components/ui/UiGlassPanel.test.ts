// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiGlassPanel from "./UiGlassPanel.vue";

describe("UiGlassPanel", () => {
  it("renders the .glass utility on a panel-rounded element", () => {
    const wrapper = mount(UiGlassPanel, { slots: { default: "x" } });
    expect(wrapper.attributes("data-ui")).toBe("glass-panel");
    expect(wrapper.attributes("data-intensity")).toBe("low");
    expect(wrapper.classes()).toEqual(expect.arrayContaining(["glass", "rounded-panel", "shadow-1", "p-4"]));
  });

  it("deepens the shadow at high intensity and honours as/padding", () => {
    const wrapper = mount(UiGlassPanel, { props: { intensity: "high", as: "aside", padding: "none" } });
    expect(wrapper.element.tagName).toBe("ASIDE");
    expect(wrapper.classes()).toContain("shadow-3");
    expect(wrapper.classes()).not.toContain("p-4");
  });

  it("carries no text of its own and forwards attrs", () => {
    const wrapper = mount(UiGlassPanel, { attrs: { "data-testid": "shell.glass", class: "rounded-none" } });
    expect(wrapper.text()).toBe("");
    expect(wrapper.attributes("data-testid")).toBe("shell.glass");
    expect(wrapper.classes()).toContain("rounded-none");
    expect(wrapper.classes()).not.toContain("rounded-panel");
  });
});
