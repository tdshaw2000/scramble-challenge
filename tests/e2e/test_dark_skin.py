"""The Dark skin: Minimal's layout with light text on dark backgrounds, readable everywhere."""

import pytest
from playwright.sync_api import expect

from tests.e2e.test_game import (
    advance,
    tom_and_amy,  # noqa: F401  (fixture)
)

# The colour each element is drawn in, and the nearest background behind it.
COLOURS = """(selector) => {
  const el = document.querySelector(selector);
  let back = el;
  while (back && getComputedStyle(back).backgroundColor === "rgba(0, 0, 0, 0)") {
    back = back.parentElement;
  }
  return {
    text: getComputedStyle(el).color,
    back: getComputedStyle(back || document.body).backgroundColor,
  };
}"""


def rgb(css):
    return [int(float(part)) for part in css[css.index("(") + 1 : -1].split(",")[:3]]


def luminance(css):
    def channel(value):
        value /= 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in rgb(css))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def dark_skin(page):
    page.context.add_cookies([{"name": "scramble_skin", "value": "dark", "url": page.url}])
    page.reload()
    expect(page.locator('link[rel="stylesheet"]')).to_have_attribute(
        "href", "/static/themes/dark/theme.css"
    )


def assert_readable(page, selector):
    colours = page.evaluate(COLOURS, selector)
    assert contrast(colours["text"], colours["back"]) >= 4.5, (selector, colours)
    return colours


def assert_dark_and_readable(page, selector):
    colours = assert_readable(page, selector)
    assert luminance(colours["back"]) < 0.05, (selector, colours)


def test_the_landing_page_is_dark(new_player):
    tom = new_player()
    tom.goto("/")
    dark_skin(tom)

    for selector in ("body", ".site-title", ".card-title", ".field-label", ".field-input"):
        assert_dark_and_readable(tom, selector)
    # The main button is a coloured fill, so it only has to be readable.
    assert_readable(tom, ".button-primary")


def test_the_round_is_dark_from_scramble_to_results(tom_and_amy):  # noqa: F811
    tom, amy, _ = tom_and_amy
    dark_skin(amy)
    amy.evaluate("window.__fakeNow = 1000000")  # the reload brought back the real clock
    tom.get_by_role("button", name="Start round").click()
    expect(amy.get_by_role("button", name="Start inspection")).to_be_visible()
    for selector in (".scramble-text", "#show-time"):
        assert_dark_and_readable(amy, selector)

    amy.get_by_role("button", name="Start inspection").click()
    assert_dark_and_readable(amy, "#countdown")
    amy.locator("#overlay").click()
    advance(amy, 9870)
    assert_dark_and_readable(amy, "#overlay .solving")
    amy.locator("#overlay").click()

    expect(amy.locator("#result-list")).to_contain_text("Amy")
    for selector in ("#result-list .name", "#result-list .time", ".penalty"):
        assert_dark_and_readable(amy, selector)


@pytest.mark.parametrize("selector", [".skin-menu", ".skin-option"])
def test_the_skin_menu_is_dark_too(new_player, selector):
    tom = new_player()
    tom.goto("/")
    dark_skin(tom)
    tom.get_by_label("Change skin").click()
    expect(tom.get_by_role("button", name="Dark")).to_be_visible()

    assert_dark_and_readable(tom, selector)
