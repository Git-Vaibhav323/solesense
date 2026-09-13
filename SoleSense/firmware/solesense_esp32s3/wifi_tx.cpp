/**
 * SoleSense ESP32-S3 Firmware
 * wifi_tx.cpp  —  Wi-Fi ACCESS POINT mode + HTTP POST
 *
 * The ESP32-S3 runs as a Wi-Fi Access Point (hotspot).
 * The laptop connects TO the ESP32 — no router or phone needed.
 *
 * Network layout:
 *   ESP32-S3  →  hotspot "SoleSense"  →  laptop connects
 *   ESP32 IP  : 192.168.4.1  (fixed, always)
 *   Laptop IP : 192.168.4.2  (assigned by ESP32 DHCP, almost always .2)
 *
 * Data flow:
 *   sensors_read() → wifi_send_packet() → HTTP POST → laptop:5005/api/sensor
 *
 * Libraries (all built into ESP32 Arduino core — no install needed):
 *   WiFi.h, HTTPClient.h, ArduinoJson (install separately via Library Manager)
 */

#include "wifi_tx.h"
#include "config.h"

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ── Module state ──────────────────────────────────────────────────────────────
static uint32_t _tx_ok_total   = 0;
static uint32_t _tx_fail_total = 0;
static String   _server_url;

// ── wifi_connect() ────────────────────────────────────────────────────────────
// Starts the ESP32 as a Wi-Fi Access Point.
// Returns immediately after AP is up — no waiting for a client to join.

bool wifi_connect() {

    _server_url = String("http://")
                  + SERVER_IP + ":"
                  + SERVER_PORT
                  + SERVER_ENDPOINT;

    Serial.println();
    Serial.println(F("[WiFi] ─────────────────────────────────────"));
    Serial.println(F("[WiFi] Mode    : ACCESS POINT (ESP32 is the hotspot)"));
    Serial.printf( "[WiFi] SSID    : %s\n", AP_SSID);
    Serial.printf( "[WiFi] Password: %s\n", AP_PASSWORD);

    // Start AP — ESP32 gets fixed IP 192.168.4.1 automatically
    bool ok = WiFi.softAP(AP_SSID, AP_PASSWORD, AP_CHANNEL);

    if (!ok) {
        Serial.println(F("[WiFi] ERROR — softAP() failed. Check board selection."));
        return false;
    }

    delay(200);   // give AP a moment to fully initialise before printing IP

    Serial.println(F("[WiFi] Hotspot ACTIVE"));
    Serial.printf( "[WiFi] ESP32 IP : %s\n", WiFi.softAPIP().toString().c_str());
    Serial.println(F("[WiFi] ─────────────────────────────────────"));
    Serial.println();
    Serial.println(F(">>> ACTION REQUIRED <<<"));
    Serial.println(F("    1. On your laptop, open Wi-Fi settings"));
    Serial.printf( "    2. Connect to network: \"%s\"\n", AP_SSID);
    Serial.printf( "    3. Password          : \"%s\"\n", AP_PASSWORD);
    Serial.println(F("    4. Run: python -m hardware.esp32_receiver"));
    Serial.println(F("    5. Run: ipconfig  — verify laptop IP is 192.168.4.2"));
    Serial.println();
    Serial.printf( "[WiFi] Will send packets to: %s\n", _server_url.c_str());
    Serial.println(F("[WiFi] Sensor loop starting now..."));
    Serial.println();

    return true;
}

// ── wifi_is_connected() ───────────────────────────────────────────────────────
// In AP mode, "connected" means at least one client (laptop) has joined.

bool wifi_is_connected() {
    return WiFi.softAPgetStationNum() > 0;
}

// ── wifi_maintain() ───────────────────────────────────────────────────────────
// In AP mode the hotspot stays up automatically — nothing to reconnect.
// We just print a message when the laptop connects or disconnects.

static bool _client_was_connected = false;

void wifi_maintain() {
    bool client_now = wifi_is_connected();

    if (client_now && !_client_was_connected) {
        _client_was_connected = true;
        Serial.println(F("[WiFi] Laptop connected to hotspot — starting TX"));
    }

    if (!client_now && _client_was_connected) {
        _client_was_connected = false;
        Serial.println(F("[WiFi] Laptop disconnected from hotspot"));
    }
}

// ── wifi_send_packet() ────────────────────────────────────────────────────────
// Serialises sensor data to flat JSON and HTTP POSTs to the laptop receiver.
//
// JSON schema (flat, matches src/hardware_input.parse_flat_packet):
//   timestamp, fsr1, fsr2, fsr3, fsr4, temperature, ax, ay, az, gx, gy, gz

bool wifi_send_packet(const SensorPacket &pkt) {

    // Only send if a client is connected — avoids TCP errors when laptop is absent
    if (!wifi_is_connected()) return false;

    StaticJsonDocument<256> doc;

    doc["timestamp"] = pkt.timestamp_ms;
    doc["fsr1"]      = pkt.fsr.calibrated[0];
    doc["fsr2"]      = pkt.fsr.calibrated[1];
    doc["fsr3"]      = pkt.fsr.calibrated[2];
    doc["fsr4"]      = pkt.fsr.calibrated[3];

    if (pkt.tmp117.ok) {
        doc["temperature"] = serialized(String(pkt.tmp117.temperature_c, 2));
    }

    doc["ax"] = serialized(String(pkt.mpu.ax, 4));
    doc["ay"] = serialized(String(pkt.mpu.ay, 4));
    doc["az"] = serialized(String(pkt.mpu.az, 4));
    doc["gx"] = serialized(String(pkt.mpu.gx, 4));
    doc["gy"] = serialized(String(pkt.mpu.gy, 4));
    doc["gz"] = serialized(String(pkt.mpu.gz, 4));

    String payload;
    payload.reserve(200);
    serializeJson(doc, payload);

    HTTPClient http;
    http.begin(_server_url);
    http.setTimeout(HTTP_TIMEOUT_MS);
    http.addHeader(F("Content-Type"), F("application/json"));

    int code = http.POST(payload);
    http.end();

    bool ok = (code == 200);
    if (ok) {
        _tx_ok_total++;
    } else {
        _tx_fail_total++;
        if (DEBUG_MODE) {
            Serial.printf("[WiFi] POST %s  code=%d  ok=%lu  fail=%lu\n",
                          ok ? "OK" : "FAIL", code,
                          _tx_ok_total, _tx_fail_total);
        }
    }
    return ok;
}

// ── wifi_print_status() ───────────────────────────────────────────────────────

void wifi_print_status() {
    Serial.println(F("[WiFi] ─────────────────────────────────────"));
    Serial.println(F("[WiFi] Mode     : ACCESS POINT"));
    Serial.printf( "[WiFi] SSID     : %s\n",  AP_SSID);
    Serial.printf( "[WiFi] ESP32 IP : %s\n",  WiFi.softAPIP().toString().c_str());
    Serial.printf( "[WiFi] Clients  : %d connected\n", WiFi.softAPgetStationNum());
    Serial.printf( "[WiFi] Target   : %s\n",  _server_url.c_str());
    Serial.printf( "[WiFi] TX ok/fail: %lu / %lu\n", _tx_ok_total, _tx_fail_total);
    Serial.println(F("[WiFi] ─────────────────────────────────────"));
}
