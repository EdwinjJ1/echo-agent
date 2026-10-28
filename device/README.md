# echo agent devices

Everything needed to build hardware for echo agent: a key on your desk, a status light, a clip-on microphone.
The device sends what you say and your presses to echo agent on your computer, and shows what the agents are doing.

Host support: the Mac version of echo agent supports the USB mode; the Windows version is being ported. Licensed under Apache-2.0.

| | |
|---|---|
| [Protocol](../docs/device-protocol/README.en.md) ([中文](../docs/device-protocol/README.md)) | Messages, capability levels, USB, pairing and per-device keys, local network, relay, Bluetooth |
| [`sim/`](sim/) | A simulated device and a minimal host, in Python |
| [`firmware/esp32s3/`](firmware/esp32s3/) | ESP32-S3 reference firmware (ESP-IDF), USB mode |
| [`fixtures/`](fixtures/) | An exchange both sides test against |
