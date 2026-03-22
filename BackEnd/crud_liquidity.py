from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Tuple, Optional
from decimal import Decimal

from models import LiquidityTransaction
from ReqRes.BuyingPower.addLiquidityTransactionReq import AddLiquidityTransactionReq
from ReqRes.BuyingPower.updateLiquidityTransactionReq import UpdateLiquidityTransactionReq


def get_all_liquidity(db: Session) -> Tuple[List[LiquidityTransaction], Decimal]:
    transactions = (
        db.query(LiquidityTransaction)
        .order_by(LiquidityTransaction.date.desc())
        .all()
    )
    total = db.query(func.coalesce(func.sum(LiquidityTransaction.amount), 0)).scalar()
    return transactions, Decimal(str(total))


def add_liquidity_transaction(db: Session, data: AddLiquidityTransactionReq) -> LiquidityTransaction:
    txn = LiquidityTransaction(**data.model_dump())
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def update_liquidity_transaction(
    db: Session, txn_id: str, data: UpdateLiquidityTransactionReq
) -> Optional[LiquidityTransaction]:
    txn = db.query(LiquidityTransaction).filter(LiquidityTransaction.id == txn_id).first()
    if not txn:
        return None

    update_fields = data.model_dump(exclude_unset=True)
    for key, value in update_fields.items():
        setattr(txn, key, value)

    db.commit()
    db.refresh(txn)
    return txn


def delete_liquidity_transaction(db: Session, txn_id: str) -> bool:
    txn = db.query(LiquidityTransaction).filter(LiquidityTransaction.id == txn_id).first()
    if not txn:
        return False
    db.delete(txn)
    db.commit()
    return True
