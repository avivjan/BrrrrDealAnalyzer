"""The dated Cash Needed schedule (Lowest ARV): one row per cash item, every dollar of Cash Needed accounted for.

Every dollar of Cash Needed is a dated row, the rehab cushion included (a hold on the purchase closing date): the
rows add up exactly to -total_cash_needed on every scenario (an internal check; nothing on screen shows it). Plus
the timing and shape rules:
no money-out row after the refi, money out before money in on a shared date, (item_key, date) unique, whole cents,
the refi-day rows in their order, and none of the rows that must never exist.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from BL.analyze.analyzeBRRR import compute_brrr_with_intermediates
from BL.analyze.brrrSteps.cash_needed_schedule import CASH_NEEDED_SCHEDULE_ITEM_KEYS
from ReqRes.common.analyze_inputs import analyzeBRRRReq

ONE_CENT = Decimal("0.01")

RECONCILIATION_SCENARIOS = {
    "base": {},
    "positive_stolen_money": {"constructionLoanBudget": 70, "rehabContingency": 0},
    "negative_stolen_money": {"constructionLoanBudget": 40},
    "tenant_after_the_refi": {"daysUntilRented": 400},
    "seller_already_paid_october_closing": {"buyClosingDate": "2026-10-01", "contractDate": "2026-09-20", "daysUntilRefi": 300},
    "seller_already_paid_december_closing": {"buyClosingDate": "2026-12-15", "contractDate": "2026-12-01"},
    "refi_lender_collects_the_whole_tax_bill": {"buyClosingDate": "2026-08-20", "contractDate": "2026-08-01", "daysUntilRefi": 200,
                                                 "propertyTaxCollectionAtRefi": "full_tax_bill_collected_at_refi"},
    "insurance_outside_both_closings": {"insurancePurchaseBillPaymentTiming": "outside_purchase_closing",
                                        "insuranceRefiBillPaymentTiming": "outside_refi_closing", "monthlyInsuranceUntilRefi": 90},
    "short_hold_refi_inside_the_first_month": {"buyClosingDate": "2026-04-15", "contractDate": "2026-04-01", "daysUntilRefi": 15,
                                               "daysUntilRented": 10, "daysUntilRehabCompleted": 5},
    "short_hold_refi_in_the_next_month": {"buyClosingDate": "2026-04-15", "contractDate": "2026-04-01", "daysUntilRefi": 25,
                                          "daysUntilRented": 20, "daysUntilRehabCompleted": 10},
    "refi_on_a_first": {"daysUntilRefi": 172, "montly_hoa": 450, "monthlyInsuranceUntilRefi": 90},   # 2026-01-10 -> 2026-07-01
    "november_30_inside_the_hold_with_a_shortfall": {"buyClosingDate": "2026-08-20", "contractDate": "2026-08-01", "daysUntilRefi": 200,
                                                     "monthlyPropertyTaxBucketDeposit": 100},
    "november_30_fallback_deposit": {"buyClosingDate": "2026-11-20", "contractDate": "2026-11-01", "daysUntilRefi": 120, "daysUntilRented": 60,
                                     "sellerPaidCurrentYearTaxes": False},
    "no_first_after_the_rehab": {"daysUntilRefi": 60, "daysUntilRehabCompleted": 55, "daysUntilRented": 55},   # rehab 03-06, refi 03-11
    "negative_cash_to_close": {"earnestMoneyDeposit": 60_000},
    "refi_shortfall_and_reserves_from_pocket": {"arv_in_thousands": 250, "maintenanceReserve": 30_000},
    "with_hoa": {"montly_hoa": 450},
    "we_pay_the_tax_bill_at_a_november_closing": {"buyClosingDate": "2026-11-20", "contractDate": "2026-11-10",
                                                  "buyerPaysCurrentYearTaxBillAtPurchaseClosing": True},
    "sub_cent_amounts": {"annual_property_taxes": 3087.97, "HMLInterestRate": 11.375, "maintenanceBeforeRefi": 500.01},
}


def _compute(brrrr_payload: dict, overrides: dict):
    return compute_brrr_with_intermediates(analyzeBRRRReq.model_validate({**brrrr_payload, **overrides}))


def _rows_of(results, item_key: str):
    return [row for row in results.cash_needed_schedule_at_lowest_arv.dated_cash_rows if row.item_key == item_key]


@pytest.mark.parametrize("scenario", list(RECONCILIATION_SCENARIOS))
class TestTheScheduleAccountsForEveryDollarOfCashNeeded:
    def test_the_dated_rows_add_up_exactly_to_cash_needed(self, brrrr_payload, scenario):
        results = _compute(brrrr_payload, RECONCILIATION_SCENARIOS[scenario])
        schedule = results.cash_needed_schedule_at_lowest_arv
        assert sum(row.signed_amount_dollars for row in schedule.dated_cash_rows) == -results.total_cash_needed

    def test_the_shape_and_timing_rules(self, brrrr_payload, scenario):
        results = _compute(brrrr_payload, RECONCILIATION_SCENARIOS[scenario])
        rows = results.cash_needed_schedule_at_lowest_arv.dated_cash_rows
        assert rows, "a deal always has cash rows"
        assert [(row.date, row.sequence_within_day) for row in rows] == sorted((row.date, row.sequence_within_day) for row in rows)
        for previous_row, row in zip(rows, rows[1:]):
            expected_sequence = previous_row.sequence_within_day + 1 if row.date == previous_row.date else 0
            assert row.sequence_within_day == expected_sequence
            if row.date == previous_row.date:
                assert not (previous_row.signed_amount_dollars > 0 > row.signed_amount_dollars), "money out comes before money in"
        assert rows[0].sequence_within_day == 0
        assert len({(row.item_key, row.date) for row in rows}) == len(rows)
        assert all(row.item_key in CASH_NEEDED_SCHEDULE_ITEM_KEYS for row in rows)
        assert all(row.signed_amount_dollars != 0 and row.signed_amount_dollars == row.signed_amount_dollars.quantize(ONE_CENT) for row in rows)
        assert all(row.date <= results.refi_closing_date for row in rows if row.signed_amount_dollars < 0), "no money out after the refi"
        assert all(row.date >= results.buy_closing_date or row.item_key == "earnest_money_deposit" for row in rows)

    def test_the_rows_that_must_never_exist(self, brrrr_payload, scenario):
        results = _compute(brrrr_payload, RECONCILIATION_SCENARIOS[scenario])
        rows = results.cash_needed_schedule_at_lowest_arv.dated_cash_rows
        item_keys = {row.item_key for row in rows}
        # Never the wire, the full reserves transfer, insurance C inside the closing, the tax lump,
        # or anything already inside Cash to Close (Buy).
        assert not item_keys & {"cash_out_routi_conservative", "cash_out_routi", "reserves_total", "insurance_bill_at_refi_inside_closing",
                                "property_tax_lump_sum_at_refi_closing", "hml_points", "prepaid_interest_buy",
                                "seller_tax_credit", "insurance_bill_at_purchase_inside_closing", "closing_costs_buy_total"}
        assert len(_rows_of(results, "stolen_money")) <= 1

    def test_each_items_rows_add_up_to_the_engines_figure_for_it_within_a_cent(self, brrrr_payload, scenario):
        """The rows are pinned to add up to Cash Needed; this proves no item absorbed someone else's dollars."""
        results = _compute(brrrr_payload, RECONCILIATION_SCENARIOS[scenario])
        payload = {**brrrr_payload, **RECONCILIATION_SCENARIOS[scenario]}
        money = lambda alias: Decimal(str(payload[alias]))   # noqa: E731
        expected_signed_total_by_item_key = {
            "earnest_money_deposit": -money("earnestMoneyDeposit"),
            "cash_to_close_buy": -results.cash_to_close_buy,
            "insurance_bill_at_purchase_outside_closing": -results.insurance_bill_at_purchase_outside_closing,
            "rehab_cushion": -money("rehabCushion"),
            "seller_tax_credit_set_aside_in_tax_bucket": -results.seller_tax_credit_set_aside_in_tax_bucket,
            "property_tax_bucket_deposit": -results.property_tax_bucket_deposit * results.property_tax_bucket_first_bill_deposit_count_until_refi,
            "property_tax_bucket_deposit_after_first_payment":
                -results.property_tax_bucket_deposit_after_first_payment * results.property_tax_bucket_later_deposit_count_until_refi,
            "property_tax_bucket_shortfall_topped_up_on_november_30": -results.property_tax_bucket_shortfall_topped_up_on_november_30,
            "hml_interest_paid_monthly": -results.hml_interest_paid_monthly,
            "hoa_dues": -results.hoa_dues_until_refi,
            "insurance_paid_monthly_until_refi": -results.insurance_paid_monthly_until_refi,
            "utilities": -results.utilities_until_rented,
            "maintenance_before_refi": -money("maintenanceBeforeRefi"),
            "appliances": -money("appliances"),
            "appraisal_fee": -money("appraisalFee"),
            "survey_fee": -money("surveyFee"),
            "stolen_money": results.stolen_money,
            "pre_refi_rental_income": results.pre_refi_rental_income,
            "cash_to_refi_table_conservative": -results.cash_to_refi_table_conservative,
            "reserves_funded_from_own_pocket_at_lowest_arv": -results.reserves_funded_from_own_pocket_at_lowest_arv,
            "insurance_bill_at_refi_outside_closing": -results.insurance_bill_at_refi_outside_closing,
            "property_tax_bucket_balance_released_at_refi": results.property_tax_bucket_balance_released_at_refi,
        }
        assert set(expected_signed_total_by_item_key) == set(CASH_NEEDED_SCHEDULE_ITEM_KEYS)
        for item_key, expected_signed_total in expected_signed_total_by_item_key.items():
            rows_total = sum((row.signed_amount_dollars for row in _rows_of(results, item_key)), Decimal("0"))
            assert abs(rows_total - expected_signed_total) <= ONE_CENT, (item_key, rows_total, expected_signed_total)

    def test_the_hml_rows_add_up_to_the_interest_paid_monthly_to_the_cent(self, brrrr_payload, scenario):
        results = _compute(brrrr_payload, RECONCILIATION_SCENARIOS[scenario])
        hml_rows = _rows_of(results, "hml_interest_paid_monthly")
        assert abs(-sum((row.signed_amount_dollars for row in hml_rows), Decimal("0")) - results.hml_interest_paid_monthly) <= ONE_CENT
        assert [row.date for row in hml_rows] == list(results.hml_interest_monthly_payment_dates)


