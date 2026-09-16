"""
SoleSense Hardware — hardware/test_receiver.py
===============================================
Standalone integration test for the ESP32 receiver pipeline.

Tests the complete path WITHOUT requiring real hardware:

  mock JSON packets
       ↓
  SoleSenseReceiver (HTTP POST simulation)
       ↓
  parse_flat_packet  (validates + normalises)
       ↓
  HardwareInputAdapter  (rolling buffer → feature row)
       ↓
  compute_risk()  (existing risk engine — unchanged)
       ↓
  RiskResult  (printed to terminal)

Run from the project root:
    cd f:/Dataset/SoleSense
    python -m hardware.test_receiver

All tests are self-contained.  No Flask server is started;
the receiver's internal _ingest() path is exercised directly
to keep the test fast and dependency-free.
"""

from __future__ import annotations

import sys
import os
import time
import math
import json
import threading
import urllib.request
import urllib.error

# ── Path setup ────────────────────────────────────────────────────────────────
# Allow running as  python -m hardware.test_receiver  from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.hardware_input import (
    parse_flat_packet,
    PacketValidationError,
    HardwareInputAdapter,
    normalize_input,
    make_mock_packet,
    FSR_SCALE_KPA,
    FSR_ADC_MAX,
    NOT_AVAILABLE_BILATERAL,
)
from src.risk_engine import compute_risk
from hardware.esp32_receiver import SoleSenseReceiver


# ── Helpers ───────────────────────────────────────────────────────────────────

_PASS = 0
_FAIL = 0


def ok(label: str) -> None:
    global _PASS
    _PASS += 1
    print(f"  ✓  {label}")


def fail(label: str, detail: str = "") -> None:
    global _FAIL
    _FAIL += 1
    msg = f"  ✗  {label}"
    if detail:
        msg += f"  →  {detail}"
    print(msg)


def section(title: str) -> None:
    print()
    print(f"{'─' * 55}")
    print(f"  {title}")
    print(f"{'─' * 55}")


def _make_raw(**overrides) -> dict:
    """Build a minimal valid raw JSON dict as the ESP32 sends it."""
    base = {
        "timestamp": 12345,
        "fsr1": 421, "fsr2": 380, "fsr3": 210, "fsr4": 510,
        "temperature": 31.42,
        "ax": 0.031, "ay": -0.020, "az": 0.987,
        "gx": 1.240, "gy": -0.810, "gz":  0.330,
    }
    base.update(overrides)
    return base


def _make_window(n: int = 100, vary: bool = True) -> list[dict]:
    """
    Return a list of n parsed packets with received_at set,
    simulating a rolling window from the receiver buffer.
    """
    now = time.time()
    packets = []
    for i in range(n):
        fsr1 = 420 + (i % 10) * 5  if vary else 420
        fsr4 = 510 + (i % 12) * 6  if vary else 510
        p = make_mock_packet(
            timestamp=i * 50,
            fsr1=fsr1, fsr4=fsr4,
            received_at=now - (n - i) * 0.05,
        )
        packets.append(p)
    return packets


# ═════════════════════════════════════════════════════════════════════════════
#  TEST GROUP 1 — JSON packet parsing
# ═════════════════════════════════════════════════════════════════════════════

