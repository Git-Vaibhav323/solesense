# SOLESENSE
### Personal Foot Loading & Gait Monitor — Research Prototype

> ⚠️ **Disclaimer:** SoleSense is a research prototype. The SoleSense Risk Indicator is experimental and not clinically validated. This system does **not** diagnose diabetes, diabetic neuropathy, foot ulcers, or any other medical condition. All thresholds are demo values unless explicitly stated otherwise.

---

## Table of Contents

1. [What is SoleSense?](#1-what-is-solesense)
2. [System Architecture](#2-system-architecture)
3. [Dataset](#3-dataset)
4. [Project Structure](#4-project-structure)
5. [Installation](#5-installation)
6. [Quick Start — Run Everything](#6-quick-start--run-everything)
7. [Step-by-Step Usage](#7-step-by-step-usage)
8. [Dashboard Guide](#8-dashboard-guide)
9. [Feature Engineering](#9-feature-engineering)
10. [Risk Engine](#10-risk-engine)
11. [Running Tests](#11-running-tests)
12. [Exploratory Notebook](#12-exploratory-notebook)
13. [Current Limitations](#13-current-limitations)
14. [Future Hardware Integration](#14-future-hardware-integration)
15. [TinyML Roadmap](#15-tinyml-roadmap)
16. [Configuration](#16-configuration)
17. [Dataset Citation](#17-dataset-citation)

---

## 1. What is SoleSense?

SoleSense monitors foot loading and gait patterns to flag abnormal behaviour — elevated pressure, bilateral asymmetry, forefoot overloading, gait irregularity — before they become a problem.

The **current build** runs entirely on the StepUP-P150 plantar pressure research dataset. The pipeline is designed from the start so that swapping the dataset for **live insole hardware** requires changing only one file (`src/data_loader.py`).

**What it does now:**
- Loads and preprocesses plantar pressure recordings for 150 subjects
- Extracts 134 biomechanically meaningful features per footstep
- Computes an explainable, rule-based SoleSense Risk Indicator
- Presents everything in a polished Streamlit + Plotly dashboard

**What it intentionally does NOT do yet:**
- Live BLE / serial hardware input (roadmap)
- Temperature sensing (hardware roadmap — no data in current dataset)
- IMU / accelerometry (hardware roadmap)
- Trained ML model (TinyML roadmap — see §15)
- Mobile app, ankle-cuff firmware, clinical diagnosis

**Conceptual pipeline:**
```
Sense → Compare → Learn → Fuse → Act
```

---

## 2. System Architecture

```
StepUP-P150 Dataset (.npz files)
            │
            ▼
    src/data_loader.py          ← DATA SOURCE ADAPTER
    ─────────────────              (swap this for hardware)
    Normalised DataFrame
    1 row = 1 footstep
            │
            ▼
    src/preprocessing.py
    ────────────────────
    Exclude flagged steps
    Stance duration filter
    Side normalisation
    Array validation
            │
            ▼
    src/feature_pipeline.py     ← orchestrator
            │
     ┌──────┼──────────────────┐
     ▼      ▼                  ▼
pressure  gait_features   bilateral_features
features  per trial        NSI asymmetry L↔R
CoP       cadence/stride   regional loading
PTI       symmetry index   directional diff
     │
     ▼
temporal_features
Rolling window (5 steps)
Persistence scoring
            │
            ▼
    data/features/features.csv
    (134 columns, 1 row/footstep)
            │
            ▼
    src/risk_engine.py
    ──────────────────
    10 explainable rules
    Weighted score 0–100
    NORMAL / MONITOR / ALERT
            │
            ▼
    dashboard/app.py
    ────────────────
    Streamlit + Plotly
    8 dashboard sections
```

**Future hardware path** — only `data_loader.py` changes:
```
SoleSense Insole (nRF52840)
  8 pressure sites + 8 temp sites + IMU
            │  BLE / Serial
            ▼
    src/hardware_adapter.py     ← NEW, same output schema
            │
    [everything else identical]
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

## 3. Dataset

**StepUP-P150** — A Dataset of High-Resolution Plantar Pressure Measurements with Varying Footwear Types and Walking Speeds for Gait Analysis and Recognition

| Field | Detail |
|---|---|
| **Institution** | Health Technologies Lab, University of New Brunswick |
| **Principal Investigator** | Erik Scheme (escheme@unb.ca) |
| **Collection period** | 2023 – 2024 |
| **Subjects** | 150 participants (IDs 001 – 150) |
| **Dataset DOI** | https://doi.org/10.20383/103.01285 |
| **Descriptor paper** | https://doi.org/10.1038/s41597-025-05792-1 |
| **License** | CC BY 4.0 |
| **Sensor** | Stepscan Technologies Inc. piezoresistive floor mat |
| **Platform size** | 3.6 m × 1.2 m |
| **Sensor density** | 4 sensors/cm² (2 per cm per axis) |
| **Full resolution** | 720 × 240 pixels |
| **Pixel size** | 0.5 cm × 0.5 cm = 0.25 cm² |
| **Sampling rate** | 100 Hz |
| **Pressure unit** | kPa |

### Trial conditions

**Walking speeds:**

| ID | Description |
|---|---|
| W1 | Preferred Speed Walking |
| W2 | Slow-to-Stop Walking |
| W3 | Slower than Preferred Walking |
| W4 | Faster than Preferred Walking |

**Balance tasks:**

| ID | Description |
|---|---|
| S1 | Balancing on Both Feet |
| S2 | Balancing on Left Foot |
| S3 | Balancing on Right Foot |

**Footwear conditions:**

| ID | Description |
|---|---|
| BF | Without Footwear (Barefoot or Sockfoot) |
| ST | Standard Sneakers (Adidas Grand Court 2.0) |
| P1 | Participant's First Pair of Personal Footwear |
| P2 | Participant's Second Pair of Personal Footwear |

### Dataset folder structure (on disk)

```
FRDR_dataset_1280_download_590_202609031103/
└── py/
    └── {001..150}/               ← subject ID
        └── {BF, ST, P1, P2}/     ← footwear condition
            ├── S1/               ← balance trial
            │   ├── trial.npz           full 30s recording (3000×720×240)
            │   └── preprocessed.npz    cropped/aligned (3000×180×180)
            ├── S2/
            ├── S3/
            ├── W1/               ← walking trial
            │   ├── metadata.csv        per-footstep labels (22 columns)
            │   ├── trial.npz           full 90s recording (~9000×720×240)
            │   ├── pipeline_1.npz      extracted footsteps in kPa (N×101×75×40)
            │   └── pipeline_2.npz      same, normalised 0–1
            ├── W2/
            ├── W3/
            └── W4/
```

### What sensors are available

| Sensor | Available | Notes |
|---|---|---|
| Plantar pressure (spatial) | ✅ YES | 75×40 px per footstep, kPa |
| Left / right foot label | ✅ YES | `Side` column in metadata.csv |
| Foot dimensions | ✅ YES | FootLength, FootWidth in px |
| Stance timing | ✅ YES | StartFrame / EndFrame at 100 Hz |
| Temperature | ❌ NOT PRESENT | Future SoleSense hardware feature |
| IMU / accelerometry | ❌ NOT PRESENT | Future SoleSense hardware feature |

---

## 4. Project Structure

```
SoleSense/
│
├── config/
│   └── config.py               ← ALL constants, thresholds, paths (edit here)
│
├── src/
│   ├── __init__.py
│   ├── data_loader.py          ← dataset adapter (swap for hardware)
│   ├── preprocessing.py        ← cleaning, validation, filtering
│   ├── pressure_features.py    ← stats, PTI, regional loading, CoP
│   ├── gait_features.py        ← cadence, stride, symmetry, variability
│   ├── bilateral_features.py   ← NSI asymmetry, directional comparison
│   ├── temporal_features.py    ← rolling window, persistence scoring
│   ├── temperature_features.py ← hardware roadmap placeholder
│   ├── risk_engine.py          ← explainable rule-based risk indicator
│   ├── anomaly_model.py        ← TinyML autoencoder placeholder
│   └── feature_pipeline.py     ← orchestrator (run this to generate features)
│
├── dashboard/
│   └── app.py                  ← Streamlit + Plotly dashboard
│
├── data/
│   ├── raw/                    ← (empty — raw data stays in original location)
│   ├── processed/              ← preprocessed_metadata.csv (generated)
│   └── features/
│       └── features.csv        ← PRIMARY OUTPUT of the pipeline
│
├── notebooks/
│   └── 01_dataset_exploration.ipynb
│
├── models/                     ← future trained model files
│
├── docs/
│   ├── DATASET_SUMMARY.md      ← full dataset schema reference
│   ├── FEATURE_DICTIONARY.md   ← every feature explained
│   ├── ARCHITECTURE.md         ← system design diagrams
│   └── figures/                ← plots generated by notebook
│
├── tests/
│   ├── conftest.py
│   ├── test_preprocessing.py
│   ├── test_pressure_features.py
│   ├── test_bilateral_features.py
│   ├── test_gait_features.py
│   └── test_risk_engine.py
│
├── requirements.txt
├── pytest.ini
└── README.md                   ← this file
```

---

## 5. Installation

**Requirements:** Python 3.10 or higher.

```powershell
cd f:\Dataset\SoleSense
pip install -r requirements.txt
```

**What gets installed:**

| Package | Purpose |
|---|---|
| numpy, pandas | data handling |
| streamlit | dashboard server |
| plotly | interactive charts |
| matplotlib | notebook plots |
| scipy | signal processing |
| pytest | test runner |
| jupyter | notebook support |

The original dataset files are **never modified**. SoleSense only reads from them.

---

## 6. Quick Start — Run Everything

Open one PowerShell window, run these two commands in order:

```powershell
# Step 1 — generate features (one time, ~50 seconds for 5 subjects)
cd f:\Dataset\SoleSense
python -m src.feature_pipeline --subjects 5 --trials W1

# Step 2 — launch the dashboard
streamlit run dashboard/app.py
```

Browser opens at `http://localhost:8501`. Done.

---

## 7. Step-by-Step Usage

### 7.1 Generate features

**Fast demo — 5 subjects, W1 (preferred walking speed) only:**
```powershell
python -m src.feature_pipeline --subjects 5 --trials W1
```
Takes ~50 seconds. Produces `data/features/features.csv` with ~1600 rows × 134 columns.

**Specific footwear only:**
```powershell
python -m src.feature_pipeline --subjects 10 --footwear BF ST --trials W1 W2
```

**All 150 subjects, all conditions** (takes ~30 min, ~4 GB RAM):
```powershell
python -m src.feature_pipeline
```

**What the pipeline prints as it runs:**
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

### 7.2 Launch the dashboard

```powershell
streamlit run dashboard/app.py
```

- Opens at `http://localhost:8501`
- Use the **sidebar** to pick subject, footwear, and trial
- Dashboard updates live
- Press `Ctrl+C` in the terminal to stop

### 7.3 Use the pipeline in Python code

```python
from src.feature_pipeline import run_pipeline
from src.risk_engine import score_features_df

# Generate features for 10 subjects
df = run_pipeline(max_subjects=10, trial_list=['W1'])

# Score every footstep
scored = score_features_df(df)
print(scored[['subject_id', 'side', 'risk_score', 'risk_level']].head())
```

### 7.4 Load a single trial

```python
from src.data_loader import load_walking_trial

trial = load_walking_trial(
    subject_id='078',
    footwear='BF',
    trial='W1',
    include_pressure_arrays=True
)
# trial is a DataFrame: 1 row per footstep
# trial['pressure_array'] contains shape (101, 75, 40) kPa arrays
```

---

## 8. Dashboard Guide

Launch with `streamlit run dashboard/app.py`.

Use the left sidebar to select **Subject → Footwear → Trial**.

### Section ① Overall Status
The first thing you see. Shows:
- **SoleSense Risk Indicator** — gauge from 0 to 100
- **Risk Level** — NORMAL / MONITOR / ALERT (colour coded green / orange / red)
- **Most Affected Region** — e.g. LEFT_FOREFOOT
- **Contributing Factors** — count of triggered risk rules
- **Steps Analysed** — footstep count for this trial

### Section ② Foot Pressure
- Mean and peak pressure per side (kPa)
- Pressure-Time Integral (PTI) per side — the cumulative loading burden
- Loading rate (how fast force rises at heel-strike)
- **Regional loading bar chart** — how load is distributed across Toe / Forefoot / Midfoot / Rearfoot for Left vs Right

### Section ③ Left ↔ Right Comparison
- Side-by-side bar charts: PTI, peak pressure, stance duration
- **Asymmetry overview** — five asymmetry metrics shown as bars with threshold lines at 10% (moderate) and 20% (high)
- Asymmetry formula: `NSI = |L − R| / ((L + R) / 2) × 100%`

### Section ④ Temperature — Hardware Roadmap
Temperature sensing is **not in the dataset**. This section shows a clearly labelled placeholder explaining the planned 8-site bilateral temperature monitoring in the SoleSense insole hardware.

### Section ⑤ Gait
Twelve gait metrics including:
- Cadence (steps/min)
- Mean step time and its coefficient of variation
- Left and right stride times
- Stance fraction (expected ~60% in normal gait)
- Gait Symmetry Index
- Step-by-step stance time chart (Left vs Right over the trial)

### Section ⑥ Pressure Map & CoP Trajectory
- **Plantar heatmap** — mean pressure map for Left and Right foot, with anatomical region lines
- **Center of Pressure trajectory** — path from heel-strike (green circle) to toe-off (red triangle) overlaid on the pressure image

### Section ⑦ Explainable Risk
The most important section. Shows exactly **why** the risk indicator is at its current level — factor by factor:

```
⚠️  Elevated peak pressure         +25 pts   Peak 347 kPa > threshold 200 kPa
⚠️  High pressure-time exposure    +25 pts   PTI 52000 kPa·s > threshold 50000
✅  Loading asymmetry                0 pts   Asymmetry 8.2% below threshold 20%
✅  Gait temporal variability        0 pts   Step CV 0.09 below threshold 0.15
```

Followed by the recommended action text. All thresholds are clearly marked as experimental.

### Section ⑧ Historical Trend
- Risk score trend across footwear conditions (BF / ST / P1 / P2) for the selected subject
- Feature trend tab: pick any key feature and see how it varies across conditions
- MONITOR and ALERT threshold lines drawn on the chart

---

## 9. Feature Engineering

134 features are extracted per footstep. Full definitions in `docs/FEATURE_DICTIONARY.md`.

### Feature groups

| Group | Module | Count | Description |
|---|---|---|---|
| Pressure statistics | `pressure_features.py` | 9 | mean, max, std, percentiles, contact area |
| Pressure-Time Integral | `pressure_features.py` | 5 | PTI total, PTI/cm², loading rate, forces |
| Regional loading | `pressure_features.py` | 12 | 4 regions × (fraction, absolute, peak) |
| Peak location | `pressure_features.py` | 5 | row, col, cm, frame of global peak |
| Center of Pressure | `pressure_features.py` | 10 | start, end, excursion, path, velocity, ranges |
| Temporal / rolling | `temporal_features.py` | 20 | 5-step rolling mean/max/std + persistence |
| Gait timing | `gait_features.py` | 22 | cadence, stride, symmetry, variability |
| Bilateral asymmetry | `bilateral_features.py` | 51 | NSI + directional for all pressure features |

### Anatomical regions (normalised 75×40 px footstep image)

```
Row 0  ─── Toe      (rows  0–14)
Row 15 ─── Forefoot (rows 15–34)  ← metatarsal heads
Row 35 ─── Midfoot  (rows 35–54)  ← arch
Row 55 ─── Rearfoot (rows 55–74)  ← heel
Row 74
```

Row 0 = toe direction, row 74 = heel direction (verified from CoP progression during stance).

### Pressure-Time Integral

PTI is the core SoleSense loading metric:

```
PTI = Σ (pressure_pixel_kPa × 0.01s)  over all pixels, all frames
```

It captures cumulative exposure — repeated moderate loading is treated differently from a single spike.

### Features NOT available in this dataset

| Feature | Reason | Status |
|---|---|---|
| Temperature | Floor mat has no temperature sensors | Hardware roadmap |
| IMU / swing phase | No accelerometry in dataset | Hardware roadmap |
| Step length / walking speed | No per-step position data | Hardware roadmap |
| Double support time | Requires bilateral simultaneous capture | Hardware roadmap |

---

## 10. Risk Engine

The risk engine (`src/risk_engine.py`) is fully explainable — no black box.

### How it works

10 named rules. Each rule checks one feature against one threshold:

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

Triggered rules add their weight to the score. Final score = `(sum / 170) × 100`, capped at 100.

### Risk levels

| Level | Score | Meaning |
|---|---|---|
| NORMAL | 0 – 29 | No significant concerns detected |
| MONITOR | 30 – 59 | One or more elevated features — watch closely |
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

All thresholds live in one place — `config/config.py`:

```python
RISK_PRESSURE_HIGH_KPA = 200.0
RISK_PRESSURE_EXPOSURE_HIGH = 50000.0
RISK_ASYMMETRY_HIGH_PCT = 20.0
RISK_ASYMMETRY_MODERATE_PCT = 10.0
RISK_GAIT_VARIABILITY_HIGH_S = 0.15
RISK_REGIONAL_LOADING_HIGH = 0.6
RISK_LEVEL_MONITOR = 30
RISK_LEVEL_ALERT = 60
```

Edit these values and rerun the dashboard — no other files need to change.

---

## 11. Running Tests

```powershell
cd f:\Dataset\SoleSense
python -m pytest tests/ --override-ini="addopts=" -v
```

78 tests covering:

| Test file | What it tests |
|---|---|
| `test_preprocessing.py` | Exclusion flags, stance filter, duplicate removal, side normalisation, array validation, NaN handling |
| `test_pressure_features.py` | Basic stats, PTI scaling, regional fractions sum to 1, CoP computation, zero-array edge cases |
| `test_bilateral_features.py` | NSI formula, division-by-zero safety, symmetric data gives 0%, asymmetric data detected correctly |
| `test_gait_features.py` | Cadence accuracy, stride time, symmetry index, step count |
| `test_risk_engine.py` | Score bounds (0–100), NaN safety, missing features graceful skip, batch scoring, trial summary |

Expected output:
```
78 passed in 4.34s
```

---

## 12. Exploratory Notebook

```powershell
cd f:\Dataset\SoleSense
jupyter notebook notebooks/01_dataset_exploration.ipynb
```

**Run all cells top to bottom.** Generates 10 figures saved to `docs/figures/`:

| Figure | Content |
|---|---|
| `01_raw_pressure_signal.png` | Force-time curve + peak pressure frame for one footstep |
| `02_pressure_distributions.png` | Peak pressure and PTI by footwear and side |
| `03_plantar_pressure_heatmap.png` | Mean plantar pressure maps, Left vs Right |
| `04_regional_loading.png` | Regional load fractions by footwear condition |
| `05_gait_timing.png` | Cadence, stance time, gait symmetry distributions |
| `06_left_right_comparison.png` | L vs R scatter, asymmetry distribution, regional asymmetry |
| `07_cop_trajectories.png` | CoP paths for 6 footsteps with background pressure |
| `08_missing_values.png` | Missing value audit (generated only if missing values exist) |
| `09_feature_correlation.png` | Pearson correlation matrix for key features |
| `10_risk_score_distribution.png` | Risk score histogram, pie chart, score by footwear |

---

## 13. Current Limitations

| Limitation | Details |
|---|---|
| **No temperature data** | StepUP-P150 is a pure pressure dataset from a floor mat. Temperature is a planned insole hardware feature. |
| **No IMU data** | No accelerometry or gyroscopy. Swing phase and double support time cannot be derived. |
| **Floor mat, not wearable** | Data was captured on a fixed 3.6 m platform. The insole hardware will be continuous and wearable. |
| **No simultaneous bilateral capture** | Left and right footsteps are sequential, not synchronous. |
| **Experimental thresholds** | All risk thresholds in `config/config.py` are demo values based on the data distribution, not clinical standards. |
| **No trained ML model** | The risk engine is rule-based. The TinyML autoencoder is a roadmap item (see §15). |
| **features.csv default size** | The default run processes 5 subjects. Run without `--subjects` for all 150. |
| **participant_metadata.csv not in this download** | Demographic data (age, BMI, etc.) is referenced in the dataset paper but was not included in this archive download. |

---

## 14. Future Hardware Integration

The SoleSense hardware design:

| Component | Spec |
|---|---|
| Insoles | 2 (left + right), bilateral simultaneous |
| Pressure sites | 8 per insole |
| Temperature sites | 8 per insole |
| IMU | 1 per insole (accelerometer + gyroscope) |
| Edge MCU | nRF52840-class |
| Connectivity | BLE to host device |
| Alert | Ankle-cuff vibration / LED |

### How to plug hardware in

**One file changes.** Replace `src/data_loader.py` with a hardware adapter that reads from the insole and returns the same DataFrame schema.

The returned DataFrame must have these columns:

```
subject_id, footwear, trial, footstep_id, side,
start_frame, end_frame, stance_time_s,
foot_length_cm, foot_width_cm,
pressure_array  # shape (101, 75, 40) kPa
```

Everything downstream — preprocessing, all feature modules, risk engine, dashboard — stays identical.

### New features unlocked by hardware

| Feature | Source |
|---|---|
| `mean_temp_left_c` | 8-site temperature array, left |
| `mean_temp_right_c` | 8-site temperature array, right |
| `delta_temp_c` | bilateral ΔT |
| `temp_persistence_score` | rolling thermal asymmetry |
| `swing_time_s` | IMU + bilateral timing |
| `double_support_time_s` | bilateral simultaneous capture |
| `step_length_cm` | IMU integration |
| `walking_speed_m_s` | IMU integration |

These are already declared as placeholders in `src/temperature_features.py` and `src/anomaly_model.py`.

---

## 15. TinyML Roadmap

The personalised anomaly model (`src/anomaly_model.py`) is designed but not yet trained.

**Planned architecture:**

```
First N sessions per user (normal gait baseline)
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
| Updates | Incremental on-device fine-tuning |

**Features used by the autoencoder** (8 selected for edge efficiency):

```
press_max_kpa, pti_total_kpa_s,
load_frac_forefoot, load_frac_rearfoot,
cop_path_length_cm, stance_time_s,
asym_pti_total_kpa_s, gait_symmetry_index
```

The API is already defined — implement `PersonalAnomalyModel.fit()` and `.predict()` in `src/anomaly_model.py`.

---

## 16. Configuration

All configurable constants are in **one file**: `config/config.py`

```python
# Dataset path
DATASET_ROOT = ...             # resolved relative to project root

# Sensor constants
SAMPLING_RATE_HZ = 100
CM_PER_PX = 0.5
CM2_PER_PX = 0.25
FOOTSTEP_ROWS = 75
FOOTSTEP_COLS = 40

# Anatomical regions (row ranges)
REGIONS = {
    "TOE":      (0,  14),
    "FOREFOOT": (15, 34),
    "MIDFOOT":  (35, 54),
    "REARFOOT": (55, 74),
}

# Preprocessing
EXCLUDE_FLAGGED_STEPS = True
MIN_STANCE_DURATION_S = 0.15
MAX_STANCE_DURATION_S = 2.5

# Risk thresholds — EXPERIMENTAL, edit freely
RISK_PRESSURE_HIGH_KPA = 200.0
RISK_PRESSURE_EXPOSURE_HIGH = 50000.0
RISK_ASYMMETRY_HIGH_PCT = 20.0
RISK_LEVEL_MONITOR = 30
RISK_LEVEL_ALERT = 60
```

---

## 17. Dataset Citation

If you use the StepUP-P150 dataset in any publication, cite both:

**Dataset:**
> Larracy, Robyn; Phinyomark, Angkoon; Salehi, Ala; MacDonald, Eve; Kazemi, Saeed; Shafiul Bashar, Shikder; Tabor, Aaron; and Scheme, Erik. (2025). StepUP-P150: A Dataset of High-Resolution Plantar Pressure Measurements with Varying Footwear Types and Walking Speeds for Gait Analysis and Recognition. Federated Research Data Repository. doi: https://doi.org/10.20383/103.01285

**Descriptor paper:**
> Larracy, R., Phinyomark, A., Salehi, A., MacDonald, E., Kazemi, S., Bashar, S. S., Tabor, A., & Scheme, E. (2025). A dataset of high-resolution plantar pressures for gait analysis across varying footwear and walking speeds. *Scientific Data* 12, 1415. https://doi.org/10.1038/s41597-025-05792-1

---

<p align="center">
SoleSense Research Prototype &nbsp;·&nbsp; Dataset: StepUP-P150 (CC BY 4.0) &nbsp;·&nbsp; Not a medical device
</p>
