from typing import List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from DAL.data_models import (
    PropertyInspection,
    PropertyInspectionItem,
    PropertyInspectionPhoto,
)


def add_inspection(db: Session, inspection: PropertyInspection) -> PropertyInspection:
    db.add(inspection)
    return inspection


def get_inspection_by_id(db: Session, inspection_id: UUID) -> Optional[PropertyInspection]:
    return db.query(PropertyInspection).filter(PropertyInspection.id == inspection_id).first()


def get_all_inspections_newest_first(db: Session) -> List[PropertyInspection]:
    return db.query(PropertyInspection).order_by(PropertyInspection.created_at.desc()).all()


def get_inspections_linked_by_column(db: Session, link_column_name: str, deal_id: UUID) -> List[PropertyInspection]:
    linked_deal_column = getattr(PropertyInspection, link_column_name)
    return db.query(PropertyInspection).filter(linked_deal_column == deal_id).order_by(PropertyInspection.created_at.desc()).all()


def get_items_of_inspection(db: Session, inspection_id: UUID) -> List[PropertyInspectionItem]:
    return db.query(PropertyInspectionItem).filter(PropertyInspectionItem.inspection_id == inspection_id).all()


def get_items_of_inspections(db: Session, inspection_ids: List[UUID]) -> List[PropertyInspectionItem]:
    if not inspection_ids:
        return []
    return db.query(PropertyInspectionItem).filter(PropertyInspectionItem.inspection_id.in_(inspection_ids)).all()


def get_item_of_inspection_for_update(db: Session, inspection_id: UUID, item_key: str) -> Optional[PropertyInspectionItem]:
    """Locks the row so two devices saving the same item merge one after the other."""

    return (
        db.query(PropertyInspectionItem)
        .filter(PropertyInspectionItem.inspection_id == inspection_id, PropertyInspectionItem.item_key == item_key)
        .with_for_update()
        .first()
    )


def get_photos_of_inspection(db: Session, inspection_id: UUID) -> List[PropertyInspectionPhoto]:
    return (
        db.query(PropertyInspectionPhoto)
        .filter(PropertyInspectionPhoto.inspection_id == inspection_id)
        .order_by(PropertyInspectionPhoto.created_at)
        .all()
    )


def get_photo_of_inspection(db: Session, inspection_id: UUID, photo_id: UUID) -> Optional[PropertyInspectionPhoto]:
    return (
        db.query(PropertyInspectionPhoto)
        .filter(PropertyInspectionPhoto.inspection_id == inspection_id, PropertyInspectionPhoto.id == photo_id)
        .first()
    )


def count_photos_of_inspection(db: Session, inspection_id: UUID, item_key: Optional[str] = None) -> int:
    query = db.query(func.count(PropertyInspectionPhoto.id)).filter(PropertyInspectionPhoto.inspection_id == inspection_id)
    if item_key is not None:
        query = query.filter(PropertyInspectionPhoto.item_key == item_key)
    return int(query.scalar() or 0)


def count_photos_per_inspection(db: Session, inspection_ids: List[UUID]) -> dict:
    if not inspection_ids:
        return {}
    rows = (
        db.query(PropertyInspectionPhoto.inspection_id, func.count(PropertyInspectionPhoto.id))
        .filter(PropertyInspectionPhoto.inspection_id.in_(inspection_ids))
        .group_by(PropertyInspectionPhoto.inspection_id)
        .all()
    )
    return {inspection_id: int(photo_count) for inspection_id, photo_count in rows}


def get_drive_file_ids_of_inspection(db: Session, inspection_id: UUID) -> List[str]:
    rows = db.query(PropertyInspectionPhoto.drive_file_id).filter(PropertyInspectionPhoto.inspection_id == inspection_id).all()
    return [drive_file_id for (drive_file_id,) in rows]


def get_deal_by_model_and_id(db: Session, deal_model, deal_id: UUID):
    return db.query(deal_model).filter(deal_model.id == deal_id).first()


def get_deal_addresses_by_model_and_ids(db: Session, deal_model, deal_ids: List[UUID]) -> dict:
    """{deal_id: address} for the linked deals shown in the authenticated list."""

    if not deal_ids:
        return {}
    return {deal_id: address for deal_id, address in db.query(deal_model.id, deal_model.address).filter(deal_model.id.in_(deal_ids))}


def repoint_inspection_links(db: Session, from_link_column_name: str, from_deal_id: UUID, to_link_column_name: str, to_deal_id: UUID) -> int:
    """Moves every inspection linked to one deal onto another (Move to Bought). The caller commits."""

    moved_count = 0
    for inspection in get_inspections_linked_by_column(db, from_link_column_name, from_deal_id):
        setattr(inspection, from_link_column_name, None)
        setattr(inspection, to_link_column_name, to_deal_id)
        moved_count += 1
    return moved_count