def test_parsing():
    section("1. JSON Packet Parsing")

    # 1-1  valid full packet
    try:
        pkt = parse_flat_packet(_make_raw())
        assert pkt["timestamp"] == 12345
        assert pkt["fsr1"] == 421
        assert pkt["temperature"] == 31.42
        assert pkt["ax"] == 0.031
        ok("valid full packet parsed")
    except Exception as e:
        fail("valid full packet parsed", str(e))

    # 1-2  temperature field absent → None (not an error)
    try:
        raw = {k: v for k, v in _make_raw().items() if k != "temperature"}
        pkt = parse_flat_packet(raw)
        assert pkt["temperature"] is None
        ok("missing temperature → None")
    except Exception as e:
        fail("missing temperature → None", str(e))

    # 1-3  IMU fields absent → default 0.0
    try:
        raw = {k: v for k, v in _make_raw().items()
               if k not in ("ax","ay","az","gx","gy","gz")}
        pkt = parse_flat_packet(raw)
        assert pkt["ax"] == 0.0 and pkt["gz"] == 0.0
        ok("absent IMU fields → 0.0")
    except Exception as e:
        fail("absent IMU fields → 0.0", str(e))

    # 1-4  FSR value over ADC_MAX → clamped
    try:
        pkt = parse_flat_packet(_make_raw(fsr1=9999))
        assert pkt["fsr1"] == FSR_ADC_MAX
        ok(f"fsr1=9999 clamped to {FSR_ADC_MAX}")
    except Exception as e:
        fail("ADC clamp high", str(e))

    # 1-5  FSR value negative → clamped to 0
    try:
        pkt = parse_flat_packet(_make_raw(fsr2=-50))
        assert pkt["fsr2"] == 0
        ok("fsr2=-50 clamped to 0")
    except Exception as e:
        fail("ADC clamp low", str(e))

    # 1-6  missing timestamp → PacketValidationError
    try:
        raw = {k: v for k, v in _make_raw().items() if k != "timestamp"}
        parse_flat_packet(raw)
        fail("missing timestamp raises error")
    except PacketValidationError:
        ok("missing timestamp → PacketValidationError")
    except Exception as e:
        fail("missing timestamp → PacketValidationError", str(e))

    # 1-7  missing fsr3 → PacketValidationError
    try:
        raw = {k: v for k, v in _make_raw().items() if k != "fsr3"}
        parse_flat_packet(raw)
        fail("missing fsr3 raises error")
    except PacketValidationError:
        ok("missing fsr3 → PacketValidationError")
    except Exception as e:
        fail("missing fsr3 → PacketValidationError", str(e))

    # 1-8  non-numeric fsr value → PacketValidationError
    try:
        parse_flat_packet(_make_raw(fsr4="heavy"))
        fail("non-numeric fsr4 raises error")
    except PacketValidationError:
        ok("non-numeric fsr4 → PacketValidationError")
    except Exception as e:
        fail("non-numeric fsr4 → PacketValidationError", str(e))

    # 1-9  malformed temperature (non-numeric) → None (silent drop)
    try:
        pkt = parse_flat_packet(_make_raw(temperature="hot"))
        assert pkt["temperature"] is None
        ok("malformed temperature → None (silent)")
    except Exception as e:
        fail("malformed temperature silent drop", str(e))

    # 1-10 empty dict → PacketValidationError
    try:
        parse_flat_packet({})
        fail("empty dict raises error")
    except PacketValidationError:
        ok("empty dict → PacketValidationError")
    except Exception as e:
        fail("empty dict → PacketValidationError", str(e))

    # 1-11 received_at is stamped automatically
    try:
        before = time.time()
        pkt = parse_flat_packet(_make_raw())
        after = time.time()
        assert before <= pkt["received_at"] <= after + 0.01
        ok("received_at wall-clock timestamp added")
    except Exception as e:
        fail("received_at timestamp", str(e))


# ═════════════════════════════════════════════════════════════════════════════
#  TEST GROUP 2 — Receiver internal state  (no HTTP, no Flask server)
# ═════════════════════════════════════════════════════════════════════════════

