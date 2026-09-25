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


# How long the finished screen shows is a real setTimeout, so on a slow machine a test can't
# rely on catching it within the second. These patch the page's setTimeout: one records the
# delays asked for, the other also stretches the one-second screen so a test can look at it.
RECORD_TIMEOUTS = """
  window.__timeouts = [];
  const realSetTimeout = window.setTimeout;
  window.setTimeout = (fn, ms, ...rest) => {
    window.__timeouts.push(ms);
    return realSetTimeout(fn, ms === 1000 && window.__stretch ? 4000 : ms, ...rest);
  };
"""


def record_timeouts(page, stretch_one_second=False):
    page.evaluate(RECORD_TIMEOUTS)
    page.evaluate(f"window.__stretch = {'true' if stretch_one_second else 'false'}")


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


# After stopping, the player's own time fills the screen for a second, then the page
# moves on. The finished screen shows the time and nothing else (the owner chose no label).
def test_stopping_shows_the_time_full_screen_for_a_second_then_the_leaderboard(tom_and_amy):
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    amy.get_by_role("button", name="Start inspection").click()
    amy.locator("#overlay").click()
    advance(amy, 12_349)
    record_timeouts(amy, stretch_one_second=True)

    amy.locator("#overlay").click()

    finished = amy.locator("#finished")
    expect(finished).to_be_visible()
    expect(finished).to_have_text("12.34")  # truncated, never rounded
    expect(amy.locator("#game")).to_have_attribute("data-phase", "finished")
    expect(amy.get_by_text("Tap anywhere")).to_be_hidden()
    assert 1000 in amy.evaluate("window.__timeouts")

    expect(amy.locator("#overlay")).to_be_hidden()
    expect(amy.locator("#leaderboard")).to_be_visible()
    assert leaderboard(amy) == [["1st", "Amy (0)", "12.34"]]


def test_taps_on_the_finished_screen_do_nothing(tom_and_amy):
    tom, amy, _ = tom_and_amy
    start_inspecting(tom, amy)
    record_timeouts(amy, stretch_one_second=True)
    amy.locator("#overlay").click()
    advance(amy, 5000)
    amy.locator("#overlay").click()

    expect(amy.locator("#finished")).to_be_visible()
    amy.locator("#overlay").dispatch_event("pointerdown")
    amy.keyboard.press("Space")

    expect(amy.locator("#overlay")).to_be_hidden()
    assert leaderboard(amy) == [["1st", "Amy (0)", "5.00"]]


def test_running_out_of_inspection_shows_dnf_for_a_second(tom_and_amy):
    tom, amy, _ = tom_and_amy
    start_inspecting(tom, amy)
    record_timeouts(amy, stretch_one_second=True)

    advance(amy, 15_000)

    finished = amy.locator("#finished")
    expect(finished).to_be_visible()
    expect(finished).to_have_text("DNF")
    # Lets themes show a DNF differently from a time.
    expect(finished).to_have_attribute("data-result", "dnf")
    expect(amy.locator("#overlay")).to_be_hidden()
    assert leaderboard(amy) == [["1st", "Amy (0)", "DNF"]]


def test_a_finished_time_is_marked_for_themes(tom_and_amy):
    tom, amy, _ = tom_and_amy
    start_inspecting(tom, amy)
    record_timeouts(amy, stretch_one_second=True)
    amy.locator("#overlay").click()
    advance(amy, 5000)
    amy.locator("#overlay").click()

    expect(amy.locator("#finished")).to_have_attribute("data-result", "time")


def test_the_last_to_finish_sees_their_time_before_the_round_results(tom_and_amy):
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    solve(amy, 9_000)
    expect(amy.locator("#overlay")).to_be_hidden()  # Amy's own second is over
    record_timeouts(tom, stretch_one_second=True)

    solve(tom, 10_000)

    # Amy is already on the results, so the round has ended for Tom's page too...
    expect(amy.get_by_role("heading", name="Round 1 results")).to_be_visible()
    # Time for the same round_complete to reach Tom's page. His one second is stretched to
    # four, so his time is still up afterwards even on a slow machine.
    tom.wait_for_timeout(300)
    # ...but Tom's own time is still showing, not the results.
    expect(tom.locator("#finished")).to_be_visible()
    expect(tom.locator("#finished")).to_have_text("10.00")
    expect(tom.get_by_role("heading", name="Round 1 results")).to_be_hidden()

    expect(tom.get_by_role("heading", name="Round 1 results")).to_be_visible()
    expect(tom.get_by_role("button", name="Start round")).to_be_visible()
    expect(tom.locator("#overlay")).to_be_hidden()


