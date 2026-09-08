<div align="center">

# 👟 SoleSense

**Foot Loading & Gait Risk Monitor**

*Plantar pressure → feature engineering → explainable risk → live dashboard*

<br>

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Plotly](https://img.shields.io/badge/Plotly-Interactive%20Charts-3F4F75?style=flat-square&logo=plotly&logoColor=white)](https://plotly.com/)
[![Status](https://img.shields.io/badge/Status-Demo%20Prototype-blue?style=flat-square)]()

</div>

---

## Overview

SoleSense is a demo prototype that turns raw plantar pressure recordings into an interactive risk dashboard. It processes footstep pressure data, extracts biomechanical features, and explains exactly which factors drive the risk score.

Built to show the full pipeline from raw sensor data to a polished web dashboard — with the architecture ready to accept live insole hardware instead of the dataset.

---

## Demo

### 🏠 Quick Analysis — live input
Adjust any sidebar slider and every chart updates instantly. No button click needed.

- Risk gauge (0–100) with NORMAL / MONITOR / ALERT
- Bilateral polar radar — left vs right foot comparison
- Regional loading donuts — Toe / Forefoot / Midfoot / Rearfoot
- Asymmetry waterfall chart
- Explainable factor breakdown — *why* the score is what it is

### 📊 Dataset Explorer — 150 subjects
Select any subject, footwear condition, and walking trial from the sidebar.

- Step-by-step risk sparkline
- Plantar pressure heatmap (75×40 px per foot)
- Center-of-pressure trajectory (heel-strike → toe-off)
- Historical trend across footwear conditions

---

## Run It

```bash
cd SoleSense
pip install -r requirements.txt

# Quick Analysis works immediately — no data needed
streamlit run dashboard/app.py

# To unlock the Dataset Explorer, generate features first
python -m src.feature_pipeline --subjects 5 --trials W1
```

Open `http://localhost:8501`

---

## Stack

| Layer | Tech |
|---|---|
| Dashboard | Streamlit + Plotly |
| Feature engineering | NumPy · Pandas · SciPy |
| Data | StepUP-P150 — 150 subjects · 100 Hz plantar pressure |
| Risk engine | Explainable rule-based · 10 factors · score 0–100 |
| Tests | pytest — 78 tests |

---

## How It Works

```
Raw .npz pressure files (75×40 px per footstep @ 100 Hz)
        ↓
data_loader.py       load + normalise footsteps
        ↓
preprocessing.py     filter · validate · clean
        ↓
feature_pipeline.py  extract 134 features per step
  ├── pressure_features.py   PTI · CoP · regional loading
  ├── gait_features.py       cadence · stride · symmetry
  ├── bilateral_features.py  left ↔ right asymmetry (NSI)
  └── temporal_features.py   rolling window · persistence
        ↓
risk_engine.py       10 explainable rules → score 0–100
        ↓
dashboard/app.py     two-page Streamlit + Plotly UI
```

> **Swap for live hardware:** replace `data_loader.py` with a BLE/serial adapter.
> Everything else stays the same.

---

## Project Structure

```
SoleSense/
├── src/
│   ├── data_loader.py          ← swap this for live hardware
│   ├── preprocessing.py
│   ├── pressure_features.py
│   ├── gait_features.py
│   ├── bilateral_features.py
│   ├── temporal_features.py
│   ├── risk_engine.py
│   └── feature_pipeline.py
├── dashboard/
│   └── app.py                  ← two-page Streamlit dashboard
├── config/config.py            ← all thresholds in one place
├── docs/
│   ├── DATASET_SUMMARY.md
│   ├── FEATURE_DICTIONARY.md
│   └── ARCHITECTURE.md
├── tests/                      ← 78 pytest tests
└── requirements.txt
```

---

## Dataset

[StepUP-P150](https://doi.org/10.20383/103.01285) — 150 subjects, 4 footwear conditions, 7 trial types, 100 Hz piezoresistive floor mat, 75×40 px footstep images in kPa. Published by the Health Technologies Lab, University of New Brunswick (CC BY 4.0).

---

<div align="center">
<sub>SoleSense · Demo Prototype · Built with Streamlit & Plotly</sub>
</div>
