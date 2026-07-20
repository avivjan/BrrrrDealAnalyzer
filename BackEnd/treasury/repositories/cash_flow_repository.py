"""Pure data-access layer for `PropertyCashFlowHistory`."""

from typing import Optional

from sqlalchemy.orm import Session

from treasury.models.property_cash_flow_history import PropertyCashFlowHistory


def create(db: Session, snapshot: PropertyCashFlowHistory) -> PropertyCashFlowHistory:
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def get_by_id(db: Session, history_id: str) -> Optional[PropertyCashFlowHistory]:
    return db.get(PropertyCashFlowHistory, history_id)


def list_all(
    db: Session,
    property_id: Optional[str] = None,
) -> list[PropertyCashFlowHistory]:
    query = db.query(PropertyCashFlowHistory)
    if property_id is not None:
        query = query.filter(PropertyCashFlowHistory.property_id == property_id)
    return query.order_by(PropertyCashFlowHistory.month_year).all()


def update(
    db: Session,
    snapshot: PropertyCashFlowHistory,
    changes: dict,
) -> PropertyCashFlowHistory:
    for key, value in changes.items():
        setattr(snapshot, key, value)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def delete(db: Session, snapshot: PropertyCashFlowHistory) -> None:
    db.delete(snapshot)
    db.commit()
