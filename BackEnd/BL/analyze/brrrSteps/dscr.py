"""BRRRR step: debt service coverage ratio, on the regular-year monthly taxes and insurance."""

from decimal import Decimal


def dscr_step(payload, mortgage_payment, monthly_property_tax_after_refi, monthly_insurance_after_refi):
    pitia = mortgage_payment + monthly_property_tax_after_refi + monthly_insurance_after_refi + payload.montly_hoa
    dscr = Decimal("0") if pitia == 0 else payload.rent / pitia
    return pitia, dscr
