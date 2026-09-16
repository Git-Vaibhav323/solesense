"""
SoleSense Gait Features
========================
Derives temporal gait metrics from sequential footstep timing.

Available in this dataset:
    StartFrame / EndFrame at 100 Hz  →  stance duration per step
    Step sequence (alternating Left/Right)  →  step time, stride time, cadence

NOT available (documented as future hardware features):
    - Swing phase (requires continuous wearable IMU or bilateral insole)
    - Double support time (same limitation)
    - Walking speed (not captured per-step in this dataset)
    - Step length (no per-step spatial position)

All features are computed per TRIAL (one walking condition) and returned
as a flat dict that can be merged into the feature table.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.config import SAMPLING_RATE_HZ


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_std(values: np.ndarray) -> float:
    return float(np.std(values)) if len(values) > 1 else 0.0

def _safe_cv(values: np.ndarray) -> float:
    """Coefficient of variation (std / mean), returns 0 if mean == 0."""
    m = float(np.mean(values))
    return float(np.std(values)) / m if m > 0 else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Per-trial gait feature extraction
# ─────────────────────────────────────────────────────────────────────────────

def compute_gait_features(trial_df: pd.DataFrame) -> Dict[str, float]:
    """
    Compute gait timing features from one trial's preprocessed footsteps.

    Parameters
    ----------
    trial_df : DataFrame for a single subject × footwear × trial,
               sorted by start_frame, containing columns:
               side, start_frame, end_frame, stance_time_s

    Returns
    -------
    Flat dict with gait features (see Feature Dictionary).
    """
    if trial_df.empty or len(trial_df) < 2:
        return _empty_gait_features()

    df = trial_df.sort_values("start_frame").reset_index(drop=True)

    # ── stance time ──────────────────────────────────────────────────────────
    stance_all = df["stance_time_s"].values
    feats: Dict[str, float] = {
        "stance_mean_s":   float(np.mean(stance_all)),
        "stance_std_s":    _safe_std(stance_all),
        "stance_cv":       _safe_cv(stance_all),
        "stance_min_s":    float(np.min(stance_all)),
        "stance_max_s":    float(np.max(stance_all)),
        "n_steps_total":   float(len(df)),
    }

    # ── step time (time between consecutive steps, any side) ─────────────────
    # Step time = time from heel-strike of step N to heel-strike of step N+1
    step_times = np.diff(df["start_frame"].values) / SAMPLING_RATE_HZ
    valid_step = step_times[(step_times > 0.2) & (step_times < 3.0)]
    if len(valid_step) >= 1:
        feats["step_time_mean_s"]  = float(np.mean(valid_step))
        feats["step_time_std_s"]   = _safe_std(valid_step)
        feats["step_time_cv"]      = _safe_cv(valid_step)
    else:
        feats.update({"step_time_mean_s": 0.0, "step_time_std_s": 0.0, "step_time_cv": 0.0})

    # ── cadence (steps per minute) ────────────────────────────────────────────
    if feats["step_time_mean_s"] > 0:
        feats["cadence_steps_per_min"] = 60.0 / feats["step_time_mean_s"]
    else:
        feats["cadence_steps_per_min"] = 0.0

    # ── stride time (same-side step interval) ────────────────────────────────
    left_starts  = df[df["side"] == "Left"]["start_frame"].values
    right_starts = df[df["side"] == "Right"]["start_frame"].values

    for side_label, starts in [("left", left_starts), ("right", right_starts)]:
        if len(starts) >= 2:
            stride_times = np.diff(np.sort(starts)) / SAMPLING_RATE_HZ
            valid_stride = stride_times[(stride_times > 0.5) & (stride_times < 5.0)]
            if len(valid_stride) >= 1:
                feats[f"stride_time_{side_label}_mean_s"] = float(np.mean(valid_stride))
                feats[f"stride_time_{side_label}_std_s"]  = _safe_std(valid_stride)
                feats[f"stride_time_{side_label}_cv"]     = _safe_cv(valid_stride)
            else:
                feats[f"stride_time_{side_label}_mean_s"] = 0.0
                feats[f"stride_time_{side_label}_std_s"]  = 0.0
                feats[f"stride_time_{side_label}_cv"]     = 0.0
        else:
            feats[f"stride_time_{side_label}_mean_s"] = 0.0
            feats[f"stride_time_{side_label}_std_s"]  = 0.0
            feats[f"stride_time_{side_label}_cv"]     = 0.0

    # ── step count per side ───────────────────────────────────────────────────
    feats["n_steps_left"]  = float(len(left_starts))
    feats["n_steps_right"] = float(len(right_starts))

    # ── stance fraction (stance / stride time) ───────────────────────────────
    # Estimated from mean stance divided by mean stride time
    for side_label in ["left", "right"]:
        key = f"stride_time_{side_label}_mean_s"
        if feats.get(key, 0) > 0:
            stance_side = df[df["side"].str.lower() == side_label]["stance_time_s"].mean()
            feats[f"stance_fraction_{side_label}"] = stance_side / feats[key]
        else:
            feats[f"stance_fraction_{side_label}"] = 0.0

    # ── gait symmetry index ───────────────────────────────────────────────────
    # Uses stride time ratio: |left_stride - right_stride| / mean_stride
    lt = feats.get("stride_time_left_mean_s", 0.0)
    rt = feats.get("stride_time_right_mean_s", 0.0)
    if lt > 0 and rt > 0:
        feats["gait_symmetry_index"] = abs(lt - rt) / ((lt + rt) / 2.0)
    else:
        feats["gait_symmetry_index"] = 0.0

    # ── temporal variability (overall gait regularity) ───────────────────────
    # Higher step_time_cv = more irregular gait
    feats["gait_temporal_variability"] = feats["step_time_cv"]

    return feats


def _empty_gait_features() -> Dict[str, float]:
    """Return a dict of NaN gait features for trials with insufficient steps."""
    keys = [
        "stance_mean_s", "stance_std_s", "stance_cv", "stance_min_s", "stance_max_s",
        "n_steps_total", "step_time_mean_s", "step_time_std_s", "step_time_cv",
        "cadence_steps_per_min",
        "stride_time_left_mean_s", "stride_time_left_std_s", "stride_time_left_cv",
        "stride_time_right_mean_s", "stride_time_right_std_s", "stride_time_right_cv",
        "n_steps_left", "n_steps_right",
        "stance_fraction_left", "stance_fraction_right",
        "gait_symmetry_index", "gait_temporal_variability",
    ]
    return {k: float("nan") for k in keys}


# ─────────────────────────────────────────────────────────────────────────────
# Batch extractor
# ─────────────────────────────────────────────────────────────────────────────

def extract_gait_features_batch(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-trial gait features for all subject × footwear × trial groups.

    Returns a DataFrame with one row per (subject_id, footwear, trial).
    """
    group_keys = ["subject_id", "footwear", "trial"]
    records = []

    for keys, group in df.groupby(group_keys):
        feats = compute_gait_features(group)
        row = dict(zip(group_keys, keys))
        row.update(feats)
        records.append(row)

    return pd.DataFrame(records)
