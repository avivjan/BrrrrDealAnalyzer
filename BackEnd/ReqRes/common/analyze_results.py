"""Response models for the /analyze/brrr and /analyze/flip calculation results.

Every field carries a description with its unit and sign convention: these
descriptions reach the website's OpenAPI document and the MCP tools' output
schemas, which is how an AI reading the numbers knows what they mean
(tests/test_mcp.py fails on an undocumented output field).
"""

from datetime import date
from typing import Optional, Dict, List
from decimal import Decimal
from pydantic import BaseModel, Field

from ReqRes.common.calc_step import CalcStep

_BREAKDOWNS = (
    "Step-by-step calculation per headline metric, keyed by metric name (e.g. 'cash_flow', "
    "'cash_out'): each step has a label, a value and the formula with the numbers filled in."
)
_MESSAGES = (
    "Reserved for input-validation warnings; currently never populated (invalid input is rejected "
    "with HTTP 400 instead), so this is null or an empty list."
)


class analyzeBRRRRes(BaseModel):
    """Result of the BRRRR (buy, rehab, rent, refinance, repeat) calculation. All money in plain dollars."""

    cash_flow: float = Field(..., description=(
        "Monthly cash flow in a regular year after the refinance, in dollars: rent minus vacancy, maintenance, capex, "
        "property management, taxes (this year's bill x 0.96 / 12), insurance (the regular-year monthly figure), "
        "HOA and the new mortgage payment. Never includes a closing lump. Negative = the property costs money every month."))
    dscr: Optional[float] = Field(None, description=(
        "Debt service coverage ratio after the refinance: monthly rent divided by the monthly PITIA "
        "(principal, interest, taxes, insurance and HOA). Above 1.0 the rent covers the payment; lenders "
        "usually want 1.2 or more."))
    cash_out: Optional[float] = Field(None, description=(
        "Cash out from the deal, in dollars: the total cash received from the deal (the refinance wire, "
        "see cash_out_routi) MINUS the reserves the owner sets aside at the refi (reserves_total: money that "
        "stays in the deal) MINUS the total cash put into it before the refinance (total_cash_invested). "
        "Negative means that much of your own money is still left in the deal (e.g. -26587 = $26,587 left in); "
        "positive means you took out more than you invested."))
    cash_out_routi: Optional[float] = Field(None, description=(
        "'Routi': the cash wire received at the refinance closing table, in dollars: the new loan "
        "(ARV x LTV) minus the hard-money payoff, refi closing costs and refi prepaid interest: the 'Due to Borrower' "
        "line of the refi settlement statement. The reserves are the owner's own money and are not taken off it. "
        "Gross, before subtracting what was invested (that subtraction is cash_out). Negative = cash brought to the table."))
    cash_out_routi_conservative: Optional[float] = Field(None, description=(
        "The refinance wire recomputed with the lowest ARV (stress test), in dollars: loan-dependent fees and "
        "prepaid interest follow the lower loan. Negative = cash to bring to the refi table."))
    cash_to_refi_table_conservative: Optional[float] = Field(None, description=(
        "Cash to bring to the refi closing under the lowest ARV, in dollars: max(0, -cash_out_routi_conservative)."))
    cash_on_cash: Optional[float] = Field(None, description=(
        "Cash-on-cash return in percent: yearly cash flow divided by the cash left in the deal. "
        "-1 means infinite (no cash left in the deal); -2 means not applicable."))
    roi: Optional[float] = Field(None, description=(
        "Return on investment in percent: one year of cash flow (12 x cash_flow) plus net_profit, divided "
        "by the cash left in the deal (|cash_out|). -1 means infinite (no cash left in the deal); "
        "-2 means not applicable (cash flow is 0 or negative)."))
    equity: Optional[float] = Field(None, description=(
        "Equity after the refinance, in dollars: ARV minus the new loan balance, plus the reserves the owner set "
        "aside (released with confidence at a sale)."))
    net_profit: Optional[float] = Field(None, description=(
        "Net profit created by the deal, in dollars: equity plus cash out (a negative cash out, money "
        "left in, reduces it)."))
    total_cash_needed_for_deal: Optional[float] = Field(None, description=(
        "Cash Needed: the single definitive out-of-pocket capital through the refinance, in dollars: the larger of "
        "total_cash_invested + rehab cushion + cash_to_refi_table_conservative + reserves_funded_from_own_pocket_at_lowest_arv "
        "(the cash brought to the refi table, and the reserves the wire cannot fund, if the appraisal comes in at the "
        "lowest ARV; planned on the stress test, not the baseline) and the day-one floor: EMD + cash_to_close_buy + the "
        "insurance bill when paid outside the purchase closing + rehab cushion + one month of utilities, of HOA (30 days), "
        "of insurance paid monthly and one tax-bucket deposit + the rest of the first month's hard-money interest (30 days "
        "less the days already prepaid inside cash_to_close_buy)."))
    total_cash_invested: Optional[float] = Field(None, description=(
        "Everything actually spent before the refinance, in dollars: EMD + cash to close (buy) + the positive "
        "seller tax credit set aside in the property's tax bucket the day after closing + the insurance bill at purchase "
        "when paid outside the closing + rehab paid beyond the construction budget (negative when the budget exceeds the "
        "rehab) + monthly hard-money interest + HOA until refi + insurance paid monthly until refi + the tax-bucket "
        "deposits until refi + any Nov 30 shortfall topped up + utilities until rented + maintenance before refi + "
        "appliances + appraisal and survey (paid outside the refi closing) + the insurance bill at refi when paid outside "
        "the closing - pre-refi rent - the tax-bucket balance released when the refi lender collects the whole bill."))
    cash_to_close_buy: Optional[float] = Field(None, description=(
        "Cash wired to the title company on purchase day, in dollars: down payment + buy closing costs (including the "
        "insurance bill when paid inside the closing) + hard-money points + prepaid interest (buy) - seller tax credit - "
        "earnest money deposit."))
    purchase_loan_amount: Optional[float] = Field(None, description=(
        "Hard-money loan on the purchase, in dollars: purchase price x (1 - down payment %)."))
    hml_amount: Optional[float] = Field(None, description=(
        "Total hard-money principal, in dollars: purchase loan + construction loan budget."))
    hml_payoff: Optional[float] = Field(None, description=(
        "Hard-money payoff at the refi, in dollars: principal plus the interest accrued since the 1st of the refi month."))
    total_hard_money_cost: Optional[float] = Field(None, description=(
        "All the cost of the hard-money loan, in dollars: points + interest until the refi + loan charges (buy)."))
    prepaid_interest_buy: Optional[float] = Field(None, description=(
        "Hard-money per-diem interest collected at the purchase closing from the closing date through the end "
        "of that month, in dollars. 0 when no buy closing date is set."))
    seller_tax_credit: Optional[float] = Field(None, description=(
        "Property-tax proration on the purchase settlement, in dollars. Positive = the seller credits the buyer "
        "for the days they owned this year (taxes still unpaid, billed in November); negative = the buyer "
        "credits the seller (an October to December closing by default, taxes already paid). The typed sellerTaxCreditAtPurchaseClosing when "
        "given, else the proration (0 when no buy closing date is set). "
        "A positive credit is set aside in the property's tax bucket the day after closing, so it lowers "
        "cash_to_close_buy but not total_cash_invested or Cash Needed; a negative one is a real cost."))
    closing_costs_buy_total: Optional[float] = Field(None, description=(
        "Sum of the buy closing-cost lines, in dollars: loan charges + recording/transfer + title/escrow + "
        "online notary + other + the insurance bill when paid inside the purchase closing."))
    deed_transfer_tax_buy: Optional[float] = Field(None, description=(
        "Deed transfer tax inside the buy recording/transfer default, in dollars: $0 on a standard deal (the "
        "seller's debit), 0.70% of the purchase price when we pay all closing costs."))
    stolen_money: Optional[float] = Field(None, description=(
        "Lender draw spread, in dollars: construction loan budget minus actual rehab (with contingency). "
        "Positive = capital pulled out through draws before the refi; negative = extra out-of-pocket rehab."))
    pre_refi_rental_income: Optional[float] = Field(None, description=(
        "Rent collected between tenant placement and the refi, in dollars (30-day months); offsets holding costs."))
    closing_costs_refi_total: Optional[float] = Field(None, description=(
        "Sum of the refi closing-cost lines, in dollars: loan charges + recording/transfer + title/escrow + "
        "online notary + underwriting + broker points + processing + other + the insurance bill when paid inside the "
        "refi closing + the tax lump when the refi lender collects the whole bill. The appraisal and the survey are "
        "paid outside the closing and are not here."))
    prepaid_interest_refi: Optional[float] = Field(None, description=(
        "DSCR-loan per-diem interest collected at the refi closing through the end of that month, in dollars "
        "(360-day year, as the refi settlement statements quote it). 0 when no buy closing date is set."))
    reserves_total: Optional[float] = Field(None, description=(
        "Reserves the owner sets aside at the refi, in dollars: maintenance + vacancy + capex + the HYSA deposit. Not "
        "taken off the wire; they lower cash_out (money that stays in the deal) and count as equity."))
    refi_closing_date: Optional[date] = Field(None, description=(
        "Buy closing date + days until refi (ISO). Absent when no buy closing date is set."))
    tenant_occupied_date: Optional[date] = Field(None, description=(
        "Buy closing date + days until rented (ISO). Absent when no buy closing date is set."))
    rehab_completed_date: Optional[date] = Field(None, description=(
        "Buy closing date + days until rehab completed (ISO). Absent when no buy closing date is set."))
    appraisal_and_survey_paid_outside_closing: Optional[float] = Field(None, description=(
        "Appraisal + survey, in dollars: paid outside the refi closing at the end of the rehab, so in "
        "total_cash_invested and not in the refi closing costs."))
    insurance_bill_at_refi_effective: Optional[float] = Field(None, description=(
        "Insurance bill at the refi actually used, in dollars: the input, or the insurance bill at purchase when null."))
    monthly_insurance_after_refi_effective: Optional[float] = Field(None, description=(
        "Insurance per month in a regular year after the refi actually used, in dollars: the input, or the insurance "
        "bill at the refi / 12 when null."))
    property_tax_bucket_deposit_effective: Optional[float] = Field(None, description=(
        "Deposit into the property's tax bucket on each 15th until the refi actually used, in dollars: the input, or "
        "(this year's bill x 0.96 - the seller credit set aside) / the 15ths left until Nov 30 when null."))
    property_tax_paid_into_bucket_until_refi: Optional[float] = Field(None, description=(
        "Every deposit into the property's tax bucket from the purchase to the refi, in dollars."))
    property_tax_lump_sum_at_refi_closing_effective: Optional[float] = Field(None, description=(
        "The tax lump the refi lender collects, in dollars: 0 unless the full bill is collected at the refi; then the "
        "input, or this year's bill when null."))
    property_tax_bucket_balance_released_at_refi: Optional[float] = Field(None, description=(
        "The tax bucket's balance that comes back to the owner when the refi lender collects the whole bill, in "
        "dollars (lowers total_cash_invested). 0 otherwise."))
    monthly_property_tax_after_refi: Optional[float] = Field(None, description=(
        "Property tax per month in a regular year after the refi, in dollars: this year's bill x 0.96 / 12 "
        "(paid on Nov 30 with the November discount)."))
    hysa_deposit_at_refi_effective: Optional[float] = Field(None, description=(
        "HYSA deposit at the refi actually used, in dollars: the input, or 3 months of the DSCR loan's principal and "
        "interest when null."))
    reserves_funded_from_own_pocket_at_lowest_arv: Optional[float] = Field(None, description=(
        "The reserves the lowest-ARV wire cannot fund, in dollars: max(0, reserves_total - max(0, "
        "cash_out_routi_conservative)). Part of Cash Needed."))
    recording_transfer_buy_effective: Optional[float] = Field(None, description=(
        "Recording/transfer charges (buy) actually used, in dollars: the input, or its formula default when null."))
    title_escrow_buy_effective: Optional[float] = Field(None, description=(
        "Title/escrow charges (buy) actually used, in dollars: the input, or its formula default when null."))
    recording_transfer_refi_effective: Optional[float] = Field(None, description=(
        "Recording/transfer charges (refi) actually used, in dollars: the input, or its formula default when null."))
    title_escrow_refi_effective: Optional[float] = Field(None, description=(
        "Title/escrow charges (refi) actually used, in dollars: the input, or its formula default when null."))
    vacancy_reserve_effective: Optional[float] = Field(None, description=(
        "Vacancy reserve actually used, in dollars: the input, or one month of rent when null."))
    lowest_arv_effective: Optional[float] = Field(None, description=(
        "Lowest ARV actually used, in dollars: the input, or 90% of ARV when null."))
    messages: Optional[list[str]] = Field(None, description=_MESSAGES)
    breakdowns: Optional[Dict[str, List[CalcStep]]] = Field(None, description=_BREAKDOWNS)


