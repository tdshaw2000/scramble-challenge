"""Each password check costs real CPU (scrypt), and production has one worker, so wrong
guesses are limited per visitor: that stops both guessing and stalling the game."""

import pytest
from flask import request

from app import create_app
from tests.admin.conftest import PASSWORD


def attempt(client, password="wrong", ip="1.1.1.1"):
    return client.post(
        "/admin/login", data={"password": password}, environ_base={"REMOTE_ADDR": ip}
    )


@pytest.fixture
def checks(monkeypatch):
    """Counts how many times the password is actually hashed and checked."""
    import app.admin

    calls = []
    real = app.admin.check_password_hash

    def counting(*args):
        calls.append(args)
        return real(*args)

    monkeypatch.setattr(app.admin, "check_password_hash", counting)
    return calls


def test_five_wrong_passwords_are_allowed(client):
    assert [attempt(client).status_code for _ in range(5)] == [401] * 5


def test_after_five_wrong_passwords_that_visitor_is_refused_without_checking(client, checks):
    for _ in range(5):
        attempt(client)

    response = attempt(client, PASSWORD)

    assert response.status_code == 429
    assert b"Too many attempts" in response.data
    assert len(checks) == 5


def test_other_visitors_can_still_log_in(client):
    for _ in range(5):
        attempt(client, ip="1.1.1.1")

    assert attempt(client, PASSWORD, ip="2.2.2.2").status_code == 302


def test_the_limit_lifts_after_fifteen_minutes(client, clock):
    for _ in range(5):
        attempt(client)
    clock.advance(minutes=14, seconds=59)
    assert attempt(client, PASSWORD).status_code == 429

    clock.advance(seconds=1)

    assert attempt(client, PASSWORD).status_code == 302


def test_logging_in_clears_earlier_wrong_guesses(client):
    for _ in range(4):
        attempt(client)
    attempt(client, PASSWORD)

    assert [attempt(client).status_code for _ in range(5)] == [401] * 5


def test_behind_the_proxy_visitors_are_told_apart_by_their_forwarded_address():
    # Every request reaches the app from Caddy's address, so without this one visitor's
    # wrong guesses would lock everyone out.
    app = create_app("testing", TRUSTED_PROXIES=1)
    seen = []

    @app.get("/whoami")
    def whoami():
        seen.append(request.remote_addr)
        return ""

    app.test_client().get(
        "/whoami",
        environ_base={"REMOTE_ADDR": "172.18.0.5"},
        headers={"X-Forwarded-For": "9.9.9.9"},
    )

    assert seen == ["9.9.9.9"]
