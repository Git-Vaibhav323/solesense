"""
SoleSense — Dataset Explorer page
Moved from app.py — full 8-section dataset dashboard.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# re-export everything from app core
from dashboard.app import (
    _inject_css, render_header, load_features, render_sidebar,
    render_overall_status, render_foot_pressure, render_bilateral,
    render_temperature, render_gait, render_cop_section,
    render_explainable_risk, render_historical_trend,
    render_hardware_input_section, render_hardware_results,
    COLORS,
)
import streamlit as st
import os

st.set_page_config(page_title="SoleSense — Dataset Explorer",
                   page_icon="📊", layout="wide")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_inject_css()
render_header()

df                       = load_features()
subject, footwear, trial = render_sidebar(df)
trial_df = df[
    (df["subject_id"] == subject) &
    (df["footwear"]   == footwear) &
    (df["trial"]      == trial)
].reset_index(drop=True)

dataset_root = os.path.join(
    PROJECT_ROOT, "..", "FRDR_dataset_1280_download_590_202609031103", "py"
)

risk_result = render_overall_status(trial_df, subject, footwear, trial)
st.divider()
render_foot_pressure(trial_df)
st.divider()
render_bilateral(trial_df)
st.divider()
render_temperature()
st.divider()
render_gait(trial_df)
st.divider()
render_cop_section(trial_df, dataset_root)
st.divider()
if risk_result:
    render_explainable_risk(risk_result)
st.divider()
render_historical_trend(df, subject)
st.divider()
hw = render_hardware_input_section()
if hw is not None:
    render_hardware_results(hw)
