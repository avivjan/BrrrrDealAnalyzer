"""Request models for the /analyze/brrr and /analyze/flip calculation inputs."""

from typing import Annotated, Any
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ReqRes.common.refi_timing import days_from_legacy_months
from ReqRes.common.brrr_legacy_inputs import construction_budget_from_legacy_hm_flag
from ReqRes.common.brrr_lifecycle_inputs import BrrrLifecycleInputs


class analyzeBRRRReq(BrrrLifecycleInputs):
    """Captures inputs required to calculate rental cash flow and DSCR.

    The lifecycle inputs (dates, granular closing costs, construction budget, holding
    items, reserves, lowest ARV) come from `BrrrLifecycleInputs`.

    Accepts each field by its alias (`purchasePrice`) or its name (`purchase_price_in_thousands`),
    like the saved-deal models: a body copied from a saved deal must never have a field silently
    dropped and replaced by its default.
    """

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_months_until_refi(cls, data: Any) -> Any:
        return days_from_legacy_months(data)

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_hm_for_rehab_flag(cls, data: Any) -> Any:
        return construction_budget_from_legacy_hm_flag(data)

    arv_in_thousands: Decimal = Field(..., description="After repair value (ARV) of the property in thousands")

    purchase_price_in_thousands: Annotated[Decimal, Field(alias="purchasePrice", description="Acquisition price for the property")]

    rehab_cost_in_thousands: Annotated[Decimal, Field(alias="rehabCost", description="Actual rehab cost (contractor and materials), in thousands")] = Decimal("0.0")

    rehab_contingency_percent: Annotated[Decimal, Field(alias="rehabContingency", description="Contingency budget as a percentage of rehab cost")] = Decimal("0.0")

    down_payment: Decimal = Field(..., description="Down payment percentage for hard money purchase (0-100)")

    closing_costs_buy_in_thousands: Annotated[Decimal, Field(alias="closingCostsBuy", description="Deprecated for BRRRR (ignored): replaced by the granular buy closing-cost fields")] = Decimal("0.0")

    use_HM_for_rehab: Annotated[bool, Field(alias="use_HM_for_rehab", description="Deprecated for BRRRR (ignored): replaced by constructionLoanBudget")] = False

    HML_points: Annotated[Decimal, Field(alias="hmlPoints", description="Hard money lender points (percentage)")] = Decimal("0.0")

    days_until_refi: Annotated[int, Field(alias="daysUntilRefi", description="whole days from purchase close to refi close")] = 180

    HML_interest_rate: Annotated[Decimal, Field(alias="HMLInterestRate", description="Interest paid during HML period (cash)")]

    closing_cost_refi_in_thousands: Annotated[Decimal, Field(alias="closingCostsRefi", description="Deprecated for BRRRR (ignored): replaced by the granular refi closing-cost fields")] = Decimal("0.0")

    refi_points: Annotated[Decimal, Field(alias="refiPoints", description="Broker points at refi as a percentage of the refi loan amount")] = Decimal("2")

    cash_reserve_in_thousands: Annotated[Decimal, Field(alias="cashReserve", description="Deprecated for BRRRR (ignored): replaced by maintenanceReserve, vacancyReserve and capexReserve")] = Decimal("0.0")

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


class analyzeFlipReq(BaseModel):
    """Captures inputs required to calculate Flip deal metrics. Accepts aliases and field names alike."""

    model_config = ConfigDict(populate_by_name=True)

    purchase_price_in_thousands: Annotated[Decimal, Field(alias="purchasePrice", description="Acquisition price for the property")]

    rehab_cost_in_thousands: Annotated[Decimal, Field(alias="rehabCost", description="Estimated rehab costs included in the deal")] = Decimal("0.0")

    rehab_contingency_percent: Annotated[Decimal, Field(alias="rehabContingency", description="Contingency budget as a percentage of rehab cost")] = Decimal("0.0")

    # Flip specific
    sale_price_in_thousands: Annotated[Decimal, Field(alias="salePrice", description="Projected Sale Price (ARV)")]

    # Hard Money / Lending
    down_payment: Decimal = Field(..., description="Down payment percentage for purchase (0-100)")
    closing_costs_buy_in_thousands: Annotated[Decimal, Field(alias="closingCostsBuy", description="Closing costs when purchasing")] = Decimal("0.0")

    use_HM_for_rehab: Annotated[bool, Field(alias="use_HM_for_rehab", description="")] = False
    HML_points: Annotated[Decimal, Field(alias="hmlPoints", description="Hard money lender points (percentage)")] = Decimal("0.0")
    HML_interest_rate: Annotated[Decimal, Field(alias="HMLInterestRate", description="Interest paid during HML period (cash)")]

    # Timing
    holding_time_months: Annotated[int, Field(alias="holdingTime", description="Months until sale")]

    # Selling Costs
    buyer_agent_selling_fee: Annotated[Decimal, Field(alias="buyerAgentSellingFee", description="Buyer agent commission percentage")] = Decimal("0.0")
    seller_agent_selling_fee: Annotated[Decimal, Field(alias="sellerAgentSellingFee", description="Seller agent commission percentage")] = Decimal("0.0")
    selling_closing_costs_in_thousands: Annotated[Decimal, Field(alias="sellingClosingCosts", description="Other closing costs in thousands")] = Decimal("0.0")

    # Operating Costs during holding
    annual_property_taxes: Decimal = Field(Decimal("0.0"), description="Annual property taxes")
    annual_insurance: Decimal = Field(Decimal("0.0"), description="Annual insurance expense")
    montly_hoa: Decimal = Field(Decimal("0.0"), description="Monthly HOA dues")
    monthly_utilities: Decimal = Field(Decimal("0.0"), description="Estimated monthly utilities")

    capital_gains_tax_rate: Annotated[Decimal, Field(alias="capitalGainsTax", description="Capital Gains Tax Rate")] = Decimal("0.0")
