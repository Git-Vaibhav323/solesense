"""
SoleSense Dashboard  ·  v2
===========================
Two pages accessible via the top navigation:

  🏠 Quick Analysis   — manual sensor input → instant live-updating risk result
  📊 Dataset Explorer — full 8-section analysis of the static features.csv

Run from the project root:
    cd f:/Dataset/SoleSense
    python -m streamlit run dashboard/app.py
"""

import warnings
warnings.filterwarnings("ignore")

import os, sys, logging
import numpy as np
import pandas as pd

logging.getLogger("streamlit").setLevel(logging.ERROR)

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.risk_engine import compute_risk, score_features_df, score_trial_summary, RiskResult
from src.temperature_features import temperature_hardware_status

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SoleSense",
    page_icon="👟",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── colour palette ────────────────────────────────────────────────────────────
C = {
    "primary":  "#1565C0",
    "accent":   "#00B0FF",
    "normal":   "#43A047",
    "monitor":  "#FB8C00",
    "alert":    "#E53935",
    "left":     "#1E88E5",
    "right":    "#E53935",
    "neutral":  "#607D8B",
    "bg":       "#0E1117",
    "card":     "#1A1F2E",
    "border":   "#2A3050",
}
LEVEL_COLOR = {"NORMAL": C["normal"], "MONITOR": C["monitor"], "ALERT": C["alert"]}
LEVEL_EMOJI = {"NORMAL": "✅", "MONITOR": "⚠️", "ALERT": "🚨"}


# ═════════════════════════════════════════════════════════════════════════════
#  CSS
# ═════════════════════════════════════════════════════════════════════════════

