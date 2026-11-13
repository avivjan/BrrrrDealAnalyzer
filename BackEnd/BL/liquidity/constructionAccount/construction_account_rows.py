"""A Bought BRRRR deal's planned liquidity rows, with its linked construction account's live rows in place of the
schedule's two (tasks/todo/ConstructionAccountPerRehab.md).

Everything here works without Mercury: it reads the bank sums stored on the link at the last refresh. So a deal save,
a re-sync and a milestone change all see the same three rows the refresh wrote, and an outage changes nothing.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from BL.analyze.analyzeBRRR import compute_brrr_with_intermediates
from BL.liquidity.constructionAccount.construction_account_projection import (
    ConstructionAccountBankSums, ConstructionAccountProjection, ConstructionAccountProjectionInputs, project_construction_account,
)
from BL.liquidity.dealCashRows.deal_cash_rows import (
    CONSTRUCTION_ACCOUNT_DEPOSIT_ITEM_KEY, DEAL_BOARD_BOUGHT, ConstructionAccountLiveRowAmounts, DealBoard, PlannedDealCashRow,
    imported_rows_of_deal, planned_cash_rows_including_construction_account_live_amounts, planned_cash_rows_including_late_refi_months,
)
from DAL.crud.liquidity_construction_account import get_construction_account_of_deal, get_manual_adjustments_of_deal
from DAL.data_models.liquidity.construction_account_models import (
    MANUAL_ADJUSTMENT_TYPE_MANUAL_DRAW, MANUAL_ADJUSTMENT_TYPE_MANUAL_PAYMENT, LiquidityConstructionAccount,
)


def bank_sums_stored_on_the_link(link: LiquidityConstructionAccount) -> ConstructionAccountBankSums:
    return ConstructionAccountBankSums(
        current_balance_dollars=Decimal(link.bank_current_balance_dollars or 0),
        available_balance_dollars=Decimal(link.bank_available_balance_dollars or 0),
        bank_loan_draws_dollars=Decimal(link.bank_loan_draws_dollars or 0),
        bank_rehab_payments_dollars=Decimal(link.bank_rehab_payments_dollars or 0),
        own_money_transferred_into_the_account_dollars=Decimal(link.bank_own_money_transferred_into_the_account_dollars or 0),
        own_money_transferred_out_of_the_account_dollars=Decimal(link.bank_own_money_transferred_out_of_the_account_dollars or 0),
    )


# The schedule's `rehab_cushion` row before the construction account rows replaced it.
LEGACY_REHAB_CUSHION_ITEM_KEY = "rehab_cushion"


def deposit_row_of_deal_is_done(db: Session, bought_brrr_deal_id) -> bool:
    """The deposit row is marked done. A deal imported before the construction account rows has no deposit row yet:
    there, a `rehab_cushion` row already marked done stands for it (the cushion decision was made)."""
    rows = imported_rows_of_deal(db, DEAL_BOARD_BOUGHT, bought_brrr_deal_id)
    deposit_rows = [row for row in rows if row.source_item_key == CONSTRUCTION_ACCOUNT_DEPOSIT_ITEM_KEY]
    if deposit_rows:
        return any(row.done_at is not None for row in deposit_rows)
    return any(row.source_item_key == LEGACY_REHAB_CUSHION_ITEM_KEY and row.done_at is not None for row in rows)


def projection_of_linked_deal(db: Session, deal, link: LiquidityConstructionAccount,
                              bank_sums: Optional[ConstructionAccountBankSums] = None) -> ConstructionAccountProjection:
    """The projection from the deal as it is now (rehab cost, budget, cushion), the link's settings, the manual
    adjustments, and `bank_sums` (default: the ones stored on the link at the last refresh). `deal` is an ORM row or
    its attributes with some changed."""
    results = compute_brrr_with_intermediates(deal)
    manual_adjustments = get_manual_adjustments_of_deal(db, link.bought_brrr_deal_id)

    def manual_sum_of(adjustment_type: str) -> Decimal:
        return sum((Decimal(adjustment.amount_dollars) for adjustment in manual_adjustments
                    if adjustment.adjustment_type == adjustment_type), Decimal("0"))

    inputs = ConstructionAccountProjectionInputs(
        construction_budget_dollars=results.construction_budget,
        rehab_cost_dollars=results.rehab_cost,
        rehab_cushion_dollars=Decimal(deal.rehab_cushion or 0),
        loan_draws_pulled_before_construction_account_dollars=Decimal(link.loan_draws_pulled_before_construction_account_dollars or 0),
        rehab_payments_made_before_construction_account_dollars=Decimal(link.rehab_payments_made_before_construction_account_dollars or 0),
        manual_draw_adjustments_dollars=manual_sum_of(MANUAL_ADJUSTMENT_TYPE_MANUAL_DRAW),
        manual_payment_adjustments_dollars=manual_sum_of(MANUAL_ADJUSTMENT_TYPE_MANUAL_PAYMENT),
        minimum_balance_to_keep_in_construction_account_dollars=Decimal(link.minimum_balance_to_keep_in_construction_account_dollars or 0),
        deposit_row_is_done=deposit_row_of_deal_is_done(db, link.bought_brrr_deal_id),
        is_closed_out=link.closed_out_at is not None,
    )
    return project_construction_account(inputs, bank_sums if bank_sums is not None else bank_sums_stored_on_the_link(link))


def rehab_completed_date_of_deal(deal) -> date:
    return deal.buy_closing_date + timedelta(days=int(deal.days_until_rehab_completed))


def planned_cash_rows_of_deal_in_liquidity(db: Session, deal_board: DealBoard, deal, today: date) -> list[PlannedDealCashRow]:
    """The rows a re-sync aims for: the deal's schedule (with the late-refi months), and for a Bought deal with a
    linked construction account, that account's live rows in place of the schedule's two."""
    planned_rows = planned_cash_rows_including_late_refi_months(deal, today)
    if deal_board != DEAL_BOARD_BOUGHT:
        return planned_rows
    link = get_construction_account_of_deal(db, deal.id)
    if link is None:
        return planned_rows
    projection = projection_of_linked_deal(db, deal, link)
    live_amounts = ConstructionAccountLiveRowAmounts(
        deposit_row_amount_dollars=projection.deposit_row_amount_dollars,
        return_row_amount_dollars=projection.return_row_amount_dollars,
        top_up_needed_dollars=projection.top_up_needed_dollars,
    )
    return planned_cash_rows_including_construction_account_live_amounts(
        planned_rows, live_amounts, purchase_closing_date=deal.buy_closing_date,
        rehab_completed_date=rehab_completed_date_of_deal(deal), today=today)
