"""BRRRR step: return on investment."""

from BL.analyze.common.deal_math import calc_roi


def roi_step(cash_out, cash_flow, net_profit):
    return calc_roi(cash_out, cash_flow, net_profit)
