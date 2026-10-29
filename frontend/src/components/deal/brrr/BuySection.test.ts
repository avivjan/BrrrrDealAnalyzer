// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { reactive } from "vue";

import BuySection from "./BuySection.vue";
import { createEmptyDealForm } from "../../../utils/dealUtils";
import type { DealInputModel } from "../../../types";

/**
 * The pencil on the Seller Tax Credit, end to end through the REAL `AutoFigure`: type the
 * credit off the settlement statement and it overrides the proration, while this year's tax
 * bill (the one shared field, cloned here) stays as typed. The money inputs are stubbed as in
 * `DealInputsForm.test.ts`; the clone is read through its stub.
 */
const fieldStub = (name: string) => ({ name, props: ["modelValue", "label"], emits: ["update:modelValue"], template: `<div :data-label="label" />` });
const stubs = {
  MoneyInput: fieldStub("MoneyInput"),
  NumberInput: fieldStub("NumberInput"),
  AutoDefaultMoneyInput: fieldStub("AutoDefaultMoneyInput"),
  PresetSelectInput: fieldStub("PresetSelectInput"),
  InputInfo: { name: "InputInfo", props: ["content"], template: `<i class="input-info" />` },
};

const mountBuy = (deal: DealInputModel) => mount(BuySection, { props: { deal, surface: "card" }, global: { stubs } });
const sellerTaxCreditFigure = (wrapper: ReturnType<typeof mountBuy>) => wrapper.find('[data-testid="form.auto.sellerTaxCredit"]');
const annualTaxesClone = (wrapper: ReturnType<typeof mountBuy>) =>
  wrapper.findAllComponents({ name: "MoneyInput" }).find((c) => c.props("label") === "Property Tax Bill (this year)")!;

describe("BuySection — the seller tax credit pencil", () => {
  it("shows the credit with a pencil and the tax bill clone beside it", () => {
    const wrapper = mountBuy(reactive({ ...createEmptyDealForm("BRRRR"), buyClosingDate: "2026-01-10", annual_property_taxes: 3600 }));
    expect(sellerTaxCreditFigure(wrapper).find('[data-part="value"]').text()).toBe("$88.77");
    expect(sellerTaxCreditFigure(wrapper).find('[data-part="edit"]').exists()).toBe(true);
    expect(sellerTaxCreditFigure(wrapper).find('[data-part="hint"]').text()).toContain("9 days owned");
    expect(annualTaxesClone(wrapper).props("modelValue")).toBe(3600);
  });

  it("typing the credit from the settlement statement overrides the proration and keeps the tax bill", async () => {
    const deal = reactive({ ...createEmptyDealForm("BRRRR"), buyClosingDate: "2026-01-10", annual_property_taxes: 3600 });
    const wrapper = mountBuy(deal);
    await sellerTaxCreditFigure(wrapper).find('[data-part="edit"]').trigger("click");
    const box = sellerTaxCreditFigure(wrapper).find('[data-part="edit-input"]');
    await box.setValue("177.53");
    await box.trigger("keydown", { key: "Enter" });

    expect(deal.sellerTaxCreditAtPurchaseClosing).toBe(177.53);
    expect(deal.annual_property_taxes).toBe(3600);
    expect(annualTaxesClone(wrapper).props("modelValue")).toBe(3600);
    expect(sellerTaxCreditFigure(wrapper).find('[data-part="value"]').text()).toBe("$177.53");
    expect(wrapper.find('[data-testid="form.field.sellerTaxCreditAtPurchaseClosing"]').text()).toContain("the proration gives $88.77");

    await wrapper.find('[data-testid="form.field.sellerTaxCreditAtPurchaseClosing"] [data-part="reset"]').trigger("click");
    expect(deal.sellerTaxCreditAtPurchaseClosing).toBeNull();
    expect(sellerTaxCreditFigure(wrapper).find('[data-part="value"]').text()).toBe("$88.77");
  });

  it("reads a December reimbursement whatever sign it is typed with", async () => {
    const deal = reactive({ ...createEmptyDealForm("BRRRR"), buyClosingDate: "2026-12-15", annual_property_taxes: 3600 });
    const wrapper = mountBuy(deal);
    expect(sellerTaxCreditFigure(wrapper).find('[data-part="value"]').text()).toBe("-$167.67");
    await sellerTaxCreditFigure(wrapper).find('[data-part="edit"]').trigger("click");
    const box = sellerTaxCreditFigure(wrapper).find('[data-part="edit-input"]');
    await box.setValue("335.34");
    await box.trigger("keydown", { key: "Enter" });
    expect(deal.sellerTaxCreditAtPurchaseClosing).toBe(-335.34);
    expect(deal.annual_property_taxes).toBe(3600);
    expect(sellerTaxCreditFigure(wrapper).find('[data-part="value"]').text()).toBe("-$335.34");
  });

  it("leaves the taxes alone when the edit is abandoned, and hides the pencil on a Jan 1 closing", async () => {
    const deal = reactive({ ...createEmptyDealForm("BRRRR"), buyClosingDate: "2026-07-01", annual_property_taxes: 3600 });
    const wrapper = mountBuy(deal);
    await sellerTaxCreditFigure(wrapper).find('[data-part="edit"]').trigger("click");
    const box = sellerTaxCreditFigure(wrapper).find('[data-part="edit-input"]');
    await box.setValue("999");
    await box.trigger("keydown", { key: "Escape" });
    expect(deal.annual_property_taxes).toBe(3600);
    expect(deal.sellerTaxCreditAtPurchaseClosing).toBeNull();

    const januaryFirst = mountBuy(reactive({ ...createEmptyDealForm("BRRRR"), buyClosingDate: "2026-01-01", annual_property_taxes: 3600 }));
    expect(sellerTaxCreditFigure(januaryFirst).find('[data-part="value"]').text()).toBe("$0");
    expect(sellerTaxCreditFigure(januaryFirst).find('[data-part="edit"]').exists()).toBe(false);
    expect(sellerTaxCreditFigure(januaryFirst).find('[data-part="hint"]').text()).toContain("nothing to prorate");
  });
});
