// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";

import UiCommandItem from "./UiCommandItem.vue";

describe("UiCommandItem", () => {
  it("is an option with a stable id, the label, and an optional hint", () => {
    const wrapper = mount(UiCommandItem, { props: { id: "go-liquidity", label: "Liquidity", hint: "G L", icon: "pi pi-chart-line" } });
    expect(wrapper.attributes("role")).toBe("option");
    expect(wrapper.attributes("id")).toBe("cmd-go-liquidity");
    expect(wrapper.attributes("aria-selected")).toBe("false");
    expect(wrapper.get('[data-part="label"]').text()).toBe("Liquidity");
    expect(wrapper.get('[data-part="hint"]').text()).toBe("G L");
    expect(wrapper.get("i").attributes("aria-hidden")).toBe("true");
  });

  it("marks the active row for the combobox and styles it with tokens", () => {
    const wrapper = mount(UiCommandItem, { props: { id: "x", label: "X", active: true } });
    expect(wrapper.attributes("aria-selected")).toBe("true");
    expect(wrapper.attributes("data-active")).toBe("true");
    expect(wrapper.classes().join(" ")).toContain("bg-primary/12");
    expect(wrapper.html()).not.toMatch(/\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/);
  });

  it("owns no behaviour: the parent's click listener arrives through attrs", async () => {
    const onClick = vi.fn();
    const wrapper = mount(UiCommandItem, { props: { id: "x", label: "X" }, attrs: { onClick, "data-testid": "shell.command.item.x" } });
    await wrapper.trigger("click");
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(wrapper.attributes("data-testid")).toBe("shell.command.item.x");
    expect((UiCommandItem as unknown as { emits?: unknown }).emits).toBeUndefined();
  });
});
