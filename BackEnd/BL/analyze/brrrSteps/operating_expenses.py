"""BRRRR step: monthly operating expenses, with their components."""

from BL.analyze.common.deal_math import calc_montly_operating_expenses


def operating_expenses_step(payload):
    return calc_montly_operating_expenses(payload)
