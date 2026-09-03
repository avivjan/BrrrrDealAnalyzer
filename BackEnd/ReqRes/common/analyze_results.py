"""Response models for the /analyze/brrr and /analyze/flip calculation results."""

from typing import Optional, Dict, List
from decimal import Decimal
from pydantic import BaseModel

from ReqRes.common.calc_step import CalcStep


class analyzeBRRRRes(BaseModel):
    """Represents the result of the cash flow calculation."""
    cash_flow: float
    dscr: Optional[float] = None
    cash_out: Optional[float] = None
    cash_out_routi: Optional[float] = None
    cash_on_cash: Optional[float] = None
    roi: Optional[float] = None
    equity: Optional[float] = None
    net_profit: Optional[float] = None
    total_cash_needed_for_deal:Optional[float] = None
    total_cash_needed_for_deal_with_buffer: Optional[float] = None
    messages: Optional[list[str]] = None
    # Self-documenting calculation steps keyed by metric (e.g. "cash_flow",
    # "roi", "net_profit"). Frontend can filter by key to render hover/PDF
    # explanations of how each headline metric was derived.
    breakdowns: Optional[Dict[str, List[CalcStep]]] = None


class analyzeFlipRes(BaseModel):
    """Represents the result of the Flip calculation."""
    net_profit: float
    roi: float
    annualized_roi: float
    total_cash_needed: float
    total_cash_needed_with_buffer: float
    total_holding_costs: float
    total_hml_interest: float
    messages: Optional[list[str]] = None
    # Self-documenting calculation steps keyed by metric (e.g. "net_profit",
    # "roi", "annualized_roi"). Frontend can filter by key to render hover/PDF
    # explanations of how each headline metric was derived.
    breakdowns: Optional[Dict[str, List[CalcStep]]] = None
