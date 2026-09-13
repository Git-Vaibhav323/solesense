"""
SoleSense — src/hardware_input.py
===================================
Hardware input adapter: the dataset-mode equivalent for live ESP32-S3 data.

This module is the single connection point between raw ESP32 sensor readings
and the existing SoleSense analytics pipeline.  Nothing downstream changes.

Architecture
------------

  ┌─────────────────────────────────────────────────────┐
  │  EXISTING PATH                                      │
  │  data_loader.load_dataset()                         │
  │        ↓                                            │
  │  preprocessing → pressure/gait/bilateral features   │
  │        ↓                                            │
  │  compute_risk(row)  →  RiskResult                   │
  └─────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────┐
  │  NEW HARDWARE PATH (this file)                      │
  │  ESP32 JSON packet  (flat fsr1..fsr4 format)        │
  │        ↓                                            │
  │  HardwareInputAdapter.packet_to_feature_row()       │
  │        ↓   same pd.Series schema                    │
  │  compute_risk(row)  →  RiskResult  ← identical      │
  └─────────────────────────────────────────────────────┘

ESP32 packet schema (flat — as the firmware sends it)
------------------------------------------------------
{
    "timestamp": 123456789,       required  int   ESP32 millis()
    "fsr1":      421,             required  int   ADC 0-4095  forefoot medial
    "fsr2":      380,             required  int   ADC 0-4095  forefoot lateral
    "fsr3":      210,             required  int   ADC 0-4095  midfoot
    "fsr4":      510,             required  int   ADC 0-4095  heel
    "temperature": 31.42,         optional  float °C  (null if unavailable)
    "ax":  0.03,                  optional  float acceleration x  (g)
    "ay": -0.02,                  optional  float acceleration y  (g)
    "az":  0.98,                  optional  float acceleration z  (g)
    "gx":  1.24,                  optional  float gyroscope x  (°/s)
    "gy": -0.81,                  optional  float gyroscope y  (°/s)
    "gz":  0.32                   optional  float gyroscope z  (°/s)
}

FSR → pressure mapping
-----------------------
  fsr1  →  forefoot_medial   (metatarsal, inner)
  fsr2  →  forefoot_lateral  (metatarsal, outer)
  fsr3  →  midfoot           (arch)
  fsr4  →  heel / rearfoot

Mapping is configurable via FSR_REGION_MAP below.

FSR → proxy pressure (kPa)
--------------------------
FSR ADC counts are NOT clinically calibrated kPa.
A linear proxy is applied:

    proxy_kpa = (adc_count / FSR_ADC_MAX) * FSR_SCALE_KPA

where FSR_SCALE_KPA = 600.0 covers a plausible plantar pressure range.
Adjust after bench calibration against known loads.

Single-insole limitation
------------------------
This prototype has ONE insole.  Bilateral features (left vs. right) are set
to 0.0 and are documented as NOT_AVAILABLE.  Bilateral risk rules will not
fire.  This is the correct behaviour — no bilateral data is fabricated.

Feature row produced
--------------------
The pd.Series returned by packet_to_feature_row() contains every column
that compute_risk() reads, plus display-only extras.  Missing-feature safety
is already built into compute_risk() (it uses row.get(..., default)).
"""

from __future__ import annotations

import math
import time
from collections import deque
from typing import Optional

import numpy as np
import pandas as pd

# ── Configurable constants ────────────────────────────────────────────────────

# FSR ADC full-scale (12-bit ESP32-S3)
FSR_ADC_MAX = 4095

# Proxy pressure scale: ADC full-scale → this many proxy kPa
# Typical peak plantar pressure range: 100–800 kPa.
# 600 kPa is a plausible midpoint for unshod walking.
# Increase after bench calibration if FSR under-reads at high loads.
FSR_SCALE_KPA: float = 600.0

# Frame duration at 20 Hz (used for PTI proxy calculation)
FRAME_DURATION_S: float = 1.0 / 20.0   # 0.05 s

# Persistence threshold: fraction of FSR_SCALE_KPA considered "elevated load"
PERSISTENCE_LOAD_THRESHOLD: float = 0.30

# Minimum load fraction to count as weight-bearing (step detection)
MIN_LOAD_FRACTION: float = 0.05

# Analysis window used when converting a rolling buffer to a feature row
DEFAULT_WINDOW_S: float = 5.0

