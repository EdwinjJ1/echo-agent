// The key: a GPIO pulled up, low while pressed. Polled every 5 ms and debounced (stable for 20 ms),
// which is simpler than interrupts and plenty fast for a key held by a person.

#include "driver/gpio.h"
#include "echo_device.h"
#include "esp_timer.h"
#include "freertos/task.h"

#define POLL_MS 5
#define STABLE_MS 20

static QueueHandle_t events;

static void button_task(void *arg)
{
    bool reported = false;  // what we last told the protocol task
    bool seen = false;      // what the pin last read
    int64_t since = 0;
    for (;;) {
        bool down = gpio_get_level(CONFIG_ECHO_BUTTON_GPIO) == 0;
        int64_t now = esp_timer_get_time() / 1000;
        if (down != seen) {
            seen = down;
            since = now;
        } else if (down != reported && now - since >= STABLE_MS) {
            reported = down;
            // the moment it changed, not the moment we were sure
            button_event_t event = {.down = down, .t_ms = since};
            xQueueSend(events, &event, 0);
        }
        vTaskDelay(pdMS_TO_TICKS(POLL_MS));
    }
}

QueueHandle_t button_init(void)
{
    gpio_config_t config = {
        .pin_bit_mask = 1ULL << CONFIG_ECHO_BUTTON_GPIO,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
    };
    gpio_config(&config);
    events = xQueueCreate(16, sizeof(button_event_t));
    xTaskCreate(button_task, "echo_button", 2048, NULL, 5, NULL);
    return events;
}
