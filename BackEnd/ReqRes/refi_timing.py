"""Backward compatibility for the `monthsUntilRefi` -> `daysUntilRefi` rename.

The BRRRR calc used to take a fractional *month* count; it now takes whole
days and accrues hard money interest per diem on a 360-day year. A month is
exactly 30 days under that convention, which is what makes the translation
below lossless — see `_migrate_months_until_refi_to_days` in `main.py`.

A payload from a stale cached frontend (or an old saved request) still carries
`monthsUntilRefi`. Read as-is it would mean 6 *days*, so convert it instead.
"""

from typing import Any

DAYS_PER_MONTH = 30

# Every spelling of the field that has ever been on the wire.
_LEGACY_KEYS = ("monthsUntilRefi", "Months_until_refi")
_CURRENT_KEYS = ("daysUntilRefi", "days_until_refi")


def days_from_legacy_months(data: Any) -> Any:
    """Fill `daysUntilRefi` from a legacy month count, if that's all we got.

    Used as a Pydantic `mode="before"` model validator. Returns `data`
    untouched unless it is a dict carrying only the legacy key, so a payload
    that already speaks days (or an ORM row being validated with
    `from_attributes`) passes straight through.
    """
    if not isinstance(data, dict):
        return data
    if any(data.get(key) is not None for key in _CURRENT_KEYS):
        return data

    for key in _LEGACY_KEYS:
        months = data.get(key)
        if months is None:
            continue
        try:
            days = round(float(months) * DAYS_PER_MONTH)
        except (TypeError, ValueError):
            return data
        return {**data, "daysUntilRefi": days}

    return data