# FSR → anatomical region mapping.
# Change this to match your physical insole assembly.
FSR_REGION_MAP: dict[str, str] = {
    "fsr1": "forefoot_medial",
    "fsr2": "forefoot_lateral",
    "fsr3": "midfoot",
    "fsr4": "heel",
}

# Bilateral features unavailable on single-insole prototype
NOT_AVAILABLE_BILATERAL = [
    "asym_pti_total_kpa_s",
    "asym_press_mean_kpa",
    "gait_symmetry_index",
    "asym_load_forefoot",
    "asym_dir_pti_total_kpa_s",
]


# ═════════════════════════════════════════════════════════════════════════════
#  Flat packet parser
# ═════════════════════════════════════════════════════════════════════════════

class PacketValidationError(ValueError):
    """Raised when a raw dict does not match the expected ESP32 packet schema."""


def parse_flat_packet(raw: dict) -> dict:
    """
    Validate and normalise a raw ESP32 JSON dict (flat fsr1..fsr4 format).

    Parameters
    ----------
    raw : dict  —  parsed JSON as received from the ESP32

    Returns
    -------
    dict with keys:
        timestamp   int       (ms)
        fsr1..fsr4  int       (ADC counts, clamped 0–FSR_ADC_MAX)
        temperature float|None
        ax..gz      float     (0.0 if unavailable)
        received_at float     (time.time() at parse)

    Raises
    ------
    PacketValidationError  on missing or non-parseable required fields.
    """
    # ── timestamp ─────────────────────────────────────────────────────────────
    if "timestamp" not in raw:
        raise PacketValidationError("Missing required field: 'timestamp'")
    try:
        timestamp = int(raw["timestamp"])
    except (TypeError, ValueError):
        raise PacketValidationError(f"Invalid timestamp: {raw['timestamp']!r}")

    # ── FSR channels ──────────────────────────────────────────────────────────
    fsr = {}
    for key in ("fsr1", "fsr2", "fsr3", "fsr4"):
        if key not in raw:
            raise PacketValidationError(f"Missing required field: '{key}'")
        try:
            val = int(raw[key])
        except (TypeError, ValueError):
            raise PacketValidationError(
                f"Invalid value for '{key}': {raw[key]!r} — expected integer ADC count"
            )
        fsr[key] = max(0, min(FSR_ADC_MAX, val))   # clamp to valid ADC range

    # ── temperature ───────────────────────────────────────────────────────────
    temperature: Optional[float] = None
    raw_temp = raw.get("temperature")
    if raw_temp is not None:
        try:
            temperature = float(raw_temp)
        except (TypeError, ValueError):
            temperature = None   # malformed → unavailable, not an error

    # ── IMU ───────────────────────────────────────────────────────────────────
    imu_fields = {}
    for axis in ("ax", "ay", "az", "gx", "gy", "gz"):
        raw_val = raw.get(axis)
        if raw_val is not None:
            try:
                imu_fields[axis] = float(raw_val)
            except (TypeError, ValueError):
                imu_fields[axis] = 0.0
        else:
            imu_fields[axis] = 0.0

    return {
        "timestamp":    timestamp,
        "fsr1":         fsr["fsr1"],
        "fsr2":         fsr["fsr2"],
        "fsr3":         fsr["fsr3"],
        "fsr4":         fsr["fsr4"],
        "temperature":  temperature,
        "ax":           imu_fields["ax"],
        "ay":           imu_fields["ay"],
        "az":           imu_fields["az"],
        "gx":           imu_fields["gx"],
        "gy":           imu_fields["gy"],
        "gz":           imu_fields["gz"],
        "received_at":  time.time(),
    }


# ═════════════════════════════════════════════════════════════════════════════
#  Single-packet → feature row  (for Quick Analysis / instant risk)
# ═════════════════════════════════════════════════════════════════════════════

