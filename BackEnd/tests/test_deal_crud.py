"""Deal persistence: the endpoints the three deal-input screens actually call.

Covers the full path a deal takes through the product — Analyze page save,
My Deals card autosave, duplicate/delete, Move to Bought, and Bought Deals card
autosave — using the exact field names `DealInputsForm` emits.
"""

from __future__ import annotations

import pytest
from ReqRes.common.brrr_lifecycle_inputs import BrrrLifecycleInputs

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
    # lifecycle line items (numeric; the date, enum, booleans and formula-default
    # nullables round-trip in TestLifecycleFieldsRoundTrip)
    "earnestMoneyDeposit",
    "loanChargesBuy",
    "otherClosingCostsBuy",
    "constructionLoanBudget",
    "rehabCushion",
    "daysUntilRented",
    "monthlyUtilitiesUntilRented",
    "maintenanceBeforeRefi",
    "appliances",
    "loanChargesRefi",
    "appraisalFee",
    "surveyFee",
    "refiUnderwritingFee",
    "brokerProcessingFeeRefi",
    "otherClosingCostsRefi",
    "maintenanceReserve",
    "capexReserve",
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


class TestLifecycleFieldsRoundTrip:
    """The non-numeric lifecycle inputs: an ISO date, a title-mode enum, two checkboxes and the
    'None = formula default' nullables, through create, update and the board load."""

    def test_date_enum_and_checkboxes_survive(self, client, brrrr_payload):
        deal = _create(client, {**brrrr_payload, "buyClosingDate": "2026-03-05", "titleModeBuy": "we_pay_all",
                                "onlineNotaryBuy": False, "onlineNotaryRefi": True, "sellerPaidCurrentYearTaxes": True})
        assert deal["buyClosingDate"] == "2026-03-05"
        assert deal["titleModeBuy"] == "we_pay_all"
        assert deal["onlineNotaryBuy"] is False and deal["onlineNotaryRefi"] is True
        assert deal["sellerPaidCurrentYearTaxes"] is True
        assert deal["refi_closing_date"] == "2026-09-01"  # + 180 days
        assert deal["tenant_occupied_date"] == "2026-06-03"  # + 90 days

    def test_formula_defaults_stay_null_until_typed(self, client, brrrr_payload):
        deal = _create(client, brrrr_payload)
        for field in ("recordingTransferBuy", "titleEscrowBuy", "recordingTransferRefi", "titleEscrowRefi",
                      "vacancyReserve", "lowestArv", "buyClosingDate"):
            if field != "buyClosingDate":
                assert deal[field] is None, field
        assert float(deal["vacancy_reserve_effective"]) == pytest.approx(float(brrrr_payload["rent"]))
        assert float(deal["lowest_arv_effective"]) == pytest.approx(0.9 * brrrr_payload["arv_in_thousands"] * 1000)
        deal_with_typed_overrides = client.put(f"/active-deals/{deal['id']}", json={**deal, "recordingTransferBuy": 1234.5, "lowestArv": 300}).json()
        assert float(deal_with_typed_overrides["recordingTransferBuy"]) == pytest.approx(1234.5)
        assert float(deal_with_typed_overrides["recording_transfer_buy_effective"]) == pytest.approx(1234.5)
        assert float(deal_with_typed_overrides["lowest_arv_effective"]) == pytest.approx(300000)
        deal_reset_to_formula = client.put(f"/active-deals/{deal['id']}", json={**deal_with_typed_overrides, "recordingTransferBuy": None}).json()
        assert deal_reset_to_formula["recordingTransferBuy"] is None
        assert float(deal_reset_to_formula["recording_transfer_buy_effective"]) != pytest.approx(1234.5)

    def test_notary_fees_and_closing_cost_notes_round_trip(self, client, brrrr_payload):
        long_note = "x" * 500
        deal = _create(client, {**brrrr_payload, "onlineNotaryFeeBuy": 175, "onlineNotaryFeeRefi": 300,
                                "otherClosingCostsBuyNote": "HOA transfer + home warranty", "otherClosingCostsRefiNote": long_note})
        assert float(deal["onlineNotaryFeeBuy"]) == 175 and float(deal["onlineNotaryFeeRefi"]) == 300
        assert deal["otherClosingCostsBuyNote"] == "HOA transfer + home warranty"
        assert deal["otherClosingCostsRefiNote"] == long_note
        assert client.post("/active-deals", json={**brrrr_payload, "otherClosingCostsBuyNote": "x" * 501}).status_code == 422
        untouched = _create(client, brrrr_payload)
        assert untouched["onlineNotaryFeeBuy"] is None and untouched["otherClosingCostsBuyNote"] is None

    def test_no_date_leaves_the_date_driven_figures_out(self, client, brrrr_payload):
        deal = _create(client, {**brrrr_payload, "buyClosingDate": None})
        assert deal["buyClosingDate"] is None and deal["refi_closing_date"] is None
        assert deal["prepaid_interest_buy"] == 0 and deal["seller_tax_credit"] == 0 and deal["prepaid_interest_refi"] == 0

    def test_a_stale_client_sending_the_hm_flag_gets_a_construction_budget(self, client, brrrr_payload):
        """A stale client speaks the pre-lifecycle model: no lifecycle field at all, just the boolean."""
        lifecycle_aliases = {field.alias or name for name, field in BrrrLifecycleInputs.model_fields.items()}
        stale_payload = {key: value for key, value in brrrr_payload.items() if key not in lifecycle_aliases}
        hard_money_rehab_deal = _create(client, {**stale_payload, "use_HM_for_rehab": True, "rehabCost": 50, "rehabContingency": 10})
        assert float(hard_money_rehab_deal["constructionLoanBudget"]) == pytest.approx(55)
        cash_rehab_deal = _create(client, {**stale_payload, "use_HM_for_rehab": False})
        assert float(cash_rehab_deal["constructionLoanBudget"]) == 0

    def test_a_current_client_that_clears_the_budget_saves_zero_even_with_the_old_flag_on(self, client, brrrr_payload):
        """The form still sends `use_HM_for_rehab` (true on a new deal) and omits a cleared budget field.
        That must mean a $0 budget, never a silently re-derived full-rehab budget."""
        payload_without_budget = {key: value for key, value in brrrr_payload.items() if key != "constructionLoanBudget"}
        deal = _create(client, {**payload_without_budget, "use_HM_for_rehab": True})
        assert float(deal["constructionLoanBudget"]) == 0
        assert deal["stolen_money"] == pytest.approx(-float(deal["rehabCost"]) * 1000 * (1 + float(deal["rehabContingency"]) / 100))


