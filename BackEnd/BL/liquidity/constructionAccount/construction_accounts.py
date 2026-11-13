"""The /liquidity/construction-accounts/* business logic (tasks/todo/ConstructionAccountPerRehab.md): link a Mercury
construction account to a Bought BRRRR deal at any stage of its rehab, correct the bank feed by hand (baselines, manual
payments and draws, per-transaction overrides), switch or close out the account, and keep the deal's three liquidity
rows (deposit, return, top-up) in step with it.

Mercury is read here, never written. Every number can be recomputed without Mercury from the bank sums stored on the
link at the last refresh, so an outage leaves the rows as they are.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from BL.analyze.analyzeBRRR import compute_brrr_with_intermediates
from BL.liquidity.common.mercury_client import (
    ACTIVE_ACCOUNT_STATUSES, MercuryApiError, MercuryConfigError, clear_cache as clear_mercury_cache, fetch_account_transactions,
)
from BL.liquidity.constructionAccount.construction_account_projection import (
    CategorisedConstructionAccountTransaction, ConstructionAccountBankTransaction, ConstructionAccountProjection,
    ConstructionAccountTransactionOverride, categorise_transactions, sum_categorised_transactions,
)
from BL.liquidity.constructionAccount.construction_account_rows import (
    bank_sums_stored_on_the_link, planned_cash_rows_of_deal_in_liquidity, projection_of_linked_deal,
)
from BL.liquidity.dealCashRows.deal_cash_rows import (
    CONSTRUCTION_ACCOUNT_DEPOSIT_ITEM_KEY, CONSTRUCTION_ACCOUNT_ITEM_KEYS, CONSTRUCTION_ACCOUNT_RETURN_ITEM_KEY, DEAL_BOARD_BOUGHT,
    apply_deal_cash_row_changes, imported_rows_of_deal,
)
from BL.liquidity.dealCashRows.liquidity_deals import LiquidityDealNotFoundError, find_brrr_deal, today_for_liquidity
from BL.liquidity.mercuryBalance import get_mercury_balance
from DAL.crud.liquidity_construction_account import (
    delete_everything_of_deal, get_all_construction_accounts, get_construction_account_by_mercury_account_id,
    get_construction_account_of_deal, get_manual_adjustment, get_manual_adjustments_of_deal, get_transaction_override,
    get_transaction_overrides_of_deal,
)
from DAL.data_models import BoughtBrrrDeal, LiquidityTransaction
from DAL.data_models.liquidity.construction_account_models import (
    LiquidityConstructionAccount, LiquidityConstructionAccountManualAdjustment, LiquidityConstructionAccountTransactionOverride,
)
from ReqRes.common.liquidity_construction_account_schemas import (
    ConstructionAccountClosedOutRes, ConstructionAccountLinkReq, ConstructionAccountManualAdjustmentReq,
    ConstructionAccountManualAdjustmentRes, ConstructionAccountRefreshRes, ConstructionAccountStatusRes,
    ConstructionAccountSumBySourceRes, ConstructionAccountSwitchPreviewRes, ConstructionAccountSwitchReq,
    ConstructionAccountTransactionOverrideReq, ConstructionAccountTransactionRes, MercuryAccountNameRes,
)

ONE_CENT = Decimal("0.01")


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


# --- Mercury (read only) ------------------------------------------------------------------------------------------

def _mercury_accounts_by_id(db: Session) -> Optional[dict[str, dict]]:
    """Every Mercury account by id, or None while Mercury is unavailable."""
    try:
        return {account["id"]: account for account in get_mercury_balance(db)["accounts"]}
    except (MercuryConfigError, MercuryApiError):
        return None


def _required_mercury_accounts_by_id(db: Session) -> dict[str, dict]:
    accounts_by_id = _mercury_accounts_by_id(db)
    if accounts_by_id is None:
        raise MercuryUnavailableError()
    return accounts_by_id


def _categorised_transactions_of_link(db: Session, link: LiquidityConstructionAccount) -> tuple[list[dict], list[CategorisedConstructionAccountTransaction]]:
    """The construction account's bank transactions, raw and categorised with the deal's overrides. Raises `MercuryUnavailableError`."""
    try:
        raw_transactions = fetch_account_transactions(link.mercury_workspace_label, link.construction_mercury_account_id)
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
        is_failed_or_cancelled=raw["is_failed_or_cancelled"]) for raw in raw_transactions]
    return raw_transactions, categorise_transactions(transactions, override_by_id)


def _read_the_bank_into_the_link(db: Session, link: LiquidityConstructionAccount, accounts_by_id: Optional[dict[str, dict]]) -> bool:
    """Store the account's balance and categorised sums on the link. False (nothing changed) while Mercury is unavailable."""
    if accounts_by_id is None or link.construction_mercury_account_id not in accounts_by_id:
        return False
    try:
        _raw_transactions, categorised = _categorised_transactions_of_link(db, link)
    except MercuryUnavailableError:
        return False
    account = accounts_by_id[link.construction_mercury_account_id]
    bank_sums = sum_categorised_transactions(_dollars(account["current_balance_dollars"]), _dollars(account["available_balance_dollars"]), categorised)
    link.bank_current_balance_dollars = bank_sums.current_balance_dollars
    link.bank_available_balance_dollars = bank_sums.available_balance_dollars
    link.bank_loan_draws_dollars = bank_sums.bank_loan_draws_dollars
    link.bank_rehab_payments_dollars = bank_sums.bank_rehab_payments_dollars
    link.bank_own_money_transferred_into_the_account_dollars = bank_sums.own_money_transferred_into_the_account_dollars
    link.bank_own_money_transferred_out_of_the_account_dollars = bank_sums.own_money_transferred_out_of_the_account_dollars
    link.bank_amounts_as_of = datetime.now(timezone.utc)
    _store_account_names(link, accounts_by_id)
    return True


