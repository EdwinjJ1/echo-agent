// echo agent device: ESP32-S3 reference firmware, USB mode.
// Protocol: docs/device-protocol/README.en.md (one JSON message per line over USB CDC).
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "sdkconfig.h"

#define ECHO_FIRMWARE_VERSION "0.1.0"
#define ECHO_MODEL "echo-desk-s3"
#define ECHO_RATE 16000
// A device shows "not connected" after this long without a status event.
#define ECHO_HOST_TIMEOUT_MS 75000

#if CONFIG_ECHO_MIC_PDM && CONFIG_ECHO_MIC_PATH_UAC
#define ECHO_MIC_UAC 1
#else
#define ECHO_MIC_UAC 0
#endif
#if CONFIG_ECHO_MIC_PDM && CONFIG_ECHO_MIC_PATH_STREAM
#define ECHO_MIC_STREAM 1
#else
#define ECHO_MIC_STREAM 0
#endif

// ---------------------------------------------------------------- light

typedef enum {
    ECHO_LIGHT_OFFLINE,  // not from the host: shown when the host is gone
    ECHO_LIGHT_IDLE,
    ECHO_LIGHT_LISTENING,
    ECHO_LIGHT_WORKING,
    ECHO_LIGHT_WAITING,
    ECHO_LIGHT_DONE,
    ECHO_LIGHT_FAILED,
} echo_light_t;

void light_init(void);
void light_set(echo_light_t light);
// The status event's "light" value; unknown names read as idle.
echo_light_t light_from_name(const char *name);

// ---------------------------------------------------------------- key

typedef struct {
    bool down;
    int64_t t_ms;  // device clock: milliseconds since boot
} button_event_t;

// Debounced key changes arrive on the returned queue.
QueueHandle_t button_init(void);

// ---------------------------------------------------------------- microphone

void mic_init(void);
// 16 kHz mono 16-bit samples; returns how many were read.
size_t mic_read(int16_t *samples, size_t count, TickType_t wait);

// ---------------------------------------------------------------- USB

// Composite device: CDC (interface name "echo-device") plus, with ECHO_MIC_UAC, a USB microphone.
// serial is the USB serial number; the host matches the serial port and the microphone by it.
void usb_start(const char *serial);
bool usb_host_open(void);        // the host has the serial port open (DTR)
size_t usb_read(uint8_t *buffer, size_t size);
void usb_write(const char *data, size_t length);

// Set by usb.c when DTR goes up, so the device says hello without waiting for sync.
extern volatile bool usb_opened;

// ---------------------------------------------------------------- protocol

void protocol_run(QueueHandle_t buttons, const char *device_id);
