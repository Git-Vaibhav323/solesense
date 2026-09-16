/**
 * SoleSense ESP32-S3 Firmware
 * config.h — ALL user-configurable settings in one place
 *
 * Edit ONLY this file before flashing.
 * All other firmware files read from here.
 *
 * ─── Pin assignment summary ──────────────────────────────────────────────────
 *
 *  GPIO  1  FSR1     (ADC1_CH0  — forefoot)
 *  GPIO  2  FSR2     (ADC1_CH1  — heel)
 *  GPIO  7  DS18B20  (1-Wire data, both sensors share this pin)
 *  GPIO  8  I2C SDA  (MPU6050)
 *  GPIO  9  I2C SCL  (MPU6050)
 *  GPIO  5  LED      (active-high, current-limit resistor required)
 *  GPIO  6  BUZZER   (active buzzer via NPN transistor — HIGH = ON)
 *  GPIO  0  BOOT button (built-in, INPUT_PULLUP)
 */

#pragma once

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 1 — FSR Analog Input Pins  (2 sensors only)
//
//  Use ADC1 pins ONLY (GPIO 1–10 on ESP32-S3-DevKitC-1).
//  ADC2 (GPIO 11–20) conflicts with Wi-Fi and gives unreliable readings.
//
//  Wiring per FSR:
//    3.3V ── FSR ── GPIO pin ── 10 kΩ ── GND
// ═══════════════════════════════════════════════════════════════════════════
#define FSR_COUNT  2

#define FSR1_PIN   1        // ADC1_CH0  — forefoot
#define FSR2_PIN   2        // ADC1_CH1  — heel

// Anatomical region strings (used in Serial output and JSON)
#define FSR1_REGION  "forefoot"
#define FSR2_REGION  "heel"

// Short labels for Serial column output (≤ 16 chars)
#define FSR1_LABEL   "Forefoot"
#define FSR2_LABEL   "Heel    "

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 2 — DS18B20 1-Wire Temperature Sensors
//
//  Both sensors share a single data wire on DS18B20_PIN.
//  Required external pull-up: 4.7 kΩ from DS18B20_PIN to 3.3 V.
//
//  Wiring (both sensors in parallel on the same bus):
//    DS18B20 pin 1 (GND)  → GND
//    DS18B20 pin 2 (DATA) → GPIO 7  ← 4.7 kΩ pull-up to 3.3 V
//    DS18B20 pin 3 (VCC)  → 3.3 V
//
//  The firmware enumerates both sensors at startup and exposes them as
//  TEMP1 and TEMP2.  Physical location (forefoot/heel) is NOT assumed
//  by the firmware — map them after assembly.
// ═══════════════════════════════════════════════════════════════════════════
#define DS18B20_PIN            7    // 1-Wire data bus (both sensors)
#define DS18B20_RESOLUTION     11   // bits: 9=0.5°C, 10=0.25°C, 11=0.125°C, 12=0.0625°C
                                    // 11-bit → 375 ms conversion, safe for 20 Hz loop
#define DS18B20_CONVERT_MS     375  // must match resolution above
#define DS18B20_SENSOR_COUNT   2    // expected number of sensors on the bus

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 3 — I²C Pins and MPU6050 Address
// ═══════════════════════════════════════════════════════════════════════════
#define I2C_SDA          8
#define I2C_SCL          9

// MPU6050 I²C address
//   AD0 → GND : 0x68  (factory default)
//   AD0 → VCC : 0x69
#define MPU6050_I2C_ADDR  0x68

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 4 — Alert Outputs
//
//  LED_PIN
//    Connect LED anode → GPIO 5 → 220 Ω resistor → LED cathode → GND.
//    HIGH = LED ON.
//
//  BUZZER_PIN
//    Active buzzer via NPN transistor (e.g. 2N2222 / BC547):
//      GPIO 6 → 1 kΩ base resistor → transistor base
//      transistor collector → buzzer (+) → 3.3 V / 5 V
//      transistor emitter  → GND
//      1N4148 flyback diode across buzzer terminals (cathode to VCC side)
//    HIGH = buzzer ON.
//    Do NOT drive an active buzzer directly from a GPIO pin.
// ═══════════════════════════════════════════════════════════════════════════
#define LED_PIN      5
#define BUZZER_PIN   6

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 5 — Sampling Rate
// ═══════════════════════════════════════════════════════════════════════════
#define SAMPLE_RATE_HZ      20
#define SAMPLE_INTERVAL_MS  (1000 / SAMPLE_RATE_HZ)   // 50 ms

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 6 — ADC Settings
// ═══════════════════════════════════════════════════════════════════════════
#define ADC_RESOLUTION_BITS  12      // 12-bit → 0–4095
#define ADC_MAX_VALUE        4095
#define ADC_REF_VOLTAGE_MV   3300

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 7 — Calibration
// ═══════════════════════════════════════════════════════════════════════════
#define CAL_SAMPLES          200     // ADC readings averaged for baseline
#define CAL_SAMPLE_DELAY_MS  10      // ms between each sample
#define CAL_SETTLE_MS        2000    // ms to wait before sampling starts
#define CAL_NOISE_WARN_ADC   15      // std-dev threshold for noise warning

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 8 — NVS Namespace
// ═══════════════════════════════════════════════════════════════════════════
#define NVS_NAMESPACE  "solesense"

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 9 — Serial / Debug
// ═══════════════════════════════════════════════════════════════════════════
#define SERIAL_BAUD  115200
#define DEBUG_MODE   1

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 10 — Wi-Fi  (Access Point mode — ESP32 IS the hotspot)
//
//  Laptop connects to "SoleSense" hotspot, then gets IP 192.168.4.2.
//  Verify with ipconfig after connecting.
// ═══════════════════════════════════════════════════════════════════════════
#define AP_SSID       "SoleSense"
#define AP_PASSWORD   "solesense123"
#define AP_CHANNEL    1

#define SERVER_IP                  "192.168.4.2"
#define SERVER_PORT                5005
#define SERVER_ENDPOINT            "/api/sensor"
#define WIFI_RECONNECT_INTERVAL_MS  5000

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 11 — HTTP
// ═══════════════════════════════════════════════════════════════════════════
#define HTTP_TIMEOUT_MS  500

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 12 — Alert Timing (non-blocking millis-based)
//
//  All durations in milliseconds.
//  No delay() calls — alert state machine uses millis() only.
// ═══════════════════════════════════════════════════════════════════════════
#define ALERT_MONITOR_BLINK_ON_MS   800    // LED slow blink ON time
#define ALERT_MONITOR_BLINK_OFF_MS  800    // LED slow blink OFF time
#define ALERT_MONITOR_BEEP_ON_MS    80     // buzzer short beep duration
#define ALERT_MONITOR_BEEP_PERIOD_MS 3000  // buzzer repeat interval

#define ALERT_ALERT_BLINK_ON_MS     150    // LED fast blink ON time
#define ALERT_ALERT_BLINK_OFF_MS    150    // LED fast blink OFF time
#define ALERT_ALERT_BEEP_ON_MS      150    // buzzer fast beep ON
#define ALERT_ALERT_BEEP_OFF_MS     150    // buzzer fast beep OFF

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 13 — Pressure Disclaimer
//
//  ⚠ FSR ADC values are NOT Newtons, kg, kPa, or clinical pressure units.
//  They are RELATIVE LOAD PROXIES: higher ADC = more load on that region.
//  Calibration removes the zero-load offset only.  Not clinically validated.
// ═══════════════════════════════════════════════════════════════════════════
