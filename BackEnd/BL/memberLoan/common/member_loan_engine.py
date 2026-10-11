"""The Member Loan calculation engine: pure, `Decimal` only, whole cents.

The signed loan agreement between Aviv Jan (Lender) and Big Whales AY LLC
(Borrower) names this app as the deciding calculator, so this module is the
single place the loan's numbers come from. It never touches the database,
FastAPI or the clock: callers pass the loan terms, the *effective* events
(approved and not reversed) and the date they want.

Rules (tasks/todo/MemberLoan.md, decisions D4, D7, D10, D15, rules R1 to R5):

* 30/360 day count (R1). Every month counts as 30 days, so a full month earns
  exactly 1% of the Total Balance whatever its calendar length. A day's
  position in its month is ``min(day - 1, 30)``; the next Interest Date (the
  1st) is position 30. A period from ``a`` to ``b`` earns
  ``balance x 1% x (position(b) - position(a)) / 30``.
* Each event, on any day (D15), closes the running period and opens a new one
  at the new balance, so interest starts or stops on the event date.
* Rounding (R4): each period's interest is rounded half-up to the cent when the
  period closes; a month's interest is the sum of those cent amounts.
* On each Interest Date the month's remaining accrued interest is added to
  Capitalized Interest, or, when the Lender elected cash for that date, to the
  non-compounding Interest payable line (D10). That day's events come after.
* A Lender withdrawal is taken from Interest payable, then Accrued Interest,
  then Capitalized Interest, then Original Principal (R3). A Yarden capital
  contribution is taken from Original Principal, then Capitalized Interest,
  then Accrued Interest, then Interest payable (D7, R3). Neither may exceed
  the Amount Owed on its date.
* Interest keeps accruing after maturity (D4).

`float` never appears in this module; `tests/test_member_loan_engine.py`
asserts that.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Optional, Sequence

# Bump whenever any rule in this module changes the arithmetic. Stored with
# every sent statement so a later engine change can be traced.
MEMBER_LOAN_ENGINE_VERSION = "1"

ONE_CENT = Decimal("0.01")
ZERO_DOLLARS = Decimal("0.00")
INTEREST_DAYS_IN_EVERY_MONTH = 30
LARGEST_ALLOWED_EVENT_AMOUNT = Decimal("10000000.00")

LENDER_WITHDRAWAL = "lender_withdrawal"
LENDER_ADDITIONAL_ADVANCE = "lender_additional_advance"
YARDEN_CAPITAL_CONTRIBUTION_REDUCTION = "yarden_capital_contribution_reduction"
YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE = "yarden_additional_withdrawal_increase"
INTEREST_PAYMENT_ELECTION = "interest_payment_election"
REVERSAL = "reversal"

EVENT_TYPES_THAT_CARRY_AN_AMOUNT = (
    LENDER_WITHDRAWAL,
    LENDER_ADDITIONAL_ADVANCE,
    YARDEN_CAPITAL_CONTRIBUTION_REDUCTION,
    YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE,
)
EVENT_TYPES_THE_ENGINE_APPLIES = EVENT_TYPES_THAT_CARRY_AN_AMOUNT + (INTEREST_PAYMENT_ELECTION,)
ALL_MEMBER_LOAN_EVENT_TYPES = EVENT_TYPES_THE_ENGINE_APPLIES + (REVERSAL,)

INTEREST_ELECTION_REINVEST = "reinvest"
INTEREST_ELECTION_CASH = "cash"
INTEREST_ELECTION_CHOICES = (INTEREST_ELECTION_REINVEST, INTEREST_ELECTION_CASH)

LEDGER_ROW_KIND_LOAN_START = "loan_start"
LEDGER_ROW_KIND_INTEREST_DATE = "interest_date"


class MemberLoanEventRejected(ValueError):
    """An event cannot be applied. The message is plain language for the members."""

    def __init__(self, plain_language_reason: str, event_id: Optional[str] = None):
        super().__init__(plain_language_reason)
        self.plain_language_reason = plain_language_reason
        self.event_id = event_id


def round_half_up_to_cent(value: Decimal) -> Decimal:
    return value.quantize(ONE_CENT, rounding=ROUND_HALF_UP)


def first_day_of_month(calendar_date: date) -> date:
    return calendar_date.replace(day=1)


def first_day_of_next_month(calendar_date: date) -> date:
    if calendar_date.month == 12:
        return date(calendar_date.year + 1, 1, 1)
    return date(calendar_date.year, calendar_date.month + 1, 1)


def first_day_of_previous_month(calendar_date: date) -> date:
    if calendar_date.month == 1:
        return date(calendar_date.year - 1, 12, 1)
    return date(calendar_date.year, calendar_date.month - 1, 1)


def day_position_in_interest_month(calendar_date: date) -> int:
    """30/360 position: the 1st is 0, the 15th is 14, the 30th is 29, the 31st is 30."""
    return min(calendar_date.day - 1, INTEREST_DAYS_IN_EVERY_MONTH)


def interest_days_between(period_start_date: date, period_end_date: date) -> int:
    """30/360 days from `period_start_date` up to `period_end_date`.

    The end is either a later date in the same month or the next Interest Date
    (the 1st of the following month), which counts as position 30.
    """
    if period_end_date == first_day_of_next_month(period_start_date):
        end_position = INTEREST_DAYS_IN_EVERY_MONTH
    elif first_day_of_month(period_end_date) == first_day_of_month(period_start_date):
        end_position = day_position_in_interest_month(period_end_date)
    else:  # pragma: no cover -- the walker never builds a period across an Interest Date
        raise AssertionError(f"a period cannot span an Interest Date: {period_start_date} to {period_end_date}")
    return end_position - day_position_in_interest_month(period_start_date)


@dataclass(frozen=True)
class MemberLoanTerms:
    loan_effective_date: date
    original_principal_at_start: Decimal
    monthly_interest_rate: Decimal
    maturity_date: date

    def __post_init__(self) -> None:
        if self.loan_effective_date.day != 1:
            raise ValueError("the loan must start on the 1st of a month")
        if self.original_principal_at_start != round_half_up_to_cent(self.original_principal_at_start):
            raise ValueError("the original principal must be whole cents")
        if self.original_principal_at_start <= ZERO_DOLLARS:
            raise ValueError("the original principal must be above zero")


DEFAULT_MEMBER_LOAN_TERMS = MemberLoanTerms(
    loan_effective_date=date(2026, 10, 1),
    original_principal_at_start=Decimal("30410.00"),
    monthly_interest_rate=Decimal("0.01"),
    maturity_date=date(2027, 10, 1),
)


@dataclass(frozen=True)
class EffectiveMemberLoanEvent:
    """An approved, not reversed event, as the engine needs it.

    `application_order` breaks ties between events on the same day: the
    approval sequence (R5). A candidate being previewed gets the next number.
    """

    event_id: str
    event_type: str
    effective_date: date
    application_order: int
    amount: Optional[Decimal] = None
    interest_election_choice: Optional[str] = None

    def canonical_dict(self) -> dict[str, Optional[str]]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "effective_date": self.effective_date.isoformat(),
            "amount": None if self.amount is None else f"{self.amount:.2f}",
            "interest_election_choice": self.interest_election_choice,
        }


@dataclass(frozen=True)
class MemberLoanBuckets:
    original_principal: Decimal
    capitalized_interest: Decimal
    accrued_interest: Decimal
    interest_payable: Decimal
    lender_capital_credited: Decimal

    @property
    def total_balance(self) -> Decimal:
        return self.original_principal + self.capitalized_interest

    @property
    def amount_owed(self) -> Decimal:
        return self.total_balance + self.accrued_interest + self.interest_payable

    def as_plain_dict(self) -> dict[str, str]:
        return {
            "original_principal": f"{self.original_principal:.2f}",
            "capitalized_interest": f"{self.capitalized_interest:.2f}",
            "total_balance": f"{self.total_balance:.2f}",
            "accrued_interest": f"{self.accrued_interest:.2f}",
            "interest_payable": f"{self.interest_payable:.2f}",
            "amount_owed": f"{self.amount_owed:.2f}",
            "lender_capital_credited": f"{self.lender_capital_credited:.2f}",
        }


@dataclass(frozen=True)
class MemberLoanBucketAllocation:
    """How an amount taken off the debt was split across the buckets."""

    from_interest_payable: Decimal = ZERO_DOLLARS
    from_accrued_interest: Decimal = ZERO_DOLLARS
    from_capitalized_interest: Decimal = ZERO_DOLLARS
    from_original_principal: Decimal = ZERO_DOLLARS

    @property
    def total_taken(self) -> Decimal:
        return self.from_interest_payable + self.from_accrued_interest + self.from_capitalized_interest + self.from_original_principal

    def as_plain_dict(self) -> dict[str, str]:
        return {
            "from_interest_payable": f"{self.from_interest_payable:.2f}",
            "from_accrued_interest": f"{self.from_accrued_interest:.2f}",
            "from_capitalized_interest": f"{self.from_capitalized_interest:.2f}",
            "from_original_principal": f"{self.from_original_principal:.2f}",
        }


@dataclass(frozen=True)
class MemberLoanInterestPeriod:
    period_start_date: date
    # Exclusive: the event date or the next Interest Date that closed the period.
    period_end_date: date
    interest_date_the_period_belongs_to: date
    balance_during_period: Decimal
    interest_days_counted: int
    interest_for_period: Decimal


@dataclass(frozen=True)
class MemberLoanLedgerRow:
    row_date: date
    # `loan_start`, `interest_date`, or the event type.
    row_kind: str
    buckets_before: MemberLoanBuckets
    buckets_after: MemberLoanBuckets
    event_id: Optional[str] = None
    amount: Optional[Decimal] = None
    allocation: Optional[MemberLoanBucketAllocation] = None
    interest_election_choice: Optional[str] = None
    # Interest Date rows only: the month that just ended.
    interest_earned_in_month: Decimal = ZERO_DOLLARS
    interest_already_settled_in_month: Decimal = ZERO_DOLLARS
    interest_added_to_debt: Decimal = ZERO_DOLLARS
    interest_moved_to_interest_payable: Decimal = ZERO_DOLLARS


@dataclass(frozen=True)
class MemberLoanPosition:
    """The loan as of one date, after that date's events."""

    as_of_date: date
    buckets: MemberLoanBuckets
    ledger_rows: tuple[MemberLoanLedgerRow, ...]
    interest_periods: tuple[MemberLoanInterestPeriod, ...]


