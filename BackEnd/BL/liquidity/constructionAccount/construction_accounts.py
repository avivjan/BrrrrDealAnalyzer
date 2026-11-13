"""The /liquidity/construction-accounts/* business logic (tasks/todo/ConstructionAccountPerRehab.md): link a Mercury
construction account to a Bought BRRRR deal at any stage of its rehab, edit the deal's rehab figures, correct the bank
feed by hand (baselines, manual payments and draws, per-transaction overrides), switch or close out the account, and
keep the deal's liquidity rows in step with it.

**Nothing here commits.** Every write answers what it changes (the deal's status before -> after and its liquidity rows
before -> after); the router commits it, or rolls it back for a `preview_only` call. That answer is the confirmation
prompt, so a change to the timeline is never silent and never waits passively.

Mercury is read through the shared, paced reader (`BL/liquidity/common/mercury_reads.py`), never written here. Every
number can be recomputed without Mercury from the bank sums stored on the link at the last read, so an outage leaves
the rows as they are.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Callable, Iterable, Optional

from sqlalchemy.orm import Session

from BL.analyze.analyzeBRRR import compute_brrr_with_intermediates
from BL.analyze.common.validation import validate_brrr_inputs_for_saved_deal
from BL.liquidity.common import mercury_reads
from BL.liquidity.common.mercury_transfers import fetch_transfer_approval_request_status
from BL.liquidity.common.mercury_client import (
    ACTIVE_ACCOUNT_STATUSES, MercuryApiError, MercuryConfigError, MercurySlowDownError, fetch_account_transactions,
)
from BL.liquidity.common.mercury_token_names import (
    READ_TOKEN_ENVIRONMENT_VARIABLE_NAME_PATTERN, TRANSFER_TOKEN_ENVIRONMENT_VARIABLE_NAME_PATTERN,
    read_token_environment_variable_name, transfer_token_environment_variable_name, workspace_has_a_transfer_token,
    workspace_labels_with_a_transfer_token,
)
from BL.liquidity.constructionAccount.construction_account_projection import (
    CategorisedConstructionAccountTransaction, ConstructionAccountBankTransaction, ConstructionAccountProjection,
    ConstructionAccountTransactionOverride, InAppTransferToMatch, bank_feed_details_of, categorise_transactions,
    match_in_app_transfers_to_the_bank_feed, sum_categorised_transactions,
)
from BL.liquidity.constructionAccount.construction_account_transfer_settings import transfer_figures_of_link
from BL.liquidity.constructionAccount.construction_account_rows import (
    bank_sums_stored_on_the_link, planned_cash_rows_of_deal_in_liquidity, projection_of_linked_deal, rehab_completed_date_of_deal,
)
from BL.liquidity.dealCashRows.deal_cash_rows import (
    CONSTRUCTION_ACCOUNT_DEPOSIT_ITEM_KEY, CONSTRUCTION_ACCOUNT_ITEM_KEYS, CONSTRUCTION_ACCOUNT_RETURN_ITEM_KEY,
    CONSTRUCTION_ACCOUNT_TOP_UP_ITEM_KEY, DEAL_BOARD_BOUGHT, DealCashRowChange, apply_deal_cash_row_changes, deal_as_attributes,
    imported_rows_of_deal, refi_closing_date_of_deal,
)
from BL.liquidity.dealCashRows.liquidity_deals import (
    LiquidityDealNotFoundError, carry_a_done_legacy_cushion_over_to_the_deposit_row, deal_cash_row_changes_res, find_brrr_deal,
    today_for_liquidity, use_deal_value_for_pairs,
)
from BL.liquidity.mercuryBalance import mercury_balance_from_workspace_reads
from DAL.crud.liquidity_construction_account import (
    delete_everything_of_deal, get_all_construction_accounts, get_construction_account_by_mercury_account_id,
    get_construction_account_of_deal, get_manual_adjustment, get_manual_adjustments_of_deal, get_transaction_override,
    get_transaction_overrides_of_deal, get_transfers_of_construction_account,
)
from DAL.data_models import BoughtBrrrDeal, LiquidityTransaction
from DAL.data_models.common.brrr_lifecycle import BrrrLifecycleColumns
from DAL.data_models.liquidity.construction_account_models import (
    TRANSFER_DIRECTION_DEPOSIT_INTO_CONSTRUCTION_ACCOUNT, TRANSFER_OUTCOME_FAILED_OR_CANCELLED_AT_MERCURY, TRANSFER_OUTCOME_ACCEPTED_BY_MERCURY,
    TRANSFER_OUTCOME_WAITING_FOR_APPROVAL_IN_MERCURY, TRANSFER_OUTCOMES_THAT_COUNT,
    LiquidityConstructionAccount, LiquidityConstructionAccountManualAdjustment, LiquidityConstructionAccountTransactionOverride,
)
from DAL.data_models.liquidity.mercury_models import LiquidityMercuryWebhook, LiquidityMercuryWorkspaceRead
from ReqRes.common.liquidity_construction_account_schemas import (
    ConstructionAccountDatedAmountRes, ConstructionAccountLinkReq, ConstructionAccountListRes, ConstructionAccountManualAdjustmentReq,
    ConstructionAccountManualAdjustmentRes, ConstructionAccountPayeeTotalRes, ConstructionAccountRefreshRes,
    ConstructionAccountRehabFiguresReq, ConstructionAccountStatusRes, ConstructionAccountSumBySourceRes,
    ConstructionAccountSwitchPreviewRes, ConstructionAccountSwitchReq, ConstructionAccountTimelineRowRes,
    ConstructionAccountTotalsRes, ConstructionAccountTransactionOverrideReq, ConstructionAccountTransactionRes,
    ConstructionAccountWriteRes, MercuryAccountNameRes, MercuryConnectionStatusRes, MercuryLastChangeRes, MercuryWorkspaceConnectionRes,
)
from ReqRes.common.liquidity_deal_schemas import UseDealValueForField

logger = logging.getLogger(__name__)

ONE_CENT = Decimal("0.01")
DOLLARS_PER_THOUSAND = Decimal("1000")
# The deal columns keep thousands with 4 decimals: to the dime, like the deal form.
THOUSANDS_PRECISION = Decimal("0.0001")
APPLIANCES_ITEM_KEY = "appliances"
TIMELINE_ROW_ITEM_KEYS_SHOWN_ON_THE_CARD = (CONSTRUCTION_ACCOUNT_DEPOSIT_ITEM_KEY, CONSTRUCTION_ACCOUNT_RETURN_ITEM_KEY,
                                            CONSTRUCTION_ACCOUNT_TOP_UP_ITEM_KEY, APPLIANCES_ITEM_KEY)
ROW_CHANGE_KINDS_THAT_WRITE = {"added", "updated", "removed"}


class ConstructionAccountDealNotFoundError(Exception):
    """No Bought BRRRR deal with that id."""


class ConstructionAccountNotLinkedError(Exception):
    """The deal has no construction account linked."""


class ConstructionAccountNotFoundError(Exception):
    """No such manual adjustment / bank transaction on that deal's construction account."""


class ConstructionAccountValidationError(Exception):
    """The request cannot be applied as it is (the message is safe to show)."""


class ConstructionAccountConflictError(Exception):
    """The request conflicts with the current state (the message is safe to show)."""


class MercuryUnavailableError(Exception):
    """Mercury did not answer, and this action needs it."""


def _dollars(amount) -> Decimal:
    return Decimal(str(amount or 0)).quantize(ONE_CENT)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _find_bought_deal(db: Session, bought_deal_id: str) -> BoughtBrrrDeal:
    try:
        return find_brrr_deal(db, DEAL_BOARD_BOUGHT, bought_deal_id)
    except LiquidityDealNotFoundError:
        raise ConstructionAccountDealNotFoundError()


