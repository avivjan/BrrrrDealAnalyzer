"""BRRRR step: Cash Needed -- the single definitive out-of-pocket capital through the refi, rounded to the cent."""

from decimal import Decimal

from BL.analyze.common.deal_math import round_to_cents


def total_cash_needed_step(payload, cash_out_figures) -> Decimal:
    # Everything spent before the refi, plus the rehab cushion (held, not spent), plus the cash brought
    # to the refi closing table and the reserves the wire cannot fund if the appraisal comes in at the
    # lowest ARV. The stress test is the figure to plan around: there is no baseline variant and no
    # floor. Never clamped: a deal that gives back more than it takes reads negative, as it is.
    # Rounded to the cent, so the dated rows of the Cash Needed schedule add up to it exactly.
    return round_to_cents(cash_out_figures.total_cash_invested + payload.rehab_cushion
                          + cash_out_figures.cash_to_refi_table_conservative
                          + cash_out_figures.reserves_funded_from_own_pocket_at_lowest_arv)
