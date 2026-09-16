/**
 * SoleSense ESP32-S3 Firmware
 * sensors.cpp — sensor driver implementation
 *
 * Sensors:
 *   - 2 × FSR
 *   - MPU6050
 *   - Up to 2 × DS18B20
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
// Module-private state
// ─────────────────────────────────────────────────────────────────────────────

// MPU6050
static Adafruit_MPU6050 _mpu;
static bool _mpu_ok = false;

// DS18B20
static OneWire _ow(DS18B20_PIN);
static DallasTemperature _dallas(&_ow);
static uint8_t _ds_count = 0;

// Cached temperature values
// -127.0 = DS18B20 error/not available
static float _last_temp[2] = { -127.0f, -127.0f };

// Tracks asynchronous temperature conversion
static uint32_t _conv_requested_ms = 0;
static bool _conv_in_flight = false;


// ─────────────────────────────────────────────────────────────────────────────
// sensors_init()
// ─────────────────────────────────────────────────────────────────────────────

bool sensors_init() {

    // ── I²C / MPU6050 ────────────────────────────────────────────────────────

    Wire.begin(I2C_SDA, I2C_SCL);

    // Use 100 kHz for reliable MPU6050 communication
    Wire.setClock(100000UL);

    Serial.println();
    Serial.println(F("[I2C] Initializing MPU6050..."));

    // Check whether the MPU6050 responds at its configured address.
    Wire.beginTransmission(MPU6050_I2C_ADDR);
    uint8_t mpu_probe_error = Wire.endTransmission();

    if (mpu_probe_error == 0) {

        Serial.printf(
            "[I2C] Device found at address 0x%02X\n",
            MPU6050_I2C_ADDR
        );

        /*
         * Initialize Adafruit MPU6050 object.
         *
         * The I²C probe is used as the actual presence check because
         * some compatible MPU6050 boards can return FALSE from begin()
         * even when the device responds correctly.
         */
        bool begin_result = _mpu.begin(MPU6050_I2C_ADDR, &Wire);

        Serial.printf(
            "[MPU6050] Adafruit begin() returned: %s\n",
            begin_result ? "TRUE" : "FALSE"
        );

        _mpu_ok = true;

        // Accelerometer
        _mpu.setAccelerometerRange(MPU6050_RANGE_4_G);

        // Gyroscope
        _mpu.setGyroRange(MPU6050_RANGE_500_DEG);

        // Low-pass filter suitable for gait movement
        _mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

        Serial.println(
            F("[MPU6050] Found at 0x68 — IMU ready")
        );

        Serial.println(
            F("[MPU6050] Accelerometer: ±4g")
        );

        Serial.println(
            F("[MPU6050] Gyroscope: ±500 deg/s")
        );

        Serial.println(
            F("[MPU6050] Filter: 21Hz")
        );

    } else {

        _mpu_ok = false;

        Serial.printf(
            "[MPU6050] NOT FOUND — SDA=GPIO%d SCL=GPIO%d addr=0x%02X\n",
            I2C_SDA,
            I2C_SCL,
            MPU6050_I2C_ADDR
        );
    }


    // ── DS18B20 / 1-Wire ─────────────────────────────────────────────────────

    Serial.println(
        F("[DS18B20] Initializing...")
    );

    /*
     * Give the DS18B20 module time to stabilize after ESP32 power-up.
     * The standalone test sketch successfully detects the sensor after
     * a startup delay, so we use the same approach here.
     */
    delay(1000);

    /*
     * Configure GPIO7 as an input with the ESP32's internal pull-up.
     *
     * NOTE:
     * A proper external 4.7kΩ pull-up from DATA to 3.3V is still
     * recommended for reliable 1-Wire communication. If your module
     * already contains a pull-up resistor, an additional one may not
     * be necessary.
     */
    pinMode(DS18B20_PIN, INPUT_PULLUP);

    // Initialize DallasTemperature
    _dallas.begin();

    // Give the 1-Wire bus a moment to settle
    delay(100);

    // Detect connected DS18B20 devices
    _ds_count = (uint8_t)_dallas.getDeviceCount();

    Serial.printf(
        "[DS18B20] Device count: %d\n",
        _ds_count
    );

    if (_ds_count == 0) {

        Serial.printf(
            "[DS18B20] NOT FOUND — check GPIO%d wiring and 4.7kΩ pull-up\n",
            DS18B20_PIN
        );

    } else {

        Serial.printf(
            "[DS18B20] Found %d sensor(s) on GPIO%d\n",
            _ds_count,
            DS18B20_PIN
        );

        // Limit operation to the two sensors supported by the project
        if (_ds_count > 2) {
            _ds_count = 2;
        }

        // Set sensor resolution
        _dallas.setResolution(DS18B20_RESOLUTION);

        // Non-blocking temperature conversion
        _dallas.setWaitForConversion(false);

        // Print addresses so sensors can be identified
        for (
            uint8_t i = 0;
            i < _ds_count && i < 2;
            i++
        ) {

            DeviceAddress addr;

            if (_dallas.getAddress(addr, i)) {

                Serial.printf(
                    "  TEMP%d address: ",
                    i + 1
                );

                for (uint8_t b = 0; b < 8; b++) {

                    Serial.printf(
                        "%02X",
                        addr[b]
                    );

                    if (b < 7) {
                        Serial.print(':');
                    }
                }

                Serial.println();
            }
        }

        /*
         * Start the first temperature conversion.
         */
        _dallas.requestTemperatures();

        _conv_requested_ms = millis();
        _conv_in_flight = true;
    }


    // FSR pins are configured by the main .ino.
    // They use analogReadResolution() and ADC attenuation.


    /*
     * The DS18B20 is optional during the current prototype stage.
     * MPU6050 presence determines overall sensor initialization status.
     */
    return _mpu_ok;
}


