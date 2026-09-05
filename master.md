You are the lead software/ML engineer for my project "SoleSense".

IMPORTANT:
Do NOT ask me to manually inspect files, open folders, copy filenames, or understand the dataset for you.

You have access to the entire workspace and filesystem. Inspect the dataset yourself programmatically and make the project decisions based on the actual files and their contents.

PROJECT GOAL
-------------
SoleSense is a prototype for continuous foot-loading and gait-risk monitoring.

The intended architecture is:

RAW DATA / HARDWARE
        ↓
SENSING
        ↓
PREPROCESSING
        ↓
FEATURE ENGINEERING
        ↓
BILATERAL COMPARISON
        ↓
HEALTH/RISK INDICATORS
        ↓
DASHBOARD
        ↓
PERSONALIZED TINYML
        ↓
EXPLAINABLE FUSION
        ↓
ALERT / OFFLOADING ACTION

The immediate goal is NOT TinyML or hardware.

FIRST BUILD:
Dataset → feature engineering → explainable risk indicators → working dashboard.

Later, the exact same software architecture should be able to accept live sensor data from the physical insole.

PROJECT CONTEXT
---------------
The planned SoleSense hardware architecture consists of:
- 2 instrumented insoles
- 8 pressure sensing sites per insole
- 8 temperature sensing sites per insole
- 1 IMU per insole
- nRF52840-class edge MCU
- bilateral left/right comparison
- personalized TinyML autoencoder
- explainable rule engine
- ankle-cuff alert

The conceptual pipeline is:

Sense → Compare → Learn → Fuse → Act

The dashboard must therefore be designed around meaningful biomechanical/physiological features rather than arbitrary raw columns.

IMPORTANT SAFETY/SCIENTIFIC CONSTRAINT
--------------------------------------
This is a research/prototype system.

Do NOT describe the system as diagnosing diabetes, diabetic neuropathy, ulcers, or any medical condition.

Do NOT invent clinically validated thresholds.

If we create a risk score, call it something like:
"SoleSense Risk Indicator"
or
"Prototype Risk Indicator"

Clearly label thresholds as experimental/demo thresholds unless the dataset itself provides validated thresholds.

The dashboard should communicate:
- abnormal loading
- asymmetry
- pressure exposure
- gait deviation
- temperature differences if temperature exists
- persistence of abnormalities

It should NOT claim medical diagnosis.

==================================================
PHASE 0 — UNDERSTAND THE DATASET AUTOMATICALLY
==================================================

First inspect the entire workspace.

Find the downloaded dataset automatically.

The dataset currently appears to contain:
- README.txt
- CITATION.txt
- LICENSE.txt
- checksum files
- a "py" directory
- numbered directories such as 126, 127, ..., 150

DO NOT assume what these numbered folders represent.

Determine this automatically.

Read:
- README.txt
- CITATION.txt if relevant
- directory metadata
- filenames
- file extensions
- representative data files

Inspect the dataset recursively.

Determine:
1. dataset name
2. dataset version
3. number of subjects/trials/sessions
4. what numbered folders represent
5. all file formats
6. number of samples
7. sampling frequency if available
8. all sensor variables
9. pressure variables
10. temperature variables if present
11. IMU variables if present
12. left/right information
13. spatial information
14. gait/step information
15. labels
16. metadata
17. missing values
18. units
19. coordinate systems if applicable
20. any limitations described by the dataset authors

Do not fabricate information.

Create a short machine-readable dataset summary at:

docs/DATASET_SUMMARY.md

==================================================
PHASE 1 — CREATE THE PROJECT STRUCTURE
==================================================

Create this structure if it does not already exist:

SoleSense/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── features/
│
├── src/
│   ├── __init__.py
│   ├── data_loader.py
│   ├── preprocessing.py
│   ├── pressure_features.py
│   ├── temperature_features.py
│   ├── gait_features.py
│   ├── bilateral_features.py
│   ├── temporal_features.py
│   ├── risk_engine.py
│   └── feature_pipeline.py
│
├── dashboard/
│   └── app.py
│
├── notebooks/
│   └── 01_dataset_exploration.ipynb
│
├── models/
│
├── docs/
│   ├── DATASET_SUMMARY.md
│   ├── FEATURE_DICTIONARY.md
│   └── ARCHITECTURE.md
│
├── tests/
│
├── requirements.txt
└── README.md

