"""Pydantic request/response schemas.

All model classes are defined once in ``ReqRes/common/``; the per-endpoint
``ReqRes/<division>/<endpoint>/`` modules are thin re-exports. This module
aggregates the public surface for convenience and for ``verify_regression.py``.
"""

from ReqRes.common.calc_step import CalcStep
from ReqRes.common.refi_timing import DAYS_PER_MONTH, days_from_legacy_months
from ReqRes.common.comps import SoldComp, RentComp
from ReqRes.common.base_deal import BaseDealReq
from ReqRes.common.analyze_inputs import analyzeBRRRReq, analyzeFlipReq
from ReqRes.common.analyze_results import analyzeBRRRRes, analyzeFlipRes
from ReqRes.common.active_deal_schemas import (
    BrrrActiveDealCreate,
    FlipActiveDealCreate,
    BrrrActiveDealRes,
    FlipActiveDealRes,
)
from ReqRes.common.bought_deal_schemas import (
    BoughtBrrrDealCreate,
    BoughtFlipDealCreate,
    BoughtBrrrDealRes,
    BoughtFlipDealRes,
)
from ReqRes.common.liquidity_schemas import (
    LiquidityFrequency,
    LiquidityTransactionCreate,
    LiquidityTransactionUpdate,
    LiquidityTransactionRes,
    LiquidityRecurringTransactionCreate,
    LiquidityRecurringTransactionUpdate,
    LiquidityRecurringTransactionRes,
    LiquiditySettingsUpdate,
    LiquiditySettingsRes,
)
from ReqRes.common.pipeline_template_schemas import (
    PipelineSubStage,
    PipelineStage,
    PipelineTemplateUpsert,
    PipelineTemplateRes,
    PipelineSubstageStat,
    PipelineStageStat,
    PipelineTemplateStatsRes,
)
from ReqRes.common.send_offer_schemas import SendOfferReq, SendOfferRes
from ReqRes.common.reps_schemas import (
    RepsUser,
    MIN_DESCRIPTION_LEN,
    LocationSnapshotKind,
    LocationSnapshot,
    EvidenceItem,
    RepsLogCreate,
    RepsLogRes,
    RepsEntryRow,
    RepsStats,
    RepsEntriesEnvelope,
    RepsPersonCreate,
    RepsPersonUpdate,
    RepsPersonRes,
    RepsPropertyOption,
    RepsPropertyCreate,
    RepsActivityCategoryRes,
    RepsActivityCategoryCreate,
    RepsUploadedFile,
    RepsUploadBatchRes,
)

__all__ = [
    "CalcStep",
    "DAYS_PER_MONTH",
    "days_from_legacy_months",
    "SoldComp",
    "RentComp",
    "BaseDealReq",
    "analyzeBRRRReq",
    "analyzeFlipReq",
    "analyzeBRRRRes",
    "analyzeFlipRes",
    "BrrrActiveDealCreate",
    "FlipActiveDealCreate",
    "BrrrActiveDealRes",
    "FlipActiveDealRes",
    "BoughtBrrrDealCreate",
    "BoughtFlipDealCreate",
    "BoughtBrrrDealRes",
    "BoughtFlipDealRes",
    "LiquidityFrequency",
    "LiquidityTransactionCreate",
    "LiquidityTransactionUpdate",
    "LiquidityTransactionRes",
    "LiquidityRecurringTransactionCreate",
    "LiquidityRecurringTransactionUpdate",
    "LiquidityRecurringTransactionRes",
    "LiquiditySettingsUpdate",
    "LiquiditySettingsRes",
    "PipelineSubStage",
    "PipelineStage",
    "PipelineTemplateUpsert",
    "PipelineTemplateRes",
    "PipelineSubstageStat",
    "PipelineStageStat",
    "PipelineTemplateStatsRes",
    "SendOfferReq",
    "SendOfferRes",
    "RepsUser",
    "MIN_DESCRIPTION_LEN",
    "LocationSnapshotKind",
    "LocationSnapshot",
    "EvidenceItem",
    "RepsLogCreate",
    "RepsLogRes",
    "RepsEntryRow",
    "RepsStats",
    "RepsEntriesEnvelope",
    "RepsPersonCreate",
    "RepsPersonUpdate",
    "RepsPersonRes",
    "RepsPropertyOption",
    "RepsPropertyCreate",
    "RepsActivityCategoryRes",
    "RepsActivityCategoryCreate",
    "RepsUploadedFile",
    "RepsUploadBatchRes",
]
