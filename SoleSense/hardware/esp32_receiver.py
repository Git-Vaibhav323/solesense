"""
SoleSense Hardware — esp32_receiver.py
========================================
Flask HTTP server that receives flat JSON packets from the ESP32-S3 over Wi-Fi.

Architecture
------------
ESP32-S3  →  HTTP POST /api/sensor  →  this server  →  rolling buffer
                                                              ↓
                                              src/hardware_input.py
                                                              ↓
                                              src/risk_engine.compute_risk()
                                                              ↓
                                              Streamlit dashboard

JSON packet schema received from ESP32 (flat format, Task 5):
--------------------------------------------------------------
{
    "timestamp":   123456789,    required  int    ESP32 millis()
    "fsr1":        421,          required  int    ADC 0-4095
    "fsr2":        380,          required  int    ADC 0-4095
    "fsr3":        210,          required  int    ADC 0-4095
    "fsr4":        510,          required  int    ADC 0-4095
    "temperature": 31.42,        optional  float  °C (absent = unavailable)
    "ax":  0.03,                 optional  float  g
    "ay": -0.02,                 optional  float  g
    "az":  0.98,                 optional  float  g
    "gx":  1.24,                 optional  float  °/s
    "gy": -0.81,                 optional  float  °/s
    "gz":  0.32                  optional  float  °/s
}

Usage (from Python)
-------------------
from hardware.esp32_receiver import get_receiver

# Start (lazily, once)
receiver = get_receiver(port=5005)

# Get latest packet dict
pkt = receiver.latest_packet()   # dict or None

# Get recent window
packets = receiver.recent_packets(n=100)   # list of dicts, oldest→newest

# Status
s = receiver.status()
# s["connected"], s["packet_rate_hz"], s["total_received"], ...

Standalone usage (terminal)
----------------------------
cd f:/Dataset/SoleSense
python -m hardware.esp32_receiver [port]

Finding your laptop IP
-----------------------
Windows : ipconfig  → IPv4 Address under your Wi-Fi adapter
Linux   : ip addr show  or  hostname -I
macOS   : ifconfig en0

Set SERVER_IP in firmware/solesense_esp32s3/config.h to that address.
"""

from __future__ import annotations

import time
import threading
import logging
from collections import deque
from typing import Optional

from flask import Flask, request, jsonify

# Use the canonical flat-packet parser from the hardware_input adapter.
# This is the single source of truth for the packet schema on the Python side.
from src.hardware_input import parse_flat_packet, PacketValidationError

log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
BUFFER_SIZE        = 400    # ~20 s at 20 Hz
RATE_WINDOW_S      = 5.0    # rolling window for packet-rate estimation
CONNECTION_TIMEOUT = 3.0    # seconds without a packet → "disconnected"


