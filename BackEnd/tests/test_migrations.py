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


def _drop_lifecycle_columns() -> None:
    with app_db.engine.begin() as conn:
        for table in BRRR_TABLES:
            for column in NEW_COLUMNS:
                conn.execute(text(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {column}"))


def _columns(table: str) -> set[str]:
    with app_db.engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = :t"
        ), {"t": table})
        return {r[0] for r in rows}


def _row(table: str, address: str) -> dict:
    with app_db.engine.connect() as conn:
        result = conn.execute(text(f"SELECT * FROM {table} WHERE address = :a"), {"a": address})
        return dict(result.mappings().one())


@pytest.fixture
def legacy_rows(client, brrrr_payload):
    """Two active BRRRR deals (hard-money rehab and cash rehab) and one bought copy, saved
    with today's schema and then stripped of the lifecycle columns."""
    hm = client.post("/active-deals", json={**brrrr_payload, "address": "HM Rehab", "use_HM_for_rehab": True}).json()
    client.post("/active-deals", json={**brrrr_payload, "address": "Cash Rehab", "use_HM_for_rehab": False,
                                          "constructionLoanBudget": 0}).json()
    moved = client.post(f"/bought-deals/from-active/{hm['id']}", params={"deal_type": "BRRRR"})
    assert moved.status_code == 200, moved.text
    _drop_lifecycle_columns()
    for table in BRRR_TABLES:
        assert not (_columns(table) & set(NEW_COLUMNS))
    yield


class TestBrrrLifecycleMigration:
    def test_adds_every_column_to_both_tables_and_is_idempotent(self, legacy_rows):
        run_migrations(app_db.engine)
        for table in BRRR_TABLES:
            assert set(NEW_COLUMNS) <= _columns(table), table
        run_migrations(app_db.engine)  # second boot: nothing left to do, nothing to crash on
        for table in BRRR_TABLES:
            assert set(NEW_COLUMNS) <= _columns(table), table

    def test_backfills_the_new_defaults(self, legacy_rows):
        run_migrations(app_db.engine)
        for table in BRRR_TABLES:
            row = _row(table, "HM Rehab")
            assert row["earnest_money_deposit"] == Decimal("5000")
            assert row["loan_charges_buy"] == Decimal("900")
            assert row["title_mode_buy"] == "standard"
            assert row["online_notary_buy"] is True and row["online_notary_refi"] is True
            assert row["rehab_cushion"] == Decimal("5000")
            assert row["days_until_rented"] == 90
            assert row["monthly_utilities_until_rented"] == Decimal("80")
            assert row["maintenance_before_refi"] == Decimal("500")
            assert row["appliances"] == Decimal("630")
            assert row["loan_charges_refi"] == Decimal("200")
            assert row["appraisal_fee"] == Decimal("700")
            assert row["survey_fee"] == Decimal("385")
            assert row["refi_underwriting_fee"] == Decimal("2000")
            assert row["broker_processing_fee_refi"] == Decimal("395")
            assert row["maintenance_reserve"] == Decimal("1500")
            assert row["capex_reserve"] == Decimal("2500")
            assert row["other_closing_costs_buy"] == 0 and row["other_closing_costs_refi"] == 0

    def test_formula_defaults_stay_null_and_the_date_stays_unknown(self, legacy_rows):
        run_migrations(app_db.engine)
        row = _row("active_deals", "HM Rehab")
        for column in ("buy_closing_date", "recording_transfer_buy", "title_escrow_buy", "seller_paid_current_year_taxes",
                       "recording_transfer_refi", "title_escrow_refi", "vacancy_reserve", "lowest_arv_in_thousands"):
            assert row[column] is None, column

    def test_construction_budget_mirrors_the_legacy_hard_money_flag(self, legacy_rows, brrrr_payload):
        run_migrations(app_db.engine)
        financed = Decimal(brrrr_payload["rehabCost"]) * (1 + Decimal(brrrr_payload["rehabContingency"]) / 100)
        assert _row("active_deals", "HM Rehab")["construction_loan_budget_in_thousands"] == financed
        assert _row("bought_brrrr_deals", "HM Rehab")["construction_loan_budget_in_thousands"] == financed
        assert _row("active_deals", "Cash Rehab")["construction_loan_budget_in_thousands"] == 0

    def test_migrated_rows_serve_through_the_api(self, legacy_rows, client):
        run_migrations(app_db.engine)
        active = client.get("/active-deals")
        assert active.status_code == 200, active.text
        by_address = {d["address"]: d for d in active.json()}
        hm = by_address["HM Rehab"]
        assert float(hm["constructionLoanBudget"]) == pytest.approx(55.0)
        assert float(hm["earnestMoneyDeposit"]) == pytest.approx(5000.0)
        assert hm["buyClosingDate"] is None and hm["prepaid_interest_buy"] == 0
        assert hm["total_cash_needed_for_deal"] is not None
        bought = client.get("/bought-deals")
        assert bought.status_code == 200, bought.text
        assert any(d["address"] == "HM Rehab" for d in bought.json())