def single_packet_to_feature_row(packet: dict) -> pd.Series:
    """
    Convert ONE parsed packet (from parse_flat_packet) to a feature row
    suitable for compute_risk().

    Use this when you only have the latest reading and want an immediate
    risk estimate without a rolling window.

    Note: temporal features (persistence, step_time_std) will be 0.0
    because a single packet has no history.  Use HardwareInputAdapter
    for window-based features.

    Parameters
    ----------
    packet : dict   output of parse_flat_packet()

    Returns
    -------
    pd.Series   compatible with src.risk_engine.compute_risk()
    """
    fsr1 = packet["fsr1"]
    fsr2 = packet["fsr2"]
    fsr3 = packet["fsr3"]
    fsr4 = packet["fsr4"]

    total_adc = fsr1 + fsr2 + fsr3 + fsr4
    total_kpa = (total_adc / FSR_ADC_MAX) * FSR_SCALE_KPA

    # Regional fractions
    ff_adc = fsr1 + fsr2                    # forefoot
    rf_adc = fsr4                           # rearfoot / heel
    mf_adc = fsr3                           # midfoot

    load_frac_forefoot = ff_adc / total_adc if total_adc > 0 else 0.0
    load_frac_rearfoot = rf_adc / total_adc if total_adc > 0 else 0.0
    load_frac_midfoot  = mf_adc / total_adc if total_adc > 0 else 0.0
    load_frac_toe      = max(0.0, 1.0 - load_frac_forefoot
                                       - load_frac_rearfoot
                                       - load_frac_midfoot)

    # Proxy kPa values
    press_max_kpa  = (max(fsr1, fsr2, fsr3, fsr4) / FSR_ADC_MAX) * FSR_SCALE_KPA
    press_mean_kpa = total_kpa / 4.0

    # PTI proxy for a single frame
    pti_proxy = total_kpa * FRAME_DURATION_S

    # IMU derived
    ax, ay, az = packet["ax"], packet["ay"], packet["az"]
    gx, gy, gz = packet["gx"], packet["gy"], packet["gz"]
    accel_mag = math.sqrt(ax**2 + ay**2 + az**2)
    gyro_mag  = math.sqrt(gx**2 + gy**2 + gz**2)

    temp = packet["temperature"]

    return pd.Series({
        # ── Risk engine inputs ────────────────────────────────────────────────
        "press_max_kpa":                press_max_kpa,
        "press_mean_kpa":               press_mean_kpa,
        "pti_total_kpa_s":              pti_proxy,
        "load_frac_forefoot":           load_frac_forefoot,
        "load_frac_rearfoot":           load_frac_rearfoot,
        "load_frac_midfoot":            load_frac_midfoot,
        "load_frac_toe":                load_frac_toe,
        "step_time_std_s":              0.0,   # single packet — no history
        "persistence_pti_total_kpa_s":  0.0,   # single packet — no history

        # ── Bilateral — NOT AVAILABLE on single insole ────────────────────────
        "asym_pti_total_kpa_s":         0.0,
        "asym_press_mean_kpa":          0.0,
        "gait_symmetry_index":          0.0,
        "asym_load_forefoot":           0.0,
        "asym_dir_pti_total_kpa_s":     0.0,
        "left_loading_fraction":        1.0,
        "right_loading_fraction":       0.0,

        # ── Display extras ────────────────────────────────────────────────────
        "temperature_c":                temp if temp is not None else 0.0,
        "accel_magnitude_g":            accel_mag,
        "gyro_magnitude_deg_s":         gyro_mag,
        "cop_path_length_cm":           0.0,   # needs window for proxy
        "stance_time_s":                0.0,   # needs window
        "cadence_steps_per_min":        0.0,   # needs window

        # ── Metadata ──────────────────────────────────────────────────────────
        "subject_id":    "HARDWARE",
        "footwear":      "LIVE",
        "trial":         "LIVE",
        "footstep_id":   packet["timestamp"],
        "side":          "Left",
    })


# ═════════════════════════════════════════════════════════════════════════════
#  Rolling window adapter  (for window-based features)
# ═════════════════════════════════════════════════════════════════════════════

