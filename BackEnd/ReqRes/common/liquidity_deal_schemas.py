"""Requests and responses of /liquidity/deals/*: a BRRRR deal's Cash Needed rows in the liquidity timeline.

Mirrored on the frontend (`src/types/liquidityDeals.ts`). Keep in sync. Amounts are exact dollars (to the cent),
positive = money in, negative = money out.
"""

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

LiquidityDealBoard = Literal["my_deals", "bought"]
DealMilestone = Literal["contract_signed", "purchase_closed", "rehab_completed", "tenant_moved_in", "refi_closed"]
DealCashRowChangeKind = Literal["added", "updated", "removed", "unchanged", "kept_done", "kept_no_longer_in_the_deal"]

_TODAY = "Your local date (ISO). Omitted = today in the time zone of the liquidity settings."


class UseDealValueForField(BaseModel):
    """Take the deal's value for one field of one row although you changed that field by hand."""

    transaction_id: str = Field(..., min_length=1, max_length=64)
    field: Literal["date", "amount"]


class DealCashRowsImportReq(BaseModel):
    use_deal_value_for: list[UseDealValueForField] = Field(default_factory=list, max_length=2000, description=(
        "The (row, field) pairs where the deal's value replaces the one you set by hand (the 'Use $2,100' taps)."))
    today: Optional[date] = Field(None, description=_TODAY)


class DealMilestoneChangeReq(BaseModel):
    milestone: DealMilestone
    new_date: date = Field(..., description="The milestone's date: the real one when approving, or a new planned one.")
    approve: bool = Field(True, description="True = it happened on new_date (approved). False = still planned, on new_date.")
    use_deal_value_for: list[UseDealValueForField] = Field(default_factory=list, max_length=2000)
    today: Optional[date] = Field(None, description=_TODAY)


class LateRefiRefreshReq(BaseModel):
    today: Optional[date] = Field(None, description=_TODAY)


class RemoveOpenDealRowsReq(BaseModel):
    earnest_money_refund_date: Optional[date] = Field(None, description=(
        "When set, the deal's earnest money deposit comes back as money in on this date (a dead deal's refund)."))


class DealCashRowChangeRes(BaseModel):
    change_kind: DealCashRowChangeKind = Field(..., description=(
        "added / updated (date, amount or text) / removed / unchanged / kept_done (a done row is never touched) / "
        "kept_no_longer_in_the_deal (the deal dropped it, you had changed it, so it stays)."))
    item_key: str
    occurrence_number: int
    description: str
    transaction_id: Optional[str] = Field(None, description="Null for a row still to be added.")
    date_before: Optional[date] = None
    date_after: Optional[date] = None
    amount_dollars_before: Optional[float] = None
    amount_dollars_after: Optional[float] = None
    deal_date_not_applied_because_you_changed_it: Optional[date] = Field(None, description=(
        "The deal's new date for a row whose date you set by hand: kept out ('Use <date>' takes it)."))
    deal_amount_dollars_not_applied_because_you_changed_it: Optional[float] = Field(None, description=(
        "The deal's new amount for a row whose amount you set by hand: kept out ('Use $<amount>' takes it)."))
    created_because_refi_is_late: bool = False


class DealCashRowChangeCountsRes(BaseModel):
    added: int
    updated: int
    removed: int
    unchanged: int
    kept_done: int
    kept_no_longer_in_the_deal: int
    conflicts_with_your_changes: int = Field(..., description="Rows where a value you set by hand was kept over the deal's.")


class DealMilestoneDateChangeRes(BaseModel):
    milestone: DealMilestone
    date_before: date
    date_after: date


class DealCashRowChangesRes(BaseModel):
    """The before -> after list of an import, a re-sync or a milestone change. A preview changes nothing."""

    deal_board: LiquidityDealBoard
    deal_id: str
    deal_address: str
    changes: list[DealCashRowChangeRes] = Field(..., description="Every row of the deal, in date order (after the change).")
    change_counts: DealCashRowChangeCountsRes
    milestone_date_changes: list[DealMilestoneDateChangeRes] = Field(default_factory=list, description=(
        "A milestone change only: every milestone whose date moves (moving the purchase closing moves the later ones)."))
    key_dates: list["DealKeyDateRes"] = Field(default_factory=list, description=(
        "An import preview / import only: the deal's key dates as its Cash Needed table shows them, in date order."))


class DealMilestoneRes(BaseModel):
    milestone: DealMilestone
    planned_date: date
    approved_at: Optional[datetime] = Field(None, description="When it was approved; null = still planned.")
    is_overdue: bool = Field(..., description="The planned date passed and it is not approved.")


class DealKeyDateRes(BaseModel):
    key: str = Field(..., description=(
        "contract_signed, purchase_closed, rehab_completed, tenant_moved_in, property_tax_bill_paid_on_november_30 or refi_closed."))
    date: date
    description: str


class ImportedLiquidityDealRes(BaseModel):
    deal_board: LiquidityDealBoard
    deal_id: str
    deal_address: str
    my_deals_deal_id_it_was_moved_from: Optional[str] = Field(None, description=(
        "A Bought deal moved from My Deals: the My Deals copy's id (that copy is in liquidity through this one)."))
    liquidity_rows_out_of_date: bool = Field(..., description="A deal save changed its rows and that change is not confirmed.")
    open_row_count: int
    done_row_count: int
    overdue_open_row_count: int
    late_refi_row_count: int
    refi_is_late: bool
    milestones: list[DealMilestoneRes]
    key_dates: list[DealKeyDateRes] = Field(default_factory=list, description=(
        "The deal's key dates as its Cash Needed table shows them, in date order (markers, not cash): the five "
        "milestones and the Nov 30 tax bill paid from the tax bucket while it falls inside the hold."))


class LateRefiRefreshDealRes(BaseModel):
    deal_board: LiquidityDealBoard
    deal_id: str
    deal_address: str
    added_row_count: int


class LateRefiRefreshRes(BaseModel):
    added_row_count: int
    deals_with_added_rows: list[LateRefiRefreshDealRes]


class RemoveOpenDealRowsRes(BaseModel):
    removed_row_count: int
    earnest_money_refund_transaction_id: Optional[str] = None


DealCashRowChangesRes.model_rebuild()
