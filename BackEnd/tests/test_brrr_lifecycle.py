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
from BL.analyze.common import deal_math as m
from ReqRes.common.analyze_inputs import analyzeBRRRReq

D = Decimal


def _calc(payload: dict, **overrides):
    return compute_brrr_with_intermediates(analyzeBRRRReq.model_validate({**payload, **overrides}))


class TestLegacyParity:
    """The refactor kept the core math: neutralise every new input and the legacy fixture
    reproduces the figures pinned before the lifecycle engine, to the last digit."""

    def test_reproduces_the_pinned_legacy_figures(self, legacy_brrrr_payload):
        r = _calc(legacy_brrrr_payload)
        assert r.total_cash_needed == D("63525.0000")
        assert r.cash_out_routi == D("15400.000000")
        assert r.cash_out == D("-48125.000000")
        assert float(r.cash_flow) == pytest.approx(85.03674361688704)

    def test_zero_budget_is_the_cash_rehab_case(self, brrrr_payload):
        r = _calc(brrrr_payload, constructionLoanBudget=0)
        assert r.hml_amount == r.purchase_loan_amount
        assert r.rehab_cash == r.rehab_cost
        assert r.stolen_money == -r.rehab_cost


class TestTaxProration:
    T = D("3650")

    def test_january_first_has_no_seller_days(self):
        assert m.calc_seller_tax_credit(self.T, date(2026, 1, 1), False) == 0

    def test_mid_year_credits_the_buyer_for_the_sellers_days(self):
        # Jan 1 .. Jun 30 = 181 days of a 365-day year
        assert m.calc_seller_tax_credit(self.T, date(2026, 7, 1), False) == self.T * 181 / 365

    def test_november_defaults_to_unpaid_and_the_override_flips_it(self, brrrr_payload):
        auto = _calc(brrrr_payload, buyClosingDate="2026-11-20")
        assert auto.seller_paid_current_year_taxes is False and auto.seller_tax_credit > 0
        flipped = _calc(brrrr_payload, buyClosingDate="2026-11-20", sellerPaidCurrentYearTaxes=True)
        assert flipped.seller_paid_current_year_taxes is True and flipped.seller_tax_credit < 0

    def test_december_reverses_the_credit(self, brrrr_payload):
        r = _calc(brrrr_payload, buyClosingDate="2026-12-15")
        assert r.seller_paid_current_year_taxes is True
        # Dec 15 .. Dec 31 = 17 days the buyer owes the seller
        assert r.seller_tax_credit == -D(brrrr_payload["annual_property_taxes"]) * 17 / 365

    def test_leap_year_prorates_on_366_days(self):
        # Feb 29 is day 60 -> 59 seller days of 366
        assert m.calc_seller_tax_credit(self.T, date(2024, 2, 29), False) == self.T * 59 / 366

    def test_credit_reduces_cash_to_close(self, brrrr_payload):
        with_credit = _calc(brrrr_payload, buyClosingDate="2026-07-01")
        without = _calc(brrrr_payload, buyClosingDate="2026-07-01", annual_property_taxes=0)
        assert with_credit.cash_to_close_buy < without.cash_to_close_buy


