from typing import List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from DAL.data_models import (
    BoughtBrrrDeal,
    BoughtFlipDeal,
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


def get_inspections_linked_to_bought_deal(db: Session, deal_id: UUID, deal_type: str) -> List[PropertyInspection]:
    linked_deal_column = (
        PropertyInspection.linked_bought_brrrr_deal_id if deal_type == "BRRRR" else PropertyInspection.linked_bought_flip_deal_id
    )
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


def get_bought_deal_by_id_and_type(db: Session, deal_id: UUID, deal_type: str):
    deal_model = BoughtBrrrDeal if deal_type == "BRRRR" else BoughtFlipDeal
    return db.query(deal_model).filter(deal_model.id == deal_id).first()


def get_bought_deal_addresses_by_ids(db: Session, brrrr_deal_ids: List[UUID], flip_deal_ids: List[UUID]) -> dict:
    """{(deal_type, deal_id): address} for the linked deals shown in the authenticated list."""

    addresses: dict = {}
    if brrrr_deal_ids:
        for deal_id, address in db.query(BoughtBrrrDeal.id, BoughtBrrrDeal.address).filter(BoughtBrrrDeal.id.in_(brrrr_deal_ids)):
            addresses[("BRRRR", deal_id)] = address
    if flip_deal_ids:
        for deal_id, address in db.query(BoughtFlipDeal.id, BoughtFlipDeal.address).filter(BoughtFlipDeal.id.in_(flip_deal_ids)):
            addresses[("FLIP", deal_id)] = address
    return addresses

