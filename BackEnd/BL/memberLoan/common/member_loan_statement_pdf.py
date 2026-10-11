"""The statement PDF: a designed, six-section page anyone can follow.

Layout (tasks/todo/MemberLoan.md, Statement PDF):
  header band  company, "Monthly Statement", the month, statement date, parties
  hero         Amount Owed in large type, beside four small figures
  1. Summary   (the hero above is section 1)
  2. What happened this month   one row per change, with a date chip
  3. How the interest was calculated   a table: period, balance × rate × days/30 = interest
  4. How the total debt was calculated   a ledger: opening, each change, interest, closing
  5. How the calculation works   a shaded box of short bullets
  6. Notes     warnings, the binding sentence, sent line, engine version, fingerprint

Built from the document's plain dict (`MemberLoanStatementDocument.as_plain_dict()`),
the same dict stored when a statement is sent, so a sent statement re-renders
exactly. The lines are produced by `member_loan_statement_document.py` in fixed
formats; this module only lays them out (a line in an unexpected format is
printed as plain text, never dropped). Table cells are written left to right,
so the text read back from the PDF still spells each equation in order, and
`tests/test_member_loan_statement.py` checks every one of them adds up.
Every string is escaped before it reaches ReportLab's Paragraph markup.
"""

from __future__ import annotations

import io
import re
from datetime import date
from typing import Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# -- palette --------------------------------------------------------------------
NAVY = colors.HexColor("#0B1F3A")
NAVY_SOFT = colors.HexColor("#1E3A5F")
ACCENT = colors.HexColor("#2563EB")
ACCENT_PALE = colors.HexColor("#EEF4FF")
SKY = colors.HexColor("#BFD3F2")
INK = colors.HexColor("#111827")
BODY_INK = colors.HexColor("#374151")
MUTED = colors.HexColor("#6B7280")
HAIRLINE = colors.HexColor("#E5E7EB")
PANEL = colors.HexColor("#F7F8FA")
POSITIVE = colors.HexColor("#047857")
NEGATIVE = colors.HexColor("#B91C1C")
WARNING_INK = colors.HexColor("#9A3412")
WARNING_PALE = colors.HexColor("#FFF7ED")
WARNING_EDGE = colors.HexColor("#FDBA74")
WHITE = colors.white

PAGE_WIDTH, PAGE_HEIGHT = LETTER
SIDE_MARGIN = 0.6 * inch
CONTENT_WIDTH = PAGE_WIDTH - 2 * SIDE_MARGIN
HEADER_BAND_HEIGHT = 1.35 * inch

# -- type -----------------------------------------------------------------------
SECTION_TITLE = ParagraphStyle("section_title", fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=NAVY)
BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=9.6, leading=14, textColor=BODY_INK)
BODY_STRONG = ParagraphStyle("body_strong", parent=BODY, fontName="Helvetica-Bold", textColor=INK)
CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=9.4, leading=12.5, textColor=BODY_INK)
CELL_STRONG = ParagraphStyle("cell_strong", parent=CELL, fontName="Helvetica-Bold", textColor=INK)
CELL_RIGHT = ParagraphStyle("cell_right", parent=CELL, alignment=TA_RIGHT)
CELL_RIGHT_STRONG = ParagraphStyle("cell_right_strong", parent=CELL_RIGHT, fontName="Helvetica-Bold", textColor=INK)
CELL_MUTED = ParagraphStyle("cell_muted", parent=CELL, textColor=MUTED)
CELL_HEADER = ParagraphStyle("cell_header", parent=CELL, fontName="Helvetica-Bold", fontSize=7.8, leading=10, textColor=MUTED)
CELL_HEADER_RIGHT = ParagraphStyle("cell_header_right", parent=CELL_HEADER, alignment=TA_RIGHT)
NOTE = ParagraphStyle("note", fontName="Helvetica-Oblique", fontSize=8.2, leading=11, textColor=MUTED)
CHIP = ParagraphStyle("chip", fontName="Helvetica-Bold", fontSize=8.6, leading=11, textColor=ACCENT, alignment=TA_LEFT)
HERO_LABEL = ParagraphStyle("hero_label", fontName="Helvetica-Bold", fontSize=8.4, leading=11, textColor=SKY)
HERO_VALUE = ParagraphStyle("hero_value", fontName="Helvetica-Bold", fontSize=26, leading=30, textColor=WHITE)
HERO_CAPTION = ParagraphStyle("hero_caption", fontName="Helvetica", fontSize=8.4, leading=11.5, textColor=SKY)
STAT_LABEL = ParagraphStyle("stat_label", fontName="Helvetica", fontSize=8.2, leading=10.5, textColor=MUTED)
STAT_VALUE = ParagraphStyle("stat_value", fontName="Helvetica-Bold", fontSize=13.5, leading=17, textColor=INK)
BULLET = ParagraphStyle("bullet", fontName="Helvetica", fontSize=9.2, leading=13.2, textColor=BODY_INK, leftIndent=11, bulletIndent=0)
WARNING = ParagraphStyle("warning", fontName="Helvetica-Bold", fontSize=9.4, leading=13.5, textColor=WARNING_INK)
BINDING = ParagraphStyle("binding", fontName="Helvetica-Bold", fontSize=9.8, leading=14, textColor=INK)
FINE_PRINT = ParagraphStyle("fine_print", fontName="Helvetica", fontSize=7.6, leading=10.5, textColor=MUTED)

