"""The construction account's math (tasks/todo/ConstructionAccountPerRehab.md), pure: no database, no network.

Throughout: construction budget $100,000, rehab cost $95,000 (so the original steal is $5,000), cushion $20,000.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from BL.liquidity.constructionAccount.construction_account_projection import (
    ConstructionAccountBankTransaction, ConstructionAccountProjectionInputs, ConstructionAccountTransactionOverride,
    TRANSACTION_CATEGORY_LOAN_DRAW, TRANSACTION_CATEGORY_OWN_MONEY, TRANSACTION_CATEGORY_REHAB_PAYMENT,
    categorise_transactions, project_construction_account, sum_categorised_transactions,
)

BUDGET, REHAB_COST, CUSHION = Decimal("100000"), Decimal("95000"), Decimal("20000")


def _transaction(transaction_id: str, signed_amount: int, internal: bool = False, failed: bool = False) -> ConstructionAccountBankTransaction:
    return ConstructionAccountBankTransaction(
        mercury_transaction_id=transaction_id, transaction_date=None, counterparty_name=transaction_id,
        signed_amount_dollars=Decimal(signed_amount), is_internal_transfer=internal, is_failed_or_cancelled=failed)


def _deposit(amount: int, transaction_id: str = "deposit") -> ConstructionAccountBankTransaction:
    return _transaction(transaction_id, amount, internal=True)


def _steal(amount: int, transaction_id: str = "steal") -> ConstructionAccountBankTransaction:
    return _transaction(transaction_id, -amount, internal=True)


def _draw(amount: int, transaction_id: str = "draw") -> ConstructionAccountBankTransaction:
    return _transaction(transaction_id, amount)


def _payment(amount: int, transaction_id: str = "payment") -> ConstructionAccountBankTransaction:
    return _transaction(transaction_id, -amount)


def _project(transactions, overrides=None, **input_changes):
    balance = sum((transaction.signed_amount_dollars for transaction in transactions if not transaction.is_failed_or_cancelled), Decimal("0"))
    inputs = ConstructionAccountProjectionInputs(
        construction_budget_dollars=BUDGET, rehab_cost_dollars=REHAB_COST, rehab_cushion_dollars=CUSHION,
        loan_draws_pulled_before_construction_account_dollars=Decimal("0"),
        rehab_payments_made_before_construction_account_dollars=Decimal("0"),
        manual_draw_adjustments_dollars=Decimal("0"), manual_payment_adjustments_dollars=Decimal("0"),
        minimum_balance_to_keep_in_construction_account_dollars=Decimal("0"),
        deposit_row_is_done=False, is_closed_out=False,
    )
    inputs = replace(inputs, **{name: (Decimal(value) if isinstance(value, int) and not isinstance(value, bool) else value)
                                for name, value in input_changes.items()})
    return project_construction_account(
        inputs, sum_categorised_transactions(balance, balance, categorise_transactions(transactions, overrides or {})))


class TestTheProjectedReturn:
    def test_before_any_money_moves_the_deposit_is_due_and_the_cushion_and_the_spread_come_back(self):
        projection = _project([])
        assert projection.original_steal_dollars == 5000
        assert (projection.total_to_deposit_dollars, projection.remaining_deposit_dollars) == (20000, 20000)
        assert projection.projected_return_at_rehab_end_dollars == 5000          # the spread alone: the account is empty
        assert projection.return_row_amount_dollars == 25000                     # + the deposit still to come
        assert (projection.deposit_row_amount_dollars, projection.top_up_needed_dollars) == (20000, 0)

    def test_the_deposit_lands_and_the_deposit_row_empties(self):
        projection = _project([_deposit(20000)])
        assert projection.remaining_deposit_dollars == 0
        assert projection.projected_return_at_rehab_end_dollars == projection.return_row_amount_dollars == 25000

    def test_an_advance_draw_does_not_move_the_projection(self):
        projection = _project([_deposit(20000), _draw(30000)])
        assert projection.current_balance_dollars == 50000
        assert (projection.loan_draws_pulled_dollars, projection.loan_draws_remaining_to_pull_dollars) == (30000, 70000)
        assert projection.projected_return_at_rehab_end_dollars == 25000

    def test_a_reimbursement_draw_paid_from_the_cushion_first_does_not_move_it_either(self):
        projection = _project([_deposit(20000), _payment(20000)])
        assert projection.current_balance_dollars == 0
        assert (projection.rehab_payments_made_dollars, projection.unpaid_rehab_remaining_dollars) == (20000, 75000)
        assert projection.projected_return_at_rehab_end_dollars == 25000
        assert projection.safe_to_steal_now_dollars == 0                         # nothing in the account to take

    def test_a_steal_lowers_the_projection_by_exactly_what_checking_gains(self):
        projection = _project([_deposit(20000), _draw(30000), _steal(5000)])
        assert projection.own_money_transferred_out_of_the_account_dollars == 5000
        assert projection.projected_return_at_rehab_end_dollars == 20000

    def test_a_change_order_lowers_it_by_its_amount(self):
        projection = _project([_deposit(20000), _draw(30000)], rehab_cost_dollars=103000)
        assert projection.projected_return_at_rehab_end_dollars == 17000

    def test_at_the_end_of_the_rehab_the_balance_is_the_return(self):
        projection = _project([_deposit(20000), _draw(100000), _payment(95000)])
        assert projection.loan_draws_remaining_to_pull_dollars == projection.unpaid_rehab_remaining_dollars == 0
        assert projection.projected_return_at_rehab_end_dollars == projection.current_balance_dollars == 25000


class TestLinkingInTheMiddleOfARehab:
    def test_a_draw_pulled_into_checking_before_the_account_existed(self):
        """The $30k case: pulled $30,000 into checking, nothing paid yet; only the cushion goes into the new account."""
        projection = _project([_deposit(20000)], loan_draws_pulled_before_construction_account_dollars=30000)
        # 20,000 + (100,000 - 30,000) - 95,000: the account will run $5,000 short, because $25,000 of the GC's money sits in checking.
        assert projection.projected_return_at_rehab_end_dollars == -5000
        assert (projection.return_row_amount_dollars, projection.top_up_needed_dollars) == (0, 5000)

    def test_moving_that_draw_into_the_account_too_makes_it_whole(self):
        projection = _project([_deposit(50000)], loan_draws_pulled_before_construction_account_dollars=30000)
        assert projection.projected_return_at_rehab_end_dollars == 25000
        assert projection.top_up_needed_dollars == 0

    def test_the_baselines_can_be_corrected_later(self):
        first_guess = _project([_deposit(20000)], loan_draws_pulled_before_construction_account_dollars=30000,
                               rehab_payments_made_before_construction_account_dollars=0)
        corrected = _project([_deposit(20000)], loan_draws_pulled_before_construction_account_dollars=30000,
                             rehab_payments_made_before_construction_account_dollars=12000)
        assert corrected.projected_return_at_rehab_end_dollars - first_guess.projected_return_at_rehab_end_dollars == 12000


class TestManualAdjustments:
    def test_a_payment_made_from_another_account_raises_the_projection_by_its_amount(self):
        projection = _project([_deposit(20000)], manual_payment_adjustments_dollars=2000)
        assert projection.rehab_payments_made_dollars == 2000
        assert projection.projected_return_at_rehab_end_dollars == 27000

    def test_a_draw_wired_outside_the_account_lowers_it(self):
        projection = _project([_deposit(20000)], manual_draw_adjustments_dollars=10000)
        assert projection.loan_draws_pulled_dollars == 10000
        assert projection.projected_return_at_rehab_end_dollars == 15000

    def test_each_sum_is_its_three_sources(self):
        projection = _project([_deposit(20000), _draw(30000), _payment(8000)],
                              loan_draws_pulled_before_construction_account_dollars=5000, manual_draw_adjustments_dollars=1000,
                              rehab_payments_made_before_construction_account_dollars=4000, manual_payment_adjustments_dollars=2000)
        assert projection.loan_draws_pulled_dollars == (projection.bank_loan_draws_dollars
                                                        + projection.loan_draws_pulled_before_construction_account_dollars
                                                        + projection.manual_draw_adjustments_dollars) == 36000
        assert projection.rehab_payments_made_dollars == (projection.bank_rehab_payments_dollars
                                                          + projection.rehab_payments_made_before_construction_account_dollars
                                                          + projection.manual_payment_adjustments_dollars) == 14000


class TestTransactionOverrides:
    def test_an_ignored_transaction_leaves_the_sums_but_stays_in_the_balance(self):
        other_property = _payment(3000, "materials-for-another-property")
        counted = _project([_deposit(20000), other_property])
        ignored = _project([_deposit(20000), other_property],
                           {"materials-for-another-property": ConstructionAccountTransactionOverride(ignored=True, category_override=None)})
        assert counted.rehab_payments_made_dollars == 3000 and ignored.rehab_payments_made_dollars == 0
        assert counted.current_balance_dollars == ignored.current_balance_dollars == 17000
        # Not a rehab payment: that $3,000 is gone from the account and still owed to the rehab.
        assert ignored.projected_return_at_rehab_end_dollars == counted.projected_return_at_rehab_end_dollars - 3000

    def test_a_refund_recategorised_as_a_rehab_payment_counts_negative(self):
        refund = _transaction("store-refund", 400)
        as_a_draw = _project([_deposit(20000), _payment(1000), refund])
        as_a_refund = _project([_deposit(20000), _payment(1000), refund],
                               {"store-refund": ConstructionAccountTransactionOverride(False, TRANSACTION_CATEGORY_REHAB_PAYMENT)})
        assert (as_a_draw.loan_draws_pulled_dollars, as_a_draw.rehab_payments_made_dollars) == (400, 1000)
        assert (as_a_refund.loan_draws_pulled_dollars, as_a_refund.rehab_payments_made_dollars) == (0, 600)

    def test_a_deposit_from_another_llc_recategorised_as_own_money_counts_toward_the_deposit(self):
        wire_from_another_llc = _transaction("wire-from-the-other-llc", 20000)
        automatic = _project([wire_from_another_llc])
        own_money = _project([wire_from_another_llc],
                             {"wire-from-the-other-llc": ConstructionAccountTransactionOverride(False, TRANSACTION_CATEGORY_OWN_MONEY)})
        assert automatic.loan_draws_pulled_dollars == 20000 and automatic.remaining_deposit_dollars == 20000
        assert own_money.loan_draws_pulled_dollars == 0 and own_money.remaining_deposit_dollars == 0
        assert own_money.projected_return_at_rehab_end_dollars == 25000

    def test_an_internal_transfer_recategorised_as_a_draw(self):
        projection = _project([_deposit(30000, "draw-moved-from-checking")],
                              {"draw-moved-from-checking": ConstructionAccountTransactionOverride(False, TRANSACTION_CATEGORY_LOAN_DRAW)})
        assert projection.loan_draws_pulled_dollars == 30000 and projection.own_money_transferred_into_the_account_dollars == 0

    def test_a_failed_or_cancelled_transaction_is_skipped(self):
        projection = _project([_deposit(20000), _transaction("bounced", -7000, failed=True)])
        assert projection.rehab_payments_made_dollars == 0 and projection.current_balance_dollars == 20000
        (bounced,) = [row for row in categorise_transactions([_transaction("bounced", -7000, failed=True)], {})]
        assert bounced.automatic_category == TRANSACTION_CATEGORY_REHAB_PAYMENT and bounced.effective_category is None


class TestTheDepositAndTheStealLimits:
    def test_a_partial_manual_deposit_leaves_the_rest_due(self):
        projection = _project([_deposit(12000)])
        assert projection.remaining_deposit_dollars == projection.deposit_row_amount_dollars == 8000
        assert projection.return_row_amount_dollars == 25000

    def test_the_cushion_is_the_one_deposit_figure(self):
        projection = _project([], rehab_cushion_dollars=8000)
        assert (projection.rehab_cushion_dollars, projection.rehab_beyond_the_construction_budget_dollars) == (8000, 0)
        assert (projection.total_to_deposit_dollars, projection.remaining_deposit_dollars) == (8000, 8000)

    def test_a_rehab_beyond_the_budget_is_part_of_the_planned_deposit(self):
        projection = _project([], rehab_cost_dollars=110000)
        assert projection.original_steal_dollars == -10000 and projection.total_to_deposit_dollars == 30000
        assert projection.return_row_amount_dollars == 20000   # only the cushion comes back

    def test_a_deposit_row_marked_done_by_hand_asks_for_nothing_more(self):
        projection = _project([_deposit(12000)], deposit_row_is_done=True)
        assert projection.remaining_deposit_dollars == 0 and projection.return_row_amount_dollars == 17000

    def test_safe_to_steal_is_capped_by_the_balance_the_projection_and_the_buffer_to_keep(self):
        assert _project([_deposit(20000), _draw(30000)]).safe_to_steal_now_dollars == 25000          # the projection
        assert _project([_deposit(20000), _payment(15000)]).safe_to_steal_now_dollars == 5000        # the balance
        assert _project([_deposit(20000), _draw(30000)],
                        minimum_balance_to_keep_in_construction_account_dollars=40000).safe_to_steal_now_dollars == 10000
        assert _project([_deposit(20000)], rehab_cost_dollars=130000).safe_to_steal_now_dollars == 0  # a top-up is coming

    def test_stealing_too_much_asks_for_a_top_up_today(self):
        projection = _project([_deposit(20000), _draw(30000), _steal(40000)])
        assert projection.projected_return_at_rehab_end_dollars == -15000
        assert (projection.return_row_amount_dollars, projection.top_up_needed_dollars) == (0, 15000)

    def test_a_closed_out_account_asks_for_nothing_and_returns_nothing(self):
        projection = _project([_deposit(20000), _draw(100000), _payment(95000), _steal(25000)], is_closed_out=True)
        assert (projection.deposit_row_amount_dollars, projection.return_row_amount_dollars,
                projection.top_up_needed_dollars, projection.safe_to_steal_now_dollars) == (0, 0, 0, 0)


# --- In-app transfers (Step E) ---------------------------------------------------------------------------------

from BL.liquidity.constructionAccount.construction_account_projection import (  # noqa: E402
    ConstructionAccountBankSums, InAppTransferNotYetInTheBankFeed, InAppTransferToMatch, bank_sums_with_in_app_transfers_not_yet_in_the_feed,
    match_in_app_transfers_to_the_bank_feed,
)


def _feed_row(transaction_id: str, signed_amount: int, on: date, internal: bool = True) -> ConstructionAccountBankTransaction:
    return ConstructionAccountBankTransaction(mercury_transaction_id=transaction_id, transaction_date=on, counterparty_name="",
                                              signed_amount_dollars=Decimal(signed_amount), is_internal_transfer=internal,
                                              is_failed_or_cancelled=False)


class TestInAppTransfers:
    def test_matched_by_mercury_id_first_then_by_amount_and_date_each_row_once(self):
        transfers = [
            InAppTransferToMatch("a", "mercury-1", Decimal(5000), date(2026, 1, 10)),
            InAppTransferToMatch("b", None, Decimal(5000), date(2026, 1, 10)),
            InAppTransferToMatch("c", None, Decimal(-2000), date(2026, 1, 20)),
        ]
        feed = [_feed_row("mercury-1", 5000, date(2026, 1, 10)), _feed_row("feed-2", 5000, date(2026, 1, 11)),
                _feed_row("too-early", -2000, date(2026, 1, 19)), _feed_row("a-wire", -2000, date(2026, 1, 21), internal=False)]
        matched = match_in_app_transfers_to_the_bank_feed(transfers, feed)
        assert {transfer_id: row.mercury_transaction_id for transfer_id, row in matched.items()} == {"a": "mercury-1", "b": "feed-2"}

    def test_a_row_already_matched_to_an_earlier_transfer_is_not_matched_again(self):
        matched = match_in_app_transfers_to_the_bank_feed(
            [InAppTransferToMatch("b", None, Decimal(5000), date(2026, 1, 10))], [_feed_row("feed-2", 5000, date(2026, 1, 11))], ["feed-2"])
        assert matched == {}

    def test_an_accepted_transfer_counts_at_once_and_moves_the_balance_only_until_a_later_read(self):
        sums = ConstructionAccountBankSums(Decimal(1000), Decimal(1000), Decimal(0), Decimal(0), Decimal(0), Decimal(0))
        after = bank_sums_with_in_app_transfers_not_yet_in_the_feed(sums, [
            InAppTransferNotYetInTheBankFeed(Decimal(5000), requested_after_the_last_bank_read=True),
            InAppTransferNotYetInTheBankFeed(Decimal(-300), requested_after_the_last_bank_read=False),
        ])
        assert (after.own_money_transferred_into_the_account_dollars, after.own_money_transferred_out_of_the_account_dollars) == (5000, 300)
        assert (after.current_balance_dollars, after.available_balance_dollars) == (6000, 6000)
