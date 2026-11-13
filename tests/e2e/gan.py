"""A second, independent description of the GAN timer protocol (GAN Halo, GAN Smart Timer),
for the tests. The page's own code (app/static/bluetooth-timer.js) is checked against this one,
and this one against real packets from the owner's Halo (fixtures/gan-halo-nrf-2026-11-13.log).

The timer notifies its state on characteristic fff5 of service fff0, unencrypted, and needs
nothing written to it. A packet is 0xFE, the number of bytes after this one, 0x01, the state,
for a stop the time (minutes, seconds, then milliseconds as 2 bytes low first), and a
CRC16-CCITT (start 0xFFFF, polynomial 0x1021) of everything after the length byte, low first.
"""

SERVICE = "0000fff0-0000-1000-8000-00805f9b34fb"
STATE = "0000fff5-0000-1000-8000-00805f9b34fb"

# The timer's states, by the number it sends.
DISCONNECT, GET_SET, HANDS_OFF, RUNNING, STOPPED, IDLE, HANDS_ON, FINISHED = range(8)


def crc16_ccitt(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def time_bytes(time_ms):
    minutes, rest = divmod(time_ms, 60_000)
    seconds, ms = divmod(rest, 1000)
    return [minutes, seconds, ms & 0xFF, ms >> 8]


def packet(state, time_ms=None):
    """The bytes the timer sends for this state; a time is sent with STOPPED and IDLE."""
    body = [0x01, state] + ([] if time_ms is None else time_bytes(time_ms))
    crc = crc16_ccitt(body)
    return [0xFE, len(body) + 2] + body + [crc & 0xFF, crc >> 8]
