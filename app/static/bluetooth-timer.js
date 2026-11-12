// Bluetooth speedcubing timers, through Web Bluetooth (Chrome and Edge, Android and desktop).
// challenge.js only sees neutral states from a connection: ready, running, stopped {timeMs},
// idle and disconnected. Each family of timers is a driver behind that; the first is QiYi
// (the QiYi Smart Timer, and the QiYi adapter fitted to a Speed Stacks timer).
//
// The QiYi protocol is our own implementation. csTimer (GPL) was used only as a description
// of how the timer behaves; no code was taken from it.
(function () {
  "use strict";

  // --- QiYi protocol ---------------------------------------------------------------------
  //
  // A message is: our sequence number (4 bytes), the number of the message it answers
  // (4 bytes), a command (2 bytes), the data's length (2 bytes), the data, and a
  // CRC16/MODBUS of all of that, high byte first. It is padded with 0x01 to whole 16-byte
  // blocks, and each block is AES-128-ECB encrypted with a fixed key. It travels as packets:
  // the first starts 0x00, the message length plus 2, 0x40, 0x00, and each later one starts
  // with its number (1, 2, ...). Every packet carries whole encrypted blocks.

  const QIYI_KEY = new Array(16).fill(0x77);
  const QIYI_HELLO = 0x0001;
  const QIYI_TIMER_DATA = 0x1003;
  const QIYI_HELLO_FIXED = [0, 0, 0, 0, 0, 0x21, 0x08, 0x00, 0x01, 0x05, 0x5a];
  const BLOCK = 16;

  let aes = null;
  function cipher() {
    if (!aes) aes = new window.aesjs.AES(QIYI_KEY);
    return aes;
  }

  function crc16modbus(bytes) {
    let crc = 0xffff;
    for (const byte of bytes) {
      crc ^= byte;
      for (let bit = 0; bit < 8; bit++) crc = crc & 1 ? (crc >>> 1) ^ 0xa001 : crc >>> 1;
    }
    return crc;
  }

  function u32(n) {
    return [(n >>> 24) & 0xff, (n >>> 16) & 0xff, (n >>> 8) & 0xff, n & 0xff];
  }

  function readU32(bytes, at) {
    return ((bytes[at] << 24) | (bytes[at + 1] << 16) | (bytes[at + 2] << 8) | bytes[at + 3]) >>> 0;
  }

  // The packets (arrays of bytes) to write to the timer for one message.
  function encode(sendSn, ackSn, cmd, data) {
    const body = [...u32(sendSn), ...u32(ackSn), cmd >> 8, cmd & 0xff, data.length >> 8, data.length & 0xff, ...data];
    const crc = crc16modbus(body);
    body.push(crc >> 8, crc & 0xff);
    const packets = [];
    for (let at = 0; at < body.length; at += BLOCK) {
      const block = body.slice(at, at + BLOCK);
      while (block.length < BLOCK) block.push(0x01);
      const header = at === 0 ? [0x00, body.length + 2, 0x40, 0x00] : [at / BLOCK];
      packets.push([...header, ...cipher().encrypt(block)]);
    }
    return packets;
  }

  // "QY-Adapter-2B0F" is at CC:A8:00:00:2B:0F, and "QY-Timer-ABCD" at CC:A1:00:00:AB:CD.
  // Reading the address from the advertisement instead would need a Chrome flag.
  function macFromName(name) {
    const match = /^QY-(Timer|Adapter).*-([0-9A-F]{2})([0-9A-F]{2})$/i.exec((name || "").trim());
    if (!match) return null;
    const prefix = match[1].toLowerCase() === "adapter" ? "CC:A8" : "CC:A1";
    return `${prefix}:00:00:${match[2]}:${match[3]}`.toUpperCase();
  }

  // The first message, which tells the timer which address it has (written backwards).
  function hello(mac) {
    const address = mac.split(":").map((part) => parseInt(part, 16)).reverse();
    return encode(1, 0, QIYI_HELLO, [...QIYI_HELLO_FIXED, ...address]);
  }

  // Joins packets from the timer back into messages. push() returns the message a packet
  // completes ({sendSn, ackSn, cmd, data}), or null while one is still arriving, or when a
  // packet is out of order or the CRC is wrong (the bad message is dropped).
  function reader() {
    let expected = 0; // the number of the packet a message in progress needs next
    let length = 0;
    let plain = [];

    function reset() {
      expected = 0;
      plain = [];
    }

    function push(packet) {
      let bytes = Array.from(packet);
      if (bytes[0] !== expected) {
        reset();
        if (bytes[0] !== 0) return null;
      }
      if (bytes[0] === 0) {
        length = bytes[1] - 2;
        bytes = bytes.slice(4);
      } else {
        bytes = bytes.slice(1);
      }
      if (bytes.length === 0 || bytes.length % BLOCK !== 0) {
        reset();
        return null;
      }
      for (let at = 0; at < bytes.length; at += BLOCK) {
        plain.push(...cipher().decrypt(bytes.slice(at, at + BLOCK)));
      }
      if (plain.length < length) {
        expected += 1;
        return null;
      }
      const message = plain.slice(0, length);
      reset();
      return decode(message);
    }

    return { push };
  }

  function decode(message) {
    if (message.length < 14) return null;
    const dataLength = (message[10] << 8) | message[11];
    if (message.length < 14 + dataLength) return null;
    const body = message.slice(0, 12 + dataLength);
    const crc = (message[12 + dataLength] << 8) | message[13 + dataLength];
    if (crc16modbus(body) !== crc) return null;
    return {
      sendSn: readU32(message, 0),
      ackSn: readU32(message, 4),
      cmd: (message[8] << 8) | message[9],
      data: message.slice(12, 12 + dataLength),
    };
  }

  // Timer data comes as a data point: its id, its type, a 2-byte length, then the value.
  // Point 4 (type 4) is the timer's state and its time so far; point 1 (type 1) is the
  // record of a finished solve, which the timer resends until it is answered.
  // The timer's own inspection state is ignored: the round's inspection is on the screen.
  const QIYI_STATES = ["idle", "idle", "ready", "running", "stopped", "stopped", "disconnected"];

  // The neutral state a message from the timer means, or null if it means nothing to us.
  function parse(message) {
    if (!message || message.cmd !== QIYI_TIMER_DATA || message.data.length < 4) return null;
    const data = message.data;
    const [point, type] = data;
    if (point === 1 && type === 1 && data.length >= 12) {
      return { state: "stopped", timeMs: readU32(data, 8), ack: true };
    }
    if (point === 4 && type === 4 && data.length >= 9) {
      const state = QIYI_STATES[data[4]];
      if (state === "stopped") {
        const timeMs = readU32(data, 5);
        return timeMs > 0 ? { state, timeMs } : null;
      }
      return state ? { state } : null;
    }
    return null;
  }

  // The answer to a record message, so the timer stops resending it.
  function ack(message) {
    return encode(message.ackSn + 1, message.sendSn, QIYI_TIMER_DATA, [0x00]);
  }

  // --- connecting ------------------------------------------------------------------------

  // Web Bluetooth: Chrome and Edge on Android and desktop. Not Safari, nor any iPhone browser.
  function supported() {
    return Boolean(navigator.bluetooth && navigator.bluetooth.requestDevice);
  }

  window.BluetoothTimer = {
    supported,
    qiyi: { ack, crc16modbus, encode, hello, macFromName, parse, reader },
  };
})();
