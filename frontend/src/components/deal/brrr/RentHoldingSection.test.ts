// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { reactive } from "vue";

import RentHoldingSection from "./RentHoldingSection.vue";
import { createEmptyDealForm } from "../../../utils/dealUtils";
import type { DealInputModel } from "../../../types";

const fieldStub = (name: string) => ({ name, props: ["modelValue", "label"], emits: ["update:modelValue"], template: `<div :data-label="label" />` });
const stubs = {
  MoneyInput: fieldStub("MoneyInput"),
  NumberInput: fieldStub("NumberInput"),
  DaysOrDateField: fieldStub("DaysOrDateField"),
  AutoDefaultMoneyInput: fieldStub("AutoDefaultMoneyInput"),
  InputInfo: { name: "InputInfo", props: ["content"], template: `<i class="input-info" />` },
};
const mountRentHolding = (deal: DealInputModel) => mount(RentHoldingSection, { props: { deal, surface: "card" }, global: { stubs } });

describe("RentHoldingSection — monthly reserves and the regular year after the refi", () => {
  it("offers % or $ on all four monthly reserves", () => {
    const wrapper = mountRentHolding(reactive(createEmptyDealForm("BRRRR")));
    const reserveLabels = wrapper.findAll('[data-ui="percent-of-rent-or-monthly-dollars"]').map((reserve) => reserve.find("[data-label]").attributes("data-label"));
    expect(reserveLabels).toEqual(["Vacancy", "Maintenance", "CapEx", "Prop. Management"]);
  });

  it("writes typed dollars to the reserve's own field and switches back to the percentage", async () => {
    const deal = reactive({ ...createEmptyDealForm("BRRRR"), rent: 1500, vacancyPercent: 5 });
    const wrapper = mountRentHolding(deal);
    const vacancy = wrapper.find('[data-testid="form.field.vacancyPercent"]');
    await vacancy.find('[data-unit="monthlyDollars"]').trigger("click");
    expect(deal.monthlyVacancyReserveDollars).toBe(75);
    await wrapper.findAllComponents({ name: "MoneyInput" }).find((c) => c.props("label") === "Vacancy")!.vm.$emit("update:modelValue", 90);
    expect(deal.monthlyVacancyReserveDollars).toBe(90);
    await wrapper.find('[data-testid="form.field.vacancyPercent"] [data-unit="percentOfRent"]').trigger("click");
    expect(deal.monthlyVacancyReserveDollars).toBeNull();
    expect(deal.vacancyPercent).toBe(6);
  });

  it("holds the 'Regular year after the refi' block and no longer the insurance bill at purchase", () => {
    const wrapper = mountRentHolding(reactive(createEmptyDealForm("BRRRR")));
    expect(wrapper.text()).toContain("Regular year after the refi");
    expect(wrapper.find('[data-testid="form.field.monthlyInsuranceAfterRefi"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="form.auto.monthlyPropertyTaxAfterRefi"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="form.field.annual_insurance"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="form.field.insurancePurchaseBillPaymentTiming"]').exists()).toBe(false);
  });
});
