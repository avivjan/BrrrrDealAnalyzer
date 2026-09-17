"""BRRRR step: debt service coverage ratio."""

from BL.analyze.common.deal_math import calc_pitia, calcDSCR


def dscr_step(payload, mortgage_payment):
    pitia = calc_pitia(mortgage_payment, payload.annual_property_taxes, payload.annual_insurance, payload.montly_hoa)
    dscr = calcDSCR(payload.rent, payload.annual_property_taxes, payload.annual_insurance, payload.montly_hoa, mortgage_payment)
    return pitia, dscr
