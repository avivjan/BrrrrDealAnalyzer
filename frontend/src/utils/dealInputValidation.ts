/**
 * Client-side validation of the deal inputs, per field.
 *
 * Mirrors the backend's `validate_brrr_inputs` / `validate_flip_inputs`
 * (`BackEnd/BL/analyze/common/validation.py`), so a payload that passes here is never
 * rejected with a 400 the user cannot see. Two kinds of problem, treated differently
 * by the form and the deal modals:
 *
 * - `invalid` — a value that is wrong (out of range, negative, a lowest ARV above the ARV,
 *   a cleared LTV). The field turns red with the message, and both the analysis and the
 *   autosave pause until it is fixed: the backend rejects the row either way.
 * - `missing` — a required field a brand-new deal legitimately starts at 0 (purchase
 *   price, ARV, rent; sale price on a flip). The board saves those zeros, so a missing
 *   field pauses the analysis only; the tab dot and the Analyze page's list already
 *   point at it.
 *
 * `validateDealInputs` in `dealUtils.ts` is the message-only view of the same list, in
 * the same order, for the Analyze page's rail.
 */
import type { DealInputModel } from "../types";
import type { NumericKey } from "../composables/useDealField";
import { phaseTabForDealInputField } from "../config/dealInputPhaseTabs";

export type DealInputFieldErrorKind = "missing" | "invalid";

export interface DealInputFieldError {
  fieldKey: NumericKey;
  message: string;
  kind: DealInputFieldErrorKind;
  /** The form tab that holds the field, so a message can say where to look. */
  phaseTabLabel: string;
}

/** (field, label) of every dollar line item of the BRRRR lifecycle; `null` = formula default, so skipped. */
const BRRR_NON_NEGATIVE_DOLLAR_FIELDS: ReadonlyArray<[NumericKey, string]> = [
  ["earnestMoneyDeposit", "Earnest money deposit"],
  ["loanChargesBuy", "Loan charges (buy)"],
  ["recordingTransferBuy", "Recording and transfer charges (buy)"],
  ["titleEscrowBuy", "Title and escrow charges (buy)"],
  ["otherClosingCostsBuy", "Other closing costs (buy)"],
  ["onlineNotaryFeeBuy", "Online notary fee (buy)"],
  ["rehabCushion", "Rehab cushion"],
  ["monthlyUtilitiesUntilRented", "Monthly utilities until rented"],
  ["maintenanceBeforeRefi", "Maintenance before refi"],
  ["appliances", "Appliances"],
  ["loanChargesRefi", "Loan charges (refi)"],
  ["recordingTransferRefi", "Recording and transfer charges (refi)"],
  ["titleEscrowRefi", "Title and escrow charges (refi)"],
  ["appraisalFee", "Appraisal fee"],
  ["surveyFee", "Survey fee"],
  ["refiUnderwritingFee", "Refi underwriting fee"],
  ["brokerProcessingFeeRefi", "Broker processing fee (refi)"],
  ["otherClosingCostsRefi", "Other closing costs (refi)"],
  ["onlineNotaryFeeRefi", "Online notary fee (refi)"],
  ["maintenanceReserve", "Maintenance reserve"],
  ["vacancyReserve", "Vacancy reserve"],
  ["capexReserve", "CapEx reserve"],
];

