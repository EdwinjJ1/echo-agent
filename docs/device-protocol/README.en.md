# echo agent Device Protocol v1

> Status: draft (2026-10). Parts marked "implemented in v1" are supported by the Mac version of echo agent and being ported to Windows. Parts marked "draft" set the direction and may still change.
> License: Apache-2.0.
> 中文：[README.md](README.md)

echo agent is a voice AI agent for your computer: hold a key and talk, and it hands the work to the coding agents on your computer (Claude Code, Codex, opencode and others).
Steps that need your approval and finished results come back to you. This protocol lets other hardware be a way into echo agent: a key on your desk, a status light,
a small microphone clipped to a collar or a glasses temple, a watch.

A device does not run an agent and does not recognize speech. It does three things: **bring what you say in** (key, microphone, wake word),
**show what is going on** (light, screen, speaker), and **press for you** (approve). Recognition, dispatching and talking to the agents all happen in echo agent on the computer,
which this document calls the **host**.

## Contents

1. [Capability levels](#1-capability-levels)
2. [Transports](#2-transports)
3. [Message format](#3-message-format)
4. [Handshake: hello](#4-handshake-hello)
5. [Key](#5-key)
6. [Audio](#6-audio)
7. [Status and approvals](#7-status-and-approvals)
8. [USB (implemented in v1)](#8-usb-implemented-in-v1)
9. [Pairing and per-device keys (draft)](#9-pairing-and-per-device-keys-draft)
10. [Local network (draft)](#10-local-network-draft)
11. [Through the relay (draft)](#11-through-the-relay-draft)
12. [Bluetooth through the phone (draft)](#12-bluetooth-through-the-phone-draft)
13. [Versions and compatibility](#13-versions-and-compatibility)
14. [Security and privacy](#14-security-and-privacy)
15. [Reference implementations](#15-reference-implementations)

## 1. Capability levels

A device lists what it has in `hello` ([section 4](#4-handshake-hello)); the host decides what to send and how to read the key from that. The levels below are common combinations, not fixed tiers:

| Level | Has | Can | Example |
|---|---|---|---|
| L0 Status light | A light, optionally a key | Show how many tasks are working and whether something waits for you; press once to approve | A light next to your monitor |
| L1 Push to talk | L0 + microphone | Hold to talk, release to send | Desk key (the first prototype) |
| L2 Talks back | L1 + speaker | Hear the line echo agent reads out | Desk device with a speaker |
| L3 Screen | + screen | See what needs approval, the latest result, the words heard | Watch, desk device with a screen |
| L4 Sees | + camera | Take a picture for echo agent | Glasses |

Two more are independent of the level: a **wake word** (the device itself listens for "echo echo" / 「回声回声」, and no sound leaves the device before it hears it) and a **battery**.

The host must cope with devices that have only some capabilities: no voice events for devices without a microphone, no approval details for devices without a screen. Devices ignore fields and events they do not know.

## 2. Transports

The same messages ([section 3](#3-message-format)) travel four ways; only the connection and the encryption differ:

| Transport | For | Pairing and encryption | Status |
|---|---|---|---|
| USB | Desk devices plugged into the computer | None: plugging in is the trust, like a USB keyboard or microphone | Implemented in v1: Mac supports it, Windows port in progress |
| Local network | Desk devices on the same Wi-Fi as the computer | One key per device, ChaCha20-Poly1305 | Draft |
| Relay | Not on the same network | Same; the relay only forwards ciphertext | Draft |
| Bluetooth through the phone | Wearables (clip, glasses) | Same; the phone only forwards ciphertext | Draft |

A device may have several at once (plugged in over USB and on Wi-Fi). The host recognizes it by its `id`, replies on the path a request came from, and sends status on the path the device used last.

## 3. Message format

Every message is a UTF-8 JSON object. There are three kinds, the same as in echo agent's phone remote:

```jsonc
{"id": "7", "m": "hello", "p": {...}}                          // request: m is the method, p the parameters (optional)
{"id": "7", "ok": true, "r": {...}}                            // successful reply, same id as the request
{"id": "7", "ok": false, "e": {"code": "usage", "message": "…"}}  // failed reply
{"ev": "status", "d": {...}}                                   // event: no reply
```

- Requests go both ways (the device sends `hello`, the host sends `provision`). The sender picks the `id`: a string of at most 36 characters, unique on that connection (an increasing number is fine).
- Reply to an unknown request with `{"ok":false,"e":{"code":"unknown_method"}}`; drop unknown events.
- Error codes: `usage` (bad parameters), `not_found`, `busy`, `unavailable` (this host can't do it; `message` says why), `unknown_method`, `version` (protocol version not supported).
- Times are integer milliseconds. `t` is the device's own monotonic clock (milliseconds since boot is fine) and is only used to measure the time between two events; `at` is Unix time in milliseconds.
- Size: at most 64 KiB per message; everything except `voice.chunk` should stay under 4 KiB.

## 4. Handshake: hello

After connecting, the device sends `hello`; the connection is ready once the host has replied. The host may send a `sync` event (`{"ev":"sync"}`) to ask the device for `hello` again, and the device must do so.

```jsonc
// device → host
{"id": "1", "m": "hello", "p": {
  "v": 1,
  "device": {
    "id": "ab12cd34ef56",          // stable id: generated once and stored, or assigned by the host when pairing (section 9)
    "model": "echo-desk-s3",       // model, named by the maker
    "name": "Desk key",            // name for people, optional
    "fw": "0.1.0",                 // firmware version
    "maker": "echo-reference"      // who made it, optional
  },
  "caps": {                        // what it has; leave out what it doesn't
    "button": {"count": 1},
    "light": {"kind": "rgb", "count": 1},        // kind: mono | rgb | ring (count LEDs)
    "mic": {"via": "uac", "rates": [16000]},     // see section 6
    "speaker": {"via": "stream", "codecs": ["opus"]},
    "screen": {"w": 240, "h": 240},
    "camera": {"formats": ["jpeg"]},
    "wake": {"phrases": ["回声回声", "echo echo"]},
    "battery": true
  }
}}

// host → device
{"id": "1", "ok": true, "r": {
  "v": 1,                                        // the version the host will speak
  "host": {"name": "Alex's MacBook Pro", "app": "echo agent", "version": "0.1.83"},
  "mic": {"via": "stream", "codec": "opus", "rate": 16000},   // how the host wants audio; absent for devices without a microphone
  "now": 1761650000000,                          // host Unix time in milliseconds
  "features": ["status", "approve", "voice"]     // what this host does, see below
}}
```

`features` may contain:

| Value | Meaning |
|---|---|
| `status` | Sends `status` events (section 7) |
| `approve` | A press on the device can approve; the `approve` request works |
| `voice` | Push to talk works (section 6) |
| `approvals` | Sends `approvals` events to devices with a screen |
| `transcript` | Sends `transcript` events to devices with a screen |

Right after the handshake the host sends one `status`, and the device lights up from it.

## 5. Key

The key only reports down and up; the host decides what that means from the current state. A one-key device needs no state of its own, and every device behaves the same.

```jsonc
{"ev": "button", "d": {"action": "down", "t": 81234}}
{"ev": "button", "d": {"action": "up", "t": 81990}}
// with several keys, add "id": a number from 0, where 0 is the main key; optional with one key
```

How the host reads one key:

- **Hold to talk**: on down the host starts listening (to the device's microphone; to the computer's if the device has none). Held longer than **400 ms** it is speech; on up the words go to echo agent, the same way as holding the shortcut on the computer.
- **Short press** (down to up under 400 ms): if the light shows "waiting for you", approve the oldest waiting request; otherwise just clear the "done" / "failed" light. Audio from that press is thrown away.
- To deny, or to answer a multiple-choice question, hold and say it ("no", "the second one"); echo agent understands. A press cannot answer a question.
- The 400 ms is measured with `t` (the device clock), not with the arrival times at the host: over the relay the delay between two messages varies a lot.

## 6. Audio

### 6.1 Microphone

The device says how audio arrives in `caps.mic.via`:

| `via` | How audio reaches the host | Used with |
|---|---|---|
| `uac` | The device is also a USB microphone (USB Audio Class); while the key is held the host records from that input | USB |
| `stream` | The device records and sends it piece by piece in `voice.*` messages | Every transport (USB too) |

With `stream` the device also lists `codecs` (`pcm16`, `opus`) and `rates`; the host picks one in its `hello` reply.

While the key is held the device sends (`stream`):

```jsonc
{"ev": "button", "d": {"action": "down", "t": 81234}}
{"id": "9", "m": "voice.begin", "p": {"sid": "s1", "codec": "opus", "rate": 16000}}   // reply {"sid":"s1"}
{"ev": "voice.chunk", "d": {"sid": "s1", "n": 1, "data": "<base64>"}}                  // about 200 ms each
{"ev": "voice.chunk", "d": {"sid": "s1", "n": 2, "data": "<base64>"}}
{"ev": "button", "d": {"action": "up", "t": 81990}}
{"id": "10", "m": "voice.end", "p": {"sid": "s1"}}                                     // reply {"text":"why did CI fail"}
```

- Start recording and sending on down without waiting for the host: a round trip through the relay takes over half a second, and waiting would lose the first word. The host throws away the audio of a short press.
- `voice.chunk` is an event with no reply. `n` starts at 1 and increases within an utterance; the host drops repeats and older pieces.
- The reply to `voice.end` is the recognized text; for a short press (taken as an approval) it is `{"text":"","discarded":true}`.
- The host hands the words over only after both `button up` and `voice.end` have arrived.
- An utterance is at most 3 minutes; the host ignores anything beyond.

**Codecs**:

| `codec` | What `data` holds | Bitrate |
|---|---|---|
| `pcm16` | 16-bit little-endian mono PCM at `rate` | 256 kbps at 16 kHz (about 340 kbps after base64) |
| `opus` | Opus packets, each preceded by its length in two bytes (big-endian); mono, `rate` 16000, 20 ms per packet | 16–24 kbps |

`pcm16` is fine over USB and the local network; use `opus` through the relay and over Bluetooth. Hosts should decode both.

### 6.2 Speaker (draft)

echo agent only reads out the first line or two of an answer, written for the ear. The host sends devices with a speaker:

```jsonc
{"ev": "say", "d": {"text": "CI failed on lint; Codex is fixing it."}}            // devices with a screen may show it
{"ev": "audio", "d": {"id": "a1", "codec": "opus", "rate": 16000, "n": 1, "data": "<base64>", "last": false}}
```

When `caps.speaker.via` is `uac` the host plays the sound on that USB output and sends no `audio`. When the host cannot speak (for example the account has no cloud voice) it sends nothing; the device must not synthesize speech itself.

## 7. Status and approvals

### 7.1 status (implemented in v1)

The host sends it whenever the state changes, and at least every 30 seconds (it doubles as a heartbeat):

```jsonc
{"ev": "status", "d": {
  "seq": 42,                  // increases within one handshake; the device only takes larger ones; starts at 1 again after a new handshake
  "light": "waiting",         // what the light should show, see below
  "working": 2,               // working: background tasks + echo agent answering
  "waiting": 1,               // requests waiting for you (approve a step, answer a question)
  "latest": {                 // the most recently finished task, or null
    "agent": "Codex",
    "status": "done",         // done | failed
    "title": "Fixed the redirect on the sign-in page",   // one line, at most 60 characters
    "at": 1761650000000
  }
}}
```

The host decides `light`, so a device with one light just follows it. The host takes the first that holds, in this order:

| `light` | When | Suggested look (RGB / single color) |
|---|---|---|
| `listening` | The host is listening to this device | Solid white / on |
| `waiting` | A request is waiting for you | Blinking amber / fast blink |
| `failed` | The latest task did not finish and hasn't been looked at | Solid red / three blinks, repeating |
| `working` | A task is working, or echo agent is answering | Breathing blue / slow breathing |
| `done` | The latest task finished and hasn't been looked at | Solid green / 2 s on, 2 s off |
| `idle` | None of the above | Off, or very dim |

`failed` and `done` give way 10 minutes after the task ended, or after a press on the device. When the host is gone (USB unplugged, connection lost, or no `status` for 75 seconds) the device shows "not connected" on its own (suggested: a slow, very dim red blink); the host never sends this state.

### 7.2 approve (implemented in v1)

Devices with a screen can choose what to approve and whether to allow it:

```jsonc
{"id": "12", "m": "approve", "p": {"id": "req-7", "allow": true}}   // reply {"ok":true}
{"id": "13", "m": "approve", "p": {}}                               // no id: approve the oldest, same as a short press
```

If the request is gone, or it is a question, the reply is `not_found` / `usage`.

### 7.3 approvals, transcript (draft)

Only for devices with `caps.screen`:

```jsonc
{"ev": "approvals", "d": {"items": [
  {"id": "req-7", "agent": "Claude Code", "kind": "command", "title": "Run a command", "detail": "npm test"}
]}}
{"ev": "transcript", "d": {"text": "why did CI", "final": false}}
```

`kind`: `command` (run a command), `fileChange` (edit files), `permissions`, `tool`, `question` (multiple choice; can only be answered by voice).

## 8. USB (implemented in v1)

The first prototype: an ESP32-S3 plugged into the computer shows up as a USB microphone plus a serial port. No Wi-Fi, no pairing, no encryption.

**USB descriptors**

- Composite device: a CDC ACM (serial) interface pair, plus a USB Audio Class microphone when there is one (UAC 1.0 or 2.0, 16-bit mono, 16 kHz or 48 kHz).
- The interface string (`iInterface`) of the CDC communication interface must be **`echo-device`**. The host only opens serial ports of USB devices with this interface name and leaves every other serial port alone (no poking at someone's dev board or 3D printer).
- The serial number (`iSerialNumber`) differs per device. The host uses it to match the serial port with the USB microphone of the same device.
- VID/PID are the maker's choice; the host does not look at them.

**On the serial port**

- One message per line: UTF-8 JSON ending in `\n`, with no newline inside. Baud rate and other serial settings have no effect; the host uses 115200 8N1.
- The host raises DTR after opening the port: common CDC stacks (TinyUSB among them) treat DTR low as nobody listening and send nothing.
- After opening the port the host sends `{"ev":"sync"}\n` and the device answers with `hello`. The device may also send `hello` on its own when the port is opened (DTR goes high). Without `hello` within 1.5 seconds the host sends `sync` again; after three tries it treats the port as not an echo device until it is plugged in again.
- When the host closes the port (quits, sleeps) or the cable is pulled, the device treats the host as gone.
- With microphone `via` `uac` the host records from the USB microphone and the serial port carries only keys and status; with `stream` the `voice.*` messages go over the serial port too (for boards that can't do UAC, and for the simulator).
- The host drops lines that don't start with `{`, so firmware may print debug logs on this port, sparingly.

**A complete exchange** (`>` from the host, `<` from the device):

```
> {"ev":"sync"}
< {"id":"1","m":"hello","p":{"v":1,"device":{"id":"3c84279a10b4","model":"echo-desk-s3","fw":"0.1.0"},"caps":{"button":{"count":1},"light":{"kind":"rgb","count":1},"mic":{"via":"uac","rates":[16000]}}}}
> {"id":"1","ok":true,"r":{"v":1,"host":{"name":"Alex's MacBook Pro","app":"echo agent","version":"0.1.83"},"mic":{"via":"uac","rate":16000},"now":1761650000000,"features":["status","approve","voice"]}}
> {"ev":"status","d":{"seq":1,"light":"idle","working":0,"waiting":0,"latest":null}}
< {"ev":"button","d":{"action":"down","t":120400}}
> {"ev":"status","d":{"seq":2,"light":"listening","working":0,"waiting":0,"latest":null}}
< {"ev":"button","d":{"action":"up","t":122950}}
> {"ev":"status","d":{"seq":3,"light":"working","working":1,"waiting":0,"latest":null}}
> {"ev":"status","d":{"seq":4,"light":"waiting","working":1,"waiting":1,"latest":null}}
< {"ev":"button","d":{"action":"down","t":151000}}
< {"ev":"button","d":{"action":"up","t":151180}}
> {"ev":"status","d":{"seq":5,"light":"working","working":1,"waiting":0,"latest":null}}
```

## 9. Pairing and per-device keys (draft)

Devices on a network (local network, relay, Bluetooth) pair first. Unlike phones, **each device has its own key**:

- The host generates a device id `deviceId` (16 random bytes) and a device key `K` (32 random bytes) and keeps them in its device list.
- If a device is opened up and its flash read out, only that device's `K` leaks: someone can pose as that device, but cannot read phone traffic or other devices' traffic, and the key stops working once the host removes the device.
- Removing a device on the host deletes its `K` and tells the relay to stop letting it in ([section 11](#11-through-the-relay-draft)). Re-pairing phones does not affect devices, and the other way round.

What the device stores:

```jsonc
{"v": 1, "device": "<deviceId>", "key": "<K>", "host": "Alex's MacBook Pro",
 "relay": "wss://relay.echoagent.dev", "room": "<room>", "lan": {"port": 51234, "addrs": ["192.168.1.20"]}}
```

Byte strings are always base64url without padding.

**How to pair**:

- **Desk devices, written by the host over USB**: the user clicks "Pair this device" in the host's settings; the host sends a `provision` request over the serial port with the above, plus the Wi-Fi name and password (typed by the user on the host). The device stores them in encrypted flash (NVS encryption on the ESP32) and replies `{"ok":true}`. `unprovision` clears them.
  ```jsonc
  {"id": "h1", "m": "provision", "p": {"pairing": {...}, "wifi": {"ssid": "…", "password": "…"}}}
  ```
- **Wearables, paired by the phone app over Bluetooth**: the phone is already paired with the host. It asks the host for a new device pairing (over its own encrypted channel) and writes it to the device over Bluetooth. The Bluetooth link uses LE Secure Connections, and during pairing the device shows six digits (on its screen, or blinked out) for the person to compare.
- Devices have no camera and scan no codes.

**Key derivation** (HKDF-SHA256, ikm = `K`, salt = `echo-device/v1`, 32 bytes each):

| info | Use |
|---|---|
| `relay-auth` | Device token `deviceToken`, the device's identity at the relay; the relay only stores the lowercase hex of `sha256(UTF-8 of base64url(deviceToken))` |
| `device->host` | Key for messages from device to host |
| `host->device` | Key for messages from host to device |

Ciphertext `box` = base64url(`nonce(12) ‖ ciphertext ‖ tag(16)`), ChaCha20-Poly1305, AAD = UTF-8 bytes of `<room>:<deviceId>`. The plaintext inside a box is a message from section 3.

## 10. Local network (draft)

On the same local network the device connects to the host directly: `ws://<address>:<port>/v1/device` (address and port from `lan` in the pairing; the same port phones use for direct connections).

1. Device → host `{"t":"hello","v":1,"device":<deviceId>,"n":<16 random bytes>}`; the host replies `{"t":"hello","v":1,"n":<host random bytes>}`.
2. Both derive keys for this connection: HKDF-SHA256, ikm = `K`, salt = `echo-device-lan/v1` ‖ device random ‖ host random, info `device->host` and `host->device`.
3. Device → host `{"t":"auth","box":<"echo-device" encrypted with this connection's key>}`; if the host knows the device and can open the box it replies `{"t":"ready","box":<encrypted "echo-device">}`. Otherwise it closes with code 4001.
4. From then on both directions send `{"t":"send","box":…}`; the heartbeat is plain-text `ping` → `pong`, every 15 seconds from the device.

## 11. Through the relay (draft)

The relay is the one phones use (`relay.echoagent.dev`), one room per host. Devices do not take phone slots:

- After authenticating, the host gives the relay its device list: `{"t":"devices","list":[{"id":<deviceId>,"verifier":<device token verifier>}]}`, and sends the whole list again whenever it changes. Devices no longer in the list are disconnected at once (close code 4003).
- The device connects to `GET /v1/rooms/<room>` and sends first `{"t":"auth","role":"device","device":<deviceId>,"token":<deviceToken>,"v":1}`.
- Up to 16 devices per room, counted apart from the up to 4 phones. One connection per device: a new one replaces the old (4000).
- The device sends `{"t":"send","box":…}` and the host receives `{"t":"box","box":…,"device":<deviceId>}`; the host sends `{"t":"send","box":…,"device":<deviceId>}`.
- Device requests are not queued: when the host is offline the relay sends `{"t":"peer","online":false}` and the device shows "not connected". Push to talk and approvals are wanted now; doing them after the host wakes up is useless.

## 12. Bluetooth through the phone (draft)

For wearables without Wi-Fi that need to save power. The phone app is a pipe: device and host are still end-to-end encrypted (`K` from section 9), and the phone cannot read the content.

- One GATT service with two characteristics: `rx` (phone writes to device, write without response) and `tx` (device notifies the phone). UUIDs to be decided.
- Frames: in the first byte of each frame the top bit set means more follow and the low 7 bits are a sequence number; the rest of the frames joined is one `{"t":"send","box":…}`.
- Audio is `opus` only.
- The phone forwards these boxes over its own path to the host (relay or local network) and tells the host which device they came from.

## 13. Versions and compatibility

- `hello.p.v` is the device's version; `v` in the reply is the version the host will use (not above the device's). If the host cannot support it, it replies with a `version` error.
- Adding fields, events or methods does not bump the version: both sides must ignore fields and events they don't know. Only changing the meaning of an existing field does.
- Firmware must not depend on the order of fields in JSON.

## 14. Security and privacy

- USB has no encryption: the cable is the trust boundary, as with a USB keyboard. Any program on the host can open the serial port, so over serial the host only sends light state and (for screens) short titles, never conversation content, and only accepts keys, audio and approvals; nothing over serial can dispatch work or read files.
- Audio goes to the host only while the key is held (or after the wake word is heard). A UAC microphone always has sound; the host records only while the key is held.
- Network transports use one key per device, see section 9. The nonce is 12 random bytes; the number of messages under one key stays far below the bound for random-nonce collisions.
- All the relay sees is which devices are online and when they sent how much.

## 15. Reference implementations

- `device/sim/`: a simulated device (Python 3, standard library only; sends Opus when libopus is present). Runs USB mode without hardware: hold to talk (feeding a wav), receive status, press once to approve.
- `device/firmware/esp32s3/`: an ESP32-S3 reference firmware skeleton (ESP-IDF 5.4, USB mode: one key, one light, a UAC microphone). It has not run on a board yet; see its README for the status.
- `device/fixtures/usb-session.json`: a complete exchange like the one in section 8; tests on both sides check against it.
