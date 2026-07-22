"""Route handling only for the settlement / waterfall / missed-rent workflows.

Every byte of domain logic lives in `allocation_engine`, `settlement_service`,
and `missed_rent_service`; this router just adapts HTTP in and out.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db import get_db
from treasury.controllers.property_controller import _to_res
from treasury.schemas.settlement_schemas import (
    MissedRentCheckRequest,
    OverflowDecisionRequest,
    WaterfallRunRequest,
)
from treasury.services import (
    missed_rent_service,
    property_service,
    settlement_service,
)
from treasury.services.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/treasury/settlement", tags=["Treasury - Settlement & Waterfall"])


@router.post("/waterfall")
def run_waterfall(payload: WaterfallRunRequest, db: Session = Depends(get_db)):
    """Run a (recovery) rent inflow through the 5-step waterfall and persist it."""
    try:
        result = settlement_service.apply_waterfall_to_property(
            db,
            payload.property_id,
            payload.rent_received,
            checking_balance=payload.checking_balance,
            pi_amount=payload.pi_amount,
            uncollected_reserve_targets=payload.uncollected_reserve_targets,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    prop = property_service.get_property(db, payload.property_id)
    return {"result": result.as_dict(), "property": _to_res(prop).model_dump()}


@router.post("/missed-rent-check")
def missed_rent_check(payload: MissedRentCheckRequest, db: Session = Depends(get_db)):
    """8th-of-the-month missed rent check for a single property."""
    as_of = None
    if payload.as_of:
        try:
            as_of = datetime.fromisoformat(payload.as_of)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid as_of: {exc}") from exc
    try:
        result = missed_rent_service.run_missed_rent_check(
            db,
            payload.property_id,
            payload.pi_amount,
            as_of=as_of,
            notify_email=payload.notify_email,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if result is None:
        return {"status": "rent_received", "property_id": payload.property_id}
    return result


@router.post("/overflow-decision")
def overflow_decision(payload: OverflowDecisionRequest, db: Session = Depends(get_db)):
    """Apply the operator's A/B/C decision for a paused reserve-cap overflow."""
    try:
        return settlement_service.resolve_overflow_decision(
            db,
            payload.property_id,
            payload.amount,
            payload.choice,
            target_property_id=payload.target_property_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --- Email action buttons (clickable one-click GET links) ----------------------


@router.get("/hysa-transfer/approve")
def approve_hysa_transfer(
    property_id: str = Query(..., min_length=1),
    pi_amount: str = Query(...),
    db: Session = Depends(get_db),
):
    """'Approve HYSA Transfer': immediate express Savings -> Checking transfer."""
    try:
        return settlement_service.approve_hysa_transfer(db, property_id, pi_amount)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/hysa-transfer/keep")
def keep_cash_in_checking(
    property_id: str = Query(..., min_length=1),
    pi_amount: str = Query("0"),
    db: Session = Depends(get_db),
):
    """'Keep Cash in Checking': no transfer; Checking absorbs the draft locally."""
    try:
        return settlement_service.keep_cash_in_checking(db, property_id, pi_amount)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
