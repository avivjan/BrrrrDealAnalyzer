"""The Mercury account balances, in dollars, and the part of them that is cash on hand.

The frontend re-anchors the liquidity timeline's opening balance to today with
`counted_as_cash_balance_dollars`: the active accounts listed in the settings'
`mercury_account_ids_counted_as_cash` (every active account while that is null). The tax bucket
and the HYSA are meant to stay out, so the deposits into them read as money out of the operating
account. A rehab's linked construction account is never cash on hand, whatever the settings say: the
lender's draws and the rehab payments move through it (tasks/todo/ConstructionAccountPerRehab.md).

Every workspace is read through the shared, paced reader (`BL/liquidity/common/mercury_reads.py`): this
read, the construction account refresh and the webhook share one snapshot and one pace per workspace, so
none of them makes a call another just made. Raises `MercuryConfigError` / `MercuryApiError` (domain
exceptions, not HTTP) -- the router maps those to 503 / 502.
"""

from sqlalchemy.orm import Session

from BL.liquidity.common import mercury_reads
from BL.liquidity.common.mercury_client import MercuryApiError, combine_workspace_summaries
from DAL.crud.liquidity import get_settings
from DAL.crud.liquidity_construction_account import get_all_construction_accounts


def mercury_balance_from_workspace_reads(db: Session, workspace_reads: list[mercury_reads.WorkspaceReadResult]) -> dict:
    """The balance answer from each workspace's read: totals, the accounts with their flags, the cash on hand."""
    workspaces = [read.workspace_summary for read in workspace_reads if read.workspace_summary is not None]
    errors = [{"workspace": read.mercury_workspace_label, "error": read.error_message}
              for read in workspace_reads if read.workspace_summary is None]
    if not workspaces and errors:
        # Every workspace failed: one API error, so the endpoint answers 502.
        raise MercuryApiError("; ".join(f"{error['workspace']}: {error['error']}" for error in errors))
    summary = combine_workspace_summaries(workspaces, errors)

    settings = get_settings(db)
    counted_account_ids = settings.mercury_account_ids_counted_as_cash if settings else None
    linked_construction_account_ids = {link.construction_mercury_account_id for link in get_all_construction_accounts(db)}

    def with_its_flags(account: dict) -> dict:
        # A stored snapshot is shared: copy every account instead of marking the stored dicts.
        return {**account,
                "is_counted_as_cash": mercury_reads.account_is_counted_as_cash(account, counted_account_ids, linked_construction_account_ids),
                "is_a_linked_construction_account": account["id"] in linked_construction_account_ids}

    accounts = [with_its_flags(account) for account in summary["accounts"]]
    next_read_times = [read.next_mercury_read_not_before for read in workspace_reads if read.next_mercury_read_not_before is not None]
    return {
        **summary,
        "accounts": accounts,
        "workspaces": [{**workspace, "accounts": [with_its_flags(account) for account in workspace["accounts"]]}
                       for workspace in summary["workspaces"]],
        "counted_as_cash_balance_dollars": round(sum(account["current_balance_dollars"] for account in accounts if account["is_counted_as_cash"]), 2),
        "mercury_account_ids_counted_as_cash": counted_account_ids,
        "next_mercury_read_not_before": max(next_read_times).isoformat() if next_read_times else None,
    }


def get_mercury_balance(db: Session, fresh: bool = False) -> dict:
    """`fresh` asks Mercury again even if the last read is recent; it still never reads a workspace more often than
    the shared pace allows (the stored snapshot answers in between)."""
    workspace_reads = mercury_reads.read_every_workspace(db, want_fresh=fresh)
    db.commit()   # the snapshots and the pace just recorded
    return mercury_balance_from_workspace_reads(db, workspace_reads)
