from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db import get_db
from treasury.schemas.transaction_schemas import (
    TransactionLedgerCreate,
    TransactionLedgerUpdate,
    TransactionLedgerRes,
)
from treasury.services import transaction_service
from treasury.services.exceptions import NotFoundError, ValidationError

router = APIRouter(
    prefix="/treasury/transactions",
    tags=["Treasury - Transaction Ledger"],
)


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


@router.get("", response_model=list[TransactionLedgerRes])
def list_transactions(
    property_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return [_to_res(txn) for txn in transaction_service.list_transactions(db, property_id)]


@router.post("", response_model=TransactionLedgerRes, status_code=201)
def create_transaction(payload: TransactionLedgerCreate, db: Session = Depends(get_db)):
    try:
        return _to_res(transaction_service.create_transaction(db, payload))
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{transaction_id}", response_model=TransactionLedgerRes)
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    try:
        return _to_res(transaction_service.get_transaction(db, transaction_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{transaction_id}", response_model=TransactionLedgerRes)
def update_transaction(
    transaction_id: str,
    payload: TransactionLedgerUpdate,
    db: Session = Depends(get_db),
):
    try:
        return _to_res(transaction_service.update_transaction(db, transaction_id, payload))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{transaction_id}")
def delete_transaction(transaction_id: str, db: Session = Depends(get_db)):
    try:
        transaction_service.delete_transaction(db, transaction_id)
        return {"message": "Transaction deleted."}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
