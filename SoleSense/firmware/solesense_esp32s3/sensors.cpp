/**
 * SoleSense ESP32-S3 Firmware
 * sensors.cpp — sensor driver implementation
 *
 * ─── Required Arduino libraries ─────────────────────────────────────────────
 *  Library                   Author          Install via
 *  ─────────────────────────────────────────────────────
 *  Adafruit MPU6050          Adafruit        Library Manager
 *  Adafruit BusIO            Adafruit        (auto-installed as dependency)
 *  Adafruit Unified Sensor   Adafruit        (auto-installed as dependency)
 *  OneWire                   Paul Stoffregen Library Manager
 *  DallasTemperature         Miles Burton    Library Manager
 *
 *  Board package: "esp32" by Espressif ≥ 2.0.14
 *  Board target : ESP32S3 Dev Module
 * ────────────────────────────────────────────────────────────────────────────
 */

#include "sensors.h"
#include "config.h"
#include "calibration.h"

#include <Arduino.h>
#include <Wire.h>

// MPU6050
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

// DS18B20
#include <OneWire.h>
#include <DallasTemperature.h>

// ─────────────────────────────────────────────────────────────────────────────
//  Module-private state
// ─────────────────────────────────────────────────────────────────────────────

// MPU6050
static Adafruit_MPU6050 _mpu;
static bool             _mpu_ok = false;

// DS18B20
static OneWire           _ow(DS18B20_PIN);
static DallasTemperature _dallas(&_ow);
static uint8_t           _ds_count = 0;

// Cached temperature values — updated whenever a conversion is ready.
// -127.0 is the DS18B20 library's error sentinel.
static float _last_temp[2] = { -127.0f, -127.0f };

// Tracks when the last asynchronous conversion was requested
static uint32_t _conv_requested_ms = 0;
static bool     _conv_in_flight    = false;

// ─────────────────────────────────────────────────────────────────────────────
//  sensors_init()
// ─────────────────────────────────────────────────────────────────────────────

bool sensors_init() {

    // ── I²C (MPU6050) ─────────────────────────────────────────────────────────
    Wire.begin(I2C_SDA, I2C_SCL);
    Wire.setClock(400000UL);

    _mpu_ok = _mpu.begin(MPU6050_I2C_ADDR, &Wire);
    if (_mpu_ok) {
        _mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
        _mpu.setGyroRange(MPU6050_RANGE_500_DEG);
        _mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
        Serial.println(F("[MPU6050] Found  (±4g, ±500°/s, 21Hz DLPF)"));
    } else {
        Serial.printf("[MPU6050] NOT FOUND — check SDA=GPIO%d SCL=GPIO%d addr=0x%02X\n",
                      I2C_SDA, I2C_SCL, MPU6050_I2C_ADDR);
    }

    // ── DS18B20 (1-Wire) ──────────────────────────────────────────────────────
    _dallas.begin();
    _ds_count = (uint8_t)_dallas.getDeviceCount();

    if (_ds_count == 0) {
        Serial.printf("[DS18B20] NOT FOUND — check GPIO%d wiring and 4.7kΩ pull-up\n",
                      DS18B20_PIN);
    } else {
        Serial.printf("[DS18B20] Found %d sensor(s) on GPIO%d\n",
                      _ds_count, DS18B20_PIN);

        // Set resolution and switch to async (non-blocking) mode
        _dallas.setResolution(DS18B20_RESOLUTION);
        _dallas.setWaitForConversion(false);   // non-blocking reads

        // Print device addresses for identification
        for (uint8_t i = 0; i < _ds_count && i < 2; i++) {
            DeviceAddress addr;
            if (_dallas.getAddress(addr, i)) {
                Serial.printf("  TEMP%d address: ", i + 1);
                for (uint8_t b = 0; b < 8; b++) {
                    Serial.printf("%02X", addr[b]);
                    if (b < 7) Serial.print(':');
                }
                Serial.println();
            }
        }

        // Kick off first conversion immediately
        _dallas.requestTemperatures();
        _conv_requested_ms = millis();
        _conv_in_flight    = true;
    }

    // FSR pins are ADC inputs — configured via analogReadResolution()
    // and analogSetAttenuation() in the main .ino before sensors_init().

    return _mpu_ok && (_ds_count > 0);
}

// ─────────────────────────────────────────────────────────────────────────────
//  sensors_read()
// ─────────────────────────────────────────────────────────────────────────────

