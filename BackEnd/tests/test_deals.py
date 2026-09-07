"""The compact cross-board deal endpoints (/deals): list, word search, portfolio
summary and single-deal detail. These back the MCP tools a chat uses first."""

from __future__ import annotations

import uuid

import pytest


def _create(client, payload) -> dict:
    response = client.post("/active-deals", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def seeded(client, brrrr_payload, flip_payload):
    """Two active deals (one per type), one moved to Bought, one dead deal with notes."""
    brrr = _create(client, {**brrrr_payload, "address": "12 Ocean Ave, Jacksonville", "stage": 3,
                            "notes": "duplex near the beach", "contact": "Ann Agent"})
    flip = _create(client, {**flip_payload, "address": "7 Harbor St, St Augustine", "stage": 2,
                            "task": "waiting on contractor bid"})
    dead = _create(client, {**brrrr_payload, "address": "99 Nowhere Rd", "stage": 5, "niche": "student rental"})
    bought = client.post(f"/bought-deals/from-active/{brrr['id']}", params={"deal_type": "BRRRR"}).json()
    return {"brrr": brrr, "flip": flip, "dead": dead, "bought": bought}


class TestList:
    def test_lists_both_boards_compact(self, client, seeded):
        rows = client.get("/deals").json()
        assert {r["board"] for r in rows} == {"active", "bought"}
        assert len(rows) == 4
        assert all("breakdowns" not in r and "sold_comps" not in r for r in rows)
        row = next(r for r in rows if r["id"] == seeded["brrr"]["id"])
        assert row["deal_type"] == "BRRRR" and row["stage"] == 3 and row["section"] == 2
        assert row["purchase_price_k"] == 200 and row["arv_or_sale_price_k"] == 320
        assert row["cash_flow_monthly"] == pytest.approx(float(seeded["brrr"]["cash_flow"]))

    def test_filters(self, client, seeded):
        assert {r["board"] for r in client.get("/deals", params={"board": "bought"}).json()} == {"bought"}
        assert [r["id"] for r in client.get("/deals", params={"deal_type": "FLIP"}).json()] == [seeded["flip"]["id"]]
        assert [r["id"] for r in client.get("/deals", params={"stage": 5}).json()] == [seeded["dead"]["id"]]
        assert [r["id"] for r in client.get("/deals", params={"stage": "purchase"}).json()] == [seeded["bought"]["id"]]
        assert len(client.get("/deals", params={"limit": 2}).json()) == 2

    def test_word_search_is_case_insensitive_and_needs_every_word(self, client, seeded):
        ids = lambda **p: {r["id"] for r in client.get("/deals", params=p).json()}  # noqa: E731
        assert ids(q="jacksonville") == {seeded["brrr"]["id"], seeded["bought"]["id"]}
        assert ids(q="DUPLEX beach") == {seeded["brrr"]["id"], seeded["bought"]["id"]}
        assert ids(q="contractor") == {seeded["flip"]["id"]}       # task
        assert ids(q="student") == {seeded["dead"]["id"]}          # niche
        assert ids(q="ann agent") == {seeded["brrr"]["id"], seeded["bought"]["id"]}   # contact
        assert ids(q="duplex contractor") == set()
        assert client.get("/deals/search", params={"q": "harbor"}).json()[0]["id"] == seeded["flip"]["id"]

    def test_bad_filters_are_400(self, client):
        assert client.get("/deals", params={"board": "sold"}).status_code == 400
        assert client.get("/deals", params={"deal_type": "CONDO"}).status_code == 400
        assert client.get("/deals/search").status_code == 422


class TestPortfolio:
    def test_counts_totals_and_top_lists(self, client, seeded):
        p = client.get("/deals/portfolio").json()
        assert (p["active_count"], p["bought_count"]) == (3, 1)
        assert p["active_by_type"] == {"BRRRR": 2, "FLIP": 1}
        assert p["active_by_stage"] == {"3": 1, "2": 1, "5": 1}
        assert p["bought_by_stage"] == {"purchase": 1}
        bought = seeded["bought"]
        assert p["bought_total_equity"] == pytest.approx(float(bought["equity"]), abs=0.01)
        assert p["bought_total_cash_flow_monthly"] == pytest.approx(float(bought["cash_flow"]), abs=0.01)
        assert p["top_bought_by_equity"][0]["id"] == bought["id"]
        assert p["top_bought_by_equity"][0]["value"] == pytest.approx(float(bought["equity"]))
        assert len(p["top_active_by_cash_on_cash"]) <= 3

    def test_empty_portfolio(self, client):
        p = client.get("/deals/portfolio").json()
        assert p["active_count"] == 0 and p["bought_count"] == 0
        assert p["top_bought_by_equity"] == [] and p["bought_total_equity"] == 0


class TestDetail:
    def test_finds_deals_on_either_board(self, client, seeded):
        active = client.get(f"/deals/{seeded['flip']['id']}").json()
        assert active["board"] == "active" and active["deal"]["deal_type"] == "FLIP"
        assert "breakdowns" in active["deal"]
        bought = client.get(f"/deals/{seeded['bought']['id']}").json()
        assert bought["board"] == "bought" and bought["deal"]["boughtStage"] == "purchase"

    def test_unknown_or_malformed_id_is_404(self, client):
        assert client.get(f"/deals/{uuid.uuid4()}").status_code == 404
        assert client.get("/deals/not-a-uuid").status_code == 404
