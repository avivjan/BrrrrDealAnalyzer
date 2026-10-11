"""The in-service monthly statement schedule (BL/memberLoan/common/member_loan_statement_schedule.py)."""

from __future__ import annotations

import pytest

from BL.memberLoan.common import member_loan_statement_schedule as schedule
from tests.member_loan_helpers import (
    configure_member_loan_environment,
    member_loan_clock,  # noqa: F401  (fixture)
    member_loan_mailbox,  # noqa: F401  (fixture)
)


@pytest.fixture(autouse=True)
def _environment(monkeypatch, member_loan_clock, member_loan_mailbox):
    configure_member_loan_environment(monkeypatch)
    monkeypatch.setenv("MEMBER_LOAN_EMAIL_DRY_RUN", "false")


def _statements(mailbox):
    return [m for m in mailbox.sent if m["subject"].startswith("Member Loan statement")]


def test_sends_once_from_6am_new_york_on_the_1st(member_loan_clock, member_loan_mailbox):
    member_loan_clock.set(2027, 1, 1, hour=10)  # 5am in New York (winter time)
    assert schedule.run_member_loan_statement_schedule_check() is None
    member_loan_clock.set(2027, 1, 1, hour=11)  # 6am in New York
    assert schedule.run_member_loan_statement_schedule_check().outcome == "sent"
    assert schedule.run_member_loan_statement_schedule_check() is None
    member_loan_clock.set(2027, 1, 9, hour=11)
    assert schedule.run_member_loan_statement_schedule_check() is None
    [mail] = _statements(member_loan_mailbox)
    assert "December 2026" in mail["subject"]


def test_a_month_missed_on_the_1st_goes_out_later_that_month(member_loan_clock, member_loan_mailbox):
    member_loan_clock.set(2026, 11, 3, hour=15)
    assert schedule.run_member_loan_statement_schedule_check().outcome == "sent"
    assert "October 2026" in _statements(member_loan_mailbox)[0]["subject"]


def test_does_nothing_in_dry_run_mode_or_before_the_first_statement(monkeypatch, member_loan_clock, member_loan_mailbox):
    member_loan_clock.set(2026, 10, 20, hour=15)  # September has no statement: the loan started in October
    assert schedule.run_member_loan_statement_schedule_check().outcome == "refused"
    monkeypatch.setenv("MEMBER_LOAN_EMAIL_DRY_RUN", "true")
    member_loan_clock.set(2026, 11, 2, hour=15)
    assert schedule.run_member_loan_statement_schedule_check() is None
    assert _statements(member_loan_mailbox) == []


def test_a_failure_is_retried_a_few_times_then_left_alone(member_loan_clock, member_loan_mailbox):
    member_loan_clock.set(2026, 11, 1, hour=15)
    member_loan_mailbox.fail_next = 10
    outcomes = [schedule.run_member_loan_statement_schedule_check() for _ in range(6)]
    assert [o.outcome if o else None for o in outcomes] == ["failed", "failed", "failed", "failed", None, None]
    member_loan_mailbox.fail_next = 0
    assert schedule.run_member_loan_statement_schedule_check() is None
    assert _statements(member_loan_mailbox) == []


def test_a_bad_configuration_is_ignored_quietly(monkeypatch, member_loan_clock):
    monkeypatch.setenv("MEMBER_LOAN_ALLOWED_USERNAMES", "someone")
    member_loan_clock.set(2026, 11, 2, hour=15)
    assert schedule.run_member_loan_statement_schedule_check() is None


def test_the_thread_never_starts_outside_production_or_under_pytest(monkeypatch):
    assert schedule.start_member_loan_statement_schedule(False) is False
    assert schedule.start_member_loan_statement_schedule(True) is False  # pytest is running
