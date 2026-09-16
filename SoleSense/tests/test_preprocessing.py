"""Tests for src/preprocessing.py"""
import numpy as np
import pandas as pd
import pytest

from src.preprocessing import preprocess, get_clean_steps, audit_missing
from config.config import FOOTSTEP_FRAMES, FOOTSTEP_ROWS, FOOTSTEP_COLS


def _make_df(n=10, all_exclude=False):
    rows = []
    for i in range(n):
        rows.append({
            "subject_id": "001", "footwear": "BF", "trial": "W1",
            "footstep_id": i, "side": "Left" if i % 2 == 0 else "Right",
            "start_frame": 100 + i * 80, "end_frame": 170 + i * 80,
            "stance_frames": 70, "stance_time_s": 0.70,
            "rscore": 0.8, "exclude": 1 if all_exclude else 0,
            "outlier": 0, "incomplete": 0,
        })
    return pd.DataFrame(rows)


class TestPreprocess:
    def test_empty_df_returns_empty(self):
        result = preprocess(pd.DataFrame(), verbose=False)
        assert result.empty

    def test_excludes_flagged_steps(self):
        df = _make_df(10)
        df.loc[0, "exclude"] = 1
        df.loc[3, "exclude"] = 1
        result = preprocess(df, verbose=False)
        assert len(result) == 8
        assert (result["exclude"] == 0).all()

    def test_all_excluded_returns_empty(self):
        df = _make_df(5, all_exclude=True)
        result = preprocess(df, verbose=False)
        assert result.empty

    def test_stance_duration_filter_short(self):
        df = _make_df(4)
        df.loc[0, "stance_time_s"] = 0.05  # too short
        result = preprocess(df, min_stance_s=0.15, verbose=False)
        assert len(result) == 3

    def test_stance_duration_filter_long(self):
        df = _make_df(4)
        df.loc[1, "stance_time_s"] = 5.0  # too long (standing)
        result = preprocess(df, max_stance_s=2.5, verbose=False)
        assert len(result) == 3

    def test_duplicate_removal(self):
        df = _make_df(5)
        df = pd.concat([df, df.iloc[[0, 1]]], ignore_index=True)  # add 2 duplicates
        result = preprocess(df, verbose=False)
        assert len(result) == 5

    def test_side_normalization(self):
        df = _make_df(4)
        df.loc[0, "side"] = "left"   # lowercase
        df.loc[1, "side"] = "RIGHT"  # uppercase
        result = preprocess(df, verbose=False)
        assert set(result["side"]).issubset({"Left", "Right"})

    def test_invalid_side_removed(self):
        df = _make_df(4)
        df.loc[2, "side"] = "Unknown"
        result = preprocess(df, verbose=False)
        assert len(result) == 3

    def test_array_validation_wrong_shape(self):
        df = _make_df(3)
        # All rows must survive non-array filters to isolate the shape check
        df["pressure_array"] = [
            np.zeros((FOOTSTEP_FRAMES, FOOTSTEP_ROWS, FOOTSTEP_COLS)) + 1.0,  # good
            np.zeros((50, 75, 40)) + 1.0,    # wrong n_frames
            np.zeros((FOOTSTEP_FRAMES, FOOTSTEP_ROWS, FOOTSTEP_COLS)) + 1.0,  # good
        ]
        result = preprocess(df, validate_arrays=True, verbose=False)
        assert len(result) == 2

    def test_array_all_zeros_removed(self):
        df = _make_df(2)
        df["pressure_array"] = [
            np.ones((FOOTSTEP_FRAMES, FOOTSTEP_ROWS, FOOTSTEP_COLS)),
            np.zeros((FOOTSTEP_FRAMES, FOOTSTEP_ROWS, FOOTSTEP_COLS)),
        ]
        result = preprocess(df, validate_arrays=True, verbose=False)
        assert len(result) == 1

    def test_index_reset(self):
        df = _make_df(5)
        df.loc[[1, 3], "exclude"] = 1
        result = preprocess(df, verbose=False)
        assert list(result.index) == list(range(len(result)))

    def test_returns_copy(self):
        df = _make_df(5)
        result = preprocess(df, verbose=False)
        result.loc[0, "side"] = "Modified"
        assert df.loc[0, "side"] != "Modified"


class TestGetCleanSteps:
    def test_filter_by_side(self, synthetic_trial_df):
        clean = preprocess(synthetic_trial_df, verbose=False)
        left = get_clean_steps(clean, side="Left")
        assert (left["side"] == "Left").all()

    def test_filter_by_footwear(self, synthetic_trial_df):
        clean = preprocess(synthetic_trial_df, verbose=False)
        result = get_clean_steps(clean, footwear="BF")
        assert (result["footwear"] == "BF").all()


class TestAuditMissing:
    def test_no_missing(self):
        df = _make_df(5)
        report = audit_missing(df)
        assert report["missing"].sum() == 0

    def test_detects_nan(self):
        df = _make_df(5)
        df.loc[2, "stance_time_s"] = float("nan")
        report = audit_missing(df)
        row = report[report["column"] == "stance_time_s"].iloc[0]
        assert row["missing"] == 1