class HardwareInputAdapter:
    """
    Maintains a rolling buffer of parsed packets and converts them into
    a feature row for compute_risk().

    This is the hardware equivalent of running the full dataset feature
    pipeline over a short window of recent steps.

    Parameters
    ----------
    window_s : float
        How many seconds of history to use.  Default 5 s = 100 packets
        at 20 Hz.
    buffer_size : int
        Maximum packets to keep.  Default 400 = 20 s at 20 Hz.

    Usage
    -----
    adapter = HardwareInputAdapter()

    # feed each incoming packet
    adapter.ingest(parse_flat_packet(raw_json))

    # get feature row for risk engine
    row = adapter.to_feature_row()
    if row is not None:
        result = compute_risk(row)
    """

    def __init__(self,
                 window_s: float = DEFAULT_WINDOW_S,
                 buffer_size: int = 400):
        self.window_s    = window_s
        self._buffer: deque[dict] = deque(maxlen=buffer_size)

    # ── Ingest ────────────────────────────────────────────────────────────────

    def ingest(self, packet: dict) -> None:
        """
        Add one parsed packet (from parse_flat_packet) to the rolling buffer.
        Thread-safe for single-writer scenarios.
        """
        self._buffer.append(packet)

    def ingest_raw(self, raw: dict) -> None:
        """
        Parse and ingest a raw JSON dict in one step.
        Raises PacketValidationError if the packet is malformed.
        """
        self.ingest(parse_flat_packet(raw))

    # ── Query ─────────────────────────────────────────────────────────────────

    def recent_packets(self) -> list[dict]:
        """
        Return packets within the current analysis window (oldest → newest).
        """
        if not self._buffer:
            return []
        now       = self._buffer[-1]["received_at"]
        cutoff    = now - self.window_s
        return [p for p in self._buffer if p["received_at"] >= cutoff]

    def latest_packet(self) -> Optional[dict]:
        """Most recently ingested packet, or None."""
        return self._buffer[-1] if self._buffer else None

    def packet_count(self) -> int:
        return len(self._buffer)

    # ── Feature row ───────────────────────────────────────────────────────────

    def to_feature_row(self) -> Optional[pd.Series]:
        """
        Convert the current analysis window into a feature row for compute_risk().

        Returns None if fewer than 2 packets are in the window (insufficient
        data for any temporal features).

        Returns
        -------
        pd.Series  compatible with src.risk_engine.compute_risk()
        """
        packets = self.recent_packets()
        if len(packets) < 2:
            return None
        return _packets_to_feature_row(packets)

    def clear(self) -> None:
        self._buffer.clear()


# ═════════════════════════════════════════════════════════════════════════════
#  Core feature calculation  (private — used by both adapter and tests)
# ═════════════════════════════════════════════════════════════════════════════

def _fsr_total_kpa(p: dict) -> float:
    """Sum of all 4 FSR channels scaled to proxy kPa."""
    total_adc = p["fsr1"] + p["fsr2"] + p["fsr3"] + p["fsr4"]
    return (total_adc / FSR_ADC_MAX) * FSR_SCALE_KPA


