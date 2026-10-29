"""The deal-reconciliation inputs: insurance a-d with their pickers, the property's tax bucket,
appraisal and survey outside the refi closing, the owner's reserves with the HYSA deposit, the
rehab completion date and the 360-day DSCR per diem.

The acceptance figures are the owner's two finished deals, 10th St and Ridgeway, as their
purchase and refi settlement statements and bank transactions read them.

The two horizons are never mixed: everything paid before or at the refi moves the purchase-to-refi
outputs only (the wires, cash invested, cash out, Cash Needed), and a regular year after the refi
(cash flow, PITIA, DSCR) uses only the steady monthly figures.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from BL.analyze.analyzeBRRR import calculate_brrr_results, compute_brrr_with_intermediates
from BL.analyze.common import deal_math
from ReqRes.common.analyze_inputs import analyzeBRRRReq

CENT = Decimal("0.01")


def _compute(payload: dict, **overrides):
    return compute_brrr_with_intermediates(analyzeBRRRReq.model_validate({**payload, **overrides}))


def _assert_equal_to_the_cent(actual, expected) -> None:
    assert float(actual) == pytest.approx(float(expected), abs=1e-6)


def _regular_year_outputs(results):
    return (results.cash_flow, results.dscr, results.pitia, results.operating_expenses)


class TestInsuranceAcrossTheDeal:
    def test_the_bill_at_purchase_lands_in_cash_to_close_or_in_cash_invested_and_cash_out_is_the_same(self, brrrr_payload):
        inside = _compute(brrrr_payload, annual_insurance=1454.46)
        outside = _compute(brrrr_payload, annual_insurance=1454.46, insurancePurchaseBillPaymentTiming="outside_purchase_closing")
        assert inside.insurance_bill_at_purchase_inside_closing == Decimal("1454.46") and inside.insurance_bill_at_purchase_outside_closing == 0
        assert outside.insurance_bill_at_purchase_inside_closing == 0 and outside.insurance_bill_at_purchase_outside_closing == Decimal("1454.46")
        _assert_equal_to_the_cent(inside.closing_costs_buy_total, outside.closing_costs_buy_total + Decimal("1454.46"))
        _assert_equal_to_the_cent(inside.cash_to_close_buy, outside.cash_to_close_buy + Decimal("1454.46"))
        _assert_equal_to_the_cent(inside.total_cash_invested, outside.total_cash_invested)
        _assert_equal_to_the_cent(inside.cash_out, outside.cash_out)
        # The floor carries it either way: inside the purchase wire, or as its own term.
        _assert_equal_to_the_cent(inside.cash_needed_floor, outside.cash_needed_floor)

    def test_the_bill_at_refi_comes_off_both_wires_or_goes_into_cash_invested_and_cash_out_is_the_same(self, brrrr_payload):
        inside = _compute(brrrr_payload, insuranceBillAtRefiClosing=2410.01)
        outside = _compute(brrrr_payload, insuranceBillAtRefiClosing=2410.01, insuranceRefiBillPaymentTiming="outside_refi_closing")
        _assert_equal_to_the_cent(inside.cash_out_routi, outside.cash_out_routi - Decimal("2410.01"))
        _assert_equal_to_the_cent(inside.cash_out_routi_conservative, outside.cash_out_routi_conservative - Decimal("2410.01"))
        _assert_equal_to_the_cent(inside.total_cash_invested, outside.total_cash_invested - Decimal("2410.01"))
        _assert_equal_to_the_cent(inside.cash_out, outside.cash_out)

    def test_the_bill_at_refi_defaults_to_the_bill_at_purchase(self, brrrr_payload):
        results = _compute(brrrr_payload, annual_insurance=1343.46)
        assert results.insurance_bill_at_refi == Decimal("1343.46")

    @pytest.mark.parametrize("insurance_bill_at_refi, expected_monthly_insurance_after_refi", [
        (Decimal("2410.01"), Decimal("200.83")),   # Ridgeway: the lender's monthly insurance escrow
        (Decimal("1343.46"), Decimal("111.96")),   # 10th St
    ])
    def test_the_regular_year_insurance_defaults_to_the_bill_at_refi_over_12(self, brrrr_payload, insurance_bill_at_refi, expected_monthly_insurance_after_refi):
        results = _compute(brrrr_payload, insuranceBillAtRefiClosing=insurance_bill_at_refi)
        assert results.monthly_insurance.quantize(CENT) == expected_monthly_insurance_after_refi

    def test_the_bills_and_the_monthly_until_refi_never_touch_the_regular_year(self, brrrr_payload):
        base = _compute(brrrr_payload, monthlyInsuranceAfterRefi=100)
        bigger_bills = _compute(brrrr_payload, monthlyInsuranceAfterRefi=100, annual_insurance=5000,
                                insuranceBillAtRefiClosing=6000, monthlyInsuranceUntilRefi=300)
        assert _regular_year_outputs(base) == _regular_year_outputs(bigger_bills)
        assert bigger_bills.cash_out < base.cash_out and bigger_bills.total_cash_needed > base.total_cash_needed

    def test_the_regular_year_insurance_never_touches_the_purchase_to_refi_outputs(self, brrrr_payload):
        low, high = _compute(brrrr_payload, monthlyInsuranceAfterRefi=100), _compute(brrrr_payload, monthlyInsuranceAfterRefi=250)
        assert (low.cash_out, low.total_cash_needed, low.cash_out_routi) == (high.cash_out, high.total_cash_needed, high.cash_out_routi)
        _assert_equal_to_the_cent(low.cash_flow, high.cash_flow + 150)

    def test_the_monthly_until_refi_is_paid_every_30_days_until_the_refi(self, brrrr_payload):
        results = _compute(brrrr_payload, monthlyInsuranceUntilRefi=120, daysUntilRefi=182)
        assert results.insurance_paid_monthly_until_refi == Decimal(120) * 182 / 30


class TestPropertyTaxBucket:
    @pytest.mark.parametrize("buy_closing_date, days_until_refi, deposits_until_nov_30, deposits_until_refi", [
        ("2026-01-16", 182, 10, 6),   # 10th St: refi 07/17, deposits Feb 15 .. Jul 15
        ("2026-04-29", 124, 7, 4),    # Ridgeway: refi 08/31, deposits May 15 .. Aug 15
    ])
    def test_the_deposits_on_the_15th_of_the_two_deals(self, brrrr_payload, buy_closing_date, days_until_refi, deposits_until_nov_30, deposits_until_refi):
        results = _compute(brrrr_payload, buyClosingDate=buy_closing_date, daysUntilRefi=days_until_refi, daysUntilRented=60)
        assert results.first_property_tax_payment_date == date(2026, 11, 30)
        assert results.property_tax_bucket_deposit_count_until_first_payment == deposits_until_nov_30
        assert results.property_tax_bucket_first_bill_deposit_count_until_refi == deposits_until_refi
        bill_paid_on_november_30 = Decimal(brrrr_payload["annual_property_taxes"]) * Decimal("0.96")
        assert results.property_tax_bucket_deposit == (bill_paid_on_november_30 - results.seller_tax_credit_set_aside_in_tax_bucket) / deposits_until_nov_30
        assert results.property_tax_paid_into_bucket_until_refi == results.property_tax_bucket_deposit * deposits_until_refi

    def test_the_seller_credit_typed_from_the_settlement_statement_wins_and_feeds_the_deposit(self, brrrr_payload):
        results = _compute(brrrr_payload, buyClosingDate="2026-01-16", daysUntilRefi=182, sellerTaxCreditAtPurchaseClosing=120.45)
        assert results.seller_tax_credit == Decimal("120.45") and results.seller_tax_credit_formula != results.seller_tax_credit
        assert results.property_tax_bucket_deposit == (Decimal(brrrr_payload["annual_property_taxes"]) * Decimal("0.96") - Decimal("120.45")) / 10

    def test_a_typed_deposit_is_used_as_is(self, brrrr_payload):
        results = _compute(brrrr_payload, buyClosingDate="2026-01-16", daysUntilRefi=182, monthlyPropertyTaxBucketDeposit=250)
        assert results.property_tax_bucket_deposit == 250 and results.property_tax_paid_into_bucket_until_refi == 250 * 6

    def test_a_nov_30_inside_the_hold_is_paid_from_the_bucket_and_next_years_deposits_follow(self, brrrr_payload):
        results = _compute(brrrr_payload, buyClosingDate="2026-08-20", daysUntilRefi=200)   # refi 2027-03-08
        assert results.refi_closing_date == date(2027, 3, 8)
        assert results.property_tax_bucket_deposit_count_until_first_payment == 3   # Sep, Oct, Nov 15
        assert results.property_tax_bucket_later_deposit_count_until_refi == 3       # Dec 15, Jan 15, Feb 15
        assert results.property_tax_bucket_deposit_after_first_payment == results.monthly_taxes
        _assert_equal_to_the_cent(results.property_tax_paid_into_bucket_until_refi,
                                  results.property_tax_bucket_deposit * 3 + results.monthly_taxes * 3)
        assert results.property_tax_bucket_shortfall_topped_up_on_november_30 == 0   # the default deposit fills it exactly
        assert results.property_tax_bucket_balance_released_at_refi == 0

    def test_a_short_typed_deposit_is_topped_up_on_nov_30(self, brrrr_payload):
        results = _compute(brrrr_payload, buyClosingDate="2026-08-20", daysUntilRefi=200, monthlyPropertyTaxBucketDeposit=100)
        _assert_equal_to_the_cent(results.property_tax_bucket_shortfall_topped_up_on_november_30,
                                  results.property_tax_bill_paid_on_november_30 - results.seller_tax_credit_set_aside_in_tax_bucket - 300)

    def test_a_december_closing_fills_the_bucket_for_the_next_nov_30(self, brrrr_payload):
        results = _compute(brrrr_payload, buyClosingDate="2026-12-15", daysUntilRefi=180)
        assert results.seller_tax_credit < 0 and results.seller_tax_credit_set_aside_in_tax_bucket == 0
        assert results.first_property_tax_payment_date == date(2027, 11, 30)
        assert results.property_tax_bucket_deposit_count_until_first_payment == 11   # Jan 15 .. Nov 15 (Dec 15 is closing day)
        assert results.property_tax_bucket_deposit == results.property_tax_bill_paid_on_november_30 / 11

    def test_a_seller_who_already_paid_this_years_bill_fills_the_bucket_for_next_year_from_dec_15(self, brrrr_payload):
        results = _compute(brrrr_payload, buyClosingDate="2026-11-20", daysUntilRefi=120, sellerPaidCurrentYearTaxes=True)
        assert results.seller_tax_credit < 0 and results.seller_tax_credit_set_aside_in_tax_bucket == 0
        assert results.first_property_tax_payment_date == date(2027, 11, 30)
        assert results.property_tax_bucket_deposit_count_until_first_payment == 12   # Dec 15, 2026 .. Nov 15, 2027
        assert results.property_tax_bucket_deposit == results.property_tax_bill_paid_on_november_30 / 12
        assert results.property_tax_bucket_first_bill_deposit_count_until_refi == 4    # Dec 15 .. Mar 15, before the Mar 20 refi
        assert results.property_tax_bucket_shortfall_topped_up_on_november_30 == 0

    @pytest.mark.parametrize("buy_closing_date", ["2026-07-01", "2026-11-10"])
    def test_already_paid_targets_next_years_bill_whatever_the_closing_month(self, brrrr_payload, buy_closing_date):
        results = _compute(brrrr_payload, buyClosingDate=buy_closing_date, daysUntilRefi=120, sellerPaidCurrentYearTaxes=True)
        assert results.first_property_tax_payment_date == date(2027, 11, 30)

    def test_a_closing_with_no_15th_left_makes_one_deposit_on_nov_30(self, brrrr_payload):
        results = _compute(brrrr_payload, buyClosingDate="2026-11-20", daysUntilRefi=120)
        assert results.property_tax_bucket_deposit_count_until_first_payment == 1
        assert results.property_tax_bucket_deposit == results.property_tax_bill_paid_on_november_30 - results.seller_tax_credit_set_aside_in_tax_bucket
        assert results.property_tax_bucket_first_bill_deposit_count_until_refi == 1

    def test_without_a_closing_date_the_deposit_is_a_twelfth_every_30_days(self, brrrr_payload):
        results = _compute(brrrr_payload, buyClosingDate=None, daysUntilRefi=180)
        assert results.first_property_tax_payment_date is None and results.property_tax_bucket_deposit_count_until_first_payment == 0
        assert results.property_tax_bucket_deposit == results.monthly_taxes
        assert results.property_tax_paid_into_bucket_until_refi == results.monthly_taxes * 6

    def test_the_regular_year_tax_is_the_bill_with_the_november_discount_over_12(self, brrrr_payload):
        results = _compute(brrrr_payload, annual_property_taxes=3087.96)
        assert results.monthly_taxes == Decimal("3087.96") * Decimal("0.96") / 12
        # The refi never changes the tax: collecting the bill at the refi leaves the regular year alone.
        with_lump = _compute(brrrr_payload, annual_property_taxes=3087.96, propertyTaxCollectionAtRefi="full_tax_bill_collected_at_refi")
        assert _regular_year_outputs(results) == _regular_year_outputs(with_lump)

    def test_the_refi_lender_collecting_the_whole_bill_lowers_both_wires_and_releases_the_bucket(self, brrrr_payload):
        dated = {"buyClosingDate": "2026-04-29", "daysUntilRefi": 124, "daysUntilRented": 60}
        bucket_keeps_paying = _compute(brrrr_payload, **dated)
        lender_collects = _compute(brrrr_payload, **dated, propertyTaxCollectionAtRefi="full_tax_bill_collected_at_refi")
        bill = Decimal(brrrr_payload["annual_property_taxes"])
        assert lender_collects.property_tax_lump_sum_at_refi_closing == bill
        _assert_equal_to_the_cent(lender_collects.cash_out_routi, bucket_keeps_paying.cash_out_routi - bill)
        _assert_equal_to_the_cent(lender_collects.cash_out_routi_conservative, bucket_keeps_paying.cash_out_routi_conservative - bill)
        released = lender_collects.seller_tax_credit_set_aside_in_tax_bucket + lender_collects.property_tax_paid_into_bucket_until_refi
        _assert_equal_to_the_cent(lender_collects.property_tax_bucket_balance_released_at_refi, released)
        _assert_equal_to_the_cent(lender_collects.total_cash_invested, bucket_keeps_paying.total_cash_invested - released)
        assert bucket_keeps_paying.property_tax_lump_sum_at_refi_closing == 0 and bucket_keeps_paying.property_tax_bucket_balance_released_at_refi == 0

    def test_a_typed_lump_is_used_as_is(self, brrrr_payload):
        results = _compute(brrrr_payload, propertyTaxCollectionAtRefi="full_tax_bill_collected_at_refi", propertyTaxLumpSumAtRefiClosing=3087.96)
        assert results.property_tax_lump_sum_at_refi_closing == Decimal("3087.96")
        ignored = _compute(brrrr_payload, propertyTaxLumpSumAtRefiClosing=3087.96)
        assert ignored.property_tax_lump_sum_at_refi_closing == 0

    def test_after_a_nov_30_inside_the_hold_only_the_later_deposits_come_back(self, brrrr_payload):
        results = _compute(brrrr_payload, buyClosingDate="2026-08-20", daysUntilRefi=200, propertyTaxCollectionAtRefi="full_tax_bill_collected_at_refi")
        _assert_equal_to_the_cent(results.property_tax_bucket_balance_released_at_refi, results.monthly_taxes * 3)


class TestAppraisalAndSurveyArePaidOutsideTheRefiClosing:
    def test_they_move_from_the_wire_to_cash_invested_and_cash_out_is_unchanged(self, brrrr_payload):
        cheap, dear = _compute(brrrr_payload, appraisalFee=0, surveyFee=0), _compute(brrrr_payload, appraisalFee=690, surveyFee=385)
        assert cheap.closing_costs_refi_total == dear.closing_costs_refi_total
        assert cheap.cash_out_routi == dear.cash_out_routi
        assert dear.appraisal_and_survey_paid_outside_closing == 1075
        _assert_equal_to_the_cent(dear.total_cash_invested, cheap.total_cash_invested + 1075)
        _assert_equal_to_the_cent(dear.cash_out, cheap.cash_out - 1075)


class TestReservesSetAsideByTheOwner:
    RIDGEWAY_REFI = {"arv_in_thousands": 230, "ltv_as_precent": 75, "interestRate": 7.625, "loanTermYears": 30}

    def test_the_hysa_deposit_defaults_to_three_months_of_principal_and_interest(self, brrrr_payload):
        results = _compute(brrrr_payload, **self.RIDGEWAY_REFI)
        assert results.refi_loan_amount == 172_500
        assert results.mortgage_payment.quantize(CENT) == Decimal("1220.94")
        assert results.hysa_deposit_at_refi == 3 * results.mortgage_payment
        assert results.hysa_deposit_at_refi.quantize(CENT) == Decimal("3662.83")

    def test_the_hysa_deposit_is_a_fourth_reserve_off_the_cash_out_not_the_wire(self, brrrr_payload):
        without_hysa, with_hysa = _compute(brrrr_payload, hysaDepositAtRefi=0), _compute(brrrr_payload, hysaDepositAtRefi=3000)
        assert with_hysa.reserves_total == without_hysa.reserves_total + 3000
        assert with_hysa.cash_out_routi == without_hysa.cash_out_routi
        assert with_hysa.cash_out == without_hysa.cash_out - 3000
        assert with_hysa.equity == without_hysa.equity + 3000
        assert with_hysa.net_profit == without_hysa.net_profit

    def test_reserves_the_lowest_arv_wire_cannot_fund_raise_cash_needed(self, brrrr_payload):
        short = _compute(brrrr_payload, arv_in_thousands=250, maintenanceReserve=30_000)
        assert short.reserves_funded_from_own_pocket_at_lowest_arv == max(Decimal(0), short.reserves_total - max(Decimal(0), short.cash_out_routi_conservative))
        assert short.reserves_funded_from_own_pocket_at_lowest_arv > 0
        _assert_equal_to_the_cent(short.cash_needed_through_refi, short.total_cash_invested + Decimal(brrrr_payload["rehabCushion"])
                                  + short.cash_to_refi_table_conservative + short.reserves_funded_from_own_pocket_at_lowest_arv)


class TestRehabCompletionDate:
    def test_it_is_the_purchase_closing_plus_the_days(self, brrrr_payload):
        assert _compute(brrrr_payload).rehab_completed_date == date(2026, 2, 24)   # 2026-01-10 + 45
        assert _compute(brrrr_payload, daysUntilRehabCompleted=60).rehab_completed_date == date(2026, 3, 11)
        assert _compute(brrrr_payload, buyClosingDate=None).rehab_completed_date is None

    def test_it_moves_no_money_yet(self, brrrr_payload):
        early, late = _compute(brrrr_payload, daysUntilRehabCompleted=10), _compute(brrrr_payload, daysUntilRehabCompleted=90)
        assert (early.cash_out, early.total_cash_needed, early.cash_flow) == (late.cash_out, late.total_cash_needed, late.cash_flow)

    @pytest.mark.parametrize("days_until_rehab_completed", [0, 90])
    def test_the_bounds_are_the_purchase_closing_and_the_tenant(self, client, brrrr_payload, days_until_rehab_completed):
        response = client.post("/analyze/brrr", json={**brrrr_payload, "daysUntilRented": 90, "daysUntilRehabCompleted": days_until_rehab_completed})
        assert response.status_code == 200, response.text
        assert "rehab_completed_date" in response.json()

    @pytest.mark.parametrize("days_until_rehab_completed, message", [
        (91, "Rehab completion must be on or before the tenant-occupied date"),
        (-1, "Days until rehab completed cannot be negative"),
    ])
    def test_outside_the_bounds_is_rejected(self, client, brrrr_payload, days_until_rehab_completed, message):
        response = client.post("/analyze/brrr", json={**brrrr_payload, "daysUntilRented": 90, "daysUntilRehabCompleted": days_until_rehab_completed})
        assert response.status_code == 400 and message in response.json()["detail"]


class TestValidationOfTheNewInputs:
    @pytest.mark.parametrize("field, label", [
        ("monthlyInsuranceUntilRefi", "Monthly insurance until refi"),
        ("monthlyPropertyTaxBucketDeposit", "Monthly property tax bucket deposit"),
        ("insuranceBillAtRefiClosing", "Insurance bill at refi"),
        ("monthlyInsuranceAfterRefi", "Monthly insurance after refi"),
        ("propertyTaxLumpSumAtRefiClosing", "Property tax lump sum at refi"),
        ("hysaDepositAtRefi", "HYSA deposit at refi"),
    ])
    def test_negative_dollars_are_rejected(self, client, brrrr_payload, field, label):
        response = client.post("/analyze/brrr", json={**brrrr_payload, field: -1})
        assert response.status_code == 400 and f"{label} cannot be negative" in response.json()["detail"]

    def test_a_negative_seller_credit_is_a_reimbursement_and_is_allowed(self, client, brrrr_payload):
        assert client.post("/analyze/brrr", json={**brrrr_payload, "sellerTaxCreditAtPurchaseClosing": -55}).status_code == 200

    @pytest.mark.parametrize("field", ["insurancePurchaseBillPaymentTiming", "insuranceRefiBillPaymentTiming", "propertyTaxCollectionAtRefi"])
    def test_the_pickers_are_enums(self, client, brrrr_payload, field):
        assert client.post("/analyze/brrr", json={**brrrr_payload, field: "somewhere_else"}).status_code == 422


class TestDscrPerDiemIsOnA360DayYear:
    def test_the_10th_st_refi_prepaid_interest(self, brrrr_payload):
        # 10th St: $212,300 at 6.75%, refi 2026-07-17 -> 15 days through month end -> $597.09 on the statement.
        results = _compute(brrrr_payload, buyClosingDate="2026-01-16", daysUntilRefi=182, daysUntilRented=60,
                           arv_in_thousands=283.0666666666666666666666667, ltv_as_precent=75, interestRate=6.75)
        assert results.refi_loan_amount.quantize(CENT) == Decimal("212300.00")
        assert results.dscr_interest_days_prepaid_at_refi_closing == 15
        assert results.prepaid_interest_refi.quantize(CENT) == Decimal("597.09")
        assert deal_math.DSCR_DAYS_PER_YEAR == 360


@pytest.mark.parametrize("overrides", [
    {"insurancePurchaseBillPaymentTiming": "outside_purchase_closing", "insuranceRefiBillPaymentTiming": "outside_refi_closing"},
    {"buyClosingDate": "2026-08-20", "daysUntilRefi": 200, "propertyTaxCollectionAtRefi": "full_tax_bill_collected_at_refi",
     "monthlyPropertyTaxBucketDeposit": 100},
    {"buyClosingDate": "2026-11-20", "daysUntilRefi": 120, "daysUntilRented": 60, "sellerTaxCreditAtPurchaseClosing": -40},
    {"buyClosingDate": None, "propertyTaxCollectionAtRefi": "full_tax_bill_collected_at_refi", "hysaDepositAtRefi": 0},
])
def test_the_explanation_holds_on_the_new_inputs(brrrr_payload, overrides):
    # every `check` and `add_sum` guard in explain/brrr.py runs here
    result = calculate_brrr_results(analyzeBRRRReq.model_validate({**brrrr_payload, **overrides}))
    labels = {step.label for steps in result.breakdowns.values() for step in steps}
    assert {"Tax Bucket Deposit (each 15th)", "Insurance Bill at Refi", "HYSA Deposit at Refi", "Reserves set aside at Refi"} <= labels
