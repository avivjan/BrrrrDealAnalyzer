from pydantic import BaseModel, Field
from datetime import date
from typing import Optional
from decimal import Decimal


class LiquidityTransactionCreate(BaseModel):
    effective_date: date
    description: str = Field(..., min_length=1, max_length=500)
    amount_k: Decimal = Field(..., description="Signed amount in $k (positive=inflow, negative=outflow)")


class LiquidityTransactionUpdate(BaseModel):
    effective_date: Optional[date] = None
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    amount_k: Optional[Decimal] = None


class LiquidityTransactionRes(BaseModel):
    id: str
    effective_date: date
    description: str
    amount_k: float
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class LiquiditySettingsUpdate(BaseModel):
    opening_balance_k: Optional[Decimal] = None
    opening_balance_date: Optional[date] = None
    reserve_k: Optional[Decimal] = None


class LiquiditySettingsRes(BaseModel):
    opening_balance_k: float
    opening_balance_date: date
    reserve_k: float
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}