# -- the line formats written by member_loan_statement_document.py ------------
MONEY = r"-?\$[\d,]+\.\d{2}"
PERIOD_LINE = re.compile(
    rf"^(?P<range>.+?): (?P<balance>{MONEY}) × (?P<rate>[\d.]+%) × (?P<days>\d+)/30 = (?P<interest>{MONEY})(?: \((?P<note>.+)\))?$"
)
DEBT_STEP_LINE = re.compile(rf"^(?P<sign>[+=\-]) (?P<amount>{MONEY}) (?P<label>.+)$")
LABEL_AND_EXPRESSION = re.compile(r"^(?P<label>[^:]+): (?P<expression>.+)$")
DATED_SENTENCE = re.compile(r"^(?P<when>[A-Z][a-z]{2} \d{1,2}) – (?P<sentence>.+)$")
PARENTHETICAL_TAIL = re.compile(r"^(?P<label>.+?) \((?P<note>[^()]+)\)$")


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def _long_date(iso_date: str) -> str:
    calendar_date = date.fromisoformat(iso_date)
    return f"{calendar_date:%b} {calendar_date.day}, {calendar_date.year}"


def _month_label(statement_month: str) -> str:
    year, month = (int(part) for part in statement_month.split("-"))
    return f"{date(year, month, 1):%B %Y}"


def _section(number: int, title: str, body: list, *, keep_together: bool = True) -> list:
    heading = Table(
        [[_p(f"{number}. {title}", SECTION_TITLE)]],
        colWidths=[CONTENT_WIDTH],
        style=TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 1.2, NAVY),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]),
    )
    if keep_together:
        return [KeepTogether([Spacer(1, 16), heading, Spacer(1, 8)] + body)]
    # Long sections may run onto the next page, but never leave their heading alone at a page end.
    return [KeepTogether([Spacer(1, 16), heading, Spacer(1, 8), body[0]])] + body[1:]


def _ledger_style(rows: int, *, total_rows: tuple[int, ...] = (), header: bool = True) -> TableStyle:
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, HAIRLINE),
    ]
    if header:
        commands += [("BACKGROUND", (0, 0), (-1, 0), PANEL), ("LINEBELOW", (0, 0), (-1, 0), 0.8, HAIRLINE)]
    for row in total_rows:
        commands += [("BACKGROUND", (0, row), (-1, row), ACCENT_PALE), ("LINEABOVE", (0, row), (-1, row), 1, ACCENT)]
    return TableStyle(commands)


# -- the six sections ------------------------------------------------------------


