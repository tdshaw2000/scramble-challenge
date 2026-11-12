"""The QiYi timer protocol's building blocks (bluetooth-timer.js), run in a real browser.

Each block of a QiYi message is AES-128 encrypted with a fixed, publicly known key (sixteen
0x77 bytes). The vendored AES library is checked against the FIPS-197 test vector first, so
the fake timer in the other tests, which uses the same library, can be trusted.
"""

import re
from pathlib import Path

import pytest

from tests.e2e import qiyi

VENDOR = Path(__file__).resolve().parents[2] / "app" / "static" / "vendor"
FIXED_KEY = [0x77] * 16


@pytest.fixture
def aes_page(new_player):
    page = new_player()
    page.goto("/")
    page.add_script_tag(url="/static/vendor/aes.js")
    return page


@pytest.fixture
def page(aes_page):
    aes_page.add_script_tag(url="/static/bluetooth-timer.js")
    return aes_page


def test_the_aes_library_is_vendored_with_its_licence_and_pinned_version():
    library = (VENDOR / "aes.js").read_text()
    assert re.search(r"aes-js v\d+\.\d+\.\d+", library)
    assert "MIT" in (VENDOR / "LICENSE-aes-js.txt").read_text()


def test_the_aes_library_matches_the_fips_197_test_vector(aes_page):
    encrypted = aes_page.evaluate(
        """() => {
          const key = Array.from({ length: 16 }, (_, i) => i);
          const plain = aesjs.utils.hex.toBytes("00112233445566778899aabbccddeeff");
          return aesjs.utils.hex.fromBytes(new aesjs.AES(key).encrypt(plain));
        }"""
    )
    assert encrypted == "69c4e0d86a7b0430d8cdb78070b4c55a"


def test_one_block_encrypted_with_the_fixed_key_decrypts_to_the_original(aes_page):
    block = list(range(16))
    result = aes_page.evaluate(
        """([key, block]) => {
          const aes = new aesjs.AES(key);
          const encrypted = Array.from(aes.encrypt(block));
          return { encrypted, decrypted: Array.from(aes.decrypt(encrypted)) };
        }""",
        [FIXED_KEY, block],
    )
    assert result["encrypted"] != block
    assert result["decrypted"] == block


# --- CRC, framing and encryption ---------------------------------------------------------

# Decrypts packets the page built, so the test can compare them with qiyi.py's plain ones.
DECRYPT_PACKETS = """(packets) => {
  const aes = new aesjs.AES(Array(16).fill(0x77));
  return packets.map((packet) => {
    const bytes = Array.from(packet);
    const header = bytes.slice(0, bytes[0] === 0 ? 4 : 1);
    const blocks = [];
    for (let i = header.length; i < bytes.length; i += 16) {
      blocks.push(Array.from(aes.decrypt(bytes.slice(i, i + 16))));
    }
    return [header, blocks];
  });
}"""

# Encrypts qiyi.py's plain packets the way a real timer sends them.
ENCRYPT_PACKETS = """(packets) => {
  const aes = new aesjs.AES(Array(16).fill(0x77));
  return packets.map(([header, blocks]) =>
    header.concat(...blocks.map((block) => Array.from(aes.encrypt(block)))));
}"""


def as_lists(packets):
    return [[header, blocks] for header, blocks in packets]


def test_crc16_modbus_matches_the_standard_check_value(page):
    assert page.evaluate("BluetoothTimer.qiyi.crc16modbus([])") == 0xFFFF
    check = page.evaluate(
        "BluetoothTimer.qiyi.crc16modbus([...'123456789'].map((c) => c.charCodeAt(0)))"
    )
    assert check == 0x4B37
    assert qiyi.crc16_modbus(b"123456789") == 0x4B37


def test_a_short_message_is_one_encrypted_packet(page):
    built = page.evaluate("BluetoothTimer.qiyi.encode(5, 9, 0x1003, [0])")

    assert len(built) == 1 and len(built[0]) == 4 + 16
    expected = qiyi.packets(qiyi.message(5, 9, qiyi.TIMER_DATA, [0]))
    assert page.evaluate(DECRYPT_PACKETS, built) == as_lists(expected)


def test_the_hello_for_the_owners_adapter_spans_two_packets(page):
    mac = "CC:A8:00:00:2B:0F"
    built = page.evaluate("(mac) => BluetoothTimer.qiyi.hello(mac)", mac)

    expected = qiyi.packets(qiyi.message(1, 0, qiyi.HELLO, qiyi.hello_data(mac)))
    assert page.evaluate(DECRYPT_PACKETS, built) == as_lists(expected)
    # The address goes in backwards, as the adapter itself advertises it.
    assert qiyi.hello_data(mac)[-6:] == [0x0F, 0x2B, 0x00, 0x00, 0xA8, 0xCC]
    assert [header for header, _ in expected] == [[0x00, 31 + 2, 0x40, 0x00], [0x01]]


