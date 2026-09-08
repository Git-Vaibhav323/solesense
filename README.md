<div align="center">

# 👟 SOLESENSE

### Personal Foot Loading & Gait Risk Monitor

*Research Prototype · Dataset → Features → Explainable Risk → Live Dashboard*

---

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Plotly](https://img.shields.io/badge/Plotly-Interactive-3F4F75?style=for-the-badge&logo=plotly&logoColor=white)](https://plotly.com/)
[![Dataset](https://img.shields.io/badge/Dataset-StepUP--P150-2ea44f?style=for-the-badge)](https://doi.org/10.20383/103.01285)
[![License](https://img.shields.io/badge/Data%20License-CC%20BY%204.0-lightgrey?style=for-the-badge)](https://creativecommons.org/licenses/by/4.0/)
[![Status](https://img.shields.io/badge/Status-Research%20Prototype-orange?style=for-the-badge)]()

<br>

> ⚠️ **Research Prototype.** The SoleSense Risk Indicator is experimental and **not clinically validated**.
> This system does **not** diagnose any medical condition. All thresholds are demo values.

</div>

---

## What is SoleSense?

SoleSense is a prototype continuous foot-loading and gait-risk monitoring system.
It takes high-resolution plantar pressure data, extracts 134 biomechanical features per footstep,
and produces an **explainable risk indicator** — showing not just *what* the score is,
but *why* each factor contributes to it.

The pipeline is designed so that swapping the research dataset for a **live hardware insole** (nRF52840 + 8 pressure sites + 8 temp sites + IMU) requires changing exactly **one file**.

```
Sense → Compare → Learn → Fuse → Act
```

---

## ✨ Key Features

| | Feature | Detail |
|---|---|---|
| 🎛️ | **Live Quick Analysis** | Sidebar sliders update all charts instantly — no button click needed |
| 📊 | **Dataset Explorer** | Full 8-section analysis of any subject/trial from StepUP-P150 |
| 🎯 | **Explainable Risk Engine** | 10 named rules → weighted score 0–100, every factor shown |
| 🕸️ | **Bilateral Polar Radar** | Desmos-style interactive L↔R comparison chart |
| 🍩 | **Regional Donut Charts** | Toe / Forefoot / Midfoot / Rearfoot loading per foot |
| 📉 | **Asymmetry Waterfall** | Signed asymmetry — positive = left dominant, negative = right |
| 📈 | **Risk Sparkline** | Step-by-step risk score with MONITOR/ALERT threshold bands |
| 🔥 | **Plantar Pressure Heatmap** | 75×40 px bilateral mean pressure maps |
| 🧭 | **CoP Trajectory** | Center-of-pressure path from heel-strike to toe-off |
| 🔬 | **Temperature Roadmap** | Hardware placeholder — 8-site bilateral insole temp (future) |

---

## 🚀 Quick Start

> Requires Python 3.10+ and the dataset at `F:\Dataset\`

```powershell
# 1 — Install dependencies
cd f:\Dataset\SoleSense
pip install -r requirements.txt

# 2 — Generate features  (~50 seconds for 5 subjects)
python -m src.feature_pipeline --subjects 5 --trials W1

# 3 — Launch the dashboard
python -m streamlit run dashboard/app.py
```

Open **`http://localhost:8501`** — the dashboard is live.

> 💡 **Tip:** Step 2 is only needed for the Dataset Explorer page.
> The **Quick Analysis** page works immediately after step 3 — no data required.

---

## 🖥️ Dashboard

The dashboard has two pages, switchable from the top navigation.

### 🏠 Page 1 — Quick Analysis *(live, no dataset needed)*

Move any sidebar slider → every chart updates instantly.

```
Left sidebar sliders          →    Main panel (live)
──────────────────                 ──────────────────────────────
Left / Right peak pressure         🔴 Risk banner (NORMAL/MONITOR/ALERT)
Left / Right PTI (kPa·s)          📊 Gauge + bilateral bar charts
Regional load % per region         🕸️  Polar radar — bilateral comparison
Gait: stance, cadence, symmetry    🍩 Dual donut — regional distribution
Persistence (rolling 5 steps)      📉 Asymmetry waterfall
                                   🧠 Explainable factor breakdown
```

### 📊 Page 2 — Dataset Explorer *(StepUP-P150 static data)*

```
Sidebar dropdowns             →    8 dashboard sections
──────────────────                 ──────────────────────────────
Subject ID (001–150)          ①   Risk gauge + sparkline over steps
Footwear (BF/ST/P1/P2)        ②   Foot pressure — donuts + regional bars
Trial (W1–W4)                 ③   Bilateral comparison — radar + waterfall
                              ④   Temperature — hardware roadmap
                              ⑤   Gait metrics — cadence, stride, symmetry
                              ⑥   Pressure heatmap + CoP trajectory
                              ⑦   Explainable risk — factor-by-factor
                              ⑧   Historical trend — risk across sessions
```

---

## 🏗️ System Architecture

```
StepUP-P150 Dataset (.npz)
         │
         ▼
 src/data_loader.py        ← swap this one file for live hardware
         │
         ▼
 src/preprocessing.py      exclusion flags · stance filter · validation
         │
         ▼
 src/feature_pipeline.py   orchestrator
    │         │         │         │
    ▼         ▼         ▼         ▼
pressure    gait     bilateral  temporal
features   timing    NSI asym   rolling
CoP/PTI    cadence   L↔R diff   persist
regions    symmetry  directnl   window
         │
         ▼
 data/features/features.csv   (134 cols · 1 row/footstep)
         │
         ▼
 src/risk_engine.py        10 rules · weighted · 0–100
         │
         ▼
 dashboard/app.py
 ┌─────────────────────┬──────────────────────┐
 │  🏠 Quick Analysis  │  📊 Dataset Explorer  │
 │  live sidebar input │  features.csv + viz   │
 └─────────────────────┴──────────────────────┘
```

**Future hardware path — only `data_loader.py` changes:**
```
SoleSense Insole (nRF52840)
  8 pressure + 8 temperature + IMU
         │ BLE / Serial
         ▼
 src/hardware_adapter.py   ← new, same output schema
         │
 [preprocessing → features → risk engine → dashboard — all unchanged]
         │
         ▼
 src/anomaly_model.py      personalised TinyML autoencoder
         │
         ▼
 Ankle-cuff vibration alert
```

---

## 📦 Dataset

**StepUP-P150** — High-Resolution Plantar Pressure with Varying Footwear & Walking Speeds

| Field | Value |
|---|---|
| Institution | Health Technologies Lab, University of New Brunswick |
| Subjects | **150** (IDs 001–150) |
| Sampling rate | **100 Hz** |
| Footstep resolution | **75 × 40 px** · 0.5 cm/px |
| Pressure unit | kPa |
| Footwear conditions | BF · ST · P1 · P2 |
| Walking trials | W1 (preferred) · W2 (slow-stop) · W3 (slower) · W4 (faster) |
| Balance trials | S1 (both feet) · S2 (left) · S3 (right) |
| DOI | [10.20383/103.01285](https://doi.org/10.20383/103.01285) |
| License | CC BY 4.0 |

---

## 🧠 Risk Engine

10 named rules. Fully explainable — every triggered factor shown in the dashboard.

| Rule | Feature | Threshold | Weight |
|---|---|---|---|
| Peak pressure | `press_max_kpa` | 200 kPa | 25 |
| Pressure-time exposure | `pti_total_kpa_s` | 50 000 kPa·s | 25 |
| Loading asymmetry | `asym_pti_total_kpa_s` | 20% | 20 |
| Persistent pressure | `persistence_pti_total_kpa_s` | 60% of steps | 20 |
| Pressure asymmetry | `asym_press_mean_kpa` | 10% | 15 |
| Forefoot overload | `load_frac_forefoot` | 60% | 15 |
| Gait variability | `step_time_std_s` | 0.15 s | 15 |
| Persistent asymmetry | `asym_load_forefoot` | 20% | 15 |
| Gait asymmetry | `gait_symmetry_index` | 0.10 | 10 |
| Rearfoot overload | `load_frac_rearfoot` | 65% | 10 |

Score = `(triggered weights / 170) × 100` capped at 100.

| Level | Score | Colour |
|---|---|---|
| NORMAL | 0 – 29 | 🟢 |
| MONITOR | 30 – 59 | 🟡 |
| ALERT | 60 – 100 | 🔴 |

All thresholds are in one place — `config/config.py`. Edit and rerun. No other files change.

---

## 📁 Project Structure

```
SoleSense/
├── config/config.py              all constants + thresholds
├── src/
│   ├── data_loader.py            dataset adapter  ← swap for hardware
│   ├── preprocessing.py
│   ├── pressure_features.py      stats · PTI · CoP · regions
│   ├── gait_features.py          cadence · stride · symmetry
│   ├── bilateral_features.py     NSI asymmetry · directional
│   ├── temporal_features.py      rolling window · persistence
│   ├── temperature_features.py   hardware roadmap placeholder
│   ├── risk_engine.py            explainable rule-based scorer
│   ├── anomaly_model.py          TinyML autoencoder placeholder
│   └── feature_pipeline.py       CLI orchestrator
├── dashboard/app.py              two-page Streamlit dashboard
├── data/features/features.csv    generated feature table
├── docs/
│   ├── DATASET_SUMMARY.md
│   ├── FEATURE_DICTIONARY.md     all 134 features documented
│   └── ARCHITECTURE.md
├── tests/                        78 pytest tests
├── requirements.txt
└── README.md
```

---

## 🔬 Feature Engineering

134 features extracted per footstep · full definitions in [`docs/FEATURE_DICTIONARY.md`](SoleSense/docs/FEATURE_DICTIONARY.md)

| Group | Count | Examples |
|---|---|---|
| Pressure statistics | 9 | mean, max, std, percentiles, contact area |
| Pressure-Time Integral | 5 | PTI total, PTI/cm², loading rate |
| Regional loading | 12 | fraction + peak per region × 4 regions |
| Center of Pressure | 10 | path length, excursion, velocity, ranges |
| Peak location | 5 | row, col, cm, frame |
| Temporal / rolling | 20 | 5-step rolling mean/max/std + persistence |
| Gait timing | 22 | cadence, stride, symmetry, variability |
| Bilateral asymmetry | 51 | NSI + directional for all pressure features |

---

## ✅ Tests

```powershell
cd f:\Dataset\SoleSense
python -m pytest tests/ -v
```

**78 tests · expected: `78 passed`**

Covers: preprocessing · pressure features · bilateral asymmetry (NSI formula, division-by-zero safety) · gait features · risk engine (score bounds, NaN safety, batch scoring)

---

## 🔭 Roadmap

```
NOW          Dataset → Features → Risk Engine → Dashboard  ✅
─────────────────────────────────────────────────────────────────
NEXT         Live hardware adapter (BLE / serial)
             8-site bilateral temperature features
             IMU: swing phase, double support, step length

LATER        Personalised TinyML autoencoder (src/anomaly_model.py)
             Edge deployment: TFLite Micro on nRF52840
             Ankle-cuff vibration alert
             Mobile companion app
```

---

## 📜 Dataset Citation

**Dataset:**
> Larracy, R. et al. (2025). *StepUP-P150: A Dataset of High-Resolution Plantar Pressure Measurements.*
> Federated Research Data Repository. doi: [10.20383/103.01285](https://doi.org/10.20383/103.01285)

**Descriptor paper:**
> Larracy, R. et al. (2025). A dataset of high-resolution plantar pressures for gait analysis
> across varying footwear and walking speeds. *Scientific Data* 12, 1415.
> [doi:10.1038/s41597-025-05792-1](https://doi.org/10.1038/s41597-025-05792-1)

---

<div align="center">

**SoleSense** · Research Prototype · Not a medical device

Dataset: StepUP-P150 (CC BY 4.0) · University of New Brunswick 2023–2024

</div>
