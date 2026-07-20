from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db import get_db
from treasury.schemas.cash_flow_schemas import (
    PropertyCashFlowHistoryCreate,
    PropertyCashFlowHistoryUpdate,
    PropertyCashFlowHistoryRes,
)
from treasury.services import cash_flow_service
from treasury.services.exceptions import NotFoundError, ValidationError

router = APIRouter(
    prefix="/treasury/cash-flow-history",
    tags=["Treasury - Property Cash Flow History"],
)


def _to_res(snapshot) -> PropertyCashFlowHistoryRes:
    return PropertyCashFlowHistoryRes(
        history_id=snapshot.history_id,
        property_id=snapshot.property_id,
        month_year=snapshot.month_year,
        monthly_cash_flow=snapshot.monthly_cash_flow,
        cumulative_cash_flow=snapshot.cumulative_cash_flow,
        created_at=snapshot.created_at.isoformat() if snapshot.created_at else None,
        updated_at=snapshot.updated_at.isoformat() if snapshot.updated_at else None,
    )


@router.get("", response_model=list[PropertyCashFlowHistoryRes])
def list_snapshots(
    property_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return [_to_res(row) for row in cash_flow_service.list_snapshots(db, property_id)]


@router.post("", response_model=PropertyCashFlowHistoryRes, status_code=201)
def create_snapshot(payload: PropertyCashFlowHistoryCreate, db: Session = Depends(get_db)):
    try:
        return _to_res(cash_flow_service.create_snapshot(db, payload))
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{history_id}", response_model=PropertyCashFlowHistoryRes)
def get_snapshot(history_id: str, db: Session = Depends(get_db)):
    try:
        return _to_res(cash_flow_service.get_snapshot(db, history_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{history_id}", response_model=PropertyCashFlowHistoryRes)
def update_snapshot(
    history_id: str,
    payload: PropertyCashFlowHistoryUpdate,
    db: Session = Depends(get_db),
):
    try:
        return _to_res(cash_flow_service.update_snapshot(db, history_id, payload))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{history_id}")
def delete_snapshot(history_id: str, db: Session = Depends(get_db)):
    try:
        cash_flow_service.delete_snapshot(db, history_id)
        return {"message": "Cash-flow snapshot deleted."}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
