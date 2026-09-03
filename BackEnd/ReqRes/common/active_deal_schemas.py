from datetime import datetime
from typing import Any, List, Optional, Annotated, Literal
from decimal import Decimal
from uuid import UUID

from pydantic import Field, model_validator

from ReqRes.common.analyze_results import analyzeBRRRRes, analyzeFlipRes
from ReqRes.common.base_deal import BaseDealReq
from ReqRes.common.comps import SoldComp
from ReqRes.common.refi_timing import days_from_legacy_months


class BrrrActiveDealCreate(BaseDealReq):
    deal_type: Literal["BRRRR"] = "BRRRR"

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_months_until_refi(cls, data: Any) -> Any:
        return days_from_legacy_months(data)

    arv_in_thousands: Optional[Decimal] = Field(Decimal("0"), description="ARV in thousands")
    days_until_refi: Annotated[Optional[int], Field(alias="daysUntilRefi")] = 180
    closing_cost_refi_in_thousands: Annotated[Optional[Decimal], Field(alias="closingCostsRefi")] = Decimal("0.0")
    # NOTE: 2 is the default for a *new* deal. Rows saved before this column
    # existed were backfilled to 1.5 by `_add_column_if_missing`, and the
    # frontend's `ensureBrrrLegacyDefaults` always sends their stored value
    # explicitly, so this default can never overwrite one of them.
    refi_points: Annotated[Optional[Decimal], Field(alias="refiPoints")] = Decimal("2")
    cash_reserve_in_thousands: Annotated[Optional[Decimal], Field(alias="cashReserve")] = Decimal("0.0")
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


class BrrrActiveDealRes(BrrrActiveDealCreate, analyzeBRRRRes):
    id: UUID
    created_at: datetime
    updated_at: datetime

class FlipActiveDealRes(FlipActiveDealCreate, analyzeFlipRes):
    id: UUID
    created_at: datetime
    updated_at: datetime
