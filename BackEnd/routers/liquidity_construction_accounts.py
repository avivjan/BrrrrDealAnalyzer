"""/liquidity/construction-accounts/* -- a rehab's own Mercury construction account (tasks/todo/ConstructionAccountPerRehab.md).

Link an account to a Bought BRRRR deal at any stage of its rehab, correct the bank feed by hand, switch or close out
the account, and keep the deal's deposit, return and top-up rows in the liquidity timeline in step with it. Mercury is
only read here. Every write is audited (which deal, what kind of change), never an amount.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from db import get_db
from BL.auth.common.audit import record as audit
from BL.liquidity.constructionAccount import construction_accounts as construction_accounts_bl
from ReqRes.common.liquidity_construction_account_schemas import (
    ConstructionAccountClosedOutRes, ConstructionAccountLinkReq, ConstructionAccountManualAdjustmentReq,
    ConstructionAccountRefreshReq, ConstructionAccountRefreshRes, ConstructionAccountStatusRes,
    ConstructionAccountSwitchPreviewRes, ConstructionAccountSwitchReq, ConstructionAccountTransactionOverrideReq,
    ConstructionAccountTransactionRes,
)

router = APIRouter()

_DEAL_NOT_FOUND = "Bought BRRRR deal not found"
_NOT_LINKED = "This deal has no construction account linked"
_NOT_FOUND_ON_THE_ACCOUNT = "Not found on this deal's construction account"
_MERCURY_UNAVAILABLE = "Mercury did not answer; try again in a moment"


def _run(action):
    """Map the business layer's errors to HTTP. A message from the business layer is written for the user; Mercury's
    own error text is never relayed."""
    try:
        return action()
    except construction_accounts_bl.ConstructionAccountDealNotFoundError:
        raise HTTPException(status_code=404, detail=_DEAL_NOT_FOUND)
    except construction_accounts_bl.ConstructionAccountNotLinkedError:
        raise HTTPException(status_code=404, detail=_NOT_LINKED)
    except construction_accounts_bl.ConstructionAccountNotFoundError:
        raise HTTPException(status_code=404, detail=_NOT_FOUND_ON_THE_ACCOUNT)
    except construction_accounts_bl.ConstructionAccountValidationError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except construction_accounts_bl.ConstructionAccountConflictError as error:
        raise HTTPException(status_code=409, detail=str(error))
    except construction_accounts_bl.MercuryUnavailableError:
        raise HTTPException(status_code=502, detail=_MERCURY_UNAVAILABLE)


def _audit(event: str, request: Request, bought_deal_id: str, **extra) -> None:
    audit(event, request, detail={"bought_deal_id": bought_deal_id, **extra})


@router.get("/liquidity/construction-accounts", response_model=List[ConstructionAccountStatusRes])
def list_liquidity_construction_accounts(db: Session = Depends(get_db)):
    """Every Bought BRRRR deal between its purchase and its refi that is in the liquidity timeline, with its
    construction account: balance, loan draws pulled and remaining, rehab payments made and remaining, the projected
    return at rehab end and what is safe to steal now. Amounts are those of the last refresh (`amounts_as_of`)."""
    return construction_accounts_bl.list_construction_accounts(db)


@router.post("/liquidity/construction-accounts/refresh", response_model=ConstructionAccountRefreshRes)
def refresh_liquidity_construction_accounts(data: ConstructionAccountRefreshReq, request: Request, db: Session = Depends(get_db)):
    """Read every linked construction account from Mercury and bring each deal's deposit, return and top-up rows in
    step. Safe to call often: it changes nothing when nothing moved."""
    result = construction_accounts_bl.refresh_construction_accounts(db, data.today)
    audit("liquidity_construction_accounts_refreshed", request, detail={
        "refreshed_deal_count": result.refreshed_deal_count, "changed_row_count": result.changed_row_count,
        "mercury_is_unavailable": result.mercury_is_unavailable})
    return result


@router.put("/liquidity/construction-accounts/{bought_deal_id}", response_model=ConstructionAccountStatusRes)
def save_liquidity_construction_account_link(bought_deal_id: str, data: ConstructionAccountLinkReq, request: Request,
                                             db: Session = Depends(get_db)):
    """Link a Mercury construction account to a Bought BRRRR deal, or edit the link. Allowed at any stage of the rehab:
    the two 'before this account' amounts say what was pulled and paid earlier, and stay editable."""
    result = _run(lambda: construction_accounts_bl.save_construction_account_link(db, bought_deal_id, data))
    _audit("liquidity_construction_account_link_saved", request, bought_deal_id)
    return result


@router.delete("/liquidity/construction-accounts/{bought_deal_id}", response_model=ConstructionAccountStatusRes)
def unlink_liquidity_construction_account(bought_deal_id: str, request: Request, db: Session = Depends(get_db)):
    """Remove the link, with its manual adjustments and transaction overrides. The deal's rows go back to the plan."""
    result = _run(lambda: construction_accounts_bl.unlink_construction_account(db, bought_deal_id))
    _audit("liquidity_construction_account_unlinked", request, bought_deal_id)
    return result


