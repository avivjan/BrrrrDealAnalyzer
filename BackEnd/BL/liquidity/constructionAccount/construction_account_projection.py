"""Pure math of a rehab's construction account (tasks/todo/ConstructionAccountPerRehab.md): no database, no network.

    loan_draws_pulled    = bank draws (non-ignored) + draws pulled before this account + manual draws
    rehab_payments_made  = bank rehab payments (non-ignored) + payments made before this account + manual payments

    projected_return_at_rehab_end =
        current balance + (construction budget - loan_draws_pulled) - (rehab cost - rehab_payments_made)

The bank feed is the default: external money in is a loan draw, external money out a rehab payment, an internal
transfer the owner's own money (a deposit or a steal). A per-transaction override ignores a row or moves it to another
category. Ignored and own-money rows are left out of both sums but stay in the balance. A failed or cancelled
transaction is skipped: it never moved money.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

TRANSACTION_CATEGORY_LOAN_DRAW = "loan_draw"
TRANSACTION_CATEGORY_REHAB_PAYMENT = "rehab_payment"
TRANSACTION_CATEGORY_OWN_MONEY = "own_money"

SAFE_TO_STEAL_CAPPED_BY_AVAILABLE_BALANCE = "available_balance"
SAFE_TO_STEAL_CAPPED_BY_BUFFER_TO_KEEP = "buffer_to_keep"
SAFE_TO_STEAL_CAPPED_BY_PROJECTED_RETURN = "projected_return"

ZERO_DOLLARS = Decimal("0")


@dataclass(frozen=True)
class ConstructionAccountBankTransaction:
    mercury_transaction_id: str
    transaction_date: Optional[date]
    counterparty_name: str
    signed_amount_dollars: Decimal        # positive = into the construction account
    is_internal_transfer: bool            # between two accounts of the same Mercury workspace
    is_failed_or_cancelled: bool
    is_pending: bool = False              # accepted by the bank, not settled yet


@dataclass(frozen=True)
class ConstructionAccountTransactionOverride:
    ignored: bool
    category_override: Optional[str]      # one of the three categories, or None = keep the automatic one
    note: Optional[str] = None


@dataclass(frozen=True)
class CategorisedConstructionAccountTransaction:
    transaction: ConstructionAccountBankTransaction
    automatic_category: str
    override: Optional[ConstructionAccountTransactionOverride]
    # None when the row counts for nothing: ignored by hand, or failed / cancelled at the bank.
    effective_category: Optional[str]


@dataclass(frozen=True)
class ConstructionAccountBankSums:
    """What the bank feed says, after the overrides: the balance and the categorised sums. Stored on the link at every
    refresh, so the projection can be recomputed without Mercury (a deal save, a re-sync, an outage)."""
    current_balance_dollars: Decimal
    available_balance_dollars: Decimal
    bank_loan_draws_dollars: Decimal
    bank_rehab_payments_dollars: Decimal
    own_money_transferred_into_the_account_dollars: Decimal
    own_money_transferred_out_of_the_account_dollars: Decimal


@dataclass(frozen=True)
class ConstructionAccountProjectionInputs:
    construction_budget_dollars: Decimal
    rehab_cost_dollars: Decimal                     # actual rehab with its contingency; appliances are not part of it
    rehab_cushion_dollars: Decimal
    loan_draws_pulled_before_construction_account_dollars: Decimal
    rehab_payments_made_before_construction_account_dollars: Decimal
    manual_draw_adjustments_dollars: Decimal
    manual_payment_adjustments_dollars: Decimal
    minimum_balance_to_keep_in_construction_account_dollars: Decimal
    deposit_row_is_done: bool
    is_closed_out: bool


@dataclass(frozen=True)
class ConstructionAccountProjection:
    current_balance_dollars: Decimal
    available_balance_dollars: Decimal
    construction_budget_dollars: Decimal
    rehab_cost_dollars: Decimal
    # loan draws: the three sources and their sum
    bank_loan_draws_dollars: Decimal
    loan_draws_pulled_before_construction_account_dollars: Decimal
    manual_draw_adjustments_dollars: Decimal
    loan_draws_pulled_dollars: Decimal
    loan_draws_remaining_to_pull_dollars: Decimal
    # rehab payments: the three sources and their sum
    bank_rehab_payments_dollars: Decimal
    rehab_payments_made_before_construction_account_dollars: Decimal
    manual_payment_adjustments_dollars: Decimal
    rehab_payments_made_dollars: Decimal
    unpaid_rehab_remaining_dollars: Decimal
    # the owner's own money through the account
    own_money_transferred_into_the_account_dollars: Decimal
    own_money_transferred_out_of_the_account_dollars: Decimal
    original_steal_dollars: Decimal
    # The one deposit figure: the rehab cushion, plus the rehab the construction budget does not cover.
    rehab_cushion_dollars: Decimal
    rehab_beyond_the_construction_budget_dollars: Decimal
    total_to_deposit_dollars: Decimal
    remaining_deposit_dollars: Decimal
    # deposited - stolen; negative once more was taken out than was put in (spread already taken).
    own_money_still_in_the_account_dollars: Decimal
    spread_already_taken_dollars: Decimal
    projected_return_at_rehab_end_dollars: Decimal
    # The projected return's two parts: the owner's own money coming back, and the lender's spread.
    own_money_back_at_rehab_end_dollars: Decimal
    spread_at_rehab_end_dollars: Decimal
    safe_to_steal_now_dollars: Decimal
    safe_to_steal_now_is_capped_by: str             # "available_balance", "buffer_to_keep" or "projected_return"
    # the three liquidity rows
    deposit_row_amount_dollars: Decimal             # money out, >= 0
    return_row_amount_dollars: Decimal              # money in, >= 0
    top_up_needed_dollars: Decimal                  # money out today, >= 0


def automatic_category_of(transaction: ConstructionAccountBankTransaction) -> str:
    if transaction.is_internal_transfer:
        return TRANSACTION_CATEGORY_OWN_MONEY
    return TRANSACTION_CATEGORY_LOAN_DRAW if transaction.signed_amount_dollars > 0 else TRANSACTION_CATEGORY_REHAB_PAYMENT


def categorise_transactions(
    transactions: Iterable[ConstructionAccountBankTransaction],
    override_by_mercury_transaction_id: dict[str, ConstructionAccountTransactionOverride],
) -> list[CategorisedConstructionAccountTransaction]:
    categorised = []
    for transaction in transactions:
        automatic_category = automatic_category_of(transaction)
        override = override_by_mercury_transaction_id.get(transaction.mercury_transaction_id)
        if transaction.is_failed_or_cancelled or (override is not None and override.ignored):
            effective_category = None
        else:
            effective_category = (override.category_override if override is not None and override.category_override else automatic_category)
        categorised.append(CategorisedConstructionAccountTransaction(transaction, automatic_category, override, effective_category))
    return categorised


def sum_categorised_transactions(current_balance_dollars: Decimal, available_balance_dollars: Decimal,
                                 categorised_transactions: Iterable[CategorisedConstructionAccountTransaction],
                                 ) -> ConstructionAccountBankSums:
    bank_loan_draws = ZERO_DOLLARS
    bank_rehab_payments = ZERO_DOLLARS
    own_money_in = ZERO_DOLLARS
    own_money_out = ZERO_DOLLARS
    for categorised in categorised_transactions:
        signed_amount = categorised.transaction.signed_amount_dollars
        if categorised.effective_category == TRANSACTION_CATEGORY_LOAN_DRAW:
            bank_loan_draws += signed_amount          # a draw sent back to the lender (money out) lowers it
        elif categorised.effective_category == TRANSACTION_CATEGORY_REHAB_PAYMENT:
            bank_rehab_payments += -signed_amount     # a refund (money in) lowers it
        elif categorised.effective_category == TRANSACTION_CATEGORY_OWN_MONEY:
            if signed_amount > 0:
                own_money_in += signed_amount
            else:
                own_money_out += -signed_amount
    return ConstructionAccountBankSums(
        current_balance_dollars=current_balance_dollars, available_balance_dollars=available_balance_dollars,
        bank_loan_draws_dollars=bank_loan_draws, bank_rehab_payments_dollars=bank_rehab_payments,
        own_money_transferred_into_the_account_dollars=own_money_in,
        own_money_transferred_out_of_the_account_dollars=own_money_out)


def bank_feed_details_of(categorised_transactions: Iterable[CategorisedConstructionAccountTransaction]) -> dict:
    """For the page only, never part of the projection: pending money, the counts, the last draw and the last payment,
    and the rehab paid per payee. JSON-ready (amounts as strings, dates as ISO strings)."""
    categorised_transactions = list(categorised_transactions)
    counted = [row for row in categorised_transactions if row.effective_category is not None]
    pending = [row for row in counted if row.transaction.is_pending]
    draws = [row for row in counted if row.effective_category == TRANSACTION_CATEGORY_LOAN_DRAW and row.transaction.signed_amount_dollars > 0]
    payments = [row for row in counted if row.effective_category == TRANSACTION_CATEGORY_REHAB_PAYMENT]

    def last_of(rows: list[CategorisedConstructionAccountTransaction]) -> Optional[dict]:
        dated = [row for row in rows if row.transaction.transaction_date is not None]
        if not dated:
            return None
        last = max(dated, key=lambda row: row.transaction.transaction_date)
        return {"date": last.transaction.transaction_date.isoformat(), "amount_dollars": str(abs(last.transaction.signed_amount_dollars)),
                "counterparty_name": last.transaction.counterparty_name}

    paid_by_payee: dict[str, Decimal] = {}
    for row in payments:
        payee = row.transaction.counterparty_name or "Unknown payee"
        paid_by_payee[payee] = paid_by_payee.get(payee, ZERO_DOLLARS) - row.transaction.signed_amount_dollars
    transaction_dates = [row.transaction.transaction_date for row in categorised_transactions if row.transaction.transaction_date is not None]
    return {
        "pending_money_in_dollars": str(sum((row.transaction.signed_amount_dollars for row in pending if row.transaction.signed_amount_dollars > 0), ZERO_DOLLARS)),
        "pending_money_out_dollars": str(-sum((row.transaction.signed_amount_dollars for row in pending if row.transaction.signed_amount_dollars < 0), ZERO_DOLLARS)),
        "transactions_counted_count": len(counted),
        "transactions_ignored_count": sum(1 for row in categorised_transactions if row.override is not None and row.override.ignored),
        "transactions_recategorised_count": sum(1 for row in counted if row.override is not None and row.override.category_override
                                                and row.override.category_override != row.automatic_category),
        "transactions_failed_or_cancelled_count": sum(1 for row in categorised_transactions if row.transaction.is_failed_or_cancelled),
        "loan_draw_count": len(draws),
        "last_loan_draw": last_of(draws),
        "last_rehab_payment": last_of([row for row in payments if row.transaction.signed_amount_dollars < 0]),
        "last_transaction_date": max(transaction_dates).isoformat() if transaction_dates else None,
        "rehab_paid_by_payee": [{"payee_name": payee, "amount_dollars": str(amount)}
                                for payee, amount in sorted(paid_by_payee.items(), key=lambda item: (-item[1], item[0]))],
    }


def project_construction_account(inputs: ConstructionAccountProjectionInputs, bank_sums: ConstructionAccountBankSums,
                                 ) -> ConstructionAccountProjection:
    bank_loan_draws = bank_sums.bank_loan_draws_dollars
    bank_rehab_payments = bank_sums.bank_rehab_payments_dollars
    own_money_in = bank_sums.own_money_transferred_into_the_account_dollars
    own_money_out = bank_sums.own_money_transferred_out_of_the_account_dollars

    loan_draws_pulled = (bank_loan_draws + inputs.loan_draws_pulled_before_construction_account_dollars
                         + inputs.manual_draw_adjustments_dollars)
    rehab_payments_made = (bank_rehab_payments + inputs.rehab_payments_made_before_construction_account_dollars
                           + inputs.manual_payment_adjustments_dollars)
    loan_draws_remaining_to_pull = inputs.construction_budget_dollars - loan_draws_pulled
    unpaid_rehab_remaining = inputs.rehab_cost_dollars - rehab_payments_made
    projected_return_at_rehab_end = bank_sums.current_balance_dollars + loan_draws_remaining_to_pull - unpaid_rehab_remaining

    original_steal = inputs.construction_budget_dollars - inputs.rehab_cost_dollars
    rehab_beyond_the_construction_budget = max(ZERO_DOLLARS, -original_steal)
    total_to_deposit = inputs.rehab_cushion_dollars + rehab_beyond_the_construction_budget
    remaining_deposit = (ZERO_DOLLARS if inputs.deposit_row_is_done or inputs.is_closed_out
                         else max(ZERO_DOLLARS, total_to_deposit - own_money_in))
    balance_free_to_take = bank_sums.available_balance_dollars - inputs.minimum_balance_to_keep_in_construction_account_dollars
    safe_to_steal_now = max(ZERO_DOLLARS, min(balance_free_to_take, projected_return_at_rehab_end))
    if projected_return_at_rehab_end < balance_free_to_take:
        safe_to_steal_now_is_capped_by = SAFE_TO_STEAL_CAPPED_BY_PROJECTED_RETURN
    elif inputs.minimum_balance_to_keep_in_construction_account_dollars > 0:
        safe_to_steal_now_is_capped_by = SAFE_TO_STEAL_CAPPED_BY_BUFFER_TO_KEEP
    else:
        safe_to_steal_now_is_capped_by = SAFE_TO_STEAL_CAPPED_BY_AVAILABLE_BALANCE
    own_money_still_in_the_account = own_money_in - own_money_out
    own_money_back_at_rehab_end = max(ZERO_DOLLARS, min(projected_return_at_rehab_end, own_money_still_in_the_account))

    # The deposit still to come will land in the balance, so the return row counts it.
    return_after_the_remaining_deposit = projected_return_at_rehab_end + remaining_deposit
    if inputs.is_closed_out:
        return_row_amount = top_up_needed = safe_to_steal_now = ZERO_DOLLARS
    else:
        return_row_amount = max(ZERO_DOLLARS, return_after_the_remaining_deposit)
        top_up_needed = max(ZERO_DOLLARS, -return_after_the_remaining_deposit)

    return ConstructionAccountProjection(
        current_balance_dollars=bank_sums.current_balance_dollars,
        available_balance_dollars=bank_sums.available_balance_dollars,
        construction_budget_dollars=inputs.construction_budget_dollars,
        rehab_cost_dollars=inputs.rehab_cost_dollars,
        bank_loan_draws_dollars=bank_loan_draws,
        loan_draws_pulled_before_construction_account_dollars=inputs.loan_draws_pulled_before_construction_account_dollars,
        manual_draw_adjustments_dollars=inputs.manual_draw_adjustments_dollars,
        loan_draws_pulled_dollars=loan_draws_pulled,
        loan_draws_remaining_to_pull_dollars=loan_draws_remaining_to_pull,
        bank_rehab_payments_dollars=bank_rehab_payments,
        rehab_payments_made_before_construction_account_dollars=inputs.rehab_payments_made_before_construction_account_dollars,
        manual_payment_adjustments_dollars=inputs.manual_payment_adjustments_dollars,
        rehab_payments_made_dollars=rehab_payments_made,
        unpaid_rehab_remaining_dollars=unpaid_rehab_remaining,
        own_money_transferred_into_the_account_dollars=own_money_in,
        own_money_transferred_out_of_the_account_dollars=own_money_out,
        original_steal_dollars=original_steal,
        rehab_cushion_dollars=inputs.rehab_cushion_dollars,
        rehab_beyond_the_construction_budget_dollars=rehab_beyond_the_construction_budget,
        total_to_deposit_dollars=total_to_deposit,
        remaining_deposit_dollars=remaining_deposit,
        own_money_still_in_the_account_dollars=own_money_still_in_the_account,
        spread_already_taken_dollars=max(ZERO_DOLLARS, -own_money_still_in_the_account),
        projected_return_at_rehab_end_dollars=projected_return_at_rehab_end,
        own_money_back_at_rehab_end_dollars=own_money_back_at_rehab_end,
        spread_at_rehab_end_dollars=projected_return_at_rehab_end - own_money_back_at_rehab_end,
        safe_to_steal_now_dollars=safe_to_steal_now,
        safe_to_steal_now_is_capped_by=safe_to_steal_now_is_capped_by,
        deposit_row_amount_dollars=remaining_deposit,
        return_row_amount_dollars=return_row_amount,
        top_up_needed_dollars=top_up_needed,
    )
