"""BRRRR step: Cash Needed -- the single definitive out-of-pocket capital through the refi."""

from decimal import Decimal


def total_cash_needed_step(payload, cash_out_figures):
    # If the refi wire is negative the investor brings that shortfall to the refi closing
    # table. The rehab cushion is capital held (not spent), so it is needed but never
    # counts as invested.
    refi_shortfall = max(Decimal("0"), -cash_out_figures.cash_out_routi)
    total_cash_needed = cash_out_figures.total_cash_invested + payload.rehab_cushion + refi_shortfall
    cash_needed_conservative = cash_out_figures.total_cash_invested + payload.rehab_cushion + cash_out_figures.cash_to_refi_table_conservative
    return refi_shortfall, total_cash_needed, cash_needed_conservative
