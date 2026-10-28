// USB descriptors of the composite device: a UAC 2.0 microphone (when built with one) and a CDC serial port
// whose interface is named "echo-device" (docs/device-protocol, section 8).

#include <string.h>
#include "tusb.h"
#include "uac_descriptors.h"
#include "usb_itf.h"

// Espressif's VID with a PID from its test range, for prototypes only; a product needs a PID of its own.
#define ECHO_USB_VID 0x303A
#define ECHO_USB_PID 0x8001

static tusb_desc_device_t const desc_device = {
    .bLength = sizeof(tusb_desc_device_t),
    .bDescriptorType = TUSB_DESC_DEVICE,
    .bcdUSB = 0x0200,
    // Interface Association Descriptors (CDC and UAC both use one)
    .bDeviceClass = TUSB_CLASS_MISC,
    .bDeviceSubClass = MISC_SUBCLASS_COMMON,
    .bDeviceProtocol = MISC_PROTOCOL_IAD,
    .bMaxPacketSize0 = CFG_TUD_ENDPOINT0_SIZE,
    .idVendor = ECHO_USB_VID,
    .idProduct = ECHO_USB_PID,
    .bcdDevice = 0x0100,
    .iManufacturer = STRID_MANUFACTURER,
    .iProduct = STRID_PRODUCT,
    .iSerialNumber = STRID_SERIAL,
    .bNumConfigurations = 1,
};

uint8_t const *tud_descriptor_device_cb(void)
{
    return (uint8_t const *)&desc_device;
}

#if ECHO_MIC_UAC
#define AUDIO_LEN TUD_AUDIO_DEVICE_DESC_LEN
#else
#define AUDIO_LEN 0
#endif
#define CONFIG_TOTAL_LEN (TUD_CONFIG_DESC_LEN + AUDIO_LEN + TUD_CDC_DESC_LEN)

static uint8_t const desc_configuration[] = {
    TUD_CONFIG_DESCRIPTOR(1, ITF_NUM_TOTAL, 0, CONFIG_TOTAL_LEN, 0x00, 100),
#if ECHO_MIC_UAC
    TUD_AUDIO_DESCRIPTOR(ITF_NUM_AUDIO_CONTROL, STRID_AUDIO, 0x00, EPNUM_AUDIO_IN, 0x00),
#endif
    TUD_CDC_DESCRIPTOR(ITF_NUM_CDC, STRID_CDC, EPNUM_CDC_NOTIF, 8, EPNUM_CDC_OUT, EPNUM_CDC_IN, 64),
};

uint8_t const *tud_descriptor_configuration_cb(uint8_t index)
{
    (void)index;
    return desc_configuration;
}

static char serial[24] = "000000000000";

void usb_descriptors_set_serial(const char *value)
{
    strncpy(serial, value, sizeof(serial) - 1);
}

static char const *strings[] = {
    [STRID_MANUFACTURER] = "echo-reference",
    [STRID_PRODUCT] = CONFIG_ECHO_DEVICE_NAME,
    [STRID_SERIAL] = serial,
    [STRID_AUDIO] = "echo microphone",
    [STRID_CDC] = "echo-device",
};

static uint16_t desc_string[33];

uint16_t const *tud_descriptor_string_cb(uint8_t index, uint16_t langid)
{
    (void)langid;
    size_t count;
    if (index == STRID_LANGID) {
        desc_string[1] = 0x0409;  // English (US)
        count = 1;
    } else {
        if (index >= sizeof(strings) / sizeof(strings[0]) || strings[index] == NULL) {
            return NULL;
        }
        const char *text = strings[index];
        count = strlen(text);
        if (count > 32) {
            count = 32;
        }
        for (size_t i = 0; i < count; i++) {
            desc_string[1 + i] = (uint8_t)text[i];
        }
    }
    desc_string[0] = (uint16_t)((TUSB_DESC_STRING << 8) | (2 * count + 2));
    return desc_string;
}
