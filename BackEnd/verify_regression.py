"""Golden-snapshot regression harness for the backend re-architecture.

One job: prove that splitting `main.py` into `routers / BL / DAL / ReqRes /
migrations` changed **nothing** a caller (or the database, or a deploy) can
observe.

    python3 verify_regression.py snapshot   # capture goldens from the current code
    python3 verify_regression.py verify     # recompute and assert bit-for-bit identity

Five snapshots land under `tests/_regression_snapshots/`:

    1. openapi.json      - the full `app.openapi()` contract
    2. schema.json       - every ORM table / column / default / index / constraint
                           (a drift here means the next deploy migrates a table)
    3. models.json       - Pydantic parse + serialize + JSON-schema + field config
                           for every request/response model, plus the months->days
                           shim in isolation
    4. calculations.json - every BRRRR / Flip metric across ~40 payloads, through
                           the HTTP layer and by direct call, plus every calculation
                           helper with fixed Decimal inputs - compared as repr()
    5. endpoints.json    - status + body + headers for a scripted pass through all
                           45 endpoints, happy and error paths

Determinism
-----------
* `$DATABASE_URL` is redirected at a throwaway SQLite file and `dotenv` is stubbed
  *before* the app is imported, exactly like `tests/conftest.py`.
* Google / Mercury / SMTP credentials are scrubbed from the environment so the
  integration endpoints take their deterministic, network-free "not configured"
  branch (502 / 503 / 500 / {"configured": false}).
* Volatile values (uuids, timestamps, auto-created dates) are redacted by key.
* Top-level list responses are sorted by content: two rows written in the same
  SQLite second share a `created_at`, so their order here is a coin flip. The
  ordering contract stays guarded by `tests/test_deal_crud.py`.

Helpers and models are resolved through `_resolve()`, which prefers the
post-refactor module path and falls back to the pre-refactor one, so this single
script captures the baseline *and* verifies the outcome.
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import os
import pathlib
import re
import sys
import tempfile
import uuid as uuid_module
from decimal import Decimal
from typing import Any, Callable

# ---------------------------------------------------------------------------
# 1. Flat imports: the app does `from db import ...`, so BackEnd/ must be on
#    sys.path no matter where this was invoked from.
# ---------------------------------------------------------------------------
BACKEND_DIR = pathlib.Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

SNAPSHOT_DIR = BACKEND_DIR / "tests" / "_regression_snapshots"

# ---------------------------------------------------------------------------
# 2. Hard database isolation, before any application import.
# ---------------------------------------------------------------------------
_TEST_DB_DIR = tempfile.mkdtemp(prefix="brrrr-verify-db-")
TEST_DB_PATH = pathlib.Path(_TEST_DB_DIR) / "verify.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# `main.py` calls load_dotenv(); BackEnd/.env carries live credentials a
# verification run has no business touching.
import dotenv  # noqa: E402

dotenv.load_dotenv = lambda *args, **kwargs: False  # type: ignore[assignment]

# Scrub every external-service credential so the integration endpoints take
# their deterministic "not configured" branch instead of hitting the network.
for _var in (
    "GOOGLE_APPLICATION_CREDENTIALS",
    "REPS_SHEET_ID_AVIV",
    "REPS_SHEET_ID_YARDEN",
    "REPS_GCS_BUCKET",
    "REPS_SHEET_TAB",
    "REPS_GCS_BASE_PREFIX",
    "REPS_PUBLIC_OBJECTS",
    "REPS_LINK_STYLE",
    "EMAIL_PASSWORD",
):
    os.environ.pop(_var, None)
for _var in [k for k in os.environ if k.startswith("MERCURY_API_TOKEN")]:
    os.environ.pop(_var, None)

# SQLite compatibility shim for `Uuid(as_uuid=True)` primary keys: production is
# Postgres, where psycopg2 adapts a plain string id in a WHERE clause. SQLite's
# bind processor calls `value.hex` and blows up on a str.
from sqlalchemy.sql import sqltypes  # noqa: E402

_original_uuid_bind_processor = sqltypes.Uuid.bind_processor


def _uuid_bind_processor(self, dialect):  # type: ignore[no-untyped-def]
    processor = _original_uuid_bind_processor(self, dialect)
    if processor is None:
        return None

    def process(value):
        if isinstance(value, str):
            try:
                value = uuid_module.UUID(value)
            except ValueError:
                pass
        return processor(value)

    return process


sqltypes.Uuid.bind_processor = _uuid_bind_processor  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# 3. Import the application. This runs create_all + migrations + seeding.
# ---------------------------------------------------------------------------
import db as app_db  # noqa: E402

if app_db.engine.url.get_backend_name() != "sqlite" or app_db.engine.url.database != str(
    TEST_DB_PATH
):
    raise RuntimeError(
        f"Refusing to run: engine is {app_db.engine.url!r}, not the temp SQLite file."
    )

import main as app_main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# `main` configures INFO logging on import; the endpoint battery walks every
# error path on purpose, so that would bury the result under stack traces.
logging.getLogger().setLevel(logging.CRITICAL)
for _noisy in ("httpx", "main", "reps_service", "mercury_service", "uvicorn"):
    logging.getLogger(_noisy).setLevel(logging.CRITICAL)

app = app_main.app


# ---------------------------------------------------------------------------
# 4. Refactor-agnostic resolution of calc helpers and Pydantic models.
# ---------------------------------------------------------------------------
def _resolve(name: str, *module_paths: str) -> Any:
    """Return `name` from the first of `module_paths` that provides it.

    Post-refactor paths first, pre-refactor last, so the same script captures the
    baseline and verifies the outcome.
    """
    tried: list[str] = []
    for path in module_paths:
        try:
            mod = importlib.import_module(path)
        except ImportError:
            tried.append(f"{path} (no module)")
            continue
        if hasattr(mod, name):
            return getattr(mod, name)
        tried.append(f"{path} (no attr)")
    raise ImportError(f"could not resolve {name!r}; tried: {', '.join(tried)}")


_MATH = ("BL.common.deal_math", "main")
_ANALYSIS = ("BL.common.deal_analysis", "main")

thousands_to_dollars = _resolve("thousands_to_dollars", *_MATH)
get_HML_amount = _resolve("get_HML_amount", *_MATH)
calc_montly_operating_expenses = _resolve("calc_montly_operating_expenses", *_MATH)
calcDSCR = _resolve("calcDSCR", *_MATH)
calc_cash_out_from_deal = _resolve("calc_cash_out_from_deal", *_MATH)
calc_cash_out_routi = _resolve("calc_cash_out_routi", *_MATH)
calc_mortgage_payment = _resolve("calc_mortgage_payment", *_MATH)
calc_cash_on_cash = _resolve("calc_cash_on_cash", *_MATH)
calc_roi = _resolve("calc_roi", *_MATH)
calc_holding_costs = _resolve("calc_holding_costs", *_MATH)
calc_HML_interest_in_cash = _resolve("calc_HML_interest_in_cash", *_MATH)
get_total_cash_needed_for_deal = _resolve("get_total_cash_needed_for_deal", *_MATH)
DAYS_PER_YEAR = _resolve("DAYS_PER_YEAR", *_MATH)
DAYS_PER_MONTH = _resolve("DAYS_PER_MONTH", *_MATH)
MONTHS_PER_YEAR = _resolve("MONTHS_PER_YEAR", *_MATH)

calculate_brrr_results = _resolve("calculate_brrr_results", *_ANALYSIS)
calculate_flip_results = _resolve("calculate_flip_results", *_ANALYSIS)

analyzeBRRRReq = _resolve(
    "analyzeBRRRReq", "ReqRes.common.analyze_inputs", "ReqRes.analyzeBRRR.analyzeBRRRReq"
)
analyzeFlipReq = _resolve(
    "analyzeFlipReq", "ReqRes.common.analyze_inputs", "ReqRes.analyzeFlip.analyzeFlipReq"
)
analyzeBRRRRes = _resolve(
    "analyzeBRRRRes", "ReqRes.common.analyze_results", "ReqRes.analyzeBRRR.analyzeBRRRRes"
)
analyzeFlipRes = _resolve(
    "analyzeFlipRes", "ReqRes.common.analyze_results", "ReqRes.analyzeFlip.analyzeFlipRes"
)

_ACTIVE = ("ReqRes.common.active_deal_schemas", "ReqRes.activeDeal.activeDealReq")
SoldComp = _resolve("SoldComp", "ReqRes.common.comps", *_ACTIVE)
RentComp = _resolve("RentComp", "ReqRes.common.comps", *_ACTIVE)
BaseDealReq = _resolve("BaseDealReq", "ReqRes.common.base_deal", *_ACTIVE)
BrrrActiveDealCreate = _resolve("BrrrActiveDealCreate", *_ACTIVE)
FlipActiveDealCreate = _resolve("FlipActiveDealCreate", *_ACTIVE)
BrrrActiveDealRes = _resolve("BrrrActiveDealRes", *_ACTIVE)
FlipActiveDealRes = _resolve("FlipActiveDealRes", *_ACTIVE)

_BOUGHT = ("ReqRes.common.bought_deal_schemas", "ReqRes.boughtDeal.boughtDealReq")
BoughtBrrrDealCreate = _resolve("BoughtBrrrDealCreate", *_BOUGHT)
BoughtFlipDealCreate = _resolve("BoughtFlipDealCreate", *_BOUGHT)
BoughtBrrrDealRes = _resolve("BoughtBrrrDealRes", *_BOUGHT)
BoughtFlipDealRes = _resolve("BoughtFlipDealRes", *_BOUGHT)

_LIQ = ("ReqRes.common.liquidity_schemas", "ReqRes.liquidity.liquidityReq")
LiquidityTransactionCreate = _resolve("LiquidityTransactionCreate", *_LIQ)
LiquidityTransactionUpdate = _resolve("LiquidityTransactionUpdate", *_LIQ)
LiquidityTransactionRes = _resolve("LiquidityTransactionRes", *_LIQ)
LiquidityRecurringTransactionCreate = _resolve("LiquidityRecurringTransactionCreate", *_LIQ)
LiquidityRecurringTransactionUpdate = _resolve("LiquidityRecurringTransactionUpdate", *_LIQ)
LiquidityRecurringTransactionRes = _resolve("LiquidityRecurringTransactionRes", *_LIQ)
LiquiditySettingsUpdate = _resolve("LiquiditySettingsUpdate", *_LIQ)
LiquiditySettingsRes = _resolve("LiquiditySettingsRes", *_LIQ)

_PIPE = ("ReqRes.common.pipeline_template_schemas", "ReqRes.pipelineTemplate")
PipelineSubStage = _resolve("PipelineSubStage", *_PIPE)
PipelineStage = _resolve("PipelineStage", *_PIPE)
PipelineTemplateUpsert = _resolve("PipelineTemplateUpsert", *_PIPE)
PipelineTemplateRes = _resolve("PipelineTemplateRes", *_PIPE)
PipelineStageStat = _resolve("PipelineStageStat", *_PIPE)
PipelineSubstageStat = _resolve("PipelineSubstageStat", *_PIPE)
PipelineTemplateStatsRes = _resolve("PipelineTemplateStatsRes", *_PIPE)

_REPS = ("ReqRes.common.reps_schemas", "ReqRes.reps.repsReq")
LocationSnapshot = _resolve("LocationSnapshot", *_REPS)
EvidenceItem = _resolve("EvidenceItem", *_REPS)
RepsLogCreate = _resolve("RepsLogCreate", *_REPS)
RepsLogRes = _resolve("RepsLogRes", *_REPS)
RepsEntryRow = _resolve("RepsEntryRow", *_REPS)
RepsStats = _resolve("RepsStats", *_REPS)
RepsEntriesEnvelope = _resolve("RepsEntriesEnvelope", *_REPS)
RepsPersonCreate = _resolve("RepsPersonCreate", *_REPS)
RepsPersonUpdate = _resolve("RepsPersonUpdate", *_REPS)
RepsPersonRes = _resolve("RepsPersonRes", *_REPS)
RepsPropertyOption = _resolve("RepsPropertyOption", *_REPS)
RepsPropertyCreate = _resolve("RepsPropertyCreate", *_REPS)
RepsActivityCategoryRes = _resolve("RepsActivityCategoryRes", *_REPS)
RepsActivityCategoryCreate = _resolve("RepsActivityCategoryCreate", *_REPS)
RepsUploadedFile = _resolve("RepsUploadedFile", *_REPS)
RepsUploadBatchRes = _resolve("RepsUploadBatchRes", *_REPS)

_EMAIL_REQ = ("ReqRes.common.send_offer_schemas", "ReqRes.email.sendOfferReq")
_EMAIL_RES = ("ReqRes.common.send_offer_schemas", "ReqRes.email.sendOfferRes")
SendOfferReq = _resolve("SendOfferReq", *_EMAIL_REQ)
SendOfferRes = _resolve("SendOfferRes", *_EMAIL_RES)

CalcStep = _resolve("CalcStep", "ReqRes.common.calc_step", "calc_breakdown")
days_from_legacy_months = _resolve(
    "days_from_legacy_months", "ReqRes.common.refi_timing", "ReqRes.refi_timing"
)

ensure_pipeline_defaults = _resolve(
    "ensure_defaults",
    "BL.pipelineTemplate.common.seed",
    "crud_pipeline_template",
)
ensure_activity_category_defaults = _resolve(
    "ensure_activity_category_defaults",
    "BL.reps.common.seed",
    "crud_reps",
)


# ---------------------------------------------------------------------------
# 5. Fixtures - the exact field names `DealInputsForm` emits.
# ---------------------------------------------------------------------------
BRRRR_PAYLOAD: dict[str, Any] = {
    "deal_type": "BRRRR",
    "purchasePrice": 200,
    "rehabCost": 50,
    "rehabContingency": 10,
    "closingCostsBuy": 5,
    "down_payment": 20,
    "hmlPoints": 2,
    "HMLInterestRate": 11,
    "use_HM_for_rehab": True,
    "annual_property_taxes": 3600,
    "annual_insurance": 1200,
    "montly_hoa": 0,
    "arv_in_thousands": 320,
    "daysUntilRefi": 180,
    "closingCostsRefi": 6,
    "refiPoints": 1.5,
    "cashReserve": 0,
    "loanTermYears": 30,
    "ltv_as_precent": 75,
    "interestRate": 6.5,
    "rent": 2600,
    "vacancyPercent": 5,
    "property_managment_fee_precentages_from_rent": 8,
    "maintenancePercent": 5,
    "capexPercent": 5,
    "address": "1 Shared Form St",
    "section": 2,
    "stage": 2,
}

FLIP_PAYLOAD: dict[str, Any] = {
    **BRRRR_PAYLOAD,
    "deal_type": "FLIP",
    "address": "2 Shared Form Ave",
    "salePrice": 320,
    "holdingTime": 6,
    "buyerAgentSellingFee": 3,
    "sellerAgentSellingFee": 3,
    "sellingClosingCosts": 5,
    "capitalGainsTax": 20,
    "monthly_utilities": 250,
}


def _brrr(**overrides: Any) -> dict[str, Any]:
    return {**BRRRR_PAYLOAD, **overrides}


def _flip(**overrides: Any) -> dict[str, Any]:
    return {**FLIP_PAYLOAD, **overrides}


#: Realistic + edge-case BRRRR payloads. Named so a diff points at the case.
BRRRR_CASES: list[tuple[str, dict[str, Any]]] = [
    ("baseline", _brrr()),
    ("no_rehab", _brrr(rehabCost=0, rehabContingency=0)),
    ("cash_rehab", _brrr(use_HM_for_rehab=False)),
    ("cash_rehab_no_hml_points", _brrr(use_HM_for_rehab=False, hmlPoints=0)),
    ("contingency_100", _brrr(rehabContingency=100)),
    ("ltv_100", _brrr(ltv_as_precent=100)),
    ("ltv_1", _brrr(ltv_as_precent=1)),
    ("one_day_refi", _brrr(daysUntilRefi=1)),
    ("year_refi", _brrr(daysUntilRefi=365)),
    ("ten_year_refi", _brrr(daysUntilRefi=3650)),
    ("cash_out_positive_sentinel", _brrr(arv_in_thousands=900, ltv_as_precent=90)),
    ("negative_cash_flow_sentinel", _brrr(rent=1, arv_in_thousands=900, ltv_as_precent=90)),
    ("zero_down", _brrr(down_payment=0)),
    ("all_cash", _brrr(down_payment=100, use_HM_for_rehab=False)),
    ("big_reserve", _brrr(cashReserve=45)),
    ("high_expenses", _brrr(vacancyPercent=25, maintenancePercent=25, capexPercent=25,
                            property_managment_fee_precentages_from_rent=24)),
    ("with_hoa", _brrr(montly_hoa=450)),
    ("tiny_magnitudes", _brrr(purchasePrice=1, arv_in_thousands=2, rehabCost=0.5, rent=10)),
    ("huge_magnitudes", _brrr(purchasePrice=25000, arv_in_thousands=40000, rehabCost=8000,
                              rent=250000)),
    ("short_loan_term", _brrr(loanTermYears=1)),
    ("zero_interest_refi", _brrr(interestRate=0)),
    ("legacy_months_payload", {k: v for k, v in _brrr().items() if k != "daysUntilRefi"}
     | {"monthsUntilRefi": 6}),
    ("omitted_optionals", {k: v for k, v in _brrr().items()
                           if k not in ("refiPoints", "cashReserve", "loanTermYears",
                                        "rehabContingency", "closingCostsRefi")}),
]

FLIP_CASES: list[tuple[str, dict[str, Any]]] = [
    ("baseline", _flip()),
    ("no_rehab", _flip(rehabCost=0, rehabContingency=0)),
    ("cash_rehab", _flip(use_HM_for_rehab=False)),
    ("contingency_100", _flip(rehabContingency=100)),
    ("one_month_hold", _flip(holdingTime=1)),
    ("two_year_hold", _flip(holdingTime=24)),
    ("loss_making", _flip(salePrice=180)),
    ("loss_no_cap_gains", _flip(salePrice=100, capitalGainsTax=40)),
    ("no_cap_gains_tax", _flip(capitalGainsTax=0)),
    ("high_cap_gains", _flip(capitalGainsTax=50)),
    ("zero_down", _flip(down_payment=0)),
    ("all_cash", _flip(down_payment=100, use_HM_for_rehab=False)),
    ("no_agent_fees", _flip(buyerAgentSellingFee=0, sellerAgentSellingFee=0)),
    ("high_agent_fees", _flip(buyerAgentSellingFee=6, sellerAgentSellingFee=6)),
    ("with_hoa_and_utilities", _flip(montly_hoa=300, monthly_utilities=500)),
    ("tiny_magnitudes", _flip(purchasePrice=1, salePrice=3, rehabCost=0.5)),
    ("huge_magnitudes", _flip(purchasePrice=25000, salePrice=40000, rehabCost=8000)),
    ("zero_hml_rate", _flip(HMLInterestRate=0)),
    ("omitted_optionals", {k: v for k, v in _flip().items()
                           if k not in ("rehabContingency", "capitalGainsTax",
                                        "monthly_utilities", "sellingClosingCosts")}),
]

#: Payloads that must be rejected.
BRRRR_INVALID_CASES: list[tuple[str, dict[str, Any]]] = [
    ("arv_zero", _brrr(arv_in_thousands=0)),
    ("purchase_zero", _brrr(purchasePrice=0)),
    ("rent_zero", _brrr(rent=0)),
    ("ltv_over_100", _brrr(ltv_as_precent=150)),
    ("negative_rehab", _brrr(rehabCost=-5)),
    ("zero_days_until_refi", _brrr(daysUntilRefi=0)),
    ("many_errors_at_once", _brrr(arv_in_thousands=0, purchasePrice=0, rent=0,
                                  ltv_as_precent=150, rehabCost=-5, daysUntilRefi=0,
                                  down_payment=-1, loanTermYears=0)),
]

FLIP_INVALID_CASES: list[tuple[str, dict[str, Any]]] = [
    ("sale_price_zero", _flip(salePrice=0)),
    ("purchase_zero", _flip(purchasePrice=0)),
    ("negative_selling_closing", _flip(sellingClosingCosts=-1)),
    ("many_errors_at_once", _flip(salePrice=0, purchasePrice=0, holdingTime=0,
                                  buyerAgentSellingFee=200)),
]


# ---------------------------------------------------------------------------
# 6. Normalisation helpers.
# ---------------------------------------------------------------------------
#: Values that legitimately differ run-to-run and carry no contract meaning.
VOLATILE_KEYS = {
    "id",
    "created_at",
    "updated_at",
    "sourceDealId",
    "source_deal_id",
    "opening_balance_date",  # GET /liquidity/settings auto-creates with today()
    "spreadsheet_id",
    "appended_range",
}

_UUID_DASHED_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_UUID_HEX_RE = re.compile(r"\b[0-9a-fA-F]{32}\b")
_MEM_ADDRESS_RE = re.compile(r" at 0x[0-9a-fA-F]+")


def _scrub_text(text: str) -> str:
    text = _UUID_DASHED_RE.sub("<uuid>", text)
    text = _UUID_HEX_RE.sub("<uuid>", text)
    return _MEM_ADDRESS_RE.sub("", text)


def _redact(value: Any) -> Any:
    """Replace volatile values by key, recursively, preserving null-ness."""
    if isinstance(value, dict):
        out = {}
        for key, val in value.items():
            if key in VOLATILE_KEYS:
                out[key] = None if val is None else f"<{key}>"
            else:
                out[key] = _redact(val)
        return out
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, str):
        return _scrub_text(value)
    return value


def _sort_list(value: Any) -> Any:
    """Order a top-level list response by content so row order cannot flake."""
    if isinstance(value, list):
        return sorted(value, key=lambda item: json.dumps(item, sort_keys=True, default=str))
    return value


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, default=str)


def _diff(expected: Any, actual: Any, path: str = "") -> list[str]:
    """Recursively locate every difference, reporting dotted paths."""
    problems: list[str] = []
    if type(expected) is not type(actual) and not (
        isinstance(expected, (int, float)) and isinstance(actual, (int, float))
    ):
        return [f"{path or '<root>'}: type {type(expected).__name__} -> {type(actual).__name__}"]

    if isinstance(expected, dict):
        for key in expected.keys() - actual.keys():
            problems.append(f"{path}.{key}: REMOVED (was {expected[key]!r})")
        for key in actual.keys() - expected.keys():
            problems.append(f"{path}.{key}: ADDED (now {actual[key]!r})")
        for key in expected.keys() & actual.keys():
            problems.extend(_diff(expected[key], actual[key], f"{path}.{key}"))
        return problems

    if isinstance(expected, list):
        if len(expected) != len(actual):
            problems.append(f"{path}: length {len(expected)} -> {len(actual)}")
        for idx, (exp, act) in enumerate(zip(expected, actual)):
            problems.extend(_diff(exp, act, f"{path}[{idx}]"))
        return problems

    if expected != actual:
        problems.append(f"{path or '<root>'}: {expected!r} -> {actual!r}")
    return problems


# ---------------------------------------------------------------------------
# 7. Snapshot 1 - the OpenAPI contract.
# ---------------------------------------------------------------------------
def capture_openapi() -> dict[str, Any]:
    # `app.openapi()` memoises; drop the cache so a re-run reflects the routes.
    app.openapi_schema = None
    return app.openapi()


# ---------------------------------------------------------------------------
# 8. Snapshot 2 - the database schema, column by column.
# ---------------------------------------------------------------------------
def _safe_python_type(coltype: Any) -> bool:
    try:
        coltype.python_type  # noqa: B018
        return True
    except (NotImplementedError, AttributeError):
        return False


def _describe_default(default: Any) -> Any:
    if default is None:
        return None
    arg = getattr(default, "arg", None)
    if arg is None:
        return _scrub_text(repr(default))
    if callable(arg):
        return f"callable:{getattr(arg, '__name__', _scrub_text(repr(arg)))}"
    return _scrub_text(repr(arg))


def _describe_server_default(server_default: Any) -> Any:
    if server_default is None:
        return None
    arg = getattr(server_default, "arg", None)
    return _scrub_text(str(arg) if arg is not None else repr(server_default))


def capture_schema() -> dict[str, Any]:
    """Every table / column / default as SQLAlchemy sees it.

    A drift here means the next deploy would try to migrate a production table.
    """
    tables: dict[str, Any] = {}
    for table in sorted(app_db.Base.metadata.tables.values(), key=lambda t: t.name):
        columns = []
        for col in table.columns:
            columns.append(
                {
                    "name": col.name,
                    "type": str(col.type),
                    "python_type": getattr(col.type, "python_type", None).__name__
                    if _safe_python_type(col.type)
                    else None,
                    "nullable": col.nullable,
                    "primary_key": col.primary_key,
                    "unique": col.unique,
                    "index": col.index,
                    "autoincrement": str(col.autoincrement),
                    "default": _describe_default(col.default),
                    "server_default": _describe_server_default(col.server_default),
                    "onupdate": _describe_default(col.onupdate),
                    "foreign_keys": sorted(str(fk.target_fullname) for fk in col.foreign_keys),
                }
            )
        tables[table.name] = {
            "columns": columns,
            "primary_key": [c.name for c in table.primary_key.columns],
            "indexes": sorted(
                (
                    {"name": ix.name, "columns": sorted(c.name for c in ix.columns),
                     "unique": bool(ix.unique)}
                    for ix in table.indexes
                ),
                key=lambda ix: str(ix["name"]),
            ),
            "constraints": sorted(
                type(c).__name__ + ":" + ",".join(sorted(col.name for col in c.columns))
                for c in table.constraints
            ),
        }
    return tables


# ---------------------------------------------------------------------------
# 9. Snapshot 3 - Pydantic aliases, defaults, validators, serialization.
# ---------------------------------------------------------------------------
def _normalise_error(exc: Exception) -> Any:
    """Pydantic error payloads carry a version-specific docs URL; strip it."""
    errors = getattr(exc, "errors", None)
    if not callable(errors):
        return str(exc)
    cleaned = []
    for err in errors():
        cleaned.append(
            {
                "type": err.get("type"),
                "loc": list(err.get("loc", ())),
                "msg": err.get("msg"),
            }
        )
    return cleaned


def _model_case(model: Any, payload: Any) -> dict[str, Any]:
    """Parse `payload` with `model` and record everything observable."""
    try:
        instance = model.model_validate(payload)
    except Exception as exc:  # a rejection is as much a contract as an accept
        return {"ok": False, "error_type": type(exc).__name__, "error": _normalise_error(exc)}
    return {
        "ok": True,
        "dump_by_alias": json.loads(instance.model_dump_json(by_alias=True)),
        "dump_by_field": json.loads(instance.model_dump_json(by_alias=False)),
        "dump_python_repr": repr(instance.model_dump(by_alias=True)),
        "exclude_unset": json.loads(instance.model_dump_json(by_alias=True, exclude_unset=True)),
    }


def capture_models() -> dict[str, Any]:
    today = "2024-03-05"
    cases: list[tuple[str, Any, Any]] = [
        # -- analyze inputs: every alias, every default, the legacy-months shim
        ("analyzeBRRRReq/full", analyzeBRRRReq, _brrr()),
        ("analyzeBRRRReq/minimal", analyzeBRRRReq, {
            "arv_in_thousands": 320, "purchasePrice": 200, "down_payment": 20,
            "HMLInterestRate": 11, "ltv_as_precent": 75, "interestRate": 6.5, "rent": 2600,
        }),
        ("analyzeBRRRReq/legacy_months_camel", analyzeBRRRReq, {
            k: v for k, v in _brrr().items() if k != "daysUntilRefi"
        } | {"monthsUntilRefi": 6}),
        ("analyzeBRRRReq/legacy_months_orm", analyzeBRRRReq, {
            k: v for k, v in _brrr().items() if k != "daysUntilRefi"
        } | {"Months_until_refi": 6}),
        ("analyzeBRRRReq/legacy_months_string", analyzeBRRRReq, {
            k: v for k, v in _brrr().items() if k != "daysUntilRefi"
        } | {"monthsUntilRefi": "6.0"}),
        ("analyzeBRRRReq/days_wins_over_months", analyzeBRRRReq,
         _brrr(daysUntilRefi=195) | {"monthsUntilRefi": 6}),
        ("analyzeBRRRReq/snake_alias_rejected", analyzeBRRRReq,
         {k: v for k, v in _brrr().items() if k != "purchasePrice"}
         | {"purchase_price_in_thousands": 200}),
        ("analyzeFlipReq/full", analyzeFlipReq, _flip()),
        ("analyzeFlipReq/minimal", analyzeFlipReq, {
            "purchasePrice": 200, "salePrice": 320, "down_payment": 20,
            "HMLInterestRate": 11, "holdingTime": 6,
        }),
        # -- analyze results
        ("analyzeBRRRRes/full", analyzeBRRRRes, {
            "cash_flow": 85.03674361688704, "dscr": 1.2, "cash_out": -1000.5,
            "cash_out_routi": 250.25, "cash_on_cash": 12.5, "roi": 30.0,
            "equity": 80000.0, "net_profit": 79000.0,
            "total_cash_needed_for_deal": 63525.0,
            "total_cash_needed_for_deal_with_buffer": 75000.0,
            "messages": ["a note"],
            "breakdowns": {"cash_flow": [{"label": "x", "value": 1.5, "formula": "1 + 0.5"}]},
        }),
        ("analyzeBRRRRes/minimal", analyzeBRRRRes, {"cash_flow": 0.0}),
        ("analyzeFlipRes/full", analyzeFlipRes, {
            "net_profit": 12620.0, "roi": 20.0, "annualized_roi": 40.0,
            "total_cash_needed": 63525.0, "total_cash_needed_with_buffer": 75000.0,
            "total_holding_costs": 9000.0, "total_hml_interest": 5000.0,
            "messages": [], "breakdowns": {},
        }),
        ("CalcStep", CalcStep, {"label": "Operating Expenses", "value": 812.5,
                                "formula": "$2600 - $1787.50 = $812.50"}),
        # -- sub-models
        ("SoldComp", SoldComp, {"url": "http://x", "arv": "310.5", "how_long_ago": "2mo"}),
        ("SoldComp/empty", SoldComp, {}),
        ("RentComp", RentComp, {"url": "http://y", "rent": "2600", "time_on_market": "10d"}),
        ("RentComp/empty", RentComp, {}),
        # -- deal create/response models (populate_by_name + from_attributes)
        ("BrrrActiveDealCreate/aliases", BrrrActiveDealCreate, _brrr()),
        ("BrrrActiveDealCreate/field_names", BrrrActiveDealCreate, {
            "deal_type": "BRRRR", "address": "1 Field St", "section": 1, "stage": 1,
            "purchase_price_in_thousands": 200, "rehab_cost_in_thousands": 50,
            "closing_costs_buy_in_thousands": 5, "down_payment": 20,
            "HML_points": 2, "HML_interest_rate": 11,
            "ltv_as_precent": 75, "days_until_refi": 180, "refi_points": 2,
            "cash_reserve_in_thousands": 0, "loan_term_years": 30,
        }),
        ("BrrrActiveDealCreate/defaults_only", BrrrActiveDealCreate, {
            "address": "1 Default St", "section": None, "stage": None,
            "ltv_as_precent": None,
        }),
        ("BrrrActiveDealCreate/legacy_months", BrrrActiveDealCreate,
         {k: v for k, v in _brrr().items() if k != "daysUntilRefi"} | {"monthsUntilRefi": 6}),
        ("BrrrActiveDealCreate/with_comps", BrrrActiveDealCreate, _brrr(
            sold_comps=[{"url": "http://s", "arv": 310, "how_long_ago": "2mo"}],
            rent_comps=[{"url": "http://r", "rent": 2500, "time_on_market": "5d"}],
        )),
        ("FlipActiveDealCreate/aliases", FlipActiveDealCreate, _flip()),
        ("FlipActiveDealCreate/missing_required", FlipActiveDealCreate, {
            "address": "x", "section": 1, "stage": 1,
        }),
        ("BrrrActiveDealRes", BrrrActiveDealRes, _brrr(
            id="11111111-1111-1111-1111-111111111111",
            created_at="2024-01-02T03:04:05+00:00",
            updated_at="2024-01-02T03:04:06+00:00",
            cash_flow=85.03674361688704,
        )),
        ("FlipActiveDealRes", FlipActiveDealRes, _flip(
            id="22222222-2222-2222-2222-222222222222",
            created_at="2024-01-02T03:04:05+00:00",
            updated_at="2024-01-02T03:04:06+00:00",
            net_profit=12620.0, roi=20.0, annualized_roi=40.0,
            total_cash_needed=63525.0, total_cash_needed_with_buffer=75000.0,
            total_holding_costs=9000.0, total_hml_interest=5000.0,
        )),
        ("BoughtBrrrDealCreate/defaults", BoughtBrrrDealCreate, _brrr()),
        ("BoughtBrrrDealCreate/aliases", BoughtBrrrDealCreate, _brrr(
            boughtStage="rehab", completedSubstages={"a": True, "b": False},
            sourceDealId="33333333-3333-3333-3333-333333333333",
        )),
        ("BoughtFlipDealCreate/defaults", BoughtFlipDealCreate, _flip()),
        ("BoughtBrrrDealRes", BoughtBrrrDealRes, _brrr(
            id="44444444-4444-4444-4444-444444444444",
            created_at="2024-01-02T03:04:05+00:00",
            updated_at="2024-01-02T03:04:06+00:00",
            cash_flow=1.0, boughtStage="purchase",
        )),
        ("BoughtFlipDealRes", BoughtFlipDealRes, _flip(
            id="55555555-5555-5555-5555-555555555555",
            created_at="2024-01-02T03:04:05+00:00",
            updated_at="2024-01-02T03:04:06+00:00",
            net_profit=1.0, roi=1.0, annualized_roi=1.0, total_cash_needed=1.0,
            total_cash_needed_with_buffer=1.0, total_holding_costs=1.0,
            total_hml_interest=1.0,
        )),
        # -- liquidity
        ("LiquidityTransactionCreate", LiquidityTransactionCreate, {
            "effective_date": today, "description": "HM draw", "amount_k": "-12.5",
        }),
        ("LiquidityTransactionCreate/blank_description", LiquidityTransactionCreate, {
            "effective_date": today, "description": "", "amount_k": 1,
        }),
        ("LiquidityTransactionCreate/long_description", LiquidityTransactionCreate, {
            "effective_date": today, "description": "x" * 501, "amount_k": 1,
        }),
        ("LiquidityTransactionUpdate/empty", LiquidityTransactionUpdate, {}),
        ("LiquidityTransactionRes", LiquidityTransactionRes, {
            "id": "abc", "effective_date": today, "description": "d", "amount_k": 1.5,
            "created_at": "2024-01-01T00:00:00", "updated_at": None,
        }),
        ("LiquidityRecurringCreate", LiquidityRecurringTransactionCreate, {
            "description": "rent", "amount_k": "2.6", "start_date": today,
            "end_date": "2025-03-05", "occurrences": 12, "frequency": "monthly",
            "interval": 1,
        }),
        ("LiquidityRecurringCreate/defaults", LiquidityRecurringTransactionCreate, {
            "description": "rent", "amount_k": 1, "start_date": today,
            "frequency": "weekly",
        }),
        ("LiquidityRecurringCreate/zero_amount", LiquidityRecurringTransactionCreate, {
            "description": "rent", "amount_k": 0, "start_date": today,
            "frequency": "weekly",
        }),
        ("LiquidityRecurringCreate/end_before_start", LiquidityRecurringTransactionCreate, {
            "description": "rent", "amount_k": 1, "start_date": today,
            "end_date": "2020-01-01", "frequency": "weekly",
        }),
        ("LiquidityRecurringCreate/bad_frequency", LiquidityRecurringTransactionCreate, {
            "description": "rent", "amount_k": 1, "start_date": today,
            "frequency": "fortnightly",
        }),
        ("LiquidityRecurringCreate/interval_out_of_range",
         LiquidityRecurringTransactionCreate, {
             "description": "rent", "amount_k": 1, "start_date": today,
             "frequency": "weekly", "interval": 366,
         }),
        ("LiquidityRecurringCreate/occurrences_out_of_range",
         LiquidityRecurringTransactionCreate, {
             "description": "rent", "amount_k": 1, "start_date": today,
             "frequency": "weekly", "occurrences": 2001,
         }),
        ("LiquidityRecurringUpdate/empty", LiquidityRecurringTransactionUpdate, {}),
        ("LiquidityRecurringRes", LiquidityRecurringTransactionRes, {
            "id": "abc", "description": "d", "amount_k": 1.5, "start_date": today,
            "frequency": "monthly", "interval": 2,
        }),
        ("LiquiditySettingsUpdate/empty", LiquiditySettingsUpdate, {}),
        ("LiquiditySettingsUpdate/full", LiquiditySettingsUpdate, {
            "opening_balance_k": "12.3456", "opening_balance_date": today, "reserve_k": "5",
        }),
        ("LiquiditySettingsRes", LiquiditySettingsRes, {
            "opening_balance_k": 12.3456, "opening_balance_date": today, "reserve_k": 5.0,
        }),
        # -- pipeline templates
        ("PipelineSubStage", PipelineSubStage, {"id": "  a  ", "label": "  Label  "}),
        ("PipelineSubStage/blank_id", PipelineSubStage, {"id": "   ", "label": "L"}),
        ("PipelineStage", PipelineStage, {
            "id": "purchase", "name": "Purchase",
            "subStages": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        }),
        ("PipelineStage/duplicate_substage", PipelineStage, {
            "id": "purchase", "name": "Purchase",
            "subStages": [{"id": "a", "label": "A"}, {"id": "a", "label": "B"}],
        }),
        ("PipelineStage/no_substages", PipelineStage, {"id": "s", "name": "S"}),
        ("PipelineTemplateUpsert", PipelineTemplateUpsert, {
            "stages": [{"id": "s1", "name": "One", "subStages": []},
                       {"id": "s2", "name": "Two", "subStages": [{"id": "x", "label": "X"}]}],
        }),
        ("PipelineTemplateUpsert/empty_stages", PipelineTemplateUpsert, {"stages": []}),
        ("PipelineTemplateUpsert/duplicate_stage", PipelineTemplateUpsert, {
            "stages": [{"id": "s1", "name": "One"}, {"id": "s1", "name": "Two"}],
        }),
        ("PipelineTemplateRes", PipelineTemplateRes, {
            "dealType": "BRRRR", "stages": [{"id": "s", "name": "S", "subStages": []}],
            "updated_at": "2024-01-01T00:00:00",
        }),
        ("PipelineTemplateRes/bad_deal_type", PipelineTemplateRes, {
            "dealType": "NOPE", "stages": [],
        }),
        ("PipelineSubstageStat", PipelineSubstageStat, {"substageId": "a",
                                                       "dealsWithCompletion": 3}),
        ("PipelineStageStat", PipelineStageStat, {"stageId": "s", "dealCount": 2}),
        ("PipelineTemplateStatsRes", PipelineTemplateStatsRes, {
            "dealType": "FLIP", "stages": [], "orphanStageDealCount": 4,
        }),
        # -- send offer
        ("SendOfferReq", SendOfferReq, {
            "agent_name": "A", "agent_email": "a@b.c", "property_address": "1 St",
            "purchase_price": "200.5", "inspection_period_days": 10,
        }),
        ("SendOfferRes", SendOfferRes, {"message": "ok", "success": True}),
        # -- REPS
        ("LocationSnapshot", LocationSnapshot, {
            "kind": "timer_start", "captured_at": "2024-01-01T00:00:00+00:00",
            "lat": 25.7, "lng": -80.2, "accuracy_m": 12.5, "note": "on site",
        }),
        ("LocationSnapshot/bad_kind", LocationSnapshot, {
            "kind": "nope", "captured_at": "2024-01-01T00:00:00+00:00",
        }),
        ("LocationSnapshot/lat_out_of_range", LocationSnapshot, {
            "kind": "bookmark", "captured_at": "2024-01-01T00:00:00+00:00", "lat": 91,
        }),
        ("EvidenceItem", EvidenceItem, {"url": "http://x", "label": "Closing meeting"}),
        ("EvidenceItem/blank_url", EvidenceItem, {"url": ""}),
        ("RepsLogCreate", RepsLogCreate, {
            "user": "Aviv2026", "property_name": "1 St", "activity_category": "Rehab",
            "description": "A sufficiently long description of the work performed.",
            "start_time": "2024-01-01T09:00:00+00:00",
            "end_time": "2024-01-01T12:30:00+00:00",
            "evidence_items": [{"url": "http://x", "label": "photo"}],
            "location_snapshots": [{"kind": "timer_start",
                                    "captured_at": "2024-01-01T09:00:00+00:00"}],
            "material_participation_rentals": True, "people_involved": ["Bob"],
        }),
        ("RepsLogCreate/short_description", RepsLogCreate, {
            "user": "Aviv2026", "description": "too short",
            "start_time": "2024-01-01T09:00:00+00:00",
            "end_time": "2024-01-01T12:30:00+00:00",
        }),
        ("RepsLogCreate/end_before_start", RepsLogCreate, {
            "user": "Aviv2026",
            "description": "A sufficiently long description of the work performed.",
            "start_time": "2024-01-01T12:00:00+00:00",
            "end_time": "2024-01-01T09:00:00+00:00",
        }),
        ("RepsLogCreate/bad_user", RepsLogCreate, {
            "user": "Nobody2026",
            "description": "A sufficiently long description of the work performed.",
            "start_time": "2024-01-01T09:00:00+00:00",
            "end_time": "2024-01-01T12:30:00+00:00",
        }),
        ("RepsEntryRow/empty", RepsEntryRow, {}),
        ("RepsStats", RepsStats, {
            "user": "Yarden2026", "total_hours": 10.5, "material_hours": 5.25,
            "non_material_hours": 5.25, "entry_count": 3, "days_elapsed": 60,
            "days_in_year": 366, "year_progress_pct": 16.39, "reps_750_pct": 1.4,
            "material_500_pct": 1.05, "avg_daily_hours_total": 0.18,
            "avg_daily_hours_material": 0.09,
        }),
        ("RepsPersonCreate", RepsPersonCreate, {"name": "Bob", "role": "GC",
                                                "notes": "reliable"}),
        ("RepsPersonUpdate/empty", RepsPersonUpdate, {}),
        ("RepsPersonRes", RepsPersonRes, {"id": "abc", "name": "Bob"}),
        ("RepsPropertyOption", RepsPropertyOption, {"name": "1 St", "source": "bought"}),
        ("RepsPropertyOption/bad_source", RepsPropertyOption, {"name": "1 St",
                                                              "source": "nope"}),
        ("RepsPropertyCreate", RepsPropertyCreate, {"name": "1 St"}),
        ("RepsActivityCategoryRes", RepsActivityCategoryRes, {"id": "abc", "name": "Rehab"}),
        ("RepsActivityCategoryCreate", RepsActivityCategoryCreate, {"name": "Rehab"}),
        ("RepsUploadedFile", RepsUploadedFile, {"name": "a.png", "url": "http://x"}),
        ("RepsUploadBatchRes", RepsUploadBatchRes, {"folder_path": "p"}),
    ]

    parsed = {name: _model_case(model, payload) for name, model, payload in cases}

    schema_models = {
        m.__name__: m
        for m in (
            analyzeBRRRReq, analyzeFlipReq, analyzeBRRRRes, analyzeFlipRes, CalcStep,
            SoldComp, RentComp, BaseDealReq,
            BrrrActiveDealCreate, FlipActiveDealCreate, BrrrActiveDealRes, FlipActiveDealRes,
            BoughtBrrrDealCreate, BoughtFlipDealCreate, BoughtBrrrDealRes, BoughtFlipDealRes,
            LiquidityTransactionCreate, LiquidityTransactionUpdate, LiquidityTransactionRes,
            LiquidityRecurringTransactionCreate, LiquidityRecurringTransactionUpdate,
            LiquidityRecurringTransactionRes,
            LiquiditySettingsUpdate, LiquiditySettingsRes,
            PipelineSubStage, PipelineStage, PipelineTemplateUpsert, PipelineTemplateRes,
            PipelineSubstageStat, PipelineStageStat, PipelineTemplateStatsRes,
            SendOfferReq, SendOfferRes,
            LocationSnapshot, EvidenceItem, RepsLogCreate, RepsLogRes, RepsEntryRow,
            RepsStats, RepsEntriesEnvelope,
            RepsPersonCreate, RepsPersonUpdate, RepsPersonRes,
            RepsPropertyOption, RepsPropertyCreate,
            RepsActivityCategoryRes, RepsActivityCategoryCreate,
            RepsUploadedFile, RepsUploadBatchRes,
        )
    }
    schemas = {name: model.model_json_schema() for name, model in sorted(schema_models.items())}

    config = {
        name: {
            "populate_by_name": model.model_config.get("populate_by_name"),
            "from_attributes": model.model_config.get("from_attributes"),
            "extra": model.model_config.get("extra"),
            "fields": {
                fname: {
                    "alias": finfo.alias,
                    "required": finfo.is_required(),
                    "default": "PydanticUndefined"
                    if repr(finfo.default) == "PydanticUndefined"
                    else repr(finfo.default),
                    "default_factory": getattr(finfo.default_factory, "__name__", None)
                    if finfo.default_factory
                    else None,
                    "annotation": str(finfo.annotation),
                }
                for fname, finfo in model.model_fields.items()
            },
        }
        for name, model in sorted(schema_models.items())
    }

    # The months -> days shim in isolation.
    shim = {}
    for label, value in [
        ("months_6", {"monthsUntilRefi": 6}),
        ("months_1", {"monthsUntilRefi": 1}),
        ("months_half", {"monthsUntilRefi": 0.5}),
        ("months_12", {"monthsUntilRefi": 12}),
        ("months_6_5", {"monthsUntilRefi": 6.5}),
        ("months_2_4", {"monthsUntilRefi": 2.4}),
        ("orm_spelling", {"Months_until_refi": 6}),
        ("string_decimal", {"monthsUntilRefi": "6.0"}),
        ("days_wins", {"daysUntilRefi": 195, "monthsUntilRefi": 6}),
        ("neither_key", {"purchasePrice": 200}),
        ("none_value", {"monthsUntilRefi": None}),
        ("empty_string", {"monthsUntilRefi": ""}),
        ("garbage", {"monthsUntilRefi": "abc"}),
        ("list_value", {"monthsUntilRefi": []}),
    ]:
        shim[label] = repr(days_from_legacy_months(value))
    shim["non_dict_passthrough"] = repr(days_from_legacy_months(("tuple",)))

    return {"parsed": parsed, "schemas": schemas, "config": config, "refi_shim": shim}


# ---------------------------------------------------------------------------
# 10. Snapshot 4 - calculations, to the last decimal place.
# ---------------------------------------------------------------------------
def capture_calculations(client: TestClient) -> dict[str, Any]:
    out: dict[str, Any] = {"constants": {}, "helpers": {}, "brrr": {}, "flip": {},
                           "brrr_invalid": {}, "flip_invalid": {}, "direct": {}}

    out["constants"] = {
        "DAYS_PER_YEAR": repr(DAYS_PER_YEAR),
        "DAYS_PER_MONTH": repr(DAYS_PER_MONTH),
        "MONTHS_PER_YEAR": repr(MONTHS_PER_YEAR),
    }

    D = Decimal

    def rec(bucket: str, label: str, fn: Callable[[], Any]) -> None:
        try:
            out[bucket][label] = repr(fn())
        except Exception as exc:
            out[bucket][label] = f"RAISED {type(exc).__name__}"

    for v in ("0", "1", "0.5", "200", "1234.5678", "-50", "99999999"):
        rec("helpers", f"thousands_to_dollars({v})", lambda v=v: thousands_to_dollars(D(v)))

    for pp, dp, rc, hm in [
        ("200000", "20", "50000", True), ("200000", "20", "50000", False),
        ("200000", "0", "0", True), ("200000", "100", "50000", False),
        ("1000", "33.33", "500", True), ("0", "20", "0", False),
    ]:
        rec("helpers", f"get_HML_amount({pp},{dp},{rc},{hm})",
            lambda pp=pp, dp=dp, rc=rc, hm=hm: get_HML_amount(D(pp), D(dp), D(rc), hm))

    for t, i, h, d in [
        ("3600", "1200", "0", 180), ("3600", "1200", "250", 180),
        ("1200", "0", "0", 360), ("0", "1200", "0", 360), ("0", "0", "100", 360),
        ("3600", "1200", "250", 1), ("3600", "1200", "250", 30),
        ("3600", "1200", "250", 60), ("3600", "1200", "250", 3650),
        ("0", "0", "0", 180), ("1", "1", "1", 7),
    ]:
        rec("helpers", f"calc_holding_costs({t},{i},{h},{d})",
            lambda t=t, i=i, h=h, d=d: calc_holding_costs(D(t), D(i), D(h), d))

    for pp, dp, rc, d, r, hm in [
        ("200000", "20", "55000", 180, "11", True),
        ("200000", "20", "55000", 180, "11", False),
        ("200000", "20", "55000", 1, "11", True),
        ("200000", "20", "55000", 3650, "11", True),
        ("200000", "20", "55000", 180, "0", True),
        ("200000", "100", "0", 180, "11", False),
    ]:
        rec("helpers", f"calc_HML_interest_in_cash({pp},{dp},{rc},{d},{r},{hm})",
            lambda pp=pp, dp=dp, rc=rc, d=d, r=r, hm=hm: calc_HML_interest_in_cash(
                D(pp), D(dp), D(rc), d, D(r), hm))

    for arv, ltv, ir, yrs in [
        ("320000", "0.75", "6.5", 30), ("320000", "0.75", "6.5", 1),
        ("320000", "1", "6.5", 30), ("320000", "0.75", "0", 30),
        ("1000", "0.5", "12", 15), ("40000000", "0.8", "7.25", 30),
    ]:
        rec("helpers", f"calc_mortgage_payment({arv},{ltv},{ir},{yrs})",
            lambda arv=arv, ltv=ltv, ir=ir, yrs=yrs: calc_mortgage_payment(
                D(arv), D(ltv), D(ir), yrs))

    for rent, tax, ins, hoa, pmt in [
        ("2600", "3600", "1200", "0", "1500"), ("2600", "0", "0", "0", "0"),
        ("2600", "3600", "1200", "450", "1500"), ("0", "3600", "1200", "0", "1500"),
    ]:
        rec("helpers", f"calcDSCR({rent},{tax},{ins},{hoa},{pmt})",
            lambda rent=rent, tax=tax, ins=ins, hoa=hoa, pmt=pmt: calcDSCR(
                D(rent), D(tax), D(ins), D(hoa), D(pmt)))

    for co, cf in [("-10000", "500"), ("10000", "500"), ("-10000", "-500"),
                   ("0", "500"), ("-10000", "0"), ("-1", "1")]:
        rec("helpers", f"calc_cash_on_cash({co},{cf})",
            lambda co=co, cf=cf: calc_cash_on_cash(D(co), D(cf)))
    for co, cf, np_ in [("-10000", "500", "80000"), ("10000", "500", "80000"),
                        ("-10000", "-500", "80000"), ("-10000", "500", "-80000")]:
        rec("helpers", f"calc_roi({co},{cf},{np_})",
            lambda co=co, cf=cf, np_=np_: calc_roi(D(co), D(cf), D(np_)))

    cash_out_args = dict(arv=D("320000"), ltv=D("0.75"), down_payment_precent=D("20"),
                         purchase_price=D("200000"), closing_costs_buy=D("5000"),
                         HML_points_in_cash=D("4300"), rehab_cost=D("55000"),
                         HML_interest_in_cash=D("11825"), closing_cost_refi=D("6000"),
                         refi_points_in_cash=D("3600"), use_HM_for_rehab=True,
                         holding_costs_until_refi=D("2400"))
    rec("helpers", "calc_cash_out_from_deal/baseline",
        lambda: calc_cash_out_from_deal(**cash_out_args))
    rec("helpers", "calc_cash_out_from_deal/with_reserve",
        lambda: calc_cash_out_from_deal(**cash_out_args, cash_reserve_in_cash=D("45000")))
    rec("helpers", "calc_cash_out_from_deal/cash_rehab",
        lambda: calc_cash_out_from_deal(**{**cash_out_args, "use_HM_for_rehab": False}))
    routi_args = dict(arv=D("320000"), ltv=D("0.75"), down_payment_precent=D("20"),
                      purchase_price=D("200000"), rehab_cost=D("55000"),
                      closing_cost_refi=D("6000"), refi_points_in_cash=D("3600"),
                      use_HM_for_rehab=True)
    rec("helpers", "calc_cash_out_routi/baseline", lambda: calc_cash_out_routi(**routi_args))
    rec("helpers", "calc_cash_out_routi/with_reserve",
        lambda: calc_cash_out_routi(**routi_args, cash_reserve_in_cash=D("45000")))
    rec("helpers", "calc_cash_out_routi/cash_rehab",
        lambda: calc_cash_out_routi(**{**routi_args, "use_HM_for_rehab": False}))

    for hm in (True, False):
        rec("helpers", f"get_total_cash_needed_for_deal(use_HM={hm})",
            lambda hm=hm: get_total_cash_needed_for_deal(
                D("20"), D("200000"), D("2400"), D("5000"), D("4300"), D("55000"),
                D("11825"), hm))
    rec("helpers", "get_total_cash_needed_for_deal/zeros",
        lambda: get_total_cash_needed_for_deal(D("0"), D("0"), D("0"), D("0"), D("0"),
                                               D("0"), D("0"), False))

    for label, payload in [("baseline", _brrr()), ("no_expenses", _brrr(
            vacancyPercent=0, maintenancePercent=0, capexPercent=0,
            property_managment_fee_precentages_from_rent=0, annual_property_taxes=0,
            annual_insurance=0, montly_hoa=0))]:
        rec("helpers", f"calc_montly_operating_expenses/{label}",
            lambda payload=payload: calc_montly_operating_expenses(
                analyzeBRRRReq.model_validate(payload)))

    # Direct orchestrator calls: the full Res model, pre-serialization.
    for name, payload in BRRRR_CASES:
        rec("direct", f"calculate_brrr_results/{name}",
            lambda payload=payload: calculate_brrr_results(
                analyzeBRRRReq.model_validate(payload)).model_dump())
    for name, payload in FLIP_CASES:
        rec("direct", f"calculate_flip_results/{name}",
            lambda payload=payload: calculate_flip_results(
                analyzeFlipReq.model_validate(payload)).model_dump())

    # Through the HTTP layer: validation + calc + response serialization.
    for name, payload in BRRRR_CASES:
        response = client.post("/analyze/brrr", json=payload)
        out["brrr"][name] = {"status": response.status_code, "body": response.json()}
    for name, payload in FLIP_CASES:
        response = client.post("/analyze/flip", json=payload)
        out["flip"][name] = {"status": response.status_code, "body": response.json()}
    for name, payload in BRRRR_INVALID_CASES:
        response = client.post("/analyze/brrr", json=payload)
        out["brrr_invalid"][name] = {"status": response.status_code, "body": response.json()}
    for name, payload in FLIP_INVALID_CASES:
        response = client.post("/analyze/flip", json=payload)
        out["flip_invalid"][name] = {"status": response.status_code, "body": response.json()}

    return out


# ---------------------------------------------------------------------------
# 11. Snapshot 5 - every endpoint, happy and error paths.
# ---------------------------------------------------------------------------
def _reset_database() -> None:
    """Empty every table and re-seed, exactly like the pytest harness does."""
    with app_db.engine.begin() as connection:
        for table in reversed(app_db.Base.metadata.sorted_tables):
            connection.execute(table.delete())
    with app_db.SessionLocal() as session:
        ensure_pipeline_defaults(session)
        ensure_activity_category_defaults(session)


class _Recorder:
    """Runs a call, normalises the result, and files it under a label."""

    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.results: dict[str, Any] = {}

    def call(self, label: str, method: str, url: str, *, binary: bool = False,
             **kwargs: Any) -> Any:
        response = self.client.request(method, url, **kwargs)
        entry: dict[str, Any] = {
            "status": response.status_code,
            "content_type": response.headers.get("content-type"),
        }
        disposition = response.headers.get("content-disposition")
        if disposition is not None:
            entry["content_disposition"] = disposition

        if binary:
            # ReportLab stamps a creation date into the PDF, so the bytes are not
            # reproducible. The content is already pinned by the calculation
            # snapshot; here we only assert it rendered a PDF.
            entry["magic"] = response.content[:4].decode("latin-1")
            entry["nonempty"] = len(response.content) > 1000
        else:
            try:
                body = response.json()
            except ValueError:
                body = {"__raw__": response.text[:500]}
            entry["body"] = _sort_list(_redact(body))

        self.results[label] = entry
        return entry

    def get(self, label: str, url: str, **kw: Any) -> Any:
        return self.call(label, "GET", url, **kw)

    def post(self, label: str, url: str, **kw: Any) -> Any:
        return self.call(label, "POST", url, **kw)

    def put(self, label: str, url: str, **kw: Any) -> Any:
        return self.call(label, "PUT", url, **kw)

    def delete(self, label: str, url: str, **kw: Any) -> Any:
        return self.call(label, "DELETE", url, **kw)


MISSING_ID = "99999999-9999-9999-9999-999999999999"


def capture_endpoints(client: TestClient) -> dict[str, Any]:
    _reset_database()
    r = _Recorder(client)

    # -- health -----------------------------------------------------------
    r.get("helloworld", "/helloworld")

    # -- active deals ---------------------------------------------------------
    r.get("active_deals/list_empty", "/active-deals")
    brrr = client.post("/active-deals", json=BRRRR_PAYLOAD).json()
    flip = client.post("/active-deals", json=FLIP_PAYLOAD).json()
    r.results["active_deals/create_brrr"] = {"status": 200, "body": _redact(brrr)}
    r.results["active_deals/create_flip"] = {"status": 200, "body": _redact(flip)}
    brrr_id, flip_id = brrr["id"], flip["id"]

    r.get("active_deals/list", "/active-deals")
    r.put("active_deals/update_brrr", f"/active-deals/{brrr_id}",
          json={**brrr, "purchasePrice": 210, "rent": 2750})
    r.put("active_deals/update_flip", f"/active-deals/{flip_id}",
          json={**flip, "sellerAgentSellingFee": 4})
    r.put("active_deals/update_missing", f"/active-deals/{MISSING_ID}", json=brrr)
    r.put("active_deals/update_clears_optional", f"/active-deals/{brrr_id}",
          json={k: v for k, v in brrr.items() if k != "closingCostsBuy"})

    dup = client.post(f"/active-deals/{brrr_id}/duplicate", params={"deal_type": "BRRRR"}).json()
    r.results["active_deals/duplicate_brrr"] = {"status": 200, "body": _redact(dup)}
    r.post("active_deals/duplicate_missing", f"/active-deals/{MISSING_ID}/duplicate",
           params={"deal_type": "BRRRR"})
    r.post("active_deals/duplicate_bad_type", f"/active-deals/{brrr_id}/duplicate",
           params={"deal_type": "NOPE"})
    r.delete("active_deals/delete_dup", f"/active-deals/{dup['id']}",
             params={"deal_type": "BRRRR"})
    r.delete("active_deals/delete_missing", f"/active-deals/{MISSING_ID}",
             params={"deal_type": "BRRRR"})
    r.delete("active_deals/delete_bad_type", f"/active-deals/{brrr_id}",
             params={"deal_type": "NOPE"})

    # -- reports ------------------------------------------------------------
    r.post("reports/brrr_pdf", "/reports/brrr-pdf", json=BRRRR_PAYLOAD,
           params={"address": "1 Shared Form St"}, binary=True)
    r.post("reports/brrr_pdf_attachment", "/reports/brrr-pdf", json=BRRRR_PAYLOAD,
           params={"address": "1 Shared Form St", "disposition": "attachment"}, binary=True)
    r.post("reports/flip_pdf", "/reports/flip-pdf", json=FLIP_PAYLOAD,
           params={"address": "2 Shared Form Ave"}, binary=True)
    r.post("reports/brrr_pdf_invalid", "/reports/brrr-pdf",
           json=_brrr(arv_in_thousands=0), params={"address": "x"})
    r.post("reports/flip_pdf_invalid", "/reports/flip-pdf",
           json=_flip(salePrice=0), params={"address": "x"})

    # -- bought deals -----------------------------------------------------------
    r.get("bought_deals/list_empty", "/bought-deals")
    bought_brrr = client.post(f"/bought-deals/from-active/{brrr_id}",
                              params={"deal_type": "BRRRR"}).json()
    bought_flip = client.post(f"/bought-deals/from-active/{flip_id}",
                              params={"deal_type": "FLIP"}).json()
    r.results["bought_deals/from_active_brrr"] = {"status": 200, "body": _redact(bought_brrr)}
    r.results["bought_deals/from_active_flip"] = {"status": 200, "body": _redact(bought_flip)}
    r.post("bought_deals/from_active_missing", f"/bought-deals/from-active/{MISSING_ID}",
           params={"deal_type": "BRRRR"})
    r.post("bought_deals/from_active_missing_flip", f"/bought-deals/from-active/{MISSING_ID}",
           params={"deal_type": "FLIP"})
    r.post("bought_deals/from_active_bad_type", f"/bought-deals/from-active/{brrr_id}",
           params={"deal_type": "NOPE"})

    r.get("bought_deals/list", "/bought-deals")
    r.post("bought_deals/create_direct", "/bought-deals",
           json={**BRRRR_PAYLOAD, "address": "3 Direct Bought Rd"})
    r.put("bought_deals/update", f"/bought-deals/{bought_brrr['id']}",
          json={**bought_brrr, "rehabCost": 65, "boughtStage": "rehab",
                "completedSubstages": {"x": True}})
    r.put("bought_deals/update_missing", f"/bought-deals/{MISSING_ID}", json=bought_brrr)
    r.delete("bought_deals/delete", f"/bought-deals/{bought_flip['id']}",
             params={"deal_type": "FLIP"})
    r.delete("bought_deals/delete_missing", f"/bought-deals/{MISSING_ID}",
             params={"deal_type": "BRRRR"})
    r.delete("bought_deals/delete_bad_type", f"/bought-deals/{bought_brrr['id']}",
             params={"deal_type": "NOPE"})

    # -- pipeline templates -------------------------------------------------
    r.get("pipeline/list", "/pipeline-templates")
    r.get("pipeline/stats_brrrr", "/pipeline-templates/BRRRR/stats")
    r.get("pipeline/stats_flip", "/pipeline-templates/FLIP/stats")
    r.get("pipeline/stats_bad_type", "/pipeline-templates/NOPE/stats")
    r.put("pipeline/update_brrrr", "/pipeline-templates/BRRRR", json={
        "stages": [
            {"id": "purchase", "name": "Purchase",
             "subStages": [{"id": "title", "label": "Title"}]},
            {"id": "rehab", "name": "Rehab", "subStages": []},
        ]
    })
    r.put("pipeline/update_bad_type", "/pipeline-templates/NOPE", json={
        "stages": [{"id": "a", "name": "A", "subStages": []}]
    })
    r.put("pipeline/update_empty_stages", "/pipeline-templates/FLIP", json={"stages": []})
    r.put("pipeline/update_duplicate_stage", "/pipeline-templates/FLIP", json={
        "stages": [{"id": "a", "name": "A"}, {"id": "a", "name": "B"}]
    })
    r.get("pipeline/stats_after_update", "/pipeline-templates/BRRRR/stats")
    r.get("pipeline/list_after_update", "/pipeline-templates")

    # -- liquidity transactions ------------------------------------------------
    r.get("liquidity/txn_list_empty", "/liquidity/transactions")
    txn = client.post("/liquidity/transactions", json={
        "effective_date": "2024-03-05", "description": "HM draw", "amount_k": -12.5,
    }).json()
    r.results["liquidity/txn_create"] = {"status": 201, "body": _redact(txn)}
    r.post("liquidity/txn_create_blank_description", "/liquidity/transactions", json={
        "effective_date": "2024-03-05", "description": "", "amount_k": 1,
    })
    r.get("liquidity/txn_list", "/liquidity/transactions")
    r.put("liquidity/txn_update", f"/liquidity/transactions/{txn['id']}",
          json={"description": "HM draw (revised)", "amount_k": -13.25})
    r.put("liquidity/txn_update_empty", f"/liquidity/transactions/{txn['id']}", json={})
    r.put("liquidity/txn_update_missing", f"/liquidity/transactions/{MISSING_ID}",
          json={"description": "x"})
    r.delete("liquidity/txn_delete", f"/liquidity/transactions/{txn['id']}")
    r.delete("liquidity/txn_delete_missing", f"/liquidity/transactions/{MISSING_ID}")

    # -- liquidity recurring ------------------------------------------------
    r.get("liquidity/recurring_list_empty", "/liquidity/recurring")
    rule = client.post("/liquidity/recurring", json={
        "description": "Rent", "amount_k": 2.6, "start_date": "2024-03-05",
        "end_date": "2025-03-05", "occurrences": 12, "frequency": "monthly", "interval": 1,
    }).json()
    r.results["liquidity/recurring_create"] = {"status": 201, "body": _redact(rule)}
    r.post("liquidity/recurring_create_zero_amount", "/liquidity/recurring", json={
        "description": "Zero", "amount_k": 0, "start_date": "2024-03-05",
        "frequency": "monthly",
    })
    r.post("liquidity/recurring_create_bad_window", "/liquidity/recurring", json={
        "description": "Bad", "amount_k": 1, "start_date": "2024-03-05",
        "end_date": "2020-01-01", "frequency": "monthly",
    })
    r.post("liquidity/recurring_create_bad_frequency", "/liquidity/recurring", json={
        "description": "Bad", "amount_k": 1, "start_date": "2024-03-05",
        "frequency": "fortnightly",
    })
    r.get("liquidity/recurring_list", "/liquidity/recurring")
    r.put("liquidity/recurring_update", f"/liquidity/recurring/{rule['id']}",
          json={"description": "Rent (revised)", "interval": 2})
    r.put("liquidity/recurring_update_bad_window", f"/liquidity/recurring/{rule['id']}",
          json={"end_date": "2020-01-01"})
    r.put("liquidity/recurring_update_zero_amount", f"/liquidity/recurring/{rule['id']}",
          json={"amount_k": 0})
    r.put("liquidity/recurring_update_missing", f"/liquidity/recurring/{MISSING_ID}",
          json={"description": "x"})
    r.get("liquidity/recurring_after_updates", "/liquidity/recurring")
    r.delete("liquidity/recurring_delete", f"/liquidity/recurring/{rule['id']}")
    r.delete("liquidity/recurring_delete_missing", f"/liquidity/recurring/{MISSING_ID}")

    # -- liquidity settings + mercury --------------------------------------
    r.get("liquidity/settings_autocreate", "/liquidity/settings")
    r.put("liquidity/settings_update", "/liquidity/settings",
          json={"opening_balance_k": 123.4567, "opening_balance_date": "2024-03-05",
                "reserve_k": 7.5})
    r.get("liquidity/settings_after_update", "/liquidity/settings")
    r.put("liquidity/settings_partial", "/liquidity/settings", json={"reserve_k": 9})
    r.get("liquidity/mercury_balance_unconfigured", "/liquidity/mercury-balance")

    # -- email ------------------------------------------------------------
    r.post("email/send_offer_unconfigured", "/send-offer", json={
        "agent_name": "Agent", "agent_email": "agent@example.com",
        "property_address": "1 Shared Form St", "purchase_price": 200,
        "inspection_period_days": 10,
    })
    r.post("email/send_offer_invalid", "/send-offer", json={"agent_name": "Agent"})

    # -- REPS -----------------------------------------------------------------
    r.get("reps/config_status_unconfigured", "/reps/config-status")

    r.get("reps/people_list_empty", "/reps/people")
    person = client.post("/reps/people", json={"name": "Bob", "role": "GC",
                                               "notes": "reliable"}).json()
    r.results["reps/people_create"] = {"status": 201, "body": _redact(person)}
    r.post("reps/people_create_duplicate", "/reps/people", json={"name": "Bob"})
    r.post("reps/people_create_blank", "/reps/people", json={"name": ""})
    r.get("reps/people_list", "/reps/people")
    r.put("reps/people_update", f"/reps/people/{person['id']}", json={"role": "Contractor"})
    r.put("reps/people_update_missing", f"/reps/people/{MISSING_ID}", json={"role": "x"})
    r.delete("reps/people_delete", f"/reps/people/{person['id']}")
    r.delete("reps/people_delete_missing", f"/reps/people/{MISSING_ID}")

    r.get("reps/properties_list", "/reps/properties")
    prospect = client.post("/reps/properties", json={"name": "9 Prospect Ln"}).json()
    r.results["reps/properties_create"] = {"status": 201, "body": _redact(prospect)}
    r.post("reps/properties_create_idempotent", "/reps/properties",
           json={"name": "9 prospect ln"})
    r.post("reps/properties_create_blank", "/reps/properties", json={"name": ""})
    r.get("reps/properties_list_after", "/reps/properties")
    r.delete("reps/properties_delete_missing", f"/reps/properties/{MISSING_ID}")

    r.get("reps/categories_list_seeded", "/reps/activity-categories")
    category = client.post("/reps/activity-categories", json={"name": "Custom Work"}).json()
    r.results["reps/categories_create"] = {"status": 201, "body": _redact(category)}
    r.post("reps/categories_create_idempotent", "/reps/activity-categories",
           json={"name": "custom work"})
    r.post("reps/categories_create_blank", "/reps/activity-categories", json={"name": ""})
    r.get("reps/categories_list_after", "/reps/activity-categories")
    r.delete("reps/categories_delete", f"/reps/activity-categories/{category['id']}")
    r.delete("reps/categories_delete_missing", f"/reps/activity-categories/{MISSING_ID}")

    # REPS external-service endpoints: deterministic "not configured" branch.
    r.post("reps/log_unconfigured", "/reps/log", json={
        "user": "Aviv2026", "property_name": "1 Shared Form St",
        "activity_category": "Rehab",
        "description": "A sufficiently long description of the work performed today.",
        "start_time": "2024-03-05T09:00:00+00:00",
        "end_time": "2024-03-05T12:30:00+00:00",
        "material_participation_rentals": True, "people_involved": ["Bob"],
    })
    r.post("reps/log_bad_user", "/reps/log", json={
        "user": "Aviv2026",
        "description": "A sufficiently long description of the work performed today.",
        "start_time": "2024-03-05T12:00:00+00:00",
        "end_time": "2024-03-05T09:00:00+00:00",
    })
    r.get("reps/entries_unconfigured", "/reps/entries", params={"user": "Aviv2026"})
    r.get("reps/entries_bad_user", "/reps/entries", params={"user": "Nobody2026"})
    r.get("reps/entries_missing_user", "/reps/entries")
    r.post("reps/upload_unconfigured", "/reps/upload",
           data={"user": "Aviv2026"},
           files={"file": ("evidence.txt", b"hello", "text/plain")})
    r.post("reps/upload_bad_user", "/reps/upload",
           data={"user": "Nobody2026"},
           files={"file": ("evidence.txt", b"hello", "text/plain")})
    r.post("reps/upload_batch_unconfigured", "/reps/upload-batch",
           data={"user": "Aviv2026", "property_name": "1 St"},
           files=[("files", ("a.txt", b"a", "text/plain")),
                  ("files", ("b.txt", b"b", "text/plain"))])
    r.post("reps/upload_batch_bad_timestamp", "/reps/upload-batch",
           data={"user": "Aviv2026", "log_timestamp": "not-a-date"},
           files=[("files", ("a.txt", b"a", "text/plain"))])

    # -- final board state ------------------------------------------------------
    r.get("final/active_deals", "/active-deals")
    r.get("final/bought_deals", "/bought-deals")

    return r.results


# ---------------------------------------------------------------------------
# 12. Driver.
# ---------------------------------------------------------------------------
SNAPSHOTS: dict[str, Callable[[TestClient], Any]] = {
    "openapi": lambda client: capture_openapi(),
    "schema": lambda client: capture_schema(),
    "models": lambda client: capture_models(),
    "calculations": capture_calculations,
    "endpoints": capture_endpoints,
}


def _capture_all() -> dict[str, Any]:
    _reset_database()
    with TestClient(app) as client:
        return {name: fn(client) for name, fn in SNAPSHOTS.items()}


def cmd_snapshot() -> int:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    captured = _capture_all()
    for name, payload in captured.items():
        path = SNAPSHOT_DIR / f"{name}.json"
        path.write_text(_canonical(payload) + "\n", encoding="utf-8")
        print(f"  wrote {path.relative_to(BACKEND_DIR)}  ({path.stat().st_size:,} bytes)")
    print(f"\nBaseline captured into {SNAPSHOT_DIR.relative_to(BACKEND_DIR)}/")
    return 0


def cmd_verify() -> int:
    missing = [n for n in SNAPSHOTS if not (SNAPSHOT_DIR / f"{n}.json").exists()]
    if missing:
        print(f"No baseline for: {', '.join(missing)}. Run `snapshot` first.")
        return 2

    captured = _capture_all()
    failures = 0
    for name in SNAPSHOTS:
        expected = json.loads((SNAPSHOT_DIR / f"{name}.json").read_text(encoding="utf-8"))
        actual = json.loads(_canonical(captured[name]))
        problems = _diff(expected, actual)
        if problems:
            failures += 1
            print(f"\n  FAIL  {name}  ({len(problems)} difference(s))")
            for line in problems[:40]:
                print(f"          {line}")
            if len(problems) > 40:
                print(f"          ... and {len(problems) - 40} more")
        else:
            print(f"  OK    {name}")

    if failures:
        print(f"\n{failures} snapshot(s) DIFFER. The refactor changed observable behaviour.")
        return 1
    print("\nAll snapshots identical. No observable behaviour changed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("snapshot", "verify"))
    args = parser.parse_args()
    print(f"[verify_regression] db={TEST_DATABASE_URL}")
    return cmd_snapshot() if args.mode == "snapshot" else cmd_verify()


if __name__ == "__main__":
    sys.exit(main())
