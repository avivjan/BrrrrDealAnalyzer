from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import date
from typing import Annotated, Literal, Optional
from decimal import Decimal
from zoneinfo import available_timezones


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
    source_deal_board: Optional[Literal["my_deals", "bought"]] = Field(None, description=(
        "Set on a row imported from a BRRRR deal's Cash Needed schedule: the board of that deal. Null = a manual transaction."))
    source_deal_id: Optional[str] = Field(None, description="The id of the deal the row was imported from.")
    source_item_key: Optional[str] = Field(None, description="The schedule item the row is, e.g. 'hml_interest_paid_monthly'.")
    source_occurrence_number: Optional[int] = Field(None, description=(
        "The n-th row of that item in the deal (1-based). With the board, the deal and the item it is the row's identity."))
    sequence_within_day: Optional[int] = Field(None, description="The order among the deal's rows on the same date.")
    created_because_refi_is_late: bool = Field(False, description=(
        "A month of carrying costs added while the deal's refi was late (its planned date passed, not approved)."))
    no_longer_in_the_deal: bool = Field(False, description=(
        "The deal no longer has this row; it stayed because you changed its date or amount."))
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

_TIMEZONE_NAME = (
    "The owner's IANA time zone (e.g. America/New_York): what 'today' is when no date is sent, as on an MCP call "
    "(overdue rows, late refis). The website sends the browser's own date.")


class LiquiditySettingsUpdate(BaseModel):
    """Partial update: only the fields sent change. Sending mercury_account_ids_counted_as_cash as null
    counts every active account again."""

    opening_balance_dollars: Optional[Decimal] = None
    opening_balance_date: Optional[date] = None
    reserve_dollars: Optional[Decimal] = None
    mercury_account_ids_counted_as_cash: Optional[list[MercuryAccountId]] = Field(
        None, max_length=100, description=_MERCURY_ACCOUNTS_COUNTED_AS_CASH)
    timezone_name: Optional[str] = Field(None, max_length=64, description=_TIMEZONE_NAME)

    @field_validator("timezone_name")
    @classmethod
    def _timezone_name_is_a_known_iana_zone(cls, timezone_name: Optional[str]) -> Optional[str]:
        if timezone_name is not None and timezone_name not in available_timezones():
            raise ValueError("timezone_name must be an IANA time zone, e.g. America/New_York.")
        return timezone_name


class LiquiditySettingsRes(BaseModel):
    opening_balance_dollars: float
    opening_balance_date: date
    reserve_dollars: float
    mercury_account_ids_counted_as_cash: Optional[list[str]] = Field(None, description=_MERCURY_ACCOUNTS_COUNTED_AS_CASH)
    timezone_name: str = Field("America/New_York", description=_TIMEZONE_NAME)
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}
