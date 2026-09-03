from datetime import datetime
from typing import Optional, Annotated, Literal, Dict
from uuid import UUID

from pydantic import Field

from ReqRes.common.active_deal_schemas import BrrrActiveDealCreate, FlipActiveDealCreate
from ReqRes.common.analyze_results import analyzeBRRRRes, analyzeFlipRes


class BoughtBrrrDealCreate(BrrrActiveDealCreate):
    deal_type: Literal["BRRRR"] = "BRRRR"
    # Stable string ID from the pipeline_templates table (slug for defaults,
    # `stage_<uuid>` for user-added stages). Defaults to the first default stage.
    bought_stage: Annotated[Optional[str], Field(alias="boughtStage")] = "purchase"
    completed_substages: Annotated[Optional[Dict[str, bool]], Field(alias="completedSubstages")] = {}
    source_deal_id: Annotated[Optional[UUID], Field(alias="sourceDealId")] = None


class BoughtFlipDealCreate(FlipActiveDealCreate):
    deal_type: Literal["FLIP"] = "FLIP"
    bought_stage: Annotated[Optional[str], Field(alias="boughtStage")] = "purchase"
    completed_substages: Annotated[Optional[Dict[str, bool]], Field(alias="completedSubstages")] = {}
    source_deal_id: Annotated[Optional[UUID], Field(alias="sourceDealId")] = None


class BoughtBrrrDealRes(BoughtBrrrDealCreate, analyzeBRRRRes):
    id: UUID
    created_at: datetime
    updated_at: datetime


class BoughtFlipDealRes(BoughtFlipDealCreate, analyzeFlipRes):
    id: UUID
    created_at: datetime
    updated_at: datetime
