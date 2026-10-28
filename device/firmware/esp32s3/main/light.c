// The light, drawn at 50 Hz from the state the host sends (status.light). Looks follow the spec's suggestions:
//   listening: on | waiting: fast blink (amber) | failed: three blinks (red) | working: slow breathing (blue)
//   done: 2 s on, 2 s off (green) | idle: off | not connected: slow, dim blink (red)

#include <math.h>
#include <string.h>
#include "echo_device.h"
#include "esp_timer.h"
#include "freertos/task.h"
#if CONFIG_ECHO_LIGHT_WS2812
#include "led_strip.h"
#else
#include "driver/ledc.h"
#endif

static volatile echo_light_t current = ECHO_LIGHT_OFFLINE;

#if CONFIG_ECHO_LIGHT_WS2812
static led_strip_handle_t strip;
#endif

typedef struct {
    uint8_t r, g, b;
} color_t;

static color_t color_of(echo_light_t light)
{
    switch (light) {
    case ECHO_LIGHT_LISTENING: return (color_t){255, 255, 255};
    case ECHO_LIGHT_WAITING: return (color_t){255, 140, 0};
    case ECHO_LIGHT_FAILED: return (color_t){255, 0, 0};
    case ECHO_LIGHT_WORKING: return (color_t){0, 80, 255};
    case ECHO_LIGHT_DONE: return (color_t){0, 200, 60};
    case ECHO_LIGHT_OFFLINE: return (color_t){255, 0, 0};
    default: return (color_t){0, 0, 0};
    }
}

// Brightness 0..1 at time t (ms) for each state.
static float level_of(echo_light_t light, int64_t t)
{
    switch (light) {
    case ECHO_LIGHT_LISTENING: return 1.0f;
    case ECHO_LIGHT_WAITING: return (t / 250) % 2 ? 1.0f : 0.0f;
    case ECHO_LIGHT_FAILED: {
        int64_t phase = t % 2000;  // three 150 ms blinks, then a pause
        return phase < 900 && (phase / 150) % 2 == 0 ? 1.0f : 0.0f;
    }
    case ECHO_LIGHT_WORKING: return 0.15f + 0.85f * (0.5f - 0.5f * cosf((float)(t % 3000) / 3000.0f * 2.0f * (float)M_PI));
    case ECHO_LIGHT_DONE: return (t / 2000) % 2 ? 0.0f : 1.0f;
    case ECHO_LIGHT_OFFLINE: return (t / 1000) % 2 ? 0.0f : 0.08f;
    default: return 0.0f;
    }
}

static void draw(float level, color_t color)
{
#if CONFIG_ECHO_LIGHT_WS2812
    led_strip_set_pixel(strip, 0, (uint32_t)(color.r * level), (uint32_t)(color.g * level), (uint32_t)(color.b * level));
    led_strip_refresh(strip);
#else
    (void)color;
    uint32_t duty = (uint32_t)(level * 8191.0f);
#if CONFIG_ECHO_LIGHT_ACTIVE_LOW
    duty = 8191 - duty;
#endif
    ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, duty);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);
#endif
}

static void light_task(void *arg)
{
    for (;;) {
        int64_t t = esp_timer_get_time() / 1000;
        echo_light_t light = current;
        draw(level_of(light, t), color_of(light));
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}

void light_init(void)
{
#if CONFIG_ECHO_LIGHT_WS2812
    led_strip_config_t config = {
        .strip_gpio_num = CONFIG_ECHO_LIGHT_GPIO,
        .max_leds = 1,
        .led_model = LED_MODEL_WS2812,
        .color_component_format = LED_STRIP_COLOR_COMPONENT_FMT_GRB,
    };
    led_strip_rmt_config_t rmt = {
        .clk_src = RMT_CLK_SRC_DEFAULT,
        .resolution_hz = 10 * 1000 * 1000,
    };
    ESP_ERROR_CHECK(led_strip_new_rmt_device(&config, &rmt, &strip));
    led_strip_clear(strip);
#else
    ledc_timer_config_t timer = {
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .duty_resolution = LEDC_TIMER_13_BIT,
        .timer_num = LEDC_TIMER_0,
        .freq_hz = 4000,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&timer));
    ledc_channel_config_t channel = {
        .gpio_num = CONFIG_ECHO_LIGHT_GPIO,
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel = LEDC_CHANNEL_0,
        .timer_sel = LEDC_TIMER_0,
        .duty = 0,
    };
    ESP_ERROR_CHECK(ledc_channel_config(&channel));
#endif
    xTaskCreate(light_task, "echo_light", 2048, NULL, 3, NULL);
}

void light_set(echo_light_t light) { current = light; }

echo_light_t light_from_name(const char *name)
{
    if (strcmp(name, "listening") == 0) return ECHO_LIGHT_LISTENING;
    if (strcmp(name, "working") == 0) return ECHO_LIGHT_WORKING;
    if (strcmp(name, "waiting") == 0) return ECHO_LIGHT_WAITING;
    if (strcmp(name, "done") == 0) return ECHO_LIGHT_DONE;
    if (strcmp(name, "failed") == 0) return ECHO_LIGHT_FAILED;
    return ECHO_LIGHT_IDLE;
}
