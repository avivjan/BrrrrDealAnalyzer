import { describe, expect, it } from "vitest";

import { createEmptyDealForm, validateDealInputs } from "./dealUtils";
import { dealInputErrorMessageByFieldKey, hasInvalidDealInput, validateDealInputFields } from "./dealInputValidation";
import { DEAL_INPUT_FIELD_KEYS_BY_PHASE_TAB, phaseTabForDealInputField } from "../config/dealInputPhaseTabs";

/** A BRRRR form that clears every rule. */
const validBrrrr = () => ({ ...createEmptyDealForm("BRRRR"), purchasePrice: 200, arv_in_thousands: 320, rent: 2600 });
const validFlip = () => ({ ...createEmptyDealForm("FLIP"), purchasePrice: 200, salePrice: 320 });

describe("validateDealInputFields", () => {
  it("passes a filled-in BRRRR and a filled-in FLIP", () => {
    expect(validateDealInputFields(validBrrrr(), "BRRRR")).toEqual([]);
    expect(validateDealInputFields(validFlip(), "FLIP")).toEqual([]);
  });

  it("reports the blank required fields of a new deal as missing, on their tab", () => {
    expect(validateDealInputFields(createEmptyDealForm("BRRRR"), "BRRRR")).toEqual([
      { fieldKey: "purchasePrice", kind: "missing", message: "Purchase price (in thousands) must be greater than 0.", phaseTabLabel: "Buy" },
      { fieldKey: "arv_in_thousands", kind: "missing", message: "ARV (in thousands) must be greater than 0.", phaseTabLabel: "Refinance" },
      { fieldKey: "rent", kind: "missing", message: "Rent must be greater than 0.", phaseTabLabel: "Rent & Holding" },
    ]);
    expect(validateDealInputFields(createEmptyDealForm("FLIP"), "FLIP")).toEqual([
      { fieldKey: "purchasePrice", kind: "missing", message: "Purchase price (in thousands) must be greater than 0.", phaseTabLabel: "Buy & Rehab" },
      { fieldKey: "salePrice", kind: "missing", message: "Sale Price (ARV) must be greater than 0.", phaseTabLabel: "Flip Strategy" },
    ]);
  });

  describe("the lowest ARV", () => {
    it("is invalid above the ARV, and names the Refinance tab", () => {
      expect(validateDealInputFields({ ...validBrrrr(), lowestArv: 400 }, "BRRRR")).toEqual([
        { fieldKey: "lowestArv", kind: "invalid", message: "Lowest ARV cannot exceed ARV.", phaseTabLabel: "Refinance" },
      ]);
    });

    it("may equal the ARV", () => {
      expect(validateDealInputFields({ ...validBrrrr(), lowestArv: 320 }, "BRRRR")).toEqual([]);
    });

    it("must be positive", () => {
      expect(validateDealInputFields({ ...validBrrrr(), lowestArv: 0 }, "BRRRR").map((e) => e.message)).toEqual(["Lowest ARV must be greater than 0."]);
    });

    it("is only compared against a known ARV, like the backend", () => {
      const errors = validateDealInputFields({ ...validBrrrr(), arv_in_thousands: 0, lowestArv: 250 }, "BRRRR");
      expect(errors.map((e) => e.message)).toEqual(["ARV (in thousands) must be greater than 0."]);
    });

    it("means the formula while null", () => {
      expect(validateDealInputFields({ ...validBrrrr(), lowestArv: null }, "BRRRR")).toEqual([]);
    });
  });

  describe("the rules with no client mirror before", () => {
    it("rejects a cleared LTV, which the backend would 422", () => {
      expect(validateDealInputFields({ ...validBrrrr(), ltv_as_precent: undefined }, "BRRRR")).toEqual([
        { fieldKey: "ltv_as_precent", kind: "invalid", message: "LTV is required.", phaseTabLabel: "Refinance" },
      ]);
    });

    it("rejects a loan term under a year", () => {
      expect(validateDealInputFields({ ...validBrrrr(), loanTermYears: 0 }, "BRRRR").map((e) => e.message)).toEqual(["Loan term must be at least 1 year."]);
    });

    it("bounds the four operating percentages", () => {
      const deal = { ...validBrrrr(), vacancyPercent: 101, property_managment_fee_precentages_from_rent: -1, maintenancePercent: 150, capexPercent: 200 };
      expect(validateDealInputFields(deal, "BRRRR").map((e) => [e.fieldKey, e.phaseTabLabel])).toEqual([
        ["vacancyPercent", "Rent & Holding"],
        ["property_managment_fee_precentages_from_rent", "Rent & Holding"],
        ["maintenancePercent", "Rent & Holding"],
        ["capexPercent", "Rent & Holding"],
      ]);
    });
  });

  it("marks every range and sign rule as invalid on the tab that holds the field", () => {
    const deal = {
      ...validBrrrr(),
      rehabCost: -1, rehabContingency: 101, down_payment: 101, hmlPoints: -1, HMLInterestRate: 101,
      annual_property_taxes: -1, annual_insurance: -1, montly_hoa: -1,
      ltv_as_precent: 0, refiPoints: 101, appraisalFee: -1, constructionLoanBudget: -1, daysUntilRented: -1,
      interestRate: 101, daysUntilRefi: 0,
    };
    const errors = validateDealInputFields(deal, "BRRRR");
    expect(errors.every((e) => e.kind === "invalid")).toBe(true);
    expect(errors.map((e) => `${e.fieldKey}@${e.phaseTabLabel}`)).toEqual([
      "rehabCost@Rehab", "rehabContingency@Rehab", "down_payment@Buy", "hmlPoints@Buy", "HMLInterestRate@Buy",
      "annual_property_taxes@Rent & Holding", "annual_insurance@Rent & Holding", "montly_hoa@Rent & Holding",
      "ltv_as_precent@Refinance", "refiPoints@Refinance", "appraisalFee@Refinance", "constructionLoanBudget@Rehab",
      "daysUntilRented@Rent & Holding", "interestRate@Refinance", "daysUntilRefi@Refinance",
    ]);
  });

  it("marks the FLIP rules on their tabs, with a zero holding time invalid rather than missing", () => {
    const deal = { ...validFlip(), holdingTime: 0, closingCostsBuy: -5, buyerAgentSellingFee: 101, sellingClosingCosts: -1, monthly_utilities: -1, capitalGainsTax: 101 };
    expect(validateDealInputFields(deal, "FLIP").map((e) => `${e.fieldKey}:${e.kind}@${e.phaseTabLabel}`)).toEqual([
      "closingCostsBuy:invalid@Buy & Rehab",
      "holdingTime:invalid@Flip Strategy",
      "buyerAgentSellingFee:invalid@Flip Strategy",
      "sellingClosingCosts:invalid@Flip Strategy",
      "monthly_utilities:invalid@Expenses",
      "capitalGainsTax:invalid@Flip Strategy",
    ]);
  });

  it("reads a saved deal's string numbers", () => {
    const errors = validateDealInputFields({ ...validBrrrr(), arv_in_thousands: "320.00", lowestArv: "400.0000" } as never, "BRRRR");
    expect(errors.map((e) => e.message)).toEqual(["Lowest ARV cannot exceed ARV."]);
  });
});

