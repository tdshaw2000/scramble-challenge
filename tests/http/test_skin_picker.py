"""Each player can pick their own skin from the gear menu; it is remembered in a cookie."""

import re
from pathlib import Path

import pytest

from app import create_app
from app.routes import SKIN_COOKIE_NAME
from tests.http.test_theme import stylesheet_links

APP = Path(__file__).resolve().parents[2] / "app"


def skin_cookie(client):
    found = client.get_cookie(SKIN_COOKIE_NAME)
    return found.value if found else None


def skin_options(html: bytes) -> list[tuple[str, str, bool]]:
    """(value, label, is_current) for each button in the skin menu."""
    return [
        (value, label.strip(), bool(current))
        for value, current, label in re.findall(
            r'<button[^>]*name="skin" value="([^"]+)"( aria-current="true")?[^>]*>([^<]+)</button>',
            html.decode(),
        )
    ]


def test_every_listed_skin_has_a_theme_folder(app):
    assert list(app.config["THEMES"]) == ["mario64", "plain", "monkeyisland2"]
    for theme in app.config["THEMES"]:
        assert (APP / "static" / "themes" / theme / "theme.css").is_file()


@pytest.mark.parametrize("theme", ["mario64", "plain", "monkeyisland2"])
def test_every_theme_styles_the_skin_picker(theme):
    css = (APP / "static" / "themes" / theme / "theme.css").read_text()

    for selector in (".skin-picker", ".skin-picker-toggle", ".skin-menu", ".skin-option"):
        assert selector in css, selector


def test_a_chosen_skin_is_used_for_the_page(client):
    client.set_cookie(SKIN_COOKIE_NAME, "plain")

    assert stylesheet_links(client.get("/").data) == ["/static/themes/plain/theme.css"]


def test_an_unknown_skin_in_the_cookie_falls_back_to_the_server_setting(client):
    client.set_cookie(SKIN_COOKIE_NAME, "../../secrets")

    assert stylesheet_links(client.get("/").data) == ["/static/themes/mario64/theme.css"]


def test_the_server_setting_is_the_default_skin():
    client = create_app("testing", THEME="plain").test_client()

    assert stylesheet_links(client.get("/").data) == ["/static/themes/plain/theme.css"]


def test_the_page_offers_each_skin_and_ticks_the_current_one(client):
    assert skin_options(client.get("/").data) == [
        ("mario64", "Mario 64", True),
        ("plain", "Minimal", False),
        ("monkeyisland2", "Monkey", False),
    ]


def test_the_tick_follows_the_chosen_skin(client):
    client.set_cookie(SKIN_COOKIE_NAME, "plain")

    assert skin_options(client.get("/").data) == [
        ("mario64", "Mario 64", False),
        ("plain", "Minimal", True),
        ("monkeyisland2", "Monkey", False),
    ]


def test_the_gear_is_on_challenge_pages_too(client, challenge):
    assert len(skin_options(client.get(f"/c/{challenge.slug}").data)) == 3


def test_the_skin_menu_comes_back_to_the_same_page(client, challenge):
    html = client.get(f"/c/{challenge.slug}").get_data(as_text=True)

    assert f'name="next" value="/c/{challenge.slug}"' in html


def test_choosing_a_skin_remembers_it_and_goes_back(client):
    response = client.post("/skin", data={"skin": "plain", "next": "/c/abc"})

    assert response.status_code == 303
    assert response.headers["Location"] == "/c/abc"
    assert skin_cookie(client) == "plain"


def test_skin_cookie_is_long_lived_and_hidden_from_scripts(client):
    response = client.post("/skin", data={"skin": "plain", "next": "/"})

    set_cookie = next(
        h for h in response.headers.getlist("Set-Cookie") if h.startswith(SKIN_COOKIE_NAME)
    )
    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie
    assert "Max-Age=" in set_cookie


def test_an_unknown_skin_is_refused(client):
    response = client.post("/skin", data={"skin": "neon", "next": "/"})

    assert response.status_code == 400
    assert skin_cookie(client) is None


@pytest.mark.parametrize(
    "next_url",
    [
        "",
        "https://evil.example/",
        "//evil.example/",
        "/\\evil.example",
        "c/abc",
        # Browsers and Werkzeug drop tabs and newlines, which would leave //evil.example.
        "/\t/evil.example",
        "/\n/evil.example",
        "/\r/evil.example",
        "/ /evil.example",
    ],
)
def test_choosing_a_skin_only_goes_back_to_a_page_on_this_site(client, next_url):
    response = client.post("/skin", data={"skin": "plain", "next": next_url})

    assert response.headers["Location"] == "/"


def skin_next(response) -> str:
    return re.search(r'name="next" value="([^"]*)"', response.get_data(as_text=True)).group(1)


def test_the_default_skin_is_one_of_the_listed_skins(app):
    assert app.config["THEME"] in app.config["THEMES"]


def test_after_a_failed_form_the_skin_menu_goes_back_to_the_page_the_form_was_on(client, challenge):
    response = client.post(
        f"/c/{challenge.slug}/join",
        data={"display_name": "   "},
        headers={"Referer": f"http://localhost/c/{challenge.slug}"},
    )

    assert response.status_code == 400
    assert skin_next(response) == f"/c/{challenge.slug}"


@pytest.mark.parametrize("referer", [None, "https://evil.example/c/abc"])
def test_after_a_failed_form_with_no_usable_referer_the_skin_menu_goes_home(client, referer):
    headers = {"Referer": referer} if referer else {}

    response = client.post("/challenges", data={"display_name": "   "}, headers=headers)

    assert response.status_code == 400
    assert skin_next(response) == "/"
