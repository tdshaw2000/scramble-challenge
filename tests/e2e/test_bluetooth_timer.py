"""Connecting a Bluetooth timer and solving with it (openspec/specs/bluetooth-timer), against
the fake QiYi timer in fake_bluetooth.py."""

import pytest
from playwright.sync_api import expect

from tests.e2e import qiyi
from tests.e2e.fake_bluetooth import (
    FAKE_BLUETOOTH,
    NO_BLUETOOTH,
    NOTIFY,
    RECORD_EMITS,
    SERVICE,
    WRITE,
    send,
    written_messages,
)
from tests.e2e.test_game import (
    FAKE_NOW,
    advance,
    join,
    leaderboard,
    set_now,
    solve,
    start_challenge,
)


def test_the_fake_timer_can_be_connected_to_and_talks_back(new_player):
    page = new_player()
    page.add_init_script(FAKE_BLUETOOTH)
    page.goto("/")
    page.add_script_tag(url="/static/vendor/aes.js")

    page.evaluate(
        """async ([service, write, notify]) => {
          const device = await navigator.bluetooth.requestDevice({
            filters: [{ namePrefix: "QY-" }], optionalServices: [service],
          });
          window.__device = device.name;
          const gatt = await device.gatt.connect();
          const timer = await gatt.getPrimaryService(service);
          await (await timer.getCharacteristic(write)).writeValue(new Uint8Array([1, 2, 3]));
          const incoming = await timer.getCharacteristic(notify);
          window.__heard = [];
          incoming.addEventListener("characteristicvaluechanged", (event) => {
            window.__heard.push(Array.from(new Uint8Array(event.target.value.buffer)));
          });
          await incoming.startNotifications();
          device.addEventListener("gattserverdisconnected", () => { window.__dropped = true; });
        }""",
        [SERVICE, WRITE, NOTIFY],
    )
    send(page, qiyi.status(qiyi.IDLE))
    page.evaluate("__bt.drop()")

    assert page.evaluate("window.__device") == "QY-Adapter-2B0F"
    assert page.evaluate("__bt.written") == [[1, 2, 3]]
    heard = page.evaluate("window.__heard")
    assert len(heard) == 2 and heard[0][:4] == [0x00, 23 + 2, 0x40, 0x00]
    assert page.evaluate("window.__dropped") is True


# --- the button --------------------------------------------------------------------------

CONNECT = "#connect-timer"


def start_round(tom, amy):
    tom.get_by_role("button", name="Start round").click()
    expect(amy.get_by_role("button", name="Start inspection")).to_be_visible()


@pytest.fixture
def tom_and_amy_with_bluetooth(new_player):
    """Tom owns the challenge; Amy's browser has Web Bluetooth with a QiYi timer nearby."""
    tom, amy = new_player(), new_player()
    for page in (tom, amy):
        page.add_init_script(FAKE_NOW)
    amy.add_init_script(FAKE_BLUETOOTH)
    amy.add_init_script(RECORD_EMITS)
    link = start_challenge(tom)
    join(amy, link, "Amy")
    for page in (tom, amy):
        set_now(page, 1_000_000)
    return tom, amy


def test_the_connect_timer_button_sits_under_show_time_with_a_stopwatch_icon(
    tom_and_amy_with_bluetooth,
):
    tom, amy = tom_and_amy_with_bluetooth
    start_round(tom, amy)

    button = amy.locator(CONNECT)
    expect(button).to_be_visible()
    expect(button).to_have_text("Connect timer")
    expect(button).to_have_attribute("aria-pressed", "false")
    expect(button.locator("svg.connect-timer-icon")).to_have_attribute("aria-hidden", "true")
    show_time = amy.locator("#show-time").bounding_box()
    assert button.bounding_box()["y"] > show_time["y"] + show_time["height"]