def _find_linked(db: Session, bought_deal_id: str) -> tuple[BoughtBrrrDeal, LiquidityConstructionAccount]:
    deal = _find_bought_deal(db, bought_deal_id)
    link = get_construction_account_of_deal(db, deal.id)
    if link is None:
        raise ConstructionAccountNotLinkedError()
    return deal, link


def _deal_of_link(db: Session, link: LiquidityConstructionAccount) -> Optional[BoughtBrrrDeal]:
    return db.query(BoughtBrrrDeal).filter(BoughtBrrrDeal.id == link.bought_brrr_deal_id).first()


# --- Mercury (read only, through the shared pace) -----------------------------------------------------------------

def _accounts_by_id_from_workspace_reads(db: Session, workspace_reads: list[mercury_reads.WorkspaceReadResult]) -> Optional[dict[str, dict]]:
    """Every account by id (with `is_counted_as_cash`), or None while no workspace has anything to show."""
    try:
        return {account["id"]: account for account in mercury_balance_from_workspace_reads(db, workspace_reads)["accounts"]}
    except MercuryApiError:
        return None


def _accounts_by_id(db: Session, want_fresh: bool) -> Optional[dict[str, dict]]:
    try:
        return _accounts_by_id_from_workspace_reads(db, mercury_reads.read_every_workspace(db, want_fresh=want_fresh))
    except MercuryConfigError:
        return None


def _required_accounts_by_id(db: Session, want_fresh: bool = False) -> dict[str, dict]:
    accounts_by_id = _accounts_by_id(db, want_fresh)
    if accounts_by_id is None:
        raise MercuryUnavailableError()
    return accounts_by_id


def _categorised_transactions_of_link(db: Session, link: LiquidityConstructionAccount, use_cache: bool,
                                      ) -> tuple[list[dict], list[CategorisedConstructionAccountTransaction]]:
    """The construction account's bank transactions, raw and categorised with the deal's overrides. A "slow down"
    answer puts the whole workspace in back-off. Raises `MercuryUnavailableError`."""
    try:
        raw_transactions = fetch_account_transactions(link.mercury_workspace_label, link.construction_mercury_account_id, use_cache=use_cache)
    except MercurySlowDownError as slow_down:
        mercury_reads.record_slow_down(mercury_reads.workspace_read_row(db, link.mercury_workspace_label), slow_down, _utc_now())
        raise MercuryUnavailableError()
    except (MercuryConfigError, MercuryApiError):
        raise MercuryUnavailableError()
    override_by_id = {
        override.mercury_transaction_id: ConstructionAccountTransactionOverride(
            ignored=bool(override.ignored), category_override=override.category_override, note=override.note)
        for override in get_transaction_overrides_of_deal(db, link.bought_brrr_deal_id)
    }
    transactions = [ConstructionAccountBankTransaction(
        mercury_transaction_id=raw["id"], transaction_date=raw["transaction_date"], counterparty_name=raw["counterparty_name"],
        signed_amount_dollars=raw["signed_amount_dollars"], is_internal_transfer=raw["is_internal_transfer"],
        is_failed_or_cancelled=raw["is_failed_or_cancelled"], is_pending=raw.get("is_pending", False)) for raw in raw_transactions]
    return raw_transactions, categorise_transactions(transactions, override_by_id)


def _bank_sums_tuple(link: LiquidityConstructionAccount) -> tuple:
    return (link.bank_current_balance_dollars, link.bank_available_balance_dollars, link.bank_loan_draws_dollars,
            link.bank_rehab_payments_dollars, link.bank_own_money_transferred_into_the_account_dollars,
            link.bank_own_money_transferred_out_of_the_account_dollars)


def _read_the_bank_into_the_link(db: Session, link: LiquidityConstructionAccount, accounts_by_id: Optional[dict[str, dict]],
                                 use_cached_transactions: bool) -> bool:
    """Store the account's balance, its categorised sums and the page's bank details on the link. False (nothing
    changed) while Mercury cannot tell. The balance comes from `accounts_by_id` (a paced read): no extra accounts call."""
    if accounts_by_id is None or link.construction_mercury_account_id not in accounts_by_id:
        return False
    try:
        _raw_transactions, categorised = _categorised_transactions_of_link(db, link, use_cache=use_cached_transactions)
    except MercuryUnavailableError:
        return False
    _match_the_in_app_transfers_to_the_bank_feed(db, link, [entry.transaction for entry in categorised])
    account = accounts_by_id[link.construction_mercury_account_id]
    bank_sums = sum_categorised_transactions(_dollars(account["current_balance_dollars"]), _dollars(account["available_balance_dollars"]), categorised)
    link.bank_current_balance_dollars = bank_sums.current_balance_dollars
    link.bank_available_balance_dollars = bank_sums.available_balance_dollars
    link.bank_loan_draws_dollars = bank_sums.bank_loan_draws_dollars
    link.bank_rehab_payments_dollars = bank_sums.bank_rehab_payments_dollars
    link.bank_own_money_transferred_into_the_account_dollars = bank_sums.own_money_transferred_into_the_account_dollars
    link.bank_own_money_transferred_out_of_the_account_dollars = bank_sums.own_money_transferred_out_of_the_account_dollars
    checking_account = accounts_by_id.get(link.primary_checking_mercury_account_id)
    link.bank_feed_details_as_of_last_refresh = {
        **bank_feed_details_of(categorised),
        "primary_checking_available_balance_dollars": (str(_dollars(checking_account["available_balance_dollars"]))
                                                        if checking_account is not None else None),
    }
    link.bank_amounts_as_of = _utc_now()
    _store_account_names(link, accounts_by_id)
    return True


def _match_the_in_app_transfers_to_the_bank_feed(db: Session, link: LiquidityConstructionAccount,
                                                 transactions: list[ConstructionAccountBankTransaction]) -> None:
    """An in-app transfer the feed now shows stops counting on its own (the feed counts it): each counts once. One the
    feed shows as failed or cancelled stops counting at all."""
    transfers = get_transfers_of_construction_account(db, link.bought_brrr_deal_id, link.construction_mercury_account_id)
    waiting = [transfer for transfer in transfers if transfer.seen_in_the_bank_feed_at is None
               and transfer.transfer_outcome in (*TRANSFER_OUTCOMES_THAT_COUNT, TRANSFER_OUTCOME_WAITING_FOR_APPROVAL_IN_MERCURY)]
    if not waiting:
        return
    matched = match_in_app_transfers_to_the_bank_feed(
        [InAppTransferToMatch(
            transfer_id=str(transfer.id), mercury_transfer_id=transfer.mercury_transfer_id,
            signed_amount_dollars=(Decimal(transfer.amount_dollars) if transfer.transfer_direction == TRANSFER_DIRECTION_DEPOSIT_INTO_CONSTRUCTION_ACCOUNT
                                   else -Decimal(transfer.amount_dollars)),
            requested_on=transfer.requested_at.date()) for transfer in waiting],
        transactions,
        [transfer.mercury_transaction_id_in_the_bank_feed for transfer in transfers if transfer.mercury_transaction_id_in_the_bank_feed])
    for transfer in waiting:
        transaction = matched.get(str(transfer.id))
        if transaction is None:
            continue
        transfer.mercury_transaction_id_in_the_bank_feed = transaction.mercury_transaction_id
        transfer.seen_in_the_bank_feed_at = _utc_now()
        if transaction.is_failed_or_cancelled:
            transfer.transfer_outcome = TRANSFER_OUTCOME_FAILED_OR_CANCELLED_AT_MERCURY
        elif transfer.transfer_outcome == TRANSFER_OUTCOME_WAITING_FOR_APPROVAL_IN_MERCURY:
            transfer.transfer_outcome = TRANSFER_OUTCOME_ACCEPTED_BY_MERCURY   # approved and sent: the feed counts it