describe("validateDealInputs (the message-only view)", () => {
  it("lists the same messages in the same order", () => {
    const deal = { ...createEmptyDealForm("BRRRR"), lowestArv: 5, arv_in_thousands: 1 };
    expect(validateDealInputs(deal, "BRRRR")).toEqual(validateDealInputFields(deal, "BRRRR").map((e) => e.message));
  });
});

describe("dealInputErrorMessageByFieldKey", () => {
  it("keeps the invalid messages only, one per field", () => {
    const deal = { ...createEmptyDealForm("BRRRR"), arv_in_thousands: 320, lowestArv: 400, down_payment: 101 };
    expect(dealInputErrorMessageByFieldKey(deal, "BRRRR")).toEqual({
      lowestArv: "Lowest ARV cannot exceed ARV.",
      down_payment: "Down payment percentage must be between 0% and 100%.",
    });
  });
});

describe("hasInvalidDealInput", () => {
  it("is false for a deal that is only missing its required fields", () => {
    expect(hasInvalidDealInput(validateDealInputFields(createEmptyDealForm("BRRRR"), "BRRRR"))).toBe(false);
    expect(hasInvalidDealInput(validateDealInputFields({ ...validBrrrr(), lowestArv: 400 }, "BRRRR"))).toBe(true);
  });
});

describe("the phase tab map", () => {
  it("knows a home tab for every field the validator can name", () => {
    const brrrrKeys = [...DEAL_INPUT_FIELD_KEYS_BY_PHASE_TAB.buy, ...DEAL_INPUT_FIELD_KEYS_BY_PHASE_TAB.rehab, ...DEAL_INPUT_FIELD_KEYS_BY_PHASE_TAB.rentHolding, ...DEAL_INPUT_FIELD_KEYS_BY_PHASE_TAB.refinance];
    expect(new Set(brrrrKeys).size).toBe(brrrrKeys.length);
    expect(phaseTabForDealInputField("lowestArv", "BRRRR")?.key).toBe("refinance");
    expect(phaseTabForDealInputField("holdingTime", "FLIP")?.key).toBe("flipStrategy");
    expect(phaseTabForDealInputField("holdingTime", "BRRRR")).toBeNull();
  });
});
