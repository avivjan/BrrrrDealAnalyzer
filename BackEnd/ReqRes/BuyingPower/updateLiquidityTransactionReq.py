from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class UpdateLiquidityTransactionReq(BaseModel):
    date: Optional[datetime] = None
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    category: Optional[str] = None