class TestEachItemOnItsDate:
    def test_the_base_deal(self, brrrr_payload):
        # contract 2026-01-03, closing 2026-01-10, rehab done 2026-02-24, tenant 2026-04-10, refi 2026-07-09
        results = _compute(brrrr_payload, {})
        dates_of = lambda item_key: [row.date for row in _rows_of(results, item_key)]   # noqa: E731
        assert dates_of("earnest_money_deposit") == [date(2026, 1, 3)]
        assert dates_of("cash_to_close_buy") == [date(2026, 1, 10)]
        assert dates_of("seller_tax_credit_set_aside_in_tax_bucket") == [date(2026, 1, 11)]
        assert dates_of("property_tax_bucket_deposit") == [date(2026, month, 15) for month in range(1, 7)]
        # Close Jan 10: Jan was prepaid, so nothing on Feb 1; Feb is paid Mar 1, ..., Jun on Jul 1 (before the Jul 9 refi).
        assert dates_of("hml_interest_paid_monthly") == [date(2026, month, 1) for month in range(3, 8)]
        assert dates_of("utilities") == [date(2026, month, 1) for month in range(2, 6)]
        assert dates_of("maintenance_before_refi") == [date(2026, month, 1) for month in range(3, 8)]
        assert dates_of("appliances") == [date(2026, 2, 24)]   # on the rehab completion
        assert dates_of("rehab_cushion") == [date(2026, 1, 10)]
        assert dates_of("appraisal_fee") == dates_of("survey_fee") == [date(2026, 2, 24)]
        assert dates_of("pre_refi_rental_income") == [date(2026, 5, 1), date(2026, 6, 1), date(2026, 7, 1)]
        assert dates_of("cash_to_refi_table_conservative") == dates_of("reserves_funded_from_own_pocket_at_lowest_arv") == [date(2026, 7, 9)]
        assert all(row.signed_amount_dollars > 0 for row in _rows_of(results, "pre_refi_rental_income"))
        assert all("Lowest-ARV refi" in row.description for row in results.cash_needed_schedule_at_lowest_arv.dated_cash_rows
                   if row.date == results.refi_closing_date)

    def test_the_cushion_is_an_ordinary_row_on_the_purchase_closing(self, brrrr_payload):
        results = _compute(brrrr_payload, {})
        (cushion,) = _rows_of(results, "rehab_cushion")
        assert (cushion.date, cushion.signed_amount_dollars) == (date(2026, 1, 10), Decimal("-5000.00"))
        assert "hold" in cushion.description
        # Money out on the closing day: after the cash to close, in catalogue order.
        closing_day = [row.item_key for row in results.cash_needed_schedule_at_lowest_arv.dated_cash_rows if row.date == date(2026, 1, 10)]
        assert closing_day[:2] == ["cash_to_close_buy", "rehab_cushion"]
        assert _rows_of(_compute(brrrr_payload, {"rehabCushion": 0}), "rehab_cushion") == []

    def test_stolen_money_comes_back_on_the_rehab_completion_or_goes_out_at_closing(self, brrrr_payload):
        (positive,) = _rows_of(_compute(brrrr_payload, {"constructionLoanBudget": 70, "rehabContingency": 0}), "stolen_money")
        assert (positive.date, positive.signed_amount_dollars) == (date(2026, 2, 24), Decimal("20000.00"))
        (negative,) = _rows_of(_compute(brrrr_payload, {"constructionLoanBudget": 40}), "stolen_money")
        assert (negative.date, negative.signed_amount_dollars) == (date(2026, 1, 10), Decimal("-15000.00"))
        assert _rows_of(_compute(brrrr_payload, {}), "stolen_money") == []

    def test_the_refi_day_rows_in_their_order(self, brrrr_payload):
        results = _compute(brrrr_payload, {"arv_in_thousands": 250, "maintenanceReserve": 30_000,
                                           "insuranceRefiBillPaymentTiming": "outside_refi_closing",
                                           "buyClosingDate": "2026-08-20", "contractDate": "2026-08-01", "daysUntilRefi": 200,
                                           "propertyTaxCollectionAtRefi": "full_tax_bill_collected_at_refi"})
        refi_rows = [row.item_key for row in results.cash_needed_schedule_at_lowest_arv.dated_cash_rows if row.date == results.refi_closing_date]
        assert refi_rows == ["cash_to_refi_table_conservative", "reserves_funded_from_own_pocket_at_lowest_arv",
                             "insurance_bill_at_refi_outside_closing", "property_tax_bucket_balance_released_at_refi"]
        (released,) = _rows_of(results, "property_tax_bucket_balance_released_at_refi")
        assert released.signed_amount_dollars > 0

    def test_a_refi_on_a_first_keeps_the_monthly_rows_on_that_day_but_pays_the_last_hml_month_in_the_payoff(self, brrrr_payload):
        results = _compute(brrrr_payload, {"daysUntilRefi": 172, "montly_hoa": 450, "monthlyInsuranceUntilRefi": 90})   # refi 2026-07-01
        refi_day = date(2026, 7, 1)
        assert results.refi_closing_date == refi_day
        assert results.hml_interest_days_accrued_into_refi_payoff == 30   # June
        assert refi_day not in [row.date for row in _rows_of(results, "hml_interest_paid_monthly")]
        refi_day_rows = [row for row in results.cash_needed_schedule_at_lowest_arv.dated_cash_rows if row.date == refi_day]
        assert [row.item_key for row in refi_day_rows][:2] == ["hoa_dues", "insurance_paid_monthly_until_refi"]
        assert "pre_refi_rental_income" in [row.item_key for row in refi_day_rows]

    def test_the_seller_already_paid_tax_bucket_starts_on_december_15(self, brrrr_payload):
        results = _compute(brrrr_payload, {"buyClosingDate": "2026-10-01", "contractDate": "2026-09-20", "daysUntilRefi": 120})
        assert results.seller_paid_current_year_taxes is True
        assert [row.date for row in _rows_of(results, "property_tax_bucket_deposit")] == [date(2026, 12, 15), date(2027, 1, 15)]
        assert _rows_of(results, "seller_tax_credit_set_aside_in_tax_bucket") == []   # a negative credit stays in cash to close

    def test_a_november_30_inside_the_hold(self, brrrr_payload):
        results = _compute(brrrr_payload, {"buyClosingDate": "2026-08-20", "contractDate": "2026-08-01", "daysUntilRefi": 200,
                                           "monthlyPropertyTaxBucketDeposit": 100})   # refi 2027-03-08
        (shortfall,) = _rows_of(results, "property_tax_bucket_shortfall_topped_up_on_november_30")
        assert shortfall.date == date(2026, 11, 30) and shortfall.signed_amount_dollars < 0
        assert [row.date for row in _rows_of(results, "property_tax_bucket_deposit_after_first_payment")] == [
            date(2026, 12, 15), date(2027, 1, 15), date(2027, 2, 15)]

    def test_maintenance_with_no_first_after_the_rehab_goes_on_the_rehab_completion(self, brrrr_payload):
        results = _compute(brrrr_payload, RECONCILIATION_SCENARIOS["no_first_after_the_rehab"])
        (maintenance,) = _rows_of(results, "maintenance_before_refi")
        assert (maintenance.date, maintenance.signed_amount_dollars) == (results.rehab_completed_date, Decimal("-500.00"))

    def test_appliances_follow_the_rehab_completion(self, brrrr_payload):
        results = _compute(brrrr_payload, {"daysUntilRefi": 40, "daysUntilRehabCompleted": 30, "daysUntilRented": 30})   # rehab done 2026-02-09
        assert [row.date for row in _rows_of(results, "appliances")] == [date(2026, 2, 9)]

    def test_every_row_is_within_a_cent_of_its_exact_amount(self, brrrr_payload):
        results = _compute(brrrr_payload, RECONCILIATION_SCENARIOS["sub_cent_amounts"])
        deposits = _rows_of(results, "property_tax_bucket_deposit")
        assert all(abs(-row.signed_amount_dollars - results.property_tax_bucket_deposit) <= ONE_CENT for row in deposits)


