"""Big Whales branded PDF deal report: one section per chosen result, each laid out like
the website's `CalculationBreakdownPopup` for that result tile.

  1. Property header (address + deal type badge).
  2. "Results in this report": the chosen tiles and their values; each row links to its section.
  3. One section per chosen tile, in tile order, built from the same rows the popup shows
     (`breakdown_tree`, a port of the popup's `calculationBreakdownTree.ts`): the headline value,
     the formula box and "Built from" for a non-sum headline, the tree with its first level
     expanded, the "= headline" total, "Derived from this", and a link to all the steps.
  4. "Step details": one block per computed step reachable from those sections. Every row that
     can be expanded on the website is a link here, so drilling down is a click, as in the popup;
     every block links back to the sections that use it.
  5. "All steps in calculation order": the popup's collapsed list, one per section.
  6. A bookmark outline mirroring each popup's fully expanded tree, and the branded footer.

Every value is formatted exactly as the popup formats it (`format_value_like_calculation_popup`,
mirroring `calculationStepFormat.ts`), and every piece of text goes through `escape` before it
reaches ReportLab's Paragraph mini-markup. Link destinations are named from indices only.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from BL.reports.common.breakdown_tree import (
    CalculationBreakdownRow,
    child_ancestor_step_labels,
    find_headline_step_index,
    is_sum_step,
    rows_of_step,
    rows_of_steps,
    steps_after_headline,
    top_level_rows_for_headline,
)
from BL.reports.common.report_result_tiles import ReportResultTile, select_report_result_tiles


# Big Whales brand palette.
BRAND_NAVY = colors.HexColor("#0B1F3A")
BRAND_BLUE = colors.HexColor("#2563EB")
BRAND_AMBER = colors.HexColor("#F59E0B")
BRAND_INK = colors.HexColor("#111827")
BRAND_MUTED = colors.HexColor("#6B7280")
BRAND_PALE = colors.HexColor("#F3F4F6")
BRAND_BORDER = colors.HexColor("#E5E7EB")


# -- values, formatted exactly like the popup (`calculationStepFormat.ts`) ---------------------
# JavaScript's Intl.NumberFormat and toFixed round the exact binary value half away from zero;
# Decimal(float) is that exact value, so ROUND_HALF_UP here reproduces them digit for digit.
_CENTS = Decimal("0.01")


def _round_half_away_from_zero_to_cents(value: float) -> Decimal:
    return Decimal(value).quantize(_CENTS, rounding=ROUND_HALF_UP)


def _format_money_like_calculation_popup(value: float) -> str:
    is_negative = value < 0 or (value == 0 and str(value).startswith("-"))
    sign = "-" if is_negative else ""
    if float(value).is_integer():
        return f"{sign}${int(abs(value)):,}"
    return f"{sign}${abs(_round_half_away_from_zero_to_cents(value)):,.2f}"


def _format_fixed_two_decimals_like_to_fixed(value: float) -> str:
    rounded = _round_half_away_from_zero_to_cents(value)
    sign = "-" if value < 0 else ""  # toFixed drops the sign of -0, keeps it on -0.001 → "-0.00"
    return f"{sign}{abs(rounded):.2f}"


def format_value_like_calculation_popup(unit: Optional[str], value: Any) -> str:
    """How a calculation step's number reads in the website's breakdown popup.

    money → `$1,234` when whole, `$1,234.56` otherwise, `-$1,234` when negative (never ∞);
    pct → `12.50%`, with the calculators' -1 / -2 sentinels as `∞%` / `-∞%`; ratio → `1.20x`.
    A missing unit is money. A missing value reads "-".
    """
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if unit == "pct":
        if number == -1:
            return "∞%"
        if number == -2:
            return "-∞%"
        return f"{_format_fixed_two_decimals_like_to_fixed(number)}%"
    if unit == "ratio":
        return f"{_format_fixed_two_decimals_like_to_fixed(number)}x"
    return _format_money_like_calculation_popup(number)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "BWTitle", parent=base["Title"],
            fontName="Helvetica-Bold", fontSize=22,
            textColor=BRAND_NAVY, alignment=TA_LEFT, spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "BWSub", parent=base["Normal"],
            fontName="Helvetica", fontSize=11,
            textColor=BRAND_MUTED, spaceAfter=14,
        ),
        "h2": ParagraphStyle(
            "BWH2", parent=base["Heading2"],
            fontName="Helvetica-Bold", fontSize=14,
            textColor=BRAND_NAVY, spaceBefore=14, spaceAfter=8,
        ),
        "h3": ParagraphStyle(
            "BWH3", parent=base["Heading3"],
            fontName="Helvetica-Bold", fontSize=12,
            textColor=BRAND_BLUE, spaceBefore=10, spaceAfter=4,
            keepWithNext=1,
        ),
        "body": ParagraphStyle(
            "BWBody", parent=base["Normal"],
            fontName="Helvetica", fontSize=10,
            textColor=BRAND_INK, leading=14,
        ),
        "small": ParagraphStyle(
            "BWSmall", parent=base["Normal"],
            fontName="Helvetica", fontSize=8,
            textColor=BRAND_MUTED, leading=11, alignment=TA_CENTER,
        ),
        "term": ParagraphStyle(
            "BWTerm", parent=base["Normal"],
            fontName="Helvetica", fontSize=9.5,
            textColor=BRAND_INK, leading=13,
        ),
        "note": ParagraphStyle(
            "BWNote", parent=base["Normal"],
            fontName="Helvetica-Oblique", fontSize=8.5,
            textColor=BRAND_MUTED, leading=11, spaceBefore=2,
        ),
        "section_title": ParagraphStyle(
            "BWSectionTitle", parent=base["Heading2"],
            fontName="Helvetica-Bold", fontSize=14,
            textColor=BRAND_NAVY, spaceBefore=16, spaceAfter=2, keepWithNext=1,
        ),
        "headline_value": ParagraphStyle(
            "BWHeadlineValue", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=18, leading=22,
            textColor=BRAND_INK, spaceAfter=8, keepWithNext=1,
        ),
        "caption": ParagraphStyle(
            "BWCaption", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=8, leading=11,
            textColor=BRAND_MUTED, spaceBefore=8, spaceAfter=3, keepWithNext=1,
        ),
        "formula": ParagraphStyle(
            "BWFormula", parent=base["Normal"],
            fontName="Courier", fontSize=8.5, leading=11.5,
            textColor=BRAND_INK,
        ),
        "row_value": ParagraphStyle(
            "BWRowValue", parent=base["Normal"],
            fontName="Helvetica", fontSize=9.5, leading=13,
            textColor=BRAND_INK, alignment=TA_RIGHT,
        ),
        "link": ParagraphStyle(
            "BWLink", parent=base["Normal"],
            fontName="Helvetica", fontSize=9, leading=12,
            textColor=BRAND_BLUE, spaceBefore=6,
        ),
        "badge": ParagraphStyle(
            "BWBadge", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=9,
            textColor=colors.white, alignment=TA_CENTER,
        ),
    }


# -- links, destinations and the outline ---------------------------------------------------------
# Destination names are built from indices only, never from text.
def _result_destination(result_index: int) -> str:
    return f"result_{result_index}"


def _step_destination(step_index: int) -> str:
    return f"step_{step_index}"


def _all_steps_destination(result_index: int) -> str:
    return f"all_steps_{result_index}"


def _link(destination: str, text_markup: str) -> str:
    return f'<a href="#{destination}" color="#2563EB">{text_markup}</a>'


class _NamedDestinationsFlowable(Flowable):
    """Zero-size marker: registers PDF named destinations at this spot, the targets of links and bookmarks."""

    def __init__(self, destination_names: list[str]):
        super().__init__()
        self.destination_names = destination_names
        self.width = self.height = 0

    def wrap(self, available_width, available_height):
        return 0, 0

    def draw(self):
        for destination_name in self.destination_names:
            self.canv.bookmarkHorizontal(destination_name, 0, 14)


@dataclass
class _OutlineEntry:
    title: str
    destination_name: str
    level: int
    closed: bool


@dataclass
class _ReachableStep:
    """A computed step that gets a block in "Step details"."""
    step_index: int
    step: dict
    # The section whose popup reached it first; a label is looked up there first, as the popup does.
    section_key: str
    # Results whose popup tree reaches this step, for the block's "Back to" links.
    result_indexes: list[int] = field(default_factory=list)
    # Extra destination names at the block, one per outline entry pointing here (an outline entry needs its own).
    outline_destination_names: list[str] = field(default_factory=list)


@dataclass
class _ReportResultSection:
    result_index: int
    tile: ReportResultTile
    steps: list[dict]
    headline_step_index: int
    headline_step: Optional[dict]
    top_level_rows: list[CalculationBreakdownRow]
    derived_rows: list[CalculationBreakdownRow]

    @property
    def root_ancestor_step_labels(self) -> frozenset[str]:
        return frozenset({self.headline_step["label"]}) if self.headline_step else frozenset()

    @property
    def title(self) -> str:
        return f"How {self.tile.tile_label} is calculated"


class _ReportLinkRegistry:
    """Numbers every reachable step once (by object identity: `find_step_by_label` returns the
    response's own dicts) and collects the outline, in document order."""

    def __init__(self, breakdowns: dict):
        self.breakdowns = breakdowns
        self.reachable_step_by_object_id: dict[int, _ReachableStep] = {}
        self.outline_entries: list[_OutlineEntry] = []

    def register_step(self, step: dict, section_key: str, result_index: int) -> _ReachableStep:
        reachable_step = self.reachable_step_by_object_id.get(id(step))
        if reachable_step is None:
            reachable_step = _ReachableStep(len(self.reachable_step_by_object_id), step, section_key)
            self.reachable_step_by_object_id[id(step)] = reachable_step
        if result_index not in reachable_step.result_indexes:
            reachable_step.result_indexes.append(result_index)
        return reachable_step

    def step_destination_of(self, step: dict) -> str:
        return _step_destination(self.reachable_step_by_object_id[id(step)].step_index)

    def register_expanded_tree(
        self,
        rows: list[CalculationBreakdownRow],
        section: _ReportResultSection,
        ancestor_step_labels: frozenset[str],
        outline_level: int,
    ) -> None:
        """Walk the popup's fully expanded ("Expand all") tree: register every linked step and add
        one outline entry per expandable row, nested as in the popup."""
        for row in rows:
            if row.linked_step is None:
                continue
            reachable_step = self.register_step(row.linked_step, section.tile.result_key, section.result_index)
            outline_destination_name = f"outline_{len(self.outline_entries)}"
            reachable_step.outline_destination_names.append(outline_destination_name)
            sign_prefix = f"{row.sign} " if row.sign else ""
            self.outline_entries.append(_OutlineEntry(
                title=f"{sign_prefix}{row.label} · {format_value_like_calculation_popup(row.unit, row.value)}",
                destination_name=outline_destination_name,
                level=outline_level,
                closed=True,
            ))
            children_ancestors = child_ancestor_step_labels(row, ancestor_step_labels)
            children = rows_of_step(row.linked_step, self.breakdowns, section.tile.result_key, row.path, children_ancestors)
            self.register_expanded_tree(children, section, children_ancestors, outline_level + 1)

    def register_steps_linked_from_step_blocks(self) -> None:
        """A step block links each operand to its own block: close the set over those links."""
        pending = list(self.reachable_step_by_object_id.values())
        while pending:
            reachable_step = pending.pop()
            for row in _rows_of_step_block(reachable_step, self.breakdowns):
                if row.linked_step is not None and id(row.linked_step) not in self.reachable_step_by_object_id:
                    pending.append(self.register_step(row.linked_step, reachable_step.section_key, reachable_step.result_indexes[0]))


def _rows_of_step_block(reachable_step: _ReachableStep, breakdowns: dict) -> list[CalculationBreakdownRow]:
    return rows_of_step(
        reachable_step.step, breakdowns, reachable_step.section_key, "", frozenset({reachable_step.step["label"]}),
    )


def _build_result_section(result_index: int, tile: ReportResultTile, result: dict, breakdowns: dict) -> _ReportResultSection:
    steps = breakdowns.get(tile.result_key) or []
    headline_step_index = find_headline_step_index(steps, result.get(tile.result_key))
    headline_step = steps[headline_step_index] if headline_step_index >= 0 else None
    return _ReportResultSection(
        result_index=result_index,
        tile=tile,
        steps=steps,
        headline_step_index=headline_step_index,
        headline_step=headline_step,
        top_level_rows=top_level_rows_for_headline(breakdowns, tile.result_key, headline_step_index),
        derived_rows=rows_of_steps(steps_after_headline(steps, headline_step_index), "derived"),
    )


# -- the popup's rows as a table -----------------------------------------------------------------
_ROW_INDENT_PER_DEPTH = 14
_TREE_COLUMN_WIDTHS = [5.45 * inch, 1.35 * inch]


class _TreeTableBuilder:
    """Rows of the popup's tree, flattened into a two-column table (label, value) with the
    depth as indentation, the "= total" lines ruled above, and formula / note lines spanning."""

    def __init__(self, styles: dict[str, ParagraphStyle], registry: _ReportLinkRegistry):
        self.styles = styles
        self.registry = registry
        self.cells: list[list[Any]] = []
        self.style_commands: list[tuple] = []

    def _indented(self, style_name: str, depth: int) -> ParagraphStyle:
        base_style = self.styles[style_name]
        return ParagraphStyle(f"{base_style.name}_depth{depth}", parent=base_style, leftIndent=depth * _ROW_INDENT_PER_DEPTH)

    def add_row(self, row: CalculationBreakdownRow, depth: int) -> None:
        sign_markup = f'<font name="Courier" color="#6B7280">{escape(row.sign) if row.sign else "&nbsp;"}</font>&nbsp;&nbsp;'
        if row.linked_step is not None:
            label_markup = _link(self.registry.step_destination_of(row.linked_step), f"<b>{escape(row.label)}</b> ›")
        else:
            label_markup = f'<font color="#6B7280">{escape(row.label)}</font>'
        self.cells.append([
            Paragraph(sign_markup + label_markup, self._indented("term", depth)),
            Paragraph(escape(format_value_like_calculation_popup(row.unit, row.value)), self.styles["row_value"]),
        ])

    def add_total(self, label: str, unit: Optional[str], value: Any, depth: int, is_headline: bool = False) -> None:
        row_index = len(self.cells)
        self.cells.append([
            Paragraph(f'<font name="Courier" color="#6B7280">=</font>&nbsp;&nbsp;<b>{escape(label)}</b>', self._indented("term", depth)),
            Paragraph(f"<b>{escape(format_value_like_calculation_popup(unit, value))}</b>", self.styles["row_value"]),
        ])
        self.style_commands.append(("LINEABOVE", (0, row_index), (-1, row_index), 1.5 if is_headline else 0.5,
                                    BRAND_BLUE if is_headline else BRAND_BORDER))

    def add_spanning(self, paragraph_markup: str, style_name: str, depth: int) -> None:
        row_index = len(self.cells)
        self.cells.append([Paragraph(paragraph_markup, self._indented(style_name, depth)), ""])
        self.style_commands.append(("SPAN", (0, row_index), (1, row_index)))

    def add_rows_expanding_first_level(
        self,
        rows: list[CalculationBreakdownRow],
        section: _ReportResultSection,
        ancestor_step_labels: frozenset[str],
    ) -> None:
        """The popup on arrival: every row, and under each expandable first-level row its own rows
        (ending on "= step") or its formula, then its note. Deeper rows stay collapsed: they link."""
        for row in rows:
            self.add_row(row, 0)
            if row.linked_step is None:
                continue
            children_ancestors = child_ancestor_step_labels(row, ancestor_step_labels)
            children = rows_of_step(row.linked_step, self.registry.breakdowns, section.tile.result_key, row.path, children_ancestors)
            if children:
                for child_row in children:
                    self.add_row(child_row, 1)
                self.add_total(row.linked_step["label"], row.linked_step.get("unit"), row.linked_step.get("value"), 1)
            else:
                self.add_spanning(escape(row.linked_step.get("formula", "")), "formula", 1)
            if row.linked_step.get("note"):
                self.add_spanning(escape(row.linked_step["note"]), "note", 1)

    def build(self) -> Table:
        table = Table(self.cells, colWidths=_TREE_COLUMN_WIDTHS)
        table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, BRAND_BORDER),
            ("BACKGROUND", (0, 0), (-1, -1), BRAND_PALE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            *self.style_commands,
        ]))
        return table


