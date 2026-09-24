/**
 * The phase tabs of `DealInputsForm` and which deal input lives on which tab.
 *
 * Lifted out of the form so the validation layer (`utils/dealInputValidation.ts`) can
 * name the tab a wrong input sits on ("Lowest ARV cannot exceed ARV. — Refinance tab")
 * without importing a component. Every field key here is a `form.field.<key>` testid in
 * `components/deal/brrr/*Section.vue` or the FLIP blocks of `DealInputsForm.vue`.
 * A field that appears twice (Annual Taxes has a clone on the Buy tab) is listed once,
 * on its home tab.
 */
import type { NumericKey } from "../composables/useDealField";

/** One tab per phase of the deal; `key` is also the `data-form-tab` the e2e fixture reads. */
export type PhaseTabKey = "buy" | "rehab" | "rentHolding" | "refinance" | "buyRehab" | "flipStrategy" | "expenses";

export interface PhaseTab {
  key: PhaseTabKey;
  label: string;
  /** PrimeIcons name, the same glyph the section header shows. */
  icon: string;
}

export const BRRRR_PHASE_TABS: readonly PhaseTab[] = [
  { key: "buy", label: "Buy", icon: "pi-home" },
  { key: "rehab", label: "Rehab", icon: "pi-wrench" },
  { key: "rentHolding", label: "Rent & Holding", icon: "pi-key" },
  { key: "refinance", label: "Refinance", icon: "pi-refresh" },
];

export const FLIP_PHASE_TABS: readonly PhaseTab[] = [
  { key: "buyRehab", label: "Buy & Rehab", icon: "pi-home" },
  { key: "flipStrategy", label: "Flip Strategy", icon: "pi-dollar" },
  { key: "expenses", label: "Expenses", icon: "pi-wallet" },
];

export const DEAL_INPUT_FIELD_KEYS_BY_PHASE_TAB: Record<PhaseTabKey, readonly NumericKey[]> = {
  buy: [
    "purchasePrice", "earnestMoneyDeposit", "down_payment", "hmlPoints", "HMLInterestRate",
    "loanChargesBuy", "recordingTransferBuy", "titleEscrowBuy", "onlineNotaryFeeBuy", "otherClosingCostsBuy",
  ],
  rehab: ["rehabCost", "constructionLoanBudget", "rehabContingency", "rehabCushion"],
  rentHolding: [
    "rent", "daysUntilRented", "monthlyUtilitiesUntilRented", "maintenanceBeforeRefi", "appliances",
    "annual_property_taxes", "annual_insurance", "montly_hoa",
    "vacancyPercent", "maintenancePercent", "capexPercent", "property_managment_fee_precentages_from_rent",
  ],
  refinance: [
    "daysUntilRefi", "arv_in_thousands", "lowestArv", "ltv_as_precent", "interestRate", "loanTermYears",
    "loanChargesRefi", "recordingTransferRefi", "titleEscrowRefi", "onlineNotaryFeeRefi", "appraisalFee", "surveyFee",
    "refiUnderwritingFee", "refiPoints", "brokerProcessingFeeRefi", "otherClosingCostsRefi",
    "maintenanceReserve", "vacancyReserve", "capexReserve",
  ],
  buyRehab: ["purchasePrice", "rehabCost", "rehabContingency", "closingCostsBuy", "down_payment", "hmlPoints", "HMLInterestRate"],
  flipStrategy: ["salePrice", "holdingTime", "buyerAgentSellingFee", "sellerAgentSellingFee", "sellingClosingCosts", "capitalGainsTax"],
  expenses: ["annual_property_taxes", "annual_insurance", "montly_hoa", "monthly_utilities"],
};

export function phaseTabsForDealType(dealType: "BRRRR" | "FLIP"): readonly PhaseTab[] {
  return dealType === "BRRRR" ? BRRRR_PHASE_TABS : FLIP_PHASE_TABS;
}

/** The tab that holds `fieldKey` for this deal type, or `null` for a field the form does not render. */
export function phaseTabForDealInputField(fieldKey: NumericKey, dealType: "BRRRR" | "FLIP"): PhaseTab | null {
  return phaseTabsForDealType(dealType).find((tab) => DEAL_INPUT_FIELD_KEYS_BY_PHASE_TAB[tab.key].includes(fieldKey)) ?? null;
}
