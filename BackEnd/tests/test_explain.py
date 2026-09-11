"""The explain layer cannot drift from the calculation.

Three guarantees, each with a test that fails the moment it is broken:

* every field of `BrrrResultsWithIntermediates` / `FlipResultsWithIntermediates` is read by its explain function (add
  an intermediate to the engine and forget to explain it -> red);
* every step's value is a field of the results record (the explain layer never
  computes a number of its own) and every sum-type step's terms add up to it;
* the runtime guards fire: a results record whose numbers no longer satisfy the
  stated equation raises `CalcExplainMismatch` instead of rendering.

Plus the presentation contract: every step carries a unit, and the PDF renders
the stacked terms, the notes and the unit-formatted headline values.
"""

from __future__ import annotations

import dataclasses
import re

import pypdf
import pytest

from BL.analyze.analyzeBRRR import compute_brrr_with_intermediates
from BL.analyze.analyzeFlip import compute_flip_with_intermediates
from BL.analyze.brrr_results import BrrrResultsWithIntermediates
from BL.analyze.common.calc_breakdown import CalcExplainMismatch
from BL.analyze.explain.brrr import BRRR_SECTIONS, explain_brrr
from BL.analyze.explain.flip import FLIP_SECTIONS, explain_flip
from BL.analyze.flip_results import FlipResultsWithIntermediates
from ReqRes.common.analyze_inputs import analyzeBRRRReq, analyzeFlipReq

# Every conditional branch of the two explain functions is reached by at least
# one of these overrides (applied on top of the conftest payloads).
BRRRR_SCENARIOS = {
    "base": {},
    "cash_rehab": {"use_HM_for_rehab": False},
    "refi_shortfall": {"arv_in_thousands": 250},
    "negative_cash_flow": {"rent": 1200},
    "positive_cash_out": {"arv_in_thousands": 420},
    "zero_interest": {"interestRate": 0},
    "cash_reserve": {"cashReserve": 45},
    "pitia_zero": {"arv_in_thousands": 0, "annual_property_taxes": 0, "annual_insurance": 0, "montly_hoa": 0},
}
NO_CASH_IN = {
    "down_payment": 0, "closingCostsBuy": 0, "hmlPoints": 0, "HMLInterestRate": 0,
    "use_HM_for_rehab": True, "annual_property_taxes": 0, "annual_insurance": 0,
    "montly_hoa": 0, "monthly_utilities": 0,
}
FLIP_SCENARIOS = {
    "base": {},
    "cash_rehab": {"use_HM_for_rehab": False},
    "loss": {"salePrice": 250},
    "no_cash_in_profit": NO_CASH_IN,
    "no_cash_in_loss": {**NO_CASH_IN, "salePrice": 250},
    "no_cash_in_break_even": {**NO_CASH_IN, "salePrice": 255, "buyerAgentSellingFee": 0,
                              "sellerAgentSellingFee": 0, "sellingClosingCosts": 0},
    "no_holding_time": {"holdingTime": 0},
}

PCT_STEPS = {"ROI", "Cash on Cash", "Annualized ROI"}
RATIO_STEPS = {"DSCR"}


class _RecordReads:
    """Wraps a results record and remembers every field the explain layer touched."""

    def __init__(self, results):
        object.__setattr__(self, "_calc", results)
        object.__setattr__(self, "reads", set())

    def __getattr__(self, name):
        self.reads.add(name)
        return getattr(self._calc, name)


def _brrr(payload: dict, overrides: dict):
    req = analyzeBRRRReq(**{**payload, **overrides})
    return req, compute_brrr_with_intermediates(req)


def _flip(payload: dict, overrides: dict):
    req = analyzeFlipReq(**{**payload, **overrides})
    return req, compute_flip_with_intermediates(req)


def _steps(breakdowns: dict) -> list[dict]:
    return [step for steps in breakdowns.values() for step in steps]


class TestEveryFieldIsExplained:
    def test_brrr(self, brrrr_payload):
        reads: set[str] = set()
        for overrides in BRRRR_SCENARIOS.values():
            req, results = _brrr(brrrr_payload, overrides)
            proxy = _RecordReads(results)
            explain_brrr(req, proxy)
            reads |= proxy.reads
        fields = {f.name for f in dataclasses.fields(BrrrResultsWithIntermediates)}
        assert fields - reads == set(), f"BrrrResultsWithIntermediates fields never explained: {sorted(fields - reads)}"

    def test_flip(self, flip_payload):
        reads: set[str] = set()
        for overrides in FLIP_SCENARIOS.values():
            req, results = _flip(flip_payload, overrides)
            proxy = _RecordReads(results)
            explain_flip(req, proxy)
            reads |= proxy.reads
        fields = {f.name for f in dataclasses.fields(FlipResultsWithIntermediates)}
        assert fields - reads == set(), f"FlipResultsWithIntermediates fields never explained: {sorted(fields - reads)}"


