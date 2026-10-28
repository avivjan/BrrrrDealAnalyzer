"""Property inspection endpoints (tasks/todo/PropertyInspection.md).

The walkthrough is public by link; listing, deleting and deal links need a
session. Public responses never carry deal data.
"""

from __future__ import annotations

import uuid

import pytest

from BL.inspection.common import inspection_request_guards
from main import app
from tests.inspection_helpers import (  # noqa: F401 -- fixtures
    PUBLIC_WRITE_HEADERS,
    SMALLEST_VALID_JPEG,
    create_bought_deal,
    create_public_inspection,
    enforced_login,
    find_keys_anywhere,
    inspection_photo_drive,
    logged_in_client,
    update_item,
)

ALL_CRITICAL_ITEM_KEYS = ["roof", "foundation", "hvac", "electrical", "plumbing", "water_heater", "sewer", "water_supply"]
DEAL_KEY_SUBSTRINGS = ("deal", "brrrr", "flip")


@pytest.fixture
def enforced_gates(monkeypatch, enforced_login):  # noqa: F811
    monkeypatch.setenv("APP_KEY_MODE", "enforce")
    monkeypatch.setenv("APP_KEY", "test-app-key-not-a-secret-0000000")


class TestPublicAccess:
    def test_public_inspection_endpoints_work_without_any_session_or_app_key(self, client, enforced_gates, inspection_photo_drive):  # noqa: F811
        inspection = create_public_inspection(client)
        inspection_id = inspection["id"]
        assert client.get(f"/public/inspections/{inspection_id}").status_code == 200
        assert client.patch(f"/public/inspections/{inspection_id}", json={"inspector_name": "Yarden"}, headers=PUBLIC_WRITE_HEADERS).status_code == 200
        assert update_item(client, inspection_id, "roof", item_status="ok").status_code == 200
        upload = client.post(
            f"/public/inspections/{inspection_id}/items/roof/photos",
            files={"full_image": ("p.jpg", SMALLEST_VALID_JPEG, "image/jpeg"), "thumbnail_image": ("t.jpg", SMALLEST_VALID_JPEG, "image/jpeg")},
            headers=PUBLIC_WRITE_HEADERS,
        )
        assert upload.status_code == 201, upload.text
        photo_id = upload.json()["id"]
        assert client.get(f"/public/inspections/{inspection_id}/photos/{photo_id}/thumbnail").status_code == 200
        assert client.get(f"/public/inspections/{inspection_id}/photos/{photo_id}/full").status_code == 200
        assert client.delete(f"/public/inspections/{inspection_id}/photos/{photo_id}", headers=PUBLIC_WRITE_HEADERS).status_code == 200
        complete = client.post(
            f"/public/inspections/{inspection_id}/complete",
            json={"completion_override_reason": "Seller would not let us in the attic"},
            headers=PUBLIC_WRITE_HEADERS,
        )
        assert complete.status_code == 200, complete.text

    def test_create_defaults_the_inspection_date_to_today_and_cleans_text(self, client):
        from datetime import date

        inspection = create_public_inspection(client, property_address="  12 Palm\x00 Ave  ", inspector_name="  ")
        assert inspection["inspection_date"] == date.today().isoformat()
        assert inspection["property_address"] == "12 Palm Ave"
        assert inspection["inspector_name"] is None
        assert inspection["inspection_status"] == "draft"
        assert uuid.UUID(inspection["id"]).version == 4

    def test_create_validates_address_and_unknown_fields(self, client):
        assert client.post("/public/inspections", json={"property_address": "x"}, headers=PUBLIC_WRITE_HEADERS).status_code == 422
        assert client.post("/public/inspections", json={"property_address": "12 Palm Ave", "linked_bought_brrrr_deal_id": str(uuid.uuid4())}, headers=PUBLIC_WRITE_HEADERS).status_code == 422
        assert client.post("/public/inspections", json={"property_address": "12 Palm Ave", "inspection_date": "2001-01-01"}, headers=PUBLIC_WRITE_HEADERS).status_code == 422

    def test_public_writes_need_the_csrf_header(self, client):
        assert client.post("/public/inspections", json={"property_address": "12 Palm Ave"}).status_code == 403
        assert client.post("/public/inspections", json={"property_address": "12 Palm Ave"}, headers={**PUBLIC_WRITE_HEADERS, "Origin": "https://evil.example"}).status_code == 403

    def test_no_public_endpoint_lists_inspections(self, client):
        create_public_inspection(client)
        public_paths = {path: operations for path, operations in app.openapi()["paths"].items() if path.startswith("/public/")}
        assert "get" not in public_paths["/public/inspections"]
        assert client.get("/public/inspections").status_code == 405
        list_like_paths = [path for path, operations in public_paths.items() if "get" in operations and "{inspection_id}" not in path]
        assert list_like_paths == []

    def test_unknown_or_malformed_inspection_id_returns_404(self, client):
        for bad_id in (str(uuid.uuid4()), "not-a-uuid", "00000000-0000-1000-8000-000000000000", str(uuid.uuid4()).upper()):
            assert client.get(f"/public/inspections/{bad_id}").status_code == 404
        inspection = create_public_inspection(client)
        assert update_item(client, inspection["id"], "swimming_pool", item_status="ok").status_code == 404
        assert client.get(f"/public/inspections/{inspection['id']}/photos/not-a-uuid/thumbnail").status_code == 404

    def test_oversized_json_body_is_refused(self, client):
        inspection = create_public_inspection(client)
        response = update_item(client, inspection["id"], "roof", item_notes="x" * 40_000)
        assert response.status_code == 413

    def test_public_inspection_rate_limit_returns_429(self, client, monkeypatch):
        monkeypatch.setitem(inspection_request_guards.REQUESTS_PER_HOUR_BY_LIMIT_NAME, "inspection_create", 2)
        create_public_inspection(client)
        create_public_inspection(client)
        response = client.post("/public/inspections", json={"property_address": "12 Palm Ave"}, headers=PUBLIC_WRITE_HEADERS)
        assert response.status_code == 429


