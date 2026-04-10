from datetime import datetime
from typing import Optional, Annotated, Literal, Dict
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from ReqRes.activeDeal.activeDealReq import BrrrActiveDealCreate, FlipActiveDealCreate
from ReqRes.analyzeBRRR.analyzeBRRRRes import analyzeBRRRRes
from ReqRes.analyzeFlip.analyzeFlipRes import analyzeFlipRes


class BoughtBrrrDealCreate(BrrrActiveDealCreate):
    deal_type: Literal["BRRRR"] = "BRRRR"
    bought_stage: Annotated[Optional[int], Field(alias="boughtStage")] = 1
    completed_substages: Annotated[Optional[Dict[str, bool]], Field(alias="completedSubstages")] = {}
    source_deal_id: Annotated[Optional[UUID], Field(alias="sourceDealId")] = None


class BoughtFlipDealCreate(FlipActiveDealCreate):
    deal_type: Literal["FLIP"] = "FLIP"
    bought_stage: Annotated[Optional[int], Field(alias="boughtStage")] = 1
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
