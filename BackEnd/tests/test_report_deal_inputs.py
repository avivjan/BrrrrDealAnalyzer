"""The interactive report's optional "Deal Inputs" section: every calculator input, by the form's stages.

- The field map is the form's: per tab, the same input keys as `frontend/src/config/dealInputPhaseTabs.ts`,
  the same tab titles, and none of the deprecated / hidden BRRRR keys.
- Values read as the form shows them: thousands × 1000, percentages, points, days, months, years, dates,
  Yes/No, choice labels, and a blank formula field as the value actually used with an "auto" chip.
- Hidden fields stay hidden; every text is escaped; only calculator inputs are included.
- The endpoints: collapsed section with the flag, none without it; the MCP tool.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from BL.reports.common.deal_html_report import build_deal_html_report
from BL.reports.common.deal_input_sections import (
    BRRRR_DEAL_INPUT_SECTIONS,
    FLIP_DEAL_INPUT_SECTIONS,
    format_deal_input_value,
    resolve_deal_input_sections,
)
from tests.mcp_helpers import call as call_mcp_tool
from tests.test_report_html import ParsedHtmlElement, parse_html

PHASE_TABS_SOURCE = (pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src" / "config" / "dealInputPhaseTabs.ts").read_text()
NON_NUMERIC_KINDS = {"date", "yes_no", "choice", "text"}
DEPRECATED_OR_HIDDEN_BRRRR_KEYS = {"closingCostsBuy", "closingCostsRefi", "cashReserve", "use_HM_for_rehab"}
PRIVATE_DEAL_FIELDS = ("notes", "contact", "task", "niche", "zillow_link", "pics_link", "google_drive_link")


def _frontend_tab_titles(const_name: str) -> list[tuple[str, str]]:
    block = re.search(rf"export const {const_name}[^=]*=\s*\[(.*?)\];", PHASE_TABS_SOURCE, re.S).group(1)
    return re.findall(r'key:\s*"([^"]+)",\s*label:\s*"([^"]+)"', block)


def _frontend_field_keys_by_tab() -> dict[str, list[str]]:
    block = re.search(r"DEAL_INPUT_FIELD_KEYS_BY_PHASE_TAB[^=]*=\s*\{(.*?)\n\};", PHASE_TABS_SOURCE, re.S).group(1)
    return {tab: re.findall(r'"([^"]+)"', keys) for tab, keys in re.findall(r"(\w+):\s*\[(.*?)\]", block, re.S)}


# -- the map is the form's -------------------------------------------------------------------------
class TestTheFieldMapIsTheForms:
    @pytest.mark.parametrize("deal_type, sections, const_name", [
        ("BRRRR", BRRRR_DEAL_INPUT_SECTIONS, "BRRRR_PHASE_TABS"),
        ("FLIP", FLIP_DEAL_INPUT_SECTIONS, "FLIP_PHASE_TABS"),
    ])
    def test_tabs_and_their_numeric_fields_match_the_frontend(self, deal_type, sections, const_name):
        assert [(section.tab_key, section.title) for section in sections] == _frontend_tab_titles(const_name)
        frontend_keys_by_tab = _frontend_field_keys_by_tab()
        for section in sections:
            numeric_keys = [f.payload_key for g in section.groups for f in g.fields if f.display_kind not in NON_NUMERIC_KINDS]
            # The two mandatory BRRRR dates are listed on the frontend's Buy tab for its validation messages; here they are date rows.
            frontend_numeric_keys = [key for key in frontend_keys_by_tab[section.tab_key] if key not in ("contractDate", "buyClosingDate")]
            assert sorted(numeric_keys) == sorted(frontend_numeric_keys), section.tab_key

    def test_no_deprecated_or_hidden_brrrr_key_is_listed(self):
        listed = {f.payload_key for s in BRRRR_DEAL_INPUT_SECTIONS for g in s.groups for f in g.fields}
        assert not listed & DEPRECATED_OR_HIDDEN_BRRRR_KEYS


# -- values read as the form shows them --------------------------------------------------------------
class TestFormatting:
    @pytest.mark.parametrize("kind, value, suffix, expected", [
        ("money_in_thousands", 200, "", "$200,000"),
        ("money_in_thousands", "212.5", "", "$212,500"),
        ("money", 2600, "/mo", "$2,600/mo"),
        ("money", 1432.5, "", "$1,432.50"),
        ("percent", 75, "", "75%"),
        ("percent", "7.250", "", "7.25%"),
        ("points", 2, "", "2 pts"),
        ("days", 180, "", "180 days"),
        ("days", 1, "", "1 day"),
        ("months", 6, "", "6 months"),
        ("years", 30, "", "30 years"),
        ("date", "2026-01-10", "", "Jan 10, 2026"),
        ("yes_no", True, "", "Yes"),
        ("yes_no", False, "", "No"),
        ("text", "  ", "", "—"),
        ("money", None, "", "—"),
    ])
    def test_each_kind(self, kind, value, suffix, expected):
        assert format_deal_input_value(kind, value, suffix) == expected

    def test_choice_labels(self):
        assert format_deal_input_value("choice", "we_pay_all", choice_labels={"we_pay_all": "We pay all closing costs"}) == "We pay all closing costs"


def _resolved_rows(deal_type, inputs, result) -> dict[str, tuple]:
    rows = {}
    for section in resolve_deal_input_sections(deal_type, inputs, result):
        for group in section.groups:
            for row in group.rows:
                rows[(section.title, row.label)] = (row.value_text, row.chips, row.hint)
    return rows


class TestResolvingTheUsersValues:
    def test_a_blank_formula_field_shows_the_value_used_with_an_auto_chip(self):
        rows = _resolved_rows("BRRRR", {"recordingTransferBuy": None, "titleEscrowRefi": 1900, "onlineNotaryBuy": True},
                              {"recording_transfer_buy_effective": 1432.5, "title_escrow_refi_effective": 1900})
        assert rows[("Buy", "Recording & Transfer")] == ("$1,432.50", ("auto",), "Formula: $250 + 0.55% of the hard money loan + the deed transfer tax")
        assert rows[("Refinance", "Title & Escrow / Settlement (Refi)")] == ("$1,900", (), None)
        assert rows[("Buy", "Notary fee")] == ("$250", ("auto",), "Default: $250")

    def test_lowest_arv_auto_is_in_dollars_already(self):
        rows = _resolved_rows("BRRRR", {"lowestArv": None}, {"lowest_arv_effective": 288000})
        assert rows[("Refinance", "Lowest ARV Possible (stress test)")][0] == "$288,000"
        rows = _resolved_rows("BRRRR", {"lowestArv": 250}, {"lowest_arv_effective": 250000})
        assert rows[("Refinance", "Lowest ARV Possible (stress test)")] == ("$250,000", (), None)

    def test_seller_paid_taxes_is_auto_from_the_closing_month(self):
        december = _resolved_rows("BRRRR", {"buyClosingDate": "2026-12-15", "sellerPaidCurrentYearTaxes": None}, {})
        assert december[("Buy", "Seller already paid this year's taxes")][:2] == ("Yes", ("auto", "yes"))
        typed = _resolved_rows("BRRRR", {"buyClosingDate": "2026-03-01", "sellerPaidCurrentYearTaxes": True}, {})
        assert typed[("Buy", "Seller already paid this year's taxes")][:2] == ("Yes", ("yes",))

    def test_the_form_hides_a_notary_fee_with_the_notary_off_and_an_empty_note(self):
        rows = _resolved_rows("BRRRR", {"onlineNotaryBuy": False, "onlineNotaryRefi": True, "otherClosingCostsBuyNote": "",
                                        "otherClosingCostsRefiNote": "Rate lock"}, {})
        assert ("Buy", "Notary fee") not in rows and ("Refinance", "Notary fee") in rows
        assert ("Buy", "What the other closing costs are for") not in rows
        assert rows[("Refinance", "What the other refi closing costs are for")][0] == "Rate lock"
        assert rows[("Buy", "Online notary")][:2] == ("No", ("no",))

    def test_day_counts_carry_the_dates_the_calculator_derives(self):
        rows = _resolved_rows("BRRRR", {"daysUntilRefi": 180, "daysUntilRented": 90},
                              {"refi_closing_date": "2026-07-09", "tenant_occupied_date": "2026-04-10"})
        assert rows[("Refinance", "Days to Refi")] == ("180 days", (), "Refi closing Jul 09, 2026")
        assert rows[("Rent & Holding", "Until Tenant Occupied")] == ("90 days", (), "Tenant occupied Apr 10, 2026")


# -- in the file ------------------------------------------------------------------------------------
def _inputs_section(document: ParsedHtmlElement) -> ParsedHtmlElement | None:
    found = document.find_all(lambda e: e.tag == "details" and e.attributes.get("id") == "deal-inputs")
    return found[0] if found else None


def _rows_by_stage(section: ParsedHtmlElement) -> dict[str, dict[str, str]]:
    stages = {}
    for stage in section.find_all(lambda e: e.tag == "details" and "stage" in e.classes):
        title = stage.find_all(lambda e: "stage-title" in e.classes)[0].text()
        stages[title] = {
            row.find_all(lambda e: e.tag == "dt")[0].text(): row.find_all(lambda e: "input-value" in e.classes)[0].text()
            for row in stage.find_all(lambda e: "input-row" in e.classes)
        }
    return stages


class TestDealInputsInTheFile:
    def test_brrrr_section_is_collapsed_with_the_four_stages_open_and_the_users_values(self, client, brrrr_payload):
        response = client.post("/reports/brrr-html", json=brrrr_payload, params={"include_deal_inputs": "true"})
        assert response.status_code == 200, response.text
        document = parse_html(response.text)
        section = _inputs_section(document)
        assert section is not None and "open" not in section.attributes
        stages = section.find_all(lambda e: e.tag == "details" and "stage" in e.classes)
        assert [s.attributes["id"] for s in stages] == ["inputs-buy", "inputs-rehab", "inputs-rentHolding", "inputs-refinance"]
        assert all("open" in s.attributes for s in stages)
        rows = _rows_by_stage(section)
        assert list(rows) == ["Buy", "Rehab", "Rent & Holding", "Refinance"]
        assert rows["Buy"]["Purchase Price"] == "$200,000"
        assert rows["Buy"]["Closing Date (Buy)"] == "Jan 10, 2026"
        assert rows["Buy"]["Down Payment"] == "20%"
        assert rows["Buy"]["Title Charges"] == "Standard (lender's policy)"
        assert rows["Rehab"]["Actual Rehab Cost"] == "$50,000"
        assert rows["Rent & Holding"]["Monthly Rent"] == "$2,600/mo"
        assert rows["Refinance"]["LTV"] == "75%"
        assert rows["Refinance"]["Loan Term"] == "30 years"
        analysis = client.post("/analyze/brrr", json=brrrr_payload).json()
        if brrrr_payload.get("recordingTransferBuy") is None:
            from BL.reports.common.deal_pdf import format_value_like_calculation_popup
            assert rows["Buy"]["Recording & Transfer"] == format_value_like_calculation_popup("money", analysis["recording_transfer_buy_effective"])
        # The summary tile links to the section.
        assert document.find_all(lambda e: e.tag == "a" and e.attributes.get("href") == "#deal-inputs")

    def test_flip_section_has_the_three_flip_stages(self, client, flip_payload):
        response = client.post("/reports/flip-html", json=flip_payload, params={"include_deal_inputs": "true"})
        rows = _rows_by_stage(_inputs_section(parse_html(response.text)))
        assert list(rows) == ["Buy & Rehab", "Flip Strategy", "Expenses"]
        assert rows["Flip Strategy"]["Holding Time"].endswith("months")
        assert rows["Flip Strategy"]["Projected Sale Price"].startswith("$")

    def test_no_section_without_the_flag(self, client, brrrr_payload):
        response = client.post("/reports/brrr-html", json=brrrr_payload)
        assert _inputs_section(parse_html(response.text)) is None
        assert 'href="#deal-inputs"' not in response.text

    def test_only_calculator_inputs_and_every_text_escaped(self, client, brrrr_payload):
        hostile = "<script>alert(1)</script>\"><img src=x onerror=alert(2)></details>"
        payload = {**brrrr_payload, "otherClosingCostsBuyNote": hostile, "notes": "PRIVATE NOTE", "contact": "PRIVATE CONTACT"}
        response = client.post("/reports/brrr-html", json=payload, params={"include_deal_inputs": "true"})
        assert response.status_code == 200, response.text
        assert "<script>alert" not in response.text and "<img" not in response.text
        rows = _rows_by_stage(_inputs_section(parse_html(response.text)))
        assert rows["Buy"]["What the other closing costs are for"] == hostile
        assert "PRIVATE NOTE" not in response.text and "PRIVATE CONTACT" not in response.text
        for private_field in PRIVATE_DEAL_FIELDS:
            assert private_field not in {f.payload_key for s in BRRRR_DEAL_INPUT_SECTIONS for g in s.groups for f in g.fields}

    def test_mcp_tool_takes_the_flag(self, client, brrrr_payload):
        blocks = call_mcp_tool("report_brrr_html", address="1 Shared Form St", body=brrrr_payload,
                               selected_result_keys=["dscr"], include_deal_inputs=True)
        assert _inputs_section(parse_html(blocks[1].resource.text)) is not None

    def test_the_builder_without_inputs_is_unchanged(self):
        body = {"cash_flow": 5, "breakdowns": {"cash_flow": [{"label": "Monthly Cash Flow", "value": 5, "unit": "money", "formula": "x"}]}}
        assert 'id="deal-inputs"' not in build_deal_html_report("A", "BRRRR", body, ["cash_flow"])