def test_there_is_no_timer_button_without_web_bluetooth(new_player):
    tom, amy = new_player(), new_player()
    amy.add_init_script(NO_BLUETOOTH)
    link = start_challenge(tom)
    join(amy, link, "Amy")
    start_round(tom, amy)

    expect(amy.locator("#show-time")).to_be_visible()
    expect(amy.locator(CONNECT)).to_be_hidden()


# --- connecting and disconnecting ---------------------------------------------------------


def connect(amy):
    amy.locator(CONNECT).click()
    expect(amy.locator(CONNECT)).to_have_text("Timer connected")


def test_connecting_asks_for_qiyi_timers_and_says_hello_with_the_address_from_the_name(
    tom_and_amy_with_bluetooth,
):
    tom, amy = tom_and_amy_with_bluetooth
    start_round(tom, amy)

    connect(amy)

    expect(amy.locator(CONNECT)).to_have_attribute("aria-pressed", "true")
    options = amy.evaluate("__bt.options")
    assert options["filters"] == [{"namePrefix": "QY-Timer"}, {"namePrefix": "QY-Adapter"}]
    assert SERVICE in options["optionalServices"]
    hello = qiyi.message(1, 0, qiyi.HELLO, qiyi.hello_data("CC:A8:00:00:2B:0F"))
    expect(amy.locator(CONNECT)).to_have_attribute("aria-pressed", "true")
    assert written_messages(amy) == [hello]


def test_a_qiyi_smart_timer_gets_its_own_address_family(tom_and_amy_with_bluetooth):
    tom, amy = tom_and_amy_with_bluetooth
    start_round(tom, amy)
    amy.evaluate("__bt.name = 'QY-Timer-AB12'")

    connect(amy)

    hello = qiyi.message(1, 0, qiyi.HELLO, qiyi.hello_data("CC:A1:00:00:AB:12"))
    assert written_messages(amy) == [hello]


def screen_solve_works(tom, amy):
    solve(amy, 5000)
    expect(amy.locator("#result-list")).to_contain_text("Amy")
    assert leaderboard(amy) == [["1st", "Amy (0)", "5.00"]]


@pytest.mark.parametrize(
    "trouble",
    [
        "__bt.cancel = true",  # the player closed the device list
        "__bt.failConnect = true",  # the timer is off or out of range
        "__bt.name = 'QY-Timer'",  # no address to be had from the name
    ],
)
def test_a_timer_that_does_not_connect_leaves_the_screen_in_charge(
    tom_and_amy_with_bluetooth, trouble
):
    tom, amy = tom_and_amy_with_bluetooth
    start_round(tom, amy)
    amy.evaluate(trouble)

    amy.locator(CONNECT).click()

    expect(amy.locator("#message")).to_have_text("Timer not connected.")
    expect(amy.locator(CONNECT)).to_have_text("Connect timer")
    expect(amy.locator(CONNECT)).to_have_attribute("aria-pressed", "false")
    assert amy.evaluate("__bt.connected") is False
    screen_solve_works(tom, amy)


def test_pressing_the_button_again_disconnects_and_the_screen_takes_over(
    tom_and_amy_with_bluetooth,
):
    tom, amy = tom_and_amy_with_bluetooth
    start_round(tom, amy)
    connect(amy)

    amy.locator(CONNECT).click()

    expect(amy.locator(CONNECT)).to_have_text("Connect timer")
    expect(amy.locator(CONNECT)).to_have_attribute("aria-pressed", "false")
    assert amy.evaluate("__bt.connected") is False
    expect(amy.locator("#message")).to_be_hidden()
    screen_solve_works(tom, amy)


SKINS = ["plain", "dark", "dos", "mario64", "monkeyisland2", "neon80s"]


