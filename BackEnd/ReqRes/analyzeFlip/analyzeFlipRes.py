from typing import Dict, List, Optional
from decimal import Decimal
from pydantic import BaseModel

from ReqRes.calcStep import CalcStep


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

    # --- Calculation transparency (added) ---
    # See analyzeBRRRRes for the contract; same shape across deal types so the
    # frontend can use the same component for both.
    breakdowns: Optional[Dict[str, str]] = None
    breakdown_steps: Optional[List[CalcStep]] = None
