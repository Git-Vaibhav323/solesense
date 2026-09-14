/**
 * SoleSense ESP32-S3 Firmware
 * sensors.cpp  —  sensor driver implementation
 *
 * ─── Required Arduino libraries ────────────────────────────────────────────
 *  Library name                    Author          Install via
 *  ──────────────────────────────  ──────────────  ─────────────────────────
 *  Adafruit MPU6050                Adafruit        Arduino Library Manager
 *  Adafruit BusIO                  Adafruit        (dependency, auto-installed)
 *  Adafruit Unified Sensor         Adafruit        (dependency, auto-installed)
 *  SparkFun TMP117 Arduino Library SparkFun        Arduino Library Manager
 *
 *  Search exact names above in Library Manager → Install.
 *  Board package: "esp32" by Espressif ≥ 2.0.14
 *  Board target : ESP32S3 Dev Module
 * ───────────────────────────────────────────────────────────────────────────
 */

#include "sensors.h"
#include "config.h"
#include "calibration.h"

#include <Arduino.h>
#include <Wire.h>

// Adafruit MPU6050 library
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

// SparkFun TMP117 library
#include <SparkFun_TMP117.h>

// ─────────────────────────────────────────────────────────────────────────────
//  Module-private state
// ─────────────────────────────────────────────────────────────────────────────

static Adafruit_MPU6050 _mpu;
static TMP117           _tmp117;

static bool _tmp_ok = false;
static bool _mpu_ok = false;

// Cache last valid TMP117 reading — TMP117 updates at ~4 Hz, sensor loop runs
// at 20 Hz, so we hold the last good value between updates.
static float _last_temp_c = 25.0f;

// ─────────────────────────────────────────────────────────────────────────────
//  sensors_init()
// ─────────────────────────────────────────────────────────────────────────────

bool sensors_init() {

    // ── I²C bus ──────────────────────────────────────────────────────────────
    // SDA and SCL are defined in config.h (default GPIO 8, 9).
    // 400 kHz fast-mode is supported by both TMP117 and MPU6050.
    Wire.begin(I2C_SDA, I2C_SCL);
    Wire.setClock(400000UL);

    // ── TMP117 ───────────────────────────────────────────────────────────────
    // SparkFun library: begin(address, wire_instance)
    // Default I²C address with ADD0 → GND : 0x48
    // Default I²C address with ADD0 → VCC : 0x49
    // Change TMP117_I2C_ADDR in config.h if your breakout uses a different jumper.
    _tmp_ok = _tmp117.begin(TMP117_I2C_ADDR, Wire);

    if (_tmp_ok) {
        // One-shot or continuous conversion mode (default is continuous, 1 Hz).
        // For 20 Hz sensor loop the default is fine; the read function checks
        // dataReady() and holds the previous value until a new sample arrives.
        Serial.println(F("[TMP117] Found — temperature sensor ready"));
    } else {
        Serial.println(F("[TMP117] NOT FOUND — check wiring and I2C address"));
        Serial.printf (  "         Expected address: 0x%02X  (SDA=GPIO%d  SCL=GPIO%d)\n",
                         TMP117_I2C_ADDR, I2C_SDA, I2C_SCL);
    }

    // ── MPU6050 ──────────────────────────────────────────────────────────────
    // Adafruit library: begin(address, wire_instance)
    // Default I²C address with AD0 → GND : 0x68
    // Default I²C address with AD0 → VCC : 0x69
    // Change MPU6050_I2C_ADDR in config.h if needed.
    _mpu_ok = _mpu.begin(MPU6050_I2C_ADDR, &Wire);

    if (_mpu_ok) {
        // ±4 g range balances sensitivity and headroom for gait impacts
        _mpu.setAccelerometerRange(MPU6050_RANGE_4_G);

        // ±500 °/s covers normal walking angular velocities
        _mpu.setGyroRange(MPU6050_RANGE_500_DEG);

        // 21 Hz DLPF removes high-frequency vibration noise while preserving
        // gait-relevant signals (step frequency typically 1–3 Hz)
        _mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

        Serial.println(F("[MPU6050] Found — IMU ready (±4g, ±500°/s, 21Hz DLPF)"));
    } else {
        Serial.println(F("[MPU6050] NOT FOUND — check wiring and I2C address"));
        Serial.printf (  "          Expected address: 0x%02X  (SDA=GPIO%d  SCL=GPIO%d)\n",
                         MPU6050_I2C_ADDR, I2C_SDA, I2C_SCL);
    }

    // FSR pins are purely analog inputs.  No pinMode() call needed; the ADC
    // is configured via analogReadResolution() and analogSetAttenuation()
    // in the main .ino before sensors_init() is called.

    return _tmp_ok && _mpu_ok;
}

// ─────────────────────────────────────────────────────────────────────────────
//  sensors_read()
// ─────────────────────────────────────────────────────────────────────────────

