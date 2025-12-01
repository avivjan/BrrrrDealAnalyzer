"""Request model for cash flow calculation inputs."""

from pydantic import BaseModel, Field


class analyzeDealReq(BaseModel):
    """Captures inputs required to calculate rental cash flow and DSCR."""

    arv_in_thousands: float = Field(..., description="After repair value (ARV) of the property in thousands")
    
    purchase_price_in_thousands: float = Field(
        ..., alias="purchasePrice", description="Acquisition price for the property"
    )
    
    rehab_cost_in_thousands: float = Field(
        0.0,
        alias="rehabCost",
        description="Estimated rehab costs included in the deal",
    )
    down_payment: float = Field(..., description="Down payment percentage for hard money purchase (0-100)")
    closing_costs_buy: float = Field(
    0.0, alias="closingCostsBuy", description="Closing costs when purchasing with hard money"
    )
    use_HM_for_rehab: bool = Field( #make it a toggle for using hard money for rehab costs
        False, alias="use_HM_for_rehab", description=""
    )
    HML_points: float = Field(
        0.0, alias="hmlPoints", description="Hard money lender points (percentage)"
    )

    Months_until_refi: float = Field(
        ..., alias="hmlInterestInCash", description="num of months from buying to refi"
    )
    
    HML_interest_rate: float = Field(
        ..., alias="hmlInterestInCash", description="Interest paid during HML period (cash)"
    )

    closing_cost_refi_in_thousands: float = Field(
        0.0, alias="closingCostsRefi", description="Closing costs during the refinance stage"
    )
    
    loan_term_years: int = Field(30, alias="loanTermYears")

    ltv_as_precent: float = Field(..., description="LTV as a percent for the DSCR refinance loan (e.g., 75 for 75%)")

    
    interest_rate: float = Field(
        ..., alias="interestRate", description="Annual mortgage interest rate (percent)"
    )
    
    rent: float = Field(..., description="Expected monthly rent")
    
    vacancy_percent: float = Field(
        0.0,
        alias="vacancyPercent",
        description="Percentage of rent reserved for vacancy",
    )
    
    property_managment_fee_precentages_from_rent: float = Field(0.0, description="precentages from the rent from property managment")
    maintenance_percent: float = Field(
        0.0,
        alias="maintenancePercent",
        description="Maintenance reserve as a percentage of rent",
    )
    capex_percent_of_rent: float = Field(
        0.0,
        alias="capexPercent",
        description="Capital expenditures reserve as a percentage of rent",
    )
    annual_property_taxes: float = Field(0.0, description="Annual property taxes")
    annual_insurance: float = Field(0.0, description="Annual insurance expense")
    montly_hoa: float = Field(0.0, description="Monthly HOA dues")

