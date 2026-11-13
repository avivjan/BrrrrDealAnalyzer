"""/liquidity/construction-accounts/* -- a rehab's own Mercury construction account (tasks/todo/ConstructionAccountPerRehab.md).

Link an account to a Bought BRRRR deal at any stage of its rehab, edit the deal's rehab figures, correct the bank feed
by hand, switch or close out the account, and keep the deal's liquidity rows in step with it.

**Every write can be previewed.** With `preview_only=true` the write runs inside the database transaction, its
answer (the deal's figures and its liquidity rows before -> after) is built, and the transaction is rolled back:
nothing is saved. That answer is the confirmation prompt the page shows before the same call is sent for real.
Only this router commits, except a transfer, which stores its key before Mercury is asked. Mercury is only read
here, except by Deposit and Steal (a passkey step-up each, never an MCP tool). Every confirmed write is audited (which
deal, what kind of change), never an amount.
"""

import re
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from db import get_db
from BL.auth.common.audit import record as audit
from BL.auth.common.session_dependency import require_recent_auth
from BL.liquidity.constructionAccount import construction_account_transfers as construction_account_transfers_bl
from BL.liquidity.constructionAccount import construction_accounts as construction_accounts_bl
from DAL.data_models.liquidity.construction_account_models import (
    TRANSFER_DIRECTION_DEPOSIT_INTO_CONSTRUCTION_ACCOUNT, TRANSFER_DIRECTION_STEAL_TO_PRIMARY_CHECKING,
)
from ReqRes.common.liquidity_construction_account_schemas import (
    ConstructionAccountLinkReq, ConstructionAccountListRes, ConstructionAccountManualAdjustmentReq, ConstructionAccountRefreshReq,
    ConstructionAccountRefreshRes, ConstructionAccountRehabFiguresReq, ConstructionAccountSwitchPreviewRes,
    ConstructionAccountSwitchReq, ConstructionAccountTransactionOverrideReq, ConstructionAccountTransactionRes,
    ConstructionAccountTransferReq, ConstructionAccountTransferWriteRes, ConstructionAccountWriteRes, MercuryConnectionStatusRes,
    MercuryLastChangeRes,
)
from ReqRes.common.liquidity_deal_schemas import UseDealValueForField

router = APIRouter()

_DEAL_NOT_FOUND = "Bought BRRRR deal not found"
_NOT_LINKED = "This deal has no construction account linked"
_NOT_FOUND_ON_THE_ACCOUNT = "Not found on this deal's construction account"
_MERCURY_UNAVAILABLE = "Mercury did not answer; try again in a moment"
_USE_THE_NEW_VALUE_FOR_PATTERN = re.compile(r"^(?P<transaction_id>[A-Za-z0-9-]{1,64}):(?P<field>date|amount)$")

PREVIEW_ONLY = Query(False, description="True = answer what this write would change, and save nothing (the confirmation prompt).")
TODAY = Query(None, description="The browser's local date; default: today in the liquidity settings' time zone.")
USE_THE_NEW_VALUE_FOR = Query(
    None, max_length=200,
    description="'<transaction id>:date' or '<transaction id>:amount' per row you edited by hand that should take the new value anyway.")


def _use_the_new_value_for(values: Optional[List[str]]) -> list[UseDealValueForField]:
    choices = []
    for value in values or []:
        match = _USE_THE_NEW_VALUE_FOR_PATTERN.match(value)
        if match is None:
            raise HTTPException(status_code=422, detail="use_the_new_value_for takes '<transaction id>:date' or '<transaction id>:amount'")
        choices.append(UseDealValueForField(transaction_id=match["transaction_id"], field=match["field"]))
    return choices


def _run(db: Session, action, commit: bool = True):
    """Run one business action, then commit it, or roll it back (`commit=False`, or any error). Maps the business
    layer's errors to HTTP: a message from it is written for the user; Mercury's own error text is never relayed."""
    try:
        result = action()
    except construction_accounts_bl.ConstructionAccountDealNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail=_DEAL_NOT_FOUND)
    except construction_accounts_bl.ConstructionAccountNotLinkedError:
        db.rollback()
        raise HTTPException(status_code=404, detail=_NOT_LINKED)
    except construction_accounts_bl.ConstructionAccountNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail=_NOT_FOUND_ON_THE_ACCOUNT)
    except construction_accounts_bl.ConstructionAccountValidationError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error))
    except construction_accounts_bl.ConstructionAccountConflictError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(error))
    except construction_account_transfers_bl.ConstructionAccountTransferRefusedError as error:
        db.rollback()
        raise HTTPException(status_code=error.http_status, detail=str(error))
    except construction_accounts_bl.MercuryUnavailableError:
        db.rollback()
        raise HTTPException(status_code=502, detail=_MERCURY_UNAVAILABLE)
    except Exception:
        db.rollback()
        raise
    if commit:
        db.commit()
    else:
        db.rollback()
    return result


