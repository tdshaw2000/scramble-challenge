"""The Monkey skin's fonts: a SCUMM-like pixel font for words, a clear one for moves and times."""

from playwright.sync_api import expect

from tests.e2e.test_game import start_challenge


def first_font(page, selector):
    family = page.eval_on_selector(selector, "el => getComputedStyle(el).fontFamily")
    return family.split(",")[0].strip().strip('"')


def test_words_use_tiny5_and_scrambles_and_times_stay_clear(new_player, live_server):
    tom = new_player()
    tom.context.add_cookies(
        [{"name": "scramble_skin", "value": "monkeyisland2", "url": live_server}]
    )
    start_challenge(tom)
    tom.evaluate("document.fonts.ready")

    for selector in ("body", ".card-title", ".button-primary", ".site-title-letter"):
        assert first_font(tom, selector) == "Tiny5", selector
    assert tom.evaluate("document.fonts.check('16px Tiny5')")

    tom.get_by_role("button", name="Start round").click()
    expect(tom.locator(".scramble-text")).to_be_visible()
    assert first_font(tom, ".scramble-text") == "VT323"
    assert first_font(tom, ".countdown") == "VT323"
    assert first_font(tom, ".finished") == "VT323"
