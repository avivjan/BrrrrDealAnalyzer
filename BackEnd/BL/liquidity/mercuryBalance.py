"""Fetch the live Mercury account balances, in dollars, and the part of them that is cash on hand.

The frontend re-anchors the liquidity timeline's opening balance to today on page load with
`counted_as_cash_balance_dollars`: the active accounts listed in the settings'
`mercury_account_ids_counted_as_cash` (every active account while that is null). The tax bucket
and the HYSA are meant to stay out, so the deposits into them read as money out of the operating
account. A rehab's linked construction account is never cash on hand, whatever the settings say: the
lender's draws and the rehab payments move through it (tasks/todo/ConstructionAccountPerRehab.md). Raises `MercuryConfigError`/`MercuryApiError` (domain exceptions, not HTTP) -- the router
maps those to 503/502.
"""

from sqlalchemy.orm import Session

from BL.liquidity.common.mercury_client import ACTIVE_ACCOUNT_STATUSES, summarize_balance
from DAL.crud.liquidity import get_settings
from DAL.crud.liquidity_construction_account import get_all_construction_accounts


def get_mercury_balance(db: Session):
    summary = summarize_balance()
    settings = get_settings(db)
    counted_account_ids = settings.mercury_account_ids_counted_as_cash if settings else None

    linked_construction_account_ids = {link.construction_mercury_account_id for link in get_all_construction_accounts(db)}

    def is_counted_as_cash(account: dict) -> bool:
        return (account["status"] in ACTIVE_ACCOUNT_STATUSES and account["id"] not in linked_construction_account_ids
                and (counted_account_ids is None or account["id"] in counted_account_ids))

    def with_its_flags(account: dict) -> dict:
        # The summary is cached: copy every account instead of marking the cached dicts.
        return {**account, "is_counted_as_cash": is_counted_as_cash(account),
                "is_a_linked_construction_account": account["id"] in linked_construction_account_ids}

    accounts = [with_its_flags(account) for account in summary["accounts"]]
    workspaces = [
        {**workspace, "accounts": [with_its_flags(account) for account in workspace["accounts"]]}
        for workspace in summary["workspaces"]
    ]
    return {
        **summary,
        "accounts": accounts,
        "workspaces": workspaces,
        "counted_as_cash_balance_dollars": round(sum(account["current_balance_dollars"] for account in accounts if account["is_counted_as_cash"]), 2),
        "mercury_account_ids_counted_as_cash": counted_account_ids,
    }
