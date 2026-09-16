"""
SoleSense Pressure Features
============================
Extracts interpretable, physically meaningful features from the normalized
footstep pressure arrays (shape: 101 frames × 75 rows × 40 cols, kPa).

Spatial coordinate convention (from DATASET_SUMMARY.md §6 and §9):
    row 0  = toe direction
    row 74 = heel direction
    col 0  = medial
    col 39 = lateral
    Each pixel = 0.5 cm × 0.5 cm = 0.25 cm²

All per-footstep features are returned as a flat dict (one row in the
final feature table).

Feature groups
--------------
A.  Basic pressure statistics      (mean, max, sd, etc.)
B.  Pressure-time exposure         (integral of pressure × duration)
C.  Regional loading               (toe / forefoot / midfoot / rearfoot fractions)
D.  Peak pressure location         (row/col of maximum pressure)
E.  Center of Pressure (CoP)       (trajectory, excursion, velocity)
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.config import (
    SAMPLING_RATE_HZ, CM_PER_PX, CM2_PER_PX,
    FOOTSTEP_ROWS, FOOTSTEP_COLS, FOOTSTEP_FRAMES,
    REGIONS,
)

# Pre-build row/col index grids once
_ROWS = np.arange(FOOTSTEP_ROWS, dtype=np.float64)   # shape (75,)
_COLS = np.arange(FOOTSTEP_COLS, dtype=np.float64)   # shape (40,)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _active_frames(arr: np.ndarray) -> np.ndarray:
    """Return frames (axis 0) where at least one pixel is > 0."""
    return arr[arr.sum(axis=(1, 2)) > 0]


def _peak_frame(arr: np.ndarray) -> np.ndarray:
    """Return the frame with the highest total pressure (shape 75×40)."""
    totals = arr.sum(axis=(1, 2))
    return arr[totals.argmax()]


# ─────────────────────────────────────────────────────────────────────────────
# A. Basic pressure statistics
# ─────────────────────────────────────────────────────────────────────────────

def compute_basic_stats(arr: np.ndarray) -> Dict[str, float]:
    """
    Compute summary statistics over all active pixels across all frames.

    Returns
    -------
    dict with keys:
        press_mean_kpa       – mean pressure of active (>0) pixels [kPa]
        press_median_kpa     – median of active pixels [kPa]
        press_max_kpa        – global peak pressure [kPa]
        press_std_kpa        – std of active pixels [kPa]
        press_p25_kpa        – 25th percentile of active pixels [kPa]
        press_p75_kpa        – 75th percentile of active pixels [kPa]
        press_p95_kpa        – 95th percentile of active pixels [kPa]
        contact_area_cm2     – mean contact area per stance frame [cm²]
        active_frame_count   – number of frames with any contact
    """
    active = arr[arr > 0]
    if active.size == 0:
        return {k: 0.0 for k in [
            "press_mean_kpa", "press_median_kpa", "press_max_kpa",
            "press_std_kpa", "press_p25_kpa", "press_p75_kpa", "press_p95_kpa",
            "contact_area_cm2", "active_frame_count",
        ]}

    per_frame_contact = (arr > 0).sum(axis=(1, 2))  # n active pixels per frame
    active_frames_mask = per_frame_contact > 0

    return {
        "press_mean_kpa":     float(np.mean(active)),
        "press_median_kpa":   float(np.median(active)),
        "press_max_kpa":      float(np.max(active)),
        "press_std_kpa":      float(np.std(active)),
        "press_p25_kpa":      float(np.percentile(active, 25)),
        "press_p75_kpa":      float(np.percentile(active, 75)),
        "press_p95_kpa":      float(np.percentile(active, 95)),
        "contact_area_cm2":   float(per_frame_contact[active_frames_mask].mean() * CM2_PER_PX),
        "active_frame_count": int(active_frames_mask.sum()),
    }


# ─────────────────────────────────────────────────────────────────────────────
# B. Pressure-time exposure
# ─────────────────────────────────────────────────────────────────────────────

def compute_pressure_time_exposure(
    arr: np.ndarray,
    stance_time_s: float,
) -> Dict[str, float]:
    """
    Pressure-time exposure captures the cumulative loading burden:
        PTI = Σ (pressure_pixel × dt)  over all pixels and all frames

    This is more clinically meaningful than peak pressure alone because
    repeated moderate loading can be as damaging as a single high peak.

    Returns
    -------
    dict with keys:
        pti_total_kpa_s      – total pressure-time integral [kPa·s]
        pti_per_cm2_kpa_s    – PTI normalised by contact area [kPa·s/cm²]
        mean_total_force_kpa – mean total force per frame (sum of kPa over contact area)
        peak_total_force_kpa – peak total force in any single frame
        loading_rate_kpa_s   – mean loading rate (peak_force / time_to_peak) [kPa/s]
    """
    dt = 1.0 / SAMPLING_RATE_HZ  # 0.01 s per frame

    # PTI: sum of (pressure × dt) over all pixels and frames
    pti_total = float(arr.sum()) * dt  # kPa·s (area factored out — per pixel)

    # Contact area (mean over active frames)
    per_frame_contact_px = (arr > 0).sum(axis=(1, 2))
    active_frames = per_frame_contact_px > 0
    if active_frames.sum() == 0:
        return {k: 0.0 for k in [
            "pti_total_kpa_s", "pti_per_cm2_kpa_s",
            "mean_total_force_kpa", "peak_total_force_kpa", "loading_rate_kpa_s",
        ]}

    mean_contact_px = float(per_frame_contact_px[active_frames].mean())
    mean_contact_cm2 = mean_contact_px * CM2_PER_PX

    pti_per_cm2 = pti_total / mean_contact_cm2 if mean_contact_cm2 > 0 else 0.0

    # Total force per frame (sum of all pixel pressures)
    per_frame_force = arr.sum(axis=(1, 2))
    mean_force = float(per_frame_force[active_frames].mean())
    peak_force = float(per_frame_force.max())

    # Loading rate: rise from first contact to peak force
    first_active = int(np.where(active_frames)[0][0])
    peak_frame_idx = int(per_frame_force.argmax())
    frames_to_peak = max(peak_frame_idx - first_active, 1)
    time_to_peak = frames_to_peak * dt
    loading_rate = peak_force / time_to_peak

    return {
        "pti_total_kpa_s":      pti_total,
        "pti_per_cm2_kpa_s":    pti_per_cm2,
        "mean_total_force_kpa": mean_force,
        "peak_total_force_kpa": peak_force,
        "loading_rate_kpa_s":   loading_rate,
    }


# ─────────────────────────────────────────────────────────────────────────────
# C. Regional loading
# ─────────────────────────────────────────────────────────────────────────────

def compute_regional_loading(arr: np.ndarray) -> Dict[str, float]:
    """
    Divide the footstep image into anatomical regions and compute
    each region's share of total cumulative pressure.

    Regions defined in config.REGIONS:
        TOE      rows  0–14
        FOREFOOT rows 15–34
        MIDFOOT  rows 35–54
        REARFOOT rows 55–74

    Returns
    -------
    dict with keys (for each region R):
        load_frac_{R}    – fraction of total cumulative load in this region
        load_kpa_{R}     – absolute cumulative kPa sum in this region
        peak_kpa_{R}     – peak pixel pressure in this region
    """
    total_load = arr.sum()
    feats: Dict[str, float] = {}

    for region, (r_start, r_end) in REGIONS.items():
        region_arr = arr[:, r_start:r_end + 1, :]
        region_sum = float(region_arr.sum())
        region_peak = float(region_arr.max())
        region_frac = region_sum / total_load if total_load > 0 else 0.0

        feats[f"load_frac_{region.lower()}"]  = region_frac
        feats[f"load_kpa_{region.lower()}"]   = region_sum
        feats[f"peak_kpa_{region.lower()}"]   = region_peak

    return feats


# ─────────────────────────────────────────────────────────────────────────────
# D. Peak pressure location
# ─────────────────────────────────────────────────────────────────────────────

def compute_peak_location(arr: np.ndarray) -> Dict[str, float]:
    """
    Find where the global peak pressure occurs.

    Returns
    -------
    dict with keys:
        peak_row_px      – row index of global peak (0=toe, 74=heel)
        peak_col_px      – col index of global peak
        peak_row_cm      – peak row in cm from toe
        peak_col_cm      – peak col in cm from medial edge
        peak_frame_idx   – frame index when peak occurs
    """
    if arr.max() == 0:
        return {k: 0.0 for k in [
            "peak_row_px", "peak_col_px", "peak_row_cm", "peak_col_cm", "peak_frame_idx"
        ]}

    frame_idx, row_idx, col_idx = np.unravel_index(arr.argmax(), arr.shape)
    return {
        "peak_row_px":    float(row_idx),
        "peak_col_px":    float(col_idx),
        "peak_row_cm":    float(row_idx) * CM_PER_PX,
        "peak_col_cm":    float(col_idx) * CM_PER_PX,
        "peak_frame_idx": float(frame_idx),
    }


# ─────────────────────────────────────────────────────────────────────────────
# E. Center of Pressure
# ─────────────────────────────────────────────────────────────────────────────

def compute_cop(arr: np.ndarray) -> Dict[str, float]:
    """
    Compute Center of Pressure trajectory over the stance phase.

    CoP per frame:
        CoP_row = Σ (pressure_ij × row_i) / Σ pressure_ij
        CoP_col = Σ (pressure_ij × col_j) / Σ pressure_ij

    Returns
    -------
    dict with keys:
        cop_start_row_cm        – CoP row at first active frame [cm from toe]
        cop_start_col_cm        – CoP col at first active frame [cm from medial]
        cop_end_row_cm          – CoP row at last active frame
        cop_end_col_cm          – CoP col at last active frame
        cop_excursion_row_cm    – total CoP displacement in row direction [cm]
        cop_excursion_col_cm    – total CoP displacement in col direction [cm]
        cop_path_length_cm      – total path length of CoP trajectory [cm]
        cop_mean_velocity_cm_s  – mean CoP velocity [cm/s]
        cop_ap_range_cm         – anterior-posterior range (row) [cm]
        cop_ml_range_cm         – medial-lateral range (col) [cm]
    """
    dt = 1.0 / SAMPLING_RATE_HZ
    per_frame_total = arr.sum(axis=(1, 2))
    active_mask = per_frame_total > 0

    if active_mask.sum() < 2:
        return {k: 0.0 for k in [
            "cop_start_row_cm", "cop_start_col_cm",
            "cop_end_row_cm", "cop_end_col_cm",
            "cop_excursion_row_cm", "cop_excursion_col_cm",
            "cop_path_length_cm", "cop_mean_velocity_cm_s",
            "cop_ap_range_cm", "cop_ml_range_cm",
        ]}

    # CoP per frame
    active_arr = arr[active_mask]                          # shape (n_active, 75, 40)
    active_tot = per_frame_total[active_mask]              # shape (n_active,)

    cop_row = (active_arr * _ROWS[:, None]).sum(axis=(1, 2)) / active_tot  # (n_active,)
    cop_col = (active_arr * _COLS[None, :]).sum(axis=(1, 2)) / active_tot  # (n_active,)

    # Convert to cm
    cop_row_cm = cop_row * CM_PER_PX
    cop_col_cm = cop_col * CM_PER_PX

    # Path length
    d_row = np.diff(cop_row_cm)
    d_col = np.diff(cop_col_cm)
    path_length = float(np.sqrt(d_row ** 2 + d_col ** 2).sum())

    n_active = active_mask.sum()
    stance_duration = n_active * dt

    return {
        "cop_start_row_cm":       float(cop_row_cm[0]),
        "cop_start_col_cm":       float(cop_col_cm[0]),
        "cop_end_row_cm":         float(cop_row_cm[-1]),
        "cop_end_col_cm":         float(cop_col_cm[-1]),
        "cop_excursion_row_cm":   float(cop_row_cm[-1] - cop_row_cm[0]),
        "cop_excursion_col_cm":   float(cop_col_cm[-1] - cop_col_cm[0]),
        "cop_path_length_cm":     path_length,
        "cop_mean_velocity_cm_s": path_length / stance_duration if stance_duration > 0 else 0.0,
        "cop_ap_range_cm":        float(cop_row_cm.max() - cop_row_cm.min()),
        "cop_ml_range_cm":        float(cop_col_cm.max() - cop_col_cm.min()),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Master extractor
# ─────────────────────────────────────────────────────────────────────────────

def extract_pressure_features(
    arr: np.ndarray,
    stance_time_s: float,
) -> Dict[str, float]:
    """
    Run all pressure feature extractors on one footstep array.

    Parameters
    ----------
    arr          : np.ndarray shape (101, 75, 40) — kPa per pixel per frame
    stance_time_s: float — measured stance duration in seconds

    Returns
    -------
    Flat dict of all pressure features.
    """
    feats: Dict[str, float] = {}
    feats.update(compute_basic_stats(arr))
    feats.update(compute_pressure_time_exposure(arr, stance_time_s))
    feats.update(compute_regional_loading(arr))
    feats.update(compute_peak_location(arr))
    feats.update(compute_cop(arr))
    return feats


def extract_pressure_features_batch(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply extract_pressure_features to every row in a preprocessed DataFrame
    that has a non-None 'pressure_array' column.

    Returns a new DataFrame with one row per footstep and all pressure features.
    """
    records = []
    for _, row in df.iterrows():
        arr = row.get("pressure_array")
        if arr is None or not isinstance(arr, np.ndarray):
            continue
        feats = extract_pressure_features(arr, float(row.get("stance_time_s", 0.0)))
        # carry forward metadata
        meta = {
            "subject_id":  row.get("subject_id", ""),
            "footwear":    row.get("footwear", ""),
            "trial":       row.get("trial", ""),
            "footstep_id": row.get("footstep_id", -1),
            "side":        row.get("side", ""),
            "stance_time_s": row.get("stance_time_s", 0.0),
            "foot_length_cm": row.get("foot_length_cm", 0.0),
            "foot_width_cm":  row.get("foot_width_cm", 0.0),
        }
        meta.update(feats)
        records.append(meta)

    return pd.DataFrame(records)