def _write(db: Session, request: Request, event: str, bought_deal_id: str, preview_only: bool, action, **audit_detail) -> ConstructionAccountWriteRes:
    result = _run(db, action, commit=not preview_only)
    if not preview_only:
        audit(event, request, detail={"bought_deal_id": bought_deal_id, "changed_the_liquidity_timeline": result.changes_the_liquidity_timeline,
                                      **audit_detail})
    return result


# --- Reads --------------------------------------------------------------------------------------------------------

@router.get("/liquidity/construction-accounts", response_model=ConstructionAccountListRes)
def list_liquidity_construction_accounts(db: Session = Depends(get_db)):
    """Every Bought BRRRR deal between its purchase and its refi that is in the liquidity timeline, with every number of
    its construction account, and the totals across them. Amounts are those of the last read (`amounts_as_of`)."""
    return _run(db, lambda: construction_accounts_bl.list_construction_accounts(db), commit=False)


@router.get("/liquidity/construction-accounts/last-change", response_model=MercuryLastChangeRes)
def get_liquidity_construction_accounts_last_change(db: Session = Depends(get_db)):
    """When the cash on hand or a construction account last changed, from the database only (never a Mercury call):
    an open page asks every few seconds and reloads when it moved."""
    return _run(db, lambda: construction_accounts_bl.last_mercury_change(db), commit=False)


@router.get("/liquidity/mercury-connection-status", response_model=MercuryConnectionStatusRes)
def get_liquidity_mercury_connection_status(db: Session = Depends(get_db)):
    """Per LLC: whether the backend found its read token and its transfer token, the exact setting names it reads them
    from, and how instant updates are doing. Names and times only, never a token or a secret."""
    return _run(db, lambda: construction_accounts_bl.mercury_connection_status(db))


@router.post("/liquidity/construction-accounts/refresh", response_model=ConstructionAccountRefreshRes)
def refresh_liquidity_construction_accounts(data: ConstructionAccountRefreshReq, request: Request, db: Session = Depends(get_db)):
    """Read every Mercury workspace (through the shared pace: one read per workspace every 10 seconds at most, whoever
    asks; a back-off after a 429) and bring each linked construction account and its rows in step. Changes the bank
    reports are applied and listed in `bank_reported_row_changes`. Safe to call often."""
    result = _run(db, lambda: construction_accounts_bl.refresh_construction_accounts(db, data.today))
    something_happened = result.changed_row_count or result.cash_balance_changed or result.construction_accounts_changed or result.mercury_is_unavailable
    if not data.is_a_background_poll or something_happened:
        audit("liquidity_construction_accounts_refreshed", request, detail={
            "refreshed_deal_count": result.refreshed_deal_count, "changed_row_count": result.changed_row_count,
            "cash_balance_changed": result.cash_balance_changed, "mercury_is_unavailable": result.mercury_is_unavailable,
            "is_a_background_poll": data.is_a_background_poll})
    return result


@router.get("/liquidity/construction-accounts/{bought_deal_id}/switch-account-preview", response_model=ConstructionAccountSwitchPreviewRes)
def preview_liquidity_construction_account_switch(bought_deal_id: str, db: Session = Depends(get_db)):
    """Before replacing the construction account: the old account's balance (it must be $0) and the baselines that
    carry its draws and payments over."""
    return _run(db, lambda: construction_accounts_bl.preview_construction_account_switch(db, bought_deal_id))


@router.get("/liquidity/construction-accounts/{bought_deal_id}/transactions", response_model=List[ConstructionAccountTransactionRes])
def list_liquidity_construction_account_transactions(bought_deal_id: str, request: Request, db: Session = Depends(get_db)):
    """The construction account's bank transactions, newest first, each with its automatic category (loan draw, rehab
    payment, own money) and what it counts as after your overrides."""
    result = _run(db, lambda: construction_accounts_bl.list_construction_account_transactions(db, bought_deal_id))
    audit("mercury_fetch", request, detail={"bought_deal_id": bought_deal_id, "ok": True, "what": "construction_account_transactions"})
    return result


# --- Writes (each one previewable) --------------------------------------------------------------------------------

