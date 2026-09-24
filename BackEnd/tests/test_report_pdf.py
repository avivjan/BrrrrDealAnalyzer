"""The "Generate Report" PDF: the chosen results, each laid out like the website's breakdown popup.

- `report_result_tiles` is pinned to the tiles the two deal modals render and to the frontend's list.
- `breakdown_tree` is the port of `calculationBreakdownTree.ts`: unit tests mirroring the TS ones, and
  a parity fixture both languages rebuild from the recorded calculation goldens.
- `format_value_like_calculation_popup` matches `calculationStepFormat.ts`.
- The PDF itself: only the chosen sections, the popup's rows with the popup's numbers, working links,
  the bookmark outline mirroring the fully expanded tree, escaping, and the 422s.
"""

from __future__ import annotations

import io
import json
import os
import pathlib
import re

import pypdf
import pytest

from BL.reports.common.breakdown_tree import (
    all_expandable_row_paths,
    child_ancestor_step_labels,
    default_expanded_row_paths,
    find_headline_step_index,
    find_step_by_label,
    rows_of_step,
    rows_of_steps,
    steps_after_headline,
    top_level_rows_for_headline,
)
from BL.reports.common.deal_pdf import build_deal_pdf, format_value_like_calculation_popup
from BL.reports.common.report_result_tiles import (
    BRRRR_REPORT_RESULT_TILES,
    FLIP_REPORT_RESULT_TILES,
    UnknownReportResultKeys,
    select_report_result_tiles,
)
from tests.test_explain import FRONTEND_BRRR_RESULT_TILE_KEYS, FRONTEND_FLIP_RESULT_TILE_KEYS

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[2]
FRONTEND_DEAL_COMPONENTS = REPOSITORY_ROOT / "frontend" / "src" / "components" / "deal"
CALCULATION_GOLDENS = pathlib.Path(__file__).resolve().parent / "_regression_snapshots" / "calculations.json"
BREAKDOWN_TREE_PARITY_FIXTURE = FRONTEND_DEAL_COMPONENTS / "__fixtures__" / "calculationBreakdownTreeParity.json"


def _pdf_text(pdf: bytes) -> str:
    pages = pypdf.PdfReader(io.BytesIO(pdf)).pages
    return re.sub(r"\s+", " ", " ".join(page.extract_text() for page in pages))


def _recorded_baseline_bodies() -> dict[str, dict]:
    recorded = json.loads(CALCULATION_GOLDENS.read_text())
    return {"BRRRR": recorded["brrr"]["baseline"]["body"], "FLIP": recorded["flip"]["baseline"]["body"]}


# -- the tile lists ------------------------------------------------------------------------------
class TestReportResultTilesMatchTheWebsiteTiles:
    def test_keys_match_the_pinned_frontend_tile_keys(self):
        assert [tile.result_key for tile in BRRRR_REPORT_RESULT_TILES] == FRONTEND_BRRR_RESULT_TILE_KEYS
        assert [tile.result_key for tile in FLIP_REPORT_RESULT_TILES] == FRONTEND_FLIP_RESULT_TILE_KEYS

    @pytest.mark.parametrize("view_file_name", ["MyDeals.vue", "BoughtDeals.vue"])
    def test_labels_match_the_tiles_each_view_renders(self, view_file_name):
        view_source = (REPOSITORY_ROOT / "frontend" / "src" / "views" / view_file_name).read_text()
        rendered_key_label_pairs = set(re.findall(r'metric-label="([^"]+)"\s+metric-key="([^"]+)"', view_source))
        for tile in [*BRRRR_REPORT_RESULT_TILES, *FLIP_REPORT_RESULT_TILES]:
            assert (tile.tile_label, tile.result_key) in rendered_key_label_pairs, tile

    def test_the_frontend_picker_list_is_the_same(self):
        frontend_source = (FRONTEND_DEAL_COMPONENTS / "reportResultTiles.ts").read_text()
        for deal_type, tiles in (("BRRRR", BRRRR_REPORT_RESULT_TILES), ("FLIP", FLIP_REPORT_RESULT_TILES)):
            block = re.search(rf"export const {deal_type}_REPORT_RESULT_TILES[^=]*=\s*\[(.*?)\];", frontend_source, re.S)
            assert block, deal_type
            frontend_tiles = re.findall(r'resultKey:\s*"([^"]+)",\s*tileLabel:\s*"([^"]+)",\s*unit:\s*"([^"]+)"', block.group(1))
            assert frontend_tiles == [(tile.result_key, tile.tile_label, tile.unit) for tile in tiles], deal_type


