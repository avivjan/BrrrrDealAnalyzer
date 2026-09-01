// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { reactive } from "vue";

import DealInputsForm from "./DealInputsForm.vue";
import {
  DEFAULT_CASH_RESERVE,
  DEFAULT_LTV_PERCENT,
  DEFAULT_REFI_POINTS,
  createEmptyDealForm,
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
const FIELD_STUBS = ["MoneyInput", "NumberInput", "SliderField"] as const;

const stubs = {
  MoneyInput: fieldStub("MoneyInput"),
  NumberInput: fieldStub("NumberInput"),
  SliderField: fieldStub("SliderField"),
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
    it("renders the BRRRR refinance + rental fields for a BRRRR deal", () => {
      const wrapper = mountForm(createEmptyDealForm("BRRRR"), "BRRRR");
      const rendered = labels(wrapper);

      // Shared
      expect(rendered).toContain("Purchase Price");
      expect(rendered).toContain("Closing Costs (Buy)");
      expect(rendered).toContain("Annual Taxes");
      // BRRRR-only
      expect(rendered).toContain("ARV");
      expect(rendered).toContain("LTV");
      expect(rendered).toContain("Refi Points");
      expect(rendered).toContain("Cash Reserve (paydown at refi)");
      expect(rendered).toContain("Monthly Rent");
      expect(rendered).toContain("Vacancy");
      expect(rendered).toContain("Prop. Mgmt");
      // FLIP-only must be absent
      expect(rendered).not.toContain("Projected Sale Price");
      expect(rendered).not.toContain("Holding Time");
      expect(rendered).not.toContain("Monthly Utilities");

      expect(wrapper.text()).toContain("Refinance (BRRRR)");
      expect(wrapper.text()).not.toContain("Flip Strategy");
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
      expect(wrapper.text()).not.toContain("Refinance (BRRRR)");
    });

    it("renders without crashing on a sparse deal missing most keys", () => {
      const sparse: DealInputModel = { deal_type: "BRRRR", address: "1 Main St" };
      const wrapper = mountForm(sparse, "BRRRR");
      expect(labels(wrapper)).toContain("Purchase Price");
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
      monthsUntilRefi: "6.0",
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

    /** The value a labelled input is actually bound to. */
    const boundValue = (
      wrapper: ReturnType<typeof mountForm>,
      label: string,
    ) => {
      const target = FIELD_STUBS.flatMap((name) =>
        wrapper.findAllComponents({ name }),
      ).find((c) => c.props("label") === label);
      expect(target, `no input labelled "${label}"`).toBeTruthy();
      return target!.props("modelValue");
    };

    it.each([
      ["Purchase Price", 200],
      ["Rehab Cost", 50],
      ["Contingency", 10],
      ["Closing Costs (Buy)", 5],
      ["Down Payment", 20],
      ["Points", 2],
      ["Interest Rate", 11],
      ["ARV", 320],
      ["Refi Points", 1.5],
      ["Monthly Rent", 2600],
      ["Annual Taxes", 3600],
      ["Annual Insurance", 1200],
      ["Vacancy", 5],
      ["Prop. Mgmt", 8],
      ["Loan Term", 30],
    ])("BRRRR: %s is populated, not blank", (label, expected) => {
      expect(boundValue(mountForm(savedBrrrr(), "BRRRR"), label)).toBe(expected);
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
      expect(boundValue(mountForm(savedBrrrr(), "BRRRR"), "Cash Reserve (paydown at refi)")).toBe(0);
    });

    it("leaves a genuinely absent field blank", () => {
      const partial = { ...(savedBrrrr() as any), rehabCost: null, closingCostsBuy: "" };
      const wrapper = mountForm(partial, "BRRRR");
      expect(boundValue(wrapper, "Rehab Cost")).toBeNull();
      expect(boundValue(wrapper, "Closing Costs (Buy)")).toBeNull();
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

      await emitFrom(wrapper, "Closing Costs (Buy)", null);

      expect(deal.closingCostsBuy).toBeUndefined();
    });

    it("falls back to the documented default when a defaulted field is cleared", async () => {
      const deal = reactive(createEmptyDealForm("BRRRR"));
      const wrapper = mountForm(deal, "BRRRR");

      await emitFrom(wrapper, "Refi Points", null);
      await emitFrom(wrapper, "Cash Reserve (paydown at refi)", null);
      await emitFrom(wrapper, "LTV", null);

      expect(deal.refiPoints).toBe(DEFAULT_REFI_POINTS);
      expect(deal.cashReserve).toBe(DEFAULT_CASH_RESERVE);
      expect(deal.ltv_as_precent).toBe(DEFAULT_LTV_PERCENT);
    });

    it("fills the three selling-cost fields from Quick Defaults", async () => {
      const deal = reactive(createEmptyDealForm("FLIP"));
      const wrapper = mountForm(deal, "FLIP");

      await wrapper.find("button").trigger("click");

      expect(deal.buyerAgentSellingFee).toBe(3);
      expect(deal.sellerAgentSellingFee).toBe(3);
      expect(deal.sellingClosingCosts).toBe(5);
    });

    it("toggles use_HM_for_rehab through the switch", async () => {
      const deal = reactive(createEmptyDealForm("BRRRR"));
      const wrapper = mountForm(deal, "BRRRR");

      await wrapper
        .findComponent({ name: "ToggleSwitch" })
        .vm.$emit("update:modelValue", true);

      expect(deal.use_HM_for_rehab).toBe(true);
    });
  });

  describe("surface variant — each host keeps its exact prior look", () => {
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
      expect(card().find("section").classes()).toContain("bg-white");
      expect(panel().find("section").classes()).toContain("bg-gray-50");
    });

    it("reproduces the section spacing the parent containers used to supply", () => {
      // Analyze page container was `space-y-8`; the modal container `space-y-6`.
      expect(card().find(":first-child").classes()).toContain("space-y-8");
      expect(panel().find(":first-child").classes()).toContain("space-y-6");
    });

    it("keeps the page's flat Rehab/Contingency layout and the modal's paired grid", () => {
      const brrrCard = mount(DealInputsForm, {
        props: { deal: createEmptyDealForm("BRRRR"), dealType: "BRRRR" as const },
        global: { stubs },
      });
      const brrrPanel = mount(DealInputsForm, {
        props: {
          deal: createEmptyDealForm("BRRRR"),
          dealType: "BRRRR" as const,
          surface: "panel" as const,
        },
        global: { stubs },
      });
      // The wrapper around Rehab Cost + Contingency: dissolved on the page
      // (`contents`), a real 2-col grid in the modal.
      expect(brrrCard.html()).toContain('class="contents"');
      expect(brrrPanel.html()).toContain("grid grid-cols-2 gap-2");
    });

    it("keeps each host's selling-costs heading and box style", () => {
      expect(card().text()).toContain("Selling Costs");
      expect(card().text()).not.toContain("Selling Costs Breakdown");
      expect(panel().text()).toContain("Selling Costs Breakdown");
    });
  });
});
