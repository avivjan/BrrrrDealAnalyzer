from sqlalchemy.orm import Session

from treasury.models.llc_configuration import LLCConfiguration
from treasury.repositories import llc_repository
from treasury.schemas.llc_schemas import LLCConfigurationCreate, LLCConfigurationUpdate
from treasury.services.exceptions import NotFoundError


def create_llc(db: Session, payload: LLCConfigurationCreate) -> LLCConfiguration:
    data = payload.model_dump()
    llc = LLCConfiguration(**data)
    return llc_repository.create(db, llc)


def get_llc(db: Session, llc_id: str) -> LLCConfiguration:
    llc = llc_repository.get_by_id(db, llc_id)
    if llc is None:
        raise NotFoundError(f"LLC '{llc_id}' not found.")
    return llc


def list_llcs(db: Session) -> list[LLCConfiguration]:
    return llc_repository.list_all(db)


def update_llc(
    db: Session,
    llc_id: str,
    payload: LLCConfigurationUpdate,
) -> LLCConfiguration:
    llc = get_llc(db, llc_id)
    changes = payload.model_dump(exclude_unset=True)
    return llc_repository.update(db, llc, changes)


def delete_llc(db: Session, llc_id: str) -> None:
    llc = get_llc(db, llc_id)
    llc_repository.delete(db, llc)
