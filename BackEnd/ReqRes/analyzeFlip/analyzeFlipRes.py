from typing import Optional
from pydantic import BaseModel

class analyzeFlipRes(BaseModel):
    """Represents the result of the Flip calculation."""
    net_profit: float
    roi: float
    annualized_roi: float
    total_cash_needed: float
    total_holding_costs: float
    total_hml_interest: float
    messages: Optional[list[str]] = None