def _store_account_names(link: LiquidityConstructionAccount, accounts_by_id: dict[str, dict]) -> None:
    construction_account = accounts_by_id.get(link.construction_mercury_account_id)
    if construction_account is not None:
        link.construction_account_name = construction_account["name"][:200]
        link.construction_account_number_last_four = construction_account.get("account_number_last_four", "")[-4:]
    checking_account = accounts_by_id.get(link.primary_checking_mercury_account_id)
    if checking_account is not None:
        link.primary_checking_account_name = checking_account["name"][:200]
        link.primary_checking_account_number_last_four = checking_account.get("account_number_last_four", "")[-4:]


# --- The deal's liquidity rows ------------------------------------------------------------------------------------

def _open_row_of_item(db: Session, bought_brrr_deal_id, item_key: str) -> Optional[LiquidityTransaction]:
    return next((row for row in imported_rows_of_deal(db, DEAL_BOARD_BOUGHT, bought_brrr_deal_id)
                 if row.source_item_key == item_key and row.done_at is None), None)


def _mark_the_construction_rows_done_that_the_account_settled(db: Session, deal: BoughtBrrrDeal) -> list[str]:
    """The deposit row once the owner's own money in the account reaches the total to deposit; the return row once the
    account is closed out. Returns the descriptions of the rows marked done now. No commit."""
    link = get_construction_account_of_deal(db, deal.id)
    if link is None:
        return []
    projection = projection_of_linked_deal(db, deal, link)
    marked_done = []
    deposit_row = _open_row_of_item(db, deal.id, CONSTRUCTION_ACCOUNT_DEPOSIT_ITEM_KEY)
    if (deposit_row is not None and projection.total_to_deposit_dollars > 0
            and projection.own_money_transferred_into_the_account_dollars >= projection.total_to_deposit_dollars):
        deposit_row.done_at = _utc_now()
        marked_done.append(deposit_row.description)
    return_row = _open_row_of_item(db, deal.id, CONSTRUCTION_ACCOUNT_RETURN_ITEM_KEY)
    if return_row is not None and link.closed_out_at is not None:
        return_row.done_at = _utc_now()
        marked_done.append(return_row.description)
    db.flush()
    return marked_done


def sync_every_liquidity_row_of_deal(db: Session, deal: BoughtBrrrDeal, today: date,
                                     use_deal_value_for: frozenset = frozenset()) -> tuple[list[DealCashRowChange], list[str]]:
    """A confirmed write: the deal's whole set of rows is brought in step with the deal and its construction account,
    whatever was pending, and 'liquidity out of date' is cleared. (changes, descriptions of rows marked done). No commit."""
    if not imported_rows_of_deal(db, DEAL_BOARD_BOUGHT, deal.id):
        return [], []
    marked_done = _mark_the_construction_rows_done_that_the_account_settled(db, deal)
    changes = apply_deal_cash_row_changes(db, DEAL_BOARD_BOUGHT, deal.id, planned_cash_rows_of_deal_in_liquidity(db, DEAL_BOARD_BOUGHT, deal, today),
                                          use_deal_value_for)
    if carry_a_done_legacy_cushion_over_to_the_deposit_row(db, DEAL_BOARD_BOUGHT, deal.id, changes):
        marked_done.append("Deposit into the construction account (your cushion was already marked done)")
    deal.liquidity_rows_out_of_date = False
    db.flush()
    return changes, marked_done


def _write_the_bank_reported_construction_rows(db: Session, deal: BoughtBrrrDeal, today: date) -> tuple[list[DealCashRowChange], list[str]]:
    """A refresh (a poll or a webhook): only the deal's construction account rows move, as the bank reports. A deal
    whose other rows still wait for their confirmation prompt is left as it is: the prompt will show it all."""
    if not imported_rows_of_deal(db, DEAL_BOARD_BOUGHT, deal.id) or deal.liquidity_rows_out_of_date:
        return [], []
    marked_done = _mark_the_construction_rows_done_that_the_account_settled(db, deal)
    changes = apply_deal_cash_row_changes(db, DEAL_BOARD_BOUGHT, deal.id, planned_cash_rows_of_deal_in_liquidity(db, DEAL_BOARD_BOUGHT, deal, today),
                                          only_item_keys=CONSTRUCTION_ACCOUNT_ITEM_KEYS)
    db.flush()
    return changes, marked_done


def _is_a_top_up_date_only_move(change: DealCashRowChange) -> bool:
    """The top-up row moving to today, with its amount unchanged: the daily roll, not news."""
    return (change.item_key == CONSTRUCTION_ACCOUNT_TOP_UP_ITEM_KEY and change.change_kind == "updated"
            and change.amount_before == change.amount_after and change.date_before != change.date_after)


# --- The page -----------------------------------------------------------------------------------------------------

def _sum_by_source(from_the_bank_feed: Decimal, before_this_account: Decimal, entered_by_hand: Decimal, total: Decimal) -> ConstructionAccountSumBySourceRes:
    return ConstructionAccountSumBySourceRes(
        from_the_bank_feed_dollars=float(from_the_bank_feed), before_this_account_dollars=float(before_this_account),
        entered_by_hand_dollars=float(entered_by_hand), total_dollars=float(total))


def _manual_adjustment_res(adjustment: LiquidityConstructionAccountManualAdjustment) -> ConstructionAccountManualAdjustmentRes:
    return ConstructionAccountManualAdjustmentRes(
        id=str(adjustment.id), adjustment_type=adjustment.adjustment_type, amount_dollars=float(adjustment.amount_dollars),
        date=adjustment.date, note=adjustment.note)


def _dated_amount_res(stored: Optional[dict]) -> Optional[ConstructionAccountDatedAmountRes]:
    if not stored:
        return None
    return ConstructionAccountDatedAmountRes(date=date.fromisoformat(stored["date"]), amount_dollars=float(Decimal(stored["amount_dollars"])),
                                             counterparty_name=stored.get("counterparty_name") or "")


def _percent(part: Decimal, whole: Decimal) -> Optional[float]:
    return None if whole <= 0 else float((part / whole * 100).quantize(Decimal("0.1")))


def suggested_rehab_cushion_dollars() -> float:
    return float(BrrrLifecycleColumns.rehab_cushion.default.arg)


