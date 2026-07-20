"""Pure data-access layer for `LLCConfiguration`."""

from typing import Optional

from sqlalchemy.orm import Session

from treasury.models.llc_configuration import LLCConfiguration


def create(db: Session, llc: LLCConfiguration) -> LLCConfiguration:
    db.add(llc)
    db.commit()
    db.refresh(llc)
    return llc


def get_by_id(db: Session, llc_id: str) -> Optional[LLCConfiguration]:
    return db.get(LLCConfiguration, llc_id)


def list_all(db: Session) -> list[LLCConfiguration]:
    return db.query(LLCConfiguration).order_by(LLCConfiguration.llc_name).all()


def update(db: Session, llc: LLCConfiguration, changes: dict) -> LLCConfiguration:
    for key, value in changes.items():
        setattr(llc, key, value)
    db.commit()
    db.refresh(llc)
    return llc


def delete(db: Session, llc: LLCConfiguration) -> None:
    db.delete(llc)
    db.commit()
