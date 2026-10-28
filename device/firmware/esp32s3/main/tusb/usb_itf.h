// Interfaces and endpoints of the composite device: UAC microphone (when built with one), then CDC.
#pragma once

#include "echo_device.h"

enum {
#if ECHO_MIC_UAC
    ITF_NUM_AUDIO_CONTROL = 0,
    ITF_NUM_AUDIO_STREAMING_MIC,
#endif
    ITF_NUM_CDC,
    ITF_NUM_CDC_DATA,
    ITF_NUM_TOTAL
};

#define EPNUM_AUDIO_IN 0x81
#define EPNUM_CDC_NOTIF 0x82
#define EPNUM_CDC_OUT 0x03
#define EPNUM_CDC_IN 0x83

// String descriptor indexes
enum {
    STRID_LANGID = 0,
    STRID_MANUFACTURER,
    STRID_PRODUCT,
    STRID_SERIAL,
    STRID_AUDIO,
    STRID_CDC,  // "echo-device": the host only opens serial ports with this interface name
};

void usb_descriptors_set_serial(const char *serial);
