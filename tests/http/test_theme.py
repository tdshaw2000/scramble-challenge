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


@pytest.mark.parametrize("theme", ["mario64", "plain", "neon80s"])
def test_each_theme_is_a_single_css_file(theme):
    assert (APP / "static" / "themes" / theme / "theme.css").is_file()


def test_every_bundled_font_has_its_licence_beside_it():
    themes = APP / "static" / "themes"
    fonts = [f for ext in ("woff2", "woff", "ttf", "otf") for f in themes.rglob(f"*.{ext}")]
    assert fonts
    for font in fonts:
        assert (font.parent / f"LICENSE-{font.stem}.txt").is_file(), font.name


def test_templates_contain_no_styling():
    for template in (APP / "templates").rglob("*.html"):
        text = template.read_text()
        assert "<style" not in text, template.name
        assert "style=" not in text, template.name


def test_scripts_never_set_styles_directly():
    for script in (APP / "static").glob("*.js"):
        assert ".style" not in script.read_text(), script.name
