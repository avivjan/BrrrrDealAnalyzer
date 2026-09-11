"""BRRRR step: cash-on-cash return."""

from BL.analyze.common.deal_math import calc_cash_on_cash


def cash_on_cash_step(cash_out, cash_flow):
    return calc_cash_on_cash(cash_out, cash_flow)
