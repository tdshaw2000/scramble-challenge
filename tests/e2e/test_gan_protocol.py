"""The GAN timer protocol (bluetooth-timer.js), checked against real packets from the owner's
GAN Halo and against gan.py, run in a real browser."""

from pathlib import Path

import pytest

from tests.e2e import gan

CAPTURE = Path(__file__).parent / "fixtures" / "gan-halo-nrf-2026-11-13.log"


def capture():
    """[(packet bytes, what the timer was doing, the time if it carried one), ...]"""
    rows = []
    for line in CAPTURE.read_text().splitlines():
        if line.startswith("#"):
            continue
        _, data, doing, *time_ms = line.split()
        rows.append((list(bytes.fromhex(data)), doing, int(time_ms[0]) if time_ms else None))
    return rows


@pytest.fixture
def page(new_player):
    page = new_player()
    page.goto("/")
    page.add_script_tag(url="/static/bluetooth-timer.js")
    return page


def parse(page, packet):
    return page.evaluate("(packet) => BluetoothTimer.gan.parse(packet)", packet)


# --- gan.py, the tests' own description, against the real timer ---------------------------

STATES = {
    "hands-on": gan.HANDS_ON,
    "get-set": gan.GET_SET,
    "running": gan.RUNNING,
    "stopped": gan.STOPPED,
    "finished": gan.FINISHED,
    "idle": gan.IDLE,
}


def test_gan_py_builds_every_real_packet_byte_for_byte():
    for data, doing, time_ms in capture():
        if doing == "idle":
            time_ms = 0  # the reset after a solve carries a zero time
        assert gan.packet(STATES[doing], time_ms) == data


def test_the_real_capture_holds_the_three_solves_the_halo_displayed():
    times = [time_ms for _, doing, time_ms in capture() if doing == "stopped"]
    assert times == [3775, 4601, 67930]  # 3.775, 4.601 and 1:07.930 on the Halo's display


# --- the page's parser ---------------------------------------------------------------------


def test_crc16_ccitt_matches_the_standard_check_value(page):
    check = page.evaluate(
        "BluetoothTimer.gan.crc16ccitt([...'123456789'].map((c) => c.charCodeAt(0)))"
    )
    assert check == 0x29B1
    assert gan.crc16_ccitt(b"123456789") == 0x29B1


MEANINGS = {
    "hands-on": {"state": "idle"},
    "get-set": {"state": "ready"},
    "running": {"state": "running"},
    "finished": None,  # the stop before it already ended the solve
    "idle": {"state": "idle"},
}


def test_every_real_packet_means_what_the_timer_was_doing(page):
    for data, doing, time_ms in capture():
        expected = (
            {"state": "stopped", "timeMs": time_ms} if doing == "stopped" else MEANINGS[doing]
        )
        assert parse(page, data) == expected, doing


@pytest.mark.parametrize(
    ("state", "time_ms", "expected"),
    [
        (gan.HANDS_OFF, None, {"state": "idle"}),  # lifted before the timer was ready
        (gan.DISCONNECT, None, {"state": "disconnected"}),
        (gan.STOPPED, 0, None),  # no time to record
        (gan.STOPPED, None, None),
        (gan.STOPPED, 59_999, {"state": "stopped", "timeMs": 59_999}),
        (gan.STOPPED, 10 * 60_000 + 1, {"state": "stopped", "timeMs": 600_001}),
        (gan.IDLE, 0, {"state": "idle"}),
        (99, None, None),
    ],
)
def test_other_states_and_times(page, state, time_ms, expected):
    assert parse(page, gan.packet(state, time_ms)) == expected


def test_a_packet_that_fails_its_check_or_is_cut_short_means_nothing(page):
    stop = gan.packet(gan.STOPPED, 3775)
    corrupt = stop[:-1] + [stop[-1] ^ 0xFF]
    wrong_time = stop[:5] + [stop[5] + 1] + stop[6:]

    assert parse(page, corrupt) is None
    assert parse(page, wrong_time) is None
    assert parse(page, stop[:-1]) is None
    assert parse(page, [0x00] + stop[1:]) is None
    assert parse(page, []) is None
