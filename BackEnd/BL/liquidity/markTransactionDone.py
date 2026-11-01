"""Mark a one-off transaction done (the money moved, or the hold was released) or open again (Undo).

A done row leaves the timeline; it is the only way a row leaves it (a passed date never does).
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from DAL.crud.liquidity import get_transaction
from BL.liquidity.common.mappers import txn_to_res


def mark_transaction_done(db: Session, txn_id: str, is_done: bool):
    """Returns the transaction's response, or `None` if not found."""
    txn = get_transaction(db, txn_id)
    if not txn:
        return None
    txn.done_at = datetime.now(timezone.utc) if is_done else None
    db.commit()
    db.refresh(txn)
    return txn_to_res(txn)
