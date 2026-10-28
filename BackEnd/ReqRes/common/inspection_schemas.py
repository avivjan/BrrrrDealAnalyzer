"""Requests and responses of the property inspection endpoints.

Public responses (`PublicInspectionRes`) never carry deal data: only the
boolean `linked`. Deal details are in the authenticated responses
(`InspectionListRowRes`, `InspectionDealLinkRes`).
"""

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from BL.inspection.common.inspection_checklist_config import strip_control_characters

MINIMUM_PROPERTY_ADDRESS_LENGTH = 3
MAXIMUM_PROPERTY_ADDRESS_LENGTH = 300
MAXIMUM_INSPECTOR_NAME_LENGTH = 120
MAXIMUM_ITEM_NOTES_LENGTH = 4000
MAXIMUM_FIELD_VALUE_CHANGES_PER_REQUEST = 20
MINIMUM_COMPLETION_OVERRIDE_REASON_LENGTH = 10
MAXIMUM_COMPLETION_OVERRIDE_REASON_LENGTH = 500

InspectionItemStatus = Literal["not_checked", "ok", "repair", "replace"]
BoughtDealType = Literal["BRRRR", "FLIP"]
DealBoard = Literal["my_deals", "bought"]


def _clean_single_line_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return " ".join(strip_control_characters(value).split())


def _clean_property_address(value: str) -> str:
    cleaned_address = _clean_single_line_text(value) or ""
    if not MINIMUM_PROPERTY_ADDRESS_LENGTH <= len(cleaned_address) <= MAXIMUM_PROPERTY_ADDRESS_LENGTH:
        raise ValueError(
            f"property_address must be between {MINIMUM_PROPERTY_ADDRESS_LENGTH} and {MAXIMUM_PROPERTY_ADDRESS_LENGTH} characters"
        )
    return cleaned_address


def _clean_inspector_name(value: Optional[str]) -> Optional[str]:
    cleaned_name = _clean_single_line_text(value)
    if cleaned_name is not None and len(cleaned_name) > MAXIMUM_INSPECTOR_NAME_LENGTH:
        raise ValueError(f"inspector_name must be at most {MAXIMUM_INSPECTOR_NAME_LENGTH} characters")
    return cleaned_name or None


class InspectionCreateReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_address: str = Field(..., max_length=MAXIMUM_PROPERTY_ADDRESS_LENGTH * 2)
    inspection_date: Optional[date] = Field(None, description="Defaults to today.")
    inspector_name: Optional[str] = Field(None, max_length=MAXIMUM_INSPECTOR_NAME_LENGTH * 2)

    _property_address_is_clean = field_validator("property_address")(_clean_property_address)
    _inspector_name_is_clean = field_validator("inspector_name")(_clean_inspector_name)


class InspectionForDealCreateReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inspection_date: Optional[date] = Field(None, description="Defaults to today.")
    inspector_name: Optional[str] = Field(None, max_length=MAXIMUM_INSPECTOR_NAME_LENGTH * 2)

    _inspector_name_is_clean = field_validator("inspector_name")(_clean_inspector_name)


class InspectionStartInfoUpdateReq(BaseModel):
    """Only the fields that are sent change."""

    model_config = ConfigDict(extra="forbid")

    property_address: Optional[str] = Field(None, max_length=MAXIMUM_PROPERTY_ADDRESS_LENGTH * 2)
    inspection_date: Optional[date] = None
    inspector_name: Optional[str] = Field(None, max_length=MAXIMUM_INSPECTOR_NAME_LENGTH * 2)

    @field_validator("property_address")
    @classmethod
    def _property_address_is_clean(cls, value: Optional[str]) -> Optional[str]:
        return None if value is None else _clean_property_address(value)

    _inspector_name_is_clean = field_validator("inspector_name")(_clean_inspector_name)


