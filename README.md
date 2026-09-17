<div align="center">

```
███████╗ ██████╗ ██╗     ███████╗███████╗███████╗███╗   ██╗███████╗███████╗
██╔════╝██╔═══██╗██║     ██╔════╝██╔════╝██╔════╝████╗  ██║██╔════╝██╔════╝
███████╗██║   ██║██║     █████╗  ███████╗█████╗  ██╔██╗ ██║███████╗█████╗
╚════██║██║   ██║██║     ██╔══╝  ╚════██║██╔══╝  ██║╚██╗██║╚════██║██╔══╝
███████║╚██████╔╝███████╗███████╗███████║███████╗██║ ╚████║███████║███████╗
╚══════╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═══╝╚══════╝╚══════╝
```

### Personal Foot Loading & Gait Monitor — Research Prototype

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Plotly](https://img.shields.io/badge/Plotly-5.18%2B-3F4F75?style=for-the-badge&logo=plotly&logoColor=white)](https://plotly.com)
[![ESP32](https://img.shields.io/badge/ESP32--S3-Live%20Hardware-E7352C?style=for-the-badge&logo=espressif&logoColor=white)](https://espressif.com)
[![Dataset](https://img.shields.io/badge/Dataset-StepUP--P150-2ea44f?style=for-the-badge)](https://doi.org/10.20383/103.01285)
[![License](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey?style=for-the-badge)](https://creativecommons.org/licenses/by/4.0/)
[![Tests](https://img.shields.io/badge/Tests-78%20passing-43A047?style=for-the-badge&logo=pytest&logoColor=white)]()
[![Status](https://img.shields.io/badge/Status-Research%20Prototype-FB8C00?style=for-the-badge)]()

> ⚠️ **Medical Disclaimer:** SoleSense is a **research prototype**. The Risk Indicator is
> experimental and **not clinically validated**. It does **not** diagnose diabetes,
> neuropathy, foot ulcers, or any medical condition. All thresholds are demo values only.

</div>

---

## What is SoleSense?

SoleSense is a **continuous, explainable foot-loading and gait monitor** that catches
abnormal plantar pressure patterns before they cause injury — elevated peak pressure,
forefoot overloading, persistent asymmetry, irregular gait timing, and temperature
deviation — all delivered with a full factor-by-factor explanation of why the risk
indicator fired.

**Today it runs on two paths simultaneously:**

| Path | Data Source | Purpose |
|---|---|---|
| 🔬 **Research** | StepUP-P150 dataset · 150 subjects · 100 Hz floor mat | Algorithm validation on real biomechanics data |
| 📡 **Hardware** | ESP32-S3 insole · FSR + TMP117 + MPU6050 · 20 Hz Wi-Fi | Live monitoring prototype |

The pipeline from sensor → features → risk score → dashboard is **identical on both
paths** — only the data source module changes.

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [System Architecture](#2-system-architecture)
3. [Dashboard Guide](#3-dashboard-guide)
4. [Hardware Prototype](#4-hardware-prototype)
5. [Dataset — StepUP-P150](#5-dataset)
6. [Project Structure](#6-project-structure)
7. [Feature Engineering](#7-feature-engineering)
8. [Risk Engine](#8-risk-engine)
9. [Installation & Running](#9-installation--running)
10. [API Usage](#10-api-usage)
11. [Running Tests](#11-running-tests)
12. [Configuration Reference](#12-configuration-reference)
13. [Limitations & Roadmap](#13-limitations--roadmap)
14. [Dataset Citation](#14-dataset-citation)

---

## 1. Quick Start

```bash
# Prerequisites: Python 3.10+, dataset downloaded (see §5)

# 1 — clone / enter project
cd SoleSense

# 2 — install dependencies
pip install -r requirements.txt

# 3 — generate features from 5 subjects (~50 seconds)
python -m src.feature_pipeline --subjects 5 --trials W1

# 4 — launch dashboard
python -m streamlit run dashboard/app.py
# → open http://localhost:8501
```

> **Tip — Quick Analysis page needs zero dataset.** Just launch and drag the sliders
> to see the risk engine respond live.

---

## 2. System Architecture

### 2.1 Full pipeline overview

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                         SOLESENSE PIPELINE                                  ║
╠══════════════════╦═══════════════════════════════════════════════════════════╣
║  DATA SOURCE     ║                                                           ║
║                  ║   ┌─────────────────┐     ┌──────────────────────────┐   ║
║  Research path ──╬──▶│ data_loader.py  │     │  hardware_adapter.py     │   ║
║  .npz files      ║   │ StepUP-P150     │     │  ESP32-S3 Wi-Fi packets  │   ║
║                  ║   └────────┬────────┘     └────────────┬─────────────┘   ║
║  Hardware path ──╬────────────┘                           │                 ║
║  ESP32-S3        ║            └───────────────────────────┘                 ║
╠══════════════════╬═══════════════════════════════════════════════════════════╣
║  SAME SCHEMA     ║   pd.DataFrame  ·  1 row = 1 footstep / 1 window        ║
╠══════════════════╬═══════════════════════════════════════════════════════════╣
║  PREPROCESSING   ║   preprocessing.py                                        ║
║                  ║   ├── Remove Exclude=1 flagged steps                      ║
║                  ║   ├── Filter stance < 0.15 s  or  > 2.5 s                ║
║                  ║   └── Validate array shape (101 × 75 × 40)               ║
╠══════════════════╬═══════════════════════════════════════════════════════════╣
║  FEATURE         ║   feature_pipeline.py  (orchestrator)                     ║
║  ENGINEERING     ║                                                           ║
║  134 features    ║   ┌──────────────┬─────────────┬──────────────────────┐  ║
║  per footstep    ║   │pressure_     │gait_        │bilateral_            │  ║
║                  ║   │features.py   │features.py  │features.py           │  ║
║                  ║   │49 features   │22 features  │51 features           │  ║
║                  ║   │stats·PTI·    │cadence·     │NSI asymmetry         │  ║
║                  ║   │CoP·regions   │stride·sym   │L↔R all metrics       │  ║
║                  ║   └──────┬───────┴──────┬──────┴──────────┬───────────┘  ║
║                  ║          └──────────────┼─────────────────┘              ║
║                  ║                         ▼                                 ║
║                  ║   temporal_features.py  (20 features)                     ║
║                  ║   rolling window 5 steps · persistence scores             ║
╠══════════════════╬═══════════════════════════════════════════════════════════╣
║  OUTPUT          ║   data/features/features.csv                              ║
║                  ║   134 columns · 1 row per footstep                        ║
╠══════════════════╬═══════════════════════════════════════════════════════════╣
║  RISK ENGINE     ║   risk_engine.py                                          ║
║                  ║   10 named rules  →  weighted sub-scores                  ║
║                  ║   score = Σ(triggered weights) / 170 × 100               ║
║                  ║                                                           ║
║                  ║    0–29  ●  NORMAL    30–59  ●  MONITOR    60+  ●  ALERT ║
╠══════════════════╬═══════════════════════════════════════════════════════════╣
║  DASHBOARD       ║   dashboard/app.py  (Streamlit + Plotly)                  ║
║                  ║   ┌────────────────┬──────────────────┬────────────────┐  ║
║                  ║   │🏠 Quick        │📊 Dataset        │📡 Live         │  ║
║                  ║   │   Analysis     │   Explorer       │   Hardware     │  ║
║                  ║   │live sliders    │StepUP-P150 data  │ESP32-S3 stream │  ║
║                  ║   │no dataset req  │8-section deep    │real-time gait  │  ║
║                  ║   │instant risk    │dive any subject  │& pressure map  │  ║
║                  ║   └────────────────┴──────────────────┴────────────────┘  ║
╚══════════════════╩═══════════════════════════════════════════════════════════╝
```

### 2.2 Hardware data flow

```
┌─────────────────────────────────────────────────────────────┐
│                    ESP32-S3 INSOLE                           │
│                                                             │
│  FSR1 (forefoot) ──┐                                        │
│  FSR2 (heel)     ──┼──▶ 12-bit ADC ──▶ Baseline subtract   │
│                    │                                         │
│  TMP117 ──────────▶│ I²C  ──▶ ±0.1 °C temperature          │
│  MPU6050 ─────────▶│ I²C  ──▶ 3-axis accel + 3-axis gyro   │
│                    │                                         │
│  All sampled at 20 Hz  →  JSON packet  →  HTTP POST         │
└─────────────────────────────┬───────────────────────────────┘
                              │  Wi-Fi  (port 5005)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│             hardware/esp32_receiver.py  (Flask)              │
│  Rolling deque buffer · 400 packets (~20 s)                 │
│  Thread-safe reads from Streamlit session                   │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│           hardware/hardware_adapter.py                       │
│  Window of packets  →  feature pd.Series                    │
│  (same schema as features.csv — drop-in for risk engine)    │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
                   compute_risk(row)  →  RiskResult
                              │
                              ▼
                   dashboard/app.py  →  📡 Live Hardware page
```

### 2.3 Future hardware path (full design)

```
SoleSense Insole v2 (planned)
  ├── 4 FSR pressure sites per foot (forefoot-medial, forefoot-lateral, midfoot, heel)
  ├── 8 temperature sites per foot (TMP117 × 8)
  ├── 1 IMU per foot (MPU6050)
  └── nRF52840 edge MCU (BLE)
              │
              ▼  BLE → Mobile App
  src/data_loader.py  ← SWAP THIS ONE FILE
              │
  [identical feature pipeline + risk engine + dashboard]
              │
              ▼
  PersonalAnomalyModel (TinyML autoencoder)
  50 features → 16 → 8 → 16 → 50  (fits in 256 KB flash)
              │
  fuse_scores(rule=70%, anomaly=30%)  →  Final Risk Indicator
              │
              ▼
  Ankle-cuff vibration / LED alert
```

### 2.4 Risk score anatomy

```
  Rule triggered?        Weight    Running total (max 170)
  ─────────────────────────────────────────────────────
  Peak pressure > 200 kPa          25  ██████████
  PTI > 50,000 kPa·s               25  ██████████
  Loading asymmetry > 20%          20  ████████
  Pressure asymmetry > 10%         15  ██████
  Forefoot overload > 60%          15  ██████
  Rearfoot overload > 65%          10  ████
  Gait variability > 0.15 s        15  ██████
  Gait timing asymmetry > 10%      10  ████
  Persistent pressure > 60%        20  ████████
  Persistent asymmetry > 20%       15  ██████
  ─────────────────────────────────────────────
  score = Σ triggered / 170 × 100  →  0 – 100

  ●  0–29   NORMAL    ●  30–59   MONITOR    ●  60–100  ALERT
```

---

## 3. Dashboard Guide

### 🏠 Page 1 — Quick Analysis *(no dataset needed)*

Adjust any sidebar slider — every chart updates instantly without a button click.

| Section | What you see |
|---|---|
| **Risk Banner** | NORMAL / MONITOR / ALERT · score 0–100 · LED colour |
| **Top Metric Cards** | Left/Right peak pressure, PTI, cadence, gait symmetry |
| **① Risk & Bilateral Pressure** | Gauge dial + 3 bilateral bar charts |
| **② Regional Loading** | Polar radar + dual donut (Toe/Forefoot/Midfoot/Rearfoot) |
| **③ Asymmetry Profile** | Waterfall chart — + = left dominant, − = right dominant |
| **④ Explainable Risk** | Every rule: triggered/not, value vs threshold, sub-score |

### 📊 Page 2 — Dataset Explorer *(requires features.csv)*

Filter by Subject → Footwear → Trial. All 8 sections update instantly.

| Section | What you see |
|---|---|
| **① Overall Status** | Risk gauge · level · affected region · step-by-step sparkline |
| **② Foot Pressure** | Mean/peak/PTI cards · donut · regional bar chart |
| **③ Left ↔ Right** | Bilateral bars · polar radar · asymmetry waterfall |
| **④ Temperature** | Hardware roadmap placeholder |
| **⑤ Gait Metrics** | 8 gait cards · stance time per step line chart |
| **⑥ Pressure Map & CoP** | Plantar heatmap · Centre-of-Pressure trajectory |
| **⑦ Explainable Risk** | Full factor table · recommended action |
| **⑧ Historical Trend** | Risk by trial/footwear · feature trend selector |

### 📡 Page 3 — Live Hardware *(ESP32-S3)*

Real-time single LEFT-foot monitoring. Enable **🧪 Mock mode** in the sidebar to test
without hardware.

| Section | What you see |
|---|---|
| **Device Status Strip** | Connection · FSR1/FSR2/TMP117/MPU6050 health · data rate |
| **Overall Status Banner** | LED dot · NORMAL/MONITOR/ALERT · risk score / 100 |
| **① Foot Pressure Map** | Anatomical SVG (toes top, heel bottom) · FSR dots sized by load |
| **② Load Over Time** | FSR1 (forefoot) + FSR2 (heel) + total · proxy-kPa axis |
| **③ PTI & Persistence** | 6 cards: forefoot PTI · heel PTI · total PTI · persistence % |
| **④ Temperature** | Current °C · baseline · deviation · trend · sparkline |
| **⑤ Gait Analysis** | Activity card · step count · cadence · intensity · variability CV · accel & gyro charts · session history |
| **⑥ Regional Hotspot** | Dominant region · reason · duration |
| **⑦ Personal Baseline** | Session baseline vs current · risk history sparkline |
| **⑧ Risk Breakdown** | Gauge · explainable factors · recommendation · LED state |

---

## 4. Hardware Prototype

### Bill of materials

| Component | Qty | Unit Cost | Role |
|---|---|---|---|
| ESP32-S3 DevKitC-1 | 1 | ~$5 | MCU + Wi-Fi + 12-bit ADC |
| FSR 402 / 406 | 2 active (4 designed) | ~$5 each | Plantar pressure |
| TMP117 breakout | 1 | ~$4 | Temperature ±0.1 °C |
| MPU6050 breakout | 1 | ~$2 | 3-axis accel + gyro |
| 10 kΩ resistors | 2–4 | < $0.10 each | FSR voltage dividers |
| **Total BOM** | | **~$22–28** | |

### Wiring

```
ESP32-S3                     Sensors
───────────────────────────────────────────────────────────────
GPIO 1  (ADC1_CH0) ──────── FSR1 (forefoot)  ──┬── 10kΩ ── GND
GPIO 2  (ADC1_CH1) ──────── FSR2 (heel)      ──┴── 10kΩ ── GND
GPIO 8  (SDA)      ──────── TMP117 SDA ─────── MPU6050 SDA
GPIO 9  (SCL)      ──────── TMP117 SCL ─────── MPU6050 SCL
3.3V               ──────── All sensor VCC
GND                ──────── All sensor GND

FSR voltage divider:
  3.3V ──[FSR]──┬── GPIO (ADC reads this voltage)
                │
              [10kΩ]
                │
               GND
```

### JSON packet (20 Hz)

```json
{
  "timestamp": 123456789,
  "fsr1": 421,  "fsr2": 380,  "fsr3": 0,  "fsr4": 0,
  "temperature": 31.42,
  "ax":  0.03,  "ay": -0.02,  "az": 0.98,
  "gx":  1.24,  "gy": -0.81,  "gz": 0.32
}
```

### Proxy-kPa formula

```
proxy_kPa = (ADC_reading / 4095) × 600
```

FSR ADC values are **not calibrated kPa** — they are relative load proxies.
All charts clearly label this as `p-kPa (proxy, uncalibrated)`.

---

## 5. Dataset

**StepUP-P150** · University of New Brunswick · 2023–2024 · CC BY 4.0

```
150 subjects  ·  4 footwear conditions  ·  7 trial types  ·  100 Hz  ·  kPa
Footstep image: 75 × 40 px  ·  0.5 cm/pixel  ·  101 frames per step
```

| Footwear | Trials |
|---|---|
| BF — Barefoot | W1 Preferred · W2 Slow-Stop · W3 Slower · W4 Faster |
| ST — Standard Sneakers | S1 Both feet · S2 Left only · S3 Right only |
| P1 / P2 — Personal footwear | (same conditions) |

### Anatomical coordinate system

```
Row  0–14  │ TOE       (digit region)        ← row 0 = toe tip
Row 15–34  │ FOREFOOT  (metatarsal heads)
Row 35–54  │ MIDFOOT   (plantar arch)
Row 55–74  │ REARFOOT  (heel pad)            ← row 74 = heel
           └──────────────────────────────────
           40 columns  ·  medial → lateral
```

Verified by CoP direction: starts at row ~65 (heel strike) → ends at row ~10 (toe-off).

---

## 6. Project Structure

```
SoleSense/
│
├── 📁 config/
│   └── config.py              ← ALL constants: thresholds · paths · sensor params
│
├── 📁 src/                    ← Core analytics library
│   ├── data_loader.py         ← DATA SOURCE ADAPTER  (swap this for hardware)
│   ├── preprocessing.py       ← exclusion · stance filter · validation
│   ├── pressure_features.py   ← stats · PTI · CoP · 4 regional fractions  (49 features)
│   ├── gait_features.py       ← cadence · stride · symmetry · variability  (22 features)
│   ├── bilateral_features.py  ← NSI left↔right for all pressure metrics    (51 features)
│   ├── temporal_features.py   ← 5-step rolling window · persistence scores (20 features)
│   ├── temperature_features.py← hardware roadmap placeholder
│   ├── risk_engine.py         ← 10-rule explainable scorer → RiskResult
│   ├── anomaly_model.py       ← TinyML autoencoder API (not yet trained)
│   ├── hardware_input.py      ← flat ESP32 packet parser + feature converter
│   └── feature_pipeline.py   ← CLI orchestrator → features.csv
│
├── 📁 hardware/               ← Live hardware integration
│   ├── esp32_receiver.py      ← Flask HTTP server · rolling 400-packet deque
│   ├── hardware_adapter.py    ← packets → feature pd.Series for risk engine
│   └── sensor_schema.py       ← structured packet dataclasses + parser
│
├── 📁 firmware/               ← Arduino firmware for ESP32-S3
│   └── solesense_esp32s3/
│       ├── solesense_esp32s3.ino  ← main sketch
│       ├── config.h               ← Wi-Fi credentials · server IP · pin assignments
│       ├── sensors.cpp/h          ← FSR + TMP117 + MPU6050 drivers
│       ├── calibration.cpp/h      ← NVS baseline calibration
│       ├── wifi_tx.cpp/h          ← HTTP POST transmission
│       └── alert.cpp/h            ← LED state driver
│
├── 📁 dashboard/
│   └── app.py                 ← 3-page Streamlit + Plotly dashboard (~2,500 lines)
│
├── 📁 data/
│   ├── raw/                   ← empty (dataset stays in original location)
│   ├── processed/             ← preprocessed_metadata.csv
│   └── features/
│       └── features.csv       ← PRIMARY OUTPUT  (134 cols · ~1,600 rows per 5 subjects)
│
├── 📁 docs/
│   ├── ARCHITECTURE.md
│   ├── DATASET_SUMMARY.md
│   ├── FEATURE_DICTIONARY.md
│   ├── UNDERSTANDING.md       ← complete technical deep-dive + 25 Q&A
│   ├── FUNDING.md             ← funding proposal + investor Q&A
│   └── figures/               ← notebook-generated plots
│
├── 📁 tests/                  ← 78 pytest tests
│   ├── test_preprocessing.py
│   ├── test_pressure_features.py
│   ├── test_bilateral_features.py
│   ├── test_gait_features.py
│   ├── test_risk_engine.py
│   └── test_hardware_adapter.py
│
├── 📁 notebooks/
│   └── 01_dataset_exploration.ipynb
│
├── requirements.txt
├── pytest.ini
└── README.md                  ← this file
```

---

## 7. Feature Engineering

134 features extracted per footstep. Full definitions: `docs/FEATURE_DICTIONARY.md`.

### Feature groups at a glance

```
┌─────────────────────────────────────────────────────────────────────┐
│  GROUP               MODULE                  FEATURES   COUNT       │
├─────────────────────────────────────────────────────────────────────┤
│  Pressure stats      pressure_features.py    mean·max·std·pctiles   9│
│  Pressure-Time (PTI) pressure_features.py    PTI·rate·force          5│
│  Regional loading    pressure_features.py    4 regions × 3 metrics  12│
│  Peak location       pressure_features.py    row·col·cm·frame        5│
│  Centre of Pressure  pressure_features.py    path·velocity·range    10│
│  ─────────────────── ─────────────────────── ────────────────── ────│
│  Temporal/rolling    temporal_features.py    5-step window+persist  20│
│  ─────────────────── ─────────────────────── ────────────────── ────│
│  Gait timing         gait_features.py        cadence·stride·sym     22│
│  ─────────────────── ─────────────────────── ────────────────── ────│
│  Bilateral asymmetry bilateral_features.py   NSI for all metrics    51│
│  ═════════════════════════════════════════════════════════════════  │
│  TOTAL                                                             134│
└─────────────────────────────────────────────────────────────────────┘
```

### Key formulas

**Pressure-Time Integral (PTI)**
```
PTI = Σ (pixel_kPa × 0.01 s)   over all pixels × all stance frames
                                 at 100 Hz, each frame = 0.01 s
Unit: kPa·s
```
Captures cumulative loading burden — sustained moderate pressure causes as much
tissue damage as brief peaks. This is the gold-standard metric in diabetic foot research.

**Normalized Symmetry Index (NSI)**
```
NSI = |L − R| / ((L + R) / 2) × 100%
```
Applied to every bilateral feature pair. Zero = perfect symmetry. Protected against
division by zero throughout.

**Centre of Pressure (CoP)**
```
CoP_row(f) = Σ(pressure[r,c,f] × r) / Σ(pressure[r,c,f])   per frame f
Path length = Σ √(ΔCoP_row² + ΔCoP_col²)   across stance frames
Unit: cm
```

**Gait Variability**
```
step_time_std = std( time between consecutive heel-strikes )
Unit: seconds   ·   threshold: > 0.15 s → elevated
```

---

## 8. Risk Engine

10 rules. Fully explainable. No black box.

### Rules, weights, and thresholds

```
 #   Rule name                 Feature                      Threshold   Weight
─────────────────────────────────────────────────────────────────────────────
 1   Peak pressure             press_max_kpa                 > 200 kPa     25
 2   Pressure-time exposure    pti_total_kpa_s               > 50,000 kPa·s 25
 3   Loading asymmetry (L↔R)  asym_pti_total_kpa_s          > 20 %        20
 4   Pressure asymmetry        asym_press_mean_kpa           > 10 %        15
 5   Forefoot overload         load_frac_forefoot            > 0.60        15
 6   Rearfoot (heel) overload  load_frac_rearfoot            > 0.65        10
 7   Gait variability          step_time_std_s               > 0.15 s      15
 8   Gait timing asymmetry     gait_symmetry_index           > 0.10        10
 9   Persistent pressure       persistence_pti_total_kpa_s   > 0.60        20
10   Persistent asymmetry      asym_load_forefoot            > 20 %        15
─────────────────────────────────────────────────────────────────────────────
                                              Total weight =              170

     score = Σ(triggered weights) / 170 × 100   (capped at 100)
```

### Risk levels

```
  ●  NORMAL   [ 0–29 ]   No significant concerns
  ●  MONITOR  [30–59 ]   One or more elevated patterns — watch closely
  ●  ALERT    [60–100]   Multiple elevated patterns — review recommended
```

### Output (`RiskResult`)

```python
RiskResult(
    risk_score = 42.3,
    risk_level = "MONITOR",
    affected_region = "LEFT_FOREFOOT",
    contributing_factors = [
        "Elevated peak pressure",
        "High pressure-time exposure"
    ],
    recommended_action = "Monitor loading patterns across sessions...",
    factors = [RiskFactor(...), ...]   # full per-rule detail for dashboard
)
```

---

## 9. Installation & Running

### Install

```bash
cd SoleSense
pip install -r requirements.txt
```

| Package | Version | Purpose |
|---|---|---|
| `numpy` | ≥ 1.24 | Array operations |
| `pandas` | ≥ 1.5 | Feature tables |
| `scipy` | ≥ 1.10 | Signal filtering |
| `streamlit` | ≥ 1.30 | Dashboard server |
| `plotly` | ≥ 5.18 | Interactive charts |
| `flask` + `flask-cors` | ≥ 3.0 | ESP32 HTTP receiver |
| `pytest` | ≥ 7.4 | Test runner |
| `jupyter` + `matplotlib` | ≥ 1.0 | Notebook |

### Generate features

```bash
# Fast demo — 5 subjects, W1 trial (~50 s)
python -m src.feature_pipeline --subjects 5 --trials W1

# Specific conditions
python -m src.feature_pipeline --subjects 10 --footwear BF ST --trials W1 W2

# Full dataset (150 subjects, all conditions — ~30 min, ~4 GB RAM)
python -m src.feature_pipeline
```

### Launch dashboard

```bash
python -m streamlit run dashboard/app.py
# → http://localhost:8501
```

### Live hardware mode

```bash
# Terminal 1 — start the ESP32 receiver
python -m hardware.esp32_receiver

# Terminal 2 — dashboard
python -m streamlit run dashboard/app.py
# → navigate to 📡 Live Hardware in the sidebar
```

> Set `SERVER_IP` in `firmware/solesense_esp32s3/config.h` to your laptop's IP
> (`ipconfig` on Windows · `ifconfig en0` on macOS · `ip addr` on Linux).

> **No hardware?** Enable **🧪 Mock mode** in the sidebar to see the full Live
> Hardware dashboard with synthetic walking data.

### Common mistake

```
ModuleNotFoundError: No module named 'src'
```

You are running from the wrong directory. **Always run from inside `SoleSense/`:**

```bash
cd SoleSense    # ← this is the critical step
python -m streamlit run dashboard/app.py
```

---

## 10. API Usage

### Score a full pipeline run

```python
from src.feature_pipeline import run_pipeline
from src.risk_engine import score_features_df

df     = run_pipeline(max_subjects=10, trial_list=["W1"])
scored = score_features_df(df)
print(scored[["subject_id","side","risk_score","risk_level"]].head())
```

### Load one trial with pressure arrays

```python
from src.data_loader import load_walking_trial

trial = load_walking_trial(
    subject_id="078", footwear="BF", trial="W1",
    include_pressure_arrays=True,
)
# trial["pressure_array"]  →  shape (101, 75, 40)  in kPa
```

### Score a single feature row

```python
import pandas as pd
from src.risk_engine import compute_risk

row = pd.Series({
    "press_max_kpa":        320.0,
    "pti_total_kpa_s":    55000.0,
    "asym_pti_total_kpa_s": 25.0,
    "load_frac_forefoot":    0.65,
    "gait_symmetry_index":   0.12,
    "step_time_std_s":       0.18,
    "persistence_pti_total_kpa_s": 0.8,
})
result = compute_risk(row)
print(result.risk_level, result.risk_score)
# → ALERT  58.8
for f in result.factors:
    if f.triggered:
        print(f"  ⚠ {f.label}: {f.detail}")
```

### Score a live hardware window

```python
from hardware.hardware_adapter import HardwareAdapter
from hardware.esp32_receiver import get_receiver
from src.risk_engine import compute_risk

receiver = get_receiver(port=5005)
adapter  = HardwareAdapter(window_s=5.0)

packets  = receiver.recent_packets(n=100)
row      = adapter.to_feature_row(packets)
if row is not None:
    result = compute_risk(row)
    print(result.risk_level, result.risk_score)
```

---

## 11. Running Tests

```bash
cd SoleSense
python -m pytest tests/ -v
# Expected: 78 passed
```

| Test file | What it covers |
|---|---|
| `test_preprocessing.py` | Exclusion flags · stance filter · NaN handling |
| `test_pressure_features.py` | Stats · PTI scaling · regional fractions sum = 1 · CoP |
| `test_bilateral_features.py` | NSI formula · div-by-zero · zero asymmetry cases |
| `test_gait_features.py` | Cadence · stride time · symmetry index · step count |
| `test_risk_engine.py` | Score bounds · NaN safety · missing feature skipping |
| `test_hardware_adapter.py` | Packet schema · adapter output · risk integration |

---

## 12. Configuration Reference

All constants in one file: `config/config.py`

```python
# Sensor / hardware
SAMPLING_RATE_HZ = 100
CM_PER_PX        = 0.5          # 0.5 cm per pixel
FOOTSTEP_ROWS    = 75
FOOTSTEP_COLS    = 40
FOOTSTEP_FRAMES  = 101

# Anatomical regions (row ranges in 75-row image)
REGIONS = {
    "TOE":      (0,  14),
    "FOREFOOT": (15, 34),
    "MIDFOOT":  (35, 54),
    "REARFOOT": (55, 74),
}

# Preprocessing
MIN_STANCE_DURATION_S = 0.15
MAX_STANCE_DURATION_S = 2.5

# Risk thresholds — EXPERIMENTAL, edit freely
RISK_PRESSURE_HIGH_KPA       = 200.0
RISK_PRESSURE_EXPOSURE_HIGH  = 50000.0
RISK_ASYMMETRY_HIGH_PCT      = 20.0
RISK_ASYMMETRY_MODERATE_PCT  = 10.0
RISK_GAIT_VARIABILITY_HIGH_S = 0.15
RISK_REGIONAL_LOADING_HIGH   = 0.6

# Risk level boundaries
RISK_LEVEL_MONITOR = 30
RISK_LEVEL_ALERT   = 60
```

Edit `config/config.py` and rerun — no other files change.

---

## 13. Limitations & Roadmap

### Current limitations

| Limitation | Detail |
|---|---|
| Uncalibrated FSR pressure | ADC proxy only — bench calibration with known weights needed |
| 2 FSRs active (of 4 designed) | Midfoot sensor not connected in prototype |
| Single insole | No bilateral comparison from hardware (bilateral rules inactive) |
| Experimental thresholds | Percentile-based, not clinically validated from outcome studies |
| Wi-Fi only | BLE + mobile app is next hardware milestone |
| No battery | Prototype runs on USB; LiPo planned |
| No longitudinal storage | Session history resets on power cycle |

### Roadmap

```
Phase 1  ✅  Research prototype
              StepUP-P150 pipeline · ESP32-S3 2-FSR · rule engine · dashboard

Phase 2  🔄  Validated hardware (6–9 months)
              4-FSR calibrated insole · LiPo · BLE · custom PCB · 30-subject pilot

Phase 3  📋  Bilateral + mobile (12 months)
              Two insoles · Flutter app · cloud backend · bilateral rules active

Phase 4  🧠  TinyML personalisation (18 months)
              Personal autoencoder baseline · on-device anomaly score

Phase 5  🏥  Clinical validation (24 months)
              IRB study · CDSCO/CE/FDA pathway
```

---

## 14. Dataset Citation

If you use StepUP-P150 in any publication, please cite:

**Dataset:**
> Larracy R, Phinyomark A, Salehi A, MacDonald E, Kazemi S, Bashar SS, Tabor A,
> Scheme E (2025). *StepUP-P150: High-Resolution Plantar Pressure Measurements.*
> FRDR. https://doi.org/10.20383/103.01285

**Descriptor paper:**
> Larracy R et al. (2025). A dataset of high-resolution plantar pressures for gait
> analysis across varying footwear and walking speeds. *Scientific Data* 12, 1415.
> https://doi.org/10.1038/s41597-025-05792-1

---

<div align="center">

**SoleSense** · Research Prototype · Not a Medical Device

Dataset: StepUP-P150 (CC BY 4.0) · University of New Brunswick 2023–2024

Hardware: ESP32-S3 · FSR 402 · TMP117 · MPU6050

*"Every step matters. We make sure it's a safe one."*

</div>
