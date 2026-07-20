"""Pure data-access layer for `TransactionLedger`."""

from typing import Optional

from sqlalchemy.orm import Session

from treasury.models.transaction_ledger import TransactionLedger


def create(db: Session, txn: TransactionLedger) -> TransactionLedger:
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def get_by_id(db: Session, transaction_id: str) -> Optional[TransactionLedger]:
    return db.get(TransactionLedger, transaction_id)


def list_all(
    db: Session,
    property_id: Optional[str] = None,
) -> list[TransactionLedger]:
    query = db.query(TransactionLedger)
    if property_id is not None:
        query = query.filter(TransactionLedger.property_id == property_id)
    return query.order_by(TransactionLedger.timestamp.desc()).all()


def update(db: Session, txn: TransactionLedger, changes: dict) -> TransactionLedger:
    for key, value in changes.items():
        setattr(txn, key, value)
    db.commit()
    db.refresh(txn)
    return txn


def delete(db: Session, txn: TransactionLedger) -> None:
    db.delete(txn)
    db.commit()
