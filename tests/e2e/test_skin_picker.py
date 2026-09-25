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
    expect(tom.locator(".skin-picker")).not_to_have_attribute("open", "")
    # The menu is closed now, so look the options up by value rather than by role.
    expect(tom.locator('.skin-option[value="plain"]')).to_have_attribute("aria-current", "true")
    expect(tom.locator('.skin-option[value="mario64"]')).not_to_have_attribute(
        "aria-current", "true"
    )

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


@pytest.mark.parametrize("skin", ["mario64", "plain", "neon80s"])
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


def test_if_saving_in_place_fails_the_menu_falls_back_to_a_normal_form_post(new_player):
    tom = new_player()
    tom.goto("/")
    attempts = []

    def fail_the_first_try(route):
        attempts.append(route.request.post_data)
        if len(attempts) == 1:
            route.abort()
        else:
            route.continue_()

    tom.route("**/skin", fail_the_first_try)

    tom.get_by_label("Change skin").click()
    tom.get_by_role("button", name="Plain").click()

    expect(tom.locator('link[rel="stylesheet"]')).to_have_attribute(
        "href", "/static/themes/plain/theme.css"
    )
    assert len(attempts) == 2


def test_if_the_server_refuses_the_in_place_save_the_menu_falls_back_to_a_form_post(
    new_player,
):
    tom = new_player()
    tom.goto("/")
    attempts = []

    def refuse_the_first_try(route):
        attempts.append(route.request.post_data)
        if len(attempts) == 1:
            route.fulfill(status=500, body="oops")
        else:
            route.continue_()

    tom.route("**/skin", refuse_the_first_try)

    tom.get_by_label("Change skin").click()
    tom.get_by_role("button", name="Plain").click()

    expect(tom.locator('link[rel="stylesheet"]')).to_have_attribute(
        "href", "/static/themes/plain/theme.css"
    )
    assert len(attempts) == 2