class SoleSenseReceiver:
    """
    Threaded Flask server that receives ESP32-S3 sensor packets.

    Packets are stored as parsed dicts (output of parse_flat_packet) in a
    thread-safe deque.  The Streamlit/analytics thread reads from the deque
    via the public API without needing to know about Flask.

    Thread safety
    -------------
    Flask worker thread : writes to deque via _ingest()
    Any other thread    : reads via latest_packet() / recent_packets() / status()
    A threading.Lock guards all deque access.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 5005):
        self._host   = host
        self._port   = port

        self._buffer: deque[dict]  = deque(maxlen=BUFFER_SIZE)
        self._lock   = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # Metrics
        self._arrival_times: deque[float] = deque(maxlen=200)
        self._last_received:  float = 0.0
        self._total_received: int   = 0
        self._total_errors:   int   = 0

        self._app = self._build_flask_app()

    # ── Flask application ─────────────────────────────────────────────────────

    def _build_flask_app(self) -> Flask:
        app      = Flask(__name__)
        ref      = self

        # Silence werkzeug request logs — they clutter the Streamlit terminal
        logging.getLogger("werkzeug").setLevel(logging.ERROR)

        @app.route("/api/sensor", methods=["POST"])
        def receive_sensor():
            raw = request.get_json(silent=True)
            if raw is None:
                ref._total_errors += 1
                return jsonify({"status": "error",
                                "msg": "body is not valid JSON"}), 400

            try:
                pkt = parse_flat_packet(raw)   # → validated dict
            except PacketValidationError as exc:
                ref._total_errors += 1
                log.warning("Packet rejected: %s", exc)
                return jsonify({"status": "error", "msg": str(exc)}), 422

            ref._ingest(pkt)
            return jsonify({"status": "ok"}), 200

        @app.route("/api/health", methods=["GET"])
        def health():
            return jsonify({
                "status":         "running",
                "total_received": ref._total_received,
                "connected":      ref.is_connected(),
                "packet_rate_hz": round(ref.packet_rate_hz(), 1),
            }), 200

        @app.route("/api/latest", methods=["GET"])
        def latest():
            pkt = ref.latest_packet()
            if pkt is None:
                return jsonify({"status": "no_data"}), 204
            s = ref.status()
            return jsonify({
                "fsr1":        pkt.get("fsr1", 0),
                "fsr2":        pkt.get("fsr2", 0),
                "fsr3":        pkt.get("fsr3", 0),
                "fsr4":        pkt.get("fsr4", 0),
                "temperature": pkt.get("temperature"),
                "ax":          pkt.get("ax", 0),
                "ay":          pkt.get("ay", 0),
                "az":          pkt.get("az", 0),
                "timestamp":   pkt.get("timestamp", 0),
                "rate_hz":     round(ref.packet_rate_hz(), 1),
                "total":       ref._total_received,
                "connected":   ref.is_connected(),
            }), 200

        return app

    # ── Internal ingest ───────────────────────────────────────────────────────

    def _ingest(self, pkt: dict) -> None:
        now = time.time()
        pkt["received_at"] = now       # stamp wall-clock arrival time
        with self._lock:
            self._buffer.append(pkt)
            self._arrival_times.append(now)
            self._last_received  = now
            self._total_received += 1

    # ── Start / stop ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the Flask receiver in a background daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(
            target=self._run_flask,
            daemon=True,
            name="solesense-receiver",
        )
        self._thread.start()
        log.info("SoleSense receiver listening on %s:%d", self._host, self._port)
        time.sleep(0.3)   # let Flask bind before callers check is_connected

    def _run_flask(self) -> None:
        self._app.run(
            host=self._host,
            port=self._port,
            threaded=True,
            use_reloader=False,
        )

    def stop(self) -> None:
        self._running = False
        log.info("SoleSense receiver stop requested.")

    # ── Public read API ───────────────────────────────────────────────────────

    def latest_packet(self) -> Optional[dict]:
        """Most recently received packet dict, or None if buffer is empty."""
        with self._lock:
            return self._buffer[-1] if self._buffer else None

    def recent_packets(self, n: int = 100) -> list[dict]:
        """
        Last `n` packets, oldest → newest.
        Returns fewer than n if the buffer is not yet full.
        """
        with self._lock:
            buf = list(self._buffer)
        return buf[-n:] if len(buf) >= n else buf

    def all_packets(self) -> list[dict]:
        """Complete buffer contents, oldest → newest."""
        with self._lock:
            return list(self._buffer)

    def clear(self) -> None:
        """Empty the packet buffer and reset all tracking state."""
        with self._lock:
            self._buffer.clear()
            self._arrival_times.clear()
            self._last_received = 0.0   # reset so is_connected() → False

    # ── Status ────────────────────────────────────────────────────────────────

    def is_connected(self) -> bool:
        """True if a packet arrived within CONNECTION_TIMEOUT seconds."""
        if self._last_received == 0.0:
            return False
        return (time.time() - self._last_received) < CONNECTION_TIMEOUT

    def packet_rate_hz(self) -> float:
        """Packets per second, measured over the last RATE_WINDOW_S seconds."""
        now = time.time()
        with self._lock:
            recent = [t for t in self._arrival_times
                      if now - t <= RATE_WINDOW_S]
        if len(recent) < 2:
            return 0.0
        elapsed = recent[-1] - recent[0]
        return (len(recent) - 1) / elapsed if elapsed > 0 else 0.0

    def status(self) -> dict:
        """
        Summary dict — safe to display directly in the Streamlit dashboard.

        Keys
        ----
        connected        bool
        packet_rate_hz   float
        total_received   int
        total_errors     int
        buffer_size      int
        last_received_s  float | None   seconds since last packet
        last_timestamp   int   | None   ESP32 millis() of last packet
        last_temp_c      float | None
        """
        pkt = self.latest_packet()
        return {
            "connected":        self.is_connected(),
            "packet_rate_hz":   round(self.packet_rate_hz(), 1),
            "total_received":   self._total_received,
            "total_errors":     self._total_errors,
            "buffer_size":      len(self._buffer),
            "last_received_s":  (round(time.time() - self._last_received, 1)
                                 if self._last_received > 0 else None),
            "last_timestamp":   pkt.get("timestamp") if pkt else None,
            "last_temp_c":      pkt.get("temperature") if pkt else None,
        }


# ── Module-level singleton ────────────────────────────────────────────────────
_receiver_instance: Optional[SoleSenseReceiver] = None


def get_receiver(host: str = "0.0.0.0", port: int = 5005) -> SoleSenseReceiver:
    """
    Return (and lazily start) the module-level singleton receiver.
    Safe to call multiple times — always returns the same instance.
    """
    global _receiver_instance
    if _receiver_instance is None:
        _receiver_instance = SoleSenseReceiver(host=host, port=port)
        _receiver_instance.start()
    return _receiver_instance


# ── Standalone entry point ────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5005

    print()
    print("=" * 52)
    print("  SoleSense ESP32-S3 Receiver")
    print(f"  Listening  :  0.0.0.0:{port}")
    print(f"  Endpoint   :  POST /api/sensor")
    print(f"  Health     :  GET  /api/health")
    print("=" * 52)
    print()
    print("  Set SERVER_IP in firmware/config.h to this")
    print("  machine's Wi-Fi IP address, then flash the ESP32.")
    print()
    print("  Press Ctrl+C to stop.")
    print()

    r = SoleSenseReceiver(host="0.0.0.0", port=port)
    r.start()

    try:
        while True:
            time.sleep(2)
            s  = r.status()
            tag = "CONNECTED  " if s["connected"] else "WAITING... "
            print(f"\r  [{tag}]  "
                  f"rate={s['packet_rate_hz']:5.1f} Hz  "
                  f"recv={s['total_received']:6d}  "
                  f"err={s['total_errors']}  "
                  f"temp={s['last_temp_c']}°C",
                  end="", flush=True)
    except KeyboardInterrupt:
        print("\nStopped.")
