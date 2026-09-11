"""BRRRR step: monthly mortgage payment on the DSCR loan."""

from BL.analyze.common.deal_math import calc_mortgage_payment


def mortgage_payment_step(payload, arv, ltv):
    return calc_mortgage_payment(arv, ltv, payload.interest_rate, payload.loan_term_years)
