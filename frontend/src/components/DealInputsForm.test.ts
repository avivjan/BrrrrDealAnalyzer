// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { reactive } from "vue";

import DealInputsForm from "./DealInputsForm.vue";
import {
  BRRR_LIFECYCLE_DEFAULTS,
  DEFAULT_CASH_RESERVE,
  DEFAULT_DAYS_UNTIL_REFI,
  DEFAULT_LTV_PERCENT,
  DEFAULT_REFI_POINTS,
  createEmptyDealForm,
  ensureBrrrLegacyDefaults,
  todayIsoDate,
} from "../utils/dealUtils";
import type { DealInputModel } from "../types";

/**
 * The PrimeVue-backed input primitives are stubbed: this suite is about the
 * shared form's own contract (which fields exist per deal type, and how values
 * are written back), not about PrimeVue's rendering.
 */
const fieldStub = (name: string) => ({
  name,
  props: ["modelValue", "label"],
  emits: ["update:modelValue"],
  template: `<div :data-label="label" />`,
});

/** Stub names that stand in for a labelled numeric input. */
const FIELD_STUBS = [
  "MoneyInput",
  "NumberInput",
  "SliderField",
  "DaysOrDateField",
  "AutoDefaultMoneyInput",
  "PresetSelectInput",
] as const;

const stubs = {
  MoneyInput: fieldStub("MoneyInput"),
  NumberInput: fieldStub("NumberInput"),
  SliderField: fieldStub("SliderField"),
  DaysOrDateField: fieldStub("DaysOrDateField"),
  AutoDefaultMoneyInput: fieldStub("AutoDefaultMoneyInput"),
  PresetSelectInput: fieldStub("PresetSelectInput"),
  InputInfo: { name: "InputInfo", props: ["content"], template: `<i class="input-info" />` },
  AutoFigure: { name: "AutoFigure", props: ["label", "value"], template: `<div class="auto-figure" :data-figure="label" :data-value="value" />` },
  ToggleSwitch: {
    name: "ToggleSwitch",
    props: ["modelValue"],
    emits: ["update:modelValue"],
    template: `<div class="toggle-switch" />`,
  },
};

function mountForm(deal: DealInputModel, dealType: "BRRRR" | "FLIP") {
  return mount(DealInputsForm, {
    props: { deal, dealType },
    global: { stubs },
  });
}

/** Every rendered input's label, in DOM order. */
function labels(wrapper: ReturnType<typeof mountForm>): string[] {
  return wrapper
    .findAll("[data-label]")
    .map((el) => el.attributes("data-label") ?? "");
}

/** The value a labelled input is actually bound to. */
function boundValue(wrapper: ReturnType<typeof mountForm>, label: string) {
  const target = FIELD_STUBS.flatMap((name) =>
    wrapper.findAllComponents({ name }),
  ).find((c) => c.props("label") === label);
  expect(target, `no input labelled "${label}"`).toBeTruthy();
  return target!.props("modelValue");
}

/** Find a stubbed input by its label and emit a new value from it. */
async function emitFrom(
  wrapper: ReturnType<typeof mountForm>,
  label: string,
  value: number | null,
) {
  const target = FIELD_STUBS.flatMap((name) =>
    wrapper.findAllComponents({ name }),
  ).find((c) => c.props("label") === label);
  expect(target, `no input labelled "${label}"`).toBeTruthy();
  await target!.vm.$emit("update:modelValue", value);
}

