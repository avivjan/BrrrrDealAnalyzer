"""The BRRRR lifecycle migration: existing rows load, backfilled, after the columns are added.

Simulates a pre-migration database by dropping the lifecycle columns from the two BRRRR
tables (the harness is PostgreSQL, the only dialect the runtime migrations run on), then
runs `run_migrations` twice: the first pass must add and backfill every column, the second
must be a no-op, and the migrated rows must still serve through the API.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import text

import db as app_db
from migrations.runner import run_migrations
from migrations.steps.brrr_lifecycle_columns import BRRR_LIFECYCLE_COLUMNS, BRRR_TABLES

NEW_COLUMNS = [name for name, _ddl, _backfill in BRRR_LIFECYCLE_COLUMNS]
ALL_DEAL_TABLES = ("active_deals", "flip_deals", "bought_brrrr_deals", "bought_flip_deals")


def _drop_lifecycle_columns() -> None:
    with app_db.engine.begin() as conn:
        for table in BRRR_TABLES:
            for column in NEW_COLUMNS:
                conn.execute(text(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {column}"))


def _column_names_of(table: str) -> set[str]:
    with app_db.engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = :t"
        ), {"t": table})
        return {r[0] for r in rows}


def _column_default_of(table: str, column: str) -> str | None:
    with app_db.engine.connect() as conn:
        return conn.execute(text(
            "SELECT column_default FROM information_schema.columns WHERE table_name = :t AND column_name = :c"
        ), {"t": table, "c": column}).scalar()


def _row_by_address(table: str, address: str) -> dict:
    with app_db.engine.connect() as conn:
        result = conn.execute(text(f"SELECT * FROM {table} WHERE address = :a"), {"a": address})
        return dict(result.mappings().one())


@pytest.fixture
def legacy_rows(client, brrrr_payload):
    """Two active BRRRR deals (hard-money rehab and cash rehab) and one bought copy, saved
    with today's schema and then stripped of the lifecycle columns."""
    hard_money_rehab_deal = client.post("/active-deals", json={**brrrr_payload, "address": "HM Rehab", "use_HM_for_rehab": True}).json()
    client.post("/active-deals", json={**brrrr_payload, "address": "Cash Rehab", "use_HM_for_rehab": False,
                                          "constructionLoanBudget": 0}).json()
    move_to_bought_response = client.post(f"/bought-deals/from-active/{hard_money_rehab_deal['id']}", params={"deal_type": "BRRRR"})
    assert move_to_bought_response.status_code == 200, move_to_bought_response.text
    _drop_lifecycle_columns()
    for table in BRRR_TABLES:
        assert not (_column_names_of(table) & set(NEW_COLUMNS))
    yield


