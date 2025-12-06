from datetime import datetime
from typing import List, Optional, Annotated

from pydantic import BaseModel, ConfigDict, Field

from ReqRes.analyzeDeal.analyzeDealRes import analyzeDealRes


class SoldComp(BaseModel):
    url: Optional[str] = None
    arv: Optional[float] = None
    how_long_ago: Optional[str] = None


class RentComp(BaseModel):
    url: Optional[str] = None
    rent: Optional[float] = None
    time_on_market: Optional[str] = None


class ActiveDealBase(BaseModel):
    arv_in_thousands: Optional[float] = Field(0, description="After repair value (ARV) of the property in thousands")
    
    purchase_price_in_thousands: Annotated[Optional[float], Field(alias="purchasePrice", description="Acquisition price for the property")] = None
    
    rehab_cost_in_thousands: Annotated[Optional[float], Field(alias="rehabCost", description="Estimated rehab costs included in the deal")] = 0.0

    down_payment:  Optional[float] = Field(None, description="Down payment percentage for hard money purchase (0-100)")
    
    closing_costs_buy_in_thousands: Annotated[Optional[float], Field(alias="closingCostsBuy", description="Closing costs when purchasing with hard money")] = 0.0

    use_HM_for_rehab: Annotated[Optional[bool], Field(alias="use_HM_for_rehab", description="")] = False # make it a toggle for using hard money for rehab costs
 
    HML_points: Annotated[Optional[float], Field(alias="hmlPoints", description="Hard money lender points (percentage)")] = 0.0

    Months_until_refi: Annotated[Optional[float], Field(alias="monthsUntilRefi", description="num of months from buying to refi")] = None
    
    HML_interest_rate: Annotated[Optional[float], Field(alias="HMLInterestRate", description="Interest paid during HML period (cash)")] = None

    closing_cost_refi_in_thousands: Annotated[Optional[float], Field(alias="closingCostsRefi", description="Closing costs during the refinance stage")] = 0.0
    
    loan_term_years: Annotated[Optional[int], Field(alias="loanTermYears")] = 30

    ltv_as_precent: Optional[float] = Field(..., description="LTV as a percent for the DSCR refinance loan (e.g., 75 for 75%)")

    interest_rate: Annotated[Optional[float], Field(alias="interestRate", description="Annual mortgage interest rate (percent)")] = None
    
    rent: Optional[float] = Field(None, description="Expected monthly rent")
    
    vacancy_percent: Annotated[Optional[float], Field(alias="vacancyPercent", description="Percentage of rent reserved for vacancy")] = 0.0
    
    property_managment_fee_precentages_from_rent: Optional[float] = Field(0.0, description="precentages from the rent from property managment")
    
    maintenance_percent: Annotated[Optional[float], Field(alias="maintenancePercent", description="Maintenance reserve as a percentage of rent")] = 0.0

    capex_percent_of_rent: Annotated[Optional[float], Field(alias="capexPercent", description="Capital expenditures reserve as a percentage of rent")] = 0.0

    annual_property_taxes: Optional[float] = Field(0.0, description="Annual property taxes")
    annual_insurance: Optional[float] = Field(0.0, description="Annual insurance expense")
    montly_hoa: Optional[float] = Field(0.0, description="Monthly HOA dues")
    section: Optional[int] = Field(..., description="Section number for categorizing the deal 1 wholesale, 2 market, 3 our off market")
    stage: Optional[int] = Field(..., description="Stage number for tracking deal progress 1 new, 2 working, 3 brought, 4 to keep in mind, 5 dead")
    address: Optional[str] = Field(..., description="Property address")
    sqft: Optional[float] = Field(None, description="Property square footage")
    bedrooms: Optional[int] = Field(None, description="Number of bedrooms")
    bathrooms: Optional[float] = Field(None, description="Number of bathrooms")
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


class ActiveDealCreate(ActiveDealBase):
    pass


class ActiveDealRes(ActiveDealBase, analyzeDealRes):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
