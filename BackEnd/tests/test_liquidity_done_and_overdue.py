"""Done / overdue on the one-off liquidity transactions: a row leaves the timeline only when marked done.

The overdue projection itself (money out on today, money in not counted) is the frontend engine's
(`frontend/src/utils/liquidityEngine.ts`, tested there); the backend stores the state and the overrides.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

import db as app_db
from migrations.runner import run_migrations


def _create(client, **overrides) -> dict:
    body = {"effective_date": "2026-11-01", "description": "HML interest for October 2026", "amount_dollars": -1970.83, **overrides}
    response = client.post("/liquidity/transactions", json=body)
    assert response.status_code == 201, response.text
    return response.json()


class TestDoneAndNotDone:
    def test_a_new_row_is_open_with_its_planned_date_and_no_overrides(self, client):
        txn = _create(client)
        assert txn["done_at"] is None and txn["originally_planned_date"] == "2026-11-01"
        assert (txn["user_overrode_date"], txn["user_overrode_amount"]) == (False, False)

    def test_done_then_undo(self, client):
        txn = _create(client)
        done = client.post(f"/liquidity/transactions/{txn['id']}/done").json()
        assert done["done_at"] is not None
        assert client.get("/liquidity/transactions").json()[0]["done_at"] is not None
        reopened = client.post(f"/liquidity/transactions/{txn['id']}/not-done").json()
        assert reopened["done_at"] is None

    def test_an_unknown_row_is_a_404(self, client):
        missing = "11111111-1111-1111-1111-111111111111"
        assert client.post(f"/liquidity/transactions/{missing}/done").status_code == 404
        assert client.post(f"/liquidity/transactions/{missing}/not-done").status_code == 404


class TestOverridesAreTrackedPerField:
    def test_moving_the_date_overrides_the_date_only(self, client):
        txn = _create(client)
        moved = client.put(f"/liquidity/transactions/{txn['id']}", json={"effective_date": "2026-11-03"}).json()
        assert (moved["user_overrode_date"], moved["user_overrode_amount"]) == (True, False)
        assert moved["originally_planned_date"] == "2026-11-01"
        back_on_plan = client.put(f"/liquidity/transactions/{txn['id']}", json={"effective_date": "2026-11-01"}).json()
        assert back_on_plan["user_overrode_date"] is False

    def test_editing_the_amount_overrides_the_amount_only_and_resending_the_same_value_is_not_an_override(self, client):
        txn = _create(client)
        same = client.put(f"/liquidity/transactions/{txn['id']}", json={"effective_date": "2026-11-01", "amount_dollars": -1970.83}).json()
        assert (same["user_overrode_date"], same["user_overrode_amount"]) == (False, False)
        edited = client.put(f"/liquidity/transactions/{txn['id']}", json={"amount_dollars": -1800}).json()
        assert (edited["user_overrode_date"], edited["user_overrode_amount"]) == (False, True)


class TestBulkActions:
    def test_mark_done_postpone_and_move_together(self, client):
        first, second = _create(client), _create(client, effective_date="2026-11-15", description="Tax bucket deposit")
        ids = [first["id"], second["id"]]
        postponed = client.post("/liquidity/transactions/bulk", json={"transaction_ids": ids, "action": "postpone_by_days", "postpone_by_days": 7}).json()
        assert [row["effective_date"] for row in postponed] == ["2026-11-08", "2026-11-22"]
        assert all(row["user_overrode_date"] for row in postponed)
        moved = client.post("/liquidity/transactions/bulk", json={"transaction_ids": ids, "action": "move_to_date", "new_effective_date": "2026-12-01"}).json()
        assert {row["effective_date"] for row in moved} == {"2026-12-01"}
        done = client.post("/liquidity/transactions/bulk", json={"transaction_ids": ids, "action": "mark_done"}).json()
        assert all(row["done_at"] for row in done)
        reopened = client.post("/liquidity/transactions/bulk", json={"transaction_ids": ids, "action": "mark_not_done"}).json()
        assert not any(row["done_at"] for row in reopened)

    def test_all_or_nothing_on_an_unknown_id(self, client):
        txn = _create(client)
        response = client.post("/liquidity/transactions/bulk", json={
            "transaction_ids": [txn["id"], "11111111-1111-1111-1111-111111111111"], "action": "mark_done"})
        assert response.status_code == 404
        assert client.get("/liquidity/transactions").json()[0]["done_at"] is None
        assert client.post("/liquidity/transactions/bulk", json={"transaction_ids": ["not-a-uuid"], "action": "mark_done"}).status_code == 404

    @pytest.mark.parametrize("body", [
        {"action": "mark_done", "transaction_ids": []},
        {"action": "move_to_date", "transaction_ids": ["x"]},
        {"action": "postpone_by_days", "transaction_ids": ["x"]},
        {"action": "postpone_by_days", "transaction_ids": ["x"], "postpone_by_days": 0},
        {"action": "explode", "transaction_ids": ["x"]},
    ])
    def test_a_malformed_request_is_a_422(self, client, body):
        assert client.post("/liquidity/transactions/bulk", json=body).status_code == 422


class TestTheMigrationMarksThePastDone:
    def test_rows_dated_before_today_start_done_and_the_rest_open(self, client):
        past = _create(client, effective_date=(date.today() - timedelta(days=3)).isoformat())
        future = _create(client, effective_date=(date.today() + timedelta(days=3)).isoformat())
        with app_db.engine.begin() as conn:
            for column in ("done_at", "originally_planned_date", "user_overrode_date", "user_overrode_amount"):
                conn.execute(text(f"ALTER TABLE liquidity_transactions DROP COLUMN {column}"))
        run_migrations(app_db.engine)
        run_migrations(app_db.engine)
        by_id = {row["id"]: row for row in client.get("/liquidity/transactions").json()}
        assert by_id[past["id"]]["done_at"] is not None and by_id[future["id"]]["done_at"] is None
        assert by_id[future["id"]]["originally_planned_date"] == future["effective_date"]
        assert by_id[past["id"]]["user_overrode_date"] is False