def _hero(document: dict) -> list:
    summary = document["summary_rows"]
    amount_owed_label, amount_owed_value = summary[-1]
    hero_card = Table(
        [[_p(amount_owed_label.upper(), HERO_LABEL)], [_p(amount_owed_value, HERO_VALUE)],
         [_p("Total Balance plus any interest not yet added to it.", HERO_CAPTION)]],
        colWidths=[2.75 * inch],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NAVY),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (0, 0), 14),
            ("TOPPADDING", (0, 1), (-1, -1), 2),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 14),
            ("BOTTOMPADDING", (0, 0), (-1, -2), 2),
        ]),
    )

    def stat(label: str, value: str) -> Table:
        return Table(
            [[_p(label, STAT_LABEL)], [_p(value, STAT_VALUE)]],
            colWidths=[2.1 * inch],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), PANEL),
                ("LINEBEFORE", (0, 0), (0, -1), 2.5, ACCENT),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
                ("TOPPADDING", (0, 1), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
            ]),
        )

    small = [stat(label, value) for label, value in summary[:-1]]
    while len(small) < 4:
        small.append(Spacer(1, 1))
    grid = Table(
        [[small[0], small[1]], [small[2], small[3]]],
        colWidths=[2.2 * inch, 2.2 * inch],
        style=TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 0),
        ]),
    )
    hero = Table(
        [[hero_card, grid]],
        colWidths=[2.9 * inch, CONTENT_WIDTH - 2.9 * inch],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (1, 0), (1, 0), 6),
        ]),
    )
    return _section(1, "Summary", [hero])


def _what_happened(document: dict) -> list:
    rows = []
    for sentence in document["what_happened_sentences"]:
        match = DATED_SENTENCE.match(sentence)
        if match:
            chip = Table(
                [[_p(match["when"], CHIP)]],
                colWidths=[0.72 * inch],
                style=TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), ACCENT_PALE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]),
            )
            rows.append([chip, _p(match["sentence"], BODY)])
        else:
            rows.append([_p(sentence, BODY), ""])
    table = Table(
        rows,
        colWidths=[0.9 * inch, CONTENT_WIDTH - 0.9 * inch],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LINEBELOW", (0, 0), (-1, -2), 0.5, HAIRLINE),
        ] + [("SPAN", (0, i), (1, i)) for i, row in enumerate(rows) if row[1] == ""]),
    )
    return _section(2, "What happened this month", [table], keep_together=len(rows) <= 6)


def _interest(document: dict) -> list:
    header = [_p("PERIOD", CELL_HEADER), _p("BALANCE", CELL_HEADER_RIGHT), _p("RATE", CELL_HEADER_RIGHT),
              _p("DAYS", CELL_HEADER_RIGHT), _p("INTEREST", CELL_HEADER_RIGHT)]
    rows = [header]
    notes = []
    loose_lines = []
    for line in document["interest_period_lines"]:
        match = PERIOD_LINE.match(line)
        if match is None:
            loose_lines.append(line)
            continue
        rows.append([
            _p(match["range"], CELL_STRONG),
            _p(match["balance"], CELL_RIGHT),
            _p(f"× {match['rate']}", CELL_RIGHT),
            _p(f"× {match['days']}/30", CELL_RIGHT),
            _p(f"= {match['interest']}", CELL_RIGHT_STRONG),
        ])
        if match["note"]:
            plain_note = match["note"].removeprefix("30-day months: ")
            notes.append(f"{match['range']}: every month counts as 30 days, so {plain_note} days.")

    total_rows = []
    for index, line in enumerate(document["interest_total_lines"]):
        is_last = index == len(document["interest_total_lines"]) - 1
        match = LABEL_AND_EXPRESSION.match(line)
        if match is None:
            loose_lines.append(line)
            continue
        expression = match["expression"]
        formula, _, value = expression.rpartition(" = ")
        if not _:
            formula, value = "", expression
        else:
            value = f"= {value}"
        label_style = CELL_STRONG if is_last else CELL
        value_style = CELL_RIGHT_STRONG if is_last else CELL_RIGHT
        rows.append([_p(match["label"], label_style), _p(formula, CELL_RIGHT), "", "", _p(value, value_style)])
        if is_last:
            total_rows.append(len(rows) - 1)

    column_widths = [2.6 * inch, 1.2 * inch, 0.8 * inch, 1.0 * inch, CONTENT_WIDTH - 5.6 * inch]
    table = Table(rows, colWidths=column_widths, style=_ledger_style(len(rows), total_rows=tuple(total_rows)), repeatRows=1)
    for row_index in range(len(document["interest_period_lines"]) + 1, len(rows)):
        table.setStyle(TableStyle([("SPAN", (1, row_index), (3, row_index))]))
    body = [
        _p("The month is split into stretches of days between changes. Each stretch earns its balance × rate × days/30.", BODY),
        Spacer(1, 6),
        table,
    ]
    body += [Spacer(1, 4)] + [_p(note, NOTE) for note in notes] if notes else []
    body += [_p(line, BODY) for line in loose_lines]
    return _section(3, "How the interest was calculated", body)


