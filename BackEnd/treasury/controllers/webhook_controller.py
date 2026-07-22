"""Route handling only — every byte of domain logic (payload parsing,
bucket mutation, rent-milestone checks, veil protection) lives in the
`webhook_parser_service` / `transaction_routing_service` modules. This
router just adapts HTTP in and out.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db import get_db
from treasury.schemas.transaction_schemas import TransactionLedgerRes
from treasury.schemas.webhook_schemas import BankWebhookPayload, WebhookIngestResult
from treasury.services import transaction_routing_service, webhook_parser_service
from treasury.services.exceptions import ValidationError

router = APIRouter(prefix="/treasury/webhooks", tags=["Treasury - Webhook Ingestion"])


def _to_res(txn) -> TransactionLedgerRes:
    return TransactionLedgerRes(
        transaction_id=txn.transaction_id,
        property_id=txn.property_id,
        amount=txn.amount,
        description=txn.description,
        timestamp=txn.timestamp.isoformat(),
        is_real_bank_tx=txn.is_real_bank_tx,
        sub_bucket_assignment=txn.sub_bucket_assignment,
        transaction_type=txn.transaction_type,
        settlement_batch_id=txn.settlement_batch_id,
        created_at=txn.created_at.isoformat() if txn.created_at else None,
        updated_at=txn.updated_at.isoformat() if txn.updated_at else None,
    )


def _to_result(result: dict) -> WebhookIngestResult:
    overflow = result.get("overflow_transaction")
    return WebhookIngestResult(
        transaction=_to_res(result["transaction"]),
        overflow_transaction=_to_res(overflow) if overflow is not None else None,
    )


@router.post("/bank-transactions", response_model=WebhookIngestResult, status_code=201)
def ingest_bank_transaction(payload: BankWebhookPayload, db: Session = Depends(get_db)):
    """Live/simulated single-transaction webhook — the real-time path.

    Ingested transactions immediately mutate the mapped property's
    virtual bucket balance and settlement queue; Rent transactions also
    run the cumulative rent milestone check inline, before the response
    is returned.
    """
    try:
        parsed = webhook_parser_service.parse_bank_webhook(payload)
        result = transaction_routing_service.ingest_webhook_transaction(db, parsed)
        return _to_result(result)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/nightly-sync", response_model=list[WebhookIngestResult], status_code=201)
def run_nightly_sync(payloads: list[BankWebhookPayload], db: Session = Depends(get_db)):
    """Batch variant of the same pipeline used for continuous nightly
    reconciliation — NOT a monthly lookback script. Each payload runs
    through the identical parse -> ingest -> mutate -> milestone-check
    pipeline as a live webhook; nothing here recomputes historical state.
    """
    try:
        results = [
            transaction_routing_service.ingest_webhook_transaction(
                db, webhook_parser_service.parse_bank_webhook(payload)
            )
            for payload in payloads
        ]
        return [_to_result(result) for result in results]
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
