from typing import Optional, Dict, List
from decimal import Decimal
from pydantic import BaseModel

from calc_breakdown import CalcStep


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
