"""
SoleSense Dashboard
====================
SOLESENSE — Personal Foot Loading & Gait Monitor

Built with Streamlit + Plotly.  Hardware-agnostic: the data source layer
is isolated so CSV files can later be replaced by live BLE/serial input.

Launch:
    cd f:/Dataset/SoleSense
    streamlit run dashboard/app.py
"""

import os
import sys
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ── path setup ────────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.risk_engine import compute_risk, score_features_df, score_trial_summary
from src.temperature_features import temperature_hardware_status

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SoleSense",
    page_icon="👟",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── colour palette ────────────────────────────────────────────────────────────
COLORS = {
    "primary":   "#1565C0",
    "accent":    "#00B0FF",
    "normal":    "#43A047",
    "monitor":   "#FB8C00",
    "alert":     "#E53935",
    "left":      "#1E88E5",
    "right":     "#E53935",
    "neutral":   "#607D8B",
    "bg_dark":   "#0E1117",
    "bg_card":   "#1A1F2E",
}

LEVEL_COLOR = {"NORMAL": COLORS["normal"], "MONITOR": COLORS["monitor"], "ALERT": COLORS["alert"]}
LEVEL_EMOJI = {"NORMAL": "✅", "MONITOR": "⚠️", "ALERT": "🚨"}

# ─────────────────────────────────────────────────────────────────────────────
# Data source adapter — swap this out when adding live hardware
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner="Loading feature data…")
def load_features() -> pd.DataFrame:
    """
    DATA SOURCE ADAPTER
    -------------------
    Currently reads from data/features/features.csv (dataset-based prototype).

    Future hardware integration:
        Replace this function with a live BLE/serial adapter that reads
        from the SoleSense insole firmware and returns the same DataFrame schema.
    """
    csv_path = os.path.join(PROJECT_ROOT, "data", "features", "features.csv")
    if not os.path.exists(csv_path):
        st.error(
            "features.csv not found.  Run the pipeline first:\n"
            "  `python -m src.feature_pipeline --subjects 10`"
        )
        st.stop()
    df = pd.read_csv(csv_path)
    return score_features_df(df)


def get_subjects(df: pd.DataFrame):
    return sorted(df["subject_id"].unique())


def get_footwear(df: pd.DataFrame):
    return sorted(df["footwear"].unique())


def get_trials(df: pd.DataFrame):
    return sorted(df["trial"].unique())


# ─────────────────────────────────────────────────────────────────────────────
# Re-usable plot helpers
# ─────────────────────────────────────────────────────────────────────────────

def _gauge(value: float, title: str, max_val: float = 100,
           threshold_monitor: float = 30, threshold_alert: float = 60) -> go.Figure:
    color = COLORS["normal"]
    if value >= threshold_alert:
        color = COLORS["alert"]
    elif value >= threshold_monitor:
        color = COLORS["monitor"]

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title, "font": {"size": 14}},
        number={"font": {"size": 32, "color": color}},
        gauge={
            "axis": {"range": [0, max_val], "tickwidth": 1},
            "bar": {"color": color, "thickness": 0.3},
            "steps": [
                {"range": [0, threshold_monitor], "color": "#1B3A2D"},
                {"range": [threshold_monitor, threshold_alert], "color": "#3E2A0A"},
                {"range": [threshold_alert, max_val], "color": "#3B0B0B"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 3},
                "thickness": 0.75,
                "value": value,
            },
        },
    ))
    fig.update_layout(height=200, margin=dict(t=30, b=0, l=20, r=20),
                      paper_bgcolor="rgba(0,0,0,0)", font_color="white")
    return fig


