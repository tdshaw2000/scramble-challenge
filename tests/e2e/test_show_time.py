"""The Show time toggle under Start inspection: off by default (WCA style, no running
time), on shows the time ticking up while solving. The choice lives in a cookie."""

import re

import pytest
from playwright.sync_api import expect

from tests.e2e.test_game import (
    advance,
    leaderboard,
    solve,
    tom_and_amy,  # noqa: F401  (fixture)
)

SHOW_TIME = "#show-time"


def start_round(tom_and_amy):  # noqa: F811
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    expect(amy.get_by_role("button", name="Start inspection")).to_be_visible()
    return tom, amy


def show_time_cookie(page):
    found = [c["value"] for c in page.context.cookies() if c["name"] == "scramble_show_time"]
    return found[0] if found else None


def test_the_toggle_is_under_start_inspection_and_off_to_begin_with(tom_and_amy):  # noqa: F811
    _, amy = start_round(tom_and_amy)

    toggle = amy.locator(SHOW_TIME)
    expect(toggle).to_be_visible()
    expect(toggle).to_have_text("Show time: Off")
    expect(toggle).to_have_attribute("aria-pressed", "false")
    inspection = amy.get_by_role("button", name="Start inspection").bounding_box()
    assert toggle.bounding_box()["y"] > inspection["y"] + inspection["height"]


def test_turning_it_on_shows_the_time_running_while_solving(tom_and_amy):  # noqa: F811
    tom, amy = start_round(tom_and_amy)
    amy.locator(SHOW_TIME).click()
    expect(amy.locator(SHOW_TIME)).to_have_text("Show time: On")
    expect(amy.locator(SHOW_TIME)).to_have_attribute("aria-pressed", "true")

    amy.get_by_role("button", name="Start inspection").click()
    expect(amy.locator("#countdown")).to_have_text("15")
    expect(amy.locator("#running-time")).to_be_hidden()
    amy.locator("#overlay").click()
    advance(amy, 4560)
    expect(amy.locator("#running-time")).to_have_text("4.56")
    expect(amy.get_by_text("Solving")).to_be_hidden()
    advance(amy, 5310)
    expect(amy.locator("#running-time")).to_have_text("9.87")
    amy.locator("#overlay").click()

    for page in (tom, amy):
        expect(page.locator("#result-list")).to_contain_text("Amy")
        assert leaderboard(page) == [["1st", "Amy (0)", "9.87"]]


def test_the_running_time_leaves_out_an_inspection_plus_two_like_a_real_timer(tom_and_amy):  # noqa: F811
    _, amy = start_round(tom_and_amy)
    amy.locator(SHOW_TIME).click()

    amy.get_by_role("button", name="Start inspection").click()
    advance(amy, 15500)
    amy.locator("#overlay").click()
    advance(amy, 3000)

    expect(amy.locator("#running-time")).to_have_text("3.00")


def test_turning_it_off_again_hides_the_time(tom_and_amy):  # noqa: F811
    _, amy = start_round(tom_and_amy)
    amy.locator(SHOW_TIME).click()
    amy.locator(SHOW_TIME).click()
    expect(amy.locator(SHOW_TIME)).to_have_text("Show time: Off")

    amy.get_by_role("button", name="Start inspection").click()
    amy.locator("#overlay").click()
    advance(amy, 4560)

    expect(amy.get_by_text("Solving")).to_be_visible()
    expect(amy.locator("#overlay")).not_to_contain_text(re.compile(r"\d"))


def test_the_choice_is_remembered_in_a_cookie_for_next_time(tom_and_amy):  # noqa: F811
    _, amy, link = tom_and_amy
    assert show_time_cookie(amy) is None
    start_round(tom_and_amy)

    amy.locator(SHOW_TIME).click()
    expect(amy.locator(SHOW_TIME)).to_have_attribute("aria-pressed", "true")
    assert show_time_cookie(amy) == "on"

    later = amy.context.new_page()
    later.goto(link)
    expect(later.locator(SHOW_TIME)).to_have_attribute("aria-pressed", "true")
    expect(later.locator(SHOW_TIME)).to_have_text("Show time: On")

    amy.locator(SHOW_TIME).click()
    expect(amy.locator(SHOW_TIME)).to_have_attribute("aria-pressed", "false")
    assert show_time_cookie(amy) == "off"


def test_the_remembered_choice_lasts_a_year(tom_and_amy):  # noqa: F811
    _, amy = start_round(tom_and_amy)
    amy.locator(SHOW_TIME).click()
    expect(amy.locator(SHOW_TIME)).to_have_attribute("aria-pressed", "true")

    cookie = next(c for c in amy.context.cookies() if c["name"] == "scramble_show_time")
    now = amy.evaluate("Date.now() / 1000")
    assert cookie["expires"] - now > 360 * 24 * 60 * 60
    assert cookie["path"] == "/"


def test_a_solve_cut_short_by_end_round_leaves_no_running_time_in_the_next_round(tom_and_amy):  # noqa: F811
    tom, amy = start_round(tom_and_amy)
    amy.locator(SHOW_TIME).click()
    amy.get_by_role("button", name="Start inspection").click()
    amy.locator("#overlay").click()
    advance(amy, 2000)

    solve(tom, 7_500)  # the owner reaches the results, where End round is
    tom.get_by_role("button", name="End round").click()
    expect(amy.locator("#overlay")).to_be_hidden()
    tom.get_by_role("button", name="Start round").click()
    amy.get_by_role("button", name="Start inspection").click()
    advance(amy, 1000)

    expect(amy.locator("#countdown")).to_have_text("14")
    expect(amy.locator("#running-time")).to_be_hidden()


@pytest.mark.parametrize("skin", ["plain", "dos", "mario64", "monkeyisland2", "neon80s"])
def test_the_toggle_is_as_tall_as_start_inspection_in_every_skin(tom_and_amy, skin):  # noqa: F811
    _, amy = start_round(tom_and_amy)
    amy.context.add_cookies([{"name": "scramble_skin", "value": skin, "url": amy.url}])
    amy.reload()
    expect(amy.get_by_role("button", name="Start inspection")).to_be_visible()

    start = amy.get_by_role("button", name="Start inspection").bounding_box()
    toggle = amy.locator(SHOW_TIME).bounding_box()
    assert toggle["height"] == start["height"]
