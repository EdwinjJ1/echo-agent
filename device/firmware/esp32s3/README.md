# ESP32-S3 reference firmware (USB mode)

A starting point for an echo agent device: one key, one light, optionally a microphone.
Plugged into a computer running echo agent it shows up as a serial port named `echo-device` and, with a microphone, a USB microphone.
Hold the key to talk, release to send; when the light shows something waiting for you, a short press approves it.
Protocol: [`docs/device-protocol/README.en.md`](../../../docs/device-protocol/README.en.md).

Status: skeleton. It compiles with ESP-IDF 5.4.1 in three configurations (the XIAO default with the USB microphone; audio over the serial port with a WS2812 light; the LCKFB board without a microphone). It has not run on a board yet.
The USB IDs are Espressif's VID `0x303A` with PID `0x8001` from its test range, for prototypes only; a product needs a PID of its own (Espressif grants them to open-source projects).

| Board | Key | Light | Microphone |
|---|---|---|---|
| Seeed XIAO ESP32S3 Sense (default) | BOOT (GPIO0) | user LED (GPIO21, lights when low) | PDM on the Sense board (clock GPIO42, data GPIO41), as a USB microphone |
| LCKFB ESP32-S3 (立创·实战派) | BOOT (GPIO0) | set the GPIO, or a WS2812 | ES7210 array: not wired up yet, the host uses the computer's microphone |

## Build and flash

```sh
# with ESP-IDF 5.4 installed (. $IDF_PATH/export.sh)
idf.py set-target esp32s3
idf.py menuconfig          # "echo device": board, pins, light, microphone
idf.py build flash monitor

# or without installing ESP-IDF
docker run --rm -v "$PWD":/project -w /project espressif/idf:v5.4.1 idf.py build
```

The native USB port (the one wired to GPIO19/20) is the device's port; the UART bridge port, if the board has one, is only for flashing and logs.

## Try it without echo agent

`device/sim/probe.py` is a minimal host: it does the handshake, prints keys and audio, and sets the light by hand.

```sh
python3 device/sim/probe.py /dev/cu.usbmodem1101    # macOS; /dev/ttyACM0 on Linux
```

## Layout

| File | What |
|---|---|
| `main/main.c` | Start-up: device id from the chip's MAC, then light, microphone, key, USB, protocol |
| `main/protocol.c` | The protocol over the serial port: hello, status → light, key events, voice over serial |
| `main/usb.c`, `main/tusb/` | TinyUSB composite device: CDC named `echo-device` plus the UAC microphone (`espressif/usb_device_uac`) |
| `main/button.c` | The key, polled and debounced |
| `main/light.c` | Light looks for each state (single-color LED or WS2812) |
| `main/mic.c` | PDM microphone at 16 kHz |

## Next

- The LCKFB board's ES7210 microphone array and ES8311 speaker (`esp_codec_dev`).
- Wi-Fi and pairing over USB (`provision`), Opus encoding, the speaker: sections 6.2 and 9–11 of the spec.
