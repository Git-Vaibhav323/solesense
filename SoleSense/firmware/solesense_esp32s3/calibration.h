/**
 * SoleSense ESP32-S3 Firmware
 * calibration.h — FSR baseline calibration API  (2 channels: FSR1, FSR2)
 *
 * Captures zero-load ADC baselines for FSR1 and FSR2, stores them in
 * ESP32 NVS flash, and subtracts them from every future reading.
 *
 *   calibrated[i] = raw[i] − baseline[i], clamped ≥ 0
 *
 * ⚠ Output is a RELATIVE LOAD PROXY — not Newtons, kg, or kPa.
 *
 * Calibration procedure
 * ─────────────────────
 * 1. Place insole flat on a table — no weight on any FSR.
 * 2. Send 'C' in Serial Monitor (or hold BOOT button at power-on).
 * 3. Follow on-screen instructions.
 * 4. Baselines are saved to flash and survive power cycles.
 */

#pragma once
#include <stdint.h>
#include <stdbool.h>

struct CalibrationData {
    uint16_t baseline[2];   // zero-load ADC mean, [0]=FSR1  [1]=FSR2
    uint16_t noise[2];      // std-dev during capture (ADC counts)
    bool     valid;         // true = loaded from NVS or just captured
};

/** Load baselines from NVS. Call before sensors_init(). */
void calibration_load();

/** Interactive baseline capture via Serial. Blocks until complete. */
void calibration_run();

/** Return const ref to current calibration (always safe to call). */
const CalibrationData &calibration_get();

/** Print calibration table to Serial. */
void calibration_print();

/** Print one-line calibration status. */
void calibration_status();

/** Erase NVS calibration and reset baselines to 0. */
void calibration_erase();

/** True if valid calibration data is loaded. */
bool calibration_is_valid();
