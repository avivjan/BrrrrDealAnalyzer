import type {
  ActiveDealRes,
  BrrrDealRes,
  DealInputModel,
  FlipDealRes,
} from "../types";
import { validateDealInputFields } from "./dealInputValidation";

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

/**
 * What Refi Points starts at on a *brand-new* deal.
 *
 * Deliberately NOT the same constant as `BRRR_LEGACY_DEFAULTS.refiPoints`,
 * which must stay 1.5 forever: that one backfills rows saved before the column
 * existed, and it mirrors the DB `server_default='1.5'` and the already-run
 * `_add_column_if_missing` migration. Changing it would silently re-price
 * every old deal. Two different numbers, two different jobs.
 */
export const DEFAULT_REFI_POINTS = 2;
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
 * Read a deal's numeric field, whatever representation it arrived in.
 *
 * A deal's numbers reach the UI in two different shapes, and every reader has to
 * cope with both:
 *
 * - **Loaded from the API** — FastAPI serialises every `Decimal` column as a JSON
 *   *string* (`"200.00"`), so `purchasePrice`, `rehabCost`, every percentage and
 *   every money field arrive as strings. Only `int` columns (`holdingTime`,
 *   `loanTermYears`) and `bool` (`use_HM_for_rehab`) arrive as real JSON values.
 * - **Typed by the user** — `DealInputsForm` writes real numbers.
 *
 * The TypeScript types on `ActiveDealRes` / `BoughtDealRes` declare these as
 * `number`, which is a lie for the first case. Anything that does arithmetic or
 * a `typeof === "number"` check on a raw deal field must go through here instead.
 *
 * Returns `undefined` for null, empty string, or anything non-numeric, so callers
 * can apply their own fallback with `??` (and a real `0` is preserved).
 */
export function toNumber(value: unknown): number | undefined {
  if (typeof value === "number") return Number.isNaN(value) ? undefined : value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isNaN(parsed) ? undefined : parsed;
  }
  return undefined;
}

/**
 * Fallbacks for the two slider-backed BRRRR fields. `SliderField` always needs a
 * concrete number (a null thumb position is meaningless), so `DealInputsForm`
 * substitutes these when the bound deal has no value yet.
 */
export const DEFAULT_LTV_PERCENT = 75;
export const DEFAULT_LONG_TERM_INTEREST_RATE = 7;

/**
 * Hold between purchase closing and refi closing, in days — 180 is the old
 * 6-month default, which is exactly 180 days under the calc's 360-day year.
 */
export const DEFAULT_DAYS_UNTIL_REFI = 180;

