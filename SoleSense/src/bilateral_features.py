"""
SoleSense Bilateral Features
=============================
Computes left ↔ right comparison features from matched pressure and gait data.

This is a key SoleSense concept: persistent asymmetry between the two feet
is more clinically meaningful than absolute loading values alone.

Asymmetry formula (Normalized Symmetry Index, NSI):
    asymmetry = |L - R| / ((L + R) / 2)  × 100 %

    where L and R are the mean values for each side across the trial.
    Division-by-zero is handled by returning 0.0 when (L + R) = 0.

Features computed:
    - Mean pressure asymmetry
    - PTI (pressure-time integral) asymmetry
    - Regional loading asymmetry (4 regions)
    - Peak pressure asymmetry
    - Contact area asymmetry
    - Stance time asymmetry
    - Stride time asymmetry
    - CoP path length asymmetry

All features are per (subject_id, footwear, trial) — i.e., one row per trial.
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.config import REGIONS


# ─────────────────────────────────────────────────────────────────────────────
# Core asymmetry formula
# ─────────────────────────────────────────────────────────────────────────────

def normalized_symmetry_index(left: float, right: float) -> float:
    """
    Normalized Symmetry Index (NSI) as a percentage.

    Returns the absolute difference normalized by the mean of both sides.
    Returns 0.0 when both sides are 0.

    Formula: |L - R| / ((L + R) / 2) × 100
    """
    denom = (left + right) / 2.0
    if denom == 0:
        return 0.0
    return abs(left - right) / denom * 100.0


def directional_asymmetry(left: float, right: float) -> float:
    """
    Signed asymmetry: positive = left > right, negative = right > left.
    Normalized by mean of both sides, expressed as percentage.
    """
    denom = (left + right) / 2.0
    if denom == 0:
        return 0.0
    return (left - right) / denom * 100.0


# ─────────────────────────────────────────────────────────────────────────────
# Per-trial bilateral features from pressure feature table
# ─────────────────────────────────────────────────────────────────────────────

def compute_bilateral_pressure_features(
    trial_pressure_df: pd.DataFrame,
) -> Dict[str, float]:
    """
    Compute bilateral pressure asymmetry for one trial.

    Parameters
    ----------
    trial_pressure_df : DataFrame of pressure features (output of
                        pressure_features.extract_pressure_features_batch),
                        filtered to a single subject × footwear × trial.
                        Must contain a 'side' column with 'Left' / 'Right'.

    Returns
    -------
    Flat dict with bilateral features.
    """
    feats: Dict[str, float] = {}

    left  = trial_pressure_df[trial_pressure_df["side"] == "Left"]
    right = trial_pressure_df[trial_pressure_df["side"] == "Right"]

    if left.empty or right.empty:
        return _empty_bilateral_features()

    # ── helper: mean of a column per side ───────────────────────────────────
    def L(col: str) -> float:
        return float(left[col].mean()) if col in left.columns else 0.0

    def R(col: str) -> float:
        return float(right[col].mean()) if col in right.columns else 0.0

    # ── pressure statistics asymmetry ────────────────────────────────────────
    for feat in ["press_mean_kpa", "press_max_kpa", "pti_total_kpa_s",
                 "pti_per_cm2_kpa_s", "contact_area_cm2", "peak_total_force_kpa"]:
        l_val, r_val = L(feat), R(feat)
        feats[f"asym_{feat}"]         = normalized_symmetry_index(l_val, r_val)
        feats[f"asym_dir_{feat}"]     = directional_asymmetry(l_val, r_val)
        feats[f"left_mean_{feat}"]    = l_val
        feats[f"right_mean_{feat}"]   = r_val

    # ── regional loading asymmetry ───────────────────────────────────────────
    for region in REGIONS.keys():
        col = f"load_frac_{region.lower()}"
        l_val, r_val = L(col), R(col)
        feats[f"asym_load_{region.lower()}"]     = normalized_symmetry_index(l_val, r_val)
        feats[f"asym_load_dir_{region.lower()}"] = directional_asymmetry(l_val, r_val)

    # ── CoP asymmetry ─────────────────────────────────────────────────────────
    for feat in ["cop_path_length_cm", "cop_ap_range_cm", "cop_ml_range_cm"]:
        l_val, r_val = L(feat), R(feat)
        feats[f"asym_{feat}"] = normalized_symmetry_index(l_val, r_val)

    # ── stance time asymmetry ─────────────────────────────────────────────────
    l_stance = float(left["stance_time_s"].mean()) if "stance_time_s" in left.columns else 0.0
    r_stance = float(right["stance_time_s"].mean()) if "stance_time_s" in right.columns else 0.0
    feats["asym_stance_time"]     = normalized_symmetry_index(l_stance, r_stance)
    feats["asym_dir_stance_time"] = directional_asymmetry(l_stance, r_stance)
    feats["left_mean_stance_s"]   = l_stance
    feats["right_mean_stance_s"]  = r_stance

    # ── overall bilateral loading ratio ──────────────────────────────────────
    total_l = L("pti_total_kpa_s")
    total_r = R("pti_total_kpa_s")
    total   = total_l + total_r
    feats["left_loading_fraction"]  = total_l / total if total > 0 else 0.5
    feats["right_loading_fraction"] = total_r / total if total > 0 else 0.5

    # ── step count balance ────────────────────────────────────────────────────
    feats["n_steps_left"]  = float(len(left))
    feats["n_steps_right"] = float(len(right))

    return feats


def _empty_bilateral_features() -> Dict[str, float]:
    """Return NaN dict when one side is missing."""
    return {
        "asym_press_mean_kpa": float("nan"),
        "asym_press_max_kpa": float("nan"),
        "asym_pti_total_kpa_s": float("nan"),
        "asym_stance_time": float("nan"),
        "left_loading_fraction": float("nan"),
        "right_loading_fraction": float("nan"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Batch extractor
# ─────────────────────────────────────────────────────────────────────────────

def extract_bilateral_features_batch(
    pressure_feat_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Apply bilateral feature extraction to all (subject, footwear, trial) groups.

    Parameters
    ----------
    pressure_feat_df : output of pressure_features.extract_pressure_features_batch

    Returns
    -------
    DataFrame with one row per (subject_id, footwear, trial).
    """
    group_keys = ["subject_id", "footwear", "trial"]
    records = []

    for keys, group in pressure_feat_df.groupby(group_keys):
        feats = compute_bilateral_pressure_features(group)
        row = dict(zip(group_keys, keys))
        row.update(feats)
        records.append(row)

    return pd.DataFrame(records)