def _store_account_names(link: LiquidityConstructionAccount, accounts_by_id: dict[str, dict]) -> None:
    construction_account = accounts_by_id.get(link.construction_mercury_account_id)
    if construction_account is not None:
        link.construction_account_name = construction_account["name"][:200]
        link.construction_account_number_last_four = construction_account.get("account_number_last_four", "")[-4:]
    checking_account = accounts_by_id.get(link.primary_checking_mercury_account_id)
    if checking_account is not None:
        link.primary_checking_account_name = checking_account["name"][:200]
        link.primary_checking_account_number_last_four = checking_account.get("account_number_last_four", "")[-4:]


# --- The three liquidity rows -------------------------------------------------------------------------------------

def _open_row_of_item(db: Session, bought_brrr_deal_id, item_key: str) -> Optional[LiquidityTransaction]:
    return next((row for row in imported_rows_of_deal(db, DEAL_BOARD_BOUGHT, bought_brrr_deal_id)
                 if row.source_item_key == item_key and row.done_at is None), None)


def write_construction_account_rows_of_deal(db: Session, deal: BoughtBrrrDeal, today: date) -> int:
    """Bring the deal's deposit, return and top-up rows in step with its construction account (or, once unlinked, back
    to the schedule's plan). Returns how many rows changed. No commit.

    Nothing is written for a deal that is not in the liquidity timeline, or that is 'liquidity out of date': its rows
    wait for the Re-sync the user confirms (which aims for these same rows)."""
    if not imported_rows_of_deal(db, DEAL_BOARD_BOUGHT, deal.id) or deal.liquidity_rows_out_of_date:
        return 0
    link = get_construction_account_of_deal(db, deal.id)
    rows_marked_done = 0
    if link is not None:
        projection = projection_of_linked_deal(db, deal, link)
        deposit_row = _open_row_of_item(db, deal.id, CONSTRUCTION_ACCOUNT_DEPOSIT_ITEM_KEY)
        deposit_has_landed = (projection.planned_deposit_dollars > 0
                              and projection.own_money_transferred_into_the_account_dollars >= projection.planned_deposit_dollars)
        if deposit_row is not None and deposit_has_landed:
            deposit_row.done_at = datetime.now(timezone.utc)
            rows_marked_done += 1
        return_row = _open_row_of_item(db, deal.id, CONSTRUCTION_ACCOUNT_RETURN_ITEM_KEY)
        if return_row is not None and link.closed_out_at is not None:
            return_row.done_at = datetime.now(timezone.utc)
            rows_marked_done += 1
        db.flush()
    planned_rows = planned_cash_rows_of_deal_in_liquidity(db, DEAL_BOARD_BOUGHT, deal, today)
    changes = apply_deal_cash_row_changes(db, DEAL_BOARD_BOUGHT, deal.id, planned_rows, only_item_keys=CONSTRUCTION_ACCOUNT_ITEM_KEYS)
    db.flush()
    return rows_marked_done + sum(1 for change in changes if change.change_kind in {"added", "updated", "removed"})


