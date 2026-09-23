"""The explain layer cannot drift from the calculation.

Three guarantees, each with a test that fails the moment it is broken:

* every field of `BrrrResultsWithIntermediates` / `FlipResultsWithIntermediates` is read by its explain function (add
  an intermediate to the engine and forget to explain it -> red);
* every step's value is a field of the results_w_intermediates record (the explain layer never
  computes a number of its own) and every sum-type step's terms add up to it;
* the runtime guards fire: a results_w_intermediates record whose numbers no longer satisfy the
  stated equation raises `CalcExplainMismatch` instead of rendering.

Plus the presentation contract: every step carries a unit, and the PDF renders
the stacked terms, the notes and the unit-formatted headline values.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal
import re
from datetime import date

import pypdf
import pytest

from BL.analyze.analyzeBRRR import calculate_brrr_results, compute_brrr_with_intermediates
from BL.analyze.analyzeFlip import calculate_flip_results, compute_flip_with_intermediates
from BL.analyze.brrr_results_with_intermediates import BrrrResultsWithIntermediates
from BL.analyze.common.calc_breakdown import CalcBreakdown, CalcExplainMismatch
from BL.analyze.explain.brrr import BRRR_SECTIONS, explain_brrr
from BL.analyze.explain.flip import FLIP_SECTIONS, explain_flip
from BL.analyze.flip_results_with_intermediates import FlipResultsWithIntermediates
from ReqRes.common.analyze_inputs import analyzeBRRRReq, analyzeFlipReq

# Every conditional branch of the two explain functions is reached by at least
# one of these overrides (applied on top of the conftest payloads).
BRRRR_SCENARIOS = {
    "base": {},
    "cash_rehab": {"constructionLoanBudget": 0},
    "refi_shortfall": {"arv_in_thousands": 250},
    "negative_cash_flow": {"rent": 1200},
    "positive_cash_out": {"arv_in_thousands": 420},
    "zero_interest": {"interestRate": 0},
    "big_reserve": {"maintenanceReserve": 45000},
    "pitia_zero": {"arv_in_thousands": 0, "annual_property_taxes": 0, "annual_insurance": 0, "montly_hoa": 0},
    # lifecycle branches
    "no_date": {"buyClosingDate": None},
    "december_paid_we_pay_all": {"buyClosingDate": "2026-12-15", "titleModeBuy": "we_pay_all"},
    "same_month_refi": {"buyClosingDate": "2026-03-20", "daysUntilRefi": 5, "daysUntilRented": 0},
    "stolen_money": {"constructionLoanBudget": 70, "rehabContingency": 0},
    "tenant_after_refi": {"daysUntilRented": 400},
    "typed_overrides": {"recordingTransferBuy": 1000, "titleEscrowBuy": 900, "recordingTransferRefi": 1000,
                        "titleEscrowRefi": 900, "vacancyReserve": 0, "lowestArv": 300, "onlineNotaryBuy": False,
                        "onlineNotaryRefi": False, "sellerPaidCurrentYearTaxes": True},
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
    """Wraps a results_w_intermediates record and remembers every field the explain layer touched."""

    def __init__(self, results_w_intermediates):
        object.__setattr__(self, "_calc", results_w_intermediates)
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
            req, results_w_intermediates = _brrr(brrrr_payload, overrides)
            proxy = _RecordReads(results_w_intermediates)
            explain_brrr(req, proxy)
            reads |= proxy.reads
        fields = {f.name for f in dataclasses.fields(BrrrResultsWithIntermediates)}
        assert fields - reads == set(), f"BrrrResultsWithIntermediates fields never explained: {sorted(fields - reads)}"

    def test_flip(self, flip_payload):
        reads: set[str] = set()
        for overrides in FLIP_SCENARIOS.values():
            req, results_w_intermediates = _flip(flip_payload, overrides)
            proxy = _RecordReads(results_w_intermediates)
            explain_flip(req, proxy)
            reads |= proxy.reads
        fields = {f.name for f in dataclasses.fields(FlipResultsWithIntermediates)}
        assert fields - reads == set(), f"FlipResultsWithIntermediates fields never explained: {sorted(fields - reads)}"


def _numeric_field_values(record) -> set[float]:
    """Every number on the record (dates, booleans and Nones are not step values)."""
    numeric_values = set()
    for record_field in dataclasses.fields(record):
        field_value = getattr(record, record_field.name)
        if isinstance(field_value, bool) or field_value is None or isinstance(field_value, date):
            continue
        numeric_values.add(float(field_value))
    return numeric_values


class TestStepsComeFromTheCalcRecord:
    @pytest.mark.parametrize("scenario", list(BRRRR_SCENARIOS))
    def test_brrr_step_values_are_fields(self, brrrr_payload, scenario):
        req, results_w_intermediates = _brrr(brrrr_payload, BRRRR_SCENARIOS[scenario])
        field_values = _numeric_field_values(results_w_intermediates)
        for step in _steps(explain_brrr(req, results_w_intermediates)):
            assert step["value"] in field_values, f"{step['label']} is not a BrrrResultsWithIntermediates field"

    @pytest.mark.parametrize("scenario", list(FLIP_SCENARIOS))
    def test_flip_step_values_are_fields(self, flip_payload, scenario):
        req, results_w_intermediates = _flip(flip_payload, FLIP_SCENARIOS[scenario])
        field_values = _numeric_field_values(results_w_intermediates)
        for step in _steps(explain_flip(req, results_w_intermediates)):
            assert step["value"] in field_values, f"{step['label']} is not a FlipResultsWithIntermediates field"

    @pytest.mark.parametrize("scenario", list(BRRRR_SCENARIOS))
    def test_brrr_terms_add_up(self, brrrr_payload, scenario):
        req, results_w_intermediates = _brrr(brrrr_payload, BRRRR_SCENARIOS[scenario])
        _assert_terms_add_up(_steps(explain_brrr(req, results_w_intermediates)))

    @pytest.mark.parametrize("scenario", list(FLIP_SCENARIOS))
    def test_flip_terms_add_up(self, flip_payload, scenario):
        req, results_w_intermediates = _flip(flip_payload, FLIP_SCENARIOS[scenario])
        _assert_terms_add_up(_steps(explain_flip(req, results_w_intermediates)))


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
        req, results_w_intermediates = _brrr(brrrr_payload, {})
        drifted = dataclasses.replace(results_w_intermediates, net_operating_income=results_w_intermediates.net_operating_income + 1)
        with pytest.raises(CalcExplainMismatch, match="Net Operating Income"):
            explain_brrr(req, drifted)

    def test_flip_mismatch_raises(self, flip_payload):
        req, results_w_intermediates = _flip(flip_payload, {})
        drifted = dataclasses.replace(results_w_intermediates, gross_profit=results_w_intermediates.gross_profit + 1)
        with pytest.raises(CalcExplainMismatch, match="Gross Profit"):
            explain_flip(req, drifted)

    def test_message_names_the_step_only(self, brrrr_payload):
        req, results_w_intermediates = _brrr(brrrr_payload, {})
        drifted = dataclasses.replace(results_w_intermediates, cash_flow=results_w_intermediates.cash_flow + 1)
        with pytest.raises(CalcExplainMismatch) as info:
            explain_brrr(req, drifted)
        assert not re.search(r"\d", str(info.value)), "guard errors must not carry deal numbers"


class TestUnits:
    def test_brrr(self, brrrr_payload):
        req, results_w_intermediates = _brrr(brrrr_payload, {})
        _assert_units(_steps(explain_brrr(req, results_w_intermediates)))
        assert {u for _, _, u in BRRR_SECTIONS} == {"money", "pct", "ratio"}

    def test_flip(self, flip_payload):
        req, results_w_intermediates = _flip(flip_payload, {})
        _assert_units(_steps(explain_flip(req, results_w_intermediates)))
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
        # The layout itself (popup-shaped sections, links, outline) is covered by tests/test_report_pdf.py;
        # this checks the explanation reaches the page.
        response = client.post("/reports/brrr-pdf", json=brrrr_payload, params={"address": "1 Shared Form St"})
        assert response.status_code == 200, response.text
        text = self._text(response.content)
        assert "How Cash Flow is calculated $85.04" in text    # headline value under the section title
        assert "DSCR › 1.36x" in text                          # ratio unit in the summary table
        assert "+ Management 8% of rent $208" in text          # a stacked term
        assert "- Operating Expenses › $998" in text           # a subtracted, drillable term
        assert "= Net Operating Income (NOI) $1,602" in text   # the total line
        assert "still left in the deal" in text                # a note
        # the lifecycle sections
        assert "How Cash to Close (Buy) is calculated" in text
        assert "How Cash-Out Routi (Lowest ARV) is calculated" in text
        assert "How Stolen Money is calculated" in text
        assert "Seller Tax Credit" in text
        assert "Cash Needed (Buffered)" not in text

    def test_address_markup_is_escaped(self, client, brrrr_payload):
        address = "1 <b>Bold</b> & Co <script>"
        response = client.post("/reports/brrr-pdf", json=brrrr_payload, params={"address": address})
        assert response.status_code == 200, response.text
        assert "1 <b>Bold</b> & Co <script>" in self._text(response.content)

    def test_flip_report(self, client, flip_payload):
        response = client.post("/reports/flip-pdf", json=flip_payload, params={"address": "2 Shared Form Ave"})
        assert response.status_code == 200, response.text
        text = self._text(response.content)
        assert "How Net Profit is calculated $12,620" in text
        assert "+ Contingency 10% $5,000" in text
        assert "Agent fees are the buyer's 3% plus the seller's 3%." in text
        assert "How ROI is calculated 19.41%" in text


# The result tiles the website's deal modals render (MyDeals.vue / BoughtDeals.vue),
# each of which opens a popup showing `breakdowns[<tile key>]`. A tile key that is
# not a section would open an empty popup, so the two lists are pinned here.
FRONTEND_BRRR_RESULT_TILE_KEYS = [
    "cash_flow", "cash_out", "cash_out_routi", "cash_on_cash", "dscr", "equity", "roi", "net_profit",
    "total_cash_needed_for_deal", "cash_to_close_buy", "cash_out_routi_conservative", "stolen_money",
]
FRONTEND_FLIP_RESULT_TILE_KEYS = [
    "net_profit", "roi", "annualized_roi", "total_cash_needed", "total_cash_needed_with_buffer",
    "total_holding_costs", "total_hml_interest",
]


class TestEverySectionKeyHasBreakdownSteps:
    """Every headline section is present in `breakdowns`, non-empty, and contains a step whose value
    and unit are the headline result itself: the website's popup marks that step as the answer
    (a section may end on a derived reading, as the lowest-ARV wire does with the cash to the table)."""

    @staticmethod
    def _assert_sections_carry_their_headline(response: dict, sections) -> None:
        breakdowns = response["breakdowns"]
        for section_key, _label, section_unit in sections:
            steps = breakdowns.get(section_key)
            assert steps, f"no breakdown steps for section {section_key!r}"
            headline_value = response[section_key]
            headline_steps = [step for step in steps if step["value"] == headline_value]
            assert headline_steps, f"no step of section {section_key!r} has the headline value {headline_value}"
            assert headline_steps[-1]["unit"] == section_unit, section_key

    @pytest.mark.parametrize("scenario", list(BRRRR_SCENARIOS))
    def test_brrr(self, brrrr_payload, scenario):
        response = calculate_brrr_results(analyzeBRRRReq(**{**brrrr_payload, **BRRRR_SCENARIOS[scenario]})).model_dump()
        self._assert_sections_carry_their_headline(response, BRRR_SECTIONS)

    @pytest.mark.parametrize("scenario", list(FLIP_SCENARIOS))
    def test_flip(self, flip_payload, scenario):
        response = calculate_flip_results(analyzeFlipReq(**{**flip_payload, **FLIP_SCENARIOS[scenario]})).model_dump()
        self._assert_sections_carry_their_headline(response, FLIP_SECTIONS)


class TestFrontendResultTileKeysAreSections:
    def test_brrr_tiles(self):
        section_keys = {key for key, _, _ in BRRR_SECTIONS}
        assert set(FRONTEND_BRRR_RESULT_TILE_KEYS) <= section_keys

    def test_flip_tiles(self):
        section_keys = {key for key, _, _ in FLIP_SECTIONS}
        assert set(FRONTEND_FLIP_RESULT_TILE_KEYS) <= section_keys


def _term_links(breakdowns: dict, section_key: str, step_label_prefix: str) -> dict[str, str | None]:
    """{term label: step_label} of the step in the section carrying the label, else the first whose label starts with it."""
    steps = breakdowns[section_key]
    for step in [s for s in steps if s["label"] == step_label_prefix] + steps:
        if step["label"].startswith(step_label_prefix):
            assert step["terms"], f"{step_label_prefix!r} is not a sum step"
            return {term["label"]: term["step_label"] for term in step["terms"]}
    raise AssertionError(f"no step starting with {step_label_prefix!r} in section {section_key!r}")


def _step_labels_with_values(breakdowns: dict) -> dict[str, set[float]]:
    labels: dict[str, set[float]] = {}
    for steps in breakdowns.values():
        for step in steps:
            labels.setdefault(step["label"], set()).add(step["value"])
    return labels


class TestTermsLinkToTheirSourceStep:
    """A sum operand that is itself a step names it in `step_label`; a raw input never does."""

    @pytest.mark.parametrize("scenario", list(BRRRR_SCENARIOS))
    def test_brrr_every_link_names_a_step_carrying_the_same_value(self, brrrr_payload, scenario):
        req, results_w_intermediates = _brrr(brrrr_payload, BRRRR_SCENARIOS[scenario])
        self._assert_links_resolve(explain_brrr(req, results_w_intermediates))

    @pytest.mark.parametrize("scenario", list(FLIP_SCENARIOS))
    def test_flip_every_link_names_a_step_carrying_the_same_value(self, flip_payload, scenario):
        req, results_w_intermediates = _flip(flip_payload, FLIP_SCENARIOS[scenario])
        self._assert_links_resolve(explain_flip(req, results_w_intermediates))

    @staticmethod
    def _assert_links_resolve(breakdowns: dict) -> None:
        labels = _step_labels_with_values(breakdowns)
        linked_terms = 0
        for section_key, steps in breakdowns.items():
            for step in steps:
                for term in step["terms"] or []:
                    if term["step_label"] is None:
                        continue
                    linked_terms += 1
                    assert term["step_label"] in labels, (section_key, step["label"], term["label"])
                    assert term["value"] in labels[term["step_label"]], (section_key, step["label"], term["label"])
        assert linked_terms > 20

    def test_brrr_expected_links_and_leaves(self, brrrr_payload):
        req, results_w_intermediates = _brrr(brrrr_payload, {})
        breakdowns = explain_brrr(req, results_w_intermediates)
        cash_needed = _term_links(breakdowns, "total_cash_needed_for_deal", "Cash Needed")
        assert cash_needed == {
            "Cash Needed through Refi": "Cash Needed through Refi",
            "Floor Top-Up": "Floor Top-Up",
        }
        through_refi = _term_links(breakdowns, "total_cash_needed_for_deal", "Cash Needed through Refi")
        assert through_refi == {
            "Total Cash Invested": "Total Cash Invested (pre-refi)",
            "Rehab Cushion": None,
            "Cash to Refi Table (Lowest ARV)": "Cash to Refi Table (Lowest ARV)",
        }
        floor = _term_links(breakdowns, "total_cash_needed_for_deal", "Cash Needed Floor")
        assert floor == {
            "Earnest Money Deposit": None,
            "Cash to Close (Buy)": "Cash to Close (Buy)",
            "Rehab Cushion": None,
            "Utilities (first month)": None,
            "HML Interest (first month)": "HML Interest (first month)",
            "Holding Costs (first month)": "Holding Costs (first month)",
        }
        invested = _term_links(breakdowns, "total_cash_needed_for_deal", "Total Cash Invested")
        assert invested["Cash to Close (Buy)"] == "Cash to Close (Buy)"
        assert invested["Seller Tax Credit set aside in the tax bucket"] == "Seller Tax Credit set aside in the tax bucket"
        assert invested["Holding Costs"] == "Holding Costs (until refi)"
        assert invested["Pre-Refi Rental Income"] == "Pre-Refi Rental Income"
        assert invested["Earnest Money Deposit"] is None
        assert invested["HML Interest paid monthly"] is None
        cash_to_close = _term_links(breakdowns, "cash_to_close_buy", "Cash to Close (Buy)")
        assert cash_to_close["Down Payment"] == "Down Payment (cash)"
        assert cash_to_close["HML Points"] == "HML Points (cash at closing)"
        assert cash_to_close["Closing Costs (Buy)"] == "Closing Costs (Buy)"
        assert cash_to_close["Seller Tax Credit"] == "Seller Tax Credit"
        closing_buy = _term_links(breakdowns, "cash_to_close_buy", "Closing Costs (Buy)")
        assert closing_buy["Online Notary"] == "Online Notary (Buy)"
        assert closing_buy["Loan Charges"] is None
        # The default notary fee is one shared constant for both legs: the refi terms stay leaves.
        assert _term_links(breakdowns, "cash_out_routi", "Closing Costs (Refi)")["Online Notary"] is None
        assert _term_links(breakdowns, "cash_out_routi_conservative", "Closing Costs (Refi) (Lowest ARV)")["Online Notary"] is None
        wire = _term_links(breakdowns, "cash_out_routi", "Cash-Out Wire (Refi")
        assert wire == {
            "Refi Loan": "Refi Loan Amount", "HML Payoff": "HML Payoff at Refi",
            "Closing Costs (Refi)": "Closing Costs (Refi)", "Prepaid Interest (Refi)": "Prepaid Interest (Refi)",
            "Reserves": "Reserves Escrowed at Refi",
        }
        noi = _term_links(breakdowns, "cash_flow", "Net Operating Income")
        assert noi == {"Rent": None, "Operating Expenses": "Monthly Operating Expenses"}
        assert _term_links(breakdowns, "cash_flow", "Monthly Cash Flow") == {"NOI": "Net Operating Income (NOI)", "Mortgage": "Monthly Mortgage Payment"}
        assert _term_links(breakdowns, "dscr", "PITIA")["Mortgage"] == "Monthly Mortgage Payment"
        assert _term_links(breakdowns, "net_profit", "Net Profit") == {"Equity": "Equity (post-refi)", "Cash Out": "Cash Out from Deal"}
        assert _term_links(breakdowns, "stolen_money", "Actual Rehab Cost")["Rehab"] is None
        assert _term_links(breakdowns, "stolen_money", "Stolen Money")["Construction Budget"] is None
        assert _term_links(breakdowns, "cash_to_close_buy", "Closing Costs (Buy)")["Other"] is None

    def test_brrr_typed_refi_lines_resolve_to_their_own_variant(self, brrrr_payload):
        req, results_w_intermediates = _brrr(brrrr_payload, BRRRR_SCENARIOS["typed_overrides"])
        breakdowns = explain_brrr(req, results_w_intermediates)
        baseline = _term_links(breakdowns, "cash_out_routi", "Closing Costs (Refi)")
        lowest = _term_links(breakdowns, "cash_out_routi_conservative", "Closing Costs (Refi) (Lowest ARV)")
        assert baseline["Recording & Transfer"] == "Recording & Transfer (Refi)"
        assert baseline["Title & Escrow"] == "Title & Escrow (Refi)"
        assert lowest["Recording & Transfer"] == "Recording & Transfer (Refi) (Lowest ARV)"
        assert lowest["Title & Escrow"] == "Title & Escrow (Refi) (Lowest ARV)"

    def test_flip_expected_links_and_leaves(self, flip_payload):
        req, results_w_intermediates = _flip(flip_payload, {})
        breakdowns = explain_flip(req, results_w_intermediates)
        cost_basis = _term_links(breakdowns, "net_profit", "Total Cost Basis")
        assert cost_basis["Purchase"] is None
        assert cost_basis["Rehab"] == "Rehab Cost (with contingency)"
        assert cost_basis["Closing"] == "Closing Costs (Buy)"
        assert _term_links(breakdowns, "net_profit", "Rehab Cost (with contingency)")["Rehab"] is None
        assert _term_links(breakdowns, "net_profit", "Gross Profit")["Total Cost Basis"] == "Total Cost Basis"
        assert _term_links(breakdowns, "net_profit", "Net Profit")["Gross Profit"] == "Gross Profit"
        # Cross-section link: the ROI section's Total Cash Invested reaches the holding-costs section.
        assert _term_links(breakdowns, "roi", "Total Cash Invested")["Holding"] == "Total Holding Costs"
        # One value object, two steps: each sum links to the step filed in its own section.
        assert _term_links(breakdowns, "total_cash_needed", "Total Cash Needed")["HML Interest"] == "HML Interest (cash, during holding)"
        assert _term_links(breakdowns, "total_holding_costs", "Total Holding Costs")["HML Interest"] == "Total HML Interest (over holding period)"
        assert _term_links(breakdowns, "total_cash_needed_with_buffer", "Total Cash Needed (Buffered)")["Closing × 1.1"] == "Closing × 1.1 buffer"
        assert _term_links(breakdowns, "total_holding_costs", "Monthly Operating Costs")["HOA"] is None


class TestCalcBreakdownLinksByValueObjectIdentity:
    @dataclasses.dataclass(frozen=True)
    class _TinyRecord:
        purchase: Decimal
        fee_buy: Decimal
        fee_refi: Decimal
        total: Decimal

    def test_shared_object_links_only_inside_its_own_section(self):
        shared_fee = Decimal("250")
        record = self._TinyRecord(purchase=Decimal("1000"), fee_buy=shared_fee, fee_refi=shared_fee, total=Decimal("1250"))
        breakdown = CalcBreakdown(record)
        breakdown.add("buy", "Fee (Buy)", record.fee_buy, "as entered")
        breakdown.add("refi", "Refi Loan", record.purchase, "as entered")
        breakdown.add_sum("buy", "Cash to Close", record.total, [("Purchase", record.purchase), ("Fee", record.fee_buy)])
        breakdown.add_sum("refi", "Refi Costs", record.total, [("Loan", record.purchase), ("Fee", record.fee_refi)])
        buy_terms = {t["label"]: t["step_label"] for t in breakdown.to_dict()["buy"][-1]["terms"]}
        refi_terms = {t["label"]: t["step_label"] for t in breakdown.to_dict()["refi"][-1]["terms"]}
        assert buy_terms == {"Purchase": "Refi Loan", "Fee": "Fee (Buy)"}  # cross-section link for the unshared object
        assert refi_terms == {"Loan": "Refi Loan", "Fee": None}  # the shared fee is ambiguous outside its section

    def test_without_a_record_every_operand_still_links_by_identity(self):
        breakdown = CalcBreakdown()
        rent = Decimal("2600")
        breakdown.add("a", "Rent Step", rent, "as entered")
        breakdown.add_sum("b", "Total", Decimal("2600"), [("Rent", rent), ("Other", Decimal("0"))])
        assert [t["step_label"] for t in breakdown.to_dict()["b"][0]["terms"]] == ["Rent Step", None]
