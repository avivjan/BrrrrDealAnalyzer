"""The rehab summary sent when a construction account is closed out
(tasks/todo/ConstructionAccountsCompactCardsAndRehabSummary.md): a PDF with the rehab's statistics, every bank
transaction, the manual entries and the in-app transfers; a CSV of every transaction; and the e-mail around them.

Built only from the deal's construction account status and its categorised transactions, as they are at close-out.
Every user or bank text goes through `escape` before ReportLab's Paragraph mini-markup or the e-mail's HTML, and every
CSV cell that a spreadsheet could read as a formula is defused.

    REHAB_SUMMARY_EMAIL    where the summary is e-mailed (the owner's address; no default: unset, the e-mail fails and is retried)
    REHAB_SUMMARY_SENDER   the Gmail account it is sent from (default the company Gmail; its app password is EMAIL_PASSWORD)
"""

from __future__ import annotations

import csv
import io
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Sequence
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from BL.memberLoan.common.member_loan_settings import DEFAULT_SENDER_ADDRESS
from ReqRes.common.liquidity_construction_account_schemas import ConstructionAccountStatusRes, ConstructionAccountTransactionRes

CATEGORY_LABELS = {"loan_draw": "Lender draw", "rehab_payment": "Rehab payment", "own_money": "Your own money"}
MANUAL_ADJUSTMENT_TYPE_LABELS = {"manual_payment": "Payment entered by hand", "manual_draw": "Draw entered by hand"}
TRANSFER_DIRECTION_LABELS = {"deposit_into_construction_account": "Deposit", "steal_to_primary_checking": "Steal"}
CSV_CELL_PREFIXES_A_SPREADSHEET_READS_AS_A_FORMULA = ("=", "+", "-", "@", "\t", "\r")
FILE_NAME_UNSAFE_CHARACTERS_PATTERN = re.compile(r"[^A-Za-z0-9 ,.#()_-]+")
LARGEST_FILE_BASE_NAME_LENGTH = 140


class RehabSummaryEmailAddressMissing(RuntimeError):
    pass


@dataclass(frozen=True)
class RehabSummaryStatistic:
    label: str
    value: str


@dataclass(frozen=True)
class RehabSummaryContent:
    deal_address: str
    closed_out_on: Optional[date]
    statistics: list[RehabSummaryStatistic]
    status: ConstructionAccountStatusRes
    transactions: Optional[list[ConstructionAccountTransactionRes]]


def rehab_summary_email_address() -> str:
    address = (os.getenv("REHAB_SUMMARY_EMAIL") or "").strip()
    if not address or "@" not in address or any(character.isspace() for character in address) or "," in address:
        raise RehabSummaryEmailAddressMissing("REHAB_SUMMARY_EMAIL is not set to one e-mail address")
    return address


def rehab_summary_sender_address() -> str:
    return (os.getenv("REHAB_SUMMARY_SENDER") or "").strip() or DEFAULT_SENDER_ADDRESS


def dollars_text(amount_dollars: Optional[float]) -> str:
    if amount_dollars is None:
        return "-"
    sign = "-" if amount_dollars < 0 else ""
    return f"{sign}${abs(amount_dollars):,.2f}".replace(".00", "")


def _percent_text(part_dollars: float, whole_dollars: float) -> str:
    return f"{part_dollars / whole_dollars * 100:.0f}%" if whole_dollars else "-"


def _days_between(start: Optional[date], end: Optional[date]) -> Optional[int]:
    return (end - start).days if start and end else None