def _debt(document: dict) -> list:
    rows = []
    loose_lines = []
    total_rows = []
    for index, line in enumerate(document["debt_equation_lines"]):
        if index == 0:
            match = LABEL_AND_EXPRESSION.match(line)
            if match:
                rows.append([_p(match["label"], CELL_STRONG), _p(match["expression"], CELL_RIGHT_STRONG)])
                continue
        match = DEBT_STEP_LINE.match(line)
        if match is None:
            loose_lines.append(line)
            continue
        sign, amount, label = match["sign"], match["amount"], match["label"]
        if sign == "=":
            rows.append([_p(label, CELL_STRONG), _p(f"= {amount}", CELL_RIGHT_STRONG)])
            total_rows.append(len(rows) - 1)
            continue
        tail = PARENTHETICAL_TAIL.match(label)
        label_cell = (
            [_p(tail["label"][:1].upper() + tail["label"][1:], CELL), _p(tail["note"][:1].upper() + tail["note"][1:] + ".", NOTE)]
            if tail else _p(label[:1].upper() + label[1:], CELL)
        )
        amount_style = ParagraphStyle("signed", parent=CELL_RIGHT, textColor=NEGATIVE if sign == "-" else POSITIVE)
        rows.append([label_cell, _p(f"{sign} {amount}", amount_style)])
    table = Table(rows, colWidths=[CONTENT_WIDTH - 1.6 * inch, 1.6 * inch],
                  style=_ledger_style(len(rows), total_rows=tuple(total_rows), header=False))
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), PANEL)]))

    owed_lines = document["amount_owed_lines"]
    owed_box = Table(
        [[_p(owed_lines[0], CELL_STRONG)]] + [[_p(line, CELL_MUTED)] for line in owed_lines[1:]],
        colWidths=[CONTENT_WIDTH],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), ACCENT_PALE),
            ("LINEBEFORE", (0, 0), (0, -1), 3, ACCENT),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
            ("TOPPADDING", (0, 1), (-1, -1), 2),
        ]),
    )
    body = [table, Spacer(1, 10), owed_box] + [_p(line, BODY) for line in loose_lines]
    return _section(4, "How the total debt was calculated", body, keep_together=len(rows) <= 14)


def _how_it_works(document: dict) -> list:
    bullets = [Paragraph(escape(line), BULLET, bulletText="•") for line in document["how_it_works_lines"]]
    half = (len(bullets) + 1) // 2
    columns = Table(
        [[bullets[:half], bullets[half:]]],
        colWidths=[CONTENT_WIDTH / 2, CONTENT_WIDTH / 2],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, -1), PANEL),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]),
    )
    return _section(5, "How the calculation works", [columns])


def _notes(document: dict, sent_line: Optional[str]) -> list:
    body: list = []
    if document["warnings"]:
        body.append(Table(
            [[_p(warning, WARNING)] for warning in document["warnings"]],
            colWidths=[CONTENT_WIDTH],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), WARNING_PALE),
                ("BOX", (0, 0), (-1, -1), 0.8, WARNING_EDGE),
                ("LINEBEFORE", (0, 0), (0, -1), 3, WARNING_INK),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]),
        ))
        body.append(Spacer(1, 10))
    body.append(Table(
        [[_p(document["binding_sentence"], BINDING)]],
        colWidths=[CONTENT_WIDTH],
        style=TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, NAVY),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ]),
    ))
    body.append(Spacer(1, 8))
    if sent_line:
        body.append(_p(sent_line, FINE_PRINT))
    body.append(_p(f"Engine version {document['engine_version']}. Ledger fingerprint: {document['ledger_fingerprint']}", FINE_PRINT))
    return _section(6, "Notes", body)


# -- page furniture ------------------------------------------------------------------


