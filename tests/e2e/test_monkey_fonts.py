"""The Monkey skin uses one font, VT323, for words, moves and times (the owner's pick: Tiny5's
letters were too small to read, e.g. its lowercase e)."""

from playwright.sync_api import expect

from tests.e2e.test_game import start_challenge


def first_font(page, selector):
    family = page.eval_on_selector(selector, "el => getComputedStyle(el).fontFamily")
    return family.split(",")[0].strip().strip('"')


def test_everything_uses_vt323(new_player, live_server):
    tom = new_player()
    tom.context.add_cookies(
        [{"name": "scramble_skin", "value": "monkeyisland2", "url": live_server}]
    )
    start_challenge(tom)
    tom.evaluate("document.fonts.ready")

    for selector in ("body", ".card-title", ".button-primary", ".site-title-letter"):
        assert first_font(tom, selector) == "VT323", selector
    assert tom.evaluate(
        "[...document.fonts].some(f => f.family === 'VT323' && f.status === 'loaded')"
    )
    assert not tom.evaluate("[...document.fonts].some(f => f.family === 'Tiny5')")
    assert first_font(tom, ".share .button") == "VT323"

    tom.get_by_role("button", name="Start round").click()
    expect(tom.locator(".scramble-text")).to_be_visible()
    assert first_font(tom, ".scramble-text") == "VT323"
    assert first_font(tom, ".countdown") == "VT323"
    assert first_font(tom, ".finished") == "VT323"