class TestSavedDealDefaultsMatchTheCalculator:
    def test_a_deal_saved_without_refi_points_is_priced_like_the_calculator(self, client, brrrr_payload):
        """`add_*_deal` used to dump with exclude_unset, so an omitted field took the DDL default
        (refi_points 1.5) while the calculator took the Pydantic default (2): one body, two wires."""
        without_refi_points = {key: value for key, value in brrrr_payload.items() if key != "refiPoints"}
        saved = _create(client, without_refi_points)
        analyzed = client.post("/analyze/brrr", json=without_refi_points).json()
        assert float(saved["refiPoints"]) == 2
        assert saved["cash_out_routi"] == pytest.approx(analyzed["cash_out_routi"])
        assert saved["cash_out"] == pytest.approx(analyzed["cash_out"])
        assert saved["total_cash_needed_for_deal"] == pytest.approx(analyzed["total_cash_needed_for_deal"])


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


class TestGoogleDriveLink:
    """The Drive folder link a bought card shows: a plain shared text field, both deal types,
    through create, autosave, move-to-bought and the bought-card autosave."""

    DRIVE_URL = "https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz"

    @pytest.mark.parametrize("payload_fixture", ["brrrr_payload", "flip_payload"])
    def test_round_trips_on_create_and_update(self, client, request, payload_fixture):
        payload = request.getfixturevalue(payload_fixture)
        deal = _create(client, {**payload, "google_drive_link": self.DRIVE_URL})
        assert deal["google_drive_link"] == self.DRIVE_URL
        cleared = client.put(f"/active-deals/{deal['id']}", json={**deal, "google_drive_link": None})
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["google_drive_link"] is None

    @pytest.mark.parametrize("payload_fixture, deal_type", [("brrrr_payload", "BRRRR"), ("flip_payload", "FLIP")])
    def test_carries_across_to_bought_and_autosaves_there(self, client, request, payload_fixture, deal_type):
        payload = request.getfixturevalue(payload_fixture)
        deal = _create(client, {**payload, "google_drive_link": self.DRIVE_URL})
        bought = client.post(f"/bought-deals/from-active/{deal['id']}", params={"deal_type": deal_type}).json()
        assert bought["google_drive_link"] == self.DRIVE_URL
        edited_url = self.DRIVE_URL + "-edited"
        updated = client.put(f"/bought-deals/{bought['id']}", json={**bought, "google_drive_link": edited_url})
        assert updated.status_code == 200, updated.text
        assert updated.json()["google_drive_link"] == edited_url
        assert client.get("/bought-deals").json()[0]["google_drive_link"] == edited_url

    def test_is_null_when_never_set(self, client, brrrr_payload):
        assert _create(client, brrrr_payload)["google_drive_link"] is None

    def test_is_capped_like_the_other_links(self, client, brrrr_payload):
        too_long = client.post("/active-deals", json={**brrrr_payload, "google_drive_link": "https://" + "x" * 2_000})
        assert too_long.status_code == 422


class TestBrokerProcessingFeeDefault:
    def test_an_omitted_fee_saves_as_zero(self, client, brrrr_payload):
        without_fee = {k: v for k, v in brrrr_payload.items() if k != "brokerProcessingFeeRefi"}
        assert float(_create(client, without_fee)["brokerProcessingFeeRefi"]) == 0.0


class TestBoughtDealReportPdf:
    """The bought modal sends the bought deal whole (stage, checklist and results included);
    the report endpoint must accept that body exactly as it accepts an active deal's."""

    @pytest.mark.parametrize("payload_fixture, deal_type, endpoint", [
        ("brrrr_payload", "BRRRR", "/reports/brrr-pdf"),
        ("flip_payload", "FLIP", "/reports/flip-pdf"),
    ])
    def test_a_bought_deal_body_renders(self, client, request, payload_fixture, deal_type, endpoint):
        payload = request.getfixturevalue(payload_fixture)
        deal = _create(client, payload)
        bought = client.post(f"/bought-deals/from-active/{deal['id']}", params={"deal_type": deal_type}).json()
        response = client.post(endpoint, json=bought, params={"address": bought["address"]})
        assert response.status_code == 200, response.text
        assert response.content[:4] == b"%PDF"
