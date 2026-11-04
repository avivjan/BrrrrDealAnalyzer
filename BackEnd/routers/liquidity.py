"""/liquidity/* -- transactions, recurring rules, settings, Mercury balance."""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from db import get_db
from ReqRes.common.liquidity_schemas import (
    LiquidityTransactionCreate, LiquidityTransactionUpdate, LiquidityTransactionRes,
    LiquidityRecurringTransactionCreate, LiquidityRecurringTransactionUpdate,
    LiquidityRecurringTransactionRes,
    LiquiditySettingsUpdate, LiquiditySettingsRes,
    LiquidityTransactionBulkActionReq,
    LiquidityRecurringOccurrenceMoveReq,
)
from BL.liquidity.markTransactionDone import mark_transaction_done as mark_transaction_done_bl
from BL.liquidity.bulkTransactionAction import apply_bulk_transaction_action as apply_bulk_transaction_action_bl, UnknownLiquidityTransactionError
from BL.liquidity.listTransactions import list_transactions as list_transactions_bl
from BL.liquidity.createTransaction import create_transaction as create_transaction_bl
from BL.liquidity.updateTransaction import update_transaction as update_transaction_bl
from BL.liquidity.deleteTransaction import delete_transaction as delete_transaction_bl
from BL.liquidity.listRecurring import list_recurring as list_recurring_bl
from BL.liquidity.createRecurring import create_recurring as create_recurring_bl
from BL.liquidity.updateRecurring import update_recurring as update_recurring_bl
from BL.liquidity.deleteRecurring import delete_recurring as delete_recurring_bl
from BL.liquidity.recurringOccurrences import (
    NotAnOccurrenceOfTheRuleError, UnknownRecurringRuleError, change_occurrence as change_occurrence_bl,
)
from BL.liquidity.getSettings import get_settings as get_settings_bl
from BL.liquidity.updateSettings import update_settings as update_settings_bl
from BL.liquidity.mercuryBalance import get_mercury_balance as get_mercury_balance_bl
from BL.liquidity.common.mercury_client import MercuryApiError, MercuryConfigError
from BL.auth.common.audit import record as audit

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

@router.post("/liquidity/transactions/{txn_id}/done", response_model=LiquidityTransactionRes)
def mark_liquidity_transaction_done(txn_id: str, db: Session = Depends(get_db)):
    result = mark_transaction_done_bl(db, txn_id, is_done=True)
    if not result:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return result

@router.post("/liquidity/transactions/{txn_id}/not-done", response_model=LiquidityTransactionRes)
def mark_liquidity_transaction_not_done(txn_id: str, db: Session = Depends(get_db)):
    result = mark_transaction_done_bl(db, txn_id, is_done=False)
    if not result:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return result

@router.post("/liquidity/transactions/bulk", response_model=List[LiquidityTransactionRes])
def apply_liquidity_transaction_bulk_action(data: LiquidityTransactionBulkActionReq, db: Session = Depends(get_db)):
    try:
        return apply_bulk_transaction_action_bl(db, data)
    except UnknownLiquidityTransactionError:
        raise HTTPException(status_code=404, detail="Transaction not found")
    except NotAnOccurrenceOfTheRuleError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

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


def _change_recurring_occurrence(db: Session, rule_id: str, scheduled_date: date, action: str, new_effective_date: Optional[date] = None):
    try:
        return change_occurrence_bl(db, rule_id, scheduled_date, action, new_effective_date)
    except UnknownRecurringRuleError:
        raise HTTPException(status_code=404, detail="Recurring rule not found")
    except NotAnOccurrenceOfTheRuleError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# One occurrence of a rule: done (the money moved), open again (Undo), or moved to another date.
@router.post("/liquidity/recurring/{rule_id}/occurrences/{scheduled_date}/done", response_model=LiquidityRecurringTransactionRes)
def mark_liquidity_recurring_occurrence_done(rule_id: str, scheduled_date: date, db: Session = Depends(get_db)):
    return _change_recurring_occurrence(db, rule_id, scheduled_date, "mark_done")


@router.post("/liquidity/recurring/{rule_id}/occurrences/{scheduled_date}/not-done", response_model=LiquidityRecurringTransactionRes)
def mark_liquidity_recurring_occurrence_not_done(rule_id: str, scheduled_date: date, db: Session = Depends(get_db)):
    return _change_recurring_occurrence(db, rule_id, scheduled_date, "mark_not_done")


@router.post("/liquidity/recurring/{rule_id}/occurrences/{scheduled_date}/move", response_model=LiquidityRecurringTransactionRes)
def move_liquidity_recurring_occurrence(rule_id: str, scheduled_date: date, data: LiquidityRecurringOccurrenceMoveReq,
                                        db: Session = Depends(get_db)):
    return _change_recurring_occurrence(db, rule_id, scheduled_date, "move_to_date", data.new_effective_date)


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
def get_mercury_balance(request: Request, db: Session = Depends(get_db)):
    """
    Fetch the live Mercury account balances, in dollars, and the cash on hand among them
    (`counted_as_cash_balance_dollars`: the accounts chosen in the liquidity settings).

    The frontend uses this to re-anchor the liquidity timeline's opening
    balance to today on page load. Every call leaves an audit row (who, from
    where, which workspaces answered) -- never a token.
    """
    try:
        result = get_mercury_balance_bl(db)
    except MercuryConfigError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except MercuryApiError as e:
        audit("mercury_fetch", request, detail={"ok": False, "error": str(e)})
        raise HTTPException(status_code=502, detail=str(e))
    audit(
        "mercury_fetch",
        request,
        detail={
            "ok": True,
            "workspaces": [w.get("workspace") for w in result.get("workspaces", [])],
            "failed": [e.get("workspace") for e in result.get("workspace_errors", [])],
        },
    )
    return result
