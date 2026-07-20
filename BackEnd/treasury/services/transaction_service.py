from sqlalchemy.orm import Session

from treasury.models.transaction_ledger import TransactionLedger
from treasury.repositories import property_repository, transaction_repository
from treasury.schemas.transaction_schemas import (
    TransactionLedgerCreate,
    TransactionLedgerUpdate,
)
from treasury.services.exceptions import NotFoundError, ValidationError


def create_transaction(
    db: Session,
    payload: TransactionLedgerCreate,
) -> TransactionLedger:
    if payload.property_id is not None and property_repository.get_by_id(db, payload.property_id) is None:
        raise ValidationError(f"Property '{payload.property_id}' not found.")
    data = payload.model_dump()
    txn = TransactionLedger(**data)
    return transaction_repository.create(db, txn)


def get_transaction(db: Session, transaction_id: str) -> TransactionLedger:
    txn = transaction_repository.get_by_id(db, transaction_id)
    if txn is None:
        raise NotFoundError(f"Transaction '{transaction_id}' not found.")
    return txn


def list_transactions(
    db: Session,
    property_id: str | None = None,
) -> list[TransactionLedger]:
    return transaction_repository.list_all(db, property_id=property_id)


def update_transaction(
    db: Session,
    transaction_id: str,
    payload: TransactionLedgerUpdate,
) -> TransactionLedger:
    txn = get_transaction(db, transaction_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.pop("clear_property", None):
        changes["property_id"] = None
    if "property_id" in changes and changes["property_id"] is not None:
        if property_repository.get_by_id(db, changes["property_id"]) is None:
            raise ValidationError(f"Property '{changes['property_id']}' not found.")
    return transaction_repository.update(db, txn, changes)


def delete_transaction(db: Session, transaction_id: str) -> None:
    txn = get_transaction(db, transaction_id)
    transaction_repository.delete(db, txn)
