"""The statement PDF: six plain sections, and every printed equation adds up
when re-read from the PDF's own text (tasks/todo/MemberLoan.md, Statement PDF)."""

from __future__ import annotations

import io
import re
from datetime import date
from decimal import Decimal

import pytest
from pypdf import PdfReader

from BL.memberLoan.common.member_loan_engine import (
    DEFAULT_MEMBER_LOAN_TERMS,
    INTEREST_PAYMENT_ELECTION,
    LENDER_ADDITIONAL_ADVANCE,
    LENDER_WITHDRAWAL,
    YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE,
    YARDEN_CAPITAL_CONTRIBUTION_REDUCTION,
    EffectiveMemberLoanEvent,
    build_member_loan_monthly_statement_figures,
    first_day_of_next_month,
    round_half_up_to_cent,
)
from BL.memberLoan.common.member_loan_statement_document import (
    BINDING_STATEMENT_SENTENCE,
    MemberLoanEventDescription,
    build_member_loan_statement_document,
    parse_money,
)
from BL.memberLoan.common.member_loan_statement_pdf import render_member_loan_statement_pdf

D = Decimal
MONEY = r"-?\$[\d,]+\.\d{2}"
SECTION_HEADINGS = (
    "1. Summary",
    "2. What happened this month",
    "3. How the interest was calculated",
    "4. How the total debt was calculated",
    "5. How the calculation works",
    "6. Notes",
)


def _event(order: int, event_type: str, on: date, amount: str | None = None, election: str | None = None):
    return EffectiveMemberLoanEvent(f"e{order}", event_type, on, order, None if amount is None else D(amount), election)


def _description(event: EffectiveMemberLoanEvent, **references) -> MemberLoanEventDescription:
    proposer, approver = ("Yarden", "Aviv") if event.event_type.startswith("yarden") else ("Aviv", "Yarden")
    return MemberLoanEventDescription(
        event_id=event.event_id, event_type=event.event_type, proposed_by_display_name=proposer, proposed_on=event.effective_date,
        approved_by_display_name=approver, approved_on=event.effective_date, effective_date=event.effective_date, amount=event.amount,
        **references,
    )


SCENARIOS = {
    "no events": [],
    "mid-month withdrawal": [_event(1, LENDER_WITHDRAWAL, date(2026, 12, 15), "1000.00")],
    "withdrawal on the 31st": [_event(1, LENDER_WITHDRAWAL, date(2026, 10, 31), "1000.00")],
    "reduction into interest": [_event(1, YARDEN_CAPITAL_CONTRIBUTION_REDUCTION, date(2026, 12, 15), "31100.00")],
    "increase": [_event(1, YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE, date(2026, 12, 15), "2000.00")],
    "advance on the 10th": [_event(1, LENDER_ADDITIONAL_ADVANCE, date(2027, 1, 10), "5000.00")],
    "advance on feb 28": [_event(1, LENDER_ADDITIONAL_ADVANCE, date(2027, 2, 28), "1000.00")],
    "cash election then withdrawal": [
        _event(1, INTEREST_PAYMENT_ELECTION, date(2026, 11, 1), election="cash"),
        _event(2, LENDER_WITHDRAWAL, date(2026, 11, 10), "400.00"),
    ],
    "several events in one month": [
        _event(1, LENDER_ADDITIONAL_ADVANCE, date(2026, 12, 3), "2500.00"),
        _event(2, LENDER_WITHDRAWAL, date(2026, 12, 15), "1000.00"),
        _event(3, YARDEN_CAPITAL_CONTRIBUTION_REDUCTION, date(2026, 12, 15), "750.00"),
        _event(4, YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE, date(2026, 12, 31), "300.00"),
    ],
}
REFERENCES = {"written_agreement_date": date(2026, 12, 1), "written_agreement_description": "Signed by both members"}


