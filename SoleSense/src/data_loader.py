"""
SoleSense Data Loader
=====================
Abstracts the StepUP-P150 dataset into a normalized internal representation.

The rest of the project does NOT depend on the dataset's file format (.npz).
When hardware produces live data, only this module (or its adapter interface)
needs to change.

Dataset structure consumed:
    {DATASET_ROOT}/{subject_id}/{footwear}/{trial}/
        metadata.csv          – per-footstep labels (walking trials only)
        pipeline_1.npz        – normalized footstep pressure arrays (kPa)
        pipeline_2.npz        – same, normalized to [0,1]
        trial.npz             – full recording tensor (walking & balance)
        preprocessed.npz      – spatially aligned balance recording

Normalized output
-----------------
Walking trials → DataFrame with one row per footstep:
    subject_id, footwear, trial, footstep_id, pass_id,
    side, start_frame, end_frame, stance_frames, stance_time_s,
    foot_length_px, foot_width_px, foot_length_cm, foot_width_cm,
    mean_pressure_integral,
    rscore, exclude, outlier, incomplete,
    pressure_array  (object column, shape 101×75×40, kPa)

Balance trials → DataFrame with one row per trial:
    subject_id, footwear, trial,
    pressure_tensor (object column, shape 3000×180×180, kPa)
"""

