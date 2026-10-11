"""The Member Loan engine against the approved expected values (tasks/todo/MemberLoan.md, Tests > Unit).

Pure: no database, no HTTP. Every expected number below was agreed in the plan
(the first four are the owner's acceptance tests; the rest were computed with
Python `Decimal` under rules R1 and R4).
"""

from __future__ import annotations

import inspect
import itertools
from datetime import date
from decimal import Decimal

import pytest

from BL.memberLoan.common import member_loan_engine as engine
from BL.memberLoan.common.member_loan_engine import (
    DEFAULT_MEMBER_LOAN_TERMS,
    INTEREST_PAYMENT_ELECTION,
    LENDER_ADDITIONAL_ADVANCE,
    LENDER_WITHDRAWAL,
    YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE,
    YARDEN_CAPITAL_CONTRIBUTION_REDUCTION,
    EffectiveMemberLoanEvent,
    MemberLoanEventRejected,
    MemberLoanTerms,
    build_member_loan_monthly_statement_figures,
    calculate_member_loan_position,
    day_position_in_interest_month,
    preview_member_loan_event,
    preview_member_loan_reversal,
    round_half_up_to_cent,
)

D = Decimal
_application_order_counter = itertools.count(1)


def make_event(event_type: str, effective_date: date, amount: str | None = None, *, election: str | None = None, event_id: str | None = None):
    order = next(_application_order_counter)
    return EffectiveMemberLoanEvent(
        event_id=event_id or f"event-{order}",
        event_type=event_type,
        effective_date=effective_date,
        application_order=order,
        amount=None if amount is None else D(amount),
        interest_election_choice=election,
    )


def position_on(as_of_date: date, events=(), terms=DEFAULT_MEMBER_LOAN_TERMS):
    return calculate_member_loan_position(terms, list(events), as_of_date)


def interest_date_row(position, interest_date: date):
    return next(r for r in position.ledger_rows if r.row_kind == "interest_date" and r.row_date == interest_date)


def periods_for(position, interest_date: date) -> list[Decimal]:
    return [p.interest_for_period for p in position.interest_periods if p.interest_date_the_period_belongs_to == interest_date]


# ---------------------------------------------------------------------------
# The owner's acceptance tests: no events
# ---------------------------------------------------------------------------


class TestAcceptanceWithoutEvents:
    def test_first_interest_date_2026_11_01(self):
        position = position_on(date(2026, 11, 1))
        assert interest_date_row(position, date(2026, 11, 1)).interest_added_to_debt == D("304.10")
        assert position.buckets.total_balance == D("30714.10")

    def test_second_interest_date_2026_12_01(self):
        position = position_on(date(2026, 12, 1))
        assert interest_date_row(position, date(2026, 12, 1)).interest_added_to_debt == D("307.14")
        assert position.buckets.total_balance == D("31021.24")

    def test_third_interest_date_2027_01_01(self):
        position = position_on(date(2027, 1, 1))
        assert interest_date_row(position, date(2027, 1, 1)).interest_added_to_debt == D("310.21")
        assert position.buckets.total_balance == D("31331.45")

    def test_mid_month_2026_12_15_accrued_interest_and_amount_owed(self):
        buckets = position_on(date(2026, 12, 15)).buckets
        assert buckets.accrued_interest == D("144.77")
        assert buckets.amount_owed == D("31166.01")

    def test_buckets_on_the_effective_date(self):
        buckets = position_on(date(2026, 10, 1)).buckets
        assert buckets.original_principal == D("30410.00")
        assert buckets.capitalized_interest == D("0.00")
        assert buckets.accrued_interest == D("0.00")
        assert buckets.amount_owed == D("30410.00")


