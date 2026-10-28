# Device simulator and probe

Reference implementations of both sides of the USB mode of the [echo agent device protocol](../../docs/device-protocol/README.en.md).
Python 3.10+, standard library only; Opus needs libopus (`brew install opus`, `apt install libopus0`).

| File | What |
|---|---|
| `sim.py` | A simulated device: a pseudo-terminal that behaves like the device's USB serial port. Hold to talk (feed a wav), receive status, press to approve |
| `probe.py` | A minimal host: checks a device (real or simulated) without echo agent |
| `echo_device.py` | Messages, framing, the key and light rules, audio helpers |
| `test_device.py` | Tests: the shared fixture, and the simulator against the probe over a real pseudo-terminal |

## Simulate a device for echo agent

```sh
python3 device/sim/sim.py --link /tmp/echo-device
# start echo agent with ECHO_DEVICE_PORT=/tmp/echo-device, then at the simulator's prompt:
> wait connected
> hold speech.wav          # 16-bit wav, any rate; or "hold 2" for two seconds of a tone
> wait light=waiting 60
> tap                      # approves the oldest waiting request
```

`--codec opus` makes the simulated microphone offer Opus only; `--mic none` makes it a light-and-key device; `--script "cmd; cmd"` runs commands and exits non-zero when a `wait` times out.

## Test

```sh
python3 -m unittest discover -s device/sim
```

The fixture `device/fixtures/usb-session.json` is shared with echo agent's own tests, so both sides agree on messages, key timing, lights and audio framing.
