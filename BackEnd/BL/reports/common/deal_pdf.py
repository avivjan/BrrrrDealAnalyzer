"""Big Whales branded PDF deal report generator.

Renders a one-shot, professional report with:
  1. Property header (address + deal type badge)
  2. High-level results summary table
  3. "Calculation Breakdown" - the CalcSteps the explain layer
     (`BL/analyze/explain/`) derives from the calculation, grouped per metric:
     sum-type steps are stacked one operand per line, every value is formatted
     by the unit the step carries, notes appear under the formula.
  4. Branded footer + disclaimer on every page.

The renderer is intentionally tolerant of unknown shapes: it accepts a plain
dict for `result` (so callers can pass either a Pydantic model dump or a raw
dict, including DB-backed deal rows merged with calc output).
"""

from __future__ import annotations

import io
from datetime import datetime
from xml.sax.saxutils import escape
from typing import Any, Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from BL.analyze.explain.brrr import BRRR_SECTIONS
from BL.analyze.explain.flip import FLIP_SECTIONS


# Big Whales brand palette.
BRAND_NAVY = colors.HexColor("#0B1F3A")
BRAND_BLUE = colors.HexColor("#2563EB")
BRAND_AMBER = colors.HexColor("#F59E0B")
BRAND_INK = colors.HexColor("#111827")
BRAND_MUTED = colors.HexColor("#6B7280")
BRAND_PALE = colors.HexColor("#F3F4F6")
BRAND_BORDER = colors.HexColor("#E5E7EB")


def _money(v: Any) -> str:
    if v is None:
        return "-"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "-"
    if f == -1:
        return "∞"
    if f == -2:
        return "-∞"
    sign = "-" if f < 0 else ""
    return f"{sign}${abs(f):,.2f}" if f != int(f) else f"{sign}${int(abs(f)):,}"


def _pct(v: Any, decimals: int = 2) -> str:
    if v is None:
        return "-"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "-"
    if f == -1:
        return "∞"
    if f == -2:
        return "-∞"
    return f"{f:.{decimals}f}%"


def _ratio(v: Any, decimals: int = 2) -> str:
    if v is None:
        return "-"
    try:
        return f"{float(v):.{decimals}f}x"
    except (TypeError, ValueError):
        return "-"


# How a value reads, by the `unit` the explain layer stamps on every step and
# section: dollars, a percentage, or a plain multiple (DSCR).
_FORMAT = {"money": _money, "pct": _pct, "ratio": _ratio}


def _fmt(unit: str, v: Any) -> str:
    return _FORMAT.get(unit, _money)(v)


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
        "badge": ParagraphStyle(
            "BWBadge", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=9,
            textColor=colors.white, alignment=TA_CENTER,
        ),
    }


# The headline metrics come from the explain layer, one list per deal type:
# (result field, label, unit). The same list drives the summary table at the
# top of the report and the order of the breakdown sections below it.
def _sections(deal_type: str) -> list[tuple[str, str, str]]:
    return BRRR_SECTIONS if deal_type == "BRRRR" else FLIP_SECTIONS


def _summary_rows(result: dict, deal_type: str) -> list[list[str]]:
    rows = [["Metric", "Value"]]
    for key, label, unit in _sections(deal_type):
        if key in result and result.get(key) is not None:
            rows.append([label, _fmt(unit, result[key])])
    return rows


def _formula_cell(step: dict, styles: dict[str, ParagraphStyle]) -> list[Any]:
    """The middle column of a breakdown row.

    A sum-type step (one carrying `terms`) is stacked one operand per line with
    its sign in front and the total on a final bold line, instead of a single
    wrapped sentence. Any other step shows its `formula` text. A `note`, when
    present, follows in small muted type.
    """
    cell: list[Any] = []
    terms = step.get("terms") or []
    if terms:
        for i, term in enumerate(terms):
            sign = "" if i == 0 else ("+ " if term.get("sign", "+") == "+" else "\u2212 ")
            cell.append(Paragraph(
                f"{sign}{term.get('label', '')} <font color='#6B7280'>{_money(term.get('value'))}</font>",
                styles["term"],
            ))
        cell.append(Paragraph(f"= <b>{_fmt(step.get('unit', 'money'), step.get('value'))}</b>", styles["term"]))
    else:
        cell.append(Paragraph(step.get("formula", ""), styles["body"]))
    if step.get("note"):
        cell.append(Paragraph(step["note"], styles["note"]))
    return cell


def _breakdown_table(steps: Iterable[dict], styles: dict[str, ParagraphStyle]) -> Table:
    # Header cells are Paragraphs, which ignore the table's TEXTCOLOR, so the
    # white is set inline.
    rows: list[list[Any]] = [[
        Paragraph("<font color='white'><b>Step</b></font>", styles["body"]),
        Paragraph("<font color='white'><b>Formula</b></font>", styles["body"]),
        Paragraph("<font color='white'><b>Value</b></font>", styles["body"]),
    ]]
    for step in steps:
        rows.append([
            Paragraph(step.get("label", ""), styles["body"]),
            _formula_cell(step, styles),
            Paragraph(f"<b>{_fmt(step.get('unit', 'money'), step.get('value'))}</b>", styles["body"]),
        ])
    table = Table(rows, colWidths=[1.6 * inch, 4.0 * inch, 1.1 * inch], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND_PALE]),
        ("BOX", (0, 0), (-1, -1), 0.5, BRAND_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, BRAND_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _summary_table(rows: list[list[str]]) -> Table:
    table = Table(rows, colWidths=[3.0 * inch, 3.7 * inch], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND_PALE]),
        ("BOX", (0, 0), (-1, -1), 0.5, BRAND_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, BRAND_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (1, 1), (1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (1, 1), (1, -1), BRAND_INK),
    ]))
    return table


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
    breakdowns: dict | None = None,
) -> bytes:
    """Render a Big Whales branded deal report PDF and return raw bytes.

    `result` should be a flat dict of the calculator output (e.g. the
    `analyzeBRRRRes` / `analyzeFlipRes` model_dump). `breakdowns` is the
    `breakdowns` dict from the same response; when omitted we look it up on
    `result["breakdowns"]`.
    """
    deal_type = (deal_type or "BRRRR").upper()
    if breakdowns is None:
        breakdowns = result.get("breakdowns") or {}

    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.55 * inch, bottomMargin=0.95 * inch,
        title=f"Big Whales Deal Report - {address or 'Property'}",
        author="Big Whales AY LLC",
    )

    flow: list[Any] = []
    flow.append(_header_block(address, deal_type, styles))
    flow.append(Spacer(1, 0.1 * inch))

    flow.append(Paragraph("Results Summary", styles["h2"]))
    flow.append(_summary_table(_summary_rows(result, deal_type)))

    flow.append(Spacer(1, 0.15 * inch))
    flow.append(Paragraph("Calculation Breakdown", styles["h2"]))
    flow.append(Paragraph(
        "Each section walks through the exact intermediate steps the calculator used "
        "to derive a headline metric, with the formula and concrete values plugged in.",
        styles["body"],
    ))

    for key, label, unit in _sections(deal_type):
        steps = breakdowns.get(key)
        if not steps:
            continue
        headline = f" &middot; {_fmt(unit, result[key])}" if result.get(key) is not None else ""
        flow.append(Paragraph(f"{label}{headline}", styles["h3"]))
        flow.append(_breakdown_table(steps, styles))
        flow.append(Spacer(1, 0.1 * inch))

    doc.build(flow, onFirstPage=_draw_branding, onLaterPages=_draw_branding)
    return buf.getvalue()
