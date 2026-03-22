from datetime import datetime
from decimal import Decimal
from typing import List
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LiquidityTransactionRes(BaseModel):
    id: UUID
    date: datetime
    description: str
    amount: Decimal
    category: str

    model_config = ConfigDict(from_attributes=True)


class GetLiquidityRes(BaseModel):
    transactions: List[LiquidityTransactionRes]
    total_liquidity: Decimal
