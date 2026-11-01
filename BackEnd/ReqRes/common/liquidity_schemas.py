from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import date
from typing import Annotated, Literal, Optional
from decimal import Decimal


# Mirrored on the frontend (`src/types/liquidity.ts`). Keep in sync.
LiquidityFrequency = Literal[
    "daily", "weekly", "biweekly", "monthly", "quarterly", "yearly"
]


class LiquidityTransactionCreate(BaseModel):
    effective_date: date
    description: str = Field(..., min_length=1, max_length=500)
    amount_dollars: Decimal = Field(..., description="Signed amount in exact dollars, to the cent (positive=inflow, negative=outflow)")


class LiquidityTransactionUpdate(BaseModel):
    effective_date: Optional[date] = None
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    amount_dollars: Optional[Decimal] = None


class LiquidityTransactionRes(BaseModel):
    id: str
    effective_date: date
    description: str
    amount_dollars: float
    done_at: Optional[str] = Field(None, description=(
        "When the row was marked done (the money moved, or the hold was released); null = still open. An open row dated "
        "before today is overdue: money out counts on today, money in is not counted until it is re-dated or done."))
    originally_planned_date: Optional[date] = Field(None, description="The date the row was first created or imported with.")
    user_overrode_date: bool = Field(False, description="The date was changed by hand; a re-sync from a deal keeps it.")
    user_overrode_amount: bool = Field(False, description="The amount was changed by hand; a re-sync from a deal keeps it.")
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


LiquidityTransactionBulkAction = Literal["mark_done", "mark_not_done", "move_to_date", "postpone_by_days"]


class LiquidityTransactionBulkActionReq(BaseModel):
    """One action on several one-off transactions at once (the timeline's bulk select)."""

    transaction_ids: list[str] = Field(..., min_length=1, max_length=500)
    action: LiquidityTransactionBulkAction
    new_effective_date: Optional[date] = Field(None, description="For move_to_date: the date every row moves to.")
    postpone_by_days: Optional[int] = Field(None, ge=1, le=3660, description="For postpone_by_days: how many days each row moves later.")

    @model_validator(mode="after")
    def _each_action_has_its_value(self) -> "LiquidityTransactionBulkActionReq":
        if self.action == "move_to_date" and self.new_effective_date is None:
            raise ValueError("move_to_date needs new_effective_date.")
        if self.action == "postpone_by_days" and self.postpone_by_days is None:
            raise ValueError("postpone_by_days needs postpone_by_days.")
        return self


class LiquidityRecurringTransactionCreate(BaseModel):
    """Definition of a repeating cash-flow rule.

    Exactly one of `end_date` / `occurrences` may be set (both may be null
    for an open-ended series; the frontend caps display at the visible
    horizon).
    """

    description: str = Field(..., min_length=1, max_length=500)
    amount_dollars: Decimal = Field(
        ..., description="Signed amount in exact dollars, to the cent (positive=inflow, negative=outflow)"
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

    @field_validator("amount_dollars")
    @classmethod
    def _amount_not_zero(cls, v: Decimal) -> Decimal:
        if v == 0:
            raise ValueError("amount_dollars must be non-zero.")
        return v

    @model_validator(mode="after")
    def _validate_window(self) -> "LiquidityRecurringTransactionCreate":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date.")
        return self


class LiquidityRecurringTransactionUpdate(BaseModel):
    """Partial update — only provided fields are written."""

    description: Optional[str] = Field(None, min_length=1, max_length=500)
    amount_dollars: Optional[Decimal] = None
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
    amount_dollars: float
    start_date: date
    end_date: Optional[date] = None
    occurrences: Optional[int] = None
    frequency: LiquidityFrequency
    interval: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


MercuryAccountId = Annotated[str, Field(min_length=1, max_length=100)]
_MERCURY_ACCOUNTS_COUNTED_AS_CASH = (
    "The Mercury account ids whose balance counts as cash on hand (the operating accounts). "
    "Null = every active account. Leave the tax bucket and the HYSA out, so the deposits into them read as money out."
)


class LiquiditySettingsUpdate(BaseModel):
    """Partial update: only the fields sent change. Sending mercury_account_ids_counted_as_cash as null
    counts every active account again."""

    opening_balance_dollars: Optional[Decimal] = None
    opening_balance_date: Optional[date] = None
    reserve_dollars: Optional[Decimal] = None
    mercury_account_ids_counted_as_cash: Optional[list[MercuryAccountId]] = Field(
        None, max_length=100, description=_MERCURY_ACCOUNTS_COUNTED_AS_CASH)


class LiquiditySettingsRes(BaseModel):
    opening_balance_dollars: float
    opening_balance_date: date
    reserve_dollars: float
    mercury_account_ids_counted_as_cash: Optional[list[str]] = Field(None, description=_MERCURY_ACCOUNTS_COUNTED_AS_CASH)
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}
