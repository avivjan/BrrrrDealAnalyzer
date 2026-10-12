"""The interactive HTML report: one self-contained file that works like the website's breakdown popups.

- Every result card holds the popup's whole tree as nested `<details>`, row for row and number for
  number (built from `breakdown_tree`, the port pinned to the popup's TS tree), with only the first
  level open, as the popup opens on arrival.
- Formulas, notes, totals, "Derived from this" and "All N steps" are where the popup shows them.
- The file is self-contained and locked down: no external resource, its own CSP whose hash matches
  its one script, and every text escaped.
- The endpoints: the file download, the selection, the 422s; and the MCP tools.
"""

from __future__ import annotations

import base64
import hashlib
import json
import pathlib
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

import pytest

from BL.reports.common.breakdown_tree import (
    child_ancestor_step_labels,
    find_headline_step_index,
    is_sum_step,
    rows_of_step,
    rows_of_steps,
    steps_after_headline,
    top_level_rows_for_headline,
)
from BL.reports.common.deal_html_report import REPORT_CONTENT_SECURITY_POLICY, build_deal_html_report
from BL.reports.common.deal_pdf import format_value_like_calculation_popup
from BL.reports.common.report_result_tiles import BRRRR_REPORT_RESULT_TILES, FLIP_REPORT_RESULT_TILES
from tests.mcp_helpers import call as call_mcp_tool

CALCULATION_GOLDENS = pathlib.Path(__file__).resolve().parent / "_regression_snapshots" / "calculations.json"
VOID_ELEMENTS = {"meta", "br", "img", "input", "link", "hr", "path", "stop", "circle"}


# -- a tiny DOM, so the tests read the file the way a browser does ---------------------------------
@dataclass
class ParsedHtmlElement:
    tag: str
    attributes: dict[str, str | None]
    children: list["ParsedHtmlElement | str"] = field(default_factory=list)

    @property
    def classes(self) -> set[str]:
        return set((self.attributes.get("class") or "").split())

    def text(self) -> str:
        return "".join(child if isinstance(child, str) else child.text() for child in self.children)

    def elements(self) -> list["ParsedHtmlElement"]:
        return [child for child in self.children if isinstance(child, ParsedHtmlElement)]

    def child(self, tag: str, css_class: str | None = None) -> "ParsedHtmlElement | None":
        for element in self.elements():
            if element.tag == tag and (css_class is None or css_class in element.classes):
                return element
        return None

    def find_all(self, predicate) -> list["ParsedHtmlElement"]:
        found = []
        for element in self.elements():
            if predicate(element):
                found.append(element)
            found.extend(element.find_all(predicate))
        return found


class _DomBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = ParsedHtmlElement("#document", {})
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        element = ParsedHtmlElement(tag, dict(attrs))
        self.stack[-1].children.append(element)
        if tag not in VOID_ELEMENTS:
            self.stack.append(element)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(ParsedHtmlElement(tag, dict(attrs)))

    def handle_endtag(self, tag):
        if tag in VOID_ELEMENTS:
            return
        while len(self.stack) > 1:
            if self.stack.pop().tag == tag:
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse_html(html: str) -> ParsedHtmlElement:
    builder = _DomBuilder()
    builder.feed(html)
    return builder.root


def _span_text(line: ParsedHtmlElement, css_class: str) -> str:
    span = line.child("span", css_class)
    return span.text() if span is not None else ""


# -- the tree, as the file has it and as the popup builds it --------------------------------------
def _actual_rows(tree_list: ParsedHtmlElement) -> list[dict]:
    """The rows of a `ul.tree` as data: sign, label, value, open, children / formula / note, and the total."""
    rows = []
    for item in tree_list.elements():
        if "total" in item.classes:
            rows.append({"total": (_span_text(item, "label"), _span_text(item, "val"))})
            continue
        details = item.child("details")
        line = details.child("summary") if details is not None else item.child("div", "line")
        row = {"sign": _span_text(line, "sign"), "label": _span_text(line, "label"), "value": _span_text(line, "val")}
        if details is not None:
            children_box = details.child("div", "children")
            nested_tree = children_box.child("ul", "tree")
            formula = children_box.child("p", "formula")
            note = children_box.child("p", "note")
            row["open"] = "open" in details.attributes
            row["children"] = _actual_rows(nested_tree) if nested_tree is not None else None
            row["formula"] = formula.text() if formula is not None else None
            row["note"] = note.text() if note is not None else None
        rows.append(row)
    return rows


def _expected_rows(rows, breakdowns, section_key, ancestor_step_labels, depth) -> list[dict]:
    """The popup's fully expanded tree, first level open, in the same shape as `_actual_rows`."""
    expected = []
    for row in rows:
        entry = {"sign": row.sign or "", "label": row.label, "value": format_value_like_calculation_popup(row.unit, row.value)}
        if row.linked_step is not None:
            children_ancestors = child_ancestor_step_labels(row, ancestor_step_labels)
            children = rows_of_step(row.linked_step, breakdowns, section_key, row.path, children_ancestors)
            step = row.linked_step
            entry["open"] = depth == 0
            entry["children"] = (
                _expected_rows(children, breakdowns, section_key, children_ancestors, depth + 1)
                + [{"total": (step["label"], format_value_like_calculation_popup(step.get("unit"), step.get("value")))}]
                if children else None
            )
            entry["formula"] = None if children else step.get("formula", "")
            entry["note"] = step.get("note") or None
        expected.append(entry)
    return expected


