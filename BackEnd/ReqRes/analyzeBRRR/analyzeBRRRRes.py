from typing import Dict, List, Optional
from decimal import Decimal
from pydantic import BaseModel

from ReqRes.calcStep import CalcStep


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

    # --- Calculation transparency (added) ---
    # `breakdowns` is a flat key->formula-string map the frontend can index by
    # metric (e.g. "cash_flow", "roi") to render hover tooltips. Strings are
    # safe to pass through to UI without computing anything client-side.
    breakdowns: Optional[Dict[str, str]] = None
    # `breakdown_steps` is the rich, ordered list of intermediate values used
    # primarily by the PDF report. Optional so legacy clients keep working.
    breakdown_steps: Optional[List[CalcStep]] = None