def status_of_deal(db: Session, deal: BoughtBrrrDeal, today: Optional[date] = None, mercury_is_unavailable: bool = False) -> ConstructionAccountStatusRes:
    resolved_today = today or today_for_liquidity(db, None)
    results = compute_brrr_with_intermediates(deal)
    link = get_construction_account_of_deal(db, deal.id)
    imported_rows = imported_rows_of_deal(db, DEAL_BOARD_BOUGHT, deal.id)
    rehab_cushion = Decimal(deal.rehab_cushion or 0)
    original_steal = results.construction_budget - results.rehab_cost
    rehab_beyond_the_budget = max(Decimal("0"), -original_steal)
    status = ConstructionAccountStatusRes(
        bought_deal_id=str(deal.id), deal_address=deal.address, deal_updated_at=deal.updated_at,
        is_linked=link is not None, is_in_the_liquidity_timeline=bool(imported_rows),
        liquidity_rows_are_out_of_date=bool(deal.liquidity_rows_out_of_date),
        actual_rehab_cost_dollars=float(Decimal(deal.rehab_cost_in_thousands or 0) * DOLLARS_PER_THOUSAND),
        rehab_contingency_percent=float(deal.rehab_contingency_percent or 0),
        rehab_cost_dollars=float(results.rehab_cost), construction_budget_dollars=float(results.construction_budget),
        original_steal_dollars=float(original_steal), rehab_cushion_dollars=float(rehab_cushion),
        suggested_rehab_cushion_dollars=suggested_rehab_cushion_dollars(),
        rehab_beyond_the_construction_budget_dollars=float(rehab_beyond_the_budget),
        total_to_deposit_dollars=float(rehab_cushion + rehab_beyond_the_budget),
        purchase_closing_date=deal.buy_closing_date, rehab_completed_date=rehab_completed_date_of_deal(deal),
        rehab_completed_is_approved=deal.rehab_completed_approved_at is not None,
        refi_closing_date=refi_closing_date_of_deal(deal), refi_closed_is_approved=deal.refi_closed_approved_at is not None,
        timeline_rows=[ConstructionAccountTimelineRowRes(
            item_key=row.source_item_key, transaction_id=str(row.id), description=row.description, effective_date=row.effective_date,
            amount_dollars=float(row.amount_dollars), is_done=row.done_at is not None,
            is_overdue=row.done_at is None and row.effective_date < resolved_today)
            for row in imported_rows if row.source_item_key in TIMELINE_ROW_ITEM_KEYS_SHOWN_ON_THE_CARD],
        appliances_dollars=float(deal.appliances or 0),
    )
    if link is None:
        return status
    projection: ConstructionAccountProjection = projection_of_linked_deal(db, deal, link)
    details = link.bank_feed_details_as_of_last_refresh or {}
    needs_attention_because = []
    if projection.remaining_deposit_dollars > 0 and deal.buy_closing_date <= resolved_today:
        needs_attention_because.append("deposit_due")
    if projection.top_up_needed_dollars > 0:
        needs_attention_because.append("top_up_needed")
    if mercury_is_unavailable:
        needs_attention_because.append("mercury_unavailable")
    return status.model_copy(update=dict(
        mercury_workspace_label=link.mercury_workspace_label,
        construction_account=MercuryAccountNameRes(
            mercury_account_id=link.construction_mercury_account_id, name=link.construction_account_name,
            account_number_last_four=link.construction_account_number_last_four),
        primary_checking_account=MercuryAccountNameRes(
            mercury_account_id=link.primary_checking_mercury_account_id, name=link.primary_checking_account_name,
            account_number_last_four=link.primary_checking_account_number_last_four),
        previous_construction_mercury_account_ids=[entry["mercury_account_id"] for entry in (link.previous_construction_mercury_account_ids or [])],
        amounts_as_of=link.bank_amounts_as_of, mercury_is_unavailable=mercury_is_unavailable,
        current_balance_dollars=float(projection.current_balance_dollars),
        available_balance_dollars=float(projection.available_balance_dollars),
        pending_money_in_dollars=float(Decimal(details.get("pending_money_in_dollars") or 0)),
        pending_money_out_dollars=float(Decimal(details.get("pending_money_out_dollars") or 0)),
        primary_checking_available_balance_dollars=(None if details.get("primary_checking_available_balance_dollars") is None
                                                    else float(Decimal(details["primary_checking_available_balance_dollars"]))),
        loan_draws_pulled=_sum_by_source(projection.bank_loan_draws_dollars, projection.loan_draws_pulled_before_construction_account_dollars,
                                         projection.manual_draw_adjustments_dollars, projection.loan_draws_pulled_dollars),
        loan_draws_remaining_to_pull_dollars=float(projection.loan_draws_remaining_to_pull_dollars),
        percent_of_the_construction_budget_pulled=_percent(projection.loan_draws_pulled_dollars, projection.construction_budget_dollars),
        loan_draw_count=details.get("loan_draw_count"),
        last_loan_draw=_dated_amount_res(details.get("last_loan_draw")),
        rehab_payments_made=_sum_by_source(projection.bank_rehab_payments_dollars, projection.rehab_payments_made_before_construction_account_dollars,
                                           projection.manual_payment_adjustments_dollars, projection.rehab_payments_made_dollars),
        unpaid_rehab_remaining_dollars=float(projection.unpaid_rehab_remaining_dollars),
        percent_of_the_rehab_paid=_percent(projection.rehab_payments_made_dollars, projection.rehab_cost_dollars),
        last_rehab_payment=_dated_amount_res(details.get("last_rehab_payment")),
        rehab_paid_by_payee=[ConstructionAccountPayeeTotalRes(payee_name=entry["payee_name"], amount_dollars=float(Decimal(entry["amount_dollars"])))
                             for entry in details.get("rehab_paid_by_payee") or []],
        own_money_transferred_into_the_account_dollars=float(projection.own_money_transferred_into_the_account_dollars),
        own_money_transferred_out_of_the_account_dollars=float(projection.own_money_transferred_out_of_the_account_dollars),
        own_money_still_in_the_account_dollars=float(projection.own_money_still_in_the_account_dollars),
        spread_already_taken_dollars=float(projection.spread_already_taken_dollars),
        remaining_deposit_dollars=float(projection.remaining_deposit_dollars),
        minimum_balance_to_keep_in_construction_account_dollars=float(link.minimum_balance_to_keep_in_construction_account_dollars or 0),
        projected_return_at_rehab_end_dollars=float(projection.projected_return_at_rehab_end_dollars),
        own_money_back_at_rehab_end_dollars=float(projection.own_money_back_at_rehab_end_dollars),
        spread_at_rehab_end_dollars=float(projection.spread_at_rehab_end_dollars),
        safe_to_steal_now_dollars=float(projection.safe_to_steal_now_dollars),
        safe_to_steal_now_is_capped_by=projection.safe_to_steal_now_is_capped_by,
        top_up_needed_dollars=float(projection.top_up_needed_dollars),
        loan_draws_pulled_before_construction_account_dollars=float(link.loan_draws_pulled_before_construction_account_dollars or 0),
        rehab_payments_made_before_construction_account_dollars=float(link.rehab_payments_made_before_construction_account_dollars or 0),
        transactions_counted_count=details.get("transactions_counted_count"),
        transactions_ignored_count=details.get("transactions_ignored_count"),
        transactions_recategorised_count=details.get("transactions_recategorised_count"),
        transactions_failed_or_cancelled_count=details.get("transactions_failed_or_cancelled_count"),
        last_transaction_date=date.fromisoformat(details["last_transaction_date"]) if details.get("last_transaction_date") else None,
        marked_ready_for_close_out_at=link.marked_ready_for_close_out_at, closed_out_at=link.closed_out_at,
        manual_adjustments=[_manual_adjustment_res(adjustment) for adjustment in get_manual_adjustments_of_deal(db, deal.id)],
        **transfer_figures_of_link(db, link),
        needs_attention_because=needs_attention_because,
    ))


def _deals_on_the_page(db: Session) -> list[BoughtBrrrDeal]:
    """Every Bought BRRRR deal in the liquidity timeline that is not refinanced yet, plus every linked deal, by address."""
    deal_ids_in_liquidity = {deal_id for (deal_id,) in db.query(LiquidityTransaction.source_deal_id)
                             .filter(LiquidityTransaction.source_deal_board == DEAL_BOARD_BOUGHT,
                                     LiquidityTransaction.source_deal_id.isnot(None)).distinct().all()}
    linked_deal_ids = {link.bought_brrr_deal_id for link in get_all_construction_accounts(db)}
    deals = [deal for deal in db.query(BoughtBrrrDeal).filter(BoughtBrrrDeal.id.in_(deal_ids_in_liquidity | linked_deal_ids)).all()
             if deal.id in linked_deal_ids or deal.refi_closed_approved_at is None]
    return sorted(deals, key=lambda deal: (deal.address or "", str(deal.id)))


