// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiSegmented from "./UiSegmented.vue";

const options = [
  { value: "light", label: "Light", icon: "pi pi-sun" },
  { value: "dark", label: "Dark", icon: "pi pi-moon" },
  { value: "system", label: "System" },
];

const mountSeg = (modelValue = "dark", props: Record<string, unknown> = {}) =>
  mount(UiSegmented, { props: { options, modelValue, ariaLabel: "Mode", ...props } });

describe("UiSegmented", () => {
  it("is a named radiogroup with one checked radio that is the only tab stop", () => {
    const wrapper = mountSeg();
    expect(wrapper.attributes("role")).toBe("radiogroup");
    expect(wrapper.attributes("aria-label")).toBe("Mode");
    const radios = wrapper.findAll('[role="radio"]');
    expect(radios.map((r) => r.attributes("aria-checked"))).toEqual(["false", "true", "false"]);
    expect(radios.map((r) => r.attributes("tabindex"))).toEqual(["-1", "0", "-1"]);
    expect(radios.map((r) => r.attributes("data-value"))).toEqual(["light", "dark", "system"]);
    expect(radios.map((r) => r.text())).toEqual(["Light", "Dark", "System"]);
  });

  it("emits the clicked value and never mutates its own state", async () => {
    const wrapper = mountSeg();
    await wrapper.findAll('[role="radio"]')[2]!.trigger("click");
    expect(wrapper.emitted("update:modelValue")).toEqual([["system"]]);
    // Still shows the prop it was given.
    expect(wrapper.findAll('[role="radio"]')[1]!.attributes("aria-checked")).toBe("true");
  });

  it("moves with the arrow keys, wrapping, and jumps with Home/End", async () => {
    const wrapper = mountSeg("dark");
    await wrapper.trigger("keydown", { key: "ArrowRight" });
    await wrapper.trigger("keydown", { key: "ArrowLeft" });
    await wrapper.trigger("keydown", { key: "End" });
    await wrapper.trigger("keydown", { key: "Home" });
    expect(wrapper.emitted("update:modelValue")!.map((e) => e[0])).toEqual(["system", "light", "system", "light"]);
    const last = mountSeg("system");
    await last.trigger("keydown", { key: "ArrowDown" });
    expect(last.emitted("update:modelValue")).toEqual([["light"]]);
  });

  it("falls back to the first option as the tab stop when the model matches nothing", () => {
    const radios = mountSeg("sepia").findAll('[role="radio"]');
    expect(radios.map((r) => r.attributes("tabindex"))).toEqual(["0", "-1", "-1"]);
  });

  it("stretches when block, keeps a touch floor at md, and uses tokens only", () => {
    const wrapper = mountSeg("dark", { block: true });
    expect(wrapper.classes()).toContain("w-full");
    expect(wrapper.get('[role="radio"]').classes()).toContain("touch:min-h-11");
    expect(wrapper.html()).not.toMatch(/\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/);
    expect(wrapper.findAll("i")).toHaveLength(2);
  });
});