def test_a_round_started_while_the_time_shows_is_not_skipped(tom_and_amy):
    # The owner may start the next round within the second Amy's time is showing.
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    solve(tom, 8_000)
    expect(tom.locator("#overlay")).to_be_hidden()

    solve(amy, 9_000)
    tom.get_by_role("button", name="Start round").click()

    expect(amy.get_by_role("heading", name="Round 2: 3x3")).to_be_visible()
    amy.wait_for_timeout(1500)
    expect(amy.get_by_role("button", name="Start inspection")).to_be_visible()
    expect(amy.locator("#overlay")).to_be_hidden()


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


def test_everyone_goes_to_the_summary_when_the_challenge_ends(tom_and_amy, live_server):
    tom, amy, link = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    solve(amy, 9_000)
    solve(tom, 12_000)
    expect(amy.get_by_role("heading", name="Round 1 results")).to_be_visible()

    tom.close()
    expect(amy.locator("#players")).to_contain_text("Tom (0) (owner) (away)")
    control(live_server, "advance-clock", seconds=30)
    control(live_server, "end-abandoned")

    expect(amy).to_have_url(f"{link}/summary")
    expect(amy.get_by_role("heading", name="This challenge has ended")).to_be_visible()
    expect(amy.locator(".standing")).to_have_text(["1st Amy (1)", "2nd Tom (0)"])
    expect(amy.locator(".result").first).to_be_hidden()

    amy.get_by_role("button", name="View rounds").click()
    expect(amy.locator(".result")).to_have_text(["1st Amy (1) 9.00", "2nd Tom (0) 12.00"])
    expect(amy.locator(".result").first).to_be_visible()

    amy.get_by_role("button", name="Hide rounds").click()
    expect(amy.locator(".result").first).to_be_hidden()
    expect(amy.get_by_role("button", name="View rounds")).to_have_attribute(
        "aria-expanded", "false"
    )


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


# On a keyboard, the spacebar does what a tap on the blank screen does.
# Records, for every spacebar keydown, whether the page stopped the browser's own action
# (scrolling the page, or pressing a focused button). Listens on window, so it runs after
# any listener on the document.
RECORD_SPACE_DEFAULTS = """
  window.__spaceDefaultPrevented = [];
  window.addEventListener("keydown", (event) => {
    if (event.code === "Space") window.__spaceDefaultPrevented.push(event.defaultPrevented);
  });
"""


def start_inspecting(tom, amy):
    tom.get_by_role("button", name="Start round").click()
    amy.get_by_role("button", name="Start inspection").click()
    expect(amy.locator("#countdown")).to_have_text("15")


def test_space_starts_the_solve_during_inspection_and_stops_it(tom_and_amy):
    tom, amy, _ = tom_and_amy
    start_inspecting(tom, amy)

    amy.keyboard.press("Space")
    expect(amy.get_by_text("Solving")).to_be_visible()
    advance(amy, 7650)
    amy.keyboard.press("Space")

    for page in (tom, amy):
        expect(page.locator("#leaderboard")).to_contain_text("Amy")
        assert leaderboard(page) == [["1st", "Amy (0)", "7.65"]]


def test_holding_space_waits_and_letting_go_starts_the_solve(tom_and_amy):
    # Like a real cubing timer: hold space while getting ready, let go to start. The
    # key's auto-repeats while it is held are not new presses.
    tom, amy, _ = tom_and_amy
    start_inspecting(tom, amy)

    amy.keyboard.down("Space")
    amy.keyboard.down("Space")
    advance(amy, 2000)
    expect(amy.locator("#countdown")).to_have_text("13")
    expect(amy.get_by_text("Solving")).to_be_hidden()

    amy.keyboard.up("Space")
    expect(amy.get_by_text("Solving")).to_be_visible()
    advance(amy, 6420)
    # Stopping happens the moment space goes down, so no time is added while letting go.
    amy.keyboard.down("Space")
    expect(amy.locator("#leaderboard")).to_contain_text("Amy")
    amy.keyboard.up("Space")

    assert leaderboard(amy) == [["1st", "Amy (0)", "6.42"]]