def list_construction_accounts(db: Session) -> ConstructionAccountListRes:
    """The page: every deal's status and the totals across the live accounts. Never calls Mercury: the amounts are
    those of the last read (`amounts_as_of`)."""
    today = today_for_liquidity(db, None)
    statuses = [status_of_deal(db, deal, today) for deal in _deals_on_the_page(db)]
    live = [status for status in statuses if status.is_linked and status.closed_out_at is None]

    def total_of(field_name: str) -> float:
        return round(sum(getattr(status, field_name) or 0 for status in live), 2)

    return ConstructionAccountListRes(
        totals=ConstructionAccountTotalsRes(
            linked_account_count=len(live), current_balance_dollars=total_of("current_balance_dollars"),
            projected_return_at_rehab_end_dollars=total_of("projected_return_at_rehab_end_dollars"),
            safe_to_steal_now_dollars=total_of("safe_to_steal_now_dollars"),
            remaining_deposit_dollars=total_of("remaining_deposit_dollars"), top_up_needed_dollars=total_of("top_up_needed_dollars"),
            accounts_needing_attention_count=sum(1 for status in live if status.needs_attention_because)),
        accounts=statuses,
    )


# --- Every write: change, sync, answer before -> after ------------------------------------------------------------

@dataclass
class _WriteOutcome:
    """What an action reports besides its database changes."""
    mercury_is_unavailable: bool = False
    balance_left_in_the_account_dollars: Optional[Decimal] = None
    extra_rows_marked_done: list[str] = field(default_factory=list)


def _write(db: Session, deal: BoughtBrrrDeal, today: Optional[date], use_deal_value_for: Iterable[UseDealValueForField],
           preview_only: bool, action: Callable[[], Optional[_WriteOutcome]],
           status_before: Optional[ConstructionAccountStatusRes] = None) -> ConstructionAccountWriteRes:
    """Run one change and the full sync of the deal's rows, and answer before -> after. Nothing is committed here:
    the router commits a confirmed write and rolls a preview back. `status_before`: when the change already happened
    (a transfer Mercury answered), the status read before it."""
    resolved_today = today_for_liquidity(db, today)
    status_before = status_before or status_of_deal(db, deal, resolved_today)
    outcome = action() or _WriteOutcome()
    db.flush()
    changes, marked_done = sync_every_liquidity_row_of_deal(db, deal, resolved_today, use_deal_value_for_pairs(use_deal_value_for))
    marked_done = marked_done + outcome.extra_rows_marked_done
    db.flush()
    rows_change = any(change.change_kind in ROW_CHANGE_KINDS_THAT_WRITE for change in changes) or bool(marked_done)
    return ConstructionAccountWriteRes(
        was_preview_only=preview_only, status_before=status_before,
        status_after=status_of_deal(db, deal, resolved_today, outcome.mercury_is_unavailable),
        changes_the_liquidity_timeline=rows_change,
        liquidity_row_changes=deal_cash_row_changes_res(DEAL_BOARD_BOUGHT, deal, changes) if status_before.is_in_the_liquidity_timeline else None,
        row_descriptions_marked_done=marked_done,
        balance_left_in_the_account_dollars=(None if outcome.balance_left_in_the_account_dollars is None
                                             else float(outcome.balance_left_in_the_account_dollars)),
    )


# --- The rehab figures (written to the Bought deal) ---------------------------------------------------------------

def save_rehab_figures(db: Session, bought_deal_id: str, data: ConstructionAccountRehabFiguresReq, today: Optional[date],
                       use_deal_value_for: list[UseDealValueForField], preview_only: bool) -> ConstructionAccountWriteRes:
    """The deal's actual rehab cost, contingency, construction budget and rehab cushion, edited from its card: validated
    like a save of the deal, written to it (its `updated_at` moves, so an older deal form is refused), then synced."""
    deal = _find_bought_deal(db, bought_deal_id)
    changed_columns = {}
    if data.actual_rehab_cost_dollars is not None:
        changed_columns["rehab_cost_in_thousands"] = (Decimal(str(data.actual_rehab_cost_dollars)) / DOLLARS_PER_THOUSAND).quantize(THOUSANDS_PRECISION)
    if data.rehab_contingency_percent is not None:
        changed_columns["rehab_contingency_percent"] = Decimal(str(data.rehab_contingency_percent)).quantize(ONE_CENT)
    if data.construction_budget_dollars is not None:
        changed_columns["construction_loan_budget_in_thousands"] = (Decimal(str(data.construction_budget_dollars)) / DOLLARS_PER_THOUSAND).quantize(THOUSANDS_PRECISION)
    if data.rehab_cushion_dollars is not None:
        changed_columns["rehab_cushion"] = _dollars(data.rehab_cushion_dollars)
    validate_brrr_inputs_for_saved_deal(deal_as_attributes(deal, **changed_columns))

    def change_the_deal() -> None:
        for column_name, value in changed_columns.items():
            setattr(deal, column_name, value)
        deal.updated_at = _utc_now()

    return _write(db, deal, today, use_deal_value_for, preview_only, change_the_deal)


# --- Link, edit, unlink, switch -----------------------------------------------------------------------------------

def _validated_accounts(db: Session, deal: BoughtBrrrDeal, construction_mercury_account_id: str, primary_checking_mercury_account_id: str,
                        accounts_by_id: dict[str, dict]) -> dict:
    construction_account = accounts_by_id.get(construction_mercury_account_id)
    checking_account = accounts_by_id.get(primary_checking_mercury_account_id)
    if construction_account is None or checking_account is None:
        raise ConstructionAccountValidationError("That Mercury account was not found")
    if construction_mercury_account_id == primary_checking_mercury_account_id:
        raise ConstructionAccountValidationError("The construction account and the checking account must be two different accounts")
    if construction_account["status"] not in ACTIVE_ACCOUNT_STATUSES or checking_account["status"] not in ACTIVE_ACCOUNT_STATUSES:
        raise ConstructionAccountValidationError("Both accounts must be active")
    if construction_account["workspace"] != checking_account["workspace"]:
        raise ConstructionAccountValidationError("Both accounts must be in the same Mercury workspace (the same LLC)")
    link_of_that_account = get_construction_account_by_mercury_account_id(db, construction_mercury_account_id)
    if link_of_that_account is not None and link_of_that_account.bought_brrr_deal_id != deal.id:
        raise ConstructionAccountConflictError("That account is already the construction account of another deal")
    if get_construction_account_by_mercury_account_id(db, primary_checking_mercury_account_id) is not None:
        raise ConstructionAccountValidationError("The checking account cannot be another deal's construction account")
    if not checking_account.get("is_counted_as_cash"):
        raise ConstructionAccountValidationError("The checking account must be one of the accounts counted as cash in the liquidity settings")
    return construction_account


def save_construction_account_link(db: Session, bought_deal_id: str, data: ConstructionAccountLinkReq, today: Optional[date],
                                   use_deal_value_for: list[UseDealValueForField], preview_only: bool) -> ConstructionAccountWriteRes:
    """Link a construction account, or edit the link (baselines, checking, buffer to keep): always allowed. Changing
    the construction account itself goes through the switch, which carries its history over."""
    deal = _find_bought_deal(db, bought_deal_id)
    accounts_by_id = _required_accounts_by_id(db)
    construction_account = _validated_accounts(db, deal, data.construction_mercury_account_id, data.primary_checking_mercury_account_id, accounts_by_id)
    existing_link = get_construction_account_of_deal(db, deal.id)
    if existing_link is not None and existing_link.construction_mercury_account_id != data.construction_mercury_account_id:
        raise ConstructionAccountConflictError("To change the construction account itself, use Switch account")

    def link_or_edit() -> _WriteOutcome:
        link = existing_link
        if link is None:
            link = LiquidityConstructionAccount(bought_brrr_deal_id=deal.id, previous_construction_mercury_account_ids=[],
                                                construction_mercury_account_id=data.construction_mercury_account_id)
            db.add(link)
        link.mercury_workspace_label = construction_account["workspace"]
        link.primary_checking_mercury_account_id = data.primary_checking_mercury_account_id
        link.loan_draws_pulled_before_construction_account_dollars = _dollars(data.loan_draws_pulled_before_construction_account_dollars)
        link.rehab_payments_made_before_construction_account_dollars = _dollars(data.rehab_payments_made_before_construction_account_dollars)
        link.minimum_balance_to_keep_in_construction_account_dollars = _dollars(data.minimum_balance_to_keep_in_construction_account_dollars)
        _store_account_names(link, accounts_by_id)
        db.flush()
        read = existing_link is None or link.bank_amounts_as_of is None
        mercury_is_unavailable = read and not _read_the_bank_into_the_link(db, link, accounts_by_id, use_cached_transactions=True)
        return _WriteOutcome(mercury_is_unavailable=mercury_is_unavailable)

    return _write(db, deal, today, use_deal_value_for, preview_only, link_or_edit)


