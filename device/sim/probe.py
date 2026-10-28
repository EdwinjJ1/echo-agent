#!/usr/bin/env python3
"""A minimal host for checking a device without echo agent: does the handshake, shows what the device sends,
and lets you set the light by hand. Works with real boards (their USB serial port) and with sim.py.

    python3 device/sim/probe.py /dev/cu.usbmodem1101          # macOS
    python3 device/sim/probe.py /dev/ttyACM0                  # Linux
    python3 device/sim/probe.py "$TMPDIR/echo-device-sim"     # the simulator

Then type a light (idle, listening, working, waiting, done, failed) to send a status event, or quit.
"""

from __future__ import annotations

import os
import select
import sys
import termios
import threading
import time
import tty
import base64

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import echo_device as proto  # noqa: E402


class Probe:
    """The host side of the USB protocol, just enough to test a device."""

    def __init__(self, fd: int, log=print, host_name: str = "probe") -> None:
        self.fd = fd
        self.log = log
        self.host_name = host_name
        self.hello: dict | None = None
        self.mic: dict | None = None
        self.gesture = proto.Gesture()
        self.gestures: list[str] = []
        self.voice_samples = 0
        self.voice_bytes = 0
        self.voice_ends = 0
        self.changed = threading.Condition()
        self.reader = proto.LineReader()
        self.seq = 0
        self.running = True
        self.write_lock = threading.Lock()
        self.thread = threading.Thread(target=self._read, daemon=True)

    def start(self) -> None:
        self.thread.start()
        self.send(proto.event("sync"))

    def stop(self) -> None:
        self.running = False

    def send(self, message: dict) -> None:
        data = proto.encode(message)
        with self.write_lock:
            view = memoryview(data)
            while view:
                try:
                    view = view[os.write(self.fd, view):]
                except BlockingIOError:
                    select.select([], [self.fd], [], 0.05)

    def status(self, light: str, working: int = 0, waiting: int = 0, latest: dict | None = None) -> None:
        self.seq += 1
        self.send(proto.event("status", {"seq": self.seq, "light": light, "working": working, "waiting": waiting, "latest": latest}))

    def wait_for(self, check, timeout: float = 10) -> bool:
        with self.changed:
            return self.changed.wait_for(check, timeout)

    def _read(self) -> None:
        while self.running:
            try:
                ready, _, _ = select.select([self.fd], [], [], 0.5)
                if not ready:
                    continue
                data = os.read(self.fd, 65536)
            except (BlockingIOError, InterruptedError):
                continue
            except OSError:
                self.log("the device went away")
                return
            if not data:
                time.sleep(0.1)
                continue
            for line in self.reader.feed(data):
                message = proto.decode(line)
                if message is None:
                    self.log("(device log) " + line)
                else:
                    self._handle(message)

    def _handle(self, message: dict) -> None:
        with self.changed:
            if message.get("m") == "hello":
                params = message.get("p", {})
                self.hello = params
                self.mic = proto.choose_mic(params.get("caps", {}))
                result = {"v": proto.VERSION, "host": {"name": self.host_name, "app": "probe", "version": "1"},
                          "now": int(time.time() * 1000), "features": ["status", "approve"] + (["voice"] if self.mic else [])}
                if self.mic:
                    result["mic"] = self.mic
                self.send(proto.reply(message["id"], result))
                self.status("idle")
                device = params.get("device", {})
                self.log("hello from %s %s (fw %s), caps %s, mic %s" % (device.get("model"), device.get("id"), device.get("fw"),
                                                                       sorted(params.get("caps", {})), self.mic))
            elif message.get("ev") == "button":
                d = message.get("d", {})
                meaning = self.gesture.handle(d.get("action", ""), float(d.get("t", time.monotonic() * 1000)))
                if meaning:
                    self.gestures.append(meaning)
                    self.log("key: %s" % meaning)
            elif message.get("m") == "voice.begin":
                self.voice_samples = self.voice_bytes = 0
                self.send(proto.reply(message["id"], {"sid": message.get("p", {}).get("sid")}))
            elif message.get("ev") == "voice.chunk":
                data = base64.b64decode(message.get("d", {}).get("data", ""))
                self.voice_bytes += len(data)
                if (self.mic or {}).get("codec", "pcm16") == "pcm16":
                    self.voice_samples += len(data) // 2
            elif message.get("m") == "voice.end":
                self.voice_ends += 1
                seconds = self.voice_samples / proto.RATE
                self.log("voice: %d bytes%s" % (self.voice_bytes, ", %.1f s" % seconds if self.voice_samples else ""))
                self.send(proto.reply(message["id"], {"text": ""}))
            elif "m" in message:
                self.send(proto.error(message["id"], "unknown_method"))
            elif "ev" in message:
                self.log("event: %s %s" % (message["ev"], message.get("d")))
            self.changed.notify_all()


def open_serial(path: str) -> int:
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    tty.setraw(fd)
    attrs = termios.tcgetattr(fd)
    attrs[4] = attrs[5] = termios.B115200
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    return fd


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    fd = open_serial(sys.argv[1])
    probe = Probe(fd)
    probe.start()
    if not probe.wait_for(lambda: probe.hello is not None, 1.5 * 3):
        print("no hello: is this an echo device? (it has to answer {\"ev\":\"sync\"} with hello)")
    try:
        while True:
            line = input().strip()
            if line in ("quit", "exit"):
                return 0
            if line in proto.LIGHTS:
                probe.status(line, working=1 if line == "working" else 0, waiting=1 if line == "waiting" else 0)
            elif line:
                print("type a light (%s) or quit" % ", ".join(proto.LIGHTS))
    except (EOFError, KeyboardInterrupt):
        return 0
    finally:
        probe.stop()
        os.close(fd)


if __name__ == "__main__":
    sys.exit(main())
