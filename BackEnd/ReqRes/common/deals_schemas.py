"""Compact, cross-board deal views for the `/deals` endpoints (and the MCP tools
built from them). Small on purpose: no calculation breakdowns, no comps. Every
field is described with its unit and sign convention so an AI reading a row
cannot misread it (tests/test_mcp.py enforces the descriptions)."""

from datetime import datetime
from typing import List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

from ReqRes.common.active_deal_schemas import BrrrActiveDealRes, FlipActiveDealRes
from ReqRes.common.bought_deal_schemas import BoughtBrrrDealRes, BoughtFlipDealRes

Board = Literal["active", "bought"]

_BOARD = "'active' = My Deals board (being analysed or worked); 'bought' = Bought Deals board (properties we bought)."


class DealSummary(BaseModel):
    """One row of the compact deal list. Money in thousands where the name ends in _k, else plain dollars."""

    id: UUID = Field(..., description="Deal id; pass it to get_deal for the full record.")
    board: Board = Field(..., description=_BOARD)
    deal_type: Literal["BRRRR", "FLIP"] = Field(..., description="BRRRR (buy, rehab, rent, refinance) or FLIP (buy, rehab, sell).")
    address: str = Field(..., description="Property address as typed on the site.")
    stage: Optional[int] = Field(None, description="Active deals only: 1 New, 2 Working, 3 Brought (under contract), 4 Keep in Mind, 5 Dead.")
    section: Optional[int] = Field(None, description="Active deals only: 1 Wholesale, 2 Market, 3 Off Market.")
    bought_stage: Optional[str] = Field(None, description="Bought deals only: the purchase pipeline stage id (e.g. purchase, closed, rehab, refinanced, sold).")
    task: Optional[str] = Field(None, description="Current task or status note for the deal.")
    purchase_price_k: Optional[float] = Field(None, description="Purchase price in thousands of dollars (140 = $140,000).")
    rehab_cost_k: Optional[float] = Field(None, description="Rehab budget in thousands of dollars.")
    arv_or_sale_price_k: Optional[float] = Field(None, description="BRRRR: after-repair value; FLIP: projected sale price. Thousands of dollars.")
    rent_monthly: Optional[float] = Field(None, description="Monthly rent in dollars (BRRRR).")
    cash_flow_monthly: Optional[float] = Field(None, description="Monthly cash flow after the refinance in dollars (BRRRR); negative = costs money each month.")
    cash_on_cash_pct: Optional[float] = Field(None, description="Cash-on-cash return in percent. -1 = infinite (no cash left in the deal), -2 = not applicable.")
    roi_pct: Optional[float] = Field(None, description="Return on investment in percent. -1 = infinite, -2 = not applicable.")
    equity: Optional[float] = Field(None, description="Equity after the refinance in dollars (ARV minus the new loan).")
    net_profit: Optional[float] = Field(None, description="Net profit in dollars: BRRRR = equity plus cash out; FLIP = sale minus all costs.")
    total_cash_needed: Optional[float] = Field(None, description="Total cash needed to do the deal, in dollars.")
    cash_out: Optional[float] = Field(None, description=(
        "BRRRR cash out in dollars: total received from the deal (the refinance wire) minus total put in. "
        "NEGATIVE = that much of your own money is still left in the deal. See cash_left_in_deal."))
    cash_left_in_deal: Optional[float] = Field(None, description=(
        "Your own money still in the deal after the refinance, in dollars (never negative): -cash_out when "
        "cash_out is negative, else 0. The number to quote for 'how much did we leave in'."))
    cash_wire_at_refi: Optional[float] = Field(None, description=(
        "'Routi': the cash wire received at the refinance closing table, in dollars (new loan minus "
        "hard-money payoff, refinance costs, points and reserve), before subtracting what was invested."))
    created_at: Optional[datetime] = Field(None, description="When the deal was created on the site.")
    updated_at: Optional[datetime] = Field(None, description="Last edit on the site.")


class TopDeal(BaseModel):
    """A deal ranked by one metric."""

    id: UUID = Field(..., description="Deal id; pass it to get_deal for the full record.")
    board: Board = Field(..., description=_BOARD)
    deal_type: str = Field(..., description="BRRRR or FLIP.")
    address: str = Field(..., description="Property address.")
    value: float = Field(..., description="The metric this list is ranked by (dollars for equity / cash flow, percent for cash-on-cash).")


class PortfolioSummary(BaseModel):
    """Headline numbers across both boards, plus the top deals by the usual metrics."""

    active_count: int = Field(..., description="Deals on the My Deals board (being analysed or worked).")
    bought_count: int = Field(..., description="Properties we bought (Bought Deals board).")
    active_by_type: dict[str, int] = Field(default_factory=dict, description="Active deals per deal type (BRRRR / FLIP).")
    bought_by_type: dict[str, int] = Field(default_factory=dict, description="Bought deals per deal type.")
    active_by_stage: dict[str, int] = Field(default_factory=dict, description="Active deals per stage: 1 New, 2 Working, 3 Brought, 4 Keep in Mind, 5 Dead.")
    bought_by_stage: dict[str, int] = Field(default_factory=dict, description="Bought deals per purchase pipeline stage id.")
    bought_total_equity: float = Field(0.0, description="Sum of equity over the bought deals, in dollars.")
    bought_total_cash_flow_monthly: float = Field(0.0, description="Sum of monthly cash flow over the bought deals, in dollars.")
    bought_total_cash_invested: float = Field(0.0, description="Sum of total cash needed over the bought deals, in dollars.")
    bought_total_net_profit: float = Field(0.0, description="Sum of net profit over the bought deals, in dollars.")
    top_bought_by_equity: List[TopDeal] = Field(default_factory=list, description="Top 3 bought deals by equity (dollars).")
    top_bought_by_cash_flow: List[TopDeal] = Field(default_factory=list, description="Top 3 bought deals by monthly cash flow (dollars).")
    top_bought_by_cash_on_cash: List[TopDeal] = Field(default_factory=list, description="Top 3 bought deals by cash-on-cash (percent; infinite/-1 excluded).")
    top_active_by_cash_on_cash: List[TopDeal] = Field(default_factory=list, description="Top 3 active deals by cash-on-cash (percent).")


class DealDetail(BaseModel):
    """One deal in full (inputs, metrics, breakdowns, comps), whichever board it is on."""

    board: Board = Field(..., description=_BOARD)
    deal: Union[BrrrActiveDealRes, FlipActiveDealRes, BoughtBrrrDealRes, BoughtFlipDealRes] = Field(
        ..., description="The full record: every input (camelCase aliases, money in thousands), notes, comps, all metrics and the calculation breakdowns.")
