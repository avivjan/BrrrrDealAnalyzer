"""Thin orchestration layer for the `/treasury/transactions` CRUD routes.

All bucket-mutation-aware domain logic (real-time balance/settlement
mutation, rent-milestone overflow, multi-LLC veil protection) lives in
`transaction_routing_service` — this module exists so the controller's
import surface stays stable while that logic evolves underneath it.
"""

from sqlalchemy.orm import Session

from treasury.models.transaction_ledger import TransactionLedger
from treasury.repositories import transaction_repository
from treasury.schemas.transaction_schemas import (
    TransactionLedgerCreate,
    TransactionLedgerUpdate,
)
from treasury.services import transaction_routing_service
from treasury.services.exceptions import NotFoundError


def create_transaction(
    db: Session,
    payload: TransactionLedgerCreate,
) -> TransactionLedger:
    return transaction_routing_service.create_transaction_with_effects(db, payload)


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
    return transaction_routing_service.apply_manual_override(db, transaction_id, payload)


def delete_transaction(db: Session, transaction_id: str) -> None:
    transaction_routing_service.delete_transaction_with_effects(db, transaction_id)
