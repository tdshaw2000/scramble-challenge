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
    # The player list is drawn by the server, so it shows before challenge.js has run.
    # Start round is enabled only once the script has run and the socket has joined.
    expect(page.get_by_role("button", name="Start round")).to_be_enabled()
    return page.get_by_label("Share this link with the other players").input_value()


def join(page, link, name):
    page.goto(link)
    page.get_by_label("Your name").fill(name)
    page.get_by_role("button", name="Join").click()
    expect(page.locator("#players")).to_contain_text(name)


# Browser tests control time through performance.now(), which the page uses for the
# countdown and the solve timer. (Playwright's clock would also freeze Socket.IO's timers.)
FAKE_NOW = """
  const realNow = performance.now.bind(performance);
  window.__fakeNow = null;
  performance.now = () => (window.__fakeNow === null ? realNow() : window.__fakeNow);
"""


def set_now(page, ms):
    page.evaluate(f"window.__fakeNow = {ms}")


def advance(page, ms):
    page.evaluate(f"window.__fakeNow += {ms}")
    page.wait_for_timeout(250)  # let the page's 100 ms ticker catch up


@pytest.fixture
def tom_and_amy(new_player):
    tom, amy = new_player(), new_player()
    for page in (tom, amy):
        page.add_init_script(FAKE_NOW)
    link = start_challenge(tom)
    join(amy, link, "Amy")
    for page in (tom, amy):
        set_now(page, 1_000_000)
    return tom, amy, link


def solve(page, ms):
    page.get_by_role("button", name="Start inspection").click()
    page.locator("#overlay").click()  # start solving
    advance(page, ms)
    page.locator("#overlay").click()  # stop


def leaderboard(page):
    return [
        [row.locator(f".{part}").inner_text() for part in ("position", "name", "time")]
        for row in page.locator("#leaderboard li").all()
    ]


# Phones share through the Web Share API (navigator.share). The tests replace it with a
# recorder, or remove it to act like a desktop browser without sharing.
RECORD_SHARES = """
  window.__shared = [];
  Object.defineProperty(navigator, "share", {
    configurable: true,
    value: (data) => { window.__shared.push(data); return Promise.resolve(); },
  });
"""

CANCEL_SHARES = """
  Object.defineProperty(navigator, "share", {
    configurable: true,
    value: () => {
      window.__shareCalled = true;
      return Promise.reject(new DOMException("Share canceled", "AbortError"));
    },
  });
"""

NO_SHARING = """
  delete Navigator.prototype.share;
  delete navigator.share;
"""


def test_share_button_opens_the_phones_share_sheet_with_the_link(new_player):
    tom = new_player()
    tom.add_init_script(RECORD_SHARES)
    link = start_challenge(tom)

    tom.get_by_role("button", name="Share", exact=True).click()

    tom.wait_for_function("window.__shared.length === 1")
    shared = tom.evaluate("window.__shared[0]")
    assert shared["url"] == link
    assert shared["title"] == "Scramble Challenge"
    assert shared["text"] == "Join my Scramble Challenge"


def settle(page):
    """Give the click handler's promises time to finish."""
    page.evaluate("new Promise((resolve) => setTimeout(resolve, 200))")


def test_cancelling_the_share_sheet_changes_nothing(new_player):
    tom = new_player()
    tom.add_init_script(CANCEL_SHARES)
    tom.context.grant_permissions(["clipboard-read", "clipboard-write"])
    start_challenge(tom)
    tom.evaluate("navigator.clipboard.writeText('untouched')")

    tom.get_by_role("button", name="Share", exact=True).click()
    tom.wait_for_function("window.__shareCalled === true")
    settle(tom)

    expect(tom.get_by_role("button", name="Share", exact=True)).to_be_visible()
    expect(tom.locator("#message")).to_be_hidden()
    assert tom.evaluate("navigator.clipboard.readText()") == "untouched"


FAIL_SHARES = """
  Object.defineProperty(navigator, "share", {
    configurable: true,
    value: () => Promise.reject(new DOMException("Not allowed", "NotAllowedError")),
  });
"""


def test_a_failed_share_copies_the_link_instead(new_player):
    tom = new_player()
    tom.add_init_script(FAIL_SHARES)
    tom.context.grant_permissions(["clipboard-read", "clipboard-write"])
    link = start_challenge(tom)

    tom.get_by_role("button", name="Share", exact=True).click()

    expect(tom.get_by_role("button", name="Copied!")).to_be_visible()
    assert tom.evaluate("navigator.clipboard.readText()") == link


# Safari and Firefox refuse clipboard writes once a failed share has used up the tap,
# and plain-http pages have no clipboard at all.
NO_SHARING_OR_COPYING = (
    NO_SHARING
    + """
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: () => Promise.reject(new DOMException("Not allowed", "NotAllowedError")) },
  });
"""
)


def test_when_copying_is_blocked_the_link_is_selected_for_copying_by_hand(new_player):
    tom = new_player()
    tom.add_init_script(NO_SHARING_OR_COPYING)
    link = start_challenge(tom)

    tom.get_by_role("button", name="Share", exact=True).click()

    expect(tom.locator("#message")).to_have_text("Copy the link above to share it.")
    selected = tom.evaluate(
        "(() => { const box = document.getElementById('share-link');"
        " return document.activeElement === box"
        " ? box.value.slice(box.selectionStart, box.selectionEnd) : null; })()"
    )
    assert selected == link