def _packets_to_feature_row(packets: list[dict]) -> pd.Series:
    """
    Convert a list of parsed packets (oldest → newest) to a feature pd.Series.

    Called by HardwareInputAdapter.to_feature_row().
    """
    n = len(packets)

    # ── Pressure arrays ───────────────────────────────────────────────────────
    press_arr = np.array([_fsr_total_kpa(p) for p in packets])

    press_max_kpa  = float(press_arr.max())
    press_mean_kpa = float(press_arr.mean())

    # PTI proxy: sum of press × frame_duration over window
    pti_total = float(np.sum(press_arr) * FRAME_DURATION_S)

    # ── Regional fractions (mean over window) ─────────────────────────────────
    def _ff_frac(p: dict) -> float:
        total = p["fsr1"] + p["fsr2"] + p["fsr3"] + p["fsr4"]
        return (p["fsr1"] + p["fsr2"]) / total if total > 0 else 0.0

    def _rf_frac(p: dict) -> float:
        total = p["fsr1"] + p["fsr2"] + p["fsr3"] + p["fsr4"]
        return p["fsr4"] / total if total > 0 else 0.0

    def _mf_frac(p: dict) -> float:
        total = p["fsr1"] + p["fsr2"] + p["fsr3"] + p["fsr4"]
        return p["fsr3"] / total if total > 0 else 0.0

    ff_arr = np.array([_ff_frac(p) for p in packets])
    rf_arr = np.array([_rf_frac(p) for p in packets])
    mf_arr = np.array([_mf_frac(p) for p in packets])

    load_frac_forefoot = float(ff_arr.mean())
    load_frac_rearfoot = float(rf_arr.mean())
    load_frac_midfoot  = float(mf_arr.mean())
    load_frac_toe      = max(0.0, 1.0 - load_frac_forefoot
                                       - load_frac_rearfoot
                                       - load_frac_midfoot)

    # ── Persistence ───────────────────────────────────────────────────────────
    threshold    = FSR_SCALE_KPA * PERSISTENCE_LOAD_THRESHOLD
    n_elevated   = int(np.sum(press_arr > threshold))
    persistence  = n_elevated / n

    # ── Step time variability ─────────────────────────────────────────────────
    step_time_std = _estimate_step_time_std(packets, press_arr)

    # ── Stance time proxy ─────────────────────────────────────────────────────
    stance_time_s = _estimate_stance_time(press_arr)

    # ── Cadence proxy ─────────────────────────────────────────────────────────
    cadence = _estimate_cadence(press_arr)

    # ── Temperature ───────────────────────────────────────────────────────────
    temps = [p["temperature"] for p in packets if p["temperature"] is not None]
    temp_c = float(np.mean(temps)) if temps else None

    # ── IMU derived ───────────────────────────────────────────────────────────
    imu_present = any(
        abs(p["ax"]) + abs(p["ay"]) + abs(p["az"]) > 0.0 for p in packets
    )
    if imu_present:
        accel_mags = np.array([
            math.sqrt(p["ax"]**2 + p["ay"]**2 + p["az"]**2)
            for p in packets
        ])
        gyro_mags = np.array([
            math.sqrt(p["gx"]**2 + p["gy"]**2 + p["gz"]**2)
            for p in packets
        ])
        accel_mag = float(accel_mags.mean())
        gyro_mag  = float(gyro_mags.mean())
        cop_proxy = float(np.std(accel_mags) * 20.0)   # scaled to cm range
    else:
        accel_mag = 0.0
        gyro_mag  = 0.0
        cop_proxy = 0.0

    # ── Feature row ───────────────────────────────────────────────────────────
    return pd.Series({
        # ── Risk engine inputs ────────────────────────────────────────────────
        "press_max_kpa":                press_max_kpa,
        "press_mean_kpa":               press_mean_kpa,
        "pti_total_kpa_s":              pti_total,
        "load_frac_forefoot":           load_frac_forefoot,
        "load_frac_rearfoot":           load_frac_rearfoot,
        "load_frac_midfoot":            load_frac_midfoot,
        "load_frac_toe":                load_frac_toe,
        "step_time_std_s":              step_time_std,
        "persistence_pti_total_kpa_s":  persistence,

        # ── Bilateral — NOT AVAILABLE on single insole ────────────────────────
        "asym_pti_total_kpa_s":         0.0,
        "asym_press_mean_kpa":          0.0,
        "gait_symmetry_index":          0.0,
        "asym_load_forefoot":           0.0,
        "asym_dir_pti_total_kpa_s":     0.0,
        "left_loading_fraction":        1.0,
        "right_loading_fraction":       0.0,

        # ── Display extras (not used in risk scoring) ─────────────────────────
        "temperature_c":                temp_c if temp_c is not None else 0.0,
        "accel_magnitude_g":            accel_mag,
        "gyro_magnitude_deg_s":         gyro_mag,
        "cop_path_length_cm":           cop_proxy,
        "stance_time_s":                stance_time_s,
        "cadence_steps_per_min":        cadence,

        # ── Metadata ──────────────────────────────────────────────────────────
        "subject_id":    "HARDWARE",
        "footwear":      "LIVE",
        "trial":         "LIVE",
        "footstep_id":   packets[-1]["timestamp"],
        "side":          "Left",
    })


# ─────────────────────────────────────────────────────────────────────────────
#  Gait estimation helpers  (private)
# ─────────────────────────────────────────────────────────────────────────────

def _estimate_step_time_std(packets: list[dict], press_arr: np.ndarray) -> float:
    """
    Estimate step-time variability from load-onset events detected in
    the pressure array.  Returns std of inter-onset intervals in seconds.
    Falls back to 0.0 if fewer than 3 onsets are found.
    """
    threshold = MIN_LOAD_FRACTION * FSR_SCALE_KPA
    onsets: list[float] = []
    in_stance = press_arr[0] > threshold

    for i in range(1, len(press_arr)):
        was_swing  = not in_stance
        now_stance = press_arr[i] > threshold
        if was_swing and now_stance:
            t = packets[i]["received_at"]
            onsets.append(t)
        in_stance = now_stance

    if len(onsets) < 3:
        return 0.0
    intervals = np.diff(onsets)
    return float(np.std(intervals))


