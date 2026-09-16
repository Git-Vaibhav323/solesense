"""Tests for src/gait_features.py"""
import pytest
import pandas as pd
import numpy as np

from src.gait_features import compute_gait_features, extract_gait_features_batch


def _make_trial_df(n_steps=20, step_interval=80, noise=0, side_alternating=True):
    """Generate a synthetic trial DataFrame."""
    rows = []
    for i in range(n_steps):
        side = "Left" if (i % 2 == 0 if side_alternating else i < n_steps // 2) else "Right"
        sf = 200 + i * step_interval + np.random.randint(-noise, noise + 1)
        rows.append({
            "subject_id": "001", "footwear": "BF", "trial": "W1",
            "footstep_id": i, "side": side,
            "start_frame": sf, "end_frame": sf + 70,
            "stance_time_s": 0.70,
        })
    return pd.DataFrame(rows)


class TestComputeGaitFeatures:
    def test_empty_df_returns_nan_dict(self):
        result = compute_gait_features(pd.DataFrame())
        assert all(isinstance(v, float) for v in result.values())

    def test_single_step_returns_dict(self):
        df = _make_trial_df(n_steps=1)
        result = compute_gait_features(df)
        assert isinstance(result, dict)

    def test_cadence_reasonable(self):
        # step_interval=80 frames = 0.8s step time → cadence ≈ 75 steps/min
        df = _make_trial_df(n_steps=20, step_interval=80)
        result = compute_gait_features(df)
        assert result["cadence_steps_per_min"] == pytest.approx(60.0 / 0.80, abs=5.0)

    def test_faster_cadence_for_shorter_interval(self):
        slow = _make_trial_df(n_steps=20, step_interval=100)
        fast = _make_trial_df(n_steps=20, step_interval=60)
        r_slow = compute_gait_features(slow)
        r_fast = compute_gait_features(fast)
        assert r_fast["cadence_steps_per_min"] > r_slow["cadence_steps_per_min"]

    def test_step_count_left_right(self):
        df = _make_trial_df(n_steps=20)
        result = compute_gait_features(df)
        assert result["n_steps_left"] == pytest.approx(10.0)
        assert result["n_steps_right"] == pytest.approx(10.0)

    def test_stride_time_approximately_double_step_time(self):
        df = _make_trial_df(n_steps=20, step_interval=80)
        result = compute_gait_features(df)
        step_t = result["step_time_mean_s"]
        stride_l = result.get("stride_time_left_mean_s", 0)
        if stride_l > 0 and step_t > 0:
            # stride ≈ 2 × step time for alternating gait
            assert stride_l == pytest.approx(step_t * 2, rel=0.2)

    def test_symmetry_index_near_zero_for_symmetric_gait(self):
        df = _make_trial_df(n_steps=20, step_interval=80)
        result = compute_gait_features(df)
        # Perfectly alternating → stride times equal → symmetry ~0
        assert result.get("gait_symmetry_index", 1.0) < 0.1

    def test_all_required_keys_present(self):
        df = _make_trial_df(n_steps=20)
        result = compute_gait_features(df)
        required = [
            "stance_mean_s", "cadence_steps_per_min",
            "step_time_mean_s", "gait_symmetry_index",
        ]
        for k in required:
            assert k in result, f"Missing key: {k}"


class TestGaitBatch:
    def test_batch_one_row_per_group(self):
        df = pd.DataFrame([{
            "subject_id": "001", "footwear": "BF", "trial": "W1",
            "footstep_id": i, "side": "Left" if i % 2 == 0 else "Right",
            "start_frame": 200 + i * 80, "end_frame": 270 + i * 80,
            "stance_time_s": 0.70,
        } for i in range(20)])
        result = extract_gait_features_batch(df)
        assert len(result) == 1
        assert "cadence_steps_per_min" in result.columns
