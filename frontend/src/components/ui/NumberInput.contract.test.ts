// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import PrimeVue from "primevue/config";
import InputNumber from "primevue/inputnumber";

import NumberInput from "./NumberInput.vue";

function mountInput(props: Record<string, unknown> = {}) {
  return mount(NumberInput, {
    props: { modelValue: null, ...props },
    global: { plugins: [[PrimeVue, { unstyled: true }]] },
  });
}

type Input = ReturnType<typeof mountInput>;

/** PrimeVue's InputNumber renders a <span> root, so the real field is inside. */
const field = (wrapper: Input) =>
  wrapper.find<HTMLInputElement>('[data-part="input"] input');

const emitted = (wrapper: Input) => wrapper.emitted("update:modelValue");

describe("NumberInput", () => {
  describe("the label", () => {
    it("renders the label when one is given", () => {
      const wrapper = mountInput({ label: "Refi Points" });
      expect(wrapper.find('[data-part="label"]').text()).toBe("Refi Points");
    });

    it("renders bare when no label is given", () => {
      expect(mountInput().find('[data-part="label"]').exists()).toBe(false);
    });

    it("still renders the input when bare", () => {
      expect(field(mountInput()).exists()).toBe(true);
    });
  });

  describe("the value in", () => {
    it("shows the bound number", () => {
      expect(field(mountInput({ modelValue: 180 })).element.value).toBe("180");
    });

    it("shows an empty box for null rather than a zero", () => {
      expect(field(mountInput({ modelValue: null })).element.value).toBe("");
    });

    it("renders a decimal without a forced fraction mask", () => {
      // `minFractionDigits: 0` is what lets 6.5 be backspaced digit by digit.
      expect(field(mountInput({ modelValue: 6.5 })).element.value).toBe("6.5");
    });

    it("appends the suffix when given", () => {
      expect(
        field(mountInput({ modelValue: 75, suffix: "%" })).element.value,
      ).toBe("75%");
    });
  });

  describe("the value out", () => {
    it("emits the number InputNumber reports on input", async () => {
      const wrapper = mountInput({ modelValue: 180 });

      await wrapper
        .findComponent(InputNumber)
        .vm.$emit("input", { value: 195, originalEvent: new Event("input") });

      expect(emitted(wrapper)).toEqual([[195]]);
    });

    it("emits null when the box is cleared, so the field can be retyped", async () => {
      const wrapper = mountInput({ modelValue: 180 });

      await wrapper
        .findComponent(InputNumber)
        .vm.$emit("input", { value: null, originalEvent: new Event("input") });

      expect(emitted(wrapper)).toEqual([[null]]);
    });

    it("emits once per input event, not twice", async () => {
      // The field used to bind v-model *and* @input, writing twice per
      // keystroke and throwing the caret to the end. One event in, one out.
      const wrapper = mountInput({ modelValue: 0 });
      const number = wrapper.findComponent(InputNumber);

      await number.vm.$emit("input", { value: 6 });
      await number.vm.$emit("input", { value: 6.5 });

      expect(emitted(wrapper)).toEqual([[6], [6.5]]);
    });

    it("does not write back on its own when the bound value changes", async () => {
      const wrapper = mountInput({ modelValue: 180 });
      await wrapper.setProps({ modelValue: 200 });
      expect(emitted(wrapper)).toBeUndefined();
    });
  });

  describe("select-all", () => {
    it.each([
      ["⌘", { metaKey: true }],
      ["Ctrl", { ctrlKey: true }],
    ])("selects the box's contents on %s+A", async (_name, modifier) => {
      const wrapper = mountInput({ modelValue: 180 });
      const input = field(wrapper);
      const select = vi.spyOn(input.element, "select");

      await input.trigger("keydown", { key: "a", ...modifier });

      expect(select).toHaveBeenCalled();
      select.mockRestore();
    });

    it("leaves a plain 'a' alone", async () => {
      const wrapper = mountInput({ modelValue: 180 });
      const input = field(wrapper);
      const select = vi.spyOn(input.element, "select");

      await input.trigger("keydown", { key: "a" });

      expect(select).not.toHaveBeenCalled();
      select.mockRestore();
    });

    it("does not throw when the event has no selectable target", async () => {
      const wrapper = mountInput({ modelValue: 180 });
      // A keydown that reaches the handler from the wrapper element itself.
      expect(() =>
        wrapper.findComponent(InputNumber).vm.$emit("keydown", {
          key: "a",
          metaKey: true,
          preventDefault: () => {},
          target: null,
        }),
      ).not.toThrow();
    });
  });
});
