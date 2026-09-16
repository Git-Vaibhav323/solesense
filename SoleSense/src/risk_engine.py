"""
SoleSense Risk Engine
======================
An EXPLAINABLE, rule-based prototype risk indicator.

⚠ IMPORTANT DISCLAIMER ⚠
All thresholds in this module are EXPERIMENTAL / DEMO values.
This system is a research prototype.  It does NOT diagnose any medical
condition, including diabetes, diabetic neuropathy, or foot ulcers.
The "SoleSense Risk Indicator" is not clinically validated.

Design principle: each rule produces a named factor with a sub-score.
The final score is the weighted sum of sub-scores, capped at 100.
Every factor is fully explainable — the dashboard shows exactly
WHY the indicator is elevated.

Risk levels (thresholds in config.py):
    0  – 29   NORMAL
    30 – 59   MONITOR
    60+        ALERT
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.config import (
    RISK_PRESSURE_HIGH_KPA,
    RISK_PRESSURE_EXPOSURE_HIGH,
    RISK_ASYMMETRY_HIGH_PCT,
    RISK_ASYMMETRY_MODERATE_PCT,
    RISK_GAIT_VARIABILITY_HIGH_S,
    RISK_REGIONAL_LOADING_HIGH,
    RISK_LEVEL_MONITOR,
    RISK_LEVEL_ALERT,
)


# ─────────────────────────────────────────────────────────────────────────────
# Data types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RiskFactor:
    name: str          # short identifier
    label: str         # human-readable description for dashboard
    sub_score: float   # contribution to risk score (0–40)
    triggered: bool    # whether this factor was activated
    value: float       # the feature value that triggered it
    threshold: float   # the threshold that was crossed
    direction: str     # "above" or "below"
    icon: str          # "⚠" or "✓"
    detail: str        # one-line detail for the dashboard


@dataclass
class RiskResult:
    subject_id: str
    footwear: str
    trial: str
    risk_score: float               # 0–100
    risk_level: str                 # NORMAL / MONITOR / ALERT
    affected_region: str            # anatomical region with most concern
    contributing_factors: List[str] # human-readable list
    recommended_action: str
    factors: List[RiskFactor] = field(default_factory=list)  # full detail

    def to_dict(self) -> dict:
        return {
            "subject_id": self.subject_id,
            "footwear": self.footwear,
            "trial": self.trial,
            "risk_score": round(self.risk_score, 1),
            "risk_level": self.risk_level,
            "affected_region": self.affected_region,
            "contributing_factors": self.contributing_factors,
            "recommended_action": self.recommended_action,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Rule definitions
# ─────────────────────────────────────────────────────────────────────────────
# Each rule: (name, label, weight, feature_col, threshold, direction, detail_template)
# direction: 'above' means factor triggers when value > threshold
#            'below' means triggers when value < threshold

_RULES: List[Tuple] = [
    # (name, label, weight, feature, threshold, direction, detail_fmt)
    (
        "peak_pressure",
        "Elevated peak pressure",
        25,
        "press_max_kpa",
        RISK_PRESSURE_HIGH_KPA,
        "above",
        "Peak pressure {value:.0f} kPa exceeds threshold of {threshold:.0f} kPa",
    ),
    (
        "pressure_exposure",
        "High pressure-time exposure",
        25,
        "pti_total_kpa_s",
        RISK_PRESSURE_EXPOSURE_HIGH,
        "above",
        "Pressure-time integral {value:.0f} kPa·s exceeds threshold of {threshold:.0f} kPa·s",
    ),
    (
        "loading_asymmetry",
        "Left/right loading asymmetry",
        20,
        "asym_pti_total_kpa_s",
        RISK_ASYMMETRY_HIGH_PCT,
        "above",
        "Loading asymmetry {value:.1f}% exceeds threshold of {threshold:.0f}%",
    ),
    (
        "pressure_asymmetry",
        "Left/right pressure asymmetry",
        15,
        "asym_press_mean_kpa",
        RISK_ASYMMETRY_MODERATE_PCT,
        "above",
        "Pressure asymmetry {value:.1f}% exceeds {threshold:.0f}%",
    ),
    (
        "forefoot_overload",
        "Forefoot overloading",
        15,
        "load_frac_forefoot",
        RISK_REGIONAL_LOADING_HIGH,
        "above",
        "Forefoot carries {value:.0%} of total load (threshold: {threshold:.0%})",
    ),
    (
        "rearfoot_overload",
        "Rearfoot (heel) overloading",
        10,
        "load_frac_rearfoot",
        0.65,
        "above",
        "Rearfoot carries {value:.0%} of total load (threshold: 65%)",
    ),
    (
        "gait_variability",
        "High gait temporal variability",
        15,
        "step_time_std_s",
        RISK_GAIT_VARIABILITY_HIGH_S,
        "above",
        "Step time variability {value:.3f} s exceeds {threshold:.3f} s",
    ),
    (
        "gait_asymmetry",
        "Gait timing asymmetry",
        10,
        "gait_symmetry_index",
        0.10,
        "above",
        "Gait symmetry index {value:.3f} exceeds 0.10 (10%)",
    ),
    (
        "persistence_pressure",
        "Persistent pressure exposure",
        20,
        "persistence_pti_total_kpa_s",
        0.6,
        "above",
        "{value:.0%} of recent steps show elevated pressure-time exposure",
    ),
    (
        "persistence_asymmetry",
        "Persistent loading asymmetry",
        15,
        "asym_load_forefoot",
        RISK_ASYMMETRY_HIGH_PCT,
        "above",
        "Persistent forefoot asymmetry detected across recent steps",
    ),
]

# Weights sum to 170; we normalise to 0–100 scale
_TOTAL_WEIGHT = sum(r[2] for r in _RULES)


# ─────────────────────────────────────────────────────────────────────────────
# Risk computation
# ─────────────────────────────────────────────────────────────────────────────

def _get_affected_region(row: pd.Series) -> str:
    """Determine the most loaded anatomical region."""
    region_cols = {
        "LEFT_FOREFOOT":  row.get("load_frac_forefoot", 0) * row.get("left_loading_fraction", 0.5),
        "RIGHT_FOREFOOT": row.get("load_frac_forefoot", 0) * row.get("right_loading_fraction", 0.5),
        "LEFT_REARFOOT":  row.get("load_frac_rearfoot", 0) * row.get("left_loading_fraction", 0.5),
        "RIGHT_REARFOOT": row.get("load_frac_rearfoot", 0) * row.get("right_loading_fraction", 0.5),
    }
    # Use directional asymmetry to determine which side
    dir_val = row.get("asym_dir_pti_total_kpa_s", 0)
    side = "LEFT" if dir_val > 0 else "RIGHT"

    frac_ff = row.get("load_frac_forefoot", 0)
    frac_rf = row.get("load_frac_rearfoot", 0)
    region = "FOREFOOT" if frac_ff > frac_rf else "REARFOOT"

    if frac_ff < 0.4 and frac_rf < 0.4:
        region = "MIDFOOT"

    return f"{side}_{region}"


def _recommended_action(level: str, factors: List[str]) -> str:
    if level == "NORMAL":
        return "No action required. Continue monitoring."
    elif level == "MONITOR":
        return (
            "Monitor loading patterns across sessions.  "
            "Consider footwear adjustment if asymmetry persists."
        )
    else:  # ALERT
        return (
            "Elevated loading detected.  "
            "Review footwear and activity level.  "
            "Consult a healthcare professional if symptoms are present.  "
            "(Note: this is a prototype indicator, not a clinical assessment.)"
        )


def compute_risk(row: pd.Series) -> RiskResult:
    """
    Compute the SoleSense Risk Indicator for one row of the feature table.

    Parameters
    ----------
    row : pd.Series — one row from the features DataFrame
          (output of feature_pipeline.run_pipeline)

    Returns
    -------
    RiskResult with all fields populated.
    """
    factors: List[RiskFactor] = []
    raw_score = 0.0

    for (name, label, weight, feat_col, threshold, direction, detail_fmt) in _RULES:
        value = row.get(feat_col, None)
        if value is None or (isinstance(value, float) and np.isnan(value)):
            # Feature unavailable — skip this rule
            continue

        triggered = (value > threshold) if direction == "above" else (value < threshold)

        sub_score = weight if triggered else 0.0
        raw_score += sub_score

        detail = detail_fmt.format(value=value, threshold=threshold)
        factors.append(RiskFactor(
            name=name,
            label=label,
            sub_score=sub_score,
            triggered=triggered,
            value=float(value),
            threshold=float(threshold),
            direction=direction,
            icon="⚠" if triggered else "✓",
            detail=detail,
        ))

    # Normalise to 0–100
    risk_score = min(100.0, (raw_score / _TOTAL_WEIGHT) * 100.0)

    # Risk level
    if risk_score >= RISK_LEVEL_ALERT:
        risk_level = "ALERT"
    elif risk_score >= RISK_LEVEL_MONITOR:
        risk_level = "MONITOR"
    else:
        risk_level = "NORMAL"

    # Contributing factors (only triggered ones)
    triggered_factors = [f.label for f in factors if f.triggered]
    affected_region = _get_affected_region(row)

    return RiskResult(
        subject_id=str(row.get("subject_id", "")),
        footwear=str(row.get("footwear", "")),
        trial=str(row.get("trial", "")),
        risk_score=risk_score,
        risk_level=risk_level,
        affected_region=affected_region,
        contributing_factors=triggered_factors,
        recommended_action=_recommended_action(risk_level, triggered_factors),
        factors=factors,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Batch scorer
# ─────────────────────────────────────────────────────────────────────────────

def score_features_df(features_df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply risk scoring to every row of the feature table.

    Returns the input DataFrame with additional columns:
        risk_score, risk_level, affected_region,
        n_contributing_factors, recommended_action
    """
    results = features_df.apply(compute_risk, axis=1)

    features_df = features_df.copy()
    features_df["risk_score"]             = [r.risk_score for r in results]
    features_df["risk_level"]             = [r.risk_level for r in results]
    features_df["affected_region"]        = [r.affected_region for r in results]
    features_df["n_contributing_factors"] = [len(r.contributing_factors) for r in results]
    features_df["recommended_action"]     = [r.recommended_action for r in results]

    return features_df


def score_trial_summary(features_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute a per-trial risk summary (max risk score across all steps in the trial).

    Returns one row per (subject_id, footwear, trial).
    """
    if "risk_score" not in features_df.columns:
        features_df = score_features_df(features_df)

    group_keys = ["subject_id", "footwear", "trial"]
    summary = features_df.groupby(group_keys).agg(
        risk_score_max=("risk_score", "max"),
        risk_score_mean=("risk_score", "mean"),
        n_steps=("footstep_id", "count"),
    ).reset_index()

    summary["risk_level"] = summary["risk_score_max"].apply(
        lambda s: "ALERT" if s >= RISK_LEVEL_ALERT
        else ("MONITOR" if s >= RISK_LEVEL_MONITOR else "NORMAL")
    )
    return summary
