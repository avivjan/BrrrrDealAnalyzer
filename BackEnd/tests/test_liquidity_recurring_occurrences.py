"""Recurring occurrences can be done, overdue and moved like one-off rows (tasks/todo/DealImpactSimulator.md, E).

Occurrences are virtual (the frontend expands a rule); a state is stored per occurrence, keyed by the date the rule
gives it, once it is marked done or moved. Occurrences before the rule's `occurrences_can_be_overdue_from` (the
day it was added; existing rules: the migration date) are history.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text

import db as app_db
from migrations.runner import run_migrations

MONTHLY_RENT = {"description": "Misc", "amount_dollars": -1500, "start_date": "2026-08-01", "frequency": "monthly", "interval": 1}


def _create_rule(client, **over) -> dict:
    response = client.post("/liquidity/recurring", json={**MONTHLY_RENT, **over})
    assert response.status_code == 201, response.text
    return response.json()


def _occurrence(client, rule_id: str, scheduled_date: str, action: str, **body):
    return client.post(f"/liquidity/recurring/{rule_id}/occurrences/{scheduled_date}/{action}", json=body or None)


class TestOccurrenceStates:
    def test_a_new_rule_counts_overdue_occurrences_only_from_the_day_it_was_added(self, client):
        rule = _create_rule(client)
        today_in_the_settings_zone = datetime.now(ZoneInfo(client.get("/liquidity/settings").json()["timezone_name"])).date()
        assert rule["occurrences_can_be_overdue_from"] == today_in_the_settings_zone.isoformat()
        assert rule["occurrence_states"] == []

    def test_the_overdue_from_date_can_be_given_on_create_and_changed(self, client):
        rule = _create_rule(client, occurrences_can_be_overdue_from="2026-09-15")
        assert rule["occurrences_can_be_overdue_from"] == "2026-09-15"
        edited = client.put(f"/liquidity/recurring/{rule['id']}", json={"occurrences_can_be_overdue_from": "2026-10-15"}).json()
        assert edited["occurrences_can_be_overdue_from"] == "2026-10-15"

    def test_done_then_undo_keeps_no_state_behind(self, client):
        rule = _create_rule(client)
        done = _occurrence(client, rule["id"], "2026-10-01", "done").json()
        assert [state["scheduled_date"] for state in done["occurrence_states"]] == ["2026-10-01"]
        assert done["occurrence_states"][0]["done_at"] is not None
        # Idempotent.
        assert len(_occurrence(client, rule["id"], "2026-10-01", "done").json()["occurrence_states"]) == 1
        reopened = _occurrence(client, rule["id"], "2026-10-01", "not-done").json()
        assert reopened["occurrence_states"] == []

    def test_moving_one_occurrence_leaves_the_rest_of_the_series(self, client):
        rule = _create_rule(client)
        moved = _occurrence(client, rule["id"], "2026-11-01", "move", new_effective_date="2026-11-08").json()
        assert moved["occurrence_states"] == [{"scheduled_date": "2026-11-01", "done_at": None, "moved_to_date": "2026-11-08"}]
        back = _occurrence(client, rule["id"], "2026-11-01", "move", new_effective_date="2026-11-01").json()
        assert back["occurrence_states"] == []

    def test_an_amount_edit_keeps_the_states(self, client):
        rule = _create_rule(client)
        _occurrence(client, rule["id"], "2026-10-01", "done")
        edited = client.put(f"/liquidity/recurring/{rule['id']}", json={"amount_dollars": -1600}).json()
        assert [state["scheduled_date"] for state in edited["occurrence_states"]] == ["2026-10-01"]

    def test_an_unknown_rule_is_a_404_and_a_date_the_rule_never_produces_a_422(self, client):
        rule = _create_rule(client)
        assert _occurrence(client, "00000000-0000-0000-0000-000000000000", "2026-10-01", "done").status_code == 404
        assert _occurrence(client, "not-a-uuid", "2026-10-01", "done").status_code == 404
        assert _occurrence(client, rule["id"], "2026-10-02", "done").status_code == 422
        assert _occurrence(client, rule["id"], "2026-07-01", "done").status_code == 422

    def test_month_ends_are_clamped_like_the_timeline(self, client):
        rule = _create_rule(client, start_date="2026-01-31")
        assert _occurrence(client, rule["id"], "2026-02-28", "done").status_code == 200
        assert _occurrence(client, rule["id"], "2026-03-31", "done").status_code == 200

    def test_deleting_the_rule_deletes_its_states(self, client):
        rule = _create_rule(client)
        _occurrence(client, rule["id"], "2026-10-01", "done")
        assert client.delete(f"/liquidity/recurring/{rule['id']}").status_code == 200
        with app_db.engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM liquidity_recurring_occurrence_states")).scalar() == 0


class TestBulkWithOccurrences:
    def test_the_bulk_action_takes_one_off_rows_and_occurrences_together(self, client):
        rule = _create_rule(client)
        one_off = client.post("/liquidity/transactions", json={"effective_date": "2026-10-05", "description": "Plumber",
                                                              "amount_dollars": -300}).json()
        response = client.post("/liquidity/transactions/bulk", json={
            "transaction_ids": [one_off["id"]], "action": "postpone_by_days", "postpone_by_days": 7,
            "recurring_occurrences": [{"recurring_rule_id": rule["id"], "scheduled_date": "2026-10-01"}],
        })
        assert response.status_code == 200, response.text
        assert response.json()[0]["effective_date"] == "2026-10-12"
        states = client.get("/liquidity/recurring").json()[0]["occurrence_states"]
        assert states == [{"scheduled_date": "2026-10-01", "done_at": None, "moved_to_date": "2026-10-08"}]

    def test_the_bulk_action_takes_occurrences_alone(self, client):
        rule = _create_rule(client)
        response = client.post("/liquidity/transactions/bulk", json={
            "action": "mark_done",
            "recurring_occurrences": [{"recurring_rule_id": rule["id"], "scheduled_date": "2026-09-01"},
                                      {"recurring_rule_id": rule["id"], "scheduled_date": "2026-10-01"}],
        })
        assert response.status_code == 200, response.text
        states = client.get("/liquidity/recurring").json()[0]["occurrence_states"]
        assert [state["scheduled_date"] for state in states] == ["2026-09-01", "2026-10-01"]
        assert all(state["done_at"] for state in states)

    def test_an_empty_bulk_request_is_refused(self, client):
        assert client.post("/liquidity/transactions/bulk", json={"action": "mark_done"}).status_code == 422


class TestMigration:
    def test_an_existing_rule_gets_the_migration_date_and_the_migration_is_idempotent(self, client):
        rule = _create_rule(client)
        with app_db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE liquidity_recurring_transactions DROP COLUMN occurrences_can_be_overdue_from"))
        run_migrations(app_db.engine)
        run_migrations(app_db.engine)
        listed = next(listed for listed in client.get("/liquidity/recurring").json() if listed["id"] == rule["id"])
        with app_db.engine.connect() as conn:
            today_in_the_database = conn.execute(text("SELECT CURRENT_DATE")).scalar()
        assert listed["occurrences_can_be_overdue_from"] == today_in_the_database.isoformat()