class TestSelectReportResultTiles:
    def test_none_means_every_tile_in_tile_order(self):
        assert select_report_result_tiles("BRRRR", None) == BRRRR_REPORT_RESULT_TILES
        assert select_report_result_tiles("FLIP", None) == FLIP_REPORT_RESULT_TILES

    def test_a_selection_keeps_tile_order_and_collapses_duplicates(self):
        chosen = select_report_result_tiles("BRRRR", ["dscr", "cash_flow", "dscr"])
        assert [tile.result_key for tile in chosen] == ["cash_flow", "dscr"]

    def test_an_empty_selection_is_refused(self):
        with pytest.raises(UnknownReportResultKeys, match="at least one"):
            select_report_result_tiles("BRRRR", [])

    def test_an_unknown_or_other_deal_type_key_is_refused(self):
        with pytest.raises(UnknownReportResultKeys, match="annualized_roi"):
            select_report_result_tiles("BRRRR", ["cash_flow", "annualized_roi"])
        with pytest.raises(UnknownReportResultKeys, match="total_hard_money_cost"):
            select_report_result_tiles("BRRRR", ["total_hard_money_cost"])


# -- the tree helpers: mirrors calculationBreakdownTree.test.ts ----------------------------------
def _money_step(label, value, **extra):
    return {"label": label, "value": value, "unit": "money", "formula": f"{label} = {value}", **extra}


TREE_FIXTURE = {
    "cash_to_close_buy": [
        _money_step("Down Payment (cash)", 40000),
        _money_step("HML Points (cash at closing)", 3220, formula="2% × Hard Money Loan ($161,000) = $3,220"),
        _money_step("Cash to Close (Buy)", 43220, terms=[
            {"label": "Down Payment", "value": 40000, "sign": "+", "step_label": "Down Payment (cash)"},
            {"label": "HML Points", "value": 3220, "sign": "+", "step_label": "HML Points (cash at closing)"},
        ]),
    ],
    "total_cash_needed_for_deal": [
        _money_step("Cash to Close (Buy)", 43220, terms=[
            {"label": "Down Payment", "value": 40000, "sign": "+", "step_label": "Down Payment (cash)"},
            {"label": "HML Points", "value": 3220, "sign": "+", "step_label": "HML Points (cash at closing)"},
        ]),
        _money_step("Holding Costs (until refi)", 2400, note="Taxes, insurance and HOA until the refi."),
        _money_step("Total Cash Invested (pre-refi)", 45620, terms=[
            {"label": "Cash to Close (Buy)", "value": 43220, "sign": "+", "step_label": "Cash to Close (Buy)"},
            {"label": "Holding Costs", "value": 2400, "sign": "+", "step_label": "Holding Costs (until refi)"},
        ]),
        _money_step("Cash Needed", 50620, terms=[
            {"label": "Total Cash Invested", "value": 45620, "sign": "+", "step_label": "Total Cash Invested (pre-refi)"},
            {"label": "Rehab Cushion", "value": 5000, "sign": "+", "step_label": None},
        ]),
    ],
    "dscr": [
        _money_step("PITIA", 2166.67, terms=[
            {"label": "Mortgage", "value": 1716.67, "sign": "+", "step_label": "Monthly Mortgage Payment"},
            {"label": "Taxes ÷ 12", "value": 450, "sign": "+"},
        ]),
        {"label": "DSCR", "value": 1.2, "unit": "ratio", "formula": "Rent ($2,600) ÷ PITIA ($2,166.67) = 1.20"},
    ],
}