class TestItems:
    def test_item_patch_merges_field_values_without_clobbering_other_fields(self, client):
        inspection_id = create_public_inspection(client)["id"]
        assert update_item(client, inspection_id, "plumbing", item_field_values={"supply_pipe_material": "pex"}).status_code == 200
        # A second device sets another field of the same item.
        response = update_item(client, inspection_id, "plumbing", item_field_values={"drain_pipe_material": "cast_iron"})
        assert response.status_code == 200
        assert response.json()["item_field_values"] == {"supply_pipe_material": "pex", "drain_pipe_material": "cast_iron"}
        # Status and notes change on their own.
        response = update_item(client, inspection_id, "plumbing", item_status="repair", item_notes="Leak under the kitchen sink")
        assert response.json()["item_status"] == "repair"
        assert response.json()["item_field_values"] == {"supply_pipe_material": "pex", "drain_pipe_material": "cast_iron"}
        # null clears a single field.
        response = update_item(client, inspection_id, "plumbing", item_field_values={"drain_pipe_material": None})
        assert response.json()["item_field_values"] == {"supply_pipe_material": "pex"}
        assert response.json()["item_notes"] == "Leak under the kitchen sink"

    def test_item_patch_validates_field_values_against_the_config(self, client):
        inspection_id = create_public_inspection(client)["id"]
        assert update_item(client, inspection_id, "roof", item_field_values={"roof_type": "straw"}).status_code == 422
        assert update_item(client, inspection_id, "roof", item_status="broken").status_code == 422
        assert update_item(client, inspection_id, "windows", item_field_values={"windows_needing_replacement_count": 500}).status_code == 422

    def test_summary_lists_repair_and_replace_items_and_the_window_count(self, client):
        inspection_id = create_public_inspection(client)["id"]
        update_item(client, inspection_id, "roof", item_status="replace", item_field_values={"roof_type": "shingle", "roof_install_year": 2004})
        update_item(client, inspection_id, "windows", item_status="repair", item_field_values={"windows_needing_replacement_count": 3})
        update_item(client, inspection_id, "sewer", item_status="ok", item_field_values={"sewer_type": "city", "septic_last_pump_date": "2020-01-01"})
        summary = client.get(f"/public/inspections/{inspection_id}").json()["summary"]
        assert [item["item_key"] for item in summary["items_marked_replace"]] == ["roof"]
        assert [item["item_key"] for item in summary["items_marked_repair"]] == ["windows"]
        assert summary["items_marked_ok"][0]["visible_field_values"] == {"sewer_type": "city"}
        assert summary["windows_needing_replacement_count"] == 3
        assert summary["checked_item_count"] == 3
        assert summary["total_item_count"] == 10
        assert "roof" not in summary["critical_item_keys_not_checked"]
        assert "hvac" in summary["critical_item_keys_not_checked"]