class TestThirtyThreeSixtyDayCount:
    def test_day_positions(self):
        assert [day_position_in_interest_month(date(2026, 10, d)) for d in (1, 15, 30, 31)] == [0, 14, 29, 30]

    def test_31_day_month_on_the_31st_is_a_full_month(self):
        assert position_on(date(2026, 10, 31)).buckets.accrued_interest == D("304.10")

    def test_february_2027_on_the_28th_then_march_1st(self):
        assert position_on(date(2027, 2, 28)).buckets.accrued_interest == D("284.80")
        position = position_on(date(2027, 3, 1))
        assert interest_date_row(position, date(2027, 3, 1)).interest_added_to_debt == D("316.45")
        assert position.buckets.total_balance == D("31961.21")

    def test_leap_year_february_2028(self):
        terms = MemberLoanTerms(date(2028, 2, 1), D("10000.00"), D("0.01"), date(2029, 2, 1))
        assert position_on(date(2028, 2, 29), terms=terms).buckets.accrued_interest == D("93.33")
        position = position_on(date(2028, 3, 1), terms=terms)
        assert interest_date_row(position, date(2028, 3, 1)).interest_added_to_debt == D("100.00")

    def test_interest_continues_after_maturity(self):
        before_maturity = position_on(date(2027, 10, 1)).buckets.total_balance
        position = position_on(date(2027, 11, 1))
        assert interest_date_row(position, date(2027, 11, 1)).interest_added_to_debt == round_half_up_to_cent(before_maturity * D("0.01"))


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class TestLenderWithdrawal:
    def test_mid_month_withdrawal_takes_accrued_then_capitalized_then_principal(self):
        withdrawal = make_event(LENDER_WITHDRAWAL, date(2026, 12, 15), "1000.00")
        position = position_on(date(2026, 12, 15), [withdrawal])
        row = next(r for r in position.ledger_rows if r.event_id == withdrawal.event_id)
        assert row.allocation.from_accrued_interest == D("144.77")
        assert row.allocation.from_capitalized_interest == D("611.24")
        assert row.allocation.from_original_principal == D("243.99")
        assert position.buckets.original_principal == D("30166.01")
        assert position.buckets.total_balance == D("30166.01")
        next_month = position_on(date(2027, 1, 1), [withdrawal])
        assert interest_date_row(next_month, date(2027, 1, 1)).interest_added_to_debt == D("160.89")
        assert next_month.buckets.total_balance == D("30326.90")

    def test_withdrawal_on_the_31st(self):
        withdrawal = make_event(LENDER_WITHDRAWAL, date(2026, 10, 31), "1000.00")
        row = next(r for r in position_on(date(2026, 10, 31), [withdrawal]).ledger_rows if r.event_id == withdrawal.event_id)
        assert row.allocation.from_accrued_interest == D("304.10")
        assert row.allocation.from_original_principal == D("695.90")
        november = position_on(date(2026, 11, 1), [withdrawal])
        assert interest_date_row(november, date(2026, 11, 1)).interest_added_to_debt == D("0.00")
        assert november.buckets.total_balance == D("29714.10")
        december = position_on(date(2026, 12, 1), [withdrawal])
        assert interest_date_row(december, date(2026, 12, 1)).interest_added_to_debt == D("297.14")

    def test_withdrawal_on_an_interest_date_comes_after_capitalization(self):
        withdrawal = make_event(LENDER_WITHDRAWAL, date(2026, 11, 1), "500.00")
        position = position_on(date(2026, 11, 1), [withdrawal])
        assert position.buckets.total_balance == D("30214.10")
        december = position_on(date(2026, 12, 1), [withdrawal])
        assert interest_date_row(december, date(2026, 12, 1)).interest_added_to_debt == D("302.14")

    def test_withdrawal_of_the_whole_amount_owed_leaves_nothing(self):
        owed = position_on(date(2026, 12, 15)).buckets.amount_owed
        payoff = make_event(LENDER_WITHDRAWAL, date(2026, 12, 15), f"{owed:.2f}")
        later = position_on(date(2027, 3, 1), [payoff]).buckets
        assert later.amount_owed == D("0.00") and later.total_balance == D("0.00")

    def test_withdrawal_above_amount_owed_is_rejected(self):
        with pytest.raises(MemberLoanEventRejected, match="more than"):
            position_on(date(2026, 12, 15), [make_event(LENDER_WITHDRAWAL, date(2026, 12, 15), "31166.02")])

    def test_withdrawal_clears_interest_payable_first(self):
        cash = make_event(INTEREST_PAYMENT_ELECTION, date(2026, 11, 1), election="cash")
        withdrawal = make_event(LENDER_WITHDRAWAL, date(2026, 11, 10), "400.00")
        position = position_on(date(2026, 11, 10), [cash, withdrawal])
        row = next(r for r in position.ledger_rows if r.event_id == withdrawal.event_id)
        assert row.allocation.from_interest_payable == D("304.10")
        assert row.allocation.from_accrued_interest == D("91.23")  # 30,410.00 x 1% x 9/30
        assert row.allocation.from_capitalized_interest == D("0.00")
        assert row.allocation.from_original_principal == D("4.67")


