"""Cumulative Rent Milestone Engine.

Rent often arrives as several partial bank payments inside the same
billing window (a tenant paying in two installments, a co-signer covering
the remainder, etc.). Overflow — money collected beyond `base_rent_target`
— must only be swept into the reserve bucket once the *cumulative* rent
received in the current window has met or exceeded the target. A single
partial payment must never be treated as overflow just because it looks
large in isolation.

This module is intentionally stateless: it derives "how much rent has
been received this window" by summing the ledger directly rather than
maintaining a separate running counter, so it can never drift out of sync
with the source of truth (the removed `interest_earned_counter` from
Phase 1 was exactly this kind of drift-prone shadow state).
"""

from datetime import datetime
from decimal import Decimal
from typing import Callable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from treasury.models.transaction_ledger import TransactionLedger
from treasury.repositories import property_repository, transaction_repository

ApplyEffect = Callable[[Session, TransactionLedger], None]


def _window_start(timestamp: datetime) -> datetime:
    """Current data window = calendar month containing `timestamp`."""
    return timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def cumulative_rent_received(
    db: Session,
    property_id: str,
    window_start: datetime,
    window_end: datetime,
) -> Decimal:
    """Sum of real-bank Rent transactions for a property within the window
    (inclusive on both ends), straight from the ledger.
    """
    total = (
        db.query(func.coalesce(func.sum(TransactionLedger.amount), 0))
        .filter(
            TransactionLedger.property_id == property_id,
            TransactionLedger.transaction_type == "Rent",
            TransactionLedger.is_real_bank_tx.is_(True),
            TransactionLedger.timestamp >= window_start,
            TransactionLedger.timestamp <= window_end,
        )
        .scalar()
    )
    return Decimal(total or 0)


def process_rent_milestone(
    db: Session,
    txn: TransactionLedger,
    apply_effect: ApplyEffect,
) -> Optional[TransactionLedger]:
    """Run the milestone check immediately after a real-bank Rent
    transaction is ingested.

    Only the portion of cumulative rent that crosses `base_rent_target`
    for the FIRST time is swept — a payment that merely brings the total
    exactly to the target produces no overflow (there's no excess to
    sweep yet), while any rent received once the target is already met
    is entirely overflow.

    Returns the minted virtual overflow entry (already applied to the
    property's reserve bucket), or None if no overflow was triggered.
    """
    if txn.transaction_type != "Rent" or not txn.is_real_bank_tx or txn.property_id is None:
        return None

    prop = property_repository.get_by_id(db, txn.property_id)
    if prop is None:
        return None

    target = Decimal(prop.base_rent_target)
    if target <= 0:
        return None

    window_start = _window_start(txn.timestamp)
    cumulative_through_this_tx = cumulative_rent_received(
        db, txn.property_id, window_start, txn.timestamp
    )
    cumulative_before = cumulative_through_this_tx - Decimal(txn.amount)

    if cumulative_before >= target:
        # Target was already met before this payment arrived — every
        # dollar of it is overflow.
        overflow_amount = Decimal(txn.amount)
    else:
        # Only the slice that pushes cumulative rent past the target
        # counts as overflow; reaching the target exactly yields zero.
        overflow_amount = max(Decimal("0"), cumulative_through_this_tx - target)

    if overflow_amount <= 0:
        return None

    overflow_txn = TransactionLedger(
        property_id=txn.property_id,
        amount=overflow_amount,
        description=(
            f"Rent overflow swept to reserve (milestone crossed by transaction "
            f"{txn.transaction_id})"
        ),
        timestamp=txn.timestamp,
        is_real_bank_tx=False,
        sub_bucket_assignment="General Reserve",
        transaction_type="Rent",
        settlement_batch_id=txn.transaction_id,
    )
    created = transaction_repository.create(db, overflow_txn)
    apply_effect(db, created)
    return created