def _validate_event_shape(terms: MemberLoanTerms, event: EffectiveMemberLoanEvent) -> None:
    if event.event_type not in EVENT_TYPES_THE_ENGINE_APPLIES:
        raise MemberLoanEventRejected(f"Unknown event type: {event.event_type}.", event.event_id)
    if event.effective_date < terms.loan_effective_date:
        raise MemberLoanEventRejected(
            f"The date {event.effective_date.isoformat()} is before the loan started on {terms.loan_effective_date.isoformat()}.",
            event.event_id,
        )
    if event.event_type in EVENT_TYPES_THAT_CARRY_AN_AMOUNT:
        amount = event.amount
        if amount is None or not isinstance(amount, Decimal):
            raise MemberLoanEventRejected("An amount is required.", event.event_id)
        if amount != round_half_up_to_cent(amount):
            raise MemberLoanEventRejected("The amount must be in whole cents.", event.event_id)
        if amount <= ZERO_DOLLARS:
            raise MemberLoanEventRejected("The amount must be more than $0.00.", event.event_id)
        if amount > LARGEST_ALLOWED_EVENT_AMOUNT:
            raise MemberLoanEventRejected("The amount is too large.", event.event_id)
    if event.event_type == INTEREST_PAYMENT_ELECTION:
        if event.interest_election_choice not in INTEREST_ELECTION_CHOICES:
            raise MemberLoanEventRejected("The interest choice must be 'reinvest' or 'cash'.", event.event_id)
        if event.effective_date.day != 1 or event.effective_date <= terms.loan_effective_date:
            raise MemberLoanEventRejected(
                "An interest choice must be for an Interest Date: the 1st of a month after the loan started.",
                event.event_id,
            )


