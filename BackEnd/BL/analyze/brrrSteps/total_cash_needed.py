"""BRRRR step: Cash Needed -- the single definitive out-of-pocket capital through the refi."""


def total_cash_needed_step(payload, cash_out_figures):
    # Everything spent before the refi, plus the rehab cushion (capital held, not spent, so
    # it is needed but never counts as invested), plus the cash brought to the refi closing
    # table if the appraisal comes in at the lowest ARV. The stress test is the figure to
    # plan around, so it is THE Cash Needed: there is no baseline variant.
    return (cash_out_figures.total_cash_invested + payload.rehab_cushion
            + cash_out_figures.cash_to_refi_table_conservative)