class TestBreakdownTreeHelpers:
    def test_finds_the_headline_by_the_tiles_value_falling_back_to_the_last_step(self):
        steps = TREE_FIXTURE["total_cash_needed_for_deal"]
        assert find_headline_step_index(steps, 45620) == 2
        assert find_headline_step_index(steps, 50620) == 3
        assert find_headline_step_index(steps, 1) == 3
        assert find_headline_step_index(steps, None) == 3
        assert find_headline_step_index([], 1) == -1

    def test_looks_a_step_up_in_the_referring_section_first_then_in_any_section(self):
        assert find_step_by_label(TREE_FIXTURE, "total_cash_needed_for_deal", "Cash to Close (Buy)") is TREE_FIXTURE["total_cash_needed_for_deal"][0]
        assert find_step_by_label(TREE_FIXTURE, "total_cash_needed_for_deal", "HML Points (cash at closing)") is TREE_FIXTURE["cash_to_close_buy"][1]
        assert find_step_by_label(TREE_FIXTURE, "total_cash_needed_for_deal", "Nowhere") is None

    def test_a_sum_headline_becomes_its_operand_rows_linked_where_the_backend_named_a_step(self):
        rows = top_level_rows_for_headline(TREE_FIXTURE, "total_cash_needed_for_deal", 3)
        assert [(r.path, r.sign, r.label, r.value, r.linked_step and r.linked_step["label"]) for r in rows] == [
            ("0", "+", "Total Cash Invested", 45620, "Total Cash Invested (pre-refi)"),
            ("1", "+", "Rehab Cushion", 5000, None),
        ]
        assert default_expanded_row_paths(rows) == ["0"]

    def test_a_linked_row_drills_down_to_its_own_operands_and_stops_at_raw_inputs(self):
        invested = top_level_rows_for_headline(TREE_FIXTURE, "total_cash_needed_for_deal", 3)[0]
        invested_rows = rows_of_step(invested.linked_step, TREE_FIXTURE, "total_cash_needed_for_deal", invested.path,
                                     {"Cash Needed", invested.linked_step["label"]})
        assert [(r.path, r.label, r.linked_step["label"]) for r in invested_rows] == [
            ("0/0", "Cash to Close (Buy)", "Cash to Close (Buy)"),
            ("0/1", "Holding Costs", "Holding Costs (until refi)"),
        ]
        cash_to_close_rows = rows_of_step(invested_rows[0].linked_step, TREE_FIXTURE, "total_cash_needed_for_deal", "0/0", set())
        assert [(r.path, r.label, r.linked_step["label"]) for r in cash_to_close_rows] == [
            ("0/0/0", "Down Payment", "Down Payment (cash)"),
            ("0/0/1", "HML Points", "HML Points (cash at closing)"),
        ]
        assert rows_of_step(cash_to_close_rows[1].linked_step, TREE_FIXTURE, "total_cash_needed_for_deal", "0/0/1", set()) == []

    def test_expand_all_enumerates_every_expandable_path_and_a_cycle_never_recurses(self):
        rows = top_level_rows_for_headline(TREE_FIXTURE, "total_cash_needed_for_deal", 3)
        assert all_expandable_row_paths(rows, TREE_FIXTURE, "total_cash_needed_for_deal", {"Cash Needed"}) == [
            "0", "0/0", "0/0/0", "0/0/1", "0/1",
        ]
        cyclic = {"loop": [
            _money_step("A", 1, terms=[{"label": "B", "value": 1, "sign": "+", "step_label": "B"}]),
            _money_step("B", 1, terms=[{"label": "A", "value": 1, "sign": "+", "step_label": "A"}]),
        ]}
        loop_rows = top_level_rows_for_headline(cyclic, "loop", 1)
        assert all_expandable_row_paths(loop_rows, cyclic, "loop", {"B"}) == ["0"]

    def test_a_non_sum_headline_lists_its_earlier_steps_and_steps_after_it_are_separate(self):
        rows = top_level_rows_for_headline(TREE_FIXTURE, "dscr", 1)
        assert [(r.path, r.sign, r.label, r.unit, r.linked_step["label"]) for r in rows] == [("input/0", None, "PITIA", "money", "PITIA")]
        assert [s["label"] for s in steps_after_headline(TREE_FIXTURE["total_cash_needed_for_deal"], 2)] == ["Cash Needed"]
        assert steps_after_headline(TREE_FIXTURE["dscr"], -1) == []


