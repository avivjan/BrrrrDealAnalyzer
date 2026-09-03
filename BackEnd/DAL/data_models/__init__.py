"""ORM table definitions, grouped by endpoint division.

Importing this package registers every table on ``Base.metadata``. It is the
stable import surface for the layers above -- import models and shared
constants from here, not from the division sub-modules.
"""

from DAL.data_models.common.base_deal import BaseDeal
from DAL.data_models.common.constants import (
    DEFAULT_BRRRR_STAGE_SLUGS_BY_LEGACY_INT,
    DEFAULT_FLIP_STAGE_SLUGS_BY_LEGACY_INT,
    LIQUIDITY_RECURRING_FREQUENCIES,
    DEFAULT_REPS_ACTIVITY_CATEGORIES,
)
from DAL.data_models.activeDeal.deals import BrrrActiveDeal, FlipActiveDeal
from DAL.data_models.boughtDeal.deals import BoughtBrrrDeal, BoughtFlipDeal
from DAL.data_models.liquidity.models import (
    LiquidityTransaction,
    LiquidityRecurringTransaction,
    LiquiditySettings,
)
from DAL.data_models.pipelineTemplate.models import PipelineTemplate
from DAL.data_models.reps.models import (
    RepsPerson,
    RepsProperty,
    RepsActivityCategory,
)

__all__ = [
    "BaseDeal",
    "DEFAULT_BRRRR_STAGE_SLUGS_BY_LEGACY_INT",
    "DEFAULT_FLIP_STAGE_SLUGS_BY_LEGACY_INT",
    "LIQUIDITY_RECURRING_FREQUENCIES",
    "DEFAULT_REPS_ACTIVITY_CATEGORIES",
    "BrrrActiveDeal",
    "FlipActiveDeal",
    "BoughtBrrrDeal",
    "BoughtFlipDeal",
    "LiquidityTransaction",
    "LiquidityRecurringTransaction",
    "LiquiditySettings",
    "PipelineTemplate",
    "RepsPerson",
    "RepsProperty",
    "RepsActivityCategory",
]