def unlink_construction_account(db: Session, bought_deal_id: str, today: Optional[date], use_deal_value_for: list[UseDealValueForField],
                                preview_only: bool) -> ConstructionAccountWriteRes:
    """Remove the link with its manual adjustments and overrides; the deal's rows go back to the schedule's plan."""
    deal, _link = _find_linked(db, bought_deal_id)
    return _write(db, deal, today, use_deal_value_for, preview_only, lambda: delete_everything_of_deal(db, deal.id))


def preview_construction_account_switch(db: Session, bought_deal_id: str) -> ConstructionAccountSwitchPreviewRes:
    """Reads the old account fresh (through the shared pace). The router commits that read: it changes no deal."""
    deal, link = _find_linked(db, bought_deal_id)
    if not _read_the_bank_into_the_link(db, link, _required_accounts_by_id(db, want_fresh=True), use_cached_transactions=False):
        raise MercuryUnavailableError()
    bank_sums = bank_sums_stored_on_the_link(link)
    return ConstructionAccountSwitchPreviewRes(
        old_construction_account_balance_dollars=float(bank_sums.current_balance_dollars),
        old_account_must_be_emptied_first=bank_sums.current_balance_dollars != 0,
        loan_draws_pulled_before_construction_account_dollars=float(
            Decimal(link.loan_draws_pulled_before_construction_account_dollars or 0) + bank_sums.bank_loan_draws_dollars),
        rehab_payments_made_before_construction_account_dollars=float(
            Decimal(link.rehab_payments_made_before_construction_account_dollars or 0) + bank_sums.bank_rehab_payments_dollars),
    )


def switch_construction_account(db: Session, bought_deal_id: str, data: ConstructionAccountSwitchReq, today: Optional[date],
                                use_deal_value_for: list[UseDealValueForField], preview_only: bool) -> ConstructionAccountWriteRes:
    """Replace the construction account mid-rehab: the old account must be empty, its draws and payments live on in the
    baselines the caller confirmed (prefilled by the preview), and it is kept in the history."""
    deal, link = _find_linked(db, bought_deal_id)
    if data.new_construction_mercury_account_id == link.construction_mercury_account_id:
        raise ConstructionAccountValidationError("That is already this deal's construction account")
    accounts_by_id = _required_accounts_by_id(db, want_fresh=True)
    if not _read_the_bank_into_the_link(db, link, accounts_by_id, use_cached_transactions=False):
        raise MercuryUnavailableError()
    if Decimal(link.bank_current_balance_dollars or 0) != 0:
        raise ConstructionAccountConflictError("Move the old construction account's balance to the new account first")
    _validated_accounts(db, deal, data.new_construction_mercury_account_id, link.primary_checking_mercury_account_id, accounts_by_id)

    def switch() -> _WriteOutcome:
        link.previous_construction_mercury_account_ids = [
            *(link.previous_construction_mercury_account_ids or []),
            {"mercury_account_id": link.construction_mercury_account_id, "switched_away_at": _utc_now().isoformat()},
        ]
        link.construction_mercury_account_id = data.new_construction_mercury_account_id
        link.loan_draws_pulled_before_construction_account_dollars = _dollars(data.loan_draws_pulled_before_construction_account_dollars)
        link.rehab_payments_made_before_construction_account_dollars = _dollars(data.rehab_payments_made_before_construction_account_dollars)
        db.flush()
        mercury_is_unavailable = not _read_the_bank_into_the_link(db, link, accounts_by_id, use_cached_transactions=False)
        return _WriteOutcome(mercury_is_unavailable=mercury_is_unavailable)

    return _write(db, deal, today, use_deal_value_for, preview_only, switch)


# --- Manual adjustments -------------------------------------------------------------------------------------------

def add_manual_adjustment(db: Session, bought_deal_id: str, data: ConstructionAccountManualAdjustmentReq, today: Optional[date],
                          use_deal_value_for: list[UseDealValueForField], preview_only: bool) -> ConstructionAccountWriteRes:
    deal, _link = _find_linked(db, bought_deal_id)
    return _write(db, deal, today, use_deal_value_for, preview_only, lambda: db.add(LiquidityConstructionAccountManualAdjustment(
        bought_brrr_deal_id=deal.id, adjustment_type=data.adjustment_type, amount_dollars=_dollars(data.amount_dollars),
        date=data.date, note=(data.note or None))))


def update_manual_adjustment(db: Session, bought_deal_id: str, adjustment_id: str, data: ConstructionAccountManualAdjustmentReq,
                             today: Optional[date], use_deal_value_for: list[UseDealValueForField], preview_only: bool) -> ConstructionAccountWriteRes:
    deal, _link = _find_linked(db, bought_deal_id)
    adjustment = get_manual_adjustment(db, deal.id, adjustment_id)
    if adjustment is None:
        raise ConstructionAccountNotFoundError()

    def change_it() -> None:
        adjustment.adjustment_type, adjustment.amount_dollars = data.adjustment_type, _dollars(data.amount_dollars)
        adjustment.date, adjustment.note = data.date, (data.note or None)

    return _write(db, deal, today, use_deal_value_for, preview_only, change_it)


def delete_manual_adjustment(db: Session, bought_deal_id: str, adjustment_id: str, today: Optional[date],
                             use_deal_value_for: list[UseDealValueForField], preview_only: bool) -> ConstructionAccountWriteRes:
    deal, _link = _find_linked(db, bought_deal_id)
    adjustment = get_manual_adjustment(db, deal.id, adjustment_id)
    if adjustment is None:
        raise ConstructionAccountNotFoundError()
    return _write(db, deal, today, use_deal_value_for, preview_only, lambda: db.delete(adjustment))


# --- Bank transactions and their overrides ------------------------------------------------------------------------

def list_construction_account_transactions(db: Session, bought_deal_id: str) -> list[ConstructionAccountTransactionRes]:
    """The construction account's bank transactions, newest first, each with its automatic and its effective category."""
    _deal, link = _find_linked(db, bought_deal_id)
    raw_transactions, categorised_transactions = _categorised_transactions_of_link(db, link, use_cache=True)
    bank_status_by_id = {raw["id"]: raw["status"] for raw in raw_transactions}
    return [ConstructionAccountTransactionRes(
        mercury_transaction_id=categorised.transaction.mercury_transaction_id,
        transaction_date=categorised.transaction.transaction_date, counterparty_name=categorised.transaction.counterparty_name,
        signed_amount_dollars=float(categorised.transaction.signed_amount_dollars),
        bank_status=bank_status_by_id.get(categorised.transaction.mercury_transaction_id, ""),
        is_pending=categorised.transaction.is_pending,
        automatic_category=categorised.automatic_category,
        ignored=bool(categorised.override and categorised.override.ignored),
        category_override=categorised.override.category_override if categorised.override else None,
        note=categorised.override.note if categorised.override else None,
        effective_category=categorised.effective_category,
    ) for categorised in reversed(categorised_transactions)]


