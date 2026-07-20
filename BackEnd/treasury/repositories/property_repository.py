"""Pure data-access layer for `PropertyStatus`."""

from typing import Optional

from sqlalchemy.orm import Session

from treasury.models.property_status import PropertyStatus


def create(db: Session, prop: PropertyStatus) -> PropertyStatus:
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop


def get_by_id(db: Session, property_id: str) -> Optional[PropertyStatus]:
    return db.get(PropertyStatus, property_id)


def list_all(db: Session, llc_id: Optional[str] = None) -> list[PropertyStatus]:
    query = db.query(PropertyStatus)
    if llc_id is not None:
        query = query.filter(PropertyStatus.llc_id == llc_id)
    return query.order_by(PropertyStatus.created_at).all()


def update(db: Session, prop: PropertyStatus, changes: dict) -> PropertyStatus:
    for key, value in changes.items():
        setattr(prop, key, value)
    db.commit()
    db.refresh(prop)
    return prop


def delete(db: Session, prop: PropertyStatus) -> None:
    db.delete(prop)
    db.commit()
