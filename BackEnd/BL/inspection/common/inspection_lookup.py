"""Finding an inspection (or a photo) from the id in the URL.

Ids are random uuid4 values. Anything that is not a well-formed uuid4, and
any id that matches nothing, gets the same 404, so a probe learns nothing.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from BL.inspection.common.inspection_checklist_config import find_inspection_checklist_item
from DAL.crud.inspection import get_inspection_by_id
from DAL.data_models import PropertyInspection

INSPECTION_NOT_FOUND = "inspection not found"
LARGEST_INSPECTION_DATE_DISTANCE_FROM_TODAY = timedelta(days=2 * 366)


def parse_random_id_or_404(raw_id: str, not_found_detail: str = INSPECTION_NOT_FOUND) -> UUID:
    try:
        parsed_id = UUID(raw_id)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=404, detail=not_found_detail)
    if parsed_id.version != 4 or str(parsed_id) != raw_id.lower():
        raise HTTPException(status_code=404, detail=not_found_detail)
    return parsed_id


def find_inspection_or_404(db: Session, raw_inspection_id: str) -> PropertyInspection:
    inspection = get_inspection_by_id(db, parse_random_id_or_404(raw_inspection_id))
    if inspection is None:
        raise HTTPException(status_code=404, detail=INSPECTION_NOT_FOUND)
    return inspection


def find_checklist_item_or_404(item_key: str) -> dict:
    checklist_item = find_inspection_checklist_item(item_key)
    if checklist_item is None:
        raise HTTPException(status_code=404, detail="checklist item not found")
    return checklist_item


def check_inspection_date_is_reasonable(inspection_date: date) -> None:
    if abs(inspection_date - date.today()) > LARGEST_INSPECTION_DATE_DISTANCE_FROM_TODAY:
        raise HTTPException(status_code=422, detail="inspection_date must be within two years of today")