class TestTheDealsKeyDatesAmongTheRows:
    """The deal's milestones are listed with the schedule so it reads as a timeline: markers, never cash."""

    def _milestones_of(self, results):
        return [(milestone.date, milestone.milestone_key, milestone.description)
                for milestone in results.cash_needed_schedule_at_lowest_arv.deal_milestones]

    def test_deal_milestones_are_the_contract_closing_rehab_tenant_and_refi_dates_in_order(self, brrrr_payload):
        assert self._milestones_of(_compute(brrrr_payload, {})) == [
            (date(2026, 1, 3), "contract_signed", "Contract signed"),
            (date(2026, 1, 10), "purchase_closed", "Purchase closing"),
            (date(2026, 2, 24), "rehab_completed", "Rehab completed"),    # + 45 days
            (date(2026, 4, 10), "tenant_moved_in", "Tenant moves in"),     # + 90 days
            (date(2026, 7, 9), "refi_closed", "Refi closing"),             # + 180 days
        ]

    def test_the_november_30_tax_bill_is_a_milestone_only_inside_the_hold(self, brrrr_payload):
        january_closing = _compute(brrrr_payload, {})
        assert "property_tax_bill_paid_on_november_30" not in [key for _, key, _ in self._milestones_of(january_closing)]
        august_closing = _compute(brrrr_payload, RECONCILIATION_SCENARIOS["november_30_inside_the_hold_with_a_shortfall"])
        milestones = self._milestones_of(august_closing)
        assert (date(2026, 11, 30), "property_tax_bill_paid_on_november_30", "Property tax bill paid from the tax bucket (Nov 30)") in milestones
        assert [milestone_date for milestone_date, _, _ in milestones] == sorted(milestone_date for milestone_date, _, _ in milestones)
        assert milestones[-1][1] == "refi_closed"

    def test_milestones_sharing_a_day_keep_the_lifecycle_order(self, brrrr_payload):
        same_day = _compute(brrrr_payload, {"daysUntilRehabCompleted": 0, "daysUntilRented": 0})
        assert [key for _, key, _ in self._milestones_of(same_day)][:4] == ["contract_signed", "purchase_closed", "rehab_completed", "tenant_moved_in"]

    @pytest.mark.parametrize("scenario", list(RECONCILIATION_SCENARIOS))
    def test_milestones_are_not_cash_rows_and_cash_needed_is_unchanged(self, brrrr_payload, scenario):
        results = _compute(brrrr_payload, RECONCILIATION_SCENARIOS[scenario])
        schedule = results.cash_needed_schedule_at_lowest_arv
        milestone_descriptions = {milestone.description for milestone in schedule.deal_milestones}
        assert not milestone_descriptions & {row.description for row in schedule.dated_cash_rows}
        assert {row.item_key for row in schedule.dated_cash_rows} <= set(CASH_NEEDED_SCHEDULE_ITEM_KEYS)
        assert -sum((row.signed_amount_dollars for row in schedule.dated_cash_rows), Decimal("0")) == results.total_cash_needed


