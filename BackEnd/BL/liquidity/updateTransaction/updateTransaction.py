from sqlalchemy.orm import Session

from ReqRes.common.liquidity_schemas import LiquidityTransactionUpdate
from DAL.crud.liquidity import update_transaction as _update_transaction
from BL.liquidity.common.mappers import txn_to_res


def update_transaction(db: Session, txn_id: str, data: LiquidityTransactionUpdate):
    """Returns the updated transaction's response, or `None` if not found."""
    txn = _update_transaction(db, txn_id, data)
    if not txn:
        return None
    return txn_to_res(txn)
