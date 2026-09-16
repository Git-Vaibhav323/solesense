"""
SoleSense TinyML Anomaly Model — Placeholder Interface
=======================================================
This module defines the INTENDED API for the personalised autoencoder
that will run on the SoleSense edge MCU (nRF52840-class).

Current state: interface only.  No model is trained.

Future architecture
-------------------
features (per-step)
    ↓
personal baseline window (first N sessions, no anomaly)
    ↓
lightweight autoencoder (trained per-user, on-device fine-tuned)
    ↓
reconstruction error per feature
    ↓
anomaly score (0–1)
    ↓
fused with rule-based risk engine score
    ↓
final SoleSense Risk Indicator

Design constraints for edge deployment
---------------------------------------
- Model must fit in < 256 KB flash (nRF52840)
- Inference < 10 ms per step on M4 Cortex
- No external dependencies at inference time
- Exportable to TFLite Micro or CMSIS-NN

Training plan
-------------
1. Collect N baseline sessions per user (normal, healthy gait)
2. Train shallow autoencoder (e.g., 50 → 16 → 8 → 16 → 50 features)
3. Threshold reconstruction error from baseline distribution
4. Personalised threshold = baseline_mean + k * baseline_std  (k configurable)
5. Fine-tune incrementally on new sessions if drift detected

Feature set (same as feature_pipeline output, reduced set for edge):
    press_max_kpa, pti_total_kpa_s,
    load_frac_forefoot, load_frac_rearfoot,
    cop_path_length_cm, stance_time_s,
    asym_pti_total_kpa_s, gait_symmetry_index
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np


# Selected features for the anomaly model (subset of full feature table)
ANOMALY_FEATURES = [
    "press_max_kpa",
    "pti_total_kpa_s",
    "load_frac_forefoot",
    "load_frac_rearfoot",
    "cop_path_length_cm",
    "stance_time_s",
    "asym_pti_total_kpa_s",
    "gait_symmetry_index",
]


@dataclass
class AnomalyResult:
    anomaly_score: float       # 0 (normal) – 1 (highly anomalous)
    reconstruction_error: float
    per_feature_error: Dict[str, float]
    is_anomaly: bool
    threshold: float
    method: str = "autoencoder"  # or "isolation_forest", etc.


class PersonalAnomalyModel:
    """
    Placeholder for a per-user personalised anomaly detector.

    Interface contract
    ------------------
    1.  fit(baseline_df)          — establish personal baseline from first N sessions
    2.  predict(feature_dict)     — score one step
    3.  update(feature_dict)      — online fine-tune (not implemented yet)
    4.  save(path) / load(path)   — persistence

    All methods raise NotImplementedError until the model is implemented.
    """

    def __init__(self, subject_id: str, k_sigma: float = 3.0):
        """
        Parameters
        ----------
        subject_id : str   — personal baseline is per-user
        k_sigma    : float — anomaly threshold = mean + k * std of reconstruction error
        """
        self.subject_id = subject_id
        self.k_sigma = k_sigma
        self.is_fitted = False
        self._baseline_mean: Optional[np.ndarray] = None
        self._baseline_std:  Optional[np.ndarray] = None
        self._threshold:     Optional[float] = None

    def fit(self, baseline_features: "pd.DataFrame") -> None:
        """
        Establish personal baseline from normal-gait sessions.

        Parameters
        ----------
        baseline_features : DataFrame with columns matching ANOMALY_FEATURES.
                            Should represent 'healthy baseline' sessions.

        Raises
        ------
        NotImplementedError — model not yet implemented.
        """
        raise NotImplementedError(
            "PersonalAnomalyModel.fit() — autoencoder training not yet implemented.  "
            "This is a future TinyML feature for the SoleSense edge deployment."
        )

    def predict(self, feature_dict: Dict[str, float]) -> AnomalyResult:
        """
        Score one step's features against the personal baseline.

        Returns AnomalyResult with anomaly_score, reconstruction error, and
        per-feature breakdown (for explainability).

        Raises
        ------
        NotImplementedError — model not yet implemented.
        RuntimeError        — if called before fit().
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted.  Call fit() with baseline sessions first.")
        raise NotImplementedError(
            "PersonalAnomalyModel.predict() — not yet implemented."
        )

    def update(self, feature_dict: Dict[str, float]) -> None:
        """
        Online update: adjust baseline distribution with new normal data.
        Intended for continual personalisation during use.

        Raises
        ------
        NotImplementedError — not yet implemented.
        """
        raise NotImplementedError("Online update not yet implemented.")

    def save(self, path: str) -> None:
        """Serialise model weights for edge deployment."""
        raise NotImplementedError("Model serialisation not yet implemented.")

    @classmethod
    def load(cls, path: str) -> "PersonalAnomalyModel":
        """Load a saved model."""
        raise NotImplementedError("Model loading not yet implemented.")

    def status(self) -> Dict[str, str]:
        """Return a status dict for the dashboard Hardware Roadmap section."""
        return {
            "status": "TINYML_ROADMAP",
            "subject_id": self.subject_id,
            "fitted": str(self.is_fitted),
            "description": (
                "The personalised anomaly model will be a shallow autoencoder "
                "trained on per-user baseline sessions and deployed to the "
                "nRF52840-class edge MCU in the SoleSense insole."
            ),
            "features": ", ".join(ANOMALY_FEATURES),
            "target_size": "< 256 KB flash",
            "target_latency": "< 10 ms per step",
        }


def fuse_scores(
    rule_score: float,
    anomaly_score: Optional[float],
    rule_weight: float = 0.7,
    anomaly_weight: float = 0.3,
) -> float:
    """
    Fuse rule-based risk score with anomaly model score.

    When anomaly_score is None (model not available), returns rule_score unchanged.

    Parameters
    ----------
    rule_score    : float 0–100 from risk_engine
    anomaly_score : float 0–1 from PersonalAnomalyModel, or None
    rule_weight / anomaly_weight : blend weights (must sum to 1.0)

    Returns
    -------
    Fused score 0–100.
    """
    if anomaly_score is None:
        return rule_score
    anomaly_scaled = anomaly_score * 100.0
    fused = rule_weight * rule_score + anomaly_weight * anomaly_scaled
    return float(np.clip(fused, 0.0, 100.0))
