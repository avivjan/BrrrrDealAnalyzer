"""BRRRR step: insurance across the deal -- the bill at purchase, the monthly payments until the refi,
the bill at the refi, and the monthly figure of a regular year after it.

Two horizons, never mixed: the first three are cash spent between the purchase and the refi (they move
Cash to Close, the refi wires, Total Cash Invested, cash out and Cash Needed); the regular-year monthly
figure is the only insurance in operating expenses, PITIA and DSCR. The bill at the refi pays the first
year after it while the regular-year figure still charges that year monthly: deliberate, the owner's call.
"""

from decimal import Decimal
from typing import NamedTuple

from BL.analyze.common.deal_math import effective, DAYS_PER_MONTH, MONTHS_PER_YEAR


class InsuranceAcrossTheDeal(NamedTuple):
    insurance_bill_at_purchase_inside_closing: Decimal    # a line of the purchase settlement
    insurance_bill_at_purchase_outside_closing: Decimal   # paid separately, in Total Cash Invested
    insurance_paid_monthly_until_refi: Decimal            # monthly x days until refi / 30
    insurance_bill_at_refi: Decimal                       # effective: input or the bill at purchase
    insurance_bill_at_refi_inside_closing: Decimal        # a line of the refi settlement (both wires)
    insurance_bill_at_refi_outside_closing: Decimal       # paid separately, in Total Cash Invested
    monthly_insurance_after_refi: Decimal                 # effective: input or the bill at the refi / 12


def insurance_step(payload) -> InsuranceAcrossTheDeal:
    insurance_bill_at_purchase = payload.annual_insurance
    insurance_bill_at_purchase_is_inside_closing = payload.insurance_purchase_bill_payment_timing == "inside_purchase_closing"
    insurance_paid_monthly_until_refi = payload.monthly_insurance_until_refi * Decimal(payload.days_until_refi) / DAYS_PER_MONTH
    insurance_bill_at_refi = effective(payload.insurance_bill_at_refi_closing, insurance_bill_at_purchase)
    insurance_bill_at_refi_is_inside_closing = payload.insurance_refi_bill_payment_timing == "inside_refi_closing"
    monthly_insurance_after_refi = effective(payload.monthly_insurance_after_refi, insurance_bill_at_refi / MONTHS_PER_YEAR)
    return InsuranceAcrossTheDeal(
        insurance_bill_at_purchase_inside_closing=insurance_bill_at_purchase if insurance_bill_at_purchase_is_inside_closing else Decimal("0"),
        insurance_bill_at_purchase_outside_closing=Decimal("0") if insurance_bill_at_purchase_is_inside_closing else insurance_bill_at_purchase,
        insurance_paid_monthly_until_refi=insurance_paid_monthly_until_refi,
        insurance_bill_at_refi=insurance_bill_at_refi,
        insurance_bill_at_refi_inside_closing=insurance_bill_at_refi if insurance_bill_at_refi_is_inside_closing else Decimal("0"),
        insurance_bill_at_refi_outside_closing=Decimal("0") if insurance_bill_at_refi_is_inside_closing else insurance_bill_at_refi,
        monthly_insurance_after_refi=monthly_insurance_after_refi,
    )
