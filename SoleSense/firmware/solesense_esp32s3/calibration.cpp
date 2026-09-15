/**
 * SoleSense ESP32-S3 Firmware
 * calibration.cpp — FSR baseline calibration  (2 channels)
 */

#include "calibration.h"
#include "config.h"
#include <Arduino.h>
#include <Preferences.h>
#include <math.h>

// ── State ─────────────────────────────────────────────────────────────────────
static CalibrationData _cal  = { {0, 0}, {0, 0}, false };
static Preferences     _prefs;

// Channel lookup tables (index 0 = FSR1, index 1 = FSR2)
static const uint8_t       _PINS[2]          = { FSR1_PIN,      FSR2_PIN      };
static const char* const   _LABELS[2]        = { FSR1_LABEL,    FSR2_LABEL    };
static const char* const   _NVS_BASE[2]      = { "cal_b_fsr1",  "cal_b_fsr2"  };
static const char* const   _NVS_NOISE[2]     = { "cal_n_fsr1",  "cal_n_fsr2"  };

// ── Helpers ───────────────────────────────────────────────────────────────────
static uint16_t _raw(int i)  { return (uint16_t)analogRead(_PINS[i]); }

static void _sep() {
    Serial.println(F("────────────────────────────────────────────────"));
}

static void _print_live() {
    Serial.print(F("  Live → "));
    for (int i = 0; i < FSR_COUNT; i++)
        Serial.printf("FSR%d: %4d  ", i + 1, _raw(i));
    Serial.println();
}

// ── calibration_load ──────────────────────────────────────────────────────────
void calibration_load() {
    _prefs.begin(NVS_NAMESPACE, true);
    bool ok = true;
    for (int i = 0; i < FSR_COUNT; i++) {
        if (_prefs.isKey(_NVS_BASE[i])) {
            _cal.baseline[i] = _prefs.getUShort(_NVS_BASE[i], 0);
            _cal.noise[i]    = _prefs.getUShort(_NVS_NOISE[i], 0);
        } else {
            _cal.baseline[i] = _cal.noise[i] = 0;
            ok = false;
        }
    }
    _prefs.end();
    _cal.valid = ok;

    if (DEBUG_MODE) {
        if (_cal.valid) {
            Serial.println(F("[CAL] Calibration loaded from flash."));
            calibration_print();
        } else {
            Serial.println(F("[CAL] No saved calibration — baselines = 0."));
            Serial.println(F("      Send 'C' to calibrate, or hold BOOT on power-on."));
        }
    }
}

