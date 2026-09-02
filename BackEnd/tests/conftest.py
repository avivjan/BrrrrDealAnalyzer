"""Test harness with hard database isolation.

Everything up to the ``# --- fixtures ---`` marker executes at *import* time,
before pytest collects a single test. That ordering is not stylistic — it is
required:

* ``db.py`` reads ``$DATABASE_URL`` and builds its ``Engine`` at import time.
* ``main.py`` runs ``Base.metadata.create_all``, ``_run_migrations()`` and the
  pipeline/REPS seeding at import time.

So by the time ``import main`` returns, a real database would already have been
connected to, migrated and written to. The only safe place to redirect it is
here, before the first application import.

Two environments make that redirect non-negotiable:

* **Render pre-deploy commands** run with the production ``DATABASE_URL``
  injected into the environment.
* **Local machines** have a ``DATABASE_URL`` exported in the shell.

Both are overwritten unconditionally below, and then verified. If verification
ever fails the run aborts instead of falling back.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import uuid as uuid_module
from typing import NoReturn

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
# ---------------------------------------------------------------------------
INHERITED_DATABASE_URL = os.environ.get("DATABASE_URL")

_TEST_DB_DIR = tempfile.mkdtemp(prefix="brrrr-test-db-")
TEST_DB_PATH = pathlib.Path(_TEST_DB_DIR) / "test.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

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
# 4. SQLite compatibility shim for `Uuid(as_uuid=True)` primary keys.
#
#    Production runs Postgres, where psycopg2 adapts a plain string id in a
#    WHERE clause. SQLite's Uuid bind processor calls `value.hex` and blows up
#    on a str. Every `/active-deals/{id}` and `/bought-deals/{id}` route passes
#    the id through as a string, so without this the CRUD tests would fail for
#    a reason that does not exist in production.
# ---------------------------------------------------------------------------
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
# 5. The safety guard.
# ---------------------------------------------------------------------------
# Substrings that must never appear in the engine URL during a test run.
_FORBIDDEN_URL_MARKERS = (
    "postgres",
    "postgresql",
    "psycopg",
    "mysql",
    "mariadb",
    "mssql",
    "oracle",
    "cockroach",
    "render.com",
    "amazonaws.com",
)


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
    """Verify `engine` is the throwaway SQLite file and nothing else.

    Called at import time, at session start, and before every single test.
    """
    url = engine.url

    if url.get_backend_name() != "sqlite":
        _abort(f"Engine backend is {url.get_backend_name()!r}, expected 'sqlite'.")

    if url.database != str(TEST_DB_PATH):
        _abort(f"Engine points at {url.database!r}, not the temp test database.")

    rendered = str(url).lower()
    for marker in _FORBIDDEN_URL_MARKERS:
        if marker in rendered:
            _abort(f"Engine URL contains forbidden marker {marker!r}.")

    if os.environ.get("DATABASE_URL") != TEST_DATABASE_URL:
        _abort("DATABASE_URL was mutated after the harness set it.")

    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
    except Exception as exc:  # pragma: no cover - only on a broken sandbox
        _abort(f"Could not bind to the isolated test database: {exc!r}")


# ---------------------------------------------------------------------------
# 6. Now — and only now — import the application.
# ---------------------------------------------------------------------------
import db as app_db  # noqa: E402

assert_isolated(app_db.engine)

import crud_reps  # noqa: E402
import main as app_main  # noqa: E402
from crud_pipeline_template import ensure_defaults as ensure_pipeline_defaults  # noqa: E402

# `main` ran create_all + migrations + seeding on import. Re-verify that all of
# that landed on the temp file and not somewhere else.
assert_isolated(app_db.engine)

app = app_main.app


# ---------------------------------------------------------------------------
# 7. Contain `get_db` inside the harness. `SessionLocal` is already bound to the
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
        crud_reps.ensure_activity_category_defaults(session)

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