@pytest.mark.parametrize("skin", SKINS)
def test_the_timer_button_looks_like_show_time_with_a_text_sized_icon_in_every_skin(
    tom_and_amy_with_bluetooth, skin
):
    tom, amy = tom_and_amy_with_bluetooth
    start_round(tom, amy)
    amy.context.add_cookies([{"name": "scramble_skin", "value": skin, "url": amy.url}])
    amy.reload()
    expect(amy.locator(CONNECT)).to_be_visible()

    button, show_time = amy.locator(CONNECT), amy.locator("#show-time")
    assert button.bounding_box()["height"] == show_time.bounding_box()["height"]
    assert button.bounding_box()["width"] == show_time.bounding_box()["width"]
    icon = button.locator(".connect-timer-icon").bounding_box()
    label = button.locator(".connect-timer-label").bounding_box()
    font_size = float(button.evaluate("b => getComputedStyle(b).fontSize")[:-2])
    assert font_size <= icon["height"] <= 1.5 * font_size
    # Side by side, the icon first, both centred on the same line.
    assert icon["x"] + icon["width"] <= label["x"]
    assert abs((icon["y"] + icon["height"] / 2) - (label["y"] + label["height"] / 2)) < 3

    connect(amy)
    on = amy.evaluate(
        "() => [getComputedStyle(document.getElementById('connect-timer')).backgroundColor,"
        " getComputedStyle(document.getElementById('connect-timer')).color]"
    )
    show_time.click()  # Show time on: the same highlight
    expect(show_time).to_have_attribute("aria-pressed", "true")
    assert on == amy.evaluate(
        "() => [getComputedStyle(document.getElementById('show-time')).backgroundColor,"
        " getComputedStyle(document.getElementById('show-time')).color]"
    )


@pytest.mark.parametrize("skin", SKINS)
def test_the_hidden_timer_button_stays_hidden_in_every_skin(new_player, skin):
    tom, amy = new_player(), new_player()
    amy.add_init_script(NO_BLUETOOTH)
    link = start_challenge(tom)
    join(amy, link, "Amy")
    amy.context.add_cookies([{"name": "scramble_skin", "value": skin, "url": amy.url}])
    start_round(tom, amy)
    amy.reload()
    expect(amy.locator("#show-time")).to_be_visible()

    expect(amy.locator(CONNECT)).to_be_hidden()


# --- the timer drives the solve ----------------------------------------------------------


def emitted(page, event):
    return page.evaluate("window.__emitted").count(event)


def start_connected_inspection(tom, amy):
    start_round(tom, amy)
    connect(amy)
    amy.get_by_role("button", name="Start inspection").click()
    expect(amy.locator("#game")).to_have_attribute("data-phase", "inspecting")


def own_result(amy):
    expect(amy.locator("#result-list")).to_contain_text("Amy")
    return leaderboard(amy)[0]


@pytest.mark.parametrize("finish", ["status", "record"])
def test_a_full_timer_solve_records_the_timers_own_time(tom_and_amy_with_bluetooth, finish):
    tom, amy = tom_and_amy_with_bluetooth
    start_connected_inspection(tom, amy)
    expect(amy.locator("#overlay-hint")).to_have_text("Use your timer")

    send(amy, qiyi.status(qiyi.GET_SET))
    expect(amy.locator("#game")).to_have_attribute("data-ready", "true")
    send(amy, qiyi.status(qiyi.IDLE))  # hands lifted too soon
    expect(amy.locator("#game")).not_to_have_attribute("data-ready", "true")
    send(amy, qiyi.status(qiyi.GET_SET))
    expect(amy.locator("#game")).to_have_attribute("data-ready", "true")
    advance(amy, 3000)
    send(amy, qiyi.status(qiyi.RUNNING))
    expect(amy.locator("#game")).to_have_attribute("data-phase", "solving")
    expect(amy.locator("#game")).not_to_have_attribute("data-ready", "true")
    advance(amy, 11000)  # the browser's clock disagrees with the timer: the timer wins
    if finish == "status":
        send(amy, qiyi.status(qiyi.STOPPED, 12345))
    else:
        send(amy, qiyi.record(12345, send_sn=7, ack_sn=3))

    expect(amy.locator("#finished")).to_have_text("12.34")
    assert own_result(amy) == ["1st", "Amy (0)", "12.34"]
    assert emitted(amy, "start_solve") == 1 and emitted(amy, "stop_solve") == 1
    if finish == "record":
        assert written_messages(amy)[-1] == qiyi.message(4, 7, qiyi.TIMER_DATA, [0])


