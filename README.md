<div align="center">

# 👟 SoleSense

**Foot Loading & Gait Risk Monitor — Demo Prototype**

*Raw plantar pressure → 134 biomechanical features → explainable risk score → live interactive dashboard*

<br>

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Plotly](https://img.shields.io/badge/Plotly-Interactive%20Charts-3F4F75?style=flat-square&logo=plotly&logoColor=white)](https://plotly.com/)
[![Dataset](https://img.shields.io/badge/Dataset-StepUP--P150%20·%20150%20Subjects-2ea44f?style=flat-square)](https://doi.org/10.20383/103.01285)
[![Status](https://img.shields.io/badge/Status-Demo%20Prototype-blue?style=flat-square)]()

</div>

---

## What is SoleSense?

SoleSense is a demo prototype that takes high-resolution plantar pressure recordings, runs them through a full feature engineering pipeline, and presents the results in a polished two-page interactive dashboard.

The core idea: don't just show a number — show **why** the number is what it is. Every risk score is broken down factor-by-factor so you can see exactly what's driving it, whether that's elevated forefoot loading, a left-right imbalance, irregular gait timing, or persistent pressure exposure.

The pipeline is designed with a clean data-source abstraction, so the same dashboard that runs on the research dataset today is ready to accept live insole sensor data tomorrow.

---

## Two-Page Dashboard

### 🏠 Page 1 — Quick Analysis
**No dataset needed. Works out of the box.**

All inputs live in the sidebar as sliders — left and right foot pressure, regional loading percentages, gait metrics, and persistence values. Every chart on the main panel responds **instantly** as you adjust any slider. No form submission, no button click.

**What you see:**
- **Risk banner** — NORMAL / MONITOR / ALERT with the score (0–100) and the most affected region
- **Risk gauge** — animated dial that moves in real time with your inputs
- **Bilateral bar charts** — PTI, peak pressure, and stance time for left vs right
- **Polar radar chart** — six-axis Desmos-style bilateral comparison showing both feet overlaid
- **Regional loading donuts** — separate donut charts for left and right foot, split into Toe / Forefoot / Midfoot / Rearfoot
- **Asymmetry waterfall** — signed bar chart showing which metrics are left-dominant or right-dominant, with threshold lines at ±10%
- **Explainable risk breakdown** — every rule shown with its contribution: which triggered, which didn't, and what the value was vs the threshold

### 📊 Page 2 — Dataset Explorer
**Powered by the StepUP-P150 dataset — 150 real subjects.**

Use the sidebar to select Subject → Footwear → Trial. The dashboard loads that session's data and renders all eight sections.

| Section | Content |
|---|---|
| ① Overall Status | Risk gauge · risk level · affected region · factor count · step-by-step sparkline |
| ② Foot Pressure | Mean/peak/PTI/loading-rate metric cards · donut charts · regional bar chart |
| ③ Bilateral Comparison | Polar radar · asymmetry waterfall · bilateral bar charts |
| ④ Temperature | Hardware roadmap card |
| ⑤ Gait Metrics | Cadence · stride time · symmetry index · variability · step-by-step chart |
| ⑥ Pressure Map & CoP | Plantar heatmap · center-of-pressure trajectory (heel-strike → toe-off) |
| ⑦ Explainable Risk | Full factor table with sub-scores and recommended action |
| ⑧ Historical Trend | Risk score across footwear conditions · feature trend selector |

---

## Getting Started

```bash
# 1. Install dependencies
cd SoleSense
pip install -r requirements.txt

# 2. Launch the dashboard
#    Quick Analysis page works immediately — no data needed
python -m streamlit run dashboard/app.py
```

Open **`http://localhost:8501`**

To unlock the Dataset Explorer (Page 2), generate the feature table first:

```bash
# Fast demo — 5 subjects, preferred walking speed (~50 seconds)
python -m src.feature_pipeline --subjects 5 --trials W1

# More data — 20 subjects, two conditions
python -m src.feature_pipeline --subjects 20 --footwear BF ST --trials W1 W2
```

---

## The Charts Explained

### Polar Radar — Bilateral Comparison
Six axes, two shapes — one blue (left foot), one red (right foot). When the shapes overlap, loading is symmetric. When one shape extends further on an axis, that foot is dominant on that metric. Axes: Peak Pressure · Mean Pressure · PTI (scaled) · Forefoot Load · Rearfoot Load · CoP Path Length.

### Asymmetry Waterfall
A horizontal bar chart with a zero line in the centre. Each bar represents one metric. Bars going right (positive) mean the left foot carries more load on that metric. Bars going left (negative) mean the right foot does. A dashed threshold line marks ±10% — bars beyond that line are flagged.

### Regional Loading Donuts
Two donut charts side by side — left foot and right foot. Each donut is divided into four regions: Toe, Forefoot, Midfoot, Rearfoot. The slice sizes show what fraction of the total load each region is absorbing. A forefoot-heavy loading pattern, for example, shows a large forefoot slice.

### Risk Sparkline
A filled area line chart showing the risk score step-by-step across an entire walking trial. The background is colour-coded into three zones: green (NORMAL), amber (MONITOR), red (ALERT), with dashed threshold lines.

### Plantar Pressure Heatmap
A 75×40 pixel thermal map of the mean pressure distribution across the foot during a trial. Brighter (yellow/white) areas indicate higher pressure. Dotted horizontal lines divide the foot into anatomical regions.

### CoP Trajectory
The center-of-pressure path overlaid on the pressure image. The green circle marks heel-strike (where the foot first contacts the ground). The red triangle marks toe-off (where it leaves). The line between them traces how the load travels through the foot during each step.

---

## Pipeline

```
StepUP-P150 .npz files
(75×40 px footstep frames · kPa · 100 Hz)
          │
          ▼
  data_loader.py        normalise · annotate side · extract arrays
          │
          ▼
  preprocessing.py      filter flagged steps · validate shape · clean
          │
          ▼
  feature_pipeline.py   orchestrate extraction
    ├── pressure_features.py    mean · max · std · PTI · CoP · 4 regions
    ├── gait_features.py        cadence · stride · stance · symmetry index
    ├── bilateral_features.py   NSI asymmetry (|L−R| / avg × 100) for all metrics
    └── temporal_features.py    5-step rolling window · persistence scoring
          │
          ▼
  features.csv  —  134 columns · 1 row per footstep
          │
          ▼
  risk_engine.py        10 named rules · weighted sum → score 0–100
          │
          ▼
  dashboard/app.py      Quick Analysis + Dataset Explorer
```

---

## Risk Engine

10 named rules. Each rule checks one feature against one threshold. Triggered rules add their weight to the score. Final score = `(sum of triggered weights / 170) × 100`.

| Rule | Checks | Threshold |
|---|---|---|
| Peak pressure | `press_max_kpa` | > 200 kPa |
| Pressure-time exposure | `pti_total_kpa_s` | > 50,000 kPa·s |
| Loading asymmetry | `asym_pti_total_kpa_s` | > 20% |
| Persistent pressure | `persistence_pti_total_kpa_s` | > 60% of steps |
| Pressure asymmetry | `asym_press_mean_kpa` | > 10% |
| Forefoot overload | `load_frac_forefoot` | > 60% |
| Gait variability | `step_time_std_s` | > 0.15 s |
| Persistent asymmetry | `asym_load_forefoot` | > 20% |
| Gait asymmetry | `gait_symmetry_index` | > 0.10 |
| Rearfoot overload | `load_frac_rearfoot` | > 65% |

**Score → Level:**  `0–29` 🟢 NORMAL &nbsp;·&nbsp; `30–59` 🟡 MONITOR &nbsp;·&nbsp; `60–100` 🔴 ALERT

All thresholds live in `config/config.py` — change them in one place and rerun.

---

## Features Extracted

134 features per footstep across 8 groups:

| Group | Count | What it captures |
|---|---|---|
| Pressure statistics | 9 | mean, max, std, percentiles, contact area |
| Pressure-Time Integral | 5 | cumulative load, loading rate |
| Regional loading | 12 | fraction of load per region × 4 regions |
| Center of Pressure | 10 | path length, excursion, velocity, start/end |
| Peak location | 5 | where on the foot the peak occurs |
| Temporal / rolling | 20 | 5-step history, persistence flags |
| Gait timing | 22 | cadence, stride, stance fraction, symmetry |
| Bilateral asymmetry | 51 | NSI + directional diff for all pressure metrics |

---

## Tech Stack

| Layer | Detail |
|---|---|
| Dashboard | Streamlit 1.30+ |
| Charts | Plotly — radar, donut, waterfall, heatmap, CoP, gauge, sparkline |
| Data processing | NumPy · Pandas · SciPy |
| Dataset | StepUP-P150 · 150 subjects · 100 Hz |
| Tests | pytest · 78 tests |
| Python | 3.10+ |

---

## Project Structure

```
SoleSense/
├── config/
│   └── config.py               all thresholds and constants in one place
├── src/
│   ├── data_loader.py           dataset adapter
│   ├── preprocessing.py         cleaning and validation
│   ├── pressure_features.py     pressure stats, PTI, CoP, regions
│   ├── gait_features.py         cadence, stride, symmetry
│   ├── bilateral_features.py    left↔right NSI asymmetry
│   ├── temporal_features.py     rolling window, persistence
│   ├── risk_engine.py           10-rule explainable scorer
│   └── feature_pipeline.py      CLI orchestrator
├── dashboard/
│   └── app.py                   two-page Streamlit dashboard
├── data/
│   └── features/features.csv    generated feature table (134 cols)
├── docs/
│   ├── DATASET_SUMMARY.md
│   ├── FEATURE_DICTIONARY.md    every feature documented
│   └── ARCHITECTURE.md
├── tests/                       78 pytest tests
├── requirements.txt
└── README.md
```

---

## Dataset

[**StepUP-P150**](https://doi.org/10.20383/103.01285) by the Health Technologies Lab, University of New Brunswick.
150 subjects · 4 footwear conditions (Barefoot, Sneakers, Personal ×2) · 4 walking speeds · 3 balance tasks · 100 Hz piezoresistive pressure floor mat · 75×40 px per footstep · pressure in kPa · CC BY 4.0.

---

<div align="center">
<sub>SoleSense · Demo Prototype · Built with Streamlit & Plotly</sub>
</div>
