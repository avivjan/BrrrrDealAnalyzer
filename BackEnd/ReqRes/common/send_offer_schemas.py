from pydantic import BaseModel, EmailStr, Field, field_validator
from decimal import Decimal


def _single_line(value: str) -> str:
    """Header-bound fields (`To:`, `Subject:`) must not carry CR/LF."""
    if "\r" in value or "\n" in value:
        raise ValueError("must be a single line")
    return value


class SendOfferReq(BaseModel):
    agent_name: str = Field(..., min_length=1, max_length=200)
    agent_email: EmailStr = Field(..., max_length=254)
    property_address: str = Field(..., min_length=1, max_length=500)
    purchase_price: Decimal
    inspection_period_days: int = Field(..., ge=0, le=365)

    @field_validator("agent_name", "property_address")
    @classmethod
    def _no_newlines(cls, v: str) -> str:
        return _single_line(v)


class SendOfferRes(BaseModel):
    message: str
    success: bool
