"""Big Whales branded PDF report generator.

Renders a single deal's analysis (BRRRR or Flip) into a high-contrast,
print-friendly PDF using reportlab's Platypus flowables. Layout is data-driven
off the same `analyzeBRRRRes` / `analyzeFlipRes` results the API already
returns – `breakdown_steps` carries every intermediate value so the report is
always in sync with the live calculator.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Iterable, List, Optional, Sequence, Tuple, Union

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from ReqRes.analyzeBRRR.analyzeBRRRRes import analyzeBRRRRes
from ReqRes.analyzeFlip.analyzeFlipRes import analyzeFlipRes
from ReqRes.calcStep import CalcStep


# Brand palette – kept in one place so future logo/skin tweaks are easy.
BRAND_NAVY = colors.HexColor("#0E2A47")
BRAND_BLUE = colors.HexColor("#1E73BE")
BRAND_ACCENT = colors.HexColor("#0FA968")
BRAND_GRAY = colors.HexColor("#444444")
BRAND_LIGHT = colors.HexColor("#F4F6F8")
BRAND_BORDER = colors.HexColor("#D9DDE2")


def _money(v) -> str:
    try:
        return f"${float(v):,.0f}"
    except Exception:
        return "$0"


def _pct(v) -> str:
    try:
        return f"{float(v):.2f}%"
    except Exception:
        return "0.00%"


def _styles():
    """Build the named ParagraphStyle set used throughout the report."""
    base = getSampleStyleSheet()["Normal"]
    return {
        "title": ParagraphStyle(
            "title",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=BRAND_NAVY,
            leading=26,
            alignment=TA_LEFT,
        ),
        "brand": ParagraphStyle(
            "brand",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=BRAND_BLUE,
            leading=12,
            alignment=TA_RIGHT,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=BRAND_NAVY,
            leading=16,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base,
            fontName="Helvetica",
            fontSize=10,
            textColor=BRAND_GRAY,
            leading=13,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base,
            fontName="Helvetica",
            fontSize=8.5,
            textColor=BRAND_GRAY,
            leading=11,
        ),
        "formula": ParagraphStyle(
            "formula",
            parent=base,
            fontName="Helvetica",
            fontSize=9,
            textColor=BRAND_GRAY,
            leading=12,
        ),
        "formula_label": ParagraphStyle(
            "formula_label",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=9.5,
            textColor=BRAND_NAVY,
            leading=12,
        ),
        "disclaimer": ParagraphStyle(
            "disclaimer",
            parent=base,
            fontName="Helvetica-Oblique",
            fontSize=7.5,
            textColor=colors.HexColor("#666666"),
            leading=10,
            alignment=TA_CENTER,
        ),
    }


def _summary_table(rows: Sequence[Tuple[str, str]], styles) -> Table:
    """Two-column key/value table for the high-level summary section."""
    data = [[Paragraph(label, styles["body"]), Paragraph(f"<b>{value}</b>", styles["body"])] for label, value in rows]
    tbl = Table(data, colWidths=[2.6 * inch, 3.4 * inch], hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, BRAND_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, BRAND_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


def _breakdown_table(steps: Iterable[CalcStep], styles) -> Table:
    """Three-column step table rendering label / value / formula per row."""
    header = [
        Paragraph("<b>Metric</b>", styles["formula_label"]),
        Paragraph("<b>Value</b>", styles["formula_label"]),
        Paragraph("<b>Formula</b>", styles["formula_label"]),
    ]
    body: List[List] = [header]
    for step in steps:
        # Format value: currency for $ amounts, % for ROI/CoC etc.
        value_str = _format_step_value(step)
        body.append([
            Paragraph(step.label, styles["formula"]),
            Paragraph(f"<b>{value_str}</b>", styles["formula"]),
            Paragraph(step.formula, styles["formula"]),
        ])

    tbl = Table(body, colWidths=[1.8 * inch, 1.2 * inch, 4.0 * inch], hAlign="LEFT", repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
        ("BOX", (0, 0), (-1, -1), 0.5, BRAND_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, BRAND_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return tbl


# Step keys whose `value` field is a percentage (not dollars). Anything not
# listed here is treated as a dollar amount.
_PERCENT_KEYS = {"roi", "annualized_roi", "cash_on_cash"}


def _format_step_value(step: CalcStep) -> str:
    """Render a step's value as money or percent depending on its key.

    DSCR is special-cased (unitless ratio); ``-1``/``-2`` sentinels from the
    BRRRR analyzer denote infinite/undefined returns and are surfaced as such.
    """
    if step.key == "dscr":
        return f"{step.value:.2f}"
    if step.key in _PERCENT_KEYS:
        if step.value == -1:
            return "∞"
        if step.value == -2:
            return "−∞"
        return _pct(step.value)
    return _money(step.value)


def _header_block(address: str, deal_type: str, styles) -> Table:
    """Top banner: bold address + deal type pill on the left, brand on right."""
    deal_label = "BRRRR Investment Analysis" if deal_type == "BRRRR" else "Flip Investment Analysis"
    left = [
        Paragraph(address or "Unnamed Property", styles["title"]),
        Paragraph(deal_label, styles["body"]),
        Paragraph(f"Generated {datetime.utcnow().strftime('%B %d, %Y')}", styles["small"]),
    ]
    right = [
        Paragraph("BIG WHALES", styles["brand"]),
        Paragraph("Real Estate Investment Group", styles["small"]),
    ]
    tbl = Table([[left, right]], colWidths=[5.0 * inch, 2.0 * inch], hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 2, BRAND_BLUE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    return tbl


def _on_page(canvas, doc):
    """Footer with brand signature + disclaimer + page number on every page."""
    canvas.saveState()

    # Footer separator
    canvas.setStrokeColor(BRAND_BLUE)
    canvas.setLineWidth(1.5)
    footer_y = 0.75 * inch
    canvas.line(0.6 * inch, footer_y, LETTER[0] - 0.6 * inch, footer_y)

    # Brand line
    canvas.setFont("Helvetica-Bold", 10)
    canvas.setFillColor(BRAND_NAVY)
    canvas.drawString(0.6 * inch, footer_y - 14, "Big Whales AY LLC")
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(BRAND_GRAY)
    canvas.drawString(0.6 * inch, footer_y - 26, "Real Estate Investment & Analysis  |  BigWhalesLLC@gmail.com")

    # Disclaimer
    canvas.setFont("Helvetica-Oblique", 7)
    canvas.setFillColor(colors.HexColor("#666666"))
    disclaimer = (
        "This report is generated for informational purposes only and is not financial, tax, or legal advice. "
        "Figures are projections based on user-supplied inputs and may differ from actual results. "
        "Verify all numbers independently before transacting."
    )
    canvas.drawString(0.6 * inch, footer_y - 40, disclaimer[:140])
    canvas.drawString(0.6 * inch, footer_y - 50, disclaimer[140:])

    # Page number
    page_num = canvas.getPageNumber()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(BRAND_GRAY)
    canvas.drawRightString(LETTER[0] - 0.6 * inch, footer_y - 14, f"Page {page_num}")

    canvas.restoreState()


def _build_doc(buffer: io.BytesIO) -> BaseDocTemplate:
    doc = BaseDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        # Reserve room for the footer block (~1 inch).
        bottomMargin=1.05 * inch,
        title="Big Whales Deal Report",
        author="Big Whales AY LLC",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="content")
    template = PageTemplate(id="branded", frames=[frame], onPage=_on_page)
    doc.addPageTemplates([template])
    return doc


def _brrr_summary_rows(payload, result: analyzeBRRRRes) -> List[Tuple[str, str]]:
    rent = float(getattr(payload, "rent", 0) or 0)
    arv_k = float(getattr(payload, "arv_in_thousands", 0) or 0)
    purchase_k = float(getattr(payload, "purchase_price_in_thousands", 0) or 0)
    rehab_k = float(getattr(payload, "rehab_cost_in_thousands", 0) or 0)
    ltv = float(getattr(payload, "ltv_as_precent", 0) or 0)
    return [
        ("Purchase Price", _money(purchase_k * 1000)),
        ("Rehab Cost (base)", _money(rehab_k * 1000)),
        ("ARV", _money(arv_k * 1000)),
        ("Refi LTV", _pct(ltv)),
        ("Monthly Rent", _money(rent)),
        ("Monthly Cash Flow", _money(result.cash_flow)),
        ("DSCR", f"{(result.dscr or 0):.2f}"),
        ("Cash Out", _money(result.cash_out)),
        ("Cash on Cash", _format_pct_with_sentinel(result.cash_on_cash)),
        ("ROI", _format_pct_with_sentinel(result.roi)),
        ("Equity After Refi", _money(result.equity)),
        ("Net Profit", _money(result.net_profit)),
        ("Total Cash Needed", _money(result.total_cash_needed_for_deal)),
        ("Total Cash Needed (w/ Buffer)", _money(result.total_cash_needed_for_deal_with_buffer)),
    ]


def _flip_summary_rows(payload, result: analyzeFlipRes) -> List[Tuple[str, str]]:
    sale_k = float(getattr(payload, "sale_price_in_thousands", 0) or 0)
    purchase_k = float(getattr(payload, "purchase_price_in_thousands", 0) or 0)
    rehab_k = float(getattr(payload, "rehab_cost_in_thousands", 0) or 0)
    holding_months = int(getattr(payload, "holding_time_months", 0) or 0)
    return [
        ("Purchase Price", _money(purchase_k * 1000)),
        ("Rehab Cost (base)", _money(rehab_k * 1000)),
        ("Projected Sale Price (ARV)", _money(sale_k * 1000)),
        ("Holding Time", f"{holding_months} months"),
        ("Total Holding Costs", _money(result.total_holding_costs)),
        ("Total HML Interest", _money(result.total_hml_interest)),
        ("Net Profit", _money(result.net_profit)),
        ("ROI", _pct(result.roi)),
        ("Annualized ROI", _pct(result.annualized_roi)),
        ("Total Cash Needed", _money(result.total_cash_needed)),
        ("Total Cash Needed (w/ Buffer)", _money(result.total_cash_needed_with_buffer)),
    ]


def _format_pct_with_sentinel(v: Optional[float]) -> str:
    """Translate the BRRRR analyzer's -1/-2 sentinels to ∞/−∞ for the PDF."""
    if v is None:
        return "-"
    if v == -1:
        return "∞"
    if v == -2:
        return "−∞"
    return _pct(v)