class InspectionItemUpdateReq(BaseModel):
    """A partial update of one item. `item_field_values` is merged key by key into
    what is stored (a `null` value clears that field), so two people filling the
    same inspection never overwrite each other's other answers."""

    model_config = ConfigDict(extra="forbid")

    item_status: Optional[InspectionItemStatus] = None
    item_notes: Optional[str] = Field(None, max_length=MAXIMUM_ITEM_NOTES_LENGTH, description="An empty string clears the notes.")
    item_field_values: Optional[Dict[str, Any]] = Field(None, description="Field key to new value; null clears the field.")

    @field_validator("item_notes")
    @classmethod
    def _item_notes_are_clean(cls, value: Optional[str]) -> Optional[str]:
        return None if value is None else strip_control_characters(value).strip()

    @field_validator("item_field_values")
    @classmethod
    def _field_value_changes_are_bounded(cls, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if value is not None and len(value) > MAXIMUM_FIELD_VALUE_CHANGES_PER_REQUEST:
            raise ValueError(f"at most {MAXIMUM_FIELD_VALUE_CHANGES_PER_REQUEST} field values per request")
        return value


class InspectionCompleteReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completion_override_reason: Optional[str] = Field(
        None,
        max_length=MAXIMUM_COMPLETION_OVERRIDE_REASON_LENGTH,
        description="Required to finish while CRITICAL items are still not checked.",
    )

    @field_validator("completion_override_reason")
    @classmethod
    def _override_reason_is_long_enough(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned_reason = strip_control_characters(value).strip()
        if len(cleaned_reason) < MINIMUM_COMPLETION_OVERRIDE_REASON_LENGTH:
            raise ValueError(f"completion_override_reason must be at least {MINIMUM_COMPLETION_OVERRIDE_REASON_LENGTH} characters")
        return cleaned_reason


class InspectionDealLinkReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deal_id: UUID
    deal_type: BoughtDealType
    deal_board: DealBoard = Field("bought", description="my_deals (the active pipeline) or bought (Bought Deals).")


class InspectionItemRes(BaseModel):
    item_key: str
    item_status: InspectionItemStatus
    item_notes: Optional[str] = None
    item_field_values: Dict[str, Any]
    updated_at: Optional[datetime] = None


class InspectionPhotoRes(BaseModel):
    id: UUID
    item_key: str
    created_at: Optional[datetime] = None


class InspectionSummaryItemRes(BaseModel):
    item_key: str
    item_label: str
    item_status: InspectionItemStatus
    item_notes: Optional[str] = None
    visible_field_values: Dict[str, Any]
    photo_count: int


class InspectionSummaryRes(BaseModel):
    checked_item_count: int
    total_item_count: int
    critical_item_keys_not_checked: List[str]
    items_marked_replace: List[InspectionSummaryItemRes]
    items_marked_repair: List[InspectionSummaryItemRes]
    items_marked_ok: List[InspectionSummaryItemRes]
    windows_needing_replacement_count: int
    photo_count: int


class PublicInspectionRes(BaseModel):
    id: UUID
    property_address: str
    inspection_date: date
    inspector_name: Optional[str] = None
    inspection_status: Literal["draft", "completed"]
    completed_at: Optional[datetime] = None
    completion_override_reason: Optional[str] = None
    linked: bool = Field(..., description="Whether the inspection is linked to a Bought Deal (which one is never public).")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    items: List[InspectionItemRes]
    photos: List[InspectionPhotoRes]
    summary: InspectionSummaryRes
    report_delivery_status: Optional[Literal["sending", "delivered", "will_retry"]] = Field(
        None, description="The report of the last finish: e-mailed and saved to Drive, still sending, or failed and retrying. Null before the first finish."
    )


class LinkedDealRes(BaseModel):
    deal_id: UUID
    deal_type: BoughtDealType
    deal_board: DealBoard
    property_address: Optional[str] = None


class InspectionDealLinkRes(BaseModel):
    linked_deal: Optional[LinkedDealRes] = None


class InspectionListRowRes(BaseModel):
    id: UUID
    property_address: str
    inspection_date: date
    inspector_name: Optional[str] = None
    inspection_status: Literal["draft", "completed"]
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    checked_item_count: int
    total_item_count: int
    repair_or_replace_item_count: int
    photo_count: int
    linked_deal: Optional[LinkedDealRes] = None