def _bar_lr(left_val: float, right_val: float, label: str, unit: str = "") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=["Left", "Right"], y=[left_val, right_val],
        marker_color=[COLORS["left"], COLORS["right"]],
        text=[f"{left_val:.1f}{unit}", f"{right_val:.1f}{unit}"],
        textposition="outside",
        cliponaxis=False,
    ))
    asym = abs(left_val - right_val) / ((left_val + right_val) / 2 + 1e-9) * 100
    fig.update_layout(
        title=dict(text=f"{label}<br><sup>Asymmetry: {asym:.1f}%</sup>", font_size=13),
        yaxis_title=unit,
        height=240,
        margin=dict(t=50, b=30, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        showlegend=False,
    )
    fig.update_yaxes(gridcolor="#333")
    return fig


def _plantar_heatmap(left_map: np.ndarray, right_map: np.ndarray) -> go.Figure:
    """Render side-by-side plantar pressure maps."""
    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=("Left Foot", "Right Foot"),
                        horizontal_spacing=0.08)

    vmax = max(left_map.max(), right_map.max(), 1)

    for col_i, (data, foot) in enumerate([(left_map, "L"), (right_map, "R")], start=1):
        fig.add_trace(
            go.Heatmap(
                z=data,
                colorscale="plasma",
                zmin=0, zmax=vmax,
                showscale=(col_i == 2),
                colorbar=dict(title="kPa", x=1.02, len=0.9) if col_i == 2 else None,
            ),
            row=1, col=col_i,
        )
        # Region separator lines
        for y_px, label in [(14, "Toe"), (34, "Forefoot"), (54, "Midfoot")]:
            fig.add_hline(y=y_px + 0.5, line_color="white", line_width=1,
                          line_dash="dot", row=1, col=col_i)

    fig.update_layout(
        height=380,
        margin=dict(t=40, b=20, l=20, r=60),
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="white",
    )
    fig.update_yaxes(title_text="Toe (0) → Heel", row=1, col=1)
    return fig