class _MemberLoanTimelineWalker:
    """Walks the loan day by day (in jumps) from its start to a target date."""

    def __init__(self, terms: MemberLoanTerms, events: Sequence[EffectiveMemberLoanEvent]):
        self.terms = terms
        for event in events:
            _validate_event_shape(terms, event)
        self.events_in_order = sorted(events, key=lambda e: (e.effective_date, e.application_order))
        self.interest_choice_by_interest_date: dict[date, str] = {}
        for election in sorted(
            (e for e in events if e.event_type == INTEREST_PAYMENT_ELECTION), key=lambda e: e.application_order
        ):
            self.interest_choice_by_interest_date[election.effective_date] = election.interest_election_choice or INTEREST_ELECTION_REINVEST

        self.original_principal = terms.original_principal_at_start
        self.capitalized_interest = ZERO_DOLLARS
        self.accrued_interest_from_closed_periods = ZERO_DOLLARS
        self.interest_payable = ZERO_DOLLARS
        self.lender_capital_credited = ZERO_DOLLARS
        self.open_period_start_date = terms.loan_effective_date
        self.interest_earned_in_current_month = ZERO_DOLLARS
        self.interest_settled_in_current_month = ZERO_DOLLARS
        self.interest_periods: list[MemberLoanInterestPeriod] = []
        zero_buckets = MemberLoanBuckets(ZERO_DOLLARS, ZERO_DOLLARS, ZERO_DOLLARS, ZERO_DOLLARS, ZERO_DOLLARS)
        self.ledger_rows: list[MemberLoanLedgerRow] = [
            MemberLoanLedgerRow(
                row_date=terms.loan_effective_date,
                row_kind=LEDGER_ROW_KIND_LOAN_START,
                buckets_before=zero_buckets,
                buckets_after=self._current_buckets(),
                amount=terms.original_principal_at_start,
            )
        ]

    # -- state ---------------------------------------------------------------

    def _total_balance(self) -> Decimal:
        return self.original_principal + self.capitalized_interest

    def _current_buckets(self) -> MemberLoanBuckets:
        return MemberLoanBuckets(
            original_principal=self.original_principal,
            capitalized_interest=self.capitalized_interest,
            accrued_interest=self.accrued_interest_from_closed_periods,
            interest_payable=self.interest_payable,
            lender_capital_credited=self.lender_capital_credited,
        )

    def _interest_for(self, balance: Decimal, interest_days: int) -> Decimal:
        return round_half_up_to_cent(
            balance * self.terms.monthly_interest_rate * interest_days / INTEREST_DAYS_IN_EVERY_MONTH
        )

    # -- periods and Interest Dates -------------------------------------------

    def _close_open_period_at(self, period_end_date: date, interest_date_the_period_belongs_to: date) -> None:
        if period_end_date <= self.open_period_start_date:
            return
        balance = self._total_balance()
        interest_days = interest_days_between(self.open_period_start_date, period_end_date)
        interest = self._interest_for(balance, interest_days)
        self.interest_periods.append(
            MemberLoanInterestPeriod(
                period_start_date=self.open_period_start_date,
                period_end_date=period_end_date,
                interest_date_the_period_belongs_to=interest_date_the_period_belongs_to,
                balance_during_period=balance,
                interest_days_counted=interest_days,
                interest_for_period=interest,
            )
        )
        self.accrued_interest_from_closed_periods += interest
        self.interest_earned_in_current_month += interest
        self.open_period_start_date = period_end_date

    def _process_interest_date(self, interest_date: date) -> None:
        self._close_open_period_at(interest_date, interest_date)
        buckets_before = self._current_buckets()
        interest_to_move = self.accrued_interest_from_closed_periods
        choice = self.interest_choice_by_interest_date.get(interest_date, INTEREST_ELECTION_REINVEST)
        moved_to_payable = ZERO_DOLLARS
        added_to_debt = ZERO_DOLLARS
        if choice == INTEREST_ELECTION_CASH:
            self.interest_payable += interest_to_move
            moved_to_payable = interest_to_move
        else:
            self.capitalized_interest += interest_to_move
            added_to_debt = interest_to_move
        self.accrued_interest_from_closed_periods = ZERO_DOLLARS
        self.ledger_rows.append(
            MemberLoanLedgerRow(
                row_date=interest_date,
                row_kind=LEDGER_ROW_KIND_INTEREST_DATE,
                buckets_before=buckets_before,
                buckets_after=self._current_buckets(),
                interest_election_choice=choice,
                interest_earned_in_month=self.interest_earned_in_current_month,
                interest_already_settled_in_month=self.interest_settled_in_current_month,
                interest_added_to_debt=added_to_debt,
                interest_moved_to_interest_payable=moved_to_payable,
            )
        )
        self.interest_earned_in_current_month = ZERO_DOLLARS
        self.interest_settled_in_current_month = ZERO_DOLLARS
        self.open_period_start_date = interest_date

    # -- events -------------------------------------------------------------

    def _take_from_buckets(self, amount: Decimal, bucket_order: Sequence[str]) -> MemberLoanBucketAllocation:
        remaining = amount
        taken: dict[str, Decimal] = {}
        for bucket in bucket_order:
            available = getattr(self, bucket)
            portion = min(remaining, available)
            setattr(self, bucket, available - portion)
            taken[bucket] = portion
            remaining -= portion
        if remaining != ZERO_DOLLARS:  # pragma: no cover -- guarded by the Amount Owed check before
            raise AssertionError("an allocation exceeded the Amount Owed")
        return MemberLoanBucketAllocation(
            from_interest_payable=taken.get("interest_payable", ZERO_DOLLARS),
            from_accrued_interest=taken.get("accrued_interest_from_closed_periods", ZERO_DOLLARS),
            from_capitalized_interest=taken.get("capitalized_interest", ZERO_DOLLARS),
            from_original_principal=taken.get("original_principal", ZERO_DOLLARS),
        )

    def _apply_event(self, event: EffectiveMemberLoanEvent) -> None:
        self._close_open_period_at(event.effective_date, first_day_of_next_month(event.effective_date))
        buckets_before = self._current_buckets()
        amount = event.amount
        allocation: Optional[MemberLoanBucketAllocation] = None
        if event.event_type == LENDER_WITHDRAWAL:
            if amount > buckets_before.amount_owed:
                raise MemberLoanEventRejected(
                    f"A withdrawal of ${amount:,.2f} on {event.effective_date.isoformat()} is more than the "
                    f"${buckets_before.amount_owed:,.2f} owed on that date.",
                    event.event_id,
                )
            allocation = self._take_from_buckets(
                amount,
                ("interest_payable", "accrued_interest_from_closed_periods", "capitalized_interest", "original_principal"),
            )
            self.interest_settled_in_current_month += allocation.from_accrued_interest
        elif event.event_type == LENDER_ADDITIONAL_ADVANCE:
            self.original_principal += amount
        elif event.event_type == YARDEN_CAPITAL_CONTRIBUTION_REDUCTION:
            if amount > buckets_before.amount_owed:
                raise MemberLoanEventRejected(
                    f"A capital contribution of ${amount:,.2f} on {event.effective_date.isoformat()} is more than the "
                    f"${buckets_before.amount_owed:,.2f} owed on that date.",
                    event.event_id,
                )
            allocation = self._take_from_buckets(
                amount,
                ("original_principal", "capitalized_interest", "accrued_interest_from_closed_periods", "interest_payable"),
            )
            self.interest_settled_in_current_month += allocation.from_accrued_interest
            self.lender_capital_credited += amount
        elif event.event_type == YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE:
            self.original_principal += amount
            self.lender_capital_credited -= amount
        # INTEREST_PAYMENT_ELECTION changes nothing on its own date; the walker
        # consulted it in `interest_choice_by_interest_date`.
        self.ledger_rows.append(
            MemberLoanLedgerRow(
                row_date=event.effective_date,
                row_kind=event.event_type,
                buckets_before=buckets_before,
                buckets_after=self._current_buckets(),
                event_id=event.event_id,
                amount=amount,
                allocation=allocation,
                interest_election_choice=event.interest_election_choice,
            )
        )

    # -- driver -------------------------------------------------------------

    def walk_through(self, as_of_date: date) -> MemberLoanPosition:
        if as_of_date < self.terms.loan_effective_date:
            raise MemberLoanEventRejected(
                f"The date {as_of_date.isoformat()} is before the loan started on {self.terms.loan_effective_date.isoformat()}."
            )
        next_interest_date = first_day_of_next_month(self.terms.loan_effective_date)
        for event in self.events_in_order:
            if event.effective_date > as_of_date:
                break
            while next_interest_date <= event.effective_date:
                self._process_interest_date(next_interest_date)
                next_interest_date = first_day_of_next_month(next_interest_date)
            self._apply_event(event)
        while next_interest_date <= as_of_date:
            self._process_interest_date(next_interest_date)
            next_interest_date = first_day_of_next_month(next_interest_date)

        accrued_interest_as_of_date = self.accrued_interest_from_closed_periods
        if as_of_date > self.open_period_start_date:
            accrued_interest_as_of_date += self._interest_for(
                self._total_balance(), interest_days_between(self.open_period_start_date, as_of_date)
            )
        buckets = MemberLoanBuckets(
            original_principal=self.original_principal,
            capitalized_interest=self.capitalized_interest,
            accrued_interest=accrued_interest_as_of_date,
            interest_payable=self.interest_payable,
            lender_capital_credited=self.lender_capital_credited,
        )
        return MemberLoanPosition(
            as_of_date=as_of_date,
            buckets=buckets,
            ledger_rows=tuple(self.ledger_rows),
            interest_periods=tuple(self.interest_periods),
        )