/** Today as an ISO calendar date (local), the default Buy closing date of a new deal. */
export function todayIsoDate(now: Date = new Date()): string {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** Defaults of the BRRRR lifecycle inputs (mirror the backend's `BrrrLifecycleInputs`). */
export const BRRR_LIFECYCLE_DEFAULTS = {
  earnestMoneyDeposit: 5000,
  loanChargesBuy: 900,
  recordingTransferBuy: null,
  titleModeBuy: "standard" as const,
  titleEscrowBuy: null,
  onlineNotaryBuy: true,
  onlineNotaryFeeBuy: null,
  otherClosingCostsBuy: 0,
  otherClosingCostsBuyNote: null,
  sellerPaidCurrentYearTaxes: null,
  constructionLoanBudget: 0,
  rehabCushion: 5000,
  daysUntilRented: 90,
  monthlyUtilitiesUntilRented: 80,
  maintenanceBeforeRefi: 500,
  appliances: 630,
  loanChargesRefi: 200,
  recordingTransferRefi: null,
  titleEscrowRefi: null,
  onlineNotaryRefi: true,
  onlineNotaryFeeRefi: null,
  appraisalFee: 700,
  surveyFee: 385,
  refiUnderwritingFee: 2000,
  brokerProcessingFeeRefi: 0,
  otherClosingCostsRefi: 0,
  otherClosingCostsRefiNote: null,
  maintenanceReserve: 1500,
  vacancyReserve: null,
  capexReserve: 2500,
  lowestArv: null,
};

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

    // Shared — buy & rehab.
    // Money fields are in *thousands*: `closingCostsBuy: 5` is $5,000, which
    // is what `MoneyInput` renders once it multiplies back up.
    purchasePrice: 0,
    rehabCost: 0,
    rehabContingency: 10,
    closingCostsBuy: 5,
    down_payment: 10,
    hmlPoints: 2,
    HMLInterestRate: 12,
    use_HM_for_rehab: true,

    // Shared — holding costs
    annual_property_taxes: 0,
    annual_insurance: 0,
    montly_hoa: 0,

    // BRRRR
    arv_in_thousands: 0,
    daysUntilRefi: DEFAULT_DAYS_UNTIL_REFI,
    closingCostsRefi: 10,
    refiPoints: DEFAULT_REFI_POINTS,
    cashReserve: DEFAULT_CASH_RESERVE,
    buyClosingDate: todayIsoDate(),
    ...BRRR_LIFECYCLE_DEFAULTS,
    loanTermYears: 30,
    ltv_as_precent: DEFAULT_LTV_PERCENT,
    interestRate: DEFAULT_LONG_TERM_INTEREST_RATE,
    rent: 0,
    vacancyPercent: 5,
    property_managment_fee_precentages_from_rent: 0,
    maintenancePercent: 5,
    capexPercent: 0,

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
 * The message-only view of `validateDealInputFields` (`utils/dealInputValidation.ts`),
 * which is where a rule is added and where each field's own error comes from.
 */
export function validateDealInputs(
  deal: DealInputModel,
  dealType: "BRRRR" | "FLIP",
): string[] {
  return validateDealInputFields(deal, dealType).map((fieldError) => fieldError.message);
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
  // `toNumber` because a saved deal's money/percentage fields arrive from the API
  // as strings — calling `.toFixed()` on one throws.
  const formatMoney = (val?: number) => {
    const n = toNumber(val);
    return n !== undefined ? `$${n.toLocaleString()}` : "-";
  };
  // -1 / -2 are the calculators' ±∞ sentinels on cash_on_cash / roi /
  // annualized_roi; decode them here only (never in formatMoney, where -$1 is
  // a real dollar amount). A genuine 0 renders "0.00%".
  const formatPercent = (val?: number) => {
    const n = toNumber(val);
    if (n === undefined) return "-";
    if (n === -1) return "∞%";
    if (n === -2) return "-∞%";
    return `${n.toFixed(2)}%`;
  };

  const isBrrr = !deal.deal_type || deal.deal_type === 'BRRRR';
  const brrr = isBrrr ? (deal as BrrrDealRes) : null;
  const flip = !isBrrr ? (deal as FlipDealRes) : null;

  let financials = "";
  let analysis = "";

  if (isBrrr && brrr) {
      financials = `
Financials (BRRRR)
------------------
Buy Closing Date: ${brrr.buyClosingDate || "-"}
Purchase Price: ${formatMoney(brrr.purchasePrice ? brrr.purchasePrice * 1000 : undefined)}
Earnest Money Deposit: ${formatMoney(brrr.earnestMoneyDeposit)}
Closing Costs (Buy): ${formatMoney(brrr.closing_costs_buy_total)} (loan charges ${formatMoney(brrr.loanChargesBuy)}, recording ${formatMoney(brrr.recording_transfer_buy_effective)}, title/escrow ${formatMoney(brrr.title_escrow_buy_effective)}, notary ${brrr.onlineNotaryBuy === false ? "no" : formatMoney(toNumber(brrr.onlineNotaryFeeBuy) ?? 250)}, other ${formatMoney(brrr.otherClosingCostsBuy)}${brrr.otherClosingCostsBuyNote ? ` — ${brrr.otherClosingCostsBuyNote}` : ""})
Actual Rehab Cost: ${formatMoney(brrr.rehabCost ? brrr.rehabCost * 1000 : undefined)}
Construction Loan Budget: ${formatMoney(toNumber(brrr.constructionLoanBudget) !== undefined ? Number(brrr.constructionLoanBudget) * 1000 : undefined)}
Rehab Cushion: ${formatMoney(brrr.rehabCushion)}
Days until Rented: ${brrr.daysUntilRented ?? "-"} (utilities ${formatMoney(brrr.monthlyUtilitiesUntilRented)}/mo, maintenance before refi ${formatMoney(brrr.maintenanceBeforeRefi)}, appliances ${formatMoney(brrr.appliances)})
Rent: ${formatMoney(brrr.rent)}
Days until Refi: ${brrr.daysUntilRefi ?? "-"} (refi ${brrr.refi_closing_date || "-"})
ARV: ${formatMoney(brrr.arv_in_thousands ? brrr.arv_in_thousands * 1000 : undefined)} (lowest ${formatMoney(brrr.lowest_arv_effective)})
Closing Costs (Refi): ${formatMoney(brrr.closing_costs_refi_total)} (broker points ${Number(brrr.refiPoints ?? BRRR_LEGACY_DEFAULTS.refiPoints)} pts, appraisal ${formatMoney(brrr.appraisalFee)}, survey ${formatMoney(brrr.surveyFee)}, underwriting ${formatMoney(brrr.refiUnderwritingFee)}, processing ${formatMoney(brrr.brokerProcessingFeeRefi)})
Reserves at Refi: ${formatMoney(brrr.reserves_total)} (maintenance ${formatMoney(brrr.maintenanceReserve)}, vacancy ${formatMoney(brrr.vacancy_reserve_effective)}, capex ${formatMoney(brrr.capexReserve)})
`;
      analysis = `
Analysis Results (BRRRR)
------------------------
Cash Flow: ${formatMoney(brrr.cash_flow)}
Cash to Close (Buy): ${formatMoney(brrr.cash_to_close_buy)} (seller tax credit ${formatMoney(brrr.seller_tax_credit)}, prepaid interest ${formatMoney(brrr.prepaid_interest_buy)})
Total Hard Money Cost: ${formatMoney(brrr.total_hard_money_cost)}
Stolen Money: ${formatMoney(brrr.stolen_money)}
Pre-Refi Rental Income: ${formatMoney(brrr.pre_refi_rental_income)}
Cash-Out Routi: ${formatMoney(brrr.cash_out_routi)}
Cash-Out Wire (Lowest ARV): ${formatMoney(brrr.cash_out_routi_conservative)}
Cash Out: ${formatMoney(brrr.cash_out)}
Cash Needed: ${formatMoney(brrr.total_cash_needed_for_deal)} (planned on the lowest ARV; cash to the refi table ${formatMoney(brrr.cash_to_refi_table_conservative)})
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
Google Drive: ${deal.google_drive_link || "-"}
${financials}
${analysis}
${comps}
`.trim();
};
