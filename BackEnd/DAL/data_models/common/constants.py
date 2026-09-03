"""Shared constants referenced by ORM models and the layers above them."""


# Stable-ID slugs used when the built-in pipeline defaults are first seeded
# and when migrating legacy integer `bought_stage` values to string IDs.
# NOTE: once assigned, these IDs must never change – they are referenced by
# `bought_stage` on existing deal rows and by keys in `completed_substages`.
DEFAULT_BRRRR_STAGE_SLUGS_BY_LEGACY_INT: dict[int, str] = {
    1: "purchase",
    2: "prepare_for_closing",
    3: "closed",
    4: "rehab",
    5: "rent",
    6: "prepare_for_refi",
    7: "refinanced",
}

DEFAULT_FLIP_STAGE_SLUGS_BY_LEGACY_INT: dict[int, str] = {
    1: "purchase",
    2: "prepare_for_closing",
    3: "closed",
    4: "rehab",
    5: "sell",
    6: "sold",
}


# Allowed `frequency` values on LiquidityRecurringTransaction. The frontend
# uses the same labels in its picker. Each value defines how the next event
# date is computed; `interval` multiplies the base unit (e.g. weekly+2 ==
# every two weeks, monthly+3 == every quarter).
LIQUIDITY_RECURRING_FREQUENCIES: tuple[str, ...] = (
    "daily",
    "weekly",
    "biweekly",
    "monthly",
    "quarterly",
    "yearly",
)


# Seeded once into RepsActivityCategory on first boot.
DEFAULT_REPS_ACTIVITY_CATEGORIES: list[str] = [
    "Acquisition / Underwriting",
    "Construction / Rehab Oversight",
    "Property Management",
    "Tenant / Leasing",
    "Bookkeeping / Admin",
    "Education / Research",
    "Travel — Property",
    "Refinance / Lender Calls",
    "Other",
]
