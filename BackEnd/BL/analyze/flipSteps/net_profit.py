"""Flip step: capital gains tax and net profit."""

from decimal import Decimal


def net_profit_after_tax_step(payload, gross_profit):
    cap_gains = Decimal("0")
    if gross_profit > 0:
        cap_gains = gross_profit * (payload.capital_gains_tax_rate / Decimal("100.0"))
    net_profit = gross_profit - cap_gains
    return cap_gains, net_profit