def test_receiver_state():
    section("2. Receiver Internal State")

    r = SoleSenseReceiver(host="0.0.0.0", port=19999)  # port unused here

    # 2-1  initially not connected
    try:
        assert not r.is_connected()
        ok("initially not connected")
    except Exception as e:
        fail("initially not connected", str(e))

    # 2-2  buffer empty → latest_packet() is None
    try:
        assert r.latest_packet() is None
        ok("empty buffer → latest_packet() is None")
    except Exception as e:
        fail("empty buffer latest_packet", str(e))

    # 2-3  packet_rate_hz() is 0.0 when no data
    try:
        assert r.packet_rate_hz() == 0.0
        ok("no data → packet_rate_hz() == 0.0")
    except Exception as e:
        fail("packet_rate_hz empty", str(e))

    # 2-4  ingest packets and check connected
    now = time.time()
    for i in range(10):
        pkt = parse_flat_packet(_make_raw(timestamp=i * 50))
        pkt["received_at"] = now - (10 - i) * 0.05
        r._ingest(pkt)   # _ingest sets _last_received = time.time() internally

    try:
        assert r.is_connected()
        ok("after ingestion → is_connected() True")
    except Exception as e:
        fail("is_connected after ingest", str(e))

    # 2-5  latest_packet returns last one
    try:
        last = r.latest_packet()
        assert last is not None
        assert last["timestamp"] == 9 * 50
        ok("latest_packet() returns most recent")
    except Exception as e:
        fail("latest_packet most recent", str(e))

    # 2-6  recent_packets(5) returns 5
    try:
        recent = r.recent_packets(5)
        assert len(recent) == 5
        ok("recent_packets(5) returns 5 items")
    except Exception as e:
        fail("recent_packets count", str(e))

    # 2-7  recent_packets oldest→newest order
    try:
        recent = r.recent_packets(10)
        ts = [p["timestamp"] for p in recent]
        assert ts == sorted(ts)
        ok("recent_packets() in chronological order")
    except Exception as e:
        fail("recent_packets order", str(e))

    # 2-8  packet_rate estimated — send packets with real time spacing
    try:
        r.clear()
        for i in range(15):
            pkt = parse_flat_packet(_make_raw(timestamp=i * 50))
            r._ingest(pkt)
            time.sleep(0.03)   # 30 ms apart → ~33 Hz, clearly non-zero
        rate = r.packet_rate_hz()
        assert rate > 0, f"expected > 0, got {rate}"
        ok(f"packet_rate_hz() = {rate:.1f} Hz (non-zero)")
    except Exception as e:
        fail("packet_rate_hz non-zero", str(e))

    # 2-9  status() dict has required keys
    try:
        s = r.status()
        required = ["connected", "packet_rate_hz", "total_received",
                    "total_errors", "buffer_size", "last_received_s"]
        for k in required:
            assert k in s, f"missing key: {k}"
        ok("status() dict has all required keys")
    except Exception as e:
        fail("status() keys", str(e))

    # 2-10 total_received counter increments
    try:
        before = r._total_received
        pkt = parse_flat_packet(_make_raw(timestamp=99999))
        r._ingest(pkt)
        assert r._total_received == before + 1
        ok("total_received counter increments on ingest")
    except Exception as e:
        fail("total_received counter", str(e))

    # 2-11 clear() empties buffer
    try:
        r.clear()
        assert r.latest_packet() is None
        assert len(r.recent_packets(100)) == 0
        ok("clear() empties buffer")
    except Exception as e:
        fail("clear()", str(e))

    # 2-12 not connected after clear (no recent packets)
    try:
        assert not r.is_connected()
        ok("not connected after clear()")
    except Exception as e:
        fail("not connected after clear", str(e))


# ═════════════════════════════════════════════════════════════════════════════
#  TEST GROUP 3 — Receiver via live HTTP POST  (Flask server)
# ═════════════════════════════════════════════════════════════════════════════

