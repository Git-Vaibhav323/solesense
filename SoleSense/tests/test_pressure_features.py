"""Tests for src/pressure_features.py"""
import numpy as np
import pytest
from config.config import FOOTSTEP_FRAMES, FOOTSTEP_ROWS, FOOTSTEP_COLS
from src.pressure_features import (
    compute_basic_stats,
    compute_pressure_time_exposure,
    compute_regional_loading,
    compute_peak_location,
    compute_cop,
    extract_pressure_features,
)


@pytest.fixture
def zero_array():
    return np.zeros((FOOTSTEP_FRAMES, FOOTSTEP_ROWS, FOOTSTEP_COLS))


@pytest.fixture
def uniform_array():
    """100 kPa everywhere in a 10×10 patch for 50 frames."""
    arr = np.zeros((FOOTSTEP_FRAMES, FOOTSTEP_ROWS, FOOTSTEP_COLS))
    arr[10:60, 20:30, 15:25] = 100.0
    return arr


class TestBasicStats:
    def test_zero_array_returns_zeros(self, zero_array):
        result = compute_basic_stats(zero_array)
        assert result["press_max_kpa"] == 0.0
        assert result["press_mean_kpa"] == 0.0
        assert result["active_frame_count"] == 0

    def test_uniform_pressure(self, uniform_array):
        result = compute_basic_stats(uniform_array)
        assert result["press_max_kpa"] == pytest.approx(100.0)
        assert result["press_mean_kpa"] == pytest.approx(100.0)
        assert result["press_std_kpa"] == pytest.approx(0.0, abs=1e-6)
        assert result["active_frame_count"] == 50

    def test_contact_area_positive(self, uniform_array):
        result = compute_basic_stats(uniform_array)
        assert result["contact_area_cm2"] > 0.0

    def test_all_percentiles_ordered(self, synthetic_footstep_array):
        result = compute_basic_stats(synthetic_footstep_array)
        assert result["press_p25_kpa"] <= result["press_median_kpa"]
        assert result["press_median_kpa"] <= result["press_p75_kpa"]
        assert result["press_p75_kpa"] <= result["press_p95_kpa"]
        assert result["press_p95_kpa"] <= result["press_max_kpa"]


class TestPTI:
    def test_zero_array_pti_zero(self, zero_array):
        result = compute_pressure_time_exposure(zero_array, 0.6)
        assert result["pti_total_kpa_s"] == 0.0

    def test_pti_positive(self, uniform_array):
        result = compute_pressure_time_exposure(uniform_array, 0.5)
        assert result["pti_total_kpa_s"] > 0.0
        assert result["mean_total_force_kpa"] > 0.0
        assert result["peak_total_force_kpa"] >= result["mean_total_force_kpa"]

    def test_loading_rate_positive(self, uniform_array):
        result = compute_pressure_time_exposure(uniform_array, 0.5)
        assert result["loading_rate_kpa_s"] > 0.0

    def test_pti_scales_with_pressure(self):
        a = np.zeros((FOOTSTEP_FRAMES, FOOTSTEP_ROWS, FOOTSTEP_COLS))
        b = np.zeros((FOOTSTEP_FRAMES, FOOTSTEP_ROWS, FOOTSTEP_COLS))
        a[10:60, 20:30, 15:25] = 100.0
        b[10:60, 20:30, 15:25] = 200.0
        r_a = compute_pressure_time_exposure(a, 0.5)
        r_b = compute_pressure_time_exposure(b, 0.5)
        assert r_b["pti_total_kpa_s"] == pytest.approx(r_a["pti_total_kpa_s"] * 2, rel=1e-5)


