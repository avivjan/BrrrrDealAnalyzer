"""Meta-tests for the harness itself.

If these fail, none of the other results can be trusted: they assert that the
suite really is talking to a throwaway SQLite file and that the safeguard in
`conftest.py` actually fires instead of quietly passing.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine

import conftest as harness
import db as app_db


class TestIsolation:
    def test_engine_is_the_throwaway_sqlite_file(self):
        assert app_db.engine.url.get_backend_name() == "sqlite"
        assert app_db.engine.url.database == str(harness.TEST_DB_PATH)
        assert str(harness.TEST_DB_PATH).startswith(os.path.realpath(os.sep))

    def test_database_url_env_points_at_the_test_database(self):
        assert os.environ["DATABASE_URL"] == harness.TEST_DATABASE_URL
        assert os.environ["DATABASE_URL"].startswith("sqlite:///")

    def test_no_production_driver_anywhere_in_the_engine_url(self):
        rendered = str(app_db.engine.url).lower()
        for marker in harness._FORBIDDEN_URL_MARKERS:
            assert marker not in rendered

    def test_sessionlocal_is_bound_to_the_test_engine(self):
        with app_db.SessionLocal() as session:
            assert session.get_bind() is app_db.engine

    def test_get_db_is_overridden_inside_the_harness(self):
        assert app_db.get_db in harness.app.dependency_overrides

    def test_dotenv_loader_is_neutralised(self):
        """BackEnd/.env holds live GCS/email credentials; tests must not load it."""
        import dotenv

        assert dotenv.load_dotenv() is False

    def test_tables_really_exist_in_the_temp_database(self):
        from sqlalchemy import inspect

        tables = set(inspect(app_db.engine).get_table_names())
        assert {"active_deals", "flip_deals", "bought_brrrr_deals", "bought_flip_deals"} <= tables


class TestSafeguardFires:
    """The guard must abort, not warn, when handed anything but the test DB."""

    def test_rejects_a_postgres_engine(self):
        postgres = create_engine(
            "postgresql+psycopg2://user:pw@prod-db.render.com:5432/appdb"
        )
        with pytest.raises(RuntimeError, match="TEST DATABASE SAFETY ABORT"):
            harness.assert_isolated(postgres)

    def test_rejects_a_different_sqlite_file(self, tmp_path):
        other = create_engine(f"sqlite:///{tmp_path / 'somewhere-else.db'}")
        with pytest.raises(RuntimeError, match="not the temp test database"):
            harness.assert_isolated(other)

    def test_rejects_a_mutated_database_url_env(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")
        with pytest.raises(RuntimeError, match="mutated after the harness set it"):
            harness.assert_isolated(app_db.engine)


class TestNoWritesEscape:
    def test_written_rows_land_in_the_temp_file_only(self, client, brrrr_payload):
        import sqlite3

        response = client.post("/active-deals", json=brrrr_payload)
        assert response.status_code == 200

        # Read the temp file directly, bypassing SQLAlchemy entirely.
        connection = sqlite3.connect(harness.TEST_DB_PATH)
        try:
            count = connection.execute("SELECT COUNT(*) FROM active_deals").fetchone()[0]
        finally:
            connection.close()
        assert count == 1
