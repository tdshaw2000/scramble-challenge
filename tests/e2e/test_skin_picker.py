"""The gear menu in a real browser: switching skin in place, and staying out of the solve."""

import pytest
from playwright.sync_api import expect

from tests.e2e.test_game import start_challenge


def stylesheet(page):
    return page.locator('link[rel="stylesheet"]').get_attribute("href")


def test_choosing_a_skin_switches_it_without_reloading_and_remembers_it(new_player):
    tom = new_player()
    start_challenge(tom)
    tom.evaluate("window.__sameLoad = true")

    tom.get_by_label("Change skin").click()
    tom.get_by_role("button", name="Plain").click()

    expect(tom.locator('link[rel="stylesheet"]')).to_have_attribute(
        "href", "/static/themes/plain/theme.css"
    )
    assert tom.evaluate("window.__sameLoad") is True
    expect(tom.get_by_role("button", name="Plain")).to_have_attribute("aria-current", "true")
    expect(tom.get_by_role("button", name="Mario 64")).not_to_have_attribute("aria-current", "true")
    expect(tom.locator(".skin-picker")).not_to_have_attribute("open", "")

    tom.reload()

    assert stylesheet(tom) == "/static/themes/plain/theme.css"


def test_each_player_keeps_their_own_skin(new_player):
    tom, amy = new_player(), new_player()
    tom.goto("/")
    amy.goto("/")

    tom.get_by_label("Change skin").click()
    tom.get_by_role("button", name="Plain").click()
    expect(tom.locator('link[rel="stylesheet"]')).to_have_attribute(
        "href", "/static/themes/plain/theme.css"
    )

    amy.reload()
    assert stylesheet(amy) == "/static/themes/mario64/theme.css"


def gear_is_covered(page):
    """True when something else is on top of the gear, so a tap can't reach it."""
    return page.evaluate(
        """() => {
          const gear = document.querySelector(".skin-picker-toggle");
          const box = gear.getBoundingClientRect();
          const top = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
          return !gear.contains(top);
        }"""
    )


@pytest.mark.parametrize("skin", ["mario64", "plain"])
def test_the_timer_screen_covers_the_gear(new_player, live_server, skin):
    tom = new_player()
    tom.context.add_cookies([{"name": "scramble_skin", "value": skin, "url": live_server}])
    start_challenge(tom)
    assert stylesheet(tom) == f"/static/themes/{skin}/theme.css"
    assert not gear_is_covered(tom)

    tom.get_by_role("button", name="Start round").click()
    tom.get_by_role("button", name="Start inspection").click()

    expect(tom.locator("#overlay")).to_be_visible()
    assert gear_is_covered(tom)


def test_tapping_outside_the_menu_closes_it(new_player):
    tom = new_player()
    tom.goto("/")

    tom.get_by_label("Change skin").click()
    expect(tom.get_by_role("button", name="Plain")).to_be_visible()

    tom.mouse.click(20, 700)

    expect(tom.get_by_role("button", name="Plain")).to_be_hidden()
    assert stylesheet(tom) == "/static/themes/mario64/theme.css"
