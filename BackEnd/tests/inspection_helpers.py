"""Shared helpers for the property inspection tests (tasks/todo/PropertyInspection.md)."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from BL.auth import service as service_bl
from BL.auth.common import settings as auth_settings
from BL.inspection import authenticatedInspection, inspectionPhotos
from tests.test_auth_passkeys import ORIGIN, XRW, enroll
from tests.webauthn_helpers import SoftPasskey

PUBLIC_WRITE_HEADERS = XRW
SMALLEST_VALID_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"


@dataclass
class FakeInspectionPhotoDrive:
    """Stands in for the Apps Script: keeps the full images in memory."""

    images_by_file_id: dict = field(default_factory=dict)
    trashed_file_ids: list = field(default_factory=list)
    saved_folder_names: list = field(default_factory=list)
    _file_id_counter: itertools.count = field(default_factory=lambda: itertools.count(1))

    def save(self, inspection_folder_name: str, file_name: str, jpeg_image: bytes) -> str:
        file_id = f"drive-file-{next(self._file_id_counter)}"
        self.images_by_file_id[file_id] = jpeg_image
        self.saved_folder_names.append(inspection_folder_name)
        return file_id

    def read(self, drive_file_id: str) -> bytes:
        return self.images_by_file_id[drive_file_id]

    def trash(self, drive_file_id: str) -> None:
        self.trashed_file_ids.append(drive_file_id)
        self.images_by_file_id.pop(drive_file_id, None)


@pytest.fixture
def inspection_photo_drive(monkeypatch) -> FakeInspectionPhotoDrive:
    drive = FakeInspectionPhotoDrive()
    monkeypatch.setattr(inspectionPhotos, "save_inspection_photo_to_drive", drive.save)
    monkeypatch.setattr(inspectionPhotos, "read_inspection_photo_from_drive", drive.read)
    monkeypatch.setattr(inspectionPhotos, "trash_inspection_photo_in_drive", drive.trash)
    monkeypatch.setattr(authenticatedInspection, "trash_inspection_photo_in_drive", drive.trash)
    return drive


@pytest.fixture
def enforced_login(monkeypatch):
    """AUTH_MODE=enforce: the logged-in inspection routes need a real passkey session."""

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "enforce")
    monkeypatch.delenv("DEVICE_POLICY", raising=False)
    monkeypatch.delenv("AUTH_COOKIE_SECURE", raising=False)
    service_bl.forget()
    yield
    service_bl.forget()


def logged_in_client() -> TestClient:
    from main import app  # the app conftest already imported and wired to the test database

    member_client = TestClient(app)
    enroll(member_client, SoftPasskey(auth_settings.rp_id(), ORIGIN), username="aviv")
    return member_client


def create_public_inspection(client: TestClient, **overrides) -> dict:
    body = {"property_address": "12 Palm Ave, Tampa, FL", "inspector_name": "Aviv", **overrides}
    response = client.post("/public/inspections", json=body, headers=PUBLIC_WRITE_HEADERS)
    assert response.status_code == 201, response.text
    return response.json()


def update_item(client: TestClient, inspection_id: str, item_key: str, **body):
    return client.patch(f"/public/inspections/{inspection_id}/items/{item_key}", json=body, headers=PUBLIC_WRITE_HEADERS)


def create_bought_deal(client: TestClient, brrrr_payload: dict) -> dict:
    response = client.post("/bought-deals", json={**brrrr_payload, "deal_type": "BRRRR"}, headers=PUBLIC_WRITE_HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def find_keys_anywhere(value, wanted_substrings: tuple[str, ...]) -> list[str]:
    """Every dict key (at any depth) that contains one of the substrings."""

    found: list[str] = []
    if isinstance(value, dict):
        for key, inner in value.items():
            if any(substring in key.lower() for substring in wanted_substrings):
                found.append(key)
            found.extend(find_keys_anywhere(inner, wanted_substrings))
    elif isinstance(value, list):
        for inner in value:
            found.extend(find_keys_anywhere(inner, wanted_substrings))
    return found
