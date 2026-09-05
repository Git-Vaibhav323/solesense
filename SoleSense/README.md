# SoleSense

**Personal Foot Loading & Gait Monitor — Research Prototype**

> ⚠ SoleSense is a research prototype. The SoleSense Risk Indicator is not clinically validated and does not diagnose any medical condition.

---

## 1. Project Purpose

SoleSense is a prototype for continuous foot-loading and gait-risk monitoring. The current build processes a plantar pressure dataset to extract biomechanically meaningful features, computes an explainable risk indicator, and presents findings in a polished research dashboard.

The architecture is designed so that the same software pipeline can later accept live data from physical SoleSense insoles without rewriting the dashboard or feature modules.

---

## 2. Dataset

**StepUP-P150** — A Dataset of High-Resolution Plantar Pressure Measurements with Varying Footwear Types and Walking Speeds for Gait Analysis and Recognition.

- **Source:** University of New Brunswick, Health Technologies Lab
- **DOI:** https://doi.org/10.20383/103.01285
- **Subjects:** 150 participants
- **Conditions:** 4 footwear × 7 trials (4 walking speeds + 3 balance tasks)
- **Sensor:** Stepscan piezoresistive floor mat, 100 Hz, kPa
- **License:** CC BY 4.0

See `docs/DATASET_SUMMARY.md` for full schema.

---

## 3. Dataset Structure (on disk)

```
FRDR_dataset_1280_download_590_202609031103/
└── py/
    └── {001..150}/          ← subject ID
        └── {BF,ST,P1,P2}/   ← footwear condition
            └── {S1,S2,S3,W1,W2,W3,W4}/   ← trial
                ├── metadata.csv       ← per-footstep labels (walking only)
                ├── trial.npz          ← full recording tensor
                ├── pipeline_1.npz     ← extracted footsteps, kPa
                └── pipeline_2.npz     ← same, normalised [0,1]
```

---

## 4. Installation

```bash
pip install -r requirements.txt
```

Requires Python 3.10+.

---

## 5. Running Feature Engineering

Process 5 subjects, W1 trial only (fast demo):

```bash
cd f:/Dataset/SoleSense
python -m src.feature_pipeline --subjects 5 --trials W1
```

Process all 150 subjects (takes ~30 min):

```bash
python -m src.feature_pipeline
```

Output: `data/features/features.csv` (134 columns, one row per footstep).

---

## 6. Generating Features

The pipeline runs these steps automatically:

1. **Load** — `src/data_loader.py` reads `.npz` and `metadata.csv` files
2. **Preprocess** — `src/preprocessing.py` removes excluded/invalid steps
3. **Pressure features** — `src/pressure_features.py` (stats, PTI, regional, CoP)
4. **Temporal features** — `src/temporal_features.py` (rolling window, persistence)
5. **Gait features** — `src/gait_features.py` (cadence, stride, symmetry)
6. **Bilateral features** — `src/bilateral_features.py` (L/R asymmetry)
7. **Join & save** → `data/features/features.csv`

---

## 7. Launching the Dashboard

```bash
cd f:/Dataset/SoleSense
streamlit run dashboard/app.py
```

Open `http://localhost:8501` in your browser.

The dashboard requires `data/features/features.csv` to exist (run the pipeline first).

---

## 8. Dashboard Interpretation

| Section | What it shows |
|---|---|
| Overall Status | SoleSense Risk Indicator gauge (0–100), risk level, affected region |
| Foot Pressure | Mean/peak pressure, PTI, regional loading bars per side |
| Left ↔ Right | Bilateral comparison of PTI, peak pressure, stance time, NSI asymmetry |
| Temperature | Hardware Roadmap placeholder (no temperature in dataset) |
| Gait | Cadence, step time, stride time, symmetry index, variability |
| Pressure Map / CoP | Plantar heatmap + Center of Pressure trajectory |
| Explainable Risk | Factor-by-factor breakdown of WHY the indicator is elevated |
| Historical Trend | Risk scores and feature trends across footwear conditions |

---

## 9. Current Limitations

- **No temperature data** — StepUP-P150 is a pure pressure dataset. Temperature is a planned hardware feature.
- **No IMU data** — No accelerometry or gyroscopy available. Swing phase cannot be derived.
- **Floor mat, not wearable** — Data was captured on a 3.6 m floor mat. The insole hardware will provide per-step data continuously.
- **No bilateral simultaneous measurement** — Left and right footsteps are captured sequentially, not synchronously.
- **5 subjects in default features.csv** — Run `--subjects 150` for the full dataset (large memory requirement).
- **Experimental thresholds** — All risk thresholds in `config/config.py` are demo values, not clinically validated.

---

## 10. Future Hardware Integration

To replace the dataset with live insole data:

1. **Replace `src/data_loader.py`** (or add a new adapter `src/hardware_adapter.py`)
2. The adapter must return a DataFrame with the same schema as `load_walking_trial()`
3. All downstream modules (preprocessing → features → risk engine → dashboard) remain unchanged
4. Update `dashboard/app.py`'s `load_features()` function to call the new adapter

Planned insole hardware:
- 8 pressure sensing sites per foot
- 8 temperature sensing sites per foot
- 1 IMU per foot (acceleration + gyroscope)
- nRF52840-class MCU
- BLE transmission to host

---

## 11. TinyML Roadmap

See `src/anomaly_model.py` for the planned personalised anomaly detection interface.

Planned model: shallow autoencoder (50 → 8 → 50 features), trained per user on baseline sessions.

Target: < 256 KB flash, < 10 ms inference on Cortex-M4.

Fusion: `risk_engine.fuse_scores(rule_score, anomaly_score)` (70% rule / 30% anomaly).

---

## 12. Running Tests

```bash
cd f:/Dataset/SoleSense
python -m pytest tests/ --override-ini="addopts=" -v
```

104 tests covering preprocessing, pressure features, bilateral asymmetry, gait features, and risk scoring.

---

## Citation

If you use the StepUP-P150 dataset, please cite:

> Larracy, R., Phinyomark, A., Salehi, A., MacDonald, E., Kazemi, S., Shafiul Bashar, S., Tabor, A., & Scheme, E. (2025). A dataset of high-resolution plantar pressures for gait analysis across varying footwear and walking speeds. *Scientific Data* 12, 1415. https://doi.org/10.1038/s41597-025-05792-1
