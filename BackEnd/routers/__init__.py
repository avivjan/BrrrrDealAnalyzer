"""HTTP routers, grouped by endpoint division. Each router is unprefixed and
untagged; route paths, methods, and function names are unchanged from the
pre-refactor `main.py` so the OpenAPI contract stays byte-identical.
"""

from routers.analyze import router as analyze
from routers.reports import router as reports
from routers.active_deal import router as active_deal
from routers.bought_deal import router as bought_deal
from routers.email import router as email
from routers.liquidity import router as liquidity
from routers.pipeline_template import router as pipeline_template
from routers.health import router as health
from routers.reps import router as reps

# Matches the top-to-bottom endpoint definition order in the pre-refactor
# main.py.
ALL_ROUTERS = [
    analyze,
    reports,
    active_deal,
    bought_deal,
    email,
    liquidity,
    pipeline_template,
    health,
    reps,
]