class TestBrrrLifecycleMigration:
    def test_adds_every_column_to_both_tables_and_is_idempotent(self, legacy_rows):
        run_migrations(app_db.engine)
        for table in BRRR_TABLES:
            assert set(NEW_COLUMNS) <= _column_names_of(table), table
        run_migrations(app_db.engine)  # second boot: nothing left to do, nothing to crash on
        for table in BRRR_TABLES:
            assert set(NEW_COLUMNS) <= _column_names_of(table), table

    def test_backfills_the_new_defaults(self, legacy_rows):
        run_migrations(app_db.engine)
        for table in BRRR_TABLES:
            migrated_row = _row_by_address(table, "HM Rehab")
            assert migrated_row["earnest_money_deposit"] == Decimal("5000")
            assert migrated_row["loan_charges_buy"] == Decimal("900")
            assert migrated_row["title_mode_buy"] == "standard"
            assert migrated_row["online_notary_buy"] is True and migrated_row["online_notary_refi"] is True
            assert migrated_row["rehab_cushion"] == Decimal("5000")
            assert migrated_row["days_until_rented"] == 90
            assert migrated_row["monthly_utilities_until_rented"] == Decimal("80")
            assert migrated_row["maintenance_before_refi"] == Decimal("500")
            assert migrated_row["appliances"] == Decimal("630")
            assert migrated_row["loan_charges_refi"] == Decimal("200")
            assert migrated_row["appraisal_fee"] == Decimal("700")
            assert migrated_row["survey_fee"] == Decimal("385")
            assert migrated_row["refi_underwriting_fee"] == Decimal("2000")
            assert migrated_row["broker_processing_fee_refi"] == Decimal("0")  # $0 unless a broker charges one
            assert migrated_row["maintenance_reserve"] == Decimal("1500")
            assert migrated_row["capex_reserve"] == Decimal("2500")
            assert migrated_row["other_closing_costs_buy"] == 0 and migrated_row["other_closing_costs_refi"] == 0

    def test_formula_defaults_stay_null_and_the_date_stays_unknown(self, legacy_rows):
        run_migrations(app_db.engine)
        migrated_row = _row_by_address("active_deals", "HM Rehab")
        for column in ("buy_closing_date", "recording_transfer_buy", "title_escrow_buy", "seller_paid_current_year_taxes",
                       "recording_transfer_refi", "title_escrow_refi", "vacancy_reserve", "lowest_arv_in_thousands",
                       "online_notary_fee_buy", "online_notary_fee_refi", "other_closing_costs_buy_note", "other_closing_costs_refi_note"):
            assert migrated_row[column] is None, column

    def test_construction_budget_mirrors_the_legacy_hard_money_flag(self, legacy_rows, brrrr_payload):
        run_migrations(app_db.engine)
        financed_rehab_in_thousands = Decimal(brrrr_payload["rehabCost"]) * (1 + Decimal(brrrr_payload["rehabContingency"]) / 100)
        assert _row_by_address("active_deals", "HM Rehab")["construction_loan_budget_in_thousands"] == financed_rehab_in_thousands
        assert _row_by_address("bought_brrrr_deals", "HM Rehab")["construction_loan_budget_in_thousands"] == financed_rehab_in_thousands
        assert _row_by_address("active_deals", "Cash Rehab")["construction_loan_budget_in_thousands"] == 0

    def test_migrated_rows_serve_through_the_api(self, legacy_rows, client):
        run_migrations(app_db.engine)
        active = client.get("/active-deals")
        assert active.status_code == 200, active.text
        by_address = {d["address"]: d for d in active.json()}
        hard_money_rehab_deal = by_address["HM Rehab"]
        assert float(hard_money_rehab_deal["constructionLoanBudget"]) == pytest.approx(55.0)
        assert float(hard_money_rehab_deal["earnestMoneyDeposit"]) == pytest.approx(5000.0)
        assert hard_money_rehab_deal["buyClosingDate"] is None and hard_money_rehab_deal["prepaid_interest_buy"] == 0
        assert hard_money_rehab_deal["total_cash_needed_for_deal"] is not None
        bought = client.get("/bought-deals")
        assert bought.status_code == 200, bought.text
        assert any(d["address"] == "HM Rehab" for d in bought.json())


class TestBrokerProcessingFeeDefault:
    def test_ddl_default_moves_to_zero_and_stored_values_are_kept(self, legacy_rows):
        """A database that shipped with the $395 default gets the new $0 default on boot;
        the rows that already carry a fee are left alone."""
        with app_db.engine.begin() as conn:
            for table in BRRR_TABLES:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN broker_processing_fee_refi NUMERIC(12,2) DEFAULT 395"))
                conn.execute(text(f"UPDATE {table} SET broker_processing_fee_refi = 395"))
        run_migrations(app_db.engine)
        run_migrations(app_db.engine)  # idempotent: SET DEFAULT twice is fine
        for table in BRRR_TABLES:
            assert (_column_default_of(table, "broker_processing_fee_refi") or "").startswith("0"), table
            assert _row_by_address(table, "HM Rehab")["broker_processing_fee_refi"] == Decimal("395")


class TestGoogleDriveLinkMigration:
    @pytest.fixture
    def tables_without_the_drive_link(self, client, brrrr_payload, flip_payload):
        client.post("/active-deals", json={**brrrr_payload, "address": "Drive BRRRR"})
        client.post("/active-deals", json={**flip_payload, "address": "Drive FLIP"})
        with app_db.engine.begin() as conn:
            for table in ALL_DEAL_TABLES:
                conn.execute(text(f"ALTER TABLE {table} DROP COLUMN IF EXISTS google_drive_link"))
        for table in ALL_DEAL_TABLES:
            assert "google_drive_link" not in _column_names_of(table)
        yield

    def test_adds_a_nullable_column_to_every_deal_table_and_is_idempotent(self, tables_without_the_drive_link):
        run_migrations(app_db.engine)
        run_migrations(app_db.engine)
        for table in ALL_DEAL_TABLES:
            assert "google_drive_link" in _column_names_of(table), table
        assert _row_by_address("active_deals", "Drive BRRRR")["google_drive_link"] is None
        assert _row_by_address("flip_deals", "Drive FLIP")["google_drive_link"] is None
