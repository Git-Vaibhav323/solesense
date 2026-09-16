/**
 * SoleSense ESP32-S3 Firmware
 * alert.h — LED and active buzzer alert output API
 *
 * Hardware
 * --------
 *  LED    : GPIO LED_PIN (config.h)
 *           Anode → GPIO → 220 Ω resistor → cathode → GND
 *           HIGH = ON
 *
 *  BUZZER : GPIO BUZZER_PIN (config.h) via NPN transistor
 *           GPIO → 1 kΩ → base | collector → buzzer(+) → 3.3V
 *           emitter → GND | 1N4148 flyback across buzzer
 *           HIGH = ON  (never drive active buzzer directly from GPIO)
 *
 * Risk states
 * -----------
 *  ALERT_NORMAL   — LED off,   buzzer silent
 *  ALERT_MONITOR  — LED slow blink,  buzzer short periodic beep
 *  ALERT_ALERT    — LED fast blink,  buzzer rapid beeps
 *
 * All timing is non-blocking (millis-based).
 * Call alert_update() every loop iteration — it never calls delay().
 */

#pragma once
#include <stdint.h>

// Risk severity levels — mirror the SoleSense risk engine states
typedef enum {
    ALERT_NORMAL  = 0,
    ALERT_MONITOR = 1,
    ALERT_ALERT   = 2
} AlertLevel;

/**
 * alert_init()
 * Configure LED_PIN and BUZZER_PIN as outputs, both initially OFF.
 * Call once from setup().
 */
void alert_init();

/**
 * alert_set(level)
 * Update the current alert level.
 * The visual/audio pattern changes on the next alert_update() call.
 * Safe to call every loop iteration — ignores duplicate level.
 */
void alert_set(AlertLevel level);

/**
 * alert_update()
 * Drive LED and buzzer according to the current level.
 * MUST be called every loop() iteration for non-blocking patterns.
 * Uses millis() internally — no delay().
 */
void alert_update();

/** Direct helpers — bypass the state machine when needed. */
void led_on();
void led_off();
void buzzer_on();
void buzzer_off();

/** Return the current alert level. */
AlertLevel alert_current_level();
