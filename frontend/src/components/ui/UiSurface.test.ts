// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiSurface from "./UiSurface.vue";

const mountSurface = (props: Record<string, unknown> = {}, attrs: Record<string, unknown> = {}) =>
  mount(UiSurface, { props, attrs, slots: { default: "Body" } });

describe("UiSurface", () => {
  it("is a div at tier 1 by default, marked for tests and styling", () => {
    const wrapper = mountSurface();
    expect(wrapper.element.tagName).toBe("DIV");
    expect(wrapper.attributes("data-ui")).toBe("surface");
    expect(wrapper.attributes("data-level")).toBe("1");
    expect(wrapper.classes()).toEqual(expect.arrayContaining(["bg-surface", "border-ui", "shadow-1", "rounded-card"]));
  });

  it("steps surface colour and shadow with the level", () => {
    expect(mountSurface({ level: 2 }).classes()).toEqual(expect.arrayContaining(["bg-surface-2", "shadow-2"]));
    expect(mountSurface({ level: 3 }).classes()).toEqual(expect.arrayContaining(["bg-surface-3", "shadow-3"]));
  });

  it("renders as the element the caller names", () => {
    expect(mountSurface({ as: "section" }).element.tagName).toBe("SECTION");
  });

  it("adds lift only when interactive, and no listeners of its own", () => {
    expect(mountSurface().classes().join(" ")).not.toContain("hover:-translate-y-px");
    expect(mountSurface({ interactive: true }).classes().join(" ")).toContain("hover:-translate-y-px");
    expect((UiSurface as unknown as { emits?: unknown }).emits).toBeUndefined();
  });

  it("pads by prop and passes attrs through, merging class via cn()", () => {
    const wrapper = mountSurface({ padding: "none" }, { "data-testid": "x.panel", class: "rounded-none" });
    expect(wrapper.classes()).not.toContain("p-4");
    expect(wrapper.attributes("data-testid")).toBe("x.panel");
    expect(wrapper.classes()).toContain("rounded-none");
    expect(wrapper.classes()).not.toContain("rounded-card");
    expect(wrapper.text()).toBe("Body");
  });

  it("uses tokens only", () => {
    expect(mountSurface({ level: 3, interactive: true }).classes().join(" ")).not.toMatch(
      /\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/,
    );
  });
});