class TestYardenCapitalContribution:
    def test_mid_month_reduction(self):
        reduction = make_event(YARDEN_CAPITAL_CONTRIBUTION_REDUCTION, date(2026, 12, 15), "5000.00")
        position = position_on(date(2026, 12, 15), [reduction])
        assert position.buckets.original_principal == D("25410.00")
        assert position.buckets.capitalized_interest == D("611.24")
        assert position.buckets.lender_capital_credited == D("5000.00")
        january = position_on(date(2027, 1, 1), [reduction])
        assert periods_for(january, date(2027, 1, 1)) == [D("144.77"), D("138.78")]
        assert interest_date_row(january, date(2027, 1, 1)).interest_added_to_debt == D("283.55")
        assert january.buckets.total_balance == D("26304.79")

    def test_reduction_above_original_principal_spills_into_capitalized_then_accrued(self):
        reduction = make_event(YARDEN_CAPITAL_CONTRIBUTION_REDUCTION, date(2026, 12, 15), "31000.00")
        row = next(r for r in position_on(date(2026, 12, 15), [reduction]).ledger_rows if r.event_id == reduction.event_id)
        assert row.allocation.from_original_principal == D("30410.00")
        assert row.allocation.from_capitalized_interest == D("590.00")
        assert row.allocation.from_accrued_interest == D("0.00")
        bigger = make_event(YARDEN_CAPITAL_CONTRIBUTION_REDUCTION, date(2026, 12, 15), "31100.00")
        row = next(r for r in position_on(date(2026, 12, 15), [bigger]).ledger_rows if r.event_id == bigger.event_id)
        assert row.allocation.from_capitalized_interest == D("611.24")
        assert row.allocation.from_accrued_interest == D("78.76")

    def test_reduction_above_amount_owed_is_rejected(self):
        with pytest.raises(MemberLoanEventRejected, match="more than"):
            position_on(date(2026, 12, 15), [make_event(YARDEN_CAPITAL_CONTRIBUTION_REDUCTION, date(2026, 12, 15), "31166.02")])


class TestYardenAdditionalWithdrawal:
    def test_mid_month_increase(self):
        increase = make_event(YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE, date(2026, 12, 15), "2000.00")
        position = position_on(date(2026, 12, 15), [increase])
        assert position.buckets.original_principal == D("32410.00")
        assert position.buckets.lender_capital_credited == D("-2000.00")
        january = position_on(date(2027, 1, 1), [increase])
        assert periods_for(january, date(2027, 1, 1)) == [D("144.77"), D("176.11")]
        assert interest_date_row(january, date(2027, 1, 1)).interest_added_to_debt == D("320.88")
        assert january.buckets.total_balance == D("33342.12")


class TestLenderAdditionalAdvance:
    def test_advance_on_the_1st(self):
        advance = make_event(LENDER_ADDITIONAL_ADVANCE, date(2027, 1, 1), "5000.00")
        assert position_on(date(2027, 1, 1), [advance]).buckets.total_balance == D("36331.45")
        february = position_on(date(2027, 2, 1), [advance])
        assert interest_date_row(february, date(2027, 2, 1)).interest_added_to_debt == D("363.31")
        assert february.buckets.total_balance == D("36694.76")

    def test_advance_on_the_10th(self):
        advance = make_event(LENDER_ADDITIONAL_ADVANCE, date(2027, 1, 10), "5000.00")
        february = position_on(date(2027, 2, 1), [advance])
        assert periods_for(february, date(2027, 2, 1)) == [D("93.99"), D("254.32")]
        assert interest_date_row(february, date(2027, 2, 1)).interest_added_to_debt == D("348.31")
        assert february.buckets.total_balance == D("36679.76")

    def test_advance_on_the_31st_earns_no_days_that_month(self):
        advance = make_event(LENDER_ADDITIONAL_ADVANCE, date(2026, 10, 31), "1000.00")
        november = position_on(date(2026, 11, 1), [advance])
        assert periods_for(november, date(2026, 11, 1)) == [D("304.10"), D("0.00")]
        assert november.buckets.total_balance == D("31714.10")

    def test_advance_on_february_28th_earns_three_days(self):
        advance = make_event(LENDER_ADDITIONAL_ADVANCE, date(2027, 2, 28), "1000.00")
        march = position_on(date(2027, 3, 1), [advance])
        periods = [p for p in march.interest_periods if p.interest_date_the_period_belongs_to == date(2027, 3, 1)]
        assert [p.interest_days_counted for p in periods] == [27, 3]
        assert [p.interest_for_period for p in periods] == [D("284.80"), D("32.64")]
        assert interest_date_row(march, date(2027, 3, 1)).interest_added_to_debt == D("317.44")
        assert march.buckets.total_balance == D("32962.20")


