// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { reactive } from "vue";

import RefinanceSection from "./RefinanceSection.vue";
import { createEmptyDealForm } from "../../../utils/dealUtils";
import type { DealInputModel } from "../../../types";

const fieldStub = (name: string) => ({ name, props: ["modelValue", "label"], emits: ["update:modelValue"], template: `<div :data-label="label" />` });
const stubs = {
  MoneyInput: fieldStub("MoneyInput"),
  NumberInput: fieldStub("NumberInput"),
  SliderField: fieldStub("SliderField"),
  DaysOrDateField: fieldStub("DaysOrDateField"),
  PresetSelectInput: fieldStub("PresetSelectInput"),
  AutoDefaultMoneyInput: {
    name: "AutoDefaultMoneyInput",
    props: ["modelValue", "label", "computedDefault", "estimateExplanationLines"],
    emits: ["update:modelValue"],
    template: `<div :data-label="label" />`,
  },
  InputInfo: { name: "InputInfo", props: ["content"], template: `<i class="input-info" />` },
};

const mountRefinance = (deal: DealInputModel) => mount(RefinanceSection, { props: { deal, surface: "card" }, global: { stubs } });
const autoDefaultInput = (wrapper: ReturnType<typeof mountRefinance>, label: string) =>
  wrapper.findAllComponents({ name: "AutoDefaultMoneyInput" }).find((c) => c.props("label") === label);

describe("RefinanceSection — the closing-cost estimates explain themselves", () => {
  // ARV $240k × 75% LTV = a $180,000 refi loan.
  const dealWithArv = () => reactive({ ...createEmptyDealForm("BRRRR"), arv_in_thousands: 240, ltv_as_precent: 75 });

  it("explains the refi recording and title defaults with the refi loan", () => {
    const wrapper = mountRefinance(dealWithArv());
    expect(autoDefaultInput(wrapper, "Recording & Transfer (Refi)")!.props("estimateExplanationLines")).toEqual([
      "0.55% × $180,000 refi loan + $250 = $1,240",
      "0.55% = 0.35% doc stamps on the note + 0.20% intangible tax; $250 records the mortgage",
    ]);
    expect(autoDefaultInput(wrapper, "Title & Escrow / Settlement (Refi)")!.props("estimateExplanationLines")).toEqual([
      "$800 + 0.45% × $180,000 refi loan = $1,610",
      "Settlement and search fees and the lender's title policy together",
    ]);
  });

  it("no longer holds the regular-year insurance (it is on Rent & Holding)", () => {
    const wrapper = mountRefinance(dealWithArv());
    expect(autoDefaultInput(wrapper, "Insurance per Month after Refi")).toBeUndefined();
    expect(wrapper.text()).not.toContain("Regular year after the refi");
  });
});