class TestInterestTimeline:
    def test_prepaid_window_runs_from_closing_through_month_end(self):
        assert m.days_through_month_end(date(2026, 1, 10)) == 22
        assert m.days_through_month_end(date(2026, 1, 31)) == 1
        assert m.days_through_month_end(date(2024, 2, 1)) == 29

    def test_three_way_split_adds_back_to_the_days_and_the_dollars(self, brrrr_payload):
        r = _calc(brrrr_payload, buyClosingDate="2026-01-10", daysUntilRefi=181)
        assert (r.prepaid_days_buy, r.monthly_interest_days, r.accrued_days_at_payoff) == (22, 150, 9)
        assert r.refi_closing_date == date(2026, 7, 10)
        _same(r.prepaid_interest_buy + r.hml_monthly_interest_paid + r.hml_accrued_interest_at_payoff, r.hml_interest)
        assert r.prepaid_interest_buy == r.hml_per_diem * 22

    def test_same_month_refi_is_all_prepaid(self, brrrr_payload):
        r = _calc(brrrr_payload, buyClosingDate="2026-01-10", daysUntilRefi=10, daysUntilRented=5)
        assert (r.prepaid_days_buy, r.monthly_interest_days, r.accrued_days_at_payoff) == (10, 0, 0)
        assert r.hml_monthly_interest_paid == 0

    def test_without_a_date_everything_is_paid_monthly(self, brrrr_payload):
        r = _calc(brrrr_payload, buyClosingDate=None)
        assert r.prepaid_interest_buy == 0 and r.hml_accrued_interest_at_payoff == 0
        assert r.hml_monthly_interest_paid == r.hml_interest
        assert r.refi_closing_date is None and r.prepaid_interest_refi == 0 and r.seller_tax_credit == 0

    def test_refi_prepaid_interest_uses_the_refi_loan_and_a_365_day_year(self, brrrr_payload):
        r = _calc(brrrr_payload, buyClosingDate="2026-01-10", daysUntilRefi=181)  # refi Jul 10 -> 22 days
        assert r.prepaid_days_refi == 22
        assert r.prepaid_interest_refi == r.refi_loan_amount * D(brrrr_payload["interestRate"]) * 22 / 365 / 100

    def test_the_payoff_carries_the_accrued_interest(self, brrrr_payload):
        r = _calc(brrrr_payload, buyClosingDate="2026-01-10", daysUntilRefi=181)
        assert r.hml_payoff == r.hml_amount + r.hml_accrued_interest_at_payoff
        assert r.hml_accrued_interest_at_payoff == r.hml_per_diem * 9


class TestBuySettlementLines:
    @pytest.mark.parametrize("price, fee", [(149_999, 2050), (150_000, 2200), (200_000, 2200), (200_001, 2400)])
    def test_we_pay_all_title_tiers(self, price, fee):
        assert m.title_escrow_buy_default("we_pay_all", D(price)) == fee

    def test_standard_title_is_flat(self):
        assert m.title_escrow_buy_default("standard", D(500_000)) == 1000

    def test_recording_default_follows_the_purchase_loan(self, brrrr_payload):
        r = _calc(brrrr_payload)
        assert r.recording_transfer_buy == D("0.0055") * r.purchase_loan_amount + 250

    def test_typed_values_override_the_formulas(self, brrrr_payload):
        r = _calc(brrrr_payload, recordingTransferBuy=1234, titleEscrowBuy=999, titleModeBuy="we_pay_all")
        assert r.recording_transfer_buy == 1234 and r.title_escrow_buy == 999

    def test_notary_checkbox_is_250_or_0(self, brrrr_payload):
        assert _calc(brrrr_payload, onlineNotaryBuy=True).notary_buy == 250
        assert _calc(brrrr_payload, onlineNotaryBuy=False).notary_buy == 0

    def test_closing_costs_total_and_cash_to_close(self, brrrr_payload):
        r = _calc(brrrr_payload, buyClosingDate="2026-01-10")
        assert r.closing_costs_buy_total == (D(brrrr_payload["loanChargesBuy"]) + r.recording_transfer_buy
                                             + r.title_escrow_buy + r.notary_buy + D(brrrr_payload["otherClosingCostsBuy"]))
        assert r.cash_to_close_buy == (r.down_payment_cash + r.closing_costs_buy_total + r.hml_points
                                       + r.prepaid_interest_buy - r.seller_tax_credit - D(brrrr_payload["earnestMoneyDeposit"]))

    def test_earnest_money_moves_cash_between_escrow_and_the_wire_only(self, brrrr_payload):
        low, high = _calc(brrrr_payload, earnestMoneyDeposit=0), _calc(brrrr_payload, earnestMoneyDeposit=10_000)
        assert high.cash_to_close_buy == low.cash_to_close_buy - 10_000
        assert high.total_cash_invested == low.total_cash_invested
        assert high.total_cash_needed == low.total_cash_needed

    def test_total_hard_money_cost(self, brrrr_payload):
        r = _calc(brrrr_payload)
        assert r.total_hard_money_cost == r.hml_points + r.hml_interest + D(brrrr_payload["loanChargesBuy"])


