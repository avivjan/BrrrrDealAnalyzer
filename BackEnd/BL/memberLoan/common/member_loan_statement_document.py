"""The monthly statement in plain words, built only from the engine's figures.

One document model feeds the PDF, the API and the e-mail, so they always say
the same thing. Every equation this module prints is re-checked with the same
numbers before the document is returned (`assert_printed_equations_add_up`),
and `tests/test_member_loan_statement.py` re-parses the PDF text and checks
them again.

Wording rules: short sentences, the members' names, money as "$1,234.56",
dates as "Dec 15". Only characters the PDF's built-in fonts can draw: "\u00d7" and "\u2013" are in
their character set, the Unicode minus sign is not, so negatives use a plain "-".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional, Sequence

from BL.memberLoan.common.member_loan_engine import (
    INTEREST_DAYS_IN_EVERY_MONTH,
    INTEREST_ELECTION_CASH,
    LENDER_ADDITIONAL_ADVANCE,
    LENDER_WITHDRAWAL,
    YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE,
    YARDEN_CAPITAL_CONTRIBUTION_REDUCTION,
    ZERO_DOLLARS,
    MemberLoanLedgerRow,
    MemberLoanMonthlyStatementFigures,
    MemberLoanStatementDoesNotAddUp,
    MemberLoanTerms,
    first_day_of_previous_month,
)

BINDING_STATEMENT_SENTENCE = (
    "This statement is binding unless either party objects in writing within 30 days after it is sent. "
    "An obvious calculation error may be corrected at any time."
)

YARDEN_INCREASE_WARNING = (
    "Warning: this statement includes an additional withdrawal by {yarden}. The signed loan agreement has no "
    "clause for this kind of event. It relies only on the separate written agreement cited next to it."
)

EVENT_TYPE_PLAIN_NAMES = {
    LENDER_WITHDRAWAL: "Withdrawal by {lender}",
    LENDER_ADDITIONAL_ADVANCE: "Additional loan by {lender}",
    YARDEN_CAPITAL_CONTRIBUTION_REDUCTION: "Capital contribution by {yarden}",
    YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE: "Additional withdrawal by {yarden}",
    "interest_payment_election": "Interest choice",
    "reversal": "Reversal",
}

BUCKET_PLAIN_LABELS = {
    "original_principal": "Principal",
    "capitalized_interest": "Capitalized interest",
    "total_balance": "Total Balance",
    "accrued_interest": "Accrued interest (not yet added to the debt)",
    "interest_payable": "Interest payable in cash",
    "amount_owed": "Amount Owed",
    "lender_capital_credited": "Credited to {lender}'s capital account",
}


def format_money(amount: Decimal) -> str:
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"


def format_short_date(calendar_date: date) -> str:
    return f"{calendar_date:%b} {calendar_date.day}"


def format_long_date(calendar_date: date) -> str:
    return f"{calendar_date:%b} {calendar_date.day}, {calendar_date.year}"


def format_month_label(month_start: date) -> str:
    return f"{month_start:%B %Y}"


def format_rate_percent(monthly_interest_rate: Decimal) -> str:
    return f"{(monthly_interest_rate * 100).normalize():f}%"


@dataclass(frozen=True)
class MemberLoanEventDescription:
    """Who proposed and approved an event, and its references. Text only, no figures."""

    event_id: str
    event_type: str
    proposed_by_display_name: str
    proposed_on: date
    approved_by_display_name: str
    approved_on: date
    effective_date: Optional[date] = None
    amount: Optional[Decimal] = None
    written_agreement_date: Optional[date] = None
    written_agreement_description: Optional[str] = None
    payment_reference: Optional[str] = None
    note: Optional[str] = None
    reversal_reason: Optional[str] = None
    reversed_event_description: Optional["MemberLoanEventDescription"] = None


@dataclass(frozen=True)
class MemberLoanStatementDocument:
    title: str
    statement_month_start: date
    statement_date: date
    summary_rows: tuple[tuple[str, str], ...]
    what_happened_sentences: tuple[str, ...]
    interest_period_lines: tuple[str, ...]
    interest_total_lines: tuple[str, ...]
    debt_equation_lines: tuple[str, ...]
    amount_owed_lines: tuple[str, ...]
    how_it_works_lines: tuple[str, ...]
    warnings: tuple[str, ...]
    binding_sentence: str
    engine_version: str
    ledger_fingerprint: str
    closing_buckets: dict = field(default_factory=dict)
    includes_yarden_additional_withdrawal: bool = False

    def as_plain_dict(self) -> dict:
        return {
            "title": self.title,
            "statement_month": self.statement_month_start.strftime("%Y-%m"),
            "statement_date": self.statement_date.isoformat(),
            "summary_rows": [list(row) for row in self.summary_rows],
            "what_happened_sentences": list(self.what_happened_sentences),
            "interest_period_lines": list(self.interest_period_lines),
            "interest_total_lines": list(self.interest_total_lines),
            "debt_equation_lines": list(self.debt_equation_lines),
            "amount_owed_lines": list(self.amount_owed_lines),
            "how_it_works_lines": list(self.how_it_works_lines),
            "warnings": list(self.warnings),
            "binding_sentence": self.binding_sentence,
            "engine_version": self.engine_version,
            "ledger_fingerprint": self.ledger_fingerprint,
            "closing_buckets": self.closing_buckets,
            "includes_yarden_additional_withdrawal": self.includes_yarden_additional_withdrawal,
        }


def member_loan_how_it_works_lines(terms: MemberLoanTerms, lender: str, yarden: str) -> tuple[str, ...]:
    rate = format_rate_percent(terms.monthly_interest_rate)
    yearly = format_rate_percent(terms.monthly_interest_rate * 12)
    return (
        f"Interest is {yearly} a year, which is {rate} a month.",
        f"Every month counts as 30 days, whatever its length on the calendar. So a full month always earns exactly {rate} of the Total Balance.",
        f"For part of a month, each day earns 1/30 of {rate}. A change on the 31st therefore earns no days that month, "
        "and a change on Feb 28 counts 3 days (2 days on Feb 29 in a leap year).",
        "The interest is worked out for each stretch of days between changes, rounded to the cent, and the stretches are added up.",
        f"On the 1st of each month the month's interest is added to the debt, so it earns interest too, unless {lender} chose to be paid that interest in cash.",
        "Interest stops on money from the day it is paid out, and starts on new money from the day it is added.",
        f"A withdrawal by {lender} is taken from interest payable in cash first, then accrued interest, then capitalized interest, then principal.",
        f"A capital contribution by {yarden} is taken from principal first, then capitalized interest, then accrued interest.",
        "Total Balance = principal + capitalized interest. Amount Owed = Total Balance + accrued interest + interest payable in cash.",
        f"Every change needs both members: one proposes it and the other approves it. A month's figures are final once its statement is sent.",
        f"The loan started on {format_long_date(terms.loan_effective_date)} with {format_money(terms.original_principal_at_start)} and is due on "
        f"{format_long_date(terms.maturity_date)}. Interest keeps running after that date until the loan is repaid.",
    )


def _approval_clause(description: Optional[MemberLoanEventDescription]) -> str:
    if description is None:
        return ""
    return (
        f" (proposed by {description.proposed_by_display_name} on {format_short_date(description.proposed_on)}, "
        f"approved by {description.approved_by_display_name} on {format_short_date(description.approved_on)})"
    )


def _references_clause(description: Optional[MemberLoanEventDescription]) -> str:
    if description is None:
        return ""
    parts = []
    if description.written_agreement_date and description.written_agreement_description:
        parts.append(
            f"Written agreement of {description.written_agreement_date.isoformat()}: \"{description.written_agreement_description}\"."
        )
    if description.payment_reference:
        parts.append(f"Payment reference: {description.payment_reference}.")
    if description.note:
        parts.append(f"Note: {description.note}.")
    return (" " + " ".join(parts)) if parts else ""


def _taken_from_clause(row: MemberLoanLedgerRow, order: Sequence[tuple[str, str]]) -> str:
    parts = []
    for attribute, plain in order:
        portion = getattr(row.allocation, attribute)
        if portion != ZERO_DOLLARS:
            parts.append(f"{plain} ({format_money(portion)})")
    if not parts:
        return ""
    if len(parts) == 1:
        return f"It was taken from {parts[0]}."
    return "It was taken from " + ", then ".join(parts) + "."


WITHDRAWAL_ORDER = (
    ("from_interest_payable", "interest payable in cash"),
    ("from_accrued_interest", "accrued interest"),
    ("from_capitalized_interest", "capitalized interest"),
    ("from_original_principal", "principal"),
)
REDUCTION_ORDER = (
    ("from_original_principal", "principal"),
    ("from_capitalized_interest", "capitalized interest"),
    ("from_accrued_interest", "accrued interest"),
    ("from_interest_payable", "interest payable in cash"),
)


def _event_sentence(row: MemberLoanLedgerRow, description: Optional[MemberLoanEventDescription], lender: str, yarden: str) -> str:
    when = format_short_date(row.row_date)
    approval = _approval_clause(description)
    references = _references_clause(description)
    amount = format_money(row.amount)
    if row.row_kind == LENDER_WITHDRAWAL:
        return f"{when} \u2013 {lender} withdrew {amount}{approval}. " + _taken_from_clause(row, WITHDRAWAL_ORDER) + references
    if row.row_kind == LENDER_ADDITIONAL_ADVANCE:
        return f"{when} \u2013 {lender} lent the company another {amount}{approval}. It was added to principal and earns interest from {when}." + references
    if row.row_kind == YARDEN_CAPITAL_CONTRIBUTION_REDUCTION:
        return (
            f"{when} \u2013 {yarden} put {amount} of capital into the company{approval}. It reduced the debt. "
            + _taken_from_clause(row, REDUCTION_ORDER)
            + f" The same {amount} is credited to {lender}'s capital account."
            + references
        )
    if row.row_kind == YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE:
        return (
            f"{when} \u2013 {yarden} withdrew {amount} from the company{approval}. Principal went up by {amount} and earns interest from {when}. "
            f"{lender}'s capital account is debited by the same {amount}." + references
        )
    return f"{when} \u2013 {row.row_kind}{approval}."  # pragma: no cover -- every engine row kind is handled above


def _event_short_label(row: MemberLoanLedgerRow, lender: str, yarden: str) -> str:
    return f"{format_short_date(row.row_date)} " + _plain_event_name_in_sentence(row.row_kind, lender, yarden)


def _plain_event_name_in_sentence(event_type: str, lender: str, yarden: str) -> str:
    """"Withdrawal by {lender}" -> "withdrawal by Aviv": lower-case the template, never the names."""
    template = EVENT_TYPE_PLAIN_NAMES[event_type]
    return (template[0].lower() + template[1:]).format(lender=lender, yarden=yarden)


def _period_line(period, rate_text: str) -> str:
    line = (
        f"{format_short_date(period.period_start_date)} \u2013 {format_short_date(period.period_end_date)}: "
        f"{format_money(period.balance_during_period)} \u00d7 {rate_text} \u00d7 {period.interest_days_counted}/{INTEREST_DAYS_IN_EVERY_MONTH} "
        f"= {format_money(period.interest_for_period)}"
    )
    calendar_days = (period.period_end_date - period.period_start_date).days
    if calendar_days != period.interest_days_counted:
        noun_and_verb = "calendar day counts" if calendar_days == 1 else "calendar days count"
        line += f" (30-day months: {calendar_days} {noun_and_verb} as {period.interest_days_counted})"
    return line


def build_member_loan_statement_document(
    figures: MemberLoanMonthlyStatementFigures,
    terms: MemberLoanTerms,
    *,
    lender_display_name: str,
    yarden_display_name: str,
    event_descriptions: dict[str, MemberLoanEventDescription],
    interest_election_description: Optional[MemberLoanEventDescription] = None,
    reversals_approved_in_month: Sequence[MemberLoanEventDescription] = (),
    proposals_left_out_count: int = 0,
    ledger_fingerprint: str = "",
) -> MemberLoanStatementDocument:
    lender, yarden = lender_display_name, yarden_display_name
    month_label = format_month_label(figures.statement_month_start)
    month_name = f"{figures.statement_month_start:%B}"
    statement_day = format_short_date(figures.statement_date)
    opening_day = format_short_date(figures.statement_month_start)
    closing_row = figures.closing_interest_date_row
    rate_text = format_rate_percent(figures.monthly_interest_rate)
    opening = figures.opening_buckets
    closing = figures.closing_buckets

    summary_rows = (
        (f"Total Balance on {opening_day}", format_money(opening.total_balance)),
        (f"Interest for {month_name}", format_money(figures.interest_earned_in_month)),
        ("Changes this month", str(len(figures.event_rows_in_month))),
        (f"Total Balance on {statement_day}", format_money(closing.total_balance)),
        (f"Amount Owed on {statement_day}", format_money(figures.amount_owed_on_statement_date)),
    )

    sentences = [_event_sentence(row, event_descriptions.get(row.event_id), lender, yarden) for row in figures.event_rows_in_month]
    for reversal in reversals_approved_in_month:
        original = reversal.reversed_event_description
        what = "an earlier change"
        if original is not None and original.amount is not None and original.effective_date is not None:
            what = (
                f"the {_plain_event_name_in_sentence(original.event_type, lender, yarden)} of "
                f"{format_short_date(original.effective_date)} ({format_money(original.amount)})"
            )
        sentences.append(
            f"{format_short_date(reversal.approved_on)} \u2013 {what[0].upper() + what[1:]} was reversed{_approval_clause(reversal)}. "
            f"It is not counted anywhere on this statement. Reason: {reversal.reversal_reason or 'not given'}."
        )
    if closing_row.interest_election_choice == INTEREST_ELECTION_CASH:
        sentences.append(
            f"{statement_day} \u2013 The interest for {month_name} ({format_money(closing_row.interest_moved_to_interest_payable)}) goes to {lender} in cash instead of being added to the debt, "
            f"as {lender} chose{_approval_clause(interest_election_description)}."
        )
    if not sentences:
        sentences.append("Nothing changed this month apart from the interest.")

    period_lines = tuple(_period_line(p, rate_text) for p in figures.interest_periods_in_month)
    period_amounts = [format_money(p.interest_for_period) for p in figures.interest_periods_in_month]
    interest_total_lines = []
    if len(period_amounts) > 1:
        interest_total_lines.append(
            f"Interest for {month_name}: " + " + ".join(period_amounts) + f" = {format_money(figures.interest_earned_in_month)}"
        )
    else:
        interest_total_lines.append(f"Interest for {month_name}: {format_money(figures.interest_earned_in_month)}")
    subtractions = []
    if closing_row.interest_already_settled_in_month != ZERO_DOLLARS:
        subtractions.append(closing_row.interest_already_settled_in_month)
        interest_total_lines.append(
            f"Already settled during the month by the changes above: {format_money(closing_row.interest_already_settled_in_month)}"
        )
    if closing_row.interest_moved_to_interest_payable != ZERO_DOLLARS:
        subtractions.append(closing_row.interest_moved_to_interest_payable)
        interest_total_lines.append(
            f"Moved to interest payable in cash on {statement_day}: {format_money(closing_row.interest_moved_to_interest_payable)}"
        )
    if subtractions:
        interest_total_lines.append(
            f"Interest added to the debt on {statement_day}: {format_money(figures.interest_earned_in_month)}"
            + "".join(f" - {format_money(s)}" for s in subtractions)
            + f" = {format_money(closing_row.interest_added_to_debt)}"
        )
    else:
        interest_total_lines.append(f"Interest added to the debt on {statement_day}: {format_money(closing_row.interest_added_to_debt)}")

    debt_lines = [f"Total Balance on {opening_day}: {format_money(opening.total_balance)}"]
    event_rows_by_id = {row.event_id: row for row in figures.event_rows_in_month}
    for step in figures.debt_equation_steps[1:-1]:
        row = event_rows_by_id[step.event_id]
        sign = "+" if step.signed_change_to_total_balance >= 0 else "-"
        detail = ""
        if row.allocation is not None and row.allocation.from_accrued_interest + row.allocation.from_interest_payable != ZERO_DOLLARS:
            detail = " (the part taken from interest not yet added to the debt does not change the Total Balance)"
        debt_lines.append(f"{sign} {format_money(abs(step.signed_change_to_total_balance))} {_event_short_label(row, lender, yarden)}{detail}")
    debt_lines.append(f"+ {format_money(closing_row.interest_added_to_debt)} interest added to the debt on {statement_day}")
    debt_lines.append(f"= {format_money(closing.total_balance)} Total Balance on {statement_day}")

    amount_owed_lines = (
        f"Amount Owed on {statement_day} = Total Balance {format_money(closing.total_balance)} "
        f"+ interest payable in cash {format_money(closing.interest_payable)} = {format_money(closing.amount_owed)}",
        f"Credited to {lender}'s capital account so far: {format_money(closing.lender_capital_credited)}",
    )

    includes_increase = any(r.row_kind == YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE for r in figures.event_rows_in_month)
    warnings = []
    if includes_increase:
        warnings.append(YARDEN_INCREASE_WARNING.format(yarden=yarden))
    if proposals_left_out_count:
        noun = "change was" if proposals_left_out_count == 1 else "changes were"
        warnings.append(
            f"{proposals_left_out_count} proposed {noun} still waiting for approval when this statement was made, so "
            f"{'it is' if proposals_left_out_count == 1 else 'they are'} not included."
        )

    closing_plain = closing.as_plain_dict()
    document = MemberLoanStatementDocument(
        title=f"Member Loan statement \u2013 {month_label}",
        statement_month_start=figures.statement_month_start,
        statement_date=figures.statement_date,
        summary_rows=summary_rows,
        what_happened_sentences=tuple(sentences),
        interest_period_lines=period_lines,
        interest_total_lines=tuple(interest_total_lines),
        debt_equation_lines=tuple(debt_lines),
        amount_owed_lines=amount_owed_lines,
        how_it_works_lines=member_loan_how_it_works_lines(terms, lender, yarden),
        warnings=tuple(warnings),
        binding_sentence=BINDING_STATEMENT_SENTENCE,
        engine_version=figures.engine_version,
        ledger_fingerprint=ledger_fingerprint,
        closing_buckets=closing_plain,
        includes_yarden_additional_withdrawal=includes_increase,
    )
    assert_printed_equations_add_up(document.interest_period_lines, document.interest_total_lines, document.debt_equation_lines, document.amount_owed_lines)
    return document


# -- checking the printed text ---------------------------------------------------

MONEY_PATTERN = r"-?\$[\d,]+\.\d{2}"


def parse_money(text: str) -> Decimal:
    negative = text.startswith("-")
    value = Decimal(text.lstrip("-").lstrip("$").replace(",", ""))
    return -value if negative else value


PERIOD_LINE_PATTERN = re.compile(rf"({MONEY_PATTERN}) \u00d7 ([\d.]+)% \u00d7 (\d+)/30 = ({MONEY_PATTERN})")
SUM_LINE_PATTERN = re.compile(rf": ((?:{MONEY_PATTERN} [+-] )+{MONEY_PATTERN}) = ({MONEY_PATTERN})$")
DEBT_STEP_PATTERN = re.compile(rf"^([+=\-]) ({MONEY_PATTERN}) ")
AMOUNT_OWED_PATTERN = re.compile(rf"Total Balance ({MONEY_PATTERN}) \+ interest payable in cash ({MONEY_PATTERN}) = ({MONEY_PATTERN})")


def assert_printed_equations_add_up(
    interest_period_lines: Sequence[str],
    interest_total_lines: Sequence[str],
    debt_equation_lines: Sequence[str],
    amount_owed_lines: Sequence[str],
) -> None:
    """Re-read the printed text and check every equation in it. Used on the
    document here and on the text extracted from the PDF in the tests."""

    from BL.memberLoan.common.member_loan_engine import round_half_up_to_cent

    for line in interest_period_lines:
        match = PERIOD_LINE_PATTERN.search(line)
        if match is None:
            raise MemberLoanStatementDoesNotAddUp(f"unreadable period line: {line}")
        balance, rate, days, interest = parse_money(match[1]), Decimal(match[2]) / 100, int(match[3]), parse_money(match[4])
        if round_half_up_to_cent(balance * rate * days / INTEREST_DAYS_IN_EVERY_MONTH) != interest:
            raise MemberLoanStatementDoesNotAddUp(f"period line does not add up: {line}")

    for line in interest_total_lines:
        match = SUM_LINE_PATTERN.search(line)
        if match is None:
            continue
        terms_text = match[1]
        tokens = re.findall(rf"([+-] )?({MONEY_PATTERN})", terms_text)
        total = Decimal("0")
        for sign, money in tokens:
            value = parse_money(money)
            total += -value if sign.strip() == "-" else value
        if total != parse_money(match[2]):
            raise MemberLoanStatementDoesNotAddUp(f"sum line does not add up: {line}")

    if interest_period_lines:
        period_total = sum(
            (parse_money(PERIOD_LINE_PATTERN.search(line)[4]) for line in interest_period_lines), Decimal("0")
        )
        first_total = re.search(rf"({MONEY_PATTERN})$", interest_total_lines[0])
        if first_total is None or parse_money(first_total[1]) != period_total:
            raise MemberLoanStatementDoesNotAddUp("the periods do not add up to the month's interest")

    opening = re.search(rf": ({MONEY_PATTERN})$", debt_equation_lines[0])
    if opening is None:
        raise MemberLoanStatementDoesNotAddUp("unreadable opening Total Balance")
    running_total = parse_money(opening[1])
    closing_total = None
    for line in debt_equation_lines[1:]:
        match = DEBT_STEP_PATTERN.search(line)
        if match is None:
            raise MemberLoanStatementDoesNotAddUp(f"unreadable debt step: {line}")
        value = parse_money(match[2])
        if match[1] == "+":
            running_total += value
        elif match[1] == "-":
            running_total -= value
        else:
            closing_total = value
    if closing_total is None or running_total != closing_total:
        raise MemberLoanStatementDoesNotAddUp(f"debt steps add up to {running_total}, statement says {closing_total}")

    owed = AMOUNT_OWED_PATTERN.search(amount_owed_lines[0])
    if owed is None or parse_money(owed[1]) + parse_money(owed[2]) != parse_money(owed[3]):
        raise MemberLoanStatementDoesNotAddUp("Amount Owed line does not add up")
    if parse_money(owed[1]) != closing_total:
        raise MemberLoanStatementDoesNotAddUp("Amount Owed uses a different Total Balance than the debt equation")


def previous_month_start(calendar_date: date) -> date:
    return first_day_of_previous_month(calendar_date.replace(day=1))
