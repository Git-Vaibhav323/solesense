/**
 * SoleSense ESP32-S3 Firmware
 * wifi_tx.cpp  —  Wi-Fi connection and HTTP POST implementation
 *
 * See wifi_tx.h for full documentation and JSON schema.
 *
 * ─── JSON output format ──────────────────────────────────────────────────────
 *
 *  FLAT — all fields at top level, no nesting:
 *
 *  {
 *    "timestamp": 123456789,
 *    "fsr1":      421,
 *    "fsr2":      380,
 *    "fsr3":      210,
 *    "fsr4":      510,
 *    "temperature": 31.42,
 *    "ax":  0.0312,
 *    "ay": -0.0198,
 *    "az":  0.9871,
 *    "gx":  1.2400,
 *    "gy": -0.8100,
 *    "gz":  0.3200
 *  }
 *
 *  This matches src/hardware_input.parse_flat_packet() on the Python side.
 *
 * ─── Why HTTP POST and not WebSocket ─────────────────────────────────────────
 *
 *  At 20 Hz with a ~200 byte payload, HTTP POST adds roughly 1–3 ms of
 *  connection overhead per packet on a local network.  That is acceptable
 *  for a 50 ms sample interval and requires no persistent connection state
 *  on the ESP32.  WebSocket would be marginally faster but adds a library
 *  dependency and more complex reconnect logic.  HTTP POST is simpler and
 *  works reliably with Flask's standard request handling.
 *
 * ─── Libraries ───────────────────────────────────────────────────────────────
 *
 *  WiFi.h       — ESP32 Arduino core (no install needed)
 *  HTTPClient.h — ESP32 Arduino core (no install needed)
 *  ArduinoJson  — install via Library Manager: "ArduinoJson" by Benoit Blanchon ≥ 6
 */

#include "wifi_tx.h"
#include "config.h"

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ─────────────────────────────────────────────────────────────────────────────
//  Module-private state
// ─────────────────────────────────────────────────────────────────────────────

static bool     _was_connected      = false;
static uint32_t _last_reconnect_ms  = 0;
static uint32_t _tx_ok_total        = 0;
static uint32_t _tx_fail_total      = 0;

// Pre-built URL string — constructed once in wifi_connect() so it is not
// rebuilt on every send.
static String _server_url;

// ─────────────────────────────────────────────────────────────────────────────
//  wifi_connect()
// ─────────────────────────────────────────────────────────────────────────────