def _document(events, month: date, **extra):
    figures = build_member_loan_monthly_statement_figures(DEFAULT_MEMBER_LOAN_TERMS, events, month)
    descriptions = {e.event_id: _description(e, **REFERENCES) for e in events}
    return build_member_loan_statement_document(
        figures, DEFAULT_MEMBER_LOAN_TERMS, lender_display_name="Aviv", yarden_display_name="Yarden",
        event_descriptions=descriptions, ledger_fingerprint="f" * 64, **extra,
    )


def pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return " ".join(" ".join(page.extract_text().split()) for page in reader.pages)


def _between(text: str, start: str, end: str) -> str:
    return text[text.index(start) + len(start): text.index(end)]


def assert_pdf_equations_add_up(text: str) -> None:
    """Re-check every equation using only the text printed in the PDF."""

    interest_section = _between(text, SECTION_HEADINGS[2], SECTION_HEADINGS[3])
    periods = re.findall(rf"({MONEY}) × ([\d.]+)% × (\d+)/30 = ({MONEY})", interest_section)
    assert periods, "no interest period lines found"
    for balance, rate, days, interest in periods:
        assert round_half_up_to_cent(parse_money(balance) * D(rate) / 100 * int(days) / 30) == parse_money(interest)
    period_sum = sum((parse_money(p[3]) for p in periods), D("0"))
    month_interest = re.search(rf"Interest for \w+: (?:(?:{MONEY}) \+ )*({MONEY})", interest_section.split("Already settled")[0])
    sum_line = re.search(rf"Interest for \w+: ((?:{MONEY} \+ )+{MONEY}) = ({MONEY})", interest_section)
    if sum_line:
        addends = [parse_money(m) for m in re.findall(MONEY, sum_line[1])]
        assert sum(addends, D("0")) == parse_money(sum_line[2]) == period_sum
    else:
        assert parse_money(month_interest[1]) == period_sum
    added = re.search(rf"Interest added to the debt on \w+ \d+: ({MONEY})((?: - {MONEY})*)(?: = ({MONEY}))?", interest_section)
    assert added is not None
    if added[3]:
        subtracted = [parse_money(m) for m in re.findall(MONEY, added[2])]
        assert parse_money(added[1]) - sum(subtracted, D("0")) == parse_money(added[3])

    debt_section = _between(text, SECTION_HEADINGS[3], SECTION_HEADINGS[4])
    debt_part, owed_part = debt_section.split("Amount Owed on", 1)
    opening = parse_money(re.search(rf"Total Balance on \w+ \d+: ({MONEY})", debt_part)[1])
    running_total = opening
    closing = None
    for sign, money in re.findall(rf"(?:^|\s)([+=-]) (\$[\d,]+\.\d{{2}})", debt_part):
        value = parse_money(money)
        if sign == "+":
            running_total += value
        elif sign == "-":
            running_total -= value
        else:
            closing = value
    assert closing is not None and running_total == closing
    owed = re.search(rf"Total Balance ({MONEY}) \+ interest payable in cash ({MONEY}) = ({MONEY})", owed_part)
    assert parse_money(owed[1]) == closing
    assert parse_money(owed[1]) + parse_money(owed[2]) == parse_money(owed[3])


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_every_printed_equation_adds_up_in_every_month(scenario):
    month = date(2026, 10, 1)
    while month <= date(2027, 3, 1):
        document = _document(SCENARIOS[scenario], month)
        text = pdf_text(render_member_loan_statement_pdf(document.as_plain_dict()))
        assert_pdf_equations_add_up(text)
        month = first_day_of_next_month(month)


def test_the_six_sections_in_order_with_the_binding_sentence():
    document = _document(SCENARIOS["mid-month withdrawal"], date(2026, 12, 1))
    text = pdf_text(render_member_loan_statement_pdf(document.as_plain_dict(), sent_line="Sent on Jan 01, 2027 to a, b."))
    positions = [text.index(heading) for heading in SECTION_HEADINGS]
    assert positions == sorted(positions)
    assert " ".join(BINDING_STATEMENT_SENTENCE.split()) in text
    assert "Engine version 1." in text and "Ledger fingerprint: " + "f" * 64 in text
    assert "Sent on Jan 01, 2027" in text


