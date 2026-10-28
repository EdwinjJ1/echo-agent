// The microphone: a PDM microphone on I2S, read as 16 kHz mono 16-bit.
// XIAO ESP32S3 Sense: clock GPIO42, data GPIO41. The LCKFB board's ES7210 array needs the codec driver
// (esp_codec_dev) and is not wired up yet; with "None" the host records from the computer's microphone.

#include "echo_device.h"
#include "esp_log.h"
#if CONFIG_ECHO_MIC_PDM
#include "driver/i2s_pdm.h"

static i2s_chan_handle_t channel;

void mic_init(void)
{
    i2s_chan_config_t chan = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    ESP_ERROR_CHECK(i2s_new_channel(&chan, NULL, &channel));
    i2s_pdm_rx_config_t pdm = {
        .clk_cfg = I2S_PDM_RX_CLK_DEFAULT_CONFIG(ECHO_RATE),
        .slot_cfg = I2S_PDM_RX_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .clk = CONFIG_ECHO_MIC_PDM_CLK_GPIO,
            .din = CONFIG_ECHO_MIC_PDM_DATA_GPIO,
        },
    };
    ESP_ERROR_CHECK(i2s_channel_init_pdm_rx_mode(channel, &pdm));
    ESP_ERROR_CHECK(i2s_channel_enable(channel));
}

size_t mic_read(int16_t *samples, size_t count, TickType_t wait)
{
    size_t bytes = 0;
    // a timeout still reports what arrived before it
    i2s_channel_read(channel, samples, count * sizeof(int16_t), &bytes, wait);
    return bytes / sizeof(int16_t);
}

#else

void mic_init(void) {}

size_t mic_read(int16_t *samples, size_t count, TickType_t wait)
{
    (void)samples;
    (void)count;
    (void)wait;
    return 0;
}

#endif
