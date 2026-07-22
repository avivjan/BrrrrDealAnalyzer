from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class WaterfallRunRequest(BaseModel):
    property_id: str
    rent_received: Decimal
    checking_balance: Decimal = Decimal("0")
    pi_amount: Decimal = Decimal("0")
    uncollected_reserve_targets: Decimal = Decimal("0")


class MissedRentCheckRequest(BaseModel):
    property_id: str
    pi_amount: Decimal
    notify_email: str = "operator@example.com"
    # Optional override for deterministic testing / backfills.
    as_of: Optional[str] = None


class OverflowDecisionRequest(BaseModel):
    property_id: str
    amount: Decimal
    choice: str = Field(..., description="A=Spillover, B=Cross-Allocate, C=Break Cap")
    target_property_id: Optional[str] = None
