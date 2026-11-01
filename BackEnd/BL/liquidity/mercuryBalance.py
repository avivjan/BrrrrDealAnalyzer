"""Fetch the live Mercury account balances, in dollars, and the part of them that is cash on hand.

The frontend re-anchors the liquidity timeline's opening balance to today on page load with
`counted_as_cash_balance_dollars`: the active accounts listed in the settings'
`mercury_account_ids_counted_as_cash` (every active account while that is null). The tax bucket
and the HYSA are meant to stay out, so the deposits into them read as money out of the operating
account. Raises `MercuryConfigError`/`MercuryApiError` (domain exceptions, not HTTP) -- the router
maps those to 503/502.
"""

from sqlalchemy.orm import Session

from BL.liquidity.common.mercury_client import ACTIVE_ACCOUNT_STATUSES, summarize_balance
from DAL.crud.liquidity import get_settings


def get_mercury_balance(db: Session):
    summary = summarize_balance()
    settings = get_settings(db)
    counted_account_ids = settings.mercury_account_ids_counted_as_cash if settings else None

    def is_counted_as_cash(account: dict) -> bool:
        return account["status"] in ACTIVE_ACCOUNT_STATUSES and (counted_account_ids is None or account["id"] in counted_account_ids)

    # The summary is cached: copy every account instead of marking the cached dicts.
    accounts = [{**account, "is_counted_as_cash": is_counted_as_cash(account)} for account in summary["accounts"]]
    workspaces = [
        {**workspace, "accounts": [{**account, "is_counted_as_cash": is_counted_as_cash(account)} for account in workspace["accounts"]]}
        for workspace in summary["workspaces"]
    ]
    return {
        **summary,
        "accounts": accounts,
        "workspaces": workspaces,
        "counted_as_cash_balance_dollars": round(sum(account["current_balance_dollars"] for account in accounts if account["is_counted_as_cash"]), 2),
        "mercury_account_ids_counted_as_cash": counted_account_ids,
    }
