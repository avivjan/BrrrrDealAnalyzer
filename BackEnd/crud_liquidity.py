from sqlalchemy.orm import Session
from models import LiquidityTransaction, LiquiditySettings
from ReqRes.liquidity.liquidityReq import (
    LiquidityTransactionCreate,
    LiquidityTransactionUpdate,
    LiquiditySettingsUpdate,
)
from datetime import date


# --- Transactions ---

def get_all_transactions(db: Session) -> list[LiquidityTransaction]:
    return db.query(LiquidityTransaction).order_by(LiquidityTransaction.effective_date).all()


def get_transaction(db: Session, txn_id: str) -> LiquidityTransaction | None:
    return db.query(LiquidityTransaction).filter(LiquidityTransaction.id == txn_id).first()


def add_transaction(db: Session, data: LiquidityTransactionCreate) -> LiquidityTransaction:
    txn = LiquidityTransaction(
        effective_date=data.effective_date,
        description=data.description,
        amount_k=data.amount_k,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def update_transaction(db: Session, txn_id: str, data: LiquidityTransactionUpdate) -> LiquidityTransaction | None:
    txn = db.query(LiquidityTransaction).filter(LiquidityTransaction.id == txn_id).first()
    if not txn:
        return None
    if data.effective_date is not None:
        txn.effective_date = data.effective_date
    if data.description is not None:
        txn.description = data.description
    if data.amount_k is not None:
        txn.amount_k = data.amount_k
    db.commit()
    db.refresh(txn)
    return txn


def delete_transaction(db: Session, txn_id: str) -> bool:
    txn = db.query(LiquidityTransaction).filter(LiquidityTransaction.id == txn_id).first()
    if not txn:
        return False
    db.delete(txn)
    db.commit()
    return True


# --- Settings (singleton row, id=1) ---

def get_settings(db: Session) -> LiquiditySettings | None:
    return db.query(LiquiditySettings).filter(LiquiditySettings.id == 1).first()


def upsert_settings(db: Session, data: LiquiditySettingsUpdate) -> LiquiditySettings:
    settings = db.query(LiquiditySettings).filter(LiquiditySettings.id == 1).first()
    if not settings:
        settings = LiquiditySettings(
            id=1,
            opening_balance_k=data.opening_balance_k if data.opening_balance_k is not None else 0,
            opening_balance_date=data.opening_balance_date if data.opening_balance_date is not None else date.today(),
            reserve_k=data.reserve_k if data.reserve_k is not None else 5,
        )
        db.add(settings)
    else:
        if data.opening_balance_k is not None:
            settings.opening_balance_k = data.opening_balance_k
        if data.opening_balance_date is not None:
            settings.opening_balance_date = data.opening_balance_date
        if data.reserve_k is not None:
            settings.reserve_k = data.reserve_k
    db.commit()
    db.refresh(settings)
    return settings
