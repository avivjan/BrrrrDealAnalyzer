"""`/analyze/brrr` and `/analyze/flip`.

The reference numbers below were captured from the endpoints before the
`DealInputsForm` refactor. They are pinned deliberately: a change to any BRRRR
or Flip formula must show up as a failing assertion here rather than as a
silently different number on someone's deal board.
"""

from __future__ import annotations

import pytest

# Captured pre-refactor for the `brrrr_payload` / `flip_payload` fixtures.
EXPECTED_BRRRR_CASH_FLOW = 85.03674361688704
EXPECTED_FLIP_NET_PROFIT = 12620.0
# Verified identical under the old month-based formulas at 6 months and the
# per-diem ones at 180 days — the two agree to the last digit, which is what
# `monthsUntilRefi` -> `daysUntilRefi` was designed to guarantee. This is the
# metric the switch could plausibly have moved, so it is pinned alongside cash
# flow (which never depended on the holding period at all).
EXPECTED_BRRRR_CASH_NEEDED = 63525.0

BRRRR_METRIC_KEYS = {
    "cash_flow",
    "dscr",
    "cash_out",
    "cash_out_routi",
    "cash_on_cash",
    "roi",
    "equity",
    "net_profit",
    "total_cash_needed_for_deal",
    "total_cash_needed_for_deal_with_buffer",
}
FLIP_METRIC_KEYS = {
    "net_profit",
    "roi",
    "annualized_roi",
    "total_cash_needed",
    "total_cash_needed_with_buffer",
    "total_holding_costs",
    "total_hml_interest",
}


class TestAnalyzeBrrr:
    def test_accepts_the_shared_form_field_names(self, client, brrrr_payload):
        response = client.post("/analyze/brrr", json=brrrr_payload)
        assert response.status_code == 200, response.text

    def test_cash_flow_is_unchanged(self, client, brrrr_payload):
        result = client.post("/analyze/brrr", json=brrrr_payload).json()
        assert result["cash_flow"] == pytest.approx(EXPECTED_BRRRR_CASH_FLOW, abs=1e-9)

    def test_response_carries_every_metric(self, client, brrrr_payload):
        result = client.post("/analyze/brrr", json=brrrr_payload).json()
        assert BRRRR_METRIC_KEYS <= set(result)

    def test_breakdowns_explain_the_headline_metrics(self, client, brrrr_payload):
        breakdowns = client.post("/analyze/brrr", json=brrrr_payload).json()["breakdowns"]
        assert breakdowns, "calculation breakdowns should not be empty"
        assert "cash_flow" in breakdowns
        step = breakdowns["cash_flow"][0]
        assert {"label", "value", "formula"} <= set(step)

    def test_rent_drives_cash_flow(self, client, brrrr_payload):
        """A calc-relevant input must move the number it feeds, by the right amount.

        Extra rent does not land in cash flow one-for-one: vacancy, maintenance,
        capex and property management are all percentages *of rent*, so only the
        remainder reaches the bottom line.
        """
        rent_based_reserves = (
            brrrr_payload["vacancyPercent"]
            + brrrr_payload["maintenancePercent"]
            + brrrr_payload["capexPercent"]
            + brrrr_payload["property_managment_fee_precentages_from_rent"]
        ) / 100
        extra_rent = 150
        expected_gain = extra_rent * (1 - rent_based_reserves)  # 150 * 0.77 = 115.5

        base = client.post("/analyze/brrr", json=brrrr_payload).json()
        bumped = client.post(
            "/analyze/brrr",
            json={**brrrr_payload, "rent": brrrr_payload["rent"] + extra_rent},
        ).json()
        assert bumped["cash_flow"] == pytest.approx(
            base["cash_flow"] + expected_gain, abs=1e-9
        )

    def test_purchase_price_does_not_move_cash_flow(self, client, brrrr_payload):
        """Documents the model: the refi mortgage is driven by ARV x LTV, not price."""
        base = client.post("/analyze/brrr", json=brrrr_payload).json()
        bumped = client.post(
            "/analyze/brrr", json={**brrrr_payload, "purchasePrice": 260}
        ).json()
        assert bumped["cash_flow"] == pytest.approx(base["cash_flow"], abs=1e-9)
        # ...but it must move the cash the deal ties up.
        assert bumped["total_cash_needed_for_deal"] != base["total_cash_needed_for_deal"]

    def test_omitted_optional_field_falls_back_to_the_server_default(
        self, client, brrrr_payload
    ):
        """`DealInputsForm` omits a cleared field rather than sending null."""
        without = {k: v for k, v in brrrr_payload.items() if k != "refiPoints"}
        response = client.post("/analyze/brrr", json=without)
        assert response.status_code == 200, response.text
        with_default = client.post(
            "/analyze/brrr", json={**brrrr_payload, "refiPoints": 2}
        ).json()
        assert response.json()["cash_out"] == pytest.approx(with_default["cash_out"])

    @pytest.mark.parametrize(
        ("field", "value", "message"),
        [
            ("arv_in_thousands", 0, "ARV"),
            ("purchasePrice", 0, "Purchase price"),
            ("rent", 0, "Rent"),
            ("ltv_as_precent", 150, "LTV"),
            ("rehabCost", -5, "Rehab cost"),
            ("daysUntilRefi", 0, "Days until refi"),
        ],
    )
    def test_validation_rejects_bad_input(
        self, client, brrrr_payload, field, value, message
    ):
        response = client.post("/analyze/brrr", json={**brrrr_payload, field: value})
        assert response.status_code == 400
        assert message.lower() in response.json()["detail"].lower()


