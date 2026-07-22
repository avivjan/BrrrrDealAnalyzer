"""DB-facing settlement operations.

This module is the adapter between the pure `allocation_engine` waterfall
math and persisted `PropertyStatus` state, plus the handful of settlement
actions that mutate physical/virtual balances directly:

  * `apply_waterfall_to_property`  — run a recovery-rent inflow through the
    5-step waterfall and persist the resulting bucket/debt/settlement moves.
  * `resolve_overflow_decision`    — apply the user's A/B/C choice for a
    'Pending User Overflow Decision' surplus.
  * `approve_hysa_transfer` / `keep_cash_in_checking` — the two email-action
    handlers for the missed-rent express-transfer prompt.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from treasury.models.transaction_ledger import TransactionLedger
from treasury.repositories import property_repository, transaction_repository
from treasury.services import allocation_engine, rent_milestone_service
from treasury.services.allocation_engine import WaterfallInput, WaterfallResult
from treasury.services.exceptions import NotFoundError, ValidationError

_CENTS = Decimal("0.01")

# Overflow decision choices surfaced in the UI when a reserve cap is breached.
OVERFLOW_SPILLOVER = "A"      # Spillover to Cash Flow
OVERFLOW_CROSS_ALLOCATE = "B"  # Cross-Allocate to same-LLC property
OVERFLOW_BREAK_CAP = "C"       # Break Cap
VALID_OVERFLOW_CHOICES = frozenset({OVERFLOW_SPILLOVER, OVERFLOW_CROSS_ALLOCATE, OVERFLOW_BREAK_CAP})


def _money(value) -> Decimal:
    return Decimal(value or 0).quantize(_CENTS)


def _get_property(db: Session, property_id: str):
    prop = property_repository.get_by_id(db, property_id)
    if prop is None:
        raise NotFoundError(f"Property '{property_id}' not found.")
    return prop


def window_bucket_allocated(
    db: Session,
    property_id: str,
    sub_bucket: str,
    *,
    as_of: Optional[datetime] = None,
) -> Decimal:
    """Sum of virtual platform allocations into `sub_bucket` this calendar month.

    Used so partial rent installments only finish the remaining monthly tax /
    reserve target instead of re-allocating the full target every time.
    """
    when = as_of or datetime.now(timezone.utc)
    window_start = rent_milestone_service._window_start(when)
    total = (
        db.query(func.coalesce(func.sum(TransactionLedger.amount), 0))
        .filter(
            TransactionLedger.property_id == property_id,
            TransactionLedger.sub_bucket_assignment == sub_bucket,
            TransactionLedger.is_real_bank_tx.is_(False),
            TransactionLedger.timestamp >= window_start,
            TransactionLedger.timestamp <= when,
        )
        .scalar()
    )
    return _money(total)


def apply_waterfall_to_property(
    db: Session,
    property_id: str,
    rent_received: Decimal,
    *,
    checking_balance: Decimal = Decimal("0"),
    pi_amount: Decimal = Decimal("0"),
    uncollected_reserve_targets: Decimal = Decimal("0"),
    tax_already_allocated: Optional[Decimal] = None,
    reserve_already_allocated: Optional[Decimal] = None,
    as_of: Optional[datetime] = None,
    source_transaction_id: Optional[str] = None,
) -> WaterfallResult:
    """Run recovery rent through the 5-step waterfall and persist the plan.

    The paused `pending_overflow` (if any) is intentionally NOT auto-applied
    — it awaits the operator's A/B/C decision via `resolve_overflow_decision`.

    Virtual Tax / General Reserve ledger rows are minted for the allocated
    amounts so the audit log and remaining-need tracker stay consistent.
    These rows do NOT re-apply bucket effects (the balances are mutated
    directly below) — they are bookkeeping markers only.
    """
    prop = _get_property(db, property_id)
    when = as_of or datetime.now(timezone.utc)

    if tax_already_allocated is None:
        tax_already_allocated = window_bucket_allocated(db, property_id, "Tax", as_of=when)
    if reserve_already_allocated is None:
        reserve_already_allocated = window_bucket_allocated(
            db, property_id, "General Reserve", as_of=when
        )

    inp = WaterfallInput(
        rent_received=_money(rent_received),
        pi_amount=_money(pi_amount),
        checking_balance=_money(checking_balance),
        reserve_debt=_money(prop.reserve_debt),
        reserve_bucket_balance=_money(prop.reserve_bucket_balance),
        reserve_bucket_cap=_money(prop.reserve_bucket_cap),
        target_tax_allocation=_money(prop.target_tax_allocation),
        target_reserve_allocation=_money(prop.target_reserve_allocation),
        tax_already_allocated=_money(tax_already_allocated),
        reserve_already_allocated=_money(reserve_already_allocated),
        chase_reserves=bool(prop.chase_reserves),
        uncollected_reserve_targets=_money(uncollected_reserve_targets),
    )
    result = allocation_engine.run_waterfall(inp)

    prop.reserve_debt = result.new_reserve_debt
    prop.reserve_bucket_balance = _money(prop.reserve_bucket_balance) + result.reserve_balance_delta
    prop.reserve_to_settle = _money(prop.reserve_to_settle) + result.reserve_to_settle_delta
    prop.tax_bucket_balance = _money(prop.tax_bucket_balance) + result.tax_balance_delta
    prop.tax_to_settle = _money(prop.tax_to_settle) + result.tax_to_settle_delta
    db.commit()
    db.refresh(prop)

    # Prefix WATERFALL- so the routing layer never re-applies / reverses these
    # bookkeeping markers (balances were already mutated above).
    batch_id = f"WATERFALL-{source_transaction_id or 'manual'}"
    if result.tax_balance_delta > 0:
        transaction_repository.create(
            db,
            TransactionLedger(
                property_id=prop.property_id,
                amount=result.tax_balance_delta,
                description=f"Waterfall Step 2 tax allocation (source {batch_id})",
                timestamp=when,
                is_real_bank_tx=False,
                sub_bucket_assignment="Tax",
                transaction_type="Rent",
                settlement_batch_id=batch_id,
            ),
        )
    if result.reserve_filled > 0:
        transaction_repository.create(
            db,
            TransactionLedger(
                property_id=prop.property_id,
                amount=result.reserve_filled,
                description=f"Waterfall Step 3 reserve allocation (source {batch_id})",
                timestamp=when,
                is_real_bank_tx=False,
                sub_bucket_assignment="General Reserve",
                transaction_type="Rent",
                settlement_batch_id=batch_id,
            ),
        )
    return result


def resolve_overflow_decision(
    db: Session,
    property_id: str,
    amount: Decimal,
    choice: str,
    *,
    target_property_id: Optional[str] = None,
):
    """Apply the operator's decision for a paused reserve-cap overflow.

      A (Spillover to Cash Flow): release the surplus as clean cash flow — no
          bucket mutation; it simply stays in Checking.
      B (Cross-Allocate): deposit the surplus into ANOTHER property's reserve
          within the exact same LLC (veil protection enforced).
      C (Break Cap): deposit the surplus into THIS property's reserve even
          though it pushes the balance beyond `reserve_bucket_cap`.
    """
    if choice not in VALID_OVERFLOW_CHOICES:
        raise ValidationError(
            f"choice must be one of {sorted(VALID_OVERFLOW_CHOICES)} "
            f"(A=Spillover, B=Cross-Allocate, C=Break Cap), got '{choice}'."
        )
    amount = _money(amount)
    if amount <= 0:
        raise ValidationError("Overflow amount must be positive.")

    source = _get_property(db, property_id)

    if choice == OVERFLOW_SPILLOVER:
        # Nothing to persist — the surplus becomes net operating cash flow.
        return {"choice": choice, "applied_to": None, "amount": str(amount)}

    if choice == OVERFLOW_BREAK_CAP:
        source.reserve_bucket_balance = _money(source.reserve_bucket_balance) + amount
        source.reserve_to_settle = _money(source.reserve_to_settle) + amount
        db.commit()
        db.refresh(source)
        return {"choice": choice, "applied_to": source.property_id, "amount": str(amount)}

    # choice == OVERFLOW_CROSS_ALLOCATE
    if not target_property_id:
        raise ValidationError("Cross-allocation requires a target_property_id.")
    target = _get_property(db, target_property_id)
    if target.llc_id != source.llc_id:
        raise ValidationError(
            "Cross-allocation blocked: target property must share the exact same "
            "llc_id as the source property (multi-LLC veil protection)."
        )
    target.reserve_bucket_balance = _money(target.reserve_bucket_balance) + amount
    target.reserve_to_settle = _money(target.reserve_to_settle) + amount
    db.commit()
    db.refresh(target)
    return {"choice": choice, "applied_to": target.property_id, "amount": str(amount)}


def approve_hysa_transfer(
    db: Session,
    property_id: str,
    pi_amount: Decimal,
    *,
    as_of: Optional[datetime] = None,
) -> dict:
    """'Approve HYSA Transfer' email action.

    Executes an Immediate Express Transfer (Same-Day ACH / instant internal
    transfer) from HYSA/Savings -> Checking so liquidity is in place on/before
    the 9th/10th, BYPASSING the regular 11th batch queue. Records the movement
    in the transaction ledger (physical balance log) rather than queueing it
    in `reserve_to_settle`.
    """
    prop = _get_property(db, property_id)
    pi_amount = _money(pi_amount)
    if pi_amount <= 0:
        raise ValidationError("pi_amount must be positive to execute an express transfer.")

    when = as_of or datetime.now(timezone.utc)
    txn = TransactionLedger(
        property_id=prop.property_id,
        amount=pi_amount,
        description=(
            f"Immediate Express Transfer (Same-Day ACH) HYSA/Savings -> Checking "
            f"to cover 10th P&I draft of ${pi_amount} (bypassed 11th batch queue)."
        ),
        timestamp=when,
        is_real_bank_tx=True,
        sub_bucket_assignment=None,
        transaction_type="Emergency Advance",
        settlement_batch_id="EXPRESS-HYSA",
    )
    created = transaction_repository.create(db, txn)
    return {
        "action": "approve_hysa_transfer",
        "transferred": str(pi_amount),
        "method": "Immediate Express Transfer (Same-Day ACH)",
        "bypassed_batch_queue": True,
        "transaction_id": created.transaction_id,
        "reserve_debt": str(_money(prop.reserve_debt)),
    }


def keep_cash_in_checking(db: Session, property_id: str, pi_amount: Decimal) -> dict:
    """'Keep Cash in Checking' (or ignored) email action.

    No express transfer executes: Checking absorbs the P&I draft locally using
    existing cash. `reserve_to_settle` for the emergency P&I stays $0.00 (never
    queued), while `reserve_debt` remains recorded as +P&I from the missed-rent
    accrual.
    """
    prop = _get_property(db, property_id)
    # Explicitly assert the emergency P&I never queued a physical sweep.
    return {
        "action": "keep_cash_in_checking",
        "transferred": "0.00",
        "reserve_to_settle_for_emergency_pi": "0.00",
        "reserve_debt": str(_money(prop.reserve_debt)),
        "note": "Checking absorbs the P&I draft locally; reserve_debt remains recorded.",
    }
