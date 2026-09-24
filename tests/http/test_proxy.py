"""In production the app sits behind Caddy, which terminates HTTPS. Share links must use
the public https address, but forwarded headers are only trusted when configured."""

import pytest

from app import create_app
from app.config import ProductionConfig
from app.extensions import db
from tests.fakes import FakeClock, FakeTNoodle

FORWARDED = {"X-Forwarded-Proto": "https", "X-Forwarded-Host": "scramble-challenge.duckdns.org"}


def share_link_page(app):
    app.extensions["tnoodle"] = FakeTNoodle()
    app.extensions["clock"] = FakeClock()
    with app.app_context():
        db.create_all()
        client = app.test_client()
        location = client.post("/challenges", data={"display_name": "Tom"}).headers["Location"]
        page = client.get(location, headers=FORWARDED).data.decode()
        db.session.remove()
        db.engine.dispose()
    return location, page


def test_behind_the_proxy_share_links_use_the_public_https_address():
    location, page = share_link_page(create_app("testing", TRUSTED_PROXIES=1))

    assert f"https://scramble-challenge.duckdns.org{location}" in page


def test_forwarded_headers_are_ignored_unless_a_proxy_is_trusted():
    location, page = share_link_page(create_app("testing"))

    assert f"http://localhost{location}" in page


@pytest.mark.parametrize(("value", "expected"), [(None, 0), ("1", 1)])
def test_production_reads_the_trusted_proxy_count_from_the_environment(
    monkeypatch, value, expected
):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    if value is None:
        monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
    else:
        monkeypatch.setenv("TRUSTED_PROXIES", value)

    assert ProductionConfig().TRUSTED_PROXIES == expected
