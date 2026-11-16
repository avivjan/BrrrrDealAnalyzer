from datetime import datetime
from typing import Optional, Annotated, Literal, Dict
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from ReqRes.common.active_deal_schemas import BrrrActiveDealCreate, FlipActiveDealCreate
from ReqRes.common.analyze_results import analyzeBRRRRes, analyzeFlipRes


MAX_SUBSTAGE_KEYS = 500


def _bounded_substages(value: Optional[Dict[str, bool]]) -> Optional[Dict[str, bool]]:
    if value is not None and len(value) > MAX_SUBSTAGE_KEYS:
        raise ValueError(f"completedSubstages may hold at most {MAX_SUBSTAGE_KEYS} entries")
    return value


class BoughtBrrrDealCreate(BrrrActiveDealCreate):
    deal_type: Literal["BRRRR"] = "BRRRR"
    # Stable string ID from the pipeline_templates table (slug for defaults,
    # `stage_<uuid>` for user-added stages). Defaults to the first default stage.
    bought_stage: Annotated[Optional[str], Field(alias="boughtStage", max_length=200)] = "purchase"
    completed_substages: Annotated[Optional[Dict[str, bool]], Field(alias="completedSubstages")] = {}
    source_deal_id: Annotated[Optional[UUID], Field(alias="sourceDealId")] = None

    _substages_bounded = field_validator("completed_substages")(_bounded_substages)


class BoughtFlipDealCreate(FlipActiveDealCreate):
    deal_type: Literal["FLIP"] = "FLIP"
    bought_stage: Annotated[Optional[str], Field(alias="boughtStage", max_length=200)] = "purchase"
    completed_substages: Annotated[Optional[Dict[str, bool]], Field(alias="completedSubstages")] = {}
    source_deal_id: Annotated[Optional[UUID], Field(alias="sourceDealId")] = None

    _substages_bounded = field_validator("completed_substages")(_bounded_substages)


class BoughtBrrrDealRes(BoughtBrrrDealCreate, analyzeBRRRRes):
    id: UUID
    created_at: datetime
    updated_at: datetime


class BoughtFlipDealRes(BoughtFlipDealCreate, analyzeFlipRes):
    id: UUID
    created_at: datetime
    updated_at: datetime


class MoveToBoughtReq(BaseModel):
    """Every Bought deal has its own Google Drive folder (tasks/todo/DealDriveFolderRehabSummaryAndProjection.md)."""
    google_drive_link: Optional[str] = Field(
        None, max_length=2000,
        description="The deal's Google Drive folder link (https://drive.google.com/drive/folders/...). Left out: the My Deals "
                    "deal's own link is used. Required one way or the other: the rehab summary and HTML to Drive save there.")


class DealProjectionSavedToDriveRes(BaseModel):
    """HTML to Drive: the deal's interactive HTML report saved in its Google Drive folder."""
    file_name: str = Field(..., description='The saved file: "<YYYY-MM-DD> deal projection.html".')
    drive_file_id: str = Field(..., description="The file's id in Google Drive.")
    drive_folder_url: str = Field(..., description="The deal's Google Drive folder (where the file is).")