void sensors_read(SensorPacket &pkt) {

    pkt.timestamp_ms = millis();

    // ── FSR channels ─────────────────────────────────────────────────────────
    // Only FSR1 and FSR2 are physically connected (FSR_COUNT = 2).
    // FSR3 and FSR4 slots are zeroed so the JSON schema stays unchanged.
    const uint8_t fsr_pins[4] = { FSR1_PIN, FSR2_PIN, FSR3_PIN, FSR4_PIN };
    const CalibrationData &cal = calibration_get();

    for (int i = 0; i < 4; i++) {
        if (i < FSR_COUNT) {
            // Active sensor — read and apply calibration baseline
            pkt.fsr.raw[i] = (uint16_t) analogRead(fsr_pins[i]);
            int32_t corrected = (int32_t)pkt.fsr.raw[i] - (int32_t)cal.baseline[i];
            pkt.fsr.calibrated[i] = (uint16_t) max(0L, corrected);
        } else {
            // Unused channel — zero both slots
            pkt.fsr.raw[i]        = 0;
            pkt.fsr.calibrated[i] = 0;
        }
    }

    // ── TMP117 ───────────────────────────────────────────────────────────────
    pkt.tmp117.ok = _tmp_ok;

    if (_tmp_ok) {
        // dataReady() polls the EEPROM_BUSY bit — true when a new conversion
        // result is available.  Default conversion cycle is ~1 s (1 Hz).
        // At 20 Hz sensor loop we simply hold the previous reading.
        if (_tmp117.dataReady()) {
            _last_temp_c = _tmp117.readTempC();
        }
        pkt.tmp117.temperature_c = _last_temp_c;
    } else {
        pkt.tmp117.temperature_c = -999.0f;   // sentinel: unavailable
    }

    // ── MPU6050 ──────────────────────────────────────────────────────────────
    pkt.mpu.ok = _mpu_ok;

    if (_mpu_ok) {
        sensors_event_t accel_evt, gyro_evt, temp_evt;
        _mpu.getEvent(&accel_evt, &gyro_evt, &temp_evt);

        // Adafruit library returns acceleration in m/s² → convert to g
        pkt.mpu.ax = accel_evt.acceleration.x / 9.80665f;
        pkt.mpu.ay = accel_evt.acceleration.y / 9.80665f;
        pkt.mpu.az = accel_evt.acceleration.z / 9.80665f;

        // Gyroscope in rad/s → convert to °/s
        pkt.mpu.gx = gyro_evt.gyro.x * (180.0f / PI);
        pkt.mpu.gy = gyro_evt.gyro.y * (180.0f / PI);
        pkt.mpu.gz = gyro_evt.gyro.z * (180.0f / PI);
    } else {
        pkt.mpu.ax = pkt.mpu.ay = pkt.mpu.az = 0.0f;
        pkt.mpu.gx = pkt.mpu.gy = pkt.mpu.gz = 0.0f;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
//  sensors_diagnostic()
// ─────────────────────────────────────────────────────────────────────────────

void sensors_diagnostic() {
    // Take a fresh live reading for the diagnostic
    SensorPacket pkt;
    sensors_read(pkt);

    Serial.println();
    Serial.println(F("===== SOLESENSE SENSOR DIAGNOSTIC ====="));

    // ── FSR ──────────────────────────────────────────────────────────────────
    // Output format required by TASK 3:  FSR1: <value>
    // Shows calibrated (baseline-subtracted) value.
    // Raw ADC value shown in parentheses for reference.
    Serial.printf("FSR1: %d  (raw %d)  [%s]\n",
                  pkt.fsr.calibrated[0], pkt.fsr.raw[0], FSR1_LABEL);
    Serial.printf("FSR2: %d  (raw %d)  [%s]\n",
                  pkt.fsr.calibrated[1], pkt.fsr.raw[1], FSR2_LABEL);
    Serial.println(F("FSR3: not connected"));
    Serial.println(F("FSR4: not connected"));

    // ── Temperature ──────────────────────────────────────────────────────────
    if (pkt.tmp117.ok) {
        Serial.printf("TEMP: %.2f C\n", pkt.tmp117.temperature_c);
    } else {
        Serial.println(F("TEMP: NOT FOUND — check wiring (SDA/SCL) and I2C address"));
    }

    // ── IMU ───────────────────────────────────────────────────────────────────
    if (pkt.mpu.ok) {
        Serial.printf("AX: %.4f\n", pkt.mpu.ax);
        Serial.printf("AY: %.4f\n", pkt.mpu.ay);
        Serial.printf("AZ: %.4f\n", pkt.mpu.az);
        Serial.printf("GX: %.4f\n", pkt.mpu.gx);
        Serial.printf("GY: %.4f\n", pkt.mpu.gy);
        Serial.printf("GZ: %.4f\n", pkt.mpu.gz);
    } else {
        Serial.println(F("AX: NOT FOUND"));
        Serial.println(F("AY: NOT FOUND"));
        Serial.println(F("AZ: NOT FOUND"));
        Serial.println(F("GX: NOT FOUND"));
        Serial.println(F("GY: NOT FOUND"));
        Serial.println(F("GZ: NOT FOUND"));
        Serial.println(F("MPU6050: check wiring (SDA/SCL) and I2C address"));
    }

    Serial.println(F("========================================"));
    Serial.println();
}

// ─────────────────────────────────────────────────────────────────────────────
//  Status accessors
// ─────────────────────────────────────────────────────────────────────────────

bool sensors_tmp117_ok()  { return _tmp_ok;  }
bool sensors_mpu6050_ok() { return _mpu_ok;  }
