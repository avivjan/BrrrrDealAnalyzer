"""A BRRRR deal's Cash Needed rows in the liquidity timeline: planned from the deal, matched to the imported
rows by identity, and the before -> after list every import, re-sync and milestone change shows first.

Identity of a deal row = deal board + deal id + item_key + occurrence number (the n-th row of that item in
date order). Never the date: dates move with the milestones, the identity does not.

The re-sync rules (tasks/todo/DealCashInLiquidity.md, decisions 18-19):
- a row marked done is never touched;
- a field the user overrode (`user_overrode_date` / `user_overrode_amount`) keeps the user's value, the other
  field still follows the deal, and the conflict is listed ("kept your $1,800, the deal now says $2,100") so
  one tap can take the deal's value instead;
- a row the deal no longer has is removed, unless it carries an override: then it stays, flagged
  `no_longer_in_the_deal`;
- the deal's new planned date always becomes `originally_planned_date`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Iterable, Literal, Optional

from sqlalchemy.orm import Session

from BL.analyze.analyzeBRRR import compute_brrr_with_intermediates
from BL.analyze.common.deal_math import first_of_next_month
from DAL.data_models import BrrrActiveDeal, BoughtBrrrDeal, LiquidityTransaction

DealBoard = Literal["my_deals", "bought"]
DEAL_BOARD_MY_DEALS: DealBoard = "my_deals"
DEAL_BOARD_BOUGHT: DealBoard = "bought"
DEAL_MODEL_BY_BOARD = {DEAL_BOARD_MY_DEALS: BrrrActiveDeal, DEAL_BOARD_BOUGHT: BoughtBrrrDeal}

# A refi this late is a deal to re-plan, not more rows: the late months stop here (it also bounds a far-future "today").
MAX_LATE_REFI_MONTHS_ADDED = 24

# The monthly money-out items that keep coming while the refi is late.
LATE_REFI_CARRYING_COST_ITEM_KEYS = frozenset({"hml_interest_paid_monthly", "hoa_dues", "insurance_paid_monthly_until_refi", "utilities"})

DealCashRowChangeKind = Literal["added", "updated", "removed", "unchanged", "kept_done", "kept_no_longer_in_the_deal"]
DealCashRowField = Literal["date", "amount"]


@dataclass(frozen=True)
class PlannedDealCashRow:
    item_key: str
    occurrence_number: int            # 1-based, the n-th row of this item in date order
    effective_date: date
    amount_dollars: Decimal
    description: str
    sequence_within_day: int
    # A month of carrying costs after the planned refi, while the refi is late (not approved yet).
    created_because_refi_is_late: bool = False
    # A row computed live from a linked construction account: a hand-edited amount (or date) never holds it back.
    amount_always_follows_the_deal: bool = False
    date_always_follows_the_deal: bool = False

    @property
    def identity(self) -> tuple[str, int]:
        return (self.item_key, self.occurrence_number)


@dataclass(frozen=True)
class DealCashRowChange:
    change_kind: DealCashRowChangeKind
    item_key: str
    occurrence_number: int
    description: str
    transaction_id: Optional[str]                 # None for a row still to be added
    date_before: Optional[date]
    date_after: Optional[date]
    amount_before: Optional[Decimal]
    amount_after: Optional[Decimal]
    # The deal's new value of a field the user overrode, kept out ("Use the deal's value" applies it).
    deal_date_not_applied_because_you_changed_it: Optional[date] = None
    deal_amount_not_applied_because_you_changed_it: Optional[Decimal] = None
    created_because_refi_is_late: bool = False


def deal_as_attributes(deal, **overrides):
    """The deal's columns as plain attributes (what the engine and the validator read), with some replaced."""
    attributes = {column.name: getattr(deal, column.name) for column in deal.__table__.columns}
    attributes.update(overrides)
    return SimpleNamespace(**attributes)


def planned_cash_rows_of_deal(deal) -> list[PlannedDealCashRow]:
    """The deal's Cash Needed schedule (Lowest ARV) as rows with their identity. `deal` is an ORM row or attributes."""
    return _planned_rows_from_schedule(compute_brrr_with_intermediates(deal).cash_needed_schedule_at_lowest_arv)


def key_dates_of_deal(deal) -> list[tuple[str, date, str]]:
    """The deal's key dates as its Cash Needed table shows them (key, date, description), in date order."""
    schedule = compute_brrr_with_intermediates(deal).cash_needed_schedule_at_lowest_arv
    return [(milestone.milestone_key, milestone.date, milestone.description) for milestone in schedule.deal_milestones]