def test_receiver_http():
    section("3. Receiver HTTP POST  (live Flask server)")

    PORT = 19876
    r = SoleSenseReceiver(host="127.0.0.1", port=PORT)
    r.start()
    time.sleep(0.5)   # let Flask bind

    url_sensor = f"http://127.0.0.1:{PORT}/api/sensor"
    url_health = f"http://127.0.0.1:{PORT}/api/health"

    def post_json(url: str, payload: dict) -> tuple[int, dict]:
        body = json.dumps(payload).encode()
        req  = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, {}

    def get_json(url: str) -> tuple[int, dict]:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                return resp.status, json.loads(resp.read())
        except Exception as e:
            return 0, {}

    # 3-1  health endpoint returns 200
    try:
        code, body = get_json(url_health)
        assert code == 200
        assert body.get("status") == "running"
        ok("GET /api/health → 200 running")
    except Exception as e:
        fail("GET /api/health", str(e))

    # 3-2  valid packet → 200 ok
    try:
        code, body = post_json(url_sensor, _make_raw())
        assert code == 200
        assert body.get("status") == "ok"
        ok("valid packet POST → 200")
    except Exception as e:
        fail("valid packet POST 200", str(e))

    # 3-3  packet appears in buffer
    try:
        time.sleep(0.1)
        pkt = r.latest_packet()
        assert pkt is not None
        assert pkt["fsr1"] == 421
        ok("packet stored in buffer after POST")
    except Exception as e:
        fail("packet in buffer", str(e))

    # 3-4  is_connected() True after valid packet
    try:
        assert r.is_connected()
        ok("is_connected() True after valid POST")
    except Exception as e:
        fail("is_connected after POST", str(e))

    # 3-5  malformed JSON body → 400
    try:
        req = urllib.request.Request(
            url_sensor, data=b"not json at all",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                code = resp.status
        except urllib.error.HTTPError as e:
            code = e.code
        assert code == 400
        ok("malformed JSON body → 400")
    except Exception as e:
        fail("malformed JSON → 400", str(e))

    # 3-6  missing required field → 422
    try:
        bad = {k: v for k, v in _make_raw().items() if k != "fsr2"}
        code, _ = post_json(url_sensor, bad)
        assert code == 422
        ok("missing fsr2 → 422")
    except Exception as e:
        fail("missing field → 422", str(e))

    # 3-7  error counter increments on bad packets
    try:
        err_before = r._total_errors
        post_json(url_sensor, {})   # will fail validation
        time.sleep(0.1)
        assert r._total_errors > err_before
        ok("total_errors increments on bad packet")
    except Exception as e:
        fail("total_errors counter", str(e))

    # 3-8  send 20 packets quickly, check rate
    try:
        for i in range(20):
            post_json(url_sensor, _make_raw(timestamp=i * 50))
        time.sleep(0.2)
        rate = r.packet_rate_hz()
        assert rate > 0
        ok(f"20 packets → rate = {rate:.1f} Hz")
    except Exception as e:
        fail("rate after burst", str(e))

    # 3-9  last_received_s is recent
    try:
        s = r.status()
        assert s["last_received_s"] is not None
        assert s["last_received_s"] < 5.0
        ok(f"last_received_s = {s['last_received_s']} s")
    except Exception as e:
        fail("last_received_s recent", str(e))


# ═════════════════════════════════════════════════════════════════════════════
#  TEST GROUP 4 — Adapter: receiver → feature row → compute_risk
# ═════════════════════════════════════════════════════════════════════════════

def test_adapter_pipeline():
    section("4. Adapter → Feature Row → compute_risk()")

    adapter = HardwareInputAdapter(window_s=5.0)

    # 4-1  empty adapter → None
    try:
        assert adapter.to_feature_row() is None
        ok("empty adapter → to_feature_row() is None")
    except Exception as e:
        fail("empty adapter None", str(e))

    # 4-2  one packet → still None (need ≥ 2)
    try:
        adapter.ingest(make_mock_packet(timestamp=0,
                                        received_at=time.time()))
        assert adapter.to_feature_row() is None
        ok("single packet → still None (< 2 needed)")
    except Exception as e:
        fail("single packet None", str(e))

    # 4-3  fill window → returns pd.Series
    import pandas as pd
    try:
        adapter.clear()
        for pkt in _make_window(100):
            adapter.ingest(pkt)
        row = adapter.to_feature_row()
        assert isinstance(row, pd.Series)
        ok("100 packets → returns pd.Series")
    except Exception as e:
        fail("100 packets → pd.Series", str(e))

    # 4-4  all required risk engine columns present
    required_cols = [
        "press_max_kpa", "pti_total_kpa_s",
        "load_frac_forefoot", "load_frac_rearfoot",
        "step_time_std_s", "persistence_pti_total_kpa_s",
        "asym_pti_total_kpa_s", "gait_symmetry_index",
        "asym_load_forefoot", "asym_press_mean_kpa",
    ]
    try:
        row = adapter.to_feature_row()
        for col in required_cols:
            assert col in row.index, f"missing: {col}"
        ok("all required risk engine columns present")
    except Exception as e:
        fail("required columns", str(e))

    # 4-5  bilateral features are 0.0 (single insole — never fabricated)
    try:
        row = adapter.to_feature_row()
        for col in NOT_AVAILABLE_BILATERAL:
            assert row[col] == 0.0, f"{col} should be 0.0, got {row[col]}"
        ok("bilateral features all 0.0 (single insole — correct)")
    except Exception as e:
        fail("bilateral 0.0", str(e))

    # 4-6  press_max_kpa is positive
    try:
        row = adapter.to_feature_row()
        assert row["press_max_kpa"] > 0
        ok(f"press_max_kpa = {row['press_max_kpa']:.1f} (positive)")
    except Exception as e:
        fail("press_max_kpa positive", str(e))

    # 4-7  load fractions sum to ≈ 1.0
    try:
        row = adapter.to_feature_row()
        total = (row["load_frac_forefoot"] + row["load_frac_rearfoot"]
                 + row["load_frac_midfoot"] + row["load_frac_toe"])
        assert abs(total - 1.0) < 0.01, f"sum = {total}"
        ok(f"load fractions sum = {total:.4f} ≈ 1.0")
    except Exception as e:
        fail("load fractions sum", str(e))

    # 4-8  persistence is 0–1
    try:
        row = adapter.to_feature_row()
        p = row["persistence_pti_total_kpa_s"]
        assert 0.0 <= p <= 1.0
        ok(f"persistence = {p:.3f}  (0–1 OK)")
    except Exception as e:
        fail("persistence range", str(e))

    # 4-9  temperature populated when data has it
    try:
        row = adapter.to_feature_row()
        assert row["temperature_c"] > 0
        ok(f"temperature_c = {row['temperature_c']:.2f} °C")
    except Exception as e:
        fail("temperature_c populated", str(e))

    # 4-10 temperature 0.0 when all packets have None
    try:
        adapter.clear()
        for pkt in _make_window(40):
            pkt["temperature"] = None
            adapter.ingest(pkt)
        row = adapter.to_feature_row()
        assert row["temperature_c"] == 0.0
        ok("temperature_c = 0.0 when unavailable")
    except Exception as e:
        fail("temperature 0.0 unavailable", str(e))

    # 4-11 normalize_input('window') returns same result
    try:
        adapter.clear()
        for pkt in _make_window(100):
            adapter.ingest(pkt)
        row1 = adapter.to_feature_row()
        row2 = normalize_input("window", adapter)
        assert row1 is not None and row2 is not None
        assert abs(row1["press_max_kpa"] - row2["press_max_kpa"]) < 0.001
        ok("normalize_input('window') consistent with direct call")
    except Exception as e:
        fail("normalize_input window", str(e))

    # 4-12 compute_risk() accepts the feature row
    try:
        row = adapter.to_feature_row()
        result = compute_risk(row)
        assert 0 <= result.risk_score <= 100
        assert result.risk_level in ("NORMAL", "MONITOR", "ALERT")
        ok(f"compute_risk() → score={result.risk_score:.1f}  level={result.risk_level}")
    except Exception as e:
        fail("compute_risk accepts row", str(e))

    # 4-13 high FSR load increases risk score vs quiet
    try:
        def _score(fsr_val: int) -> float:
            a = HardwareInputAdapter(window_s=5.0)
            now = time.time()
            for i in range(100):
                a.ingest(make_mock_packet(
                    fsr1=fsr_val, fsr2=fsr_val, fsr3=fsr_val, fsr4=fsr_val,
                    received_at=now - (100-i)*0.05,
                ))
            row = a.to_feature_row()
            return compute_risk(row).risk_score

        score_heavy = _score(3800)
        score_light = _score(10)
        assert score_heavy > score_light
        ok(f"high load score ({score_heavy:.1f}) > low load score ({score_light:.1f})")
    except Exception as e:
        fail("high load raises risk", str(e))


# ═════════════════════════════════════════════════════════════════════════════
#  TEST GROUP 5 — End-to-end: HTTP POST → buffer → risk result
# ═════════════════════════════════════════════════════════════════════════════

def test_end_to_end():
    section("5. End-to-End: HTTP POST → Buffer → Risk")

    PORT = 19877
    r = SoleSenseReceiver(host="127.0.0.1", port=PORT)
    r.start()
    time.sleep(0.5)

    url = f"http://127.0.0.1:{PORT}/api/sensor"

    def post(payload):
        body = json.dumps(payload).encode()
        req  = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            return e.code

    # Send 100 packets simulating ~5 s of walking
    adapter = HardwareInputAdapter(window_s=5.0)
    now     = time.time()

    for i in range(100):
        raw = _make_raw(
            timestamp=i * 50,
            fsr1=400 + (i % 10) * 8,
            fsr4=500 + (i % 8)  * 10,
        )
        code = post(raw)
        if code != 200:
            fail(f"packet {i} POST failed", f"HTTP {code}")
            return

    time.sleep(0.3)

    # 5-1  all 100 arrived
    try:
        assert r._total_received >= 100
        ok(f"all 100 packets received  (total={r._total_received})")
    except Exception as e:
        fail("100 packets received", str(e))

    # 5-2  connected
    try:
        assert r.is_connected()
        ok("receiver reports connected")
    except Exception as e:
        fail("connected", str(e))

    # 5-3  buffer has packets
    try:
        pkts = r.recent_packets(100)
        assert len(pkts) >= 100
        ok(f"buffer has {len(pkts)} packets")
    except Exception as e:
        fail("buffer has packets", str(e))

    # 5-4  feed into adapter → feature row
    try:
        pkts = r.recent_packets(100)
        for p in pkts:
            adapter.ingest(p)
        row = adapter.to_feature_row()
        assert row is not None
        ok("received packets → feature row")
    except Exception as e:
        fail("received packets → feature row", str(e))

    # 5-5  feature row → risk result
    try:
        row    = adapter.to_feature_row()
        result = compute_risk(row)
        assert 0 <= result.risk_score <= 100
        ok(f"risk result: {result.risk_level}  score={result.risk_score:.1f}")
    except Exception as e:
        fail("feature row → risk result", str(e))

    # 5-6  zero-error path
    try:
        assert r._total_errors == 0
        ok("zero validation errors during clean run")
    except Exception as e:
        fail("zero errors", str(e))


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main():
    print()
    print("=" * 55)
    print("  SOLESENSE  —  Receiver Pipeline Test")
    print("  No hardware required.  Mock packets only.")
    print("=" * 55)

    test_parsing()
    test_receiver_state()
    test_receiver_http()
    test_adapter_pipeline()
    test_end_to_end()

    print()
    print("=" * 55)
    total = _PASS + _FAIL
    print(f"  Results:  {_PASS}/{total} passed  |  {_FAIL} failed")
    print("=" * 55)
    print()

    if _FAIL > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