class TestTheScheduleOnTheApi:
    def test_analyze_returns_the_schedule_and_it_adds_up(self, client, brrrr_payload):
        body = client.post("/analyze/brrr", json=brrrr_payload).json()
        schedule = body["cash_needed_schedule_at_lowest_arv"]
        assert set(schedule) == {"dated_cash_rows", "deal_milestones"}
        assert set(schedule["deal_milestones"][0]) == {"date", "milestone_key", "description"}
        rows = schedule["dated_cash_rows"]
        assert set(rows[0]) == {"date", "sequence_within_day", "description", "signed_amount_dollars", "item_key"}
        assert float(-sum(Decimal(row["signed_amount_dollars"]) for row in rows)) == body["total_cash_needed_for_deal"]

    def test_a_saved_deal_carries_the_schedule(self, client, brrrr_payload):
        deal = client.post("/active-deals", json=brrrr_payload).json()
        listed = client.get("/active-deals").json()[0]
        assert deal["cash_needed_schedule_at_lowest_arv"] == listed["cash_needed_schedule_at_lowest_arv"]
        assert listed["cash_needed_schedule_at_lowest_arv"]["dated_cash_rows"]

    def test_the_mcp_analyze_brrr_tool_returns_the_schedule_and_it_adds_up(self, client, brrrr_payload):
        from tests.mcp_helpers import call_json
        analyzed = call_json("analyze_brrr", body=brrrr_payload)
        schedule = analyzed["cash_needed_schedule_at_lowest_arv"]
        assert float(-sum(Decimal(row["signed_amount_dollars"]) for row in schedule["dated_cash_rows"])) == analyzed["total_cash_needed_for_deal"]

    def test_the_mcp_instructions_say_the_dates_are_required_and_describe_the_schedule(self):
        import mcp_server
        assert "contractDate and buyClosingDate" in mcp_server.INSTRUCTIONS and "a missing one is a 422" in mcp_server.INSTRUCTIONS
        assert "cash_needed_schedule_at_lowest_arv" in mcp_server.INSTRUCTIONS