@router.get("/liquidity/construction-accounts/{bought_deal_id}/switch-account-preview", response_model=ConstructionAccountSwitchPreviewRes)
def preview_liquidity_construction_account_switch(bought_deal_id: str, db: Session = Depends(get_db)):
    """Before replacing the construction account: the old account's balance (it must be $0) and the baselines that
    carry its draws and payments over."""
    return _run(lambda: construction_accounts_bl.preview_construction_account_switch(db, bought_deal_id))


@router.post("/liquidity/construction-accounts/{bought_deal_id}/switch-account", response_model=ConstructionAccountStatusRes)
def switch_liquidity_construction_account(bought_deal_id: str, data: ConstructionAccountSwitchReq, request: Request,
                                          db: Session = Depends(get_db)):
    """Replace the deal's construction account mid-rehab. Refused (409) while the old account still holds money."""
    result = _run(lambda: construction_accounts_bl.switch_construction_account(db, bought_deal_id, data))
    _audit("liquidity_construction_account_switched", request, bought_deal_id)
    return result


@router.post("/liquidity/construction-accounts/{bought_deal_id}/manual-adjustments", response_model=ConstructionAccountStatusRes, status_code=201)
def add_liquidity_construction_account_manual_adjustment(bought_deal_id: str, data: ConstructionAccountManualAdjustmentReq,
                                                         request: Request, db: Session = Depends(get_db)):
    """Record rehab money that never touched the construction account: a payment made from another account, by credit
    card or in cash (`manual_payment`), or a draw the lender wired elsewhere (`manual_draw`)."""
    result = _run(lambda: construction_accounts_bl.add_manual_adjustment(db, bought_deal_id, data))
    _audit("liquidity_construction_account_manual_adjustment_added", request, bought_deal_id, adjustment_type=data.adjustment_type)
    return result


@router.put("/liquidity/construction-accounts/{bought_deal_id}/manual-adjustments/{adjustment_id}", response_model=ConstructionAccountStatusRes)
def update_liquidity_construction_account_manual_adjustment(bought_deal_id: str, adjustment_id: str,
                                                            data: ConstructionAccountManualAdjustmentReq, request: Request,
                                                            db: Session = Depends(get_db)):
    result = _run(lambda: construction_accounts_bl.update_manual_adjustment(db, bought_deal_id, adjustment_id, data))
    _audit("liquidity_construction_account_manual_adjustment_updated", request, bought_deal_id, adjustment_type=data.adjustment_type)
    return result