// ── calibration_run ───────────────────────────────────────────────────────────
void calibration_run() {
    Serial.println();
    _sep();
    Serial.println(F("   SOLESENSE — FSR BASELINE CALIBRATION"));
    _sep();
    Serial.println(F("⚠  Output is a RELATIVE LOAD PROXY — NOT kPa or Newtons."));
    Serial.println();
    Serial.println(F("STEP 1 — Remove ALL weight from the insole."));
    Serial.printf( "         Waiting %d s...\n", CAL_SETTLE_MS / 1000);
    delay(CAL_SETTLE_MS);

    Serial.println();
    Serial.println(F("STEP 2 — Verify readings (should be near 0–50):"));
    uint32_t t0 = millis();
    while (millis() - t0 < 3000) { _print_live(); delay(500); }

    Serial.println();
    Serial.println(F("Send any key to START SAMPLING, or wait 10 s to auto-proceed."));
    while (Serial.available()) Serial.read();
    uint32_t ws = millis();
    while (!Serial.available() && millis() - ws < 10000) delay(50);
    while (Serial.available()) Serial.read();

    Serial.println();
    Serial.println(F("STEP 3 — SAMPLING (do NOT touch insole)..."));
    Serial.printf( "         %d samples × %d ms = %.1f s\n",
                   CAL_SAMPLES, CAL_SAMPLE_DELAY_MS,
                   (float)(CAL_SAMPLES * CAL_SAMPLE_DELAY_MS) / 1000.0f);

    float mean[2] = {0}, M2[2] = {0};
    for (int s = 0; s < CAL_SAMPLES; s++) {
        for (int i = 0; i < FSR_COUNT; i++) {
            float x     = (float)_raw(i);
            float delta = x - mean[i];
            mean[i] += delta / (float)(s + 1);
            M2[i]   += delta * (x - mean[i]);
        }
        delay(CAL_SAMPLE_DELAY_MS);
        if ((s + 1) % 20 == 0) {
            Serial.print('.');
            if ((s + 1) % 100 == 0)
                Serial.printf(" %d%%\n", (s + 1) * 100 / CAL_SAMPLES);
        }
    }
    Serial.println(F(" Done."));

    // Save
    bool noise_warn = false;
    _prefs.begin(NVS_NAMESPACE, false);
    for (int i = 0; i < FSR_COUNT; i++) {
        _cal.baseline[i] = (uint16_t)roundf(mean[i]);
        float var        = (CAL_SAMPLES > 1) ? M2[i] / (float)(CAL_SAMPLES - 1) : 0.0f;
        _cal.noise[i]    = (uint16_t)roundf(sqrtf(var));
        _prefs.putUShort(_NVS_BASE[i],  _cal.baseline[i]);
        _prefs.putUShort(_NVS_NOISE[i], _cal.noise[i]);
        if (_cal.noise[i] > (uint16_t)CAL_NOISE_WARN_ADC) noise_warn = true;
    }
    _prefs.end();
    _cal.valid = true;

    calibration_print();

    if (noise_warn) {
        Serial.println(F("⚠  NOISE WARNING — check wiring or reduce vibration."));
    } else {
        Serial.println(F("✓  Noise OK."));
    }

    _sep();
    Serial.println(F("  Calibration SAVED. Resuming in 3 s..."));
    _sep();
    delay(3000);
}

// ── calibration_get ───────────────────────────────────────────────────────────
const CalibrationData &calibration_get() { return _cal; }

// ── calibration_print ─────────────────────────────────────────────────────────
void calibration_print() {
    Serial.println();
    Serial.println(F("─── FSR Calibration Baselines ──────────────────"));
    Serial.printf( " %-3s  %-10s  %-10s  %-6s\n",
                   "Ch", "Region", "Baseline", "Noise");
    Serial.println(F("────────────────────────────────────────────────"));
    const char* regions[2] = { FSR1_REGION, FSR2_REGION };
    for (int i = 0; i < FSR_COUNT; i++) {
        Serial.printf(" %d    %-10s  %4d ADC    %3d ADC%s\n",
                      i + 1, regions[i],
                      _cal.baseline[i], _cal.noise[i],
                      _cal.noise[i] > (uint16_t)CAL_NOISE_WARN_ADC ? "  ⚠" : "");
    }
    Serial.println(F("────────────────────────────────────────────────"));
    Serial.println(F(" ⚠ Relative load proxies — NOT kPa or Newtons."));
    Serial.println();
}

// ── calibration_status ────────────────────────────────────────────────────────
void calibration_status() {
    if (_cal.valid) {
        int n = 0;
        for (int i = 0; i < FSR_COUNT; i++) if (_cal.baseline[i] > 0) n++;
        Serial.printf("[CAL] CALIBRATED (%d/%d channels have baseline > 0)\n",
                      n, FSR_COUNT);
    } else {
        Serial.println(F("[CAL] NOT CALIBRATED — using baseline = 0"));
    }
}

// ── calibration_erase ─────────────────────────────────────────────────────────
void calibration_erase() {
    _prefs.begin(NVS_NAMESPACE, false);
    _prefs.clear();
    _prefs.end();
    for (int i = 0; i < FSR_COUNT; i++) _cal.baseline[i] = _cal.noise[i] = 0;
    _cal.valid = false;
    Serial.println(F("[CAL] Erased. Send 'C' to recalibrate."));
}

// ── calibration_is_valid ──────────────────────────────────────────────────────
bool calibration_is_valid() { return _cal.valid; }