def refi_closing_date_of_deal(deal) -> date:
    return deal.buy_closing_date + timedelta(days=int(deal.days_until_refi))


def refi_is_late(deal, today: date) -> bool:
    """The planned refi date passed and the refi is not approved yet."""
    return deal.refi_closed_approved_at is None and refi_closing_date_of_deal(deal) < today


def planned_cash_rows_including_late_refi_months(deal, today: date) -> list[PlannedDealCashRow]:
    """The deal's rows, plus (while the refi is late) the monthly carrying costs from the planned refi up to the
    first 1st after today, that 1st included. Those come from a provisional analysis with the refi the day after that
    1st (so the 1st is a payment day, not inside a payoff), never written to the deal; only the money-out monthly
    items are taken (no rent: conservative), with their normal identity."""
    planned_rows = planned_cash_rows_of_deal(deal)
    if not refi_is_late(deal, today):
        return planned_rows
    planned_refi_date = refi_closing_date_of_deal(deal)
    latest_provisional_refi_date = _months_after(planned_refi_date, MAX_LATE_REFI_MONTHS_ADDED)
    provisional_refi_date = min(first_of_next_month(today), latest_provisional_refi_date) + timedelta(days=1)
    provisional_deal = deal_as_attributes(deal, days_until_refi=(provisional_refi_date - deal.buy_closing_date).days)
    identities_of_the_deal = {row.identity for row in planned_rows}
    late_refi_rows = [
        replace(row, created_because_refi_is_late=True)
        for row in planned_cash_rows_of_deal(provisional_deal)
        if row.item_key in LATE_REFI_CARRYING_COST_ITEM_KEYS and row.effective_date >= planned_refi_date
        and row.identity not in identities_of_the_deal
    ]
    return sorted(planned_rows + late_refi_rows, key=lambda row: (row.effective_date, row.sequence_within_day))


CONSTRUCTION_ACCOUNT_DEPOSIT_ITEM_KEY = "construction_account_deposit"
CONSTRUCTION_ACCOUNT_RETURN_ITEM_KEY = "construction_account_balance_returned_at_rehab_end"
# Never a schedule row: it exists only while a linked construction account is projected to run short.
CONSTRUCTION_ACCOUNT_TOP_UP_ITEM_KEY = "construction_account_top_up_needed"
CONSTRUCTION_ACCOUNT_ITEM_KEYS = frozenset({
    CONSTRUCTION_ACCOUNT_DEPOSIT_ITEM_KEY, CONSTRUCTION_ACCOUNT_RETURN_ITEM_KEY, CONSTRUCTION_ACCOUNT_TOP_UP_ITEM_KEY,
})


@dataclass(frozen=True)
class ConstructionAccountLiveRowAmounts:
    """The three liquidity rows of a linked construction account, each a positive amount (0 = no row)."""
    deposit_row_amount_dollars: Decimal
    return_row_amount_dollars: Decimal
    top_up_needed_dollars: Decimal


def planned_cash_rows_including_construction_account_live_amounts(
        planned_rows: Iterable[PlannedDealCashRow], live_amounts: ConstructionAccountLiveRowAmounts,
        purchase_closing_date: date, rehab_completed_date: date, today: date) -> list[PlannedDealCashRow]:
    """The deal's rows with the schedule's two construction-account rows replaced by the linked account's live ones
    (tasks/todo/ConstructionAccountPerRehab.md): the deposit still to make, what the account will give back, and a
    top-up dated today while it is projected to run short. Their amounts always follow the account."""
    planned_rows = list(planned_rows)
    schedule_row_by_item_key = {row.item_key: row for row in planned_rows if row.item_key in CONSTRUCTION_ACCOUNT_ITEM_KEYS}
    rows = [row for row in planned_rows if row.item_key not in CONSTRUCTION_ACCOUNT_ITEM_KEYS]

    def live_row(item_key: str, effective_date: date, signed_amount_dollars: Decimal, description: str, date_always_follows: bool) -> None:
        if signed_amount_dollars == 0:
            return
        schedule_row = schedule_row_by_item_key.get(item_key)
        rows.append(PlannedDealCashRow(
            item_key=item_key, occurrence_number=1, effective_date=effective_date, amount_dollars=signed_amount_dollars,
            description=description, sequence_within_day=schedule_row.sequence_within_day if schedule_row else 0,
            amount_always_follows_the_deal=True, date_always_follows_the_deal=date_always_follows))

    live_row(CONSTRUCTION_ACCOUNT_DEPOSIT_ITEM_KEY, purchase_closing_date, -live_amounts.deposit_row_amount_dollars,
             "Deposit into the construction account (still to deposit)", False)
    live_row(CONSTRUCTION_ACCOUNT_RETURN_ITEM_KEY, rehab_completed_date, live_amounts.return_row_amount_dollars,
             "Construction account balance returned at rehab end (live from the account)", False)
    live_row(CONSTRUCTION_ACCOUNT_TOP_UP_ITEM_KEY, today, -live_amounts.top_up_needed_dollars,
             "Top-up needed in the construction account", True)
    return sorted(rows, key=lambda row: (row.effective_date, row.sequence_within_day))


