# DATASET SUMMARY — StepUP-P150

Generated automatically by SoleSense Phase 0 inspection.

---

## 1. Dataset Identity

| Field | Value |
|---|---|
| **Name** | StepUP-P150 |
| **Full Title** | A Dataset of High-Resolution Plantar Pressure Measurements with Varying Footwear Types and Walking Speeds for Gait Analysis and Recognition |
| **DOI** | https://doi.org/10.20383/103.01285 |
| **Data Descriptor DOI** | https://doi.org/10.1038/s41597-025-05792-1 |
| **Collection Period** | 2023–2024 |
| **Institution** | Health Technologies Lab, University of New Brunswick |
| **License** | CC BY 4.0 |
| **Principal Investigator** | Erik Scheme (escheme@unb.ca) |

---

## 2. Dataset Size & Structure

| Field | Value |
|---|---|
| **Number of subjects** | 150 (IDs: 001–150) |
| **Footwear conditions** | 4 (BF, ST, P1, P2) |
| **Trial types** | 7 per footwear (S1, S2, S3, W1, W2, W3, W4) |
| **Total trial folders per subject** | 28 |
| **File formats** | `.npz` (NumPy, used here), `.mat` (MATLAB, not in this download) |

### Condition Codes

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

**Footwear:**
| ID | Description |
|---|---|
| BF | Barefoot / Sockfoot |
| ST | Standard Sneakers (Adidas Grand Court 2.0) |
| P1 | Participant's First Pair of Personal Footwear |
| P2 | Participant's Second Pair of Personal Footwear |

---

## 3. Hardware / Instrumentation

| Field | Value |
|---|---|
| **Device** | Stepscan Technologies Inc. piezoresistive floor mat |
| **Platform dimensions** | 3.6 m × 1.2 m runway |
| **Sensor density** | 4 sensors/cm² (2 sensors/cm per axis) |
| **Full platform resolution** | 720 × 240 pixels |
| **Pixel physical size** | 0.5 cm × 0.5 cm (= 0.25 cm² per sensor) |
| **Sampling rate** | 100 Hz |
| **Pressure unit** | kPa |
| **Pressure range observed** | 0 – ~766 kPa (raw trial); 0 – ~766 kPa (pipeline_1 footsteps) |

---

## 4. Files Per Trial

### Walking trials (W1–W4)

| File | Description | Shape |
|---|---|---|
| `metadata.csv` | Per-footstep labels, bounding boxes, quality flags | `(n_footsteps, 22)` |
| `trial.npz` | Full 90-second pressure recording | `(~9000 frames, 720 px, 240 px)` — `uint16` |
| `pipeline_1.npz` | Extracted + normalized footsteps, kPa | `(n_footsteps, 101 frames, 75 px, 40 px)` — `float64` |
| `pipeline_2.npz` | Same as pipeline_1 but normalized to [0, 1] range | `(n_footsteps, 101 frames, 75 px, 40 px)` — `float64` |

### Balance trials (S1–S3)

| File | Description | Shape |
|---|---|---|
| `trial.npz` | Full 30-second pressure recording | `(~3000 frames, 720 px, 240 px)` — `uint16` |
| `preprocessed.npz` | Spatially cropped, aligned recording | `(3000 frames, 180 px, 180 px)` — `uint16` |

---

## 5. Metadata CSV Fields (Walking Trials)

| Column | Description | Unit/Type |
|---|---|---|
| `ParticipantID` | Subject number (1–150) | int |
| `Footwear` | Footwear condition (BF/ST/P1/P2) | str |
| `Speed` | Walking condition (W1–W4) | str |
| `FootstepID` | Index of footstep within trial | int |
| `PassID` | Pass (back-and-forth lap) index | int |
| `StartFrame` | Frame index of contact onset | int @ 100 Hz |
| `EndFrame` | Frame index of contact offset | int @ 100 Hz |
| `Ymin`, `Ymax` | Bounding box rows on platform | px |
| `Xmin`, `Xmax` | Bounding box cols on platform | px |
| `Orientation` | Foot orientation flag | 0 or 1 |
| `Side` | Left or Right | str |
| `Standing` | 1 if stationary contact | bool int |
| `Incomplete` | 1 if footstep partially off platform | bool int |
| `Rscore` | Quality/reliability score | float [0,1] |
| `Outlier` | 1 if detected as outlier | bool int |
| `Exclude` | 1 if excluded from analysis | bool int |
| `RotationAngle` | Rotation applied during normalization | degrees |
| `FootLength` | Foot length in sensor pixels | px (×0.5 = cm) |
| `FootWidth` | Foot width in sensor pixels | px (×0.5 = cm) |
| `MeanPressure` | Cumulative pressure integral (sum of kPa over all pixels × all stance frames) | kPa·frames |

