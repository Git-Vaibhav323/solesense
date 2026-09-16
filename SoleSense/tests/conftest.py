"""
pytest configuration and shared fixtures for SoleSense tests.
"""
import os
import sys
import numpy as np
import pandas as pd
import pytest

# Ensure project root is on the path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from config.config import FOOTSTEP_FRAMES, FOOTSTEP_ROWS, FOOTSTEP_COLS


@pytest.fixture
def synthetic_footstep_array():
    """
    A realistic synthetic pressure array (101 × 75 × 40 kPa).
    Simulates a heel-strike → midstance → toe-off pattern.
    """
    arr = np.zeros((FOOTSTEP_FRAMES, FOOTSTEP_ROWS, FOOTSTEP_COLS), dtype=np.float64)
    # Ramp up and down over 60 frames
    for i in range(60):
        frame = min(i, 59 - i) / 30.0  # 0→1→0 envelope
        # Rearfoot loading at heel strike (early frames)
        heel_intensity = max(0, 1.0 - i / 20.0) * 200.0
        arr[i, 55:75, 15:25] += heel_intensity * frame
        # Forefoot loading at push-off (later frames)
        ff_intensity = max(0, (i - 30) / 30.0) * 300.0
        arr[i, 15:35, 15:25] += ff_intensity
    arr = np.clip(arr, 0, 766)
    return arr


@pytest.fixture
def synthetic_single_step_df(synthetic_footstep_array):
    """DataFrame with one footstep row including a pressure array."""
    return pd.DataFrame([{
        "subject_id": "001",
        "footwear": "BF",
        "trial": "W1",
        "footstep_id": 0,
        "side": "Left",
        "start_frame": 200,
        "end_frame": 260,
        "stance_frames": 60,
        "stance_time_s": 0.60,
        "foot_length_px": 56.0,
        "foot_width_px": 22.0,
        "foot_length_cm": 28.0,
        "foot_width_cm": 11.0,
        "mean_pressure_integral": 15000.0,
        "rscore": 0.8,
        "exclude": 0,
        "outlier": 0,
        "incomplete": 0,
        "rotation_angle": -2.0,
        "pressure_array": synthetic_footstep_array,
    }])


@pytest.fixture
def synthetic_trial_df():
    """A multi-step bilateral trial DataFrame without pressure arrays."""
    rng = np.random.default_rng(42)
    rows = []
    for i in range(20):
        side = "Left" if i % 2 == 0 else "Right"
        rows.append({
            "subject_id": "001",
            "footwear": "BF",
            "trial": "W1",
            "footstep_id": i,
            "side": side,
            "start_frame": 200 + i * 80,
            "end_frame": 270 + i * 80,
            "stance_frames": 70,
            "stance_time_s": 0.70 + rng.normal(0, 0.04),
            "foot_length_cm": 28.0,
            "foot_width_cm": 11.0,
            "exclude": 0,
            "outlier": 0,
            "incomplete": 0,
            "rscore": 0.9,
            "pressure_array": None,
        })
    return pd.DataFrame(rows)


@pytest.fixture
def synthetic_pressure_features_df():
    """Synthetic pressure feature table (bilateral, one trial)."""
    rng = np.random.default_rng(42)
    rows = []
    for i in range(20):
        side = "Left" if i % 2 == 0 else "Right"
        base = 15000 if side == "Left" else 14000  # slight left dominance
        rows.append({
            "subject_id": "001", "footwear": "BF", "trial": "W1",
            "footstep_id": i, "side": side,
            "stance_time_s": 0.70,
            "foot_length_cm": 28.0, "foot_width_cm": 11.0,
            "press_mean_kpa": rng.uniform(30, 80),
            "press_max_kpa": rng.uniform(200, 500),
            "pti_total_kpa_s": base + rng.normal(0, 500),
            "pti_per_cm2_kpa_s": 200 + rng.normal(0, 20),
            "contact_area_cm2": 60 + rng.normal(0, 5),
            "peak_total_force_kpa": 20000 + rng.normal(0, 1000),
            "load_frac_toe": 0.05,
            "load_frac_forefoot": 0.40 + rng.normal(0, 0.05),
            "load_frac_midfoot": 0.20,
            "load_frac_rearfoot": 0.35,
            "cop_path_length_cm": 12 + rng.normal(0, 2),
            "cop_ap_range_cm": 10 + rng.normal(0, 1),
            "cop_ml_range_cm": 2 + rng.normal(0, 0.3),
        })
    return pd.DataFrame(rows)
