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


THEMES = ["mario64", "plain", "neon80s", "monkeyisland2", "dos", "dark"]


@pytest.mark.parametrize("theme", THEMES)
def test_each_theme_is_a_single_css_file(theme):
    assert (APP / "static" / "themes" / theme / "theme.css").is_file()


def test_every_bundled_font_has_its_licence_beside_it():
    themes = APP / "static" / "themes"
    fonts = [f for ext in ("woff2", "woff", "ttf", "otf") for f in themes.rglob(f"*.{ext}")]
    assert fonts
    for font in fonts:
        assert (font.parent / f"LICENSE-{font.stem}.txt").is_file(), font.name


@pytest.mark.parametrize("theme", THEMES)
def test_every_file_a_theme_points_to_exists(theme):
    folder = APP / "static" / "themes" / theme
    for url in re.findall(r'url\("([^"]+)"\)', (folder / "theme.css").read_text()):
        assert (folder / url).is_file(), url


def test_templates_contain_no_styling():
    for template in (APP / "templates").rglob("*.html"):
        text = template.read_text()
        assert "<style" not in text, template.name
        assert "style=" not in text, template.name


def test_scripts_never_set_styles_directly():
    for script in (APP / "static").glob("*.js"):
        assert ".style" not in script.read_text(), script.name


@pytest.mark.parametrize("theme", THEMES)
def test_every_theme_styles_the_share_buttons_and_qr_popup(theme):
    css = (APP / "static" / "themes" / theme / "theme.css").read_text()

    for selector in (".share-label", ".qr-dialog", ".qr-dialog::backdrop", ".qr-image"):
        assert selector in css, selector


def css_rule(css: str, selector: str) -> str:
    """The body of the first rule whose selector list is exactly `selector`."""
    match = re.search(rf"(?m)^{re.escape(selector)}\s*\{{([^}}]*)\}}", css)
    assert match, selector
    return match.group(1)


@pytest.mark.parametrize("theme", THEMES)
def test_pressing_the_timer_screen_never_selects_text_on_any_phone(theme):
    # Safari (every iPhone browser) still only understands the -webkit- spelling, and the
    # callout is the iPhone's long-press copy menu.
    rule = css_rule((APP / "static" / "themes" / theme / "theme.css").read_text(), ".overlay")

    for declaration in (
        "-webkit-user-select: none",
        "user-select: none",
        "-webkit-touch-callout: none",
    ):
        assert re.search(rf"(?<![-\w]){declaration};", rule), declaration


@pytest.mark.parametrize("theme", THEMES)
def test_every_theme_styles_the_penalty_toggles(theme):
    css = (APP / "static" / "themes" / theme / "theme.css").read_text()

    for selector in (".penalties", '.penalty[aria-pressed="true"]', ".penalty:disabled"):
        assert selector in css, selector


@pytest.mark.parametrize("theme", THEMES)
def test_every_theme_styles_the_show_time_toggle_and_the_running_time(theme):
    css = (APP / "static" / "themes" / theme / "theme.css").read_text()

    for selector in (".show-time", '.show-time[aria-pressed="true"]', ".running-time"):
        assert selector in css, selector
