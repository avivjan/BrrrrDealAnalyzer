"""The inspection endpoints for logged-in users: list, delete, and the Bought Deal link.

These routes sit behind the site's normal gates (`main.install_routers`), so
they need the same session as every other data page.
"""

from __future__ import annotations

import logging
from typing import List
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from BL.inspection.common.inspection_lookup import find_inspection_or_404
from BL.inspection.common.inspection_photo_google_drive import InspectionPhotoStorageUnavailable, trash_inspection_photo_in_drive
from BL.inspection.common.inspection_views import inspection_list_row_response, linked_bought_deal_response, linked_deal_type_and_id
from BL.inspection.publicInspection import load_public_inspection_response, new_inspection
from DAL.crud.inspection import (
    add_inspection,
    count_photos_per_inspection,
    get_all_inspections_newest_first,
    get_bought_deal_addresses_by_ids,
    get_bought_deal_by_id_and_type,
    get_drive_file_ids_of_inspection,
    get_inspections_linked_to_bought_deal,
    get_items_of_inspections,
)
from DAL.data_models import PropertyInspection
from ReqRes.common.inspection_schemas import (
    InspectionDealLinkReq,
    InspectionDealLinkRes,
    InspectionForBoughtDealCreateReq,
    InspectionListRowRes,
    PublicInspectionRes,
)

logger = logging.getLogger(__name__)

BOUGHT_DEAL_NOT_FOUND = "bought deal not found"


def _list_rows(db: Session, inspections: List[PropertyInspection]) -> List[InspectionListRowRes]:
    inspection_ids = [inspection.id for inspection in inspections]
    items_by_inspection_id: dict = {}
    for item in get_items_of_inspections(db, inspection_ids):
        items_by_inspection_id.setdefault(item.inspection_id, []).append(item)
    photo_count_by_inspection_id = count_photos_per_inspection(db, inspection_ids)
    linked_deal_addresses = get_bought_deal_addresses_by_ids(
        db,
        [inspection.linked_bought_brrrr_deal_id for inspection in inspections if inspection.linked_bought_brrrr_deal_id],
        [inspection.linked_bought_flip_deal_id for inspection in inspections if inspection.linked_bought_flip_deal_id],
    )
    return [
        inspection_list_row_response(
            inspection,
            items_by_inspection_id.get(inspection.id, []),
            photo_count_by_inspection_id.get(inspection.id, 0),
            linked_deal_addresses.get(linked_deal_type_and_id(inspection)),
        )
        for inspection in inspections
    ]


def list_all_inspections(db: Session) -> List[InspectionListRowRes]:
    return _list_rows(db, get_all_inspections_newest_first(db))


def delete_inspection_and_its_photos(db: Session, raw_inspection_id: str) -> None:
    inspection = find_inspection_or_404(db, raw_inspection_id)
    drive_file_ids = get_drive_file_ids_of_inspection(db, inspection.id)
    db.delete(inspection)
    db.commit()
    for drive_file_id in drive_file_ids:
        try:
            trash_inspection_photo_in_drive(drive_file_id)
        except InspectionPhotoStorageUnavailable:
            logger.warning("inspection deleted, but a Drive photo could not be trashed")


def _find_bought_deal_or_404(db: Session, deal_id: UUID, deal_type: str):
    deal = get_bought_deal_by_id_and_type(db, deal_id, deal_type)
    if deal is None:
        raise HTTPException(status_code=404, detail=BOUGHT_DEAL_NOT_FOUND)
    return deal


def _deal_link_response(db: Session, inspection: PropertyInspection) -> InspectionDealLinkRes:
    deal_type, deal_id = linked_deal_type_and_id(inspection)
    if deal_type is None:
        return InspectionDealLinkRes(linked_deal=None)
    deal = get_bought_deal_by_id_and_type(db, deal_id, deal_type)
    return InspectionDealLinkRes(linked_deal=linked_bought_deal_response(inspection, deal.address if deal else None))


def get_inspection_deal_link_details(db: Session, raw_inspection_id: str) -> InspectionDealLinkRes:
    return _deal_link_response(db, find_inspection_or_404(db, raw_inspection_id))


def _link_inspection(inspection: PropertyInspection, deal_type: str, deal_id: UUID) -> None:
    inspection.linked_bought_brrrr_deal_id = deal_id if deal_type == "BRRRR" else None
    inspection.linked_bought_flip_deal_id = deal_id if deal_type == "FLIP" else None


def link_inspection_to_bought_deal(db: Session, raw_inspection_id: str, request: InspectionDealLinkReq) -> InspectionDealLinkRes:
    inspection = find_inspection_or_404(db, raw_inspection_id)
    _find_bought_deal_or_404(db, request.bought_deal_id, request.deal_type)
    _link_inspection(inspection, request.deal_type, request.bought_deal_id)
    db.commit()
    db.refresh(inspection)
    return _deal_link_response(db, inspection)


def unlink_inspection_from_bought_deal(db: Session, raw_inspection_id: str) -> InspectionDealLinkRes:
    inspection = find_inspection_or_404(db, raw_inspection_id)
    _link_inspection(inspection, "", None)
    db.commit()
    return InspectionDealLinkRes(linked_deal=None)


def list_inspections_of_bought_deal(db: Session, deal_id: UUID, deal_type: str) -> List[InspectionListRowRes]:
    _find_bought_deal_or_404(db, deal_id, deal_type)
    return _list_rows(db, get_inspections_linked_to_bought_deal(db, deal_id, deal_type))


def create_inspection_linked_to_bought_deal(
    db: Session, deal_id: UUID, deal_type: str, request: InspectionForBoughtDealCreateReq
) -> PublicInspectionRes:
    deal = _find_bought_deal_or_404(db, deal_id, deal_type)
    inspection = new_inspection(deal.address, request.inspection_date, request.inspector_name)
    _link_inspection(inspection, deal_type, deal_id)
    add_inspection(db, inspection)
    db.commit()
    db.refresh(inspection)
    return load_public_inspection_response(db, inspection)
