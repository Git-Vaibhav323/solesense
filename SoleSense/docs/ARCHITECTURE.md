# SoleSense Architecture

## Current Pipeline (Dataset Prototype)

```
StepUP-P150 Dataset (.npz files)
            │
            ▼
    src/data_loader.py
    ─────────────────
    Normalised DataFrame:
    1 row = 1 footstep
    (subject_id, side, footwear, trial,
     timestamp, pressure_array [101×75×40 kPa])
            │
            ▼
    src/preprocessing.py
    ────────────────────
    - Exclude flagged steps (Exclude=1)
    - Stance duration filter (0.15–2.5 s)
    - Side normalization
    - Array shape & content validation
    - Missing-value audit
            │
            ▼
    src/feature_pipeline.py  (orchestrator)
            │
    ┌───────┼───────────────────────┐
    │       │                       │
    ▼       ▼                       ▼
pressure  gait_features.py  bilateral_features.py
features  ───────────────   ───────────────────────
.py       per-trial:        per-trial, per side:
          cadence           NSI asymmetry
          step time         directional asymmetry
          stride time       regional loading asym
          gait symmetry     loading fractions
          variability
    │
    ▼
temporal_features.py
────────────────────
Rolling window (5 steps):
  mean / max / std per feature
  persistence score per feature
            │
            ▼
    data/features/features.csv
    (1 row per footstep, 134 columns)
            │
            ▼
    src/risk_engine.py
    ──────────────────
    10 explainable rules → sub-scores
    Weighted sum → SoleSense Risk Indicator (0–100)
    RiskResult:
      risk_score
      risk_level (NORMAL/MONITOR/ALERT)
      affected_region
      contributing_factors  ← shown in dashboard
      recommended_action
            │
            ▼
    dashboard/app.py  (Streamlit + Plotly)
    ─────────────────────────────────────
    ① Overall Status       — gauge + risk level
    ② Foot Pressure        — regional loading bars
    ③ Left ↔ Right         — bilateral comparison
    ④ Temperature          — Hardware Roadmap placeholder
    ⑤ Gait                 — timing metrics
    ⑥ Pressure Map / CoP   — heatmap + trajectory
    ⑦ Explainable Risk     — factor-by-factor breakdown
    ⑧ Historical Trend     — risk over sessions
```

---

## Future Hardware Pipeline

```
SoleSense Physical Insole
  ├─ 8 pressure sensors (per foot)
  ├─ 8 temperature sensors (per foot)
  └─ 1 IMU (per foot)
  └─ nRF52840 edge MCU
            │
            ▼  (BLE / Serial / USB)
    src/data_loader.py   ← SWAP THIS MODULE
    (hardware sensor adapter)
            │
    [same preprocessing + feature engineering]
            │
            ▼
    src/anomaly_model.py  (PersonalAnomalyModel)
    ──────────────────────────────────────────
    Personal baseline (first N sessions)
            ↓
    Shallow autoencoder (fits in < 256 KB flash)
            ↓
    Reconstruction error per feature
            ↓
    Anomaly score (0–1)
            │
            ▼
    src/risk_engine.fuse_scores()
    ──────────────────────────────
    Rule-based score (70%)
  + Anomaly score (30%)
  = Fused SoleSense Risk Indicator
            │
            ▼
    dashboard/app.py   (same UI, live data)
            │
            ▼
    Ankle-cuff alert  (vibration / LED)
    (future firmware action)
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| One row per footstep (not per frame) | Clinically meaningful unit; aligns with dataset structure |
| Separate feature modules | Each module is independently testable and replaceable |
| Hardware-agnostic data adapter | `data_loader.py` is the only dataset-specific file |
| Rule-based risk engine (no black-box) | Explainability is a design requirement |
| No temperature fabrication | Dataset has no temperature; placeholder documents the gap honestly |
| Experimental thresholds labeled clearly | Avoids false clinical claims |
| NSI asymmetry formula | Standard biomechanics symmetry index; documented |
| Rolling persistence features | Distinguishes transient spikes from sustained loading patterns |

---

## Module Map

```
f:\Dataset\SoleSense\
├── config/
│   └── config.py            ← ALL configurable constants (thresholds, paths, etc.)
├── src/
│   ├── data_loader.py        ← DATA SOURCE ADAPTER — swap for hardware
│   ├── preprocessing.py      ← cleaning + validation
│   ├── pressure_features.py  ← basic stats, PTI, regions, CoP
│   ├── gait_features.py      ← cadence, stride, symmetry
│   ├── bilateral_features.py ← NSI asymmetry L↔R
│   ├── temporal_features.py  ← rolling window, persistence
│   ├── temperature_features.py ← HARDWARE ROADMAP placeholder
│   ├── feature_pipeline.py   ← orchestrator (run this to generate features.csv)
│   ├── risk_engine.py        ← explainable rule-based scoring
│   └── anomaly_model.py      ← TINYML ROADMAP placeholder
├── dashboard/
│   └── app.py                ← Streamlit dashboard
├── data/
│   ├── raw/                  ← (empty — raw data stays in original location)
│   ├── processed/            ← preprocessed_metadata.csv
│   └── features/             ← features.csv  ← PRIMARY OUTPUT
├── docs/
│   ├── DATASET_SUMMARY.md
│   ├── FEATURE_DICTIONARY.md
│   └── ARCHITECTURE.md  ← this file
├── tests/
│   ├── conftest.py
│   ├── test_preprocessing.py
│   ├── test_pressure_features.py
│   ├── test_bilateral_features.py
│   ├── test_gait_features.py
│   └── test_risk_engine.py
└── notebooks/
    └── 01_dataset_exploration.ipynb
```
