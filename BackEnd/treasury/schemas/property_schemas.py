from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class PropertyStatusCreate(BaseModel):
    """Create a property. `property_id` is always server-generated (UUID hex).

    Note: `target_reserve_allocation` is NOT accepted here — it is derived
    from `base_rent_target * precentage_of_rent_to_reserve / 100`. Set the
    percentage instead.
    """

    llc_id: str
    property_name: str = Field(..., min_length=1, max_length=300)
    tax_bucket_balance: Decimal = Decimal("0")
    tax_to_settle: Decimal = Decimal("0")
    reserve_bucket_balance: Decimal = Decimal("0")
    reserve_to_settle: Decimal = Decimal("0")
    reserve_bucket_cap: Decimal = Decimal("0")
    reserve_debt: Decimal = Decimal("0")
    base_rent_target: Decimal = Decimal("0")
    target_tax_allocation: Decimal = Decimal("0")
    precentage_of_rent_to_reserve: Decimal = Decimal("0")
    chase_reserves: bool = False


class PropertyStatusUpdate(BaseModel):
    llc_id: Optional[str] = None
    property_name: Optional[str] = Field(None, min_length=1, max_length=300)
    tax_bucket_balance: Optional[Decimal] = None
    tax_to_settle: Optional[Decimal] = None
    reserve_bucket_balance: Optional[Decimal] = None
    reserve_to_settle: Optional[Decimal] = None
    reserve_bucket_cap: Optional[Decimal] = None
    reserve_debt: Optional[Decimal] = None
    base_rent_target: Optional[Decimal] = None
    target_tax_allocation: Optional[Decimal] = None
    precentage_of_rent_to_reserve: Optional[Decimal] = None
    chase_reserves: Optional[bool] = None


class PropertyStatusRes(BaseModel):
    property_id: str
    llc_id: str
    property_name: str
    tax_bucket_balance: Decimal
    tax_to_settle: Decimal
    reserve_bucket_balance: Decimal
    reserve_to_settle: Decimal
    reserve_bucket_cap: Decimal
    reserve_debt: Decimal
    base_rent_target: Decimal
    target_tax_allocation: Decimal
    precentage_of_rent_to_reserve: Decimal
    # Derived, read-only: base_rent_target * precentage_of_rent_to_reserve / 100.
    target_reserve_allocation: Decimal
    chase_reserves: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}
