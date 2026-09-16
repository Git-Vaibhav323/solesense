# SoleSense Feature Dictionary

Generated from `src/feature_pipeline.py` output (134 columns).  
Dataset: StepUP-P150 | Unit of analysis: **one footstep** (per-step row)  
Spatial: 0.5 cm/pixel | Temporal: 100 Hz (0.01 s/frame)

---

## Metadata Columns

| Feature | Description | Unit |
|---|---|---|
| `subject_id` | Participant identifier (001–150) | str |
| `footwear` | Footwear condition (BF/ST/P1/P2) | str |
| `trial` | Walking speed condition (W1–W4) | str |
| `footstep_id` | Index of this footstep within its trial | int |
| `side` | Foot side: Left or Right | str |
| `stance_time_s` | Duration of ground contact = (EndFrame−StartFrame) / 100 | seconds |
| `foot_length_cm` | Measured foot length in cm (from metadata, ×0.5 cm/px) | cm |
| `foot_width_cm` | Measured foot width in cm | cm |

---

## A — Basic Pressure Statistics

These characterise the pressure distribution across all active pixels and all frames of a single footstep contact.

| Feature | Description | Formula | Unit |
|---|---|---|---|
| `press_mean_kpa` | Mean pressure of all non-zero pixels across all frames | mean(active pixels) | kPa |
| `press_median_kpa` | Median pressure of active pixels | median(active pixels) | kPa |
| `press_max_kpa` | Global peak pressure anywhere in the footstep | max(arr) | kPa |
| `press_std_kpa` | Standard deviation of active pixel pressures | std(active pixels) | kPa |
| `press_p25_kpa` | 25th percentile of active pixels | P25(active) | kPa |
| `press_p75_kpa` | 75th percentile | P75(active) | kPa |
| `press_p95_kpa` | 95th percentile — near-peak loading | P95(active) | kPa |
| `contact_area_cm2` | Mean contact area per stance frame | mean(active_px/frame) × 0.25 cm² | cm² |
| `active_frame_count` | Number of frames with any sensor activation | count(frames where sum>0) | frames |

---

## B — Pressure-Time Exposure

Captures the cumulative loading burden. A key SoleSense metric because repeated moderate loading can be as damaging as isolated peaks.

| Feature | Description | Formula | Unit |
|---|---|---|---|
| `pti_total_kpa_s` | Pressure-Time Integral: total loading over entire stance | Σ(pixel_kpa × 0.01s) all pixels, all frames | kPa·s |
| `pti_per_cm2_kpa_s` | PTI normalized by mean contact area | pti_total / contact_area_cm2 | kPa·s/cm² |
| `mean_total_force_kpa` | Mean total foot force per active frame | mean(sum of all pixel kPa per frame) | kPa |
| `peak_total_force_kpa` | Peak total foot force in any single frame | max(sum of all pixel kPa per frame) | kPa |
| `loading_rate_kpa_s` | How rapidly force increases from first contact to peak | peak_force / time_to_peak | kPa/s |

---

## C — Regional Loading

The normalized footstep image (75×40 px) is divided into 4 anatomical regions (row 0 = toe, row 74 = heel). Fractions sum to 1.0.

| Region | Row range | Anatomy |
|---|---|---|
| TOE | 0–14 | Digit region |
| FOREFOOT | 15–34 | Metatarsal heads |
| MIDFOOT | 35–54 | Arch |
| REARFOOT | 55–74 | Heel |

For each region R ∈ {toe, forefoot, midfoot, rearfoot}:

| Feature | Description | Unit |
|---|---|---|
| `load_frac_{R}` | Fraction of total cumulative load in region R | 0–1 |
| `load_kpa_{R}` | Absolute cumulative kPa sum in region R | kPa |
| `peak_kpa_{R}` | Peak pixel pressure in region R | kPa |

---

## D — Peak Pressure Location

| Feature | Description | Unit |
|---|---|---|
| `peak_row_px` | Row index of the global pressure peak (0=toe, 74=heel) | px |
| `peak_col_px` | Column index of the global peak | px |
| `peak_row_cm` | Peak row converted to cm from toe edge | cm |
| `peak_col_cm` | Peak col converted to cm from medial edge | cm |
| `peak_frame_idx` | Frame index when global peak occurs | frame @ 100 Hz |

---

## E — Center of Pressure (CoP)

Computed per frame as the pressure-weighted centroid of the contact image. Traces the progression from heel-strike to toe-off.

| Feature | Description | Formula | Unit |
|---|---|---|---|
| `cop_start_row_cm` | CoP row at first active frame (heel-strike region) | Σ(p·row)/Σp at frame 0 | cm |
| `cop_start_col_cm` | CoP column at first active frame | Σ(p·col)/Σp at frame 0 | cm |
| `cop_end_row_cm` | CoP row at last active frame (toe-off region) | — | cm |
| `cop_end_col_cm` | CoP column at last active frame | — | cm |
| `cop_excursion_row_cm` | Total AP displacement = end_row − start_row | signed | cm |
| `cop_excursion_col_cm` | Total ML displacement | signed | cm |
| `cop_path_length_cm` | Total arc length of CoP trajectory | Σ√(Δrow²+Δcol²) | cm |
| `cop_mean_velocity_cm_s` | Mean CoP travel speed | path_length / stance_time | cm/s |
| `cop_ap_range_cm` | Anterior-posterior range of CoP motion | max−min of cop_row | cm |
| `cop_ml_range_cm` | Medial-lateral range of CoP motion | max−min of cop_col | cm |