def test_the_december_example_reads_as_agreed():
    document = _document(SCENARIOS["mid-month withdrawal"], date(2026, 12, 1))
    text = pdf_text(render_member_loan_statement_pdf(document.as_plain_dict()))
    assert (
        "Dec 15 – Aviv withdrew $1,000.00 (proposed by Aviv on Dec 15, approved by Yarden on Dec 15). "
        "It was taken from accrued interest ($144.77), then capitalized interest ($611.24), then principal ($243.99)."
    ) in text
    assert "Dec 1 – Dec 15: $31,021.24 × 1% × 14/30 = $144.77" in text
    assert "Dec 15 – Jan 1: $30,166.01 × 1% × 16/30 = $160.89" in text
    assert "Interest for December: $144.77 + $160.89 = $305.66" in text
    assert "= $30,326.90 Total Balance on Jan 1" in text
    for label, value in (("Total Balance on Dec 1", "$31,021.24"), ("Interest for December", "$305.66"),
                         ("Changes this month", "1"), ("Total Balance on Jan 1", "$30,326.90"), ("Amount Owed on Jan 1", "$30,326.90")):
        assert f"{label} {value}" in text


def test_a_yarden_increase_and_left_out_proposals_are_warned_about():
    document = _document(SCENARIOS["increase"], date(2026, 12, 1), proposals_left_out_count=2)
    text = pdf_text(render_member_loan_statement_pdf(document.as_plain_dict()))
    assert "The signed loan agreement has no clause for this kind of event" in text
    assert "2 proposed changes were still waiting for approval" in text
    assert 'Written agreement of 2026-12-01: "Signed by both members"' in text
    assert document.includes_yarden_additional_withdrawal


def test_30_360_days_are_explained_where_they_differ_from_the_calendar():
    document = _document(SCENARIOS["advance on feb 28"], date(2027, 2, 1))
    text = pdf_text(render_member_loan_statement_pdf(document.as_plain_dict()))
    assert "Feb 28 – Mar 1: $32,644.76 × 1% × 3/30 = $32.64 (30-day months: 1 calendar day counts as 3)" in text
    assert "a change on Feb 28 counts 3 days" in text


def test_a_cash_election_is_explained():
    document = _document(SCENARIOS["cash election then withdrawal"][:1], date(2026, 10, 1))
    assert any(
        "The interest for October ($304.10) goes to Aviv in cash instead of being added to the debt" in s
        for s in document.what_happened_sentences
    )
    assert document.amount_owed_lines[0] == (
        "Amount Owed on Nov 1 = Total Balance $30,410.00 + interest payable in cash $304.10 = $30,714.10"
    )


def test_text_is_escaped_before_it_reaches_the_pdf_markup():
    hostile = MemberLoanEventDescription(
        event_id="e1", event_type=LENDER_WITHDRAWAL, proposed_by_display_name="Aviv", proposed_on=date(2026, 12, 15),
        approved_by_display_name="Yarden", approved_on=date(2026, 12, 15), note="<b>bold</b> & <a href='x'>link</a>",
    )
    events = SCENARIOS["mid-month withdrawal"]
    figures = build_member_loan_monthly_statement_figures(DEFAULT_MEMBER_LOAN_TERMS, events, date(2026, 12, 1))
    document = build_member_loan_statement_document(
        figures, DEFAULT_MEMBER_LOAN_TERMS, lender_display_name="Aviv", yarden_display_name="Yarden", event_descriptions={"e1": hostile},
    )
    text = pdf_text(render_member_loan_statement_pdf(document.as_plain_dict()))
    assert "<b>bold</b> & <a href='x'>link</a>" in text
