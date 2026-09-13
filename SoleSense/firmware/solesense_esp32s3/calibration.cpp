/**
 * SoleSense ESP32-S3 Firmware
 * calibration.cpp  —  FSR baseline calibration implementation
 *
 * See calibration.h for full documentation.
 *
 * Dependencies:
 *   Preferences   — built into ESP32 Arduino core (no install needed)
 *   Arduino.h     — analogRead, Serial, delay, millis
 */

#include "calibration.h"
#include "config.h"

#include <Arduino.h>
#include <Preferences.h>
#include <math.h>       // sqrtf

// ─────────────────────────────────────────────────────────────────────────────
//  Module-private state
// ─────────────────────────────────────────────────────────────────────────────

// In-RAM calibration (loaded from NVS on boot or captured during cal run)
static CalibrationData _cal = { {0,0,0,0}, {0,0,0,0}, false };

// NVS handle (Preferences library — ESP32 built-in flash key-value store)
static Preferences _prefs;

// ── Constant lookup tables keyed by channel index [0..3] ─────────────────────

// ADC pins — must match FSR1_PIN..FSR4_PIN in config.h
static const uint8_t _FSR_PINS[4] = {
    FSR1_PIN, FSR2_PIN, FSR3_PIN, FSR4_PIN
};

// Anatomical region names from config.h (used in JSON and diagnostics)
static const char* const _FSR_REGIONS[4] = {
    FSR1_REGION, FSR2_REGION, FSR3_REGION, FSR4_REGION
};

// Short human-readable labels for Serial column output from config.h
static const char* const _FSR_LABELS[4] = {
    FSR1_LABEL, FSR2_LABEL, FSR3_LABEL, FSR4_LABEL
};

// NVS key names — must be ≤ 15 chars (Preferences library limit)
static const char* const _NVS_KEY_BASELINE[4] = {
    "cal_b_fsr1", "cal_b_fsr2", "cal_b_fsr3", "cal_b_fsr4"
};
static const char* const _NVS_KEY_NOISE[4] = {
    "cal_n_fsr1", "cal_n_fsr2", "cal_n_fsr3", "cal_n_fsr4"
};

// ─────────────────────────────────────────────────────────────────────────────
//  Private helpers
// ─────────────────────────────────────────────────────────────────────────────

/**
 * _read_fsr_raw()
 * Take one raw ADC reading for channel i.
 * No calibration applied — used only during calibration capture itself.
 */
static uint16_t _read_fsr_raw(int i) {
    return (uint16_t) analogRead(_FSR_PINS[i]);
}

/**
 * _print_live_readings()
 * Print current raw ADC values for all 4 FSRs in a compact table.
 * Used during the pre-sampling monitoring phase so the user can confirm
 * the insole is unloaded before sampling begins.
 */
static void _print_live_readings() {
    Serial.print(F("  Live readings →  "));
    for (int i = 0; i < 4; i++) {
        uint16_t v = _read_fsr_raw(i);
        Serial.printf("FSR%d: %4d  ", i + 1, v);
    }
    Serial.println();
}

/**
 * _separator()
 * Print a horizontal rule for table formatting.
 */
static void _separator() {
    Serial.println(F("────────────────────────────────────────────────────"));
}

// ─────────────────────────────────────────────────────────────────────────────
//  calibration_load()
// ─────────────────────────────────────────────────────────────────────────────

