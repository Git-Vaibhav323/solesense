"""
SoleSense Feature Pipeline
===========================
Orchestrates the full dataset → features workflow.

Usage (from project root):
    python -m src.feature_pipeline --subjects 5 --output data/features/features.csv

Or in code:
    from src.feature_pipeline import run_pipeline
    df = run_pipeline(max_subjects=10)
"""

import argparse
import logging
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.config import DATA_FEATURES_DIR, DATA_PROCESSED_DIR
from src.data_loader import load_dataset, list_available_subjects
from src.preprocessing import preprocess
from src.pressure_features import extract_pressure_features_batch
from src.gait_features import extract_gait_features_batch
from src.bilateral_features import extract_bilateral_features_batch
from src.temporal_features import add_temporal_features

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")


def run_pipeline(
    subject_ids=None,
    max_subjects: int = None,
    footwear_list=None,
    trial_list=None,
    output_path: str = None,
    save_intermediate: bool = False,
    dataset_root: str = None,
) -> pd.DataFrame:
    """
    Full feature pipeline: load → preprocess → features → save.

    Parameters
    ----------
    subject_ids    : list of str IDs, or None for all available
    max_subjects   : cap (useful for development/testing)
    footwear_list  : list like ['BF', 'W1'], or None for all
    trial_list     : list like ['W1', 'W2'], or None for all
    output_path    : where to save features.csv; None = default
    save_intermediate: also save preprocessed metadata (no pressure arrays)

    Returns
    -------
    DataFrame with all per-footstep features.
    """
    t0 = time.time()
    os.makedirs(DATA_FEATURES_DIR, exist_ok=True)
    os.makedirs(DATA_PROCESSED_DIR, exist_ok=True)

    if output_path is None:
        output_path = os.path.join(DATA_FEATURES_DIR, "features.csv")

    # ── 1. Load ─────────────────────────────────────────────────────────────
    logger.info("=== STEP 1: Loading dataset ===")
    all_subjects = list_available_subjects(dataset_root)
    if subject_ids is None:
        subject_ids = all_subjects
    if max_subjects is not None:
        subject_ids = subject_ids[:max_subjects]

    raw_df = load_dataset(
        subject_ids=subject_ids,
        footwear_list=footwear_list,
        trial_list=trial_list,
        include_pressure_arrays=True,  # needed for pressure features
        dataset_root=dataset_root,
    )

    if raw_df.empty:
        logger.error("No data loaded. Check DATASET_ROOT in config/config.py")
        return pd.DataFrame()

    logger.info("Loaded %d footstep records.", len(raw_df))

    # ── 2. Preprocess ────────────────────────────────────────────────────────
    logger.info("=== STEP 2: Preprocessing ===")
    clean_df = preprocess(raw_df, verbose=True)
    logger.info("%d footsteps after preprocessing.", len(clean_df))

    if save_intermediate:
        # save without pressure arrays (too large)
        meta_cols = [c for c in clean_df.columns if c != "pressure_array"]
        clean_df[meta_cols].to_csv(
            os.path.join(DATA_PROCESSED_DIR, "preprocessed_metadata.csv"), index=False
        )
        logger.info("Saved preprocessed metadata.")

    # ── 3. Pressure features ─────────────────────────────────────────────────
    logger.info("=== STEP 3: Extracting pressure features ===")
    pressure_feat_df = extract_pressure_features_batch(clean_df)
    logger.info("Pressure features: %d rows, %d columns", *pressure_feat_df.shape)

    # ── 4. Temporal features (rolling) ───────────────────────────────────────
    logger.info("=== STEP 4: Adding temporal/persistence features ===")
    pressure_feat_df = add_temporal_features(pressure_feat_df)
    logger.info("After temporal features: %d columns", pressure_feat_df.shape[1])

    # ── 5. Gait features (per trial) ─────────────────────────────────────────
    logger.info("=== STEP 5: Extracting gait features ===")
    gait_feat_df = extract_gait_features_batch(clean_df)
    logger.info("Gait features: %d trials", len(gait_feat_df))

    # ── 6. Bilateral features (per trial) ────────────────────────────────────
    logger.info("=== STEP 6: Extracting bilateral features ===")
    bilateral_feat_df = extract_bilateral_features_batch(pressure_feat_df)
    logger.info("Bilateral features: %d trials", len(bilateral_feat_df))

    # ── 7. Join everything ────────────────────────────────────────────────────
    logger.info("=== STEP 7: Joining feature tables ===")
    # Per-step features (pressure + temporal) joined with per-trial features (gait + bilateral)
    join_keys = ["subject_id", "footwear", "trial"]

    features_df = pressure_feat_df.merge(gait_feat_df, on=join_keys, how="left")
    features_df = features_df.merge(bilateral_feat_df, on=join_keys, how="left")

    logger.info("Final feature table: %d rows × %d columns", *features_df.shape)

    # ── 8. Save ──────────────────────────────────────────────────────────────
    logger.info("=== STEP 8: Saving features to %s ===", output_path)
    # Drop pressure_array column if present (not needed in CSV)
    save_cols = [c for c in features_df.columns if c != "pressure_array"]
    features_df[save_cols].to_csv(output_path, index=False)
    logger.info("Saved %d rows.", len(features_df))

    elapsed = time.time() - t0
    logger.info("Pipeline completed in %.1f seconds.", elapsed)

    return features_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SoleSense Feature Pipeline")
    parser.add_argument("--subjects", type=int, default=None,
                        help="Max number of subjects to process (None = all)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output CSV path (default: data/features/features.csv)")
    parser.add_argument("--footwear", nargs="+", default=None,
                        help="Footwear conditions to include, e.g. BF ST")
    parser.add_argument("--trials", nargs="+", default=None,
                        help="Trial conditions to include, e.g. W1 W2")
    args = parser.parse_args()

    run_pipeline(
        max_subjects=args.subjects,
        footwear_list=args.footwear,
        trial_list=args.trials,
        output_path=args.output,
        save_intermediate=True,
    )
