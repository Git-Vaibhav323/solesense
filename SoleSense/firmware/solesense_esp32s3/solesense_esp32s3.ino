/**
 * ╔══════════════════════════════════════════════════════════════╗
 * ║         SOLESENSE — ESP32-S3 Firmware                        ║
 * ╠══════════════════════════════════════════════════════════════╣
 * ║  Sensors  : FSR×2 · DS18B20×2 · MPU6050                     ║
 * ║  Alerts   : LED (GPIO 5) · Active buzzer (GPIO 6)            ║
 * ║  Network  : Wi-Fi AP → HTTP POST → laptop receiver           ║
 * ║  Rate     : 20 Hz                                            ║
 * ║  Platform : ESP32-S3 (Arduino framework)                     ║
 * ╠══════════════════════════════════════════════════════════════╣
 * ║  ⚠  NOT a medical device.  Research prototype only.          ║
 * ╚══════════════════════════════════════════════════════════════╝
 *
 * ── Required Arduino libraries ──────────────────────────────────
 *  Install via  Tools → Manage Libraries:
 *    "Adafruit MPU6050"          by Adafruit
 *    "OneWire"                   by Paul Stoffregen
 *    "DallasTemperature"         by Miles Burton
 *    "ArduinoJson"               by Benoit Blanchon  (≥ 6.x)
 *  (Adafruit BusIO + Adafruit Unified Sensor install automatically)
 *
 * ── Board setup ─────────────────────────────────────────────────
 *  Board manager URL:
 *    https://raw.githubusercontent.com/espressif/arduino-esp32/
 *    gh-pages/package_esp32_index.json
 *  Board   : ESP32S3 Dev Module
 *  Package : esp32 by Espressif ≥ 2.0.14
 *
 * ── Pin assignments ─────────────────────────────────────────────
 *  GPIO  1  FSR1      ADC1_CH0  forefoot
 *  GPIO  2  FSR2      ADC1_CH1  heel
 *  GPIO  7  DS18B20   1-Wire data (4.7 kΩ pull-up to 3.3 V)
 *  GPIO  8  SDA       MPU6050 I²C
 *  GPIO  9  SCL       MPU6050 I²C
 *  GPIO  5  LED       active-high (220 Ω series resistor)
 *  GPIO  6  BUZZER    active buzzer via NPN transistor
 *  GPIO  0  BOOT      built-in button (INPUT_PULLUP)
 *
 * ── Serial commands (115200 baud) ───────────────────────────────
 *  D  — full sensor diagnostic
 *  C  — FSR calibration mode
 *  E  — erase saved FSR calibration
 *  W  — Wi-Fi status
 *  H  — help
 *
 * ── Startup modes ───────────────────────────────────────────────
 *  Normal boot       → sensor loop + Wi-Fi TX
 *  Hold BOOT (GPIO0) → FSR calibration mode
 */

#include "config.h"
#include "calibration.h"
#include "sensors.h"
#include "alert.h"
#include "wifi_tx.h"
#include <Arduino.h>

// ─────────────────────────────────────────────────────────────────
//  Constants
// ─────────────────────────────────────────────────────────────────
#define BOOT_BUTTON_PIN  0

// ─────────────────────────────────────────────────────────────────
//  State
// ─────────────────────────────────────────────────────────────────
static uint32_t  _last_sample_ms = 0;
static uint32_t  _sample_count   = 0;

// ── Risk state placeholder ────────────────────────────────────────
// The firmware does not compute a risk score locally.
// The laptop receiver calculates risk and will send it back in a
// future task (bi-directional control).
// For now, the alert level is set to NORMAL at startup and can be
// changed by calling alert_set() from the main loop once a
// risk-state feedback channel is implemented.
// Placeholder interface — replace body when feedback is added.
static AlertLevel _risk_level = ALERT_NORMAL;

static void risk_state_update(const SensorPacket &pkt) {
    // ── PLACEHOLDER ──────────────────────────────────────────────
    // This function is intentionally left as a stub.
    // DO NOT invent a medical risk algorithm here.
    // The existing SoleSense risk engine runs on the laptop.
    // When the laptop sends a risk level back to the ESP32
    // (e.g. via a separate HTTP endpoint), parse it here and call:
    //
    //   if      (received_level == "ALERT")   _risk_level = ALERT_ALERT;
    //   else if (received_level == "MONITOR") _risk_level = ALERT_MONITOR;
    //   else                                  _risk_level = ALERT_NORMAL;
    //
    // For the current prototype, LED and buzzer remain NORMAL.
    (void)pkt;
    alert_set(_risk_level);
}

