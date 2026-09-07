"""Response models for the /analyze/brrr and /analyze/flip calculation results.

Every field carries a description with its unit and sign convention: these
descriptions reach the website's OpenAPI document and the MCP tools' output
schemas, which is how an AI reading the numbers knows what they mean
(tests/test_mcp.py fails on an undocumented output field).
"""

from typing import Optional, Dict, List
from decimal import Decimal
from pydantic import BaseModel, Field

from ReqRes.common.calc_step import CalcStep

_BREAKDOWNS = (
    "Step-by-step calculation per headline metric, keyed by metric name (e.g. 'cash_flow', "
    "'cash_out'): each step has a label, a value and the formula with the numbers filled in."
)
_MESSAGES = "Warnings from input validation (e.g. an unusual rate), if any."


class analyzeBRRRRes(BaseModel):
    """Result of the BRRRR (buy, rehab, rent, refinance, repeat) calculation. All money in plain dollars."""

    cash_flow: float = Field(..., description=(
        "Monthly cash flow after the refinance, in dollars: rent minus vacancy, maintenance, capex, "
        "property management, taxes, insurance, HOA and the new mortgage payment. Negative = the "
        "property costs money every month."))
    dscr: Optional[float] = Field(None, description=(
        "Debt service coverage ratio after the refinance: net operating income divided by the annual "
        "mortgage payments. Above 1.0 the rent covers the loan; lenders usually want 1.2 or more."))
    cash_out: Optional[float] = Field(None, description=(
        "Cash out from the deal, in dollars: the total cash received from the deal (the refinance wire, "
        "see cash_out_routi) MINUS the total cash put into it before the refinance (down payment, closing "
        "costs, points, out-of-pocket rehab, hard-money interest, holding costs). Negative means that much "
        "of your own money is still left in the deal (e.g. -26587 = $26,587 left in); positive means you "
        "took out more than you invested."))
    cash_out_routi: Optional[float] = Field(None, description=(
        "'Routi': the cash wire received at the refinance closing table, in dollars: the new loan "
        "(ARV x LTV) minus the hard-money payoff, refinance closing costs, refinance points and the cash "
        "reserve. Gross, before subtracting what was invested (that subtraction is cash_out)."))
    cash_on_cash: Optional[float] = Field(None, description=(
        "Cash-on-cash return in percent: yearly cash flow divided by the cash left in the deal. "
        "-1 means infinite (no cash left in the deal); -2 means not applicable."))
    roi: Optional[float] = Field(None, description=(
        "Return on investment in percent: net profit divided by the cash invested. "
        "-1 means infinite (no cash left in the deal); -2 means not applicable."))
    equity: Optional[float] = Field(None, description=(
        "Equity after the refinance, in dollars: ARV minus the new loan balance."))
    net_profit: Optional[float] = Field(None, description=(
        "Net profit created by the deal, in dollars: equity plus cash out (a negative cash out, money "
        "left in, reduces it)."))
    total_cash_needed_for_deal: Optional[float] = Field(None, description=(
        "Total cash needed to do the deal, in dollars: down payment, buy closing costs, points, "
        "out-of-pocket rehab, hard-money interest and holding costs until the refinance."))
    total_cash_needed_for_deal_with_buffer: Optional[float] = Field(None, description=(
        "total_cash_needed_for_deal plus the rehab contingency buffer, in dollars."))
    messages: Optional[list[str]] = Field(None, description=_MESSAGES)
    breakdowns: Optional[Dict[str, List[CalcStep]]] = Field(None, description=_BREAKDOWNS)


class analyzeFlipRes(BaseModel):
    """Result of the fix-and-flip calculation. All money in plain dollars."""

    net_profit: float = Field(..., description=(
        "Net profit of the flip, in dollars: sale price minus purchase, rehab, buy and sell closing "
        "costs, agent fees, hard-money points and interest, holding costs and capital gains tax."))
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
        "Taxes, insurance, HOA and utilities over the holding time, in dollars."))
    total_hml_interest: float = Field(..., description=(
        "Hard-money loan interest over the holding time, in dollars."))
    messages: Optional[list[str]] = Field(None, description=_MESSAGES)
    breakdowns: Optional[Dict[str, List[CalcStep]]] = Field(None, description=_BREAKDOWNS)