def test_space_mixes_with_taps(tom_and_amy):
    tom, amy, _ = tom_and_amy
    start_inspecting(tom, amy)

    amy.locator("#overlay").click()
    advance(amy, 5000)
    amy.keyboard.press("Space")

    expect(amy.locator("#leaderboard")).to_contain_text("Amy")
    assert leaderboard(amy) == [["1st", "Amy (0)", "5.00"]]


def test_space_does_not_scroll_the_page_while_timing(tom_and_amy):
    tom, amy, _ = tom_and_amy
    amy.evaluate(RECORD_SPACE_DEFAULTS)
    start_inspecting(tom, amy)

    amy.keyboard.press("Space")
    advance(amy, 3000)
    amy.keyboard.press("Space")

    expect(amy.locator("#leaderboard")).to_contain_text("Amy")
    assert amy.evaluate("window.__spaceDefaultPrevented") == [True, True]


def test_space_still_presses_a_focused_button_outside_the_timer(tom_and_amy):
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    amy.get_by_role("button", name="Start inspection").focus()

    amy.keyboard.press("Space")

    expect(amy.locator("#countdown")).to_have_text("15")
    expect(amy.get_by_text("Solving")).to_be_hidden()


def test_space_with_ctrl_alt_or_meta_is_left_alone(tom_and_amy):
    # Those are usually shortcuts (switching input language, Spotlight), not timer presses.
    tom, amy, _ = tom_and_amy
    start_inspecting(tom, amy)

    for shortcut in ("Control+Space", "Alt+Space", "Meta+Space"):
        amy.keyboard.press(shortcut)

    expect(amy.locator("#countdown")).to_have_text("15")
    expect(amy.get_by_text("Solving")).to_be_hidden()


def test_holding_space_marks_the_screen_ready_for_themes(tom_and_amy):
    # Real timers light up while held, so the player knows letting go will start. The page
    # sets data-ready on #game; each theme decides how it looks.
    tom, amy, _ = tom_and_amy
    start_inspecting(tom, amy)
    game = amy.locator("#game")

    amy.keyboard.down("Space")
    expect(game).to_have_attribute("data-ready", "true")

    amy.keyboard.up("Space")
    expect(amy.get_by_text("Solving")).to_be_visible()
    expect(game).not_to_have_attribute("data-ready", "true")


def test_letting_go_of_space_after_inspection_ran_out_does_not_start_a_solve(tom_and_amy):
    tom, amy, _ = tom_and_amy
    start_inspecting(tom, amy)

    amy.keyboard.down("Space")
    advance(amy, 15_000)
    expect(amy.locator("#message")).to_have_text("Inspection ran out: DNF.")
    expect(amy.locator("#game")).not_to_have_attribute("data-ready", "true")
    amy.keyboard.up("Space")

    expect(amy.locator("#overlay")).to_be_hidden()
    # The leaderboard comes from the server, so wait for it before reading it.
    expect(amy.locator("#leaderboard")).to_contain_text("DNF")
    assert leaderboard(amy) == [["1st", "Amy (0)", "DNF"]]


# A finger (or mouse button) on the blank screen works like the spacebar: hold it down
# during inspection to get ready, lift it to start the solve; a press while solving stops.
def press_overlay(page):
    box = page.locator("#overlay").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()


def test_holding_a_finger_down_waits_and_lifting_it_starts_the_solve(tom_and_amy):
    tom, amy, _ = tom_and_amy
    start_inspecting(tom, amy)

    press_overlay(amy)
    expect(amy.locator("#game")).to_have_attribute("data-ready", "true")
    advance(amy, 2000)
    expect(amy.locator("#countdown")).to_have_text("13")
    expect(amy.get_by_text("Solving")).to_be_hidden()

    amy.mouse.up()
    expect(amy.get_by_text("Solving")).to_be_visible()
    expect(amy.locator("#game")).not_to_have_attribute("data-ready", "true")
    advance(amy, 4310)
    # Stopping happens the moment the finger goes down, so lifting it adds no time.
    press_overlay(amy)
    expect(amy.locator("#leaderboard")).to_contain_text("Amy")
    amy.mouse.up()

    assert leaderboard(amy) == [["1st", "Amy (0)", "4.31"]]