def _estimate_stance_time(press_arr: np.ndarray) -> float:
    """
    Estimate mean stance duration (seconds) from contiguous weight-bearing
    segments in the pressure array.
    """
    threshold  = MIN_LOAD_FRACTION * FSR_SCALE_KPA
    in_stance  = False
    start_idx  = 0
    durations: list[float] = []

    for i, p in enumerate(press_arr):
        if not in_stance and p > threshold:
            in_stance = True
            start_idx = i
        elif in_stance and p <= threshold:
            durations.append((i - start_idx) * FRAME_DURATION_S)
            in_stance = False

    if in_stance:
        durations.append((len(press_arr) - start_idx) * FRAME_DURATION_S)

    return float(np.mean(durations)) if durations else 0.7   # 0.7 s fallback


def _estimate_cadence(press_arr: np.ndarray) -> float:
    """
    Estimate cadence (steps/min) from step-onset count over the window.
    """
    threshold   = MIN_LOAD_FRACTION * FSR_SCALE_KPA
    in_stance   = press_arr[0] > threshold
    step_count  = 0

    for i in range(1, len(press_arr)):
        now_stance = press_arr[i] > threshold
        if not in_stance and now_stance:
            step_count += 1
        in_stance = now_stance

    window_s = len(press_arr) * FRAME_DURATION_S
    return (step_count / window_s * 60.0) if window_s > 0 else 0.0


# ═════════════════════════════════════════════════════════════════════════════
#  normalize_input()  —  common entry point for both dataset and hardware
# ═════════════════════════════════════════════════════════════════════════════

def normalize_input(source: str, data) -> Optional[pd.Series]:
    """
    Universal entry point that accepts either a dataset feature row or a
    hardware packet/adapter, and returns a pd.Series for compute_risk().

    Parameters
    ----------
    source : str
        "dataset"  — data is already a pd.Series from the feature pipeline
        "packet"   — data is a parsed packet dict (single reading)
        "window"   — data is a HardwareInputAdapter (uses its rolling window)

    data :
        pd.Series (dataset), dict (packet), or HardwareInputAdapter (window)

    Returns
    -------
    pd.Series ready for compute_risk(), or None if conversion fails.

    Examples
    --------
    # Dataset path (unchanged)
    row    = features_df.iloc[0]
    result = compute_risk(normalize_input("dataset", row))

    # Single hardware packet
    packet = parse_flat_packet(raw_json)
    result = compute_risk(normalize_input("packet", packet))

    # Rolling window
    adapter = HardwareInputAdapter()
    adapter.ingest(packet)
    row = normalize_input("window", adapter)
    if row is not None:
        result = compute_risk(row)
    """
    if source == "dataset":
        if not isinstance(data, pd.Series):
            raise TypeError("source='dataset' expects a pd.Series")
        return data   # already in the right format

    elif source == "packet":
        if not isinstance(data, dict):
            raise TypeError("source='packet' expects a parsed packet dict")
        return single_packet_to_feature_row(data)

    elif source == "window":
        if not isinstance(data, HardwareInputAdapter):
            raise TypeError("source='window' expects a HardwareInputAdapter")
        return data.to_feature_row()

    else:
        raise ValueError(
            f"Unknown source '{source}'. "
            "Use 'dataset', 'packet', or 'window'."
        )


# ═════════════════════════════════════════════════════════════════════════════
#  Mock packet for testing  (clearly labelled — never used in production)
# ═════════════════════════════════════════════════════════════════════════════

def make_mock_packet(timestamp: int = 0,
                     fsr1: int = 420,
                     fsr2: int = 380,
                     fsr3: int = 210,
                     fsr4: int = 510,
                     temperature: float = 31.4,
                     ax: float = 0.03, ay: float = -0.02, az: float = 0.98,
                     gx: float = 1.2,  gy: float = -0.8,  gz: float = 0.3,
                     received_at: Optional[float] = None) -> dict:
    """
    Return a valid parsed packet dict for pipeline testing without hardware.
    MOCK DATA — clearly labelled, never used in production hardware mode.
    """
    return {
        "timestamp":   timestamp,
        "fsr1":        fsr1,
        "fsr2":        fsr2,
        "fsr3":        fsr3,
        "fsr4":        fsr4,
        "temperature": temperature,
        "ax": ax, "ay": ay, "az": az,
        "gx": gx, "gy": gy, "gz": gz,
        "received_at": received_at if received_at is not None else time.time(),
    }