class TestInterestElection:
    def test_cash_election_moves_interest_to_payable_without_compounding(self):
        cash = make_event(INTEREST_PAYMENT_ELECTION, date(2026, 11, 1), election="cash")
        november = position_on(date(2026, 11, 1), [cash]).buckets
        assert november.interest_payable == D("304.10")
        assert november.total_balance == D("30410.00")
        december = position_on(date(2026, 12, 1), [cash])
        assert interest_date_row(december, date(2026, 12, 1)).interest_added_to_debt == D("304.10")

    def test_the_latest_election_for_a_date_wins(self):
        cash = make_event(INTEREST_PAYMENT_ELECTION, date(2026, 11, 1), election="cash")
        reinvest = make_event(INTEREST_PAYMENT_ELECTION, date(2026, 11, 1), election="reinvest")
        assert position_on(date(2026, 11, 1), [cash, reinvest]).buckets.interest_payable == D("0.00")

    def test_an_election_must_be_for_an_interest_date(self):
        with pytest.raises(MemberLoanEventRejected, match="Interest Date"):
            position_on(date(2026, 11, 5), [make_event(INTEREST_PAYMENT_ELECTION, date(2026, 11, 5), election="cash")])


class TestOrderingAndValidation:
    def test_two_events_on_the_same_day_apply_in_approval_order(self):
        advance = make_event(LENDER_ADDITIONAL_ADVANCE, date(2026, 12, 15), "100.00")
        withdrawal = make_event(LENDER_WITHDRAWAL, date(2026, 12, 15), "31266.01")  # only possible after the advance
        assert position_on(date(2026, 12, 15), [withdrawal, advance]).buckets.amount_owed == D("0.00")
        late_advance = EffectiveMemberLoanEvent(advance.event_id, advance.event_type, advance.effective_date, withdrawal.application_order + 1, advance.amount)
        with pytest.raises(MemberLoanEventRejected):
            position_on(date(2026, 12, 15), [withdrawal, late_advance])

    @pytest.mark.parametrize("amount", ["0.00", "-5.00", "10.001"])
    def test_bad_amounts_are_rejected(self, amount):
        with pytest.raises(MemberLoanEventRejected):
            position_on(date(2026, 12, 15), [make_event(LENDER_ADDITIONAL_ADVANCE, date(2026, 12, 15), amount)])

    def test_an_event_before_the_loan_started_is_rejected(self):
        with pytest.raises(MemberLoanEventRejected, match="before the loan started"):
            position_on(date(2026, 10, 5), [make_event(LENDER_ADDITIONAL_ADVANCE, date(2026, 9, 30), "1.00")])

    def test_events_after_the_as_of_date_do_not_count(self):
        later = make_event(LENDER_ADDITIONAL_ADVANCE, date(2027, 1, 10), "5000.00")
        assert position_on(date(2026, 12, 15), [later]).buckets.amount_owed == D("31166.01")


