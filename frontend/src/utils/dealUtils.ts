import type { ActiveDealRes, BrrrDealRes, FlipDealRes } from "../types";

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
