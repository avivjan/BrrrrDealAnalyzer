from typing import Optional
from decimal import Decimal
from pydantic import BaseModel

class analyzeFlipRes(BaseModel):
    """Represents the result of the Flip calculation."""
    net_profit: Decimal
    roi: Decimal
    annualized_roi: Decimal
    total_cash_needed: Decimal
    total_holding_costs: Decimal
    total_hml_interest: Decimal
    messages: Optional[list[str]] = None