// ─────────────────────────────────────────────────────────────────
//  Forward declarations
// ─────────────────────────────────────────────────────────────────
static void print_help();
static void print_sensor_line(const SensorPacket &pkt);

// ═════════════════════════════════════════════════════════════════
//  setup()
// ═════════════════════════════════════════════════════════════════
void setup() {
    Serial.begin(SERIAL_BAUD);
    delay(600);

    Serial.println();
    Serial.println(F("╔══════════════════════════════════════════════╗"));
    Serial.println(F("║      SOLESENSE  ESP32-S3  FIRMWARE           ║"));
    Serial.println(F("║      FSR×2 · DS18B20×2 · MPU6050             ║"));
    Serial.println(F("║      LED · Buzzer · Wi-Fi AP                 ║"));
    Serial.println(F("╚══════════════════════════════════════════════╝"));
    Serial.println();

    // ── Alert outputs (init early so LED can signal boot status) ──
    alert_init();
    led_on();   // LED ON during setup to show boot progress

    // ── ADC ───────────────────────────────────────────────────────
    analogReadResolution(ADC_RESOLUTION_BITS);
    analogSetAttenuation(ADC_11db);
    Serial.printf("ADC: %d-bit, 11dB (0–3.3V)\n", ADC_RESOLUTION_BITS);

    // ── BOOT button ───────────────────────────────────────────────
    pinMode(BOOT_BUTTON_PIN, INPUT_PULLUP);

    // ── Calibration ───────────────────────────────────────────────
    calibration_load();
    calibration_status();

    if (digitalRead(BOOT_BUTTON_PIN) == LOW) {
        Serial.println(F("[BOOT] BOOT held → FSR calibration mode"));
        calibration_run();
    }

    // ── Sensors ───────────────────────────────────────────────────
    Serial.println(F("[INIT] Initialising sensors..."));
    bool all_ok = sensors_init();

    Serial.println();
    if (all_ok) {
        Serial.println(F("[INIT] All sensors OK."));
    } else {
        Serial.println(F("[INIT] WARNING: one or more sensors not detected."));
        Serial.println(F("       Check wiring. Firmware continues anyway."));
    }

    // ── Startup diagnostic ────────────────────────────────────────
    sensors_diagnostic();

    // ── Pin summary ───────────────────────────────────────────────
    Serial.println(F("Pin assignment:"));
    Serial.printf( "  FSR1    → GPIO %d  (%s)\n", FSR1_PIN, FSR1_REGION);
    Serial.printf( "  FSR2    → GPIO %d  (%s)\n", FSR2_PIN, FSR2_REGION);
    Serial.printf( "  DS18B20 → GPIO %d  (1-Wire, %d sensor(s) found)\n",
                   DS18B20_PIN, sensors_ds18b20_count());
    Serial.printf( "  MPU6050 → SDA=GPIO%d  SCL=GPIO%d  addr=0x%02X  — %s\n",
                   I2C_SDA, I2C_SCL, MPU6050_I2C_ADDR,
                   sensors_mpu6050_ok() ? "FOUND" : "NOT FOUND");
    Serial.printf( "  LED     → GPIO %d\n", LED_PIN);
    Serial.printf( "  BUZZER  → GPIO %d  (via NPN transistor)\n", BUZZER_PIN);
    Serial.println();

    print_help();

    // ── Wi-Fi AP ──────────────────────────────────────────────────
    wifi_connect();

    led_off();   // boot complete — LED control handed to alert FSM

    Serial.printf("[LOOP] Sensor loop at %d Hz (%d ms interval)\n",
                  SAMPLE_RATE_HZ, SAMPLE_INTERVAL_MS);
    Serial.println(F("       Serial print: once per second"));
    Serial.println(F("       Wi-Fi TX    : every packet"));
    Serial.println();

    _last_sample_ms = millis();
}

