/**
 * The two canonical deal payloads.
 *
 * Field-for-field copies of `BRRRR_PAYLOAD` / `FLIP_PAYLOAD` in
 * `BackEnd/verify_regression.py` — the same fixtures the backend's own golden
 * harness uses, so a diff between the two suites points at one shared set of
 * numbers rather than two drifting ones. Money fields are in *thousands*
 * (`purchasePrice: 200` is $200,000); `rent`, taxes, insurance, HOA and
 * utilities are in real dollars.
 */

export type DealType = 'BRRRR' | 'FLIP';

export const BRRRR_PAYLOAD = {
  deal_type: 'BRRRR',
  purchasePrice: 200,
  rehabCost: 50,
  rehabContingency: 10,
  closingCostsBuy: 5,
  down_payment: 20,
  hmlPoints: 2,
  HMLInterestRate: 11,
  use_HM_for_rehab: true,
  annual_property_taxes: 3600,
  annual_insurance: 1200,
  montly_hoa: 0,
  arv_in_thousands: 320,
  daysUntilRefi: 180,
  closingCostsRefi: 6,
  refiPoints: 1.5,
  cashReserve: 0,
  loanTermYears: 30,
  ltv_as_precent: 75,
  interestRate: 6.5,
  rent: 2600,
  vacancyPercent: 5,
  property_managment_fee_precentages_from_rent: 8,
  maintenancePercent: 5,
  capexPercent: 5,
  address: '1 Shared Form St',
  section: 2,
  stage: 2,
} as const;

export const FLIP_PAYLOAD = {
  ...BRRRR_PAYLOAD,
  deal_type: 'FLIP',
  address: '2 Shared Form Ave',
  salePrice: 320,
  holdingTime: 6,
  buyerAgentSellingFee: 3,
  sellerAgentSellingFee: 3,
  sellingClosingCosts: 5,
  capitalGainsTax: 20,
  monthly_utilities: 250,
} as const;

export function payloadFor(type: DealType): Record<string, unknown> {
  return { ...(type === 'FLIP' ? FLIP_PAYLOAD : BRRRR_PAYLOAD) };
}

/**
 * Money fields the form stores in thousands. `MoneyInput` shows and accepts
 * real dollars for these, so a spec typing `purchasePrice: 200` must type
 * `200000`. Mirrors every `:inThousands="true"` in `DealInputsForm.vue`.
 */
export const IN_THOUSANDS_FIELDS = new Set([
  'purchasePrice',
  'rehabCost',
  'closingCostsBuy',
  'arv_in_thousands',
  'closingCostsRefi',
  'cashReserve',
  'salePrice',
  'sellingClosingCosts',
]);

/**
 * The order the Analyze page's form fields are filled in. Only the inputs the
 * form actually renders for that deal type; `arv_in_thousands` / `salePrice`
 * mirror each other through the watchers in `AnalyzeDeal.vue`, so the mirrored
 * twin is deliberately not typed a second time.
 */
export const BRRRR_FORM_FIELDS = [
  'purchasePrice',
  'rehabCost',
  'rehabContingency',
  'closingCostsBuy',
  'down_payment',
  'hmlPoints',
  'HMLInterestRate',
  'arv_in_thousands',
  'ltv_as_precent',
  'daysUntilRefi',
  'closingCostsRefi',
  'refiPoints',
  'cashReserve',
  'interestRate',
  'loanTermYears',
  'rent',
  'annual_property_taxes',
  'annual_insurance',
  'montly_hoa',
  'vacancyPercent',
  'maintenancePercent',
  'capexPercent',
  'property_managment_fee_precentages_from_rent',
] as const;

export const FLIP_FORM_FIELDS = [
  'purchasePrice',
  'rehabCost',
  'rehabContingency',
  'closingCostsBuy',
  'down_payment',
  'hmlPoints',
  'HMLInterestRate',
  'salePrice',
  'holdingTime',
  'buyerAgentSellingFee',
  'sellerAgentSellingFee',
  'sellingClosingCosts',
  'capitalGainsTax',
  'annual_property_taxes',
  'annual_insurance',
  'montly_hoa',
  'monthly_utilities',
] as const;