# -- parity with the TypeScript tree -------------------------------------------------------------
def _expanded_rows_for_parity(rows, breakdowns, section_key, ancestor_step_labels) -> list[dict]:
    """The popup's fully expanded tree, depth first, as plain rows (the TS test builds the same)."""
    flattened = []
    for row in rows:
        flattened.append({
            "path": row.path,
            "sign": row.sign,
            "label": row.label,
            "value": row.value,
            "unit": row.unit,
            "linkedStepLabel": row.linked_step["label"] if row.linked_step else None,
            "formattedValue": format_value_like_calculation_popup(row.unit, row.value),
        })
        if row.linked_step is not None:
            ancestors = child_ancestor_step_labels(row, ancestor_step_labels)
            children = rows_of_step(row.linked_step, breakdowns, section_key, row.path, ancestors)
            flattened.extend(_expanded_rows_for_parity(children, breakdowns, section_key, ancestors))
    return flattened


def _breakdown_tree_parity_document() -> dict:
    document = {
        "_about": (
            "The popup's fully expanded tree for every result tile of the recorded baseline deals "
            "(BackEnd/tests/_regression_snapshots/calculations.json). Built by "
            "BackEnd/tests/test_report_pdf.py (the PDF's Python tree) and checked by both it and "
            "calculationBreakdownTree.test.ts (the popup's TS tree). Re-record with "
            "RECORD_BREAKDOWN_TREE_PARITY=1 pytest tests/test_report_pdf.py after a golden change."
        ),
    }
    for deal_type, body in _recorded_baseline_bodies().items():
        breakdowns = body["breakdowns"]
        tiles = BRRRR_REPORT_RESULT_TILES if deal_type == "BRRRR" else FLIP_REPORT_RESULT_TILES
        per_tile = {}
        for tile in tiles:
            steps = breakdowns[tile.result_key]
            headline_index = find_headline_step_index(steps, body[tile.result_key])
            headline_label = steps[headline_index]["label"]
            per_tile[tile.result_key] = {
                "headlineStepIndex": headline_index,
                "headlineStepLabel": headline_label,
                "rows": _expanded_rows_for_parity(
                    top_level_rows_for_headline(breakdowns, tile.result_key, headline_index),
                    breakdowns, tile.result_key, frozenset({headline_label}),
                ),
                "derivedRows": _expanded_rows_for_parity(
                    rows_of_steps(steps_after_headline(steps, headline_index), "derived"),
                    breakdowns, tile.result_key, frozenset(),
                ),
            }
        document[deal_type] = per_tile
    return document


class TestBreakdownTreeParityWithThePopup:
    def test_the_python_tree_matches_the_shared_fixture(self):
        document = _breakdown_tree_parity_document()
        if os.environ.get("RECORD_BREAKDOWN_TREE_PARITY"):
            BREAKDOWN_TREE_PARITY_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
            BREAKDOWN_TREE_PARITY_FIXTURE.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n")
        assert json.loads(BREAKDOWN_TREE_PARITY_FIXTURE.read_text()) == document


# -- value formatting: mirrors calculationStepFormat.test.ts --------------------------------------
class TestFormatValueLikeCalculationPopup:
    @pytest.mark.parametrize("unit, value, expected", [
        ("money", 150000, "$150,000"),
        ("money", 1234.5, "$1,234.50"),
        ("money", -26587, "-$26,587"),
        ("money", 0, "$0"),
        ("money", 85.04, "$85.04"),
        ("money", 0.125, "$0.13"),        # Intl rounds a binary tie half away from zero
        ("money", -0.125, "-$0.13"),
        (None, -1, "-$1"),                # money sentinels are never decoded
        ("money", -2, "-$2"),
        ("pct", 19.874, "19.87%"),
        ("pct", -1, "∞%"),
        ("pct", -2, "-∞%"),
        ("pct", 1.005, "1.00%"),          # 1.005 is 1.00499… in binary, as toFixed sees it
        ("ratio", 1.2, "1.20x"),
        ("ratio", 1.234, "1.23x"),
        ("money", None, "-"),
    ])
    def test_formats_like_the_popup(self, unit, value, expected):
        assert format_value_like_calculation_popup(unit, value) == expected