class TestHardMoneyInterestPaidMonthlyIsRateOverTwelve:
    """Each full month of hard-money interest is the loan x the annual rate / 12 (1% at 12%), whatever the month's
    length (tasks/todo/LiquidityDealTransactionsAndHmlMonthlyInterest.md, A). Only the partial months are per diem."""

    # 2026-12-10 -> 2027-07-08: December's rest is prepaid at the closing; January (31), February (28), March (31),
    # April (30), May (31) and June (30) are paid on Feb 1 .. Jul 1; July 1 .. 7 are inside the payoff.
    MIXED_MONTH_LENGTHS = {"buyClosingDate": "2026-12-10", "contractDate": "2026-12-01", "daysUntilRefi": 210, "HMLInterestRate": 12}

    def test_every_monthly_row_is_exactly_one_twelfth_of_the_annual_rate(self, brrrr_payload):
        results = _compute(brrrr_payload, self.MIXED_MONTH_LENGTHS)
        monthly_payment = (results.hml_amount * Decimal("12") / Decimal("12") / Decimal("100")).quantize(ONE_CENT)
        rows = _rows_of(results, "hml_interest_paid_monthly")
        assert [row.date for row in rows] == [date(2027, month, 1) for month in range(2, 8)]
        assert {-row.signed_amount_dollars for row in rows} == {monthly_payment}
        assert monthly_payment == (results.hml_amount / Decimal("100")).quantize(ONE_CENT)   # 1% at 12%

    def test_the_total_is_the_prepaid_days_plus_the_monthly_payments_plus_the_payoff_days(self, brrrr_payload):
        results = _compute(brrrr_payload, self.MIXED_MONTH_LENGTHS)
        per_diem = results.hml_amount * Decimal("12") / Decimal("360") / Decimal("100")
        assert results.prepaid_interest_buy == per_diem * 22                      # Dec 10 .. Dec 31
        assert results.hml_interest_paid_monthly == results.hml_amount * Decimal("0.01") * 6
        assert results.hml_interest_accrued_into_refi_payoff == per_diem * results.hml_interest_days_accrued_into_refi_payoff
        assert results.hml_interest == (results.prepaid_interest_buy + results.hml_interest_paid_monthly
                                        + results.hml_interest_accrued_into_refi_payoff)

    def test_the_schedule_still_adds_up_to_cash_needed(self, brrrr_payload):
        results = _compute(brrrr_payload, self.MIXED_MONTH_LENGTHS)
        total = sum(row.signed_amount_dollars for row in results.cash_needed_schedule_at_lowest_arv.dated_cash_rows)
        assert total == -results.total_cash_needed
