/**
 * The result tiles of the deal modals, in the order they appear there: what the
 * "Generate Report" picker offers, and what the PDF titles each section with
 * ("How Cash Flow is calculated"). Mirrors `BackEnd/BL/reports/common/report_result_tiles.py`;
 * `BackEnd/tests/test_report_pdf.py` pins this file, the backend list and the tiles
 * `MyDeals.vue` / `BoughtDeals.vue` render to each other.
 */
import type { CalcStep } from "../../types";

export interface ReportResultTile {
  /** The analysis field and breakdown section key, e.g. "cash_flow"; sent to the report endpoint. */
  resultKey: string;
  /** The tile's caption in the deal modal. */
  tileLabel: string;
  unit: NonNullable<CalcStep["unit"]>;
}

export const BRRRR_REPORT_RESULT_TILES: readonly ReportResultTile[] = [
  { resultKey: "cash_flow", tileLabel: "Cash Flow", unit: "money" },
  { resultKey: "cash_out", tileLabel: "Cash Out", unit: "money" },
  { resultKey: "cash_out_routi", tileLabel: "Cash-Out Routi", unit: "money" },
  { resultKey: "cash_on_cash", tileLabel: "CoC", unit: "pct" },
  { resultKey: "dscr", tileLabel: "DSCR", unit: "ratio" },
  { resultKey: "equity", tileLabel: "Equity", unit: "money" },
  { resultKey: "roi", tileLabel: "ROI", unit: "pct" },
  { resultKey: "net_profit", tileLabel: "Net Profit", unit: "money" },
  { resultKey: "total_cash_needed_for_deal", tileLabel: "Cash Needed", unit: "money" },
  { resultKey: "cash_to_close_buy", tileLabel: "Cash to Close (Buy)", unit: "money" },
  { resultKey: "cash_out_routi_conservative", tileLabel: "Cash-Out Routi (Lowest ARV)", unit: "money" },
  { resultKey: "stolen_money", tileLabel: "Stolen Money", unit: "money" },
];

export const FLIP_REPORT_RESULT_TILES: readonly ReportResultTile[] = [
  { resultKey: "net_profit", tileLabel: "Net Profit", unit: "money" },
  { resultKey: "roi", tileLabel: "ROI", unit: "pct" },
  { resultKey: "annualized_roi", tileLabel: "Annualized ROI", unit: "pct" },
  { resultKey: "total_cash_needed", tileLabel: "Cash Needed", unit: "money" },
  { resultKey: "total_cash_needed_with_buffer", tileLabel: "Cash Needed (Buffered)", unit: "money" },
  { resultKey: "total_holding_costs", tileLabel: "Holding Costs", unit: "money" },
  { resultKey: "total_hml_interest", tileLabel: "HML Interest", unit: "money" },
];

export function reportResultTilesForDealType(dealType: "BRRRR" | "FLIP"): readonly ReportResultTile[] {
  return dealType === "FLIP" ? FLIP_REPORT_RESULT_TILES : BRRRR_REPORT_RESULT_TILES;
}
