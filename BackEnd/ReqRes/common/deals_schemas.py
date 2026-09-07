"""Compact, cross-board deal views for the `/deals` endpoints (and the MCP tools
built from them). Small on purpose: no calculation breakdowns, no comps."""

from datetime import datetime
from typing import List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

from ReqRes.common.active_deal_schemas import BrrrActiveDealRes, FlipActiveDealRes
from ReqRes.common.bought_deal_schemas import BoughtBrrrDealRes, BoughtFlipDealRes

Board = Literal["active", "bought"]


class DealSummary(BaseModel):
    """One row of the compact deal list. Money in thousands where the name says so."""

    id: UUID
    board: Board
    deal_type: Literal["BRRRR", "FLIP"]
    address: str
    stage: Optional[int] = None            # active deals: 1 New, 2 Working, 3 Brought, 4 Keep in Mind, 5 Dead
    section: Optional[int] = None          # active deals: 1 Wholesale, 2 Market, 3 Off Market
    bought_stage: Optional[str] = None     # bought deals: pipeline stage id
    task: Optional[str] = None
    purchase_price_k: Optional[float] = None
    rehab_cost_k: Optional[float] = None
    arv_or_sale_price_k: Optional[float] = None
    rent_monthly: Optional[float] = None
    cash_flow_monthly: Optional[float] = None
    cash_on_cash_pct: Optional[float] = None
    roi_pct: Optional[float] = None
    equity: Optional[float] = None
    net_profit: Optional[float] = None
    total_cash_needed: Optional[float] = None
    cash_out: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TopDeal(BaseModel):
    id: UUID
    board: Board
    deal_type: str
    address: str
    value: float


class PortfolioSummary(BaseModel):
    """Headline numbers across both boards, plus the top deals by the usual metrics."""

    active_count: int
    bought_count: int
    active_by_type: dict[str, int] = Field(default_factory=dict)
    bought_by_type: dict[str, int] = Field(default_factory=dict)
    active_by_stage: dict[str, int] = Field(default_factory=dict)
    bought_by_stage: dict[str, int] = Field(default_factory=dict)
    bought_total_equity: float = 0.0
    bought_total_cash_flow_monthly: float = 0.0
    bought_total_cash_invested: float = 0.0
    bought_total_net_profit: float = 0.0
    top_bought_by_equity: List[TopDeal] = Field(default_factory=list)
    top_bought_by_cash_flow: List[TopDeal] = Field(default_factory=list)
    top_bought_by_cash_on_cash: List[TopDeal] = Field(default_factory=list)
    top_active_by_cash_on_cash: List[TopDeal] = Field(default_factory=list)


class DealDetail(BaseModel):
    """One deal in full (inputs, metrics, breakdowns, comps), whichever board it is on."""

    board: Board
    deal: Union[BrrrActiveDealRes, FlipActiveDealRes, BoughtBrrrDealRes, BoughtFlipDealRes]
