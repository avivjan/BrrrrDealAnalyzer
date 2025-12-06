from typing import Optional
from decimal import Decimal
from pydantic import BaseModel


class analyzeBRRRRes(BaseModel):
    """Represents the result of the cash flow calculation."""
    cash_flow: Decimal
    dscr: Optional[Decimal] = None
    cash_out: Optional[Decimal] = None
    cash_on_cash: Optional[Decimal] = None
    roi: Optional[Decimal] = None
    equity: Optional[Decimal] = None
    net_profit: Optional[Decimal] = None
    total_cash_needed_for_deal:Optional[Decimal] = None
    messages: Optional[list[str]] = None
    
    
