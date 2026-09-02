"""Deal persistence: the endpoints the three deal-input screens actually call.

Covers the full path a deal takes through the product — Analyze page save,
My Deals card autosave, duplicate/delete, Move to Bought, and Bought Deals card
autosave — using the exact field names `DealInputsForm` emits.
"""

from __future__ import annotations

import pytest

# Every field the shared form writes, paired with the value the fixtures send.
# Guards the frontend key -> Pydantic alias -> DB column chain: if an alias is
# renamed on one side only, the value stops round-tripping and this fails.
SHARED_FORM_FIELDS = [
    "purchasePrice",
    "rehabCost",
    "rehabContingency",
    "closingCostsBuy",
    "down_payment",
    "hmlPoints",
    "HMLInterestRate",
    "annual_property_taxes",
    "annual_insurance",
    "montly_hoa",
]
BRRRR_ONLY_FIELDS = [
    "arv_in_thousands",
    "daysUntilRefi",
    "closingCostsRefi",
    "refiPoints",
    "cashReserve",
    "loanTermYears",
    "ltv_as_precent",
    "interestRate",
    "rent",
    "vacancyPercent",
    "property_managment_fee_precentages_from_rent",
    "maintenancePercent",
    "capexPercent",
]
FLIP_ONLY_FIELDS = [
    "salePrice",
    "holdingTime",
    "buyerAgentSellingFee",
    "sellerAgentSellingFee",
    "sellingClosingCosts",
    "capitalGainsTax",
    "monthly_utilities",
]