def _css():
    st.markdown("""
<style>
/* global */
.stApp { background-color:#0E1117; color:#E0E0E0; }
.block-container { padding-top:1rem; }

/* header banner */
.ss-header {
    background:linear-gradient(135deg,#1565C0 0%,#0D47A1 50%,#01579B 100%);
    border-radius:14px; padding:22px 32px; margin-bottom:18px;
    box-shadow:0 4px 24px rgba(21,101,192,0.4);
}
.ss-header h1 {
    color:white; font-size:2.6rem; letter-spacing:5px;
    font-weight:900; margin:0;
}
.ss-header p { color:#90CAF9; font-size:1rem; margin:4px 0 0 0; }

/* nav pills */
.nav-pill {
    display:inline-block; padding:7px 20px; border-radius:20px;
    font-size:0.9rem; font-weight:600; cursor:pointer;
    border:1px solid #2A3050; margin-right:8px;
    transition:all 0.2s;
}
.nav-active { background:#1565C0; color:white; border-color:#1565C0; }
.nav-inactive { background:#1A1F2E; color:#90CAF9; }

/* metric cards */
.mc {
    background:#1A1F2E; border:1px solid #2A3050;
    border-radius:10px; padding:14px 18px; margin:5px 0;
}
.mc h4 {
    color:#90CAF9; font-size:0.72rem; margin:0 0 5px 0;
    text-transform:uppercase; letter-spacing:1.5px;
}
.mc p { font-size:1.55rem; font-weight:700; margin:0; }

/* result box */
.rbox { border-radius:12px; padding:20px 26px; margin:14px 0; }

/* hardware card */
.hwc {
    background:#0D1B2A; border:1px solid #1565C0;
    border-radius:10px; padding:12px 16px; margin:4px 0;
}
.hwc h4 {
    color:#42A5F5; font-size:0.72rem; margin:0 0 4px 0;
    text-transform:uppercase; letter-spacing:1px;
}
.hwc p { font-size:1.35rem; font-weight:700; margin:0; color:#E3F2FD; }

/* section headers */
.sh {
    color:#90CAF9; font-size:0.72rem; text-transform:uppercase;
    letter-spacing:2px; border-bottom:1px solid #2A3050;
    padding-bottom:6px; margin:22px 0 12px 0;
}

/* disclaimer */
.disc {
    background:#1A1F2E; border-left:3px solid #FB8C00;
    padding:8px 14px; border-radius:4px;
    color:#FFB74D; font-size:0.78rem; margin-top:10px;
}

/* factor row */
.factor-row { padding:8px 0; border-bottom:1px solid #1e2330; }

/* sidebar */
[data-testid="stSidebar"] { background:#131722; }

/* input labels */
div[data-testid="stNumberInput"] label,
div[data-testid="stSlider"]      label { color:#90CAF9 !important; }

/* live badge */
.live-badge {
    display:inline-block; background:#E53935; color:white;
    font-size:0.7rem; font-weight:700; padding:2px 8px;
    border-radius:10px; letter-spacing:1px; margin-left:8px;
    animation:pulse 1.5s infinite;
}
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }

/* footer */
.footer {
    text-align:center; color:#555; font-size:0.75rem;
    margin-top:30px; padding-top:12px;
    border-top:1px solid #1e2330;
}
</style>
""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
#  Shared chart helpers
# ═════════════════════════════════════════════════════════════════════════════

def _chart_layout(fig, height=260, margin=(40, 30, 40, 20), title=None):
    fig.update_layout(
        height=height,
        margin=dict(t=margin[0], b=margin[1], l=margin[2], r=margin[3]),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        title=title,
    )
    fig.update_xaxes(gridcolor="#252b3b", zerolinecolor="#252b3b")
    fig.update_yaxes(gridcolor="#252b3b", zerolinecolor="#252b3b")
    return fig


def gauge(value: float, title: str = "Risk", max_val=100,
          thr_mon=30, thr_alert=60) -> go.Figure:
    color = C["normal"]
    if value >= thr_alert:  color = C["alert"]
    elif value >= thr_mon:  color = C["monitor"]
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        delta={"reference": thr_mon, "increasing": {"color": C["alert"]},
               "decreasing": {"color": C["normal"]}},
        title={"text": title, "font": {"size": 13}},
        number={"font": {"size": 38, "color": color}},
        gauge={
            "axis": {"range": [0, max_val], "tickwidth": 1, "tickcolor": "#555"},
            "bar":  {"color": color, "thickness": 0.28},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": [
                {"range": [0, thr_mon],        "color": "#162618"},
                {"range": [thr_mon, thr_alert], "color": "#2e1f06"},
                {"range": [thr_alert, max_val], "color": "#2d0808"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 3},
                "thickness": 0.75, "value": value,
            },
        },
    ))
    fig.update_layout(
        height=230, margin=dict(t=40, b=0, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)", font_color="white",
    )
    return fig


def bar_lr(lv: float, rv: float, label: str, unit: str = "") -> go.Figure:
    asym = abs(lv - rv) / ((lv + rv) / 2 + 1e-9) * 100
    fig  = go.Figure()
    fig.add_trace(go.Bar(
        x=["Left", "Right"], y=[lv, rv],
        marker_color=[C["left"], C["right"]],
        marker_line_color=["#42A5F5", "#EF9A9A"],
        marker_line_width=1.5,
        text=[f"{lv:.1f}{unit}", f"{rv:.1f}{unit}"],
        textposition="outside", cliponaxis=False,
    ))
    return _chart_layout(fig, height=230, title=dict(
        text=f"{label}<br><sup style='color:#aaa'>Asymmetry {asym:.1f}%</sup>",
        font=dict(size=13),
    ))


def radar_chart(categories: list, left_vals: list, right_vals: list,
                title: str = "Bilateral Radar") -> go.Figure:
    """Desmos-style polar/radar chart for bilateral comparison."""
    cats = categories + [categories[0]]
    lv   = left_vals  + [left_vals[0]]
    rv   = right_vals + [right_vals[0]]
    fig  = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=lv, theta=cats, fill="toself", name="Left",
        line=dict(color=C["left"], width=2.5),
        fillcolor="rgba(30,136,229,0.18)",
    ))
    fig.add_trace(go.Scatterpolar(
        r=rv, theta=cats, fill="toself", name="Right",
        line=dict(color=C["right"], width=2.5),
        fillcolor="rgba(229,57,53,0.15)",
    ))
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, gridcolor="#252b3b",
                            tickfont=dict(color="#888", size=9)),
            angularaxis=dict(gridcolor="#252b3b",
                             tickfont=dict(color="#90CAF9", size=10)),
        ),
        showlegend=True,
        legend=dict(orientation="h", y=-0.12, font=dict(size=11)),
        title=dict(text=title, font=dict(size=13, color="#90CAF9")),
        height=320,
        margin=dict(t=50, b=50, l=40, r=40),
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="white",
    )
    return fig


def donut_regional(left_vals: list, right_vals: list) -> go.Figure:
    """Desmos-inspired dual-donut regional loading."""
    labels = ["Toe", "Forefoot", "Midfoot", "Rearfoot"]
    colors = ["#42A5F5", "#1565C0", "#0D47A1", "#004E9A"]
    fig = make_subplots(rows=1, cols=2, specs=[[{"type":"pie"}, {"type":"pie"}]],
                        subplot_titles=["Left Foot", "Right Foot"])
    fig.add_trace(go.Pie(
        labels=labels, values=left_vals, hole=0.55,
        marker_colors=colors, textinfo="label+percent",
        textfont=dict(size=11), name="Left",
        hovertemplate="%{label}: %{value:.0f}%<extra>Left</extra>",
    ), row=1, col=1)
    fig.add_trace(go.Pie(
        labels=labels, values=right_vals, hole=0.55,
        marker_colors=["#EF9A9A","#E53935","#B71C1C","#7f0000"],
        textinfo="label+percent",
        textfont=dict(size=11), name="Right",
        hovertemplate="%{label}: %{value:.0f}%<extra>Right</extra>",
    ), row=1, col=2)
    fig.update_layout(
        height=300, margin=dict(t=40, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)", font_color="white",
        showlegend=False,
    )
    return fig


def asymmetry_waterfall(names: list, values: list) -> go.Figure:
    """Waterfall-style asymmetry chart — positive = left dominant."""
    colors = [C["left"] if v > 0 else C["right"] for v in values]
    fig = go.Figure(go.Bar(
        x=names, y=values,
        marker_color=colors,
        text=[f"{v:+.1f}%" for v in values],
        textposition="outside",
        cliponaxis=False,
    ))
    fig.add_hline(y=0, line_color="#555", line_width=1)
    fig.add_hline(y=10,  line_dash="dash", line_color=C["monitor"],
                  annotation_text="10% threshold", annotation_font_color=C["monitor"])
    fig.add_hline(y=-10, line_dash="dash", line_color=C["monitor"])
    return _chart_layout(fig, height=260, title=dict(
        text="Bilateral Asymmetry  (+ = Left dominant, − = Right dominant)",
        font=dict(size=13),
    ))


def risk_score_sparkline(scores: list, title: str = "Risk Over Steps") -> go.Figure:
    """Animated line with gradient fill."""
    x = list(range(len(scores)))
    fig = go.Figure()
    # coloured zones
    fig.add_hrect(y0=0,  y1=30, fillcolor="rgba(67,160,71,0.08)",  line_width=0)
    fig.add_hrect(y0=30, y1=60, fillcolor="rgba(251,140,0,0.08)",  line_width=0)
    fig.add_hrect(y0=60, y1=100,fillcolor="rgba(229,57,53,0.08)",  line_width=0)
    fig.add_hline(y=30, line_dash="dash", line_color=C["monitor"],
                  annotation_text="MONITOR", annotation_position="right",
                  annotation_font_color=C["monitor"])
    fig.add_hline(y=60, line_dash="dash", line_color=C["alert"],
                  annotation_text="ALERT", annotation_position="right",
                  annotation_font_color=C["alert"])
    fig.add_trace(go.Scatter(
        x=x, y=scores,
        mode="lines",
        fill="tozeroy",
        fillcolor="rgba(21,101,192,0.15)",
        line=dict(color=C["accent"], width=2.5, shape="spline"),
        hovertemplate="Step %{x}<br>Risk: %{y:.1f}<extra></extra>",
    ))
    return _chart_layout(fig, height=240, title=dict(text=title, font=dict(size=13)),
                         margin=(40, 30, 40, 80))


def plantar_heatmap(left_map: np.ndarray, right_map: np.ndarray) -> go.Figure:
    fig  = make_subplots(rows=1, cols=2,
                         subplot_titles=("Left Foot", "Right Foot"),
                         horizontal_spacing=0.08)
    vmax = max(left_map.max(), right_map.max(), 1)
    for ci, data in enumerate([left_map, right_map], start=1):
        fig.add_trace(
            go.Heatmap(z=data, colorscale="plasma", zmin=0, zmax=vmax,
                       showscale=(ci == 2),
                       colorbar=dict(title="kPa", x=1.02, len=0.9) if ci == 2 else None),
            row=1, col=ci,
        )
        for yp in [14, 34, 54]:
            fig.add_hline(y=yp + 0.5, line_color="white", line_width=1,
                          line_dash="dot", row=1, col=ci)
    fig.update_layout(height=360, margin=dict(t=40, b=20, l=20, r=60),
                      paper_bgcolor="rgba(0,0,0,0)", font_color="white")
    fig.update_yaxes(title_text="Toe (0) → Heel", row=1, col=1)
    return fig


def cop_trajectory(arr: np.ndarray, side: str) -> go.Figure:
    _R = np.arange(75, dtype=float)
    _C = np.arange(40, dtype=float)
    pf = arr.sum(axis=(1, 2))
    am = pf > 0
    if am.sum() < 2:
        return go.Figure()
    aa, at = arr[am], pf[am]
    cr = (aa * _R[:, None]).sum(axis=(1, 2)) / at * 0.5
    cc = (aa * _C[None, :]).sum(axis=(1, 2)) / at * 0.5
    n  = len(cr)
    fig = go.Figure()
    bg = arr.mean(axis=0)
    fig.add_trace(go.Heatmap(z=bg, colorscale="Greys", showscale=False,
                              x=np.arange(40)*0.5, y=np.arange(75)*0.5,
                              opacity=0.5))
    fig.add_trace(go.Scatter(
        x=cc, y=cr, mode="lines+markers",
        line=dict(color="cyan", width=2.5, shape="spline"),
        marker=dict(color=list(range(n)), colorscale="plasma",
                    size=5, showscale=False), name="CoP path",
        hovertemplate="Lat: %{x:.1f} cm<br>Lon: %{y:.1f} cm<extra></extra>",
    ))
    fig.add_trace(go.Scatter(x=[cc[0]], y=[cr[0]], mode="markers",
                              marker=dict(color="lime", size=13, symbol="circle"),
                              name="Heel strike"))
    fig.add_trace(go.Scatter(x=[cc[-1]], y=[cr[-1]], mode="markers",
                              marker=dict(color="red", size=13, symbol="triangle-up"),
                              name="Toe-off"))
    fig.update_layout(
        title=f"CoP Trajectory — {side}",
        xaxis_title="Lateral (cm)", yaxis_title="Toe→Heel (cm)",
        height=320, margin=dict(t=40, b=30, l=40, r=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="white", legend=dict(orientation="h", y=-0.18),
    )
    fig.update_xaxes(gridcolor="#252b3b")
    fig.update_yaxes(gridcolor="#252b3b")
    return fig


def time_series(df: pd.DataFrame, col: str, title: str, unit: str = "") -> go.Figure:
    fig = go.Figure()
    for side, color in [("Left", C["left"]), ("Right", C["right"])]:
        sd = df[df["side"] == side].sort_values("footstep_id")
        if sd.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sd["footstep_id"], y=sd[col],
            mode="lines+markers", name=side,
            line=dict(color=color, width=2, shape="spline"),
            marker=dict(size=4),
            hovertemplate=f"Step %{{x}}<br>{col}: %{{y:.2f}} {unit}<extra>{side}</extra>",
        ))
    return _chart_layout(fig, height=260,
                         title=dict(text=title, font=dict(size=13)),
                         margin=(40, 30, 40, 20))


def _risk_factor_rows(rr: RiskResult):
    for f in rr.factors:
        icon  = "⚠️" if f.triggered else "✅"
        color = C["alert"] if f.triggered else C["normal"]
        c1, c2 = st.columns([5, 1])
        c1.markdown(
            f'<div class="factor-row">'
            f'<span style="color:{color};font-size:15px">{icon} <b>{f.label}</b></span><br>'
            f'<span style="color:#888;font-size:12px">{f.detail}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        c2.markdown(
            f'<div style="text-align:right;color:{color};font-size:1.3rem;'
            f'font-weight:bold;padding-top:8px">+{f.sub_score:.0f}</div>',
            unsafe_allow_html=True,
        )


# ═════════════════════════════════════════════════════════════════════════════
#  Shared page header
# ═════════════════════════════════════════════════════════════════════════════

def _header(subtitle: str):
    st.markdown(
        f'<div class="ss-header">'
        f'<h1>SOLESENSE</h1>'
        f'<p>{subtitle}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ═════════════════════════════════════════════════════════════════════════════
#  Data loader — cached
# ═════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner="Loading dataset features…")
def _load_features() -> pd.DataFrame:
    csv = os.path.join(PROJECT_ROOT, "data", "features", "features.csv")
    if not os.path.exists(csv):
        return pd.DataFrame()
    return score_features_df(pd.read_csv(csv))


# ═════════════════════════════════════════════════════════════════════════════
#  PAGE 1 — Quick Analysis  (live, no dataset required)
# ═════════════════════════════════════════════════════════════════════════════

def page_quick_analysis():
    _header("Quick Analysis &nbsp;|&nbsp; Enter sensor values for an instant risk result")

    st.markdown(
        '<div style="background:#0D1B2A;border:1px solid #1565C0;border-radius:10px;'
        'padding:12px 18px;margin-bottom:18px;">'
        '<b style="color:#42A5F5">How to use</b> &nbsp;'
        '<span style="color:#90CAF9;font-size:0.88rem">'
        'Adjust any slider or number input — the dashboard updates <b>live</b> '
        'without needing to click a button. All charts respond instantly.'
        '</span></div>',
        unsafe_allow_html=True,
    )

    # ── sidebar controls (live — no form needed) ──────────────────────────────
    with st.sidebar:
        st.markdown("## 🎛 Sensor Inputs")
        st.markdown("*All charts update live as you change values.*")
        st.markdown('<span class="live-badge">LIVE</span>', unsafe_allow_html=True)
        st.markdown("---")

        st.markdown("#### 🦶 Left Foot")
        lf_peak = st.slider("Peak Pressure (kPa)",  0, 800, 250, 5,  key="ql_pk")
        lf_mean = st.slider("Mean Pressure (kPa)",  0, 300,  60, 2,  key="ql_mn")
        lf_pti  = st.slider("PTI (kPa·s)",          0, 80000, 18000, 500, key="ql_pti")
        lf_ff   = st.slider("Forefoot %",           0, 100,   42, 1,  key="ql_ff")
        lf_rf   = st.slider("Rearfoot %",           0, 100,   35, 1,  key="ql_rf")
        lf_mf   = st.slider("Midfoot %",            0, 100,   20, 1,  key="ql_mf")
        lf_toe  = max(0, 100 - lf_ff - lf_rf - lf_mf)

        st.markdown("#### 🦶 Right Foot")
        rf_peak = st.slider("Peak Pressure (kPa)",  0, 800, 230, 5,  key="qr_pk")
        rf_mean = st.slider("Mean Pressure (kPa)",  0, 300,  55, 2,  key="qr_mn")
        rf_pti  = st.slider("PTI (kPa·s)",          0, 80000, 17000, 500, key="qr_pti")
        rf_ff   = st.slider("Forefoot %",           0, 100,   38, 1,  key="qr_ff")
        rf_rf   = st.slider("Rearfoot %",           0, 100,   40, 1,  key="qr_rf")
        rf_mf   = st.slider("Midfoot %",            0, 100,   18, 1,  key="qr_mf")
        rf_toe  = max(0, 100 - rf_ff - rf_rf - rf_mf)

        st.markdown("#### 🚶 Gait")
        stance_l = st.slider("Left Stance (s)",   0.10, 2.0, 0.72, 0.01, key="q_stl")
        stance_r = st.slider("Right Stance (s)",  0.10, 2.0, 0.70, 0.01, key="q_str")
        step_std = st.slider("Step Time Std (s)", 0.00, 0.5, 0.04, 0.005,key="q_sts")
        cadence  = st.slider("Cadence (steps/min)", 40, 160, 109, 1,     key="q_cad")
        gait_sym = st.slider("Gait Symmetry Idx", 0.00, 0.5, 0.05, 0.01, key="q_gsym")
        cop_l    = st.slider("Left CoP Path (cm)",  0.0, 30.0, 12.5, 0.5, key="q_copl")
        cop_r    = st.slider("Right CoP Path (cm)", 0.0, 30.0, 11.8, 0.5, key="q_copr")

        st.markdown("#### 🔁 Persistence")
        pers_pti  = st.slider("Pressure Persistence",  0.0, 1.0, 0.2, 0.05, key="q_pp")
        pers_asym = st.slider("Asymmetry Persistence", 0.0, 1.0, 0.1, 0.05, key="q_pa")

        st.markdown(
            '<div class="disc">⚠ EXPERIMENTAL — Not for clinical use.</div>',
            unsafe_allow_html=True,
        )

    # ── compute risk live ─────────────────────────────────────────────────────
    def nsi(L, R):
        d = (L + R) / 2
        return abs(L - R) / d * 100 if d > 0 else 0.0

    row = pd.Series({
        "subject_id": "LIVE", "footwear": "INPUT", "trial": "MANUAL",
        "press_max_kpa":               max(lf_peak, rf_peak),
        "press_mean_kpa":              (lf_mean + rf_mean) / 2,
        "pti_total_kpa_s":             max(lf_pti, rf_pti),
        "asym_pti_total_kpa_s":        nsi(lf_pti, rf_pti),
        "asym_dir_pti_total_kpa_s":    lf_pti - rf_pti,
        "asym_press_mean_kpa":         nsi(lf_mean, rf_mean),
        "load_frac_forefoot":          (lf_ff + rf_ff) / 200,
        "load_frac_rearfoot":          (lf_rf + rf_rf) / 200,
        "asym_load_forefoot":          nsi(lf_ff / 100, rf_ff / 100),
        "step_time_std_s":             step_std,
        "gait_symmetry_index":         gait_sym,
        "persistence_pti_total_kpa_s": pers_pti,
        "left_loading_fraction":       lf_pti / (lf_pti + rf_pti + 1e-9),
        "right_loading_fraction":      rf_pti / (lf_pti + rf_pti + 1e-9),
        "cop_path_length_cm":          (cop_l + cop_r) / 2,
        "asym_cop_path_length_cm":     nsi(cop_l, cop_r),
        "stance_time_s":               (stance_l + stance_r) / 2,
        "asym_stance_time":            nsi(stance_l, stance_r),
    })

    rr = compute_risk(row)
    lc = LEVEL_COLOR[rr.risk_level]

    # ── risk banner ───────────────────────────────────────────────────────────
    st.markdown(
        f'<div class="rbox" style="background:#0D1B2A;border:3px solid {lc};">'
        f'<h1 style="color:{lc};margin:0;font-size:2.4rem">'
        f'{LEVEL_EMOJI[rr.risk_level]}  {rr.risk_level}</h1>'
        f'<p style="color:white;font-size:1.2rem;margin:6px 0 2px 0">'
        f'SoleSense Risk Indicator: '
        f'<b style="color:{lc};font-size:2rem">{rr.risk_score:.1f}</b>/100</p>'
        f'<p style="color:#90CAF9;margin:0">Most affected: '
        f'{rr.affected_region.replace("_"," ")}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── top metric cards ──────────────────────────────────────────────────────
    m1,m2,m3,m4,m5,m6 = st.columns(6)
    for col, lbl, val, color in [
        (m1, "Left Peak",   f"{lf_peak} kPa",    C["left"]),
        (m2, "Right Peak",  f"{rf_peak} kPa",    C["right"]),
        (m3, "Left PTI",    f"{lf_pti:,} kPa·s", C["left"]),
        (m4, "Right PTI",   f"{rf_pti:,} kPa·s", C["right"]),
        (m5, "Cadence",     f"{cadence}/min",     C["neutral"]),
        (m6, "Gait Sym.",   f"{gait_sym:.3f}",    C["neutral"]),
    ]:
        col.markdown(
            f'<div class="hwc"><h4>{lbl}</h4>'
            f'<p style="color:{color}">{val}</p></div>',
            unsafe_allow_html=True,
        )

    st.markdown("")

    # ── Row 1: gauge + bilateral bars ─────────────────────────────────────────
    st.markdown('<div class="sh">① Risk & Bilateral Pressure</div>',
                unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.plotly_chart(gauge(rr.risk_score, "Risk Indicator"), use_container_width=True)
    with c2:
        st.plotly_chart(bar_lr(lf_pti, rf_pti, "PTI", " kPa·s"), use_container_width=True)
    with c3:
        st.plotly_chart(bar_lr(lf_peak, rf_peak, "Peak Pressure", " kPa"),
                        use_container_width=True)
    with c4:
        st.plotly_chart(bar_lr(stance_l, stance_r, "Stance Time", " s"),
                        use_container_width=True)

    # ── Row 2: Radar + Donuts ─────────────────────────────────────────────────
    st.markdown('<div class="sh">② Regional Loading — Desmos View</div>',
                unsafe_allow_html=True)
    r2c1, r2c2 = st.columns([1, 1])
    with r2c1:
        max_v = max(lf_peak, rf_peak, lf_pti/500, rf_pti/500, 1)
        st.plotly_chart(radar_chart(
            categories=["Peak Pressure", "Mean Pressure", "PTI (scaled)",
                        "Forefoot Load", "Rearfoot Load", "CoP Path"],
            left_vals=[lf_peak, lf_mean, lf_pti/500, lf_ff, lf_rf, cop_l],
            right_vals=[rf_peak, rf_mean, rf_pti/500, rf_ff, rf_rf, cop_r],
            title="Bilateral Polar Comparison",
        ), use_container_width=True)
    with r2c2:
        st.plotly_chart(donut_regional(
            left_vals=[lf_toe, lf_ff, lf_mf, lf_rf],
            right_vals=[rf_toe, rf_ff, rf_mf, rf_rf],
        ), use_container_width=True)

    # ── Row 3: Asymmetry waterfall ────────────────────────────────────────────
    st.markdown('<div class="sh">③ Asymmetry Profile</div>', unsafe_allow_html=True)
    asym_names  = ["PTI", "Peak P.", "Forefoot", "Rearfoot", "Stance", "CoP Path"]
    asym_signed = [
        (lf_pti  - rf_pti)  / ((lf_pti  + rf_pti)  / 2 + 1e-9) * 100,
        (lf_peak - rf_peak) / ((lf_peak + rf_peak) / 2 + 1e-9) * 100,
        (lf_ff   - rf_ff)   / ((lf_ff   + rf_ff)   / 2 + 1e-9) * 100,
        (lf_rf   - rf_rf)   / ((lf_rf   + rf_rf)   / 2 + 1e-9) * 100,
        (stance_l - stance_r)/ ((stance_l+stance_r) / 2 + 1e-9) * 100,
        (cop_l   - cop_r)   / ((cop_l   + cop_r)   / 2 + 1e-9) * 100,
    ]
    st.plotly_chart(asymmetry_waterfall(asym_names, asym_signed), use_container_width=True)

    # ── Row 4: Explainable risk ───────────────────────────────────────────────
    st.markdown('<div class="sh">④ Explainable Risk Breakdown</div>', unsafe_allow_html=True)
    st.markdown(
        f'**Why is the indicator <span style="color:{lc}">{rr.risk_level}</span>?**',
        unsafe_allow_html=True,
    )
    if not rr.contributing_factors:
        st.success("✅ No risk factors triggered. All values within normal range.")
    else:
        st.markdown(f"**{len(rr.contributing_factors)} factor(s) contributing to the score:**")
    _risk_factor_rows(rr)

    st.markdown(
        f'<div style="background:#1A1F2E;border-left:4px solid {lc};'
        f'border-radius:6px;padding:14px 18px;color:#ddd;margin-top:16px">'
        f'💡 <b>Recommended Action:</b><br>{rr.recommended_action}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="disc">⚠ EXPERIMENTAL PROTOTYPE — Not for clinical use. '
        'SoleSense does not diagnose any medical condition. '
        'All thresholds are demo values only.</div>',
        unsafe_allow_html=True,
    )


# ═════════════════════════════════════════════════════════════════════════════
#  PAGE 2 — Dataset Explorer  (static features.csv)
# ═════════════════════════════════════════════════════════════════════════════

def page_dataset_explorer():
    _header("Dataset Explorer &nbsp;|&nbsp; StepUP-P150 · 150 Subjects · 100 Hz")

    df = _load_features()

    if df.empty:
        st.error(
            "**features.csv not found.**  "
            "Run the feature pipeline first:\n\n"
            "```\ncd f:/Dataset/SoleSense\n"
            "python -m src.feature_pipeline --subjects 5 --trials W1\n```"
        )
        st.markdown(
            '<div style="background:#0D1B2A;border:1px solid #1565C0;'
            'border-radius:10px;padding:18px 22px;margin-top:16px">'
            '<b style="color:#42A5F5;font-size:1rem">📋 Dataset Summary</b><br><br>'
            '<span style="color:#90CAF9">The StepUP-P150 dataset contains:<br>'
            '• 150 subjects<br>'
            '• 4 footwear conditions (BF, ST, P1, P2)<br>'
            '• 7 trial types per footwear (W1–W4 walking, S1–S3 balance)<br>'
            '• High-resolution plantar pressure at 100 Hz<br>'
            '• 75×40 px per footstep frame<br>'
            '• Left/right annotated footsteps'
            '</span></div>',
            unsafe_allow_html=True,
        )
        return

    # ── sidebar filters ───────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## 🎛 Session Filters")
        subject  = st.selectbox("Subject ID",    sorted(df["subject_id"].unique()))
        sub_df   = df[df["subject_id"] == subject]
        footwear = st.selectbox("Footwear",      sorted(sub_df["footwear"].unique()))
        fw_df    = sub_df[sub_df["footwear"] == footwear]
        trial    = st.selectbox("Trial / Speed", sorted(fw_df["trial"].unique()))
        st.divider()
        st.markdown(
            f"**Subjects:** {df['subject_id'].nunique()}  \n"
            f"**Steps loaded:** {len(df):,}  \n"
            f"**Sensor:** StepUP-P150 · 100 Hz"
        )
        st.divider()
        st.markdown('<div class="disc">⚠ EXPERIMENTAL.</div>', unsafe_allow_html=True)

    trial_df = fw_df[fw_df["trial"] == trial].copy()

    # ── § 1 Overall Status ────────────────────────────────────────────────────
    st.markdown('<div class="sh">① Overall Status</div>', unsafe_allow_html=True)
    if trial_df.empty:
        st.warning("No data for this selection.")
        return

    rep = trial_df.sort_values("risk_score", ascending=False).iloc[0]
    rr  = compute_risk(rep)
    lc  = LEVEL_COLOR[rr.risk_level]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.plotly_chart(gauge(rr.risk_score, "Risk Indicator"), use_container_width=True)
    with c2:
        st.markdown(
            f'<div class="mc"><h4>Risk Level</h4>'
            f'<p style="color:{lc}">{LEVEL_EMOJI[rr.risk_level]} {rr.risk_level}</p></div>'
            f'<div class="mc"><h4>Affected Region</h4>'
            f'<p style="color:#90CAF9;font-size:1rem">'
            f'{rr.affected_region.replace("_"," ")}</p></div>',
            unsafe_allow_html=True,
        )
    with c3:
        n = len(rr.contributing_factors)
        st.markdown(
            f'<div class="mc"><h4>Factors</h4>'
            f'<p style="color:{C["monitor"] if n>0 else C["normal"]}">{n}</p></div>'
            f'<div class="mc"><h4>Steps Analysed</h4>'
            f'<p>{len(trial_df):,}</p></div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="mc"><h4>Session</h4>'
            f'<p style="font-size:0.9rem">S{subject} · {footwear} · {trial}</p></div>'
            f'<div class="mc"><h4>Mean Risk</h4>'
            f'<p style="color:{lc}">{trial_df["risk_score"].mean():.1f}</p></div>',
            unsafe_allow_html=True,
        )

    # risk sparkline over steps
    if "risk_score" in trial_df.columns and len(trial_df) > 1:
        scores = trial_df.sort_values("footstep_id")["risk_score"].tolist()
        st.plotly_chart(risk_score_sparkline(scores, "Risk Score — Step by Step"),
                        use_container_width=True)

    # ── § 2 Foot Pressure ────────────────────────────────────────────────────
    st.markdown('<div class="sh">② Foot Pressure</div>', unsafe_allow_html=True)
    ldf = trial_df[trial_df["side"] == "Left"]
    rdf = trial_df[trial_df["side"] == "Right"]

    def sm(ds, col):
        return float(ds[col].mean()) if not ds.empty and col in ds else 0.0

    p1, p2, p3, p4 = st.columns(4)
    with p1:
        st.markdown(
            f'<div class="mc"><h4>Left Mean</h4>'
            f'<p style="color:{C["left"]}">{sm(ldf,"press_mean_kpa"):.1f} kPa</p></div>'
            f'<div class="mc"><h4>Left Peak</h4>'
            f'<p style="color:{C["left"]}">{sm(ldf,"press_max_kpa"):.1f} kPa</p></div>',
            unsafe_allow_html=True,
        )
    with p2:
        st.markdown(
            f'<div class="mc"><h4>Right Mean</h4>'
            f'<p style="color:{C["right"]}">{sm(rdf,"press_mean_kpa"):.1f} kPa</p></div>'
            f'<div class="mc"><h4>Right Peak</h4>'
            f'<p style="color:{C["right"]}">{sm(rdf,"press_max_kpa"):.1f} kPa</p></div>',
            unsafe_allow_html=True,
        )
    with p3:
        st.markdown(
            f'<div class="mc"><h4>Left PTI</h4>'
            f'<p style="color:{C["left"]}">{sm(ldf,"pti_total_kpa_s"):.0f}</p></div>'
            f'<div class="mc"><h4>Right PTI</h4>'
            f'<p style="color:{C["right"]}">{sm(rdf,"pti_total_kpa_s"):.0f}</p></div>',
            unsafe_allow_html=True,
        )
    with p4:
        st.markdown(
            f'<div class="mc"><h4>Load Rate L</h4>'
            f'<p>{sm(ldf,"loading_rate_kpa_s"):.0f} kPa/s</p></div>'
            f'<div class="mc"><h4>Load Rate R</h4>'
            f'<p>{sm(rdf,"loading_rate_kpa_s"):.0f} kPa/s</p></div>',
            unsafe_allow_html=True,
        )

    # Regional donut
    reg_cols = ["load_frac_toe","load_frac_forefoot","load_frac_midfoot","load_frac_rearfoot"]
    lv_reg = [sm(ldf, c)*100 for c in reg_cols]
    rv_reg = [sm(rdf, c)*100 for c in reg_cols]
    dc1, dc2 = st.columns(2)
    with dc1:
        st.plotly_chart(donut_regional(lv_reg, rv_reg), use_container_width=True)
    with dc2:
        # grouped bar for regions
        reg_labels = ["Toe","Forefoot","Midfoot","Rearfoot"]
        fig_reg = go.Figure()
        for side, vals, color in [("Left", lv_reg, C["left"]), ("Right", rv_reg, C["right"])]:
            fig_reg.add_trace(go.Bar(
                name=side, x=reg_labels, y=vals,
                marker_color=color, opacity=0.85,
                text=[f"{v:.1f}%" for v in vals], textposition="auto",
            ))
        _chart_layout(fig_reg, height=280,
                      title=dict(text="Regional Load Distribution", font=dict(size=13)),
                      margin=(40,30,40,20))
        fig_reg.update_layout(barmode="group",
                               yaxis_title="Load %",
                               legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_reg, use_container_width=True)

    # ── § 3 Bilateral Comparison ─────────────────────────────────────────────
    st.markdown('<div class="sh">③ Left ↔ Right Comparison</div>', unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    with b1:
        st.plotly_chart(bar_lr(sm(ldf,"pti_total_kpa_s"), sm(rdf,"pti_total_kpa_s"),
                               "PTI","kPa·s"), use_container_width=True)
    with b2:
        st.plotly_chart(bar_lr(sm(ldf,"press_max_kpa"), sm(rdf,"press_max_kpa"),
                               "Peak Pressure","kPa"), use_container_width=True)
    with b3:
        st.plotly_chart(bar_lr(sm(ldf,"stance_time_s"), sm(rdf,"stance_time_s"),
                               "Stance Time","s"), use_container_width=True)

    # Radar
    def sv(col):
        return (sm(ldf, col), sm(rdf, col))
    l_pti, r_pti = sv("pti_total_kpa_s")
    l_pk,  r_pk  = sv("press_max_kpa")
    l_st,  r_st  = sv("stance_time_s")
    l_cop, r_cop = sv("cop_path_length_cm") if "cop_path_length_cm" in trial_df else (0,0)
    l_ff = sm(ldf, "load_frac_forefoot")*100
    r_ff = sm(rdf, "load_frac_forefoot")*100

    rc1, rc2 = st.columns([1,1])
    with rc1:
        st.plotly_chart(radar_chart(
            categories=["PTI (scaled)","Peak P.","Stance","CoP Path","Forefoot"],
            left_vals=[l_pti/500, l_pk, l_st*100, l_cop, l_ff],
            right_vals=[r_pti/500, r_pk, r_st*100, r_cop, r_ff],
            title="Bilateral Polar View",
        ), use_container_width=True)
    with rc2:
        # signed asymmetry waterfall
        row0 = trial_df.iloc[0]
        def ga(k): return float(row0.get(k, 0) or 0)
        asym_n = ["PTI","Peak P.","Forefoot","Stance","CoP"]
        asym_v = [
            (l_pti-r_pti)/((l_pti+r_pti)/2+1e-9)*100,
            (l_pk-r_pk)/((l_pk+r_pk)/2+1e-9)*100,
            (l_ff-r_ff)/((l_ff+r_ff)/2+1e-9)*100,
            (l_st-r_st)/((l_st+r_st)/2+1e-9)*100,
            (l_cop-r_cop)/((l_cop+r_cop)/2+1e-9)*100,
        ]
        st.plotly_chart(asymmetry_waterfall(asym_n, asym_v), use_container_width=True)

    # ── § 4 Temperature (hardware roadmap) ───────────────────────────────────
    st.markdown('<div class="sh">④ Temperature</div>', unsafe_allow_html=True)
    s = temperature_hardware_status()
    st.markdown(
        '<div style="background:#1A1F2E;border:1px solid #2A3050;'
        'border-radius:10px;padding:18px;">'
        '<h3 style="color:#FF9800;margin-top:0">🔬 Hardware Roadmap</h3>'
        f'<p style="color:#ccc">{s["description"]}</p>'
        f'<p style="color:#aaa;font-size:0.9rem">'
        f'<b>Planned:</b> {s["planned_sensors"]} · {s["planned_feature"]}</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── § 5 Gait ─────────────────────────────────────────────────────────────
    st.markdown('<div class="sh">⑤ Gait Metrics</div>', unsafe_allow_html=True)
    row0 = trial_df.iloc[0]
    gait_metrics = {
        "Cadence":     (row0.get("cadence_steps_per_min", 0),     "steps/min"),
        "Step Time":   (row0.get("step_time_mean_s", 0),          "s"),
        "Step CV":     (row0.get("step_time_cv", 0),              "—"),
        "Stance":      (row0.get("stance_mean_s", 0),             "s"),
        "Gait Sym.":   (row0.get("gait_symmetry_index", 0),       "—"),
        "Stride L":    (row0.get("stride_time_left_mean_s", 0),   "s"),
        "Stride R":    (row0.get("stride_time_right_mean_s", 0),  "s"),
        "Variability": (row0.get("gait_temporal_variability", 0), "—"),
    }
    gcols = st.columns(4)
    for i, (lbl, (val, unit)) in enumerate(gait_metrics.items()):
        vs    = f"{val:.3f}" if isinstance(val, float) and val < 10 else f"{val:.1f}"
        color = C["neutral"]
        if lbl == "Gait Sym." and val > 0.1:  color = C["monitor"]
        if lbl == "Step CV"   and val > 0.15: color = C["monitor"]
        gcols[i % 4].markdown(
            f'<div class="mc"><h4>{lbl}</h4>'
            f'<p style="color:{color}">{vs} '
            f'<span style="font-size:0.75rem;color:#888">{unit}</span></p></div>',
            unsafe_allow_html=True,
        )
    st.plotly_chart(time_series(trial_df, "stance_time_s", "Stance Time per Step", "s"),
                    use_container_width=True)

    # ── § 6 Pressure Map & CoP ────────────────────────────────────────────────
    st.markdown('<div class="sh">⑥ Pressure Map & CoP Trajectory</div>',
                unsafe_allow_html=True)
    try:
        from src.data_loader import load_walking_trial
        subj    = str(trial_df["subject_id"].iloc[0]).zfill(3)
        raw     = load_walking_trial(subj, footwear, trial,
                                     include_pressure_arrays=True,
                                     dataset_root=os.path.join(
                                         PROJECT_ROOT, "..",
                                         "FRDR_dataset_1280_download_590_202609031103"))
        if raw is not None and not raw.empty:
            raw = raw[raw["exclude"] == 0].reset_index(drop=True)
            lmaps, rmaps, larr, rarr = [], [], None, None
            for _, r in raw.iterrows():
                arr = r.get("pressure_array")
                if arr is None:
                    continue
                if r["side"] == "Left":
                    lmaps.append(arr.mean(axis=0))
                    if larr is None:
                        larr = arr
                else:
                    rmaps.append(arr.mean(axis=0))
                    if rarr is None:
                        rarr = arr
            lavg = np.mean(lmaps, axis=0) if lmaps else np.zeros((75, 40))
            ravg = np.mean(rmaps, axis=0) if rmaps else np.zeros((75, 40))
            hc1, hc2 = st.columns(2)
            with hc1:
                st.plotly_chart(plantar_heatmap(lavg, ravg), use_container_width=True)
            with hc2:
                cc1, cc2 = st.columns(2)
                with cc1:
                    if larr is not None:
                        st.plotly_chart(cop_trajectory(larr, "Left"),
                                        use_container_width=True)
                with cc2:
                    if rarr is not None:
                        st.plotly_chart(cop_trajectory(rarr, "Right"),
                                        use_container_width=True)
        else:
            st.info("Raw pressure arrays not available for this trial.")
    except Exception as e:
        st.info(f"Pressure map unavailable: {e}")

    # ── § 7 Explainable Risk ──────────────────────────────────────────────────
    st.markdown('<div class="sh">⑦ Explainable Risk</div>', unsafe_allow_html=True)
    st.markdown(
        f'**Why is the indicator <span style="color:{lc}">{rr.risk_level}</span>?**',
        unsafe_allow_html=True,
    )
    if not rr.contributing_factors:
        st.success("No risk factors triggered.")
    _risk_factor_rows(rr)
    st.markdown(
        f'<div style="background:#1A1F2E;border-left:4px solid {lc};'
        f'border-radius:6px;padding:12px 16px;color:#ddd;margin-top:12px">'
        f'💡 <b>Recommended Action:</b> {rr.recommended_action}</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="disc">⚠ EXPERIMENTAL — not clinically validated.</div>',
                unsafe_allow_html=True)

    # ── § 8 Historical Trend ──────────────────────────────────────────────────
    st.markdown('<div class="sh">⑧ Historical Trend</div>', unsafe_allow_html=True)
    sub_df  = df[df["subject_id"] == subject]
    summary = score_trial_summary(sub_df)

    tab1, tab2 = st.tabs(["📈 Risk Score Trend", "📉 Feature Trends"])
    with tab1:
        fig_t = go.Figure()
        for fw_name, color in zip(["BF","ST","P1","P2"],
                                  ["#2196F3","#4CAF50","#FF9800","#E91E63"]):
            fd = summary[summary["footwear"] == fw_name].sort_values("trial")
            if fd.empty:
                continue
            fig_t.add_trace(go.Scatter(
                x=fd["trial"], y=fd["risk_score_max"],
                mode="lines+markers", name=fw_name,
                line=dict(color=color, width=2, shape="spline"),
                marker=dict(size=9, symbol="circle"),
                hovertemplate="Trial: %{x}<br>Max Risk: %{y:.1f}<extra>" + fw_name + "</extra>",
            ))
        fig_t.add_hrect(y0=0,  y1=30, fillcolor="rgba(67,160,71,0.07)",  line_width=0)
        fig_t.add_hrect(y0=30, y1=60, fillcolor="rgba(251,140,0,0.07)",  line_width=0)
        fig_t.add_hrect(y0=60, y1=100,fillcolor="rgba(229,57,53,0.07)",  line_width=0)
        fig_t.add_hline(y=30, line_dash="dash", line_color=C["monitor"],
                        annotation_text="MONITOR", annotation_font_color=C["monitor"])
        fig_t.add_hline(y=60, line_dash="dash", line_color=C["alert"],
                        annotation_text="ALERT",   annotation_font_color=C["alert"])
        _chart_layout(fig_t, height=320,
                      title=dict(text=f"Subject {subject} — Risk Trend by Trial",
                                 font=dict(size=13)),
                      margin=(40,40,40,80))
        fig_t.update_layout(yaxis=dict(range=[0,100]),
                             legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_t, use_container_width=True)

    with tab2:
        feat_opts = {
            "Peak Pressure":     "press_max_kpa",
            "PTI":               "pti_total_kpa_s",
            "Asymmetry (PTI)":   "asym_pti_total_kpa_s",
            "Stance Time":       "stance_time_s",
            "CoP Path":          "cop_path_length_cm",
            "Gait Symmetry":     "gait_symmetry_index",
        }
        sel  = st.selectbox("Select feature", list(feat_opts.keys()))
        fcol = feat_opts[sel]
        if fcol in sub_df.columns:
            td   = sub_df.groupby(["footwear","trial"])[fcol].mean().reset_index()
            fig2 = px.line(td, x="trial", y=fcol, color="footwear", markers=True,
                           color_discrete_sequence=["#2196F3","#4CAF50","#FF9800","#E91E63"])
            _chart_layout(fig2, height=300, margin=(40,40,40,20))
            fig2.update_layout(legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info(f"Feature '{fcol}' not in dataset.")


# ═════════════════════════════════════════════════════════════════════════════
#  Navigation & entry point
# ═════════════════════════════════════════════════════════════════════════════

def main():
    _css()

    # ── top navigation ────────────────────────────────────────────────────────
    nav_options = ["🏠 Quick Analysis", "📊 Dataset Explorer"]
    selected    = st.radio(
        "Navigate",
        nav_options,
        horizontal=True,
        label_visibility="collapsed",
    )
    st.markdown("<hr style='border-color:#1e2330;margin:0 0 6px 0'>", unsafe_allow_html=True)

    if selected == "🏠 Quick Analysis":
        page_quick_analysis()
    else:
        page_dataset_explorer()

    st.markdown(
        '<div class="footer">SoleSense · Research Prototype · Not a medical device · '
        'StepUP-P150 Dataset · University of New Brunswick 2023–2024</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__" or True:
    main()
