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
)
from tests.e2e.test_game import FAKE_NOW, join, set_now, start_challenge


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