# -- the report ----------------------------------------------------------------------------------
def _outline_titles_by_level(outline, level=0) -> list[tuple[int, str]]:
    titles = []
    for item in outline:
        if isinstance(item, list):
            titles.extend(_outline_titles_by_level(item, level + 1))
        else:
            titles.append((level, item.title))
    return titles


def _expected_outline(body: dict, tiles) -> list[tuple[int, str]]:
    """The outline the popup's "Expand all" tree implies: each result, then every expandable row, nested."""
    breakdowns = body["breakdowns"]

    def expandable_rows(rows, section_key, ancestors, level):
        entries = []
        for row in rows:
            if row.linked_step is None:
                continue
            sign_prefix = f"{row.sign} " if row.sign else ""
            entries.append((level, f"{sign_prefix}{row.label} · {format_value_like_calculation_popup(row.unit, row.value)}"))
            children_ancestors = child_ancestor_step_labels(row, ancestors)
            entries.extend(expandable_rows(
                rows_of_step(row.linked_step, breakdowns, section_key, row.path, children_ancestors),
                section_key, children_ancestors, level + 1,
            ))
        return entries

    expected = []
    for tile in tiles:
        steps = breakdowns[tile.result_key]
        headline_index = find_headline_step_index(steps, body[tile.result_key])
        expected.append((0, f"How {tile.tile_label} is calculated · {format_value_like_calculation_popup(tile.unit, body[tile.result_key])}"))
        expected.extend(expandable_rows(top_level_rows_for_headline(breakdowns, tile.result_key, headline_index),
                                        tile.result_key, frozenset({steps[headline_index]["label"]}), 1))
        expected.extend(expandable_rows(rows_of_steps(steps_after_headline(steps, headline_index), "derived"),
                                        tile.result_key, frozenset(), 1))
    return expected


def _popup_default_view_lines(body: dict, tile) -> list[str]:
    """What the popup shows on arrival for a tile, one "sign label [›] value" line per row, in order."""
    breakdowns = body["breakdowns"]
    steps = breakdowns[tile.result_key]
    headline_index = find_headline_step_index(steps, body[tile.result_key])
    headline = steps[headline_index]

    def line(row):
        arrow = " ›" if row.linked_step is not None else ""
        return f"{row.sign or ''} {row.label}{arrow} {format_value_like_calculation_popup(row.unit, row.value)}".strip()

    lines = []
    for rows, ancestors in (
        (top_level_rows_for_headline(breakdowns, tile.result_key, headline_index), frozenset({headline["label"]})),
        (rows_of_steps(steps_after_headline(steps, headline_index), "derived"), frozenset()),
    ):
        for row in rows:
            lines.append(line(row))
            if row.linked_step is None:
                continue
            children = rows_of_step(row.linked_step, breakdowns, tile.result_key, row.path, child_ancestor_step_labels(row, ancestors))
            lines.extend(line(child) for child in children)
            if children:
                lines.append(f"= {row.linked_step['label']} {format_value_like_calculation_popup(row.linked_step['unit'], row.linked_step['value'])}")
    return lines


def _normalize_like_pdf_text(text: str) -> str:
    return re.sub(r"\s+", " ", text)


