// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import PresetSelectInput from "./PresetSelectInput.vue";

const stubs = {
  MoneyInput: { name: "MoneyInput", props: ["modelValue", "label"], emits: ["update:modelValue"], template: `<div class="money" />` },
};
const PRESETS = [{ label: "3shacks", value: 900 }, { label: "212", value: 1900 }];
const mountIt = (modelValue: number | null) =>
  mount(PresetSelectInput, { props: { modelValue, label: "Loan Charges", presets: PRESETS }, global: { stubs } });

describe("PresetSelectInput", () => {
  it("selects the preset that matches the amount, else Custom", () => {
    expect(mountIt(900).find<HTMLSelectElement>("select").element.value).toBe("3shacks");
    expect(mountIt(1900).find<HTMLSelectElement>("select").element.value).toBe("212");
    expect(mountIt(1250).find<HTMLSelectElement>("select").element.value).toBe("__custom__");
    expect(mountIt(null).find<HTMLSelectElement>("select").element.value).toBe("__custom__");
  });

  it("picking a preset writes its amount", async () => {
    const w = mountIt(900);
    await w.find("select").setValue("212");
    expect(w.emitted("update:modelValue")![0]).toEqual([1900]);
  });

  it("typing an amount passes straight through", async () => {
    const w = mountIt(900);
    await w.findComponent({ name: "MoneyInput" }).vm.$emit("update:modelValue", 1250);
    expect(w.emitted("update:modelValue")![0]).toEqual([1250]);
  });
});
