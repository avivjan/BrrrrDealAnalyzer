from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from ReqRes.analyzeDeal.analyzeDealReq import analyzeDealReq


class SoldComp(BaseModel):
    url: str
    arv: float
    how_long_ago: str


class RentComp(BaseModel):
    url: str
    rent: float
    time_on_market: str


class ActiveDealBase(analyzeDealReq):
    address: str
    status: str
    zillow_link: Optional[str] = None
    overall_design: Optional[str] = None
    crime_rate: Optional[str] = None
    pics_link: Optional[str] = None
    contact: Optional[str] = None
    task: Optional[str] = None
    niche: Optional[str] = None
    ltv_min_when_dscr_1_15: Optional[float] = None
    sold_comps: Optional[List[SoldComp]] = None
    rent_comps: Optional[List[RentComp]] = None
    notes: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ActiveDealCreate(ActiveDealBase):
    pass


class ActiveDealRes(ActiveDealBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
