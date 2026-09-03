"""Fetch the live sum of all active Mercury account balances, in $k.

The frontend uses this to re-anchor the liquidity timeline's opening balance
to today on page load. Raises `MercuryConfigError`/`MercuryApiError`
(domain exceptions, not HTTP) -- the router maps those to 503/502.
"""

from BL.liquidity.common.mercury_client import summarize_balance


def get_mercury_balance():
    return summarize_balance()
