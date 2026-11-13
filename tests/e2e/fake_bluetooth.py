"""A fake `navigator.bluetooth` with one timer in it, for the browser tests: a QiYi timer, or a
GAN timer when its name starts GAN.

Installed with add_init_script before the page loads. The test drives it through
window.__bt:
  __bt.name           the timer's advertised name (set before connecting)
  __bt.cancel         true: the device chooser is cancelled
  __bt.failConnect    true: the GATT connection fails
  __bt.options        what the page asked the chooser for
  __bt.written        every packet the page wrote to the timer, as arrays of bytes
  __bt.connected      whether the page is connected
  __bt.send(packets)  the timer sends [[header, [plain block, ...]], ...] (from qiyi.packets);
                      each block is encrypted here with the vendored AES library
  __bt.sendGan(bytes) a GAN timer sends one packet, as gan.packet() builds it
  __bt.drop()         the timer goes away (switched off, out of range)
"""

from tests.e2e import gan, qiyi

SERVICE = "0000fd50-0000-1000-8000-00805f9b34fb"
WRITE = "00000001-0000-1001-8001-00805f9b07d0"
NOTIFY = "00000002-0000-1001-8001-00805f9b07d0"

FAKE_BLUETOOTH = (
    """
(() => {
  const SERVICE = "__SERVICE__", WRITE = "__WRITE__", NOTIFY = "__NOTIFY__";
  const GAN_SERVICE = "__GAN_SERVICE__", GAN_STATE = "__GAN_STATE__";
  const bt = (window.__bt = {
    name: "QY-Adapter-2B0F", cancel: false, failConnect: false, options: null,
    written: [], connected: false,
  });

  const notify = new EventTarget();
  notify.uuid = NOTIFY;
  notify.value = null;
  notify.startNotifications = async () => notify;
  notify.stopNotifications = async () => notify;

  const write = { uuid: WRITE };
  write.writeValue = async (value) => {
    if (!bt.connected) throw new DOMException("GATT Server is disconnected.", "NetworkError");
    const bytes = value instanceof ArrayBuffer ? new Uint8Array(value)
      : new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
    bt.written.push(Array.from(bytes));
  };
  write.writeValueWithResponse = write.writeValue;
  write.writeValueWithoutResponse = write.writeValue;

  const service = {
    uuid: SERVICE,
    getCharacteristic: async (uuid) => {
      if (uuid === WRITE) return write;
      if (uuid === NOTIFY) return notify;
      throw new DOMException("No Characteristics matching UUID " + uuid, "NotFoundError");
    },
  };
  service.getCharacteristics = async () => [write, notify];

  // A GAN timer has its own service, with one characteristic that notifies its state.
  const ganState = new EventTarget();
  ganState.uuid = GAN_STATE;
  ganState.value = null;
  ganState.startNotifications = async () => ganState;
  ganState.stopNotifications = async () => ganState;
  const ganService = {
    uuid: GAN_SERVICE,
    getCharacteristic: async (uuid) => {
      if (uuid === GAN_STATE) return ganState;
      throw new DOMException("No Characteristics matching UUID " + uuid, "NotFoundError");
    },
  };
  const isGan = () => bt.name.startsWith("GAN");

  const device = new EventTarget();
  const server = {
    device,
    get connected() { return bt.connected; },
    connect: async () => {
      if (bt.failConnect) throw new DOMException("Connection failed.", "NetworkError");
      bt.connected = true;
      return server;
    },
    disconnect: () => {
      if (!bt.connected) return;
      bt.connected = false;
      device.dispatchEvent(new Event("gattserverdisconnected"));
    },
    getPrimaryService: async (uuid) => {
      if (!bt.connected) throw new DOMException("GATT Server is disconnected.", "NetworkError");
      if (isGan() && uuid === GAN_SERVICE) return ganService;
      if (!isGan() && (uuid === SERVICE || uuid === 0xfd50)) return service;
      throw new DOMException("No Services matching UUID " + uuid, "NotFoundError");
    },
  };
  device.gatt = server;
  Object.defineProperty(device, "name", { get: () => bt.name });
  device.id = "fake-timer";

  bt.send = (packets) => {
    const aes = new aesjs.AES(Array(16).fill(0x77));
    for (const [header, blocks] of packets) {
      const bytes = header.concat(...blocks.map((block) => Array.from(aes.encrypt(block))));
      notify.value = new DataView(new Uint8Array(bytes).buffer);
      notify.dispatchEvent(new Event("characteristicvaluechanged"));
    }
  };
  bt.sendGan = (bytes) => {
    ganState.value = new DataView(new Uint8Array(bytes).buffer);
    ganState.dispatchEvent(new Event("characteristicvaluechanged"));
  };
  bt.drop = () => server.disconnect();

  Object.defineProperty(navigator, "bluetooth", {
    configurable: true,
    value: {
      getAvailability: async () => true,
      requestDevice: async (options) => {
        bt.options = JSON.parse(JSON.stringify(options));
        if (bt.cancel) {
          throw new DOMException("User cancelled the requestDevice() chooser.", "NotFoundError");
        }
        return device;
      },
    },
  });
})();
""".replace("__SERVICE__", SERVICE)
    .replace("__WRITE__", WRITE)
    .replace("__NOTIFY__", NOTIFY)
    .replace("__GAN_SERVICE__", gan.SERVICE)
    .replace("__GAN_STATE__", gan.STATE)
)

NO_BLUETOOTH = """
  delete Navigator.prototype.bluetooth;
  delete navigator.bluetooth;
"""

# Records the name of every Socket.IO event the page sends, in window.__emitted, by wrapping
# io() as the Socket.IO script defines it.
RECORD_EMITS = """
(() => {
  window.__emitted = [];
  let real;
  Object.defineProperty(window, "io", {
    configurable: true,
    get: () => real,
    set: (io) => {
      real = (...args) => {
        const socket = io(...args);
        const emit = socket.emit.bind(socket);
        socket.emit = (event, ...rest) => {
          window.__emitted.push(event);
          return emit(event, ...rest);
        };
        return socket;
      };
      Object.assign(real, io);
    },
  });
})();
"""

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


def send(page, msg):
    """The fake timer sends one message."""
    page.evaluate("(packets) => __bt.send(packets)", [list(p) for p in qiyi.packets(msg)])


def written_messages(page):
    """Every message the page wrote to the timer, decrypted and unpadded, as qiyi.message()
    would build it."""
    decrypted = page.evaluate(DECRYPT_PACKETS, page.evaluate("__bt.written"))
    messages, current, length = [], [], 0
    for header, blocks in decrypted:
        if header[0] == 0:
            current, length = [], header[1] - 2
        for block in blocks:
            current += block
        if len(current) >= length:
            messages.append(current[:length])
    return messages


def send_gan(page, *packets):
    """The fake GAN timer sends these packets (from gan.packet), in order."""
    for packet in packets:
        page.evaluate("(bytes) => __bt.sendGan(bytes)", packet)