bool wifi_connect() {

    _server_url = String("http://")
                  + SERVER_IP + ":"
                  + SERVER_PORT
                  + SERVER_ENDPOINT;

    Serial.println();
    Serial.println(F("[WiFi] ─────────────────────────────────────"));
    Serial.printf( "[WiFi] SSID    : %s\n", WIFI_SSID);
    Serial.printf( "[WiFi] Target  : %s\n", _server_url.c_str());
    Serial.print(  F("[WiFi] Connecting"));

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    uint32_t t_start = millis();
    while (WiFi.status() != WL_CONNECTED) {
        if (millis() - t_start > (uint32_t)WIFI_CONNECT_TIMEOUT_MS) {
            Serial.println();
            Serial.println(F("[WiFi] TIMEOUT — could not connect within limit."));
            Serial.println(F("[WiFi] Sensor loop will start; reconnect is automatic."));
            Serial.println(F("[WiFi] Check WIFI_SSID / WIFI_PASSWORD in config.h."));
            return false;
        }
        delay(250);
        Serial.print('.');
    }

    _was_connected = true;
    Serial.println();
    wifi_print_status();
    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
//  wifi_is_connected()
// ─────────────────────────────────────────────────────────────────────────────

bool wifi_is_connected() {
    return WiFi.status() == WL_CONNECTED;
}

// ─────────────────────────────────────────────────────────────────────────────
//  wifi_maintain()
// ─────────────────────────────────────────────────────────────────────────────

void wifi_maintain() {
    if (WiFi.status() == WL_CONNECTED) {
        if (!_was_connected) {
            // Just reconnected — announce it
            _was_connected = true;
            Serial.println(F("[WiFi] Reconnected."));
            wifi_print_status();
        }
        return;
    }

    // Disconnected path
    if (_was_connected) {
        _was_connected = false;
        Serial.println(F("[WiFi] Connection lost — will retry automatically."));
    }

    uint32_t now = millis();
    if (now - _last_reconnect_ms >= (uint32_t)WIFI_RECONNECT_INTERVAL_MS) {
        _last_reconnect_ms = now;
        if (DEBUG_MODE) {
            Serial.println(F("[WiFi] Attempting reconnect..."));
        }
        WiFi.disconnect(true);
        delay(100);
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
//  wifi_send_packet()
//
//  Builds the flat JSON payload and POSTs it.
//  JSON field layout (matches src/hardware_input.parse_flat_packet):
//
//    "timestamp"   uint32  millis()
//    "fsr1"        uint16  calibrated ADC  (forefoot medial)
//    "fsr2"        uint16  calibrated ADC  (forefoot lateral)
//    "fsr3"        uint16  calibrated ADC  (midfoot)
//    "fsr4"        uint16  calibrated ADC  (heel)
//    "temperature" float   °C  (present only when TMP117 ok)
//    "ax"          float   g
//    "ay"          float   g
//    "az"          float   g
//    "gx"          float   °/s
//    "gy"          float   °/s
//    "gz"          float   °/s
// ─────────────────────────────────────────────────────────────────────────────

bool wifi_send_packet(const SensorPacket &pkt) {
    if (!wifi_is_connected()) return false;

    // StaticJsonDocument capacity:
    //   timestamp (10) + 4 × fsr (5×8) + temp (16) + 6 × imu (8×8)
    //   ≈ 150 chars payload; 256 bytes is comfortably sufficient.
    StaticJsonDocument<256> doc;

    // ── Timestamp ─────────────────────────────────────────────────────────────
    doc["timestamp"] = pkt.timestamp_ms;

    // ── FSR channels ──────────────────────────────────────────────────────────
    // Flat integer fields — no nesting.
    // Names "fsr1".."fsr4" match the required schema in Task 5.
    doc["fsr1"] = pkt.fsr.calibrated[0];   // forefoot medial  (FSR1_REGION)
    doc["fsr2"] = pkt.fsr.calibrated[1];   // forefoot lateral (FSR2_REGION)
    doc["fsr3"] = pkt.fsr.calibrated[2];   // midfoot          (FSR3_REGION)
    doc["fsr4"] = pkt.fsr.calibrated[3];   // heel             (FSR4_REGION)

    // ── Temperature ───────────────────────────────────────────────────────────
    // Omit the field entirely if TMP117 is unavailable.
    // Python parse_flat_packet() treats a missing key the same as null.
    if (pkt.tmp117.ok) {
        doc["temperature"] = serialized(String(pkt.tmp117.temperature_c, 2));
    }
    // else: key not added → Python receives no "temperature" key

    // ── IMU ───────────────────────────────────────────────────────────────────
    // Send 0.0 for all axes when MPU6050 is not available.
    // This makes the packet always valid (ax..gz always present) and
    // lets the Python side detect "no IMU" via accel_magnitude ≈ 0.
    doc["ax"] = serialized(String(pkt.mpu.ax, 4));
    doc["ay"] = serialized(String(pkt.mpu.ay, 4));
    doc["az"] = serialized(String(pkt.mpu.az, 4));
    doc["gx"] = serialized(String(pkt.mpu.gx, 4));
    doc["gy"] = serialized(String(pkt.mpu.gy, 4));
    doc["gz"] = serialized(String(pkt.mpu.gz, 4));

    // ── Serialise ─────────────────────────────────────────────────────────────
    String payload;
    payload.reserve(200);
    serializeJson(doc, payload);

    // ── HTTP POST ─────────────────────────────────────────────────────────────
    HTTPClient http;
    http.begin(_server_url);
    http.setTimeout(HTTP_TIMEOUT_MS);
    http.addHeader(F("Content-Type"), F("application/json"));

    int http_code = http.POST(payload);
    http.end();

    bool ok = (http_code == 200);

    if (ok) {
        _tx_ok_total++;
    } else {
        _tx_fail_total++;
        if (DEBUG_MODE) {
            // Only print failures — successful packets are silent to keep
            // the Serial log readable during normal operation.
            if (http_code > 0) {
                Serial.printf("[WiFi] POST returned HTTP %d  (ok=%lu fail=%lu)\n",
                              http_code, _tx_ok_total, _tx_fail_total);
            } else {
                // Negative codes are WiFi/TCP errors from HTTPClient
                Serial.printf("[WiFi] POST error %d  (ok=%lu fail=%lu)\n",
                              http_code, _tx_ok_total, _tx_fail_total);
            }
        }
    }

    return ok;
}

// ─────────────────────────────────────────────────────────────────────────────
//  wifi_print_status()
// ─────────────────────────────────────────────────────────────────────────────

void wifi_print_status() {
    Serial.println(F("[WiFi] ─────────────────────────────────────"));
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println(F("[WiFi] Status  : CONNECTED"));
        Serial.printf( "[WiFi] SSID    : %s\n",  WiFi.SSID().c_str());
        Serial.printf( "[WiFi] IP      : %s\n",  WiFi.localIP().toString().c_str());
        Serial.printf( "[WiFi] Gateway : %s\n",  WiFi.gatewayIP().toString().c_str());
        Serial.printf( "[WiFi] RSSI    : %d dBm\n", (int)WiFi.RSSI());
        Serial.printf( "[WiFi] Target  : %s\n",  _server_url.c_str());
        Serial.printf( "[WiFi] TX ok/fail: %lu / %lu\n",
                       _tx_ok_total, _tx_fail_total);
    } else {
        Serial.println(F("[WiFi] Status  : DISCONNECTED"));
        Serial.printf( "[WiFi] Last target: %s\n", _server_url.c_str());
    }
    Serial.println(F("[WiFi] ─────────────────────────────────────"));
}
