from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import date
from typing import Literal, Optional
from decimal import Decimal


# Mirrored on the frontend (`src/types/liquidity.ts`). Keep in sync.
LiquidityFrequency = Literal[
    "daily", "weekly", "biweekly", "monthly", "quarterly", "yearly"
]


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


class LiquidityRecurringTransactionCreate(BaseModel):
    """Definition of a repeating cash-flow rule.

    Exactly one of `end_date` / `occurrences` may be set (both may be null
    for an open-ended series; the frontend caps display at the visible
    horizon).
    """

    description: str = Field(..., min_length=1, max_length=500)
    amount_k: Decimal = Field(
        ..., description="Signed amount in $k (positive=inflow, negative=outflow)"
    )
    start_date: date
    end_date: Optional[date] = None
    occurrences: Optional[int] = Field(
        None,
        ge=1,
        le=2000,
        description="Optional cap on the number of occurrences (1-based).",
    )
    frequency: LiquidityFrequency
    interval: int = Field(
        1, ge=1, le=365, description="'Every N units' multiplier on top of frequency."
    )

    @field_validator("amount_k")
    @classmethod
    def _amount_not_zero(cls, v: Decimal) -> Decimal:
        if v == 0:
            raise ValueError("amount_k must be non-zero.")
        return v

    @model_validator(mode="after")
    def _validate_window(self) -> "LiquidityRecurringTransactionCreate":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date.")
        return self


class LiquidityRecurringTransactionUpdate(BaseModel):
    """Partial update — only provided fields are written."""

    description: Optional[str] = Field(None, min_length=1, max_length=500)
    amount_k: Optional[Decimal] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    occurrences: Optional[int] = Field(None, ge=1, le=2000)
    frequency: Optional[LiquidityFrequency] = None
    interval: Optional[int] = Field(None, ge=1, le=365)

    # The `end_date < start_date` invariant has to be checked at the CRUD
    # layer once we merge the patch into the existing row, since either
    # field may be missing from the patch payload.


class LiquidityRecurringTransactionRes(BaseModel):
    id: str
    description: str
    amount_k: float
    start_date: date
    end_date: Optional[date] = None
    occurrences: Optional[int] = None
    frequency: LiquidityFrequency
    interval: int
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
