"""The `monthsUntilRefi` -> `daysUntilRefi` compatibility shim.

Read literally, a stale payload's `monthsUntilRefi: 6` would mean six *days* —
a 30x understatement of the hold, and so of the hard money interest. This is
the one piece of the rename that has to be exactly right.
"""

from __future__ import annotations

import pytest

from ReqRes.refi_timing import days_from_legacy_months


class TestDaysFromLegacyMonths:
    @pytest.mark.parametrize(
        ("months", "expected_days"),
        [
            (6, 180),      # the old default
            (1, 30),
            (0.5, 15),     # the old column was NUMERIC(5,1) - halves were legal
            (12, 360),
            (6.5, 195),
            (2.4, 72),
        ],
    )
    def test_a_month_is_thirty_days(self, months, expected_days):
        result = days_from_legacy_months({"monthsUntilRefi": months})
        assert result["daysUntilRefi"] == expected_days

    def test_it_accepts_the_orm_spelling_too(self):
        result = days_from_legacy_months({"Months_until_refi": 6})
        assert result["daysUntilRefi"] == 180

    def test_it_reads_the_string_a_json_decimal_arrives_as(self):
        # FastAPI serialises Decimal columns as strings, so a payload echoed
        # back from an older client carries "6.0", not 6.
        result = days_from_legacy_months({"monthsUntilRefi": "6.0"})
        assert result["daysUntilRefi"] == 180

    def test_a_current_payload_is_left_alone(self):
        payload = {"daysUntilRefi": 195, "monthsUntilRefi": 6}
        # Days already present wins; the legacy key is ignored rather than
        # overwriting a value the user actually chose.
        assert days_from_legacy_months(payload)["daysUntilRefi"] == 195

    def test_it_does_not_invent_a_value_when_neither_key_is_present(self):
        payload = {"purchasePrice": 200}
        assert "daysUntilRefi" not in days_from_legacy_months(payload)

    def test_it_does_not_mutate_the_caller_s_payload(self):
        payload = {"monthsUntilRefi": 6}
        days_from_legacy_months(payload)
        assert payload == {"monthsUntilRefi": 6}

    @pytest.mark.parametrize("value", [None, "", "abc", [], {}])
    def test_unusable_values_fall_through_to_normal_validation(self, value):
        # Better to let Pydantic report a missing/invalid field than to guess.
        result = days_from_legacy_months({"monthsUntilRefi": value})
        assert "daysUntilRefi" not in result

    def test_a_non_dict_passes_straight_through(self):
        # `from_attributes=True` validates ORM rows, which are not dicts.
        sentinel = object()
        assert days_from_legacy_months(sentinel) is sentinel