// ─────────────────────────────────────────────────────────────────────────────
// sensors_read()
// ─────────────────────────────────────────────────────────────────────────────

void sensors_read(SensorPacket &pkt) {

    pkt.timestamp_ms = millis();


    // ── FSR — 2 channels ─────────────────────────────────────────────────────

    const uint8_t fsr_pins[FSR_COUNT] = {
        FSR1_PIN,
        FSR2_PIN
    };

    const CalibrationData &cal = calibration_get();

    for (int i = 0; i < FSR_COUNT; i++) {

        // Raw ADC reading
        pkt.fsr.raw[i] =
            (uint16_t)analogRead(fsr_pins[i]);

        // Subtract calibrated no-load baseline
        int32_t corr =
            (int32_t)pkt.fsr.raw[i]
            -
            (int32_t)cal.baseline[i];

        // Prevent negative calibrated values
        pkt.fsr.calibrated[i] =
            (uint16_t)max(0L, corr);
    }


    // ── DS18B20 — non-blocking ───────────────────────────────────────────────

    pkt.ds18b20.sensor_count = _ds_count;

    if (_ds_count > 0) {

        // Check whether previous conversion has finished
        bool conv_ready =
            _conv_in_flight &&
            (
                millis() - _conv_requested_ms
                >=
                DS18B20_CONVERT_MS
            );

        if (conv_ready) {

            // Read available temperatures
            for (
                uint8_t i = 0;
                i < _ds_count && i < 2;
                i++
            ) {

                float t =
                    _dallas.getTempCByIndex(i);

                // -127°C is the DallasTemperature error value
                if (t > -120.0f) {

                    _last_temp[i] = t;
                }
            }

            // Start next conversion
            _dallas.requestTemperatures();

            _conv_requested_ms = millis();

            _conv_in_flight = true;
        }


        // Return latest valid values
        pkt.ds18b20.temperature_c[0] =
            _last_temp[0];

        if (_ds_count >= 2) {

            pkt.ds18b20.temperature_c[1] =
                _last_temp[1];

        } else {

            pkt.ds18b20.temperature_c[1] =
                -127.0f;
        }


        // TEMP1 is valid when it has a valid reading
        pkt.ds18b20.ok =
            (_last_temp[0] > -120.0f);

    } else {

        pkt.ds18b20.temperature_c[0] =
            -127.0f;

        pkt.ds18b20.temperature_c[1] =
            -127.0f;

        pkt.ds18b20.ok = false;
    }


    // ── MPU6050 ──────────────────────────────────────────────────────────────

    pkt.mpu.ok = _mpu_ok;

    if (_mpu_ok) {

        sensors_event_t a;
        sensors_event_t g;
        sensors_event_t t;

        _mpu.getEvent(
            &a,
            &g,
            &t
        );


        // Accelerometer
        // Adafruit reports m/s².
        // Convert to g.
        pkt.mpu.ax =
            a.acceleration.x / 9.80665f;

        pkt.mpu.ay =
            a.acceleration.y / 9.80665f;

        pkt.mpu.az =
            a.acceleration.z / 9.80665f;


        // Gyroscope
        // Adafruit reports radians/sec.
        // Convert to degrees/sec.
        pkt.mpu.gx =
            g.gyro.x * (180.0f / PI);

        pkt.mpu.gy =
            g.gyro.y * (180.0f / PI);

        pkt.mpu.gz =
            g.gyro.z * (180.0f / PI);

    } else {

        pkt.mpu.ax =
        pkt.mpu.ay =
        pkt.mpu.az = 0.0f;

        pkt.mpu.gx =
        pkt.mpu.gy =
        pkt.mpu.gz = 0.0f;
    }
}


