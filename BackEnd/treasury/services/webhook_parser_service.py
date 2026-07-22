"""Webhook payload parsing — the ONLY place that knows how to translate a
raw (simulated or live) bank webhook body into the platform's normalized
transaction shape.

Keeping this isolated from `transaction_routing_service` means the
ingestion pipeline never has to know or care what a specific bank's
webhook payload looks like; it only ever deals with a validated
`TransactionLedgerCreate`.
"""

from typing import Optional

from treasury.models.transaction_ledger import VALID_SUB_BUCKETS, VALID_TRANSACTION_TYPES
from treasury.schemas.transaction_schemas import TransactionLedgerCreate
from treasury.schemas.webhook_schemas import BankWebhookPayload
from treasury.services.exceptions import ValidationError

# Shorthand categories a simulated bank webhook can send instead of the
# raw (transaction_type, is_real_bank_tx, sub_bucket_assignment) triple.
#
# 'Real Bank Transactions' (is_real_bank_tx=True) are actual money moving
# through the bank account: Rent, P&I, and Debit/Wire repairs. 'Virtual
# Platform Actions' (is_real_bank_tx=False) never touch the real bank
# account — they're bookkeeping moves the platform makes on its own
# ledger, like sweeping a Tax allocation or a rent-overflow entry into
# the reserve bucket.
_CATEGORY_MAP: dict[str, dict] = {
    "rent": {"transaction_type": "Rent", "is_real_bank_tx": True, "sub_bucket_assignment": None},
    "principal_interest": {
        "transaction_type": "P&I",
        "is_real_bank_tx": True,
        "sub_bucket_assignment": None,
    },
    "repair": {
        "transaction_type": "Repair",
        "is_real_bank_tx": True,
        "sub_bucket_assignment": None,
    },
    "emergency_advance": {
        "transaction_type": "Emergency Advance",
        "is_real_bank_tx": True,
        "sub_bucket_assignment": None,
    },
    "intercompany_loan": {
        "transaction_type": "Intercompany Loan",
        "is_real_bank_tx": True,
        "sub_bucket_assignment": None,
    },
    "tax_allocation": {
        "transaction_type": "Rent",
        "is_real_bank_tx": False,
        "sub_bucket_assignment": "Tax",
    },
    "reserve_allocation": {
        "transaction_type": "Rent",
        "is_real_bank_tx": False,
        "sub_bucket_assignment": "General Reserve",
    },
}


def parse_bank_webhook(payload: BankWebhookPayload) -> TransactionLedgerCreate:
    """Normalize a webhook payload into a `TransactionLedgerCreate`.

    Callers may either supply the shorthand `category` (for simulated
    webhooks / test fixtures) or the explicit `transaction_type` /
    `is_real_bank_tx` / `sub_bucket_assignment` triple directly (for a
    real bank integration that already knows how to classify itself).
    Explicit fields always win over the category shorthand.
    """
    derived = _CATEGORY_MAP.get(payload.category) if payload.category else None
    if payload.category and derived is None:
        raise ValidationError(
            f"Unknown webhook category '{payload.category}'. "
            f"Expected one of {sorted(_CATEGORY_MAP)} or explicit transaction_type/"
            f"is_real_bank_tx/sub_bucket_assignment fields."
        )

    transaction_type = payload.transaction_type or (derived or {}).get("transaction_type")
    is_real_bank_tx = (
        payload.is_real_bank_tx
        if payload.is_real_bank_tx is not None
        else (derived or {}).get("is_real_bank_tx", False)
    )
    sub_bucket_assignment: Optional[str] = (
        payload.sub_bucket_assignment
        if payload.sub_bucket_assignment is not None
        else (derived or {}).get("sub_bucket_assignment")
    )

    if transaction_type is None:
        raise ValidationError(
            "Webhook payload must supply either 'category' or an explicit 'transaction_type'."
        )
    if transaction_type not in VALID_TRANSACTION_TYPES:
        raise ValidationError(
            f"transaction_type must be one of {sorted(VALID_TRANSACTION_TYPES)}, "
            f"got '{transaction_type}'"
        )
    if sub_bucket_assignment is not None and sub_bucket_assignment not in VALID_SUB_BUCKETS:
        raise ValidationError(
            f"sub_bucket_assignment must be one of {sorted(VALID_SUB_BUCKETS)} or null, "
            f"got '{sub_bucket_assignment}'"
        )

    return TransactionLedgerCreate(
        property_id=payload.property_id,
        amount=payload.amount,
        description=payload.description,
        timestamp=payload.timestamp,
        is_real_bank_tx=bool(is_real_bank_tx),
        sub_bucket_assignment=sub_bucket_assignment,
        transaction_type=transaction_type,
        settlement_batch_id=payload.settlement_batch_id,
    )
