"""PDFs for signing: the Loan Change Record, the statement with its acknowledgment
page, and the signature certificate appended to make the signed copy.

The palette, type and section headings come from `member_loan_statement_pdf.py`
so every Member Loan document looks the same. Everything is drawn from the
document's plain content dict (`member_loan_signing_documents.py`), and every
string is escaped before it reaches ReportLab's Paragraph markup.

The signed copy is the unsigned PDF's pages, unchanged, followed by the
certificate: the document's SHA-256 printed on the certificate is the SHA-256
of exactly those first pages as they were signed.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Callable, Sequence

from pypdf import PdfReader, PdfWriter
from reportlab.lib.units import inch
from reportlab.platypus import BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate, PageTemplate, Spacer, Table, TableStyle

from BL.memberLoan.common.member_loan_settings import LOAN_TIME_ZONE
from BL.memberLoan.common.member_loan_statement_pdf import (
    ACCENT,
    ACCENT_PALE,
    BODY,
    BODY_STRONG,
    BULLET,
    CELL,
    CELL_HEADER,
    CELL_HEADER_RIGHT,
    CELL_RIGHT,
    CELL_RIGHT_STRONG,
    CELL_STRONG,
    CONTENT_WIDTH,
    FINE_PRINT,
    HAIRLINE,
    HEADER_BAND_HEIGHT,
    MUTED,
    NAVY,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    PANEL,
    SIDE_MARGIN,
    SKY,
    WARNING,
    WARNING_EDGE,
    WARNING_PALE,
    WHITE,
    _ledger_style,
    _long_date,
    _p,
    _section,
    render_member_loan_statement_pdf,
)

SIGNATURE_IMAGE_WIDTH = 2.2 * inch
SIGNATURE_IMAGE_HEIGHT = 0.75 * inch


def _header_band(kicker: str, title: str, subtitle: str, right_label: str, right_value: str, right_lines: Sequence[str], footer_label: str):
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
        text.textLine(kicker)
        canvas.drawText(text)
        canvas.restoreState()
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 21)
        canvas.drawString(SIDE_MARGIN, top - 0.80 * inch, title)
        canvas.setFillColor(SKY)
        canvas.setFont("Helvetica", 12)
        canvas.drawString(SIDE_MARGIN, top - 1.08 * inch, subtitle)
        right = PAGE_WIDTH - SIDE_MARGIN
        canvas.setFont("Helvetica-Bold", 7.6)
        canvas.drawRightString(right, top - 0.42 * inch, right_label)
        canvas.setFont("Helvetica-Bold", 12)
        canvas.setFillColor(WHITE)
        canvas.drawRightString(right, top - 0.62 * inch, right_value)
        canvas.setFont("Helvetica", 8.6)
        canvas.setFillColor(SKY)
        for position, line in enumerate(right_lines):
            canvas.drawRightString(right, top - (0.90 + 0.17 * position) * inch, line)
        canvas.restoreState()
        _footer(canvas, doc, footer_label)

    return draw


def _later_band(label: str):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, PAGE_HEIGHT - 0.32 * inch, PAGE_WIDTH, 0.32 * inch, stroke=0, fill=1)
        canvas.setFont("Helvetica-Bold", 7.8)
        canvas.setFillColor(SKY)
        canvas.drawString(SIDE_MARGIN, PAGE_HEIGHT - 0.2 * inch, label.upper())
        canvas.restoreState()
        _footer(canvas, doc, label)

    return draw


def _footer(canvas, doc, label: str) -> None:
    canvas.saveState()
    canvas.setStrokeColor(HAIRLINE)
    canvas.setLineWidth(0.6)
    canvas.line(SIDE_MARGIN, 0.62 * inch, PAGE_WIDTH - SIDE_MARGIN, 0.62 * inch)
    canvas.setFont("Helvetica", 7.6)
    canvas.setFillColor(MUTED)
    canvas.drawString(SIDE_MARGIN, 0.45 * inch, f"Big Whales AY LLC  ·  {label}")
    canvas.drawRightString(PAGE_WIDTH - SIDE_MARGIN, 0.45 * inch, f"Page {doc.page}")
    canvas.restoreState()


def _build(story: list, *, title: str, subject: str, first_page: Callable, later_page: Callable) -> bytes:
    buffer = io.BytesIO()
    pdf = BaseDocTemplate(
        buffer, pagesize=(PAGE_WIDTH, PAGE_HEIGHT), leftMargin=SIDE_MARGIN, rightMargin=SIDE_MARGIN,
        topMargin=0.6 * inch, bottomMargin=0.85 * inch, title=title, author="Big Whales AY LLC", subject=subject,
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
        PageTemplate(id="first", frames=[first_frame], onPage=first_page),
        PageTemplate(id="later", frames=[later_frame], onPage=later_page),
    ])
    pdf.build([NextPageTemplate("later")] + story)
    return buffer.getvalue()


def _bullets(lines: Sequence[str]) -> list:
    return [_p(line, BULLET) for line in lines]


def _key_value_table(rows: Sequence[Sequence[str]]) -> Table:
    table = Table(
        [[_p(label, CELL_STRONG), _p(value, CELL)] for label, value in rows],
        colWidths=[1.9 * inch, CONTENT_WIDTH - 1.9 * inch],
    )
    table.setStyle(_ledger_style(len(rows), header=False))
    return table


def _warning_box(lines: Sequence[str]) -> list:
    if not lines:
        return []
    box = Table([[_p(line, WARNING)] for line in lines], colWidths=[CONTENT_WIDTH])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WARNING_PALE),
        ("BOX", (0, 0), (-1, -1), 0.8, WARNING_EDGE),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return [Spacer(1, 10), box]


def _signature_blocks(signers: Sequence[dict]) -> list:
    """Each signer's statement and an empty line: the signatures themselves are on the certificate."""

    blocks = []
    for signer in signers:
        statement_paragraphs = [_p(line, BODY) for line in signer["statement_text"].split("\n")]
        block = Table(
            [[_p(f"{signer['legal_name']} — {signer['role_label']}", BODY_STRONG)]]
            + [[paragraph] for paragraph in statement_paragraphs]
            + [[_p("Signature: signed electronically in the Software (see the signature certificate)", FINE_PRINT)]],
            colWidths=[CONTENT_WIDTH],
        )
        block.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PANEL),
            ("LINEBEFORE", (0, 0), (0, -1), 2.5, ACCENT),
            ("LEFTPADDING", (0, 0), (-1, -1), 11), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, 0), 8), ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
        ]))
        # No KeepTogether here: `_section` already keeps the heading with the first block,
        # and a nested KeepTogether pushes the whole section to a new page.
        blocks += [block, Spacer(1, 8)]
    return blocks


