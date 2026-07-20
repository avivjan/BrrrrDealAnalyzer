from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db import get_db
from treasury.schemas.property_schemas import (
    PropertyStatusCreate,
    PropertyStatusUpdate,
    PropertyStatusRes,
)
from treasury.services import property_service
from treasury.services.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/treasury/properties", tags=["Treasury - Property Status"])


def _to_res(prop) -> PropertyStatusRes:
    return PropertyStatusRes(
        property_id=prop.property_id,
        llc_id=prop.llc_id,
        tax_bucket_balance=prop.tax_bucket_balance,
        tax_to_settle=prop.tax_to_settle,
        ins_bucket_balance=prop.ins_bucket_balance,
        ins_to_settle=prop.ins_to_settle,
        reserve_bucket_balance=prop.reserve_bucket_balance,
        reserve_to_settle=prop.reserve_to_settle,
        reserve_bucket_cap=prop.reserve_bucket_cap,
        reserve_debt=prop.reserve_debt,
        interest_earned_counter=prop.interest_earned_counter,
        base_rent_target=prop.base_rent_target,
        target_tax_allocation=prop.target_tax_allocation,
        target_ins_allocation=prop.target_ins_allocation,
        target_reserve_allocation=prop.target_reserve_allocation,
        force_tax_ins_accrual=prop.force_tax_ins_accrual,
        double_reserve_on_recovery=prop.double_reserve_on_recovery,
        created_at=prop.created_at.isoformat() if prop.created_at else None,
        updated_at=prop.updated_at.isoformat() if prop.updated_at else None,
    )


@router.get("", response_model=list[PropertyStatusRes])
def list_properties(
    llc_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return [_to_res(prop) for prop in property_service.list_properties(db, llc_id=llc_id)]


@router.post("", response_model=PropertyStatusRes, status_code=201)
def create_property(payload: PropertyStatusCreate, db: Session = Depends(get_db)):
    try:
        return _to_res(property_service.create_property(db, payload))
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{property_id}", response_model=PropertyStatusRes)
def get_property(property_id: str, db: Session = Depends(get_db)):
    try:
        return _to_res(property_service.get_property(db, property_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{property_id}", response_model=PropertyStatusRes)
def update_property(
    property_id: str,
    payload: PropertyStatusUpdate,
    db: Session = Depends(get_db),
):
    try:
        return _to_res(property_service.update_property(db, property_id, payload))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{property_id}")
def delete_property(property_id: str, db: Session = Depends(get_db)):
    try:
        property_service.delete_property(db, property_id)
        return {"message": "Property deleted (cascaded to its cash-flow history)."}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
