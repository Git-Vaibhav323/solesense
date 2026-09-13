"""
SoleSense Hardware — hardware_adapter.py
==========================================
Converts a rolling window of SensorPackets from the ESP32-S3 into the
feature row that src/risk_engine.compute_risk() expects.

Architecture
------------
SensorPacket (from esp32_receiver)
        ↓
  HardwareAdapter.to_feature_row()
        ↓
  pd.Series  ←── same schema as features.csv
        ↓
  src/risk_engine.compute_risk()
        ↓
  RiskResult  →  dashboard

Feature mapping
---------------
The risk engine uses these 10 columns:

  press_max_kpa                  ← FSR peak, scaled from ADC → proxy kPa
  pti_total_kpa_s                ← summed FSR load over window
  asym_pti_total_kpa_s           ← NOT AVAILABLE (one insole) → 0.0
  asym_press_mean_kpa            ← NOT AVAILABLE (one insole) → 0.0
  load_frac_forefoot             ← (forefoot_medial + forefoot_lateral) / total
  load_frac_rearfoot             ← heel / total
  step_time_std_s                ← std of inter-packet interval (gait proxy)
  gait_symmetry_index            ← NOT AVAILABLE (one insole) → 0.0
  persistence_pti_total_kpa_s    ← fraction of recent packets above PTI threshold
  asym_load_forefoot             ← NOT AVAILABLE (one insole) → 0.0

Additional columns passed through for display (not used in risk scoring):
  left_loading_fraction          ← 1.0 (single insole is the reference)
  right_loading_fraction         ← 0.0
  asym_dir_pti_total_kpa_s       ← 0.0
  cop_path_length_cm             ← proxy from IMU accel magnitude
  stance_time_s                  ← proxy from contiguous load window
  cadence_steps_per_min          ← estimated from load onset events
  temperature_c                  ← raw TMP117 reading (extra column)
  accel_magnitude_g              ← √(ax²+ay²+az²)
  gyro_magnitude_deg_s           ← √(gx²+gy²+gz²)

⚠ Single-insole limitations (documented)
-----------------------------------------
Bilateral features (asym_*) are set to 0.0 because there is only ONE
insole. These are clearly marked NOT_AVAILABLE in the output dict.
The risk engine will not trigger bilateral rules (their thresholds will
not be crossed), which is the correct behaviour for a one-foot prototype.

FSR → pressure scaling
-----------------------
FSR ADC counts are NOT clinically calibrated kPa. We apply a linear
scaling:  proxy_kpa = (adc_count / FSR_ADC_MAX) * FSR_SCALE_KPA
where FSR_SCALE_KPA = 600.0 is a plausible plantar pressure range.
This is a RELATIVE proxy only. Do not interpret as absolute clinical kPa.
"""

from __future__ import annotations

import time
import numpy as np
import pandas as pd
from typing import Optional

from hardware.sensor_schema import SensorPacket, FSR_ADC_MAX

# ── Scaling constants ─────────────────────────────────────────────────────────
# Typical peak plantar pressure range: 100–800 kPa
# We map FSR ADC full-scale (4095) → 600 kPa as a plausible midpoint.
# Change this if you perform a bench calibration against known loads.
FSR_SCALE_KPA = 600.0

# PTI: we treat each 50 ms sample as one "frame" at 20 Hz
# PTI_proxy = sum(press_kpa_per_sample) * FRAME_DURATION_S
FRAME_DURATION_S = 1.0 / 20.0   # 0.05 s

# Persistence threshold: fraction of max PTI proxy considered "elevated"
PTI_PERSISTENCE_THRESHOLD_FRACTION = 0.3

# Step detection: minimum load to count as "weight bearing"
MIN_LOAD_FRACTION = 0.05   # at least 5% of FSR_SCALE_KPA

# Columns that are unavailable on a single insole
NOT_AVAILABLE_BILATERAL = [
    "asym_pti_total_kpa_s",
    "asym_press_mean_kpa",
    "gait_symmetry_index",
    "asym_load_forefoot",
    "asym_dir_pti_total_kpa_s",
]


