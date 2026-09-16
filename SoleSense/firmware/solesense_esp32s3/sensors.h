/**
 * SoleSense ESP32-S3 Firmware
 * sensors.h — sensor data structures and API
 *
 * Hardware covered:
 *   FSR1, FSR2    — 2-channel FSR pressure (ADC1)
 *   DS18B20 ×2   — 1-Wire temperature (GPIO 7, shared bus)
 *   MPU6050       — I²C 6-axis IMU
 *
 * All pin / address constants come from config.h.
 */

#pragma once
#include <stdint.h>
#include <stdbool.h>

// ─────────────────────────────────────────────────────────────────────────────
//  Data structures
// ─────────────────────────────────────────────────────────────────────────────

/**
 * FsrData — 2 active FSR channels only.
 *   raw[0]        = FSR1 direct ADC count  (0–4095)
 *   raw[1]        = FSR2 direct ADC count
 *   calibrated[0] = FSR1 baseline-subtracted, clamped ≥ 0
 *   calibrated[1] = FSR2 baseline-subtracted, clamped ≥ 0
 */
struct FsrData {
    uint16_t raw[2];
    uint16_t calibrated[2];
};

/**
 * DS18B20Data — readings from both 1-Wire temperature sensors.
 *
 *   sensor_count   : number of DS18B20s detected on the bus (0, 1, or 2)
 *   temperature_c  : [0] = TEMP1, [1] = TEMP2 in °C
 *                    Set to -127.0 (DS18B20 error sentinel) when unavailable.
 *   ok             : true if at least one sensor responded
 *
 * NOTE: The firmware does NOT assume which sensor is "forefoot" or "heel".
 *       TEMP1 and TEMP2 correspond to the enumeration order at startup.
 *       Map to physical locations after assembly.
 */
struct DS18B20Data {
    uint8_t sensor_count;
    float   temperature_c[2];
    bool    ok;
};

/**
 * MPU6050Data — 6-axis IMU.
 *   ok         : true if sensor was detected at init
 *   ax,ay,az   : acceleration in g  (m/s² ÷ 9.80665)
 *   gx,gy,gz   : angular velocity in °/s  (rad/s × 180/π)
 *
 * Configured ranges: ±4 g accelerometer, ±500 °/s gyroscope, 21 Hz DLPF.
 */
struct MPU6050Data {
    bool  ok;
    float ax, ay, az;
    float gx, gy, gz;
};

/**
 * SensorPacket — one complete sample at ~50 ms intervals (20 Hz).
 */
struct SensorPacket {
    uint32_t    timestamp_ms;
    FsrData     fsr;
    DS18B20Data ds18b20;
    MPU6050Data mpu;
};

// ─────────────────────────────────────────────────────────────────────────────
//  API
// ─────────────────────────────────────────────────────────────────────────────

/**
 * sensors_init()
 * Initialise all sensors.  Call once from setup() after calibration_load().
 *
 * Initialises: I²C bus, DS18B20 1-Wire bus, MPU6050.
 * FSR pins need no init — ADC is configured in setup() before this call.
 *
 * DS18B20 conversion is kicked off asynchronously here so the first
 * sensors_read() call has data ready without a blocking wait.
 *
 * Returns true if MPU6050 responded AND at least one DS18B20 was found.
 */
bool sensors_init();

/**
 * sensors_read()
 * Read all sensors into pkt.  Call every SAMPLE_INTERVAL_MS from loop().
 *
 * DS18B20 note: conversion takes ~375 ms at 11-bit resolution.
 * The function retrieves the last completed conversion result, then
 * immediately triggers the next one.  At 20 Hz this produces one new
 * temperature reading approximately every 8 sensor cycles (~400 ms).
 * The previous value is held between updates — no blocking.
 */
void sensors_read(SensorPacket &pkt);

/**
 * sensors_diagnostic()
 * Print a full hardware snapshot to Serial in the required format:
 *
 *   ===== SOLESENSE SENSOR DIAGNOSTIC =====
 *   FSR1: 523  (raw 535)
 *   FSR2: 417  (raw 429)
 *   TEMP1: 32.41 C
 *   TEMP2: 31.98 C
 *   AX: 0.0120
 *   AY: -0.0340
 *   AZ: 0.9980
 *   GX: 1.2400
 *   GY: -0.8200
 *   GZ: 3.1700
 *   ========================================
 */
void sensors_diagnostic();

/** True if MPU6050 was detected at init. */
bool sensors_mpu6050_ok();

/** Number of DS18B20 sensors detected on the bus (0, 1, or 2). */
uint8_t sensors_ds18b20_count();
