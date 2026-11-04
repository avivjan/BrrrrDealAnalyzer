"""One occurrence of a recurring rule: mark it done (or open again) and move it to another date
(tasks/todo/DealImpactSimulator.md, E).

Occurrences are virtual: the frontend expands a rule into them. An occurrence's state is stored only once it is
marked done or moved, keyed by the date the rule gives it (`scheduled_date`). The schedule here mirrors the
frontend's `dateForOccurrence` (`frontend/src/utils/liquidityEngine.ts`): occurrence i is the start date plus
i x the cadence, months clamped to the month's last day, capped by `occurrences` and `end_date`.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from BL.liquidity.common.mappers import recurring_to_res
from DAL.crud.liquidity import get_recurring
from DAL.data_models import LiquidityRecurringOccurrenceState, LiquidityRecurringTransaction

# The same ceiling as the frontend's expansion (`safetyCap`).
MAX_OCCURRENCES_CHECKED = 2000


class UnknownRecurringRuleError(LookupError):
    """No recurring rule has this id."""


class NotAnOccurrenceOfTheRuleError(ValueError):
    """The rule never produces an occurrence on this date."""


def _add_months_clamped(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year, month = start.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def scheduled_date_of_occurrence(rule: LiquidityRecurringTransaction, index: int) -> date:
    if index == 0:
        return rule.start_date
    interval = max(1, int(rule.interval or 1))
    if rule.frequency == "daily":
        return rule.start_date + timedelta(days=index * interval)
    if rule.frequency == "weekly":
        return rule.start_date + timedelta(days=index * 7 * interval)
    if rule.frequency == "biweekly":
        return rule.start_date + timedelta(days=index * 14 * interval)
    if rule.frequency == "monthly":
        return _add_months_clamped(rule.start_date, index * interval)
    if rule.frequency == "quarterly":
        return _add_months_clamped(rule.start_date, index * 3 * interval)
    if rule.frequency == "yearly":
        return _add_months_clamped(rule.start_date, index * 12 * interval)
    return rule.start_date


def rule_produces_date(rule: LiquidityRecurringTransaction, scheduled_date: date) -> bool:
    if scheduled_date < rule.start_date or (rule.end_date and scheduled_date > rule.end_date):
        return False
    for index in range(min(rule.occurrences or MAX_OCCURRENCES_CHECKED, MAX_OCCURRENCES_CHECKED)):
        occurrence_date = scheduled_date_of_occurrence(rule, index)
        if occurrence_date == scheduled_date:
            return True
        if occurrence_date > scheduled_date:
            return False
    return False


def _rule_or_raise(db: Session, rule_id: str) -> LiquidityRecurringTransaction:
    try:
        uuid.UUID(str(rule_id))
    except ValueError as exc:
        raise UnknownRecurringRuleError(rule_id) from exc
    rule = get_recurring(db, rule_id)
    if rule is None:
        raise UnknownRecurringRuleError(rule_id)
    return rule


def _state_of(db: Session, rule: LiquidityRecurringTransaction, scheduled_date: date) -> LiquidityRecurringOccurrenceState:
    if not rule_produces_date(rule, scheduled_date):
        raise NotAnOccurrenceOfTheRuleError(f"{rule.description!r} has no occurrence on {scheduled_date.isoformat()}.")
    state = next((existing for existing in rule.occurrence_states if existing.scheduled_date == scheduled_date), None)
    if state is None:
        state = LiquidityRecurringOccurrenceState(recurring_rule_id=rule.id, scheduled_date=scheduled_date)
        rule.occurrence_states.append(state)
    return state


def _drop_if_plain(rule: LiquidityRecurringTransaction, state: LiquidityRecurringOccurrenceState) -> None:
    """An occurrence open on its own date needs no row."""
    if state.done_at is None and state.moved_to_date is None:
        rule.occurrence_states.remove(state)


def apply_occurrence_change(state: LiquidityRecurringOccurrenceState, action: str, now: datetime,
                            new_effective_date: Optional[date] = None, postpone_by_days: Optional[int] = None) -> None:
    if action == "mark_done":
        state.done_at = now
    elif action == "mark_not_done":
        state.done_at = None
    elif action == "move_to_date":
        state.moved_to_date = None if new_effective_date == state.scheduled_date else new_effective_date
    elif action == "postpone_by_days":
        moved_to = (state.moved_to_date or state.scheduled_date) + timedelta(days=postpone_by_days or 0)
        state.moved_to_date = None if moved_to == state.scheduled_date else moved_to


def change_occurrence(db: Session, rule_id: str, scheduled_date: date, action: str,
                      new_effective_date: Optional[date] = None):
    """Done / open again / move one occurrence. Returns the rule's response with its states."""
    rule = _rule_or_raise(db, rule_id)
    state = _state_of(db, rule, scheduled_date)
    apply_occurrence_change(state, action, datetime.now(timezone.utc), new_effective_date)
    _drop_if_plain(rule, state)
    db.commit()
    db.refresh(rule)
    return recurring_to_res(rule)


def change_occurrences_in_bulk(db: Session, occurrence_refs, action: str, new_effective_date: Optional[date],
                               postpone_by_days: Optional[int]) -> None:
    """The bulk bar's action on recurring occurrences, all or nothing (the caller commits)."""
    now = datetime.now(timezone.utc)
    resolved = []
    for occurrence_ref in occurrence_refs:
        rule = _rule_or_raise(db, occurrence_ref.recurring_rule_id)
        resolved.append((rule, _state_of(db, rule, occurrence_ref.scheduled_date)))
    for rule, state in resolved:
        apply_occurrence_change(state, action, now, new_effective_date, postpone_by_days)
        _drop_if_plain(rule, state)