class analyzeFlipRes(BaseModel):
    """Result of the fix-and-flip calculation. All money in plain dollars."""

    net_profit: float = Field(..., description=(
        "Net profit of the flip, in dollars: sale price minus purchase, rehab, buy and sell closing "
        "costs, agent fees, hard-money points, holding costs (which include the hard-money interest) "
        "and capital gains tax."))
    roi: float = Field(..., description=(
        "Return on investment in percent: net profit divided by the total cash needed. "
        "-1 means infinite (no cash needed); -2 means not applicable."))
    annualized_roi: float = Field(..., description=(
        "roi scaled to a year by the holding time in months (roi x 12 / holding months), in percent."))
    total_cash_needed: float = Field(..., description=(
        "Total cash needed to do the flip, in dollars: down payment, buy closing costs, points, "
        "out-of-pocket rehab, hard-money interest and holding costs."))
    total_cash_needed_with_buffer: float = Field(..., description=(
        "total_cash_needed plus the rehab contingency buffer, in dollars."))
    total_holding_costs: float = Field(..., description=(
        "Hard-money interest plus taxes, insurance, HOA and utilities over the holding time, in dollars "
        "(total_hml_interest + the operating costs)."))
    total_hml_interest: float = Field(..., description=(
        "Hard-money loan interest over the holding time, in dollars."))
    messages: Optional[list[str]] = Field(None, description=_MESSAGES)
    breakdowns: Optional[Dict[str, List[CalcStep]]] = Field(None, description=_BREAKDOWNS)
