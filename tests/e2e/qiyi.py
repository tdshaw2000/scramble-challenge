"""A second, independent description of the QiYi timer protocol, for the tests.

The page's own code (app/static/bluetooth-timer.js) is checked against this one. Here the
messages are built in Python up to the plain 16-byte blocks; the browser side of the fake
timer (FAKE_BLUETOOTH in tests/e2e/test_bluetooth_timer.py) only encrypts each block with
the vendored AES library, which test_bluetooth_protocol.py checks against FIPS-197.

A message is: our sequence number (4 bytes), the number of the message it answers (4 bytes),
a command (2 bytes), the data's length (2 bytes), the data, then a CRC16/MODBUS of all that
(high byte first). It is padded with 0x01 bytes to whole 16-byte blocks. It travels as one or
more packets: the first starts 0x00, the message length plus 2, 0x40, 0x00; the rest start
with their number (1, 2, ...). Each block is AES-128-ECB encrypted with sixteen 0x77 bytes.
"""

FIXED_KEY = [0x77] * 16
HELLO = 0x0001
TIMER_DATA = 0x1003

# The timer's states, by the number it sends in a status message.
IDLE, INSPECTION, GET_SET, RUNNING, FINISHED, STOPPED, DISCONNECT = range(7)


def crc16_modbus(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def u32(n):
    return [(n >> 24) & 0xFF, (n >> 16) & 0xFF, (n >> 8) & 0xFF, n & 0xFF]


def message(send_sn, ack_sn, cmd, data):
    body = u32(send_sn) + u32(ack_sn) + [cmd >> 8, cmd & 0xFF, len(data) >> 8, len(data) & 0xFF]
    body += list(data)
    crc = crc16_modbus(body)
    return body + [crc >> 8, crc & 0xFF]


def packets(msg, blocks_per_packet=1):
    """[(header, [plain 16-byte block, ...]), ...] ready for the fake to encrypt and send."""
    padded = msg + [0x01] * (-len(msg) % 16)
    blocks = [padded[i : i + 16] for i in range(0, len(padded), 16)]
    out = []
    for n, i in enumerate(range(0, len(blocks), blocks_per_packet)):
        header = [0x00, len(msg) + 2, 0x40, 0x00] if n == 0 else [n]
        out.append((header, blocks[i : i + blocks_per_packet]))
    return out


def hello_data(mac):
    """What the app says first: a fixed part, then the timer's address backwards."""
    address = [int(part, 16) for part in mac.split(":")]
    return [0, 0, 0, 0, 0, 0x21, 0x08, 0x00, 0x01, 0x05, 0x5A] + address[::-1]


def status(state, time_ms=0, send_sn=1, ack_sn=1):
    """The timer telling the app its state (data point 4, type 4), with the time so far."""
    data = [4, 4, 0, 5, state] + u32(time_ms)
    return message(send_sn, ack_sn, TIMER_DATA, data)


def record(solve_ms, inspect_ms=0, send_sn=7, ack_sn=3):
    """The timer reporting a finished solve (data point 1, type 1). The app must answer it."""
    data = [1, 1, 0, 12] + [0, 0, 0, 0] + u32(solve_ms) + u32(inspect_ms)
    return message(send_sn, ack_sn, TIMER_DATA, data)
