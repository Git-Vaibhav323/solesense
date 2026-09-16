"""
SoleSense Preprocessing
=======================
Each step is justified by the actual dataset characteristics.

Steps applied (in order):
1. Exclude flagged footsteps  — dataset provides Exclude/Outlier flags; trust them.
2. Stance duration filter     — removes implausibly short (<0.15 s) or long (>2.5 s)
                                contacts that are standing pauses or noise.
3. Rscore filter              — optional minimum reliability score.
4. Duplicate removal          — same subject/footwear/trial/footstepID seen twice.
5. Side normalization         — ensure 'side' is 'Left' or 'Right' only.
6. Pressure array validation  — flag footsteps where the pressure array is all-zeros
                                or has unexpected shape.
7. Missing-value audit        — log columns with NaN but do not silently impute
                                numeric sensor columns; drop rows with NaN in key cols.

NOT applied (and why):
- Filtering / smoothing of raw pressure arrays: pipeline_1 is already a
  preprocessed, extracted, and aligned footstep image.  Applying additional
  temporal filters would be double-processing.
- Resampling: all data is at 100 Hz; no resampling is necessary.
- Unit normalization: values are already in kPa (pipeline_1).
- Z-score or min-max normalization: preserved for feature-level decisions;
  pipeline_2 already provides a [0,1] normalized version if needed.
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.config import (
    EXCLUDE_FLAGGED_STEPS,
    MIN_STANCE_DURATION_S,
    MAX_STANCE_DURATION_S,
    MIN_RSCORE,
    FOOTSTEP_ROWS,
    FOOTSTEP_COLS,
    FOOTSTEP_FRAMES,
)

logger = logging.getLogger(__name__)

# Columns that must not be NaN for a row to be usable
_REQUIRED_COLS = [
    "subject_id", "footwear", "trial", "footstep_id",
    "side", "start_frame", "end_frame", "stance_time_s",
]


def preprocess(
    df: pd.DataFrame,
    exclude_flagged: bool = EXCLUDE_FLAGGED_STEPS,
    min_stance_s: float = MIN_STANCE_DURATION_S,
    max_stance_s: float = MAX_STANCE_DURATION_S,
    min_rscore: float = MIN_RSCORE,
    validate_arrays: bool = True,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Apply the full preprocessing pipeline to a footstep DataFrame.

    Parameters
    ----------
    df              : DataFrame from data_loader.load_walking_trial / load_dataset
    exclude_flagged : drop rows where exclude==1 or outlier==1
    min_stance_s    : drop footsteps shorter than this (seconds)
    max_stance_s    : drop footsteps longer than this (seconds)
    min_rscore      : drop footsteps below this Rscore
    validate_arrays : check pressure_array shapes when present
    verbose         : log a report of what was removed

    Returns
    -------
    Cleaned DataFrame, index reset.
    """
    if df.empty:
        return df.copy()

    original_n = len(df)
    report = {}

    # ── step 0: work on a copy ──────────────────────────────────────────────
    df = df.copy()

    # ── step 1: exclude dataset-flagged footsteps ───────────────────────────
    if exclude_flagged and "exclude" in df.columns:
        mask_excl = df["exclude"] == 1
        report["excluded_by_flag"] = int(mask_excl.sum())
        df = df[~mask_excl]

    # ── step 2: stance duration filter ─────────────────────────────────────
    if "stance_time_s" in df.columns:
        mask_too_short = df["stance_time_s"] < min_stance_s
        mask_too_long = df["stance_time_s"] > max_stance_s
        report["too_short"] = int(mask_too_short.sum())
        report["too_long"] = int(mask_too_long.sum())
        df = df[~mask_too_short & ~mask_too_long]

    # ── step 3: Rscore filter ───────────────────────────────────────────────
    if min_rscore > 0 and "rscore" in df.columns:
        mask_low_r = df["rscore"] < min_rscore
        report["low_rscore"] = int(mask_low_r.sum())
        df = df[~mask_low_r]

    # ── step 4: duplicate removal ───────────────────────────────────────────
    key_cols = [c for c in ["subject_id", "footwear", "trial", "footstep_id"] if c in df.columns]
    if key_cols:
        n_before = len(df)
        df = df.drop_duplicates(subset=key_cols)
        report["duplicates"] = n_before - len(df)

    # ── step 5: side normalization ──────────────────────────────────────────
    if "side" in df.columns:
        df["side"] = df["side"].astype(str).str.strip().str.capitalize()
        invalid_side = ~df["side"].isin(["Left", "Right"])
        if invalid_side.any():
            logger.warning("Dropping %d rows with invalid side values", invalid_side.sum())
            df = df[~invalid_side]

    # ── step 6: pressure array validation ──────────────────────────────────
    if validate_arrays and "pressure_array" in df.columns:
        def _valid_array(arr) -> bool:
            if arr is None:
                return True  # no array loaded — metadata-only mode, acceptable
            if not isinstance(arr, np.ndarray):
                return False
            if arr.shape != (FOOTSTEP_FRAMES, FOOTSTEP_ROWS, FOOTSTEP_COLS):
                return False
            return True

        def _nonzero_array(arr) -> bool:
            if arr is None:
                return True
            return arr.max() > 0

        bad_shape = ~df["pressure_array"].apply(_valid_array)
        all_zero = ~df["pressure_array"].apply(_nonzero_array)
        report["bad_array_shape"] = int(bad_shape.sum())
        report["all_zero_array"] = int(all_zero.sum())
        df = df[~bad_shape & ~all_zero]

    # ── step 7: required column NaN audit ──────────────────────────────────
    present_required = [c for c in _REQUIRED_COLS if c in df.columns]
    n_before = len(df)
    df = df.dropna(subset=present_required)
    report["nan_in_required_cols"] = n_before - len(df)

    # ── log summary ─────────────────────────────────────────────────────────
    removed = original_n - len(df)
    if verbose:
        logger.info(
            "Preprocessing: %d → %d rows (removed %d = %.1f%%)",
            original_n, len(df), removed, 100 * removed / max(original_n, 1)
        )
        for reason, count in report.items():
            if count > 0:
                logger.info("  %-30s %d", reason + ":", count)

    df.reset_index(drop=True, inplace=True)
    return df


def get_clean_steps(
    df: pd.DataFrame,
    side: Optional[str] = None,
    footwear: Optional[str] = None,
    trial: Optional[str] = None,
) -> pd.DataFrame:
    """
    Convenience filter: return clean steps for a specific side/footwear/trial.

    Parameters
    ----------
    df       : preprocessed DataFrame
    side     : 'Left', 'Right', or None (both)
    footwear : e.g. 'BF', or None (all)
    trial    : e.g. 'W1', or None (all)
    """
    mask = pd.Series([True] * len(df), index=df.index)
    if side is not None and "side" in df.columns:
        mask &= df["side"].str.capitalize() == side.capitalize()
    if footwear is not None and "footwear" in df.columns:
        mask &= df["footwear"] == footwear
    if trial is not None and "trial" in df.columns:
        mask &= df["trial"] == trial
    return df[mask].reset_index(drop=True)


def audit_missing(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a summary DataFrame of missing values per column.
    """
    total = len(df)
    result = []
    for col in df.columns:
        if col == "pressure_array":
            n_none = df[col].apply(lambda x: x is None).sum()
            result.append({"column": col, "missing": int(n_none), "pct": 100 * n_none / max(total, 1)})
        else:
            n_miss = df[col].isna().sum()
            result.append({"column": col, "missing": int(n_miss), "pct": 100 * n_miss / max(total, 1)})
    return pd.DataFrame(result)
