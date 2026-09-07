"""Unhandled errors reach the client as `internal error` plus a reference id,
never as exception text (F-09); deliberate HTTPExceptions are untouched."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from main import _unhandled_exception


def _scratch() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(Exception, _unhandled_exception)

    @app.get("/boom")
    def boom():
        raise RuntimeError("database password is hunter2")

    @app.get("/teapot")
    def teapot():
        raise HTTPException(status_code=418, detail="short and stout")

    return app


def test_unhandled_exception_body_has_a_ref_and_no_exception_text(caplog):
    with caplog.at_level(logging.ERROR, logger="main"):
        response = TestClient(_scratch(), raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "internal error"
    assert len(body["ref"]) == 12
    assert "hunter2" not in response.text
    # ... but the log line carries the ref so the traceback can be found.
    assert any(body["ref"] in r.getMessage() for r in caplog.records)
    assert "hunter2" in caplog.text


def test_http_exceptions_pass_through():
    response = TestClient(_scratch()).get("/teapot")
    assert response.status_code == 418
    assert response.json() == {"detail": "short and stout"}


def test_the_live_app_never_echoes_driver_errors(client):
    # A bad UUID used to surface a raw psycopg2 error as an unhandled 500.
    response = TestClient(client.app, raise_server_exceptions=False).delete("/active-deals/not-a-uuid")
    assert response.status_code == 500
    assert response.json()["detail"] == "internal error"
    assert "psycopg2" not in response.text and "SELECT" not in response.text
