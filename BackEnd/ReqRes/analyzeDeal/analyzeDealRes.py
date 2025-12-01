from typing import Optional

from pydantic import BaseModel


class analyzeDealRes(BaseModel):
    """Represents the result of the cash flow calculation."""
    cash_flow: float
    dscr: Optional[float] = None
    cash_out: Optional[float] = None
    cash_on_cash: Optional[float] = None
    roi: Optional[float] = None
    equity: Optional[float] = None
    net_profit: Optional[float] = None
    total_cash_needed_for_deal:Optional[float] = None
    messages: Optional[list[str]] = None
    
    