def refresh_construction_accounts(db: Session, today: Optional[date]) -> ConstructionAccountRefreshRes:
    """Read every linked construction account from Mercury and bring its deal's three rows in step. Idempotent."""
    resolved_today = today_for_liquidity(db, today)
    links = [link for link in get_all_construction_accounts(db) if link.closed_out_at is None]
    accounts_by_id = _mercury_accounts_by_id(db) if links else {}
    refreshed_deal_count = changed_row_count = 0
    for link in links:
        deal = db.query(BoughtBrrrDeal).filter(BoughtBrrrDeal.id == link.bought_brrr_deal_id).first()
        if deal is None:
            continue
        if _read_the_bank_into_the_link(db, link, accounts_by_id):
            refreshed_deal_count += 1
        changed_row_count += write_construction_account_rows_of_deal(db, deal, resolved_today)
    db.commit()
    return ConstructionAccountRefreshRes(refreshed_deal_count=refreshed_deal_count, changed_row_count=changed_row_count,
                                         mercury_is_unavailable=bool(links) and accounts_by_id is None)


def _refresh_one_deal(db: Session, deal: BoughtBrrrDeal, link: Optional[LiquidityConstructionAccount], read_the_bank: bool) -> bool:
    """After a write on one deal: optionally re-read its bank sums, then its rows, then commit. True = Mercury did not answer."""
    mercury_is_unavailable = False
    if link is not None and read_the_bank:
        mercury_is_unavailable = not _read_the_bank_into_the_link(db, link, _mercury_accounts_by_id(db))
    db.flush()
    write_construction_account_rows_of_deal(db, deal, today_for_liquidity(db, None))
    db.commit()
    return mercury_is_unavailable


# --- The page -----------------------------------------------------------------------------------------------------

def _sum_by_source(from_the_bank_feed: Decimal, before_this_account: Decimal, entered_by_hand: Decimal, total: Decimal) -> ConstructionAccountSumBySourceRes:
    return ConstructionAccountSumBySourceRes(
        from_the_bank_feed_dollars=float(from_the_bank_feed), before_this_account_dollars=float(before_this_account),
        entered_by_hand_dollars=float(entered_by_hand), total_dollars=float(total))


def _manual_adjustment_res(adjustment: LiquidityConstructionAccountManualAdjustment) -> ConstructionAccountManualAdjustmentRes:
    return ConstructionAccountManualAdjustmentRes(
        id=str(adjustment.id), adjustment_type=adjustment.adjustment_type, amount_dollars=float(adjustment.amount_dollars),
        date=adjustment.date, note=adjustment.note)


