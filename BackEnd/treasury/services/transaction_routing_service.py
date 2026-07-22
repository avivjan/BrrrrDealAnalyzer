"""Core domain logic for transaction ingestion, real-time bucket mutation,
and human-in-the-loop reassignment.

Route handlers must never touch bucket balances directly — every mutation,
whether it originates from a live bank webhook, a nightly batch sync, or a
manual HITL override in the Transaction Audit Log, flows through this
module so the ledger and each property's virtual bucket state can never
drift apart.
"""

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from treasury.models.transaction_ledger import TransactionLedger
from treasury.repositories import property_repository, transaction_repository
from treasury.schemas.transaction_schemas import (
    TransactionLedgerCreate,
    TransactionLedgerUpdate,
)
from treasury.services import rent_milestone_service
from treasury.services.exceptions import NotFoundError, ValidationError

# Maps a sub-bucket assignment to the (balance, settlement-queue) columns
# it mutates on `PropertyStatus`. Anything not in this map (i.e. `None`,
# raw real-bank Rent/P&I/Repair rows) never touches a bucket — it's just
# a ledger record of real money movement.
_BUCKET_FIELDS = {
    "Tax": ("tax_bucket_balance", "tax_to_settle"),
    "General Reserve": ("reserve_bucket_balance", "reserve_to_settle"),
}


def _apply_bucket_delta(
    db: Session,
    property_id: Optional[str],
    sub_bucket: Optional[str],
    delta: Decimal,
) -> None:
    """Mutate a property's bucket balance + settlement queue by `delta`.

    `delta` may be negative to unwind a previously-applied effect (an
    edit or delete). No-ops for orphaned transactions or unassigned
    buckets, since there's nothing to settle against.
    """
    if property_id is None or sub_bucket not in _BUCKET_FIELDS or delta == 0:
        return
    prop = property_repository.get_by_id(db, property_id)
    if prop is None:
        return
    balance_field, settle_field = _BUCKET_FIELDS[sub_bucket]
    setattr(prop, balance_field, Decimal(getattr(prop, balance_field)) + delta)
    setattr(prop, settle_field, Decimal(getattr(prop, settle_field)) + delta)
    db.commit()
    db.refresh(prop)


def _apply_effect(db: Session, txn: TransactionLedger) -> None:
    _apply_bucket_delta(db, txn.property_id, txn.sub_bucket_assignment, Decimal(txn.amount))


def _reverse_effect(db: Session, txn: TransactionLedger) -> None:
    _apply_bucket_delta(db, txn.property_id, txn.sub_bucket_assignment, -Decimal(txn.amount))


def _assert_same_llc_veil(
    db: Session,
    old_property_id: Optional[str],
    new_property_id: Optional[str],
) -> None:
    """Multi-LLC veil protection.

    A transaction may only be reassigned to a property inside the exact
    same `llc_id` as its current property. Letting money hop across LLC
    boundaries would commingle funds between legally-separate entities,
    so it's rejected outright rather than silently allowed.
    """
    if old_property_id is None or new_property_id is None or old_property_id == new_property_id:
        return
    new_prop = property_repository.get_by_id(db, new_property_id)
    if new_prop is None:
        raise ValidationError(f"Property '{new_property_id}' not found.")
    old_prop = property_repository.get_by_id(db, old_property_id)
    if old_prop is not None and old_prop.llc_id != new_prop.llc_id:
        raise ValidationError(
            "Cross-LLC reassignment blocked: target property must share the exact same "
            "llc_id as the source property (multi-LLC veil protection)."
        )


def _ingest(
    db: Session,
    payload: TransactionLedgerCreate,
) -> tuple[TransactionLedger, Optional[TransactionLedger]]:
    if payload.property_id is not None and property_repository.get_by_id(db, payload.property_id) is None:
        raise ValidationError(f"Property '{payload.property_id}' not found.")

    txn = TransactionLedger(**payload.model_dump())
    created = transaction_repository.create(db, txn)
    _apply_effect(db, created)
    overflow = rent_milestone_service.process_rent_milestone(db, created, _apply_effect)
    return created, overflow


def create_transaction_with_effects(
    db: Session,
    payload: TransactionLedgerCreate,
) -> TransactionLedger:
    """Manual HITL creation (e.g. "+ Add Transaction" in the audit log).

    Same real-time bucket-mutation + rent-milestone pipeline as a webhook,
    just without the overflow companion entry surfaced back to the caller
    (the audit log will pick it up on its next refresh).
    """
    created, _overflow = _ingest(db, payload)
    return created


def ingest_webhook_transaction(
    db: Session,
    payload: TransactionLedgerCreate,
) -> dict:
    """Webhook / nightly-sync entry point.

    Returns both the primary ledger row and the overflow companion entry
    (if the rent milestone was crossed), so the caller can surface the
    full effect of a single bank event.
    """
    created, overflow = _ingest(db, payload)
    return {"transaction": created, "overflow_transaction": overflow}


def apply_manual_override(
    db: Session,
    transaction_id: str,
    payload: TransactionLedgerUpdate,
) -> TransactionLedger:
    """Human-in-the-loop override.

    Any edit to `property_id`, `sub_bucket_assignment`, `amount`,
    `transaction_type`, or `description` instantly unwinds the
    transaction's prior bucket effect and reapplies the new one, so every
    affected property's balances and settlement queues are recalculated
    in the same request — never left stale until some later batch job.
    """
    txn = transaction_repository.get_by_id(db, transaction_id)
    if txn is None:
        raise NotFoundError(f"Transaction '{transaction_id}' not found.")

    changes = payload.model_dump(exclude_unset=True)
    if changes.pop("clear_property", None):
        changes["property_id"] = None

    if "property_id" in changes:
        _assert_same_llc_veil(db, txn.property_id, changes["property_id"])
    elif txn.property_id is not None and property_repository.get_by_id(db, txn.property_id) is None:
        raise ValidationError(f"Property '{txn.property_id}' not found.")

    # Unwind the effect of the transaction as it stood BEFORE this edit,
    # then persist the edit, then re-apply the effect of the transaction
    # as it stands AFTER — this correctly handles every combination of
    # property, sub-bucket, and amount changing at once.
    _reverse_effect(db, txn)
    updated = transaction_repository.update(db, txn, changes)
    _apply_effect(db, updated)
    return updated


def delete_transaction_with_effects(db: Session, transaction_id: str) -> None:
    """Deleting a ledger line must also unwind whatever bucket effect it
    previously applied — otherwise the property's balance would silently
    retain money attributed to a record that no longer exists.
    """
    txn = transaction_repository.get_by_id(db, transaction_id)
    if txn is None:
        raise NotFoundError(f"Transaction '{transaction_id}' not found.")
    _reverse_effect(db, txn)
    transaction_repository.delete(db, txn)