import os
import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Tuple

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.config import (
    DATASET_ROOT, SAMPLING_RATE_HZ, CM_PER_PX,
    FOOTSTEP_ROWS, FOOTSTEP_COLS, FOOTSTEP_FRAMES,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")

FOOTWEAR_CONDITIONS = ["BF", "ST", "P1", "P2"]
WALKING_TRIALS = ["W1", "W2", "W3", "W4"]
BALANCE_TRIALS = ["S1", "S2", "S3"]


# ─────────────────────────────────────────────────────────────────────────────
# Low-level file readers
# ─────────────────────────────────────────────────────────────────────────────

def _load_npz_array(path: str) -> Optional[np.ndarray]:
    """Load the first array from an .npz file.  Returns None on failure."""
    try:
        data = np.load(path, allow_pickle=True)
        key = list(data.keys())[0]
        return data[key]
    except Exception as exc:
        logger.warning("Could not load %s: %s", path, exc)
        return None


def _load_metadata_csv(path: str) -> Optional[pd.DataFrame]:
    """Load metadata.csv for a walking trial.  Returns None on failure."""
    try:
        df = pd.read_csv(path)
        return df
    except Exception as exc:
        logger.warning("Could not load %s: %s", path, exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Single-trial loaders
# ─────────────────────────────────────────────────────────────────────────────

def load_walking_trial(
    subject_id: str,
    footwear: str,
    trial: str,
    include_pressure_arrays: bool = True,
    use_pipeline: int = 1,
    dataset_root: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """
    Load one walking trial for one subject.

    Parameters
    ----------
    subject_id : str   e.g. '078'
    footwear   : str   one of BF / ST / P1 / P2
    trial      : str   one of W1 / W2 / W3 / W4
    include_pressure_arrays : bool
        If True, attach the per-footstep pressure array (101×75×40) as an
        object column.  Set False when only metadata is needed (faster).
    use_pipeline : int  1 (kPa) or 2 (normalized 0-1)
    dataset_root : str or None  override default root

    Returns
    -------
    pd.DataFrame  with one row per footstep, or None on failure.
    """
    root = dataset_root or DATASET_ROOT
    trial_dir = os.path.join(root, subject_id, footwear, trial)

    if not os.path.isdir(trial_dir):
        logger.debug("Trial dir not found: %s", trial_dir)
        return None

    # ── metadata ────────────────────────────────────────────────────────────
    meta_path = os.path.join(trial_dir, "metadata.csv")
    meta = _load_metadata_csv(meta_path)
    if meta is None or len(meta) == 0:
        return None

    # ── pressure arrays ──────────────────────────────────────────────────────
    pressure_arrays = None
    if include_pressure_arrays:
        npz_file = f"pipeline_{use_pipeline}.npz"
        arr = _load_npz_array(os.path.join(trial_dir, npz_file))
        if arr is not None:
            # arr shape: (n_footsteps, 101, 75, 40)
            if arr.shape[0] == len(meta):
                pressure_arrays = arr
            else:
                logger.warning(
                    "%s/%s/%s: pipeline array has %d rows but metadata has %d",
                    subject_id, footwear, trial, arr.shape[0], len(meta)
                )

    # ── build normalized DataFrame ───────────────────────────────────────────
    df = pd.DataFrame()
    df["subject_id"] = meta["ParticipantID"].astype(str).str.zfill(3)
    df["footwear"] = meta["Footwear"].astype(str)
    df["trial"] = meta["Speed"].astype(str)
    df["footstep_id"] = meta["FootstepID"].astype(int)
    df["pass_id"] = meta["PassID"].astype(int)
    df["side"] = meta["Side"].astype(str)   # 'Left' or 'Right'

    df["start_frame"] = meta["StartFrame"].astype(int)
    df["end_frame"] = meta["EndFrame"].astype(int)
    df["stance_frames"] = df["end_frame"] - df["start_frame"]
    df["stance_time_s"] = df["stance_frames"] / SAMPLING_RATE_HZ

    df["foot_length_px"] = meta["FootLength"].astype(float)
    df["foot_width_px"] = meta["FootWidth"].astype(float)
    df["foot_length_cm"] = df["foot_length_px"] * CM_PER_PX
    df["foot_width_cm"] = df["foot_width_px"] * CM_PER_PX

    df["mean_pressure_integral"] = meta["MeanPressure"].astype(float)
    # mean_pressure_integral = cumulative sum of kPa over all pixels × all frames
    # (This is the raw "MeanPressure" field from the dataset metadata)

    df["rscore"] = meta["Rscore"].astype(float)
    df["exclude"] = meta["Exclude"].astype(int)
    df["outlier"] = meta["Outlier"].astype(int)
    df["incomplete"] = meta["Incomplete"].astype(int)
    df["rotation_angle"] = meta["RotationAngle"].astype(float)

    if pressure_arrays is not None:
        df["pressure_array"] = [pressure_arrays[i] for i in range(len(df))]
    else:
        df["pressure_array"] = None

    df.reset_index(drop=True, inplace=True)
    return df


def load_balance_trial(
    subject_id: str,
    footwear: str,
    trial: str,
    use_preprocessed: bool = True,
    dataset_root: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """
    Load one balance trial for one subject.

    Returns a DataFrame with a single row containing a 3D pressure tensor
    (frames × rows × cols) in the 'pressure_tensor' column.
    """
    root = dataset_root or DATASET_ROOT
    trial_dir = os.path.join(root, subject_id, footwear, trial)

    if not os.path.isdir(trial_dir):
        return None

    npz_file = "preprocessed.npz" if use_preprocessed else "trial.npz"
    arr = _load_npz_array(os.path.join(trial_dir, npz_file))
    if arr is None:
        return None

    df = pd.DataFrame([{
        "subject_id": subject_id.zfill(3),
        "footwear": footwear,
        "trial": trial,
        "n_frames": arr.shape[0],
        "rows": arr.shape[1],
        "cols": arr.shape[2],
        "pressure_tensor": arr,
    }])
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Batch loaders
# ─────────────────────────────────────────────────────────────────────────────

def load_subject(
    subject_id: str,
    footwear_list: Optional[List[str]] = None,
    trial_list: Optional[List[str]] = None,
    include_pressure_arrays: bool = True,
    dataset_root: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load all walking trials for one subject.

    Parameters
    ----------
    subject_id    : str  e.g. '078'
    footwear_list : list of condition codes, defaults to all four
    trial_list    : list of walking trial codes, defaults to W1–W4
    """
    fw_list = footwear_list or FOOTWEAR_CONDITIONS
    tr_list = trial_list or WALKING_TRIALS

    frames = []
    for fw in fw_list:
        for tr in tr_list:
            df = load_walking_trial(
                subject_id, fw, tr,
                include_pressure_arrays=include_pressure_arrays,
                dataset_root=dataset_root,
            )
            if df is not None:
                frames.append(df)

    if not frames:
        logger.warning("No data loaded for subject %s", subject_id)
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def load_dataset(
    subject_ids: Optional[List[str]] = None,
    footwear_list: Optional[List[str]] = None,
    trial_list: Optional[List[str]] = None,
    include_pressure_arrays: bool = False,
    max_subjects: Optional[int] = None,
    dataset_root: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load walking trial metadata for multiple subjects.

    Pressure arrays are excluded by default (large memory footprint).
    Set include_pressure_arrays=True only when needed for feature extraction.

    Parameters
    ----------
    subject_ids   : list of str IDs; if None, all 150 subjects are loaded
    max_subjects  : limit for development/testing
    """
    root = dataset_root or DATASET_ROOT

    if subject_ids is None:
        try:
            all_ids = sorted([
                d for d in os.listdir(root)
                if os.path.isdir(os.path.join(root, d))
            ])
        except FileNotFoundError:
            logger.error("Dataset root not found: %s", root)
            return pd.DataFrame()
        subject_ids = all_ids

    if max_subjects is not None:
        subject_ids = subject_ids[:max_subjects]

    logger.info("Loading %d subjects ...", len(subject_ids))
    frames = []
    for i, sid in enumerate(subject_ids):
        if (i + 1) % 10 == 0:
            logger.info("  %d / %d subjects loaded", i + 1, len(subject_ids))
        df = load_subject(
            sid,
            footwear_list=footwear_list,
            trial_list=trial_list,
            include_pressure_arrays=include_pressure_arrays,
            dataset_root=root,
        )
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    logger.info("Loaded %d footstep records across %d subjects", len(combined), len(frames))
    return combined


# ─────────────────────────────────────────────────────────────────────────────
# Convenience accessors
# ─────────────────────────────────────────────────────────────────────────────

def list_available_subjects(dataset_root: Optional[str] = None) -> List[str]:
    """Return sorted list of subject IDs present on disk."""
    root = dataset_root or DATASET_ROOT
    try:
        return sorted([
            d for d in os.listdir(root)
            if os.path.isdir(os.path.join(root, d))
        ])
    except FileNotFoundError:
        return []


def get_footstep_array(
    row: pd.Series,
    subject_id: str,
    use_pipeline: int = 1,
    dataset_root: Optional[str] = None,
) -> Optional[np.ndarray]:
    """
    Fetch the pressure array for a single footstep row on demand.
    Useful when the full dataset was loaded without pressure arrays.

    Returns ndarray shape (101, 75, 40) or None.
    """
    root = dataset_root or DATASET_ROOT
    trial_dir = os.path.join(root, subject_id, row["footwear"], row["trial"])
    arr = _load_npz_array(os.path.join(trial_dir, f"pipeline_{use_pipeline}.npz"))
    if arr is None:
        return None
    idx = int(row["footstep_id"])
    if idx < arr.shape[0]:
        return arr[idx]
    return None