@router.put("/liquidity/construction-accounts/{bought_deal_id}/rehab-figures", response_model=ConstructionAccountWriteRes)
def save_liquidity_construction_account_rehab_figures(bought_deal_id: str, data: ConstructionAccountRehabFiguresReq, request: Request,
                                                      preview_only: bool = PREVIEW_ONLY, today: Optional[date] = TODAY,
                                                      use_the_new_value_for: Optional[List[str]] = USE_THE_NEW_VALUE_FOR,
                                                      db: Session = Depends(get_db)):
    """Edit the Bought deal's actual rehab cost, contingency, construction budget or rehab cushion (the one deposit
    figure) from its construction account card: validated and written like a save of the deal, then its liquidity
    rows follow. Works for a deal with no account linked too."""
    choices = _use_the_new_value_for(use_the_new_value_for)
    return _write(db, request, "liquidity_construction_account_rehab_figures_saved", bought_deal_id, preview_only,
                  lambda: construction_accounts_bl.save_rehab_figures(db, bought_deal_id, data, today, choices, preview_only),
                  changed_figures=sorted(data.model_fields_set))


@router.put("/liquidity/construction-accounts/{bought_deal_id}", response_model=ConstructionAccountWriteRes)
def save_liquidity_construction_account_link(bought_deal_id: str, data: ConstructionAccountLinkReq, request: Request,
                                             preview_only: bool = PREVIEW_ONLY, today: Optional[date] = TODAY,
                                             use_the_new_value_for: Optional[List[str]] = USE_THE_NEW_VALUE_FOR,
                                             db: Session = Depends(get_db)):
    """Link a Mercury construction account to a Bought BRRRR deal, or edit the link. Allowed at any stage of the rehab:
    the two 'before this account' amounts say what was pulled and paid earlier, and stay editable."""
    choices = _use_the_new_value_for(use_the_new_value_for)
    return _write(db, request, "liquidity_construction_account_link_saved", bought_deal_id, preview_only,
                  lambda: construction_accounts_bl.save_construction_account_link(db, bought_deal_id, data, today, choices, preview_only))


@router.delete("/liquidity/construction-accounts/{bought_deal_id}", response_model=ConstructionAccountWriteRes)
def unlink_liquidity_construction_account(bought_deal_id: str, request: Request, preview_only: bool = PREVIEW_ONLY,
                                          today: Optional[date] = TODAY,
                                          use_the_new_value_for: Optional[List[str]] = USE_THE_NEW_VALUE_FOR,
                                          db: Session = Depends(get_db)):
    """Remove the link, with its manual adjustments and transaction overrides. The deal's rows go back to the plan."""
    choices = _use_the_new_value_for(use_the_new_value_for)
    return _write(db, request, "liquidity_construction_account_unlinked", bought_deal_id, preview_only,
                  lambda: construction_accounts_bl.unlink_construction_account(db, bought_deal_id, today, choices, preview_only))


@router.post("/liquidity/construction-accounts/{bought_deal_id}/switch-account", response_model=ConstructionAccountWriteRes)
def switch_liquidity_construction_account(bought_deal_id: str, data: ConstructionAccountSwitchReq, request: Request,
                                          preview_only: bool = PREVIEW_ONLY, today: Optional[date] = TODAY,
                                          use_the_new_value_for: Optional[List[str]] = USE_THE_NEW_VALUE_FOR,
                                          db: Session = Depends(get_db)):
    """Replace the deal's construction account mid-rehab. Refused (409) while the old account still holds money."""
    choices = _use_the_new_value_for(use_the_new_value_for)
    return _write(db, request, "liquidity_construction_account_switched", bought_deal_id, preview_only,
                  lambda: construction_accounts_bl.switch_construction_account(db, bought_deal_id, data, today, choices, preview_only))


@router.post("/liquidity/construction-accounts/{bought_deal_id}/manual-adjustments", response_model=ConstructionAccountWriteRes, status_code=201)
def add_liquidity_construction_account_manual_adjustment(bought_deal_id: str, data: ConstructionAccountManualAdjustmentReq, request: Request,
                                                         preview_only: bool = PREVIEW_ONLY, today: Optional[date] = TODAY,
                                                         use_the_new_value_for: Optional[List[str]] = USE_THE_NEW_VALUE_FOR,
                                                         db: Session = Depends(get_db)):
    """Record rehab money that never touched the construction account: a payment made from another account, by credit
    card or in cash (`manual_payment`), or a draw the lender wired elsewhere (`manual_draw`)."""
    choices = _use_the_new_value_for(use_the_new_value_for)
    return _write(db, request, "liquidity_construction_account_manual_adjustment_added", bought_deal_id, preview_only,
                  lambda: construction_accounts_bl.add_manual_adjustment(db, bought_deal_id, data, today, choices, preview_only),
                  adjustment_type=data.adjustment_type)