def status_of_deal(db: Session, deal: BoughtBrrrDeal, mercury_is_unavailable: bool = False) -> ConstructionAccountStatusRes:
    results = compute_brrr_with_intermediates(deal)
    link = get_construction_account_of_deal(db, deal.id)
    status = ConstructionAccountStatusRes(
        bought_deal_id=str(deal.id), deal_address=deal.address, is_linked=link is not None,
        rows_wait_for_a_resync=bool(deal.liquidity_rows_out_of_date),
        rehab_completed_is_approved=deal.rehab_completed_approved_at is not None,
        construction_budget_dollars=float(results.construction_budget), rehab_cost_dollars=float(results.rehab_cost),
        rehab_cushion_dollars=float(deal.rehab_cushion or 0), original_steal_dollars=float(results.construction_budget - results.rehab_cost),
    )
    if link is None:
        return status
    projection: ConstructionAccountProjection = projection_of_linked_deal(db, deal, link)
    planned_deposit_by_the_formula = Decimal(deal.rehab_cushion or 0) + max(Decimal("0"), -projection.original_steal_dollars)
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
        loan_draws_pulled=_sum_by_source(projection.bank_loan_draws_dollars, projection.loan_draws_pulled_before_construction_account_dollars,
                                         projection.manual_draw_adjustments_dollars, projection.loan_draws_pulled_dollars),
        loan_draws_remaining_to_pull_dollars=float(projection.loan_draws_remaining_to_pull_dollars),
        rehab_payments_made=_sum_by_source(projection.bank_rehab_payments_dollars, projection.rehab_payments_made_before_construction_account_dollars,
                                           projection.manual_payment_adjustments_dollars, projection.rehab_payments_made_dollars),
        unpaid_rehab_remaining_dollars=float(projection.unpaid_rehab_remaining_dollars),
        own_money_transferred_into_the_account_dollars=float(projection.own_money_transferred_into_the_account_dollars),
        own_money_transferred_out_of_the_account_dollars=float(projection.own_money_transferred_out_of_the_account_dollars),
        planned_deposit_dollars=float(projection.planned_deposit_dollars),
        planned_deposit_by_the_formula_dollars=float(planned_deposit_by_the_formula),
        planned_deposit_override_dollars=None if link.planned_deposit_override_dollars is None else float(link.planned_deposit_override_dollars),
        remaining_deposit_dollars=float(projection.remaining_deposit_dollars),
        minimum_balance_to_keep_in_construction_account_dollars=float(link.minimum_balance_to_keep_in_construction_account_dollars or 0),
        projected_return_at_rehab_end_dollars=float(projection.projected_return_at_rehab_end_dollars),
        safe_to_steal_now_dollars=float(projection.safe_to_steal_now_dollars),
        top_up_needed_dollars=float(projection.top_up_needed_dollars),
        loan_draws_pulled_before_construction_account_dollars=float(link.loan_draws_pulled_before_construction_account_dollars or 0),
        rehab_payments_made_before_construction_account_dollars=float(link.rehab_payments_made_before_construction_account_dollars or 0),
        marked_ready_for_close_out_at=link.marked_ready_for_close_out_at, closed_out_at=link.closed_out_at,
        manual_adjustments=[_manual_adjustment_res(adjustment) for adjustment in get_manual_adjustments_of_deal(db, deal.id)],
    ))


def list_construction_accounts(db: Session) -> list[ConstructionAccountStatusRes]:
    """Every Bought BRRRR deal the timeline's deal bar shows that is not refinanced yet, plus every linked deal, by
    address. Never calls Mercury: the amounts are those of the last refresh (`amounts_as_of`)."""
    deal_ids_in_liquidity = {deal_id for (deal_id,) in db.query(LiquidityTransaction.source_deal_id)
                             .filter(LiquidityTransaction.source_deal_board == DEAL_BOARD_BOUGHT,
                                     LiquidityTransaction.source_deal_id.isnot(None)).distinct().all()}
    linked_deal_ids = {link.bought_brrr_deal_id for link in get_all_construction_accounts(db)}
    deals = []
    for deal in db.query(BoughtBrrrDeal).filter(BoughtBrrrDeal.id.in_(deal_ids_in_liquidity | linked_deal_ids)).all():
        if deal.id in linked_deal_ids or deal.refi_closed_approved_at is None:
            deals.append(deal)
    deals.sort(key=lambda deal: (deal.address or "", str(deal.id)))
    return [status_of_deal(db, deal) for deal in deals]


# --- Link, edit, unlink, switch -----------------------------------------------------------------------------------

def _validated_accounts(db: Session, deal: BoughtBrrrDeal, construction_mercury_account_id: str,
                        primary_checking_mercury_account_id: str) -> tuple[dict, dict, dict[str, dict]]:
    accounts_by_id = _required_mercury_accounts_by_id(db)
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
    return construction_account, checking_account, accounts_by_id