def _months_after(day: date, months: int) -> date:
    """The 1st of the month `months` after `day`'s month."""
    month_index = day.year * 12 + day.month - 1 + months
    return date(month_index // 12, month_index % 12 + 1, 1)


def _planned_rows_from_schedule(schedule) -> list[PlannedDealCashRow]:
    occurrence_count_by_item_key: dict[str, int] = {}
    planned_rows = []
    for row in sorted(schedule.dated_cash_rows, key=lambda row: (row.item_key, row.date, row.sequence_within_day)):
        occurrence_count_by_item_key[row.item_key] = occurrence_count_by_item_key.get(row.item_key, 0) + 1
        planned_rows.append(PlannedDealCashRow(
            item_key=row.item_key, occurrence_number=occurrence_count_by_item_key[row.item_key], effective_date=row.date,
            amount_dollars=row.signed_amount_dollars, description=row.description, sequence_within_day=row.sequence_within_day,
        ))
    return sorted(planned_rows, key=lambda row: (row.effective_date, row.sequence_within_day))


def imported_rows_of_deal(db: Session, deal_board: DealBoard, deal_id) -> list[LiquidityTransaction]:
    return (db.query(LiquidityTransaction)
            .filter(LiquidityTransaction.source_deal_board == deal_board, LiquidityTransaction.source_deal_id == deal_id)
            .order_by(LiquidityTransaction.effective_date, LiquidityTransaction.sequence_within_day)
            .all())


def diff_deal_cash_rows(planned_rows: Iterable[PlannedDealCashRow], imported_rows: Iterable[LiquidityTransaction],
                        use_deal_value_for: frozenset[tuple[str, DealCashRowField]] = frozenset()) -> list[DealCashRowChange]:
    """What a re-sync would do to each row, in date order. `use_deal_value_for` = (transaction id, field) pairs the
    user chose to take the deal's value for, despite an override."""
    planned_by_identity = {row.identity: row for row in planned_rows}
    imported_by_identity = {(txn.source_item_key, txn.source_occurrence_number): txn for txn in imported_rows}
    changes: list[DealCashRowChange] = []
    for identity, planned in planned_by_identity.items():
        txn = imported_by_identity.get(identity)
        if txn is None:
            changes.append(DealCashRowChange("added", planned.item_key, planned.occurrence_number, planned.description, None,
                                             None, planned.effective_date, None, planned.amount_dollars,
                                             created_because_refi_is_late=planned.created_because_refi_is_late))
            continue
        before_date, before_amount = txn.effective_date, Decimal(txn.amount_dollars)
        if txn.done_at is not None:
            changes.append(DealCashRowChange("kept_done", planned.item_key, planned.occurrence_number, txn.description, str(txn.id),
                                             before_date, before_date, before_amount, before_amount,
                                             created_because_refi_is_late=bool(txn.created_because_refi_is_late)))
            continue
        keeps_users_date = (bool(txn.user_overrode_date) and (str(txn.id), "date") not in use_deal_value_for
                            and not planned.date_always_follows_the_deal)
        keeps_users_amount = (bool(txn.user_overrode_amount) and (str(txn.id), "amount") not in use_deal_value_for
                              and not planned.amount_always_follows_the_deal)
        after_date = before_date if keeps_users_date else planned.effective_date
        after_amount = before_amount if keeps_users_amount else planned.amount_dollars
        changed = (after_date != before_date or after_amount != before_amount or planned.description != txn.description
                   or bool(txn.no_longer_in_the_deal))
        changes.append(DealCashRowChange(
            "updated" if changed else "unchanged", planned.item_key, planned.occurrence_number, planned.description, str(txn.id),
            before_date, after_date, before_amount, after_amount,
            deal_date_not_applied_because_you_changed_it=planned.effective_date if keeps_users_date and planned.effective_date != before_date else None,
            deal_amount_not_applied_because_you_changed_it=planned.amount_dollars if keeps_users_amount and planned.amount_dollars != before_amount else None,
            created_because_refi_is_late=planned.created_because_refi_is_late,
        ))
    for identity, txn in imported_by_identity.items():
        if identity in planned_by_identity:
            continue
        before_date, before_amount = txn.effective_date, Decimal(txn.amount_dollars)
        if txn.done_at is not None:
            kind: DealCashRowChangeKind = "kept_done"
        elif txn.user_overrode_date or txn.user_overrode_amount:
            kind = "kept_no_longer_in_the_deal"
        else:
            kind = "removed"
        changes.append(DealCashRowChange(kind, txn.source_item_key, txn.source_occurrence_number, txn.description, str(txn.id),
                                         before_date, None if kind == "removed" else before_date,
                                         before_amount, None if kind == "removed" else before_amount,
                                         created_because_refi_is_late=bool(txn.created_because_refi_is_late)))
    return sorted(changes, key=lambda change: (change.date_after or change.date_before, change.item_key, change.occurrence_number))


def apply_deal_cash_row_changes(db: Session, deal_board: DealBoard, deal_id, planned_rows: Iterable[PlannedDealCashRow],
                                use_deal_value_for: frozenset[tuple[str, DealCashRowField]] = frozenset(),
                                only_add_missing_late_refi_rows: bool = False,
                                only_item_keys: Optional[frozenset[str]] = None) -> list[DealCashRowChange]:
    """Write the re-sync to the deal's rows (no commit). `only_add_missing_late_refi_rows` adds the late-refi months
    still missing and touches nothing else (a row you deleted by hand is never brought back by it). `only_item_keys`
    writes the rows of those items and touches nothing else (the construction account's live rows)."""
    planned_rows = list(planned_rows)
    imported_rows = imported_rows_of_deal(db, deal_board, deal_id)
    changes = diff_deal_cash_rows(planned_rows, imported_rows, use_deal_value_for)
    planned_by_identity = {row.identity: row for row in planned_rows}
    imported_by_id = {str(txn.id): txn for txn in imported_rows}
    applied = []
    for change in changes:
        planned = planned_by_identity.get((change.item_key, change.occurrence_number))
        if only_add_missing_late_refi_rows and not (change.change_kind == "added" and planned.created_because_refi_is_late):
            continue
        if only_item_keys is not None and change.item_key not in only_item_keys:
            continue
        if change.change_kind == "added":
            db.add(LiquidityTransaction(
                effective_date=planned.effective_date, description=planned.description, amount_dollars=planned.amount_dollars,
                originally_planned_date=planned.effective_date, source_deal_board=deal_board, source_deal_id=deal_id,
                source_item_key=planned.item_key, source_occurrence_number=planned.occurrence_number,
                sequence_within_day=planned.sequence_within_day, created_because_refi_is_late=planned.created_because_refi_is_late,
            ))
        elif change.change_kind == "updated":
            txn = imported_by_id[change.transaction_id]
            txn.effective_date, txn.amount_dollars, txn.description = change.date_after, change.amount_after, planned.description
            txn.sequence_within_day, txn.originally_planned_date = planned.sequence_within_day, planned.effective_date
            txn.user_overrode_date = change.date_after != planned.effective_date
            txn.user_overrode_amount = change.amount_after != planned.amount_dollars
            txn.no_longer_in_the_deal = False
            txn.created_because_refi_is_late = planned.created_because_refi_is_late
        elif change.change_kind == "unchanged":
            # A conflict-only row (your date kept, the deal's moved) still learns the deal's planned date.
            txn = imported_by_id[change.transaction_id]
            txn.sequence_within_day, txn.originally_planned_date = planned.sequence_within_day, planned.effective_date
            txn.created_because_refi_is_late = planned.created_because_refi_is_late
        elif change.change_kind == "removed":
            db.delete(imported_by_id[change.transaction_id])
        elif change.change_kind == "kept_no_longer_in_the_deal":
            imported_by_id[change.transaction_id].no_longer_in_the_deal = True
        applied.append(change)
    return applied