Do NOT duplicate the original dataset unnecessarily.

Keep raw data untouched.

==================================================
PHASE 2 — BUILD A DATA ADAPTER
==================================================

Create:

src/data_loader.py

The loader must abstract away the dataset's original file format.

The rest of the project should NOT care whether the original dataset is:
CSV, MAT, HDF5, TXT, etc.

Create a normalized internal representation.

Use a structure conceptually similar to:

timestamp
subject_id
trial_id
foot/side if available
pressure channels
temperature channels if available
IMU channels if available
spatial coordinates if available
labels/metadata if available

Adapt this to the ACTUAL dataset.

Do not force variables that don't exist.

The loader should expose clean pandas DataFrames or equivalent structures.

Add error handling and useful logging.

==================================================
PHASE 3 — PREPROCESSING
==================================================

Create:

src/preprocessing.py

Implement only preprocessing justified by the dataset.

Potential operations:

- missing-value handling
- duplicate removal
- signal validation
- unit normalization
- timestamp normalization
- filtering/noise reduction
- normalization
- outlier detection
- resampling if necessary

Do not blindly apply filters.

Document why each preprocessing step is used.

Preserve raw data.

==================================================
PHASE 4 — FEATURE ENGINEERING
==================================================

This is the CORE of the current project.

Create separate feature modules.

------------------------------------------
A. PRESSURE FEATURES
------------------------------------------

Create:

src/pressure_features.py

Extract whichever features are supported by the actual dataset.

Potential features include:

- mean pressure
- median pressure
- maximum pressure
- minimum pressure
- pressure standard deviation
- pressure range
- pressure variability
- pressure percentiles
- contact duration
- peak pressure location
- regional loading
- pressure-time exposure
- cumulative pressure exposure
- loading rate if temporal resolution allows it

Pressure-time exposure should conceptually capture:

pressure × duration

rather than only instantaneous peak pressure.

------------------------------------------
B. CENTER OF PRESSURE
------------------------------------------

If the dataset contains spatial pressure information, calculate:

CoP_x
CoP_y
CoP velocity
CoP path length
CoP excursion

Use the actual coordinate system supplied by the dataset.

Do NOT invent sensor coordinates.

If spatial information is unavailable, skip these features and document that.

------------------------------------------
C. GAIT FEATURES
------------------------------------------

Create:

src/gait_features.py

Extract supported gait features such as:

- step time
- stride time
- stance time
- swing time
- cadence
- contact time
- gait-cycle duration
- temporal variability

Only calculate features that can actually be derived from the available signals.

------------------------------------------
D. BILATERAL FEATURES
------------------------------------------

Create:

src/bilateral_features.py

This is a major SoleSense feature.

Where left/right matched measurements exist, calculate:

- left/right difference
- absolute difference
- relative difference
- asymmetry percentage
- regional asymmetry
- pressure asymmetry
- gait symmetry
- temperature asymmetry if temperature exists

Use robust formulas and document them.

For example, where appropriate:

asymmetry =
abs(L - R) / ((L + R) / 2)

Avoid division-by-zero problems.

------------------------------------------
E. TEMPERATURE FEATURES
------------------------------------------

If the dataset contains temperature:

Create:

src/temperature_features.py

Calculate:

- mean temperature
- maximum temperature
- minimum temperature
- temperature variability
- regional temperature
- left/right temperature difference
- temperature asymmetry
- persistence of temperature difference

If temperature does NOT exist in the dataset:

DO NOT fabricate temperature.

Instead document:

"Temperature is a future hardware feature and is not available in the current dataset."

------------------------------------------
F. TEMPORAL / PERSISTENCE FEATURES
------------------------------------------

Create:

src/temporal_features.py

Implement features such as:

- rolling mean
- rolling maximum
- rolling standard deviation
- duration above threshold
- number of consecutive abnormal windows
- persistence of regional loading
- rolling pressure exposure

The goal is to distinguish:

single abnormal event

from:

persistent abnormal behavior.

