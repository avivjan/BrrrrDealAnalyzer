// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import InspectionFinishDialog from "./InspectionFinishDialog.vue";
import InspectionStatusPicker from "./InspectionStatusPicker.vue";
import InspectionWindowReplacementCounter from "./InspectionWindowReplacementCounter.vue";
import { findChecklistItem } from "../../inspection/inspectionChecklistLogic";

const windowsCounterField = findChecklistItem("windows")!.fields[0]!;

describe("InspectionWindowReplacementCounter", () => {
  it("steps with big +/- buttons and emits the new count", async () => {
    const wrapper = mount(InspectionWindowReplacementCounter, { props: { field: windowsCounterField, modelValue: 2 } });
    expect(wrapper.get('[data-testid="inspection.counter.value"]').text()).toBe("2");
    await wrapper.get('[data-testid="inspection.counter.increase"]').trigger("click");
    await wrapper.get('[data-testid="inspection.counter.decrease"]').trigger("click");
    expect(wrapper.emitted("update:modelValue")).toEqual([[3], [1]]);
    expect(wrapper.find("input").exists()).toBe(false); // never typed
  });

  it("starts at 0 and cannot go below the minimum or above the maximum", async () => {
    const atZero = mount(InspectionWindowReplacementCounter, { props: { field: windowsCounterField, modelValue: undefined } });
    expect(atZero.get('[data-testid="inspection.counter.value"]').text()).toBe("0");
    expect(atZero.get('[data-testid="inspection.counter.decrease"]').attributes("disabled")).toBeDefined();
    const atMaximum = mount(InspectionWindowReplacementCounter, { props: { field: windowsCounterField, modelValue: 99 } });
    expect(atMaximum.get('[data-testid="inspection.counter.increase"]').attributes("disabled")).toBeDefined();
  });
});

describe("InspectionStatusPicker", () => {
  it("offers OK, Repair and Replace as one-tap radios and marks the current one", async () => {
    const wrapper = mount(InspectionStatusPicker, { props: { modelValue: "repair" } });
    const radios = wrapper.findAll('[role="radio"]');
    expect(radios.map((radio) => radio.text())).toEqual(["OK", "Repair", "Replace"]);
    expect(radios.map((radio) => radio.attributes("aria-checked"))).toEqual(["false", "true", "false"]);
    await wrapper.get('[data-testid="inspection.card.status.replace"]').trigger("click");
    await wrapper.get('[data-testid="inspection.card.status.reset"]').trigger("click");
    expect(wrapper.emitted("update:modelValue")).toEqual([["replace"], ["not_checked"]]);
  });

  it("has no reset link while the item is not checked", () => {
    const wrapper = mount(InspectionStatusPicker, { props: { modelValue: "not_checked" } });
    expect(wrapper.find('[data-testid="inspection.card.status.reset"]').exists()).toBe(false);
  });
});

describe("InspectionFinishDialog", () => {
  it("lists the missions left and only confirms with a reason of at least 10 characters", async () => {
    const wrapper = mount(InspectionFinishDialog, {
      props: { remainingCriticalItemLabels: ["HVAC", "Sewer"], isSubmitting: false, errorMessage: null },
      attachTo: document.body,
    });
    const dialog = document.body;
    expect(dialog.textContent).toContain("HVAC");
    expect(dialog.textContent).toContain("Sewer");
    const confirmButton = () => dialog.querySelector<HTMLButtonElement>('[data-testid="inspection.finish-dialog.confirm"]')!;
    const reasonBox = dialog.querySelector<HTMLTextAreaElement>('[data-testid="inspection.finish-dialog.reason"]')!;
    expect(confirmButton().disabled).toBe(true);
    reasonBox.value = "too short";
    reasonBox.dispatchEvent(new Event("input"));
    await wrapper.vm.$nextTick();
    expect(confirmButton().disabled).toBe(true);
    reasonBox.value = "  No access to the attic today  ";
    reasonBox.dispatchEvent(new Event("input"));
    await wrapper.vm.$nextTick();
    expect(confirmButton().disabled).toBe(false);
    confirmButton().click();
    expect(wrapper.emitted("confirm")).toEqual([["No access to the attic today"]]);
    wrapper.unmount();
  });
});