def test_share_button_copies_the_link_where_sharing_is_unsupported(new_player):
    tom = new_player()
    tom.add_init_script(NO_SHARING)
    tom.context.grant_permissions(["clipboard-read", "clipboard-write"])
    link = start_challenge(tom)

    tom.get_by_role("button", name="Share", exact=True).click()

    expect(tom.get_by_role("button", name="Copied!")).to_be_visible()
    assert tom.evaluate("navigator.clipboard.readText()") == link
    expect(tom.get_by_role("button", name="Share", exact=True)).to_be_visible(timeout=4000)


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
    expect(amy.get_by_label("Share this link with the other players")).to_be_hidden()


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
    advance(amy, 3000)
    expect(amy.locator("#countdown")).to_have_text("12")
    advance(amy, 11500)
    expect(amy.locator("#countdown")).to_have_text("1")


def test_letting_the_countdown_reach_zero_is_a_dnf(tom_and_amy):
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    amy.get_by_role("button", name="Start inspection").click()

    advance(amy, 15_000)

    expect(amy.locator("#overlay")).to_be_hidden()
    expect(amy.locator("#message")).to_have_text("Inspection ran out: DNF.")
    for page in (tom, amy):
        expect(page.locator("#leaderboard")).to_contain_text("Amy")
        assert leaderboard(page) == [["1st", "Amy (0)", "DNF"]]


def test_solving_shows_no_running_time_and_stopping_posts_it(tom_and_amy):
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    amy.get_by_role("button", name="Start inspection").click()

    amy.locator("#overlay").click()
    expect(amy.get_by_text("Solving")).to_be_visible()
    advance(amy, 9870)
    expect(amy.locator("#overlay")).not_to_contain_text(re.compile(r"\d"))
    amy.locator("#overlay").click()

    for page in (tom, amy):
        expect(page.locator("#leaderboard")).to_contain_text("Amy")
        assert leaderboard(page) == [["1st", "Amy (0)", "9.87"]]


def test_ties_share_a_position_and_the_round_ends_when_everyone_is_done(tom_and_amy):
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()

    solve(amy, 10_000)
    solve(tom, 10_000)

    for page in (tom, amy):
        expect(page.get_by_role("heading", name="Round 1 results")).to_be_visible()
        assert leaderboard(page) == [["1st", "Amy (1)", "10.00"], ["1st", "Tom (1)", "10.00"]]
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
        assert leaderboard(page) == [["1st", "Tom (1)", "7.50"], ["2nd", "Amy (0)", "DNF"]]
    expect(tom.get_by_role("button", name="End round")).to_be_hidden()


def test_round_wins_add_up_as_points_after_each_name(tom_and_amy):
    tom, amy, _ = tom_and_amy
    for tom_ms, amy_ms in ((12_000, 9_000), (8_000, 9_500)):
        tom.get_by_role("button", name="Start round").click()
        solve(amy, amy_ms)
        solve(tom, tom_ms)
        expect(tom.get_by_role("button", name="Start round")).to_be_visible()

    for page in (tom, amy):
        expect(page.locator("#players")).to_contain_text("Tom (1) (owner)")
        expect(page.locator("#players")).to_contain_text("Amy (1)")
        assert leaderboard(page) == [["1st", "Tom (1)", "8.00"], ["2nd", "Amy (1)", "9.50"]]


def test_joining_mid_round_gets_the_scramble_straight_away(tom_and_amy, new_player):
    tom, _, link = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    bob = new_player()

    join(bob, link, "Bob")

    expect(bob.get_by_role("button", name="Start inspection")).to_be_visible()


def test_everyone_is_told_when_the_owner_leaves_for_good(tom_and_amy, live_server):
    tom, amy, _ = tom_and_amy

    tom.close()
    expect(amy.locator("#players")).to_contain_text("Tom (0) (owner) (away)")
    control(live_server, "advance-clock", seconds=30)
    control(live_server, "end-abandoned")

    expect(amy.get_by_text("This challenge has ended")).to_be_visible()


def test_times_over_a_minute_show_minutes(new_player):
    page = new_player()
    start_challenge(page)

    assert page.evaluate("ScrambleChallenge.formatTime(62350)") == "1:02.35"
    assert page.evaluate("ScrambleChallenge.formatTime(9870)") == "9.87"
    assert page.evaluate("ScrambleChallenge.formatTime(null)") == "DNF"


@pytest.mark.parametrize(
    ("time_ms", "shown"),
    [
        (12_345, "12.34"),
        (12_349, "12.34"),
        (59_999, "59.99"),
        (60_009, "1:00.00"),
        (600_000, "10:00.00"),
        (1_005, "1.00"),
    ],
)
def test_times_are_truncated_to_hundredths_like_wca(new_player, time_ms, shown):
    page = new_player()
    start_challenge(page)

    assert page.evaluate(f"ScrambleChallenge.formatTime({time_ms})") == shown
