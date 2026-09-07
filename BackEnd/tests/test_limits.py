"""Request-size and field-length limits (F-08): 413 before a huge body is
read, 422 for oversized fields, and the REPS upload caps."""

from __future__ import annotations

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from BL.common.body_limit import BodyLimitMiddleware
import importlib

# `routers/__init__.py` rebinds `routers.reps` to the router object; the module
# (whose caps the tests shrink) has to be looked up by name.
reps_router = importlib.import_module("routers.reps")


class TestBodyLimit:
    def test_oversized_body_is_refused_before_the_app_sees_it(self, monkeypatch):
        monkeypatch.setenv("MAX_BODY_BYTES", "100")
        app = FastAPI()
        seen = []

        @app.post("/x")
        async def x(payload: dict):
            seen.append(payload)
            return {"ok": True}

        app.add_middleware(BodyLimitMiddleware)
        client = TestClient(app)
        assert client.post("/x", json={"k": "v"}).status_code == 200
        response = client.post("/x", content=b'{"k": "' + b"v" * 200 + b'"}', headers={"content-type": "application/json"})
        assert response.status_code == 413
        assert response.json() == {"detail": "request body too large"}
        assert len(seen) == 1

    def test_the_live_app_has_the_limit(self, client, monkeypatch, brrrr_payload):
        monkeypatch.setenv("MAX_BODY_BYTES", "200")
        assert client.post("/analyze/brrr", json=brrrr_payload).status_code == 413


class TestFieldLimits:
    def test_notes_are_capped(self, client, brrrr_payload):
        assert client.post("/active-deals", json={**brrrr_payload, "notes": "x" * 20_000}).status_code == 200
        assert client.post("/active-deals", json={**brrrr_payload, "notes": "x" * 20_001}).status_code == 422

    def test_comp_lists_are_capped(self, client, brrrr_payload):
        comps = [{"url": "https://example.com", "arv": 1, "how_long_ago": "1d"}] * 201
        assert client.post("/active-deals", json={**brrrr_payload, "sold_comps": comps}).status_code == 422

    def test_reps_people_list_is_capped(self, client):
        payload = {
            "user": "Aviv2026",
            "description": "Walked the property with the contractor and reviewed the roof",
            "start_time": "2026-09-07T08:00:00+00:00",
            "end_time": "2026-09-07T09:00:00+00:00",
            "people_involved": ["p"] * 101,
        }
        assert client.post("/reps/log", json=payload).status_code == 422


class TestUploadCaps:
    def _files(self, n: int, size: int = 8):
        return [("files", (f"f{i}.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * size), "image/png")) for i in range(n)]

    def test_too_many_files(self, client):
        response = client.post("/reps/upload-batch", data={"user": "Aviv2026"}, files=self._files(11))
        assert response.status_code == 400
        assert "At most 10" in response.json()["detail"]

    def test_a_file_over_the_per_file_cap(self, client, monkeypatch):
        monkeypatch.setattr(reps_router, "MAX_UPLOAD_BYTES_PER_FILE", 64)
        response = client.post("/reps/upload-batch", data={"user": "Aviv2026"}, files=self._files(1, size=200))
        assert response.status_code == 413

    def test_total_over_the_batch_cap(self, client, monkeypatch):
        monkeypatch.setattr(reps_router, "MAX_UPLOAD_BYTES_TOTAL", 100)
        response = client.post("/reps/upload-batch", data={"user": "Aviv2026"}, files=self._files(3, size=40))
        assert response.status_code == 413

    def test_the_single_upload_route_has_the_same_cap(self, client, monkeypatch):
        monkeypatch.setattr(reps_router, "MAX_UPLOAD_BYTES_PER_FILE", 64)
        response = client.post("/reps/upload", data={"user": "Aviv2026"}, files={"file": ("f.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 200), "image/png")})
        assert response.status_code == 413

    def test_unknown_user_is_not_enumerated(self, client):
        response = client.post("/reps/upload-batch", data={"user": "Mallory"}, files=self._files(1))
        assert response.status_code == 400
        assert "Aviv" not in response.text and "Yarden" not in response.text
