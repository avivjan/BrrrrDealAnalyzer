"""The BRRRR lifecycle engine: dates, settlement lines, draws, holding income, reserves, stress test.

Unit tests run the pure engine (`compute_brrr_with_intermediates`) on request models; the
validation and API-shape tests go through `/analyze/brrr`. The accounting identities at the
end are the reconcile checks a settlement statement and a bank wire must satisfy.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from BL.analyze.analyzeBRRR import calculate_brrr_results, compute_brrr_with_intermediates
from BL.analyze.common import deal_math
from ReqRes.common.analyze_inputs import analyzeBRRRReq



def _compute(payload: dict, **overrides):
    return compute_brrr_with_intermediates(analyzeBRRRReq.model_validate({**payload, **overrides}))


class TestLegacyParity:
    """The refactor kept the core math: neutralise every new input and the legacy fixture
    reproduces the figures pinned before the lifecycle engine, to the last digit."""

    def test_reproduces_the_pinned_legacy_figures(self, legacy_brrrr_payload):
        results = _compute(legacy_brrrr_payload)
        assert results.total_cash_needed == Decimal("63525.0000")
        assert results.cash_out_routi == Decimal("15400.000000")
        assert results.cash_out == Decimal("-48125.000000")
        assert float(results.cash_flow) == pytest.approx(85.03674361688704)

    def test_zero_budget_is_the_cash_rehab_case(self, brrrr_payload):
        results = _compute(brrrr_payload, constructionLoanBudget=0)
        assert results.hml_amount == results.purchase_loan_amount
        assert results.rehab_paid_cash_out_of_pocket == results.rehab_cost
        assert results.stolen_money == -results.rehab_cost


class TestTaxProration:
    T = Decimal("3650")

    def test_january_first_has_no_seller_days(self):
        assert deal_math.calc_seller_tax_credit(self.T, date(2026, 1, 1), False) == 0

    def test_mid_year_credits_the_buyer_for_the_sellers_days(self):
        # Jan 1 .. Jun 30 = 181 days of a 365-day year
        assert deal_math.calc_seller_tax_credit(self.T, date(2026, 7, 1), False) == self.T * 181 / 365

    def test_november_defaults_to_unpaid_and_the_override_flips_it(self, brrrr_payload):
        november_auto = _compute(brrrr_payload, buyClosingDate="2026-11-20")
        assert november_auto.seller_paid_current_year_taxes is False and november_auto.seller_tax_credit > 0
        november_paid_override = _compute(brrrr_payload, buyClosingDate="2026-11-20", sellerPaidCurrentYearTaxes=True)
        assert november_paid_override.seller_paid_current_year_taxes is True and november_paid_override.seller_tax_credit < 0

    def test_december_reverses_the_credit(self, brrrr_payload):
        results = _compute(brrrr_payload, buyClosingDate="2026-12-15")
        assert results.seller_paid_current_year_taxes is True
        # Dec 15 .. Dec 31 = 17 days the buyer owes the seller
        assert results.seller_tax_credit == -Decimal(brrrr_payload["annual_property_taxes"]) * 17 / 365

    def test_leap_year_prorates_on_366_days(self):
        # Feb 29 is day 60 -> 59 seller days of 366
        assert deal_math.calc_seller_tax_credit(self.T, date(2024, 2, 29), False) == self.T * 59 / 366

    def test_credit_reduces_cash_to_close(self, brrrr_payload):
        with_tax_credit = _compute(brrrr_payload, buyClosingDate="2026-07-01")
        without_tax_credit = _compute(brrrr_payload, buyClosingDate="2026-07-01", annual_property_taxes=0)
        assert with_tax_credit.cash_to_close_buy < without_tax_credit.cash_to_close_buy


class TestInterestTimeline:
    def test_prepaid_window_runs_from_closing_through_month_end(self):
        assert deal_math.days_through_month_end(date(2026, 1, 10)) == 22
        assert deal_math.days_through_month_end(date(2026, 1, 31)) == 1
        assert deal_math.days_through_month_end(date(2024, 2, 1)) == 29

    def test_three_way_split_adds_back_to_the_days_and_the_dollars(self, brrrr_payload):
        results = _compute(brrrr_payload, buyClosingDate="2026-01-10", daysUntilRefi=181)
        assert (results.hml_interest_days_prepaid_at_purchase_closing, results.hml_interest_days_paid_monthly, results.hml_interest_days_accrued_into_refi_payoff) == (22, 150, 9)
        assert results.refi_closing_date == date(2026, 7, 10)
        _assert_equal_to_the_cent(results.prepaid_interest_buy + results.hml_interest_paid_monthly + results.hml_interest_accrued_into_refi_payoff, results.hml_interest)
        assert results.prepaid_interest_buy == results.hml_per_diem * 22

    def test_same_month_refi_is_all_prepaid(self, brrrr_payload):
        results = _compute(brrrr_payload, buyClosingDate="2026-01-10", daysUntilRefi=10, daysUntilRented=5)
        assert (results.hml_interest_days_prepaid_at_purchase_closing, results.hml_interest_days_paid_monthly, results.hml_interest_days_accrued_into_refi_payoff) == (10, 0, 0)
        assert results.hml_interest_paid_monthly == 0

    def test_without_a_date_everything_is_paid_monthly(self, brrrr_payload):
        results = _compute(brrrr_payload, buyClosingDate=None)
        assert results.prepaid_interest_buy == 0 and results.hml_interest_accrued_into_refi_payoff == 0
        assert results.hml_interest_paid_monthly == results.hml_interest
        assert results.refi_closing_date is None and results.prepaid_interest_refi == 0 and results.seller_tax_credit == 0

    def test_refi_prepaid_interest_uses_the_refi_loan_and_a_365_day_year(self, brrrr_payload):
        results = _compute(brrrr_payload, buyClosingDate="2026-01-10", daysUntilRefi=181)  # refi Jul 10 -> 22 days
        assert results.dscr_interest_days_prepaid_at_refi_closing == 22
        assert results.prepaid_interest_refi == results.refi_loan_amount * Decimal(brrrr_payload["interestRate"]) * 22 / 365 / 100

    def test_the_payoff_carries_the_accrued_interest(self, brrrr_payload):
        results = _compute(brrrr_payload, buyClosingDate="2026-01-10", daysUntilRefi=181)
        assert results.hml_payoff == results.hml_amount + results.hml_interest_accrued_into_refi_payoff
        assert results.hml_interest_accrued_into_refi_payoff == results.hml_per_diem * 9


class TestBuySettlementLines:
    @pytest.mark.parametrize("price, fee", [(149_999, 2050), (150_000, 2200), (200_000, 2200), (200_001, 2400)])
    def test_we_pay_all_title_tiers(self, price, fee):
        assert deal_math.title_escrow_buy_default("we_pay_all", Decimal(price)) == fee

    def test_standard_title_is_flat(self):
        assert deal_math.title_escrow_buy_default("standard", Decimal(500_000)) == 1000

    def test_recording_default_follows_the_purchase_loan(self, brrrr_payload):
        results = _compute(brrrr_payload)
        assert results.recording_transfer_buy == Decimal("0.0055") * results.purchase_loan_amount + 250

    def test_typed_values_override_the_formulas(self, brrrr_payload):
        results = _compute(brrrr_payload, recordingTransferBuy=1234, titleEscrowBuy=999, titleModeBuy="we_pay_all")
        assert results.recording_transfer_buy == 1234 and results.title_escrow_buy == 999

    def test_notary_checkbox_is_250_or_0(self, brrrr_payload):
        assert _compute(brrrr_payload, onlineNotaryBuy=True).notary_buy == 250
        assert _compute(brrrr_payload, onlineNotaryBuy=False).notary_buy == 0

    def test_closing_costs_total_and_cash_to_close(self, brrrr_payload):
        results = _compute(brrrr_payload, buyClosingDate="2026-01-10")
        assert results.closing_costs_buy_total == (Decimal(brrrr_payload["loanChargesBuy"]) + results.recording_transfer_buy
                                             + results.title_escrow_buy + results.notary_buy + Decimal(brrrr_payload["otherClosingCostsBuy"]))
        assert results.cash_to_close_buy == (results.down_payment_cash + results.closing_costs_buy_total + results.hml_points
                                       + results.prepaid_interest_buy - results.seller_tax_credit - Decimal(brrrr_payload["earnestMoneyDeposit"]))

    def test_earnest_money_moves_cash_between_escrow_and_the_wire_only(self, brrrr_payload):
        low, high = _compute(brrrr_payload, earnestMoneyDeposit=0), _compute(brrrr_payload, earnestMoneyDeposit=10_000)
        assert high.cash_to_close_buy == low.cash_to_close_buy - 10_000
        assert high.total_cash_invested == low.total_cash_invested
        assert high.total_cash_needed == low.total_cash_needed

    def test_total_hard_money_cost(self, brrrr_payload):
        results = _compute(brrrr_payload)
        assert results.total_hard_money_cost == results.hml_points + results.hml_interest + Decimal(brrrr_payload["loanChargesBuy"])


class TestRehabDraws:
    def test_stolen_money_is_budget_minus_actual(self, brrrr_payload):
        budget_above_rehab = _compute(brrrr_payload, constructionLoanBudget=70, rehabContingency=0)  # rehab 50k, budget 70k
        assert budget_above_rehab.stolen_money == 20_000 and budget_above_rehab.rehab_paid_cash_out_of_pocket == -20_000
        budget_below_rehab = _compute(brrrr_payload, constructionLoanBudget=30, rehabContingency=0)
        assert budget_below_rehab.stolen_money == -20_000 and budget_below_rehab.rehab_paid_cash_out_of_pocket == 20_000

    def test_stolen_money_reduces_cash_invested_and_cash_needed(self, brrrr_payload):
        budget_equal_to_rehab = _compute(brrrr_payload, rehabContingency=0, constructionLoanBudget=50)
        budget_above_rehab = _compute(brrrr_payload, rehabContingency=0, constructionLoanBudget=70)
        # 20k more principal: draws return 20k, but points and interest grow on the bigger loan
        assert budget_above_rehab.total_cash_invested < budget_equal_to_rehab.total_cash_invested
        assert budget_above_rehab.hml_amount == budget_equal_to_rehab.hml_amount + 20_000

    def test_cushion_is_needed_but_not_invested(self, brrrr_payload):
        without_cushion, with_cushion = _compute(brrrr_payload, rehabCushion=0), _compute(brrrr_payload, rehabCushion=7000)
        assert with_cushion.total_cash_needed == without_cushion.total_cash_needed + 7000
        assert with_cushion.total_cash_invested == without_cushion.total_cash_invested and with_cushion.cash_out == without_cushion.cash_out


class TestHoldingIncomeAndCosts:
    def test_pre_refi_rent_covers_placement_to_refi(self, brrrr_payload):
        results = _compute(brrrr_payload, daysUntilRefi=180, daysUntilRented=90)
        assert results.days_tenant_occupied_before_refi == 90
        assert results.pre_refi_rental_income == Decimal(brrrr_payload["rent"]) * 90 / 30

    def test_tenant_after_refi_earns_nothing(self, brrrr_payload):
        results = _compute(brrrr_payload, daysUntilRefi=90, daysUntilRented=120)
        assert results.days_tenant_occupied_before_refi == 0 and results.pre_refi_rental_income == 0

    def test_utilities_run_until_the_tenant(self, brrrr_payload):
        results = _compute(brrrr_payload, daysUntilRented=45, monthlyUtilitiesUntilRented=80)
        assert results.utilities_until_rented == Decimal(80) * 45 / 30

    def test_rent_offsets_and_items_add_to_the_cash_invested(self, brrrr_payload):
        results = _compute(brrrr_payload)
        assert results.total_cash_invested == (Decimal(brrrr_payload["earnestMoneyDeposit"]) + results.cash_to_close_buy + results.rehab_paid_cash_out_of_pocket
                                         + results.hml_interest_paid_monthly + results.holding_costs + results.utilities_until_rented
                                         + Decimal(brrrr_payload["maintenanceBeforeRefi"]) + Decimal(brrrr_payload["appliances"])
                                         - results.pre_refi_rental_income)


class TestRefinanceSettlement:
    def test_closing_costs_refi_lists_every_line(self, brrrr_payload):
        results = _compute(brrrr_payload)
        payload = brrrr_payload
        assert results.closing_costs_refi_total == (Decimal(payload["loanChargesRefi"]) + results.recording_transfer_refi + results.title_escrow_refi
                                              + results.notary_refi + Decimal(payload["appraisalFee"]) + Decimal(payload["surveyFee"]) + Decimal(payload["refiUnderwritingFee"])
                                              + results.broker_points_refi + Decimal(payload["brokerProcessingFeeRefi"]) + Decimal(payload["otherClosingCostsRefi"]))
        assert results.recording_transfer_refi == Decimal("0.0055") * results.refi_loan_amount + 250
        assert results.title_escrow_refi == 800 + Decimal("0.0045") * results.refi_loan_amount
        assert results.broker_points_refi == Decimal(payload["refiPoints"]) / 100 * results.refi_loan_amount

    def test_vacancy_reserve_defaults_to_one_month_of_rent(self, brrrr_payload):
        assert _compute(brrrr_payload, vacancyReserve=None).vacancy_reserve == Decimal(brrrr_payload["rent"])
        assert _compute(brrrr_payload, vacancyReserve=0).vacancy_reserve == 0

    def test_reserves_reduce_the_wire_and_count_as_equity(self, brrrr_payload):
        without_capex_reserve, with_capex_reserve = _compute(brrrr_payload, capexReserve=0), _compute(brrrr_payload, capexReserve=4000)
        assert with_capex_reserve.cash_out_routi == without_capex_reserve.cash_out_routi - 4000
        assert with_capex_reserve.equity == without_capex_reserve.equity + 4000
        assert with_capex_reserve.net_profit == without_capex_reserve.net_profit


class TestLowestArvStressTest:
    def test_defaults_to_90_percent_of_arv(self, brrrr_payload):
        results = _compute(brrrr_payload)
        assert results.lowest_arv == Decimal("0.90") * results.arv
        assert results.conservative_refi_loan_amount == results.lowest_arv * results.ltv

    def test_override_never_touches_the_baseline(self, brrrr_payload):
        default_lowest_arv, overridden_lowest_arv = _compute(brrrr_payload), _compute(brrrr_payload, lowestArv=250)
        assert overridden_lowest_arv.lowest_arv == 250_000 and overridden_lowest_arv.arv == default_lowest_arv.arv
        assert overridden_lowest_arv.cash_out_routi == default_lowest_arv.cash_out_routi
        assert overridden_lowest_arv.cash_out_routi_conservative < default_lowest_arv.cash_out_routi_conservative

    def test_formula_fees_follow_the_lower_loan_but_typed_fees_stay(self, brrrr_payload):
        formula_fees = _compute(brrrr_payload)
        assert formula_fees.recording_transfer_refi_conservative < formula_fees.recording_transfer_refi
        assert formula_fees.broker_points_refi_conservative < formula_fees.broker_points_refi
        typed_fees = _compute(brrrr_payload, recordingTransferRefi=1000, titleEscrowRefi=900)
        assert typed_fees.recording_transfer_refi_conservative == typed_fees.recording_transfer_refi == 1000
        assert typed_fees.title_escrow_refi_conservative == typed_fees.title_escrow_refi == 900

    def test_conservative_wire_is_never_above_the_baseline(self, brrrr_payload):
        results = _compute(brrrr_payload)
        assert results.cash_out_routi_conservative <= results.cash_out_routi
        assert results.cash_to_refi_table_conservative == max(Decimal(0), -results.cash_out_routi_conservative)
        assert results.cash_needed_conservative == results.total_cash_invested + Decimal(brrrr_payload["rehabCushion"]) + results.cash_to_refi_table_conservative


SCENARIOS = {
    "dated": {"buyClosingDate": "2026-01-10", "daysUntilRefi": 181},
    "no_date": {"buyClosingDate": None},
    "december_we_pay_all": {"buyClosingDate": "2026-12-15", "titleModeBuy": "we_pay_all"},
    "cash_rehab": {"constructionLoanBudget": 0},
    "stolen_money": {"constructionLoanBudget": 70, "rehabContingency": 0},
    "shortfall": {"arv_in_thousands": 250, "maintenanceReserve": 30_000},
    "tenant_after_refi": {"daysUntilRented": 400},
    "same_month": {"buyClosingDate": "2026-03-20", "daysUntilRefi": 5, "daysUntilRented": 0},
}


def _assert_equal_to_the_cent(actual, expected) -> None:
    """Exact to the cent and beyond. These identities re-add the engine's terms in a different
    order, so the last of the 28 Decimal digits may differ; the engine's own guards (same order,
    plain `==`) run in `test_the_explanation_holds_on_every_scenario`."""
    assert float(actual) == pytest.approx(float(expected), abs=1e-6)


class TestReconcileIdentities:
    """What the settlement statements and the bank must agree with, on every scenario."""

    @pytest.mark.parametrize("scenario", list(SCENARIOS))
    def test_buy_settlement_sources_equal_uses(self, brrrr_payload, scenario):
        results = _compute(brrrr_payload, **SCENARIOS[scenario])
        sources = Decimal(brrrr_payload["earnestMoneyDeposit"]) + results.cash_to_close_buy + results.purchase_loan_amount + results.seller_tax_credit
        uses = results.purchase_price + results.closing_costs_buy_total + results.hml_points + results.prepaid_interest_buy
        _assert_equal_to_the_cent(sources, uses)

    @pytest.mark.parametrize("scenario", list(SCENARIOS))
    def test_interest_slices_reconcile(self, brrrr_payload, scenario):
        results = _compute(brrrr_payload, **SCENARIOS[scenario])
        _assert_equal_to_the_cent(results.prepaid_interest_buy + results.hml_interest_paid_monthly + results.hml_interest_accrued_into_refi_payoff, results.hml_interest)
        assert results.hml_interest_days_prepaid_at_purchase_closing + results.hml_interest_days_paid_monthly + results.hml_interest_days_accrued_into_refi_payoff == int(SCENARIOS[scenario].get("daysUntilRefi", brrrr_payload["daysUntilRefi"]))

    @pytest.mark.parametrize("scenario", list(SCENARIOS))
    def test_refi_settlement_reconciles(self, brrrr_payload, scenario):
        results = _compute(brrrr_payload, **SCENARIOS[scenario])
        _assert_equal_to_the_cent(results.refi_loan_amount, results.hml_payoff + results.closing_costs_refi_total + results.prepaid_interest_refi + results.reserves_total + results.cash_out_routi)
        _assert_equal_to_the_cent(results.conservative_refi_loan_amount, results.hml_payoff + results.closing_costs_refi_total_conservative
              + results.prepaid_interest_refi_conservative + results.reserves_total + results.cash_out_routi_conservative)

    @pytest.mark.parametrize("scenario", list(SCENARIOS))
    def test_cash_identities(self, brrrr_payload, scenario):
        results = _compute(brrrr_payload, **SCENARIOS[scenario])
        _assert_equal_to_the_cent(results.cash_out, results.cash_out_routi - results.total_cash_invested)
        _assert_equal_to_the_cent(results.total_cash_needed - Decimal(brrrr_payload["rehabCushion"]) - results.refi_shortfall, results.total_cash_invested)
        assert results.stolen_money == results.construction_budget - results.rehab_cost == -results.rehab_paid_cash_out_of_pocket

    @pytest.mark.parametrize("scenario", list(SCENARIOS))
    def test_the_explanation_holds_on_every_scenario(self, brrrr_payload, scenario):
        # every `check` and `add_sum` guard in explain/brrr.py runs here
        result = calculate_brrr_results(analyzeBRRRReq.model_validate({**brrrr_payload, **SCENARIOS[scenario]}))
        assert result.breakdowns and "cash_to_close_buy" in result.breakdowns


class TestApiShapeAndValidation:
    def test_response_carries_the_lifecycle_outputs_and_effective_defaults(self, client, brrrr_payload):
        body = client.post("/analyze/brrr", json=brrrr_payload).json()
        for key in ("cash_to_close_buy", "seller_tax_credit", "prepaid_interest_buy", "total_hard_money_cost", "stolen_money",
                    "pre_refi_rental_income", "cash_out_routi_conservative", "cash_to_refi_table_conservative",
                    "cash_needed_conservative", "total_cash_invested", "refi_closing_date", "tenant_occupied_date",
                    "recording_transfer_buy_effective", "title_escrow_buy_effective", "recording_transfer_refi_effective",
                    "title_escrow_refi_effective", "vacancy_reserve_effective", "lowest_arv_effective"):
            assert key in body, key
        assert "total_cash_needed_for_deal_with_buffer" not in body
        assert body["refi_closing_date"] == "2026-07-09"  # 2026-01-10 + 180
        assert body["vacancy_reserve_effective"] == pytest.approx(brrrr_payload["rent"])

    def test_deprecated_lumps_are_ignored(self, client, brrrr_payload):
        without_legacy_lumps = client.post("/analyze/brrr", json=brrrr_payload).json()
        with_legacy_lumps = client.post("/analyze/brrr", json={**brrrr_payload, "closingCostsBuy": 99, "closingCostsRefi": 99, "cashReserve": 99,
                                                                "use_HM_for_rehab": False}).json()
        assert without_legacy_lumps["total_cash_needed_for_deal"] == with_legacy_lumps["total_cash_needed_for_deal"]
        assert without_legacy_lumps["cash_out_routi"] == with_legacy_lumps["cash_out_routi"]

    @pytest.mark.parametrize("field, value, message", [
        ("earnestMoneyDeposit", -1, "Earnest money deposit cannot be negative"),
        ("loanChargesBuy", -1, "Loan charges (buy) cannot be negative"),
        ("recordingTransferBuy", -1, "Recording and transfer charges (buy) cannot be negative"),
        ("titleEscrowBuy", -1, "Title and escrow charges (buy) cannot be negative"),
        ("otherClosingCostsBuy", -1, "Other closing costs (buy) cannot be negative"),
        ("constructionLoanBudget", -1, "Construction loan budget cannot be negative"),
        ("rehabCushion", -1, "Rehab cushion cannot be negative"),
        ("daysUntilRented", -1, "Days until rented cannot be negative"),
        ("monthlyUtilitiesUntilRented", -1, "Monthly utilities until rented cannot be negative"),
        ("maintenanceBeforeRefi", -1, "Maintenance before refi cannot be negative"),
        ("appliances", -1, "Appliances cannot be negative"),
        ("loanChargesRefi", -1, "Loan charges (refi) cannot be negative"),
        ("recordingTransferRefi", -1, "Recording and transfer charges (refi) cannot be negative"),
        ("titleEscrowRefi", -1, "Title and escrow charges (refi) cannot be negative"),
        ("appraisalFee", -1, "Appraisal fee cannot be negative"),
        ("surveyFee", -1, "Survey fee cannot be negative"),
        ("refiUnderwritingFee", -1, "Refi underwriting fee cannot be negative"),
        ("brokerProcessingFeeRefi", -1, "Broker processing fee (refi) cannot be negative"),
        ("otherClosingCostsRefi", -1, "Other closing costs (refi) cannot be negative"),
        ("maintenanceReserve", -1, "Maintenance reserve cannot be negative"),
        ("vacancyReserve", -1, "Vacancy reserve cannot be negative"),
        ("capexReserve", -1, "CapEx reserve cannot be negative"),
        ("refiPoints", 101, "Broker points must be between 0% and 100%"),
        ("lowestArv", 0, "Lowest ARV must be greater than 0"),
        ("lowestArv", 999, "Lowest ARV cannot exceed ARV"),
    ])
    def test_validation_rejects_bad_lifecycle_input(self, client, brrrr_payload, field, value, message):
        response = client.post("/analyze/brrr", json={**brrrr_payload, field: value})
        assert response.status_code == 400
        assert message in response.json()["detail"]

    def test_title_mode_is_an_enum_and_the_date_must_be_iso(self, client, brrrr_payload):
        assert client.post("/analyze/brrr", json={**brrrr_payload, "titleModeBuy": "seller_pays"}).status_code == 422
        assert client.post("/analyze/brrr", json={**brrrr_payload, "buyClosingDate": "10/01/2026"}).status_code == 422
