"""The DOS skin draws everything in the IBM VGA 8x16 text-mode font, at sizes that are whole
multiples of its 16px cell so the bitmap letters stay sharp."""

from playwright.sync_api import expect

from tests.e2e.test_game import start_challenge


def computed(page, selector, prop):
    return page.eval_on_selector(selector, f"el => getComputedStyle(el).{prop}")


def first_font(page, selector):
    return computed(page, selector, "fontFamily").split(",")[0].strip().strip('"')


def test_everything_uses_the_ibm_vga_font_at_sharp_sizes(new_player, live_server):
    tom = new_player()
    tom.context.add_cookies([{"name": "scramble_skin", "value": "dos", "url": live_server}])
    start_challenge(tom)
    tom.evaluate("document.fonts.ready")

    assert tom.evaluate(
        "[...document.fonts].some(f => f.family === 'IBM VGA' && f.status === 'loaded')"
    )
    tom.get_by_role("button", name="Start round").click()
    expect(tom.locator(".scramble-text")).to_be_visible()

    for selector in (
        "body",
        ".site-title-letter",
        ".card-title",
        ".button-primary",
        ".scramble-text",
        ".countdown",
        ".finished",
    ):
        assert first_font(tom, selector) == "IBM VGA", selector
        size = float(computed(tom, selector, "fontSize").removesuffix("px"))
        assert size % 8 == 0, f"{selector} is {size}px"
