/**
 * Which outputs each BRRRR input moves — the text behind every (i) icon on the form.
 *
 * Direct dependencies only, in the order a reader cares about; the downstream metrics
 * (cash out, net profit, ROI, cash-on-cash) follow from the listed ones. Traced from
 * `BackEnd/BL/analyze/brrrSteps/`; `brrrInputImpacts.test.ts` checks every BRRRR input the
 * form renders has an entry and every output named here exists on `BrrrAnalyzeRes`.
 */
import type { BrrrAnalyzeRes } from "../types";

export type BrrrOutputKey = keyof Omit<BrrrAnalyzeRes, "messages" | "breakdowns">;

export const BRRR_OUTPUT_LABELS: Partial<Record<BrrrOutputKey, string>> = {
  cash_to_close_buy: "Cash to Close (Buy)",
  total_hard_money_cost: "Total Hard Money Cost",
  stolen_money: "Stolen Money",
  pre_refi_rental_income: "Pre-Refi Rental Income",
  seller_tax_credit: "Seller Tax Credit",
  prepaid_interest_buy: "Prepaid Interest (Buy)",
  prepaid_interest_refi: "Prepaid Interest (Refi)",
  total_cash_invested: "Total Cash Invested",
  total_cash_needed_for_deal: "Cash Needed",
  cash_needed_conservative: "Cash Needed (Lowest ARV)",
  cash_out_routi: "Cash-Out Wire",
  cash_out_routi_conservative: "Cash-Out Wire (Lowest ARV)",
  cash_to_refi_table_conservative: "Cash to Refi Table (Lowest ARV)",
  cash_out: "Cash Out",
  net_profit: "Net Profit",
  roi: "ROI",
  cash_on_cash: "Cash on Cash",
  equity: "Equity",
  cash_flow: "Cash Flow",
  dscr: "DSCR",
  hml_amount: "Hard Money Loan",
  hml_payoff: "HML Payoff",
  purchase_loan_amount: "Purchase Loan",
  closing_costs_buy_total: "Closing Costs (Buy)",
  closing_costs_refi_total: "Closing Costs (Refi)",
  reserves_total: "Reserves",
};

const CASH_METRICS: BrrrOutputKey[] = ["total_cash_needed_for_deal", "cash_out", "net_profit", "roi", "cash_on_cash"];
const BUY_CLOSING_LINE: BrrrOutputKey[] = ["closing_costs_buy_total", "cash_to_close_buy", ...CASH_METRICS];
const REFI_CLOSING_LINE: BrrrOutputKey[] = ["closing_costs_refi_total", "cash_out_routi", "cash_out_routi_conservative", ...CASH_METRICS];
const RESERVE: BrrrOutputKey[] = ["reserves_total", "cash_out_routi", "cash_out_routi_conservative", "equity", ...CASH_METRICS];
const HOLDING_ITEM: BrrrOutputKey[] = ["total_cash_invested", ...CASH_METRICS];

