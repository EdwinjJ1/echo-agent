// USB: our own TinyUSB start (PHY, stack, task), the CDC serial port, and the UAC microphone fed from mic.c.

#include "echo_device.h"
#include "esp_log.h"
#include "esp_private/usb_phy.h"
#include "freertos/task.h"
#include "tusb.h"
#include "usb_itf.h"
#if ECHO_MIC_UAC
#include "usb_device_uac.h"
#endif

static const char *TAG = "echo_usb";
static usb_phy_handle_t phy;
volatile bool usb_opened = false;

static void usb_task(void *arg)
{
    for (;;) {
        tud_task();
    }
}

// DTR up: the host opened the serial port. The protocol task says hello without waiting for sync.
void tud_cdc_line_state_cb(uint8_t itf, bool dtr, bool rts)
{
    (void)itf;
    (void)rts;
    if (dtr) {
        usb_opened = true;
    }
}

void tud_mount_cb(void) { ESP_LOGI(TAG, "mounted"); }
void tud_umount_cb(void) { ESP_LOGI(TAG, "unmounted"); }

#if ECHO_MIC_UAC
// The host reads the microphone every few milliseconds; give it what the I2S has, silence if nothing yet.
static esp_err_t uac_input(uint8_t *buffer, size_t length, size_t *bytes_read, void *context)
{
    (void)context;
    size_t samples = mic_read((int16_t *)buffer, length / sizeof(int16_t), pdMS_TO_TICKS(5));
    for (size_t i = samples * sizeof(int16_t); i < length; i++) {
        buffer[i] = 0;
    }
    *bytes_read = length;
    return ESP_OK;
}
#endif

void usb_start(const char *serial)
{
    usb_descriptors_set_serial(serial);
    usb_phy_config_t config = {
        .controller = USB_PHY_CTRL_OTG,
        .otg_mode = USB_OTG_MODE_DEVICE,
        .target = USB_PHY_TARGET_INT,
    };
    ESP_ERROR_CHECK(usb_new_phy(&config, &phy));
    if (!tusb_init()) {
        ESP_LOGE(TAG, "TinyUSB did not start");
        return;
    }
    xTaskCreatePinnedToCore(usb_task, "echo_usb", 4096, NULL, 6, NULL, 0);
#if ECHO_MIC_UAC
    uac_device_config_t uac = {
        .skip_tinyusb_init = true,
        .input_cb = uac_input,
        .spk_itf_num = -1,
        .mic_itf_num = ITF_NUM_AUDIO_STREAMING_MIC,
    };
    ESP_ERROR_CHECK(uac_device_init(&uac));
#endif
}

bool usb_host_open(void) { return tud_mounted() && tud_cdc_connected(); }

size_t usb_read(uint8_t *buffer, size_t size)
{
    if (!tud_cdc_available()) {
        return 0;
    }
    return tud_cdc_read(buffer, size);
}

// Writes all of it, waiting for room; gives up after about a second if the host stopped reading.
void usb_write(const char *data, size_t length)
{
    size_t sent = 0;
    int idle = 0;
    while (sent < length && idle < 100) {
        if (!tud_cdc_connected()) {
            return;
        }
        uint32_t room = tud_cdc_write_available();
        if (room == 0) {
            tud_cdc_write_flush();
            vTaskDelay(pdMS_TO_TICKS(10));
            idle++;
            continue;
        }
        size_t piece = length - sent < room ? length - sent : room;
        sent += tud_cdc_write(data + sent, piece);
        idle = 0;
    }
    tud_cdc_write_flush();
}
