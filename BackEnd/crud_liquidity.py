from sqlalchemy.orm import Session
from models import (
    LiquidityTransaction,
    LiquidityRecurringTransaction,
    LiquiditySettings,
    LIQUIDITY_RECURRING_FREQUENCIES,
)
from ReqRes.liquidity.liquidityReq import (
    LiquidityTransactionCreate,
    LiquidityTransactionUpdate,
    LiquidityRecurringTransactionCreate,
    LiquidityRecurringTransactionUpdate,
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


def add_recurring(
    db: Session, data: LiquidityRecurringTransactionCreate
) -> LiquidityRecurringTransaction:
    if data.frequency not in LIQUIDITY_RECURRING_FREQUENCIES:
        # Should already be guarded by the Literal type, but defense-in-depth
        # so a hand-rolled HTTP client can't poison the DB.
        raise ValueError(f"Unsupported frequency: {data.frequency!r}")
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


def update_recurring(
    db: Session, rule_id: str, data: LiquidityRecurringTransactionUpdate
) -> LiquidityRecurringTransaction | None:
    """Apply a partial update; raises ValueError if the merged row is invalid.

    The `end_date >= start_date` invariant lives here (not in the schema)
    because either field may be omitted from the patch payload.
    """
    rule = (
        db.query(LiquidityRecurringTransaction)
        .filter(LiquidityRecurringTransaction.id == rule_id)
        .first()
    )
    if not rule:
        return None

    if data.description is not None:
        rule.description = data.description
    if data.amount_k is not None:
        if data.amount_k == 0:
            raise ValueError("amount_k must be non-zero.")
        rule.amount_k = data.amount_k
    if data.start_date is not None:
        rule.start_date = data.start_date
    # `end_date` is intentionally allowed to be set back to NULL via PATCH,
    # but the Update schema can't distinguish "unset" from "explicit null"
    # without a sentinel. Update endpoints treat `None` as "leave as-is" to
    # match the rest of this codebase.
    if data.end_date is not None:
        rule.end_date = data.end_date
    if data.occurrences is not None:
        rule.occurrences = data.occurrences
    if data.frequency is not None:
        if data.frequency not in LIQUIDITY_RECURRING_FREQUENCIES:
            raise ValueError(f"Unsupported frequency: {data.frequency!r}")
        rule.frequency = data.frequency
    if data.interval is not None:
        rule.interval = data.interval

    if rule.end_date is not None and rule.end_date < rule.start_date:
        raise ValueError("end_date must be on or after start_date.")

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
