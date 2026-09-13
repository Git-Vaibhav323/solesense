/**
 * SoleSense ESP32-S3 Firmware
 * sensors.h  —  sensor data structures and API
 *
 * Covers:
 *   FSR1–4    : 4-channel FSR pressure via ADC1
 *   TMP117    : I²C temperature sensor
 *   MPU6050   : I²C 6-axis IMU (accelerometer + gyroscope)
 *
 * Pin and address configuration is in config.h — do not hard-code
 * anything here.
 */

#pragma once
#include <stdint.h>
#include <stdbool.h>

// ─────────────────────────────────────────────────────────────────────────────
//  Sensor data structs
// ─────────────────────────────────────────────────────────────────────────────

/**
 * FSR readings — one slot per sensor channel.
 *   raw[]        : direct ADC count  (0 – ADC_MAX_VALUE from config.h)
 *   calibrated[] : baseline-subtracted count, clamped ≥ 0
 *                  Use calibrated[] for all analytics downstream.
 * Index mapping  :  [0]=FSR1  [1]=FSR2  [2]=FSR3  [3]=FSR4
 */
struct FsrData {
    uint16_t raw[4];
    uint16_t calibrated[4];
};

/**
 * TMP117 temperature reading.
 *   ok            : true  = sensor responded and data is valid
 *                   false = sensor not found or I²C error
 *   temperature_c : degrees Celsius (only valid when ok == true)
 *                   Set to -999.0 as a sentinel when ok == false.
 */
struct TMP117Data {
    bool  ok;
    float temperature_c;
};

/**
 * MPU6050 inertial measurement.
 *   ok           : true = sensor responded
 *   ax, ay, az   : acceleration in g  (m/s² divided by 9.81)
 *   gx, gy, gz   : angular velocity in °/s
 *
 * Ranges configured in sensors_init():
 *   Accelerometer : ±4 g  (MPU6050_RANGE_4_G)
 *   Gyroscope     : ±500 °/s  (MPU6050_RANGE_500_DEG)
 *   DLPF          : 21 Hz bandwidth  (MPU6050_BAND_21_HZ)
 */
struct MPU6050Data {
    bool  ok;
    float ax, ay, az;   // g
    float gx, gy, gz;   // °/s
};

/**
 * Complete sensor snapshot — one packet per sample cycle (~50 ms at 20 Hz).
 */
struct SensorPacket {
    uint32_t    timestamp_ms;  // millis() at the moment of reading
    FsrData     fsr;
    TMP117Data  tmp117;
    MPU6050Data mpu;
};

// ─────────────────────────────────────────────────────────────────────────────
//  API
// ─────────────────────────────────────────────────────────────────────────────

/**
 * sensors_init()
 * Initialize the I²C bus and both I²C sensors.
 * FSR pins are ADC inputs — no explicit init required for those.
 *
 * Must be called once from setup(), after calibration_load().
 * Returns true only if BOTH TMP117 and MPU6050 responded.
 * A false return does NOT prevent the rest of the firmware from running;
 * individual .ok flags in SensorPacket reflect per-sensor status.
 */
bool sensors_init();

/**
 * sensors_read()
 * Read all four sensors into `pkt`.
 *
 * FSR  : analogRead on each ADC pin → raw[], then subtract calibration
 *        baseline → calibrated[].
 * TMP117: reads only when dataReady() is true (~4 Hz); otherwise the
 *         previous value is held.  First call after init may return the
 *         sensor's power-on default (~25 °C).
 * MPU6050: reads every call.  Values converted to g and °/s.
 *
 * Call at SAMPLE_INTERVAL_MS intervals from loop().
 */
void sensors_read(SensorPacket &pkt);

/**
 * sensors_diagnostic()
 * Print a one-shot hardware report to Serial.
 *
 * Exact output format (one line per value):
 *
 *   ===== SOLESENSE SENSOR DIAGNOSTIC =====
 *   FSR1: 412
 *   FSR2: 385
 *   FSR3: 201
 *   FSR4: 530
 *   TEMP: 31.42 C        (or "TEMP: NOT FOUND")
 *   AX: 0.031
 *   AY: -0.019
 *   AZ: 0.984
 *   GX: 1.240
 *   GY: -0.810
 *   GZ: 0.330
 *   ========================================
 *
 * Call after sensors_init().  Safe to call repeatedly.
 */
void sensors_diagnostic();

/**
 * sensors_tmp117_ok()   — true if TMP117 was detected at init
 * sensors_mpu6050_ok()  — true if MPU6050 was detected at init
 */
bool sensors_tmp117_ok();
bool sensors_mpu6050_ok();
