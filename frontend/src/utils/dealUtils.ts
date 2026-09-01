import type {
  ActiveDealRes,
  BrrrDealRes,
  DealInputModel,
  FlipDealRes,
} from "../types";

/**
 * Backend-side defaults for BRRRR fields that were added after the initial
 * schema. Mirrors the Pydantic/SQLAlchemy defaults so legacy rows loaded
 * without these keys still render and recalculate correctly.
 *
 * When you add a new BRRRR field with a server default, add it here and
 * `ensureBrrrLegacyDefaults` will backfill it on every loaded deal.
 */
const BRRR_LEGACY_DEFAULTS = {
  refiPoints: 1.5,
  cashReserve: 0,
} as const;

export const DEFAULT_REFI_POINTS = BRRR_LEGACY_DEFAULTS.refiPoints;
export const DEFAULT_CASH_RESERVE = BRRR_LEGACY_DEFAULTS.cashReserve;

type BrrrLegacyKey = keyof typeof BRRR_LEGACY_DEFAULTS;
type BrrrLegacyShape = {
  deal_type?: "BRRRR" | "FLIP";
} & Partial<Record<BrrrLegacyKey, number>>;

/** Backfill missing BRRRR fields with their backend defaults (mutates in place). */
export function ensureBrrrLegacyDefaults(deal: BrrrLegacyShape): void {
  if (deal.deal_type === "FLIP") return;
  for (const key of Object.keys(BRRR_LEGACY_DEFAULTS) as BrrrLegacyKey[]) {
    const v = deal[key];
    if (v == null || Number.isNaN(Number(v))) {
      deal[key] = BRRR_LEGACY_DEFAULTS[key];
    }
  }
}

/**
 * @deprecated Use `ensureBrrrLegacyDefaults`. Kept as an alias so older
 * imports keep compiling while we migrate consumers.
 */
export const ensureBrrrRefiPointsDefault = ensureBrrrLegacyDefaults;

/**
 * Fallbacks for the two slider-backed BRRRR fields. `SliderField` always needs a
 * concrete number (a null thumb position is meaningless), so `DealInputsForm`
 * substitutes these when the bound deal has no value yet.
 */
export const DEFAULT_LTV_PERCENT = 75;
export const DEFAULT_LONG_TERM_INTEREST_RATE = 6.5;

/**
 * Initial values for a brand-new deal on the Analyze page.
 *
 * Returns BRRRR *and* FLIP fields regardless of `dealType`: the Analyze page
 * lets the user toggle between the two after typing, and the ARV/sale-price
 * mirror needs both keys to exist. The backend's discriminated-union create
 * models ignore the fields that don't belong to the chosen type.
 *
 * When you add a new input to `DealInputsForm`, add its default here.
 */
export function createEmptyDealForm(
  dealType: "BRRRR" | "FLIP" = "BRRRR",
): DealInputModel {
  return {
    deal_type: dealType,

    // Shared — buy & rehab
    purchasePrice: 0,
    rehabCost: 0,
    rehabContingency: 0,
    closingCostsBuy: 0,
    down_payment: 0,
    hmlPoints: 0,
    HMLInterestRate: 11,
    use_HM_for_rehab: false,

    // Shared — holding costs
    annual_property_taxes: 0,
    annual_insurance: 0,
    montly_hoa: 0,

    // BRRRR
    arv_in_thousands: 0,
    monthsUntilRefi: 6,
    closingCostsRefi: 0,
    refiPoints: DEFAULT_REFI_POINTS,
    cashReserve: DEFAULT_CASH_RESERVE,
    loanTermYears: 30,
    ltv_as_precent: DEFAULT_LTV_PERCENT,
    interestRate: DEFAULT_LONG_TERM_INTEREST_RATE,
    rent: 0,
    vacancyPercent: 5,
    property_managment_fee_precentages_from_rent: 0,
    maintenancePercent: 5,
    capexPercent: 5,

    // Flip
    salePrice: 0,
    holdingTime: 6,
    buyerAgentSellingFee: 0,
    sellerAgentSellingFee: 0,
    sellingClosingCosts: 0,
    capitalGainsTax: 0,
    monthly_utilities: 0,
  };
}