def _cop_trajectory(arr: np.ndarray, side: str) -> go.Figure:
    """Plot CoP trajectory over a background pressure heatmap."""
    _R = np.arange(75, dtype=float)
    _C = np.arange(40, dtype=float)
    per_frame = arr.sum(axis=(1, 2))
    active = per_frame > 0
    if active.sum() < 2:
        return go.Figure()
    act_arr = arr[active]
    act_tot = per_frame[active]
    cop_row = (act_arr * _R[:, None]).sum(axis=(1, 2)) / act_tot * 0.5
    cop_col = (act_arr * _C[None, :]).sum(axis=(1, 2)) / act_tot * 0.5

    bg = arr.mean(axis=0)
    n = len(cop_row)
    colors_seq = [f"rgb({int(255*(1-i/n))},{int(100*(i/n))},{int(255*(i/n))})" for i in range(n)]

    fig = go.Figure()
    fig.add_trace(go.Heatmap(z=bg, colorscale="Greys", showscale=False,
                              x=np.arange(40)*0.5, y=np.arange(75)*0.5))
    fig.add_trace(go.Scatter(
        x=cop_col, y=cop_row, mode="lines+markers",
        line=dict(color="cyan", width=2),
        marker=dict(color=list(range(n)), colorscale="plasma", size=5, showscale=False),
        name="CoP path",
    ))
    fig.add_trace(go.Scatter(x=[cop_col[0]], y=[cop_row[0]], mode="markers",
                              marker=dict(color="lime", size=12, symbol="circle"),
                              name="Strike"))
    fig.add_trace(go.Scatter(x=[cop_col[-1]], y=[cop_row[-1]], mode="markers",
                              marker=dict(color="red", size=12, symbol="triangle-up"),
                              name="Toe-off"))
    fig.update_layout(
        title=f"CoP Trajectory — {side}",
        xaxis_title="Lateral (cm)", yaxis_title="Toe→Heel (cm)",
        height=340, margin=dict(t=40, b=30, l=40, r=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="white", legend=dict(orientation="h", y=-0.12),
    )
    fig.update_xaxes(gridcolor="#333")
    fig.update_yaxes(gridcolor="#333")
    return fig


def _risk_factor_table(risk_result) -> None:
    """Render the explainable risk factor breakdown."""
    for factor in risk_result.factors:
        icon = "⚠️" if factor.triggered else "✅"
        color = COLORS["alert"] if factor.triggered else COLORS["normal"]
        bar_pct = int(factor.sub_score / 40 * 100) if factor.triggered else 0
        with st.container():
            col1, col2 = st.columns([3, 1])
            col1.markdown(
                f'<span style="color:{color};font-size:15px">{icon} **{factor.label}**</span><br>'
                f'<span style="color:#aaa;font-size:12px">{factor.detail}</span>',
                unsafe_allow_html=True,
            )
            col2.markdown(
                f'<div style="text-align:right;color:{color};font-size:18px;font-weight:bold">'
                f'+{factor.sub_score:.0f}</div>',
                unsafe_allow_html=True,
            )


def _time_series_chart(df: pd.DataFrame, col: str, title: str, unit: str = "") -> go.Figure:
    fig = go.Figure()
    for side, color in [("Left", COLORS["left"]), ("Right", COLORS["right"])]:
        side_df = df[df["side"] == side].sort_values("footstep_id")
        if side_df.empty:
            continue
        fig.add_trace(go.Scatter(
            x=side_df["footstep_id"],
            y=side_df[col],
            mode="lines+markers",
            name=side,
            line=dict(color=color, width=2),
            marker=dict(size=4),
        ))
    fig.update_layout(
        title=title,
        xaxis_title="Step index",
        yaxis_title=unit,
        height=260,
        margin=dict(t=40, b=30, l=40, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        legend=dict(orientation="h", y=-0.2),
    )
    fig.update_xaxes(gridcolor="#333")
    fig.update_yaxes(gridcolor="#333")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────

def _inject_css():
    st.markdown("""
    <style>
    /* Global dark background */
    .stApp { background-color: #0E1117; color: #E0E0E0; }
    /* Header strip */
    .solesense-header {
        background: linear-gradient(135deg, #1565C0 0%, #0D47A1 50%, #01579B 100%);
        border-radius: 12px; padding: 20px 32px; margin-bottom: 20px;
    }
    .solesense-header h1 { color: white; font-size: 2.4rem; letter-spacing: 4px;
        font-weight: 800; margin: 0; }
    .solesense-header p { color: #90CAF9; font-size: 1.0rem; margin: 4px 0 0 0; }
    /* Metric cards */
    .metric-card {
        background: #1A1F2E; border: 1px solid #2A3050;
        border-radius: 10px; padding: 16px 20px; margin: 6px 0;
    }
    .metric-card h4 { color: #90CAF9; font-size: 0.8rem; margin: 0 0 6px 0;
        text-transform: uppercase; letter-spacing: 1px; }
    .metric-card p { font-size: 1.6rem; font-weight: 700; margin: 0; }
    /* Section headers */
    .section-header {
        color: #90CAF9; font-size: 0.75rem; text-transform: uppercase;
        letter-spacing: 2px; border-bottom: 1px solid #2A3050;
        padding-bottom: 6px; margin: 20px 0 12px 0;
    }
    /* Risk badge */
    .risk-badge-NORMAL  { background:#1B3A2D; color:#43A047; }
    .risk-badge-MONITOR { background:#3E2A0A; color:#FB8C00; }
    .risk-badge-ALERT   { background:#3B0B0B; color:#EF5350; }
    .risk-badge {
        display:inline-block; border-radius:20px; padding:6px 18px;
        font-size:1.1rem; font-weight:700; letter-spacing:2px;
    }
    /* Disclaimer */
    .disclaimer {
        background:#1A1F2E; border-left:3px solid #FB8C00;
        padding:8px 14px; border-radius:4px; color:#FFB74D;
        font-size:0.8rem; margin-top:10px;
    }
    /* Sidebar */
    [data-testid="stSidebar"] { background:#131722; }
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

def render_sidebar(df: pd.DataFrame):
    with st.sidebar:
        st.markdown("## 🎛 Session Controls")
        subject = st.selectbox("Subject ID", get_subjects(df), index=0)
        sub_df = df[df["subject_id"] == subject]

        footwear = st.selectbox("Footwear", get_footwear(sub_df), index=0)
        fw_df = sub_df[sub_df["footwear"] == footwear]

        trial = st.selectbox("Trial / Speed", get_trials(fw_df), index=0)

        st.divider()
        st.markdown("**Data source:** `data/features/features.csv`  \n"
                    "**Sensor:** StepUP-P150 floor mat  \n"
                    "**Sampling:** 100 Hz  \n"
                    "**Subjects loaded:** " + str(df["subject_id"].nunique()))
        st.divider()
        st.markdown(
            '<div class="disclaimer">⚠ EXPERIMENTAL PROTOTYPE<br>'
            'Not for clinical use. SoleSense Risk Indicator is not validated.</div>',
            unsafe_allow_html=True,
        )
    return subject, footwear, trial


# ─────────────────────────────────────────────────────────────────────────────
# Section renderers
# ─────────────────────────────────────────────────────────────────────────────

def render_header():
    st.markdown("""
    <div class="solesense-header">
      <h1>SOLESENSE</h1>
      <p>Personal Foot Loading &amp; Gait Monitor &nbsp;|&nbsp; Research Prototype</p>
    </div>
    """, unsafe_allow_html=True)


def render_overall_status(trial_df: pd.DataFrame, subject: str, footwear: str, trial: str):
    st.markdown('<div class="section-header">① Overall Status</div>', unsafe_allow_html=True)

    if trial_df.empty:
        st.warning("No data for this selection.")
        return None

    # Compute risk on the median-like representative row
    rep_row = trial_df.sort_values("risk_score", ascending=False).iloc[0]
    risk_result = compute_risk(rep_row)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.plotly_chart(_gauge(risk_result.risk_score, "Risk Indicator"), use_container_width=True)
    with col2:
        level_color = LEVEL_COLOR[risk_result.risk_level]
        st.markdown(
            f'<div class="metric-card"><h4>Risk Level</h4>'
            f'<p style="color:{level_color}">'
            f'{LEVEL_EMOJI[risk_result.risk_level]} {risk_result.risk_level}</p></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="metric-card"><h4>Most Affected Region</h4>'
            f'<p style="color:#90CAF9;font-size:1.1rem">{risk_result.affected_region.replace("_"," ")}</p></div>',
            unsafe_allow_html=True,
        )
    with col3:
        n = len(risk_result.contributing_factors)
        st.markdown(
            f'<div class="metric-card"><h4>Contributing Factors</h4>'
            f'<p style="color:{COLORS["monitor"] if n>0 else COLORS["normal"]}">{n}</p></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="metric-card"><h4>Steps Analysed</h4>'
            f'<p>{len(trial_df)}</p></div>',
            unsafe_allow_html=True,
        )
    with col4:
        st.markdown(
            f'<div class="metric-card"><h4>Session</h4>'
            f'<p style="font-size:0.95rem">Subject {subject}<br>{footwear} | {trial}</p></div>',
            unsafe_allow_html=True,
        )
        mean_risk = trial_df["risk_score"].mean()
        st.markdown(
            f'<div class="metric-card"><h4>Mean Risk (trial)</h4>'
            f'<p style="color:{LEVEL_COLOR[risk_result.risk_level]}">{mean_risk:.1f}</p></div>',
            unsafe_allow_html=True,
        )
    return risk_result


def render_foot_pressure(trial_df: pd.DataFrame):
    st.markdown('<div class="section-header">② Foot Pressure</div>', unsafe_allow_html=True)

    left_df  = trial_df[trial_df["side"] == "Left"]
    right_df = trial_df[trial_df["side"] == "Right"]

    col1, col2, col3, col4 = st.columns(4)
    for col, df_side, label, color in [
        (col1, left_df,  "Left",  COLORS["left"]),
        (col2, right_df, "Right", COLORS["right"]),
    ]:
        with col:
            mean_p = df_side["press_mean_kpa"].mean() if not df_side.empty else 0
            max_p  = df_side["press_max_kpa"].max()  if not df_side.empty else 0
            pti    = df_side["pti_total_kpa_s"].mean() if not df_side.empty else 0
            area   = df_side["contact_area_cm2"].mean() if not df_side.empty else 0
            st.markdown(
                f'<div class="metric-card"><h4>{label} Mean Pressure</h4>'
                f'<p style="color:{color}">{mean_p:.1f} kPa</p></div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="metric-card"><h4>{label} Peak Pressure</h4>'
                f'<p style="color:{color}">{max_p:.1f} kPa</p></div>',
                unsafe_allow_html=True,
            )
    with col3:
        pti_l = left_df["pti_total_kpa_s"].mean() if not left_df.empty else 0
        pti_r = right_df["pti_total_kpa_s"].mean() if not right_df.empty else 0
        st.markdown(
            f'<div class="metric-card"><h4>Left PTI</h4>'
            f'<p style="color:{COLORS["left"]}">{pti_l:.0f} kPa·s</p></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="metric-card"><h4>Right PTI</h4>'
            f'<p style="color:{COLORS["right"]}">{pti_r:.0f} kPa·s</p></div>',
            unsafe_allow_html=True,
        )
    with col4:
        st.markdown(
            f'<div class="metric-card"><h4>Loading Rate (Left)</h4>'
            f'<p>{left_df["loading_rate_kpa_s"].mean():.0f} kPa/s</p></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="metric-card"><h4>Loading Rate (Right)</h4>'
            f'<p>{right_df["loading_rate_kpa_s"].mean():.0f} kPa/s</p></div>',
            unsafe_allow_html=True,
        )

    # Regional loading chart
    st.markdown("")
    reg_cols = ["load_frac_toe", "load_frac_forefoot", "load_frac_midfoot", "load_frac_rearfoot"]
    reg_labels = ["Toe", "Forefoot", "Midfoot", "Rearfoot"]
    reg_colors = ["#FF5722", "#FF9800", "#4CAF50", "#2196F3"]

    fig = go.Figure()
    for side, df_s, color_s in [("Left", left_df, COLORS["left"]), ("Right", right_df, COLORS["right"])]:
        if df_s.empty:
            continue
        means = [df_s[c].mean() * 100 for c in reg_cols]
        fig.add_trace(go.Bar(
            name=side, x=reg_labels, y=means,
            marker_color=color_s, opacity=0.85,
            text=[f"{v:.1f}%" for v in means], textposition="auto",
        ))
    fig.update_layout(
        title="Regional Loading Distribution",
        yaxis_title="Load Fraction (%)", barmode="group",
        height=280, margin=dict(t=40, b=30, l=40, r=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="white", legend=dict(orientation="h", y=-0.2),
    )
    fig.update_yaxes(gridcolor="#333")
    st.plotly_chart(fig, use_container_width=True)


def render_bilateral(trial_df: pd.DataFrame):
    st.markdown('<div class="section-header">③ Left ↔ Right Comparison</div>', unsafe_allow_html=True)

    left_df  = trial_df[trial_df["side"] == "Left"]
    right_df = trial_df[trial_df["side"] == "Right"]

    def safe_mean(df_s, col):
        return float(df_s[col].mean()) if not df_s.empty and col in df_s else 0.0

    c1, c2, c3 = st.columns(3)
    with c1:
        l_val = safe_mean(left_df, "pti_total_kpa_s")
        r_val = safe_mean(right_df, "pti_total_kpa_s")
        st.plotly_chart(_bar_lr(l_val, r_val, "Pressure-Time Integral", "kPa·s"),
                        use_container_width=True)
    with c2:
        l_val = safe_mean(left_df, "press_max_kpa")
        r_val = safe_mean(right_df, "press_max_kpa")
        st.plotly_chart(_bar_lr(l_val, r_val, "Peak Pressure", "kPa"),
                        use_container_width=True)
    with c3:
        l_val = safe_mean(left_df, "stance_time_s")
        r_val = safe_mean(right_df, "stance_time_s")
        st.plotly_chart(_bar_lr(l_val, r_val, "Stance Duration", "s"),
                        use_container_width=True)

    # Asymmetry metrics
    asym_cols = {
        "PTI Asymmetry":        "asym_pti_total_kpa_s",
        "Peak Pressure Asym":   "asym_press_max_kpa",
        "Forefoot Load Asym":   "asym_load_forefoot",
        "Stance Time Asym":     "asym_stance_time",
        "CoP Path Asym":        "asym_cop_path_length_cm",
    }
    asym_row = trial_df.iloc[0]
    asym_vals = {k: float(asym_row.get(v, 0)) if not pd.isna(asym_row.get(v, 0)) else 0.0
                 for k, v in asym_cols.items()}

    fig_asym = go.Figure(go.Bar(
        x=list(asym_vals.keys()),
        y=list(asym_vals.values()),
        marker_color=[
            COLORS["alert"] if v > 20 else COLORS["monitor"] if v > 10 else COLORS["normal"]
            for v in asym_vals.values()
        ],
        text=[f"{v:.1f}%" for v in asym_vals.values()],
        textposition="outside",
    ))
    fig_asym.add_hline(y=10, line_dash="dash", line_color=COLORS["monitor"],
                        annotation_text="Moderate (10%)", annotation_position="right")
    fig_asym.add_hline(y=20, line_dash="dash", line_color=COLORS["alert"],
                        annotation_text="High (20%)", annotation_position="right")
    fig_asym.update_layout(
        title="Bilateral Asymmetry Overview",
        yaxis_title="NSI (%)", height=280,
        margin=dict(t=40, b=40, l=40, r=100),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="white", showlegend=False,
    )
    fig_asym.update_yaxes(gridcolor="#333")
    st.plotly_chart(fig_asym, use_container_width=True)


def render_temperature():
    st.markdown('<div class="section-header">④ Temperature</div>', unsafe_allow_html=True)
    status = temperature_hardware_status()
    st.markdown(f"""
    <div style="background:#1A1F2E;border:1px solid #2A3050;border-radius:10px;padding:20px;">
      <h3 style="color:#FF9800;margin-top:0">🔬 Hardware Roadmap</h3>
      <p style="color:#ccc;line-height:1.7">{status['description']}</p>
      <table style="color:#aaa;font-size:0.9rem;width:100%">
        <tr><td style="padding:4px 12px 4px 0"><b>Planned sensors</b></td>
            <td>{status['planned_sensors']}</td></tr>
        <tr><td style="padding:4px 12px 4px 0"><b>Planned feature</b></td>
            <td>{status['planned_feature']}</td></tr>
        <tr><td style="padding:4px 12px 4px 0"><b>Dataset note</b></td>
            <td>{status['dataset_note']}</td></tr>
      </table>
    </div>
    """, unsafe_allow_html=True)


def render_gait(trial_df: pd.DataFrame):
    st.markdown('<div class="section-header">⑤ Gait</div>', unsafe_allow_html=True)

    row = trial_df.iloc[0]
    gait_metrics = {
        "Cadence": (row.get("cadence_steps_per_min", 0), "steps/min"),
        "Mean Step Time": (row.get("step_time_mean_s", 0), "s"),
        "Step Time CV": (row.get("step_time_cv", 0), "—"),
        "Mean Stance Time": (row.get("stance_mean_s", 0), "s"),
        "Gait Symmetry Index": (row.get("gait_symmetry_index", 0), "—"),
        "Steps (Left)": (row.get("n_steps_left_x", row.get("n_steps_left", 0)), ""),
        "Steps (Right)": (row.get("n_steps_right_x", row.get("n_steps_right", 0)), ""),
        "Stance Fraction L": (row.get("stance_fraction_left", 0), "—"),
        "Stance Fraction R": (row.get("stance_fraction_right", 0), "—"),
        "Left Stride Time": (row.get("stride_time_left_mean_s", 0), "s"),
        "Right Stride Time": (row.get("stride_time_right_mean_s", 0), "s"),
        "Temporal Variability": (row.get("gait_temporal_variability", 0), "—"),
    }
    cols = st.columns(4)
    for i, (label, (val, unit)) in enumerate(gait_metrics.items()):
        val_s = f"{val:.3f}" if isinstance(val, float) and val < 10 else f"{val:.1f}"
        color = COLORS["neutral"]
        if label == "Gait Symmetry Index" and val > 0.1:
            color = COLORS["monitor"]
        if label == "Step Time CV" and val > 0.15:
            color = COLORS["monitor"]
        cols[i % 4].markdown(
            f'<div class="metric-card"><h4>{label}</h4>'
            f'<p style="color:{color}">{val_s} <span style="font-size:0.8rem;color:#888">{unit}</span></p></div>',
            unsafe_allow_html=True,
        )

    st.markdown("")
    # Stance time over steps
    st.plotly_chart(
        _time_series_chart(trial_df, "stance_time_s", "Stance Time per Step", "s"),
        use_container_width=True,
    )


def render_cop_section(trial_df: pd.DataFrame, dataset_root: str):
    st.markdown('<div class="section-header">⑥ Pressure Map & CoP Trajectory</div>',
                unsafe_allow_html=True)

    # Collect pressure arrays on-demand
    from src.data_loader import load_walking_trial
    left_df = trial_df[trial_df["side"] == "Left"]
    right_df = trial_df[trial_df["side"] == "Right"]

    subject = str(trial_df["subject_id"].iloc[0]).zfill(3)
    footwear = trial_df["footwear"].iloc[0]
    tr = trial_df["trial"].iloc[0]

    raw = load_walking_trial(subject, footwear, tr, include_pressure_arrays=True,
                              dataset_root=dataset_root)
    if raw is None or raw.empty:
        st.info("Pressure arrays not available for map rendering.")
        return

    raw = raw[raw["exclude"] == 0].reset_index(drop=True)

    left_maps, right_maps = [], []
    left_arr, right_arr = None, None
    for _, r in raw.iterrows():
        arr = r.get("pressure_array")
        if arr is None:
            continue
        if r["side"] == "Left":
            left_maps.append(arr.mean(axis=0))
            if left_arr is None:
                left_arr = arr
        else:
            right_maps.append(arr.mean(axis=0))
            if right_arr is None:
                right_arr = arr

    left_avg  = np.mean(left_maps, axis=0)  if left_maps  else np.zeros((75, 40))
    right_avg = np.mean(right_maps, axis=0) if right_maps else np.zeros((75, 40))

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(_plantar_heatmap(left_avg, right_avg), use_container_width=True)
    with c2:
        cop_col1, cop_col2 = st.columns(2)
        with cop_col1:
            if left_arr is not None:
                st.plotly_chart(_cop_trajectory(left_arr, "Left"), use_container_width=True)
        with cop_col2:
            if right_arr is not None:
                st.plotly_chart(_cop_trajectory(right_arr, "Right"), use_container_width=True)

    # CoP metrics
    cop_feats = ["cop_path_length_cm", "cop_ap_range_cm", "cop_ml_range_cm",
                 "cop_mean_velocity_cm_s"]
    cop_labels = ["CoP Path (cm)", "AP Range (cm)", "ML Range (cm)", "CoP Velocity (cm/s)"]
    c1, c2, c3, c4 = st.columns(4)
    for col, feat, label in zip([c1, c2, c3, c4], cop_feats, cop_labels):
        l_val = left_df[feat].mean() if feat in left_df and not left_df.empty else 0
        r_val = right_df[feat].mean() if feat in right_df and not right_df.empty else 0
        col.markdown(
            f'<div class="metric-card"><h4>{label}</h4>'
            f'<p style="color:{COLORS["left"]};font-size:1.1rem">L: {l_val:.2f}</p>'
            f'<p style="color:{COLORS["right"]};font-size:1.1rem">R: {r_val:.2f}</p></div>',
            unsafe_allow_html=True,
        )


def render_explainable_risk(risk_result):
    st.markdown('<div class="section-header">⑦ Explainable Risk</div>', unsafe_allow_html=True)

    level_color = LEVEL_COLOR[risk_result.risk_level]
    st.markdown(
        f"**Why is the SoleSense Risk Indicator "
        f'<span style="color:{level_color}">{risk_result.risk_level}</span>?**',
        unsafe_allow_html=True,
    )
    if risk_result.contributing_factors:
        st.markdown(f"**{len(risk_result.contributing_factors)} active factor(s):**")
    else:
        st.success("No risk factors triggered in this session.")

    _risk_factor_table(risk_result)

    st.markdown("")
    rec_color = LEVEL_COLOR[risk_result.risk_level]
    st.markdown(
        f'<div style="background:#1A1F2E;border-left:4px solid {rec_color};'
        f'border-radius:6px;padding:12px 16px;color:#ddd;margin-top:12px">'
        f'💡 <b>Recommended Action:</b> {risk_result.recommended_action}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="disclaimer">⚠ All thresholds are EXPERIMENTAL. '
        'SoleSense does not diagnose any medical condition.</div>',
        unsafe_allow_html=True,
    )


def render_historical_trend(df: pd.DataFrame, subject: str):
    st.markdown('<div class="section-header">⑧ Historical Trend</div>', unsafe_allow_html=True)

    sub_df = df[df["subject_id"] == subject]
    if sub_df.empty:
        st.info("No historical data for this subject.")
        return

    trial_summary = score_trial_summary(sub_df)

    tab1, tab2 = st.tabs(["Risk Score Trend", "Feature Trends"])

    with tab1:
        fig = go.Figure()
        for fw, color in zip(["BF", "ST", "P1", "P2"],
                              ["#2196F3", "#4CAF50", "#FF9800", "#E91E63"]):
            fw_data = trial_summary[trial_summary["footwear"] == fw].sort_values("trial")
            if fw_data.empty:
                continue
            fig.add_trace(go.Scatter(
                x=fw_data["trial"], y=fw_data["risk_score_max"],
                mode="lines+markers", name=fw,
                line=dict(color=color, width=2),
                marker=dict(size=8),
            ))
        fig.add_hline(y=30, line_dash="dash", line_color=COLORS["monitor"],
                       annotation_text="MONITOR")
        fig.add_hline(y=60, line_dash="dash", line_color=COLORS["alert"],
                       annotation_text="ALERT")
        fig.update_layout(
            title=f"Subject {subject} — Risk Score Trend by Footwear",
            xaxis_title="Trial", yaxis_title="Max Risk Score",
            yaxis=dict(range=[0, 100]),
            height=320, margin=dict(t=40, b=40, l=40, r=40),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="white", legend=dict(orientation="h", y=-0.2),
        )
        fig.update_yaxes(gridcolor="#333")
        fig.update_xaxes(gridcolor="#333")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        feat_options = {
            "Peak Pressure (kPa)": "press_max_kpa",
            "PTI (kPa·s)": "pti_total_kpa_s",
            "PTI Asymmetry (%)": "asym_pti_total_kpa_s",
            "Stance Time (s)": "stance_time_s",
            "CoP Path (cm)": "cop_path_length_cm",
        }
        selected = st.selectbox("Feature to trend", list(feat_options.keys()))
        feat_col = feat_options[selected]

        trend_df = sub_df.groupby(["footwear", "trial"])[feat_col].mean().reset_index()
        fig2 = px.line(
            trend_df, x="trial", y=feat_col, color="footwear",
            markers=True, title=f"Subject {subject} — {selected} by Condition",
            color_discrete_sequence=["#2196F3", "#4CAF50", "#FF9800", "#E91E63"],
        )
        fig2.update_layout(
            height=300, margin=dict(t=40, b=40, l=40, r=40),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="white", xaxis_title="Trial",
        )
        fig2.update_yaxes(gridcolor="#333")
        fig2.update_xaxes(gridcolor="#333")
        st.plotly_chart(fig2, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main app
# ─────────────────────────────────────────────────────────────────────────────

def main():
    _inject_css()
    render_header()

    df = load_features()
    subject, footwear, trial = render_sidebar(df)

    trial_df = df[
        (df["subject_id"] == subject) &
        (df["footwear"] == footwear) &
        (df["trial"] == trial)
    ].reset_index(drop=True)

    dataset_root = os.path.join(
        PROJECT_ROOT, "..", "FRDR_dataset_1280_download_590_202609031103", "py"
    )

    # ── Sections ─────────────────────────────────────────────────────────────
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

    # Footer
    st.markdown("---")
    st.markdown(
        '<p style="text-align:center;color:#555;font-size:0.8rem">'
        'SoleSense Research Prototype · Dataset: StepUP-P150 (CC BY 4.0) · '
        'Not a medical device</p>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
