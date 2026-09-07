"""Compact views over both deal boards: list / word search, portfolio summary, one
deal in full. Built on the existing full responses (BL.common.deal_response), so
every number is the same one the website shows; this module only projects,
filters and ranks. A few hundred deals is small, so it all happens in Python."""

from __future__ import annotations

import uuid
from collections import Counter
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from BL.activeDeal.getActiveDeals import get_active_deals
from BL.boughtDeal.getBoughtDeals import get_bought_deals
from BL.common.deal_response import create_bought_deal_response, create_deal_response
from DAL.crud.active_deal import get_brrr_deal, get_flip_deal
from DAL.data_models import BoughtBrrrDeal, BoughtFlipDeal
from ReqRes.common.deals_schemas import DealDetail, DealSummary, PortfolioSummary, TopDeal

SEARCH_FIELDS = ("address", "notes", "task", "niche", "contact", "overall_design", "crime_rate")
NOT_APPLICABLE = (-1, -2)   # the calculators encode "infinite" / "no cash left in" this way


def _num(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metric(value):
    """A metric for ranking: None when missing or when the calculator's -1/-2 sentinels."""
    number = _num(value)
    return None if number is None or number in NOT_APPLICABLE else number


def summarize(deal, board: str) -> DealSummary:
    is_brrr = deal.deal_type == "BRRRR"
    return DealSummary(
        id=deal.id, board=board, deal_type=deal.deal_type, address=deal.address or "",
        stage=getattr(deal, "stage", None), section=getattr(deal, "section", None),
        bought_stage=getattr(deal, "bought_stage", None), task=getattr(deal, "task", None),
        purchase_price_k=_num(deal.purchase_price_in_thousands),
        rehab_cost_k=_num(deal.rehab_cost_in_thousands),
        arv_or_sale_price_k=_num(deal.arv_in_thousands if is_brrr else deal.sale_price_in_thousands),
        rent_monthly=_num(getattr(deal, "rent", None)),
        cash_flow_monthly=_num(getattr(deal, "cash_flow", None)),
        cash_on_cash_pct=_num(getattr(deal, "cash_on_cash", None)),
        roi_pct=_num(getattr(deal, "roi", None)),
        equity=_num(getattr(deal, "equity", None)),
        net_profit=_num(getattr(deal, "net_profit", None)),
        total_cash_needed=_num(getattr(deal, "total_cash_needed_for_deal", None)
                               if is_brrr else getattr(deal, "total_cash_needed", None)),
        cash_out=_num(getattr(deal, "cash_out", None)),
        cash_left_in_deal=_left_in(_num(getattr(deal, "cash_out", None))),
        cash_wire_at_refi=_num(getattr(deal, "cash_out_routi", None)),
        created_at=deal.created_at, updated_at=deal.updated_at,
    )


def _left_in(cash_out):
    """Money still in the deal: the negative part of cash_out, never negative."""
    if cash_out is None:
        return None
    return round(-cash_out, 2) if cash_out < 0 else 0.0


def _words(q: Optional[str]) -> list[str]:
    return [w for w in (q or "").lower().split() if w]


def _matches(deal, words: list[str]) -> bool:
    haystack = " ".join(str(getattr(deal, f, "") or "") for f in SEARCH_FIELDS).lower()
    return all(w in haystack for w in words)


def _all_deals(db: Session, board: str) -> list[tuple[object, str]]:
    deals: list[tuple[object, str]] = []
    if board in ("active", "all"):
        deals += [(d, "active") for d in get_active_deals(db)]
    if board in ("bought", "all"):
        deals += [(d, "bought") for d in get_bought_deals(db)]
    return deals


def list_deals(db: Session, *, board: str = "all", deal_type: Optional[str] = None,
               stage: Optional[str] = None, q: Optional[str] = None, limit: int = 50) -> list[DealSummary]:
    words = _words(q)
    rows = []
    for deal, where in _all_deals(db, board):
        if deal_type and deal.deal_type != deal_type:
            continue
        if stage is not None and str(getattr(deal, "stage", None)) != str(stage) \
                and str(getattr(deal, "bought_stage", None)) != str(stage):
            continue
        if words and not _matches(deal, words):
            continue
        rows.append(summarize(deal, where))
    rows.sort(key=lambda r: (r.created_at is None, r.created_at), reverse=True)
    return rows[:limit]


def _top(rows: Iterable[DealSummary], attr: str, n: int = 3) -> list[TopDeal]:
    ranked = [(r, _metric(getattr(r, attr))) for r in rows]
    ranked = [(r, v) for r, v in ranked if v is not None]
    ranked.sort(key=lambda rv: rv[1], reverse=True)
    return [TopDeal(id=r.id, board=r.board, deal_type=r.deal_type, address=r.address, value=v)
            for r, v in ranked[:n]]


def portfolio_summary(db: Session) -> PortfolioSummary:
    active = [summarize(d, "active") for d in get_active_deals(db)]
    bought = [summarize(d, "bought") for d in get_bought_deals(db)]
    total = lambda rows, attr: round(sum(_metric(getattr(r, attr)) or 0.0 for r in rows), 2)  # noqa: E731
    return PortfolioSummary(
        active_count=len(active), bought_count=len(bought),
        active_by_type=dict(Counter(r.deal_type for r in active)),
        bought_by_type=dict(Counter(r.deal_type for r in bought)),
        active_by_stage=dict(Counter(str(r.stage) for r in active)),
        bought_by_stage=dict(Counter(str(r.bought_stage) for r in bought)),
        bought_total_equity=total(bought, "equity"),
        bought_total_cash_flow_monthly=total(bought, "cash_flow_monthly"),
        bought_total_cash_invested=total(bought, "total_cash_needed"),
        bought_total_net_profit=total(bought, "net_profit"),
        top_bought_by_equity=_top(bought, "equity"),
        top_bought_by_cash_flow=_top(bought, "cash_flow_monthly"),
        top_bought_by_cash_on_cash=_top(bought, "cash_on_cash_pct"),
        top_active_by_cash_on_cash=_top(active, "cash_on_cash_pct"),
    )


def get_deal(db: Session, deal_id: str) -> Optional[DealDetail]:
    """Find one deal by id on either board (BRRRR or FLIP); None when nowhere."""
    try:
        uuid.UUID(str(deal_id))
    except ValueError:
        return None
    for finder in (get_brrr_deal, get_flip_deal):
        row = finder(db, deal_id)
        if row is not None:
            return DealDetail(board="active", deal=create_deal_response(row))
    for model in (BoughtBrrrDeal, BoughtFlipDeal):
        row = db.query(model).filter(model.id == deal_id).first()
        if row is not None:
            return DealDetail(board="bought", deal=create_bought_deal_response(row))
    return None
