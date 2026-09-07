"""/deals -- compact, cross-board views: list / word search, portfolio summary,
one deal in full. Added for the MCP tools (a chat cannot digest the full
board dumps), usable by the website too. Read-only."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db import get_db
from ReqRes.common.deals_schemas import DealDetail, DealSummary, PortfolioSummary
from BL.deals import compact

router = APIRouter()

BOARDS = ("all", "active", "bought")


def _check(board: str, deal_type: Optional[str]) -> None:
    if board not in BOARDS:
        raise HTTPException(status_code=400, detail="board must be 'all', 'active' or 'bought'")
    if deal_type is not None and deal_type not in ("BRRRR", "FLIP"):
        raise HTTPException(status_code=400, detail="deal_type must be 'BRRRR' or 'FLIP'")


@router.get("/deals", response_model=List[DealSummary])
def list_deals(
    board: str = Query("all", description="all | active (My Deals board) | bought (Bought Deals board)"),
    deal_type: Optional[str] = Query(None, description="BRRRR or FLIP"),
    stage: Optional[str] = Query(None, description="active stage number 1-5, or a bought pipeline stage id"),
    q: Optional[str] = Query(None, description="words to find in address, notes, task, niche or contact (all must match)"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    _check(board, deal_type)
    return compact.list_deals(db, board=board, deal_type=deal_type, stage=stage, q=q, limit=limit)


@router.get("/deals/search", response_model=List[DealSummary])
def search_deals(
    q: str = Query(..., min_length=1, description="words to find in address, notes, task, niche or contact"),
    board: str = Query("all"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    _check(board, None)
    return compact.list_deals(db, board=board, q=q, limit=limit)


@router.get("/deals/portfolio", response_model=PortfolioSummary)
def portfolio_summary(db: Session = Depends(get_db)):
    return compact.portfolio_summary(db)


@router.get("/deals/{deal_id}", response_model=DealDetail)
def get_deal(deal_id: str, db: Session = Depends(get_db)):
    found = compact.get_deal(db, deal_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Deal not found on either board")
    return found
