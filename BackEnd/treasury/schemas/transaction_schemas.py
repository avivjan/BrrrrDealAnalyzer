from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from treasury.models.transaction_ledger import VALID_SUB_BUCKETS, VALID_TRANSACTION_TYPES


class TransactionLedgerCreate(BaseModel):
    transaction_id: Optional[str] = None
    property_id: Optional[str] = None
    amount: Decimal
    description: str = Field(..., min_length=1, max_length=500)
    timestamp: datetime
    is_real_bank_tx: bool = False
    sub_bucket_assignment: Optional[str] = None
    transaction_type: str
    settlement_batch_id: Optional[str] = None

    @field_validator("sub_bucket_assignment")
    @classmethod
    def validate_sub_bucket(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in VALID_SUB_BUCKETS:
            raise ValueError(
                f"sub_bucket_assignment must be one of {sorted(VALID_SUB_BUCKETS)} or null, got '{value}'"
            )
        return value

    @field_validator("transaction_type")
    @classmethod
    def validate_transaction_type(cls, value: str) -> str:
        if value not in VALID_TRANSACTION_TYPES:
            raise ValueError(
                f"transaction_type must be one of {sorted(VALID_TRANSACTION_TYPES)}, got '{value}'"
            )
        return value


class TransactionLedgerUpdate(BaseModel):
    property_id: Optional[str] = None
    amount: Optional[Decimal] = None
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    timestamp: Optional[datetime] = None
    is_real_bank_tx: Optional[bool] = None
    sub_bucket_assignment: Optional[str] = None
    transaction_type: Optional[str] = None
    settlement_batch_id: Optional[str] = None
    clear_property: Optional[bool] = None

    @field_validator("sub_bucket_assignment")
    @classmethod
    def validate_sub_bucket(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in VALID_SUB_BUCKETS:
            raise ValueError(
                f"sub_bucket_assignment must be one of {sorted(VALID_SUB_BUCKETS)} or null, got '{value}'"
            )
        return value

    @field_validator("transaction_type")
    @classmethod
    def validate_transaction_type(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in VALID_TRANSACTION_TYPES:
            raise ValueError(
                f"transaction_type must be one of {sorted(VALID_TRANSACTION_TYPES)}, got '{value}'"
            )
        return value


class TransactionLedgerRes(BaseModel):
    transaction_id: str
    property_id: Optional[str] = None
    amount: Decimal
    description: str
    timestamp: str
    is_real_bank_tx: bool
    sub_bucket_assignment: Optional[str] = None
    transaction_type: str
    settlement_batch_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}
