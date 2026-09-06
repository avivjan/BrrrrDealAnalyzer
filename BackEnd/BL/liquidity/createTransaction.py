from sqlalchemy.orm import Session

from ReqRes.common.liquidity_schemas import LiquidityTransactionCreate
from DAL.crud.liquidity import add_transaction
from BL.liquidity.common.mappers import txn_to_res


def create_transaction(db: Session, data: LiquidityTransactionCreate):
    txn = add_transaction(db, data)
    db.commit()
    db.refresh(txn)
    return txn_to_res(txn)
