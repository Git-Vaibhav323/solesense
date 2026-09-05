"""
SoleSense Configuration
All configurable parameters in one place.
Thresholds are EXPERIMENTAL / DEMO values unless stated otherwise.
"""

import os

# ── Dataset path ────────────────────────────────────────────────────────────
DATASET_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "FRDR_dataset_1280_download_590_202609031103",
        "py",
    )
)

# ── Sensor / hardware constants ──────────────────────────────────────────────
SAMPLING_RATE_HZ = 100          # sensor frame rate
PX_PER_CM = 2                   # 4 sensors/cm² → 2 sensors/cm per axis
CM_PER_PX = 0.5                 # 1 pixel = 0.5 cm
CM2_PER_PX = 0.25               # 1 pixel covers 0.25 cm²

FOOTSTEP_ROWS = 75              # pipeline_1/2 normalized height (heel→toe)
FOOTSTEP_COLS = 40              # pipeline_1/2 normalized width
FOOTSTEP_FRAMES = 101           # fixed window length in frames

# ── Anatomical region definitions (row ranges in normalized 75-row image) ────
# Assumption: row 0 = toe, row 74 = heel (see DATASET_SUMMARY.md §9)
REGIONS = {
    "TOE":      (0,  14),
    "FOREFOOT": (15, 34),
    "MIDFOOT":  (35, 54),
    "REARFOOT": (55, 74),
}

# ── Preprocessing ─────────────────────────────────────────────────────────
EXCLUDE_FLAGGED_STEPS = True    # remove steps where Exclude=1
MIN_STANCE_DURATION_S = 0.15    # below this is not a real stance phase
MAX_STANCE_DURATION_S = 2.5     # above this is likely a standing pause
MIN_RSCORE = 0.0                # minimum reliability score; 0 = keep all

# ── Feature engineering ───────────────────────────────────────────────────
# Rolling window for temporal features
ROLLING_WINDOW_STEPS = 5        # number of consecutive steps for rolling stats

# ── Risk engine thresholds (EXPERIMENTAL — demo only) ─────────────────────
# These are NOT clinically validated.
RISK_PRESSURE_HIGH_KPA = 200.0          # peak pressure considered elevated
RISK_PRESSURE_EXPOSURE_HIGH = 50000.0   # high cumulative pressure-time integral
RISK_ASYMMETRY_HIGH_PCT = 20.0          # left/right asymmetry % considered high
RISK_ASYMMETRY_MODERATE_PCT = 10.0      # moderate asymmetry threshold
RISK_GAIT_VARIABILITY_HIGH_S = 0.15     # std of step time considered high
RISK_REGIONAL_LOADING_HIGH = 0.6        # fraction of total load in one region

# Risk level boundaries (score 0–100)
RISK_LEVEL_MONITOR = 30
RISK_LEVEL_ALERT = 60

# ── Output paths ─────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PROCESSED_DIR = os.path.join(PROJECT_ROOT, "data", "processed")
DATA_FEATURES_DIR = os.path.join(PROJECT_ROOT, "data", "features")
DOCS_FIGURES_DIR = os.path.join(PROJECT_ROOT, "docs", "figures")
