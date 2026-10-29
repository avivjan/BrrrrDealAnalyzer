"""BRRRR step: the property's tax bucket until the refi, and the regular-year monthly tax after it.

How the owner works: at the purchase closing the seller's prorated credit goes straight into a tax
bucket for this property. The bill is paid on Nov 30 with the 4% November discount (bill x 0.96). What
the credit does not cover is split evenly over the 15ths left until that Nov 30 and auto-deposited on
each one. When the seller already paid this year's bill (they are reimbursed at closing), the bucket
fills toward next year's Nov 30 from the first 15th after closing: a Nov 20 closing deposits from Dec 15. A Nov 30 inside the hold is paid from the bucket (any shortfall topped up that day); the
deposits after it are the next year's bill x 0.96 / 12. Without a buy closing date there are no
15ths to count: the deposit defaults to bill x 0.96 / 12 for every 30 days until the refi.

When the refi lender collects the whole bill as a lump, the lender pays the Nov 30 bill: the lump is a
refi settlement line, and the bucket's balance at the refi comes back to the owner.

The refi never changes the tax itself: a regular year after it costs bill x 0.96 / 12 a month.
"""

from datetime import date
from decimal import Decimal
from typing import NamedTuple, Optional

from BL.analyze.common.deal_math import (
    effective, property_tax_bucket_deposit_dates, first_property_tax_payment_date,
    PROPERTY_TAX_NOVEMBER_PAYMENT_FACTOR, DAYS_PER_MONTH, MONTHS_PER_YEAR,
)


class PropertyTaxBucket(NamedTuple):
    property_tax_bill_paid_on_november_30: Decimal                 # this year's bill x 0.96
    first_property_tax_payment_date: Optional[date]                # the first Nov 30 the owner pays; None without a closing date
    property_tax_bucket_deposit_count_until_first_payment: int     # the 15ths after closing through that Nov 30 (1 when none is left); 0 without a date
    property_tax_bucket_deposit: Decimal                           # effective: input or the formula, deposited on each of those 15ths
    property_tax_bucket_first_bill_deposit_count_until_refi: Decimal   # those deposits made on or before the refi (days until refi / 30 without a date)
    property_tax_bucket_deposit_after_first_payment: Decimal       # bill x 0.96 / 12, on each 15th after a Nov 30 inside the hold
    property_tax_bucket_later_deposit_count_until_refi: int        # those deposits made on or before the refi
    property_tax_paid_into_bucket_until_refi: Decimal              # every deposit until the refi
    property_tax_bucket_shortfall_topped_up_on_november_30: Decimal    # what the bucket lacked on a Nov 30 inside the hold
    property_tax_lump_sum_at_refi_closing: Decimal                 # the refi lender's lump; 0 unless the full bill is collected
    property_tax_bucket_balance_released_at_refi: Decimal          # comes back when the lender collects the lump; 0 otherwise
    monthly_property_tax_after_refi: Decimal                       # bill x 0.96 / 12, the regular-year figure


