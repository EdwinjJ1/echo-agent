"""Tests for the reference implementation: the shared fixture, and the simulator against the probe over a real pty.

    python3 -m unittest discover -s device/sim
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import tty
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import echo_device as proto  # noqa: E402
from probe import Probe  # noqa: E402
from sim import SimDevice  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "usb-session.json")


def fixture() -> dict:
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


class FixtureTests(unittest.TestCase):
    def test_transcript_lines_decode_and_round_trip(self):
        for step in fixture()["transcript"]:
            line = proto.encode(step["message"])
            self.assertTrue(line.endswith(b"\n"))
            self.assertNotIn(b"\n", line[:-1])
            self.assertEqual(proto.decode(line), step["message"])

    def test_transcript_key_meanings(self):
        gesture = proto.Gesture(fixture()["holdMs"])
        for step in fixture()["transcript"]:
            message = step["message"]
            if message.get("ev") == "button":
                d = message["d"]
                self.assertEqual(gesture.handle(d["action"], d["t"]), step["meaning"])

    def test_gestures(self):
        for case in fixture()["gestures"]:
            gesture = proto.Gesture()
            meanings = [m for m in (gesture.handle(a, t) for a, t in case["events"]) if m]
            self.assertEqual(meanings, case["meanings"], case)

    def test_lights(self):
        for case in fixture()["lights"]:
            self.assertEqual(proto.light(case["listening"], case["working"], case["waiting"], case["latest"]), case["light"], case)

    def test_mic_choices(self):
        for case in fixture()["micChoices"]:
            self.assertEqual(proto.choose_mic({"mic": case["mic"]}), case["choice"], case)

    def test_status_ignores_older_events(self):
        status = proto.Status()
        self.assertTrue(status.take({"seq": 2, "light": "waiting", "waiting": 1}))
        self.assertFalse(status.take({"seq": 1, "light": "idle"}))
        self.assertEqual(status.light, "waiting")
        self.assertTrue(status.take({"seq": 3, "light": "sparkly"}))
        self.assertEqual(status.light, "idle")

    def test_non_messages_are_dropped(self):
        for line in ["I (123) boot: ESP-IDF", "", "[1,2]", "{not json", '{"x":1}']:
            self.assertIsNone(proto.decode(line), line)

    def test_line_reader_splits_and_joins(self):
        reader = proto.LineReader()
        self.assertEqual(reader.feed(b'{"ev":"a"}\n{"ev"'), ['{"ev":"a"}'])
        self.assertEqual(reader.feed(b':"b"}\n\n'), ['{"ev":"b"}'])

    def test_opus_framing(self):
        opus = fixture()["opus"]
        data = base64.b64decode(opus["data"])
        packets, i = [], 0
        while i < len(data):
            n = int.from_bytes(data[i:i + 2], "big")
            packets.append(data[i + 2:i + 2 + n])
            i += 2 + n
        self.assertEqual(i, len(data))
        self.assertEqual(len(packets), opus["packets"])

    @unittest.skipIf(proto.load_opus() is None, "libopus not installed")
    def test_opus_encoder_makes_20ms_packets(self):
        encoder = proto.OpusEncoder()
        self.assertEqual(len(encoder.encode(proto.tone(0.1))), 5)
        self.assertEqual(len(encoder.encode(proto.tone(0.01), flush=True)), 1)


class SimulatorTests(unittest.TestCase):
    """The simulator and the probe talk over a real pseudo-terminal, as the simulator and a host do."""

    def setUp(self):
        self.master, self.slave = os.openpty()
        tty.setraw(self.slave)
        os.set_blocking(self.master, False)
        os.set_blocking(self.slave, False)
        self.logs: list[str] = []
        caps = proto.Caps(mic="stream", codecs=("pcm16", "opus"))
        self.device = SimDevice(self.master, proto.Identity(id="sim0001", name="Test"), caps, log=self.logs.append, realtime=False)
        self.host = Probe(self.slave, log=self.logs.append)
        self.device.start()
        self.host.start()
        self.assertTrue(self.device.wait_for(lambda: self.device.host is not None, 5), self.logs)

    def tearDown(self):
        self.device.stop()
        self.host.stop()
        time.sleep(0.6)
        os.close(self.master)
        os.close(self.slave)

    def test_handshake_picks_pcm16_and_lights_up(self):
        self.assertEqual(self.device.mic, {"via": "stream", "codec": "pcm16", "rate": 16000})
        self.assertEqual(self.host.hello["device"]["id"], "sim0001")
        self.assertTrue(self.device.wait_for(lambda: self.device.status.seq == 1, 5))
        self.assertEqual(self.device.status.light, "idle")

    def test_hold_to_talk_streams_the_audio(self):
        text = self.device.hold(proto.tone(1.0))
        self.assertEqual(text, "")
        self.assertTrue(self.host.wait_for(lambda: self.host.voice_ends == 1, 5))
        self.assertEqual(self.host.gestures, ["pressed", "talked"])
        self.assertEqual(self.host.voice_samples, 16000)

    def test_short_press_is_a_tap(self):
        self.device.tap()
        self.assertTrue(self.host.wait_for(lambda: len(self.host.gestures) == 2, 5))
        self.assertEqual(self.host.gestures, ["pressed", "tapped"])

    def test_status_reaches_the_device(self):
        self.host.status("waiting", working=1, waiting=1)
        self.assertTrue(self.device.wait_for(lambda: self.device.status.light == "waiting", 5))
        self.assertEqual(self.device.status.waiting, 1)

    def test_sync_asks_for_hello_again(self):
        self.host.hello = None
        self.host.send(proto.event("sync"))
        self.assertTrue(self.host.wait_for(lambda: self.host.hello is not None, 5))


if __name__ == "__main__":
    unittest.main()
