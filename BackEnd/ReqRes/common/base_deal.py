from typing import List, Optional, Annotated
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ReqRes.common.comps import SoldComp, RentComp

MAX_SHORT_TEXT = 500
MAX_TEXT = 2_000
MAX_URL = 2_000
MAX_NOTES = 20_000
MAX_COMPS = 200


class BaseDealReq(BaseModel):
    # Shared Fields
    purchase_price_in_thousands: Annotated[Optional[Decimal], Field(alias="purchasePrice", description="Acquisition price for the property")] = None
    rehab_cost_in_thousands: Annotated[Optional[Decimal], Field(alias="rehabCost", description="Estimated rehab costs included in the deal")] = Decimal("0.0")
    rehab_contingency_percent: Annotated[Optional[Decimal], Field(alias="rehabContingency", description="Contingency percentage for rehab costs")] = Decimal("0.0")
    down_payment:  Optional[Decimal] = Field(None, description="Down payment percentage (0-100)")
    closing_costs_buy_in_thousands: Annotated[Optional[Decimal], Field(alias="closingCostsBuy", description="Closing costs when purchasing")] = Decimal("0.0")
    use_HM_for_rehab: Annotated[Optional[bool], Field(alias="use_HM_for_rehab", description="")] = False
    HML_points: Annotated[Optional[Decimal], Field(alias="hmlPoints", description="Hard money lender points (percentage)")] = Decimal("0.0")
    HML_interest_rate: Annotated[Optional[Decimal], Field(alias="HMLInterestRate", description="Interest paid during HML period (cash)")] = None
    annual_property_taxes: Optional[Decimal] = Field(Decimal("0.0"), description="Annual property taxes")
    annual_insurance: Optional[Decimal] = Field(Decimal("0.0"), description="Annual insurance expense")
    montly_hoa: Optional[Decimal] = Field(Decimal("0.0"), description="Monthly HOA dues")

    section: Optional[int] = Field(..., description="Section number")
    stage: Optional[int] = Field(..., description="Stage number")
    # Length caps (SECURITY_PLAN.md F-08). Generous on purpose: a saved deal is
    # re-sent whole on every autosave, so a limit must never reject a record
    # that already exists.
    address: Optional[str] = Field(..., description="Property address", max_length=MAX_SHORT_TEXT)
    sqft: Optional[Decimal] = Field(None, description="Property square footage")
    bedrooms: Optional[int] = Field(None, description="Number of bedrooms")
    bathrooms: Optional[Decimal] = Field(None, description="Number of bathrooms")
    zillow_link: Optional[str] = Field(None, max_length=MAX_URL)
    overall_design: Optional[str] = Field(None, max_length=MAX_TEXT)
    crime_rate: Optional[str] = Field(None, max_length=MAX_TEXT)
    pics_link: Optional[str] = Field(None, max_length=MAX_URL)
    contact: Optional[str] = Field(None, max_length=MAX_TEXT)
    task: Optional[str] = Field(None, max_length=MAX_TEXT)
    niche: Optional[str] = Field(None, max_length=MAX_TEXT)
    sold_comps: Optional[List[SoldComp]] = Field(None, max_length=MAX_COMPS)
    rent_comps: Optional[List[RentComp]] = Field(None, max_length=MAX_COMPS)
    notes: Optional[str] = Field(None, max_length=MAX_NOTES)

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