def _boxed(flowables: list[Any], border_color=BRAND_BLUE) -> Table:
    table = Table([[flowables]], colWidths=[sum(_TREE_COLUMN_WIDTHS)])
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.75, border_color),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF4FF")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


# -- the report's parts ----------------------------------------------------------------------------
def _results_summary_table(sections: list[_ReportResultSection], result: dict, styles) -> Table:
    rows: list[list[Any]] = [[
        Paragraph("<font color='white'><b>Result</b></font>", styles["body"]),
        Paragraph("<font color='white'><b>Value</b></font>", styles["row_value"]),
    ]]
    for section in sections:
        value_text = format_value_like_calculation_popup(section.tile.unit, result.get(section.tile.result_key))
        rows.append([
            Paragraph(_link(_result_destination(section.result_index), f"{escape(section.tile.tile_label)} ›"), styles["body"]),
            Paragraph(f"<b>{escape(value_text)}</b>", styles["row_value"]),
        ])
    table = Table(rows, colWidths=[4.6 * inch, 2.2 * inch], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND_PALE]),
        ("BOX", (0, 0), (-1, -1), 0.5, BRAND_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, BRAND_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _result_section_flowables(section: _ReportResultSection, registry: _ReportLinkRegistry, styles) -> list[Any]:
    """One result, laid out like its `CalculationBreakdownPopup`."""
    heading = [
        _NamedDestinationsFlowable([_result_destination(section.result_index)]),
        Paragraph(escape(section.title), styles["section_title"]),
    ]
    headline_step = section.headline_step
    if headline_step is None:
        return [KeepTogether(heading + [Paragraph(
            "No breakdown available for this result.", styles["note"],
        )])]

    headline_value_text = format_value_like_calculation_popup(headline_step.get("unit"), headline_step.get("value"))
    flow: list[Any] = heading + [Paragraph(escape(headline_value_text), styles["headline_value"])]
    headline_is_sum = is_sum_step(headline_step)

    if not headline_is_sum:
        # A headline that is not a sum: its formula first, then the section's steps as its inputs.
        box_contents: list[Any] = [Paragraph(escape(headline_step.get("formula", "")), styles["formula"])]
        if headline_step.get("note"):
            box_contents.append(Paragraph(escape(headline_step["note"]), styles["note"]))
        if section.top_level_rows:
            box_contents.append(Paragraph("BUILT FROM", styles["caption"]))
        flow.append(_boxed(box_contents))
        flow.append(Spacer(1, 4))

    if section.top_level_rows or headline_is_sum:
        tree = _TreeTableBuilder(styles, registry)
        tree.add_rows_expanding_first_level(section.top_level_rows, section, section.root_ancestor_step_labels)
        if headline_is_sum:
            tree.add_total(headline_step["label"], headline_step.get("unit"), headline_step.get("value"), 0, is_headline=True)
        flow.append(tree.build())
    if headline_is_sum and headline_step.get("note"):
        flow.append(Paragraph(escape(headline_step["note"]), styles["note"]))

    if section.derived_rows:
        flow.append(Paragraph("DERIVED FROM THIS", styles["caption"]))
        derived_tree = _TreeTableBuilder(styles, registry)
        derived_tree.add_rows_expanding_first_level(section.derived_rows, section, frozenset())
        flow.append(derived_tree.build())

    flow.append(Paragraph(
        _link(_all_steps_destination(section.result_index), f"All {len(section.steps)} steps in calculation order ›"),
        styles["link"],
    ))
    return flow


def _back_links_markup(result_indexes: list[int], sections_by_index: dict[int, _ReportResultSection]) -> str:
    return "← Back to " + " · ".join(
        _link(_result_destination(result_index), escape(sections_by_index[result_index].title))
        for result_index in result_indexes
    )


def _step_detail_flowables(reachable_step: _ReachableStep, registry: _ReportLinkRegistry,
                           sections_by_index: dict[int, _ReportResultSection], styles) -> list[Any]:
    """A computed step on its own, as the popup shows it once expanded: its operands (each linked
    further) and "= step", or its formula; then its note and the way back."""
    step = reachable_step.step
    value_text = format_value_like_calculation_popup(step.get("unit"), step.get("value"))
    flow: list[Any] = [
        _NamedDestinationsFlowable([_step_destination(reachable_step.step_index), *reachable_step.outline_destination_names]),
        Paragraph(f"{escape(step.get('label', ''))} · {escape(value_text)}", styles["h3"]),
    ]
    rows = _rows_of_step_block(reachable_step, registry.breakdowns)
    tree = _TreeTableBuilder(styles, registry)
    if rows:
        for row in rows:
            tree.add_row(row, 0)
        tree.add_total(step.get("label", ""), step.get("unit"), step.get("value"), 0, is_headline=True)
    else:
        tree.add_spanning(escape(step.get("formula", "")), "formula", 0)
    if step.get("note"):
        tree.add_spanning(escape(step["note"]), "note", 0)
    flow.append(tree.build())
    flow.append(Paragraph(_back_links_markup(reachable_step.result_indexes, sections_by_index), styles["link"]))
    return [KeepTogether(flow[:3]), *flow[3:]]


def _all_steps_flowables(section: _ReportResultSection, registry: _ReportLinkRegistry, styles) -> list[Any]:
    """The popup's collapsed "All N steps in calculation order" list, for one result."""
    flow: list[Any] = [
        _NamedDestinationsFlowable([_all_steps_destination(section.result_index)]),
        Paragraph(f"{escape(section.title)}: all {len(section.steps)} steps in calculation order", styles["h3"]),
    ]
    tree = _TreeTableBuilder(styles, registry)
    for step_number, step in enumerate(section.steps, start=1):
        label_markup = f"{step_number}. {escape(step.get('label', ''))}"
        if id(step) in registry.reachable_step_by_object_id:
            label_markup = _link(registry.step_destination_of(step), f"<b>{label_markup}</b> ›")
        else:
            label_markup = f"<b>{label_markup}</b>"
        row_index = len(tree.cells)
        tree.cells.append([
            Paragraph(label_markup, styles["term"]),
            Paragraph(f"<b>{escape(format_value_like_calculation_popup(step.get('unit'), step.get('value')))}</b>", styles["row_value"]),
        ])
        if row_index:
            tree.style_commands.append(("LINEABOVE", (0, row_index), (-1, row_index), 0.5, BRAND_BORDER))
        tree.add_spanning(escape(step.get("formula", "")), "formula", 1)
        if step.get("note"):
            tree.add_spanning(escape(step["note"]), "note", 1)
    if tree.cells:
        flow.append(tree.build())
    flow.append(Paragraph(_link(_result_destination(section.result_index), f"← Back to {escape(section.title)}"), styles["link"]))
    return [KeepTogether(flow[:3]), *flow[3:]]


def _header_block(address: str, deal_type: str, styles: dict[str, ParagraphStyle]) -> Table:
    badge_color = BRAND_BLUE if deal_type == "BRRRR" else BRAND_AMBER
    badge = Table(
        [[Paragraph(deal_type, styles["badge"])]],
        colWidths=[0.9 * inch],
    )
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), badge_color),
        ("BOX", (0, 0), (-1, -1), 0.5, badge_color),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    # The address is user text and Paragraph speaks a mini-HTML: escape it.
    title = Paragraph(f"<b>{escape(address or 'Property')}</b>", styles["title"])
    sub = Paragraph(
        f"Deal Report &middot; Generated {datetime.now().strftime('%b %d, %Y')}",
        styles["subtitle"],
    )
    block = Table(
        [[title, badge], [sub, ""]],
        colWidths=[5.3 * inch, 1.4 * inch],
    )
    block.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("SPAN", (0, 1), (1, 1)),
        ("LINEBELOW", (0, 1), (-1, 1), 2, badge_color),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
    ]))
    return block