def calculate_member_loan_position(
    terms: MemberLoanTerms, effective_events: Iterable[EffectiveMemberLoanEvent], as_of_date: date
) -> MemberLoanPosition:
    """The loan as of `as_of_date`, after every effective event dated that day."""

    return _MemberLoanTimelineWalker(terms, list(effective_events)).walk_through(as_of_date)


def latest_relevant_date(terms: MemberLoanTerms, events: Iterable[EffectiveMemberLoanEvent]) -> date:
    return max([terms.loan_effective_date] + [e.effective_date for e in events])


def validate_member_loan_events(terms: MemberLoanTerms, effective_events: Sequence[EffectiveMemberLoanEvent]) -> None:
    """Raise `MemberLoanEventRejected` if any event cannot be applied in sequence (R6)."""

    calculate_member_loan_position(terms, effective_events, latest_relevant_date(terms, effective_events))


@dataclass(frozen=True)
class MemberLoanEventPreview:
    """Before and after the change, both on the change's effective date."""

    effective_date: date
    buckets_before: MemberLoanBuckets
    buckets_after: MemberLoanBuckets
    allocation: Optional[MemberLoanBucketAllocation]
    preview_fingerprint: str
    candidate_description: dict = field(default_factory=dict)

    def as_plain_dict(self) -> dict:
        return {
            "effective_date": self.effective_date.isoformat(),
            "buckets_before": self.buckets_before.as_plain_dict(),
            "buckets_after": self.buckets_after.as_plain_dict(),
            "allocation": None if self.allocation is None else self.allocation.as_plain_dict(),
            "preview_fingerprint": self.preview_fingerprint,
        }