describe("DealInputsForm", () => {
  describe("section visibility", () => {
    it("renders the four lifecycle sections with every BRRRR input", () => {
      const wrapper = mountForm(createEmptyDealForm("BRRRR"), "BRRRR");
      const rendered = labels(wrapper);
      const text = wrapper.text();

      for (const heading of ["Buy", "Rehab", "Rent & Holding", "Refinance"]) expect(text).toContain(heading);
      // Buy
      for (const label of ["Purchase Price", "Earnest Money Deposit", "Down Payment", "Points", "Interest Rate",
                           "Loan Charges", "Recording & Transfer", "Title & Escrow / Settlement", "Other Closing Costs"])
        expect(rendered, label).toContain(label);
      expect(wrapper.find('[data-testid="form.field.buyClosingDate"] input[type="date"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="form.field.titleModeBuy"] select').exists()).toBe(true);
      expect(wrapper.find('[data-testid="form.field.onlineNotaryBuy"] input[type="checkbox"]').exists()).toBe(true);
      // Rehab
      for (const label of ["Actual Rehab Cost", "Construction Loan Budget", "Contingency", "Rehab Cushion"])
        expect(rendered, label).toContain(label);
      // Rent & Holding
      for (const label of ["Monthly Rent", "Until Tenant Occupied", "Utilities until Rented (per month)", "Maintenance before Refi",
                           "Appliances", "Annual Taxes", "Annual Insurance", "Monthly HOA", "Vacancy", "Maint.", "CapEx", "Prop. Mgmt"])
        expect(rendered, label).toContain(label);
      // Refinance
      for (const label of ["Days to Refi", "ARV", "Lowest ARV Possible (stress test)", "LTV", "Long Term Interest Rate", "Loan Term",
                           "Loan Charges (Refi)", "Recording & Transfer (Refi)", "Title & Escrow / Settlement (Refi)", "Other Closing Costs (Refi)",
                           "Appraisal", "Survey", "Underwriting Fee", "Broker Points", "Broker Processing Fee",
                           "Maintenance Reserve", "Vacancy Reserve (1 month rent)", "CapEx Reserve"])
        expect(rendered, label).toContain(label);
      expect(wrapper.find('[data-testid="form.field.onlineNotaryRefi"] input[type="checkbox"]').exists()).toBe(true);
      // Deprecated for BRRRR: the legacy lumps and the hard-money toggle are gone
      expect(rendered).not.toContain("Closing Costs (Buy)");
      expect(rendered).not.toContain("Refi Closing Costs");
      expect(rendered).not.toContain("Cash Reserve (escrowed at refi)");
      expect(wrapper.find('[data-testid="form.hm-toggle"]').exists()).toBe(false);
      // FLIP-only must be absent
      expect(rendered).not.toContain("Projected Sale Price");
      expect(rendered).not.toContain("Holding Time");
      expect(rendered).not.toContain("Monthly Utilities");
      expect(text).not.toContain("Flip Strategy");
    });

    it("shows an auto-calculated figure only once its inputs exist", () => {
      const emptyForm = mountForm(createEmptyDealForm("BRRRR"), "BRRRR");
      const autoFiguresByLabel = (wrapper: ReturnType<typeof mountForm>) =>
        Object.fromEntries(wrapper.findAll("[data-figure]").map((figure) => [figure.attributes("data-figure"), figure.attributes("data-value")]));
      // no purchase price yet -> no cash to close, no hard money cost
      expect(autoFiguresByLabel(emptyForm)["Cash to Close (Buy)"]).toBeUndefined();
      const typedForm = mountForm({ ...createEmptyDealForm("BRRRR"), purchasePrice: 140, arv_in_thousands: 200, rent: 2600 }, "BRRRR");
      expect(Number(autoFiguresByLabel(typedForm)["Cash to Close (Buy)"])).toBeGreaterThan(0);
      expect(Number(autoFiguresByLabel(typedForm)["Total Hard Money Cost"])).toBeGreaterThan(0);
      expect(Number(autoFiguresByLabel(typedForm)["Pre-Refi Rental Income"])).toBe(2600 * 90 / 30);
    });

    it("renders the flip strategy fields for a FLIP deal", () => {
      const wrapper = mountForm(createEmptyDealForm("FLIP"), "FLIP");
      const rendered = labels(wrapper);

      // Shared still present
      expect(rendered).toContain("Purchase Price");
      expect(rendered).toContain("Annual Taxes");
      // FLIP-only
      expect(rendered).toContain("Projected Sale Price");
      expect(rendered).toContain("Holding Time");
      expect(rendered).toContain("Buyer Agent Fee");
      expect(rendered).toContain("Capital Gains Tax Rate");
      expect(rendered).toContain("Monthly Utilities");
      // BRRRR-only must be absent
      expect(rendered).not.toContain("ARV");
      expect(rendered).not.toContain("Monthly Rent");
      expect(rendered).not.toContain("Vacancy");

      expect(wrapper.text()).toContain("Flip Strategy");
      expect(wrapper.text()).not.toContain("Rent & Holding");
      expect(wrapper.find('[data-testid="form.hm-toggle"]').exists()).toBe(true);
    });

    it("renders without crashing on a sparse deal missing most keys", () => {
      const sparse: DealInputModel = { deal_type: "BRRRR", address: "1 Main St" };
      const wrapper = mountForm(sparse, "BRRRR");
      expect(labels(wrapper)).toContain("Purchase Price");
    });
  });

  describe("the phase tabs", () => {
    const boxStyle = (wrapper: ReturnType<typeof mountForm>, tabKey: string) =>
      wrapper.find(`[data-form-tab="${tabKey}"]`).attributes("style") ?? "";
    const isShown = (wrapper: ReturnType<typeof mountForm>, tabKey: string) =>
      !boxStyle(wrapper, tabKey).includes("display: none");
    const tabKeys = (wrapper: ReturnType<typeof mountForm>) =>
      wrapper.findAll('[data-testid^="form.tab."]:not([data-testid$=".needs-input"])').map((el) => el.attributes("data-testid"));

    it("offers one tab per BRRRR phase and opens on Buy", () => {
      const wrapper = mountForm(createEmptyDealForm("BRRRR"), "BRRRR");
      expect(tabKeys(wrapper)).toEqual(["form.tab.buy", "form.tab.rehab", "form.tab.rentHolding", "form.tab.refinance"]);
      expect(isShown(wrapper, "buy")).toBe(true);
      for (const hidden of ["rehab", "rentHolding", "refinance"]) expect(isShown(wrapper, hidden), hidden).toBe(false);
    });

    it("offers one tab per FLIP phase and opens on Buy & Rehab", () => {
      const wrapper = mountForm(createEmptyDealForm("FLIP"), "FLIP");
      expect(tabKeys(wrapper)).toEqual(["form.tab.buyRehab", "form.tab.flipStrategy", "form.tab.expenses"]);
      expect(isShown(wrapper, "buyRehab")).toBe(true);
      expect(isShown(wrapper, "flipStrategy")).toBe(false);
      expect(isShown(wrapper, "expenses")).toBe(false);
    });

    it("shows exactly the clicked phase and keeps the others mounted", async () => {
      const wrapper = mountForm(createEmptyDealForm("BRRRR"), "BRRRR");
      await wrapper.find('[data-testid="form.tab.refinance"]').trigger("click");
      expect(isShown(wrapper, "refinance")).toBe(true);
      expect(isShown(wrapper, "buy")).toBe(false);
      // Still in the DOM: a hidden section's fields keep their state and stay findable.
      expect(labels(wrapper)).toContain("Purchase Price");
      expect(labels(wrapper)).toContain("ARV");
    });

    it("writes a value typed into a hidden phase back to the deal", async () => {
      const deal = reactive(createEmptyDealForm("BRRRR"));
      const wrapper = mountForm(deal, "BRRRR");
      await emitFrom(wrapper, "ARV", 320); // Refinance tab, while Buy is open
      expect(deal.arv_in_thousands).toBe(320);
    });

    it("lands on the first tab of the other strategy when the deal type switches", async () => {
      const wrapper = mountForm(createEmptyDealForm("BRRRR"), "BRRRR");
      await wrapper.find('[data-testid="form.tab.rehab"]').trigger("click");
      await wrapper.setProps({ dealType: "FLIP" });
      expect(tabKeys(wrapper)).toHaveLength(3);
      expect(isShown(wrapper, "buyRehab")).toBe(true);
      expect(isShown(wrapper, "flipStrategy")).toBe(false);
    });

    it("dots every tab whose needed inputs are still empty, and clears the dot as they are typed", async () => {
      const deal = reactive(createEmptyDealForm("BRRRR"));
      const wrapper = mountForm(deal, "BRRRR");
      const dot = (tabKey: string) => wrapper.find(`[data-testid="form.tab.${tabKey}.needs-input"]`).exists();
      for (const tabKey of ["buy", "rehab", "rentHolding", "refinance"]) expect(dot(tabKey), tabKey).toBe(true);

      await emitFrom(wrapper, "Purchase Price", 200);
      await emitFrom(wrapper, "Actual Rehab Cost", 50);
      await emitFrom(wrapper, "ARV", 320);
      expect(dot("buy")).toBe(false);
      expect(dot("rehab")).toBe(false);
      expect(dot("refinance")).toBe(false);
      expect(dot("rentHolding")).toBe(true); // rent, taxes and insurance are all still 0

      await emitFrom(wrapper, "Monthly Rent", 2600);
      await emitFrom(wrapper, "Annual Taxes", 3600);
      expect(dot("rentHolding")).toBe(true); // insurance still missing
      await emitFrom(wrapper, "Annual Insurance", 1200);
      expect(dot("rentHolding")).toBe(false);
    });

    it("dots the FLIP tabs by their own needed inputs", () => {
      const wrapper = mountForm({ ...createEmptyDealForm("FLIP"), purchasePrice: 200, rehabCost: 50 }, "FLIP");
      expect(wrapper.find('[data-testid="form.tab.buyRehab.needs-input"]').exists()).toBe(false);
      expect(wrapper.find('[data-testid="form.tab.flipStrategy.needs-input"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="form.tab.expenses.needs-input"]').exists()).toBe(true);
    });

    it("marks the needed inputs on the fields themselves", () => {
      const needed = (wrapper: ReturnType<typeof mountForm>) =>
        wrapper.findAllComponents({ name: "MoneyInput" }).filter((c) => c.attributes("needed-to-run-analysis") === "true").map((c) => c.props("label"));
      expect(needed(mountForm(createEmptyDealForm("BRRRR"), "BRRRR"))).toEqual(
        ["Purchase Price", "Actual Rehab Cost", "Monthly Rent", "Annual Taxes", "Annual Insurance", "ARV"],
      );
      expect(needed(mountForm(createEmptyDealForm("FLIP"), "FLIP"))).toEqual(
        ["Purchase Price", "Rehab Cost", "Projected Sale Price", "Annual Taxes", "Annual Insurance"],
      );
    });
  });

  describe("populating from a saved deal (API shape)", () => {
    /**
     * A deal as it actually arrives from `/active-deals` and `/bought-deals`:
     * FastAPI serialises every `Decimal` column to a JSON *string*, so money and
     * percentage fields are strings while `int`/`bool` columns are not. Binding
     * these blank was a real regression — the modals showed empty inputs for
     * every saved deal while the analysis results rendered correctly.
     */
    const savedBrrrr = () => ({
      deal_type: "BRRRR" as const,
      address: "2286 Laurel Grove Ln W",
      purchasePrice: "200.00",
      rehabCost: "50.00",
      rehabContingency: "10.00",
      closingCostsBuy: "5.00",
      down_payment: "20.00",
      hmlPoints: "2.00",
      HMLInterestRate: "11.00",
      annual_property_taxes: "3600.00",
      annual_insurance: "1200.00",
      montly_hoa: "0.00",
      arv_in_thousands: "320.00",
      daysUntilRefi: 180,
      closingCostsRefi: "6.00",
      refiPoints: "1.50",
      cashReserve: "0.00",
      loanTermYears: 30,
      ltv_as_precent: "80.00",
      interestRate: "6.75",
      rent: "2600.00",
      vacancyPercent: "5.00",
      property_managment_fee_precentages_from_rent: "8.00",
      maintenancePercent: "5.00",
      capexPercent: "5.00",
      use_HM_for_rehab: true,
      buyClosingDate: "2026-01-10",
      earnestMoneyDeposit: "5000.00",
      loanChargesBuy: "900.00",
      recordingTransferBuy: null,
      titleModeBuy: "we_pay_all",
      titleEscrowBuy: "2200.00",
      onlineNotaryBuy: false,
      onlineNotaryFeeBuy: null,
      otherClosingCostsBuy: "0.00",
      otherClosingCostsBuyNote: "HOA transfer",
      sellerPaidCurrentYearTaxes: null,
      constructionLoanBudget: "55.0000",
      rehabCushion: "5000.00",
      daysUntilRented: 90,
      monthlyUtilitiesUntilRented: "80.00",
      maintenanceBeforeRefi: "500.00",
      appliances: "630.00",
      loanChargesRefi: "200.00",
      recordingTransferRefi: "1075.00",
      titleEscrowRefi: null,
      onlineNotaryRefi: true,
      onlineNotaryFeeRefi: "300.00",
      appraisalFee: "700.00",
      surveyFee: "385.00",
      refiUnderwritingFee: "2240.00",
      brokerProcessingFeeRefi: "395.00",
      otherClosingCostsRefi: "0.00",
      maintenanceReserve: "1500.00",
      vacancyReserve: null,
      capexReserve: "2500.00",
      lowestArv: "280.0000",
    }) as unknown as DealInputModel;

    const savedFlip = () => ({
      deal_type: "FLIP" as const,
      address: "2286 Laurel Grove Ln W",
      purchasePrice: "200.00",
      rehabCost: "50.00",
      rehabContingency: "10.00",
      closingCostsBuy: "5.00",
      down_payment: "20.00",
      hmlPoints: "2.00",
      HMLInterestRate: "11.00",
      annual_property_taxes: "3600.00",
      annual_insurance: "1200.00",
      montly_hoa: "0.00",
      monthly_utilities: "250.00",
      salePrice: "320.00",
      holdingTime: 5,
      buyerAgentSellingFee: "3.00",
      sellerAgentSellingFee: "3.00",
      sellingClosingCosts: "5.00",
      capitalGainsTax: "20.00",
      use_HM_for_rehab: true,
    }) as unknown as DealInputModel;

    it.each([
      ["Purchase Price", 200],
      ["Actual Rehab Cost", 50],
      ["Contingency", 10],
      ["Down Payment", 20],
      ["Points", 2],
      ["Interest Rate", 11],
      ["ARV", 320],
      ["Days to Refi", 180],
      ["Broker Points", 1.5],
      ["Monthly Rent", 2600],
      ["Annual Taxes", 3600],
      ["Annual Insurance", 1200],
      ["Vacancy", 5],
      ["Prop. Mgmt", 8],
      ["Loan Term", 30],
      // lifecycle inputs, strings from the API like every other Decimal
      ["Earnest Money Deposit", 5000],
      ["Loan Charges", 900],
      ["Title & Escrow / Settlement", 2200],
      ["Construction Loan Budget", 55],
      ["Rehab Cushion", 5000],
      ["Until Tenant Occupied", 90],
      ["Utilities until Rented (per month)", 80],
      ["Maintenance before Refi", 500],
      ["Appliances", 630],
      ["Loan Charges (Refi)", 200],
      ["Notary fee", 300],
      ["Recording & Transfer (Refi)", 1075],
      ["Appraisal", 700],
      ["Survey", 385],
      ["Underwriting Fee", 2240],
      ["Broker Processing Fee", 395],
      ["Maintenance Reserve", 1500],
      ["CapEx Reserve", 2500],
      ["Lowest ARV Possible (stress test)", 280],
    ])("BRRRR: %s is populated, not blank", (label, expected) => {
      expect(boundValue(mountForm(savedBrrrr(), "BRRRR"), label)).toBe(expected);
    });

    it("binds the date, the title mode and the checkboxes from the saved deal", () => {
      const wrapper = mountForm(savedBrrrr(), "BRRRR");
      expect(wrapper.find<HTMLInputElement>('[data-testid="form.field.buyClosingDate"] input').element.value).toBe("2026-01-10");
      expect(wrapper.find<HTMLSelectElement>('[data-testid="form.field.titleModeBuy"] select').element.value).toBe("we_pay_all");
      expect(wrapper.find<HTMLInputElement>('[data-testid="form.field.onlineNotaryBuy"] input').element.checked).toBe(false);
      expect(wrapper.find<HTMLInputElement>('[data-testid="form.field.onlineNotaryRefi"] input').element.checked).toBe(true);
    });

    it("leaves a formula-defaulted field null so the formula applies", () => {
      const wrapper = mountForm(savedBrrrr(), "BRRRR");
      expect(boundValue(wrapper, "Recording & Transfer")).toBeNull(); // the first one is Buy
      expect(boundValue(wrapper, "Vacancy Reserve (1 month rent)")).toBeNull();
    });

    it.each([
      ["Purchase Price", 200],
      ["Projected Sale Price", 320],
      ["Holding Time", 5],
      ["Buyer Agent Fee", 3],
      ["Seller Agent Fee", 3],
      ["Closing Costs", 5],
      ["Capital Gains Tax Rate", 20],
      ["Monthly Utilities", 250],
      ["Annual Taxes", 3600],
    ])("FLIP: %s is populated, not blank", (label, expected) => {
      expect(boundValue(mountForm(savedFlip(), "FLIP"), label)).toBe(expected);
    });

    it("shows the deal's own slider values, not the defaults", () => {
      // The dangerous case: a fallback silently replacing real data. This deal
      // is 80% LTV at 6.75%, not the 75% / 6.5% defaults.
      const wrapper = mountForm(savedBrrrr(), "BRRRR");
      expect(boundValue(wrapper, "LTV")).toBe(80);
      expect(boundValue(wrapper, "Long Term Interest Rate")).toBe(6.75);
    });

    it("keeps a real zero rather than falling back", () => {
      expect(boundValue(mountForm(savedBrrrr(), "BRRRR"), "Monthly HOA")).toBe(0);
      expect(boundValue(mountForm(savedBrrrr(), "BRRRR"), "Other Closing Costs")).toBe(0);
    });

    it("leaves a genuinely absent field blank", () => {
      const partial = { ...(savedBrrrr() as any), rehabCost: null, appliances: "" };
      const wrapper = mountForm(partial, "BRRRR");
      expect(boundValue(wrapper, "Actual Rehab Cost")).toBeNull();
      expect(boundValue(wrapper, "Appliances")).toBeNull();
    });

    it("reads a saved deal without mutating it (no autosave trigger on open)", () => {
      const deal = savedBrrrr();
      const before = JSON.stringify(deal);
      mountForm(deal, "BRRRR");
      expect(JSON.stringify(deal)).toBe(before);
    });
  });

  describe("writing values back", () => {
    it("mutates the caller's object in place rather than replacing it", async () => {
      // The card modals drive auto-save from a deep watcher on this exact
      // object, so the reference must survive an edit.
      const deal = reactive(createEmptyDealForm("BRRRR"));
      const wrapper = mountForm(deal, "BRRRR");

      await emitFrom(wrapper, "Purchase Price", 250);

      expect(deal.purchasePrice).toBe(250);
      expect(wrapper.props("deal")).toBe(deal);
      expect(wrapper.emitted()["update:deal"]).toBeUndefined();
    });

    it("clears an optional field to undefined, not 0", async () => {
      // undefined is omitted from the payload so the backend default applies;
      // writing 0 would silently persist a real zero.
      const deal = reactive(createEmptyDealForm("BRRRR"));
      const wrapper = mountForm(deal, "BRRRR");

      await emitFrom(wrapper, "Other Closing Costs", null);

      expect(deal.otherClosingCostsBuy).toBeUndefined();
    });

    it("stores null, not undefined, on a formula-defaulted field so the formula reaches the backend", async () => {
      const deal = reactive({ ...createEmptyDealForm("BRRRR"), recordingTransferBuy: 1234 });
      const wrapper = mountForm(deal, "BRRRR");

      await emitFrom(wrapper, "Recording & Transfer", null);

      expect(deal.recordingTransferBuy).toBeNull();
      expect("recordingTransferBuy" in deal).toBe(true);
    });

    it("seeds the construction budget at rehab + contingency from the first rehab amount, then leaves them independent", async () => {
      const deal = reactive(createEmptyDealForm("BRRRR")); // contingency 10% by default
      const wrapper = mountForm(deal, "BRRRR");

      await emitFrom(wrapper, "Actual Rehab Cost", 40);
      expect(deal.constructionLoanBudget).toBe(44); // 40 × 1.10: the lender finances the contingency

      await emitFrom(wrapper, "Construction Loan Budget", 55);
      expect(deal.rehabCost).toBe(40);
      await emitFrom(wrapper, "Actual Rehab Cost", 42);
      expect(deal.constructionLoanBudget).toBe(55);
    });

    it("seeds the budget at exactly the rehab when there is no contingency, rounded to whole dollars in thousands", async () => {
      const noContingency = reactive({ ...createEmptyDealForm("BRRRR"), rehabContingency: 0 });
      await emitFrom(mountForm(noContingency, "BRRRR"), "Actual Rehab Cost", 40);
      expect(noContingency.constructionLoanBudget).toBe(40);

      const floatingPointTrap = reactive(createEmptyDealForm("BRRRR"));
      await emitFrom(mountForm(floatingPointTrap, "BRRRR"), "Actual Rehab Cost", 50);
      expect(floatingPointTrap.constructionLoanBudget).toBe(55); // not 55.000000000000007
    });

    it("copies a budget typed first to the rehab unchanged (a budget is the lender's number)", async () => {
      const deal = reactive(createEmptyDealForm("BRRRR"));
      await emitFrom(mountForm(deal, "BRRRR"), "Construction Loan Budget", 55);
      expect(deal.rehabCost).toBe(55);
      expect(deal.constructionLoanBudget).toBe(55);
    });

    it("never mirrors into a saved deal that already has a rehab figure", async () => {
      const deal = reactive({ ...createEmptyDealForm("BRRRR"), rehabCost: 50, constructionLoanBudget: 0 });
      const wrapper = mountForm(deal, "BRRRR");

      await emitFrom(wrapper, "Actual Rehab Cost", 52);
      expect(deal.constructionLoanBudget).toBe(0); // a cash rehab stays a cash rehab
    });

    it("writes the date, the title mode and the checkboxes back", async () => {
      const deal = reactive(createEmptyDealForm("BRRRR"));
      const wrapper = mountForm(deal, "BRRRR");

      await wrapper.find('[data-testid="form.field.buyClosingDate"] input').setValue("2026-03-05");
      await wrapper.find('[data-testid="form.field.titleModeBuy"] select').setValue("we_pay_all");
      await wrapper.find('[data-testid="form.field.onlineNotaryBuy"] input').setValue(false);

      expect(deal.buyClosingDate).toBe("2026-03-05");
      expect(deal.titleModeBuy).toBe("we_pay_all");
      expect(deal.onlineNotaryBuy).toBe(false);
    });

    it("shows the notary fee only while the checkbox is on, and writes the closing-cost note back", async () => {
      const deal = reactive(createEmptyDealForm("BRRRR"));
      const wrapper = mountForm(deal, "BRRRR");
      expect(wrapper.find('[data-testid="form.field.onlineNotaryFeeBuy"]').exists()).toBe(true);
      expect(boundValue(wrapper, "Notary fee")).toBeNull(); // null = the $250 default

      await wrapper.find('[data-testid="form.field.onlineNotaryBuy"] input[type="checkbox"]').setValue(false);
      expect(deal.onlineNotaryBuy).toBe(false);
      expect(wrapper.find('[data-testid="form.field.onlineNotaryFeeBuy"]').exists()).toBe(false);

      await wrapper.find('[data-testid="form.field.otherClosingCostsBuyNote"]').setValue("HOA transfer + home warranty");
      expect(deal.otherClosingCostsBuyNote).toBe("HOA transfer + home warranty");
      await wrapper.find('[data-testid="form.field.otherClosingCostsBuyNote"]').setValue("");
      expect(deal.otherClosingCostsBuyNote).toBeNull();
    });

    it("resets the seller-paid-taxes override back to auto", async () => {
      const deal = reactive({ ...createEmptyDealForm("BRRRR"), buyClosingDate: "2026-11-20", annual_property_taxes: 3600 });
      const wrapper = mountForm(deal, "BRRRR");

      await wrapper.find('[data-testid="form.field.sellerPaidCurrentYearTaxes"] input').setValue(true);
      expect(deal.sellerPaidCurrentYearTaxes).toBe(true);
      await wrapper.find('[data-testid="form.field.sellerPaidCurrentYearTaxes"] [data-part="reset"]').trigger("click");
      expect(deal.sellerPaidCurrentYearTaxes).toBeNull();
    });

    it("leaves a defaulted field empty when cleared, instead of snapping back", async () => {
      // This used to assert the opposite, and that was the bug: clearing one of
      // these wrote the default straight back, so deleting the last digit of
      // Refi Points instantly restored 1.5 and you could never retype it.
      // Defaults belong at deal creation and load, not on every keystroke.
      const deal = reactive(createEmptyDealForm("BRRRR"));
      const wrapper = mountForm(deal, "BRRRR");

      await emitFrom(wrapper, "Broker Points", null);
      await emitFrom(wrapper, "Maintenance Reserve", null);
      await emitFrom(wrapper, "LTV", null);
      await emitFrom(wrapper, "Long Term Interest Rate", null);

      expect(deal.refiPoints).toBeUndefined();
      expect(deal.maintenanceReserve).toBeUndefined();
      expect(deal.ltv_as_precent).toBeUndefined();
      expect(deal.interestRate).toBeUndefined();
    });

    it("shows the cleared field as empty, not as the default again", async () => {
      // The other half of the same bug, and the one you actually felt: even
      // with `set` fixed, a default substituted on *read* refilled the box
      // between keystrokes, so LTV and the rate could not be retyped.
      const deal = reactive(createEmptyDealForm("BRRRR"));
      const wrapper = mountForm(deal, "BRRRR");

      await emitFrom(wrapper, "Long Term Interest Rate", null);
      await emitFrom(wrapper, "LTV", null);
      await emitFrom(wrapper, "Broker Points", null);

      expect(boundValue(wrapper, "Long Term Interest Rate")).toBeNull();
      expect(boundValue(wrapper, "LTV")).toBeNull();
      expect(boundValue(wrapper, "Broker Points")).toBeNull();
    });

    it("can be retyped digit by digit without the default fighting back", async () => {
      // The lived complaint: backspacing through "1.5" and typing "2".
      const deal = reactive(createEmptyDealForm("BRRRR"));
      const wrapper = mountForm(deal, "BRRRR");

      await emitFrom(wrapper, "Broker Points", null); // cleared
      expect(deal.refiPoints).toBeUndefined();
      await emitFrom(wrapper, "Broker Points", 2);
      expect(deal.refiPoints).toBe(2);
    });

    it("starts a new deal on the documented defaults", () => {
      const deal = createEmptyDealForm("BRRRR");

      expect(deal.refiPoints).toBe(DEFAULT_REFI_POINTS);
      expect(deal.cashReserve).toBe(DEFAULT_CASH_RESERVE);
      expect(deal.ltv_as_precent).toBe(DEFAULT_LTV_PERCENT);
      expect(deal.daysUntilRefi).toBe(DEFAULT_DAYS_UNTIL_REFI);
      expect(deal.interestRate).toBe(7);
      expect(deal.rehabContingency).toBe(10);
      expect(deal.down_payment).toBe(10);
      expect(deal.hmlPoints).toBe(2);
      expect(deal.HMLInterestRate).toBe(12);
      expect(deal.use_HM_for_rehab).toBe(true);
      expect(deal.capexPercent).toBe(0);
      // Money defaults are in thousands: $5,000 buy / $10,000 refi closing.
      expect(deal.closingCostsBuy).toBe(5);
      expect(deal.closingCostsRefi).toBe(10);
      // Lifecycle defaults (plain dollars unless noted), closing date = today.
      expect(deal.buyClosingDate).toBe(todayIsoDate());
      expect(deal).toMatchObject(BRRR_LIFECYCLE_DEFAULTS);
      expect(deal.recordingTransferBuy).toBeNull();
      expect(deal.lowestArv).toBeNull();
      expect(deal.vacancyReserve).toBeNull();
    });

    it("keeps the legacy 1.5 backfill separate from the new-deal default", () => {
      // A deal saved before `refiPoints` existed must still read 1.5 — that is
      // what is actually in the database. Only *new* deals start at 2.
      const legacy = { deal_type: "BRRRR" as const } as DealInputModel;
      ensureBrrrLegacyDefaults(legacy);

      expect(legacy.refiPoints).toBe(1.5);
      expect(createEmptyDealForm("BRRRR").refiPoints).toBe(2);
    });

    it("fills the three selling-cost fields from Quick Defaults", async () => {
      const deal = reactive(createEmptyDealForm("FLIP"));
      const wrapper = mountForm(deal, "FLIP");

      await wrapper.find('[data-testid="form.quick-defaults"]').trigger("click");

      expect(deal.buyerAgentSellingFee).toBe(3);
      expect(deal.sellerAgentSellingFee).toBe(3);
      expect(deal.sellingClosingCosts).toBe(5);
    });

    it("toggles use_HM_for_rehab through the switch (FLIP; BRRRR uses the construction budget)", async () => {
      const deal = reactive(createEmptyDealForm("FLIP"));
      const wrapper = mountForm(deal, "FLIP");

      await wrapper
        .findComponent({ name: "ToggleSwitch" })
        .vm.$emit("update:modelValue", true);

      expect(deal.use_HM_for_rehab).toBe(true);
    });
  });

  describe("surface variant — each host's contract is exposed as data attributes", () => {
    const card = () =>
      mount(DealInputsForm, {
        props: { deal: createEmptyDealForm("FLIP"), dealType: "FLIP" as const },
        global: { stubs },
      });
    const panel = () =>
      mount(DealInputsForm, {
        props: {
          deal: createEmptyDealForm("FLIP"),
          dealType: "FLIP" as const,
          surface: "panel" as const,
        },
        global: { stubs },
      });

    it("uses white card sections on the page, grey panel sections in modals", () => {
      expect(card().find("section").attributes("data-surface")).toBe("card");
      expect(panel().find("section").attributes("data-surface")).toBe("panel");
    });

    it("exposes the surface on the root so hosts can style spacing", () => {
      expect(
        card().find('[data-testid="form.root"]').attributes("data-surface"),
      ).toBe("card");
      expect(
        panel().find('[data-testid="form.root"]').attributes("data-surface"),
      ).toBe("panel");
    });

    it("keeps the page's flat Rehab/Contingency layout and the modal's paired grid (FLIP)", () => {
      const brrrCard = card();
      const brrrPanel = panel();
      // The wrapper around Rehab Cost + Contingency: dissolved on the page
      // (`contents`), a real 2-col grid in the modal.
      expect(brrrCard.find("[data-layout]").attributes("data-layout")).toBe(
        "flat",
      );
      expect(brrrPanel.find("[data-layout]").attributes("data-layout")).toBe(
        "paired",
      );
    });

    it("keeps each host's selling-costs heading and box style", () => {
      expect(card().text()).toContain("Selling Costs");
      expect(card().text()).not.toContain("Selling Costs Breakdown");
      expect(panel().text()).toContain("Selling Costs Breakdown");
    });
  });
});