@router.delete("/liquidity/construction-accounts/{bought_deal_id}/manual-adjustments/{adjustment_id}", response_model=ConstructionAccountStatusRes)
def delete_liquidity_construction_account_manual_adjustment(bought_deal_id: str, adjustment_id: str, request: Request,
                                                            db: Session = Depends(get_db)):
    result = _run(lambda: construction_accounts_bl.delete_manual_adjustment(db, bought_deal_id, adjustment_id))
    _audit("liquidity_construction_account_manual_adjustment_deleted", request, bought_deal_id)
    return result


@router.get("/liquidity/construction-accounts/{bought_deal_id}/transactions", response_model=List[ConstructionAccountTransactionRes])
def list_liquidity_construction_account_transactions(bought_deal_id: str, request: Request, db: Session = Depends(get_db)):
    """The construction account's bank transactions, newest first, each with its automatic category (loan draw, rehab
    payment, own money) and what it counts as after your overrides."""
    result = _run(lambda: construction_accounts_bl.list_construction_account_transactions(db, bought_deal_id))
    _audit("mercury_fetch", request, bought_deal_id, ok=True, what="construction_account_transactions")
    return result


@router.put("/liquidity/construction-accounts/{bought_deal_id}/transactions/{mercury_transaction_id}/override",
            response_model=ConstructionAccountStatusRes)
def set_liquidity_construction_account_transaction_override(bought_deal_id: str, mercury_transaction_id: str,
                                                            data: ConstructionAccountTransactionOverrideReq, request: Request,
                                                            db: Session = Depends(get_db)):
    """Ignore one bank transaction of the construction account, or count it in another category."""
    result = _run(lambda: construction_accounts_bl.set_transaction_override(db, bought_deal_id, mercury_transaction_id, data))
    _audit("liquidity_construction_account_transaction_override_set", request, bought_deal_id,
           ignored=data.ignored, category_override=data.category_override)
    return result


@router.delete("/liquidity/construction-accounts/{bought_deal_id}/transactions/{mercury_transaction_id}/override",
               response_model=ConstructionAccountStatusRes)
def clear_liquidity_construction_account_transaction_override(bought_deal_id: str, mercury_transaction_id: str, request: Request,
                                                              db: Session = Depends(get_db)):
    """Back to the transaction's automatic category."""
    result = _run(lambda: construction_accounts_bl.clear_transaction_override(db, bought_deal_id, mercury_transaction_id))
    _audit("liquidity_construction_account_transaction_override_cleared", request, bought_deal_id)
    return result


@router.post("/liquidity/construction-accounts/{bought_deal_id}/mark-ready-for-close-out", response_model=ConstructionAccountStatusRes)
def mark_liquidity_construction_account_ready_for_close_out(bought_deal_id: str, request: Request, db: Session = Depends(get_db)):
    """The rehab is over as far as this account goes, before the rehab-completed milestone is approved."""
    result = _run(lambda: construction_accounts_bl.mark_ready_for_close_out(db, bought_deal_id))
    _audit("liquidity_construction_account_marked_ready_for_close_out", request, bought_deal_id)
    return result


@router.post("/liquidity/construction-accounts/{bought_deal_id}/mark-closed-out", response_model=ConstructionAccountClosedOutRes)
def mark_liquidity_construction_account_closed_out(bought_deal_id: str, request: Request, db: Session = Depends(get_db)):
    """Close the account out without a transfer (you emptied it in Mercury): its return row is marked done."""
    result = _run(lambda: construction_accounts_bl.mark_closed_out(db, bought_deal_id))
    _audit("liquidity_construction_account_closed_out", request, bought_deal_id)
    return result


@router.post("/liquidity/construction-accounts/{bought_deal_id}/reopen", response_model=ConstructionAccountStatusRes)
def reopen_liquidity_construction_account(bought_deal_id: str, request: Request, db: Session = Depends(get_db)):
    """Undo a close-out: the account is live again and its return row counts again."""
    result = _run(lambda: construction_accounts_bl.reopen_construction_account(db, bought_deal_id))
    _audit("liquidity_construction_account_reopened", request, bought_deal_id)
    return result
