from typing import Optional

from pydantic import BaseModel


class CalcCashFlowRes(BaseModel):
    """Represents the result of the cash flow calculation."""
    cash_flow: float
    dscr: Optional[float] = None
    cash_out: Optional[float] = None
    messages: Optional[list[str]] = None
    
    