"""Request model for cash flow calculation inputs."""

from pydantic import BaseModel, Field


class CalcCashFlowReq(BaseModel):
    """Captures inputs required to calculate rental cash flow and DSCR."""

    arv: float = Field(..., description="After repair value (ARV) of the property")
    purchase_price: float = Field(
        ..., alias="purchasePrice", description="Acquisition price for the property"
    )
    rehab_cost: float = Field(
        0.0,
        alias="rehabCost",
        description="Estimated rehab costs included in the deal",
    )
    down_payment: float = Field(..., description="Down payment percentage for hard money purchase (0-100)")
    closing_costs_buy: float = Field(
    0.0, alias="closingCostsBuy", description="Closing costs when purchasing with hard money"
    )
    HML_points: float = Field(
        0.0, alias="hmlPoints", description="Hard money lender points (percentage)"
    )

    HML_interest_in_cash: float = Field(
        0.0, alias="hmlInterestInCash", description="Interest paid during HML period (cash)"
    )

    closing_cost_refi: float = Field(
        0.0, alias="closingCostsRefi", description="Closing costs during the refinance stage"
    )

    ltv: float = Field(..., description="LTV ratio for the DSCR refinance loan (e.g., 0.75)")

    loan_term_years: int = Field(30, alias="loanTermYears")
    
    rent: float = Field(..., description="Expected monthly rent")
    interest_rate: float = Field(
        ..., alias="interestRate", description="Annual mortgage interest rate (percent)"
    )
    vacancy_percent: float = Field(
        0.0,
        alias="vacancyPercent",
        description="Percentage of rent reserved for vacancy",
    )

    taxes: float = Field(0.0, description="Annual property taxes")
    insurance: float = Field(0.0, description="Annual insurance expense")
    hoa: float = Field(0.0, description="Monthly HOA dues")
    property_managment_fee_precentages_from_rent: float = Field(0.0, description="precentages from the rent from property managment")
    maintenance_percent: float = Field(
        0.0,
        alias="maintenancePercent",
        description="Maintenance reserve as a percentage of rent",
    )
    capex_percent: float = Field(
        0.0,
        alias="capexPercent",
        description="Capital expenditures reserve as a percentage of rent",
    )

