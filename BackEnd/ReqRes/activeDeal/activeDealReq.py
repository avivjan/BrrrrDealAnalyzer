from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ReqRes.analyzeDeal.analyzeDealReq import analyzeDealReq


class SoldComp(BaseModel):
    url: str
    arv: float
    how_long_ago: str


class RentComp(BaseModel):
    url: str
    rent: float
    time_on_market: str


class ActiveDealBase(BaseModel):
    arv_in_thousands: Optional[float] = Field(0, description="After repair value (ARV) of the property in thousands")
    
    purchase_price_in_thousands: Optional[float] = Field(
        None, alias="purchasePrice", description="Acquisition price for the property"
    )
    
    rehab_cost_in_thousands: Optional[float] = Field(
        0.0,
        alias="rehabCost",
        description="Estimated rehab costs included in the deal",
    )
    down_payment:  Optional[float] = Field(None, description="Down payment percentage for hard money purchase (0-100)")
    closing_costs_buy_in_thousands: Optional[float] = Field(
    0.0, alias="closingCostsBuy", description="Closing costs when purchasing with hard money"
    )
    use_HM_for_rehab: Optional[bool] = Field( #make it a toggle for using hard money for rehab costs
        False, alias="use_HM_for_rehab", description=""
    )   
    HML_points: Optional[float] = Field(
        0.0, alias="hmlPoints", description="Hard money lender points (percentage)"
    )

    Months_until_refi: Optional[float] = Field(
        None, alias="monthsUntilRefi", description="num of months from buying to refi"
    )
    
    HML_interest_rate: Optional[float] = Field(
        None, alias="HMLInterestRate", description="Interest paid during HML period (cash)"
    )   

    closing_cost_refi_in_thousands: Optional[float] = Field(
        0.0, alias="closingCostsRefi", description="Closing costs during the refinance stage"
    )
    
    loan_term_years: Optional[int] = Field(30, alias="loanTermYears")

    ltv_as_precent: Optional[float] = Field(..., description="LTV as a percent for the DSCR refinance loan (e.g., 75 for 75%)")

    interest_rate: Optional[float] = Field(
        None, alias="interestRate", description="Annual mortgage interest rate (percent)"
    )
    
    rent: Optional[float] = Field(None, description="Expected monthly rent")
    
    vacancy_percent: Optional[float] = Field(
        0.0,
        alias="vacancyPercent",
        description="Percentage of rent reserved for vacancy",
    )
    
    property_managment_fee_precentages_from_rent: Optional[float] = Field(0.0, description="precentages from the rent from property managment")
    maintenance_percent: Optional[float] = Field(
        0.0,
        alias="maintenancePercent",
        description="Maintenance reserve as a percentage of rent",
    )
    capex_percent_of_rent: Optional[float] = Field(
        0.0,
        alias="capexPercent",
        description="Capital expenditures reserve as a percentage of rent",
    )
    annual_property_taxes: Optional[float] = Field(0.0, description="Annual property taxes")
    annual_insurance: Optional[float] = Field(0.0, description="Annual insurance expense")
    montly_hoa: Optional[float] = Field(0.0, description="Monthly HOA dues")
    section: Optional[int] = Field(..., description="Section number for categorizing the deal 1 wholesale, 2 market, 3 our off market")
    stage: Optional[int] = Field(..., description="Stage number for tracking deal progress 1 new, 2 working, 3 brought, 4 to keep in mind, 5 dead")
    address: Optional[str] = Field(..., description="Property address")
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
