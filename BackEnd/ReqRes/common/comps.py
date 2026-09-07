from typing import Optional
from decimal import Decimal

from pydantic import BaseModel, Field


class SoldComp(BaseModel):
    url: Optional[str] = Field(None, max_length=2_000)
    arv: Optional[Decimal] = None
    how_long_ago: Optional[str] = Field(None, max_length=200)


class RentComp(BaseModel):
    url: Optional[str] = Field(None, max_length=2_000)
    rent: Optional[Decimal] = None
    time_on_market: Optional[str] = Field(None, max_length=200)
