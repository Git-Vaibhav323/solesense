/**
 * SoleSense ESP32-S3 Firmware
 * calibration.h  —  FSR baseline calibration API
 *
 * ─── What this does ──────────────────────────────────────────────────────────
 *
 *  Captures the ADC reading for each FSR when the insole is completely
 *  unloaded, stores those baselines in ESP32 flash (NVS), and subtracts
 *  them from every future reading.
 *
 *  Result: calibrated[i] = raw[i] − baseline[i], clamped ≥ 0
 *
 *  A value of 0 means "at or below the resting level".
 *  A positive value means "load above the resting level".
 *
 * ─── What this does NOT do ───────────────────────────────────────────────────
 *
 *  ⚠ The output is a RELATIVE LOAD PROXY, not Newtons, kg, or kPa.
 *    FSRs are non-linear and vary between units.  Baseline subtraction
 *    only removes the zero-load offset; it does not linearise or
 *    cross-calibrate sensors against each other.
 *    See config.h Section 11 for the full pressure disclaimer.
 *
 * ─── NVS persistence ─────────────────────────────────────────────────────────
 *
 *  Baselines are saved to flash using the ESP32 Preferences library.
 *  They survive power cycles.  Recalibrate whenever:
 *    - A sensor is replaced or re-seated
 *    - The insole assembly changes
 *    - Readings drift noticeably at rest
 *
 * ─── Calibration procedure ───────────────────────────────────────────────────
 *
 *  1. Power the ESP32-S3 with the insole COMPLETELY UNLOADED (flat on a table,
 *     no pressure applied to any FSR).
 *  2. In the Arduino IDE Serial Monitor (115200 baud), send:  C  then Enter
 *     (or hold BOOT button during power-on for automatic calibration)
 *  3. Follow the on-screen instructions.
 *     The firmware will:
 *       a. Wait CAL_SETTLE_MS ms for you to remove your hand
 *       b. Sample each FSR CAL_SAMPLES times
 *       c. Compute mean and std-dev for each channel
 *       d. Warn if noise exceeds CAL_NOISE_WARN_ADC counts
 *       e. Save baselines to NVS flash
 *       f. Print a confirmation table
 *  4. Press any key or reset to resume normal operation.
 *
 * ─── Region mapping ──────────────────────────────────────────────────────────
 *
 *  The four FSR channels map to anatomical regions.
 *  Labels are defined in config.h:
 *    FSR1  →  FSR1_REGION  (default: "forefoot_medial")
 *    FSR2  →  FSR2_REGION  (default: "forefoot_lateral")
 *    FSR3  →  FSR3_REGION  (default: "midfoot")
 *    FSR4  →  FSR4_REGION  (default: "heel")
 *
 *  Change FSR1_REGION..FSR4_REGION in config.h to match your insole layout.
 *  Also update FSR_REGION_MAP in src/hardware_input.py on the laptop side.
 */

#pragma once
#include <stdint.h>
#include <stdbool.h>

// ─────────────────────────────────────────────────────────────────────────────
//  Calibration data structure
// ─────────────────────────────────────────────────────────────────────────────

struct CalibrationData {
    uint16_t baseline[4];   // mean ADC count at zero load, per FSR channel
    uint16_t noise[4];      // std-dev of ADC during baseline capture (ADC counts)
                            // High noise (> CAL_NOISE_WARN_ADC) may indicate
                            // a loose connection or mechanical vibration.
    bool     valid;         // true  = baselines were loaded from NVS or
                            //         just captured — safe to use
                            // false = no calibration found; baseline[] = {0,0,0,0}
                            //         readings still work but are uncorrected
};

// ─────────────────────────────────────────────────────────────────────────────
//  API
// ─────────────────────────────────────────────────────────────────────────────

/**
 * calibration_load()
 *
 * Read previously saved baselines from NVS into RAM.
 * If no saved data exists, baselines default to 0 (valid = false).
 *
 * Call once from setup(), BEFORE sensors_init() and sensors_read().
 */
void calibration_load();

/**
 * calibration_run()
 *
 * Interactive baseline calibration via Serial.
 *
 * Steps performed:
 *   1. Print instructions to Serial
 *   2. Wait CAL_SETTLE_MS ms (user removes weight from insole)
 *   3. Live monitoring loop — prints current ADC value per sensor every
 *      500 ms so the user can confirm the insole is truly unloaded
 *   4. Prompt user to confirm (send any key) before sampling begins
 *   5. Collect CAL_SAMPLES readings, compute mean and std-dev per channel
 *   6. Warn if std-dev > CAL_NOISE_WARN_ADC (possible wiring issue)
 *   7. Save baselines to NVS flash
 *   8. Print confirmation table with region labels
 *
 * The function blocks until calibration is complete.
 * Returns normally; caller resumes the sensor loop.
 */
void calibration_run();

/**
 * calibration_get()
 *
 * Return a const reference to the current in-RAM calibration data.
 * Always safe to call — returns valid struct even if uncalibrated
 * (all baselines = 0).  Used by sensors_read() on every sample.
 */
const CalibrationData &calibration_get();

/**
 * calibration_print()
 *
 * Print the current calibration table to Serial in human-readable form:
 *
 *   ─── FSR Calibration Baselines ──────────────────
 *    Ch  Region              Baseline   Noise
 *   ────────────────────────────────────────────────
 *    1   Forefoot Med.          12       3  ADC counts
 *    2   Forefoot Lat.           8       2  ADC counts
 *    3   Midfoot                 6       1  ADC counts
 *    4   Heel                   11       4  ADC counts
 *   ────────────────────────────────────────────────
 *   ⚠ Values are relative load proxies — NOT calibrated kPa or Newtons.
 */
void calibration_print();

/**
 * calibration_status()
 *
 * Print a one-line status to Serial:
 *   [CAL] Status: CALIBRATED (4/4 channels)   ← baselines loaded from NVS
 *   [CAL] Status: NOT CALIBRATED              ← no NVS data; raw ADC used
 *
 * Call from the main diagnostic to give immediate status at a glance.
 */
void calibration_status();

/**
 * calibration_erase()
 *
 * Erase all calibration data from NVS and reset in-RAM baselines to 0.
 * Next load_calibration() call will return valid = false.
 *
 * Use when replacing sensors or rebuilding the insole.
 */
void calibration_erase();

/**
 * calibration_is_valid()
 *
 * Returns true if valid calibration data is loaded.
 * Convenience wrapper around calibration_get().valid.
 */
bool calibration_is_valid();