def _recategorise_with_the_stored_balance(db: Session, link: LiquidityConstructionAccount) -> bool:
    """After an override: the same transactions, categorised again. The balance stays the one of the last read, so no
    accounts call is made; the transactions come from the cache when they are recent."""
    stored_balance_as_accounts = {
        link.construction_mercury_account_id: {"current_balance_dollars": link.bank_current_balance_dollars or 0,
                                               "available_balance_dollars": link.bank_available_balance_dollars or 0,
                                               "name": link.construction_account_name,
                                               "account_number_last_four": link.construction_account_number_last_four},
    }
    stored_checking = (link.bank_feed_details_as_of_last_refresh or {}).get("primary_checking_available_balance_dollars")
    if stored_checking is not None:
        stored_balance_as_accounts[link.primary_checking_mercury_account_id] = {
            "current_balance_dollars": stored_checking, "available_balance_dollars": stored_checking,
            "name": link.primary_checking_account_name, "account_number_last_four": link.primary_checking_account_number_last_four}
    as_of = link.bank_amounts_as_of
    recategorised = _read_the_bank_into_the_link(db, link, stored_balance_as_accounts, use_cached_transactions=True)
    link.bank_amounts_as_of = as_of   # the balance is no fresher than before
    return recategorised


def _require_a_transaction_of_the_account(db: Session, link: LiquidityConstructionAccount, mercury_transaction_id: str) -> None:
    raw_transactions, _categorised = _categorised_transactions_of_link(db, link, use_cache=True)
    if mercury_transaction_id not in {raw["id"] for raw in raw_transactions}:
        raise ConstructionAccountNotFoundError()


def set_transaction_override(db: Session, bought_deal_id: str, mercury_transaction_id: str, data: ConstructionAccountTransactionOverrideReq,
                             today: Optional[date], use_deal_value_for: list[UseDealValueForField], preview_only: bool) -> ConstructionAccountWriteRes:
    """Ignore a bank transaction, or put it in another category. Only a transaction of this deal's own construction
    account can be overridden."""
    deal, link = _find_linked(db, bought_deal_id)
    _require_a_transaction_of_the_account(db, link, mercury_transaction_id)

    def override_it() -> _WriteOutcome:
        override = get_transaction_override(db, deal.id, mercury_transaction_id)
        if override is None:
            override = LiquidityConstructionAccountTransactionOverride(mercury_transaction_id=mercury_transaction_id, bought_brrr_deal_id=deal.id)
            db.add(override)
        override.ignored, override.category_override, override.note = data.ignored, data.category_override, (data.note or None)
        db.flush()
        return _WriteOutcome(mercury_is_unavailable=not _recategorise_with_the_stored_balance(db, link))

    return _write(db, deal, today, use_deal_value_for, preview_only, override_it)


def clear_transaction_override(db: Session, bought_deal_id: str, mercury_transaction_id: str, today: Optional[date],
                               use_deal_value_for: list[UseDealValueForField], preview_only: bool) -> ConstructionAccountWriteRes:
    """Back to the automatic category."""
    deal, link = _find_linked(db, bought_deal_id)
    override = get_transaction_override(db, deal.id, mercury_transaction_id)
    if override is None:
        raise ConstructionAccountNotFoundError()

    def clear_it() -> _WriteOutcome:
        db.delete(override)
        db.flush()
        return _WriteOutcome(mercury_is_unavailable=not _recategorise_with_the_stored_balance(db, link))

    return _write(db, deal, today, use_deal_value_for, preview_only, clear_it)


# --- Close-out ----------------------------------------------------------------------------------------------------

def mark_ready_for_close_out(db: Session, bought_deal_id: str, today: Optional[date], use_deal_value_for: list[UseDealValueForField],
                             preview_only: bool) -> ConstructionAccountWriteRes:
    """The rehab is over as far as this account goes, before the rehab-completed milestone is approved."""
    deal, link = _find_linked(db, bought_deal_id)

    def mark_it() -> None:
        if link.marked_ready_for_close_out_at is None:
            link.marked_ready_for_close_out_at = _utc_now()

    return _write(db, deal, today, use_deal_value_for, preview_only, mark_it)


def mark_closed_out(db: Session, bought_deal_id: str, today: Optional[date], use_deal_value_for: list[UseDealValueForField],
                    preview_only: bool) -> ConstructionAccountWriteRes:
    """Close the account out without a transfer (it was emptied in Mercury): the return row is marked done and the
    account is no longer refreshed. The answer says what is still in it, if anything."""
    deal, link = _find_linked(db, bought_deal_id)

    def close_it() -> _WriteOutcome:
        _read_the_bank_into_the_link(db, link, _accounts_by_id(db, want_fresh=True), use_cached_transactions=False)
        if link.closed_out_at is None:
            link.closed_out_at = _utc_now()
        return _WriteOutcome(balance_left_in_the_account_dollars=Decimal(link.bank_current_balance_dollars or 0))

    return _write(db, deal, today, use_deal_value_for, preview_only, close_it)


def reopen_construction_account(db: Session, bought_deal_id: str, today: Optional[date], use_deal_value_for: list[UseDealValueForField],
                                preview_only: bool) -> ConstructionAccountWriteRes:
    """Undo a close-out: the account is live again and its return row counts again."""
    deal, link = _find_linked(db, bought_deal_id)

    def reopen_it() -> None:
        if link.closed_out_at is None:
            return
        link.closed_out_at = None
        for row in imported_rows_of_deal(db, DEAL_BOARD_BOUGHT, deal.id):
            if row.source_item_key == CONSTRUCTION_ACCOUNT_RETURN_ITEM_KEY and row.done_at is not None:
                row.done_at = None

    return _write(db, deal, today, use_deal_value_for, preview_only, reopen_it)


# --- Live Mercury: the refresh, the last change, the connection ---------------------------------------------------

TRANSFER_APPROVAL_REQUEST_STATUSES_THAT_END_THE_REQUEST = ("rejected", "cancelled")
TRANSFER_APPROVAL_REQUEST_STATUS_APPROVED = "approved"


def _settle_the_in_app_transfers_rejected_or_cancelled_in_mercury(db: Session, mercury_workspace_label: str) -> bool:
    """An in-app transfer waiting for its approval in Mercury never reaches the bank feed if the request is rejected or
    cancelled there: ask Mercury for each one still waiting (zero calls when none is). Rejected or cancelled: the
    transfer stops counting (failed_or_cancelled_at_mercury). Approved: only the status is kept; the bank feed counts
    the money when it arrives. Any error leaves the transfer as it is and never fails the refresh. True when a transfer
    changed."""
    some_transfer_changed = False
    for link in get_all_construction_accounts(db):
        if link.mercury_workspace_label != mercury_workspace_label or link.closed_out_at is not None:
            continue
        transfers_waiting_for_approval = [
            transfer for transfer in get_transfers_of_construction_account(db, link.bought_brrr_deal_id, link.construction_mercury_account_id)
            if transfer.transfer_outcome == TRANSFER_OUTCOME_WAITING_FOR_APPROVAL_IN_MERCURY and transfer.mercury_transfer_id
            and transfer.seen_in_the_bank_feed_at is None]
        for transfer in transfers_waiting_for_approval:
            try:
                transfer_approval_request_status = fetch_transfer_approval_request_status(mercury_workspace_label, transfer.mercury_transfer_id)
            except Exception as error:   # a missing scope (401/403), no answer, no token: try again at the next refresh
                logger.warning("Mercury transfer approval status not read (%s)", type(error).__name__)
                continue
            if transfer_approval_request_status in TRANSFER_APPROVAL_REQUEST_STATUSES_THAT_END_THE_REQUEST:
                transfer.transfer_outcome = TRANSFER_OUTCOME_FAILED_OR_CANCELLED_AT_MERCURY
                transfer.mercury_transfer_status = transfer_approval_request_status
                some_transfer_changed = True
            elif (transfer_approval_request_status == TRANSFER_APPROVAL_REQUEST_STATUS_APPROVED
                  and transfer.mercury_transfer_status != TRANSFER_APPROVAL_REQUEST_STATUS_APPROVED):
                transfer.mercury_transfer_status = TRANSFER_APPROVAL_REQUEST_STATUS_APPROVED
                some_transfer_changed = True
    return some_transfer_changed


