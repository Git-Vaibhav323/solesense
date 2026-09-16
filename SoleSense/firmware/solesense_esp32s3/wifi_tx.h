/**
 * SoleSense ESP32-S3 Firmware
 * wifi_tx.h — Wi-Fi Access Point + HTTP POST API
 *
 * ESP32 creates its own hotspot.  Laptop connects to it.
 * Sensor packets are POSTed to the laptop receiver at 20 Hz.
 *
 * JSON schema sent to laptop
 * --------------------------
 * {
 *   "timestamp":    <uint32 ms>,
 *   "fsr1":         <uint16 ADC>,
 *   "fsr2":         <uint16 ADC>,
 *   "temperature1": <float °C>   | omitted if unavailable,
 *   "temperature2": <float °C>   | omitted if unavailable,
 *   "ax": <float g>,  "ay": <float g>,  "az": <float g>,
 *   "gx": <float °/s>,"gy": <float °/s>,"gz": <float °/s>
 * }
 *
 * Configuration: AP_SSID, AP_PASSWORD, SERVER_IP, SERVER_PORT in config.h
 * Libraries: WiFi.h, HTTPClient.h (ESP32 core), ArduinoJson ≥ 6 (Library Manager)
 */

#pragma once
#include "sensors.h"

/** Start Access Point.  Call once from setup(). */
bool wifi_connect();

/** True if at least one client (laptop) is connected to the AP. */
bool wifi_is_connected();

/** Non-blocking watchdog — call every loop() iteration. */
void wifi_maintain();

/** Serialise SensorPacket to JSON and HTTP POST to laptop. */
bool wifi_send_packet(const SensorPacket &pkt);

/** Print Wi-Fi status to Serial. */
void wifi_print_status();
