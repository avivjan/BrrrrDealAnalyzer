"""The statement PDF: six short sections anyone can follow (tasks/todo/MemberLoan.md).

1. Summary box  2. What happened this month  3. How the interest was calculated
4. How the total debt was calculated  5. How the calculation works
6. Warnings, the binding sentence, engine version and ledger fingerprint.

Built from the document's plain dict (`MemberLoanStatementDocument.as_plain_dict()`),
the same dict stored when a statement is sent, so a sent statement can be
re-rendered exactly. Every string is escaped before it reaches ReportLab's
Paragraph markup.
"""

from __future__ import annotations

import io
from typing import Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

INK = colors.HexColor("#111827")
NAVY = colors.HexColor("#0B1F3A")
MUTED = colors.HexColor("#6B7280")
PALE = colors.HexColor("#F3F4F6")
BORDER = colors.HexColor("#E5E7EB")
WARNING_INK = colors.HexColor("#9A3412")
WARNING_PALE = colors.HexColor("#FFF7ED")

TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=NAVY, spaceAfter=2)
SUBTITLE = ParagraphStyle("subtitle", fontName="Helvetica", fontSize=10, leading=14, textColor=MUTED, spaceAfter=12)
HEADING = ParagraphStyle("heading", fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=NAVY, spaceBefore=14, spaceAfter=6)
BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=14.5, textColor=INK, spaceAfter=5)
EQUATION = ParagraphStyle("equation", fontName="Helvetica", fontSize=10, leading=15, textColor=INK, leftIndent=8, spaceAfter=2)
EQUATION_TOTAL = ParagraphStyle("equation_total", parent=EQUATION, fontName="Helvetica-Bold")
SMALL = ParagraphStyle("small", fontName="Helvetica", fontSize=8.5, leading=12, textColor=MUTED, spaceAfter=3)
WARNING = ParagraphStyle("warning", fontName="Helvetica-Bold", fontSize=10, leading=14, textColor=WARNING_INK)


def _paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def _boxed(flowables: list, background, border) -> Table:
    box = Table([[flowables]], colWidths=[7.0 * inch])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("BOX", (0, 0), (-1, -1), 0.75, border),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return box


def render_member_loan_statement_pdf(document: dict, *, sent_line: Optional[str] = None) -> bytes:
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(
        buffer, pagesize=LETTER, leftMargin=0.75 * inch, rightMargin=0.75 * inch, topMargin=0.7 * inch, bottomMargin=0.7 * inch,
        title=document["title"], author="Big Whales AY LLC", subject="Member Loan statement",
    )
    story: list = [
        _paragraph(document["title"], TITLE),
        _paragraph(
            f"Big Whales AY LLC (Borrower) and Aviv Jan (Lender). Statement date: {document['statement_date']}. "
            "All amounts in US dollars.",
            SUBTITLE,
        ),
    ]

    summary = Table(
        [[_paragraph(label, BODY), _paragraph(value, ParagraphStyle("right", parent=BODY, alignment=2, fontName="Helvetica-Bold"))]
         for label, value in document["summary_rows"]],
        colWidths=[4.8 * inch, 2.2 * inch],
    )
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.75, BORDER),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [_paragraph("1. Summary", HEADING), summary]

    story.append(_paragraph("2. What happened this month", HEADING))
    story += [_paragraph(sentence, BODY) for sentence in document["what_happened_sentences"]]

    story.append(_paragraph("3. How the interest was calculated", HEADING))
    story.append(_paragraph("The month is split into stretches of days between changes. Each stretch: balance × rate × days/30.", BODY))
    story += [_paragraph(line, EQUATION) for line in document["interest_period_lines"]]
    totals = document["interest_total_lines"]
    story += [_paragraph(line, EQUATION_TOTAL if i == len(totals) - 1 else EQUATION) for i, line in enumerate(totals)]

    story.append(_paragraph("4. How the total debt was calculated", HEADING))
    debt_lines = document["debt_equation_lines"]
    story += [_paragraph(line, EQUATION_TOTAL if line.startswith("=") else EQUATION) for line in debt_lines]
    story.append(Spacer(1, 4))
    owed = document["amount_owed_lines"]
    story.append(_paragraph(owed[0], EQUATION_TOTAL))
    story += [_paragraph(line, EQUATION) for line in owed[1:]]

    how = [_paragraph("5. How the calculation works", ParagraphStyle("box_heading", parent=HEADING, spaceBefore=0))]
    how += [_paragraph(f"• {line}", BODY) for line in document["how_it_works_lines"]]
    story += [Spacer(1, 10), _boxed(how, PALE, BORDER)]

    footer: list = []
    if document["warnings"]:
        footer.append(_boxed([_paragraph(w, WARNING) for w in document["warnings"]], WARNING_PALE, WARNING_INK))
        footer.append(Spacer(1, 8))
    footer.append(_paragraph(document["binding_sentence"], ParagraphStyle("binding", parent=BODY, fontName="Helvetica-Bold")))
    if sent_line:
        footer.append(_paragraph(sent_line, SMALL))
    footer.append(_paragraph(f"Engine version {document['engine_version']}. Ledger fingerprint: {document['ledger_fingerprint']}", SMALL))
    story += [_paragraph("6. Notes", HEADING), KeepTogether(footer)]

    def _page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(LETTER[0] - 0.75 * inch, 0.45 * inch, f"Page {doc.page}")
        canvas.restoreState()

    pdf.build(story, onFirstPage=_page_number, onLaterPages=_page_number)
    return buffer.getvalue()