def read(page, packets):
    """What the page's reader makes of these packets, fed in order: one result per packet."""
    return page.evaluate(
        """(packets) => {
          const reader = BluetoothTimer.qiyi.reader();
          return packets.map((packet) => reader.push(packet));
        }""",
        page.evaluate(ENCRYPT_PACKETS, as_lists(packets)),
    )


def test_the_reader_decrypts_a_message_and_checks_its_crc(page):
    msg = qiyi.status(qiyi.RUNNING, 1234, send_sn=6, ack_sn=2)

    *arriving, done = read(page, qiyi.packets(msg))
    assert arriving == [None]
    assert done == {"sendSn": 6, "ackSn": 2, "cmd": 0x1003, "data": msg[12:-2]}


def test_the_reader_joins_a_message_split_over_packets(page):
    msg = qiyi.record(12345)
    assert len(msg) > 16

    results = read(page, qiyi.packets(msg))
    assert results[0] is None
    assert results[1]["data"] == msg[12:-2]


def test_the_reader_takes_several_blocks_in_one_packet(page):
    msg = qiyi.record(12345)

    assert read(page, qiyi.packets(msg, blocks_per_packet=2))[0]["data"] == msg[12:-2]


def test_the_reader_drops_a_message_with_a_bad_crc(page):
    msg = qiyi.status(qiyi.RUNNING, 1234)
    msg[-1] ^= 0xFF

    assert read(page, qiyi.packets(msg)) == [None, None]


def test_the_reader_ignores_a_stray_follow_on_packet_and_recovers(page):
    long_msg, short_msg = qiyi.record(12345), qiyi.status(qiyi.IDLE)
    stray = qiyi.packets(long_msg)[1]

    results = read(page, [stray, *qiyi.packets(short_msg)])
    assert results[:-1] == [None, None]
    assert results[-1]["data"] == short_msg[12:-2]


# --- what the timer's messages mean ------------------------------------------------------


def meaning(page, msg):
    """The neutral state the page reads from one whole message from the timer."""
    return page.evaluate(
        """(packets) => {
          const reader = BluetoothTimer.qiyi.reader();
          let message = null;
          for (const packet of packets) message = reader.push(packet) || message;
          return BluetoothTimer.qiyi.parse(message);
        }""",
        page.evaluate(ENCRYPT_PACKETS, as_lists(qiyi.packets(msg))),
    )


@pytest.mark.parametrize(
    ("state", "time_ms", "expected"),
    [
        (qiyi.IDLE, 0, {"state": "idle"}),
        (qiyi.INSPECTION, 0, {"state": "idle"}),  # the round's inspection is the screen's
        (qiyi.GET_SET, 0, {"state": "ready"}),
        (qiyi.RUNNING, 0, {"state": "running"}),
        (qiyi.RUNNING, 3456, {"state": "running"}),
        (qiyi.STOPPED, 12345, {"state": "stopped", "timeMs": 12345}),
        (qiyi.FINISHED, 12345, {"state": "stopped", "timeMs": 12345}),
        (qiyi.STOPPED, 0, None),  # no time to record
        (qiyi.DISCONNECT, 0, {"state": "disconnected"}),
        (99, 0, None),
    ],
)
def test_status_messages_map_to_neutral_states(page, state, time_ms, expected):
    assert meaning(page, qiyi.status(state, time_ms)) == expected


def test_a_record_message_is_a_stop_with_the_final_time_and_must_be_answered(page):
    assert meaning(page, qiyi.record(12345, inspect_ms=8000)) == {
        "state": "stopped",
        "timeMs": 12345,
        "ack": True,
    }


def test_the_answer_to_a_record_message_follows_on_from_it(page):
    record = qiyi.record(12345, send_sn=7, ack_sn=3)
    built = page.evaluate(
        """(message) => BluetoothTimer.qiyi.ack(message)""",
        {"sendSn": 7, "ackSn": 3, "cmd": qiyi.TIMER_DATA, "data": record[12:-2]},
    )

    expected = qiyi.packets(qiyi.message(4, 7, qiyi.TIMER_DATA, [0]))
    assert page.evaluate(DECRYPT_PACKETS, built) == as_lists(expected)


def test_other_messages_mean_nothing(page):
    assert meaning(page, qiyi.message(2, 1, qiyi.HELLO, [0])) is None
    assert meaning(page, qiyi.message(2, 1, qiyi.TIMER_DATA, [9, 9, 0, 0])) is None
    assert page.evaluate("BluetoothTimer.qiyi.parse(null)") is None
