#!/usr/bin/env python3
"""A simulated echo agent device, so the USB mode can be run without hardware.

It opens a pseudo-terminal that behaves like the device's USB serial port and links it at --link.
Start echo agent with ECHO_DEVICE_PORT=<link> and it treats the simulator like a plugged-in device.
The simulator's microphone is `stream` (audio as voice.* over the serial port); a real board can also be a USB microphone.

    python3 device/sim/sim.py --link /tmp/echo-device                 # then type commands
    python3 device/sim/sim.py --link /tmp/echo-device --script "wait connected 30; hold hello.wav; wait light=working 10"

Commands (interactive, or ;-separated in --script):
    hold <file.wav | seconds>   hold the key and talk (a wav, or that many seconds of a tone); release when it ends
    tap                         a short press (approves what is waiting)
    wait connected [timeout]    until the host has answered hello
    wait light=<light> [timeout]
    sleep <seconds>
    status                      print the last status
    quit
"""

from __future__ import annotations

import argparse
import os
import secrets
import select
import shlex
import sys
import termios
import threading
import time
import tty

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import echo_device as proto  # noqa: E402


class SimDevice:
    """The device side of the protocol over a file descriptor (the pty master)."""

    def __init__(self, fd: int, identity: proto.Identity, caps: proto.Caps, log=print, realtime: bool = True) -> None:
        self.fd = fd
        self.identity = identity
        self.caps = caps
        self.log = log
        self.realtime = realtime
        self.status = proto.Status()
        self.host: dict | None = None
        self.mic: dict | None = None
        self.replies: dict[str, dict] = {}
        self.changed = threading.Condition()
        self.started = time.monotonic()
        self.next_id = 0
        self.last_status = 0.0
        self.write_lock = threading.Lock()
        self.reader = proto.LineReader()
        self.running = True
        self.thread = threading.Thread(target=self._read, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.running = False

    # ------------------------------------------------------------ sending

    def now(self) -> int:
        return int((time.monotonic() - self.started) * 1000)

    def send(self, message: dict) -> None:
        data = proto.encode(message)
        with self.write_lock:
            view = memoryview(data)
            while view:
                try:
                    n = os.write(self.fd, view)
                    view = view[n:]
                except BlockingIOError:
                    select.select([], [self.fd], [], 0.05)

    def call(self, method: str, params: dict | None = None) -> str:
        self.next_id += 1
        id = str(self.next_id)
        self.send(proto.request(id, method, params))
        return id

    def wait_reply(self, id: str, timeout: float = 10) -> dict | None:
        with self.changed:
            self.changed.wait_for(lambda: id in self.replies, timeout)
            return self.replies.pop(id, None)

    def hello(self) -> None:
        self.call("hello", proto.hello_params(self.identity, self.caps))

    def button(self, action: str, t: int | None = None) -> None:
        self.send(proto.event("button", {"action": action, "t": self.now() if t is None else t}))

    # ------------------------------------------------------------ gestures

    def hold(self, samples: list[int]) -> str | None:
        """Hold the key while the audio plays, then release. Returns the words the host heard."""
        start = self.now()
        self.button("down", start)
        sid = None
        if self.mic and self.mic.get("via") == "stream":
            sid = "s%d" % self.now()
            codec = self.mic.get("codec", "pcm16")
            self.call("voice.begin", {"sid": sid, "codec": codec, "rate": proto.RATE})
            encoder = proto.OpusEncoder() if codec == "opus" else None
            n = 0
            pieces = list(proto.chunks(samples))
            for i, piece in enumerate(pieces):
                if encoder:
                    data = proto.frame_packets(encoder.encode(piece, flush=i == len(pieces) - 1))
                else:
                    data = proto.pcm16_bytes(piece)
                if data:
                    n += 1
                    self.send(proto.event("voice.chunk", {"sid": sid, "n": n, "data": proto.b64(data)}))
                if self.realtime:
                    time.sleep(len(piece) / proto.RATE)
        elif self.realtime:
            time.sleep(len(samples) / proto.RATE)
        # the device clock moves with the audio even when we send it faster than real time
        self.button("up", max(self.now(), start + len(samples) * 1000 // proto.RATE))
        if sid is None:
            return None
        reply = self.wait_reply(self.call("voice.end", {"sid": sid}), timeout=30)
        return (reply or {}).get("r", {}).get("text")

    def tap(self) -> None:
        start = self.now()
        self.button("down", start)
        sid = None
        if self.mic and self.mic.get("via") == "stream":
            sid = "s%d" % start
            self.call("voice.begin", {"sid": sid, "codec": self.mic.get("codec", "pcm16"), "rate": proto.RATE})
        time.sleep(0.12)
        self.button("up", start + 120)
        if sid:
            self.call("voice.end", {"sid": sid})

    # ------------------------------------------------------------ waiting

    def wait_for(self, check, timeout: float) -> bool:
        with self.changed:
            return self.changed.wait_for(check, timeout)

    def connected(self) -> bool:
        return self.host is not None and time.monotonic() - self.last_status < proto.HOST_TIMEOUT_S

    # ------------------------------------------------------------ receiving

    def _read(self) -> None:
        while self.running:
            try:
                ready, _, _ = select.select([self.fd], [], [], 0.5)
                if not ready:
                    continue
                data = os.read(self.fd, 65536)
            except BlockingIOError:
                continue
            except OSError:
                # macOS reports EIO while nobody has the other end open; wait for the host to open it
                time.sleep(0.2)
                continue
            if not data:
                time.sleep(0.2)
                continue
            for line in self.reader.feed(data):
                message = proto.decode(line)
                if message is not None:
                    self._handle(message)

    def _handle(self, message: dict) -> None:
        if message.get("ev") == "sync":
            self.hello()
            return
        if message.get("ev") == "status":
            with self.changed:
                before = self.status.light
                if self.status.take(message.get("d", {})):
                    self.last_status = time.monotonic()
                    if self.status.light != before:
                        self.log("light: %s (working %d, waiting %d)" % (self.status.light, self.status.working, self.status.waiting))
                self.changed.notify_all()
            return
        if "ev" in message:
            self.log("event: %s %s" % (message["ev"], message.get("d")))
            return
        if "m" in message:
            # v1 hosts send no requests over USB
            self.send(proto.error(message["id"], "unknown_method"))
            return
        with self.changed:
            self.replies[message["id"]] = message
            result = message.get("r") or {}
            if message.get("ok") and "host" in result:
                self.host = result["host"]
                self.mic = result.get("mic")
                # seq counts within one handshake: a host that restarted begins again at 1
                self.status.seq = 0
                self.last_status = time.monotonic()
                self.log("connected to %s %s (mic: %s)" % (result["host"].get("app"), result["host"].get("version"), self.mic))
            self.changed.notify_all()


def open_pty(link: str | None) -> tuple[int, int, str]:
    master, slave = os.openpty()
    tty.setraw(slave)
    attrs = termios.tcgetattr(master)
    termios.tcsetattr(master, termios.TCSANOW, attrs)
    name = os.ttyname(slave)
    if link:
        if os.path.islink(link) or os.path.exists(link):
            os.remove(link)
        os.symlink(name, link)
    return master, slave, name


def run(device: SimDevice, command: str) -> bool:
    words = shlex.split(command)
    if not words:
        return True
    verb, args = words[0], words[1:]
    if verb == "hold":
        if not args:
            print("hold <file.wav | seconds>")
            return True
        try:
            samples = proto.tone(float(args[0]))
        except ValueError:
            samples = proto.read_wav(args[0])
        text = device.hold(samples)
        if text is not None:
            print("heard: %r" % text)
    elif verb == "tap":
        device.tap()
    elif verb == "wait":
        what = args[0] if args else "connected"
        timeout = float(args[1]) if len(args) > 1 else 30
        if what == "connected":
            ok = device.wait_for(lambda: device.host is not None, timeout)
        elif what.startswith("light="):
            want = what.split("=", 1)[1]
            ok = device.wait_for(lambda: device.status.light == want, timeout)
        else:
            print("wait connected | wait light=<light>")
            return True
        print(("ok: " if ok else "timed out: ") + what)
        return ok
    elif verb == "sleep":
        time.sleep(float(args[0]) if args else 1)
    elif verb == "status":
        s = device.status
        print("light %s, working %d, waiting %d, latest %s" % (s.light, s.working, s.waiting, s.latest))
    elif verb in ("quit", "exit"):
        raise SystemExit(0)
    else:
        print("unknown command: " + verb)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulated echo agent device (USB mode)")
    parser.add_argument("--link", default=os.path.join(os.environ.get("TMPDIR", "/tmp"), "echo-device-sim"),
                        help="path of the symlink to the simulated serial port (give it to the host as ECHO_DEVICE_PORT)")
    parser.add_argument("--id", default=None, help="device id (default: random)")
    parser.add_argument("--name", default="Simulated device")
    parser.add_argument("--mic", choices=["stream", "none"], default="stream")
    parser.add_argument("--codec", choices=["pcm16", "opus"], default="pcm16", help="codec the microphone offers")
    parser.add_argument("--fast", action="store_true", help="send audio as fast as possible instead of in real time")
    parser.add_argument("--script", help="commands to run, separated by ;")
    args = parser.parse_args()

    master, slave, name = open_pty(args.link)
    codecs = ("opus",) if args.codec == "opus" else ("pcm16",)
    caps = proto.Caps(mic=None if args.mic == "none" else "stream", codecs=codecs)
    identity = proto.Identity(id=args.id or secrets.token_hex(6), name=args.name)
    device = SimDevice(master, identity, caps, realtime=not args.fast)
    device.start()
    print("simulated device %s on %s (linked at %s)" % (identity.id, name, args.link), flush=True)
    try:
        if args.script:
            for command in args.script.split(";"):
                if not run(device, command.strip()):
                    return 1
            return 0
        while True:
            try:
                line = input("> ")
            except EOFError:
                return 0
            run(device, line)
    except KeyboardInterrupt:
        return 0
    finally:
        device.stop()
        if args.link and os.path.islink(args.link) and os.readlink(args.link) == name:
            os.remove(args.link)
        os.close(slave)
        os.close(master)


if __name__ == "__main__":
    sys.exit(main())