export const BRRR_INPUT_IMPACTS: Record<string, BrrrOutputKey[]> = {
  // Buy
  buyClosingDate: ["prepaid_interest_buy", "seller_tax_credit", "cash_to_close_buy", "hml_payoff", "prepaid_interest_refi", "cash_out_routi", ...CASH_METRICS],
  purchasePrice: ["purchase_loan_amount", "hml_amount", "total_hard_money_cost", "cash_to_close_buy", "hml_payoff", "cash_out_routi", ...CASH_METRICS],
  down_payment: ["purchase_loan_amount", "hml_amount", "total_hard_money_cost", "cash_to_close_buy", "hml_payoff", "cash_out_routi", ...CASH_METRICS],
  earnestMoneyDeposit: ["cash_to_close_buy"],
  hmlPoints: ["total_hard_money_cost", "cash_to_close_buy", ...CASH_METRICS],
  HMLInterestRate: ["total_hard_money_cost", "prepaid_interest_buy", "cash_to_close_buy", "hml_payoff", "cash_out_routi", ...CASH_METRICS],
  loanChargesBuy: ["total_hard_money_cost", ...BUY_CLOSING_LINE],
  recordingTransferBuy: BUY_CLOSING_LINE,
  titleModeBuy: BUY_CLOSING_LINE,
  titleEscrowBuy: BUY_CLOSING_LINE,
  onlineNotaryBuy: BUY_CLOSING_LINE,
  otherClosingCostsBuy: BUY_CLOSING_LINE,
  sellerPaidCurrentYearTaxes: ["seller_tax_credit", "cash_to_close_buy", ...CASH_METRICS],
  // Rehab
  rehabCost: ["stolen_money", "total_cash_invested", ...CASH_METRICS],
  rehabContingency: ["stolen_money", "total_cash_invested", ...CASH_METRICS],
  constructionLoanBudget: ["hml_amount", "stolen_money", "total_hard_money_cost", "hml_payoff", "cash_out_routi", ...CASH_METRICS],
  rehabCushion: ["total_cash_needed_for_deal", "cash_needed_conservative"],
  // Rent & holding
  rent: ["pre_refi_rental_income", "reserves_total", "cash_flow", "dscr", "cash_out_routi", ...CASH_METRICS],
  daysUntilRented: ["pre_refi_rental_income", ...HOLDING_ITEM],
  monthlyUtilitiesUntilRented: HOLDING_ITEM,
  maintenanceBeforeRefi: HOLDING_ITEM,
  appliances: HOLDING_ITEM,
  annual_property_taxes: ["seller_tax_credit", "cash_to_close_buy", "total_cash_invested", "cash_flow", "dscr", ...CASH_METRICS],
  annual_insurance: ["total_cash_invested", "cash_flow", "dscr", ...CASH_METRICS],
  montly_hoa: ["total_cash_invested", "cash_flow", "dscr", ...CASH_METRICS],
  vacancyPercent: ["cash_flow", "dscr", "cash_on_cash", "roi"],
  maintenancePercent: ["cash_flow", "dscr", "cash_on_cash", "roi"],
  capexPercent: ["cash_flow", "dscr", "cash_on_cash", "roi"],
  property_managment_fee_precentages_from_rent: ["cash_flow", "dscr", "cash_on_cash", "roi"],
  // Refinance
  daysUntilRefi: ["total_hard_money_cost", "pre_refi_rental_income", "prepaid_interest_refi", "hml_payoff", "cash_out_routi", ...CASH_METRICS],
  arv_in_thousands: ["cash_out_routi", "cash_out_routi_conservative", "equity", "cash_flow", "dscr", ...CASH_METRICS],
  lowestArv: ["cash_out_routi_conservative", "cash_to_refi_table_conservative", "cash_needed_conservative"],
  ltv_as_precent: ["cash_out_routi", "cash_out_routi_conservative", "equity", "cash_flow", "dscr", ...CASH_METRICS],
  interestRate: ["prepaid_interest_refi", "cash_out_routi", "cash_flow", "dscr", "cash_on_cash", "roi"],
  loanTermYears: ["cash_flow", "dscr", "cash_on_cash", "roi"],
  loanChargesRefi: REFI_CLOSING_LINE,
  recordingTransferRefi: REFI_CLOSING_LINE,
  titleEscrowRefi: REFI_CLOSING_LINE,
  onlineNotaryRefi: REFI_CLOSING_LINE,
  appraisalFee: REFI_CLOSING_LINE,
  surveyFee: REFI_CLOSING_LINE,
  refiUnderwritingFee: REFI_CLOSING_LINE,
  refiPoints: REFI_CLOSING_LINE,
  brokerProcessingFeeRefi: REFI_CLOSING_LINE,
  otherClosingCostsRefi: REFI_CLOSING_LINE,
  maintenanceReserve: RESERVE,
  vacancyReserve: RESERVE,
  capexReserve: RESERVE,
};

/** "Affects: Cash to Close (Buy), Cash Needed, …" for the (i) icon of `field`. */
export function impactText(field: string): string {
  const affectedOutputKeys = BRRR_INPUT_IMPACTS[field] ?? [];
  const affectedOutputLabels = affectedOutputKeys.map((outputKey) => BRRR_OUTPUT_LABELS[outputKey] ?? outputKey);
  return affectedOutputLabels.length ? `Affects: ${affectedOutputLabels.join(", ")}` : "";
}
