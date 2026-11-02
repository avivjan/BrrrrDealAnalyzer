"""The /liquidity/deals/* business logic: import a BRRRR deal's Cash Needed rows (always after a preview), re-sync them,
approve or move its milestones (written back to the deal), add the late-refi months, and clean up on delete / dead.

Every write here goes through `apply_deal_cash_row_changes` (deal_cash_rows.py), so the identity, the Done rows and
your overrides follow the same rules everywhere. Previews never write.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from BL.analyze.common.validation import validate_brrr_inputs_for_saved_deal
from BL.liquidity.dealCashRows.deal_cash_rows import (
    DEAL_BOARD_BOUGHT, DEAL_BOARD_MY_DEALS, DEAL_MODEL_BY_BOARD, DealBoard, DealCashRowChange,
    apply_deal_cash_row_changes, deal_as_attributes, diff_deal_cash_rows, imported_rows_of_deal,
    planned_cash_rows_including_late_refi_months, refi_is_late,
)
from BL.liquidity.dealCashRows.deal_milestones import (
    DEAL_MILESTONES_IN_ORDER, DealMilestone, approved_at_of_milestone, deal_columns_with_milestone_on,
    milestone_is_overdue, planned_date_of_milestone,
)
from DAL.crud.liquidity import get_settings
from DAL.data_models import BoughtBrrrDeal, LiquidityTransaction
from ReqRes.common.liquidity_deal_schemas import (
    DealCashRowChangeCountsRes, DealCashRowChangeRes, DealCashRowChangesRes, DealMilestoneChangeReq,
    DealMilestoneDateChangeRes, DealMilestoneRes, ImportedLiquidityDealRes, LateRefiRefreshDealRes, LateRefiRefreshRes,
    RemoveOpenDealRowsRes, UseDealValueForField,
)

DEFAULT_LIQUIDITY_TIMEZONE_NAME = "America/New_York"


class LiquidityDealNotFoundError(Exception):
    """No BRRRR deal with that id on that board."""


class DealImportedThroughItsBoughtCopyError(Exception):
    """A My Deals deal whose Bought copy is already in the liquidity timeline: importing it would count the property twice."""


def today_for_liquidity(db: Session, today: Optional[date]) -> date:
    """The date the caller sent (the browser's local date), else today in the settings' time zone."""
    if today is not None:
        return today
    settings = get_settings(db)
    return datetime.now(ZoneInfo((settings.timezone_name if settings else None) or DEFAULT_LIQUIDITY_TIMEZONE_NAME)).date()


def find_brrr_deal(db: Session, deal_board: DealBoard, deal_id: str):
    try:
        deal_uuid = uuid.UUID(str(deal_id))
    except ValueError:
        raise LiquidityDealNotFoundError()
    deal = db.query(DEAL_MODEL_BY_BOARD[deal_board]).filter(DEAL_MODEL_BY_BOARD[deal_board].id == deal_uuid).first()
    if deal is None:
        raise LiquidityDealNotFoundError()
    return deal


def bought_copy_in_liquidity_of_my_deals_deal(db: Session, my_deals_deal_id) -> Optional[BoughtBrrrDeal]:
    for bought_copy in db.query(BoughtBrrrDeal).filter(BoughtBrrrDeal.source_deal_id == my_deals_deal_id).all():
        if imported_rows_of_deal(db, DEAL_BOARD_BOUGHT, bought_copy.id):
            return bought_copy
    return None


def _refuse_a_my_deals_deal_imported_through_its_bought_copy(db: Session, deal_board: DealBoard, deal) -> None:
    if deal_board == DEAL_BOARD_MY_DEALS and bought_copy_in_liquidity_of_my_deals_deal(db, deal.id) is not None:
        raise DealImportedThroughItsBoughtCopyError()


def _use_deal_value_for_pairs(use_deal_value_for: Iterable[UseDealValueForField]) -> frozenset:
    return frozenset((choice.transaction_id, choice.field) for choice in use_deal_value_for)


def _change_to_res(change: DealCashRowChange) -> DealCashRowChangeRes:
    def as_float(amount: Optional[Decimal]) -> Optional[float]:
        return None if amount is None else float(amount)
    return DealCashRowChangeRes(
        change_kind=change.change_kind, item_key=change.item_key, occurrence_number=change.occurrence_number,
        description=change.description, transaction_id=change.transaction_id,
        date_before=change.date_before, date_after=change.date_after,
        amount_dollars_before=as_float(change.amount_before), amount_dollars_after=as_float(change.amount_after),
        deal_date_not_applied_because_you_changed_it=change.deal_date_not_applied_because_you_changed_it,
        deal_amount_dollars_not_applied_because_you_changed_it=as_float(change.deal_amount_not_applied_because_you_changed_it),
        created_because_refi_is_late=change.created_because_refi_is_late,
    )


def _changes_res(deal_board: DealBoard, deal, changes: list[DealCashRowChange],
                 milestone_date_changes: Optional[list[DealMilestoneDateChangeRes]] = None) -> DealCashRowChangesRes:
    def count_of(change_kind: str) -> int:
        return sum(1 for change in changes if change.change_kind == change_kind)
    return DealCashRowChangesRes(
        deal_board=deal_board, deal_id=str(deal.id), deal_address=deal.address,
        changes=[_change_to_res(change) for change in changes],
        change_counts=DealCashRowChangeCountsRes(
            added=count_of("added"), updated=count_of("updated"), removed=count_of("removed"),
            unchanged=count_of("unchanged"), kept_done=count_of("kept_done"),
            kept_no_longer_in_the_deal=count_of("kept_no_longer_in_the_deal"),
            conflicts_with_your_changes=sum(1 for change in changes if change.deal_date_not_applied_because_you_changed_it is not None
                                            or change.deal_amount_not_applied_because_you_changed_it is not None),
        ),
        milestone_date_changes=milestone_date_changes or [],
    )


# --- Import and re-sync -------------------------------------------------------------------------------------------

def preview_deal_import(db: Session, deal_board: DealBoard, deal_id: str, use_deal_value_for: list[UseDealValueForField],
                        today: Optional[date]) -> DealCashRowChangesRes:
    deal = find_brrr_deal(db, deal_board, deal_id)
    _refuse_a_my_deals_deal_imported_through_its_bought_copy(db, deal_board, deal)
    planned_rows = planned_cash_rows_including_late_refi_months(deal, today_for_liquidity(db, today))
    changes = diff_deal_cash_rows(planned_rows, imported_rows_of_deal(db, deal_board, deal.id), _use_deal_value_for_pairs(use_deal_value_for))
    return _changes_res(deal_board, deal, changes)


def import_deal(db: Session, deal_board: DealBoard, deal_id: str, use_deal_value_for: list[UseDealValueForField],
                today: Optional[date]) -> DealCashRowChangesRes:
    """Import the deal's rows, or re-sync them (the same call: safe to press twice). Clears 'liquidity out of date'."""
    deal = find_brrr_deal(db, deal_board, deal_id)
    _refuse_a_my_deals_deal_imported_through_its_bought_copy(db, deal_board, deal)
    planned_rows = planned_cash_rows_including_late_refi_months(deal, today_for_liquidity(db, today))
    changes = apply_deal_cash_row_changes(db, deal_board, deal.id, planned_rows, _use_deal_value_for_pairs(use_deal_value_for))
    deal.liquidity_rows_out_of_date = False
    db.commit()
    return _changes_res(deal_board, deal, changes)


# --- Milestones ---------------------------------------------------------------------------------------------------

def _deal_with_milestone_change(deal, change: DealMilestoneChangeReq):
    """The deal's attributes after the change (validated like a deal save), and the milestones whose date moves."""
    changed_columns = deal_columns_with_milestone_on(deal, change.milestone, change.new_date, change.approve)
    changed_deal = deal_as_attributes(deal, **changed_columns)
    validate_brrr_inputs_for_saved_deal(changed_deal)
    milestone_date_changes = [
        DealMilestoneDateChangeRes(milestone=milestone, date_before=planned_date_of_milestone(deal, milestone),
                                   date_after=planned_date_of_milestone(changed_deal, milestone))
        for milestone in DEAL_MILESTONES_IN_ORDER
        if planned_date_of_milestone(deal, milestone) != planned_date_of_milestone(changed_deal, milestone)
    ]
    return changed_columns, changed_deal, milestone_date_changes


def preview_milestone_change(db: Session, deal_board: DealBoard, deal_id: str, change: DealMilestoneChangeReq) -> DealCashRowChangesRes:
    deal = find_brrr_deal(db, deal_board, deal_id)
    _changed_columns, changed_deal, milestone_date_changes = _deal_with_milestone_change(deal, change)
    planned_rows = planned_cash_rows_including_late_refi_months(changed_deal, today_for_liquidity(db, change.today))
    changes = diff_deal_cash_rows(planned_rows, imported_rows_of_deal(db, deal_board, deal.id), _use_deal_value_for_pairs(change.use_deal_value_for))
    return _changes_res(deal_board, deal, changes, milestone_date_changes)


def apply_milestone_change(db: Session, deal_board: DealBoard, deal_id: str, change: DealMilestoneChangeReq) -> DealCashRowChangesRes:
    """Write the milestone's date (and approval) to the deal and re-sync its rows, in one transaction."""
    deal = find_brrr_deal(db, deal_board, deal_id)
    changed_columns, changed_deal, milestone_date_changes = _deal_with_milestone_change(deal, change)
    planned_rows = planned_cash_rows_including_late_refi_months(changed_deal, today_for_liquidity(db, change.today))
    changes = apply_deal_cash_row_changes(db, deal_board, deal.id, planned_rows, _use_deal_value_for_pairs(change.use_deal_value_for))
    for column_name, value in changed_columns.items():
        setattr(deal, column_name, value)
    deal.liquidity_rows_out_of_date = False
    db.commit()
    return _changes_res(deal_board, deal, changes, milestone_date_changes)


# --- The late-refi months -----------------------------------------------------------------------------------------

def _imported_deals(db: Session) -> list[tuple[DealBoard, object]]:
    imported_deal_keys = (db.query(LiquidityTransaction.source_deal_board, LiquidityTransaction.source_deal_id)
                          .filter(LiquidityTransaction.source_deal_id.isnot(None)).distinct().all())
    imported_deals = []
    for deal_board, deal_id in imported_deal_keys:
        if deal_board not in DEAL_MODEL_BY_BOARD:
            continue
        deal = db.query(DEAL_MODEL_BY_BOARD[deal_board]).filter(DEAL_MODEL_BY_BOARD[deal_board].id == deal_id).first()
        if deal is not None:
            imported_deals.append((deal_board, deal))
    return sorted(imported_deals, key=lambda board_and_deal: (board_and_deal[1].address or "", str(board_and_deal[1].id)))


def refresh_late_refis(db: Session, today: Optional[date]) -> LateRefiRefreshRes:
    """Add the carrying-cost months still missing for every imported deal whose refi is late. Idempotent by identity."""
    resolved_today = today_for_liquidity(db, today)
    deals_with_added_rows = []
    for deal_board, deal in _imported_deals(db):
        if not refi_is_late(deal, resolved_today):
            continue
        added_changes = apply_deal_cash_row_changes(db, deal_board, deal.id, planned_cash_rows_including_late_refi_months(deal, resolved_today),
                                                    only_add_missing_late_refi_rows=True)
        if added_changes:
            deals_with_added_rows.append(LateRefiRefreshDealRes(deal_board=deal_board, deal_id=str(deal.id), deal_address=deal.address,
                                                                added_row_count=len(added_changes)))
    db.commit()
    return LateRefiRefreshRes(added_row_count=sum(deal.added_row_count for deal in deals_with_added_rows),
                              deals_with_added_rows=deals_with_added_rows)


# --- The Deals panel ----------------------------------------------------------------------------------------------

def list_imported_deals(db: Session, today: Optional[date]) -> list[ImportedLiquidityDealRes]:
    resolved_today = today_for_liquidity(db, today)
    imported_deals = []
    for deal_board, deal in _imported_deals(db):
        rows = imported_rows_of_deal(db, deal_board, deal.id)
        open_rows = [row for row in rows if row.done_at is None]
        imported_deals.append(ImportedLiquidityDealRes(
            deal_board=deal_board, deal_id=str(deal.id), deal_address=deal.address,
            my_deals_deal_id_it_was_moved_from=str(deal.source_deal_id) if deal_board == DEAL_BOARD_BOUGHT and deal.source_deal_id else None,
            liquidity_rows_out_of_date=bool(deal.liquidity_rows_out_of_date),
            open_row_count=len(open_rows), done_row_count=len(rows) - len(open_rows),
            overdue_open_row_count=sum(1 for row in open_rows if row.effective_date < resolved_today),
            late_refi_row_count=sum(1 for row in rows if row.created_because_refi_is_late),
            refi_is_late=refi_is_late(deal, resolved_today),
            milestones=[DealMilestoneRes(milestone=milestone, planned_date=planned_date_of_milestone(deal, milestone),
                                         approved_at=approved_at_of_milestone(deal, milestone),
                                         is_overdue=milestone_is_overdue(deal, milestone, resolved_today))
                        for milestone in DEAL_MILESTONES_IN_ORDER],
        ))
    return imported_deals


# --- Deal saves, moves, deletes -----------------------------------------------------------------------------------

def mark_liquidity_rows_out_of_date_if_the_save_changed_them(db: Session, deal_board: DealBoard, deal) -> None:
    """After a deal save (already committed): an imported deal whose rows would change is flagged, never re-synced
    silently. The 'Review N changes' badge shows the list; confirming it is a re-import. A late-refi month still to
    be added is not a change of the save (the late-refi refresh adds it)."""
    imported_rows = imported_rows_of_deal(db, deal_board, deal.id)
    if not imported_rows:
        return
    flagged_row_ids = {str(row.id) for row in imported_rows if row.no_longer_in_the_deal}
    planned_rows = planned_cash_rows_including_late_refi_months(deal, today_for_liquidity(db, None))
    rows_would_change = any(
        _the_change_writes_a_row(change, flagged_row_ids) for change in diff_deal_cash_rows(planned_rows, imported_rows))
    if bool(deal.liquidity_rows_out_of_date) != rows_would_change:
        deal.liquidity_rows_out_of_date = rows_would_change
        db.commit()


def _the_change_writes_a_row(change: DealCashRowChange, flagged_row_ids: set[str]) -> bool:
    if change.change_kind == "added":
        return not change.created_because_refi_is_late
    if change.change_kind == "kept_no_longer_in_the_deal":
        return change.transaction_id not in flagged_row_ids
    return change.change_kind in {"updated", "removed"}


def repoint_deal_rows(db: Session, from_deal_board: DealBoard, from_deal_id, to_deal_board: DealBoard, to_deal_id) -> int:
    """Move to Bought: the rows follow the deal onto its Bought copy (the caller commits, in the move's transaction)."""
    moved_row_count = 0
    for row in imported_rows_of_deal(db, from_deal_board, from_deal_id):
        row.source_deal_board, row.source_deal_id = to_deal_board, to_deal_id
        moved_row_count += 1
    return moved_row_count


def delete_open_rows_of_deal(db: Session, deal_board: DealBoard, deal_id) -> int:
    """The deal's open rows go (a deleted or dead deal); the done ones stay as history. The caller commits."""
    removed_row_count = 0
    for row in imported_rows_of_deal(db, deal_board, deal_id):
        if row.done_at is None:
            db.delete(row)
            removed_row_count += 1
    return removed_row_count


def remove_open_rows_of_deal(db: Session, deal_board: DealBoard, deal_id: str,
                             earnest_money_refund_date: Optional[date]) -> RemoveOpenDealRowsRes:
    """A dead deal: its open rows go, and the earnest money may come back as money in (a manual row, not the deal's)."""
    deal = find_brrr_deal(db, deal_board, deal_id)
    removed_row_count = delete_open_rows_of_deal(db, deal_board, deal.id)
    refund_transaction = None
    if earnest_money_refund_date is not None and Decimal(deal.earnest_money_deposit or 0) > 0:
        refund_transaction = LiquidityTransaction(
            effective_date=earnest_money_refund_date, originally_planned_date=earnest_money_refund_date,
            description=f"Earnest money refund: {deal.address}"[:500], amount_dollars=Decimal(deal.earnest_money_deposit),
        )
        db.add(refund_transaction)
    db.commit()
    return RemoveOpenDealRowsRes(removed_row_count=removed_row_count,
                                 earnest_money_refund_transaction_id=str(refund_transaction.id) if refund_transaction else None)