# -- the Loan Change Record --------------------------------------------------------


def render_loan_change_record_pdf(content: dict) -> bytes:
    figures_rows = content["figures_rows"]
    figures = Table(
        [[_p("Figure", CELL_HEADER), _p("Before", CELL_HEADER_RIGHT), _p("After", CELL_HEADER_RIGHT)]]
        + [
            [_p(label, CELL_STRONG if label == "Amount Owed" else CELL),
             _p(before, CELL_RIGHT_STRONG if label == "Amount Owed" else CELL_RIGHT),
             _p(after, CELL_RIGHT_STRONG if label == "Amount Owed" else CELL_RIGHT)]
            for label, before, after in figures_rows
        ],
        colWidths=[CONTENT_WIDTH - 2.6 * inch, 1.3 * inch, 1.3 * inch],
        repeatRows=1,
    )
    owed_rows = tuple(position + 1 for position, row in enumerate(figures_rows) if row[0] == "Amount Owed")
    figures.setStyle(_ledger_style(len(figures_rows) + 1, total_rows=owed_rows))

    story: list = [_p(content["agreement_reference"], BODY), Spacer(1, 4)]
    story += _section(1, "Parties", _bullets(content["parties_lines"]))
    story += _section(2, "What changes", [_key_value_table(content["change_rows"])])
    story += _section(3, "What the Agreement says", _bullets(content["contract_basis_lines"]))
    story += _section(
        4,
        f"Figures before and after, on {_long_date(content['figures_effective_date'])}",
        [figures] + [Spacer(1, 6)] + [_p(line, BODY) for line in content["allocation_lines"]] + _warning_box(content["warnings"]),
    )
    story += _section(5, "Effect", _bullets(content["effect_lines"]))
    story += _section(6, "Signatures", _signature_blocks(content["signers"]), keep_together=False)
    story += [Spacer(1, 10), _p(f"Figures fingerprint: {content['preview_fingerprint']}", FINE_PRINT)]
    label = f"Loan Change Record No. {content['record_number']}"
    first = _header_band(
        "BIG WHALES AY LLC  ·  MEMBER LOAN", "Loan Change Record", f"No. {content['record_number']} · {content['change_rows'][0][1]}",
        "PREPARED ON", _long_date(content["prepared_on"]), ["Lender: " + content["parties_lines"][0].split(": ", 1)[1], "Borrower: Big Whales AY LLC"],
        label,
    )
    return _build(story, title=content["title"], subject="Member Loan change record", first_page=first, later_page=_later_band(label))


# -- the statement and its acknowledgment page ----------------------------------------


def render_statement_acknowledgment_pdf(content: dict) -> bytes:
    story: list = []
    story += _section(1, "Acknowledgment", [_p(line, BODY) for line in content["acknowledgment_intro_lines"]])
    story += _section(2, "Signatures", _signature_blocks(content["signers"]), keep_together=False)
    label = f"Member Loan statement · {content['month_label']} · acknowledgment"
    first = _header_band(
        "BIG WHALES AY LLC  ·  MEMBER LOAN", "Statement Acknowledgment", content["month_label"],
        "AMOUNT OWED", content["amount_owed"], [f"as of {_long_date(content['statement_date'])}"], label,
    )
    return _build(story, title=f"{content['title']} – acknowledgment", subject="Member Loan statement acknowledgment",
                  first_page=first, later_page=_later_band(label))