def property_tax_bucket_step(payload, timeline, seller_tax_credit_set_aside_in_tax_bucket, seller_paid_current_year_taxes) -> PropertyTaxBucket:
    property_tax_bill = payload.annual_property_taxes
    property_tax_bill_paid_on_november_30 = property_tax_bill * PROPERTY_TAX_NOVEMBER_PAYMENT_FACTOR
    monthly_property_tax_after_refi = property_tax_bill_paid_on_november_30 / MONTHS_PER_YEAR
    full_bill_collected_at_refi = payload.property_tax_collection_at_refi == "full_tax_bill_collected_at_refi"

    if timeline.buy_closing_date is None:
        first_payment_date = None
        deposit_count_until_first_payment = 0
        property_tax_bucket_deposit = effective(payload.monthly_property_tax_bucket_deposit, monthly_property_tax_after_refi)
        first_bill_deposit_count_until_refi = Decimal(payload.days_until_refi) / DAYS_PER_MONTH
        later_deposit_count_until_refi = 0
        first_payment_is_paid_from_bucket = False
    else:
        refi_closing_date = timeline.refi_closing_date
        first_payment_date = first_property_tax_payment_date(timeline.buy_closing_date, seller_paid_current_year_taxes)
        first_bill_deposit_dates = (property_tax_bucket_deposit_dates(timeline.buy_closing_date, first_payment_date)
                                    or [first_payment_date])
        deposit_count_until_first_payment = len(first_bill_deposit_dates)
        property_tax_bucket_deposit_default = max(
            Decimal("0"),
            (property_tax_bill_paid_on_november_30 - seller_tax_credit_set_aside_in_tax_bucket) / Decimal(deposit_count_until_first_payment),
        )
        property_tax_bucket_deposit = effective(payload.monthly_property_tax_bucket_deposit, property_tax_bucket_deposit_default)
        first_bill_deposit_count_until_refi = Decimal(sum(1 for deposit_date in first_bill_deposit_dates if deposit_date <= refi_closing_date))
        # A refi lender collecting the whole bill on Nov 30 itself pays that bill; otherwise the bucket does.
        first_payment_is_paid_from_bucket = (first_payment_date < refi_closing_date if full_bill_collected_at_refi
                                             else first_payment_date <= refi_closing_date)
        later_deposit_count_until_refi = (len(property_tax_bucket_deposit_dates(first_payment_date, refi_closing_date))
                                          if first_payment_is_paid_from_bucket else 0)

    property_tax_bucket_deposit_after_first_payment = monthly_property_tax_after_refi
    property_tax_paid_into_bucket_until_refi = (property_tax_bucket_deposit * first_bill_deposit_count_until_refi
                                                + property_tax_bucket_deposit_after_first_payment * Decimal(later_deposit_count_until_refi))
    property_tax_bucket_shortfall_topped_up_on_november_30 = (
        max(Decimal("0"), property_tax_bill_paid_on_november_30 - seller_tax_credit_set_aside_in_tax_bucket
            - property_tax_bucket_deposit * Decimal(deposit_count_until_first_payment))
        if first_payment_is_paid_from_bucket else Decimal("0")
    )
    if full_bill_collected_at_refi:
        property_tax_lump_sum_at_refi_closing = effective(payload.property_tax_lump_sum_at_refi_closing, property_tax_bill)
        property_tax_bucket_balance_released_at_refi = (
            seller_tax_credit_set_aside_in_tax_bucket + property_tax_paid_into_bucket_until_refi + property_tax_bucket_shortfall_topped_up_on_november_30
            - (property_tax_bill_paid_on_november_30 if first_payment_is_paid_from_bucket else Decimal("0"))
        )
    else:
        property_tax_lump_sum_at_refi_closing = Decimal("0")
        property_tax_bucket_balance_released_at_refi = Decimal("0")

    return PropertyTaxBucket(
        property_tax_bill_paid_on_november_30=property_tax_bill_paid_on_november_30,
        first_property_tax_payment_date=first_payment_date,
        property_tax_bucket_deposit_count_until_first_payment=deposit_count_until_first_payment,
        property_tax_bucket_deposit=property_tax_bucket_deposit,
        property_tax_bucket_first_bill_deposit_count_until_refi=first_bill_deposit_count_until_refi,
        property_tax_bucket_deposit_after_first_payment=property_tax_bucket_deposit_after_first_payment,
        property_tax_bucket_later_deposit_count_until_refi=later_deposit_count_until_refi,
        property_tax_paid_into_bucket_until_refi=property_tax_paid_into_bucket_until_refi,
        property_tax_bucket_shortfall_topped_up_on_november_30=property_tax_bucket_shortfall_topped_up_on_november_30,
        property_tax_lump_sum_at_refi_closing=property_tax_lump_sum_at_refi_closing,
        property_tax_bucket_balance_released_at_refi=property_tax_bucket_balance_released_at_refi,
        monthly_property_tax_after_refi=monthly_property_tax_after_refi,
    )