/** A deal field as a number; empty, null, or non-numeric reads as 0 (the backend default). */
function numberOrZero(value: unknown): number {
  if (value == null || value === "") return 0;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

const isOutsidePercentRange = (value: number) => value < 0 || value > 100;

export function validateDealInputFields(deal: DealInputModel, dealType: "BRRRR" | "FLIP"): DealInputFieldError[] {
  const errors: DealInputFieldError[] = [];
  const dealRecord = deal as Record<string, unknown>;
  const numberOf = (fieldKey: NumericKey) => numberOrZero(dealRecord[fieldKey]);
  const report = (fieldKey: NumericKey, kind: DealInputFieldErrorKind, message: string) => {
    errors.push({ fieldKey, kind, message, phaseTabLabel: phaseTabForDealInputField(fieldKey, dealType)?.label ?? "" });
  };
  const reportMissingUnlessPositive = (fieldKey: NumericKey, message: string) => {
    if (numberOf(fieldKey) <= 0) report(fieldKey, "missing", message);
  };
  const reportIfNegative = (fieldKey: NumericKey, message: string) => {
    if (numberOf(fieldKey) < 0) report(fieldKey, "invalid", message);
  };
  const reportIfOutsidePercentRange = (fieldKey: NumericKey, message: string) => {
    if (isOutsidePercentRange(numberOf(fieldKey))) report(fieldKey, "invalid", message);
  };

  reportMissingUnlessPositive("purchasePrice", "Purchase price (in thousands) must be greater than 0.");
  reportIfNegative("rehabCost", "Rehab cost (in thousands) cannot be negative.");
  reportIfOutsidePercentRange("rehabContingency", "Contingency must be between 0% and 100%.");
  reportIfOutsidePercentRange("down_payment", "Down payment percentage must be between 0% and 100%.");
  reportIfOutsidePercentRange("hmlPoints", "HML points must be between 0% and 100%.");
  reportIfOutsidePercentRange("HMLInterestRate", "HML interest rate must be between 0% and 100%.");
  if (dealType === "FLIP") reportIfNegative("closingCostsBuy", "Closing costs (buy) cannot be negative.");
  reportIfNegative("annual_property_taxes", "Annual property taxes cannot be negative.");
  reportIfNegative("annual_insurance", "Annual insurance cannot be negative.");
  reportIfNegative("montly_hoa", "HOA dues cannot be negative.");

  if (dealType === "BRRRR") {
    reportMissingUnlessPositive("arv_in_thousands", "ARV (in thousands) must be greater than 0.");
    reportMissingUnlessPositive("rent", "Rent must be greater than 0.");
    // A cleared LTV is dropped from the payload and the backend rejects the row (422),
    // so an empty box is a wrong value here, not a missing one.
    if (dealRecord.ltv_as_precent == null || dealRecord.ltv_as_precent === "") {
      report("ltv_as_precent", "invalid", "LTV is required.");
    } else if (numberOf("ltv_as_precent") <= 0 || numberOf("ltv_as_precent") > 100) {
      report("ltv_as_precent", "invalid", "LTV must be between 0% and 100%.");
    }
    reportIfOutsidePercentRange("refiPoints", "Broker points must be between 0% and 100%.");
    for (const [fieldKey, label] of BRRR_NON_NEGATIVE_DOLLAR_FIELDS) {
      if (dealRecord[fieldKey] != null && numberOf(fieldKey) < 0) report(fieldKey, "invalid", `${label} cannot be negative.`);
    }
    reportIfNegative("constructionLoanBudget", "Construction loan budget cannot be negative.");
    reportIfNegative("daysUntilRented", "Days until rented cannot be negative.");
    if (dealRecord.lowestArv != null) {
      const lowestArvThousands = numberOf("lowestArv");
      const arvThousands = numberOf("arv_in_thousands");
      if (lowestArvThousands <= 0) report("lowestArv", "invalid", "Lowest ARV must be greater than 0.");
      // Only meaningful once the ARV is known: the backend compares against a positive ARV only.
      else if (arvThousands > 0 && lowestArvThousands > arvThousands) report("lowestArv", "invalid", "Lowest ARV cannot exceed ARV.");
    }
    // The slider's thumb only covers the realistic band, but the typed box is
    // deliberately unclamped so it never rewrites what you meant — which makes
    // this the only thing standing between a typo and a saved 70% mortgage.
    reportIfOutsidePercentRange("interestRate", "Long term interest rate must be between 0% and 100%.");
    if (numberOf("daysUntilRefi") <= 0) report("daysUntilRefi", "invalid", "Days until refi must be greater than 0.");
    if (dealRecord.loanTermYears != null && numberOf("loanTermYears") <= 0) report("loanTermYears", "invalid", "Loan term must be at least 1 year.");
    reportIfOutsidePercentRange("vacancyPercent", "Vacancy percentage must be between 0% and 100%.");
    reportIfOutsidePercentRange("property_managment_fee_precentages_from_rent", "Property management percentage must be between 0% and 100%.");
    reportIfOutsidePercentRange("maintenancePercent", "Maintenance percentage must be between 0% and 100%.");
    reportIfOutsidePercentRange("capexPercent", "CapEx percentage must be between 0% and 100%.");
  } else {
    reportMissingUnlessPositive("salePrice", "Sale Price (ARV) must be greater than 0.");
    if (numberOf("holdingTime") <= 0) report("holdingTime", "invalid", "Holding time must be greater than 0.");
    reportIfOutsidePercentRange("buyerAgentSellingFee", "Buyer agent fee must be between 0% and 100%.");
    reportIfOutsidePercentRange("sellerAgentSellingFee", "Seller agent fee must be between 0% and 100%.");
    reportIfNegative("sellingClosingCosts", "Closing costs cannot be negative.");
    reportIfNegative("monthly_utilities", "Monthly utilities cannot be negative.");
    reportIfOutsidePercentRange("capitalGainsTax", "Capital gains tax rate must be between 0% and 100%.");
  }

  return errors;
}

/** The `invalid` messages keyed by field, for the form to hand each input its own line. */
export function dealInputErrorMessageByFieldKey(deal: DealInputModel, dealType: "BRRRR" | "FLIP"): Partial<Record<NumericKey, string>> {
  const messageByFieldKey: Partial<Record<NumericKey, string>> = {};
  for (const error of validateDealInputFields(deal, dealType)) {
    if (error.kind === "invalid" && messageByFieldKey[error.fieldKey] == null) messageByFieldKey[error.fieldKey] = error.message;
  }
  return messageByFieldKey;
}

export function hasInvalidDealInput(errors: readonly DealInputFieldError[]): boolean {
  return errors.some((error) => error.kind === "invalid");
}
