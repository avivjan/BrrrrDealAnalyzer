from pydantic import BaseModel, Field


class CalcPrecentageOfARVReq(BaseModel):
    arv: float = Field(..., description="After repair value (ARV)")
    purchase_price: float = Field(..., description="Purchase price of the property")

    # Whether transfer taxes apply. If True, 0.7% of purchase price is added in `main.py`.
    is_transfer_taxes: bool = Field(
        False,
        description="Whether transfer taxes (doc stamps) apply; if true, 0.7% of purchase price is added",
    )

    title_fees: float = Field(1200.0, description="Title fees")
    title_insurance: float = Field(1200.0, description="Title insurance")
    recording_fees: float = Field(150.0, description="Recording fees")
    lender_underwriting_fees: float = Field(600.0, description="Lender underwriting fees")
    inspection_costs: float = Field(400.0, description="Inspection costs")

    origination_points_percent: float = Field(
        3.0, description="Origination points as a percent of purchase price"
    )

    hml_underwriting_fee: float = Field(0.0, description="HML underwriting fee (currently unused)")
    hml_processing_fee: float = Field(0.0, description="HML processing fee (currently unused)")
    hml_appraisal_fee: float = Field(500.0, description="Hard money lender appraisal fee")
    draw_setup_fee: float = Field(350.0, description="Draw setup fee")

    rehab_cost: float = Field(0.0, description="Estimated rehab costs")
    rehab_utilities_cost: float = Field(
        1000.0,
        description="Utilities and holding costs during rehab",
    )
    builders_risk_insurance_cost: float = Field(
        0.0, description="Builder's risk insurance cost (currently unused)"
    )
