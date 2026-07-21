import uuid

from sqlalchemy.orm import Session

from treasury.models.property_status import PropertyStatus
from treasury.repositories import llc_repository, property_repository
from treasury.schemas.property_schemas import PropertyStatusCreate, PropertyStatusUpdate
from treasury.services.exceptions import NotFoundError, ValidationError


def create_property(db: Session, payload: PropertyStatusCreate) -> PropertyStatus:
    if llc_repository.get_by_id(db, payload.llc_id) is None:
        raise ValidationError(f"LLC '{payload.llc_id}' not found.")
    data = payload.model_dump()
    # Always mint an opaque UUID — never accept address strings as PKs.
    data["property_id"] = uuid.uuid4().hex
    data["property_name"] = data["property_name"].strip()
    if not data["property_name"]:
        raise ValidationError("property_name is required.")
    prop = PropertyStatus(**data)
    return property_repository.create(db, prop)


def get_property(db: Session, property_id: str) -> PropertyStatus:
    prop = property_repository.get_by_id(db, property_id)
    if prop is None:
        raise NotFoundError(f"Property '{property_id}' not found.")
    return prop


def list_properties(db: Session, llc_id: str | None = None) -> list[PropertyStatus]:
    return property_repository.list_all(db, llc_id=llc_id)


def update_property(
    db: Session,
    property_id: str,
    payload: PropertyStatusUpdate,
) -> PropertyStatus:
    prop = get_property(db, property_id)
    changes = payload.model_dump(exclude_unset=True)
    if "llc_id" in changes and llc_repository.get_by_id(db, changes["llc_id"]) is None:
        raise ValidationError(f"LLC '{changes['llc_id']}' not found.")
    if "property_name" in changes:
        changes["property_name"] = str(changes["property_name"]).strip()
        if not changes["property_name"]:
            raise ValidationError("property_name cannot be empty.")
    return property_repository.update(db, prop, changes)


def delete_property(db: Session, property_id: str) -> None:
    prop = get_property(db, property_id)
    property_repository.delete(db, prop)