/**
 * Client-side bounds checks for the deal inputs, mirroring the backend's
 * `validate_brrr_inputs` / `validate_flip_inputs`. Returns human-readable
 * messages; an empty array means the deal is safe to submit.
 *
 * When you add a new input to `DealInputsForm`, add its bounds check here.
 */
export function validateDealInputs(
  deal: DealInputModel,
  dealType: "BRRRR" | "FLIP",
): string[] {
  const errors: string[] = [];
  const num = (v: number | undefined) => (v == null ? 0 : Number(v));

  if (!deal.purchasePrice || num(deal.purchasePrice) <= 0)
    errors.push("Purchase price (in thousands) must be greater than 0.");
  if (num(deal.rehabCost) < 0)
    errors.push("Rehab cost (in thousands) cannot be negative.");
  if (num(deal.rehabContingency) < 0 || num(deal.rehabContingency) > 100)
    errors.push("Contingency must be between 0% and 100%.");
  if (num(deal.down_payment) < 0 || num(deal.down_payment) > 100)
    errors.push("Down payment percentage must be between 0% and 100%.");

  if (dealType === "BRRRR") {
    if (!deal.arv_in_thousands || num(deal.arv_in_thousands) <= 0)
      errors.push("ARV (in thousands) must be greater than 0.");
    if (!deal.rent || num(deal.rent) <= 0)
      errors.push("Rent must be greater than 0.");
    if (num(deal.ltv_as_precent) <= 0 || num(deal.ltv_as_precent) > 100)
      errors.push("LTV must be between 0% and 100%.");
    if (num(deal.refiPoints) < 0 || num(deal.refiPoints) > 100)
      errors.push("Refi points must be between 0% and 100%.");
    if (num(deal.cashReserve) < 0)
      errors.push("Cash reserve cannot be negative.");
  } else {
    if (!deal.salePrice || num(deal.salePrice) <= 0)
      errors.push("Sale Price (ARV) must be greater than 0.");
    if (num(deal.holdingTime) <= 0)
      errors.push("Holding time must be greater than 0.");
    if (num(deal.buyerAgentSellingFee) < 0 || num(deal.buyerAgentSellingFee) > 100)
      errors.push("Buyer agent fee must be between 0% and 100%.");
    if (num(deal.sellerAgentSellingFee) < 0 || num(deal.sellerAgentSellingFee) > 100)
      errors.push("Seller agent fee must be between 0% and 100%.");
    if (num(deal.sellingClosingCosts) < 0)
      errors.push("Closing costs cannot be negative.");
  }

  return errors;
}

export const getStageName = (id: number) => {
  const map: Record<number, string> = {
    1: "New - need to analyze",
    2: "Working",
    3: "Brought",
    4: "Keep in Mind",
    5: "Dead",
  };
  return map[id] || "Unknown";
};