def _recorded_baseline_bodies() -> dict[str, dict]:
    recorded = json.loads(CALCULATION_GOLDENS.read_text())
    return {"BRRRR": recorded["brrr"]["baseline"]["body"], "FLIP": recorded["flip"]["baseline"]["body"]}


def _card(document: ParsedHtmlElement, result_index: int) -> ParsedHtmlElement:
    cards = document.find_all(lambda e: e.tag == "section" and e.attributes.get("id") == f"result-{result_index}")
    assert len(cards) == 1
    return cards[0]


# -- the cards equal the popups --------------------------------------------------------------------
class TestEveryCardIsThePopup:
    @pytest.mark.parametrize("deal_type", ["BRRRR", "FLIP"])
    def test_each_card_holds_the_popups_tree_row_for_row_with_the_first_level_open(self, deal_type):
        body = _recorded_baseline_bodies()[deal_type]
        breakdowns = body["breakdowns"]
        tiles = BRRRR_REPORT_RESULT_TILES if deal_type == "BRRRR" else FLIP_REPORT_RESULT_TILES
        document = parse_html(build_deal_html_report("1 Shared Form St", deal_type, body))

        for result_index, tile in enumerate(tiles):
            card = _card(document, result_index)
            steps = breakdowns[tile.result_key]
            headline_index = find_headline_step_index(steps, body[tile.result_key])
            headline = steps[headline_index]
            assert card.find_all(lambda e: e.tag == "h2")[0].text() == f"How {tile.tile_label} is calculated"
            assert card.find_all(lambda e: "headline" in e.classes)[0].text() == format_value_like_calculation_popup(headline["unit"], headline["value"])

            root_trees = card.find_all(lambda e: e.tag == "ul" and {"tree", "root"} <= e.classes)
            expected_top = _expected_rows(top_level_rows_for_headline(breakdowns, tile.result_key, headline_index),
                                          breakdowns, tile.result_key, frozenset({headline["label"]}), 0)
            if is_sum_step(headline):
                expected_top.append({"total": (headline["label"], format_value_like_calculation_popup(headline["unit"], headline["value"]))})
            else:
                formula_box = card.find_all(lambda e: "formula-box" in e.classes)[0]
                assert formula_box.child("p", "formula").text() == headline["formula"]
            derived_steps = steps_after_headline(steps, headline_index)
            expected_trees = [expected_top] if expected_top else []
            if derived_steps:
                expected_trees.append(_expected_rows(rows_of_steps(derived_steps, "derived"), breakdowns, tile.result_key, frozenset(), 0))
            assert [_actual_rows(tree) for tree in root_trees] == expected_trees, tile.result_key

            all_steps = card.find_all(lambda e: e.tag == "details" and "all-steps" in e.classes)[0]
            assert "open" not in all_steps.attributes
            assert all_steps.child("summary").text() == f"All {len(steps)} steps in calculation order"
            listed = all_steps.child("ol").elements()
            assert [item.find_all(lambda e: e.tag == "span" and "label" in e.classes)[0].text() for item in listed] == [s["label"] for s in steps]
            assert [item.child("p", "formula").text() for item in listed] == [s["formula"] for s in steps]

    def test_only_the_selected_results_in_tile_order_with_summary_tiles_linking_to_them(self):
        body = _recorded_baseline_bodies()["BRRRR"]
        document = parse_html(build_deal_html_report("A", "BRRRR", body, ["dscr", "cash_flow"]))
        headings = [h.text() for h in document.find_all(lambda e: e.tag == "h2")]
        assert headings == ["How Cash Flow is calculated", "How DSCR is calculated"]
        summary_tiles = document.find_all(lambda e: e.tag == "a" and "tile" in e.classes)
        assert [(a.attributes["href"], _span_text(a, "tile-label"), _span_text(a, "tile-value")) for a in summary_tiles] == [
            ("#result-0", "Cash Flow", format_value_like_calculation_popup("money", body["cash_flow"])),
            ("#result-1", "DSCR", format_value_like_calculation_popup("ratio", body["dscr"])),
        ]

    def test_pr_83_explanations_are_in_the_file(self):
        body = _recorded_baseline_bodies()["BRRRR"]
        html = build_deal_html_report("A", "BRRRR", body)
        document = parse_html(html)
        steps_by_label = {step["label"]: step for steps in body["breakdowns"].values() for step in steps}
        hml_monthly = steps_by_label["HML Interest paid monthly"]
        expandable_labels = [s.find_all(lambda e: "label" in e.classes)[0].text()
                             for s in document.find_all(lambda e: e.tag == "summary" and "line" in e.classes)]
        assert "HML Interest paid monthly" in expandable_labels
        texts = {p.text() for p in document.find_all(lambda e: e.tag == "p")}
        for label in ("HML Interest paid monthly", "Deed Transfer Tax (Buy)", "Title & Escrow (Buy)"):
            assert steps_by_label[label]["formula"] in texts, label
            assert steps_by_label[label]["note"] in texts, label
        assert "Monthly HML interest: per diem" in hml_monthly["formula"]