class TestReportPdfRendersThePopups:
    def test_every_tile_is_a_popup_shaped_section_by_default(self, client, brrrr_payload):
        response = client.post("/reports/brrr-pdf", json=brrrr_payload, params={"address": "1 Shared Form St"})
        assert response.status_code == 200, response.text
        text = _pdf_text(response.content)
        for tile in BRRRR_REPORT_RESULT_TILES:
            assert f"How {tile.tile_label} is calculated" in text
        assert "Results in this report" in text and "Step details" in text
        assert "All steps in calculation order" in text

    def test_only_the_selected_results_are_rendered(self, client, brrrr_payload):
        response = client.post("/reports/brrr-pdf", json=brrrr_payload,
                               params={"address": "1 Shared Form St", "selected_result_keys": ["dscr", "cash_flow"]})
        assert response.status_code == 200, response.text
        text = _pdf_text(response.content)
        assert "How Cash Flow is calculated" in text and "How DSCR is calculated" in text
        for tile in BRRRR_REPORT_RESULT_TILES:
            if tile.result_key not in ("cash_flow", "dscr"):
                assert f"How {tile.tile_label} is calculated" not in text, tile.result_key
        outline_top_level = [title for level, title in _outline_titles_by_level(pypdf.PdfReader(io.BytesIO(response.content)).outline) if level == 0]
        assert [title.split(" · ")[0] for title in outline_top_level] == ["How Cash Flow is calculated", "How DSCR is calculated"]

    @pytest.mark.parametrize("deal_type", ["BRRRR", "FLIP"])
    def test_every_row_the_popup_shows_on_arrival_is_in_the_pdf_with_the_popups_number(self, client, brrrr_payload, flip_payload, deal_type):
        payload, route, tiles = (
            (brrrr_payload, "brrr", BRRRR_REPORT_RESULT_TILES) if deal_type == "BRRRR" else (flip_payload, "flip", FLIP_REPORT_RESULT_TILES)
        )
        analysis = client.post(f"/analyze/{route}", json=payload)
        assert analysis.status_code == 200, analysis.text
        body = analysis.json()
        for tile in tiles:
            response = client.post(f"/reports/{route}-pdf", json=payload, params={"selected_result_keys": [tile.result_key]})
            assert response.status_code == 200, response.text
            text = _pdf_text(response.content)
            headline_value = format_value_like_calculation_popup(tile.unit, body[tile.result_key])
            assert f"How {tile.tile_label} is calculated {headline_value}" in text, tile.result_key
            for expected_line in _popup_default_view_lines(body, tile):
                assert _normalize_like_pdf_text(expected_line) in text, (tile.result_key, expected_line)

    @pytest.mark.parametrize("deal_type", ["BRRRR", "FLIP"])
    def test_the_outline_mirrors_each_popups_fully_expanded_tree(self, client, brrrr_payload, flip_payload, deal_type):
        payload, route, tiles = (
            (brrrr_payload, "brrr", BRRRR_REPORT_RESULT_TILES) if deal_type == "BRRRR" else (flip_payload, "flip", FLIP_REPORT_RESULT_TILES)
        )
        body = client.post(f"/analyze/{route}", json=payload).json()
        response = client.post(f"/reports/{route}-pdf", json=payload)
        reader = pypdf.PdfReader(io.BytesIO(response.content))
        assert _outline_titles_by_level(reader.outline) == _expected_outline(body, tiles)

    def test_bookmarks_and_links_land_on_the_step_they_name(self, client, brrrr_payload):
        response = client.post("/reports/brrr-pdf", json=brrrr_payload, params={"selected_result_keys": ["total_cash_needed_for_deal"]})
        reader = pypdf.PdfReader(io.BytesIO(response.content))
        page_texts = [_normalize_like_pdf_text(page.extract_text()) for page in reader.pages]

        def check(items):
            for item in items:
                if isinstance(item, list):
                    check(item)
                    continue
                target_page_index = reader.get_destination_page_number(item)
                row_label = item.title.split(" · ")[0].lstrip("+- ").strip()
                if row_label.startswith("How "):
                    assert row_label in page_texts[target_page_index]
                    continue
                # The step block's heading is the linked step's own label, which starts where the row's does
                # (the row "Cash to Close (Buy)" opens "Cash to Close (Buy)"; "Total Cash Invested" opens
                # "Total Cash Invested (pre-refi)"), so the block is found by its value line on that page.
                assert "· " + item.title.split(" · ")[1] in page_texts[target_page_index], item.title

        check(reader.outline)
        page_object_ids = {page.indirect_reference.idnum for page in reader.pages}
        link_count = 0
        for page in reader.pages:
            for annotation_reference in page.get("/Annots") or []:
                annotation = annotation_reference.get_object()
                if annotation.get("/Subtype") != "/Link":
                    continue
                link_count += 1
                assert annotation["/Dest"][0].idnum in page_object_ids
        body = client.post("/analyze/brrr", json=brrrr_payload).json()
        tile = next(t for t in BRRRR_REPORT_RESULT_TILES if t.result_key == "total_cash_needed_for_deal")
        expandable_rows_on_arrival = sum(" › " in line for line in _popup_default_view_lines(body, tile))
        assert link_count >= expandable_rows_on_arrival + 2  # + the summary row and the "All steps" link
        assert "← Back to How Cash Needed is calculated" in " ".join(page_texts)

    def test_flip_report(self, client, flip_payload):
        response = client.post("/reports/flip-pdf", json=flip_payload, params={"address": "2 Shared Form Ave"})
        assert response.status_code == 200, response.text
        text = _pdf_text(response.content)
        assert "How Net Profit is calculated $12,620" in text
        assert "How ROI is calculated 19.41%" in text
        assert "Agent fees are the buyer's 3% plus the seller's 3%." in text

    def test_address_markup_is_escaped(self, client, brrrr_payload):
        address = "1 <b>Bold</b> & Co <script>"
        response = client.post("/reports/brrr-pdf", json=brrrr_payload, params={"address": address, "selected_result_keys": ["dscr"]})
        assert response.status_code == 200, response.text
        assert "1 <b>Bold</b> & Co <script>" in _pdf_text(response.content)

    def test_step_text_markup_is_escaped(self):
        body = {
            "cash_flow": 5,
            "breakdowns": {"cash_flow": [
                {"label": "<b>Rent</b> & <a href='#x'>co</a>", "value": 5, "unit": "money",
                 "formula": "a < b > c & <font size=40>d</font>", "note": "<i>note</i> &amp;"},
            ]},
        }
        text = _pdf_text(build_deal_pdf("Addr", "BRRRR", body, ["cash_flow"]))
        assert "a < b > c & <font size=40>d</font>" in text
        assert "<i>note</i> &amp;" in text

    @pytest.mark.parametrize("route, params", [
        ("brrr", {"selected_result_keys": ["not_a_result"]}),
        ("brrr", {"selected_result_keys": ["annualized_roi"]}),          # a flip tile on the BRRRR route
        ("brrr", {"selected_result_keys": ["total_hard_money_cost"]}),   # a section without a tile
        ("brrr", {"selected_result_keys": [""]}),
        ("flip", {"selected_result_keys": ["cash_flow"]}),
    ])
    def test_unknown_or_empty_selections_are_a_422(self, client, brrrr_payload, flip_payload, route, params):
        payload = brrrr_payload if route == "brrr" else flip_payload
        response = client.post(f"/reports/{route}-pdf", json=payload, params=params)
        assert response.status_code == 422, response.text