@router.put("/liquidity/construction-accounts/{bought_deal_id}/manual-adjustments/{adjustment_id}", response_model=ConstructionAccountWriteRes)
def update_liquidity_construction_account_manual_adjustment(bought_deal_id: str, adjustment_id: str, data: ConstructionAccountManualAdjustmentReq,
                                                            request: Request, preview_only: bool = PREVIEW_ONLY, today: Optional[date] = TODAY,
                                                            use_the_new_value_for: Optional[List[str]] = USE_THE_NEW_VALUE_FOR,
                                                            db: Session = Depends(get_db)):
    choices = _use_the_new_value_for(use_the_new_value_for)
    return _write(db, request, "liquidity_construction_account_manual_adjustment_updated", bought_deal_id, preview_only,
                  lambda: construction_accounts_bl.update_manual_adjustment(db, bought_deal_id, adjustment_id, data, today, choices, preview_only),
                  adjustment_type=data.adjustment_type)


@router.delete("/liquidity/construction-accounts/{bought_deal_id}/manual-adjustments/{adjustment_id}", response_model=ConstructionAccountWriteRes)
def delete_liquidity_construction_account_manual_adjustment(bought_deal_id: str, adjustment_id: str, request: Request,
                                                            preview_only: bool = PREVIEW_ONLY, today: Optional[date] = TODAY,
                                                            use_the_new_value_for: Optional[List[str]] = USE_THE_NEW_VALUE_FOR,
                                                            db: Session = Depends(get_db)):
    choices = _use_the_new_value_for(use_the_new_value_for)
    return _write(db, request, "liquidity_construction_account_manual_adjustment_deleted", bought_deal_id, preview_only,
                  lambda: construction_accounts_bl.delete_manual_adjustment(db, bought_deal_id, adjustment_id, today, choices, preview_only))


@router.put("/liquidity/construction-accounts/{bought_deal_id}/transactions/{mercury_transaction_id}/override",
            response_model=ConstructionAccountWriteRes)
def set_liquidity_construction_account_transaction_override(bought_deal_id: str, mercury_transaction_id: str,
                                                            data: ConstructionAccountTransactionOverrideReq, request: Request,
                                                            preview_only: bool = PREVIEW_ONLY, today: Optional[date] = TODAY,
                                                            use_the_new_value_for: Optional[List[str]] = USE_THE_NEW_VALUE_FOR,
                                                            db: Session = Depends(get_db)):
    """Ignore one bank transaction of the construction account, or count it in another category."""
    choices = _use_the_new_value_for(use_the_new_value_for)
    return _write(db, request, "liquidity_construction_account_transaction_override_set", bought_deal_id, preview_only,
                  lambda: construction_accounts_bl.set_transaction_override(db, bought_deal_id, mercury_transaction_id, data, today, choices, preview_only),
                  ignored=data.ignored, category_override=data.category_override)


@router.delete("/liquidity/construction-accounts/{bought_deal_id}/transactions/{mercury_transaction_id}/override",
               response_model=ConstructionAccountWriteRes)
def clear_liquidity_construction_account_transaction_override(bought_deal_id: str, mercury_transaction_id: str, request: Request,
                                                              preview_only: bool = PREVIEW_ONLY, today: Optional[date] = TODAY,
                                                              use_the_new_value_for: Optional[List[str]] = USE_THE_NEW_VALUE_FOR,
                                                              db: Session = Depends(get_db)):
    """Back to the transaction's automatic category."""
    choices = _use_the_new_value_for(use_the_new_value_for)
    return _write(db, request, "liquidity_construction_account_transaction_override_cleared", bought_deal_id, preview_only,
                  lambda: construction_accounts_bl.clear_transaction_override(db, bought_deal_id, mercury_transaction_id, today, choices, preview_only))


@router.post("/liquidity/construction-accounts/{bought_deal_id}/mark-ready-for-close-out", response_model=ConstructionAccountWriteRes)
def mark_liquidity_construction_account_ready_for_close_out(bought_deal_id: str, request: Request, preview_only: bool = PREVIEW_ONLY,
                                                            today: Optional[date] = TODAY,
                                                            use_the_new_value_for: Optional[List[str]] = USE_THE_NEW_VALUE_FOR,
                                                            db: Session = Depends(get_db)):
    """The rehab is over as far as this account goes, before the rehab-completed milestone is approved."""
    choices = _use_the_new_value_for(use_the_new_value_for)
    return _write(db, request, "liquidity_construction_account_marked_ready_for_close_out", bought_deal_id, preview_only,
                  lambda: construction_accounts_bl.mark_ready_for_close_out(db, bought_deal_id, today, choices, preview_only))


