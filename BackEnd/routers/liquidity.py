"""/liquidity/* -- transactions, recurring rules, settings, Mercury balance."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db import get_db
from ReqRes.common.liquidity_schemas import (
    LiquidityTransactionCreate, LiquidityTransactionUpdate, LiquidityTransactionRes,
    LiquidityRecurringTransactionCreate, LiquidityRecurringTransactionUpdate,
    LiquidityRecurringTransactionRes,
    LiquiditySettingsUpdate, LiquiditySettingsRes,
)
from BL.liquidity.listTransactions import list_transactions as list_transactions_bl
from BL.liquidity.createTransaction import create_transaction as create_transaction_bl
from BL.liquidity.updateTransaction import update_transaction as update_transaction_bl
from BL.liquidity.deleteTransaction import delete_transaction as delete_transaction_bl
from BL.liquidity.listRecurring import list_recurring as list_recurring_bl
from BL.liquidity.createRecurring import create_recurring as create_recurring_bl
from BL.liquidity.updateRecurring import update_recurring as update_recurring_bl
from BL.liquidity.deleteRecurring import delete_recurring as delete_recurring_bl
from BL.liquidity.getSettings import get_settings as get_settings_bl
from BL.liquidity.updateSettings import update_settings as update_settings_bl
from BL.liquidity.mercuryBalance import get_mercury_balance as get_mercury_balance_bl
from BL.liquidity.common.mercury_client import MercuryApiError, MercuryConfigError

router = APIRouter()


@router.get("/liquidity/transactions", response_model=List[LiquidityTransactionRes])
def list_liquidity_transactions(db: Session = Depends(get_db)):
    return list_transactions_bl(db)

@router.post("/liquidity/transactions", response_model=LiquidityTransactionRes, status_code=201)
def create_liquidity_transaction(data: LiquidityTransactionCreate, db: Session = Depends(get_db)):
    return create_transaction_bl(db, data)

@router.put("/liquidity/transactions/{txn_id}", response_model=LiquidityTransactionRes)
def update_liquidity_transaction(txn_id: str, data: LiquidityTransactionUpdate, db: Session = Depends(get_db)):
    result = update_transaction_bl(db, txn_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return result

@router.delete("/liquidity/transactions/{txn_id}")
def delete_liquidity_transaction(txn_id: str, db: Session = Depends(get_db)):
    if not delete_transaction_bl(db, txn_id):
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"message": "Transaction deleted"}


# --- Recurring transactions (e.g. monthly HM interest, weekly rent) ---
# Stored as rules; the frontend expands each rule into virtual events on
# the timeline. Editing the rule retroactively fixes every projected event.

@router.get("/liquidity/recurring", response_model=List[LiquidityRecurringTransactionRes])
def list_liquidity_recurring(db: Session = Depends(get_db)):
    return list_recurring_bl(db)


@router.post(
    "/liquidity/recurring",
    response_model=LiquidityRecurringTransactionRes,
    status_code=201,
)
def create_liquidity_recurring(
    data: LiquidityRecurringTransactionCreate, db: Session = Depends(get_db)
):
    try:
        return create_recurring_bl(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/liquidity/recurring/{rule_id}", response_model=LiquidityRecurringTransactionRes
)
def update_liquidity_recurring(
    rule_id: str,
    data: LiquidityRecurringTransactionUpdate,
    db: Session = Depends(get_db),
):
    try:
        result = update_recurring_bl(db, rule_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="Recurring rule not found")
    return result


@router.delete("/liquidity/recurring/{rule_id}")
def delete_liquidity_recurring(rule_id: str, db: Session = Depends(get_db)):
    if not delete_recurring_bl(db, rule_id):
        raise HTTPException(status_code=404, detail="Recurring rule not found")
    return {"message": "Recurring rule deleted"}


@router.get("/liquidity/settings", response_model=LiquiditySettingsRes)
def get_liquidity_settings(db: Session = Depends(get_db)):
    return get_settings_bl(db)

@router.put("/liquidity/settings", response_model=LiquiditySettingsRes)
def update_liquidity_settings(data: LiquiditySettingsUpdate, db: Session = Depends(get_db)):
    return update_settings_bl(db, data)


@router.get("/liquidity/mercury-balance")
def get_mercury_balance():
    """
    Fetch the live sum of all active Mercury account balances, in $k.

    The frontend uses this to re-anchor the liquidity timeline's opening
    balance to today on page load.
    """
    try:
        return get_mercury_balance_bl()
    except MercuryConfigError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except MercuryApiError as e:
        raise HTTPException(status_code=502, detail=str(e))
