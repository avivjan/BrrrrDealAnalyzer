"""What the members sign, as plain structured content (tasks/todo/MemberLoanSigning.md).

Two kinds of document:
  loan_change         a Loan Change Record: one per proposed change. It says
                      what changes, which section of the Agreement allows it,
                      the figures before and after, and what each member's
                      signature means.
  monthly_statement   the month's statement plus an acknowledgment page: the
                      Lender confirms the figures; Yarden, for the Borrower and
                      as Guarantor, acknowledges the debt and promises to pay.

The content is a plain dict, stored with the document. The PDF
(`member_loan_signing_pdf.py`) and the app's on-screen version are both drawn
from it, so what a member reads is what they sign. Wording follows Amendment
No. 1: Section 1.3 (agreeing), Section 2.3 (confirming a withdrawal or an
interest choice is not consent), Section 6.2 (sign or object).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from BL.memberLoan.common.member_loan_access import MemberLoanMember, MemberLoanMembers
from BL.memberLoan.common.member_loan_engine import (
    INTEREST_ELECTION_CASH,
    INTEREST_PAYMENT_ELECTION,
    LENDER_ADDITIONAL_ADVANCE,
    LENDER_WITHDRAWAL,
    REVERSAL,
    YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE,
    YARDEN_CAPITAL_CONTRIBUTION_REDUCTION,
    first_day_of_previous_month,
)
from BL.memberLoan.common.member_loan_statement_document import (
    BUCKET_PLAIN_LABELS,
    YARDEN_INCREASE_WARNING,
    format_long_date,
    format_money,
    format_month_label,
)

DOCUMENT_KIND_LOAN_CHANGE = "loan_change"
DOCUMENT_KIND_MONTHLY_STATEMENT = "monthly_statement"
SIGNATURE_MEANING_SIGNED = "signed"
SIGNATURE_MEANING_OBJECTED = "objected"
SIGNER_ROLE_LENDER_AND_MEMBER = "lender_and_member"
SIGNER_ROLE_MEMBER_FOR_BORROWER_AND_GUARANTOR = "member_for_borrower_and_guarantor"
SIGNER_ROLE_LABELS = {
    SIGNER_ROLE_LENDER_AND_MEMBER: "Lender and Member",
    SIGNER_ROLE_MEMBER_FOR_BORROWER_AND_GUARANTOR: "Member, for Big Whales AY LLC (Borrower), and personally as Guarantor",
}
BORROWER_LEGAL_NAME = "Big Whales AY LLC"
AGREEMENT_REFERENCE = (
    "the Loan Agreement signed on October 6, 2026 and effective as of October 1, 2026 between the Lender, "
    "the Borrower and the Guarantor, as amended by Amendment No. 1 (the \"Agreement\")"
)
EVENT_TYPES_WHOSE_COUNTERSIGNATURE_ONLY_CONFIRMS_FACTS = (LENDER_WITHDRAWAL, INTEREST_PAYMENT_ELECTION)
FIGURES_SHOWN_IN_A_CHANGE_RECORD = (
    "original_principal", "capitalized_interest", "total_balance", "accrued_interest", "interest_payable", "amount_owed",
    "lender_capital_credited",
)


def signer_role_for(member: MemberLoanMember, members: MemberLoanMembers) -> str:
    return SIGNER_ROLE_LENDER_AND_MEMBER if member.username == members.lender.username else SIGNER_ROLE_MEMBER_FOR_BORROWER_AND_GUARANTOR


def parties_lines(members: MemberLoanMembers) -> list[str]:
    return [
        f"Lender: {members.lender.legal_name}",
        f"Borrower: {BORROWER_LEGAL_NAME}, a Florida limited liability company",
        f"Guarantor: {members.yarden.legal_name}",
    ]


def plain_change_name_with_legal_names(event_type: str, members: MemberLoanMembers) -> str:
    return {
        LENDER_WITHDRAWAL: f"Withdrawal by {members.lender.legal_name}",
        LENDER_ADDITIONAL_ADVANCE: f"Additional loan by {members.lender.legal_name}",
        YARDEN_CAPITAL_CONTRIBUTION_REDUCTION: f"Capital contribution by {members.yarden.legal_name}",
        YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE: f"Additional withdrawal by {members.yarden.legal_name}",
        INTEREST_PAYMENT_ELECTION: "Interest choice",
        REVERSAL: "Reversal of an earlier change",
    }[event_type]


def _contract_basis_lines(change: dict, members: MemberLoanMembers) -> list[str]:
    lender, yarden = members.lender.legal_name, members.yarden.legal_name
    event_type = change["event_type"]
    if event_type == LENDER_WITHDRAWAL:
        return [
            "Section 6.1 of the Agreement: the Lender may withdraw all or any part of the Amount Owed at any time.",
            "Section 6.3, as replaced by Amendment No. 1, Section 2.6: the payment applies first to Interest Payable, then to "
            "Accrued Interest, then to Capitalized Interest, then to the Original Principal. Interest on the amount paid stops "
            "on the date it is paid (Section 4.5).",
            f"Amendment No. 1, Section 2.3: {yarden}'s signature only confirms that the notice was given and the payment was made. "
            "It is not consent.",
        ]
    if event_type == LENDER_ADDITIONAL_ADVANCE:
        return [
            "Section 2.2 of the Agreement, as replaced by Amendment No. 1, Section 3: the Lender may lend additional money on any "
            "day by written agreement signed by both Members. The amount is added to the Original Principal on the date the "
            "Borrower receives it and earns interest from that date.",
            "Amendment No. 1, Section 1.3: this Change Record, once signed by both Members, is that written agreement.",
        ]
    if event_type == YARDEN_CAPITAL_CONTRIBUTION_REDUCTION:
        return [
            f"Section 7 of the Agreement, as amended by Amendment No. 1, Section 4: a capital contribution by {yarden} that "
            f"{lender} does not match (an Unmatched Contribution) reduces the Original Principal, then Capitalized Interest, "
            "then Accrued Interest, then Interest Payable. Interest on each reduced amount stops on that date.",
            f"Section 7.2: no cash is paid to the Lender. The same amount is credited to {lender}'s capital account.",
        ]
    if event_type == YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE:
        return [
            f"Section 7A, added by Amendment No. 1, Section 5: money paid to {yarden} that {lender} does not receive equally "
            "(an Unmatched Withdrawal) is added to the Original Principal on the date it is received and earns interest from "
            f"that date. It is charged to {lender}'s capital account.",
            f"Section 7A.3: {lender}'s signature on this record is the written consent required by Section 6.5.",
        ]
    if event_type == INTEREST_PAYMENT_ELECTION:
        interest_date = date.fromisoformat(change["effective_date"])
        month = format_month_label(first_day_of_previous_month(interest_date))
        if change.get("interest_election_choice") == INTEREST_ELECTION_CASH:
            effect = (
                f"the interest for {month} is not added to the Total Balance on {format_long_date(interest_date)}. It stays owed "
                "as Interest Payable, earns no interest, and is paid first by the next withdrawal."
            )
        else:
            effect = (
                f"the interest for {month} is added to the Total Balance on {format_long_date(interest_date)} as Capitalized "
                "Interest and earns interest from that date (Section 4.3)."
            )
        return [
            f"Section 4.4 of the Agreement and Amendment No. 1, Section 2.4: the Lender chose that {effect}",
            f"Amendment No. 1, Section 2.3: {yarden}'s signature only confirms that the notice was given. It is not consent.",
        ]
    if event_type == REVERSAL:
        return [
            "Amendment No. 1, Section 1.6: a recorded change is never edited or deleted; a mistake is fixed only by a new record.",
            f"This record cancels Change Record No. {change['reversed_record_number']} ({change['reversed_change_summary']}) as if "
            "it had never been made, from its own date.",
        ]
    raise ValueError(f"no contract basis for {event_type}")


def _change_rows(change: dict, members: MemberLoanMembers) -> list[list[str]]:
    rows = [["Change", plain_change_name_with_legal_names(change["event_type"], members)]]
    if change.get("amount") is not None:
        rows.append(["Amount", format_money(Decimal(change["amount"]))])
    effective = date.fromisoformat(change["effective_date"])
    if change["event_type"] == INTEREST_PAYMENT_ELECTION:
        choice = "Paid in cash" if change.get("interest_election_choice") == INTEREST_ELECTION_CASH else "Added to the debt"
        rows.append(["Interest Date", format_long_date(effective)])
        rows.append(["Choice", choice])
    else:
        rows.append(["Date it takes effect", format_long_date(effective)])
    if change.get("written_agreement_date"):
        rows.append([
            "Written agreement",
            f"{format_long_date(date.fromisoformat(change['written_agreement_date']))}: {change.get('written_agreement_description') or ''}".strip(),
        ])
    if change.get("payment_reference"):
        rows.append(["Payment reference", change["payment_reference"]])
    if change["event_type"] == REVERSAL:
        rows.append(["Change it cancels", f"No. {change['reversed_record_number']}: {change['reversed_change_summary']}"])
        rows.append(["Reason", change.get("reversal_reason") or ""])
    if change.get("note"):
        rows.append(["Note", change["note"]])
    return rows


def _figures_rows(preview: dict, members: MemberLoanMembers) -> list[list[str]]:
    rows = []
    before, after = preview["buckets_before"], preview["buckets_after"]
    for key in FIGURES_SHOWN_IN_A_CHANGE_RECORD:
        if key in ("interest_payable", "lender_capital_credited") and before[key] == after[key] == "0.00":
            continue
        label = BUCKET_PLAIN_LABELS[key].format(lender=members.lender.legal_name)
        rows.append([label, format_money(Decimal(before[key])), format_money(Decimal(after[key]))])
    return rows


def _allocation_lines(preview: dict, change: dict) -> list[str]:
    allocation = preview.get("allocation")
    if not allocation:
        return []
    parts = [
        (allocation["from_interest_payable"], "Interest Payable"),
        (allocation["from_accrued_interest"], "Accrued Interest"),
        (allocation["from_capitalized_interest"], "Capitalized Interest"),
        (allocation["from_original_principal"], "the Original Principal"),
    ]
    if change["event_type"] == YARDEN_CAPITAL_CONTRIBUTION_REDUCTION:
        parts = [parts[3], parts[2], parts[1], parts[0]]
    taken = [f"{format_money(Decimal(amount))} from {label}" for amount, label in parts if Decimal(amount) != 0]
    return ["It is applied as follows: " + ", then ".join(taken) + "."] if taken else []


def proposer_statement_text(proposer: MemberLoanMember, members: MemberLoanMembers) -> str:
    role = SIGNER_ROLE_LABELS[signer_role_for(proposer, members)]
    return (
        f"I, {proposer.legal_name}, propose this change to the Agreement and sign this Change Record as {role}. "
        "I confirm that the facts stated in it are true."
    )


def counterparty_statement_text(change: dict, counterparty: MemberLoanMember, members: MemberLoanMembers) -> str:
    role = SIGNER_ROLE_LABELS[signer_role_for(counterparty, members)]
    if change["event_type"] in EVENT_TYPES_WHOSE_COUNTERSIGNATURE_ONLY_CONFIRMS_FACTS:
        if change["event_type"] == LENDER_WITHDRAWAL:
            facts = (
                f"that the notice was given and that {format_money(Decimal(change['amount']))} was paid to "
                f"{members.lender.legal_name} on {format_long_date(date.fromisoformat(change['effective_date']))}"
            )
        else:
            facts = f"that {members.lender.legal_name} gave notice of this interest choice"
        return (
            f"I, {counterparty.legal_name}, signing as {role}, confirm {facts}. Under Section 2.3 of Amendment No. 1, this "
            "is a confirmation of fact, not consent."
        )
    return (
        f"I, {counterparty.legal_name}, agree to this change and sign as {role}. This Change Record is a written agreement "
        "signed by both Members under Section 1.3 of Amendment No. 1. Every other term of the Agreement stays unchanged."
    )


def build_loan_change_document_content(
    *,
    change: dict,
    preview: dict,
    record_number: int,
    proposer: MemberLoanMember,
    members: MemberLoanMembers,
    prepared_on: date,
) -> dict:
    """`change` holds the proposal's fields as plain text (amounts "1000.00", dates ISO)."""

    counterparty = members.other_than(proposer)
    warnings = []
    if change["event_type"] == YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE or change.get("reversed_event_type") == YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE:
        warnings.append(YARDEN_INCREASE_WARNING.format(yarden=members.yarden.legal_name).replace("this statement", "this record"))
    signers = [
        {
            "username": proposer.username,
            "legal_name": proposer.legal_name,
            "role": signer_role_for(proposer, members),
            "role_label": SIGNER_ROLE_LABELS[signer_role_for(proposer, members)],
            "signs_as": "proposer",
            "statement_text": proposer_statement_text(proposer, members),
        },
        {
            "username": counterparty.username,
            "legal_name": counterparty.legal_name,
            "role": signer_role_for(counterparty, members),
            "role_label": SIGNER_ROLE_LABELS[signer_role_for(counterparty, members)],
            "signs_as": "counterparty",
            "statement_text": counterparty_statement_text(change, counterparty, members),
        },
    ]
    name = plain_change_name_with_legal_names(change["event_type"], members)
    return {
        "document_kind": DOCUMENT_KIND_LOAN_CHANGE,
        "title": f"Loan Change Record No. {record_number} – {name}",
        "record_number": record_number,
        "prepared_on": prepared_on.isoformat(),
        "agreement_reference": f"This Change Record is made under {AGREEMENT_REFERENCE}.",
        "parties_lines": parties_lines(members),
        "change": change,
        "change_rows": _change_rows(change, members),
        "contract_basis_lines": _contract_basis_lines(change, members),
        "figures_effective_date": preview["effective_date"],
        "figures_rows": _figures_rows(preview, members),
        "allocation_lines": _allocation_lines(preview, change),
        "effect_lines": [
            "This record updates the existing loan. Every other term of the Agreement stays unchanged.",
            "Nothing changes until both Members have signed it. The change then takes effect on the date shown above.",
            "If other changes alter these figures before the second signature, this record can no longer be signed and the "
            "change must be proposed again.",
        ],
        "warnings": warnings,
        "preview_fingerprint": preview["preview_fingerprint"],
        "signers": signers,
    }


