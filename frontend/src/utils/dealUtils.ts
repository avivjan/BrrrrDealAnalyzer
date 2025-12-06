import type { ActiveDealRes } from "../types";

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

  return `
DEAL SUMMARY TO AI
------------------
Address: ${deal.address}
Stage: ${getStageName(deal.stage)}
Task: ${deal.task || "N/A"}
Notes: ${deal.notes || "N/A"}

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

FINANCIALS (Inputs)
-------------------
Purchase Price: ${formatMoney(deal.purchasePrice ? deal.purchasePrice * 1000 : undefined)}
Rehab Cost: ${formatMoney(deal.rehabCost ? deal.rehabCost * 1000 : undefined)}
Closing Costs (Buy): ${formatMoney(deal.closingCostsBuy ? deal.closingCostsBuy * 1000 : undefined)}
ARV: ${formatMoney(deal.arv_in_thousands ? deal.arv_in_thousands * 1000 : undefined)}
Rent: ${formatMoney(deal.rent)}

ANALYSIS RESULTS
----------------
Cash Flow: ${formatMoney(deal.cash_flow)}
Cash Out: ${formatMoney(deal.cash_out)}
Cash Needed: ${formatMoney(deal.total_cash_needed_for_deal)}
DSCR: ${deal.dscr?.toFixed(2) || "-"}
CoC Return: ${formatPercent(deal.cash_on_cash)}
ROI: ${formatPercent(deal.roi)}
Equity: ${formatMoney(deal.equity)}
Net Profit: ${formatMoney(deal.net_profit)}

COMPS
-----
Sold Comps: ${deal.sold_comps?.map(c => `\n  - ${c.url} (ARV: ${c.arv}, Date: ${c.how_long_ago})`).join("") || "None"}
Rent Comps: ${deal.rent_comps?.map(c => `\n  - ${c.url} (Rent: ${c.rent}, Time: ${c.time_on_market})`).join("") || "None"}
`.trim();
};

