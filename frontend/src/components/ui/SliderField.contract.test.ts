// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import PrimeVue from "primevue/config";
import InputNumber from "primevue/inputnumber";
import Slider from "primevue/slider";

import SliderField from "./SliderField.vue";

function mountField(props: Record<string, unknown> = {}) {
  return mount(SliderField, {
    props: { modelValue: 75, label: "LTV", min: 0, max: 100, ...props },
    global: { plugins: [[PrimeVue, { unstyled: true }]] },
  });
}

type Field = ReturnType<typeof mountField>;

/** PrimeVue's InputNumber renders a <span> root, so the real field is inside. */
const box = (wrapper: Field) =>
  wrapper.find<HTMLInputElement>('[data-part="input"] input');

const slider = (wrapper: Field) => wrapper.findComponent(Slider);
const emitted = (wrapper: Field) => wrapper.emitted("update:modelValue");

describe("SliderField", () => {
  it("labels the pair once, above both controls", () => {
    expect(mountField().find('[data-part="label"]').text()).toBe("LTV");
  });

  describe("the field anatomy", () => {
    it("draws the label alone in the shared 20px row", () => {
      const row = mountField().get('[data-part="label-row"]');
      expect(row.classes()).toContain("h-5");
      expect(row.find('[data-part="label"]').exists()).toBe(true);
      // The number box used to sit up here and made the row taller than every
      // other field's label row.
      expect(row.find('[data-part="input"]').exists()).toBe(false);
    });

    it("puts the slider and the number box together in one 42px control row", () => {
      const control = mountField().get('[data-part="control"]');
      expect(control.classes()).toContain("min-h-[42px]");
      expect(control.find('[data-part="slider"]').exists()).toBe(true);
      expect(control.find('[data-part="input"]').exists()).toBe(true);
    });

    it("gives the number box the same box every other field has", () => {
      const classes = box(mountField()).classes();
      expect(classes).toContain("ui-input");
      // No smaller padding or type size: the box must be the standard height.
      expect(classes).not.toContain("text-sm");
      expect(classes).not.toContain("py-1");
      expect(classes).not.toContain("px-2");
    });

    it("marks a required field with an asterisk for the eye and a word for the ear", () => {
      const wrapper = mountField({ required: true });
      const marker = wrapper.get('label [data-part="required"]');
      expect(marker.text()).toBe("*");
      expect(marker.attributes("aria-hidden")).toBe("true");
      expect(wrapper.get("label .sr-only").text()).toBe("required");
      expect(mountField().find('[data-part="required"]').exists()).toBe(false);
    });
  });

  describe("the number box", () => {
    it("shows the bound value", () => {
      expect(box(mountField({ modelValue: 80 })).element.value).toBe("80");
    });

    it("emits what was typed", async () => {
      const wrapper = mountField();
      await wrapper.findComponent(InputNumber).vm.$emit("input", { value: 82 });
      expect(emitted(wrapper)).toEqual([[82]]);
    });

    it("keeps a real null when cleared, instead of snapping back", async () => {
      const wrapper = mountField();
      await wrapper.findComponent(InputNumber).vm.$emit("input", { value: null });

      expect(emitted(wrapper)).toEqual([[null]]);
      await wrapper.setProps({ modelValue: null });
      expect(box(wrapper).element.value).toBe("");
    });

    it("renders a decimal without a fraction mask", () => {
      // 7 must not render as 7.00, or backspacing it is near-impossible.
      expect(box(mountField({ modelValue: 7 })).element.value).toBe("7");
      expect(box(mountField({ modelValue: 6.75 })).element.value).toBe("6.75");
    });

    it("shows the suffix when given", () => {
      expect(
        box(mountField({ modelValue: 75, suffix: "%" })).element.value,
      ).toBe("75%");
    });
  });

  describe("the slider", () => {
    it("emits when the thumb moves", async () => {
      const wrapper = mountField();
      await slider(wrapper).vm.$emit("update:modelValue", 65);
      expect(emitted(wrapper)).toEqual([[65]]);
    });

    it("sits at the bound value", () => {
      expect(slider(mountField({ modelValue: 80 })).props("modelValue")).toBe(80);
    });

    it("parks at the low end when the box is empty, without emitting", () => {
      const wrapper = mountField({ modelValue: null, min: 0, sliderMin: 50 });
      expect(slider(wrapper).props("modelValue")).toBe(50);
      expect(emitted(wrapper)).toBeUndefined();
    });
  });

  describe("the two ranges", () => {
    it("gives the thumb its own tighter bounds when asked", () => {
      // A DSCR rate: the thumb covers 3–12 while the box accepts 0–30.
      const wrapper = mountField({
        modelValue: 7,
        label: "Long Term Interest Rate",
        min: 0,
        max: 30,
        sliderMin: 3,
        sliderMax: 12,
      });

      expect(slider(wrapper).props("min")).toBe(3);
      expect(slider(wrapper).props("max")).toBe(12);
      expect(wrapper.findComponent(InputNumber).props("min")).toBe(0);
      expect(wrapper.findComponent(InputNumber).props("max")).toBe(30);
    });

    it("falls back to the typed bounds when none are given for the thumb", () => {
      const wrapper = mountField({ min: 40, max: 90 });
      expect(slider(wrapper).props("min")).toBe(40);
      expect(slider(wrapper).props("max")).toBe(90);
    });

    it("does not clamp a typed value into the thumb's range", async () => {
      // Typing 65 into a rate box whose thumb stops at 12 used to become 12.
      const wrapper = mountField({
        modelValue: 7,
        min: 0,
        max: 100,
        sliderMin: 3,
        sliderMax: 12,
      });

      await wrapper.findComponent(InputNumber).vm.$emit("input", { value: 65 });

      expect(emitted(wrapper)).toEqual([[65]]);
    });

    it("shares one step between the box and the thumb", () => {
      const wrapper = mountField({ step: 0.25 });
      expect(slider(wrapper).props("step")).toBe(0.25);
      expect(wrapper.findComponent(InputNumber).props("step")).toBe(0.25);
    });
  });
});
