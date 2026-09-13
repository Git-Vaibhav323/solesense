/**
 * SoleSense ESP32-S3 Firmware
 * config.h — ALL user-configurable settings in one place
 *
 * This is the ONLY file you need to edit before flashing.
 * All other firmware files read their settings from here.
 *
 * ─── Sections ───────────────────────────────────────────────────────────────
 *   1. FSR pins
 *   2. FSR anatomical region mapping   ← change this to match your insole
 *   3. I²C pins and addresses
 *   4. Sampling rate
 *   5. ADC settings
 *   6. Calibration settings
 *   7. NVS namespace
 *   8. Serial / debug
 *   9. Wi-Fi  (Task 5 — leave as placeholders for now)
 *  10. HTTP   (Task 5)
 *  11. Pressure disclaimer
 */

#pragma once

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 1 — FSR Analog Input Pins
//
//  Use ADC1 pins ONLY (GPIO 1–10 on ESP32-S3-DevKitC-1).
//  ADC2 (GPIO 11–20) is shared with the Wi-Fi RF block and gives
//  unreliable readings when Wi-Fi is active.
//
//  Physical FSR wiring per sensor:
//    3.3V ─── FSR ─── GPIO pin ─── 10 kΩ ─── GND
//  (voltage divider: GPIO reads HIGH under load, LOW at rest)
// ═══════════════════════════════════════════════════════════════════════════
#define FSR1_PIN   1    // ADC1_CH0
#define FSR2_PIN   2    // ADC1_CH1
#define FSR3_PIN   3    // ADC1_CH2
#define FSR4_PIN   4    // ADC1_CH3

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 2 — FSR Anatomical Region Mapping
//
//  These names describe where each FSR sits on the physical insole.
//  CHANGE THESE if you rearrange your sensor layout.
//
//  They are used in:
//    - Serial calibration output (human-readable labels)
//    - JSON packet field names sent to the laptop (Task 5)
//    - hardware_input.py FSR_REGION_MAP on the Python side
//
//  The Python side (src/hardware_input.py) has a matching FSR_REGION_MAP:
//    fsr1 → forefoot_medial
//    fsr2 → forefoot_lateral
//    fsr3 → midfoot
//    fsr4 → heel
//  If you change names here, update FSR_REGION_MAP in hardware_input.py too.
//
//  ⚠ IMPORTANT: These are anatomical location labels only.
//    They do NOT imply clinical pressure measurement.
//    See Section 11 for the pressure disclaimer.
// ═══════════════════════════════════════════════════════════════════════════
#define FSR1_REGION  "forefoot_medial"    // metatarsal head, inner side
#define FSR2_REGION  "forefoot_lateral"   // metatarsal head, outer side
#define FSR3_REGION  "midfoot"            // arch / navicular area
#define FSR4_REGION  "heel"               // calcaneus / rearfoot

// Short labels for Serial output (keep ≤ 16 chars for column alignment)
#define FSR1_LABEL  "Forefoot Med."
#define FSR2_LABEL  "Forefoot Lat."
#define FSR3_LABEL  "Midfoot      "
#define FSR4_LABEL  "Heel         "

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 3 — I²C Pins and Device Addresses
// ═══════════════════════════════════════════════════════════════════════════
#define I2C_SDA  8
#define I2C_SCL  9

// TMP117 — I²C address set by the ADD0 solder jumper on the breakout board:
//   ADD0 → GND : 0x48  (factory default on most breakouts)
//   ADD0 → VCC : 0x49
//   ADD0 → SDA : 0x4A
//   ADD0 → SCL : 0x4B
#define TMP117_I2C_ADDR  0x48