def build_deal_report_pdf(
    *,
    deal_type: str,
    address: Optional[str],
    payload,
    result: Union[analyzeBRRRRes, analyzeFlipRes],
) -> bytes:
    """Render a deal-analysis PDF and return its bytes.

    The caller is responsible for running the analyzer; this function only
    formats the inputs/results into a document. `result.breakdown_steps` is
    expected to be populated for the most useful report (the Calculation
    Breakdown section degrades gracefully if it's empty).
    """
    buf = io.BytesIO()
    doc = _build_doc(buf)
    styles = _styles()

    story = []
    story.append(_header_block(address or "Unnamed Property", deal_type, styles))
    story.append(Spacer(1, 0.2 * inch))

    # --- High-level summary ---
    story.append(Paragraph("Summary", styles["h2"]))
    if deal_type == "BRRRR":
        rows = _brrr_summary_rows(payload, result)  # type: ignore[arg-type]
    else:
        rows = _flip_summary_rows(payload, result)  # type: ignore[arg-type]
    story.append(_summary_table(rows, styles))
    story.append(Spacer(1, 0.25 * inch))

    # --- Calculation breakdown ---
    story.append(Paragraph("Calculation Breakdown", styles["h2"]))
    story.append(Paragraph(
        "Each row shows the intermediate value used by the calculator and the formula that produced it. "
        "All math is identical to the live analyzer.",
        styles["body"],
    ))
    story.append(Spacer(1, 0.08 * inch))
    steps = result.breakdown_steps or []
    if steps:
        story.append(_breakdown_table(steps, styles))
    else:
        story.append(Paragraph("No breakdown steps were captured.", styles["small"]))

    doc.build(story)
    return buf.getvalue()
