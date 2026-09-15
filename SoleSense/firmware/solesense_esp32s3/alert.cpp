/**
 * SoleSense ESP32-S3 Firmware
 * alert.cpp — non-blocking LED + buzzer state machine
 */

#include "alert.h"
#include "config.h"
#include <Arduino.h>

// ── Module state ──────────────────────────────────────────────────────────────
static AlertLevel _level        = ALERT_NORMAL;
static AlertLevel _prev_level   = ALERT_NORMAL;

// LED blink state
static bool     _led_state      = false;
static uint32_t _led_last_ms    = 0;

// Buzzer state
static bool     _buz_state      = false;
static uint32_t _buz_last_ms    = 0;
static bool     _buz_in_gap     = false;   // true = waiting between beep cycles

// ── Init ──────────────────────────────────────────────────────────────────────
void alert_init() {
    pinMode(LED_PIN,    OUTPUT);
    pinMode(BUZZER_PIN, OUTPUT);
    digitalWrite(LED_PIN,    LOW);
    digitalWrite(BUZZER_PIN, LOW);
}

// ── Direct helpers ────────────────────────────────────────────────────────────
void led_on()     { digitalWrite(LED_PIN,    HIGH); _led_state = true;  }
void led_off()    { digitalWrite(LED_PIN,    LOW);  _led_state = false; }
void buzzer_on()  { digitalWrite(BUZZER_PIN, HIGH); _buz_state = true;  }
void buzzer_off() { digitalWrite(BUZZER_PIN, LOW);  _buz_state = false; }

// ── Set level ─────────────────────────────────────────────────────────────────
void alert_set(AlertLevel level) {
    if (level == _level) return;
    _level = level;

    // Reset timing state on level change so new pattern starts immediately
    _led_last_ms = 0;
    _buz_last_ms = 0;
    _buz_in_gap  = false;

    // Force outputs to known state
    if (level == ALERT_NORMAL) {
        led_off();
        buzzer_off();
    }
}

AlertLevel alert_current_level() { return _level; }

// ── Update (call every loop iteration) ───────────────────────────────────────
void alert_update() {
    uint32_t now = millis();

    switch (_level) {

        // ── NORMAL — everything off ───────────────────────────────────────────
        case ALERT_NORMAL:
            led_off();
            buzzer_off();
            break;

        // ── MONITOR — slow LED blink + short periodic beep ───────────────────
        case ALERT_MONITOR: {
            // LED: blink ON/OFF at ALERT_MONITOR_BLINK_ON/OFF_MS
            uint32_t led_period = _led_state
                                  ? ALERT_MONITOR_BLINK_ON_MS
                                  : ALERT_MONITOR_BLINK_OFF_MS;
            if (now - _led_last_ms >= led_period) {
                _led_last_ms = now;
                _led_state ? led_off() : led_on();
            }

            // Buzzer: short beep every ALERT_MONITOR_BEEP_PERIOD_MS
            if (!_buz_state && !_buz_in_gap) {
                // Start a beep
                buzzer_on();
                _buz_last_ms = now;
            } else if (_buz_state) {
                // Beep in progress — check if it should end
                if (now - _buz_last_ms >= ALERT_MONITOR_BEEP_ON_MS) {
                    buzzer_off();
                    _buz_last_ms = now;
                    _buz_in_gap  = true;   // now in the long gap
                }
            } else if (_buz_in_gap) {
                // Waiting for the next beep cycle
                if (now - _buz_last_ms >= ALERT_MONITOR_BEEP_PERIOD_MS) {
                    _buz_in_gap  = false;
                    _buz_last_ms = now;    // will trigger beep on next call
                }
            }
            break;
        }

        // ── ALERT — fast LED blink + rapid buzzer beeps ───────────────────────
        case ALERT_ALERT: {
            // LED: fast blink
            uint32_t led_period = _led_state
                                  ? ALERT_ALERT_BLINK_ON_MS
                                  : ALERT_ALERT_BLINK_OFF_MS;
            if (now - _led_last_ms >= led_period) {
                _led_last_ms = now;
                _led_state ? led_off() : led_on();
            }

            // Buzzer: rapid beep ON/OFF
            uint32_t buz_period = _buz_state
                                  ? ALERT_ALERT_BEEP_ON_MS
                                  : ALERT_ALERT_BEEP_OFF_MS;
            if (now - _buz_last_ms >= buz_period) {
                _buz_last_ms = now;
                _buz_state ? buzzer_off() : buzzer_on();
            }
            break;
        }
    }
}
