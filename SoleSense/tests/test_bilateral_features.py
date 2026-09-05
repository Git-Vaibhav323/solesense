"""Tests for src/bilateral_features.py"""
import pytest
import pandas as pd
import numpy as np

from src.bilateral_features import (
    normalized_symmetry_index,
    directional_asymmetry,
    compute_bilateral_pressure_features,
    extract_bilateral_features_batch,
)


class TestNSI:
    def test_perfect_symmetry(self):
        assert normalized_symmetry_index(10.0, 10.0) == pytest.approx(0.0)

    def test_zero_both_sides(self):
        assert normalized_symmetry_index(0.0, 0.0) == pytest.approx(0.0)

    def test_one_side_zero(self):
        # |10 - 0| / ((10+0)/2) * 100 = 200%
        result = normalized_symmetry_index(10.0, 0.0)
        assert result == pytest.approx(200.0)

    def test_known_asymmetry(self):
        # L=12, R=8 → |12-8|/10 * 100 = 40%
        result = normalized_symmetry_index(12.0, 8.0)
        assert result == pytest.approx(40.0)

    def test_symmetry_is_commutative(self):
        a = normalized_symmetry_index(15.0, 10.0)
        b = normalized_symmetry_index(10.0, 15.0)
        assert a == pytest.approx(b)

    def test_always_non_negative(self):
        for l, r in [(5, 10), (10, 5), (0, 0), (100, 1)]:
            assert normalized_symmetry_index(l, r) >= 0.0


class TestDirectionalAsymmetry:
    def test_positive_when_left_greater(self):
        result = directional_asymmetry(20.0, 10.0)
        assert result > 0.0

    def test_negative_when_right_greater(self):
        result = directional_asymmetry(10.0, 20.0)
        assert result < 0.0

    def test_zero_when_equal(self):
        result = directional_asymmetry(10.0, 10.0)
        assert result == pytest.approx(0.0)

    def test_zero_both_zero(self):
        result = directional_asymmetry(0.0, 0.0)
        assert result == pytest.approx(0.0)


class TestBilateralPressureFeatures:
    def test_returns_empty_for_missing_side(self):
        # Only left side
        df = pd.DataFrame([{
            "subject_id": "001", "footwear": "BF", "trial": "W1",
            "side": "Left", "pti_total_kpa_s": 15000.0,
            "press_mean_kpa": 50.0, "press_max_kpa": 400.0,
        }])
        result = compute_bilateral_pressure_features(df)
        assert "asym_pti_total_kpa_s" in result
        assert pd.isna(result.get("asym_press_mean_kpa", float("nan")))

    def test_loading_fractions_sum_to_one(self, synthetic_pressure_features_df):
        result = compute_bilateral_pressure_features(synthetic_pressure_features_df)
        total = result.get("left_loading_fraction", 0) + result.get("right_loading_fraction", 0)
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_asymmetry_non_negative(self, synthetic_pressure_features_df):
        result = compute_bilateral_pressure_features(synthetic_pressure_features_df)
        for key in ["asym_press_mean_kpa", "asym_pti_total_kpa_s", "asym_stance_time"]:
            assert result.get(key, -1) >= 0.0, f"{key} should be non-negative"

    def test_symmetric_data_gives_low_asymmetry(self):
        rows = []
        for i in range(10):
            side = "Left" if i % 2 == 0 else "Right"
            rows.append({
                "subject_id": "001", "footwear": "BF", "trial": "W1",
                "side": side, "footstep_id": i, "stance_time_s": 0.70,
                "press_mean_kpa": 50.0, "press_max_kpa": 300.0,
                "pti_total_kpa_s": 15000.0, "pti_per_cm2_kpa_s": 200.0,
                "contact_area_cm2": 60.0, "peak_total_force_kpa": 18000.0,
                "load_frac_toe": 0.05, "load_frac_forefoot": 0.40,
                "load_frac_midfoot": 0.20, "load_frac_rearfoot": 0.35,
                "cop_path_length_cm": 12.0, "cop_ap_range_cm": 10.0, "cop_ml_range_cm": 2.0,
            })
        df = pd.DataFrame(rows)
        result = compute_bilateral_pressure_features(df)
        assert result["asym_pti_total_kpa_s"] == pytest.approx(0.0, abs=1e-4)
        assert result["left_loading_fraction"] == pytest.approx(0.5, abs=1e-4)

    def test_asymmetric_data_detected(self):
        rows = []
        for i in range(10):
            side = "Left" if i % 2 == 0 else "Right"
            pti = 20000.0 if side == "Left" else 10000.0  # 2× left loading
            rows.append({
                "subject_id": "001", "footwear": "BF", "trial": "W1",
                "side": side, "footstep_id": i, "stance_time_s": 0.70,
                "press_mean_kpa": 50.0, "press_max_kpa": 300.0,
                "pti_total_kpa_s": pti, "pti_per_cm2_kpa_s": 200.0,
                "contact_area_cm2": 60.0, "peak_total_force_kpa": 18000.0,
                "load_frac_toe": 0.05, "load_frac_forefoot": 0.40,
                "load_frac_midfoot": 0.20, "load_frac_rearfoot": 0.35,
                "cop_path_length_cm": 12.0, "cop_ap_range_cm": 10.0, "cop_ml_range_cm": 2.0,
            })
        df = pd.DataFrame(rows)
        result = compute_bilateral_pressure_features(df)
        # |20000-10000| / 15000 * 100 ≈ 66.7%
        assert result["asym_pti_total_kpa_s"] == pytest.approx(66.67, abs=0.1)
        assert result["asym_dir_pti_total_kpa_s"] > 0  # left > right

    def test_division_by_zero_safe(self):
        rows = []
        for i in range(4):
            side = "Left" if i % 2 == 0 else "Right"
            rows.append({
                "subject_id": "001", "footwear": "BF", "trial": "W1",
                "side": side, "footstep_id": i, "stance_time_s": 0.70,
                "press_mean_kpa": 0.0, "press_max_kpa": 0.0,
                "pti_total_kpa_s": 0.0, "pti_per_cm2_kpa_s": 0.0,
                "contact_area_cm2": 0.0, "peak_total_force_kpa": 0.0,
                "load_frac_toe": 0.0, "load_frac_forefoot": 0.0,
                "load_frac_midfoot": 0.0, "load_frac_rearfoot": 0.0,
                "cop_path_length_cm": 0.0, "cop_ap_range_cm": 0.0, "cop_ml_range_cm": 0.0,
            })
        df = pd.DataFrame(rows)
        result = compute_bilateral_pressure_features(df)  # must not raise
        assert result["asym_pti_total_kpa_s"] == pytest.approx(0.0)


class TestBilateralBatch:
    def test_returns_one_row_per_trial(self, synthetic_pressure_features_df):
        result = extract_bilateral_features_batch(synthetic_pressure_features_df)
        assert len(result) == 1  # single trial in fixture
        assert "subject_id" in result.columns
        assert "asym_pti_total_kpa_s" in result.columns