# -- main's PR #83 breakdown explanations reach the PDF --------------------------------------------
BRRRR_BREAKDOWN_SCENARIOS = {
    "standard_with_closing_date": {},
    "we_pay_all_closing_costs": {"titleModeBuy": "we_pay_all"},
    "no_buy_closing_date": {"buyClosingDate": None},
}


def _analysis_and_report_text(client, payload: dict, selected_result_keys: list[str]) -> tuple[dict, str, list]:
    analysis = client.post("/analyze/brrr", json=payload)
    assert analysis.status_code == 200, analysis.text
    report = client.post("/reports/brrr-pdf", json=payload, params={"selected_result_keys": selected_result_keys})
    assert report.status_code == 200, report.text
    reader = pypdf.PdfReader(io.BytesIO(report.content))
    return analysis.json(), _pdf_text(report.content), _outline_titles_by_level(reader.outline)


def _step_by_label(breakdowns: dict, label: str) -> dict:
    step = find_step_by_label(breakdowns, "total_cash_needed_for_deal", label)
    assert step is not None, label
    return step


class TestBreakdownExplanationsFromPr83ReachThePdf:
    """HML Interest paid monthly (a new step, now drillable from Total Cash Invested), the deed transfer
    tax's who-pays explanation and the title & escrow price tier: each in the PDF, word for word as the
    popup shows it, for a standard deal, a we-pay-all deal and a deal without a buy closing date."""

    @pytest.mark.parametrize("scenario", list(BRRRR_BREAKDOWN_SCENARIOS))
    def test_hml_interest_paid_monthly_is_a_link_under_total_cash_invested_with_its_own_block(self, client, brrrr_payload, scenario):
        payload = {**brrrr_payload, **BRRRR_BREAKDOWN_SCENARIOS[scenario]}
        analysis, text, outline = _analysis_and_report_text(client, payload, ["total_cash_needed_for_deal", "cash_out"])
        step = _step_by_label(analysis["breakdowns"], "HML Interest paid monthly")
        value_text = format_value_like_calculation_popup("money", step["value"])

        # A clickable row (›) in the first-level-expanded Total Cash Invested of both sections.
        assert text.count(f"+ HML Interest paid monthly › {value_text}") >= 2
        # Its Step details block: heading, the monthly × months formula and the prepaid / accrued note.
        assert f"HML Interest paid monthly · {value_text}" in text
        assert _normalize_like_pdf_text(step["formula"]) in text
        assert _normalize_like_pdf_text(step["note"]) in text
        assert "Monthly HML interest: per diem" in step["formula"]
        if scenario == "no_buy_closing_date":
            assert step["note"].startswith("No buy closing date")
        else:
            assert "paid from your pocket on the 1st of each month" in step["note"]
        # The bookmark tree nests it under Total Cash Invested.
        for index, (level, title) in enumerate(outline):
            if title == f"+ HML Interest paid monthly · {value_text}":
                parent_title = next(t for lvl, t in reversed(outline[:index]) if lvl == level - 1)
                assert "Total Cash Invested" in parent_title
                break
        else:
            pytest.fail("no outline entry for HML Interest paid monthly")

    @pytest.mark.parametrize("scenario", list(BRRRR_BREAKDOWN_SCENARIOS))
    def test_deed_transfer_tax_and_title_escrow_explanations_are_in_the_pdf(self, client, brrrr_payload, scenario):
        payload = {**brrrr_payload, **BRRRR_BREAKDOWN_SCENARIOS[scenario]}
        analysis, text, _ = _analysis_and_report_text(client, payload, ["cash_to_close_buy"])
        deed_step = _step_by_label(analysis["breakdowns"], "Deed Transfer Tax (Buy)")
        title_step = _step_by_label(analysis["breakdowns"], "Title & Escrow (Buy)")
        for step in (deed_step, title_step):
            assert _normalize_like_pdf_text(step["formula"]) in text, step["label"]
            assert _normalize_like_pdf_text(step["note"]) in text, step["label"]
        if scenario == "we_pay_all_closing_costs":
            assert "we also pay the seller's deed transfer tax" in deed_step["formula"]
            assert "added into Recording & Transfer (Buy)" in deed_step["note"]
            assert "fee is set by the purchase price tier" in title_step["formula"]
            assert "Purchase $200,000 is between $150,000 and $200,000 → $2,200" in text
        else:
            assert "the seller pays the deed transfer tax" in deed_step["formula"]
            assert "Choosing 'we pay all closing costs' would add it" in deed_step["note"]
            assert title_step["formula"].startswith("Standard deal → flat $1,000")
        # Title & Escrow is an operand of Closing Costs (Buy), itself opened under Cash to Close: a link to its block.
        title_value_text = format_value_like_calculation_popup("money", title_step["value"])
        assert f"+ Title & Escrow › {title_value_text}" in text
        assert f"Title & Escrow (Buy) · {title_value_text}" in text
