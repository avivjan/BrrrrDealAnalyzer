"""Meta-tests for the harness itself.

If these fail, none of the other results can be trusted: they assert that the
suite really is talking to the throwaway test PostgreSQL and that the safeguard
in `conftest.py` actually fires instead of quietly passing.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, make_url

import conftest as harness
import db as app_db


class TestIsolation:
    def test_engine_is_the_throwaway_test_postgres(self):
        url = app_db.engine.url
        assert url.get_backend_name() == "postgresql"
        assert url.host in harness._LOOPBACK_HOSTS
        assert url.database.endswith(harness._TEST_DB_SUFFIX)
        assert str(url) == str(make_url(harness.TEST_DATABASE_URL))

    def test_database_url_env_points_at_the_test_database(self):
        assert os.environ["DATABASE_URL"] == harness.TEST_DATABASE_URL
        assert os.environ["DATABASE_URL"].startswith("postgresql")

    def test_no_production_marker_anywhere_in_the_engine_url(self):
        rendered = str(app_db.engine.url).lower()
        for marker in harness._FORBIDDEN_URL_MARKERS:
            assert marker not in rendered

    def test_connected_database_is_the_one_in_the_url(self):
        with app_db.engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT current_database()").scalar() == app_db.engine.url.database

    def test_sessionlocal_is_bound_to_the_test_engine(self):
        with app_db.SessionLocal() as session:
            assert session.get_bind() is app_db.engine

    def test_get_db_is_overridden_inside_the_harness(self):
        assert app_db.get_db in harness.app.dependency_overrides

    def test_dotenv_loader_is_neutralised(self):
        """BackEnd/.env holds live GCS/email credentials; tests must not load it."""
        import dotenv

        assert dotenv.load_dotenv() is False

    def test_tables_really_exist_in_the_test_database(self):
        from sqlalchemy import inspect

        tables = set(inspect(app_db.engine).get_table_names())
        assert {"active_deals", "flip_deals", "bought_brrrr_deals", "bought_flip_deals"} <= tables


class TestSafeguardFires:
    """The guard must abort, not warn, when handed anything but the test DB."""

    def test_rejects_a_hosted_production_postgres(self):
        hosted = create_engine("postgresql+psycopg2://user:pw@prod-db.render.com:5432/appdb")
        with pytest.raises(RuntimeError, match="TEST DATABASE SAFETY ABORT"):
            harness.assert_isolated(hosted)

    def test_rejects_a_non_loopback_host_even_with_a_test_name(self):
        remote = create_engine("postgresql+psycopg2://user:pw@db.internal.example:5432/brrrr_test")
        with pytest.raises(RuntimeError, match="not a loopback address"):
            harness.assert_isolated(remote)

    def test_rejects_a_loopback_database_without_the_test_suffix(self):
        url = make_url(harness.TEST_DATABASE_URL).set(database="brrrr")
        with pytest.raises(RuntimeError, match="must end with '_test'"):
            harness.assert_isolated(create_engine(url))

    def test_rejects_a_sqlite_engine(self, tmp_path):
        other = create_engine(f"sqlite:///{tmp_path / 'somewhere-else.db'}")
        with pytest.raises(RuntimeError, match="expected 'postgresql'"):
            harness.assert_isolated(other)

    def test_rejects_a_mutated_database_url_env(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")
        with pytest.raises(RuntimeError, match="mutated after the harness set it"):
            harness.assert_isolated(app_db.engine)


class TestNoWritesEscape:
    def test_written_rows_land_in_the_test_database_only(self, client, brrrr_payload):
        import psycopg2

        response = client.post("/active-deals", json=brrrr_payload)
        assert response.status_code == 200

        # Read the test database directly, bypassing SQLAlchemy entirely.
        url = make_url(harness.TEST_DATABASE_URL)
        connection = psycopg2.connect(
            host=url.host, port=url.port, user=url.username, password=url.password, dbname=url.database
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM active_deals")
                count = cursor.fetchone()[0]
        finally:
            connection.close()
        assert count == 1