# -- self-contained and locked down ---------------------------------------------------------------
class TestTheFileIsSelfContainedAndSafe:
    def test_no_external_resources_and_a_csp_that_allows_only_its_own_script(self):
        html = build_deal_html_report("A", "BRRRR", _recorded_baseline_bodies()["BRRRR"])
        assert "http://" not in html and "https://" not in html and "//cdn" not in html
        scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
        assert len(scripts) == 1
        script_hash = "sha256-" + base64.b64encode(hashlib.sha256(scripts[0].encode()).digest()).decode()
        assert f"script-src '{script_hash}'" in REPORT_CONTENT_SECURITY_POLICY
        assert f'<meta http-equiv="Content-Security-Policy" content="{REPORT_CONTENT_SECURITY_POLICY}">' in html
        assert "default-src 'none'" in REPORT_CONTENT_SECURITY_POLICY
        assert 'name="viewport"' in html and '<meta charset="utf-8">' in html

    def test_every_text_is_escaped(self):
        hostile = "<script>alert(1)</script>\"><img src=x onerror=alert(2)></style></details>"
        body = {
            "cash_flow": 5,
            "breakdowns": {"cash_flow": [
                {"label": "PITIA" + hostile, "value": 3, "unit": "money", "formula": "f" + hostile, "note": "n" + hostile},
                {"label": "Monthly Cash Flow", "value": 5, "unit": "money", "formula": "x", "note": hostile,
                 "terms": [{"label": "t" + hostile, "value": 5, "sign": "+", "step_label": "PITIA" + hostile}]},
            ]},
        }
        html = build_deal_html_report("Addr" + hostile, "BRRRR", body, ["cash_flow"])
        assert "<script>alert" not in html and "<img" not in html and "onerror=alert(2)>" not in html
        assert html.count("<script>") == 1 and html.count("</style>") == 1
        document = parse_html(html)
        assert document.find_all(lambda e: e.tag == "h1")[0].text() == "Addr" + hostile
        assert any(p.text() == "f" + hostile for p in document.find_all(lambda e: e.tag == "p"))
        # Even the deal type (always "BRRRR" / "FLIP" from the routes) is escaped where it is printed.
        html_with_hostile_deal_type = build_deal_html_report("A", "<i>x</i>", body, ["cash_flow"])
        assert "<I>X</I>" not in html_with_hostile_deal_type and "&lt;I&gt;X&lt;/I&gt;" in html_with_hostile_deal_type


# -- the endpoints and the MCP tools ---------------------------------------------------------------
class TestHtmlReportEndpoints:
    @pytest.mark.parametrize("route, deal_type", [("brrr", "BRRRR"), ("flip", "FLIP")])
    def test_returns_a_downloadable_html_file(self, client, brrrr_payload, flip_payload, route, deal_type):
        payload = brrrr_payload if route == "brrr" else flip_payload
        response = client.post(f"/reports/{route}-html", json=payload, params={"address": "1 Shared/Form St."})
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert response.headers["content-disposition"] == f'attachment; filename="BigWhales_{deal_type}_1_Shared_Form_St.html"'
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["content-security-policy"].endswith("; sandbox allow-scripts")
        assert response.text.startswith("<!doctype html>")
        assert "1 Shared/Form St." in parse_html(response.text).find_all(lambda e: e.tag == "h1")[0].text()

    def test_selected_results_only(self, client, brrrr_payload):
        response = client.post("/reports/brrr-html", json=brrrr_payload, params={"selected_result_keys": ["roi", "dscr"]})
        assert response.status_code == 200, response.text
        headings = [h.text() for h in parse_html(response.text).find_all(lambda e: e.tag == "h2")]
        assert headings == ["How DSCR is calculated", "How ROI is calculated"]

    @pytest.mark.parametrize("route, keys", [("brrr", ["annualized_roi"]), ("brrr", [""]), ("flip", ["cash_flow"])])
    def test_unknown_selections_are_a_422(self, client, brrrr_payload, flip_payload, route, keys):
        payload = brrrr_payload if route == "brrr" else flip_payload
        response = client.post(f"/reports/{route}-html", json=payload, params={"selected_result_keys": keys})
        assert response.status_code == 422, response.text

    def test_mcp_tool_returns_the_file_as_an_embedded_html_resource(self, client, brrrr_payload):
        blocks = call_mcp_tool("report_brrr_html", address="1 Shared Form St", body=brrrr_payload, selected_result_keys=["dscr"])
        assert [block.type for block in blocks] == ["text", "resource"]
        assert "BigWhales_BRRRR_1_Shared_Form_St.html" in blocks[0].text
        assert blocks[1].resource.mimeType == "text/html"
        headings = [h.text() for h in parse_html(blocks[1].resource.text).find_all(lambda e: e.tag == "h2")]
        assert headings == ["How DSCR is calculated"]