void calibration_load() {
    _prefs.begin(NVS_NAMESPACE, /*readOnly=*/ true);

    bool found_all = true;
    for (int i = 0; i < 4; i++) {
        if (_prefs.isKey(_NVS_KEY_BASELINE[i])) {
            _cal.baseline[i] = _prefs.getUShort(_NVS_KEY_BASELINE[i], 0);
        } else {
            _cal.baseline[i] = 0;
            found_all = false;
        }
        if (_prefs.isKey(_NVS_KEY_NOISE[i])) {
            _cal.noise[i] = _prefs.getUShort(_NVS_KEY_NOISE[i], 0);
        } else {
            _cal.noise[i] = 0;
        }
    }

    _prefs.end();
    _cal.valid = found_all;

    if (DEBUG_MODE) {
        if (_cal.valid) {
            Serial.println(F("[CAL] Calibration loaded from flash."));
            calibration_print();
        } else {
            Serial.println(F("[CAL] No saved calibration — baselines set to 0."));
            Serial.println(F("      Send 'C' in Serial Monitor to calibrate,"));
            Serial.println(F("      or hold BOOT button on next power-on."));
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
//  calibration_run()
// ─────────────────────────────────────────────────────────────────────────────

void calibration_run() {

    Serial.println();
    _separator();
    Serial.println(F("   SOLESENSE  —  FSR BASELINE CALIBRATION"));
    _separator();
    Serial.println();
    Serial.println(F("PURPOSE"));
    Serial.println(F("  Measures the resting ADC value for each FSR when no"));
    Serial.println(F("  weight is applied.  Future readings will subtract this"));
    Serial.println(F("  baseline so that 0 = no load."));
    Serial.println();
    Serial.println(F("⚠  IMPORTANT: calibrated values are RELATIVE LOAD PROXIES."));
    Serial.println(F("   They are NOT Newtons, kg, kPa, or any clinical unit."));
    Serial.println();

    // ── Step 1: Preparation ───────────────────────────────────────────────────
    Serial.println(F("STEP 1 — PREPARE THE INSOLE"));
    Serial.println(F("  • Place the insole on a flat surface."));
    Serial.println(F("  • Make sure NO weight is pressing on any FSR."));
    Serial.println(F("  • Keep the insole still throughout calibration."));
    Serial.println();
    Serial.printf( "  Waiting %d seconds for you to remove all weight...\n",
                   CAL_SETTLE_MS / 1000);

    delay(CAL_SETTLE_MS);

    // ── Step 2: Live monitoring — let user verify readings are stable ──────────
    Serial.println();
    Serial.println(F("STEP 2 — VERIFY READINGS ARE STABLE"));
    Serial.println(F("  The values below should be LOW (near 0–50 ADC counts)."));
    Serial.println(F("  If any value is HIGH (> 200), something is pressing the insole."));
    Serial.println();

    const uint32_t MONITOR_DURATION_MS = 3000;  // 3 s of live preview
    const uint32_t MONITOR_INTERVAL_MS = 500;
    uint32_t monitor_start = millis();

    while (millis() - monitor_start < MONITOR_DURATION_MS) {
        _print_live_readings();
        delay(MONITOR_INTERVAL_MS);
    }

    Serial.println();
    Serial.println(F("  If readings look correct (low, stable), send any key to"));
    Serial.println(F("  START SAMPLING.  Otherwise remove weight and reset."));
    Serial.println(F("  Waiting for keypress..."));

    // Drain any stale bytes already in the buffer
    while (Serial.available()) Serial.read();

    // Block until user sends any character (or auto-proceed after 10 s)
    uint32_t wait_start = millis();
    while (!Serial.available()) {
        if (millis() - wait_start > 10000UL) {
            Serial.println(F("  (auto-proceeding after 10 s timeout)"));
            break;
        }
        delay(50);
    }
    while (Serial.available()) Serial.read();   // flush

    // ── Step 3: Collect samples ───────────────────────────────────────────────
    Serial.println();
    Serial.println(F("STEP 3 — SAMPLING  (do NOT touch the insole)"));
    Serial.printf( "  Collecting %d samples per channel × %d ms = %.1f seconds...\n",
                   CAL_SAMPLES, CAL_SAMPLE_DELAY_MS,
                   (float)(CAL_SAMPLES * CAL_SAMPLE_DELAY_MS) / 1000.0f);

    // Accumulators for mean and variance (Welford online algorithm for numerics)
    float  mean[4]  = {0};
    float  M2[4]    = {0};   // sum of squared deviations

    for (int s = 0; s < CAL_SAMPLES; s++) {
        for (int i = 0; i < 4; i++) {
            float x   = (float) _read_fsr_raw(i);
            float delta = x - mean[i];
            mean[i]  += delta / (float)(s + 1);
            M2[i]    += delta * (x - mean[i]);
        }
        delay(CAL_SAMPLE_DELAY_MS);

        // Progress dots — one dot every 20 samples
        if ((s + 1) % 20 == 0) {
            Serial.print('.');
            if ((s + 1) % 100 == 0) {
                Serial.printf(" %d%%\n", (s + 1) * 100 / CAL_SAMPLES);
            }
        }
    }
    Serial.println(F(" Done."));

    // ── Step 4: Compute std-dev, check noise, save ────────────────────────────
    Serial.println();
    Serial.println(F("STEP 4 — RESULTS"));
    _separator();

    bool noise_warn = false;
    for (int i = 0; i < 4; i++) {
        _cal.baseline[i] = (uint16_t) roundf(mean[i]);
        float variance   = (CAL_SAMPLES > 1) ? M2[i] / (float)(CAL_SAMPLES - 1) : 0.0f;
        _cal.noise[i]    = (uint16_t) roundf(sqrtf(variance));

        if (_cal.noise[i] > (uint16_t)CAL_NOISE_WARN_ADC) {
            noise_warn = true;
        }
    }

    _cal.valid = true;

    // Save to NVS
    _prefs.begin(NVS_NAMESPACE, /*readOnly=*/ false);
    for (int i = 0; i < 4; i++) {
        _prefs.putUShort(_NVS_KEY_BASELINE[i], _cal.baseline[i]);
        _prefs.putUShort(_NVS_KEY_NOISE[i],    _cal.noise[i]);
    }
    _prefs.end();

    // Print the result table
    calibration_print();

    // Noise warning
    if (noise_warn) {
        Serial.println();
        Serial.println(F("⚠  NOISE WARNING"));
        Serial.println(F("   One or more channels showed high variability during sampling."));
        Serial.printf( "   Threshold: %d ADC counts\n", CAL_NOISE_WARN_ADC);
        Serial.println(F("   Possible causes:"));
        Serial.println(F("     - Loose wire or connector"));
        Serial.println(F("     - Mechanical vibration (place on stable surface)"));
        Serial.println(F("     - Electrical interference near power supply"));
        Serial.println(F("   Calibration was saved but consider re-running after"));
        Serial.println(F("   checking wiring."));
    } else {
        Serial.println(F("✓  Noise levels OK."));
    }

    // ── Step 5: Confirm ───────────────────────────────────────────────────────
    Serial.println();
    _separator();
    Serial.println(F("  Calibration SAVED to flash.  Baselines will persist"));
    Serial.println(F("  across power cycles."));
    Serial.println();
    Serial.println(F("  To re-calibrate:  send 'C' in Serial Monitor"));
    Serial.println(F("  To erase:         send 'E' in Serial Monitor"));
    _separator();
    Serial.println();

    Serial.println(F("  Resuming sensor loop in 3 seconds..."));
    delay(3000);
}

// ─────────────────────────────────────────────────────────────────────────────
//  calibration_get()
// ─────────────────────────────────────────────────────────────────────────────

const CalibrationData &calibration_get() {
    return _cal;
}

// ─────────────────────────────────────────────────────────────────────────────
//  calibration_print()
// ─────────────────────────────────────────────────────────────────────────────

void calibration_print() {
    Serial.println();
    Serial.println(F("─── FSR Calibration Baselines ──────────────────────────"));
    Serial.printf( " %-3s  %-20s  %-10s  %-5s\n",
                   "Ch", "Region", "Baseline", "Noise");
    Serial.println(F("────────────────────────────────────────────────────────"));

    for (int i = 0; i < 4; i++) {
        Serial.printf(" %d    %-20s  %4d ADC    %3d ADC",
                      i + 1,
                      _FSR_LABELS[i],
                      _cal.baseline[i],
                      _cal.noise[i]);
        if (_cal.noise[i] > (uint16_t)CAL_NOISE_WARN_ADC) {
            Serial.print(F("  ⚠ noisy"));
        }
        Serial.println();
    }

    Serial.println(F("────────────────────────────────────────────────────────"));
    Serial.println(F(" ⚠ Values are relative load proxies — NOT kPa or Newtons."));
    Serial.println();

    if (!_cal.valid) {
        Serial.println(F(" [UNCALIBRATED — baselines default to 0]"));
    }
}

// ─────────────────────────────────────────────────────────────────────────────
//  calibration_status()
// ─────────────────────────────────────────────────────────────────────────────

void calibration_status() {
    if (_cal.valid) {
        // Count how many channels have a non-zero baseline
        int n = 0;
        for (int i = 0; i < 4; i++) {
            if (_cal.baseline[i] > 0) n++;
        }
        Serial.printf("[CAL] Status: CALIBRATED (%d/4 channels have baseline > 0)\n", n);
    } else {
        Serial.println(F("[CAL] Status: NOT CALIBRATED (no saved data — using baseline = 0)"));
    }
}

// ─────────────────────────────────────────────────────────────────────────────
//  calibration_erase()
// ─────────────────────────────────────────────────────────────────────────────

void calibration_erase() {
    _prefs.begin(NVS_NAMESPACE, /*readOnly=*/ false);
    _prefs.clear();
    _prefs.end();

    for (int i = 0; i < 4; i++) {
        _cal.baseline[i] = 0;
        _cal.noise[i]    = 0;
    }
    _cal.valid = false;

    Serial.println(F("[CAL] Calibration erased from flash.  Baselines reset to 0."));
    Serial.println(F("      Send 'C' to run calibration again."));
}

// ─────────────────────────────────────────────────────────────────────────────
//  calibration_is_valid()
// ─────────────────────────────────────────────────────────────────────────────

bool calibration_is_valid() {
    return _cal.valid;
}