def save_construction_account_link(db: Session, bought_deal_id: str, data: ConstructionAccountLinkReq) -> ConstructionAccountStatusRes:
    """Link a construction account, or edit the link (baselines, checking, deposit target, buffer): always allowed.
    Changing the construction account itself goes through the switch, which carries its history over."""
    deal = _find_bought_deal(db, bought_deal_id)
    construction_account, _checking_account, accounts_by_id = _validated_accounts(
        db, deal, data.construction_mercury_account_id, data.primary_checking_mercury_account_id)
    link = get_construction_account_of_deal(db, deal.id)
    if link is None:
        link = LiquidityConstructionAccount(bought_brrr_deal_id=deal.id, previous_construction_mercury_account_ids=[],
                                            construction_mercury_account_id=data.construction_mercury_account_id)
        db.add(link)
    elif link.construction_mercury_account_id != data.construction_mercury_account_id:
        raise ConstructionAccountConflictError("To change the construction account itself, use Switch account")
    link.mercury_workspace_label = construction_account["workspace"]
    link.primary_checking_mercury_account_id = data.primary_checking_mercury_account_id
    link.loan_draws_pulled_before_construction_account_dollars = _dollars(data.loan_draws_pulled_before_construction_account_dollars)
    link.rehab_payments_made_before_construction_account_dollars = _dollars(data.rehab_payments_made_before_construction_account_dollars)
    link.planned_deposit_override_dollars = (None if data.planned_deposit_override_dollars is None
                                             else _dollars(data.planned_deposit_override_dollars))
    link.minimum_balance_to_keep_in_construction_account_dollars = _dollars(data.minimum_balance_to_keep_in_construction_account_dollars)
    _store_account_names(link, accounts_by_id)
    db.flush()
    # The account is no longer cash on hand: the cached balance summary must not say otherwise.
    mercury_is_unavailable = _refresh_one_deal(db, deal, link, read_the_bank=True)
    return status_of_deal(db, deal, mercury_is_unavailable)


def unlink_construction_account(db: Session, bought_deal_id: str) -> ConstructionAccountStatusRes:
    """Remove the link with its manual adjustments and overrides; the deal's rows go back to the schedule's plan."""
    deal, _link = _find_linked(db, bought_deal_id)
    delete_everything_of_deal(db, deal.id)
    db.flush()
    _refresh_one_deal(db, deal, None, read_the_bank=False)
    return status_of_deal(db, deal)


def preview_construction_account_switch(db: Session, bought_deal_id: str) -> ConstructionAccountSwitchPreviewRes:
    deal, link = _find_linked(db, bought_deal_id)
    if not _read_the_bank_into_the_link(db, link, _required_mercury_accounts_by_id(db)):
        raise MercuryUnavailableError()
    db.commit()
    bank_sums = bank_sums_stored_on_the_link(link)
    return ConstructionAccountSwitchPreviewRes(
        old_construction_account_balance_dollars=float(bank_sums.current_balance_dollars),
        old_account_must_be_emptied_first=bank_sums.current_balance_dollars != 0,
        loan_draws_pulled_before_construction_account_dollars=float(
            Decimal(link.loan_draws_pulled_before_construction_account_dollars or 0) + bank_sums.bank_loan_draws_dollars),
        rehab_payments_made_before_construction_account_dollars=float(
            Decimal(link.rehab_payments_made_before_construction_account_dollars or 0) + bank_sums.bank_rehab_payments_dollars),
    )