def build_rehab_summary_content(status: ConstructionAccountStatusRes, transactions: Optional[list[ConstructionAccountTransactionRes]],
                                closed_out_on: Optional[date]) -> RehabSummaryContent:
    draws_received = status.loan_draws_pulled.total_dollars if status.loan_draws_pulled else 0.0
    paid_to_contractors = status.rehab_payments_made.total_dollars if status.rehab_payments_made else 0.0
    under_or_over_budget = status.construction_budget_dollars - status.rehab_cost_dollars
    days_from_purchase_to_close_out = _days_between(status.purchase_closing_date, closed_out_on)
    statistics = [
        RehabSummaryStatistic("Purchase closing", status.purchase_closing_date.isoformat() if status.purchase_closing_date else "-"),
        RehabSummaryStatistic("Rehab completed (planned)", status.rehab_completed_date.isoformat() if status.rehab_completed_date else "-"),
        RehabSummaryStatistic("Construction account closed out", closed_out_on.isoformat() if closed_out_on else "-"),
        RehabSummaryStatistic("Days from purchase to close-out", str(days_from_purchase_to_close_out) if days_from_purchase_to_close_out is not None else "-"),
        RehabSummaryStatistic("Lender's construction budget", dollars_text(status.construction_budget_dollars)),
        RehabSummaryStatistic("Rehab cost (actual + contingency)",
                              f"{dollars_text(status.rehab_cost_dollars)} ({dollars_text(status.actual_rehab_cost_dollars)} + {status.rehab_contingency_percent:g}%)"),
        RehabSummaryStatistic("Under budget: you keep" if under_or_over_budget >= 0 else "Over budget: you covered", dollars_text(abs(under_or_over_budget))),
        RehabSummaryStatistic("Lender draws received",
                              f"{dollars_text(draws_received)} in {status.loan_draw_count or 0} draws ({_percent_text(draws_received, status.construction_budget_dollars)} of the budget)"),
        RehabSummaryStatistic("Lender budget never drawn", dollars_text(status.loan_draws_remaining_to_pull_dollars)),
        RehabSummaryStatistic("Paid to contractors", f"{dollars_text(paid_to_contractors)} ({_percent_text(paid_to_contractors, status.rehab_cost_dollars)} of the rehab cost)"),
        RehabSummaryStatistic("Rehab cost left unpaid", dollars_text(status.unpaid_rehab_remaining_dollars)),
        RehabSummaryStatistic("Your deposit (planned)", dollars_text(status.total_to_deposit_dollars)),
        RehabSummaryStatistic("Your money deposited", dollars_text(status.own_money_transferred_into_the_account_dollars)),
        RehabSummaryStatistic("Money taken out to checking (steals and close-out)", dollars_text(status.own_money_transferred_out_of_the_account_dollars)),
        RehabSummaryStatistic("Net back to you (taken out - deposited)", dollars_text(
            (status.own_money_transferred_out_of_the_account_dollars or 0) - (status.own_money_transferred_into_the_account_dollars or 0))),
        RehabSummaryStatistic("Left in the account at close-out", dollars_text(status.current_balance_dollars)),
    ]
    return RehabSummaryContent(deal_address=status.deal_address, closed_out_on=closed_out_on, statistics=statistics,
                               status=status, transactions=transactions)


def rehab_summary_file_base_name(content: RehabSummaryContent) -> str:
    safe_address = FILE_NAME_UNSAFE_CHARACTERS_PATTERN.sub(" ", content.deal_address).strip() or "rehab"
    day = content.closed_out_on.isoformat() if content.closed_out_on else "not closed out"
    return f"Rehab summary {day} {safe_address}"[:LARGEST_FILE_BASE_NAME_LENGTH].strip()


def _transaction_category_text(transaction: ConstructionAccountTransactionRes) -> str:
    if transaction.ignored:
        return "Ignored"
    if transaction.effective_category is None:
        return "Failed or cancelled"
    label = CATEGORY_LABELS.get(transaction.effective_category, transaction.effective_category)
    return f"{label} (corrected)" if transaction.category_override else label


def _defused_csv_cell(value: object) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(CSV_CELL_PREFIXES_A_SPREADSHEET_READS_AS_A_FORMULA) else text


