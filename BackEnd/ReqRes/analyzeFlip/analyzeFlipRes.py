from typing import Optional, Dict, List
from decimal import Decimal
from pydantic import BaseModel

from calc_breakdown import CalcStep


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
