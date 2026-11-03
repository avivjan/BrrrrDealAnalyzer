// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { reactive } from "vue";

import BuySection from "./BuySection.vue";
import { createEmptyDealForm } from "../../../utils/dealUtils";
import type { DealInputModel } from "../../../types";

/**
 * The pencil on the Seller Tax Credit, end to end through the REAL `AutoFigure`: type the
 * credit off the settlement statement and it overrides the proration, and this year's tax bill
 * (the one shared field, cloned here) follows: it becomes the bill whose proration gives that
 * credit. The money inputs are stubbed as in `DealInputsForm.test.ts`; the clone is read
 * through its stub.
 */
const fieldStub = (name: string) => ({ name, props: ["modelValue", "label"], emits: ["update:modelValue"], template: `<div :data-label="label" />` });
const stubs = {
  MoneyInput: fieldStub("MoneyInput"),
  NumberInput: fieldStub("NumberInput"),
  AutoDefaultMoneyInput: {
    name: "AutoDefaultMoneyInput",
    props: ["modelValue", "label", "computedDefault", "estimateExplanationLines"],
    emits: ["update:modelValue"],
    template: `<div :data-label="label" />`,
  },
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

  it("typing the credit from the settlement statement overrides the proration and updates the tax bill to match", async () => {
    const deal = reactive({ ...createEmptyDealForm("BRRRR"), buyClosingDate: "2026-01-10", annual_property_taxes: 3600 });
    const wrapper = mountBuy(deal);
    await sellerTaxCreditFigure(wrapper).find('[data-part="edit"]').trigger("click");
    const box = sellerTaxCreditFigure(wrapper).find('[data-part="edit-input"]');
    await box.setValue("177.53");
    await box.trigger("keydown", { key: "Enter" });

    expect(deal.sellerTaxCreditAtPurchaseClosing).toBe(177.53);
    // 177.53 × 365 ÷ 9 seller days = the bill whose proration gives that credit.
    expect(deal.annual_property_taxes).toBe(7199.83);
    expect(annualTaxesClone(wrapper).props("modelValue")).toBe(7199.83);
    expect(sellerTaxCreditFigure(wrapper).find('[data-part="value"]').text()).toBe("$177.53");
    expect(wrapper.find('[data-testid="form.field.sellerTaxCreditAtPurchaseClosing"]').text()).toContain("the proration gives $177.53");

    await wrapper.find('[data-testid="form.field.sellerTaxCreditAtPurchaseClosing"] [data-part="reset"]').trigger("click");
    expect(deal.sellerTaxCreditAtPurchaseClosing).toBeNull();
    expect(deal.annual_property_taxes).toBe(7199.83); // "auto" only drops the typed credit; the bill stays
    expect(sellerTaxCreditFigure(wrapper).find('[data-part="value"]').text()).toBe("$177.53");
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
    expect(deal.annual_property_taxes).toBe(7199.95); // 335.34 × 365 ÷ 17 days the buyer owes back
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

describe("BuySection — the two mandatory dates", () => {
  const mountWithErrors = (deal: DealInputModel, fieldErrorMessages: Record<string, string>) =>
    mount(BuySection, { props: { deal, surface: "card", fieldErrorMessages }, global: { stubs } });

  it("writes the typed contract date to the deal", async () => {
    const deal = reactive({ ...createEmptyDealForm("BRRRR"), contractDate: "2026-01-03", buyClosingDate: "2026-01-10" });
    const wrapper = mountBuy(deal);
    const contractDateInput = wrapper.find('[data-testid="form.field.contractDate"] input');
    expect((contractDateInput.element as HTMLInputElement).value).toBe("2026-01-03");
    await contractDateInput.setValue("2026-01-05");
    await contractDateInput.trigger("change");
    expect(deal.contractDate).toBe("2026-01-05");
    expect(deal.buyClosingDate).toBe("2026-01-10"); // typed by hand (not contract + 10): it stays
  });

  it("moves a closing date still on its default to the new contract date + 10", async () => {
    const deal = reactive({ ...createEmptyDealForm("BRRRR"), contractDate: "2026-01-03", buyClosingDate: "2026-01-13" });
    const contractDateInput = mountBuy(deal).find('[data-testid="form.field.contractDate"] input');
    await contractDateInput.setValue("2026-02-20");
    await contractDateInput.trigger("change");
    expect(deal.buyClosingDate).toBe("2026-03-02");
    await contractDateInput.setValue("2026-03-01");
    await contractDateInput.trigger("change");
    expect(deal.buyClosingDate).toBe("2026-03-11"); // still following
  });

  it("fills an empty closing date from the contract date, and keeps one typed by hand", async () => {
    const deal = reactive({ ...createEmptyDealForm("BRRRR"), contractDate: null, buyClosingDate: null });
    const wrapper = mountBuy(deal);
    const contractDateInput = wrapper.find('[data-testid="form.field.contractDate"] input');
    await contractDateInput.setValue("2026-05-01");
    await contractDateInput.trigger("change");
    expect(deal.buyClosingDate).toBe("2026-05-11");

    const closingDateInput = wrapper.find('[data-testid="form.field.buyClosingDate"] input');
    await closingDateInput.setValue("2026-05-20");
    await closingDateInput.trigger("change");
    await contractDateInput.setValue("2026-05-05");
    await contractDateInput.trigger("change");
    expect(deal.buyClosingDate).toBe("2026-05-20");
  });

  it("turns a wrong date red with its message", () => {
    const deal = reactive({ ...createEmptyDealForm("BRRRR"), contractDate: "2026-01-11", buyClosingDate: "2026-01-10" });
    const wrapper = mountWithErrors(deal, { contractDate: "Contract date must be on or before the buy closing date." });
    const contractDateField = wrapper.find('[data-testid="form.field.contractDate"]');
    expect(contractDateField.find("input").classes()).toContain("ui-input-invalid");
    expect(contractDateField.find("input").attributes("aria-invalid")).toBe("true");
    expect(contractDateField.find('[data-part="error-message"]').text()).toBe("Contract date must be on or before the buy closing date.");
    expect(wrapper.find('[data-testid="form.field.buyClosingDate"] [data-part="error-message"]').exists()).toBe(false);
  });
});

describe("BuySection — the insurance bill at purchase and the closing-cost estimates", () => {
  const estimateExplanationLinesOf = (wrapper: ReturnType<typeof mountBuy>, label: string) =>
    wrapper.findAllComponents({ name: "AutoDefaultMoneyInput" }).find((c) => c.props("label") === label)!.props("estimateExplanationLines");

  it("holds the insurance bill at purchase and where it is paid", () => {
    const wrapper = mountBuy(reactive({ ...createEmptyDealForm("BRRRR"), annual_insurance: 1200 }));
    expect(wrapper.findAllComponents({ name: "MoneyInput" }).find((c) => c.props("label") === "Insurance Bill at Purchase")!.props("modelValue")).toBe(1200);
    expect(wrapper.find('[data-testid="form.field.insurancePurchaseBillPaymentTiming"] select').exists()).toBe(true);
  });

  it("explains the Florida title estimate under its input: $1,540 on a $100k purchase with a $123k loan, we pay all", () => {
    const deal = reactive({ ...createEmptyDealForm("BRRRR"), purchasePrice: 100, down_payment: 0, constructionLoanBudget: 23, titleModeBuy: "we_pay_all" as const });
    const wrapper = mountBuy(deal);
    const titleInput = wrapper.findAllComponents({ name: "AutoDefaultMoneyInput" }).find((c) => c.props("label") === "Title & Escrow / Settlement")!;
    expect(titleInput.props("computedDefault")).toBeCloseTo(1540, 10);
    expect(estimateExplanationLinesOf(wrapper, "Title & Escrow / Settlement")).toEqual([
      "Office fees $600: $350 settlement + $150 title search + $100 municipal lien search",
      "Owner's policy $575: FL promulgated rate (F.A.C. 69O-186.003), $100,000 ÷ $1,000 × $5.75",
      "Lender's policy $365: $250 endorsements (ALTA 8.1, Form 9, simultaneous issue) + $5.00 per $1,000 of the $23,000 loan above the price",
    ]);
    expect(wrapper.find('[data-testid="form.auto.wePayAllExtraClosingCost"]').text()).toContain("owner's title policy + 0.70% deed transfer tax");
  });

  it("explains the recording estimate under its input with the deal's numbers", () => {
    const deal = reactive({ ...createEmptyDealForm("BRRRR"), purchasePrice: 100, down_payment: 0, constructionLoanBudget: 23 });
    expect(estimateExplanationLinesOf(mountBuy(deal), "Recording & Transfer")[0]).toBe("$250 + 0.55% × $123,000 + $0 = $926.50");
  });
});

describe("BuySection — who pays this year's tax bill", () => {
  const taxBillSelect = (wrapper: ReturnType<typeof mountBuy>) => wrapper.find('[data-testid="form.field.sellerPaidCurrentYearTaxes"] select');

  it("offers the three choices, on auto by the closing month", () => {
    const wrapper = mountBuy(reactive({ ...createEmptyDealForm("BRRRR"), buyClosingDate: "2026-07-01", annual_property_taxes: 3600 }));
    expect(taxBillSelect(wrapper).findAll("option").map((option) => option.text())).toEqual([
      "Seller already paid / pays it at closing (we reimburse our days)",
      "We pay it at closing (seller credits their days)",
      "We pay it in November, outside closing (POC)",
    ]);
    expect((taxBillSelect(wrapper).element as HTMLSelectElement).value).toBe("we_pay_in_november_outside_closing");
    expect(wrapper.find('[data-testid="form.field.sellerPaidCurrentYearTaxes"] [data-part="auto"]').exists()).toBe(true);
  });

  it("writes both stored fields for each choice, and auto resets them", async () => {
    const deal = reactive({ ...createEmptyDealForm("BRRRR"), buyClosingDate: "2026-11-20", annual_property_taxes: 3600 });
    const wrapper = mountBuy(deal);
    await taxBillSelect(wrapper).setValue("we_pay_at_purchase_closing");
    expect([deal.buyerPaysCurrentYearTaxBillAtPurchaseClosing, deal.sellerPaidCurrentYearTaxes]).toEqual([true, null]);
    expect(wrapper.find('[data-testid="form.field.sellerPaidCurrentYearTaxes"] [data-part="hint"]').text()).toContain("$3,456");
    expect(sellerTaxCreditFigure(wrapper).find('[data-part="value"]').text()).toBe("$3,185.75");
    await taxBillSelect(wrapper).setValue("seller_paid_or_pays_at_closing");
    expect([deal.buyerPaysCurrentYearTaxBillAtPurchaseClosing, deal.sellerPaidCurrentYearTaxes]).toEqual([false, true]);
    await taxBillSelect(wrapper).setValue("we_pay_in_november_outside_closing");
    expect([deal.buyerPaysCurrentYearTaxBillAtPurchaseClosing, deal.sellerPaidCurrentYearTaxes]).toEqual([false, false]);
    await wrapper.find('[data-testid="form.field.sellerPaidCurrentYearTaxes"] [data-part="reset"]').trigger("click");
    expect([deal.buyerPaysCurrentYearTaxBillAtPurchaseClosing, deal.sellerPaidCurrentYearTaxes]).toEqual([false, null]);
  });
});

describe("BuySection — the assignment fee", () => {
  it("sits under the purchase price and shows the total the lender finances", async () => {
    const deal = reactive({ ...createEmptyDealForm("BRRRR"), purchasePrice: 200 });
    const wrapper = mountBuy(deal);
    const moneyLabels = wrapper.findAllComponents({ name: "MoneyInput" }).map((input) => input.props("label"));
    expect(moneyLabels.indexOf("Assignment Fee")).toBe(moneyLabels.indexOf("Purchase Price") + 1);
    const assignmentFee = wrapper.findAllComponents({ name: "MoneyInput" }).find((input) => input.props("label") === "Assignment Fee")!;
    await assignmentFee.vm.$emit("update:modelValue", 15000);
    expect(deal.assignmentFee).toBe(15000);
  });
});
