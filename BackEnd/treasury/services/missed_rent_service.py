"""8th-of-the-Month Missed Rent & Email Workflow.

An automated check meant to run at 11:59 PM on the 8th of every month. For
each property it compares cumulative rent received in the current window
against `base_rent_target`. When rent is unpaid or only partial, it:

  1. Takes the upcoming 10th P&I mortgage draft amount (supplied by caller).
  2. Virtually deducts the P&I from `reserve_bucket_balance`.
  3. Increments `reserve_debt` by the P&I amount (+P&I).
  4. Performs the standard virtual tax allocation: adds `target_tax_allocation`
     to `tax_bucket_balance` and tracks it in `tax_to_settle` for the normal
     future 11th settlement sweep. Because property taxes are remitted to the
     state annually in November, a missed rent payment does NOT trigger any
     emergency physical transfer into Savings — the tax simply accrues
     virtually and physically catches up on future 11th sweeps once rent
     recovers.
  5. Sends the operator an email offering an Immediate Express HYSA transfer.

Scheduling (cron / APScheduler at 23:59 on day 8) is wired at the app layer;
this module exposes the pure workflow so it stays fully unit-testable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from treasury.models.transaction_ledger import TransactionLedger
from treasury.repositories import property_repository, transaction_repository
from treasury.services import rent_milestone_service, treasury_mailer
from treasury.services.exceptions import NotFoundError

_CENTS = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(value or 0).quantize(_CENTS)


def run_missed_rent_check(
    db: Session,
    property_id: str,
    pi_amount: Decimal,
    *,
    as_of: Optional[datetime] = None,
    notify_email: str = "operator@example.com",
    base_action_url: str = "http://localhost:8000/treasury/settlement",
    send: bool = True,
) -> Optional[dict]:
    """Run the missed-rent workflow for a single property.

    Returns a result dict (including the generated email payload) when rent
    was missed/partial and the workflow fired, or ``None`` when rent for the
    window has already met/exceeded the target (nothing to do).
    """
    prop = property_repository.get_by_id(db, property_id)
    if prop is None:
        raise NotFoundError(f"Property '{property_id}' not found.")

    target = _money(prop.base_rent_target)
    if target <= 0:
        # No rent target configured — cannot classify a "miss".
        return None

    when = as_of or datetime.now(timezone.utc)
    window_start = rent_milestone_service._window_start(when)
    cumulative = rent_milestone_service.cumulative_rent_received(
        db, property_id, window_start, when
    )
    if cumulative >= target:
        # Rent fully received this cycle — no missed-rent action required.
        return None

    pi_amount = _money(pi_amount)
    tax_alloc = _money(prop.target_tax_allocation)

    # Step 2: virtually deduct P&I from the reserve bucket.
    prop.reserve_bucket_balance = _money(prop.reserve_bucket_balance) - pi_amount
    # Step 3: record the shortfall as reserve debt (+P&I).
    prop.reserve_debt = _money(prop.reserve_debt) + pi_amount
    # Step 4: standard virtual tax allocation (accrue + queue for 11th sweep).
    #         NO emergency physical transfer — taxes are remitted annually in Nov.
    prop.tax_bucket_balance = _money(prop.tax_bucket_balance) + tax_alloc
    prop.tax_to_settle = _money(prop.tax_to_settle) + tax_alloc
    db.commit()
    db.refresh(prop)

    # Bookkeeping marker so the waterfall's remaining-need tracker knows tax
    # for this cycle was already virtually accrued (WATERFALL- prefix skips
    # the routing layer's bucket re-apply / reverse).
    if tax_alloc > 0:
        transaction_repository.create(
            db,
            TransactionLedger(
                property_id=prop.property_id,
                amount=tax_alloc,
                description="Missed-rent virtual tax allocation (queued for 11th sweep)",
                timestamp=when,
                is_real_bank_tx=False,
                sub_bucket_assignment="Tax",
                transaction_type="Rent",
                settlement_batch_id="WATERFALL-MISSED-RENT",
            ),
        )

    # Step 5: build + send the express-transfer decision email.
    approve_url = (
        f"{base_action_url}/hysa-transfer/approve"
        f"?property_id={prop.property_id}&pi_amount={pi_amount}"
    )
    keep_url = (
        f"{base_action_url}/hysa-transfer/keep"
        f"?property_id={prop.property_id}&pi_amount={pi_amount}"
    )
    email = treasury_mailer.build_missed_rent_email(
        to=notify_email,
        property_name=prop.property_name or prop.property_id,
        pi_amount=pi_amount,
        approve_url=approve_url,
        keep_url=keep_url,
    )
    email_sent = treasury_mailer.send(email) if send else False

    return {
        "status": "missed_rent",
        "property_id": prop.property_id,
        "cumulative_rent_received": str(_money(cumulative)),
        "base_rent_target": str(target),
        "pi_amount": str(pi_amount),
        "reserve_debt": str(_money(prop.reserve_debt)),
        "reserve_bucket_balance": str(_money(prop.reserve_bucket_balance)),
        "tax_bucket_balance": str(_money(prop.tax_bucket_balance)),
        "tax_to_settle": str(_money(prop.tax_to_settle)),
        "email_sent": bool(email_sent),
        "email": email.as_dict(),
    }
