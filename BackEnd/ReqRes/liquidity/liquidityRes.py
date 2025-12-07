from pydantic import BaseModel
from decimal import Decimal

class LiquidityRes(BaseModel):
    big_whale_amount: Decimal
    mini_whale_amount: Decimal
    
    class Config:
        from_attributes = True

