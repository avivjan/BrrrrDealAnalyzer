// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import DaysUntilRefiField from "./DaysUntilRefiField.vue";

/** The number-entry mode is covered by NumberInput's own behaviour. */
const stubs = {
  NumberInput: {
    name: "NumberInput",
    props: ["modelValue", "label", "suffix", "min"],
    emits: ["update:modelValue"],
    template: `<div class="number-input" />`,
  },
};

function mountField(modelValue: number | null = 180) {
  return mount(DaysUntilRefiField, {
    props: { modelValue, label: "Days until Refi" },
    global: { stubs },
  });
}

type Field = ReturnType<typeof mountField>;

const toggle = (wrapper: Field) => wrapper.find("button");
const dateInputs = (wrapper: Field) =>
  wrapper.findAll<HTMLInputElement>('input[type="date"]');

/** The picker's confirm button is always the last one rendered. */
const doneButton = (wrapper: Field) => {
  const buttons = wrapper.findAll("button");
  return buttons[buttons.length - 1]!;
};

/** The purchase-closing and refi-closing date inputs, in that order. */
const purchaseInput = (wrapper: Field) => dateInputs(wrapper)[0]!;
const refiInput = (wrapper: Field) => dateInputs(wrapper)[1]!;

/** The most recent value the field emitted, or `undefined` if it never did. */
const lastEmitted = (wrapper: Field) => {
  const events = wrapper.emitted("update:modelValue");
  return events ? events[events.length - 1] : undefined;
};

async function pickDates(wrapper: Field, from: string, to: string) {
  await toggle(wrapper).trigger("click");
  await purchaseInput(wrapper).setValue(from);
  await refiInput(wrapper).setValue(to);
}

describe("DaysUntilRefiField", () => {
  it("starts in number-entry mode showing the day count", () => {
    const wrapper = mountField(180);
    expect(wrapper.findComponent({ name: "NumberInput" }).props("modelValue")).toBe(180);
    expect(dateInputs(wrapper)).toHaveLength(0);
  });

  it("passes a typed day count straight through", async () => {
    const wrapper = mountField(180);
    await wrapper
      .findComponent({ name: "NumberInput" })
      .vm.$emit("update:modelValue", 195);
    expect(lastEmitted(wrapper)).toEqual([195]);
  });

  describe("calendar mode", () => {
    it("converts two dates into a day count", async () => {
      const wrapper = mountField(180);
      // 2026-03-01 -> 2026-08-28 is 180 days.
      await pickDates(wrapper, "2026-03-01", "2026-08-28");
      expect(wrapper.text()).toContain("180 days");
    });

    it("counts a single day correctly", async () => {
      const wrapper = mountField(180);
      await pickDates(wrapper, "2026-03-01", "2026-03-02");
      expect(wrapper.text()).toContain("1 days");
    });

    it("counts across a leap day", async () => {
      const wrapper = mountField(180);
      // 2028 is a leap year: Feb 28 -> Mar 1 is 2 days, not 1.
      await pickDates(wrapper, "2028-02-28", "2028-03-01");
      expect(wrapper.text()).toContain("2 days");
    });

    it("emits and collapses back to the number on Done", async () => {
      const wrapper = mountField(180);
      await pickDates(wrapper, "2026-03-01", "2026-08-28");
      await doneButton(wrapper).trigger("click");

      expect(lastEmitted(wrapper)).toEqual([180]);
      expect(dateInputs(wrapper)).toHaveLength(0);
      expect(wrapper.findComponent({ name: "NumberInput" }).exists()).toBe(true);
    });

    it("refuses a refi date that is not after the purchase date", async () => {
      const wrapper = mountField(180);
      await pickDates(wrapper, "2026-08-28", "2026-03-01");

      expect(wrapper.text()).toContain("must be after");
      expect(doneButton(wrapper).attributes("disabled")).toBeDefined();

      await doneButton(wrapper).trigger("click");
      expect(wrapper.emitted("update:modelValue")).toBeUndefined();
    });

    it("refuses two identical dates", async () => {
      const wrapper = mountField(180);
      await pickDates(wrapper, "2026-03-01", "2026-03-01");
      expect(doneButton(wrapper).attributes("disabled")).toBeDefined();
    });

    it("waits for both dates before offering a count", async () => {
      const wrapper = mountField(180);
      await toggle(wrapper).trigger("click");
      await purchaseInput(wrapper).setValue("2026-03-01");

      expect(wrapper.text()).toContain("Pick both dates");
      expect(doneButton(wrapper).attributes("disabled")).toBeDefined();
    });

    it("can be reopened later to change an existing value", async () => {
      const wrapper = mountField(180);
      await pickDates(wrapper, "2026-03-01", "2026-08-28");
      await doneButton(wrapper).trigger("click");

      // Second pass: a different pair replaces the first answer.
      await pickDates(wrapper, "2026-03-01", "2026-06-01");
      await doneButton(wrapper).trigger("click");
      expect(lastEmitted(wrapper)).toEqual([92]);
    });

    it("reopens blank rather than showing a stale pair", async () => {
      // The dates aren't stored, so anything left in the boxes would only be a
      // guess at what produced the current day count.
      const wrapper = mountField(180);
      await pickDates(wrapper, "2026-03-01", "2026-08-28");
      await doneButton(wrapper).trigger("click");
      await toggle(wrapper).trigger("click");

      for (const input of dateInputs(wrapper)) {
        expect(input.element.value).toBe("");
      }
    });

    it("leaves the value untouched when the picker is dismissed", async () => {
      const wrapper = mountField(180);
      await pickDates(wrapper, "2026-03-01", "2026-08-28");
      await toggle(wrapper).trigger("click"); // "Enter days instead"

      expect(wrapper.emitted("update:modelValue")).toBeUndefined();
      expect(wrapper.findComponent({ name: "NumberInput" }).props("modelValue")).toBe(180);
    });
  });
});
