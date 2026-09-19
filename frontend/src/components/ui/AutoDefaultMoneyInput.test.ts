// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import AutoDefaultMoneyInput from "./AutoDefaultMoneyInput.vue";

const stubs = {
  MoneyInput: { name: "MoneyInput", props: ["modelValue", "label", "inThousands", "info"], emits: ["update:modelValue"], template: `<div class="money" />` },
};
const mountIt = (modelValue: number | null, computedDefault: number | null = 1130) =>
  mount(AutoDefaultMoneyInput, { props: { modelValue, computedDefault, label: "Recording & Transfer" }, global: { stubs } });

describe("AutoDefaultMoneyInput", () => {
  it("shows the formula value with an auto tag while the field is null", () => {
    const w = mountIt(null);
    expect(w.attributes("data-auto")).toBe("true");
    expect(w.find('[data-part="auto"]').exists()).toBe(true);
    expect(w.find('[data-part="reset"]').exists()).toBe(false);
    expect(w.findComponent({ name: "MoneyInput" }).props("modelValue")).toBe(1130);
  });

  it("shows the override with a reset that puts the formula back", async () => {
    const w = mountIt(1234);
    expect(w.attributes("data-auto")).toBe("false");
    expect(w.findComponent({ name: "MoneyInput" }).props("modelValue")).toBe(1234);
    await w.find('[data-part="reset"]').trigger("click");
    expect(w.emitted("update:modelValue")![0]).toEqual([null]);
  });

  it("passes a typed number through, and a cleared box back to the formula", async () => {
    const w = mountIt(null);
    await w.findComponent({ name: "MoneyInput" }).vm.$emit("update:modelValue", 999);
    await w.findComponent({ name: "MoneyInput" }).vm.$emit("update:modelValue", null);
    expect(w.emitted("update:modelValue")).toEqual([[999], [null]]);
  });

  it("shows nothing while the formula's inputs are missing", () => {
    expect(mountIt(null, null).findComponent({ name: "MoneyInput" }).props("modelValue")).toBeNull();
  });
});
