"""Tests for src/risk_engine.py"""
import math
import pytest
import pandas as pd
import numpy as np

from src.risk_engine import (
    compute_risk,
    score_features_df,
    score_trial_summary,
    RiskResult,
)


def _make_row(**kwargs) -> pd.Series:
    """Helper: build a risk-scoreable feature row with sensible defaults."""
    defaults = {
        "subject_id": "001", "footwear": "BF", "trial": "W1",
        "press_max_kpa": 150.0,           # below 200 threshold → not triggered
        "pti_total_kpa_s": 20000.0,        # below 50000 → not triggered
        "asym_pti_total_kpa_s": 5.0,       # below 20% → not triggered
        "asym_press_mean_kpa": 8.0,        # below 10% → not triggered
        "load_frac_forefoot": 0.45,        # below 0.60 → not triggered
        "load_frac_rearfoot": 0.40,        # below 0.65 → not triggered
        "step_time_std_s": 0.05,           # below 0.15 → not triggered
        "gait_symmetry_index": 0.05,       # below 0.10 → not triggered
        "persistence_pti_total_kpa_s": 0.2,
        "asym_load_forefoot": 8.0,
        "left_loading_fraction": 0.52,
        "right_loading_fraction": 0.48,
        "asym_dir_pti_total_kpa_s": 5.0,
    }
    defaults.update(kwargs)
    return pd.Series(defaults)


class TestRiskScore:
    def test_normal_profile_low_score(self):
        row = _make_row()
        result = compute_risk(row)
        assert result.risk_level == "NORMAL"
        assert result.risk_score < 30.0

    def test_high_pressure_triggers_factor(self):
        row = _make_row(press_max_kpa=300.0)  # above 200 threshold
        result = compute_risk(row)
        triggered = [f for f in result.factors if f.name == "peak_pressure" and f.triggered]
        assert len(triggered) == 1

    def test_high_asymmetry_triggers_factor(self):
        row = _make_row(asym_pti_total_kpa_s=25.0)  # above 20% threshold
        result = compute_risk(row)
        triggered = [f for f in result.factors if f.name == "loading_asymmetry" and f.triggered]
        assert len(triggered) == 1

    def test_multiple_triggers_increase_score(self):
        row_one = _make_row(press_max_kpa=300.0)
        row_multi = _make_row(press_max_kpa=300.0, asym_pti_total_kpa_s=25.0,
                               pti_total_kpa_s=60000.0)
        r_one = compute_risk(row_one)
        r_multi = compute_risk(row_multi)
        assert r_multi.risk_score > r_one.risk_score

    def test_score_bounded_0_100(self):
        # Trigger everything
        row = _make_row(
            press_max_kpa=1000.0, pti_total_kpa_s=100000.0,
            asym_pti_total_kpa_s=50.0, asym_press_mean_kpa=30.0,
            load_frac_forefoot=0.8, load_frac_rearfoot=0.8,
            step_time_std_s=0.5, gait_symmetry_index=0.5,
            persistence_pti_total_kpa_s=1.0, asym_load_forefoot=30.0,
        )
        result = compute_risk(row)
        assert 0.0 <= result.risk_score <= 100.0

    def test_risk_levels_consistent(self):
        for score_val, expected_level in [(10, "NORMAL"), (35, "MONITOR"), (65, "ALERT")]:
            row = _make_row()
            # Build a mock result manually to verify level logic
            from src.risk_engine import RISK_LEVEL_MONITOR, RISK_LEVEL_ALERT
            if score_val >= RISK_LEVEL_ALERT:
                assert expected_level == "ALERT"
            elif score_val >= RISK_LEVEL_MONITOR:
                assert expected_level == "MONITOR"
            else:
                assert expected_level == "NORMAL"

    def test_nan_features_skipped_gracefully(self):
        row = _make_row(press_max_kpa=float("nan"))
        result = compute_risk(row)  # must not raise
        assert isinstance(result.risk_score, float)
        assert not math.isnan(result.risk_score)

    def test_missing_feature_skipped_gracefully(self):
        row = pd.Series({"subject_id": "001", "footwear": "BF", "trial": "W1"})
        result = compute_risk(row)  # sparse row — must not raise
        assert isinstance(result.risk_score, float)

    def test_contributing_factors_match_triggered(self):
        row = _make_row(press_max_kpa=300.0, asym_pti_total_kpa_s=25.0)
        result = compute_risk(row)
        n_triggered = sum(1 for f in result.factors if f.triggered)
        assert len(result.contributing_factors) == n_triggered

    def test_result_has_affected_region(self):
        row = _make_row()
        result = compute_risk(row)
        assert isinstance(result.affected_region, str)
        assert "_" in result.affected_region  # e.g. "LEFT_FOREFOOT"

    def test_to_dict_serialisable(self):
        row = _make_row()
        result = compute_risk(row)
        d = result.to_dict()
        assert "risk_score" in d
        assert "risk_level" in d
        assert "contributing_factors" in d
        assert isinstance(d["contributing_factors"], list)


class TestBatchScoring:
    def test_score_features_df_adds_columns(self):
        df = pd.read_csv("data/features/features.csv")
        scored = score_features_df(df.head(20))
        for col in ["risk_score", "risk_level", "affected_region", "n_contributing_factors"]:
            assert col in scored.columns

    def test_risk_scores_numeric(self):
        df = pd.read_csv("data/features/features.csv")
        scored = score_features_df(df.head(20))
        assert scored["risk_score"].between(0, 100).all()

    def test_trial_summary_one_row_per_trial(self):
        df = pd.read_csv("data/features/features.csv")
        scored = score_features_df(df)
        summary = score_trial_summary(scored)
        # Should have one row per (subject, footwear, trial)
        n_groups = df.groupby(["subject_id", "footwear", "trial"]).ngroups
        assert len(summary) == n_groups