def test_a_press_the_browser_cancels_does_not_start_the_solve(tom_and_amy):
    tom, amy, _ = tom_and_amy
    start_inspecting(tom, amy)

    press_overlay(amy)
    expect(amy.locator("#game")).to_have_attribute("data-ready", "true")
    amy.locator("#overlay").dispatch_event("pointercancel")

    expect(amy.locator("#game")).not_to_have_attribute("data-ready", "true")
    amy.mouse.up()
    expect(amy.locator("#countdown")).to_have_text("15")
    expect(amy.get_by_text("Solving")).to_be_hidden()


def test_a_long_press_does_not_open_the_phones_menu(tom_and_amy):
    tom, amy, _ = tom_and_amy
    start_inspecting(tom, amy)

    not_prevented = amy.evaluate(
        "document.getElementById('overlay').dispatchEvent("
        "new MouseEvent('contextmenu', { bubbles: true, cancelable: true }))"
    )

    assert not_prevented is False


def test_a_finger_that_drifts_while_held_still_starts_the_solve_when_lifted(new_player):
    # Real touch events, as a phone sends them. A finger rarely stays perfectly still, and
    # the browser must not take a small drift over as a scroll (which cancels the press).
    tom, amy = new_player(), new_player(has_touch=True, is_mobile=True)
    for page in (tom, amy):
        page.add_init_script(FAKE_NOW)
    link = start_challenge(tom)
    join(amy, link, "Amy")
    for page in (tom, amy):
        set_now(page, 1_000_000)
    start_inspecting(tom, amy)
    touch = amy.context.new_cdp_session(amy)

    touch.send(
        "Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": 195, "y": 400}]}
    )
    expect(amy.locator("#game")).to_have_attribute("data-ready", "true")
    for y in (420, 440, 460):
        touch.send(
            "Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": 195, "y": y}]}
        )
    touch.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})

    expect(amy.get_by_text("Solving")).to_be_visible()


def test_the_owner_ends_the_challenge_after_a_round_and_everyone_sees_the_summary(tom_and_amy):
    tom, amy, link = tom_and_amy
    end_challenge = tom.get_by_role("button", name=re.compile("End challenge"))
    expect(end_challenge).to_be_hidden()  # no results yet
    tom.get_by_role("button", name="Start round").click()
    solve(tom, 8_000)
    expect(tom.get_by_role("button", name="End round")).to_be_visible()
    expect(end_challenge).to_be_hidden()  # not while the round is running

    solve(amy, 9_000)
    expect(end_challenge).to_be_visible()
    expect(end_challenge).to_have_text(re.compile(r"End challenge\s*show results"))
    expect(amy.get_by_role("heading", name="Round 1 results")).to_be_visible()
    expect(amy.get_by_role("button", name=re.compile("End challenge"))).to_have_count(0)

    end_challenge.click()
    expect(tom.get_by_text("End the challenge for everyone?")).to_be_visible()
    tom.get_by_role("button", name="Cancel").click()
    expect(tom.get_by_text("End the challenge for everyone?")).to_be_hidden()
    expect(amy).to_have_url(link)

    end_challenge.click()
    tom.get_by_role("button", name="Yes, end it").click()

    for page in (tom, amy):
        expect(page).to_have_url(f"{link}/summary")
        expect(page.get_by_role("heading", name="This challenge has ended")).to_be_visible()


def test_starting_another_round_puts_the_end_challenge_button_away(tom_and_amy):
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    solve(tom, 8_000)
    solve(amy, 9_000)
    end_challenge = tom.get_by_role("button", name=re.compile("End challenge"))
    end_challenge.click()
    expect(tom.get_by_text("End the challenge for everyone?")).to_be_visible()

    tom.get_by_role("button", name="Start round").click()
    solve(tom, 8_000)

    expect(tom.get_by_role("heading", name="Round 2")).to_be_visible()
    expect(end_challenge).to_be_hidden()
    expect(tom.get_by_text("End the challenge for everyone?")).to_be_hidden()