// MPU6050 — I²C address set by the AD0 pin:
//   AD0 → GND : 0x68  (factory default)
//   AD0 → VCC : 0x69
#define MPU6050_I2C_ADDR  0x68

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 4 — Sampling Rate
// ═══════════════════════════════════════════════════════════════════════════
#define SAMPLE_RATE_HZ      20
#define SAMPLE_INTERVAL_MS  (1000 / SAMPLE_RATE_HZ)   // 50 ms

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 5 — ADC Settings
// ═══════════════════════════════════════════════════════════════════════════
#define ADC_RESOLUTION_BITS  12          // ESP32-S3: 12-bit → 0–4095
#define ADC_MAX_VALUE        4095        // 2^12 − 1
#define ADC_REF_VOLTAGE_MV   3300        // mV (3.3 V rail)

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 6 — Calibration Settings
//
//  CAL_SAMPLES        : how many ADC readings to average for the baseline.
//                       200 samples × 10 ms = 2 seconds of averaging.
//                       Increase for noisier sensors.
//
//  CAL_SAMPLE_DELAY_MS: delay between samples in calibration mode.
//                       10 ms → 100 samples/s during calibration.
//
//  CAL_SETTLE_MS      : how long to wait (ms) after the user confirms
//                       the insole is unloaded before sampling begins.
//                       Gives time to remove hand/foot.
//
//  CAL_NOISE_WARN_ADC : if the std-dev of baseline samples exceeds this
//                       value, a noise warning is printed to Serial.
//                       Default 15 ADC counts ≈ 0.4% of full scale.
// ═══════════════════════════════════════════════════════════════════════════
#define CAL_SAMPLES          200
#define CAL_SAMPLE_DELAY_MS  10
#define CAL_SETTLE_MS        2000
#define CAL_NOISE_WARN_ADC   15

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 7 — NVS Namespace
//  Namespace key used by the ESP32 Preferences library to store calibration.
// ═══════════════════════════════════════════════════════════════════════════
#define NVS_NAMESPACE  "solesense"

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 8 — Serial / Debug
//
//  DEBUG_MODE 1 : verbose startup messages, sensor status, calibration detail
//  DEBUG_MODE 0 : minimal output (use when integrating with laptop receiver)
// ═══════════════════════════════════════════════════════════════════════════
#define SERIAL_BAUD  115200
#define DEBUG_MODE   1

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 9 — Wi-Fi  ACCESS POINT MODE
//
//  The ESP32-S3 creates its OWN hotspot.
//  Your laptop connects TO the ESP32 — no phone or router needed.
//
//  Step 1: Flash this firmware
//  Step 2: On your laptop, connect to Wi-Fi network "SoleSense"
//  Step 3: Run the Python receiver — it will always be reachable at 192.168.4.2
//
//  AP_SSID     : the hotspot name that appears on your laptop's Wi-Fi list
//  AP_PASSWORD : must be 8+ characters (or "" for open, not recommended)
//  SERVER_IP   : your laptop's IP on the AP network
//                The ESP32 AP always assigns 192.168.4.2 to the first client.
//                Verify with ipconfig AFTER connecting to "SoleSense" hotspot.
// ═══════════════════════════════════════════════════════════════════════════
#define AP_SSID      "SoleSense"
#define AP_PASSWORD  "solesense123"
#define AP_CHANNEL   1

// Your laptop's IP once it joins the SoleSense hotspot (almost always 192.168.4.2)
#define SERVER_IP                 "192.168.4.2"
#define SERVER_PORT               5005
#define SERVER_ENDPOINT           "/api/sensor"
#define WIFI_CONNECT_TIMEOUT_MS   15000
#define WIFI_RECONNECT_INTERVAL_MS 5000

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 10 — HTTP  (Task 5)
// ═══════════════════════════════════════════════════════════════════════════
#define HTTP_TIMEOUT_MS  500

// ═══════════════════════════════════════════════════════════════════════════
//  SECTION 11 — Pressure Disclaimer  (READ BEFORE USE)
//
//  ⚠ FSR ADC values are NOT calibrated Newtons, kg, kPa, or any other
//    clinical pressure unit.
//
//  FSR (Force-Sensitive Resistor) sensors exhibit:
//    - Significant non-linearity (resistance ≠ linear with force)
//    - Sensor-to-sensor variation (same force → different ADC count)
//    - Hysteresis (response differs loading vs. unloading)
//    - Drift over time and temperature
//
//  What calibration_run() provides:
//    - Zero-load baseline subtraction (removes sensor offset)
//    - A RELATIVE load proxy — higher ADC → more load on that region
//
//  What calibration_run() does NOT provide:
//    - Conversion to absolute force (Newtons)
//    - Conversion to absolute pressure (kPa or Pa)
//    - Clinical or biomechanically validated measurements
//
//  To obtain approximate force values you would need:
//    1. Apply known reference weights to each FSR individually
//    2. Record ADC counts at each weight
//    3. Fit a calibration curve (typically logarithmic for FSRs)
//    4. Store the curve coefficients — not implemented in this prototype
//
//  SoleSense uses calibrated FSR values as relative regional load proxies
//  only.  All downstream risk calculations treat them accordingly.
// ═══════════════════════════════════════════════════════════════════════════