class TestCompletion:
    def test_completion_blocked_with_unchecked_critical_items(self, client):
        inspection_id = create_public_inspection(client)["id"]
        for item_key in ALL_CRITICAL_ITEM_KEYS[:-1]:
            update_item(client, inspection_id, item_key, item_status="ok")
        response = client.post(f"/public/inspections/{inspection_id}/complete", json={}, headers=PUBLIC_WRITE_HEADERS)
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "critical_items_unchecked"
        assert response.json()["detail"]["critical_item_keys_not_checked"] == ["water_supply"]

        update_item(client, inspection_id, "water_supply", item_status="repair")
        response = client.post(f"/public/inspections/{inspection_id}/complete", json={}, headers=PUBLIC_WRITE_HEADERS)
        assert response.status_code == 200
        assert response.json()["inspection_status"] == "completed"
        assert response.json()["completion_override_reason"] is None

    def test_completion_override_requires_reason(self, client):
        inspection_id = create_public_inspection(client)["id"]
        too_short = client.post(f"/public/inspections/{inspection_id}/complete", json={"completion_override_reason": "nah"}, headers=PUBLIC_WRITE_HEADERS)
        assert too_short.status_code == 422
        response = client.post(
            f"/public/inspections/{inspection_id}/complete",
            json={"completion_override_reason": "Roof inspected by the roofer separately"},
            headers=PUBLIC_WRITE_HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["completion_override_reason"] == "Roof inspected by the roofer separately"
        assert client.get(f"/public/inspections/{inspection_id}").json()["completion_override_reason"] == "Roof inspected by the roofer separately"


class TestLoggedInRoutes:
    def test_link_unlink_list_delete_and_bought_deals_picker_return_401_without_session(self, client, enforced_login):  # noqa: F811
        inspection_id = create_public_inspection(client)["id"]
        deal_link_body = {"bought_deal_id": str(uuid.uuid4()), "deal_type": "BRRRR"}
        assert client.get("/inspections").status_code == 401
        assert client.get("/bought-deals").status_code == 401
        assert client.get(f"/inspections/{inspection_id}/deal-link").status_code == 401
        assert client.put(f"/inspections/{inspection_id}/deal-link", json=deal_link_body, headers=PUBLIC_WRITE_HEADERS).status_code == 401
        assert client.delete(f"/inspections/{inspection_id}/deal-link", headers=PUBLIC_WRITE_HEADERS).status_code == 401
        assert client.get(f"/bought-deals/{uuid.uuid4()}/inspections?deal_type=BRRRR").status_code == 401
        assert client.post(f"/bought-deals/{uuid.uuid4()}/inspections?deal_type=BRRRR", json={}, headers=PUBLIC_WRITE_HEADERS).status_code == 401

    def test_delete_inspection_requires_session(self, client, enforced_login, inspection_photo_drive):  # noqa: F811
        inspection_id = create_public_inspection(client)["id"]
        assert client.delete(f"/inspections/{inspection_id}", headers=PUBLIC_WRITE_HEADERS).status_code == 401
        assert client.get(f"/public/inspections/{inspection_id}").status_code == 200

        member_client = logged_in_client()
        client.post(
            f"/public/inspections/{inspection_id}/items/roof/photos",
            files={"full_image": ("p.jpg", SMALLEST_VALID_JPEG, "image/jpeg"), "thumbnail_image": ("t.jpg", SMALLEST_VALID_JPEG, "image/jpeg")},
            headers=PUBLIC_WRITE_HEADERS,
        )
        assert member_client.delete(f"/inspections/{inspection_id}", headers=PUBLIC_WRITE_HEADERS).status_code == 200
        assert client.get(f"/public/inspections/{inspection_id}").status_code == 404
        assert inspection_photo_drive.trashed_file_ids == ["drive-file-1"]

    def test_logged_in_user_lists_links_and_unlinks(self, client, enforced_login, brrrr_payload):  # noqa: F811
        member_client = logged_in_client()
        deal = create_bought_deal(member_client, brrrr_payload)
        inspection_id = create_public_inspection(client)["id"]
        update_item(client, inspection_id, "roof", item_status="replace")

        linked = member_client.put(
            f"/inspections/{inspection_id}/deal-link", json={"bought_deal_id": deal["id"], "deal_type": "BRRRR"}, headers=PUBLIC_WRITE_HEADERS
        )
        assert linked.status_code == 200, linked.text
        assert linked.json()["linked_deal"] == {"bought_deal_id": deal["id"], "deal_type": "BRRRR", "property_address": deal["address"]}

        rows = member_client.get("/inspections").json()
        assert rows[0]["id"] == inspection_id
        assert rows[0]["repair_or_replace_item_count"] == 1
        assert rows[0]["linked_deal"]["bought_deal_id"] == deal["id"]

        deal_rows = member_client.get(f"/bought-deals/{deal['id']}/inspections?deal_type=BRRRR").json()
        assert [row["id"] for row in deal_rows] == [inspection_id]

        unlinked = member_client.delete(f"/inspections/{inspection_id}/deal-link", headers=PUBLIC_WRITE_HEADERS)
        assert unlinked.json() == {"linked_deal": None}
        assert member_client.get(f"/bought-deals/{deal['id']}/inspections?deal_type=BRRRR").json() == []

    def test_linking_to_a_missing_deal_is_404(self, client, brrrr_payload):
        inspection_id = create_public_inspection(client)["id"]
        response = client.put(
            f"/inspections/{inspection_id}/deal-link", json={"bought_deal_id": str(uuid.uuid4()), "deal_type": "FLIP"}, headers=PUBLIC_WRITE_HEADERS
        )
        assert response.status_code == 404

    def test_new_inspection_from_a_bought_deal_is_linked_with_the_address_prefilled(self, client, brrrr_payload):
        deal = create_bought_deal(client, brrrr_payload)
        response = client.post(f"/bought-deals/{deal['id']}/inspections?deal_type=BRRRR", json={"inspector_name": "Yarden"}, headers=PUBLIC_WRITE_HEADERS)
        assert response.status_code == 201, response.text
        assert response.json()["property_address"] == deal["address"]
        assert response.json()["linked"] is True
        assert client.get(f"/inspections/{response.json()['id']}/deal-link").json()["linked_deal"]["bought_deal_id"] == deal["id"]

    def test_deleting_the_deal_keeps_the_inspection_and_clears_the_link(self, client, brrrr_payload):
        deal = create_bought_deal(client, brrrr_payload)
        inspection = client.post(f"/bought-deals/{deal['id']}/inspections?deal_type=BRRRR", json={}, headers=PUBLIC_WRITE_HEADERS).json()
        assert client.delete(f"/bought-deals/{deal['id']}?deal_type=BRRRR", headers=PUBLIC_WRITE_HEADERS).status_code == 200
        after = client.get(f"/public/inspections/{inspection['id']}").json()
        assert after["linked"] is False


class TestNoDealDataInPublicResponses:
    def test_public_get_never_returns_deal_data_even_when_linked(self, client, brrrr_payload, inspection_photo_drive):  # noqa: F811
        deal = create_bought_deal(client, brrrr_payload)
        inspection = client.post(f"/bought-deals/{deal['id']}/inspections?deal_type=BRRRR", json={}, headers=PUBLIC_WRITE_HEADERS).json()
        inspection_id = inspection["id"]
        public_responses = [
            client.get(f"/public/inspections/{inspection_id}").json(),
            client.patch(f"/public/inspections/{inspection_id}", json={"inspector_name": "Aviv"}, headers=PUBLIC_WRITE_HEADERS).json(),
            update_item(client, inspection_id, "roof", item_status="ok").json(),
            client.post(
                f"/public/inspections/{inspection_id}/items/roof/photos",
                files={"full_image": ("p.jpg", SMALLEST_VALID_JPEG, "image/jpeg"), "thumbnail_image": ("t.jpg", SMALLEST_VALID_JPEG, "image/jpeg")},
                headers=PUBLIC_WRITE_HEADERS,
            ).json(),
            client.post(
                f"/public/inspections/{inspection_id}/complete", json={"completion_override_reason": "testing the public shape"}, headers=PUBLIC_WRITE_HEADERS
            ).json(),
        ]
        for public_response in public_responses:
            assert find_keys_anywhere(public_response, DEAL_KEY_SUBSTRINGS) == [], public_response
            assert deal["id"] not in str(public_response)
        assert public_responses[0]["linked"] is True

    def test_public_response_schemas_have_no_deal_fields(self):
        spec = app.openapi()
        public_response_refs = set()
        for path, operations in spec["paths"].items():
            if not path.startswith("/public/"):
                continue
            for operation in operations.values():
                for response in operation["responses"].values():
                    schema = response.get("content", {}).get("application/json", {}).get("schema", {})
                    if "$ref" in schema:
                        public_response_refs.add(schema["$ref"].rsplit("/", 1)[-1])
        assert public_response_refs >= {"PublicInspectionRes", "InspectionItemRes", "InspectionPhotoRes"}
        schemas = spec["components"]["schemas"]
        seen, pending = set(), list(public_response_refs)
        while pending:
            name = pending.pop()
            if name in seen:
                continue
            seen.add(name)
            assert find_keys_anywhere(schemas[name].get("properties", {}), DEAL_KEY_SUBSTRINGS) == [], name
            for ref in __import__("re").findall(r"#/components/schemas/(\w+)", str(schemas[name])):
                pending.append(ref)


class TestPhotos:
    def _upload(self, client, inspection_id, full_image=SMALLEST_VALID_JPEG, thumbnail_image=SMALLEST_VALID_JPEG, item_key="roof"):
        return client.post(
            f"/public/inspections/{inspection_id}/items/{item_key}/photos",
            files={"full_image": ("p.jpg", full_image, "image/jpeg"), "thumbnail_image": ("t.jpg", thumbnail_image, "image/jpeg")},
            headers=PUBLIC_WRITE_HEADERS,
        )

    def test_photo_upload_stores_full_image_in_drive_and_thumbnail_here(self, client, inspection_photo_drive):  # noqa: F811
        inspection = create_public_inspection(client)
        photo = self._upload(client, inspection["id"]).json()
        assert inspection_photo_drive.saved_folder_names[0].endswith(f"({inspection['id'][:8]})")
        thumbnail = client.get(f"/public/inspections/{inspection['id']}/photos/{photo['id']}/thumbnail")
        assert thumbnail.headers["content-type"] == "image/jpeg"
        assert thumbnail.headers["x-content-type-options"] == "nosniff"
        assert thumbnail.content == SMALLEST_VALID_JPEG
        assert client.get(f"/public/inspections/{inspection['id']}").json()["photos"][0]["id"] == photo["id"]

    def test_photo_upload_rejects_non_jpeg_and_oversized_files(self, client, inspection_photo_drive):  # noqa: F811
        inspection_id = create_public_inspection(client)["id"]
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        html_pretending_to_be_jpeg = b"<html><script>alert(1)</script></html>"
        assert self._upload(client, inspection_id, full_image=png).status_code == 415
        assert self._upload(client, inspection_id, thumbnail_image=html_pretending_to_be_jpeg).status_code == 415
        oversized_full_image = b"\xff\xd8\xff\xe0" + b"\x00" * (4 * 1024 * 1024) + b"\xff\xd9"
        assert self._upload(client, inspection_id, full_image=oversized_full_image).status_code == 413
        oversized_thumbnail = b"\xff\xd8\xff\xe0" + b"\x00" * (150 * 1024) + b"\xff\xd9"
        assert self._upload(client, inspection_id, thumbnail_image=oversized_thumbnail).status_code == 413
        assert self._upload(client, inspection_id, item_key="swimming_pool").status_code == 404
        assert inspection_photo_drive.images_by_file_id == {}

    def test_photo_count_limits(self, client, inspection_photo_drive, monkeypatch):  # noqa: F811
        from BL.inspection import inspectionPhotos

        monkeypatch.setattr(inspectionPhotos, "MAXIMUM_PHOTOS_PER_ITEM", 2)
        monkeypatch.setattr(inspectionPhotos, "MAXIMUM_PHOTOS_PER_INSPECTION", 3)
        inspection_id = create_public_inspection(client)["id"]
        assert self._upload(client, inspection_id).status_code == 201
        assert self._upload(client, inspection_id).status_code == 201
        assert self._upload(client, inspection_id).status_code == 409
        assert self._upload(client, inspection_id, item_key="hvac").status_code == 201
        assert self._upload(client, inspection_id, item_key="sewer").status_code == 409

    def test_photo_upload_answers_503_when_drive_is_not_configured(self, client, monkeypatch):
        monkeypatch.delenv("INSPECTION_PHOTOS_DRIVE_UPLOAD_URL", raising=False)
        inspection_id = create_public_inspection(client)["id"]
        response = self._upload(client, inspection_id)
        assert response.status_code == 503
        assert response.json()["detail"] == "photo_storage_unavailable"

    def test_photo_of_another_inspection_is_404(self, client, inspection_photo_drive):  # noqa: F811
        first_inspection_id = create_public_inspection(client)["id"]
        second_inspection_id = create_public_inspection(client)["id"]
        photo_id = self._upload(client, first_inspection_id).json()["id"]
        assert client.get(f"/public/inspections/{second_inspection_id}/photos/{photo_id}/thumbnail").status_code == 404
        assert client.delete(f"/public/inspections/{second_inspection_id}/photos/{photo_id}", headers=PUBLIC_WRITE_HEADERS).status_code == 404

