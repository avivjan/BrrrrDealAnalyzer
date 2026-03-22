from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class AddLiquidityTransactionReq(BaseModel):
    date: datetime
    description: str
    amount: Decimal
    category: str