---

## 6. Spatial Coordinate System

- Footstep images (pipeline_1/pipeline_2) are normalized to 75 × 40 pixels.
- **Row axis (0→74):** Heel (row 74) → Toe (row 0) direction.
- **Column axis (0→39):** Medial → Lateral direction (varies by side).
- Physical size: 75 px × 0.5 cm/px = **37.5 cm** length; 40 px × 0.5 cm/px = **20 cm** width.
- Orientation normalization aligns all footsteps regardless of walking direction.

---

## 7. Derived Timing

At 100 Hz sampling:
- **Stance duration** = `(EndFrame - StartFrame) / 100` seconds.
  - Observed range: 0.17 s – 3.25 s (including anomalies)
  - Typical: 0.68 s – 0.88 s
- **Step time** = time between consecutive same-side footsteps (approximately stride time / 2).
- **Pipeline footstep array** = fixed 101 frames = 1.01 s window.

---

## 8. Sensor Variables Present

| Variable | Available | Notes |
|---|---|---|
| **Plantar pressure (spatial)** | ✓ YES | 75×40 px per footstep; units kPa |
| **Left/right side label** | ✓ YES | `Side` column in metadata.csv |
| **Foot dimensions** | ✓ YES | FootLength, FootWidth in px |
| **Timing / stance duration** | ✓ YES | StartFrame, EndFrame at 100 Hz |
| **Gait cycle timing** | ✓ Derived | From consecutive footstep timestamps |
| **CoP trajectory** | ✓ Derived | Computed from spatial pressure arrays |
| **Temperature** | ✗ NOT PRESENT | Future SoleSense hardware feature |
| **IMU / acceleration** | ✗ NOT PRESENT | Future SoleSense hardware feature |
| **EMG** | ✗ NOT PRESENT | Not part of this dataset |

---

## 9. Regional Anatomy Mapping

The normalized 75×40 px footstep image is anatomically divided as follows (assumption documented):

| Region | Row range | Column range | Anatomy |
|---|---|---|---|
| Toe | 0–14 | 0–39 | Digits (approximate) |
| Forefoot | 15–34 | 0–39 | Metatarsal heads |
| Midfoot | 35–54 | 0–39 | Arch region |
| Rearfoot | 55–74 | 0–39 | Heel |

**Assumption:** Row 0 = toe, Row 74 = heel, based on observed CoP progression from row ~45 (heel strike) to ~24 (toe-off) during stance phase.

---

## 10. Known Limitations (from README and inspection)

1. `participant_metadata.csv` (demographics) is not included in this download archive; only per-footstep `metadata.csv` files are present.
2. ~20–22% of footsteps are flagged `Exclude=1` (outliers, incomplete contacts). These are filtered during preprocessing.
3. No temperature data — this is a pure plantar pressure dataset.
4. No IMU data — no accelerometry or gyroscopy.
5. No bilateral simultaneous measurement — left and right footsteps are captured sequentially as the participant walks across the platform.
6. The `MeanPressure` column is a cumulative pressure integral (sum across all pixels across all frames), not a per-pixel mean kPa value.
7. Balance trials (S1–S3) do not have extracted footstep metadata; only full-trial tensors are available.
8. Platform is not wearable — this is a floor-based capture, not an insole.

---

## 11. Dataset Path (this installation)

```
f:\Dataset\FRDR_dataset_1280_download_590_202609031103\py\
```

Subject folders: `001` through `150`
Structure: `py/{subject_id}/{footwear}/{trial}/`