==================================================
PHASE 5 — FEATURE TABLE
==================================================

Create a clean final feature table:

data/features/features.csv

Each row should represent a meaningful analysis window, step, gait cycle, trial, or other appropriate unit based on the dataset.

Include metadata:

subject_id
trial_id
timestamp/window identifier

Then include the engineered features.

Create:

docs/FEATURE_DICTIONARY.md

Document every feature:

feature name
description
formula
unit
source signal
reason for inclusion

Do NOT create hundreds of meaningless features.

Prefer interpretable, physically meaningful features.

==================================================
PHASE 6 — EXPLORATORY ANALYSIS
==================================================

Create:

notebooks/01_dataset_exploration.ipynb

Automatically generate visualizations for the actual dataset.

Include where applicable:

1. raw pressure signals
2. pressure distribution
3. pressure heatmap
4. temporal pressure curves
5. gait timing distributions
6. left/right comparisons
7. asymmetry distributions
8. CoP trajectory
9. temperature distributions if available
10. missing-value analysis
11. feature correlations

Save important plots under:

docs/figures/

The notebook should run from the project root.

==================================================
PHASE 7 — SOLESENSE RISK ENGINE
==================================================

Create:

src/risk_engine.py

Build an EXPLAINABLE prototype risk engine.

Do NOT start with a black-box neural network.

The engine should combine interpretable signals such as:

- elevated pressure
- high pressure-time exposure
- persistent regional loading
- left/right pressure asymmetry
- gait asymmetry
- gait deviation
- temperature asymmetry if available

The risk engine should produce:

risk_score
risk_level
affected_region
contributing_factors
recommended_action

Example structure:

{
    "risk_score": 42,
    "risk_level": "MONITOR",
    "affected_region": "LEFT_FOREFOOT",
    "contributing_factors": [
        "Elevated pressure-time exposure",
        "Left/right loading asymmetry"
    ],
    "recommended_action": "Monitor loading and consider offloading"
}

These are prototype indicators only.

Do not claim clinical validity.

Make all thresholds configurable in one place.

==================================================
PHASE 8 — BUILD THE DASHBOARD
==================================================

Use:

Streamlit + Plotly

Create:

dashboard/app.py

The dashboard should look like a polished engineering/research dashboard, not a generic data-science demo.

Title:

SOLESENSE

Subtitle:

Personal Foot Loading & Gait Monitor

Dashboard sections:

------------------------------------------
1. OVERALL STATUS
------------------------------------------

Display:

Risk Indicator
Risk Level
Most affected region
Number of contributing factors

------------------------------------------
2. FOOT PRESSURE
------------------------------------------

Show:

- pressure distribution
- peak pressure
- average pressure
- pressure-time exposure
- regional loading

If spatial information exists, show a plantar pressure visualization.

------------------------------------------
3. LEFT ↔ RIGHT COMPARISON
------------------------------------------

Show:

- left loading
- right loading
- asymmetry percentage
- regional comparison

Use intuitive visualizations.

------------------------------------------
4. TEMPERATURE
------------------------------------------

If temperature exists:

Show:

Left temperature
Right temperature
ΔT
regional temperature differences

If temperature does not exist:

Show a clearly labelled "Hardware Roadmap" placeholder explaining that temperature sensing will be introduced with the physical insole.

------------------------------------------
5. GAIT
------------------------------------------

Show:

cadence
step time
stance time
swing time
gait symmetry
temporal variability

Only show metrics supported by the dataset.

------------------------------------------
6. PRESSURE / COP VISUALIZATION
------------------------------------------

If possible show:

pressure heatmap
CoP trajectory

------------------------------------------
7. EXPLAINABLE RISK
------------------------------------------

This is important.

Do NOT simply display:

"AI Risk = 73"

Instead show:

WHY IS THE RISK INDICATOR ELEVATED?

Example:

⚠ Elevated forefoot pressure exposure
⚠ Left/right loading asymmetry
⚠ Persistent loading pattern
✓ No major gait asymmetry detected

------------------------------------------
8. HISTORICAL TREND
------------------------------------------

Show risk/feature values over time where the dataset supports temporal history.

Allow filtering by:

subject
trial/session
time/window

==================================================
PHASE 9 — DESIGN THE DASHBOARD FOR FUTURE HARDWARE
==================================================

This is extremely important.

Do NOT couple the dashboard directly to CSV files.

Create a clean interface:

Data Source
    ↓
Data Adapter
    ↓
Normalized Sensor Data
    ↓
Feature Engineering
    ↓
Risk Engine
    ↓
Dashboard

The Data Source should eventually be replaceable:

CURRENT:
Dataset

FUTURE:
Serial
BLE
nRF52840
ESP32-S3
other MCU

The dashboard should not need to be rewritten when live hardware is introduced.

==================================================
PHASE 10 — FUTURE TINYML INTERFACE
==================================================

Do NOT implement the actual TinyML model yet.

But design the architecture so that later we can add:

features
    ↓
personal baseline
    ↓
autoencoder
    ↓
reconstruction error
    ↓
anomaly score
    ↓
risk fusion

Create a placeholder interface such as:

src/anomaly_model.py

with a clean API.

The eventual model will be a small personalized autoencoder suitable for edge deployment.

Do not train a fake model just to have one.

==================================================
PHASE 11 — TESTING
==================================================

Create tests for:

- data loading
- preprocessing
- bilateral asymmetry calculations
- pressure-time exposure
- division-by-zero handling
- missing values
- risk scoring
- feature generation

Use pytest.

==================================================
PHASE 12 — DOCUMENTATION
==================================================

Update README.md with:

1. Project purpose
2. Dataset used
3. Dataset structure
4. Installation
5. Running feature engineering
6. Generating features
7. Launching dashboard
8. Dashboard interpretation
9. Current limitations
10. Future hardware integration
11. TinyML roadmap

Also create:

docs/ARCHITECTURE.md

with:

Dataset
 ↓
Data Adapter
 ↓
Preprocessing
 ↓
Feature Engineering
 ↓
Bilateral Comparison
 ↓
Risk Engine
 ↓
Dashboard

and future:

Hardware
 ↓
Sensor Adapter
 ↓
Feature Engineering
 ↓
TinyML
 ↓
Fusion
 ↓
Ankle Cuff

==================================================
IMPORTANT ENGINEERING RULES
==================================================

1. INSPECT FIRST, CODE SECOND.

2. Never assume the dataset structure.

3. Never invent variables that don't exist.

4. Never fabricate temperature data.

5. Never fabricate clinical thresholds.

6. Never modify the original dataset.

7. Make the pipeline reproducible.

8. Use relative paths/configuration rather than hardcoded machine-specific paths.

9. Keep feature engineering modular.

10. Keep the dashboard independent of the dataset format.

11. Prefer interpretable features.

12. Document assumptions.

13. If a requested feature cannot be derived from this dataset, explicitly document why and mark it as a future hardware feature.

14. Don't build the mobile app yet.

15. Don't build BLE yet.

16. Don't build the ankle cuff yet.

17. Don't train TinyML yet.

18. Get the dataset → features → dashboard pipeline working FIRST.

==================================================
EXECUTION ORDER
==================================================

Execute the work in this exact order:

1. Inspect workspace
2. Identify dataset
3. Read README and metadata
4. Inspect representative files
5. Determine dataset schema
6. Create DATASET_SUMMARY.md
7. Create project structure
8. Implement data_loader.py
9. Implement preprocessing.py
10. Implement feature engineering
11. Generate features.csv
12. Create feature dictionary
13. Create exploratory notebook
14. Implement risk_engine.py
15. Build Streamlit dashboard
16. Test everything
17. Run the dashboard
18. Fix errors
19. Update README
20. Give me a concise final report

At the end, report:

DATASET:
- what dataset was found
- number of subjects/trials
- relevant signals

FEATURE ENGINEERING:
- features successfully extracted
- features unavailable and why

DASHBOARD:
- what is implemented
- how to launch it

NEXT:
- exact next step for integrating the physical insole

Do not stop after inspecting the dataset.

Actually implement the pipeline and dashboard.

If you encounter an ambiguity, make the most reasonable engineering choice from the actual dataset, document the assumption, and continue rather than asking me to manually investigate files.