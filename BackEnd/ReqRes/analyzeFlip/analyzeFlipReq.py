from typing import Annotated, Optional
from decimal import Decimal
from pydantic import BaseModel, Field

class analyzeFlipReq(BaseModel):
    """Captures inputs required to calculate Flip deal metrics."""

    purchase_price_in_thousands: Annotated[Decimal, Field(alias="purchasePrice", description="Acquisition price for the property")]
    
    rehab_cost_in_thousands: Annotated[Decimal, Field(alias="rehabCost", description="Estimated rehab costs included in the deal")] = Decimal("0.0")
    
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

