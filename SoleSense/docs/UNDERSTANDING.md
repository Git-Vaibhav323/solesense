# SOLESENSE — Complete Project Understanding
### Everything You Need to Know · Software · Hardware · Formulas · Graphs · Q&A
#### Last updated to reflect: Gait Analysis v2 · Single left-foot prototype · All dashboard sections

> Written for a judge, funder, collaborator, or new team member. Nothing is assumed.
> Every formula is derived from first principles. Every graph is explained. Every
> design decision is justified.

---

## TABLE OF CONTENTS

1. [What Problem Are We Solving?](#1-what-problem-are-we-solving)
2. [What Is SoleSense?](#2-what-is-solesense)
3. [Why This Problem Matters](#3-why-this-problem-matters)
4. [System Architecture](#4-system-architecture)
5. [The Dataset — StepUP-P150](#5-the-dataset)
6. [Hardware Prototype — ESP32-S3 Insole](#6-hardware-prototype)
7. [Software Pipeline — Step by Step](#7-software-pipeline)
8. [Feature Engineering — Every Formula Explained](#8-feature-engineering)
9. [The Risk Engine — Every Rule, Every Weight, Every Threshold](#9-the-risk-engine)
10. [Dashboard — Every Graph Explained](#10-dashboard)
11. [Gait Analysis Section — Deep Dive](#11-gait-analysis-section)
12. [Technology Choices — Why We Used What We Used](#12-technology-choices)
13. [Limitations — What We Know We Haven't Solved](#13-limitations)
14. [Roadmap — Where This Goes Next](#14-roadmap)
15. [Hardware Practicality — Weight, Comfort, Wearability](#15-hardware-practicality)
16. [Cross-Questions Judges Will Ask — With Full Answers](#16-cross-questions)

---

## 1. What Problem Are We Solving?

### The core problem

Every day, millions of people walk with abnormal foot-loading patterns and have no idea.
A diabetic patient develops forefoot ulcers because they have been offloading their heel
for weeks. An athlete develops a stress fracture because one foot bears 30% more load
than the other across an entire training season. An elderly person's gait grows
progressively irregular — a known precursor to falls — but no one catches it until
after the fall.

The common thread: **foot loading problems are invisible until they cause injury.**

### Why detection is hard today

- Clinical gait labs cost $30,000–$100,000 per system and require specialist access
- Wearable insoles with clinical-grade pressure sensing cost $3,000–$8,000
- Consumer insoles (Nurvv, Superfeet) track running metrics but flag no clinical anomalies
- Physiotherapists rely on visual observation, which misses subtle bilateral asymmetries

### Our answer

SoleSense is a **low-cost, explainable, wearable foot-loading monitor** that:

1. Measures plantar pressure, temperature, and motion continuously using cheap sensors
2. Extracts 134 biomechanically meaningful features per footstep
3. Runs a transparent, rule-based risk indicator that tells you **exactly which loading
   pattern is abnormal and why**
4. Alerts the user in real time via LED, dashboard, and gait analysis card

The goal is not to replace a podiatrist. It is to give people and their clinicians
a continuous, affordable early-warning system.

---

## 2. What Is SoleSense?

SoleSense is a two-layer system:

### Layer 1 — Research software (current build)

A complete data-science pipeline that:
- Ingests the StepUP-P150 plantar pressure dataset (150 subjects, 100 Hz)
- Extracts 134 biomechanical features per footstep
- Scores each footstep with an explainable 0–100 risk indicator
- Displays results on a 3-page Streamlit + Plotly dashboard

This proves the algorithm works on validated real human data before hardware is finalised.

### Layer 2 — Physical hardware prototype (current build)

An ESP32-S3 microcontroller insole with:
- 2 active FSR pressure sensors — FSR1 (forefoot centre) and FSR2 (heel centre)
- TMP117 precision temperature sensor (±0.1 °C, I²C)
- MPU6050 IMU — 3-axis accelerometer (g) + 3-axis gyroscope (°/s), I²C
- Wi-Fi streaming at 20 Hz (HTTP POST JSON)
- Live Streamlit dashboard with anatomically correct foot map, gait analysis, temperature
  baseline, personal baseline comparison, and explainable risk

The same analytics pipeline runs on live sensor data with zero modification to the
risk engine or dashboard code.

---

## 3. Why This Problem Matters

### Diabetic foot disease

- 537 million people worldwide have diabetes (IDF 2021); 101 million in India alone
- 15–25% will develop a diabetic foot ulcer in their lifetime
- 85% of all lower-limb amputations in diabetics are preceded by a foot ulcer
- A foot ulcer costs ₹1–5 lakh to treat; amputation costs ₹4–8 lakh and ends mobility
- Root cause: **peripheral neuropathy destroys the pain signal.** The patient cannot feel
  the damage building. SoleSense replaces the lost pain signal with sensor data.

### Athletes and sports medicine

- Bilateral loading asymmetry > 10–15% correlates with stress fracture risk, IT band
  syndrome, and ACL re-injury
- Athletes have no affordable way to monitor day-to-day loading between clinic visits

### Elderly fall prevention

- Falls are the leading cause of injury death in people over 65
- Step-time variability (std > ~0.1 s) is a validated predictor of fall risk
  (Hausdorff et al. 2001 — doubles fall risk at high variability values)
- SoleSense monitors gait variability continuously and flags deterioration early

### Rehabilitation

- After surgery, patients are told to bear partial weight — no affordable tool verifies this
- SoleSense gives real-time objective feedback on bilateral weight distribution

---

## 4. System Architecture

```
╔══════════════════════════════════════════════════════════════════════════╗
║                      SOLESENSE DATA FLOW                                ║
╠══════════════╦═══════════════════════════════════════════════════════════╣
║ DATA SOURCES ║                                                           ║
║              ║  [Research]                    [Hardware]                 ║
║              ║  StepUP-P150 .npz             ESP32-S3 JSON              ║
║              ║  150 subjects · 100 Hz        20 Hz · Wi-Fi POST         ║
║              ║       │                            │                      ║
║              ║       ▼                            ▼                      ║
║              ║  data_loader.py          hardware_adapter.py              ║
║              ║       │                            │                      ║
║              ║       └────────────┬───────────────┘                      ║
╠══════════════╬════════════════════▼══════════════════════════════════════╣
║ SHARED SCHEMA║  pd.DataFrame · 1 row = 1 footstep / 1 sensor window     ║
╠══════════════╬═══════════════════════════════════════════════════════════╣
║ PREPROCESS   ║  Remove Exclude=1 · filter stance 0.15–2.5 s · validate  ║
╠══════════════╬═══════════════════════════════════════════════════════════╣
║ FEATURES     ║  pressure(49) + gait(22) + bilateral(51) + temporal(20)  ║
║ 134 total    ║                    = 134 features                         ║
╠══════════════╬═══════════════════════════════════════════════════════════╣
║ RISK ENGINE  ║  10 named rules · weighted sum / 170 × 100               ║
║              ║  ● NORMAL 0–29  ● MONITOR 30–59  ● ALERT 60–100         ║
╠══════════════╬═══════════════════════════════════════════════════════════╣
║ DASHBOARD    ║  🏠 Quick Analysis | 📊 Dataset Explorer | 📡 Live HW   ║
╚══════════════╩═══════════════════════════════════════════════════════════╝
```

**The one-file-swap principle:** Replacing `data_loader.py` with any hardware adapter
that returns the same DataFrame schema causes zero changes in preprocessing, features,
risk engine, or dashboard. This is the core architectural decision.

---

## 5. The Dataset

### Why StepUP-P150?

We needed a validated, high-resolution, publicly available plantar pressure dataset to
build and test the pipeline before finalising hardware. StepUP-P150 (University of New
Brunswick, 2023–2024) is the best publicly available option:

- 150 subjects — stable percentile estimates
- 100 Hz — sufficient temporal resolution for gait analysis
- 75×40 px at 0.5 cm/pixel — captures 4 anatomical regions with clinical detail
- 4 footwear conditions + 7 trial types — diverse movements
- CC BY 4.0 — fully open for research use

### Anatomical coordinate system

```
Row  0–14  │  TOE       ← row 0 = toe tip
Row 15–34  │  FOREFOOT  (metatarsal heads)
Row 35–54  │  MIDFOOT   (plantar arch)
Row 55–74  │  REARFOOT  ← row 74 = heel

Verified: CoP starts ~row 65 (heel strike) → ends ~row 10 (toe-off)
```

### What the dataset does NOT have

Temperature, IMU, simultaneous bilateral capture, per-subject demographics.
All of these are addressed by the hardware prototype or roadmap.

---

## 6. Hardware Prototype

### Components and why each was chosen

| Component | Why This One |
|---|---|
| **ESP32-S3 DevKitC-1** | Dual-core 240 MHz, 12-bit ADC, built-in Wi-Fi, Arduino-compatible, ~$5 |
| **FSR 402 / 406** | Ultra-thin (0.3 mm), flexible, 0.1–10 N range, ~$5 each |
| **TMP117** | ±0.1 °C (best-in-class for body temp), I²C, 1.8–3.3 V, ~$4 |
| **MPU6050** | 6-DOF (3-axis accel + 3-axis gyro), I²C, widely supported, ~$2 |
| **10 kΩ resistors** | Create measurable voltage from FSR resistance change |

Total BOM: ~$22–28 per insole.

### Why FSRs and not piezoelectric?

Piezoelectric sensors generate voltage only from *dynamic* (changing) force — they cannot
measure static loading (standing still). FSRs are piezoresistive — resistance decreases
under any force, static or dynamic. Since foot loading includes both static (standing)
and dynamic (walking) components, FSRs are the correct choice. They are also thinner
and cheaper.

### Why TMP117 for temperature?

The Milwaukee Protocol for diabetic foot monitoring requires detecting >2.2 °C bilateral
temperature asymmetry. TMP117 at ±0.1 °C accuracy captures this threshold. Cheaper
sensors (LM35, NTC thermistor) have ±0.5–1 °C accuracy — insufficient for clinical use.

### Why MPU6050 for IMU?

The MPU6050 gives us:
- Foot-strike detection (sharp deceleration peak at heel contact on AZ axis)
- Activity classification (standing vs walking vs running from dynamic accel magnitude)
- Gait variability (CV of acceleration magnitude across steps)
- Step detection and cadence estimation (via load-onset events combined with IMU peaks)
- Angular velocity for step timing when pressure alone is ambiguous

It is the most widely supported IMU module with mature Arduino libraries.

### FSR circuit — voltage divider

```
3.3V ─── [FSR] ───┬─── GPIO ADC input
                  │
               [10kΩ]
                  │
                 GND

At rest:   FSR ~100 kΩ  →  V_out ≈ 0.3 V  →  ADC ~370
Under foot: FSR ~1–5 kΩ →  V_out ≈ 2.5 V  →  ADC ~3100

ADC is 12-bit (0–4095). FSR2 used as heel sensor.
```

### Proxy-kPa formula and why 600

```
proxy_kPa = (ADC / 4095) × 600
```

Typical peak plantar pressure during normal walking: 100–800 kPa depending on region.
600 kPa is a conservative midpoint for the forefoot+heel range under shod walking.
This is a **relative scaling factor, not a calibration** — always labelled `p-kPa
(proxy, uncalibrated)` throughout the dashboard. Absolute calibration requires pressing
known weights and fitting an ADC→force curve.

### Current sensor placement (2-sensor prototype)

```
FSR1  →  Forefoot (centred in metatarsal zone)
FSR2  →  Heel (centred in rearfoot zone)
Midfoot sensor: NOT CONNECTED — shown as N/C in the foot SVG
```

### Single-insole limitation

This is a LEFT FOOT only prototype. All bilateral comparison features
(`asym_*`, `gait_symmetry_index`) are set to 0.0 and are not scored by the risk engine.
This is **correct behaviour** — no fake values are generated.

---

## 7. Software Pipeline

### Step 1 — Data ingestion (`src/data_loader.py`)

Reads `.npz` from StepUP-P150. Returns one row per footstep with the pressure array
attached (`shape = (101, 75, 40)` in kPa). This file is the only dataset-specific code.

### Step 2 — Preprocessing (`src/preprocessing.py`)

```
Input:  1793 rows (5 subjects, W1)
─ Remove Exclude=1 flagged steps  →  -145
─ Remove stance < 0.15 s          →  (typically 0)
─ Remove stance > 2.5 s           →  (typically 0)
Output: 1648 rows  (92% retained)
```

### Step 3 — Feature extraction (134 features)

Four modules run in sequence. Each is independently unit-tested.

### Step 4 — Risk scoring

`compute_risk(row: pd.Series) → RiskResult` — 10 rules evaluated, sub-scores summed,
normalised to 0–100, level determined, RiskResult returned with full factor detail.

### Step 5 — Dashboard

Three Streamlit pages. `page_quick_analysis()`, `page_dataset_explorer()`,
`page_live_hardware()`. The last one starts the Flask receiver singleton, pulls packets
from the rolling deque, converts to feature row, calls `compute_risk`, renders all
8 sections including the new Gait Analysis section.

---

## 8. Feature Engineering

### A. Basic Pressure Statistics

| Feature | Formula | Clinical meaning |
|---|---|---|
| `press_max_kpa` | `max(all pixels, all frames)` | Focal stress point — ulcer risk location |
| `press_mean_kpa` | `mean(active pixels)` | Average loading level |
| `press_std_kpa` | `std(active pixels)` | Spread — uneven distribution = warning |
| `press_p95_kpa` | 95th percentile | Near-peak, robust to noise |
| `contact_area_cm2` | `mean(active_px/frame) × 0.25 cm²` | Smaller = more concentrated load |

**Why 200 kPa threshold for peak pressure:**
IWGDF (International Working Group on the Diabetic Foot) guidelines identify
>200 kPa forefoot pressure as a significant ulcer risk factor. 75th percentile of
StepUP-P150 barefoot data ≈ 195 kPa — threshold sits just above normal distribution.

---

### B. Pressure-Time Integral (PTI) — The Most Important Metric

```
PTI = Σ (pixel_kPa × Δt)  =  Σ (pixel_kPa × 0.01 s)
      over all pixels × all stance frames at 100 Hz
Unit: kPa·s
```

**Why PTI and not just peak pressure:**

Tissue damage follows a dose-response model. A 300 kPa spike for 10 ms = 3 kPa·s.
A 150 kPa sustained pressure for 800 ms = 120 kPa·s. The sustained pressure causes
far more cumulative tissue damage. PTI captures both intensity *and* duration.
Bus et al. (Diabetes Care, 2004): *"PTI, not peak pressure, was the strongest predictor
of plantar ulceration in diabetic neuropathy."*

**Threshold derivation (50,000 kPa·s):**
Approximately the 75th percentile of PTI distribution across StepUP-P150 barefoot trials.
Data-informed, not clinically validated from outcome studies (that is Phase 3).

---

### C. Regional Loading Fractions

```
load_frac_R = Σ(pixel_kPa in region R, all frames) / Σ(all pixel_kPa, all frames)
```

The four regions always sum to 1.0. Tells you WHERE on the foot load concentrates.

**Normal walking distribution:**
- Forefoot: ~55–65% (at push-off)
- Rearfoot: ~25–35% (at heel strike)
- Midfoot: ~10% (arch)
- Toe: ~5%

**Forefoot > 60%:** Toe-walking, high heels, Achilles tightness, Charcot midfoot
**Rearfoot > 65%:** Antalgic gait protecting a sore forefoot, neurological conditions

**Threshold derivation:**
60% forefoot and 65% rearfoot ≈ 80th percentile of respective distributions in dataset.

---

### D. Centre of Pressure (CoP)

```
CoP_row(f) = Σ(pressure[r,c,f] × r) / Σ(pressure[r,c,f])   weighted centroid
CoP_col(f) = Σ(pressure[r,c,f] × c) / Σ(pressure[r,c,f])

Path length = Σ √((CoP_row(f) - CoP_row(f-1))² + (CoP_col(f) - CoP_col(f-1))²)
Unit: cm  (using 0.5 cm/pixel)
```

Traces the progression of the body's weight across the foot from heel-strike to toe-off.
Equivalent to clinical force-plate CoP measurement. Abnormal trajectories indicate
gait dysfunction.

---

### E. Normalized Symmetry Index (NSI)

```
NSI = |L − R| / ((L + R) / 2) × 100%
```

Applied to every bilateral feature. Zero = perfect symmetry.
Division-by-zero protected throughout: if (L + R) = 0, NSI = 0.

**Why not just L − R absolute difference?**
Absolute difference depends on body weight and speed. A 50 kPa difference means
different things for a 50 kg vs 100 kg person. NSI normalises by the mean — comparable
across subjects, sessions, and conditions.

**Directional version:** `asym_dir = L − R` (positive = left dominant)

**Clinical thresholds:**
- NSI > 10%: moderate asymmetry (literature: Seeley et al. 2010, healthy < 10–15%)
- NSI > 20%: high asymmetry (associated with compensatory loading patterns)

---

### F. Gait Timing Features

```
step_time(n) = (start_frame(n+1) - start_frame(n)) / 100    at 100 Hz
cadence = 60 / step_time_mean                                steps per minute
GSI (Gait Symmetry Index) = |stride_L - stride_R| / ((stride_L + stride_R)/2)
step_time_std = std(step_time_1, ..., step_time_N)
```

**Why step_time_std matters:**
Hausdorff et al. (2001) showed step-time variability is a stronger fall predictor
than mean gait speed in elderly subjects. Our 0.15 s threshold ≈ 90th percentile
of StepUP-P150 distribution.

---

### G. Temporal Features — Rolling Window and Persistence

**Rolling window (5 steps):**
```
roll_mean_F = mean(F_t, F_{t-1}, F_{t-2}, F_{t-3}, F_{t-4})
```
Why 5 steps? ~3.5 s of recent history — long enough to distinguish sustained patterns
from transient spikes, short enough to respond to changing conditions in seconds.

**Persistence score:**
```
persistence_F = count(last 5 steps where F > threshold_F) / 5   ∈ [0.0, 1.0]
```
1.0 = elevated in every recent step = confirmed sustained pattern.
0.0 = no recent elevation = transient event.

This is the mechanism that prevents false alarms from a single noisy reading.

---

## 9. The Risk Engine

### Why rule-based, not ML?

1. **No outcome labels** — StepUP-P150 has no injury outcomes to supervise on
2. **Clinical explainability requirement** — "forefoot carries 68% of load" is actionable;
   "the model says 73%" is not
3. **Regulatory clarity** — rule-based systems with documented thresholds are easier
   to audit than neural networks for medical use
4. **No ML framework needed** — the engine runs on any Python environment, including
   embedded MCUs via the TinyML roadmap

### The 10 Rules — full detail

#### Rule 1 — Elevated Peak Pressure
```
Feature:    press_max_kpa       Threshold: 200 kPa    Weight: 25
Derivation: IWGDF guidelines + 75th percentile of dataset
Meaning:    Focal pressure high enough to begin impeding tissue perfusion
```

#### Rule 2 — High Pressure-Time Exposure
```
Feature:    pti_total_kpa_s     Threshold: 50,000 kPa·s   Weight: 25
Derivation: 75th percentile of PTI distribution, barefoot trials
Meaning:    Cumulative loading exceeds what most people experience in a normal step
```

#### Rule 3 — Loading Asymmetry
```
Feature:    asym_pti_total_kpa_s   Threshold: 20%   Weight: 20
Derivation: Seeley et al. (2010) — healthy < 10–15%; 20% = clearly elevated
Meaning:    One foot accumulates significantly more total load than the other
```

#### Rule 4 — Pressure Asymmetry
```
Feature:    asym_press_mean_kpa   Threshold: 10%   Weight: 15
Derivation: Lower threshold than Rule 3 to catch early-stage asymmetry
Meaning:    Average pressure per pixel is asymmetric — different loading quality
```

#### Rule 5 — Forefoot Overload
```
Feature:    load_frac_forefoot   Threshold: 0.60   Weight: 15
Derivation: 80th percentile of forefoot fraction distribution
Meaning:    Metatarsal region bearing >60% — toe-walking, high-heel pattern
```

#### Rule 6 — Rearfoot Overload
```
Feature:    load_frac_rearfoot   Threshold: 0.65   Weight: 10
Derivation: 80th percentile of rearfoot fraction distribution
Meaning:    Heel bearing >65% — antalgic gait protecting a sore forefoot
```

#### Rule 7 — Gait Temporal Variability
```
Feature:    step_time_std_s   Threshold: 0.15 s   Weight: 15
Derivation: ~90th percentile of step_time_std across dataset; Hausdorff 2001
Meaning:    Step timing is irregular — fatigue, pain, neurological, or falling risk
```

#### Rule 8 — Gait Timing Asymmetry
```
Feature:    gait_symmetry_index   Threshold: 0.10   Weight: 10
Derivation: Robinson et al. (1987) — clinical gait asymmetry definition
Meaning:    One side's stride takes >10% longer — limping or pain avoidance
```

#### Rule 9 — Persistent Pressure
```
Feature:    persistence_pti_total_kpa_s   Threshold: 0.60   Weight: 20
Derivation: ≥3 of last 5 steps above PTI threshold = sustained pattern
Meaning:    Not a one-off spike — repeated elevated loading across recent steps
```

#### Rule 10 — Persistent Asymmetry
```
Feature:    asym_load_forefoot   Threshold: 20%   Weight: 15
Derivation: NSI on forefoot fraction, consistent across multiple steps
Meaning:    Structural or habitual forefoot imbalance, not a single step artefact
```

### Score calculation
```
raw_score  = Σ weight_i  for each triggered rule_i
risk_score = min(100, raw_score / 170 × 100)

Maximum possible: all 10 rules trigger → 170/170 × 100 = 100
Typical MONITOR: 2–3 rules → 50–65/170 × 100 = 29–38
```

### Risk level boundaries
```
NORMAL  [ 0–29 ]   ~0–1 rules triggered
MONITOR [30–59 ]   ~2–3 rules triggered
ALERT   [60–100]   ~4+ rules triggered
```

---

## 10. Dashboard

### Page 1 — Quick Analysis

**Risk gauge:** Plotly Indicator dial, 0–100, green/amber/red zones. Delta shows
change from the 30-point MONITOR threshold. Single number summarising current risk.

**Bilateral bar charts (PTI, peak pressure, stance time):** Left and right bars with NSI
% in subtitle. Shows which foot is bearing more load and by how much.

**Polar/radar chart:** 6 axes (Peak P., Mean P., PTI scaled, Forefoot Load, Rearfoot
Load, CoP Path). Left = blue polygon, Right = red. Perfect symmetry = overlapping shapes.

**Dual donut (regional loading):** Outer ring = % per region. Shows where on the foot
load concentrates.

**Asymmetry waterfall:** Signed NSI % per feature. Positive = left dominant, negative =
right dominant. ±10% dashed threshold lines.

**Explainable risk rows:** One row per rule. ✅ not triggered / ⚠️ triggered. Shows
exact value, threshold, and sub-score. This is the core "why" explanation.

---

### Page 2 — Dataset Explorer

**Risk sparkline:** Step-by-step risk score across a trial. Coloured background zones.
Shows whether risk is consistently elevated or only occasional spikes.

**Plantar heatmap:** Mean pressure map for left and right foot. Colour scale = plasma
(dark = low, bright = high). Dashed lines at anatomical region boundaries. Shows
exactly where on the foot pressure concentrates — direct ulcer risk visualisation.

**CoP trajectory:** Pressure-weighted centroid path from heel-strike (green circle) to
toe-off (red triangle) overlaid on mean pressure background. Abnormal paths indicate
gait dysfunction.

**Historical trend:** Risk score by trial and footwear condition across sessions.
Shows whether shoes reduce or increase loading compared to barefoot.

---

### Page 3 — Live Hardware

#### Overall status banner
Gradient border coloured by risk level. LED dot (glows green/amber/red). Large risk
score badge. Activity and trend pills.

#### Section ① — Left Foot Pressure Map
Anatomically correct SVG. Toes/forefoot = TOP (y≈78), heel = BOTTOM (y≈260).
One dot per active sensor. Dot radius ∝ ADC reading. Colour: green (<30%) → amber
(30–60%) → red (>60% of scale). Midfoot shows N/C grey circle.

#### Section ② — Load Over Time
Three traces: FSR1 (forefoot, blue), FSR2 (heel, light blue), Total (white, filled).
X-axis = time in seconds (last N-second window). Y-axis = proxy kPa (p-kPa), labelled
as uncalibrated. Dashed threshold at 30% of scale.

*What the chart tells you:* Rhythmic alternating peaks = walking. Flat elevated line =
standing under sustained load. Irregular spikes = uneven gait.

#### Section ③ — Pressure-Time Exposure & Persistence
6 metric cards + dual-axis bar chart. Bar height = average p-kPa per region.
Overlaid orange bars = persistence %. Annotation: "⚠ Proxy values — not calibrated kPa."

#### Section ④ — Temperature
Cards: Current °C · Session Baseline · Deviation (current − baseline) · Trend direction.
Sparkline with green baseline band (±0.5 °C). Deviation > 1.5 °C → ALERT colour.

*Why it matters:* Warming at a location signals inflammation or friction. Bilateral
temperature asymmetry > 2.2 °C is the Milwaukee Protocol threshold for diabetic
Charcot foot pre-warning.

#### Section ⑤ — Gait Analysis
Full detail in Section 11 below.

#### Section ⑥ — Regional Hotspot
Which region is dominant, reason, duration. Turns amber at >5 s, red at >10 s.
*Prolonged single-region loading is the mechanism for pressure injuries.*

#### Section ⑦ — Personal Baseline
Session baseline load vs current window. Deviation %. Risk history sparkline with
green/amber/red zone backgrounds. Session load history sparkline with baseline line.

#### Section ⑧ — Risk Breakdown & Insights
Gauge + explainable factor rows + recommended action (plain language) + LED state footer.

---

## 11. Gait Analysis Section

This section (Section ⑤ in Live Hardware) is the most technically rich part of the
dashboard. It uses **only real MPU6050 data** — no invented metrics.

### What the MPU6050 provides

```
ax, ay, az   →  acceleration in g along each axis
               (1 g = 9.81 m/s², stationary foot reads ~(0, 0, 1))
gx, gy, gz   →  angular velocity in °/s around each axis
               (zero when foot is not rotating)
```

### Derived gait metrics and their formulas

**Total acceleration magnitude:**
```
|A|(t) = √(ax(t)² + ay(t)² + az(t)²)
Unit: g
Stationary foot: |A| ≈ 1.0 g (gravity only)
Walking foot:    |A| oscillates 0.8–1.4 g with each step
```

**Dynamic acceleration (motion component):**
```
dynamic_accel = mean(||A| − 1.0|)   across window
Unit: g
Near 0 = stationary, higher = more movement above gravity
```

**Movement intensity (0–100 score):**
```
movement_intensity = min(100, dynamic_accel × 100)
0   = completely stationary
30  = slow walking
60  = brisk walking
100 = running / high impact
```
Derived from dynamic accel — purely proportional, no external calibration needed.

**Gait variability (Coefficient of Variation of |A|):**
```
gait_CV = std(|A|) / mean(|A|) × 100%
Unit: %
Low (< 15%)  = steady, consistent gait
High (> 30%) = irregular, inconsistent motion pattern
```
CV of acceleration magnitude captures gait rhythmicity without requiring step
event detection — it measures how consistent the foot's motion pattern is across
the entire window.

**Step count estimate:**
```
step_count_est = round(cadence_est_imu × window_s / 60)
```
Uses cadence derived from FSR load-onset events (more reliable than pure IMU step
detection for a foot-mounted sensor at 20 Hz).

**Step timing (when cadence is reliable — ≥2 steps detected):**
```
step_time_mean_s = 60 / cadence_est_imu
stride_time_s    = step_time_mean_s × 2     (two steps = one stride)
step_time_std    = from feature_row (FSR-derived)
variability flag = HIGH if step_time_std > 0.15 s
```
Stride time shown only as an estimate — single insole cannot directly measure
bilateral stride.

**Gait vs personal baseline:**
```
gait_baseline_val = mean(first 20 readings of |A| history)  [session start]
gait_current_val  = mean(last 10 readings of |A| history)   [recent window]
gait_deviation    = (current - baseline) / baseline × 100%
```

**Gait trend:**
```
|deviation| < 5%  → STABLE    (green)
5% ≤ |deviation| < 15% → CHANGING (amber)
|deviation| ≥ 15%  → DEVIATING (red)
```

### Activity classification logic

```python
def _activity_class(dynamic_accel, gyro_mag, cadence):
    if dynamic_accel < 0.05 AND gyro_mag < 2.0:
        return "STANDING / STATIC"   # near-zero motion
    elif cadence > 80:
        return "RUNNING"             # fast pace (>80 spm)
    elif cadence > 40:
        return "WALKING"             # normal walking (40–80 spm)
    elif dynamic_accel > 0.3:
        return "ACTIVE / DYNAMIC"    # high motion, slow cadence
    else:
        return "LOW ACTIVITY"        # some motion, not classified as walking
```

### GAIT ANALYSIS card logic

```
State                                    Card level   Plain text
─────────────────────────────────────────────────────────────────────────────
Foot at rest / standing                  NORMAL 🟢  "No significant movement detected"
Trend STABLE and CV < 15%               NORMAL 🟢  "Consistent with session baseline"
Trend CHANGING or 15% ≤ CV < 30%        MONITOR 🟡 "Moderate deviation from baseline"
Trend DEVIATING or CV ≥ 30%             MONITOR 🔴 "Notable deviation, check for fatigue"
```

### Acceleration chart (existing chart, improved)

- **AX (forward/back):** Anteroposterior motion — peaks during push-off
- **AY (side/side):** Mediolateral sway — elevated in asymmetric gait
- **AZ (up/down):** Vertical bounce — largest signal in walking
- **|A| magnitude:** Total motion intensity — most clinically interpretable trace
- **1 g reference line + green band:** Shows what a stationary foot looks like

### Gyroscope chart (existing chart, improved)

- **GX (roll rate):** Foot rolling inward/outward (pronation/supination)
- **GY (pitch rate):** Foot rocking toe-to-heel
- **GZ (yaw rate):** Foot twisting — elevated in toe-out/in gait
- **|G| magnitude:** Total angular speed

### Movement intensity history sparkline (new)

Session-long rolling plot of mean |A| per window. Green band = ±5% of baseline.
Shows whether movement has changed since session start — the personal baseline concept
applied to gait motion rather than just load.

---

## 12. Technology Choices

### Why Python?
NumPy/Pandas/SciPy provide the most mature ecosystem for signal processing and
feature extraction. StepUP-P150 is in NumPy `.npz` format. Python is also lingua franca
for ML, important for the TinyML roadmap.

### Why Streamlit?
Streamlit builds a production-quality interactive dashboard in pure Python. Every slider
update re-runs the Python function — that is why charts update live without a submit button.
For a prototype, it provides the fastest path from algorithm to visual.

### Why Plotly?
Interactive charts with zoom, pan, and hover tooltips. Matplotlib would produce static
images. Plotly integrates natively with Streamlit via `st.plotly_chart`.

### Why rule-based risk engine?
- No outcome labels in the dataset (cannot train a supervised model)
- Clinical explainability is a regulatory requirement
- Rule-based systems with documented thresholds are easier to audit
- Every sub-score is traceable to a specific sensor reading

### Why ESP32-S3?
Wi-Fi built-in (no shield needed), 12-bit ADC (better resolution than Arduino's 10-bit),
240 MHz dual-core, Arduino-compatible libraries, $5 cost.

### Why Wi-Fi and not BLE for prototype?
HTTP POST debugging is trivial (curl, browser). No pairing required. BLE is planned for
production to reduce power consumption by ~5×.

### Why Flask for receiver?
Simplest Python HTTP server. Runs in a background thread inside Streamlit. Thread-safe
deque buffer allows concurrent read/write. 400-packet buffer = 20 s history even if
dashboard disconnects briefly.

---

## 13. Limitations

| Area | Honest Assessment |
|---|---|
| FSR calibration | ADC readings are proxies. Bench calibration with known weights needed for clinical kPa |
| Only 2 FSRs active | Midfoot not connected. Regional distribution is forefoot/heel binary only |
| Single insole | Bilateral rules inactive. No left-right comparison from hardware |
| Thresholds experimental | Percentile-based on 150 healthy subjects. Not from longitudinal injury outcomes |
| 20 Hz vs 100 Hz | 5× lower than dataset. PTI and gait timing estimates less precise |
| No battery | Prototype on USB power. LiPo + charging circuit is Phase 2 |
| No persistent storage | Session history resets on power cycle. No longitudinal tracking |
| Gait metrics from FSR | Cadence/stance estimated from load-onset, not direct IMU step detection |
| Shoe shoe weight | Development board in current form. Production PCB target < 15 g |

---

## 14. Roadmap

```
Phase 1 ✅  Research prototype (DONE)
            StepUP-P150 pipeline · ESP32-S3 2-FSR prototype · rule engine
            3-page dashboard · gait analysis section · 78 tests

Phase 2 🔄  Validated hardware (6–9 months)
            4-FSR calibrated insole · LiPo battery · BLE · custom PCB
            30-subject physiotherapy pilot · provisional patent

Phase 3 📋  Bilateral + mobile (12 months)
            Two insoles simultaneously · Flutter mobile app
            Cloud backend · bilateral rules fully active

Phase 4 🧠  TinyML personalisation (18 months)
            Personal autoencoder per user (50 features → 16 → 8 → 16 → 50)
            TFLite Micro on nRF52840 (<256 KB flash)
            Anomaly score fused with rule score: 70% rule + 30% anomaly

Phase 5 🏥  Clinical validation (24 months)
            IRB-approved 300-subject prospective study
            CDSCO/CE/FDA regulatory pathway
```

---

## 15. Hardware Practicality

### Weight

| Component | Weight |
|---|---|
| ESP32-S3 DevKitC board | ~20 g |
| 2× FSR sensors | < 1 g |
| TMP117 + MPU6050 | ~4 g |
| Wiring + connectors | ~5 g |
| LiPo 500 mAh (planned) | ~10 g |
| Enclosure (foam + plastic) | ~5 g |
| **Total prototype** | **~45 g** |

A standard insole weighs 30–50 g. Our prototype doubles it but adds < 1% of body weight
for a 70 kg person. Production PCB target: < 15 g total electronics.

### Comfort

FSR sensors are 0.3 mm thick — thinner than a credit card. They do not create pressure
hotspots when embedded in foam. The main discomfort in the prototype is cable routing
from insole to ankle. Production design resolves this with a heel-cup enclosure
or integrated BLE module.

Thickness: prototype adds ~6–8 mm. Production target: 4 mm (standard orthotic
insole thickness). Compatible with most athletic and therapeutic footwear.

### Shoe compatibility

Diabetic therapeutic footwear typically has extra depth (8–12 mm) specifically to
accommodate orthotics — SoleSense insoles fit within this space. Standard athletic
shoes have 3–6 mm removable insoles that can be replaced with the sensor insole.

---

## 16. Cross-Questions Judges Will Ask

---

**Q1: Where do your thresholds come from?**

Two sources: (a) Clinical literature — 200 kPa peak pressure from IWGDF guidelines,
10% gait asymmetry from Seeley et al. 2010, 0.15 s step variability from Hausdorff
et al. 2001. (b) Data distribution — most thresholds sit at the 75th–80th percentile
of the StepUP-P150 distribution. All are labelled EXPERIMENTAL because clinical
validation (longitudinal injury outcomes) is Phase 3.

---

**Q2: How is this different from Nurvv Run or Moticon?**

Nurvv is for runners only, no temperature, no explainable clinical risk score, $250.
Moticon is for research labs, $3,000+, no diabetic foot focus, no real-time risk.
SoleSense: ~$25 BOM, diabetic foot + sports + elderly focus, explainable rule engine,
temperature monitoring, full gait analysis, open-source analytics.

---

**Q3: You only have 2 FSRs — how is that sufficient?**

The forefoot/heel ratio is the most clinically relevant pressure axis. Forefoot and
heel are the two primary ulceration sites for diabetic foot. Midfoot is the least
critical region clinically. The hardware supports 4 FSRs — only 2 are connected in
the current prototype to validate end-to-end pipeline. Phase 2 connects all 4.

---

**Q4: FSR values are proxy-kPa — doesn't that make results meaningless?**

No. The regional fractions (Forefoot %, Heel %) and persistence scores are ratio-based
— they do not depend on absolute calibration. The forefoot/heel ratio from two ADC
readings is meaningful even without calibration. Full absolute calibration is Phase 2.
Every chart is clearly labelled "p-kPa (proxy, uncalibrated)" so no one is misled.

---

**Q5: Why not use a CNN on the pressure images directly?**

Three reasons: (a) No outcome labels for supervised training. (b) 101×75×40 = 303,000
values requires a 3D-CNN with millions of parameters — impractical on nRF52840
with 256 KB flash. (c) 150 healthy subjects with no pathological examples is insufficient
for a robust classifier. The autoencoder uses 50 engineered features — fits in edge
hardware and detects personal anomalies without requiring outcome labels.

---

**Q6: How does the system handle people with naturally asymmetric gait?**

The personal baseline comparison (Session ⑦ and gait analysis) tracks deviation from
*that user's own baseline*, not a population average. If someone always walks at 15%
asymmetry, their baseline captures that — only *worsening* is flagged. The TinyML
autoencoder will reinforce this by training per-user, not per-population.

---

**Q7: What is PTI and why does it matter more than peak pressure?**

PTI = Σ(pressure × time) = cumulative loading. Tissue damage follows a dose-response:
sustained moderate pressure causes as much damage as a brief intense spike. Bus et al.
(Diabetes Care, 2004) showed PTI, not peak pressure, was the strongest predictor of
ulceration in neuropathy. Our risk engine gives PTI weight 25/170 — tied for highest
with peak pressure.

---

**Q8: Why is your gait variability threshold 0.15 s?**

Hausdorff et al. (2001, Archives of Neurology) showed increasing step-time variability
correlates with fall risk in elderly subjects. 0.15 s step-time std ≈ 90th percentile
of the StepUP-P150 distribution — above this, timing irregularity is meaningful.
This is a conservative threshold (more false positives) chosen to minimise missed
real risk events.

---

**Q9: Why is the gait variability CV formula std/mean × 100?**

Coefficient of variation normalises variability by the mean — making it comparable
across people who walk at different speeds (different mean step times). A CV of 15%
means step-to-step variation is 15% of the mean step duration, which is meaningful
regardless of whether the person walks fast or slow. This is standard biostatistics for
comparing variability across different-scale measurements.

---

**Q10: How does the Gait Analysis card choose its interpretation text?**

Four states based on two independent signals: (1) activity type from IMU classification
and (2) gait trend from personal baseline deviation + variability CV:
- Rest/standing → NORMAL
- Active, trend stable, CV < 15% → NORMAL
- Active, trend changing OR CV 15–30% → MONITOR (amber)
- Active, trend deviating OR CV ≥ 30% → MONITOR (red)
Both signals must be consistent before an elevated state is shown — reduces false alarms.

---

**Q11: What does "|A| = 1 g" mean and why is it the reference?**

When a foot is completely stationary (standing), the only acceleration measured is
gravity: 1 g = 9.81 m/s² downward. So a stationary MPU6050 reads approximately
(ax≈0, ay≈0, az≈1.0) with total magnitude |A| ≈ 1.0 g. Deviation from 1 g indicates
foot movement. Dynamic_accel = mean(||A| − 1|) captures this deviation cleanly.

---

**Q12: Does the IMU cadence agree with the FSR cadence?**

The current implementation uses FSR load-onset events (pressure threshold crossings)
for cadence estimation — this is more reliable than pure accelerometer peak detection
at 20 Hz. IMU confirms the activity class (WALKING if cadence > 40 spm). Both signals
are shown separately to allow cross-checking. Disagreement between the two would
indicate a sensor issue.

---

**Q13: What if someone is doing stair climbing or cycling — does the classification fail?**

The classification handles STANDING, WALKING, RUNNING, ACTIVE DYNAMIC, and LOW
ACTIVITY. Stair climbing would register as ACTIVE DYNAMIC (high accel, low cadence)
which is the correct conservative flag — "unusual motion, not classified as level
walking." Cycling would show low FSR load + characteristic IMU rotation patterns, likely
classified as LOW ACTIVITY. The classification is a first-pass filter, not a precise
activity recognition system.

---

**Q14: How do you prevent the session baseline from drifting during a long session?**

The session baseline is computed from the first 20 readings (≈ first 20 refresh cycles
after session start) and then frozen. It does not drift with the session. The user can
also press "Set Temp Baseline" in the sidebar to reset it manually. This is the same
approach used for temperature baseline — personal reference at session start, not
rolling average.

---

**Q15: The foot SVG — is the orientation anatomically correct?**

Verified: FSR1 dot is at SVG y=78 (top region = forefoot). FSR2 dot is at SVG y=260
(bottom region = heel). The foot path starts at y=10 (toe tip) and the heel curve is
at y=280–285. FOREFOOT label at y=48 (top), HEEL label at y=298 (bottom). This is
anatomically correct: toes/forefoot at the top of the image, heel at the bottom.
Confirmed by verification script during development.

---

**Q16: How many calculations happen per dashboard refresh?**

Per 2-second refresh cycle (default):
- ~40 packets received at 20 Hz
- Feature row computation: ~15 arithmetic operations on numpy arrays
- Risk engine: 10 rule evaluations
- Dashboard: ~8 Plotly charts generated with full layout
- Session state updates: 3–4 deque appends

Total: < 100 ms computation per refresh cycle. The 2-second sleep is for user
readability, not computational limitation.

---

**Q17: What is the gait_CV specifically measuring?**

CV (Coefficient of Variation) of |A| = std(|A| across window) / mean(|A| across window) × 100%.
This measures how *consistent* the foot's total acceleration magnitude is over the
recent window. During steady walking, |A| oscillates rhythmically → low CV.
During irregular or halting gait, |A| varies erratically → high CV.
It is analogous to measuring whether a heartbeat is regular (low HRV) or irregular
(high HRV) — but for foot motion.

---

**Q18: Why store gait history in session state and not a database?**

Session state (Streamlit's in-memory dict) provides instant read/write with no I/O
overhead. It persists across dashboard refreshes within a session. It resets when
the user closes the browser or the Streamlit server restarts — appropriate for a
single-session monitoring prototype. Phase 2 adds a FastAPI + PostgreSQL backend
for longitudinal multi-session storage.

---

**Q19: What makes SoleSense different from a pedometer?**

A pedometer counts steps (yes/no). SoleSense measures:
- WHERE on the foot pressure is applied (forefoot vs heel fraction)
- HOW MUCH cumulative load (PTI in proxy kPa·s)
- HOW CONSISTENTLY the motion pattern is sustained (gait variability CV)
- HOW the temperature is changing from personal baseline
- WHAT the foot's motion quality looks like in 3 dimensions (accel + gyro)
- AGAINST the person's own reference (personal baseline comparison)
- WITH a plain-language explanation of what is abnormal

A pedometer tells you how many steps. SoleSense tells you the quality of each one.

---

**Q20: Is there anything fake or simulated in the Live Hardware page?**

In real hardware mode: no. Every value comes from the ESP32-S3.
In mock mode (🧪 checkbox): yes — synthetic walking packets are generated using
sinusoidal patterns to simulate walking. Mock mode is clearly labelled with a blue
info banner and a "Mock mode" badge. There is no way to accidentally mistake
mock data for real hardware data.

---

**Q21: How does the risk engine handle missing or NaN features?**

Each rule checks `row.get(feat_col, None)`. If the value is None or NaN, the rule
is silently skipped (not counted as triggered, not counted as missed). This means
a feature row with only 3 of 10 features available still gets a meaningful partial
risk score. This NaN-safety is tested in `test_risk_engine.py` (test: missing
feature graceful skip).

---

**Q22: Why does the dashboard say "proxy kPa" instead of just "kPa"?**

Because it is honest. The FSR → ADC → scaled value is not a calibrated pressure
measurement. Calling it "kPa" would be misleading and potentially dangerous (someone
might compare it against clinical kPa thresholds). "proxy kPa" communicates:
"this is in the same order of magnitude as kPa and is proportional to real pressure,
but you should not rely on the absolute value for clinical decisions." The
`p-kPa (proxy, uncalibrated)` label appears on every relevant axis, card, and chart.

---

**Q23: What is the Milwaukee Protocol and how does SoleSense relate to it?**

The Milwaukee Protocol (Lavery et al., 2007, Diabetes Care) is a clinical practice
guideline: diabetic patients should check foot temperature daily; if any site is
>2.2 °C warmer than the corresponding contralateral site, reduce activity and
consult a clinician. This simple protocol reduced ulceration by 10× in the study.
SoleSense implements the temperature monitoring component: TMP117 at ±0.1 °C can
detect a 2.2 °C threshold. Bilateral comparison requires two insoles (Phase 2).
Current prototype: deviation from personal session baseline, which catches
unilateral warming trends.

---

**Q24: What do the gyroscope readings specifically tell you about gait?**

- **GX (roll rate):** How fast the foot rolls inward or outward per second. High GX →
  excessive pronation (roll in) or supination (roll out). Common in flat-footed gait
  or in running with poor foot mechanics.
- **GY (pitch rate):** Toe-to-heel rocking rate. During heel-strike, foot pitches
  rapidly forward — GY peaks. Reduced GY peak = "shuffling gait" (no heel strike).
- **GZ (yaw rate):** Foot twisting about vertical axis. Elevated GZ = toe-out or
  toe-in gait, often seen in hip or knee compensation patterns.
- **|G| total:** Overall angular speed of the foot. Combined with |A|, gives a
  picture of the foot's full 3D motion intensity.

---

**Q25: What would a physiotherapist do with this data?**

A physiotherapist would look at:
1. **Forefoot fraction trending > 60%** → suspect Achilles tightness or toe-walking
   pattern → prescribe calf stretching
2. **PTI persistently elevated on one foot** → offloading asymmetry → check for pain
   avoidance, prescribe gait retraining
3. **Step-time std > 0.15 s** → irregular rhythm → check for fatigue, neurological
   signs, or muscle weakness
4. **Temperature rising from baseline** → possible inflammation → reduce activity
5. **DEVIATING gait trend mid-session** → something changed during this session →
   ask the patient what they felt at that time point

The dashboard gives the physiotherapist objective, time-stamped data to anchor
clinical conversations — replacing "how does your foot feel?" with "your forefoot
was carrying 67% of load for 8 minutes and then your gait rhythm became irregular."

---

*For funding strategy and scale-up planning, see FUNDING.md in this directory.*
*For the architecture overview and quick-start, see the main README.md.*

---

<p align="center">
SoleSense · Research Prototype · Not a Medical Device<br>
Dataset: StepUP-P150 (CC BY 4.0) · University of New Brunswick 2023–2024<br>
Hardware: ESP32-S3 + FSR 402 + TMP117 + MPU6050
</p>
