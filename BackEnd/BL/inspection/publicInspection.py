"""The public inspection endpoints: anyone holding the inspection's link."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from BL.inspection.common.inspection_checklist_config import (
    ITEM_STATUS_NOT_CHECKED,
    InspectionFieldValueInvalid,
    find_inspection_checklist_item,
    validate_item_field_value_changes,
)
from BL.inspection.common.inspection_lookup import (
    check_inspection_date_is_reasonable,
    find_checklist_item_or_404,
    find_inspection_or_404,
)
from BL.inspection.common.inspection_report_delivery import (
    MAXIMUM_REPORTS_PER_INSPECTION_PER_DAY,
    count_reports_of_inspection_today,
    latest_report_delivery_status,
    record_inspection_report,
)
from BL.inspection.common.inspection_views import (
    critical_item_keys_not_checked,
    inspection_item_response,
    public_inspection_response,
)
from DAL.crud.inspection import (
    add_inspection,
    get_item_of_inspection_for_update,
    get_items_of_inspection,
    get_photos_of_inspection,
)
from DAL.data_models import PropertyInspection, PropertyInspectionItem
from DAL.data_models.inspection.models import INSPECTION_STATUS_COMPLETED
from ReqRes.common.inspection_schemas import (
    InspectionCompleteReq,
    InspectionCreateReq,
    InspectionItemRes,
    InspectionItemUpdateReq,
    InspectionStartInfoUpdateReq,
    PublicInspectionRes,
)


def load_public_inspection_response(db: Session, inspection: PropertyInspection) -> PublicInspectionRes:
    return public_inspection_response(
        inspection,
        get_items_of_inspection(db, inspection.id),
        get_photos_of_inspection(db, inspection.id),
        latest_report_delivery_status(db, inspection.id),
    )


def new_inspection(property_address: str, inspection_date: date | None, inspector_name: str | None) -> PropertyInspection:
    chosen_inspection_date = inspection_date or date.today()
    check_inspection_date_is_reasonable(chosen_inspection_date)
    return PropertyInspection(
        property_address=property_address,
        inspection_date=chosen_inspection_date,
        inspector_name=inspector_name,
    )


def create_public_inspection(db: Session, request: InspectionCreateReq) -> PublicInspectionRes:
    inspection = add_inspection(db, new_inspection(request.property_address, request.inspection_date, request.inspector_name))
    db.commit()
    db.refresh(inspection)
    return load_public_inspection_response(db, inspection)


def get_public_inspection(db: Session, raw_inspection_id: str) -> PublicInspectionRes:
    return load_public_inspection_response(db, find_inspection_or_404(db, raw_inspection_id))


def update_public_inspection_start_info(db: Session, raw_inspection_id: str, request: InspectionStartInfoUpdateReq) -> PublicInspectionRes:
    inspection = find_inspection_or_404(db, raw_inspection_id)
    sent_fields = request.model_fields_set
    if "property_address" in sent_fields:
        if request.property_address is None:
            raise HTTPException(status_code=422, detail="property_address cannot be empty")
        inspection.property_address = request.property_address
    if "inspection_date" in sent_fields:
        if request.inspection_date is None:
            raise HTTPException(status_code=422, detail="inspection_date cannot be empty")
        check_inspection_date_is_reasonable(request.inspection_date)
        inspection.inspection_date = request.inspection_date
    if "inspector_name" in sent_fields:
        inspection.inspector_name = request.inspector_name
    db.commit()
    db.refresh(inspection)
    return load_public_inspection_response(db, inspection)


def _apply_item_update(item: PropertyInspectionItem, request: InspectionItemUpdateReq, cleaned_field_value_changes: dict) -> None:
    if request.item_status is not None:
        item.item_status = request.item_status
    if request.item_notes is not None:
        item.item_notes = request.item_notes or None
    if cleaned_field_value_changes:
        merged_field_values = dict(item.item_field_values or {})
        for field_key, value in cleaned_field_value_changes.items():
            if value is None:
                merged_field_values.pop(field_key, None)
            else:
                merged_field_values[field_key] = value
        item.item_field_values = merged_field_values


def update_public_inspection_item(db: Session, raw_inspection_id: str, item_key: str, request: InspectionItemUpdateReq) -> InspectionItemRes:
    inspection = find_inspection_or_404(db, raw_inspection_id)
    checklist_item = find_checklist_item_or_404(item_key)
    try:
        cleaned_field_value_changes = validate_item_field_value_changes(checklist_item, request.item_field_values or {})
    except InspectionFieldValueInvalid as invalid:
        raise HTTPException(status_code=422, detail=str(invalid))

    item = get_item_of_inspection_for_update(db, inspection.id, item_key)
    if item is None:
        item = PropertyInspectionItem(
            inspection_id=inspection.id, item_key=item_key, item_status=ITEM_STATUS_NOT_CHECKED, item_field_values={}
        )
        db.add(item)
        try:
            db.flush()
        except IntegrityError:
            # The other device created the row a moment ago: merge into theirs.
            db.rollback()
            item = get_item_of_inspection_for_update(db, inspection.id, item_key)
    _apply_item_update(item, request, cleaned_field_value_changes)
    inspection.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return inspection_item_response(item)


def complete_public_inspection(
    db: Session, raw_inspection_id: str, request: InspectionCompleteReq
) -> tuple[PublicInspectionRes, Optional[UUID]]:
    """Finishes the inspection and records its report. Returns the response and the
    report to deliver after the commit (none once today's report cap is reached)."""

    inspection = find_inspection_or_404(db, raw_inspection_id)
    items = get_items_of_inspection(db, inspection.id)
    missing_critical_item_keys = critical_item_keys_not_checked(items)
    if missing_critical_item_keys and not request.completion_override_reason:
        missing_labels = [find_inspection_checklist_item(item_key)["label"] for item_key in missing_critical_item_keys]
        raise HTTPException(
            status_code=409,
            detail={
                "code": "critical_items_unchecked",
                "message": "Check every CRITICAL item first, or give a reason to finish anyway: " + ", ".join(missing_labels),
                "critical_item_keys_not_checked": missing_critical_item_keys,
            },
        )
    inspection.inspection_status = INSPECTION_STATUS_COMPLETED
    inspection.completed_at = datetime.now(timezone.utc)
    inspection.completion_override_reason = request.completion_override_reason if missing_critical_item_keys else None
    db.flush()
    report = None
    if count_reports_of_inspection_today(db, inspection.id) < MAXIMUM_REPORTS_PER_INSPECTION_PER_DAY:
        report = record_inspection_report(db, inspection)
    db.commit()
    db.refresh(inspection)
    return load_public_inspection_response(db, inspection), (report.id if report else None)
