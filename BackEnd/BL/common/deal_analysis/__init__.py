"""The BRRRR/Flip calculation orchestrators.

Both accept either the matching Pydantic request model (`analyzeBRRRReq` /
`analyzeFlipReq`) or an ORM deal row -- everything inside is duck-typed
attribute access, which is what lets `BL.common.deal_response.create_deal_response`
/ `create_bought_deal_response` pass a `BrrrActiveDeal`/`FlipActiveDeal`
straight in.

Each deal type lives in its own module (`brrr.py`, `flip.py`), broken into
named calculation steps that mirror the `breakdowns` dict's metric groupings.
This package re-exports the two public entry points so
`from BL.common.deal_analysis import calculate_brrr_results, calculate_flip_results`
resolves exactly as it did when this was a single module.
"""

from BL.common.deal_analysis.brrr import calculate_brrr_results
from BL.common.deal_analysis.flip import calculate_flip_results

__all__ = ["calculate_brrr_results", "calculate_flip_results"]
