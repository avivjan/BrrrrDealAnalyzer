"""One action on several one-off transactions at once: mark done / open, move to a date, or postpone by days.

All or nothing: an unknown id fails the whole request before anything changes. Moving a row by hand
marks its date as the user's (`user_overrode_date`, while it differs from the planned date), so a
re-sync from its deal keeps it.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from DAL.crud.liquidity import get_transactions_by_ids
from BL.liquidity.common.mappers import txn_to_res
from ReqRes.common.liquidity_schemas import LiquidityTransactionBulkActionReq


class UnknownLiquidityTransactionError(LookupError):
    """At least one id in the bulk request is not a transaction."""


def apply_bulk_transaction_action(db: Session, data: LiquidityTransactionBulkActionReq):
    try:
        txn_ids = [uuid.UUID(txn_id) for txn_id in dict.fromkeys(data.transaction_ids)]
    except ValueError as exc:
        raise UnknownLiquidityTransactionError("Unknown transaction id.") from exc
    txns = get_transactions_by_ids(db, txn_ids)
    if len(txns) != len(txn_ids):
        raise UnknownLiquidityTransactionError("Unknown transaction id.")
    now = datetime.now(timezone.utc)
    for txn in txns:
        if data.action == "mark_done":
            txn.done_at = now
        elif data.action == "mark_not_done":
            txn.done_at = None
        elif data.action == "move_to_date":
            txn.effective_date = data.new_effective_date
            txn.user_overrode_date = txn.effective_date != txn.originally_planned_date
        elif data.action == "postpone_by_days":
            txn.effective_date = txn.effective_date + timedelta(days=data.postpone_by_days)
            txn.user_overrode_date = txn.effective_date != txn.originally_planned_date
    db.commit()
    for txn in txns:
        db.refresh(txn)
    return [txn_to_res(txn) for txn in sorted(txns, key=lambda txn: (txn.effective_date, str(txn.id)))]
