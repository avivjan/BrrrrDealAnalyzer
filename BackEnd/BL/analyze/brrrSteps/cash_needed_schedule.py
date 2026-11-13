"""BRRRR step: the dated cash schedule behind Cash Needed, in the Lowest-ARV scenario.

One row per individual cash item, never grouped by date: each row is one future transaction of the
liquidity timeline (its date, a description, a signed amount in dollars, a stable item key). Positive
= money in, negative = money out.

The rehab runs through its own construction account (tasks/todo/ConstructionAccountPerRehab.md): the lender
wires the draws there and every rehab payment leaves from it, so neither is ever a row. Two rows stand for it:
the deposit into the account on the purchase closing date (the rehab cushion, plus the rehab beyond the
construction budget) and what the account gives back on the rehab completion (the cushion, plus the draw
spread). The cushion goes out and comes back, so the rows add up to -(Cash Needed - rehab cushion): Cash
Needed still counts the cushion as cash committed to the deal.

Timing rule: money in as late as reasonable, money out as early as reasonable, so an error in the
estimate only makes the timeline look worse than reality, never better. No money-out row falls after
the refi. On a date shared by several rows, money out comes first, then money in, each in catalogue
order (the order of `CASH_NEEDED_SCHEDULE_ITEM_KEYS`).

Never a row: the refi wire, the full reserves transfer (the reserves live in their own account),
insurance bill C paid inside the refi closing and the tax lump (both inside the wire), anything
already inside Cash to Close (Buy) (the points, the prepaid interest, the seller credit, insurance
bill A paid inside the closing, the closing costs), the construction draws and the rehab payments (they
move through the construction account; only the deposit into it and what it gives back are ours).

Rounding: every row is whole cents. The rows are rounded on their running total, item by item in
catalogue order then by date, and the last running total is pinned to -(total_cash_needed - rehab_cushion);
so each row is within a cent of its exact amount and each item's rows add up to its exact total within a cent.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import NamedTuple

from BL.analyze.common.deal_math import (
    calc_hml_monthly_interest_payment, first_of_month_dates, last_day_of_previous_month, round_to_cents,
)

SELLER_TAX_CREDIT_SET_ASIDE_DAYS_AFTER_BUY_CLOSING = 1

# The catalogue: every item a row can be, in the order rows sharing a date and a direction are listed.
CASH_NEEDED_SCHEDULE_ITEM_KEYS = (
    "earnest_money_deposit",
    "cash_to_close_buy",
    "insurance_bill_at_purchase_outside_closing",
    "construction_account_deposit",
    "seller_tax_credit_set_aside_in_tax_bucket",
    "property_tax_bucket_deposit",
    "property_tax_bucket_deposit_after_first_payment",
    "property_tax_bucket_shortfall_topped_up_on_november_30",
    "hml_interest_paid_monthly",
    "hoa_dues",
    "insurance_paid_monthly_until_refi",
    "utilities",
    "maintenance_before_refi",
    "appliances",
    "appraisal_fee",
    "survey_fee",
    "construction_account_balance_returned_at_rehab_end",
    "pre_refi_rental_income",
    "cash_to_refi_table_conservative",
    "reserves_funded_from_own_pocket_at_lowest_arv",
    "insurance_bill_at_refi_outside_closing",
    "property_tax_bucket_balance_released_at_refi",
)
_CATALOGUE_POSITION_BY_ITEM_KEY = {item_key: position for position, item_key in enumerate(CASH_NEEDED_SCHEDULE_ITEM_KEYS)}

# The deal's key dates, shown among the cash rows so the schedule reads as a timeline. Markers, not cash:
# never a row of `dated_cash_rows`, never imported into the liquidity timeline. The first five are the
# liquidity timeline's own milestones (`BL/liquidity/dealCashRows/deal_milestones.py`); on a date they share,
# they are listed in this order.
CASH_NEEDED_SCHEDULE_MILESTONE_KEYS = (
    "contract_signed",
    "purchase_closed",
    "rehab_completed",
    "tenant_moved_in",
    "property_tax_bill_paid_on_november_30",
    "refi_closed",
)
_CATALOGUE_POSITION_BY_MILESTONE_KEY = {milestone_key: position for position, milestone_key in enumerate(CASH_NEEDED_SCHEDULE_MILESTONE_KEYS)}
_AT_THE_LOWEST_ARV_REFI = " (Lowest-ARV refi)"


class CashNeededScheduleRow(NamedTuple):
    date: date
    sequence_within_day: int          # 0, 1, ... in the order of the rows that share this date
    description: str
    signed_amount_dollars: Decimal    # whole cents; positive = money in, negative = money out
    item_key: str                     # one of CASH_NEEDED_SCHEDULE_ITEM_KEYS; (item_key, date) is unique


class CashNeededScheduleMilestone(NamedTuple):
    date: date
    milestone_key: str                # one of CASH_NEEDED_SCHEDULE_MILESTONE_KEYS
    description: str


class CashNeededScheduleAtLowestArv(NamedTuple):
    dated_cash_rows: tuple[CashNeededScheduleRow, ...]
    deal_milestones: tuple[CashNeededScheduleMilestone, ...]   # the key dates, in date order; not cash


def deal_milestones_of_the_schedule(timeline, first_property_tax_payment_date: date) -> tuple[CashNeededScheduleMilestone, ...]:
    """The deal's key dates in date order. The Nov 30 tax bill is one only while it falls inside the hold
    (after the purchase closing, on or before the refi): the bucket pays it, so it explains the deposits around it."""
    milestones = [
        CashNeededScheduleMilestone(timeline.contract_date, "contract_signed", "Contract signed"),
        CashNeededScheduleMilestone(timeline.buy_closing_date, "purchase_closed", "Purchase closing"),
        CashNeededScheduleMilestone(timeline.rehab_completed_date, "rehab_completed", "Rehab completed"),
        CashNeededScheduleMilestone(timeline.tenant_occupied_date, "tenant_moved_in", "Tenant moves in"),
        CashNeededScheduleMilestone(timeline.refi_closing_date, "refi_closed", "Refi closing"),
    ]
    if timeline.buy_closing_date < first_property_tax_payment_date <= timeline.refi_closing_date:
        milestones.append(CashNeededScheduleMilestone(first_property_tax_payment_date, "property_tax_bill_paid_on_november_30",
                                                      "Property tax bill paid from the tax bucket (Nov 30)"))
    return tuple(sorted(milestones, key=lambda milestone: (milestone.date, _CATALOGUE_POSITION_BY_MILESTONE_KEY[milestone.milestone_key])))


def cash_needed_schedule_step(payload, timeline, hml_amount, hml_and_holding, buy_settlement, insurance, property_tax_bucket,
                              stolen_money, cash_out_figures, total_cash_needed) -> CashNeededScheduleAtLowestArv:
    buy_closing_date = timeline.buy_closing_date
    refi_closing_date = timeline.refi_closing_date
    rehab_completed_date = timeline.rehab_completed_date
    # (date, item_key, description, exact signed amount)
    exact_rows: list[tuple[date, str, str, Decimal]] = []

    def money_out(on_date: date, item_key: str, description: str, amount: Decimal) -> None:
        exact_rows.append((on_date, item_key, description, -amount))

    def money_in(on_date: date, item_key: str, description: str, amount: Decimal) -> None:
        exact_rows.append((on_date, item_key, description, amount))

    # -- Buy
    money_out(timeline.contract_date, "earnest_money_deposit", "Earnest money deposit", payload.earnest_money_deposit)
    money_out(buy_closing_date, "cash_to_close_buy", "Cash to close (the purchase wire)", buy_settlement.cash_to_close_buy)
    money_out(buy_closing_date, "insurance_bill_at_purchase_outside_closing", "Insurance bill at purchase (paid outside the closing)",
              insurance.insurance_bill_at_purchase_outside_closing)
    # The construction account's bootstrap deposit: the cushion, plus the rehab the construction budget does not cover.
    original_steal = stolen_money
    money_out(buy_closing_date, "construction_account_deposit",
              "Deposit into the construction account (rehab cushion" + (" + rehab beyond the construction budget)" if original_steal < 0 else ")"),
              payload.rehab_cushion + max(Decimal("0"), -original_steal))
    money_out(buy_closing_date + timedelta(days=SELLER_TAX_CREDIT_SET_ASIDE_DAYS_AFTER_BUY_CLOSING), "seller_tax_credit_set_aside_in_tax_bucket",
              "Seller tax credit set aside in the tax bucket", buy_settlement.seller_tax_credit_set_aside_in_tax_bucket)

    # -- The property's tax bucket (a separate bank account): the deposits leave this one
    for deposit_date in property_tax_bucket.property_tax_bucket_first_bill_deposit_dates_until_refi:
        money_out(deposit_date, "property_tax_bucket_deposit", "Tax bucket deposit", property_tax_bucket.property_tax_bucket_deposit)
    for deposit_date in property_tax_bucket.property_tax_bucket_later_deposit_dates_until_refi:
        money_out(deposit_date, "property_tax_bucket_deposit_after_first_payment", "Tax bucket deposit (next year's bill)",
                  property_tax_bucket.property_tax_bucket_deposit_after_first_payment)
    money_out(property_tax_bucket.first_property_tax_payment_date, "property_tax_bucket_shortfall_topped_up_on_november_30",
              "Tax bucket shortfall topped up for the Nov 30 bill", property_tax_bucket.property_tax_bucket_shortfall_topped_up_on_november_30)

    # -- The monthly items, on the 1sts
    for payment_date in timeline.hml_interest_monthly_payment_dates:
        month_paid_for = last_day_of_previous_month(payment_date)
        money_out(payment_date, "hml_interest_paid_monthly", f"HML interest for {month_paid_for.strftime('%B %Y')}",
                  calc_hml_monthly_interest_payment(hml_amount, payload.HML_interest_rate))
    for payment_date in timeline.first_of_month_dates_after_closing_through_refi:
        money_out(payment_date, "hoa_dues", "HOA dues", payload.montly_hoa)
        money_out(payment_date, "insurance_paid_monthly_until_refi", "Insurance (monthly)", payload.monthly_insurance_until_refi)
    for bill_date in timeline.utility_bill_dates_until_refi:
        money_out(bill_date, "utilities", "Utilities", payload.monthly_utilities_until_rented)

    # -- Rehab and the end of it
    maintenance_dates = first_of_month_dates(rehab_completed_date, refi_closing_date) or [rehab_completed_date]
    maintenance_share = payload.maintenance_before_refi / len(maintenance_dates)
    for share_number, maintenance_date in enumerate(maintenance_dates, start=1):
        is_last_share = share_number == len(maintenance_dates)
        share_amount = payload.maintenance_before_refi - maintenance_share * (len(maintenance_dates) - 1) if is_last_share else maintenance_share
        share_text = f" (share {share_number} of {len(maintenance_dates)})" if len(maintenance_dates) > 1 else ""
        money_out(maintenance_date, "maintenance_before_refi", f"Maintenance before refi{share_text}", share_amount)
    money_out(rehab_completed_date, "appliances", "Appliances", payload.appliances)
    money_out(rehab_completed_date, "appraisal_fee", "Appraisal (paid outside the refi closing)", payload.appraisal_fee)
    money_out(rehab_completed_date, "survey_fee", "Survey (paid outside the refi closing)", payload.survey_fee)
    # What the construction account gives back once the rehab is paid: the cushion, plus the draw spread (stolen money).
    # The draws and the rehab payments move through that account and are never rows.
    money_in(rehab_completed_date, "construction_account_balance_returned_at_rehab_end",
             "Construction account balance returned at rehab end (cushion" + (" + draw spread)" if original_steal > 0 else ")"),
             payload.rehab_cushion + max(Decimal("0"), original_steal))

    # -- Rent, on the 1sts after the tenant moves in
    for collection_date in timeline.rent_collection_dates_before_refi:
        money_in(collection_date, "pre_refi_rental_income", "Rent collected", payload.rent)

    # -- The refi, at the lowest ARV. Never the wire, never the full reserves transfer.
    money_out(refi_closing_date, "cash_to_refi_table_conservative", "Cash to the refi table" + _AT_THE_LOWEST_ARV_REFI,
              cash_out_figures.cash_to_refi_table_conservative)
    money_out(refi_closing_date, "reserves_funded_from_own_pocket_at_lowest_arv", "Reserves the wire cannot fund" + _AT_THE_LOWEST_ARV_REFI,
              cash_out_figures.reserves_funded_from_own_pocket_at_lowest_arv)
    money_out(refi_closing_date, "insurance_bill_at_refi_outside_closing", "Insurance bill at refi (paid outside the closing)" + _AT_THE_LOWEST_ARV_REFI,
              insurance.insurance_bill_at_refi_outside_closing)
    money_in(refi_closing_date, "property_tax_bucket_balance_released_at_refi", "Tax bucket balance released" + _AT_THE_LOWEST_ARV_REFI,
             property_tax_bucket.property_tax_bucket_balance_released_at_refi)

    non_zero_exact_rows = [row for row in exact_rows if row[3] != 0]
    rounded_amount_by_exact_row = _rounded_on_the_running_total(non_zero_exact_rows, target_signed_total=-(total_cash_needed - payload.rehab_cushion))

    rows_in_date_order = sorted(
        non_zero_exact_rows,
        key=lambda row: (row[0], 0 if row[3] < 0 else 1, _CATALOGUE_POSITION_BY_ITEM_KEY[row[1]]),
    )
    dated_cash_rows: list[CashNeededScheduleRow] = []
    for row in rows_in_date_order:
        row_date, item_key, description, _exact_amount = row
        if rounded_amount_by_exact_row[id(row)] == 0:   # a sub-cent amount: dropping it leaves the total untouched
            continue
        sequence_within_day = dated_cash_rows[-1].sequence_within_day + 1 if dated_cash_rows and dated_cash_rows[-1].date == row_date else 0
        dated_cash_rows.append(CashNeededScheduleRow(row_date, sequence_within_day, description, rounded_amount_by_exact_row[id(row)], item_key))

    return CashNeededScheduleAtLowestArv(
        dated_cash_rows=tuple(dated_cash_rows),
        deal_milestones=deal_milestones_of_the_schedule(timeline, property_tax_bucket.first_property_tax_payment_date),
    )


def _rounded_on_the_running_total(exact_rows: list[tuple[date, str, str, Decimal]], target_signed_total: Decimal) -> dict[int, Decimal]:
    """Each row's whole-cent amount: round(running exact total) - round(previous running total), walking the rows item by
    item in catalogue order, then by date, with the last running total pinned to `target_signed_total`. Rows of one item
    sit next to each other in that walk, so their rounded sum stays within a cent of their exact sum."""
    rows_in_rounding_order = sorted(exact_rows, key=lambda row: (_CATALOGUE_POSITION_BY_ITEM_KEY[row[1]], row[0]))
    rounded_amount_by_exact_row: dict[int, Decimal] = {}
    running_exact_total = Decimal("0")
    previous_rounded_running_total = Decimal("0")
    for position, row in enumerate(rows_in_rounding_order):
        running_exact_total += row[3]
        is_last_row = position == len(rows_in_rounding_order) - 1
        rounded_running_total = round_to_cents(target_signed_total) if is_last_row else round_to_cents(running_exact_total)
        rounded_amount_by_exact_row[id(row)] = rounded_running_total - previous_rounded_running_total
        previous_rounded_running_total = rounded_running_total
    return rounded_amount_by_exact_row
