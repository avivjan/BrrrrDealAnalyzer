"""Request model for cash flow calculation inputs."""

from typing import Annotated
from decimal import Decimal
from pydantic import BaseModel, Field


class analyzeDealReq(BaseModel):
    """Captures inputs required to calculate rental cash flow and DSCR."""

    arv_in_thousands: Decimal = Field(..., description="After repair value (ARV) of the property in thousands")
    
    purchase_price_in_thousands: Annotated[Decimal, Field(alias="purchasePrice", description="Acquisition price for the property")]
    
    rehab_cost_in_thousands: Annotated[Decimal, Field(alias="rehabCost", description="Estimated rehab costs included in the deal")] = Decimal("0.0")

    down_payment: Decimal = Field(..., description="Down payment percentage for hard money purchase (0-100)")
    
    closing_costs_buy_in_thousands: Annotated[Decimal, Field(alias="closingCostsBuy", description="Closing costs when purchasing with hard money")] = Decimal("0.0")

    use_HM_for_rehab: Annotated[bool, Field(alias="use_HM_for_rehab", description="")] = False # make it a toggle for using hard money for rehab costs

    HML_points: Annotated[Decimal, Field(alias="hmlPoints", description="Hard money lender points (percentage)")] = Decimal("0.0")

    Months_until_refi: Annotated[Decimal, Field(alias="monthsUntilRefi", description="num of months from buying to refi")]
    
    HML_interest_rate: Annotated[Decimal, Field(alias="HMLInterestRate", description="Interest paid during HML period (cash)")]   

    closing_cost_refi_in_thousands: Annotated[Decimal, Field(alias="closingCostsRefi", description="Closing costs during the refinance stage")] = Decimal("0.0")
    
    loan_term_years: Annotated[int, Field(alias="loanTermYears")] = 30

    ltv_as_precent: Decimal = Field(..., description="LTV as a percent for the DSCR refinance loan (e.g., 75 for 75%)")

    
    interest_rate: Annotated[Decimal, Field(alias="interestRate", description="Annual mortgage interest rate (percent)")]
    
    rent: Decimal = Field(..., description="Expected monthly rent")
    
    vacancy_percent: Annotated[Decimal, Field(alias="vacancyPercent", description="Percentage of rent reserved for vacancy")] = Decimal("0.0")
    
    property_managment_fee_precentages_from_rent: Decimal = Field(Decimal("0.0"), description="precentages from the rent from property managment")
    
    maintenance_percent: Annotated[Decimal, Field(alias="maintenancePercent", description="Maintenance reserve as a percentage of rent")] = Decimal("0.0")

    capex_percent_of_rent: Annotated[Decimal, Field(alias="capexPercent", description="Capital expenditures reserve as a percentage of rent")] = Decimal("0.0")

    annual_property_taxes: Decimal = Field(Decimal("0.0"), description="Annual property taxes")
    annual_insurance: Decimal = Field(Decimal("0.0"), description="Annual insurance expense")
    montly_hoa: Decimal = Field(Decimal("0.0"), description="Monthly HOA dues")