class TestRehabDraws:
    def test_stolen_money_is_budget_minus_actual(self, brrrr_payload):
        over = _calc(brrrr_payload, constructionLoanBudget=70, rehabContingency=0)  # rehab 50k, budget 70k
        assert over.stolen_money == 20_000 and over.rehab_cash == -20_000
        under = _calc(brrrr_payload, constructionLoanBudget=30, rehabContingency=0)
        assert under.stolen_money == -20_000 and under.rehab_cash == 20_000

    def test_stolen_money_reduces_cash_invested_and_cash_needed(self, brrrr_payload):
        base = _calc(brrrr_payload, rehabContingency=0, constructionLoanBudget=50)
        over = _calc(brrrr_payload, rehabContingency=0, constructionLoanBudget=70)
        # 20k more principal: draws return 20k, but points and interest grow on the bigger loan
        assert over.total_cash_invested < base.total_cash_invested
        assert over.hml_amount == base.hml_amount + 20_000

    def test_cushion_is_needed_but_not_invested(self, brrrr_payload):
        a, b = _calc(brrrr_payload, rehabCushion=0), _calc(brrrr_payload, rehabCushion=7000)
        assert b.total_cash_needed == a.total_cash_needed + 7000
        assert b.total_cash_invested == a.total_cash_invested and b.cash_out == a.cash_out


class TestHoldingIncomeAndCosts:
    def test_pre_refi_rent_covers_placement_to_refi(self, brrrr_payload):
        r = _calc(brrrr_payload, daysUntilRefi=180, daysUntilRented=90)
        assert r.days_rented_before_refi == 90
        assert r.pre_refi_rental_income == D(brrrr_payload["rent"]) * 90 / 30

    def test_tenant_after_refi_earns_nothing(self, brrrr_payload):
        r = _calc(brrrr_payload, daysUntilRefi=90, daysUntilRented=120)
        assert r.days_rented_before_refi == 0 and r.pre_refi_rental_income == 0

    def test_utilities_run_until_the_tenant(self, brrrr_payload):
        r = _calc(brrrr_payload, daysUntilRented=45, monthlyUtilitiesUntilRented=80)
        assert r.utilities_until_rented == D(80) * 45 / 30

    def test_rent_offsets_and_items_add_to_the_cash_invested(self, brrrr_payload):
        r = _calc(brrrr_payload)
        assert r.total_cash_invested == (D(brrrr_payload["earnestMoneyDeposit"]) + r.cash_to_close_buy + r.rehab_cash
                                         + r.hml_monthly_interest_paid + r.holding_costs + r.utilities_until_rented
                                         + D(brrrr_payload["maintenanceBeforeRefi"]) + D(brrrr_payload["appliances"])
                                         - r.pre_refi_rental_income)


class TestRefinanceSettlement:
    def test_closing_costs_refi_lists_every_line(self, brrrr_payload):
        r = _calc(brrrr_payload)
        p = brrrr_payload
        assert r.closing_costs_refi_total == (D(p["loanChargesRefi"]) + r.recording_transfer_refi + r.title_escrow_refi
                                              + r.notary_refi + D(p["appraisalFee"]) + D(p["surveyFee"]) + D(p["refiUnderwritingFee"])
                                              + r.broker_points_refi + D(p["brokerProcessingFeeRefi"]) + D(p["otherClosingCostsRefi"]))
        assert r.recording_transfer_refi == D("0.0055") * r.refi_loan_amount + 250
        assert r.title_escrow_refi == 800 + D("0.0045") * r.refi_loan_amount
        assert r.broker_points_refi == D(p["refiPoints"]) / 100 * r.refi_loan_amount

    def test_vacancy_reserve_defaults_to_one_month_of_rent(self, brrrr_payload):
        assert _calc(brrrr_payload, vacancyReserve=None).vacancy_reserve == D(brrrr_payload["rent"])
        assert _calc(brrrr_payload, vacancyReserve=0).vacancy_reserve == 0

    def test_reserves_reduce_the_wire_and_count_as_equity(self, brrrr_payload):
        a, b = _calc(brrrr_payload, capexReserve=0), _calc(brrrr_payload, capexReserve=4000)
        assert b.cash_out_routi == a.cash_out_routi - 4000
        assert b.equity == a.equity + 4000
        assert b.net_profit == a.net_profit