// ─────────────────────────────────────────────────────────────────────────────
// sensors_diagnostic()
// ─────────────────────────────────────────────────────────────────────────────

void sensors_diagnostic() {

    SensorPacket pkt;

    sensors_read(pkt);


    Serial.println();

    Serial.println(
        F("===== SOLESENSE SENSOR DIAGNOSTIC =====")
    );


    // ── FSR ───────────────────────────────────────────────────────────────────

    Serial.printf(
        "FSR1: %d  (raw %d)  [%s]\n",
        pkt.fsr.calibrated[0],
        pkt.fsr.raw[0],
        FSR1_LABEL
    );

    Serial.printf(
        "FSR2: %d  (raw %d)  [%s]\n",
        pkt.fsr.calibrated[1],
        pkt.fsr.raw[1],
        FSR2_LABEL
    );


    // ── DS18B20 ──────────────────────────────────────────────────────────────

    if (pkt.ds18b20.ok) {

        if (
            pkt.ds18b20.temperature_c[0]
            > -120.0f
        ) {

            Serial.printf(
                "TEMP1: %.2f C\n",
                pkt.ds18b20.temperature_c[0]
            );

        } else {

            Serial.println(
                F("TEMP1: error")
            );
        }


        if (pkt.ds18b20.sensor_count >= 2) {

            if (
                pkt.ds18b20.temperature_c[1]
                > -120.0f
            ) {

                Serial.printf(
                    "TEMP2: %.2f C\n",
                    pkt.ds18b20.temperature_c[1]
                );

            } else {

                Serial.println(
                    F("TEMP2: error")
            );
            }

        } else {

            Serial.println(
                F("TEMP2: not found")
            );
        }

    } else {

        Serial.println(
            F("TEMP1: NOT FOUND")
        );

        Serial.println(
            F("TEMP2: NOT FOUND")
        );

        Serial.printf(
            "       Check GPIO%d wiring and 4.7kΩ pull-up to 3.3V\n",
            DS18B20_PIN
        );
    }


    // ── MPU6050 ──────────────────────────────────────────────────────────────

    if (pkt.mpu.ok) {

        Serial.printf(
            "AX: %.4f\n",
            pkt.mpu.ax
        );

        Serial.printf(
            "AY: %.4f\n",
            pkt.mpu.ay
        );

        Serial.printf(
            "AZ: %.4f\n",
            pkt.mpu.az
        );

        Serial.printf(
            "GX: %.4f\n",
            pkt.mpu.gx
        );

        Serial.printf(
            "GY: %.4f\n",
            pkt.mpu.gy
        );

        Serial.printf(
            "GZ: %.4f\n",
            pkt.mpu.gz
        );

    } else {

        Serial.println(
            F("AX: NOT FOUND")
        );

        Serial.println(
            F("AY: NOT FOUND")
        );

        Serial.println(
            F("AZ: NOT FOUND")
        );

        Serial.println(
            F("GX: NOT FOUND")
        );

        Serial.println(
            F("GY: NOT FOUND")
        );

        Serial.println(
            F("GZ: NOT FOUND")
        );

        Serial.printf(
            "MPU6050: check SDA=GPIO%d SCL=GPIO%d addr=0x%02X\n",
            I2C_SDA,
            I2C_SCL,
            MPU6050_I2C_ADDR
        );
    }


    Serial.println(
        F("========================================")
    );

    Serial.println();
}


// ─────────────────────────────────────────────────────────────────────────────
// Accessors
// ─────────────────────────────────────────────────────────────────────────────

bool sensors_mpu6050_ok() {
    return _mpu_ok;
}


uint8_t sensors_ds18b20_count() {
    return _ds_count;
}