class TestRegionalLoading:
    def test_fractions_sum_to_one(self, synthetic_footstep_array):
        result = compute_regional_loading(synthetic_footstep_array)
        total = (result["load_frac_toe"] + result["load_frac_forefoot"] +
                 result["load_frac_midfoot"] + result["load_frac_rearfoot"])
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_rearfoot_high_for_heel_pressure(self):
        arr = np.zeros((FOOTSTEP_FRAMES, FOOTSTEP_ROWS, FOOTSTEP_COLS))
        arr[:, 55:75, :] = 100.0  # only rearfoot
        result = compute_regional_loading(arr)
        assert result["load_frac_rearfoot"] == pytest.approx(1.0, abs=1e-6)
        assert result["load_frac_forefoot"] == pytest.approx(0.0, abs=1e-6)

    def test_forefoot_high_for_toe_pressure(self):
        arr = np.zeros((FOOTSTEP_FRAMES, FOOTSTEP_ROWS, FOOTSTEP_COLS))
        arr[:, 15:35, :] = 100.0  # only forefoot
        result = compute_regional_loading(arr)
        assert result["load_frac_forefoot"] == pytest.approx(1.0, abs=1e-6)

    def test_zero_array(self, zero_array):
        result = compute_regional_loading(zero_array)
        for region in ["toe", "forefoot", "midfoot", "rearfoot"]:
            assert result[f"load_frac_{region}"] == 0.0


class TestPeakLocation:
    def test_zero_array(self, zero_array):
        result = compute_peak_location(zero_array)
        assert result["peak_row_px"] == 0.0

    def test_peak_at_known_location(self):
        arr = np.zeros((FOOTSTEP_FRAMES, FOOTSTEP_ROWS, FOOTSTEP_COLS))
        arr[5, 10, 20] = 500.0  # known peak
        result = compute_peak_location(arr)
        assert result["peak_row_px"] == pytest.approx(10.0)
        assert result["peak_col_px"] == pytest.approx(20.0)
        assert result["peak_frame_idx"] == pytest.approx(5.0)

    def test_cm_conversion(self):
        arr = np.zeros((FOOTSTEP_FRAMES, FOOTSTEP_ROWS, FOOTSTEP_COLS))
        arr[0, 30, 10] = 100.0
        result = compute_peak_location(arr)
        assert result["peak_row_cm"] == pytest.approx(30 * 0.5)
        assert result["peak_col_cm"] == pytest.approx(10 * 0.5)


class TestCoP:
    def test_zero_array_returns_zeros(self, zero_array):
        result = compute_cop(zero_array)
        assert result["cop_path_length_cm"] == 0.0

    def test_cop_at_centre_for_uniform_patch(self):
        arr = np.zeros((FOOTSTEP_FRAMES, FOOTSTEP_ROWS, FOOTSTEP_COLS))
        arr[10:60, 34:41, 18:22] = 100.0  # patch centred at (37.5, 20) px
        result = compute_cop(arr)
        # CoP start (early frames) = same patch ≈ row 37 * 0.5 = 18.5 cm
        assert result["cop_start_row_cm"] == pytest.approx(37.5 * 0.5, abs=0.5)

    def test_path_length_positive_for_real_data(self, synthetic_footstep_array):
        result = compute_cop(synthetic_footstep_array)
        assert result["cop_path_length_cm"] > 0.0

    def test_velocity_positive(self, synthetic_footstep_array):
        result = compute_cop(synthetic_footstep_array)
        assert result["cop_mean_velocity_cm_s"] > 0.0

    def test_ap_range_positive(self, synthetic_footstep_array):
        result = compute_cop(synthetic_footstep_array)
        assert result["cop_ap_range_cm"] >= 0.0


class TestExtractAll:
    def test_returns_all_key_features(self, synthetic_footstep_array):
        result = extract_pressure_features(synthetic_footstep_array, 0.60)
        expected_keys = [
            "press_mean_kpa", "press_max_kpa", "pti_total_kpa_s",
            "load_frac_forefoot", "load_frac_rearfoot",
            "cop_path_length_cm", "peak_row_px",
        ]
        for k in expected_keys:
            assert k in result, f"Missing feature: {k}"

    def test_no_nan_in_output(self, synthetic_footstep_array):
        import math
        result = extract_pressure_features(synthetic_footstep_array, 0.60)
        for k, v in result.items():
            assert not math.isnan(v), f"NaN in feature: {k}"
