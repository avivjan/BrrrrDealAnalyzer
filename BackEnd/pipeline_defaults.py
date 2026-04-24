"""Default bought-deal pipeline templates.

Seed data + legacy integer → stable string ID mapping. IDs are stable string
slugs; once a default row is seeded into the `pipeline_templates` table, users
can freely rename / reorder / add / delete stages without touching these IDs.
"""

from typing import Any


# Default BRRRR pipeline. Stage / substage `id` values are permanent slugs.
DEFAULT_BRRRR_STAGES: list[dict[str, Any]] = [
    {
        "id": "purchase",
        "name": "Purchase",
        "subStages": [
            {"id": "purchase_agreement", "label": "Purchase Agreement"},
            {"id": "emd", "label": "EMD"},
        ],
    },
    {
        "id": "prepare_for_closing",
        "name": "Prepare for Closing",
        "subStages": [
            {"id": "lender_approval", "label": "Lender Approval"},
            {"id": "insurance", "label": "Insurance"},
            {"id": "title_insurance", "label": "Title Insurance"},
            {"id": "title_approval", "label": "Title Approval (Ready to Close)"},
            {"id": "understand_breakdown", "label": "Understand Breakdown"},
        ],
    },
    {
        "id": "closed",
        "name": "Closed",
        "subStages": [
            {"id": "save_package", "label": "Save Package"},
        ],
    },
    {
        "id": "rehab",
        "name": "Rehab",
        "subStages": [],
    },
    {
        "id": "rent",
        "name": "Rent",
        "subStages": [
            {"id": "decide_who_rents", "label": "Decide Who Rents It"},
            {"id": "pictures_ads", "label": "Pictures & Ads"},
        ],
    },
    {
        "id": "prepare_for_refi",
        "name": "Prepare for Refi",
        "subStages": [
            {"id": "choose_best_lender", "label": "Choose Best Lender"},
            {"id": "lender_approval_refi", "label": "Lender Approval"},
            {"id": "appraisal", "label": "Appraisal"},
            {"id": "decide_reserve", "label": "Decide on Reserve (Down/% /Max)"},
        ],
    },
    {
        "id": "refinanced",
        "name": "Refinanced",
        "subStages": [
            {"id": "save_package_refi", "label": "Save Package"},
        ],
    },
]


DEFAULT_FLIP_STAGES: list[dict[str, Any]] = [
    {
        "id": "purchase",
        "name": "Purchase",
        "subStages": [
            {"id": "purchase_agreement", "label": "Purchase Agreement"},
            {"id": "emd", "label": "EMD"},
        ],
    },
    {
        "id": "prepare_for_closing",
        "name": "Prepare for Closing",
        "subStages": [
            {"id": "lender_approval", "label": "Lender Approval"},
            {"id": "insurance", "label": "Insurance"},
            {"id": "title_insurance", "label": "Title Insurance"},
            {"id": "title_approval", "label": "Title Approval (Ready to Close)"},
        ],
    },
    {
        "id": "closed",
        "name": "Closed",
        "subStages": [],
    },
    {
        "id": "rehab",
        "name": "Rehab",
        "subStages": [],
    },
    {
        "id": "sell",
        "name": "Sell",
        "subStages": [
            {"id": "decide_who_sells", "label": "Decide Who Sells It"},
            {"id": "pictures_ads", "label": "Pictures & Ads"},
        ],
    },
    {
        "id": "sold",
        "name": "Sold",
        "subStages": [],
    },
]


def default_stages_for(deal_type: str) -> list[dict[str, Any]]:
    if deal_type == "BRRRR":
        return [dict(s, subStages=[dict(sub) for sub in s["subStages"]]) for s in DEFAULT_BRRRR_STAGES]
    if deal_type == "FLIP":
        return [dict(s, subStages=[dict(sub) for sub in s["subStages"]]) for s in DEFAULT_FLIP_STAGES]
    raise ValueError(f"Unknown deal_type: {deal_type}")