---

## F — Temporal / Persistence Features

Rolling window over the last 5 consecutive steps **per side** (Left or Right). Distinguishes a single spike from persistent abnormality.

For each tracked feature F ∈ {press_max_kpa, pti_total_kpa_s, load_frac_forefoot, load_frac_rearfoot, cop_path_length_cm}:

| Feature | Description | Unit |
|---|---|---|
| `roll_mean_{F}` | Rolling mean of F over last 5 steps | same as F |
| `roll_max_{F}` | Rolling max of F over last 5 steps | same as F |
| `roll_std_{F}` | Rolling std of F over last 5 steps | same as F |
| `persistence_{F}` | Fraction of last 5 steps where F > threshold | 0–1 |

Persistence thresholds (EXPERIMENTAL):

| Feature | Threshold |
|---|---|
| `press_max_kpa` | 200 kPa |
| `pti_total_kpa_s` | 50 000 kPa·s |
| `load_frac_forefoot` | 0.50 (50% in forefoot) |
| `load_frac_rearfoot` | 0.55 (55% in rearfoot) |
| `cop_path_length_cm` | 15 cm |

---

## G — Gait Features (per trial)

Derived from consecutive footstep timestamps within one trial. Replicated into each per-step row for convenience.

| Feature | Description | Formula | Unit |
|---|---|---|---|
| `stance_mean_s` | Mean stance duration across all steps in trial | mean(stance_time_s) | s |
| `stance_std_s` | Std of stance duration | std(stance_time_s) | s |
| `stance_cv` | Coefficient of variation of stance duration | std/mean | — |
| `stance_min_s` / `stance_max_s` | Min/max stance duration | — | s |
| `n_steps_total` | Total steps in trial (post-filtering) | count | — |
| `step_time_mean_s` | Mean time between consecutive heel-strikes | mean(Δstart_frame)/100 | s |
| `step_time_std_s` | Std of step time | — | s |
| `step_time_cv` | Coefficient of variation of step time | std/mean | — |
| `cadence_steps_per_min` | Walking cadence | 60 / step_time_mean | steps/min |
| `stride_time_{side}_mean_s` | Mean same-side step interval (stride time) per side | mean(Δstart, same side) | s |
| `stride_time_{side}_std_s` | Std of stride time per side | — | s |
| `stride_time_{side}_cv` | CV of stride time per side | — | — |
| `n_steps_left` / `n_steps_right` | Step count per side | — | — |
| `stance_fraction_{side}` | Stance/stride time ratio (≈ 60% in normal gait) | stance_mean / stride_mean | — |
| `gait_symmetry_index` | Bilateral stride time asymmetry | \|L−R\| / ((L+R)/2) | — |
| `gait_temporal_variability` | Overall gait regularity (= step_time_cv) | — | — |

**Not available** (future hardware):
- Swing time (requires continuous IMU or bilateral simultaneous capture)
- Double support time (same)
- Step length / walking speed (no positional data per step)

---

## H — Bilateral Features (per trial)

Computed via Normalized Symmetry Index:  
`NSI = |L − R| / ((L + R) / 2) × 100%`

Positive directional values (`asym_dir_*`) mean left > right.

For each pressure feature F:

| Feature | Description | Unit |
|---|---|---|
| `asym_{F}` | Absolute bilateral asymmetry (NSI) | % |
| `asym_dir_{F}` | Signed asymmetry (positive = left higher) | % |
| `left_mean_{F}` / `right_mean_{F}` | Per-side mean of feature F | same as F |

Specific asymmetry features:

| Feature | Source feature |
|---|---|
| `asym_press_mean_kpa` | Mean pressure |
| `asym_press_max_kpa` | Peak pressure |
| `asym_pti_total_kpa_s` | PTI (primary loading asymmetry) |
| `asym_contact_area_cm2` | Contact area |
| `asym_peak_total_force_kpa` | Peak total force |
| `asym_load_{region}` | Regional loading (4 regions) |
| `asym_cop_path_length_cm` | CoP path length |
| `asym_cop_ap_range_cm` | CoP AP range |
| `asym_stance_time` | Stance duration |
| `left_loading_fraction` / `right_loading_fraction` | Share of total PTI per side | 0–1 |

---

## Temperature Features (Hardware Roadmap)

Temperature sensing is **not present** in the StepUP-P150 dataset.  
Planned features for the SoleSense insole hardware are documented in `src/temperature_features.py`.

---

## Risk Score (from `src/risk_engine.py`)

| Feature | Description | Range |
|---|---|---|
| `risk_score` | SoleSense Risk Indicator (EXPERIMENTAL, not clinically validated) | 0–100 |
| `risk_level` | NORMAL / MONITOR / ALERT | — |
| `affected_region` | Anatomical region of primary concern | str |
| `n_contributing_factors` | Number of triggered risk rules | int |
| `recommended_action` | Prototype recommendation text | str |

Risk thresholds (EXPERIMENTAL — configurable in `config/config.py`):

| Level | Score range |
|---|---|
| NORMAL | 0–29 |
| MONITOR | 30–59 |
| ALERT | 60–100 |