# -- monthly statement ----------------------------------------------------------------


def lender_statement_acknowledgment_text(members: MemberLoanMembers, month_label: str) -> str:
    return (
        f"I, {members.lender.legal_name}, Lender, have reviewed this statement for {month_label}. I confirm that its figures are "
        "correct and I have no objection to it."
    )


def yarden_statement_acknowledgment_text(members: MemberLoanMembers, month_label: str, amount_owed: str, statement_date: date) -> str:
    when = format_long_date(statement_date)
    items = [
        f"I, {members.yarden.legal_name}, sign for {BORROWER_LEGAL_NAME} as its Member and personally as Guarantor. For "
        f"the statement for {month_label}:",
        "1. The figures in this statement are correct and I have no objection to it.",
        f"2. The Borrower owes the Lender the Amount Owed of {amount_owed} as of {when}, plus interest from that date under the Agreement.",
        "3. This amount is owed without any defense, offset or counterclaim. Any that existed on this date are waived.",
        "4. The Borrower promises to pay it as the Agreement requires, including on demand under Section 6.1 and on the Maturity Date.",
        "5. The personal guarantee in Section 10 of the Agreement, and the security in Section 8 of Amendment No. 1, remain in full "
        "force for this amount.",
        "6. This is a written acknowledgment of the debt.",
    ]
    return "\n".join(items)


