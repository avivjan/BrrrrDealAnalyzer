"""Builds inspection responses from the stored rows and the checklist config.

`public_inspection_response` is the only shape the public endpoints return.
It is built field by field (never from the ORM object as a whole), so no deal
column can reach a public response: only the boolean `linked`.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable, List, Optional

from BL.inspection.common.inspection_checklist_config import (
    ITEM_STATUS_NOT_CHECKED,
    ITEM_STATUS_OK,
    ITEM_STATUS_REPAIR,
    ITEM_STATUS_REPLACE,
    all_inspection_checklist_items,
    critical_inspection_item_keys,
    visible_field_values,
)
from BL.inspection.common.inspection_deal_links import linked_deal_of_inspection
from DAL.data_models import PropertyInspection, PropertyInspectionItem, PropertyInspectionPhoto
from ReqRes.common.inspection_schemas import (
    InspectionItemRes,
    InspectionListRowRes,
    InspectionPhotoRes,
    InspectionSummaryItemRes,
    InspectionSummaryRes,
    LinkedDealRes,
    PublicInspectionRes,
)

WINDOWS_ITEM_KEY = "windows"
WINDOWS_NEEDING_REPLACEMENT_FIELD_KEY = "windows_needing_replacement_count"


def inspection_is_linked_to_a_deal(inspection: PropertyInspection) -> bool:
    return linked_deal_of_inspection(inspection)[0] is not None


def item_status_by_key(items: Iterable[PropertyInspectionItem]) -> dict:
    return {item.item_key: item.item_status for item in items}


def critical_item_keys_not_checked(items: Iterable[PropertyInspectionItem]) -> List[str]:
    statuses = item_status_by_key(items)
    return [item_key for item_key in critical_inspection_item_keys() if statuses.get(item_key, ITEM_STATUS_NOT_CHECKED) == ITEM_STATUS_NOT_CHECKED]


def build_inspection_summary(items: List[PropertyInspectionItem], photos: List[PropertyInspectionPhoto]) -> InspectionSummaryRes:
    stored_items_by_key = {item.item_key: item for item in items}
    photo_count_by_item_key = Counter(photo.item_key for photo in photos)
    summary_items_by_status: dict = {ITEM_STATUS_OK: [], ITEM_STATUS_REPAIR: [], ITEM_STATUS_REPLACE: []}
    checked_item_count = 0
    windows_needing_replacement_count = 0
    checklist_items = all_inspection_checklist_items()
    for checklist_item in checklist_items:
        stored_item = stored_items_by_key.get(checklist_item["key"])
        if stored_item is None or stored_item.item_status == ITEM_STATUS_NOT_CHECKED:
            continue
        checked_item_count += 1
        current_field_values = visible_field_values(checklist_item, stored_item.item_field_values or {})
        if checklist_item["key"] == WINDOWS_ITEM_KEY:
            windows_needing_replacement_count = int(current_field_values.get(WINDOWS_NEEDING_REPLACEMENT_FIELD_KEY) or 0)
        summary_items_by_status[stored_item.item_status].append(
            InspectionSummaryItemRes(
                item_key=checklist_item["key"],
                item_label=checklist_item["label"],
                item_status=stored_item.item_status,
                item_notes=stored_item.item_notes,
                visible_field_values=current_field_values,
                photo_count=photo_count_by_item_key.get(checklist_item["key"], 0),
            )
        )
    return InspectionSummaryRes(
        checked_item_count=checked_item_count,
        total_item_count=len(checklist_items),
        critical_item_keys_not_checked=critical_item_keys_not_checked(items),
        items_marked_replace=summary_items_by_status[ITEM_STATUS_REPLACE],
        items_marked_repair=summary_items_by_status[ITEM_STATUS_REPAIR],
        items_marked_ok=summary_items_by_status[ITEM_STATUS_OK],
        windows_needing_replacement_count=windows_needing_replacement_count,
        photo_count=len(photos),
    )


def inspection_item_response(item: PropertyInspectionItem) -> InspectionItemRes:
    return InspectionItemRes(
        item_key=item.item_key,
        item_status=item.item_status,
        item_notes=item.item_notes,
        item_field_values=item.item_field_values or {},
        updated_at=item.updated_at,
    )


def public_inspection_response(
    inspection: PropertyInspection,
    items: List[PropertyInspectionItem],
    photos: List[PropertyInspectionPhoto],
    report_delivery_status: Optional[str] = None,
) -> PublicInspectionRes:
    return PublicInspectionRes(
        id=inspection.id,
        property_address=inspection.property_address,
        inspection_date=inspection.inspection_date,
        inspector_name=inspection.inspector_name,
        inspection_status=inspection.inspection_status,
        completed_at=inspection.completed_at,
        completion_override_reason=inspection.completion_override_reason,
        linked=inspection_is_linked_to_a_deal(inspection),
        created_at=inspection.created_at,
        updated_at=inspection.updated_at,
        items=[inspection_item_response(item) for item in items],
        photos=[InspectionPhotoRes(id=photo.id, item_key=photo.item_key, created_at=photo.created_at) for photo in photos],
        summary=build_inspection_summary(items, photos),
        report_delivery_status=report_delivery_status,
    )


def linked_deal_response(inspection: PropertyInspection, linked_deal_address: Optional[str]) -> Optional[LinkedDealRes]:
    kind, deal_id = linked_deal_of_inspection(inspection)
    if kind is None:
        return None
    return LinkedDealRes(deal_id=deal_id, deal_type=kind.deal_type, deal_board=kind.deal_board, property_address=linked_deal_address)


def inspection_list_row_response(
    inspection: PropertyInspection,
    items: List[PropertyInspectionItem],
    photo_count: int,
    linked_deal_address: Optional[str],
) -> InspectionListRowRes:
    statuses = [item.item_status for item in items]
    return InspectionListRowRes(
        id=inspection.id,
        property_address=inspection.property_address,
        inspection_date=inspection.inspection_date,
        inspector_name=inspection.inspector_name,
        inspection_status=inspection.inspection_status,
        completed_at=inspection.completed_at,
        created_at=inspection.created_at,
        updated_at=inspection.updated_at,
        checked_item_count=sum(1 for status in statuses if status != ITEM_STATUS_NOT_CHECKED),
        total_item_count=len(all_inspection_checklist_items()),
        repair_or_replace_item_count=sum(1 for status in statuses if status in (ITEM_STATUS_REPAIR, ITEM_STATUS_REPLACE)),
        photo_count=photo_count,
        linked_deal=linked_deal_response(inspection, linked_deal_address),
    )
