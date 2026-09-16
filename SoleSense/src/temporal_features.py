"""
SoleSense Temporal / Persistence Features
==========================================
Distinguishes a single abnormal event from persistent abnormal behaviour.

The goal is NOT to detect an isolated spike but to capture whether
elevated loading or asymmetry persists across consecutive steps.

All features operate on the per-footstep feature table (one row per step)
and produce rolling/window statistics.  The output adds new columns to the
same table (in-place on a copy).

Features computed:
    rolling_mean_<feat>      – rolling mean over last N steps (per side)
    rolling_max_<feat>       – rolling max over last N steps
    rolling_std_<feat>       – rolling std over last N steps
    above_thresh_count_<feat>– number of steps in window above threshold
    persistence_score_<feat> – fraction of window steps above threshold [0–1]

Key features tracked for persistence:
    press_max_kpa            – peak pressure per step
    pti_total_kpa_s          – pressure-time integral
    load_frac_forefoot       – forefoot loading fraction
    load_frac_rearfoot       – rearfoot loading fraction
"""

import numpy as np
import pandas as pd
from typing import Optional, List, Dict

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.config import (
    ROLLING_WINDOW_STEPS,
    RISK_PRESSURE_HIGH_KPA,
    RISK_PRESSURE_EXPOSURE_HIGH,
    RISK_ASYMMETRY_HIGH_PCT,
)

# Features to compute rolling stats on (must exist in the pressure feature table)
TRACKED_FEATURES = [
    "press_max_kpa",
    "pti_total_kpa_s",
    "load_frac_forefoot",
    "load_frac_rearfoot",
    "cop_path_length_cm",
]

# Thresholds for persistence scoring (EXPERIMENTAL)
PERSISTENCE_THRESHOLDS = {
    "press_max_kpa":      RISK_PRESSURE_HIGH_KPA,
    "pti_total_kpa_s":    RISK_PRESSURE_EXPOSURE_HIGH,
    "load_frac_forefoot": 0.50,   # >50% load in forefoot = elevated
    "load_frac_rearfoot": 0.55,   # >55% load in rearfoot = heel-heavy
    "cop_path_length_cm": 15.0,   # >15 cm CoP path = elevated excursion
}


def add_temporal_features(
    df: pd.DataFrame,
    window: int = ROLLING_WINDOW_STEPS,
    group_by_side: bool = True,
) -> pd.DataFrame:
    """
    Add rolling temporal features to a per-footstep feature DataFrame.

    Parameters
    ----------
    df            : per-footstep DataFrame with pressure features already computed
                    (output of pressure_features.extract_pressure_features_batch)
    window        : number of consecutive steps in the rolling window
    group_by_side : if True, rolling stats are computed separately for Left/Right;
                    this is more meaningful since L/R alternate in the sequence

    Returns
    -------
    Copy of df with additional rolling feature columns appended.
    """
    df = df.copy()

    # Sort by subject / footwear / trial / side / footstep_id for correct ordering
    sort_cols = [c for c in ["subject_id", "footwear", "trial", "side", "footstep_id"]
                 if c in df.columns]
    df = df.sort_values(sort_cols).reset_index(drop=True)

    present_features = [f for f in TRACKED_FEATURES if f in df.columns]

    if group_by_side and "side" in df.columns:
        # Apply rolling within each (subject, footwear, trial, side) group
        group_keys = [c for c in ["subject_id", "footwear", "trial", "side"] if c in df.columns]
        new_cols = _rolling_within_groups(df, present_features, group_keys, window)
    else:
        # Apply rolling within each (subject, footwear, trial) group
        group_keys = [c for c in ["subject_id", "footwear", "trial"] if c in df.columns]
        new_cols = _rolling_within_groups(df, present_features, group_keys, window)

    for col_name, col_data in new_cols.items():
        df[col_name] = col_data.values

    return df


def _rolling_within_groups(
    df: pd.DataFrame,
    features: List[str],
    group_keys: List[str],
    window: int,
) -> Dict[str, pd.Series]:
    """Compute rolling stats per group, return dict of new column name → Series."""
    result: Dict[str, pd.Series] = {}
    grouped = df.groupby(group_keys, sort=False)

    for feat in features:
        threshold = PERSISTENCE_THRESHOLDS.get(feat, None)
        series = df[feat].astype(float)

        roll_mean = grouped[feat].transform(
            lambda x: x.rolling(window=window, min_periods=1).mean()
        )
        roll_max = grouped[feat].transform(
            lambda x: x.rolling(window=window, min_periods=1).max()
        )
        roll_std = grouped[feat].transform(
            lambda x: x.rolling(window=window, min_periods=1).std().fillna(0.0)
        )

        result[f"roll_mean_{feat}"] = roll_mean
        result[f"roll_max_{feat}"]  = roll_max
        result[f"roll_std_{feat}"]  = roll_std

        if threshold is not None:
            # Persistence: fraction of window steps above threshold
            above = (series > threshold).astype(float)
            persist = grouped["subject_id"].transform(  # dummy groupby for index alignment
                lambda x: x  # will be overridden
            )
            # Use rolling on the binary 'above' series within groups
            persist = grouped[feat].transform(
                lambda x: (x > threshold).astype(float).rolling(
                    window=window, min_periods=1
                ).mean()
            )
            result[f"persistence_{feat}"] = persist

    return result


def compute_trial_persistence_summary(
    df: pd.DataFrame,
    window: int = ROLLING_WINDOW_STEPS,
) -> pd.DataFrame:
    """
    Summarise persistence features per trial (one row per subject×footwear×trial×side).

    Returns
    -------
    DataFrame with max persistence score for each tracked feature per trial/side.
    """
    # Ensure temporal features are computed
    if "persistence_press_max_kpa" not in df.columns:
        df = add_temporal_features(df, window=window)

    group_keys = [c for c in ["subject_id", "footwear", "trial", "side"] if c in df.columns]
    persistence_cols = [c for c in df.columns if c.startswith("persistence_")]

    if not persistence_cols:
        return pd.DataFrame()

    agg = df.groupby(group_keys)[persistence_cols].max().reset_index()
    return agg
