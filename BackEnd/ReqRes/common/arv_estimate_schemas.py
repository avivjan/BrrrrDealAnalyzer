"""`POST /arv-estimate`: the request, and the template Claude fills in.

`ArvEstimateRes` is the response model and also the JSON schema of the
`submit_arv_estimate` tool Claude must call with its answer
(BL/arvEstimate/common/anthropic_arv_client.py). Every field name says what it
holds so the model, the UI and a reader of the JSON never need a legend.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


def _single_line(value: str) -> str:
    if "\r" in value or "\n" in value:
        raise ValueError("must be a single line")
    return value


class ArvEstimateReq(BaseModel):
    deal_type: Literal["BRRRR", "FLIP"]
    property_address: str = Field(..., min_length=3, max_length=300)
    investor_situation_note: str = Field("", max_length=2000)
    subject_square_feet: Optional[float] = Field(None, ge=0, le=100_000)
    subject_bedrooms: Optional[float] = Field(None, ge=0, le=50)
    subject_bathrooms: Optional[float] = Field(None, ge=0, le=50)
    purchase_price: Optional[float] = Field(None, ge=0, le=100_000_000)
    rehab_budget: Optional[float] = Field(None, ge=0, le=100_000_000)

    @field_validator("property_address")
    @classmethod
    def _address_is_one_trimmed_line(cls, value: str) -> str:
        value = _single_line(value).strip()
        if len(value) < 3:
            raise ValueError("must be at least 3 characters")
        return value


class ArvComparableProperty(BaseModel):
    address: str
    distance_from_subject_in_miles: Optional[float] = None
    listing_status: Literal["SOLD", "ACTIVE", "PENDING"]
    sale_or_list_date: Optional[str] = Field(None, description="ISO date (YYYY-MM-DD) of the sale, or of the listing for active/pending.")
    sale_or_list_price: Optional[float] = None
    bedrooms: Optional[float] = None
    bathrooms: Optional[float] = None
    square_feet: Optional[float] = None
    year_built: Optional[int] = None
    lot_size_square_feet: Optional[float] = None
    price_per_square_foot: Optional[float] = None
    days_on_market: Optional[int] = None
    renovation_condition: str = Field(..., description="e.g. 'Flip-grade renovated', 'Turn-key', 'Partially updated'.")
    adjusted_value_for_subject: Optional[float] = Field(None, description="This comp's price after bed/bath/size/lot adjustments to match the subject.")
    adjustment_explanation: str = ""
    weight_in_valuation: Literal["PRIMARY", "SUPPORTING", "EXCLUDED"]
    source_url: Optional[str] = None


class ArvDiscardedComparable(BaseModel):
    address: str
    reason_for_discarding: str


class ArvSubjectPropertyAsFound(BaseModel):
    bedrooms: Optional[float] = None
    bathrooms: Optional[float] = None
    square_feet: Optional[float] = None
    year_built: Optional[int] = None
    lot_size_square_feet: Optional[float] = None
    property_style: Optional[str] = None


class ArvEstimateRes(BaseModel):
    estimated_arv_range_low: float = Field(..., gt=0)
    estimated_arv_range_high: float = Field(..., gt=0)
    target_arv: float = Field(..., gt=0, description="The single most likely ARV for this strategy, in dollars.")
    conservative_lowest_arv: float = Field(..., gt=0, description="A stress-test ARV the investor should still survive, in dollars.")
    confidence_score_1_to_10: int = Field(..., ge=1, le=10)
    average_days_on_market_of_sold_comparables: Optional[float] = None
    median_days_on_market_of_sold_comparables: Optional[float] = None
    market_pace_verdict: Literal["FAST", "NORMAL", "SLOW", "UNKNOWN"]
    market_logic: str = Field(..., description="Why this value: which comps carried it and how they were adjusted.")
    subject_property_as_found: ArvSubjectPropertyAsFound
    sold_comparables: list[ArvComparableProperty]
    active_or_pending_comparables: list[ArvComparableProperty]
    discarded_comparables: list[ArvDiscardedComparable] = []
    data_caveats: list[str] = []
    source_urls: list[str] = []


class ArvEstimateJobRes(BaseModel):
    """An estimate runs as a background job (a real one takes minutes, longer than
    Netlify's proxy waits): `POST /arv-estimate` starts it, `GET
    /arv-estimate/{arv_estimate_job_id}` is polled until it is not RUNNING."""

    arv_estimate_job_id: str
    status: Literal["RUNNING", "SUCCEEDED", "FAILED"]
    arv_estimate: Optional[ArvEstimateRes] = None
    failure_message: Optional[str] = None