def _draw_branding(canvas, doc):
    """Persistent footer drawn on every page."""
    canvas.saveState()
    width, _ = LETTER
    # Left: Big Whales signature.
    canvas.setFont("Helvetica-Bold", 11)
    canvas.setFillColor(BRAND_NAVY)
    canvas.drawString(0.6 * inch, 0.55 * inch, "Big Whales AY LLC")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(BRAND_MUTED)
    canvas.drawString(
        0.6 * inch, 0.4 * inch,
        "Real-estate analytics by big whales \u2022 BigWhalesLLC@gmail.com",
    )
    # Right: page number.
    canvas.drawRightString(
        width - 0.6 * inch, 0.4 * inch, f"Page {doc.page}",
    )
    # Disclaimer line above footer.
    canvas.setFont("Helvetica-Oblique", 7)
    canvas.drawCentredString(
        width / 2.0, 0.78 * inch,
        "Disclaimer: This report is generated for informational purposes only and does not constitute "
        "financial, tax, or legal advice. Verify all figures with a licensed professional before transacting.",
    )
    # Top accent stripe.
    canvas.setFillColor(BRAND_NAVY)
    canvas.rect(0, LETTER[1] - 0.18 * inch, width, 0.18 * inch, fill=1, stroke=0)
    canvas.setFillColor(BRAND_AMBER)
    canvas.rect(0, LETTER[1] - 0.22 * inch, width, 0.04 * inch, fill=1, stroke=0)
    canvas.restoreState()