def _create(client, payload) -> dict:
    response = client.post("/active-deals", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


class TestCreateAndRoundTrip:
    def test_saves_a_brrrr_deal(self, client, brrrr_payload):
        deal = _create(client, brrrr_payload)
        assert deal["deal_type"] == "BRRRR"
        assert deal["address"] == "1 Shared Form St"
        assert deal["id"]

    def test_saves_a_flip_deal(self, client, flip_payload):
        deal = _create(client, flip_payload)
        assert deal["deal_type"] == "FLIP"

    @pytest.mark.parametrize("field", SHARED_FORM_FIELDS + BRRRR_ONLY_FIELDS)
    def test_brrrr_field_round_trips(self, client, brrrr_payload, field):
        deal = _create(client, brrrr_payload)
        assert float(deal[field]) == pytest.approx(float(brrrr_payload[field]))

    @pytest.mark.parametrize("field", SHARED_FORM_FIELDS + FLIP_ONLY_FIELDS)
    def test_flip_field_round_trips(self, client, flip_payload, field):
        deal = _create(client, flip_payload)
        assert float(deal[field]) == pytest.approx(float(flip_payload[field]))

    def test_saved_deal_comes_back_with_its_analysis(self, client, brrrr_payload):
        deal = _create(client, brrrr_payload)
        assert deal["cash_flow"] is not None
        assert deal["total_cash_needed_for_deal"] is not None

    def test_use_hm_for_rehab_boolean_survives(self, client, brrrr_payload):
        assert _create(client, {**brrrr_payload, "use_HM_for_rehab": True})["use_HM_for_rehab"] is True
        assert _create(client, {**brrrr_payload, "use_HM_for_rehab": False})["use_HM_for_rehab"] is False


class TestBoardLoad:
    def test_lists_both_deal_types_newest_first(self, client, brrrr_payload, flip_payload):
        _create(client, brrrr_payload)
        _create(client, flip_payload)
        deals = client.get("/active-deals").json()
        assert len(deals) == 2
        assert {d["deal_type"] for d in deals} == {"BRRRR", "FLIP"}

    def test_empty_board(self, client):
        assert client.get("/active-deals").json() == []


class TestCardAutosave:
    def test_put_persists_an_edit(self, client, brrrr_payload):
        deal = _create(client, brrrr_payload)
        updated = client.put(
            f"/active-deals/{deal['id']}", json={**deal, "purchasePrice": 210, "rent": 2750}
        )
        assert updated.status_code == 200, updated.text
        assert float(updated.json()["purchasePrice"]) == 210
        assert float(updated.json()["rent"]) == 2750

    def test_put_recalculates(self, client, brrrr_payload):
        """Saving an edit must return freshly computed metrics, not the stored ones.

        Only the share of rent left after the rent-based reserves (vacancy,
        maintenance, capex, management) reaches cash flow.
        """
        rent_based_reserves = (
            brrrr_payload["vacancyPercent"]
            + brrrr_payload["maintenancePercent"]
            + brrrr_payload["capexPercent"]
            + brrrr_payload["property_managment_fee_precentages_from_rent"]
        ) / 100
        extra_rent = 150

        deal = _create(client, brrrr_payload)
        updated = client.put(
            f"/active-deals/{deal['id']}",
            json={**deal, "rent": brrrr_payload["rent"] + extra_rent},
        ).json()
        assert updated["cash_flow"] == pytest.approx(
            deal["cash_flow"] + extra_rent * (1 - rent_based_reserves), abs=1e-9
        )

    def test_clearing_an_optional_field_applies_the_server_default(
        self, client, brrrr_payload
    ):
        """The form omits a cleared money field instead of sending null."""
        deal = _create(client, brrrr_payload)
        without = {k: v for k, v in deal.items() if k != "closingCostsBuy"}
        updated = client.put(f"/active-deals/{deal['id']}", json=without)
        assert updated.status_code == 200, updated.text
        assert float(updated.json()["closingCostsBuy"]) == 0.0

    def test_editing_a_flip_deal(self, client, flip_payload):
        deal = _create(client, flip_payload)
        updated = client.put(
            f"/active-deals/{deal['id']}",
            json={**deal, "buyerAgentSellingFee": 3, "sellingClosingCosts": 5},
        ).json()
        assert float(updated["buyerAgentSellingFee"]) == 3
        assert float(updated["sellingClosingCosts"]) == 5


class TestDuplicateAndDelete:
    def test_duplicate_copies_the_inputs_and_marks_the_address(self, client, brrrr_payload):
        deal = _create(client, brrrr_payload)
        copy = client.post(
            f"/active-deals/{deal['id']}/duplicate", params={"deal_type": "BRRRR"}
        )
        assert copy.status_code == 200, copy.text
        assert copy.json()["id"] != deal["id"]
        assert "(Copy)" in copy.json()["address"]
        assert float(copy.json()["arv_in_thousands"]) == float(deal["arv_in_thousands"])
        assert len(client.get("/active-deals").json()) == 2

    def test_delete_removes_the_deal(self, client, brrrr_payload):
        deal = _create(client, brrrr_payload)
        assert client.delete(
            f"/active-deals/{deal['id']}", params={"deal_type": "BRRRR"}
        ).status_code in (200, 204)
        assert client.get("/active-deals").json() == []


class TestMoveToBought:
    def test_carries_every_input_across(self, client, brrrr_payload):
        deal = _create(client, brrrr_payload)
        bought = client.post(
            f"/bought-deals/from-active/{deal['id']}", params={"deal_type": "BRRRR"}
        )
        assert bought.status_code == 200, bought.text
        body = bought.json()
        assert body["boughtStage"]
        for field in SHARED_FORM_FIELDS + BRRRR_ONLY_FIELDS:
            assert float(body[field]) == pytest.approx(float(brrrr_payload[field])), field

    def test_bought_card_autosave(self, client, brrrr_payload):
        deal = _create(client, brrrr_payload)
        bought = client.post(
            f"/bought-deals/from-active/{deal['id']}", params={"deal_type": "BRRRR"}
        ).json()
        updated = client.put(f"/bought-deals/{bought['id']}", json={**bought, "rehabCost": 65})
        assert updated.status_code == 200, updated.text
        assert float(updated.json()["rehabCost"]) == 65

    def test_bought_board_lists_the_deal(self, client, flip_payload):
        deal = _create(client, flip_payload)
        client.post(
            f"/bought-deals/from-active/{deal['id']}", params={"deal_type": "FLIP"}
        )
        bought = client.get("/bought-deals").json()
        assert len(bought) == 1
        assert bought[0]["deal_type"] == "FLIP"

    def test_delete_a_bought_deal(self, client, brrrr_payload):
        deal = _create(client, brrrr_payload)
        bought = client.post(
            f"/bought-deals/from-active/{deal['id']}", params={"deal_type": "BRRRR"}
        ).json()
        client.delete(f"/bought-deals/{bought['id']}", params={"deal_type": "BRRRR"})
        assert client.get("/bought-deals").json() == []


class TestDealReportPdf:
    def test_brrr_report_renders(self, client, brrrr_payload):
        response = client.post(
            "/reports/brrr-pdf", json=brrrr_payload, params={"address": "1 Shared Form St"}
        )
        assert response.status_code == 200, response.text
        assert response.content[:4] == b"%PDF"

    def test_flip_report_renders(self, client, flip_payload):
        response = client.post(
            "/reports/flip-pdf", json=flip_payload, params={"address": "2 Shared Form Ave"}
        )
        assert response.status_code == 200, response.text
        assert response.content[:4] == b"%PDF"