class TestStepsComeFromTheCalcRecord:
    @pytest.mark.parametrize("scenario", list(BRRRR_SCENARIOS))
    def test_brrr_step_values_are_fields(self, brrrr_payload, scenario):
        req, results = _brrr(brrrr_payload, BRRRR_SCENARIOS[scenario])
        field_values = {float(getattr(results, f.name)) for f in dataclasses.fields(results)}
        for step in _steps(explain_brrr(req, results)):
            assert step["value"] in field_values, f"{step['label']} is not a BrrrResultsWithIntermediates field"

    @pytest.mark.parametrize("scenario", list(FLIP_SCENARIOS))
    def test_flip_step_values_are_fields(self, flip_payload, scenario):
        req, results = _flip(flip_payload, FLIP_SCENARIOS[scenario])
        field_values = {float(getattr(results, f.name)) for f in dataclasses.fields(results)}
        for step in _steps(explain_flip(req, results)):
            assert step["value"] in field_values, f"{step['label']} is not a FlipResultsWithIntermediates field"

    @pytest.mark.parametrize("scenario", list(BRRRR_SCENARIOS))
    def test_brrr_terms_add_up(self, brrrr_payload, scenario):
        req, results = _brrr(brrrr_payload, BRRRR_SCENARIOS[scenario])
        _assert_terms_add_up(_steps(explain_brrr(req, results)))

    @pytest.mark.parametrize("scenario", list(FLIP_SCENARIOS))
    def test_flip_terms_add_up(self, flip_payload, scenario):
        req, results = _flip(flip_payload, FLIP_SCENARIOS[scenario])
        _assert_terms_add_up(_steps(explain_flip(req, results)))


def _assert_terms_add_up(steps: list[dict]) -> None:
    summed = 0
    for step in steps:
        if step.get("terms"):
            summed += 1
            total = sum(t["value"] if t["sign"] == "+" else -t["value"] for t in step["terms"])
            assert total == pytest.approx(step["value"], abs=1e-6), step["label"]
    assert summed >= 5, "sum-type steps went missing"


class TestGuardsFire:
    def test_brrr_mismatch_raises(self, brrrr_payload):
        req, results = _brrr(brrrr_payload, {})
        drifted = dataclasses.replace(results, net_operating_income=results.net_operating_income + 1)
        with pytest.raises(CalcExplainMismatch, match="Net Operating Income"):
            explain_brrr(req, drifted)

    def test_flip_mismatch_raises(self, flip_payload):
        req, results = _flip(flip_payload, {})
        drifted = dataclasses.replace(results, gross_profit=results.gross_profit + 1)
        with pytest.raises(CalcExplainMismatch, match="Gross Profit"):
            explain_flip(req, drifted)

    def test_message_names_the_step_only(self, brrrr_payload):
        req, results = _brrr(brrrr_payload, {})
        drifted = dataclasses.replace(results, cash_flow=results.cash_flow + 1)
        with pytest.raises(CalcExplainMismatch) as info:
            explain_brrr(req, drifted)
        assert not re.search(r"\d", str(info.value)), "guard errors must not carry deal numbers"


class TestUnits:
    def test_brrr(self, brrrr_payload):
        req, results = _brrr(brrrr_payload, {})
        _assert_units(_steps(explain_brrr(req, results)))
        assert {u for _, _, u in BRRR_SECTIONS} == {"money", "pct", "ratio"}

    def test_flip(self, flip_payload):
        req, results = _flip(flip_payload, {})
        _assert_units(_steps(explain_flip(req, results)))
        assert dict((k, u) for k, _, u in FLIP_SECTIONS)["roi"] == "pct"


def _assert_units(steps: list[dict]) -> None:
    for step in steps:
        expected = "pct" if step["label"] in PCT_STEPS else "ratio" if step["label"] in RATIO_STEPS else "money"
        assert step["unit"] == expected, step["label"]


class TestPdfRendersTheExplanation:
    @staticmethod
    def _text(pdf: bytes) -> str:
        import io
        pages = pypdf.PdfReader(io.BytesIO(pdf)).pages
        return re.sub(r"\s+", " ", " ".join(page.extract_text() for page in pages))

    def test_brrr_report(self, client, brrrr_payload):
        response = client.post("/reports/brrr-pdf", json=brrrr_payload, params={"address": "1 Shared Form St"})
        assert response.status_code == 200, response.text
        text = self._text(response.content)
        assert "Monthly Cash Flow · $85.04" in text          # headline value in the section heading
        assert "DSCR 1.36x" in text                            # ratio unit in the summary table
        assert "+ Management 8% of rent $208" in text          # a stacked term
        assert "− Operating Expenses $998 = $1,602" in text    # a subtracted term and the total line
        assert "still left in the deal" in text                # a note

    def test_address_markup_is_escaped(self, client, brrrr_payload):
        address = "1 <b>Bold</b> & Co <script>"
        response = client.post("/reports/brrr-pdf", json=brrrr_payload, params={"address": address})
        assert response.status_code == 200, response.text
        assert "1 <b>Bold</b> & Co <script>" in self._text(response.content)

    def test_flip_report(self, client, flip_payload):
        response = client.post("/reports/flip-pdf", json=flip_payload, params={"address": "2 Shared Form Ave"})
        assert response.status_code == 200, response.text
        text = self._text(response.content)
        assert "Net Profit · $12,620" in text
        assert "+ Contingency 10% $5,000 = $55,000" in text
        assert "Agent fees are the buyer's 3% plus the seller's 3%." in text
        assert "ROI · 19.41%" in text