def switch_construction_account(db: Session, bought_deal_id: str, data: ConstructionAccountSwitchReq) -> ConstructionAccountStatusRes:
    """Replace the construction account mid-rehab: the old account must be empty, its draws and payments live on in the
    baselines the caller confirmed (prefilled by the preview), and it is kept in the history."""
    deal, link = _find_linked(db, bought_deal_id)
    if data.new_construction_mercury_account_id == link.construction_mercury_account_id:
        raise ConstructionAccountValidationError("That is already this deal's construction account")
    accounts_by_id = _required_mercury_accounts_by_id(db)
    if not _read_the_bank_into_the_link(db, link, accounts_by_id):
        raise MercuryUnavailableError()
    if Decimal(link.bank_current_balance_dollars or 0) != 0:
        db.commit()
        raise ConstructionAccountConflictError("Move the old construction account's balance to the new account first")
    _validated_accounts(db, deal, data.new_construction_mercury_account_id, link.primary_checking_mercury_account_id)
    link.previous_construction_mercury_account_ids = [
        *(link.previous_construction_mercury_account_ids or []),
        {"mercury_account_id": link.construction_mercury_account_id, "switched_away_at": datetime.now(timezone.utc).isoformat()},
    ]
    link.construction_mercury_account_id = data.new_construction_mercury_account_id
    link.loan_draws_pulled_before_construction_account_dollars = _dollars(data.loan_draws_pulled_before_construction_account_dollars)
    link.rehab_payments_made_before_construction_account_dollars = _dollars(data.rehab_payments_made_before_construction_account_dollars)
    db.flush()
    clear_mercury_cache()
    mercury_is_unavailable = _refresh_one_deal(db, deal, link, read_the_bank=True)
    return status_of_deal(db, deal, mercury_is_unavailable)


# --- Manual adjustments -------------------------------------------------------------------------------------------

def add_manual_adjustment(db: Session, bought_deal_id: str, data: ConstructionAccountManualAdjustmentReq) -> ConstructionAccountStatusRes:
    deal, link = _find_linked(db, bought_deal_id)
    db.add(LiquidityConstructionAccountManualAdjustment(
        bought_brrr_deal_id=deal.id, adjustment_type=data.adjustment_type, amount_dollars=_dollars(data.amount_dollars),
        date=data.date, note=(data.note or None)))
    db.flush()
    _refresh_one_deal(db, deal, link, read_the_bank=False)
    return status_of_deal(db, deal)


def update_manual_adjustment(db: Session, bought_deal_id: str, adjustment_id: str,
                             data: ConstructionAccountManualAdjustmentReq) -> ConstructionAccountStatusRes:
    deal, link = _find_linked(db, bought_deal_id)
    adjustment = get_manual_adjustment(db, deal.id, adjustment_id)
    if adjustment is None:
        raise ConstructionAccountNotFoundError()
    adjustment.adjustment_type, adjustment.amount_dollars = data.adjustment_type, _dollars(data.amount_dollars)
    adjustment.date, adjustment.note = data.date, (data.note or None)
    db.flush()
    _refresh_one_deal(db, deal, link, read_the_bank=False)
    return status_of_deal(db, deal)


def delete_manual_adjustment(db: Session, bought_deal_id: str, adjustment_id: str) -> ConstructionAccountStatusRes:
    deal, link = _find_linked(db, bought_deal_id)
    adjustment = get_manual_adjustment(db, deal.id, adjustment_id)
    if adjustment is None:
        raise ConstructionAccountNotFoundError()
    db.delete(adjustment)
    db.flush()
    _refresh_one_deal(db, deal, link, read_the_bank=False)
    return status_of_deal(db, deal)


# --- Bank transactions and their overrides ------------------------------------------------------------------------

def list_construction_account_transactions(db: Session, bought_deal_id: str) -> list[ConstructionAccountTransactionRes]:
    """The construction account's bank transactions, newest first, each with its automatic and its effective category."""
    _deal, link = _find_linked(db, bought_deal_id)
    raw_transactions, categorised_transactions = _categorised_transactions_of_link(db, link)
    bank_status_by_id = {raw["id"]: raw["status"] for raw in raw_transactions}
    return [ConstructionAccountTransactionRes(
        mercury_transaction_id=categorised.transaction.mercury_transaction_id,
        transaction_date=categorised.transaction.transaction_date, counterparty_name=categorised.transaction.counterparty_name,
        signed_amount_dollars=float(categorised.transaction.signed_amount_dollars),
        bank_status=bank_status_by_id.get(categorised.transaction.mercury_transaction_id, ""),
        automatic_category=categorised.automatic_category,
        ignored=bool(categorised.override and categorised.override.ignored),
        category_override=categorised.override.category_override if categorised.override else None,
        note=categorised.override.note if categorised.override else None,
        effective_category=categorised.effective_category,
    ) for categorised in reversed(categorised_transactions)]


