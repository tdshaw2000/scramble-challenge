"""The look lives in one swappable theme folder; markup and scripts carry no styling."""

import re
from pathlib import Path

import pytest

from app import create_app

APP = Path(__file__).resolve().parents[2] / "app"


def stylesheet_links(html: bytes) -> list[str]:
    return re.findall(r'<link rel="stylesheet" href="([^"]+)"', html.decode())


def test_pages_use_the_mario64_theme_by_default(client):
    assert stylesheet_links(client.get("/").data) == ["/static/themes/mario64/theme.css"]


def test_the_theme_is_a_config_setting():
    app = create_app("testing", THEME="plain")

    assert stylesheet_links(app.test_client().get("/").data) == ["/static/themes/plain/theme.css"]


THEMES = ["mario64", "plain", "monkeyisland2"]


@pytest.mark.parametrize("theme", THEMES)
def test_each_theme_is_a_single_css_file(theme):
    assert (APP / "static" / "themes" / theme / "theme.css").is_file()


@pytest.mark.parametrize("theme", THEMES)
def test_bundled_fonts_ship_with_their_licence(theme):
    fonts = APP / "static" / "themes" / theme / "fonts"
    for font in fonts.glob("*.woff2"):
        assert (fonts / f"LICENSE-{font.stem}.txt").is_file(), font.name


def test_templates_contain_no_styling():
    for template in (APP / "templates").rglob("*.html"):
        text = template.read_text()
        assert "<style" not in text, template.name
        assert "style=" not in text, template.name


def test_scripts_never_set_styles_directly():
    for script in (APP / "static").glob("*.js"):
        assert ".style" not in script.read_text(), script.name
