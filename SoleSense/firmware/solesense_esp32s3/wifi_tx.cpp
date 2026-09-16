/**
 * SoleSense ESP32-S3 Firmware
 * wifi_tx.cpp — Wi-Fi Access Point + HTTP POST implementation
 *
 * JSON schema (flat, matches src/hardware_input.parse_flat_packet):
 * {
 *   "timestamp":    123456789,
 *   "fsr1":         421,
 *   "fsr2":         380,
 *   "temperature1": 32.41,    ← omitted if DS18B20 sensor 0 unavailable
 *   "temperature2": 31.98,    ← omitted if DS18B20 sensor 1 unavailable
 *   "ax":  0.0312,
 *   "ay": -0.0198,
 *   "az":  0.9871,
 *   "gx":  1.2400,
 *   "gy": -0.8100,
 *   "gz":  0.3200
 * }
 *
 * Fields NOT present: fsr3, fsr4, tmp117, temperature (legacy single-sensor)
 */

#include "wifi_tx.h"
#include "config.h"
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ── State ─────────────────────────────────────────────────────────────────────
static uint32_t _tx_ok    = 0;
static uint32_t _tx_fail  = 0;
static String   _url;
static bool     _client_was_connected = false;

// ── wifi_connect ──────────────────────────────────────────────────────────────
bool wifi_connect() {
    _url = String("http://") + SERVER_IP + ":" + SERVER_PORT + SERVER_ENDPOINT;

    Serial.println(F("[WiFi] ─────────────────────────────────────"));
    Serial.println(F("[WiFi] Mode     : ACCESS POINT"));
    Serial.printf( "[WiFi] SSID     : %s\n", AP_SSID);
    Serial.printf( "[WiFi] Password : %s\n", AP_PASSWORD);

    if (!WiFi.softAP(AP_SSID, AP_PASSWORD, AP_CHANNEL)) {
        Serial.println(F("[WiFi] ERROR — softAP() failed"));
        return false;
    }
    delay(200);

    Serial.println(F("[WiFi] Hotspot ACTIVE"));
    Serial.printf( "[WiFi] ESP32 IP : %s\n", WiFi.softAPIP().toString().c_str());
    Serial.printf( "[WiFi] Target   : %s\n", _url.c_str());
    Serial.println(F("[WiFi] ─────────────────────────────────────"));
    Serial.println();
    Serial.println(F(">>> Connect your laptop to Wi-Fi: \"" AP_SSID "\""));
    Serial.println(F("    Password: \"" AP_PASSWORD "\""));
    Serial.println(F("    Then run: python -m streamlit run dashboard/app.py"));
    Serial.println();
    return true;
}

// ── wifi_is_connected ─────────────────────────────────────────────────────────
bool wifi_is_connected() {
    return WiFi.softAPgetStationNum() > 0;
}

// ── wifi_maintain ─────────────────────────────────────────────────────────────
void wifi_maintain() {
    bool now = wifi_is_connected();
    if (now && !_client_was_connected) {
        _client_was_connected = true;
        Serial.println(F("[WiFi] Laptop connected — TX active"));
    } else if (!now && _client_was_connected) {
        _client_was_connected = false;
        Serial.println(F("[WiFi] Laptop disconnected"));
    }
}

// ── wifi_send_packet ──────────────────────────────────────────────────────────
bool wifi_send_packet(const SensorPacket &pkt) {
    if (!wifi_is_connected()) return false;

    // Capacity: timestamp(10) + fsr×2(10) + temp×2(20) + imu×6(60) + keys ≈ 220
    StaticJsonDocument<320> doc;

    doc["timestamp"] = pkt.timestamp_ms;

    // FSR — 2 channels only
    doc["fsr1"] = pkt.fsr.calibrated[0];
    doc["fsr2"] = pkt.fsr.calibrated[1];

    // DS18B20 temperatures — omit field if sensor not available / errored
    if (pkt.ds18b20.ok && pkt.ds18b20.temperature_c[0] > -120.0f) {
        doc["temperature1"] = serialized(String(pkt.ds18b20.temperature_c[0], 2));
    }
    if (pkt.ds18b20.sensor_count >= 2 && pkt.ds18b20.temperature_c[1] > -120.0f) {
        doc["temperature2"] = serialized(String(pkt.ds18b20.temperature_c[1], 2));
    }

    // IMU — always present (0.0 when MPU6050 not connected)
    doc["ax"] = serialized(String(pkt.mpu.ax, 4));
    doc["ay"] = serialized(String(pkt.mpu.ay, 4));
    doc["az"] = serialized(String(pkt.mpu.az, 4));
    doc["gx"] = serialized(String(pkt.mpu.gx, 4));
    doc["gy"] = serialized(String(pkt.mpu.gy, 4));
    doc["gz"] = serialized(String(pkt.mpu.gz, 4));

    String payload;
    payload.reserve(220);
    serializeJson(doc, payload);

    HTTPClient http;
    http.begin(_url);
    http.setTimeout(HTTP_TIMEOUT_MS);
    http.addHeader(F("Content-Type"), F("application/json"));

    int code = http.POST(payload);
    http.end();

    bool ok = (code == 200);
    ok ? _tx_ok++ : _tx_fail++;

    if (!ok && DEBUG_MODE) {
        Serial.printf("[WiFi] POST FAIL code=%d  ok=%lu fail=%lu\n",
                      code, _tx_ok, _tx_fail);
    }
    return ok;
}

// ── wifi_print_status ─────────────────────────────────────────────────────────
void wifi_print_status() {
    Serial.println(F("[WiFi] ─────────────────────────────────────"));
    Serial.println(F("[WiFi] Mode     : ACCESS POINT"));
    Serial.printf( "[WiFi] SSID     : %s\n",  AP_SSID);
    Serial.printf( "[WiFi] ESP32 IP : %s\n",  WiFi.softAPIP().toString().c_str());
    Serial.printf( "[WiFi] Clients  : %d\n",  WiFi.softAPgetStationNum());
    Serial.printf( "[WiFi] Target   : %s\n",  _url.c_str());
    Serial.printf( "[WiFi] TX ok/fail: %lu / %lu\n", _tx_ok, _tx_fail);
    Serial.println(F("[WiFi] ─────────────────────────────────────"));
}