def test_a_timer_start_in_the_last_two_seconds_of_inspection_is_a_plus_two(
    tom_and_amy_with_bluetooth,
):
    tom, amy = tom_and_amy_with_bluetooth
    start_connected_inspection(tom, amy)

    advance(amy, 15500)
    send(amy, qiyi.status(qiyi.RUNNING))
    expect(amy.locator("#game")).to_have_attribute("data-phase", "solving")
    send(amy, qiyi.status(qiyi.STOPPED, 10000))

    assert own_result(amy) == ["1st", "Amy (0)", "12.00+"]


def test_inspection_still_runs_out_to_a_dnf_with_a_timer_connected(tom_and_amy_with_bluetooth):
    tom, amy = tom_and_amy_with_bluetooth
    start_connected_inspection(tom, amy)

    advance(amy, 17100)

    expect(amy.locator("#finished")).to_have_text("DNF")
    send(amy, qiyi.status(qiyi.RUNNING))
    send(amy, qiyi.status(qiyi.STOPPED, 5000))
    assert own_result(amy) == ["1st", "Amy (0)", "DNF"]
    assert emitted(amy, "start_solve") == 0 and emitted(amy, "stop_solve") == 0


def test_timer_activity_outside_inspection_and_solving_does_nothing(tom_and_amy_with_bluetooth):
    tom, amy = tom_and_amy_with_bluetooth
    start_round(tom, amy)
    connect(amy)

    # On the scramble screen, before inspection.
    for state in (qiyi.GET_SET, qiyi.RUNNING):
        send(amy, qiyi.status(state))
    send(amy, qiyi.status(qiyi.STOPPED, 4000))
    amy.wait_for_timeout(300)
    expect(amy.locator("#game")).to_have_attribute("data-phase", "scramble")
    expect(amy.locator("#game")).not_to_have_attribute("data-ready", "true")

    # After the attempt is finished.
    amy.get_by_role("button", name="Start inspection").click()
    send(amy, qiyi.status(qiyi.RUNNING))
    send(amy, qiyi.status(qiyi.STOPPED, 6000))
    assert own_result(amy) == ["1st", "Amy (0)", "6.00"]
    send(amy, qiyi.status(qiyi.GET_SET))
    send(amy, qiyi.status(qiyi.RUNNING))
    send(amy, qiyi.record(7000))
    amy.wait_for_timeout(300)

    expect(amy.locator("#game")).not_to_have_attribute("data-ready", "true")
    assert own_result(amy) == ["1st", "Amy (0)", "6.00"]
    assert emitted(amy, "start_solve") == 1 and emitted(amy, "stop_solve") == 1


def test_the_screen_and_spacebar_neither_start_nor_stop_a_solve_while_connected(
    tom_and_amy_with_bluetooth,
):
    tom, amy = tom_and_amy_with_bluetooth
    start_connected_inspection(tom, amy)

    amy.locator("#overlay").click()
    amy.keyboard.press("Space")
    amy.wait_for_timeout(300)
    expect(amy.locator("#game")).to_have_attribute("data-phase", "inspecting")
    expect(amy.locator("#game")).not_to_have_attribute("data-ready", "true")

    send(amy, qiyi.status(qiyi.RUNNING))
    expect(amy.locator("#game")).to_have_attribute("data-phase", "solving")
    amy.locator("#overlay").click()
    amy.keyboard.press("Space")
    amy.wait_for_timeout(300)
    expect(amy.locator("#game")).to_have_attribute("data-phase", "solving")

    send(amy, qiyi.status(qiyi.STOPPED, 8000))
    assert own_result(amy) == ["1st", "Amy (0)", "8.00"]
    assert emitted(amy, "start_solve") == 1 and emitted(amy, "stop_solve") == 1


