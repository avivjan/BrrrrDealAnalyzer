from datetime import datetime
from typing import List, Optional, Annotated, Literal
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ReqRes.analyzeBRRR.analyzeBRRRRes import analyzeBRRRRes
from ReqRes.analyzeFlip.analyzeFlipRes import analyzeFlipRes


class SoldComp(BaseModel):
    url: Optional[str] = None
    arv: Optional[Decimal] = None
    how_long_ago: Optional[str] = None


class RentComp(BaseModel):
    url: Optional[str] = None
    rent: Optional[Decimal] = None
    time_on_market: Optional[str] = None


class BaseDealReq(BaseModel):
    # Shared Fields
    purchase_price_in_thousands: Annotated[Optional[Decimal], Field(alias="purchasePrice", description="Acquisition price for the property")] = None
    rehab_cost_in_thousands: Annotated[Optional[Decimal], Field(alias="rehabCost", description="Estimated rehab costs included in the deal")] = Decimal("0.0")
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
    address: Optional[str] = Field(..., description="Property address")
    sqft: Optional[Decimal] = Field(None, description="Property square footage")
    bedrooms: Optional[int] = Field(None, description="Number of bedrooms")
    bathrooms: Optional[Decimal] = Field(None, description="Number of bathrooms")
    zillow_link: Optional[str] = None
    overall_design: Optional[str] = None
    crime_rate: Optional[str] = None
    pics_link: Optional[str] = None
    contact: Optional[str] = None
    task: Optional[str] = None
    niche: Optional[str] = None
    sold_comps: Optional[List[SoldComp]] = None
    rent_comps: Optional[List[RentComp]] = None 
    notes: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class BrrrActiveDealCreate(BaseDealReq):
    deal_type: Literal["BRRRR"] = "BRRRR"
    arv_in_thousands: Optional[Decimal] = Field(Decimal("0"), description="ARV in thousands")
    Months_until_refi: Annotated[Optional[Decimal], Field(alias="monthsUntilRefi")] = None
    closing_cost_refi_in_thousands: Annotated[Optional[Decimal], Field(alias="closingCostsRefi")] = Decimal("0.0")
    loan_term_years: Annotated[Optional[int], Field(alias="loanTermYears")] = 30
    ltv_as_precent: Optional[Decimal] = Field(..., description="LTV for Refi")
    interest_rate: Annotated[Optional[Decimal], Field(alias="interestRate")] = None
    rent: Optional[Decimal] = Field(None, description="Expected monthly rent")
    vacancy_percent: Annotated[Optional[Decimal], Field(alias="vacancyPercent")] = Decimal("0.0")
    property_managment_fee_precentages_from_rent: Optional[Decimal] = Field(Decimal("0.0"))
    maintenance_percent: Annotated[Optional[Decimal], Field(alias="maintenancePercent")] = Decimal("0.0")
    capex_percent_of_rent: Annotated[Optional[Decimal], Field(alias="capexPercent")] = Decimal("0.0")


class FlipActiveDealCreate(BaseDealReq):
    deal_type: Literal["FLIP"] = "FLIP"
    sale_price_in_thousands: Annotated[Decimal, Field(alias="salePrice")]
    holding_time_months: Annotated[int, Field(alias="holdingTime")]
    
    buyer_agent_selling_fee: Annotated[Decimal, Field(alias="buyerAgentSellingFee")] = Decimal("0.0")
    seller_agent_selling_fee: Annotated[Decimal, Field(alias="sellerAgentSellingFee")] = Decimal("0.0")
    selling_closing_costs_in_thousands: Annotated[Decimal, Field(alias="sellingClosingCosts")] = Decimal("0.0")

    monthly_utilities: Decimal = Field(Decimal("0.0"))
    capital_gains_tax_rate: Annotated[Decimal, Field(alias="capitalGainsTax")] = Decimal("0.0")
    sale_comps: Optional[List[SoldComp]] = None


from uuid import UUID

class BrrrActiveDealRes(BrrrActiveDealCreate, analyzeBRRRRes):
    id: UUID
    created_at: datetime
    updated_at: datetime

class FlipActiveDealRes(FlipActiveDealCreate, analyzeFlipRes):
    id: UUID
    created_at: datetime
    updated_at: datetime
