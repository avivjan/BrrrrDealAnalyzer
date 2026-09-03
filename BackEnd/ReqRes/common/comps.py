from typing import Optional
from decimal import Decimal

from pydantic import BaseModel


class SoldComp(BaseModel):
    url: Optional[str] = None
    arv: Optional[Decimal] = None
    how_long_ago: Optional[str] = None


class RentComp(BaseModel):
    url: Optional[str] = None
    rent: Optional[Decimal] = None
    time_on_market: Optional[str] = None
