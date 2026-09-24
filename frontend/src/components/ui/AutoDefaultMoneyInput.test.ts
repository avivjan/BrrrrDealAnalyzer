// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import AutoDefaultMoneyInput from "./AutoDefaultMoneyInput.vue";

const stubs = {
  MoneyInput: { name: "MoneyInput", props: ["modelValue", "label", "inThousands", "info"], emits: ["update:modelValue"], template: `<div class="money" />` },
};
const mountField = (modelValue: number | null, computedDefault: number | null = 1130) =>
  mount(AutoDefaultMoneyInput, { props: { modelValue, computedDefault, label: "Recording & Transfer" }, global: { stubs } });

describe("AutoDefaultMoneyInput", () => {
  it("shows the formula value with an auto tag while the field is null", () => {
    const wrapper = mountField(null);
    expect(wrapper.attributes("data-auto")).toBe("true");
    expect(wrapper.find('[data-part="auto"]').exists()).toBe(true);
    expect(wrapper.find('[data-part="reset"]').exists()).toBe(false);
    expect(wrapper.findComponent({ name: "MoneyInput" }).props("modelValue")).toBe(1130);
  });

  it("shows the override with a reset that puts the formula back", async () => {
    const wrapper = mountField(1234);
    expect(wrapper.attributes("data-auto")).toBe("false");
    expect(wrapper.findComponent({ name: "MoneyInput" }).props("modelValue")).toBe(1234);
    await wrapper.find('[data-part="reset"]').trigger("click");
    expect(wrapper.emitted("update:modelValue")![0]).toEqual([null]);
  });

  it("passes a typed number through, and a cleared box back to the formula", async () => {
    const wrapper = mountField(null);
    await wrapper.findComponent({ name: "MoneyInput" }).vm.$emit("update:modelValue", 999);
    await wrapper.findComponent({ name: "MoneyInput" }).vm.$emit("update:modelValue", null);
    expect(wrapper.emitted("update:modelValue")).toEqual([[999], [null]]);
  });

  it("shows nothing while the formula's inputs are missing", () => {
    expect(mountField(null, null).findComponent({ name: "MoneyInput" }).props("modelValue")).toBeNull();
  });
});
