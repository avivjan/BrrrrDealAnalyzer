"""The inspection endpoints for logged-in users: list, delete, and the deal link (My Deals or Bought).

These routes sit behind the site's normal gates (`main.install_routers`), so
they need the same session as every other data page.
"""

from __future__ import annotations

import logging
from typing import List
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from BL.inspection.common.inspection_deal_links import (
    DEAL_LINK_KINDS,
    DealLinkKind,
    deal_link_kind,
    link_inspection_to,
    linked_deal_of_inspection,
)
from BL.inspection.common.inspection_lookup import find_inspection_or_404
from BL.inspection.common.inspection_photo_google_drive import InspectionPhotoStorageUnavailable, trash_inspection_photo_in_drive
from BL.inspection.common.inspection_views import inspection_list_row_response, linked_deal_response
from BL.inspection.publicInspection import load_public_inspection_response, new_inspection
from DAL.crud.inspection import (
    add_inspection,
    count_photos_per_inspection,
    get_all_inspections_newest_first,
    get_deal_addresses_by_model_and_ids,
    get_deal_by_model_and_id,
    get_drive_file_ids_of_inspection,
    get_inspections_linked_by_column,
    get_items_of_inspections,
)
from DAL.data_models import PropertyInspection
from ReqRes.common.inspection_schemas import (
    InspectionDealLinkReq,
    InspectionDealLinkRes,
    InspectionForDealCreateReq,
    InspectionListRowRes,
    PublicInspectionRes,
)

logger = logging.getLogger(__name__)

DEAL_NOT_FOUND = "deal not found"


def _list_rows(db: Session, inspections: List[PropertyInspection]) -> List[InspectionListRowRes]:
    inspection_ids = [inspection.id for inspection in inspections]
    items_by_inspection_id: dict = {}
    for item in get_items_of_inspections(db, inspection_ids):
        items_by_inspection_id.setdefault(item.inspection_id, []).append(item)
    photo_count_by_inspection_id = count_photos_per_inspection(db, inspection_ids)
    linked_deal_addresses: dict = {}
    for kind in DEAL_LINK_KINDS:
        linked_deal_ids = [getattr(inspection, kind.link_column_name) for inspection in inspections if getattr(inspection, kind.link_column_name)]
        for deal_id, address in get_deal_addresses_by_model_and_ids(db, kind.deal_model, linked_deal_ids).items():
            linked_deal_addresses[(kind, deal_id)] = address
    return [
        inspection_list_row_response(
            inspection,
            items_by_inspection_id.get(inspection.id, []),
            photo_count_by_inspection_id.get(inspection.id, 0),
            linked_deal_addresses.get(linked_deal_of_inspection(inspection)),
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


def _find_deal_or_404(db: Session, kind: DealLinkKind, deal_id: UUID):
    deal = get_deal_by_model_and_id(db, kind.deal_model, deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail=DEAL_NOT_FOUND)
    return deal


def _deal_link_response(db: Session, inspection: PropertyInspection) -> InspectionDealLinkRes:
    kind, deal_id = linked_deal_of_inspection(inspection)
    if kind is None:
        return InspectionDealLinkRes(linked_deal=None)
    deal = get_deal_by_model_and_id(db, kind.deal_model, deal_id)
    return InspectionDealLinkRes(linked_deal=linked_deal_response(inspection, deal.address if deal else None))


def get_inspection_deal_link_details(db: Session, raw_inspection_id: str) -> InspectionDealLinkRes:
    return _deal_link_response(db, find_inspection_or_404(db, raw_inspection_id))


def link_inspection_to_deal_of_board(db: Session, raw_inspection_id: str, request: InspectionDealLinkReq) -> InspectionDealLinkRes:
    inspection = find_inspection_or_404(db, raw_inspection_id)
    kind = deal_link_kind(request.deal_board, request.deal_type)
    _find_deal_or_404(db, kind, request.deal_id)
    link_inspection_to(inspection, kind, request.deal_id)
    db.commit()
    db.refresh(inspection)
    return _deal_link_response(db, inspection)


def unlink_inspection_from_its_deal(db: Session, raw_inspection_id: str) -> InspectionDealLinkRes:
    inspection = find_inspection_or_404(db, raw_inspection_id)
    link_inspection_to(inspection, None, None)
    db.commit()
    return InspectionDealLinkRes(linked_deal=None)


def list_inspections_of_deal(db: Session, deal_board: str, deal_id: UUID, deal_type: str) -> List[InspectionListRowRes]:
    kind = deal_link_kind(deal_board, deal_type)
    _find_deal_or_404(db, kind, deal_id)
    return _list_rows(db, get_inspections_linked_by_column(db, kind.link_column_name, deal_id))


def create_inspection_linked_to_deal(
    db: Session, deal_board: str, deal_id: UUID, deal_type: str, request: InspectionForDealCreateReq
) -> PublicInspectionRes:
    kind = deal_link_kind(deal_board, deal_type)
    deal = _find_deal_or_404(db, kind, deal_id)
    inspection = new_inspection(deal.address, request.inspection_date, request.inspector_name)
    link_inspection_to(inspection, kind, deal_id)
    add_inspection(db, inspection)
    db.commit()
    db.refresh(inspection)
    return load_public_inspection_response(db, inspection)
