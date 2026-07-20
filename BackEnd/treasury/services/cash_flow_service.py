from sqlalchemy.orm import Session

from treasury.models.property_cash_flow_history import PropertyCashFlowHistory
from treasury.repositories import cash_flow_repository, property_repository
from treasury.schemas.cash_flow_schemas import (
    PropertyCashFlowHistoryCreate,
    PropertyCashFlowHistoryUpdate,
)
from treasury.services.exceptions import NotFoundError, ValidationError


def create_snapshot(
    db: Session,
    payload: PropertyCashFlowHistoryCreate,
) -> PropertyCashFlowHistory:
    if property_repository.get_by_id(db, payload.property_id) is None:
        raise ValidationError(f"Property '{payload.property_id}' not found.")
    data = payload.model_dump()
    snapshot = PropertyCashFlowHistory(**data)
    return cash_flow_repository.create(db, snapshot)


def get_snapshot(db: Session, history_id: str) -> PropertyCashFlowHistory:
    snapshot = cash_flow_repository.get_by_id(db, history_id)
    if snapshot is None:
        raise NotFoundError(f"Cash-flow snapshot '{history_id}' not found.")
    return snapshot


def list_snapshots(
    db: Session,
    property_id: str | None = None,
) -> list[PropertyCashFlowHistory]:
    return cash_flow_repository.list_all(db, property_id=property_id)


def update_snapshot(
    db: Session,
    history_id: str,
    payload: PropertyCashFlowHistoryUpdate,
) -> PropertyCashFlowHistory:
    snapshot = get_snapshot(db, history_id)
    changes = payload.model_dump(exclude_unset=True)
    return cash_flow_repository.update(db, snapshot, changes)


def delete_snapshot(db: Session, history_id: str) -> None:
    snapshot = get_snapshot(db, history_id)
    cash_flow_repository.delete(db, snapshot)