export const formatDealForClipboard = (deal: ActiveDealRes): string => {
  const formatMoney = (val?: number) =>
    val !== undefined ? `$${val.toLocaleString()}` : "-";
  const formatPercent = (val?: number) =>
    val !== undefined ? `${val.toFixed(2)}%` : "-";

  const isBrrr = !deal.deal_type || deal.deal_type === 'BRRRR';
  const brrr = isBrrr ? (deal as BrrrDealRes) : null;
  const flip = !isBrrr ? (deal as FlipDealRes) : null;

  let financials = "";
  let analysis = "";

  if (isBrrr && brrr) {
      financials = `
Financials (BRRRR)
------------------
Purchase Price: ${formatMoney(brrr.purchasePrice ? brrr.purchasePrice * 1000 : undefined)}
Rehab Cost: ${formatMoney(brrr.rehabCost ? brrr.rehabCost * 1000 : undefined)}
Closing Costs (Buy): ${formatMoney(brrr.closingCostsBuy ? brrr.closingCostsBuy * 1000 : undefined)}
ARV: ${formatMoney(brrr.arv_in_thousands ? brrr.arv_in_thousands * 1000 : undefined)}
Refi Points: ${Number(brrr.refiPoints ?? DEFAULT_REFI_POINTS)} pts
Cash Reserve: ${formatMoney(((brrr.cashReserve ?? DEFAULT_CASH_RESERVE)) * 1000)}
Rent: ${formatMoney(brrr.rent)}
`;
      analysis = `
Analysis Results (BRRRR)
------------------------
Cash Flow: ${formatMoney(brrr.cash_flow)}
Cash Out: ${formatMoney(brrr.cash_out)}
Cash Out Routi: ${formatMoney(brrr.cash_out_routi)}
Cash Needed: ${formatMoney(brrr.total_cash_needed_for_deal)}
Cash Needed (Buffered): ${formatMoney(brrr.total_cash_needed_for_deal_with_buffer)}
DSCR: ${brrr.dscr?.toFixed(2) || "-"}
CoC Return: ${formatPercent(brrr.cash_on_cash)}
ROI: ${formatPercent(brrr.roi)}
Equity: ${formatMoney(brrr.equity)}
Net Profit: ${formatMoney(brrr.net_profit)}
`;
  } else if (flip) {
      financials = `
Financials (FLIP)
-----------------
Purchase Price: ${formatMoney(flip.purchasePrice ? flip.purchasePrice * 1000 : undefined)}
Rehab Cost: ${formatMoney(flip.rehabCost ? flip.rehabCost * 1000 : undefined)}
Closing Costs (Buy): ${formatMoney(flip.closingCostsBuy ? flip.closingCostsBuy * 1000 : undefined)}
Sale Price: ${formatMoney(flip.salePrice ? flip.salePrice * 1000 : undefined)}
Holding Time: ${flip.holdingTime} months
`;
      analysis = `
Analysis Results (FLIP)
-----------------------
Net Profit: ${formatMoney(flip.net_profit)}
ROI: ${formatPercent(flip.roi)}
Annualized ROI: ${formatPercent(flip.annualized_roi)}
Total Cash Needed: ${formatMoney(flip.total_cash_needed)}
Total Cash Needed (Buffered): ${formatMoney(flip.total_cash_needed_with_buffer)}
Holding Costs: ${formatMoney(flip.total_holding_costs)}
`;
  }

  const comps = `
COMPS
-----
Sold Comps: ${deal.sold_comps?.map(c => `\n  - ${c.url} (ARV: ${c.arv}, Date: ${c.how_long_ago})`).join("") || "None"}
${isBrrr ? `Rent Comps: ${deal.rent_comps?.map(c => `\n  - ${c.url} (Rent: ${c.rent}, Time: ${c.time_on_market})`).join("") || "None"}` : ''}
${!isBrrr && (deal as any).sale_comps ? `For Sale Comps: ${(deal as any).sale_comps?.map((c: any) => `\n  - ${c.url} (List: ${c.arv}, DOM: ${c.how_long_ago})`).join("") || "None"}` : ''}
`;

  return `
DEAL SUMMARY TO AI
------------------
Address: ${deal.address}
Stage: ${getStageName(deal.stage)}
Task: ${deal.task || "N/A"}
Notes: ${deal.notes || "N/A"}
Type: ${deal.deal_type || 'BRRRR'}

PROPERTY DETAILS
----------------
SqFt: ${deal.sqft || "-"}
Beds: ${deal.bedrooms || "-"}
Baths: ${deal.bathrooms || "-"}
Section: ${deal.section === 1 ? "Wholesale" : deal.section === 2 ? "Market" : "Off Market"}
Design: ${deal.overall_design || "-"}
Crime: ${deal.crime_rate || "-"}
Niche: ${deal.niche || "-"}

LINKS
-----
Zillow: ${deal.zillow_link || "-"}
Photos: ${deal.pics_link || "-"}
${financials}
${analysis}
${comps}
`.trim();
};
