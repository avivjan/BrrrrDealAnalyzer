from sqlalchemy.orm import Session
from DAL.data_models import (
    LiquidityTransaction,
    LiquidityRecurringTransaction,
    LiquiditySettings,
)
from ReqRes.liquidity.liquidityReq import (
    LiquidityTransactionCreate,
    LiquidityTransactionUpdate,
    LiquidityRecurringTransactionCreate,
)


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


# --- Recurring Transactions ---

def get_all_recurring(db: Session) -> list[LiquidityRecurringTransaction]:
    """Return every recurring rule, oldest start-date first."""
    return (
        db.query(LiquidityRecurringTransaction)
        .order_by(LiquidityRecurringTransaction.start_date)
        .all()
    )


def get_recurring(db: Session, rule_id: str) -> LiquidityRecurringTransaction | None:
    return (
        db.query(LiquidityRecurringTransaction)
        .filter(LiquidityRecurringTransaction.id == rule_id)
        .first()
    )


def insert_recurring(
    db: Session, data: LiquidityRecurringTransactionCreate
) -> LiquidityRecurringTransaction:
    rule = LiquidityRecurringTransaction(
        description=data.description,
        amount_k=data.amount_k,
        start_date=data.start_date,
        end_date=data.end_date,
        occurrences=data.occurrences,
        frequency=data.frequency,
        interval=data.interval,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def save_recurring(db: Session, rule: LiquidityRecurringTransaction) -> LiquidityRecurringTransaction:
    """Persist a `LiquidityRecurringTransaction` the caller has already mutated."""
    db.commit()
    db.refresh(rule)
    return rule


def delete_recurring(db: Session, rule_id: str) -> bool:
    rule = (
        db.query(LiquidityRecurringTransaction)
        .filter(LiquidityRecurringTransaction.id == rule_id)
        .first()
    )
    if not rule:
        return False
    db.delete(rule)
    db.commit()
    return True


# --- Settings (singleton row, id=1) ---

def get_settings(db: Session) -> LiquiditySettings | None:
    return db.query(LiquiditySettings).filter(LiquiditySettings.id == 1).first()


def insert_settings(
    db: Session, *, opening_balance_k, opening_balance_date, reserve_k
) -> LiquiditySettings:
    settings = LiquiditySettings(
        id=1,
        opening_balance_k=opening_balance_k,
        opening_balance_date=opening_balance_date,
        reserve_k=reserve_k,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def save_settings(db: Session, settings: LiquiditySettings) -> LiquiditySettings:
    """Persist a `LiquiditySettings` the caller has already mutated."""
    db.commit()
    db.refresh(settings)
    return settings