def _require_a_transaction_of_the_account(db: Session, link: LiquidityConstructionAccount, mercury_transaction_id: str) -> None:
    raw_transactions, _categorised = _categorised_transactions_of_link(db, link)
    if mercury_transaction_id not in {raw["id"] for raw in raw_transactions}:
        raise ConstructionAccountNotFoundError()


def set_transaction_override(db: Session, bought_deal_id: str, mercury_transaction_id: str,
                             data: ConstructionAccountTransactionOverrideReq) -> ConstructionAccountStatusRes:
    """Ignore a bank transaction, or put it in another category. Only a transaction of this deal's own construction
    account can be overridden."""
    deal, link = _find_linked(db, bought_deal_id)
    _require_a_transaction_of_the_account(db, link, mercury_transaction_id)
    override = get_transaction_override(db, deal.id, mercury_transaction_id)
    if override is None:
        override = LiquidityConstructionAccountTransactionOverride(mercury_transaction_id=mercury_transaction_id, bought_brrr_deal_id=deal.id)
        db.add(override)
    override.ignored, override.category_override, override.note = data.ignored, data.category_override, (data.note or None)
    db.flush()
    mercury_is_unavailable = _refresh_one_deal(db, deal, link, read_the_bank=True)
    return status_of_deal(db, deal, mercury_is_unavailable)


def clear_transaction_override(db: Session, bought_deal_id: str, mercury_transaction_id: str) -> ConstructionAccountStatusRes:
    """Back to the automatic category."""
    deal, link = _find_linked(db, bought_deal_id)
    override = get_transaction_override(db, deal.id, mercury_transaction_id)
    if override is None:
        raise ConstructionAccountNotFoundError()
    db.delete(override)
    db.flush()
    mercury_is_unavailable = _refresh_one_deal(db, deal, link, read_the_bank=True)
    return status_of_deal(db, deal, mercury_is_unavailable)


# --- Close-out ----------------------------------------------------------------------------------------------------

def mark_ready_for_close_out(db: Session, bought_deal_id: str) -> ConstructionAccountStatusRes:
    """The rehab is over as far as this account goes, before the rehab-completed milestone is approved."""
    deal, link = _find_linked(db, bought_deal_id)
    if link.marked_ready_for_close_out_at is None:
        link.marked_ready_for_close_out_at = datetime.now(timezone.utc)
    db.commit()
    return status_of_deal(db, deal)


def mark_closed_out(db: Session, bought_deal_id: str) -> ConstructionAccountClosedOutRes:
    """Close the account out without a transfer (it was emptied in Mercury): the return row is marked done and the
    account is no longer refreshed. The answer says what is still in it, if anything."""
    deal, link = _find_linked(db, bought_deal_id)
    _read_the_bank_into_the_link(db, link, _mercury_accounts_by_id(db))
    balance_left_in_the_account = Decimal(link.bank_current_balance_dollars or 0)
    if link.closed_out_at is None:
        link.closed_out_at = datetime.now(timezone.utc)
    db.flush()
    _refresh_one_deal(db, deal, link, read_the_bank=False)
    return ConstructionAccountClosedOutRes(status=status_of_deal(db, deal), balance_left_in_the_account_dollars=float(balance_left_in_the_account))


def reopen_construction_account(db: Session, bought_deal_id: str) -> ConstructionAccountStatusRes:
    """Undo a close-out: the account is live again and its return row counts again."""
    deal, link = _find_linked(db, bought_deal_id)
    if link.closed_out_at is not None:
        link.closed_out_at = None
        for row in imported_rows_of_deal(db, DEAL_BOARD_BOUGHT, deal.id):
            if row.source_item_key == CONSTRUCTION_ACCOUNT_RETURN_ITEM_KEY and row.done_at is not None:
                row.done_at = None
    db.flush()
    mercury_is_unavailable = _refresh_one_deal(db, deal, link, read_the_bank=True)
    return status_of_deal(db, deal, mercury_is_unavailable)