class TestPreviewAndReversal:
    def test_preview_shows_before_and_after_on_the_effective_date(self):
        candidate = make_event(LENDER_WITHDRAWAL, date(2026, 12, 15), "1000.00")
        preview = preview_member_loan_event(DEFAULT_MEMBER_LOAN_TERMS, [], candidate)
        assert preview.buckets_before.amount_owed == D("31166.01")
        assert preview.buckets_after.amount_owed == D("30166.01")
        assert preview.allocation.from_capitalized_interest == D("611.24")

    def test_fingerprint_is_stable_and_changes_when_other_approvals_change_the_figures(self):
        candidate = make_event(LENDER_WITHDRAWAL, date(2026, 12, 15), "1000.00")
        first = preview_member_loan_event(DEFAULT_MEMBER_LOAN_TERMS, [], candidate).preview_fingerprint
        assert preview_member_loan_event(DEFAULT_MEMBER_LOAN_TERMS, [], candidate).preview_fingerprint == first
        unrelated_later = make_event(LENDER_ADDITIONAL_ADVANCE, date(2027, 1, 10), "5000.00")
        assert preview_member_loan_event(DEFAULT_MEMBER_LOAN_TERMS, [unrelated_later], candidate).preview_fingerprint == first
        earlier_advance = make_event(LENDER_ADDITIONAL_ADVANCE, date(2026, 12, 2), "100.00")
        assert preview_member_loan_event(DEFAULT_MEMBER_LOAN_TERMS, [earlier_advance], candidate).preview_fingerprint != first

    def test_approving_an_earlier_withdrawal_that_breaks_a_later_one_is_refused(self):
        later_withdrawal = make_event(LENDER_WITHDRAWAL, date(2026, 12, 20), "31000.00")
        earlier = make_event(LENDER_WITHDRAWAL, date(2026, 12, 10), "1000.00")
        with pytest.raises(MemberLoanEventRejected):
            preview_member_loan_event(DEFAULT_MEMBER_LOAN_TERMS, [later_withdrawal], earlier)

    def test_reversal_preview_returns_to_the_figures_without_the_event(self):
        withdrawal = make_event(LENDER_WITHDRAWAL, date(2026, 12, 15), "1000.00")
        preview = preview_member_loan_reversal(DEFAULT_MEMBER_LOAN_TERMS, [withdrawal], withdrawal.event_id)
        assert preview.buckets_before.amount_owed == D("30166.01")
        assert preview.buckets_after.amount_owed == D("31166.01")

    def test_reversing_an_increase_that_a_later_withdrawal_needs_is_refused(self):
        increase = make_event(YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE, date(2026, 12, 2), "5000.00")
        withdrawal = make_event(LENDER_WITHDRAWAL, date(2026, 12, 20), "34000.00")
        with pytest.raises(MemberLoanEventRejected):
            preview_member_loan_reversal(DEFAULT_MEMBER_LOAN_TERMS, [increase, withdrawal], increase.event_id)


# ---------------------------------------------------------------------------
# Monthly statement figures: every equation adds up
# ---------------------------------------------------------------------------

STATEMENT_SCENARIOS = {
    "no events": [],
    "mid-month withdrawal": [make_event(LENDER_WITHDRAWAL, date(2026, 12, 15), "1000.00")],
    "withdrawal on the 31st": [make_event(LENDER_WITHDRAWAL, date(2026, 10, 31), "1000.00")],
    "reduction": [make_event(YARDEN_CAPITAL_CONTRIBUTION_REDUCTION, date(2026, 12, 15), "5000.00")],
    "increase": [make_event(YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE, date(2026, 12, 15), "2000.00")],
    "advance on the 10th": [make_event(LENDER_ADDITIONAL_ADVANCE, date(2027, 1, 10), "5000.00")],
    "advance on feb 28": [make_event(LENDER_ADDITIONAL_ADVANCE, date(2027, 2, 28), "1000.00")],
    "cash election": [make_event(INTEREST_PAYMENT_ELECTION, date(2026, 11, 1), election="cash")],
    "event on the interest date": [make_event(LENDER_WITHDRAWAL, date(2026, 11, 1), "500.00")],
}


@pytest.mark.parametrize("scenario", sorted(STATEMENT_SCENARIOS))
def test_every_monthly_statement_adds_up(scenario):
    events = STATEMENT_SCENARIOS[scenario]
    month = date(2026, 10, 1)
    while month <= date(2027, 3, 1):
        figures = build_member_loan_monthly_statement_figures(DEFAULT_MEMBER_LOAN_TERMS, events, month)
        assert sum(s.signed_change_to_total_balance for s in figures.debt_equation_steps) == figures.closing_buckets.total_balance
        month = engine.first_day_of_next_month(month)


def test_december_statement_with_a_mid_month_withdrawal():
    withdrawal = STATEMENT_SCENARIOS["mid-month withdrawal"][0]
    figures = build_member_loan_monthly_statement_figures(DEFAULT_MEMBER_LOAN_TERMS, [withdrawal], date(2026, 12, 1))
    assert figures.opening_buckets.total_balance == D("31021.24")
    assert [p.interest_for_period for p in figures.interest_periods_in_month] == [D("144.77"), D("160.89")]
    assert figures.interest_earned_in_month == D("305.66")
    assert figures.closing_interest_date_row.interest_already_settled_in_month == D("144.77")
    assert figures.closing_buckets.total_balance == D("30326.90")
    assert [s.signed_change_to_total_balance for s in figures.debt_equation_steps] == [D("31021.24"), D("-855.23"), D("160.89")]


def test_the_engine_never_uses_float():
    source = inspect.getsource(engine)
    assert "float(" not in source and ": float" not in source