def objection_statement_text(member: MemberLoanMember, month_label: str, reason: str) -> str:
    return (
        f"I, {member.legal_name}, object in writing to the statement for {month_label} under Section 8.3 of the Agreement "
        f"for this reason: {reason}"
    )


def build_statement_signing_document_content(*, statement_document: dict, members: MemberLoanMembers, sent_line: str) -> dict:
    month_start = date.fromisoformat(statement_document["statement_month"] + "-01")
    month_label = format_month_label(month_start)
    statement_date = date.fromisoformat(statement_document["statement_date"])
    amount_owed = statement_document["summary_rows"][-1][1]
    return {
        "document_kind": DOCUMENT_KIND_MONTHLY_STATEMENT,
        "title": f"Member Loan statement – {month_label}",
        "statement_month": statement_document["statement_month"],
        "month_label": month_label,
        "statement_date": statement_document["statement_date"],
        "amount_owed": amount_owed,
        "sent_line": sent_line,
        "statement_document": statement_document,
        "acknowledgment_intro_lines": [
            f"This page is part of the statement for {month_label} sent under Section 8.1 of the Agreement.",
            "Each Member may sign it to confirm the statement, or object to it in writing with the reason (Amendment No. 1, "
            "Section 6.2).",
            "Signing is not required: under Section 8.3 the statement becomes binding 30 days after it is sent unless a party "
            "objects in writing (Amendment No. 1, Section 6.3).",
        ],
        "signers": [
            {
                "username": members.lender.username,
                "legal_name": members.lender.legal_name,
                "role": SIGNER_ROLE_LENDER_AND_MEMBER,
                "role_label": "Lender",
                "statement_text": lender_statement_acknowledgment_text(members, month_label),
            },
            {
                "username": members.yarden.username,
                "legal_name": members.yarden.legal_name,
                "role": SIGNER_ROLE_MEMBER_FOR_BORROWER_AND_GUARANTOR,
                "role_label": SIGNER_ROLE_LABELS[SIGNER_ROLE_MEMBER_FOR_BORROWER_AND_GUARANTOR],
                "statement_text": yarden_statement_acknowledgment_text(members, month_label, amount_owed, statement_date),
            },
        ],
    }


def signer_entry(content: dict, username: str) -> Optional[dict]:
    return next((s for s in content["signers"] if s["username"] == username), None)
