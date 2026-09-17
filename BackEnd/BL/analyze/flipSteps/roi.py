"""Flip step: ROI and annualized ROI."""

from decimal import Decimal


def roi_and_annualized_step(payload, net_profit, total_cash_invested):
    # No cash invested: the return is unbounded. Reuse the engine's sentinels
    # (-1 = +∞, -2 = -∞, same as the BRRRR CoC/ROI) so every renderer decodes
    # them the same way; a break-even deal with no cash in is a genuine 0%.
    if total_cash_invested > 0:
        roi = (net_profit / total_cash_invested) * Decimal("100.0")
    elif net_profit > 0:
        roi = Decimal("-1")
    elif net_profit < 0:
        roi = Decimal("-2")
    else:
        roi = Decimal("0")

    years = payload.holding_time_months / Decimal("12.0")
    if total_cash_invested <= 0:
        annualized_roi = roi  # the sentinel (or 0) carries through unchanged
    elif years > 0:
        annualized_roi = roi / years
    else:
        annualized_roi = Decimal("0")
    return years, roi, annualized_roi
