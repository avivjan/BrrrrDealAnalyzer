from pydantic import BaseModel
from decimal import Decimal

class LiquidityUpdate(BaseModel):
    big_whale_amount: Decimal
    mini_whale_amount: Decimal

