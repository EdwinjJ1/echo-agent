// echo agent device: ESP32-S3 reference firmware, USB mode.
// One key, one light, optionally a microphone. Plugged into a computer running echo agent it shows up as
// a serial port (and a USB microphone); hold the key to talk, a short press approves what is waiting.

#include <stdio.h>
#include "echo_device.h"
#include "esp_log.h"
#include "esp_mac.h"

void app_main(void)
{
    // The chip's MAC as the device id and the USB serial number: stable, and different per board.
    uint8_t mac[6];
    esp_efuse_mac_get_default(mac);
    char id[13];
    snprintf(id, sizeof(id), "%02x%02x%02x%02x%02x%02x", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    ESP_LOGI("echo", "echo device %s, firmware %s", id, ECHO_FIRMWARE_VERSION);

    light_init();
    light_set(ECHO_LIGHT_OFFLINE);
    mic_init();
    QueueHandle_t buttons = button_init();
    usb_start(id);
    protocol_run(buttons, id);
}
