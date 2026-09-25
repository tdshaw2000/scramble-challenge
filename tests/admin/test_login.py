from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

import pytest

from app import create_app
from tests.admin.conftest import PASSWORD


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"ADMIN_PASSWORD_HASH": "x"},  # no secret key to sign the login cookie with
        {"SECRET_KEY": "x"},  # no password set
    ],
)
def test_admin_area_does_not_exist_until_a_password_and_secret_key_are_set(overrides):
    client = create_app("testing", **overrides).test_client()

    assert client.get("/admin").status_code == 404
    assert client.get("/admin/login").status_code == 404
    assert client.post("/admin/login", data={"password": PASSWORD}).status_code == 404


def test_admin_pages_send_visitors_to_the_login_page(client):
    response = client.get("/admin")

    assert response.status_code == 302
    assert response.headers["Location"] == "/admin/login"


def test_login_page_asks_for_the_password(client):
    response = client.get("/admin/login")

    assert response.status_code == 200
    assert b'type="password"' in response.data
    assert b'name="password"' in response.data


def test_the_right_password_logs_in_and_goes_to_the_admin_home(client):
    response = client.post("/admin/login", data={"password": PASSWORD})

    assert response.status_code == 302
    assert response.headers["Location"] == "/admin"
    assert client.get("/admin").status_code == 200


def test_a_wrong_password_is_refused(client):
    response = client.post("/admin/login", data={"password": "wrong"})

    assert response.status_code == 401
    assert b"Wrong password" in response.data
    assert client.get("/admin").status_code == 302


def test_a_missing_password_is_refused(client):
    assert client.post("/admin/login").status_code == 401


def test_login_cookie_is_hidden_from_scripts_and_lasts_a_month(client):
    response = client.post("/admin/login", data={"password": PASSWORD})

    set_cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie
    expires = parsedate_to_datetime(set_cookie.split("Expires=")[1].split(";")[0])
    assert abs(expires - (datetime.now(UTC) + timedelta(days=30))) < timedelta(minutes=1)


def test_login_cookie_is_https_only_in_production(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")

    assert create_app("production").config["SESSION_COOKIE_SECURE"] is True


def test_production_reads_the_password_hash_and_secret_key_from_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "the-hash")
    monkeypatch.setenv("SECRET_KEY", "the-key")

    config = create_app("production").config
    assert config["ADMIN_PASSWORD_HASH"] == "the-hash"
    assert config["SECRET_KEY"] == "the-key"


def test_production_leaves_the_admin_area_off_when_the_environment_has_no_password(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.delenv("ADMIN_PASSWORD_HASH", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    config = create_app("production").config
    assert not config["ADMIN_PASSWORD_HASH"]
    assert not config["SECRET_KEY"]


def test_logging_out_ends_the_admin_session(admin):
    response = admin.post("/admin/logout")

    assert response.status_code == 302
    assert response.headers["Location"] == "/admin/login"
    assert admin.get("/admin").status_code == 302


def test_logging_in_does_not_change_the_players_device_cookie(admin):
    from app.routes import COOKIE_NAME

    assert admin.get_cookie(COOKIE_NAME) is None
