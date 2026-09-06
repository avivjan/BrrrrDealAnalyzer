"""The one place that decides which database a test harness may touch.

Shared by ``tests/conftest.py`` (pytest) and ``verify_regression.py`` (the
golden-snapshot harness, which ``frontend/e2e/backend/serve_throwaway.py``
imports for its side effects). Pure module: importing it touches nothing.

A harness calls, in this order, before any application import:

1. ``resolve_test_database_url()`` — the URL to use. Only ``TEST_DATABASE_URL``
   is consulted; ``DATABASE_URL`` (the production variable) never is.
2. ``os.environ["DATABASE_URL"] = <that url>`` — so ``db.py`` builds its engine
   on it.
3. ``assert_isolated(engine, expected_url)`` — once the engine exists, and again
   as often as it likes: the engine must be PostgreSQL, on a loopback host, with
   a database whose name ends in ``_test``, free of any hosted-provider marker,
   and ``current_database()`` must match. Anything else aborts the process.
4. ``reset_schema(engine)`` — only after the check passed: drop and recreate the
   ``public`` schema so the models define what exists.
"""

from __future__ import annotations

import os
import sys
from typing import NoReturn

from sqlalchemy import text

DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg2://brrrr_test:brrrr_test@127.0.0.1:55432/brrrr_test"

# Hosts a test database may live on. Production databases are remote.
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

# Substrings that must never appear in the engine URL during a test run.
FORBIDDEN_URL_MARKERS = (
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
TEST_DB_SUFFIX = "_test"

START_HINT = "docker compose -f BackEnd/docker-compose.test.yml up -d --wait"


def resolve_test_database_url() -> str:
    """The database a harness may use: `$TEST_DATABASE_URL`, else the compose container."""
    return os.environ.get("TEST_DATABASE_URL") or DEFAULT_TEST_DATABASE_URL


def abort(reason: str, expected_url: str, inherited_url: str | None) -> NoReturn:
    """Kill the run loudly. Never degrade to 'best effort' on a safety check."""
    banner = (
        "\n"
        "================= TEST DATABASE SAFETY ABORT =================\n"
        f"{reason}\n"
        f"  expected : {expected_url}\n"
        f"  in env   : {os.environ.get('DATABASE_URL')!r}\n"
        f"  inherited: {'<set>' if inherited_url else '<unset>'}\n"
        "Tests must never touch a real database. Aborting the run.\n"
        "==============================================================\n"
    )
    sys.stderr.write(banner)
    sys.stderr.flush()
    raise RuntimeError(banner)


def assert_isolated(engine, expected_url: str, inherited_url: str | None = None) -> None:
    """Verify `engine` is the throwaway test PostgreSQL and nothing else."""
    url = engine.url

    def _abort(reason: str) -> NoReturn:
        abort(reason, expected_url, inherited_url)

    if url.get_backend_name() != "postgresql":
        _abort(f"Engine backend is {url.get_backend_name()!r}, expected 'postgresql'.")

    if (url.host or "") not in LOOPBACK_HOSTS:
        _abort(f"Engine host is {url.host!r}, not a loopback address.")

    if not (url.database or "").endswith(TEST_DB_SUFFIX):
        _abort(f"Engine database is {url.database!r}; a test database name must end with {TEST_DB_SUFFIX!r}.")

    rendered = str(url).lower()
    for marker in FORBIDDEN_URL_MARKERS:
        if marker in rendered:
            _abort(f"Engine URL contains forbidden marker {marker!r}.")

    if os.environ.get("DATABASE_URL") != expected_url:
        _abort("DATABASE_URL was mutated after the harness set it.")

    try:
        with engine.connect() as connection:
            actual = connection.exec_driver_sql("SELECT current_database()").scalar()
    except Exception as exc:
        _abort(f"Could not connect to the isolated test database: {exc!r}\n  Is it running?  {START_HINT}")
    if actual != url.database:
        _abort(f"Connected to database {actual!r}, expected {url.database!r}.")


def reset_schema(engine) -> None:
    """Drop everything in the test database so the models define the schema.

    Only ever call this after `assert_isolated` has passed for the same engine.
    """
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