def test_an_untimed_inspection_round_works_with_the_timer(tom_and_amy_with_bluetooth):
    tom, amy = tom_and_amy_with_bluetooth
    tom.get_by_label("Timed inspection").uncheck()
    start_connected_inspection(tom, amy)
    expect(amy.locator("#countdown")).to_be_hidden()

    advance(amy, 20000)
    send(amy, qiyi.status(qiyi.RUNNING))
    expect(amy.locator("#game")).to_have_attribute("data-phase", "solving")
    send(amy, qiyi.status(qiyi.STOPPED, 9000))

    assert own_result(amy) == ["1st", "Amy (0)", "9.00"]


# --- losing the timer --------------------------------------------------------------------

LOST_HINT = "Timer lost: tap anywhere"
LOST_MESSAGE = "Timer lost: use the screen instead."


def test_losing_the_timer_in_inspection_hands_the_solve_to_the_screen(
    tom_and_amy_with_bluetooth,
):
    tom, amy = tom_and_amy_with_bluetooth
    start_connected_inspection(tom, amy)
    advance(amy, 3000)
    send(amy, qiyi.status(qiyi.GET_SET))
    expect(amy.locator("#game")).to_have_attribute("data-ready", "true")

    amy.evaluate("__bt.drop()")

    expect(amy.locator("#overlay-hint")).to_have_text(LOST_HINT)
    expect(amy.locator("#message")).to_have_text(LOST_MESSAGE)
    expect(amy.locator("#game")).not_to_have_attribute("data-ready", "true")
    expect(amy.locator(CONNECT)).to_have_text("Connect timer")
    advance(amy, 1000)
    expect(amy.locator("#countdown")).to_have_text("11")
    amy.locator("#overlay").click()
    expect(amy.locator("#game")).to_have_attribute("data-phase", "solving")
    advance(amy, 5000)
    amy.locator("#overlay").click()

    assert own_result(amy) == ["1st", "Amy (0)", "5.00"]


def test_losing_the_timer_mid_solve_lets_the_screen_stop_it_timed_from_the_timers_start(
    tom_and_amy_with_bluetooth,
):
    tom, amy = tom_and_amy_with_bluetooth
    start_connected_inspection(tom, amy)
    send(amy, qiyi.status(qiyi.RUNNING))
    expect(amy.locator("#game")).to_have_attribute("data-phase", "solving")
    advance(amy, 4000)

    amy.evaluate("__bt.drop()")

    expect(amy.locator("#overlay-hint")).to_have_text(LOST_HINT)
    expect(amy.locator("#message")).to_have_text(LOST_MESSAGE)
    advance(amy, 2340)
    amy.locator("#overlay").click()

    assert own_result(amy) == ["1st", "Amy (0)", "6.34"]


def test_after_a_lost_timer_the_next_inspection_says_tap_anywhere_again(
    tom_and_amy_with_bluetooth,
):
    tom, amy = tom_and_amy_with_bluetooth
    start_round(tom, amy)
    connect(amy)

    amy.evaluate("__bt.drop()")
    expect(amy.locator("#message")).to_have_text(LOST_MESSAGE)
    amy.get_by_role("button", name="Start inspection").click()

    expect(amy.locator("#overlay-hint")).to_have_text("Tap anywhere")


def test_the_timer_switching_itself_off_counts_as_losing_it(tom_and_amy_with_bluetooth):
    tom, amy = tom_and_amy_with_bluetooth
    start_connected_inspection(tom, amy)

    send(amy, qiyi.status(qiyi.DISCONNECT))

    expect(amy.locator("#overlay-hint")).to_have_text(LOST_HINT)
    assert amy.evaluate("__bt.connected") is False