def build_rehab_summary_transactions_csv(content: RehabSummaryContent) -> str:
    """Every bank transaction, then every manual entry: one row each, amounts signed (positive = into the account)."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "source", "counterparty", "amount_dollars", "category", "bank_status", "note"])
    for transaction in reversed(content.transactions or []):
        writer.writerow([_defused_csv_cell(value) for value in (
            transaction.transaction_date.isoformat() if transaction.transaction_date else "", "bank", transaction.counterparty_name,
            f"{transaction.signed_amount_dollars:.2f}", _transaction_category_text(transaction), transaction.bank_status, transaction.note or "")])
    for adjustment in content.status.manual_adjustments:
        signed_amount = adjustment.amount_dollars if adjustment.adjustment_type == "manual_draw" else -adjustment.amount_dollars
        writer.writerow([_defused_csv_cell(value) for value in (
            adjustment.date.isoformat() if adjustment.date else "", "entered by hand", "",
            f"{signed_amount:.2f}", MANUAL_ADJUSTMENT_TYPE_LABELS.get(adjustment.adjustment_type, adjustment.adjustment_type), "", adjustment.note or "")])
    return output.getvalue()


def _paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def _table(header: Sequence[str], rows: list[Sequence[str]], column_widths: Sequence[float], cell_style: ParagraphStyle) -> Table:
    table = Table([[_paragraph(cell, cell_style) for cell in header]] + [[_paragraph(cell, cell_style) for cell in row] for row in rows],
                  colWidths=list(column_widths), repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def build_rehab_summary_pdf(content: RehabSummaryContent) -> bytes:
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle("RehabSummaryCell", parent=styles["BodyText"], fontSize=8, leading=10)
    heading_style = styles["Heading2"]
    story = [
        _paragraph(f"Rehab summary: {content.deal_address}", styles["Title"]),
        _paragraph("The construction account was closed out. These are its numbers as they were then.", styles["BodyText"]),
        Spacer(1, 0.15 * inch),
        _paragraph("The numbers", heading_style),
        _table(["", ""], [(statistic.label, statistic.value) for statistic in content.statistics], [3.4 * inch, 3.6 * inch], cell_style),
    ]
    if content.status.rehab_paid_by_payee:
        story += [Spacer(1, 0.15 * inch), _paragraph("Paid to each contractor", heading_style),
                  _table(["Payee", "Paid"], [(payee.payee_name, dollars_text(payee.amount_dollars)) for payee in content.status.rehab_paid_by_payee],
                         [5 * inch, 2 * inch], cell_style)]
    story += [Spacer(1, 0.15 * inch), _paragraph("Bank transactions", heading_style)]
    if content.transactions is None:
        story.append(_paragraph("Mercury could not be read when this summary was made: use Send again on the Construction accounts page.", styles["BodyText"]))
    elif not content.transactions:
        story.append(_paragraph("None.", styles["BodyText"]))
    else:
        story.append(_table(["Date", "Counterparty", "Amount", "Category", "Note"], [(
            transaction.transaction_date.isoformat() if transaction.transaction_date else "", transaction.counterparty_name,
            dollars_text(transaction.signed_amount_dollars), _transaction_category_text(transaction), transaction.note or "",
        ) for transaction in reversed(content.transactions)], [0.85 * inch, 2.1 * inch, 1 * inch, 1.35 * inch, 1.7 * inch], cell_style))
    if content.status.manual_adjustments:
        story += [Spacer(1, 0.15 * inch), _paragraph("Entered by hand", heading_style),
                  _table(["Date", "Kind", "Amount", "Note"], [(
                      adjustment.date.isoformat() if adjustment.date else "", MANUAL_ADJUSTMENT_TYPE_LABELS.get(adjustment.adjustment_type, adjustment.adjustment_type),
                      dollars_text(adjustment.amount_dollars), adjustment.note or "",
                  ) for adjustment in content.status.manual_adjustments], [0.85 * inch, 2 * inch, 1.15 * inch, 3 * inch], cell_style)]
    if content.status.transfers_made_in_the_app:
        story += [Spacer(1, 0.15 * inch), _paragraph("Transfers made in the app", heading_style),
                  _table(["Requested", "Kind", "Amount", "Outcome"], [(
                      transfer.requested_at.strftime("%Y-%m-%d %H:%M") if transfer.requested_at else "",
                      TRANSFER_DIRECTION_LABELS.get(transfer.transfer_direction, transfer.transfer_direction),
                      dollars_text(transfer.amount_dollars), transfer.transfer_outcome.replace("_", " "),
                  ) for transfer in content.status.transfers_made_in_the_app], [1.4 * inch, 1.2 * inch, 1.2 * inch, 3.2 * inch], cell_style)]
    output = io.BytesIO()
    SimpleDocTemplate(output, pagesize=LETTER, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                      title="Rehab summary").build(story)
    return output.getvalue()


def rehab_summary_email_subject(deal_address: str) -> str:
    return f"Rehab completed – {deal_address}"[:200]


def rehab_summary_email_text(deal_address: str, statistics: Sequence[RehabSummaryStatistic], drive_folder_url: Optional[str]) -> str:
    lines = [f"The construction account of {deal_address} was closed out.", ""]
    lines += [f"{statistic.label}: {statistic.value}" for statistic in statistics]
    lines += ["", "The PDF (every number, transaction and transfer) and a CSV of the transactions are attached."]
    if drive_folder_url:
        lines.append(f"Both are saved in Google Drive: {drive_folder_url}")
    return "\n".join(lines)


def rehab_summary_email_html(deal_address: str, statistics: Sequence[RehabSummaryStatistic], drive_folder_url: Optional[str]) -> str:
    rows = "".join(
        f'<tr><td style="padding:4px 12px 4px 0;color:#475569">{escape(statistic.label)}</td>'
        f'<td style="padding:4px 0;font-weight:600">{escape(statistic.value)}</td></tr>' for statistic in statistics)
    drive_line = (f'<p>Both are saved in <a href="{escape(drive_folder_url, {chr(34): "&quot;"})}">Google Drive</a>.</p>'
                  if drive_folder_url and drive_folder_url.startswith("https://drive.google.com/") else "")
    return (f"<html><body style=\"font-family:Arial,sans-serif;color:#0f172a\">"
            f"<h2>Rehab completed: {escape(deal_address)}</h2>"
            f"<p>The construction account was closed out. Its numbers then:</p><table>{rows}</table>"
            f"<p>The PDF (every number, transaction and transfer) and a CSV of the transactions are attached.</p>{drive_line}"
            f"</body></html>")


def closed_out_on_of(closed_out_at: Optional[datetime]) -> Optional[date]:
    return closed_out_at.date() if closed_out_at else None


def statistics_as_stored(statistics: Sequence[RehabSummaryStatistic]) -> list[dict]:
    return [{"label": statistic.label, "value": statistic.value} for statistic in statistics]


def statistics_from_stored(stored_statistics: object) -> list[RehabSummaryStatistic]:
    if not isinstance(stored_statistics, list):
        return []
    return [RehabSummaryStatistic(str(item.get("label", "")), str(item.get("value", ""))) for item in stored_statistics if isinstance(item, dict)]