@router.post("/liquidity/construction-accounts/{bought_deal_id}/mark-closed-out", response_model=ConstructionAccountWriteRes)
def mark_liquidity_construction_account_closed_out(bought_deal_id: str, request: Request, preview_only: bool = PREVIEW_ONLY,
                                                   today: Optional[date] = TODAY,
                                                   use_the_new_value_for: Optional[List[str]] = USE_THE_NEW_VALUE_FOR,
                                                   db: Session = Depends(get_db)):
    """Close the account out without a transfer (you emptied it in Mercury): its return row is marked done."""
    choices = _use_the_new_value_for(use_the_new_value_for)
    return _write(db, request, "liquidity_construction_account_closed_out", bought_deal_id, preview_only,
                  lambda: construction_accounts_bl.mark_closed_out(db, bought_deal_id, today, choices, preview_only))


@router.post("/liquidity/construction-accounts/{bought_deal_id}/reopen", response_model=ConstructionAccountWriteRes)
def reopen_liquidity_construction_account(bought_deal_id: str, request: Request, preview_only: bool = PREVIEW_ONLY,
                                          today: Optional[date] = TODAY,
                                          use_the_new_value_for: Optional[List[str]] = USE_THE_NEW_VALUE_FOR,
                                          db: Session = Depends(get_db)):
    """Undo a close-out: the account is live again and its return row counts again."""
    choices = _use_the_new_value_for(use_the_new_value_for)
    return _write(db, request, "liquidity_construction_account_reopened", bought_deal_id, preview_only,
                  lambda: construction_accounts_bl.reopen_construction_account(db, bought_deal_id, today, choices, preview_only))


# --- Transfers: the app moves money (a passkey step-up each; never MCP tools) -----------------------------------

def _transfer(db: Session, request: Request, bought_deal_id: str, transfer_direction: str, data: ConstructionAccountTransferReq,
              preview_only: bool, today: Optional[date], use_the_new_value_for: Optional[List[str]]) -> ConstructionAccountTransferWriteRes:
    choices = _use_the_new_value_for(use_the_new_value_for)
    # The preview asks Mercury nothing; the transfer needs a person who just used their passkey.
    principal = None if preview_only else require_recent_auth(request, db)
    result = _run(db, lambda: construction_account_transfers_bl.make_construction_account_transfer(
        db, bought_deal_id, transfer_direction, data, today, choices, preview_only,
        requested_by_user_id=principal.user.id if principal else None), commit=not preview_only)
    if not preview_only and result.transfer is not None:
        audit("liquidity_construction_account_transfer", request, detail={
            "bought_deal_id": bought_deal_id, "transfer_direction": transfer_direction, "transfer_id": result.transfer.transfer_id,
            "transfer_outcome": result.transfer.transfer_outcome})
    return result


@router.post("/liquidity/construction-accounts/{bought_deal_id}/deposit", response_model=ConstructionAccountTransferWriteRes)
def deposit_into_liquidity_construction_account(bought_deal_id: str, data: ConstructionAccountTransferReq, request: Request,
                                                preview_only: bool = PREVIEW_ONLY, today: Optional[date] = TODAY,
                                                use_the_new_value_for: Optional[List[str]] = USE_THE_NEW_VALUE_FOR,
                                                db: Session = Depends(get_db)):
    """Move money from the LLC's primary checking into the deal's construction account, through Mercury."""
    return _transfer(db, request, bought_deal_id, TRANSFER_DIRECTION_DEPOSIT_INTO_CONSTRUCTION_ACCOUNT, data, preview_only, today,
                     use_the_new_value_for)


@router.post("/liquidity/construction-accounts/{bought_deal_id}/steal", response_model=ConstructionAccountTransferWriteRes)
def steal_from_liquidity_construction_account(bought_deal_id: str, data: ConstructionAccountTransferReq, request: Request,
                                              preview_only: bool = PREVIEW_ONLY, today: Optional[date] = TODAY,
                                              use_the_new_value_for: Optional[List[str]] = USE_THE_NEW_VALUE_FOR,
                                              db: Session = Depends(get_db)):
    """Move money from the deal's construction account back to the LLC's primary checking, through Mercury."""
    return _transfer(db, request, bought_deal_id, TRANSFER_DIRECTION_STEAL_TO_PRIMARY_CHECKING, data, preview_only, today,
                     use_the_new_value_for)
