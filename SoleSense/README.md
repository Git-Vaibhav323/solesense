# SOLESENSE
### Personal Foot Loading & Gait Monitor — Research Prototype

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B?logo=streamlit&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-5.18%2B-3F4F75?logo=plotly&logoColor=white)
![Dataset](https://img.shields.io/badge/Dataset-StepUP--P150-green)
![License](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey)
![Status](https://img.shields.io/badge/Status-Research%20Prototype-orange)

> ⚠️ **Medical Disclaimer:** SoleSense is a **research prototype**. The SoleSense Risk
> Indicator is experimental and **not clinically validated**. It does **not** diagnose
> diabetes, neuropathy, foot ulcers, or any other medical condition. All thresholds are
> demo values unless stated otherwise.

---

## What is SoleSense?

SoleSense monitors foot loading and gait patterns to flag abnormal behaviour — elevated
pressure, bilateral asymmetry, forefoot overloading, irregular gait timing — before they
become a problem.

The **current build** runs entirely on the StepUP-P150 plantar pressure research dataset
(150 subjects, 100 Hz floor mat). The entire pipeline is designed so that swapping the
dataset for **live insole hardware** requires changing exactly one file.

```
Sense → Compare → Learn → Fuse → Act
```

**What it does today:**
- Loads and preprocesses high-resolution plantar pressure recordings (75×40 px per step)
- Extracts 134 biomechanically meaningful features per footstep
- Computes an explainable, rule-based SoleSense Risk Indicator (0–100)
- Provides a polished two-page Streamlit + Plotly dashboard:
  - **Quick Analysis** — type or slide sensor values, get a live risk result instantly
  - **Dataset Explorer** — full 8-section analysis of any subject/trial in the dataset

**What it does NOT do yet** (roadmap):
- Live BLE / serial hardware input
- Temperature sensing (no data in current dataset)
- IMU / accelerometry
- Trained ML model (TinyML autoencoder — see §15)
- Mobile app, ankle-cuff firmware, clinical diagnosis

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Dashboard Guide](#2-dashboard-guide)
3. [System Architecture](#3-system-architecture)
4. [Dataset](#4-dataset)
5. [Project Structure](#5-project-structure)
6. [Installation](#6-installation)
7. [Running the Feature Pipeline](#7-running-the-feature-pipeline)
8. [Using the API in Python](#8-using-the-api-in-python)
9. [Feature Engineering](#9-feature-engineering)
10. [Risk Engine](#10-risk-engine)
11. [Running Tests](#11-running-tests)
12. [Exploratory Notebook](#12-exploratory-notebook)
13. [Current Limitations](#13-current-limitations)
14. [Future Hardware Integration](#14-future-hardware-integration)
15. [TinyML Roadmap](#15-tinyml-roadmap)
16. [Configuration Reference](#16-configuration-reference)
17. [Dataset Citation](#17-dataset-citation)

---

## 1. Quick Start

> **Prerequisites:** Python 3.10+, pip, dataset downloaded to `F:\Dataset\`

```powershell
# 1. Install dependencies
cd f:\Dataset\SoleSense
pip install -r requirements.txt

# 2. Generate features (5 subjects, preferred walking speed — ~50 seconds)
python -m src.feature_pipeline --subjects 5 --trials W1

# 3. Launch the dashboard
python -m streamlit run dashboard/app.py
```

Open `http://localhost:8501` in your browser. Done.

> **Common mistake:** Running from `F:\Dataset` instead of `F:\Dataset\SoleSense` gives
> `ModuleNotFoundError: No module named 'src'`.  
> Fix: `cd f:\Dataset\SoleSense` first.

---

## 2. Dashboard Guide

The dashboard has two pages, switchable from the top navigation bar.

### 🏠 Page 1 — Quick Analysis *(live input, no dataset required)*

All controls live in the **left sidebar** — sliders for pressure, PTI, regional loading,
gait metrics and persistence. Every chart updates **instantly** as you move a slider.
No button click needed.

| Section | What you see |
|---|---|
| **Risk Banner** | NORMAL / MONITOR / ALERT with score 0–100 and affected region |
| **Metric Cards** | Left/Right peak pressure, PTI, cadence, gait symmetry — live |
| **① Risk & Bilateral Pressure** | Gauge + three bilateral bar charts (PTI, peak, stance) |
| **② Regional Loading — Desmos View** | Polar/radar bilateral comparison + dual donut regional chart |
| **③ Asymmetry Profile** | Waterfall bar chart — positive = left dominant, negative = right dominant |
| **④ Explainable Risk Breakdown** | Factor-by-factor explanation: which rules triggered and why |

**To test the live input:**
1. Launch the app on the Quick Analysis page
2. Drag **Left PTI** to max in the sidebar — the gauge jumps to ALERT 🚨 immediately
3. Set both feet equal — the asymmetry waterfall flattens to zero
4. Drag **Gait Symmetry Index** above 0.10 — the gait asymmetry factor triggers

---

### 📊 Page 2 — Dataset Explorer *(static StepUP-P150 data)*

Requires `features.csv` to exist (run step 2 from Quick Start above).

Use the **sidebar dropdowns** to filter: Subject → Footwear → Trial.

| Section | What you see |
|---|---|
| **① Overall Status** | Risk gauge, risk level, affected region, factor count, step-by-step risk sparkline |
| **② Foot Pressure** | Mean/peak/PTI/loading-rate cards + dual donut + regional bar chart |
| **③ Left ↔ Right Comparison** | Bilateral bar charts + polar radar + asymmetry waterfall |
| **④ Temperature** | Hardware Roadmap card — planned 8-site insole temperature |
| **⑤ Gait Metrics** | 8 gait cards + stance time per step line chart |
| **⑥ Pressure Map & CoP** | Plantar pressure heatmap + CoP trajectory (heel-strike → toe-off) |
| **⑦ Explainable Risk** | Full factor table with sub-scores + recommended action |
| **⑧ Historical Trend** | Risk score by trial/footwear + feature trend selector |

---

## 3. System Architecture

```
StepUP-P150 Dataset (.npz files)
            │
            ▼
    src/data_loader.py          ← DATA SOURCE ADAPTER
    ─────────────────              swap this one file for hardware
    Normalised DataFrame
    1 row = 1 footstep
            │
            ▼
    src/preprocessing.py
    ────────────────────
    Exclude flagged steps
    Stance duration filter (0.15 – 2.5 s)
    Side normalisation
    Array shape validation
            │
            ▼
    src/feature_pipeline.py     ← orchestrator
            │
     ┌──────┼──────────────────┬──────────────────┐
     ▼      ▼                  ▼                  ▼
pressure  gait_features   bilateral_features  temporal_features
 stats     per trial        NSI asymmetry       rolling window
 CoP       cadence          L ↔ R pressure      5-step history
 PTI       stride time      regional diff       persistence
 regions   symmetry idx     directional         score
            │
            ▼
    data/features/features.csv
    (134 columns · 1 row per footstep)
            │
            ▼
    src/risk_engine.py
    ──────────────────
    10 named explainable rules
    Weighted score → 0–100
    NORMAL / MONITOR / ALERT
            │
            ▼
    dashboard/app.py
    ────────────────────────────────
    Page 1: Quick Analysis  (live)
    Page 2: Dataset Explorer (static)
    Streamlit + Plotly
```

**Future hardware path — only `data_loader.py` changes:**

```
SoleSense Insole (nRF52840)
  8 pressure sites + 8 temp sites + IMU
            │  BLE / Serial
            ▼
    src/hardware_adapter.py     ← NEW file, same output schema
            │
    [preprocessing → features → risk engine → dashboard — all identical]
            │
            ▼
    src/anomaly_model.py        ← TinyML autoencoder
    Personalised anomaly score
            │
            ▼
    risk_engine.fuse_scores()
    Rule score + anomaly score
            │
            ▼
    dashboard/app.py            ← unchanged
            │
            ▼
    Ankle-cuff alert
```

---

## 4. Dataset

**StepUP-P150** — High-Resolution Plantar Pressure Measurements with Varying Footwear
Types and Walking Speeds for Gait Analysis and Recognition.

| Field | Detail |
|---|---|
| Institution | Health Technologies Lab, University of New Brunswick |
| Principal Investigator | Erik Scheme (escheme@unb.ca) |
| Collection period | 2023 – 2024 |
| Subjects | 150 (IDs 001 – 150) |
| Dataset DOI | https://doi.org/10.20383/103.01285 |
| Descriptor paper | https://doi.org/10.1038/s41597-025-05792-1 |
| License | CC BY 4.0 |
| Sensor | Stepscan Technologies piezoresistive floor mat |
| Platform | 3.6 m × 1.2 m · 4 sensors/cm² · 720×240 px |
| Footstep image | 75×40 px · 0.5 cm/px |
| Sampling rate | 100 Hz |
| Pressure unit | kPa |

### Trial conditions

**Walking (90 s each):**

| ID | Description |
|---|---|
| W1 | Preferred Speed Walking |
| W2 | Slow-to-Stop Walking |
| W3 | Slower than Preferred |
| W4 | Faster than Preferred |

**Balance (30 s each):**

| ID | Description |
|---|---|
| S1 | Both feet |
| S2 | Left foot only |
| S3 | Right foot only |

**Footwear:**

| ID | Description |
|---|---|
| BF | Barefoot / Sockfoot |
| ST | Standard Sneakers (Adidas Grand Court 2.0) |
| P1 | Participant's Own Footwear #1 |
| P2 | Participant's Own Footwear #2 |

### Files per walking trial

| File | Content | Shape |
|---|---|---|
| `metadata.csv` | Per-footstep labels, bounding boxes, side annotation | N rows × 22 cols |
| `trial.npz` | Full 90 s pressure recording | ~9000 × 720 × 240 |
| `pipeline_1.npz` | Extracted footsteps in kPa | N × 101 × 75 × 40 |
| `pipeline_2.npz` | Same, normalised 0–1 | N × 101 × 75 × 40 |

### Sensors available in this dataset

| Sensor | Available |
|---|---|
| Plantar pressure (spatial, kPa) | ✅ |
| Left / right foot label | ✅ |
| Foot dimensions (length, width) | ✅ |
| Stance timing (start/end frame at 100 Hz) | ✅ |
| Temperature | ❌ Future hardware |
| IMU / accelerometry | ❌ Future hardware |

---

## 5. Project Structure

```
SoleSense/
│
├── config/
│   └── config.py               ← all constants, thresholds, paths
│
├── src/
│   ├── data_loader.py          ← dataset adapter (swap for hardware)
│   ├── preprocessing.py        ← cleaning, validation, filtering
│   ├── pressure_features.py    ← stats, PTI, CoP, regional loading
│   ├── gait_features.py        ← cadence, stride, symmetry, variability
│   ├── bilateral_features.py   ← NSI asymmetry, directional comparison
│   ├── temporal_features.py    ← rolling window, persistence scoring
│   ├── temperature_features.py ← hardware roadmap placeholder
│   ├── risk_engine.py          ← explainable rule-based risk engine
│   ├── anomaly_model.py        ← TinyML autoencoder placeholder
│   └── feature_pipeline.py     ← orchestrator CLI
│
├── dashboard/
│   └── app.py                  ← two-page Streamlit + Plotly dashboard
│
├── data/
│   ├── raw/                    ← empty (raw data stays in original location)
│   ├── processed/              ← preprocessed_metadata.csv
│   └── features/
│       └── features.csv        ← PRIMARY OUTPUT (generated by pipeline)
│
├── notebooks/
│   └── 01_dataset_exploration.ipynb
│
├── models/                     ← future trained model files
│
├── docs/
│   ├── DATASET_SUMMARY.md
│   ├── FEATURE_DICTIONARY.md
│   ├── ARCHITECTURE.md
│   └── figures/                ← plots from notebook
│
├── tests/
│   ├── test_preprocessing.py
│   ├── test_pressure_features.py
│   ├── test_bilateral_features.py
│   ├── test_gait_features.py
│   └── test_risk_engine.py
│
├── requirements.txt
├── pytest.ini
└── README.md
```

---

## 6. Installation

**Requirements:** Python 3.10 or higher.

```powershell
cd f:\Dataset\SoleSense
pip install -r requirements.txt
```

| Package | Purpose |
|---|---|
| numpy, pandas | data handling |
| scipy | signal filtering |
| streamlit | dashboard server |
| plotly | interactive charts |
| matplotlib | notebook plots |
| pytest | test runner |
| jupyter | notebook support |

The original dataset files are **never modified**. SoleSense reads from them only.

---

## 7. Running the Feature Pipeline

### Fast demo (5 subjects, W1 only — ~50 seconds)

```powershell
cd f:\Dataset\SoleSense
python -m src.feature_pipeline --subjects 5 --trials W1
```

Produces `data/features/features.csv` with ~1,600 rows × 134 columns.

### Specific subjects and conditions

```powershell
python -m src.feature_pipeline --subjects 10 --footwear BF ST --trials W1 W2
```

### All 150 subjects, all conditions (~30 min, ~4 GB RAM)

```powershell
python -m src.feature_pipeline
```

### What the pipeline prints

```
INFO | Loading 5 subjects ...
INFO | Loaded 1793 footstep records across 5 subjects
INFO | Preprocessing: 1793 → 1648 rows (removed 145 = 8.1%)
INFO |   excluded_by_flag: 145
INFO | Pressure features: 1648 rows, 49 columns
INFO | After temporal features: 69 columns
INFO | Gait features: 20 trials
INFO | Bilateral features: 20 trials
INFO | Final feature table: 1648 rows × 134 columns
INFO | Pipeline completed in 50.7 seconds.
```

---

## 8. Using the API in Python

### Score an entire run

```python
from src.feature_pipeline import run_pipeline
from src.risk_engine import score_features_df

df     = run_pipeline(max_subjects=10, trial_list=["W1"])
scored = score_features_df(df)
print(scored[["subject_id", "side", "risk_score", "risk_level"]].head())
```

### Load a single trial with pressure arrays

```python
from src.data_loader import load_walking_trial

trial = load_walking_trial(
    subject_id="078",
    footwear="BF",
    trial="W1",
    include_pressure_arrays=True,
)
# 1 row per footstep
# trial["pressure_array"] → shape (101, 75, 40) kPa
```

### Score one feature row manually

```python
import pandas as pd
from src.risk_engine import compute_risk

row = pd.Series({
    "press_max_kpa": 320,
    "pti_total_kpa_s": 55000,
    "asym_pti_total_kpa_s": 25.0,
    "load_frac_forefoot": 0.55,
    "gait_symmetry_index": 0.08,
    "step_time_std_s": 0.12,
    "persistence_pti_total_kpa_s": 0.4,
})
result = compute_risk(row)
print(result.risk_level, result.risk_score)
print(result.contributing_factors)
```

---

## 9. Feature Engineering

134 features extracted per footstep. Full definitions in `docs/FEATURE_DICTIONARY.md`.

### Feature groups

| Group | Module | Features | Description |
|---|---|---|---|
| Pressure statistics | `pressure_features.py` | 9 | mean, max, std, percentiles, contact area |
| Pressure-Time Integral | `pressure_features.py` | 5 | PTI total, PTI/cm², loading rate |
| Regional loading | `pressure_features.py` | 12 | 4 regions × (fraction, absolute, peak) |
| Peak location | `pressure_features.py` | 5 | row, col, cm, frame of peak |
| Center of Pressure | `pressure_features.py` | 10 | start/end, excursion, path, velocity, ranges |
| Temporal / rolling | `temporal_features.py` | 20 | 5-step rolling mean/max/std + persistence |
| Gait timing | `gait_features.py` | 22 | cadence, stride, symmetry, variability |
| Bilateral asymmetry | `bilateral_features.py` | 51 | NSI + directional for all pressure features |

### Anatomical regions (normalised 75×40 px footstep)

```
Row  0–14  → Toe
Row 15–34  → Forefoot   (metatarsal heads)
Row 35–54  → Midfoot    (arch)
Row 55–74  → Rearfoot   (heel)
```

Row 0 = toe direction, row 74 = heel direction (verified from CoP progression).

### Pressure-Time Integral (PTI)

The core SoleSense loading metric. Captures cumulative exposure:

```
PTI = Σ (pressure_px_kPa × 0.01 s)  over all pixels and all frames
```

Repeated moderate loading is treated differently from a single spike.

### Asymmetry formula (NSI)

```
NSI = |L − R| / ((L + R) / 2) × 100%
```

Zero for perfect symmetry. Used for all bilateral comparisons.
Division-by-zero is protected throughout.

### Features not available in this dataset

| Feature | Reason | Plan |
|---|---|---|
| Temperature | Floor mat has no temp sensors | Hardware roadmap |
| IMU / swing phase | No accelerometry | Hardware roadmap |
| Step length / speed | No per-step position data | Hardware roadmap |
| Double support time | No simultaneous bilateral | Hardware roadmap |

---

## 10. Risk Engine

10 named rules. Fully explainable — no black box.

### Rules and weights

| Rule | Feature | Threshold | Weight |
|---|---|---|---|
| Peak pressure | `press_max_kpa` | 200 kPa | 25 |
| Pressure-time exposure | `pti_total_kpa_s` | 50 000 kPa·s | 25 |
| Loading asymmetry | `asym_pti_total_kpa_s` | 20% | 20 |
| Pressure asymmetry | `asym_press_mean_kpa` | 10% | 15 |
| Forefoot overload | `load_frac_forefoot` | 60% | 15 |
| Rearfoot overload | `load_frac_rearfoot` | 65% | 10 |
| Gait variability | `step_time_std_s` | 0.15 s | 15 |
| Gait asymmetry | `gait_symmetry_index` | 0.10 | 10 |
| Persistent pressure | `persistence_pti_total_kpa_s` | 60% of steps | 20 |
| Persistent asymmetry | `asym_load_forefoot` | 20% | 15 |

Score = `(triggered weights / 170) × 100`, capped at 100.

### Risk levels

| Level | Score | Meaning |
|---|---|---|
| NORMAL | 0 – 29 | No significant concerns |
| MONITOR | 30 – 59 | One or more elevated features |
| ALERT | 60 – 100 | Multiple elevated features — review recommended |

### Output structure

```python
{
    "risk_score": 42.3,
    "risk_level": "MONITOR",
    "affected_region": "LEFT_FOREFOOT",
    "contributing_factors": [
        "Elevated peak pressure",
        "High pressure-time exposure"
    ],
    "recommended_action": "Monitor loading patterns across sessions..."
}
```

### Changing thresholds

All thresholds are in one place — `config/config.py`. Edit and rerun.
No other files change.

---

## 11. Running Tests

```powershell
cd f:\Dataset\SoleSense
python -m pytest tests/ -v
```

78 tests, expected result: `78 passed`.

| Test file | Covers |
|---|---|
| `test_preprocessing.py` | Exclusion flags, stance filter, duplicates, NaN handling |
| `test_pressure_features.py` | Stats, PTI scaling, regional fractions sum to 1, CoP, edge cases |
| `test_bilateral_features.py` | NSI formula, division-by-zero, symmetric = 0%, asymmetric detected |
| `test_gait_features.py` | Cadence, stride time, symmetry index, step count |
| `test_risk_engine.py` | Score bounds, NaN safety, missing feature graceful skip, batch scoring |

---

## 12. Exploratory Notebook

```powershell
cd f:\Dataset\SoleSense
jupyter notebook notebooks/01_dataset_exploration.ipynb
```

Run all cells top to bottom. Saves 10 figures to `docs/figures/`:

| Figure | Content |
|---|---|
| `01_raw_pressure_signal.png` | Force-time curve + peak pressure frame |
| `02_pressure_distributions.png` | Peak pressure and PTI by footwear and side |
| `03_plantar_pressure_heatmap.png` | Mean pressure maps, L vs R |
| `04_regional_loading.png` | Regional load fractions by footwear condition |
| `05_gait_timing.png` | Cadence, stance time, symmetry distributions |
| `06_left_right_comparison.png` | L vs R scatter + asymmetry distribution |
| `07_cop_trajectories.png` | CoP paths for 6 footsteps |
| `08_missing_values.png` | Missing value audit (only if values are missing) |
| `09_feature_correlation.png` | Pearson correlation matrix |
| `10_risk_score_distribution.png` | Risk score histogram by footwear |

---

## 13. Current Limitations

| Limitation | Detail |
|---|---|
| No temperature data | StepUP-P150 is a pure pressure dataset. Temperature is a hardware feature. |
| No IMU data | Swing phase and double support time cannot be derived. |
| Floor mat, not wearable | Data from a fixed 3.6 m platform. Future hardware is a continuous insole. |
| Sequential bilateral | Left/right steps are captured sequentially, not simultaneously. |
| Experimental thresholds | All risk thresholds in `config/config.py` are demo values based on data distribution, not clinical standards. |
| No trained ML model | The risk engine is purely rule-based. TinyML is roadmap only. |
| Default run is 5 subjects | Use `python -m src.feature_pipeline` (no flags) for all 150. |
| Demographic metadata | `participant_metadata.csv` (age, BMI, etc.) was not included in this archive download. |

---

## 14. Future Hardware Integration

### Planned SoleSense insole hardware

| Component | Specification |
|---|---|
| Insoles | 2 (left + right), bilateral simultaneous |
| Pressure sites | 8 per insole |
| Temperature sites | 8 per insole |
| IMU | 1 per insole (accelerometer + gyroscope) |
| Edge MCU | nRF52840-class |
| Connectivity | BLE to host device |
| Alert | Ankle-cuff vibration / LED |

### How to plug in hardware — one file changes

Replace `src/data_loader.py` with a hardware adapter that reads from the insole serial/BLE
stream and returns a DataFrame with this schema:

```python
# Required columns — match these exactly
{
    "subject_id":       str,
    "footwear":         str,
    "trial":            str,
    "footstep_id":      int,
    "side":             str,   # "Left" or "Right"
    "start_frame":      int,
    "end_frame":        int,
    "stance_time_s":    float,
    "foot_length_cm":   float,
    "foot_width_cm":    float,
    "pressure_array":   np.ndarray,  # shape (101, 75, 40), kPa
}
```

Everything downstream — preprocessing, feature modules, risk engine, dashboard — stays
identical.

### New features unlocked by hardware

| Feature | Source signal |
|---|---|
| `mean_temp_left_c` | 8-site temperature, left insole |
| `delta_temp_c` | bilateral ΔT (L − R) |
| `temp_persistence_score` | rolling thermal asymmetry |
| `swing_time_s` | IMU + bilateral timing |
| `double_support_time_s` | bilateral simultaneous |
| `step_length_cm` | IMU integration |
| `walking_speed_m_s` | IMU integration |

These are already declared as placeholders in `src/temperature_features.py`
and `src/anomaly_model.py`.

---

## 15. TinyML Roadmap

`src/anomaly_model.py` defines the API. The model is not yet trained.

**Planned architecture:**

```
First N sessions per user  →  personal baseline
            ↓
Shallow autoencoder
50 features → 16 → 8 → 16 → 50
            ↓
Reconstruction error per feature
            ↓
Anomaly score = error / (baseline_mean + k × baseline_std)
            ↓
fuse_scores(rule_score=0.7, anomaly_score=0.3)
            ↓
Final SoleSense Risk Indicator
```

**Edge deployment targets:**

| Constraint | Target |
|---|---|
| Flash size | < 256 KB (nRF52840) |
| Inference time | < 10 ms per step |
| Format | TFLite Micro or CMSIS-NN |
| Training | Per-user, on first N sessions |

**8 features selected for edge efficiency:**

```
press_max_kpa          pti_total_kpa_s
load_frac_forefoot     load_frac_rearfoot
cop_path_length_cm     stance_time_s
asym_pti_total_kpa_s   gait_symmetry_index
```

Implement `PersonalAnomalyModel.fit()` and `.predict()` in `src/anomaly_model.py`.

---

## 16. Configuration Reference

All constants in **one file**: `config/config.py`

```python
# Sensor
SAMPLING_RATE_HZ = 100
CM_PER_PX        = 0.5
FOOTSTEP_ROWS    = 75
FOOTSTEP_COLS    = 40

# Anatomical regions (row ranges in 75-row footstep)
REGIONS = {
    "TOE":      (0,  14),
    "FOREFOOT": (15, 34),
    "MIDFOOT":  (35, 54),
    "REARFOOT": (55, 74),
}

# Preprocessing
EXCLUDE_FLAGGED_STEPS  = True
MIN_STANCE_DURATION_S  = 0.15
MAX_STANCE_DURATION_S  = 2.5

# Risk thresholds — EXPERIMENTAL, edit freely
RISK_PRESSURE_HIGH_KPA      = 200.0
RISK_PRESSURE_EXPOSURE_HIGH = 50000.0
RISK_ASYMMETRY_HIGH_PCT     = 20.0
RISK_ASYMMETRY_MODERATE_PCT = 10.0
RISK_GAIT_VARIABILITY_HIGH_S = 0.15
RISK_REGIONAL_LOADING_HIGH  = 0.6
RISK_LEVEL_MONITOR          = 30
RISK_LEVEL_ALERT            = 60
```

---

## 17. Dataset Citation

If you use StepUP-P150 in any publication, please cite both:

**Dataset:**
> Larracy, R.; Phinyomark, A.; Salehi, A.; MacDonald, E.; Kazemi, S.; Shafiul Bashar, S.;
> Tabor, A.; Scheme, E. (2025). *StepUP-P150: A Dataset of High-Resolution Plantar Pressure
> Measurements with Varying Footwear Types and Walking Speeds for Gait Analysis and
> Recognition.* Federated Research Data Repository.  
> doi: https://doi.org/10.20383/103.01285

**Descriptor paper:**
> Larracy, R., Phinyomark, A., Salehi, A., MacDonald, E., Kazemi, S., Bashar, S. S.,
> Tabor, A., & Scheme, E. (2025). A dataset of high-resolution plantar pressures for gait
> analysis across varying footwear and walking speeds. *Scientific Data* 12, 1415.  
> https://doi.org/10.1038/s41597-025-05792-1

---

<p align="center">
  <b>SoleSense</b> · Research Prototype · Not a medical device<br>
  Dataset: StepUP-P150 (CC BY 4.0) · University of New Brunswick 2023–2024
</p>
