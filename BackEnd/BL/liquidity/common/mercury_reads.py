"""The one paced way to read Mercury (tasks/todo/ConstructionAccountPerRehab.md, "Requirement 4 -- live Mercury").

Every reader goes through here: the general balance (`GET /liquidity/mercury-balance`), the construction account
refresh and the webhook. One gate per workspace (one LLC), kept in the database so every server process shares it:

- at most one read of a workspace every `MINIMUM_SECONDS_BETWEEN_MERCURY_READS_OF_ONE_WORKSPACE`, however many tabs,
  pages or readers ask: a reader that asks sooner gets the stored snapshot, never a second call;
- when Mercury answers "slow down" (429) to any call, that workspace backs off for all readers, doubling up to
  `MAXIMUM_BACK_OFF_SECONDS` and honouring its Retry-After.

Mercury's limits are not published; these numbers are conservative guesses. A read failure is never stored as a
snapshot and never starts the floor, so the next ask tries again.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from BL.liquidity.common import mercury_client
from BL.liquidity.common.mercury_client import ACTIVE_ACCOUNT_STATUSES, MercuryApiError, MercuryConfigError, MercurySlowDownError
from DAL.crud.liquidity import get_settings
from DAL.crud.liquidity_construction_account import get_all_construction_accounts
from DAL.data_models.liquidity.mercury_models import LiquidityMercuryWorkspaceRead

MINIMUM_SECONDS_BETWEEN_MERCURY_READS_OF_ONE_WORKSPACE = 10
FIRST_BACK_OFF_SECONDS = 20
MAXIMUM_BACK_OFF_SECONDS = 300

NO_MERCURY_TOKENS_MESSAGE = (
    "No Mercury tokens found. Add MERCURY_API_TOKEN_<LABEL> entries "
    "(e.g. MERCURY_API_TOKEN_AJYK, MERCURY_API_TOKEN_AY) to BackEnd/.env."
)


@dataclass(frozen=True)
class WorkspaceReadResult:
    mercury_workspace_label: str
    # The workspace's summarised accounts: read now, or the stored snapshot. None = nothing to show (a failed read).
    workspace_summary: Optional[dict]
    was_read_from_mercury_now: bool
    # In our own words; set when a read was tried now and failed (the stored snapshot is not offered in its place).
    error_message: Optional[str]
    next_mercury_read_not_before: Optional[datetime]
    cash_balance_changed_now: bool


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def workspace_labels_with_a_read_token() -> list[str]:
    return sorted(mercury_client.discover_tokens().keys())


def workspace_read_row(db: Session, mercury_workspace_label: str, lock_it: bool = False) -> LiquidityMercuryWorkspaceRead:
    """The workspace's row, created on first use. `lock_it` holds it for this transaction, so two processes asking
    together make one read between them."""
    query = db.query(LiquidityMercuryWorkspaceRead).filter(LiquidityMercuryWorkspaceRead.mercury_workspace_label == mercury_workspace_label)
    row = (query.with_for_update() if lock_it else query).first()
    if row is None:
        row = LiquidityMercuryWorkspaceRead(mercury_workspace_label=mercury_workspace_label, consecutive_slow_down_answers=0)
        db.add(row)
        db.flush()
    return row


def account_is_counted_as_cash(account: dict, counted_account_ids: Optional[list], linked_construction_account_ids: set[str]) -> bool:
    """An active account chosen in the liquidity settings (null = every active account). A rehab's linked construction
    account is never cash on hand, whatever the settings say."""
    return (account["status"] in ACTIVE_ACCOUNT_STATUSES and account["id"] not in linked_construction_account_ids
            and (counted_account_ids is None or account["id"] in counted_account_ids))


def counted_as_cash_balance_of_workspace(db: Session, workspace_summary: dict) -> Decimal:
    settings = get_settings(db)
    counted_account_ids = settings.mercury_account_ids_counted_as_cash if settings else None
    linked_construction_account_ids = {link.construction_mercury_account_id for link in get_all_construction_accounts(db)}
    return sum((Decimal(str(account["current_balance_dollars"])) for account in workspace_summary["accounts"]
                if account_is_counted_as_cash(account, counted_account_ids, linked_construction_account_ids)), Decimal("0")).quantize(Decimal("0.01"))


def record_slow_down(row: LiquidityMercuryWorkspaceRead, slow_down: MercurySlowDownError, now: datetime) -> None:
    """Mercury answered 429 to a call for this workspace: no read of it before the back-off ends."""
    row.consecutive_slow_down_answers = int(row.consecutive_slow_down_answers or 0) + 1
    doubled_seconds = min(MAXIMUM_BACK_OFF_SECONDS, FIRST_BACK_OFF_SECONDS * 2 ** (row.consecutive_slow_down_answers - 1))
    back_off_seconds = min(MAXIMUM_BACK_OFF_SECONDS, max(doubled_seconds, slow_down.retry_after_seconds or 0))
    row.next_mercury_read_not_before = now + timedelta(seconds=back_off_seconds)


def mercury_may_be_read_now(row: LiquidityMercuryWorkspaceRead, now: datetime) -> bool:
    if row.next_mercury_read_not_before is not None and now < row.next_mercury_read_not_before:
        return False
    return (row.last_mercury_read_at is None
            or (now - row.last_mercury_read_at).total_seconds() >= MINIMUM_SECONDS_BETWEEN_MERCURY_READS_OF_ONE_WORKSPACE)


def next_read_time_of(row: LiquidityMercuryWorkspaceRead) -> Optional[datetime]:
    floor_ends_at = (row.last_mercury_read_at + timedelta(seconds=MINIMUM_SECONDS_BETWEEN_MERCURY_READS_OF_ONE_WORKSPACE)
                     if row.last_mercury_read_at else None)
    candidates = [moment for moment in (floor_ends_at, row.next_mercury_read_not_before) if moment is not None]
    return max(candidates) if candidates else None


def discard_snapshot_of_workspace(db: Session, mercury_workspace_label: str, now: Optional[datetime] = None) -> None:
    """A webhook said something moved in this workspace: its cached balances are no longer offered, and the next
    allowed read is a fresh one whoever asks."""
    row = workspace_read_row(db, mercury_workspace_label, lock_it=True)
    row.accounts_snapshot = None
    row.fresh_read_requested_at = now or utc_now()
    mercury_client.clear_cache()


def read_workspace(db: Session, mercury_workspace_label: str, want_fresh: bool, now: Optional[datetime] = None) -> WorkspaceReadResult:
    """One workspace's accounts through the gate. No commit: the caller commits.

    Mercury is read when it may be (the floor and any back-off have passed) and it is worth it: there is no snapshot,
    the caller wants fresh data, a webhook asked for a fresh read, or the snapshot is older than the cache time.
    Otherwise the stored snapshot answers."""
    now = now or utc_now()
    row = workspace_read_row(db, mercury_workspace_label, lock_it=True)
    snapshot_age_seconds = (now - row.last_mercury_read_at).total_seconds() if row.last_mercury_read_at else None
    snapshot_is_too_old = snapshot_age_seconds is None or snapshot_age_seconds >= mercury_client.cache_seconds()
    worth_reading = row.accounts_snapshot is None or want_fresh or row.fresh_read_requested_at is not None or snapshot_is_too_old
    if not (worth_reading and mercury_may_be_read_now(row, now)):
        return WorkspaceReadResult(mercury_workspace_label, row.accounts_snapshot, False, None, next_read_time_of(row), False)

    try:
        workspace_summary = mercury_client.fetch_workspace_summary(mercury_workspace_label)
    except MercurySlowDownError as slow_down:
        record_slow_down(row, slow_down, now)
        # A back-off is pacing, not a failure: the last snapshot is still the answer.
        return WorkspaceReadResult(mercury_workspace_label, row.accounts_snapshot, False,
                                   None if row.accounts_snapshot is not None else str(slow_down), next_read_time_of(row), False)
    except (MercuryApiError, MercuryConfigError) as error:
        return WorkspaceReadResult(mercury_workspace_label, None, False, str(error), next_read_time_of(row), False)

    row.accounts_snapshot = workspace_summary
    row.last_mercury_read_at = now
    row.next_mercury_read_not_before = None
    row.consecutive_slow_down_answers = 0
    row.fresh_read_requested_at = None
    counted_as_cash_balance = counted_as_cash_balance_of_workspace(db, workspace_summary)
    cash_balance_changed = row.counted_as_cash_balance_dollars is None or Decimal(row.counted_as_cash_balance_dollars) != counted_as_cash_balance
    if cash_balance_changed:
        row.counted_as_cash_balance_dollars = counted_as_cash_balance
        row.cash_balance_last_changed_at = now
    db.flush()
    return WorkspaceReadResult(mercury_workspace_label, workspace_summary, True, None, next_read_time_of(row), cash_balance_changed)


def read_every_workspace(db: Session, want_fresh: bool, now: Optional[datetime] = None) -> list[WorkspaceReadResult]:
    """Every workspace that has a read token, each through its own gate. Raises `MercuryConfigError` when there is none."""
    labels = workspace_labels_with_a_read_token()
    if not labels:
        raise MercuryConfigError(NO_MERCURY_TOKENS_MESSAGE)
    return [read_workspace(db, label, want_fresh, now) for label in labels]


def mark_construction_accounts_changed(db: Session, mercury_workspace_label: str, now: Optional[datetime] = None) -> None:
    workspace_read_row(db, mercury_workspace_label).construction_accounts_last_changed_at = now or utc_now()


def last_change_times(db: Session) -> tuple[Optional[datetime], Optional[datetime]]:
    """(the cash balance's last change, the construction accounts' last change), across every workspace."""
    rows = db.query(LiquidityMercuryWorkspaceRead).all()
    cash_balance_changes = [row.cash_balance_last_changed_at for row in rows if row.cash_balance_last_changed_at]
    construction_account_changes = [row.construction_accounts_last_changed_at for row in rows if row.construction_accounts_last_changed_at]
    return (max(cash_balance_changes) if cash_balance_changes else None,
            max(construction_account_changes) if construction_account_changes else None)