def _preview_fingerprint(candidate_description: dict, before: MemberLoanBuckets, after: MemberLoanBuckets) -> str:
    canonical = json.dumps(
        {"candidate": candidate_description, "before": before.as_plain_dict(), "after": after.as_plain_dict()},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _next_application_order(events: Sequence[EffectiveMemberLoanEvent]) -> int:
    return max([0] + [e.application_order for e in events]) + 1


def preview_member_loan_event(
    terms: MemberLoanTerms,
    effective_events: Sequence[EffectiveMemberLoanEvent],
    candidate_event: EffectiveMemberLoanEvent,
) -> MemberLoanEventPreview:
    """What approving `candidate_event` would change, checked against the whole timeline (R6, R7).

    The candidate is applied after every effective event on its date. Raises
    `MemberLoanEventRejected` when the candidate, or any later effective event
    once the candidate is in, cannot be applied.
    """

    candidate_event = EffectiveMemberLoanEvent(
        event_id=candidate_event.event_id,
        event_type=candidate_event.event_type,
        effective_date=candidate_event.effective_date,
        application_order=_next_application_order(effective_events),
        amount=candidate_event.amount,
        interest_election_choice=candidate_event.interest_election_choice,
    )
    events_with_candidate = list(effective_events) + [candidate_event]
    validate_member_loan_events(terms, events_with_candidate)
    before = calculate_member_loan_position(terms, effective_events, candidate_event.effective_date).buckets
    after_position = calculate_member_loan_position(terms, events_with_candidate, candidate_event.effective_date)
    candidate_row = next(r for r in after_position.ledger_rows if r.event_id == candidate_event.event_id)
    description = candidate_event.canonical_dict()
    return MemberLoanEventPreview(
        effective_date=candidate_event.effective_date,
        buckets_before=before,
        buckets_after=after_position.buckets,
        allocation=candidate_row.allocation,
        preview_fingerprint=_preview_fingerprint(description, before, after_position.buckets),
        candidate_description=description,
    )


def preview_member_loan_reversal(
    terms: MemberLoanTerms,
    effective_events: Sequence[EffectiveMemberLoanEvent],
    reversed_event_id: str,
) -> MemberLoanEventPreview:
    """What approving a reversal of `reversed_event_id` would change, on the reversed event's date."""

    target = next((e for e in effective_events if e.event_id == reversed_event_id), None)
    if target is None:
        raise MemberLoanEventRejected("Only an approved event that is still in effect can be reversed.")
    events_without_target = [e for e in effective_events if e.event_id != reversed_event_id]
    validate_member_loan_events(terms, events_without_target)
    before = calculate_member_loan_position(terms, effective_events, target.effective_date).buckets
    after = calculate_member_loan_position(terms, events_without_target, target.effective_date).buckets
    description = {"reversal_of": target.canonical_dict()}
    return MemberLoanEventPreview(
        effective_date=target.effective_date,
        buckets_before=before,
        buckets_after=after,
        allocation=None,
        preview_fingerprint=_preview_fingerprint(description, before, after),
        candidate_description=description,
    )


# -- monthly statement figures --------------------------------------------------


@dataclass(frozen=True)
class MemberLoanDebtEquationStep:
    plain_language_label: str
    signed_change_to_total_balance: Decimal
    event_id: Optional[str] = None


@dataclass(frozen=True)
class MemberLoanMonthlyStatementFigures:
    """Every number on one month's statement, straight from the walker.

    The month runs from `statement_month_start` up to `statement_date`, the
    Interest Date that closes it. "Opening" is right after the Interest Date at
    the month start (before that day's events); "closing" is right after the
    `statement_date` Interest Date (before that day's events).
    """

    statement_month_start: date
    statement_date: date
    opening_buckets: MemberLoanBuckets
    closing_buckets: MemberLoanBuckets
    event_rows_in_month: tuple[MemberLoanLedgerRow, ...]
    interest_periods_in_month: tuple[MemberLoanInterestPeriod, ...]
    closing_interest_date_row: MemberLoanLedgerRow
    debt_equation_steps: tuple[MemberLoanDebtEquationStep, ...]
    monthly_interest_rate: Decimal
    engine_version: str = MEMBER_LOAN_ENGINE_VERSION

    @property
    def interest_earned_in_month(self) -> Decimal:
        return self.closing_interest_date_row.interest_earned_in_month

    @property
    def amount_owed_on_statement_date(self) -> Decimal:
        return self.closing_buckets.amount_owed


class MemberLoanStatementDoesNotAddUp(AssertionError):
    """A printed equation would not add up. Never shown to a member: it is a bug."""


def build_member_loan_monthly_statement_figures(
    terms: MemberLoanTerms,
    effective_events: Sequence[EffectiveMemberLoanEvent],
    statement_month_start: date,
) -> MemberLoanMonthlyStatementFigures:
    if statement_month_start.day != 1 or statement_month_start < terms.loan_effective_date:
        raise MemberLoanEventRejected("A statement covers a calendar month on or after the loan's first month.")
    statement_date = first_day_of_next_month(statement_month_start)
    position = calculate_member_loan_position(terms, effective_events, statement_date)

    if statement_month_start == terms.loan_effective_date:
        opening_row = next(r for r in position.ledger_rows if r.row_kind == LEDGER_ROW_KIND_LOAN_START)
    else:
        opening_row = next(
            r for r in position.ledger_rows if r.row_kind == LEDGER_ROW_KIND_INTEREST_DATE and r.row_date == statement_month_start
        )
    closing_row = next(
        r for r in position.ledger_rows if r.row_kind == LEDGER_ROW_KIND_INTEREST_DATE and r.row_date == statement_date
    )
    event_rows = tuple(
        r
        for r in position.ledger_rows
        if r.event_id is not None
        and r.row_kind != INTEREST_PAYMENT_ELECTION
        and statement_month_start <= r.row_date < statement_date
    )
    periods = tuple(p for p in position.interest_periods if p.interest_date_the_period_belongs_to == statement_date)

    steps = [MemberLoanDebtEquationStep("Total Balance at the start of the month", opening_row.buckets_after.total_balance)]
    for row in event_rows:
        steps.append(
            MemberLoanDebtEquationStep(
                row.row_kind,
                row.buckets_after.total_balance - row.buckets_before.total_balance,
                row.event_id,
            )
        )
    steps.append(MemberLoanDebtEquationStep("interest_added_to_debt", closing_row.interest_added_to_debt))

    figures = MemberLoanMonthlyStatementFigures(
        statement_month_start=statement_month_start,
        statement_date=statement_date,
        opening_buckets=opening_row.buckets_after,
        closing_buckets=closing_row.buckets_after,
        event_rows_in_month=event_rows,
        interest_periods_in_month=periods,
        closing_interest_date_row=closing_row,
        debt_equation_steps=tuple(steps),
        monthly_interest_rate=terms.monthly_interest_rate,
    )
    assert_member_loan_statement_adds_up(figures)
    return figures


def assert_member_loan_statement_adds_up(figures: MemberLoanMonthlyStatementFigures) -> None:
    """Every equation the statement prints must hold, or the statement is not built."""

    for period in figures.interest_periods_in_month:
        recomputed = round_half_up_to_cent(
            period.balance_during_period * figures.monthly_interest_rate * period.interest_days_counted / INTEREST_DAYS_IN_EVERY_MONTH
        )
        if recomputed != period.interest_for_period:
            raise MemberLoanStatementDoesNotAddUp(f"period {period.period_start_date} interest {period.interest_for_period} != {recomputed}")
    period_sum = sum((p.interest_for_period for p in figures.interest_periods_in_month), ZERO_DOLLARS)
    closing_row = figures.closing_interest_date_row
    if period_sum != closing_row.interest_earned_in_month:
        raise MemberLoanStatementDoesNotAddUp(f"periods sum {period_sum} != interest earned {closing_row.interest_earned_in_month}")
    if (
        closing_row.interest_earned_in_month
        - closing_row.interest_already_settled_in_month
        - closing_row.interest_moved_to_interest_payable
        != closing_row.interest_added_to_debt
    ):
        raise MemberLoanStatementDoesNotAddUp("interest earned minus settled minus payable != interest added to debt")
    debt_sum = sum((s.signed_change_to_total_balance for s in figures.debt_equation_steps), ZERO_DOLLARS)
    if debt_sum != figures.closing_buckets.total_balance:
        raise MemberLoanStatementDoesNotAddUp(f"debt steps sum {debt_sum} != closing Total Balance {figures.closing_buckets.total_balance}")
    if figures.closing_buckets.accrued_interest != ZERO_DOLLARS:
        raise MemberLoanStatementDoesNotAddUp("accrued interest must be zero right after an Interest Date")
