"""echo agent device protocol v1: messages, framing and audio helpers.

Standard library only. Opus needs libopus (found through ctypes); everything else works without it.
Spec: docs/device-protocol/README.en.md
"""

from __future__ import annotations

import array
import base64
import ctypes
import ctypes.util
import json
import math
import struct
import wave
from dataclasses import dataclass, field
from typing import Iterator

VERSION = 1
USB_INTERFACE_NAME = "echo-device"
HOLD_MS = 400
LIGHTS = ("idle", "listening", "working", "waiting", "done", "failed")
# A device shows "not connected" after this long without a status event.
HOST_TIMEOUT_S = 75
CHUNK_MS = 200
RATE = 16000


# ---------------------------------------------------------------- messages

def request(id: str, method: str, params: dict | None = None) -> dict:
    return {"id": id, "m": method, "p": params or {}}


def reply(id: str, result: dict | None = None) -> dict:
    return {"id": id, "ok": True, "r": result or {}}


def error(id: str, code: str, message: str | None = None) -> dict:
    e = {"code": code}
    if message:
        e["message"] = message
    return {"id": id, "ok": False, "e": e}


def event(name: str, data: dict | None = None) -> dict:
    return {"ev": name, "d": data or {}}


def encode(message: dict) -> bytes:
    """One line on the serial port: compact JSON plus a newline."""
    return (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def decode(line: str | bytes) -> dict | None:
    """A message, or None for anything that isn't one (debug logs, garbage)."""
    if isinstance(line, bytes):
        line = line.decode("utf-8", "replace")
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        value = json.loads(line)
    except ValueError:
        return None
    if not isinstance(value, dict):
        return None
    if "ev" in value or ("id" in value and ("m" in value or "ok" in value)):
        return value
    return None


class LineReader:
    """Splits a byte stream into lines; drops a line that grows past 64 KiB."""

    LIMIT = 64 * 1024

    def __init__(self) -> None:
        self.buffer = b""

    def feed(self, data: bytes) -> list[str]:
        self.buffer += data
        lines = []
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            if line:
                lines.append(line.decode("utf-8", "replace"))
        if len(self.buffer) > self.LIMIT:
            self.buffer = b""
        return lines


# ---------------------------------------------------------------- hello

@dataclass
class Caps:
    buttons: int = 1
    light: str | None = "rgb"
    mic: str | None = "stream"            # "uac", "stream" or None
    codecs: tuple[str, ...] = ("pcm16",)
    rates: tuple[int, ...] = (RATE,)
    screen: tuple[int, int] | None = None

    def json(self) -> dict:
        caps: dict = {}
        if self.buttons:
            caps["button"] = {"count": self.buttons}
        if self.light:
            caps["light"] = {"kind": self.light, "count": 1}
        if self.mic == "uac":
            caps["mic"] = {"via": "uac", "rates": list(self.rates)}
        elif self.mic == "stream":
            caps["mic"] = {"via": "stream", "codecs": list(self.codecs), "rates": list(self.rates)}
        if self.screen:
            caps["screen"] = {"w": self.screen[0], "h": self.screen[1]}
        return caps


@dataclass
class Identity:
    id: str
    model: str = "echo-sim"
    name: str | None = None
    fw: str = "0.1.0"
    maker: str = "echo-reference"

    def json(self) -> dict:
        device = {"id": self.id, "model": self.model, "fw": self.fw, "maker": self.maker}
        if self.name:
            device["name"] = self.name
        return device


def hello_params(identity: Identity, caps: Caps) -> dict:
    return {"v": VERSION, "device": identity.json(), "caps": caps.json()}


def choose_mic(caps: dict) -> dict | None:
    """What a host picks for a device's microphone (same rule as the Mac host)."""
    mic = caps.get("mic")
    if not mic:
        return None
    rates = mic.get("rates") or [RATE]
    rate = min(rates, key=lambda r: abs(r - RATE))
    if mic.get("via") == "uac":
        return {"via": "uac", "rate": rate}
    codecs = [c for c in (mic.get("codecs") or ["pcm16"]) if c in ("pcm16", "opus")]
    for codec in ("pcm16", "opus"):
        if codec in codecs:
            return {"via": "stream", "codec": codec, "rate": rate}
    return None


# ---------------------------------------------------------------- key and light

class Gesture:
    """How a host reads one key: down starts listening, a hold over 400 ms is speech, shorter is a press."""

    def __init__(self, hold_ms: int = HOLD_MS) -> None:
        self.hold_ms = hold_ms
        self.down_at: float | None = None

    def handle(self, action: str, t: float) -> str | None:
        if action == "down":
            if self.down_at is not None:
                return None
            self.down_at = t
            return "pressed"
        if action == "up":
            if self.down_at is None:
                return None
            held = t - self.down_at
            self.down_at = None
            return "talked" if held >= self.hold_ms else "tapped"
        return None


def light(listening: bool, working: int, waiting: int, latest: str | None) -> str:
    """The light a host shows. latest is "done" / "failed" for a fresh, unseen result, else None."""
    if listening:
        return "listening"
    if waiting > 0:
        return "waiting"
    if latest == "failed":
        return "failed"
    if working > 0:
        return "working"
    if latest == "done":
        return "done"
    return "idle"


# ---------------------------------------------------------------- audio

def read_wav(path: str) -> list[int]:
    """16-bit PCM samples at 16 kHz mono from a 16-bit wav of any rate and channel count."""
    with wave.open(path, "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("the wav has to be 16-bit PCM")
        channels, rate = w.getnchannels(), w.getframerate()
        frames = array.array("h", w.readframes(w.getnframes()))
    if channels > 1:
        frames = array.array("h", (sum(frames[i:i + channels]) // channels for i in range(0, len(frames), channels)))
    return resample(list(frames), rate, RATE)


def resample(samples: list[int], source: int, target: int) -> list[int]:
    """Linear interpolation; good enough for speech going into a recognizer."""
    if source == target or not samples:
        return list(samples)
    count = int(len(samples) * target / source)
    out = []
    for i in range(count):
        x = i * source / target
        j = int(x)
        k = min(j + 1, len(samples) - 1)
        out.append(int(samples[j] + (samples[k] - samples[j]) * (x - j)))
    return out


def tone(seconds: float, frequency: float = 440.0, level: float = 0.3) -> list[int]:
    return [int(level * 32767 * math.sin(2 * math.pi * frequency * i / RATE)) for i in range(int(seconds * RATE))]


def pcm16_bytes(samples: list[int]) -> bytes:
    return struct.pack("<%dh" % len(samples), *samples)


def chunks(samples: list[int], ms: int = CHUNK_MS) -> Iterator[list[int]]:
    size = RATE * ms // 1000
    for i in range(0, len(samples), size):
        yield samples[i:i + size]


class OpusEncoder:
    """libopus through ctypes: 16 kHz mono, 20 ms packets."""

    FRAME = RATE // 50

    def __init__(self, bitrate: int = 20000) -> None:
        self.lib = load_opus()
        if self.lib is None:
            raise RuntimeError("libopus not found (macOS: brew install opus; Debian: apt install libopus0)")
        error = ctypes.c_int()
        self.lib.opus_encoder_create.restype = ctypes.c_void_p
        self.state = self.lib.opus_encoder_create(RATE, 1, 2048, ctypes.byref(error))  # OPUS_APPLICATION_VOIP
        if error.value != 0 or not self.state:
            raise RuntimeError("opus_encoder_create failed: %d" % error.value)
        self.lib.opus_encoder_ctl(ctypes.c_void_p(self.state), 4002, ctypes.c_int(bitrate))  # OPUS_SET_BITRATE
        self.rest: list[int] = []

    def encode(self, samples: list[int], flush: bool = False) -> list[bytes]:
        """Whole 20 ms packets; leftovers wait for the next call (or are padded with silence on flush)."""
        self.rest += samples
        if flush and len(self.rest) % self.FRAME:
            self.rest += [0] * (self.FRAME - len(self.rest) % self.FRAME)
        packets = []
        out = ctypes.create_string_buffer(1276)
        while len(self.rest) >= self.FRAME:
            frame, self.rest = self.rest[:self.FRAME], self.rest[self.FRAME:]
            pcm = (ctypes.c_int16 * self.FRAME)(*frame)
            n = self.lib.opus_encode(ctypes.c_void_p(self.state), pcm, self.FRAME, out, len(out))
            if n < 0:
                raise RuntimeError("opus_encode failed: %d" % n)
            packets.append(out.raw[:n])
        return packets

    def __del__(self) -> None:
        if getattr(self, "state", None):
            self.lib.opus_encoder_destroy(ctypes.c_void_p(self.state))


def load_opus():
    names = [ctypes.util.find_library("opus"), "/opt/homebrew/lib/libopus.dylib", "/usr/local/lib/libopus.dylib", "libopus.so.0"]
    for name in names:
        if not name:
            continue
        try:
            return ctypes.CDLL(name)
        except OSError:
            continue
    return None


def frame_packets(packets: list[bytes]) -> bytes:
    """Opus packets in one voice.chunk: each preceded by its length, two bytes big-endian."""
    return b"".join(struct.pack(">H", len(p)) + p for p in packets)


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


@dataclass
class Status:
    """The last status event a device received."""
    seq: int = 0
    light: str = "idle"
    working: int = 0
    waiting: int = 0
    latest: dict | None = None
    extra: dict = field(default_factory=dict)

    def take(self, data: dict) -> bool:
        """Applies a status event; False if it is older than what we have."""
        seq = int(data.get("seq", 0))
        if seq and seq <= self.seq:
            return False
        self.seq = seq
        self.light = data.get("light", "idle") if data.get("light") in LIGHTS else "idle"
        self.working = int(data.get("working", 0))
        self.waiting = int(data.get("waiting", 0))
        self.latest = data.get("latest")
        return True