def render_statement_signing_pdf(content: dict) -> bytes:
    """The statement exactly as sent, followed by its acknowledgment page."""

    statement_pdf = render_member_loan_statement_pdf(content["statement_document"], sent_line=content["sent_line"])
    return concatenate_pdfs([statement_pdf, render_statement_acknowledgment_pdf(content)])


def render_signing_document_pdf(content: dict) -> bytes:
    if content["document_kind"] == "monthly_statement":
        return render_statement_signing_pdf(content)
    return render_loan_change_record_pdf(content)


# -- the signature certificate ----------------------------------------------------------


def _times(moment: datetime) -> str:
    in_new_york = moment.astimezone(LOAN_TIME_ZONE)
    in_utc = moment.astimezone(timezone.utc)
    return f"{in_new_york:%b} {in_new_york.day}, {in_new_york.year} {in_new_york:%H:%M:%S} New York  ·  {in_utc:%Y-%m-%d %H:%M:%S} UTC"


def render_signature_certificate_pdf(*, content: dict, unsigned_pdf_sha256: str, signatures: Sequence, completed_at: datetime) -> bytes:
    """`signatures` are `MemberLoanSignature` rows in signing order."""

    story: list = [
        _p(f"Document: {content['title']}", BODY_STRONG),
        _p(f"SHA-256 of the signed pages (pages before this certificate): {unsigned_pdf_sha256}", FINE_PRINT),
        _p(f"Completed: {_times(completed_at)}", FINE_PRINT),
        Spacer(1, 4),
        _p(
            "Each signature below was made in the Big Whales Deal Analyzer under Amendment No. 1, Section 1.2: the signer viewed "
            "the document, typed their full legal name, confirmed the electronic signature consent, drew a signature and confirmed "
            "with their own passkey. The passkey signed the value SHA-256(\"<document SHA-256>:<nonce>\"), which binds it to "
            "this exact document.",
            BODY,
        ),
    ]
    for signature in signatures:
        meaning = "Objected" if signature.signature_meaning == "objected" else "Signed"
        image = Image(io.BytesIO(bytes(signature.drawn_signature_png)), width=SIGNATURE_IMAGE_WIDTH,
                      height=SIGNATURE_IMAGE_HEIGHT, kind="proportional")
        rows = [
            ["Signer", f"{signature.typed_full_legal_name} ({signature.signer_username})", CELL],
            ["Result", meaning + (f": {signature.objection_reason}" if signature.objection_reason else ""), CELL],
            ["Time", _times(signature.signed_at), CELL],
            ["Statement signed", signature.signature_statement_text.replace("\n", " "), CELL],
            ["Passkey credential", signature.webauthn_credential_id, FINE_PRINT],
            ["Challenge nonce", signature.passkey_challenge_nonce, FINE_PRINT],
            ["Device and address", f"device {signature.device_id or 'unknown'}  ·  IP {signature.request_ip or 'unknown'}", FINE_PRINT],
            ["Browser", signature.user_agent or "unknown", FINE_PRINT],
        ]
        image_column_width = SIGNATURE_IMAGE_WIDTH + 0.3 * inch
        details_column_width = CONTENT_WIDTH - image_column_width
        details_inner_width = details_column_width - 16  # the card's own left and right padding
        details = Table([[_p(label, CELL_STRONG), _p(value, style)] for label, value, style in rows],
                        colWidths=[1.3 * inch, details_inner_width - 1.3 * inch])
        details.setStyle(_ledger_style(len(rows), header=False))
        card = Table([[image, details]], colWidths=[image_column_width, details_column_width])
        card.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOX", (0, 0), (-1, -1), 0.8, HAIRLINE),
            ("BACKGROUND", (0, 0), (0, 0), ACCENT_PALE),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story += [Spacer(1, 12), KeepTogether([card])]
    label = "Signature certificate"
    first = _header_band(
        "BIG WHALES AY LLC  ·  MEMBER LOAN", "Signature Certificate", content["title"][:70],
        "COMPLETED", _long_date(completed_at.astimezone(LOAN_TIME_ZONE).date().isoformat()),
        [f"{len(signatures)} signature{'s' if len(signatures) != 1 else ''}"], label,
    )
    return _build(story, title=f"{content['title']} – signature certificate", subject="Member Loan signature certificate",
                  first_page=first, later_page=_later_band(label))


def concatenate_pdfs(pdfs: Sequence[bytes]) -> bytes:
    writer = PdfWriter()
    for pdf in pdfs:
        for page in PdfReader(io.BytesIO(pdf)).pages:
            writer.add_page(page)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()

