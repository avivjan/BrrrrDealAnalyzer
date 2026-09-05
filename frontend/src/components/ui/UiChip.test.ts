// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiChip from "./UiChip.vue";

const mountChip = (props: Record<string, unknown> = {}, slot = "BRRRR") => mount(UiChip, { props, slots: { default: slot } });

describe("UiChip", () => {
  it("is a span pill with the slot text and nothing else", () => {
    const wrapper = mountChip();
    expect(wrapper.element.tagName).toBe("SPAN");
    expect(wrapper.attributes("data-ui")).toBe("chip");
    expect(wrapper.classes()).toEqual(expect.arrayContaining(["rounded-full", "border-ui"]));
    expect(wrapper.text()).toBe("BRRRR");
  });

  it("becomes a link with a touch-sized floor when given an href", () => {
    const wrapper = mountChip({ href: "https://docs.example" }, "Lenders");
    expect(wrapper.element.tagName).toBe("A");
    expect(wrapper.attributes("href")).toBe("https://docs.example");
    expect(wrapper.classes()).toContain("touch:min-h-11");
    expect(wrapper.classes().join(" ")).toContain("focus-visible:ring-2");
  });

  it("lets `as` override the tag", () => {
    expect(mountChip({ as: "li" }).element.tagName).toBe("LI");
  });

  it("gives every tone its own token look, and grows with size", () => {
    const tones = ["neutral", "primary", "accent", "positive", "negative", "warning"] as const;
    const seen = tones.map((tone) => mountChip({ tone }).classes().join(" "));
    expect(new Set(seen).size).toBe(6);
    expect(seen.join(" ")).not.toMatch(/\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/);
    expect(mountChip({ size: "md" }).classes()).toContain("text-sm");
  });

  it("renders a decorative icon before the label", () => {
    const icon = mountChip({ icon: "pi pi-link" }).find("i");
    expect(icon.classes()).toEqual(expect.arrayContaining(["pi", "pi-link"]));
    expect(icon.attributes("aria-hidden")).toBe("true");
  });

  it("passes attrs through and merges class", () => {
    const wrapper = mount(UiChip, { attrs: { "data-testid": "landing.resource.x", class: "rounded-none" } });
    expect(wrapper.attributes("data-testid")).toBe("landing.resource.x");
    expect(wrapper.classes()).toContain("rounded-none");
    expect(wrapper.classes()).not.toContain("rounded-full");
  });
});
