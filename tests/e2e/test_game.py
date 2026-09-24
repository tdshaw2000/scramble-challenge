"""The screens from SPEC.md, driven in real browsers, one phone-sized window per player."""

import re

import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import control


def start_challenge(page, name="Tom"):
    page.goto("/")
    page.get_by_label("Your name").fill(name)
    page.get_by_role("button", name="Start new challenge").click()
    expect(page.locator("#players")).to_contain_text(name)
    return page.get_by_label("Share link").input_value()


def join(page, link, name):
    page.goto(link)
    page.get_by_label("Your name").fill(name)
    page.get_by_role("button", name="Join").click()
    expect(page.locator("#players")).to_contain_text(name)


@pytest.fixture
def tom_and_amy(new_player):
    tom, amy = new_player(), new_player()
    for page in (tom, amy):
        page.clock.install()
    link = start_challenge(tom)
    join(amy, link, "Amy")
    return tom, amy, link


def solve(page, ms):
    page.get_by_role("button", name="Start inspection").click()
    page.locator("#overlay").click()  # start solving
    page.clock.run_for(ms)
    page.locator("#overlay").click()  # stop


def leaderboard(page):
    return [row.inner_text().split("\n") for row in page.locator("#leaderboard li").all()]


def test_copy_link_button_copies_the_share_link(new_player):
    tom = new_player()
    tom.context.grant_permissions(["clipboard-read", "clipboard-write"])
    link = start_challenge(tom)

    tom.get_by_role("button", name="Copy link").click()

    expect(tom.get_by_role("button", name="Copied!")).to_be_visible()
    assert tom.evaluate("navigator.clipboard.readText()") == link


def test_friend_joins_by_link_and_both_lists_update(new_player):
    tom, amy = new_player(), new_player()
    link = start_challenge(tom)

    amy.goto(link)
    expect(amy.get_by_role("button", name="Join")).to_be_visible()
    join(amy, link, "Amy")

    expect(tom.locator("#players")).to_contain_text("Amy")
    expect(amy.locator("#players")).to_contain_text("Tom")
    expect(amy.get_by_text("Waiting for the challenge owner to start a round")).to_be_visible()
    expect(amy.get_by_role("button", name="Start round")).to_be_hidden()
    expect(amy.get_by_label("Share link")).to_be_hidden()


def test_starting_a_round_reveals_the_same_scramble_to_everyone(tom_and_amy):
    tom, amy, _ = tom_and_amy

    tom.get_by_role("button", name="Start round").click()

    for page in (tom, amy):
        expect(page.get_by_role("heading", name="Round 1")).to_be_visible()
        expect(page.locator("#scramble-text")).to_have_text(re.compile(r"R U R' U' \d+"))
        expect(page.get_by_role("button", name="Start inspection")).to_be_visible()
        expect(page.get_by_role("img", name="Scramble diagram")).to_be_visible()
    assert tom.locator("#scramble-text").inner_text() == amy.locator("#scramble-text").inner_text()


def test_inspection_counts_down_from_15_on_a_blank_screen(tom_and_amy):
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()

    amy.get_by_role("button", name="Start inspection").click()

    expect(amy.locator("#countdown")).to_have_text("15")
    expect(amy.locator("#scramble-text")).to_be_hidden()
    amy.clock.run_for(3000)
    expect(amy.locator("#countdown")).to_have_text("12")
    amy.clock.run_for(20000)
    expect(amy.locator("#countdown")).to_have_text("0")


def test_solving_shows_no_running_time_and_stopping_posts_it(tom_and_amy):
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    amy.get_by_role("button", name="Start inspection").click()

    amy.locator("#overlay").click()
    expect(amy.get_by_text("Solving")).to_be_visible()
    amy.clock.run_for(9870)
    expect(amy.locator("#overlay")).not_to_contain_text(re.compile(r"\d"))
    amy.locator("#overlay").click()

    for page in (tom, amy):
        expect(page.locator("#leaderboard")).to_contain_text("Amy")
        assert leaderboard(page) == [["1st", "Amy", "9.87"]]


def test_ties_share_a_position_and_the_round_ends_when_everyone_is_done(tom_and_amy):
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()

    solve(amy, 10_000)
    solve(tom, 10_000)

    for page in (tom, amy):
        expect(page.get_by_role("heading", name="Round 1 results")).to_be_visible()
        assert leaderboard(page) == [["1st", "Amy", "10.00"], ["1st", "Tom", "10.00"]]
    expect(tom.get_by_role("button", name="Start round")).to_be_visible()
    expect(tom.get_by_label("Puzzle")).to_have_value("333")


def test_only_the_owner_can_end_a_round_early_and_unfinished_players_get_dnf(tom_and_amy):
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    solve(tom, 7_500)

    expect(amy.get_by_role("button", name="End round")).to_be_hidden()
    tom.get_by_role("button", name="End round").click()

    for page in (tom, amy):
        expect(page.get_by_role("heading", name="Round 1 results")).to_be_visible()
        assert leaderboard(page) == [["1st", "Tom", "7.50"], ["2nd", "Amy", "DNF"]]
    expect(tom.get_by_role("button", name="End round")).to_be_hidden()


def test_joining_mid_round_gets_the_scramble_straight_away(tom_and_amy, new_player):
    tom, _, link = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    bob = new_player()

    join(bob, link, "Bob")

    expect(bob.get_by_role("button", name="Start inspection")).to_be_visible()


def test_everyone_is_told_when_the_owner_leaves_for_good(tom_and_amy, live_server):
    tom, amy, _ = tom_and_amy

    tom.close()
    expect(amy.locator("#players")).to_contain_text("Tom (away)")
    control(live_server, "advance-clock", seconds=30)
    control(live_server, "end-abandoned")

    expect(amy.get_by_text("This challenge has ended")).to_be_visible()


def test_times_over_a_minute_show_minutes(new_player):
    page = new_player()
    start_challenge(page)

    assert page.evaluate("ScrambleChallenge.formatTime(62350)") == "1:02.35"
    assert page.evaluate("ScrambleChallenge.formatTime(9870)") == "9.87"
    assert page.evaluate("ScrambleChallenge.formatTime(null)") == "DNF"