def build_deal_pdf(
    address: str,
    deal_type: str,
    result: dict,
    selected_result_keys: list[str] | None = None,
) -> bytes:
    """Render the Big Whales branded deal report PDF and return its bytes.

    `result` is the calculator output as a dict (`analyzeBRRRRes` / `analyzeFlipRes` model_dump),
    carrying `breakdowns`. `selected_result_keys` picks the result tiles to include (None = every
    tile); `select_report_result_tiles` rejects unknown keys and an empty list.
    """
    deal_type = (deal_type or "BRRRR").upper()
    breakdowns = result.get("breakdowns") or {}
    tiles = select_report_result_tiles(deal_type, selected_result_keys)

    styles = _styles()
    registry = _ReportLinkRegistry(breakdowns)
    sections = [_build_result_section(index, tile, result, breakdowns) for index, tile in enumerate(tiles)]
    sections_by_index = {section.result_index: section for section in sections}

    # Number the steps and lay out the outline in reading order: each result, then its expanded tree.
    for section in sections:
        headline_value_text = format_value_like_calculation_popup(section.tile.unit, result.get(section.tile.result_key))
        registry.outline_entries.append(_OutlineEntry(
            f"{section.title} · {headline_value_text}", _result_destination(section.result_index), 0, False,
        ))
        registry.register_expanded_tree(section.top_level_rows, section, section.root_ancestor_step_labels, 1)
        registry.register_expanded_tree(section.derived_rows, section, frozenset(), 1)
    registry.register_steps_linked_from_step_blocks()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.55 * inch, bottomMargin=0.95 * inch,
        title=f"Big Whales Deal Report - {address or 'Property'}",
        author="Big Whales AY LLC",
    )

    flow: list[Any] = [_header_block(address, deal_type, styles), Spacer(1, 0.1 * inch)]
    flow.append(Paragraph("Results in this report", styles["h2"]))
    flow.append(_results_summary_table(sections, result, styles))
    flow.append(Paragraph(
        "Each result below reads like its breakdown popup on the website: the answer first, with the "
        "first level opened. A blue label is a calculated step: click it to see how that step is "
        "calculated. The bookmarks panel holds every result's full tree.",
        styles["note"],
    ))

    for section in sections:
        flow.extend(_result_section_flowables(section, registry, styles))

    reachable_steps = sorted(registry.reachable_step_by_object_id.values(), key=lambda reachable: reachable.step_index)
    if reachable_steps:
        flow.append(Paragraph("Step details", styles["h2"]))
        for reachable_step in reachable_steps:
            flow.extend(_step_detail_flowables(reachable_step, registry, sections_by_index, styles))

    flow.append(Paragraph("All steps in calculation order", styles["h2"]))
    for section in sections:
        flow.extend(_all_steps_flowables(section, registry, styles))

    flow.append(Spacer(1, 0.1 * inch))
    flow.append(Paragraph(
        "Money is in dollars, percentages as shown, ratios as a multiple (1.20x). "
        "\"∞\" and \"-∞\" mean the divisor was zero. A note under a step explains a convention.",
        styles["note"],
    ))

    def draw_first_page(canvas, document):
        _draw_branding(canvas, document)
        for outline_entry in registry.outline_entries:
            canvas.addOutlineEntry(outline_entry.title, outline_entry.destination_name,
                                   level=outline_entry.level, closed=outline_entry.closed)
        canvas.showOutline()

    doc.build(flow, onFirstPage=draw_first_page, onLaterPages=_draw_branding)
    return buf.getvalue()
