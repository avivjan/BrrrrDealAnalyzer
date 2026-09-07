"""`BL.common.secret.Secret` never prints its value."""

from __future__ import annotations

import logging

from BL.common.secret import Secret


def test_reveal_returns_the_value():
    assert Secret("tok-123").reveal() == "tok-123"


def test_every_string_form_is_redacted():
    s = Secret("tok-123")
    assert repr(s) == "Secret(***)"
    assert str(s) == "Secret(***)"
    assert f"{s}" == "Secret(***)"
    assert f"{s!r}" == "Secret(***)"
    assert "%s" % s == "Secret(***)"
    assert "tok-123" not in repr({"default": s})
    assert "tok-123" not in repr([s])


def test_logging_a_secret_does_not_leak(caplog):
    with caplog.at_level(logging.INFO):
        logging.getLogger("x").info("token is %s", Secret("tok-123"))
    assert "tok-123" not in caplog.text
    assert "Secret(***)" in caplog.text


def test_wipe_empties_the_buffer():
    s = Secret("tok-123")
    s.wipe()
    assert not s and len(s) == 0 and s.reveal() == ""


def test_equality_is_by_value_and_constant_time_shaped():
    assert Secret("a") == Secret("a")
    assert Secret("a") != Secret("b")
    assert (Secret("a") == "a") is False
