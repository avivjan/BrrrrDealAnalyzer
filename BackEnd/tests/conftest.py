"""Test harness with hard database isolation, on a throwaway PostgreSQL.

Everything up to the ``# --- fixtures ---`` marker executes at *import* time,
before pytest collects a single test. That ordering is not stylistic — it is
required:

* ``db.py`` reads ``$DATABASE_URL`` and builds its ``Engine`` at import time.
* ``main.py`` runs ``Base.metadata.create_all``, the migrations and the
  pipeline/REPS seeding at import time.

So by the time ``import main`` returns, a real database would already have been
connected to, migrated and written to. The only safe place to redirect it is
here, before the first application import.

The suite talks to a dedicated PostgreSQL that exists only for tests:

* locally, the container from ``BackEnd/docker-compose.test.yml``
  (``docker compose -f BackEnd/docker-compose.test.yml up -d --wait``);
* in CI, the ``postgres`` service container of the backend job.

``$DATABASE_URL`` from the environment is never used, whatever it says: it is
overwritten with ``$TEST_DATABASE_URL`` (default: the compose container) before
any application import, and the resulting engine is then verified — at import,
at session start and before every test — to be PostgreSQL on a loopback host
with a database whose name ends in ``_test``. Anything else aborts the run.
Once verified, the schema is dropped and recreated so every session starts from
the models as they are now, not from whatever the last run left behind.
"""

from __future__ import annotations

import os
import pathlib
import sys

import pytest

# ---------------------------------------------------------------------------
# 1. Flat imports. `main.py` does `from db import ...`, so BackEnd/ must be on
#    sys.path regardless of the directory pytest was invoked from.
# ---------------------------------------------------------------------------
BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# ---------------------------------------------------------------------------
# 2. Replace whatever DATABASE_URL the environment supplied, before any import.
#    Only TEST_DATABASE_URL is consulted; the production variable never is.
#    The rules live in tests/db_isolation_guard.py, shared with
#    verify_regression.py (and through it the Playwright backend server).
# ---------------------------------------------------------------------------
from tests.db_isolation_guard import (  # noqa: E402
    FORBIDDEN_URL_MARKERS as _FORBIDDEN_URL_MARKERS,
    LOOPBACK_HOSTS as _LOOPBACK_HOSTS,
    TEST_DB_SUFFIX as _TEST_DB_SUFFIX,
    assert_isolated as _assert_isolated,
    reset_schema as _reset_schema,
    resolve_test_database_url,
)

INHERITED_DATABASE_URL = os.environ.get("DATABASE_URL")
TEST_DATABASE_URL = resolve_test_database_url()

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# ---------------------------------------------------------------------------
# 3. Neutralise dotenv. `main.py` calls `load_dotenv()`, which defaults to
#    override=False and therefore cannot clobber the line above — but
#    BackEnd/.env also carries live GCS credentials, a Google Sheets id and an
#    email password. A test run has no business loading any of them, so the
#    loader is stubbed out before `main` can import it.
# ---------------------------------------------------------------------------
import dotenv  # noqa: E402

dotenv.load_dotenv = lambda *args, **kwargs: False  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 4. The safety guard, bound to this harness's expected URL.
# ---------------------------------------------------------------------------
def assert_isolated(engine) -> None:
    """Verify `engine` is the throwaway test PostgreSQL and nothing else.

    Called at import time, at session start, and before every single test.
    """
    _assert_isolated(engine, TEST_DATABASE_URL, INHERITED_DATABASE_URL)


# ---------------------------------------------------------------------------
# 5. Now — and only now — import the application.
# ---------------------------------------------------------------------------
import db as app_db  # noqa: E402

assert_isolated(app_db.engine)
_reset_schema(app_db.engine)

import main as app_main  # noqa: E402
from BL.pipelineTemplate.common.seed import ensure_defaults as ensure_pipeline_defaults  # noqa: E402
from DAL.crud.reps import ensure_activity_category_defaults  # noqa: E402

# `main` ran create_all + migrations + seeding on import. Re-verify that all of
# that landed on the test database and not somewhere else.
assert_isolated(app_db.engine)

app = app_main.app


# ---------------------------------------------------------------------------
# 6. Contain `get_db` inside the harness. `SessionLocal` is already bound to the
#    test engine, so this is belt-and-braces: it guarantees request-scoped
#    sessions come from the harness even if the app's wiring changes later.
# ---------------------------------------------------------------------------
def _override_get_db():
    session = app_db.SessionLocal()
    try:
        yield session
    finally:
        session.close()


app.dependency_overrides[app_db.get_db] = _override_get_db


def pytest_sessionstart(session) -> None:  # noqa: ARG001
    """Second gate, after plugins and any other conftest have had their turn."""
    assert_isolated(app_db.engine)


# --- fixtures ---------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_database():
    """Re-check isolation, then hand each test an empty, freshly seeded DB."""
    assert_isolated(app_db.engine)

    with app_db.engine.begin() as connection:
        for table in reversed(app_db.Base.metadata.sorted_tables):
            connection.execute(table.delete())

    # `move_to_bought` resolves the first pipeline stage, so the templates have
    # to exist again after the wipe.
    with app_db.SessionLocal() as session:
        ensure_pipeline_defaults(session)
        ensure_activity_category_defaults(session)

    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def brrrr_payload() -> dict:
    """A complete BRRRR deal, using the exact field names `DealInputsForm` emits."""
    return {
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


@pytest.fixture
def flip_payload(brrrr_payload: dict) -> dict:
    """The same deal underwritten as a flip."""
    return {
        **brrrr_payload,
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
