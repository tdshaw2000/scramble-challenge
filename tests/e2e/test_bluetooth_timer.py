"""Connecting a Bluetooth timer and solving with it (openspec/specs/bluetooth-timer), against
the fake QiYi timer in fake_bluetooth.py."""

from tests.e2e import qiyi
from tests.e2e.fake_bluetooth import (
    FAKE_BLUETOOTH,
    NOTIFY,
    SERVICE,
    WRITE,
    send,
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