void sensors_read(SensorPacket &pkt) {

    pkt.timestamp_ms = millis();

    // ── FSR (2 channels) ──────────────────────────────────────────────────────
    const uint8_t fsr_pins[FSR_COUNT] = { FSR1_PIN, FSR2_PIN };
    const CalibrationData &cal = calibration_get();

    for (int i = 0; i < FSR_COUNT; i++) {
        pkt.fsr.raw[i] = (uint16_t)analogRead(fsr_pins[i]);
        int32_t corr   = (int32_t)pkt.fsr.raw[i] - (int32_t)cal.baseline[i];
        pkt.fsr.calibrated[i] = (uint16_t)max(0L, corr);
    }

    // ── DS18B20 (non-blocking) ────────────────────────────────────────────────
    pkt.ds18b20.sensor_count = _ds_count;

    if (_ds_count > 0) {
        // Has enough time elapsed for the conversion to finish?
        bool conv_ready = _conv_in_flight &&
                          (millis() - _conv_requested_ms >= DS18B20_CONVERT_MS);

        if (conv_ready) {
            // Retrieve results
            for (uint8_t i = 0; i < _ds_count && i < 2; i++) {
                float t = _dallas.getTempCByIndex(i);
                if (t > -120.0f) {          // -127 = error, reject
                    _last_temp[i] = t;
                }
            }
            // Immediately request the next conversion
            _dallas.requestTemperatures();
            _conv_requested_ms = millis();
        }

        // Expose last good readings (held between updates)
        pkt.ds18b20.temperature_c[0] = _last_temp[0];
        pkt.ds18b20.temperature_c[1] = (_ds_count >= 2) ? _last_temp[1] : -127.0f;
        pkt.ds18b20.ok = (_last_temp[0] > -120.0f);

    } else {
        pkt.ds18b20.temperature_c[0] = -127.0f;
        pkt.ds18b20.temperature_c[1] = -127.0f;
        pkt.ds18b20.ok               = false;
    }

    // ── MPU6050 ───────────────────────────────────────────────────────────────
    pkt.mpu.ok = _mpu_ok;
    if (_mpu_ok) {
        sensors_event_t a, g, t;
        _mpu.getEvent(&a, &g, &t);
        pkt.mpu.ax = a.acceleration.x / 9.80665f;
        pkt.mpu.ay = a.acceleration.y / 9.80665f;
        pkt.mpu.az = a.acceleration.z / 9.80665f;
        pkt.mpu.gx = g.gyro.x * (180.0f / PI);
        pkt.mpu.gy = g.gyro.y * (180.0f / PI);
        pkt.mpu.gz = g.gyro.z * (180.0f / PI);
    } else {
        pkt.mpu.ax = pkt.mpu.ay = pkt.mpu.az = 0.0f;
        pkt.mpu.gx = pkt.mpu.gy = pkt.mpu.gz = 0.0f;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
//  sensors_diagnostic()
// ─────────────────────────────────────────────────────────────────────────────

void sensors_diagnostic() {
    SensorPacket pkt;
    sensors_read(pkt);

    Serial.println();
    Serial.println(F("===== SOLESENSE SENSOR DIAGNOSTIC ====="));

    // FSR
    Serial.printf("FSR1: %d  (raw %d)  [%s]\n",
                  pkt.fsr.calibrated[0], pkt.fsr.raw[0], FSR1_LABEL);
    Serial.printf("FSR2: %d  (raw %d)  [%s]\n",
                  pkt.fsr.calibrated[1], pkt.fsr.raw[1], FSR2_LABEL);

    // DS18B20
    if (pkt.ds18b20.ok) {
        if (pkt.ds18b20.temperature_c[0] > -120.0f)
            Serial.printf("TEMP1: %.2f C\n", pkt.ds18b20.temperature_c[0]);
        else
            Serial.println(F("TEMP1: error"));

        if (pkt.ds18b20.sensor_count >= 2) {
            if (pkt.ds18b20.temperature_c[1] > -120.0f)
                Serial.printf("TEMP2: %.2f C\n", pkt.ds18b20.temperature_c[1]);
            else
                Serial.println(F("TEMP2: error"));
        } else {
            Serial.println(F("TEMP2: not found"));
        }
    } else {
        Serial.println(F("TEMP1: NOT FOUND"));
        Serial.println(F("TEMP2: NOT FOUND"));
        Serial.printf( "       Check GPIO%d wiring and 4.7kΩ pull-up to 3.3V\n",
                       DS18B20_PIN);
    }

    // MPU6050
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
        Serial.printf( "MPU6050: check SDA=GPIO%d SCL=GPIO%d addr=0x%02X\n",
                       I2C_SDA, I2C_SCL, MPU6050_I2C_ADDR);
    }

    Serial.println(F("========================================"));
    Serial.println();
}

// ─────────────────────────────────────────────────────────────────────────────
//  Accessors
// ─────────────────────────────────────────────────────────────────────────────

bool    sensors_mpu6050_ok()    { return _mpu_ok;   }
uint8_t sensors_ds18b20_count() { return _ds_count; }
