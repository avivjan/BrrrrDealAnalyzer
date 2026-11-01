"""/liquidity/deals/* -- a BRRRR deal's Cash Needed rows in the liquidity timeline (tasks/todo/DealCashInLiquidity.md).

Import (after a preview), re-sync, milestone approvals written back to the deal, the late-refi months, and the open
rows of a dead deal. Every write is audited (which deal, how many rows), never an amount.
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from db import get_db
from BL.auth.common.audit import record as audit
from BL.liquidity.dealCashRows.liquidity_deals import (
    DealImportedThroughItsBoughtCopyError, LiquidityDealNotFoundError, apply_milestone_change as apply_milestone_change_bl,
    import_deal as import_deal_bl, list_imported_deals as list_imported_deals_bl,
    preview_deal_import as preview_deal_import_bl, preview_milestone_change as preview_milestone_change_bl,
    refresh_late_refis as refresh_late_refis_bl, remove_open_rows_of_deal as remove_open_rows_of_deal_bl,
)
from ReqRes.common.liquidity_deal_schemas import (
    DealCashRowChangesRes, DealCashRowsImportReq, DealMilestoneChangeReq, ImportedLiquidityDealRes, LateRefiRefreshReq,
    LateRefiRefreshRes, LiquidityDealBoard, RemoveOpenDealRowsReq, RemoveOpenDealRowsRes,
)

router = APIRouter()

_DEAL_NOT_FOUND = "BRRRR deal not found on that board"
_IMPORTED_THROUGH_ITS_BOUGHT_COPY = "This deal is in liquidity through its Bought copy: import or re-sync the Bought deal instead"


def _run_on_deal(action):
    try:
        return action()
    except LiquidityDealNotFoundError:
        raise HTTPException(status_code=404, detail=_DEAL_NOT_FOUND)
    except DealImportedThroughItsBoughtCopyError:
        raise HTTPException(status_code=409, detail=_IMPORTED_THROUGH_ITS_BOUGHT_COPY)


def _audit_changes(event: str, request: Request, result: DealCashRowChangesRes, **extra) -> None:
    audit(event, request, detail={"deal_board": result.deal_board, "deal_id": result.deal_id,
                                  "change_counts": result.change_counts.model_dump(), **extra})


@router.get("/liquidity/deals", response_model=List[ImportedLiquidityDealRes])
def list_liquidity_deals(today: Optional[date] = None, db: Session = Depends(get_db)):
    return list_imported_deals_bl(db, today)


@router.post("/liquidity/deals/refresh-late-refis", response_model=LateRefiRefreshRes)
def refresh_liquidity_late_refis(data: LateRefiRefreshReq, request: Request, db: Session = Depends(get_db)):
    result = refresh_late_refis_bl(db, data.today)
    if result.added_row_count:
        audit("liquidity_late_refi_rows_added", request, detail={
            "added_row_count": result.added_row_count, "deal_ids": [deal.deal_id for deal in result.deals_with_added_rows]})
    return result


@router.post("/liquidity/deals/{deal_board}/{deal_id}/import-preview", response_model=DealCashRowChangesRes)
def preview_liquidity_deal_import(deal_board: LiquidityDealBoard, deal_id: str, data: DealCashRowsImportReq, db: Session = Depends(get_db)):
    return _run_on_deal(lambda: preview_deal_import_bl(db, deal_board, deal_id, data.use_deal_value_for, data.today))


@router.post("/liquidity/deals/{deal_board}/{deal_id}/import", response_model=DealCashRowChangesRes)
def import_liquidity_deal(deal_board: LiquidityDealBoard, deal_id: str, data: DealCashRowsImportReq, request: Request,
                          db: Session = Depends(get_db)):
    result = _run_on_deal(lambda: import_deal_bl(db, deal_board, deal_id, data.use_deal_value_for, data.today))
    _audit_changes("liquidity_deal_imported", request, result)
    return result


@router.post("/liquidity/deals/{deal_board}/{deal_id}/milestones/preview", response_model=DealCashRowChangesRes)
def preview_liquidity_deal_milestone_change(deal_board: LiquidityDealBoard, deal_id: str, data: DealMilestoneChangeReq,
                                            db: Session = Depends(get_db)):
    return _run_on_deal(lambda: preview_milestone_change_bl(db, deal_board, deal_id, data))


@router.post("/liquidity/deals/{deal_board}/{deal_id}/milestones/apply", response_model=DealCashRowChangesRes)
def apply_liquidity_deal_milestone_change(deal_board: LiquidityDealBoard, deal_id: str, data: DealMilestoneChangeReq, request: Request,
                                          db: Session = Depends(get_db)):
    result = _run_on_deal(lambda: apply_milestone_change_bl(db, deal_board, deal_id, data))
    _audit_changes("liquidity_deal_milestone_changed", request, result, milestone=data.milestone,
                   new_date=data.new_date.isoformat(), approve=data.approve)
    return result


@router.post("/liquidity/deals/{deal_board}/{deal_id}/remove-open-rows", response_model=RemoveOpenDealRowsRes)
def remove_liquidity_deal_open_rows(deal_board: LiquidityDealBoard, deal_id: str, data: RemoveOpenDealRowsReq, request: Request,
                                    db: Session = Depends(get_db)):
    result = _run_on_deal(lambda: remove_open_rows_of_deal_bl(db, deal_board, deal_id, data.earnest_money_refund_date))
    audit("liquidity_deal_open_rows_removed", request, detail={
        "deal_board": deal_board, "deal_id": deal_id, "removed_row_count": result.removed_row_count,
        "earnest_money_refunded": result.earnest_money_refund_transaction_id is not None})
    return result
