// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import AutoDefaultMoneyInput from "./AutoDefaultMoneyInput.vue";

const stubs = {
  MoneyInput: { name: "MoneyInput", props: ["modelValue", "label", "inThousands", "info", "errorMessage"], emits: ["update:modelValue"], template: `<div class="money" />` },
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

  it("hands the error message to the money box underneath", () => {
    const wrapper = mount(AutoDefaultMoneyInput, {
      props: { modelValue: 400, computedDefault: 288, label: "Lowest ARV Possible", errorMessage: "Lowest ARV cannot exceed ARV." },
      global: { stubs },
    });
    expect(wrapper.findComponent({ name: "MoneyInput" }).props("errorMessage")).toBe("Lowest ARV cannot exceed ARV.");
  });

  describe("the estimate explanation under the box", () => {
    const explanationLines = ["$250 + 0.55% × $123,000 + $0 = $926.50", "No deed transfer tax: the seller pays it on a standard deal"];
    const mountWithExplanation = (modelValue: number | null) =>
      mount(AutoDefaultMoneyInput, {
        props: { modelValue, computedDefault: 926.5, label: "Recording & Transfer", estimateExplanationLines: explanationLines },
        global: { stubs },
      });

    it("shows every line while the field is on its formula default", () => {
      const explanation = mountWithExplanation(null).find('[data-part="estimate-explanation"]');
      expect(explanation.exists()).toBe(true);
      expect(explanation.findAll("li").map((line) => line.text())).toEqual(explanationLines);
    });

    it("hides once a dollar amount is typed, and comes back on reset", async () => {
      const wrapper = mountWithExplanation(null);
      await wrapper.setProps({ modelValue: 1000 });
      expect(wrapper.find('[data-part="estimate-explanation"]').exists()).toBe(false);
      await wrapper.setProps({ modelValue: null });
      expect(wrapper.find('[data-part="estimate-explanation"]').exists()).toBe(true);
    });

    it("renders nothing when no explanation is given", () => {
      expect(mountField(null).find('[data-part="estimate-explanation"]').exists()).toBe(false);
    });
  });
});