class HardwareAdapter:
    """
    Converts a list of recent SensorPackets into a pd.Series that
    compute_risk() accepts.

    Parameters
    ----------
    window_s : float
        How many seconds of history to use for feature calculation.
        Default 5 s = 100 packets at 20 Hz.
    """

    def __init__(self, window_s: float = 5.0):
        self.window_s = window_s

    # ── Main conversion ───────────────────────────────────────────────────────
    def to_feature_row(self, packets: list[SensorPacket]) -> Optional[pd.Series]:
        """
        Convert recent packets to a feature row for the risk engine.

        Parameters
        ----------
        packets : list[SensorPacket]
            Recent packets, oldest first.  Typically 100 (5 s at 20 Hz).
            Must contain at least 2 packets.

        Returns
        -------
        pd.Series or None if insufficient data.
        """
        if len(packets) < 2:
            return None

        # Trim to window
        if packets[-1].received_at and packets[0].received_at:
            cutoff = packets[-1].received_at - self.window_s
            packets = [p for p in packets if p.received_at and p.received_at >= cutoff]

        if len(packets) < 2:
            return None

        # ── FSR arrays ────────────────────────────────────────────────────────
        # Scale ADC → proxy kPa
        def _fsr_kpa(pkt: SensorPacket) -> float:
            """Sum of all 4 FSR channels as proxy kPa."""
            total_adc = pkt.fsr.total()
            return (total_adc / FSR_ADC_MAX) * FSR_SCALE_KPA

        press_kpa_arr   = np.array([_fsr_kpa(p) for p in packets])
        press_max_kpa   = float(press_kpa_arr.max())
        press_mean_kpa  = float(press_kpa_arr.mean())

        # PTI proxy: sum of press_kpa * frame_duration
        pti_total = float(np.sum(press_kpa_arr) * FRAME_DURATION_S)

        # ── Regional fractions (mean over window) ─────────────────────────────
        ff_fracs = np.array([p.fsr.forefoot_fraction() for p in packets])
        rf_fracs = np.array([p.fsr.rearfoot_fraction() for p in packets])
        mf_fracs = np.array([p.fsr.midfoot_fraction()  for p in packets])

        load_frac_forefoot = float(ff_fracs.mean())
        load_frac_rearfoot = float(rf_fracs.mean())
        load_frac_midfoot  = float(mf_fracs.mean())
        load_frac_toe      = max(0.0, 1.0 - load_frac_forefoot
                                           - load_frac_rearfoot
                                           - load_frac_midfoot)

        # ── Step timing proxy (gait variability) ──────────────────────────────
        step_time_std_s = self._estimate_step_time_std(packets, press_kpa_arr)

        # ── Persistence (fraction of packets above PTI threshold) ─────────────
        pti_threshold = FSR_SCALE_KPA * PTI_PERSISTENCE_THRESHOLD_FRACTION
        n_elevated    = int(np.sum(press_kpa_arr > pti_threshold))
        persistence   = n_elevated / len(press_kpa_arr)

        # ── Temperature ───────────────────────────────────────────────────────
        temps = [p.temp for p in packets if p.temp is not None]
        temp_c = float(np.mean(temps)) if temps else None

        # ── IMU derived ───────────────────────────────────────────────────────
        imu_pkts = [p for p in packets if p.imu is not None]
        if imu_pkts:
            accel_mags = np.array([p.imu.accel_magnitude() for p in imu_pkts])
            gyro_mags  = np.array([p.imu.gyro_magnitude()  for p in imu_pkts])
            accel_mag  = float(accel_mags.mean())
            gyro_mag   = float(gyro_mags.mean())
            # CoP path proxy: scale accel variance to cm range
            cop_proxy  = float(np.std(accel_mags) * 20.0)
        else:
            accel_mag = 0.0
            gyro_mag  = 0.0
            cop_proxy = 0.0

        # ── Stance time proxy ─────────────────────────────────────────────────
        stance_time_s = self._estimate_stance_time(press_kpa_arr, FRAME_DURATION_S)

        # ── Cadence proxy ─────────────────────────────────────────────────────
        cadence = self._estimate_cadence(press_kpa_arr, FRAME_DURATION_S)

        # ── Build feature row ─────────────────────────────────────────────────
        row = pd.Series({
            # ── Used by risk engine ──────────────────────────────────────────
            "press_max_kpa":                press_max_kpa,
            "press_mean_kpa":               press_mean_kpa,
            "pti_total_kpa_s":              pti_total,
            "load_frac_forefoot":           load_frac_forefoot,
            "load_frac_rearfoot":           load_frac_rearfoot,
            "load_frac_midfoot":            load_frac_midfoot,
            "load_frac_toe":                load_frac_toe,
            "step_time_std_s":              step_time_std_s,
            "persistence_pti_total_kpa_s":  persistence,

            # ── Bilateral — NOT AVAILABLE on single insole ───────────────────
            "asym_pti_total_kpa_s":         0.0,   # NOT_AVAILABLE
            "asym_press_mean_kpa":          0.0,   # NOT_AVAILABLE
            "gait_symmetry_index":          0.0,   # NOT_AVAILABLE
            "asym_load_forefoot":           0.0,   # NOT_AVAILABLE
            "asym_dir_pti_total_kpa_s":     0.0,   # NOT_AVAILABLE
            "left_loading_fraction":        1.0,   # single insole = reference
            "right_loading_fraction":       0.0,

            # ── Extra columns for display ────────────────────────────────────
            "cop_path_length_cm":           cop_proxy,
            "stance_time_s":                stance_time_s,
            "cadence_steps_per_min":        cadence,
            "temperature_c":                temp_c if temp_c is not None else 0.0,
            "accel_magnitude_g":            accel_mag,
            "gyro_magnitude_deg_s":         gyro_mag,

            # ── Metadata ─────────────────────────────────────────────────────
            "subject_id":   "HARDWARE",
            "footwear":     "LIVE",
            "trial":        "LIVE",
            "footstep_id":  int(time.time()),
            "side":         "Left",   # single insole — user-configurable
        })

        return row

    # ── Gait estimation helpers ───────────────────────────────────────────────

    @staticmethod
    def _estimate_step_time_std(packets: list[SensorPacket],
                                press_arr: np.ndarray) -> float:
        """
        Estimate step time variability from load onset events.
        Each time press crosses MIN_LOAD_FRACTION * FSR_SCALE_KPA upward
        is counted as a "step onset".  Returns std of inter-onset intervals.
        Falls back to 0.0 if fewer than 3 onsets detected.
        """
        threshold = MIN_LOAD_FRACTION * FSR_SCALE_KPA
        onsets = []
        in_stance = press_arr[0] > threshold

        for i in range(1, len(press_arr)):
            was_swing  = not in_stance
            now_stance = press_arr[i] > threshold
            if was_swing and now_stance:
                # Use received_at if available, else index * frame_duration
                if packets[i].received_at and packets[0].received_at:
                    onsets.append(packets[i].received_at - packets[0].received_at)
                else:
                    onsets.append(i * FRAME_DURATION_S)
            in_stance = now_stance

        if len(onsets) < 3:
            return 0.0

        intervals = np.diff(onsets)
        return float(np.std(intervals))

    @staticmethod
    def _estimate_stance_time(press_arr: np.ndarray,
                              frame_dur: float) -> float:
        """
        Estimate mean stance duration from contiguous weight-bearing segments.
        """
        threshold   = MIN_LOAD_FRACTION * FSR_SCALE_KPA
        in_stance   = False
        stance_start = 0
        durations   = []

        for i, p in enumerate(press_arr):
            if not in_stance and p > threshold:
                in_stance    = True
                stance_start = i
            elif in_stance and p <= threshold:
                durations.append((i - stance_start) * frame_dur)
                in_stance = False

        if in_stance:
            durations.append((len(press_arr) - stance_start) * frame_dur)

        return float(np.mean(durations)) if durations else 0.7

    @staticmethod
    def _estimate_cadence(press_arr: np.ndarray,
                          frame_dur: float) -> float:
        """
        Estimate cadence (steps/min) from step onset count over window duration.
        """
        threshold  = MIN_LOAD_FRACTION * FSR_SCALE_KPA
        in_stance  = press_arr[0] > threshold
        step_count = 0

        for i in range(1, len(press_arr)):
            now_stance = press_arr[i] > threshold
            if not in_stance and now_stance:
                step_count += 1
            in_stance = now_stance

        window_s = len(press_arr) * frame_dur
        return (step_count / window_s * 60.0) if window_s > 0 else 0.0

    # ── Convenience: feature row from receiver ────────────────────────────────
    def from_receiver(self, receiver) -> Optional[pd.Series]:
        """
        Pull recent packets from a SoleSenseReceiver and return a feature row.
        Pass the receiver object from esp32_receiver.get_receiver().
        """
        n_packets = int(self.window_s * 20)   # 20 Hz
        packets   = receiver.recent_packets(n=n_packets)
        return self.to_feature_row(packets)


# ── Not-available documentation ───────────────────────────────────────────────
NOT_AVAILABLE_DOCS = {
    "asym_pti_total_kpa_s": (
        "Left/right loading asymmetry — requires TWO insoles. "
        "Set to 0.0 for single-insole prototype."
    ),
    "asym_press_mean_kpa": (
        "Left/right pressure asymmetry — requires TWO insoles. "
        "Set to 0.0 for single-insole prototype."
    ),
    "gait_symmetry_index": (
        "Bilateral gait symmetry — requires TWO insoles. "
        "Set to 0.0 for single-insole prototype."
    ),
    "asym_load_forefoot": (
        "Persistent bilateral forefoot asymmetry — requires TWO insoles. "
        "Set to 0.0 for single-insole prototype."
    ),
}