def _first_page(document: dict):
    month = _month_label(document["statement_month"])
    statement_date = _long_date(document["statement_date"])

    def draw(canvas, doc):
        canvas.saveState()
        top = PAGE_HEIGHT
        canvas.setFillColor(NAVY)
        canvas.rect(0, top - HEADER_BAND_HEIGHT, PAGE_WIDTH, HEADER_BAND_HEIGHT, stroke=0, fill=1)
        canvas.setFillColor(ACCENT)
        canvas.rect(0, top - HEADER_BAND_HEIGHT - 4, PAGE_WIDTH, 4, stroke=0, fill=1)

        canvas.saveState()  # the letter-spacing must not leak into the lines below
        text = canvas.beginText(SIDE_MARGIN, top - 0.42 * inch)
        text.setFont("Helvetica-Bold", 8.5)
        text.setCharSpace(1.6)
        text.setFillColor(SKY)
        text.textLine("BIG WHALES AY LLC  ·  MEMBER LOAN")
        canvas.drawText(text)
        canvas.restoreState()
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 23)
        canvas.drawString(SIDE_MARGIN, top - 0.80 * inch, "Monthly Statement")
        canvas.setFillColor(SKY)
        canvas.setFont("Helvetica", 13)
        canvas.drawString(SIDE_MARGIN, top - 1.08 * inch, month)

        right = PAGE_WIDTH - SIDE_MARGIN
        canvas.setFont("Helvetica-Bold", 7.6)
        canvas.setFillColor(SKY)
        canvas.drawRightString(right, top - 0.42 * inch, "STATEMENT DATE")
        canvas.setFont("Helvetica-Bold", 12)
        canvas.setFillColor(WHITE)
        canvas.drawRightString(right, top - 0.62 * inch, statement_date)
        canvas.setFont("Helvetica", 8.6)
        canvas.setFillColor(SKY)
        canvas.drawRightString(right, top - 0.90 * inch, "Lender: Aviv Jan")
        canvas.drawRightString(right, top - 1.07 * inch, "Borrower: Big Whales AY LLC")
        canvas.restoreState()
        _footer(canvas, doc, month)

    return draw


def _later_page(document: dict):
    month = _month_label(document["statement_month"])

    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, PAGE_HEIGHT - 0.32 * inch, PAGE_WIDTH, 0.32 * inch, stroke=0, fill=1)
        canvas.setFont("Helvetica-Bold", 7.8)
        canvas.setFillColor(SKY)
        canvas.drawString(SIDE_MARGIN, PAGE_HEIGHT - 0.2 * inch, f"MEMBER LOAN  ·  {month.upper()}")
        canvas.restoreState()
        _footer(canvas, doc, month)

    return draw


def _footer(canvas, doc, month: str) -> None:
    canvas.saveState()
    canvas.setStrokeColor(HAIRLINE)
    canvas.setLineWidth(0.6)
    canvas.line(SIDE_MARGIN, 0.62 * inch, PAGE_WIDTH - SIDE_MARGIN, 0.62 * inch)
    canvas.setFont("Helvetica", 7.6)
    canvas.setFillColor(MUTED)
    canvas.drawString(SIDE_MARGIN, 0.45 * inch, f"Big Whales AY LLC  ·  Member Loan statement  ·  {month}")
    canvas.drawRightString(PAGE_WIDTH - SIDE_MARGIN, 0.45 * inch, f"Page {doc.page}")
    canvas.restoreState()


def render_member_loan_statement_pdf(document: dict, *, sent_line: Optional[str] = None) -> bytes:
    buffer = io.BytesIO()
    pdf = BaseDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=SIDE_MARGIN,
        rightMargin=SIDE_MARGIN,
        topMargin=0.6 * inch,
        bottomMargin=0.85 * inch,
        title=document["title"],
        author="Big Whales AY LLC",
        subject="Member Loan statement",
    )
    first_frame = Frame(
        SIDE_MARGIN, 0.85 * inch, CONTENT_WIDTH, PAGE_HEIGHT - HEADER_BAND_HEIGHT - 0.25 * inch - 0.85 * inch,
        id="first", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    later_frame = Frame(
        SIDE_MARGIN, 0.85 * inch, CONTENT_WIDTH, PAGE_HEIGHT - 0.6 * inch - 0.85 * inch,
        id="later", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    pdf.addPageTemplates([
        PageTemplate(id="first", frames=[first_frame], onPage=_first_page(document)),
        PageTemplate(id="later", frames=[later_frame], onPage=_later_page(document)),
    ])
    story: list = [NextPageTemplate("later")]
    story += _hero(document)
    story += _what_happened(document)
    story += _interest(document)
    story += _debt(document)
    story += _how_it_works(document)
    story += _notes(document, sent_line)
    pdf.build(story)
    return buffer.getvalue()