class TestLowestArvStressTest:
    def test_defaults_to_90_percent_of_arv(self, brrrr_payload):
        r = _calc(brrrr_payload)
        assert r.lowest_arv == D("0.90") * r.arv
        assert r.conservative_refi_loan_amount == r.lowest_arv * r.ltv

    def test_override_never_touches_the_baseline(self, brrrr_payload):
        base, low = _calc(brrrr_payload), _calc(brrrr_payload, lowestArv=250)
        assert low.lowest_arv == 250_000 and low.arv == base.arv
        assert low.cash_out_routi == base.cash_out_routi and low.cash_out_routi_conservative < base.cash_out_routi_conservative

    def test_formula_fees_follow_the_lower_loan_but_typed_fees_stay(self, brrrr_payload):
        auto = _calc(brrrr_payload)
        assert auto.recording_transfer_refi_conservative < auto.recording_transfer_refi
        assert auto.broker_points_refi_conservative < auto.broker_points_refi
        typed = _calc(brrrr_payload, recordingTransferRefi=1000, titleEscrowRefi=900)
        assert typed.recording_transfer_refi_conservative == typed.recording_transfer_refi == 1000
        assert typed.title_escrow_refi_conservative == typed.title_escrow_refi == 900

    def test_conservative_wire_is_never_above_the_baseline(self, brrrr_payload):
        r = _calc(brrrr_payload)
        assert r.cash_out_routi_conservative <= r.cash_out_routi
        assert r.cash_to_refi_table_conservative == max(D(0), -r.cash_out_routi_conservative)
        assert r.cash_needed_conservative == r.total_cash_invested + D(brrrr_payload["rehabCushion"]) + r.cash_to_refi_table_conservative


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


def _same(a, b) -> None:
    """Exact to the cent and beyond. These identities re-add the engine's terms in a different
    order, so the last of the 28 Decimal digits may differ; the engine's own guards (same order,
    plain `==`) run in `test_the_explanation_holds_on_every_scenario`."""
    assert float(a) == pytest.approx(float(b), abs=1e-6)


class TestReconcileIdentities:
    """What the settlement statements and the bank must agree with, on every scenario."""

    @pytest.mark.parametrize("scenario", list(SCENARIOS))
    def test_buy_settlement_sources_equal_uses(self, brrrr_payload, scenario):
        r = _calc(brrrr_payload, **SCENARIOS[scenario])
        sources = D(brrrr_payload["earnestMoneyDeposit"]) + r.cash_to_close_buy + r.purchase_loan_amount + r.seller_tax_credit
        uses = r.purchase_price + r.closing_costs_buy_total + r.hml_points + r.prepaid_interest_buy
        _same(sources, uses)

    @pytest.mark.parametrize("scenario", list(SCENARIOS))
    def test_interest_slices_reconcile(self, brrrr_payload, scenario):
        r = _calc(brrrr_payload, **SCENARIOS[scenario])
        _same(r.prepaid_interest_buy + r.hml_monthly_interest_paid + r.hml_accrued_interest_at_payoff, r.hml_interest)
        assert r.prepaid_days_buy + r.monthly_interest_days + r.accrued_days_at_payoff == int(SCENARIOS[scenario].get("daysUntilRefi", brrrr_payload["daysUntilRefi"]))

    @pytest.mark.parametrize("scenario", list(SCENARIOS))
    def test_refi_settlement_reconciles(self, brrrr_payload, scenario):
        r = _calc(brrrr_payload, **SCENARIOS[scenario])
        _same(r.refi_loan_amount, r.hml_payoff + r.closing_costs_refi_total + r.prepaid_interest_refi + r.reserves_total + r.cash_out_routi)
        _same(r.conservative_refi_loan_amount, r.hml_payoff + r.closing_costs_refi_total_conservative
              + r.prepaid_interest_refi_conservative + r.reserves_total + r.cash_out_routi_conservative)

    @pytest.mark.parametrize("scenario", list(SCENARIOS))
    def test_cash_identities(self, brrrr_payload, scenario):
        r = _calc(brrrr_payload, **SCENARIOS[scenario])
        _same(r.cash_out, r.cash_out_routi - r.total_cash_invested)
        _same(r.total_cash_needed - D(brrrr_payload["rehabCushion"]) - r.refi_shortfall, r.total_cash_invested)
        assert r.stolen_money == r.construction_budget - r.rehab_cost == -r.rehab_cash

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
        a = client.post("/analyze/brrr", json=brrrr_payload).json()
        b = client.post("/analyze/brrr", json={**brrrr_payload, "closingCostsBuy": 99, "closingCostsRefi": 99, "cashReserve": 99,
                                              "use_HM_for_rehab": False}).json()
        assert a["total_cash_needed_for_deal"] == b["total_cash_needed_for_deal"]
        assert a["cash_out_routi"] == b["cash_out_routi"]

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
