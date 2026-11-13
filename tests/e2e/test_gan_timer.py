"""Connecting a GAN timer (the owner's is a GAN Halo) and solving with it
(openspec/specs/bluetooth-timer), against the fake GAN timer in fake_bluetooth.py. Everything
else about a connected timer is shared with QiYi and tested in test_bluetooth_timer.py."""

import re

import pytest
from playwright.sync_api import expect

from tests.e2e import gan
from tests.e2e.fake_bluetooth import send_gan
from tests.e2e.test_bluetooth_timer import (
    CONNECT,
    LOST_HINT,
    LOST_MESSAGE,
    connect,
    emitted,
    own_result,
    screen_solve_works,
    start_round,
    tom_and_amy_with_bluetooth,  # noqa: F401 (a fixture)
)
from tests.e2e.test_game import advance

HALO = "GAN-STv4769"


@pytest.fixture
def tom_and_amy_with_a_halo(tom_and_amy_with_bluetooth):  # noqa: F811
    tom, amy = tom_and_amy_with_bluetooth
    amy.evaluate(f"__bt.name = '{HALO}'")
    return tom, amy


def start_connected_inspection(tom, amy):
    start_round(tom, amy)
    connect(amy)
    amy.get_by_role("button", name="Start inspection").click()
    expect(amy.locator("#game")).to_have_attribute("data-phase", "inspecting")


def test_a_gan_timer_connects_and_nothing_is_written_to_it(tom_and_amy_with_a_halo):
    tom, amy = tom_and_amy_with_a_halo
    start_round(tom, amy)

    connect(amy)

    expect(amy.locator(CONNECT)).to_have_attribute("aria-pressed", "true")
    assert amy.evaluate("__bt.connected") is True
    assert amy.evaluate("__bt.written") == []


def test_a_gan_timer_that_does_not_connect_leaves_the_screen_in_charge(tom_and_amy_with_a_halo):
    tom, amy = tom_and_amy_with_a_halo
    start_round(tom, amy)
    amy.evaluate("__bt.failConnect = true")

    amy.locator(CONNECT).click()

    expect(amy.locator("#message")).to_have_text("Timer not connected.")
    screen_solve_works(tom, amy)


def test_a_full_solve_on_a_gan_timer_as_the_halo_sends_it(tom_and_amy_with_a_halo):
    tom, amy = tom_and_amy_with_a_halo
    start_connected_inspection(tom, amy)
    advance(amy, 3000)

    send_gan(amy, gan.packet(gan.HANDS_ON))
    expect(amy.locator("#game")).not_to_have_attribute("data-ready", "true")
    send_gan(amy, gan.packet(gan.GET_SET))
    expect(amy.locator("#game")).to_have_attribute("data-ready", "true")
    send_gan(amy, gan.packet(gan.RUNNING))
    expect(amy.locator("#game")).to_have_attribute("data-phase", "solving")
    advance(amy, 9000)  # the browser's clock disagrees with the timer: the timer wins
    send_gan(amy, gan.packet(gan.STOPPED, 3775), gan.packet(gan.FINISHED))
    send_gan(amy, gan.packet(gan.IDLE, 0))  # the player resets the timer

    expect(amy.locator("#finished")).to_have_text("3.77")
    assert own_result(amy) == ["1st", "Amy (0)", "3.77"]
    assert emitted(amy, "start_solve") == 1 and emitted(amy, "stop_solve") == 1


def test_a_gan_time_over_a_minute(tom_and_amy_with_a_halo):
    tom, amy = tom_and_amy_with_a_halo
    start_connected_inspection(tom, amy)

    send_gan(amy, gan.packet(gan.RUNNING))
    expect(amy.locator("#game")).to_have_attribute("data-phase", "solving")
    send_gan(amy, gan.packet(gan.STOPPED, 67930))

    expect(amy.locator("#finished")).to_have_text("1:07.93")


def test_lifting_hands_too_soon_clears_ready(tom_and_amy_with_a_halo):
    tom, amy = tom_and_amy_with_a_halo
    start_connected_inspection(tom, amy)

    send_gan(amy, gan.packet(gan.GET_SET))
    expect(amy.locator("#game")).to_have_attribute("data-ready", "true")
    send_gan(amy, gan.packet(gan.HANDS_OFF))

    expect(amy.locator("#game")).not_to_have_attribute("data-ready", "true")
    expect(amy.locator("#game")).to_have_attribute("data-phase", "inspecting")


@pytest.mark.parametrize("how", ["__bt.drop()", "disconnect state"])
def test_losing_a_gan_timer_mid_solve_hands_it_to_the_screen(tom_and_amy_with_a_halo, how):
    tom, amy = tom_and_amy_with_a_halo
    start_connected_inspection(tom, amy)
    send_gan(amy, gan.packet(gan.RUNNING))
    expect(amy.locator("#game")).to_have_attribute("data-phase", "solving")
    advance(amy, 4000)

    if how == "__bt.drop()":
        amy.evaluate(how)
    else:
        send_gan(amy, gan.packet(gan.DISCONNECT))

    expect(amy.locator("#overlay-hint")).to_have_text(LOST_HINT)
    expect(amy.locator("#message")).to_have_text(LOST_MESSAGE)
    assert amy.evaluate("__bt.connected") is False
    advance(amy, 1000)
    amy.locator("#overlay").click()
    assert own_result(amy) == ["1st", "Amy (0)", "5.00"]


def test_with_timerlog_every_gan_packet_is_shown(tom_and_amy_with_a_halo):
    tom, amy = tom_and_amy_with_a_halo
    amy.goto(amy.url + "?timerlog")
    start_round(tom, amy)

    connect(amy)
    send_gan(amy, gan.packet(gan.GET_SET))

    expect(amy.locator("#timer-log-text")).to_have_value(
        re.compile("received " + bytes(gan.packet(gan.GET_SET)).hex())
    )
