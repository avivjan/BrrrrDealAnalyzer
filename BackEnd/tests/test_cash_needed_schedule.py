"""The dated Cash Needed schedule (Lowest ARV): one row per cash item, every dollar of Cash Needed accounted for.

Reconciliation, exact on every scenario: the dated rows add up to -(total_cash_needed - rehab cushion), and the
cushion is held (never a row) from the purchase closing to the rehab completion. Plus the timing and shape rules:
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
    "sub_cent_amounts": {"annual_property_taxes": 3087.97, "HMLInterestRate": 11.375, "maintenanceBeforeRefi": 500.01},
}


def _compute(brrrr_payload: dict, overrides: dict):
    return compute_brrr_with_intermediates(analyzeBRRRReq.model_validate({**brrrr_payload, **overrides}))


def _rows_of(results, item_key: str):
    return [row for row in results.cash_needed_schedule_at_lowest_arv.dated_cash_rows if row.item_key == item_key]


@pytest.mark.parametrize("scenario", list(RECONCILIATION_SCENARIOS))
class TestTheScheduleAccountsForEveryDollarOfCashNeeded:
    def test_the_dated_rows_add_up_exactly_to_cash_needed_less_the_cushion(self, brrrr_payload, scenario):
        results = _compute(brrrr_payload, RECONCILIATION_SCENARIOS[scenario])
        schedule = results.cash_needed_schedule_at_lowest_arv
        rehab_cushion = Decimal(str(brrrr_payload["rehabCushion"]))
        assert sum(row.signed_amount_dollars for row in schedule.dated_cash_rows) == -(results.total_cash_needed - rehab_cushion)
        assert schedule.dated_cash_rows_net_outflow_dollars + schedule.cash_that_must_stay_in_account_total_dollars == results.total_cash_needed
        assert schedule.total_cash_needed_dollars == results.total_cash_needed

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
        # Never the wire, the full reserves transfer, insurance C inside the closing, the tax lump, the cushion,
        # or anything already inside Cash to Close (Buy).
        assert not item_keys & {"cash_out_routi_conservative", "cash_out_routi", "reserves_total", "insurance_bill_at_refi_inside_closing",
                                "property_tax_lump_sum_at_refi_closing", "rehab_cushion", "hml_points", "prepaid_interest_buy",
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
        assert dates_of("appliances") == [date(2026, 3, 10)]
        assert dates_of("appraisal_fee") == dates_of("survey_fee") == [date(2026, 2, 24)]
        assert dates_of("pre_refi_rental_income") == [date(2026, 5, 1), date(2026, 6, 1), date(2026, 7, 1)]
        assert dates_of("cash_to_refi_table_conservative") == dates_of("reserves_funded_from_own_pocket_at_lowest_arv") == [date(2026, 7, 9)]
        assert all(row.signed_amount_dollars > 0 for row in _rows_of(results, "pre_refi_rental_income"))
        assert all("Lowest-ARV refi" in row.description for row in results.cash_needed_schedule_at_lowest_arv.dated_cash_rows
                   if row.date == results.refi_closing_date)

    def test_the_cushion_must_stay_in_the_account_from_closing_to_rehab_completion(self, brrrr_payload):
        results = _compute(brrrr_payload, {})
        (cushion,) = results.cash_needed_schedule_at_lowest_arv.cash_that_must_stay_in_account
        assert (cushion.item_key, cushion.amount_dollars) == ("rehab_cushion", Decimal("5000"))
        assert (cushion.reserve_starts_on_date, cushion.reserve_ends_on_date) == (date(2026, 1, 10), date(2026, 2, 24))
        assert results.cash_needed_schedule_at_lowest_arv.cash_that_must_stay_in_account_total_dollars == Decimal("5000")

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

    def test_appliances_are_capped_at_the_refi(self, brrrr_payload):
        results = _compute(brrrr_payload, {"daysUntilRefi": 40, "daysUntilRehabCompleted": 30, "daysUntilRented": 30})   # refi 2026-02-19
        assert [row.date for row in _rows_of(results, "appliances")] == [date(2026, 2, 19)]

    def test_every_row_is_within_a_cent_of_its_exact_amount(self, brrrr_payload):
        results = _compute(brrrr_payload, RECONCILIATION_SCENARIOS["sub_cent_amounts"])
        deposits = _rows_of(results, "property_tax_bucket_deposit")
        assert all(abs(-row.signed_amount_dollars - results.property_tax_bucket_deposit) <= ONE_CENT for row in deposits)


class TestTheScheduleOnTheApi:
    def test_analyze_returns_the_schedule_and_its_summary_adds_up(self, client, brrrr_payload):
        body = client.post("/analyze/brrr", json=brrrr_payload).json()
        schedule = body["cash_needed_schedule_at_lowest_arv"]
        rows = schedule["dated_cash_rows"]
        assert set(rows[0]) == {"date", "sequence_within_day", "description", "signed_amount_dollars", "item_key"}
        net_outflow = -sum(Decimal(row["signed_amount_dollars"]) for row in rows)
        assert net_outflow == Decimal(schedule["dated_cash_rows_net_outflow_dollars"])
        assert net_outflow + Decimal(schedule["cash_that_must_stay_in_account_total_dollars"]) == Decimal(schedule["total_cash_needed_dollars"])
        assert float(schedule["total_cash_needed_dollars"]) == body["total_cash_needed_for_deal"]
        assert schedule["cash_that_must_stay_in_account"][0]["reserve_starts_on_date"] == brrrr_payload["buyClosingDate"]

    def test_a_saved_deal_carries_the_schedule(self, client, brrrr_payload):
        deal = client.post("/active-deals", json=brrrr_payload).json()
        listed = client.get("/active-deals").json()[0]
        assert deal["cash_needed_schedule_at_lowest_arv"] == listed["cash_needed_schedule_at_lowest_arv"]
        assert listed["cash_needed_schedule_at_lowest_arv"]["dated_cash_rows"]

    def test_the_mcp_analyze_brrr_tool_returns_the_schedule_and_it_adds_up(self, client, brrrr_payload):
        from tests.mcp_helpers import call_json
        analyzed = call_json("analyze_brrr", body=brrrr_payload)
        schedule = analyzed["cash_needed_schedule_at_lowest_arv"]
        net_outflow = -sum(Decimal(row["signed_amount_dollars"]) for row in schedule["dated_cash_rows"])
        assert net_outflow + Decimal(schedule["cash_that_must_stay_in_account_total_dollars"]) == Decimal(schedule["total_cash_needed_dollars"])
        assert float(schedule["total_cash_needed_dollars"]) == analyzed["total_cash_needed_for_deal"]

    def test_the_mcp_instructions_say_the_dates_are_required_and_describe_the_schedule(self):
        import mcp_server
        assert "contractDate and buyClosingDate" in mcp_server.INSTRUCTIONS and "a missing one is a 422" in mcp_server.INSTRUCTIONS
        assert "cash_needed_schedule_at_lowest_arv" in mcp_server.INSTRUCTIONS