// ═════════════════════════════════════════════════════════════════
//  loop()
// ═════════════════════════════════════════════════════════════════
void loop() {

    // ── Non-blocking alert update (LED + buzzer) ──────────────────
    alert_update();

    // ── Wi-Fi watchdog ────────────────────────────────────────────
    wifi_maintain();

    // ── Serial commands ───────────────────────────────────────────
    if (Serial.available()) {
        char cmd = (char)toupper(Serial.read());
        while (Serial.available()) Serial.read();   // flush rest of line

        switch (cmd) {
            case 'D':
                Serial.println(F("[CMD] Diagnostic"));
                calibration_status();
                sensors_diagnostic();
                calibration_print();
                wifi_print_status();
                break;
            case 'C':
                Serial.println(F("[CMD] Calibration mode"));
                calibration_run();
                break;
            case 'E':
                Serial.println(F("[CMD] Erasing calibration"));
                calibration_erase();
                break;
            case 'W':
                wifi_print_status();
                break;
            case 'H':
                print_help();
                break;
            default:
                Serial.printf("[CMD] Unknown '%c' — send H for help\n", cmd);
                break;
        }
    }

    // ── 20 Hz timing gate ─────────────────────────────────────────
    uint32_t now = millis();
    if (now - _last_sample_ms < (uint32_t)SAMPLE_INTERVAL_MS) return;
    _last_sample_ms = now;
    _sample_count++;

    // ── Read sensors ──────────────────────────────────────────────
    SensorPacket pkt;
    sensors_read(pkt);

    // ── Update alert state ────────────────────────────────────────
    risk_state_update(pkt);

    // ── Transmit ──────────────────────────────────────────────────
    wifi_send_packet(pkt);

    // ── Serial output once per second (every SAMPLE_RATE_HZ samples)
    if (_sample_count % (uint32_t)SAMPLE_RATE_HZ == 0) {
        print_sensor_line(pkt);
    }
}

// ═════════════════════════════════════════════════════════════════
//  print_sensor_line()
//  Exact required format — one block per second
// ═════════════════════════════════════════════════════════════════
static void print_sensor_line(const SensorPacket &pkt) {
    Serial.println(F("─────────────────────────────────────────"));

    // FSR — calibrated (baseline-subtracted) values
    Serial.printf("FSR1: %d\n", pkt.fsr.calibrated[0]);
    Serial.printf("FSR2: %d\n", pkt.fsr.calibrated[1]);

    // DS18B20 temperatures
    if (pkt.ds18b20.ok && pkt.ds18b20.temperature_c[0] > -120.0f)
        Serial.printf("TEMP1: %.2f C\n", pkt.ds18b20.temperature_c[0]);
    else
        Serial.println(F("TEMP1: not found"));

    if (pkt.ds18b20.sensor_count >= 2 && pkt.ds18b20.temperature_c[1] > -120.0f)
        Serial.printf("TEMP2: %.2f C\n", pkt.ds18b20.temperature_c[1]);
    else
        Serial.println(F("TEMP2: not found"));

    // IMU
    if (pkt.mpu.ok) {
        Serial.printf("AX: %.4f\n", pkt.mpu.ax);
        Serial.printf("AY: %.4f\n", pkt.mpu.ay);
        Serial.printf("AZ: %.4f\n", pkt.mpu.az);
        Serial.printf("GX: %.4f\n", pkt.mpu.gx);
        Serial.printf("GY: %.4f\n", pkt.mpu.gy);
        Serial.printf("GZ: %.4f\n", pkt.mpu.gz);
    } else {
        Serial.println(F("AX: not found"));
        Serial.println(F("AY: not found"));
        Serial.println(F("AZ: not found"));
        Serial.println(F("GX: not found"));
        Serial.println(F("GY: not found"));
        Serial.println(F("GZ: not found"));
    }

    // Alert state
    const char* lv_str = "NORMAL";
    if      (_risk_level == ALERT_ALERT)   lv_str = "ALERT";
    else if (_risk_level == ALERT_MONITOR) lv_str = "MONITOR";

    Serial.printf("LED: %s\n",    digitalRead(LED_PIN)    ? "ON" : "OFF");
    Serial.printf("BUZZER: %s\n", digitalRead(BUZZER_PIN) ? "ON" : "OFF");
    Serial.printf("T: %lu ms  WiFi: %s  RISK: %s\n",
                  pkt.timestamp_ms,
                  wifi_is_connected() ? "OK" : "NO CLIENT",
                  lv_str);
}

// ═════════════════════════════════════════════════════════════════
//  print_help()
// ═════════════════════════════════════════════════════════════════
static void print_help() {
    Serial.println(F("Serial commands (115200 baud):"));
    Serial.println(F("  D  — full diagnostic snapshot"));
    Serial.println(F("  C  — FSR calibration (remove weight first)"));
    Serial.println(F("  E  — erase saved FSR calibration"));
    Serial.println(F("  W  — Wi-Fi status"));
    Serial.println(F("  H  — this help"));
    Serial.println();
}
