from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class LLCConfigurationCreate(BaseModel):
    llc_id: Optional[str] = Field(
        None,
        description="Optional human-friendly id; generated when omitted.",
    )
    llc_name: str = Field(..., min_length=1, max_length=200)
    checking_redline_buffer: Decimal = Field(default=Decimal("1000.00"))


class LLCConfigurationUpdate(BaseModel):
    llc_name: Optional[str] = Field(None, min_length=1, max_length=200)
    checking_redline_buffer: Optional[Decimal] = None


class LLCConfigurationRes(BaseModel):
    llc_id: str
    llc_name: str
    checking_redline_buffer: Decimal
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}
