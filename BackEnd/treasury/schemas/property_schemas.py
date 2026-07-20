from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class PropertyStatusCreate(BaseModel):
    property_id: Optional[str] = Field(
        None,
        description="Optional human-friendly id; generated when omitted.",
    )
    llc_id: str
    tax_bucket_balance: Decimal = Decimal("0")
    tax_to_settle: Decimal = Decimal("0")
    ins_bucket_balance: Decimal = Decimal("0")
    ins_to_settle: Decimal = Decimal("0")
    reserve_bucket_balance: Decimal = Decimal("0")
    reserve_to_settle: Decimal = Decimal("0")
    reserve_bucket_cap: Decimal = Decimal("0")
    reserve_debt: Decimal = Decimal("0")
    interest_earned_counter: Decimal = Decimal("0")
    base_rent_target: Decimal = Decimal("0")
    target_tax_allocation: Decimal = Decimal("0")
    target_ins_allocation: Decimal = Decimal("0")
    target_reserve_allocation: Decimal = Decimal("0")
    force_tax_ins_accrual: bool = False
    double_reserve_on_recovery: bool = False


class PropertyStatusUpdate(BaseModel):
    llc_id: Optional[str] = None
    tax_bucket_balance: Optional[Decimal] = None
    tax_to_settle: Optional[Decimal] = None
    ins_bucket_balance: Optional[Decimal] = None
    ins_to_settle: Optional[Decimal] = None
    reserve_bucket_balance: Optional[Decimal] = None
    reserve_to_settle: Optional[Decimal] = None
    reserve_bucket_cap: Optional[Decimal] = None
    reserve_debt: Optional[Decimal] = None
    interest_earned_counter: Optional[Decimal] = None
    base_rent_target: Optional[Decimal] = None
    target_tax_allocation: Optional[Decimal] = None
    target_ins_allocation: Optional[Decimal] = None
    target_reserve_allocation: Optional[Decimal] = None
    force_tax_ins_accrual: Optional[bool] = None
    double_reserve_on_recovery: Optional[bool] = None


class PropertyStatusRes(BaseModel):
    property_id: str
    llc_id: str
    tax_bucket_balance: Decimal
    tax_to_settle: Decimal
    ins_bucket_balance: Decimal
    ins_to_settle: Decimal
    reserve_bucket_balance: Decimal
    reserve_to_settle: Decimal
    reserve_bucket_cap: Decimal
    reserve_debt: Decimal
    interest_earned_counter: Decimal
    base_rent_target: Decimal
    target_tax_allocation: Decimal
    target_ins_allocation: Decimal
    target_reserve_allocation: Decimal
    force_tax_ins_accrual: bool
    double_reserve_on_recovery: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}
