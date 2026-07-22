from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from treasury.schemas.transaction_schemas import TransactionLedgerRes


class BankWebhookPayload(BaseModel):
    """Simulated or live bank webhook body.

    Either supply `category` as a shorthand (`rent`, `principal_interest`,
    `repair`, `emergency_advance`, `intercompany_loan`, `tax_allocation`,
    `reserve_allocation`) or provide the explicit `transaction_type` /
    `is_real_bank_tx` / `sub_bucket_assignment` fields directly.
    """

    property_id: Optional[str] = None
    amount: Decimal
    description: str = Field(..., min_length=1, max_length=500)
    timestamp: datetime
    category: Optional[str] = None
    transaction_type: Optional[str] = None
    is_real_bank_tx: Optional[bool] = None
    sub_bucket_assignment: Optional[str] = None
    settlement_batch_id: Optional[str] = None


class WebhookIngestResult(BaseModel):
    transaction: TransactionLedgerRes
    overflow_transaction: Optional[TransactionLedgerRes] = None