class TestRefiTiming:
    """`monthsUntilRefi` became `daysUntilRefi`, accrued per diem on a 360-day
    year. A month is exactly 30 days under that convention, which is what makes
    the migration (`days = months * 30`) leave every saved deal's numbers alone.
    """

    def test_180_days_reproduces_the_old_6_month_result(self, client, brrrr_payload):
        # The fixture is the pre-rename payload translated by that same *30, so
        # this asserting the pinned cash-flow *and* the cash figures below is
        # the proof the per-diem switch changed nothing for existing deals.
        result = client.post("/analyze/brrr", json=brrrr_payload).json()
        assert result["cash_flow"] == pytest.approx(EXPECTED_BRRRR_CASH_FLOW, abs=1e-9)
        # 6 months of HML interest + holding costs, priced per diem.
        assert result["total_cash_needed_for_deal"] == pytest.approx(
            EXPECTED_BRRRR_CASH_NEEDED, abs=1e-9
        )

    def test_a_legacy_months_payload_is_converted_not_read_as_days(
        self, client, brrrr_payload
    ):
        """A stale frontend still sends `monthsUntilRefi: 6` — that is 180 days,
        not 6 days. Reading it literally would understate the hold by 29x."""
        legacy = {k: v for k, v in brrrr_payload.items() if k != "daysUntilRefi"}
        legacy["monthsUntilRefi"] = 6
        legacy_result = client.post("/analyze/brrr", json=legacy).json()
        current_result = client.post("/analyze/brrr", json=brrrr_payload).json()
        assert legacy_result["total_cash_needed_for_deal"] == pytest.approx(
            current_result["total_cash_needed_for_deal"]
        )

    def test_days_drive_the_holding_period_cost(self, client, brrrr_payload):
        short = client.post(
            "/analyze/brrr", json={**brrrr_payload, "daysUntilRefi": 90}
        ).json()
        long = client.post(
            "/analyze/brrr", json={**brrrr_payload, "daysUntilRefi": 360}
        ).json()
        # Longer hold => more HML interest and holding cost => more cash in.
        assert long["total_cash_needed_for_deal"] > short["total_cash_needed_for_deal"]
        # ...but the stabilised rental does not care how long the rehab took.
        assert long["cash_flow"] == pytest.approx(short["cash_flow"], abs=1e-9)

    def test_a_single_day_is_meaningful(self, client, brrrr_payload):
        """The whole point of the days switch: 181 != 180."""
        base = client.post("/analyze/brrr", json=brrrr_payload).json()
        one_more = client.post(
            "/analyze/brrr", json={**brrrr_payload, "daysUntilRefi": 181}
        ).json()
        assert one_more["total_cash_needed_for_deal"] > base["total_cash_needed_for_deal"]


class TestAnalyzeFlip:
    def test_accepts_the_shared_form_field_names(self, client, flip_payload):
        response = client.post("/analyze/flip", json=flip_payload)
        assert response.status_code == 200, response.text

    def test_net_profit_is_unchanged(self, client, flip_payload):
        result = client.post("/analyze/flip", json=flip_payload).json()
        assert result["net_profit"] == pytest.approx(EXPECTED_FLIP_NET_PROFIT, abs=1e-9)

    def test_response_carries_every_metric(self, client, flip_payload):
        result = client.post("/analyze/flip", json=flip_payload).json()
        assert FLIP_METRIC_KEYS <= set(result)

    def test_breakdowns_explain_the_headline_metrics(self, client, flip_payload):
        breakdowns = client.post("/analyze/flip", json=flip_payload).json()["breakdowns"]
        assert breakdowns
        assert "net_profit" in breakdowns

    def test_selling_costs_reduce_net_profit(self, client, flip_payload):
        base = client.post("/analyze/flip", json=flip_payload).json()
        pricier = client.post(
            "/analyze/flip", json={**flip_payload, "sellerAgentSellingFee": 6}
        ).json()
        assert pricier["net_profit"] < base["net_profit"]

    def test_longer_hold_costs_more(self, client, flip_payload):
        base = client.post("/analyze/flip", json=flip_payload).json()
        longer = client.post(
            "/analyze/flip", json={**flip_payload, "holdingTime": 12}
        ).json()
        assert longer["total_holding_costs"] > base["total_holding_costs"]
        assert longer["total_hml_interest"] > base["total_hml_interest"]

    @pytest.mark.parametrize(
        ("field", "value", "message"),
        [
            ("salePrice", 0, "sale price"),
            ("purchasePrice", 0, "purchase price"),
            ("sellingClosingCosts", -1, "closing cost"),
        ],
    )
    def test_validation_rejects_bad_input(
        self, client, flip_payload, field, value, message
    ):
        response = client.post("/analyze/flip", json={**flip_payload, field: value})
        assert response.status_code == 400
        assert message.lower() in response.json()["detail"].lower()
