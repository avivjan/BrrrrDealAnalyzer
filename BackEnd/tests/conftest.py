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
from typing import NoReturn

import pytest
from sqlalchemy import text

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
# ---------------------------------------------------------------------------
INHERITED_DATABASE_URL = os.environ.get("DATABASE_URL")

DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg2://brrrr_test:brrrr_test@127.0.0.1:55432/brrrr_test"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or DEFAULT_TEST_DATABASE_URL

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
# 4. The safety guard.
# ---------------------------------------------------------------------------
# Hosts a test database may live on. Production databases are remote.
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

# Substrings that must never appear in the engine URL during a test run.
_FORBIDDEN_URL_MARKERS = (
    "render.com",
    "amazonaws.com",
    "neon.tech",
    "supabase",
    "railway",
    "azure.com",
    "googleapis.com",
    "digitalocean",
)

# The database name must end with this so a test URL can never be mistaken
# for a real one, even on a loopback host.
_TEST_DB_SUFFIX = "_test"


def _abort(reason: str) -> NoReturn:
    """Kill the run loudly. Never degrade to 'best effort' on a safety check."""
    banner = (
        "\n"
        "================= TEST DATABASE SAFETY ABORT =================\n"
        f"{reason}\n"
        f"  expected : {TEST_DATABASE_URL}\n"
        f"  in env   : {os.environ.get('DATABASE_URL')!r}\n"
        f"  inherited: {'<set>' if INHERITED_DATABASE_URL else '<unset>'}\n"
        "Tests must never touch a real database. Aborting the run.\n"
        "==============================================================\n"
    )
    sys.stderr.write(banner)
    sys.stderr.flush()
    raise RuntimeError(banner)


def assert_isolated(engine) -> None:
    """Verify `engine` is the throwaway test PostgreSQL and nothing else.

    Called at import time, at session start, and before every single test.
    """
    url = engine.url

    if url.get_backend_name() != "postgresql":
        _abort(f"Engine backend is {url.get_backend_name()!r}, expected 'postgresql'.")

    if (url.host or "") not in _LOOPBACK_HOSTS:
        _abort(f"Engine host is {url.host!r}, not a loopback address.")

    if not (url.database or "").endswith(_TEST_DB_SUFFIX):
        _abort(f"Engine database is {url.database!r}; a test database name must end with {_TEST_DB_SUFFIX!r}.")

    rendered = str(url).lower()
    for marker in _FORBIDDEN_URL_MARKERS:
        if marker in rendered:
            _abort(f"Engine URL contains forbidden marker {marker!r}.")

    if os.environ.get("DATABASE_URL") != TEST_DATABASE_URL:
        _abort("DATABASE_URL was mutated after the harness set it.")

    try:
        with engine.connect() as connection:
            actual = connection.exec_driver_sql("SELECT current_database()").scalar()
    except Exception as exc:
        _abort(
            f"Could not connect to the isolated test database: {exc!r}\n"
            "  Is it running?  docker compose -f BackEnd/docker-compose.test.yml up -d --wait"
        )
    if actual != url.database:
        _abort(f"Connected to database {actual!r}, expected {url.database!r}.")


def _reset_schema(engine) -> None:
    """Drop everything in the test database so the models define the schema.

    Only ever called after `assert_isolated` has passed for the same engine.
    """
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))


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