def refresh_one_workspace(db: Session, mercury_workspace_label: str, workspace_read: mercury_reads.WorkspaceReadResult,
                          today: date) -> tuple[int, int, bool, list, bool]:
    """After a read of one workspace: its linked construction accounts take the new balances (their transactions are
    read only when the accounts were read from Mercury now, or the link was never read), and their rows move as the bank
    reports. (deals refreshed, rows changed, construction accounts changed, bank-reported row changes, Mercury failed)."""
    accounts_by_id = _accounts_by_id_from_workspace_reads(db, [workspace_read]) if workspace_read.workspace_summary is not None else None
    refreshed_deal_count = changed_row_count = 0
    construction_accounts_changed = False
    bank_reported_row_changes = []
    mercury_failed = workspace_read.workspace_summary is None
    for link in get_all_construction_accounts(db):
        if link.mercury_workspace_label != mercury_workspace_label or link.closed_out_at is not None:
            continue
        deal = _deal_of_link(db, link)
        if deal is None:
            continue
        if workspace_read.was_read_from_mercury_now or link.bank_amounts_as_of is None:
            sums_before = _bank_sums_tuple(link)
            if _read_the_bank_into_the_link(db, link, accounts_by_id, use_cached_transactions=False):
                refreshed_deal_count += 1
                construction_accounts_changed = construction_accounts_changed or _bank_sums_tuple(link) != sums_before
            elif accounts_by_id is not None:
                mercury_failed = True
        changes, marked_done = _write_the_bank_reported_construction_rows(db, deal, today)
        reported = [change for change in changes if change.change_kind in ROW_CHANGE_KINDS_THAT_WRITE and not _is_a_top_up_date_only_move(change)]
        changed_row_count += len(marked_done) + sum(1 for change in changes if change.change_kind in ROW_CHANGE_KINDS_THAT_WRITE)
        if reported or marked_done:
            construction_accounts_changed = True
            bank_reported_row_changes.append(deal_cash_row_changes_res(DEAL_BOARD_BOUGHT, deal, reported))
    if workspace_read.was_read_from_mercury_now and _settle_the_in_app_transfers_rejected_or_cancelled_in_mercury(db, mercury_workspace_label):
        construction_accounts_changed = True
    if construction_accounts_changed:
        mercury_reads.mark_construction_accounts_changed(db, mercury_workspace_label)
    return refreshed_deal_count, changed_row_count, construction_accounts_changed, bank_reported_row_changes, mercury_failed


def refresh_construction_accounts(db: Session, today: Optional[date], want_fresh: bool = True) -> ConstructionAccountRefreshRes:
    """Read every workspace with a token (through the shared pace: never more than one Mercury read per workspace in
    the floor, whoever asks) and bring its linked construction accounts and their rows in step. The router commits."""
    resolved_today = today_for_liquidity(db, today)
    try:
        workspace_reads = mercury_reads.read_every_workspace(db, want_fresh=want_fresh)
    except MercuryConfigError:
        workspace_reads = []
    refreshed_deal_count = changed_row_count = 0
    cash_balance_changed = construction_accounts_changed = False
    mercury_is_unavailable = not workspace_reads and bool(get_all_construction_accounts(db))
    bank_reported_row_changes = []
    for workspace_read in workspace_reads:
        cash_balance_changed = cash_balance_changed or workspace_read.cash_balance_changed_now
        refreshed, changed_rows, accounts_changed, reported, failed = refresh_one_workspace(
            db, workspace_read.mercury_workspace_label, workspace_read, resolved_today)
        refreshed_deal_count += refreshed
        changed_row_count += changed_rows
        construction_accounts_changed = construction_accounts_changed or accounts_changed
        bank_reported_row_changes.extend(reported)
        mercury_is_unavailable = mercury_is_unavailable or failed
    db.flush()
    cash_balance_last_changed_at, construction_accounts_last_changed_at = mercury_reads.last_change_times(db)
    next_read_times = [read.next_mercury_read_not_before for read in workspace_reads if read.next_mercury_read_not_before is not None]
    return ConstructionAccountRefreshRes(
        refreshed_deal_count=refreshed_deal_count, changed_row_count=changed_row_count, mercury_is_unavailable=mercury_is_unavailable,
        next_mercury_read_not_before=min(next_read_times) if next_read_times else None,
        cash_balance_changed=cash_balance_changed, construction_accounts_changed=construction_accounts_changed,
        cash_balance_last_changed_at=cash_balance_last_changed_at, construction_accounts_last_changed_at=construction_accounts_last_changed_at,
        bank_reported_row_changes=bank_reported_row_changes,
    )


def last_mercury_change(db: Session) -> MercuryLastChangeRes:
    cash_balance_last_changed_at, construction_accounts_last_changed_at = mercury_reads.last_change_times(db)
    candidates = [moment for moment in (cash_balance_last_changed_at, construction_accounts_last_changed_at) if moment is not None]
    instant_updates = [row for row in db.query(LiquidityMercuryWorkspaceRead).all() if row.last_instant_update_at is not None]
    latest_instant_update = max(instant_updates, key=lambda row: row.last_instant_update_at) if instant_updates else None
    return MercuryLastChangeRes(last_changed_at=max(candidates) if candidates else None,
                                cash_balance_last_changed_at=cash_balance_last_changed_at,
                                construction_accounts_last_changed_at=construction_accounts_last_changed_at,
                                last_instant_update_at=latest_instant_update.last_instant_update_at if latest_instant_update else None,
                                bank_reported_row_changes_of_last_instant_update=(
                                    latest_instant_update.bank_reported_row_changes_of_last_instant_update or [] if latest_instant_update else []))


def mercury_connection_status(db: Session) -> MercuryConnectionStatusRes:
    """Per LLC: which tokens the backend found (by the exact names it reads) and how instant updates are doing. Names
    and times only, never a token or a secret."""
    webhooks_by_label = {webhook.mercury_workspace_label: webhook for webhook in db.query(LiquidityMercuryWebhook).all()}
    read_labels = set(mercury_reads.workspace_labels_with_a_read_token())
    labels = (read_labels | set(workspace_labels_with_a_transfer_token()) | set(webhooks_by_label)
              | {link.mercury_workspace_label for link in get_all_construction_accounts(db)})
    workspaces = []
    for label in sorted(labels):
        webhook = webhooks_by_label.get(label)
        read_row = mercury_reads.workspace_read_row(db, label)
        workspaces.append(MercuryWorkspaceConnectionRes(
            mercury_workspace_label=label, has_read_token=label in read_labels, has_transfer_token=workspace_has_a_transfer_token(label),
            read_token_environment_variable_name=read_token_environment_variable_name(label),
            transfer_token_environment_variable_name=transfer_token_environment_variable_name(label),
            instant_updates_are_on=bool(webhook and webhook.turned_on_at and webhook.mercury_webhook_endpoint_id),
            last_valid_event_received_at=webhook.last_valid_event_received_at if webhook else None,
            last_webhook_error_message=webhook.last_webhook_error_message if webhook else None,
            last_webhook_error_at=webhook.last_webhook_error_at if webhook else None,
            next_mercury_read_not_before=mercury_reads.next_read_time_of(read_row),
        ))
    return MercuryConnectionStatusRes(
        workspaces=workspaces, read_token_environment_variable_name_pattern=READ_TOKEN_ENVIRONMENT_VARIABLE_NAME_PATTERN,
        transfer_token_environment_variable_name_pattern=TRANSFER_TOKEN_ENVIRONMENT_VARIABLE_NAME_PATTERN)
