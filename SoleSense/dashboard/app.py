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
/* ── global ──────────────────────────────────────────────────────────────── */
.stApp { background-color:#0E1117; color:#E0E0E0; }
.block-container { padding-top:1rem; }

/* ── hide default Streamlit top decoration bar ───────────────────────────── */
header[data-testid="stHeader"] { display:none !important; }
#MainMenu { visibility:hidden; }
footer    { visibility:hidden; }

/* ── sidebar background & ALL text inside it ─────────────────────────────── */
[data-testid="stSidebar"] {
    background: #131722 !important;
}
[data-testid="stSidebar"] * {
    color: #D0D8F0 !important;
}
/* sidebar headings */
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4 {
    color: #FFFFFF !important;
}
/* sidebar markdown paragraphs / labels */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label {
    color: #C8D4F0 !important;
}
/* slider track + thumb labels */
[data-testid="stSidebar"] [data-testid="stSlider"] label,
[data-testid="stSidebar"] [data-testid="stNumberInput"] label {
    color: #90CAF9 !important;
    font-size: 0.82rem !important;
}
/* selectbox label */
[data-testid="stSidebar"] [data-testid="stSelectbox"] label {
    color: #90CAF9 !important;
}
/* divider line */
[data-testid="stSidebar"] hr { border-color: #2A3050 !important; }

/* ── sidebar nav radio buttons ───────────────────────────────────────────── */
[data-testid="stSidebar"] div[role="radiogroup"] {
    display: flex;
    flex-direction: column;
    gap: 6px;
}
[data-testid="stSidebar"] div[role="radiogroup"] label {
    background: #1E2538 !important;
    border: 1px solid #3A4568 !important;
    border-radius: 10px !important;
    padding: 10px 16px !important;
    color: #90CAF9 !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    cursor: pointer !important;
    transition: background 0.2s, border-color 0.2s !important;
    width: 100% !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
    background: #1565C0 !important;
    border-color: #42A5F5 !important;
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] label input {
    display: none !important;
}

/* ── main content text defaults ──────────────────────────────────────────── */
.stMarkdown, .stMarkdown p { color: #E0E0E0; }

/* ── header banner ───────────────────────────────────────────────────────── */
.ss-header {
    background: linear-gradient(135deg,#1565C0 0%,#0D47A1 50%,#01579B 100%);
    border-radius:14px; padding:22px 32px; margin-bottom:18px;
    box-shadow:0 4px 24px rgba(21,101,192,0.4);
}
.ss-header h1 {
    color:#FFFFFF !important; font-size:2.6rem; letter-spacing:5px;
    font-weight:900; margin:0;
}
.ss-header p { color:#90CAF9 !important; font-size:1rem; margin:4px 0 0 0; }

/* ── section headers (sh) ────────────────────────────────────────────────── */
.sh {
    color: #FFFFFF !important;
    font-size: 0.88rem;
    text-transform: uppercase;
    letter-spacing: 2px;
    font-weight: 800;
    border-left: 4px solid #42A5F5;
    border-bottom: 1px solid #2A3050;
    padding: 10px 0 10px 16px;
    margin: 28px 0 16px 0;
    background: linear-gradient(90deg, rgba(21,101,192,0.18) 0%, transparent 65%);
    border-radius: 0 8px 8px 0;
}

/* ── metric cards (mc) ───────────────────────────────────────────────────── */
.mc {
    background:#1A1F2E; border:1px solid #2A3050;
    border-radius:10px; padding:14px 18px; margin:5px 0;
}
.mc h4 {
    color:#90CAF9 !important; font-size:0.72rem; margin:0 0 5px 0;
    text-transform:uppercase; letter-spacing:1.5px;
}
.mc p { font-size:1.55rem; font-weight:700; margin:0; color:#E0E0E0; }

/* ── hardware / top metric cards (hwc) ───────────────────────────────────── */
.hwc {
    background:#0D1B2A; border:1px solid #1565C0;
    border-radius:10px; padding:12px 16px; margin:4px 0;
}
.hwc h4 {
    color:#42A5F5 !important; font-size:0.72rem; margin:0 0 4px 0;
    text-transform:uppercase; letter-spacing:1px;
}
.hwc p { font-size:1.35rem; font-weight:700; margin:0; color:#E3F2FD !important; }

/* ── result box ──────────────────────────────────────────────────────────── */
.rbox { border-radius:12px; padding:20px 26px; margin:14px 0; }

/* ── disclaimer ──────────────────────────────────────────────────────────── */
.disc {
    background:#1A1F2E; border-left:3px solid #FB8C00;
    padding:8px 14px; border-radius:4px;
    color:#FFB74D !important; font-size:0.78rem; margin-top:10px;
}

/* ── factor rows ─────────────────────────────────────────────────────────── */
.factor-row { padding:8px 0; border-bottom:1px solid #1e2330; }

/* ── input labels in main area ───────────────────────────────────────────── */
div[data-testid="stNumberInput"] label,
div[data-testid="stSlider"]      label { color:#90CAF9 !important; }

/* ── live badge ──────────────────────────────────────────────────────────── */
.live-badge {
    display:inline-block; background:#E53935; color:#FFFFFF !important;
    font-size:0.7rem; font-weight:700; padding:2px 8px;
    border-radius:10px; letter-spacing:1px; margin-left:8px;
    animation:pulse 1.5s infinite;
}
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }

/* ── footer ──────────────────────────────────────────────────────────────── */
.footer {
    text-align:center; color:#888 !important; font-size:0.75rem;
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

        # sort subjects numerically, display zero-padded
        raw_subjects = sorted(df["subject_id"].unique(),
                              key=lambda x: int(x) if str(x).isdigit() else x)
        subj_labels  = [str(s).zfill(3) if str(s).isdigit() else str(s) for s in raw_subjects]
        subj_idx     = st.selectbox("Subject ID", range(len(subj_labels)),
                                    format_func=lambda i: subj_labels[i])
        subject      = raw_subjects[subj_idx]

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
        subj_display = str(subject).zfill(3) if str(subject).isdigit() else str(subject)
        st.markdown(
            f'<div class="mc"><h4>Session</h4>'
            f'<p style="font-size:0.9rem">Sub {subj_display} · {footwear} · {trial}</p></div>'
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
    st.divider()
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
    st.divider()
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
#  PAGE 3 — Live Hardware  (ESP32-S3 Wi-Fi stream)
#  Single LEFT-foot prototype: FSR1=forefoot, FSR2=heel, TMP117, MPU6050
#  Anatomically correct: TOES/FOREFOOT = top, HEEL = bottom
#  Units: ADC counts (raw), proxy-kPa (labelled), °C, g
# ═════════════════════════════════════════════════════════════════════════════

# ── Session-level baseline state (persisted across reruns) ───────────────────
_BASELINE_KEY   = "hw_temp_baseline"
_LOAD_HIST_KEY  = "hw_load_history"
_RISK_HIST_KEY  = "hw_risk_history"
_HOTSPOT_KEY    = "hw_hotspot_state"

FSR_ADC_MAX_DISPLAY = 4095   # 12-bit
# Proxy scaling — label clearly as "proxy kPa (relative)"
_PROXY_SCALE    = 600.0   # ADC 4095 → 600 proxy-kPa
_PROXY_LABEL    = "proxy kPa (relative, uncalibrated)"
_PROXY_ABBR     = "p-kPa"


def _adc_to_proxy(adc: float) -> float:
    return (adc / FSR_ADC_MAX_DISPLAY) * _PROXY_SCALE


def _hw_foot_svg(forefoot: float, heel: float,
                 max_adc: float = FSR_ADC_MAX_DISPLAY) -> str:
    """
    Return an SVG of the anatomically correct LEFT foot outline.
    Toes/forefoot = TOP, heel = BOTTOM.
    One FSR dot per active sensor: FSR1 (forefoot, centred) and FSR2 (heel).
    forefoot, heel are ADC counts (0-4095).
    """
    def _colour(v):
        f = min(v / max(max_adc * 0.05, 1), 1.0)
        if f < 0.3:   return "#43A047", 0.55 + f * 1.2
        elif f < 0.6: return "#FB8C00", 0.65 + f * 0.8
        else:         return "#E53935", 0.75 + f * 0.5

    def _dot(cx, cy, val):
        col, op = _colour(val)
        r = 14 + int(val / max_adc * 22)
        pct = int(val / max_adc * 100)
        return (
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{col}" '
            f'opacity="{op:.2f}" stroke="white" stroke-width="1.5"/>'
            f'<text x="{cx}" y="{cy+4}" text-anchor="middle" '
            f'fill="white" font-size="11" font-weight="bold">{pct}%</text>'
        )

    foot_path = (
        "M 80 10 "
        "C 100 8, 118 18, 122 35 "
        "C 128 55, 130 75, 128 95 "
        "C 126 115, 124 135, 120 155 "
        "C 116 175, 114 195, 116 215 "
        "C 118 235, 112 258, 100 272 "
        "C 88 285, 70 290, 58 285 "
        "C 44 278, 36 260, 38 240 "
        "C 40 218, 42 198, 44 178 "
        "C 46 158, 44 138, 40 118 "
        "C 36 98, 30 78, 34 55 "
        "C 38 30, 54 14, 80 10 Z"
    )

    dots_html = ""
    # Single forefoot sensor (FSR1) — centred in the forefoot zone
    dots_html += _dot(80, 78, forefoot)
    # Midfoot — not connected
    dots_html += (
        '<circle cx="80" cy="162" r="12" fill="#2A3050" opacity="0.7" '
        'stroke="#444" stroke-width="1" stroke-dasharray="3,2"/>'
        '<text x="80" y="166" text-anchor="middle" fill="#555" '
        'font-size="9">N/C</text>'
    )
    # Single heel sensor (FSR2)
    dots_html += _dot(80, 260, heel)

    labels = (
        f'<text x="80" y="48" text-anchor="middle" fill="#90CAF9" '
        f'font-size="10" font-weight="600" letter-spacing="1">FOREFOOT</text>'
        f'<text x="80" y="158" text-anchor="middle" fill="#607D8B" '
        f'font-size="10" letter-spacing="1">MIDFOOT</text>'
        f'<text x="80" y="298" text-anchor="middle" fill="#90CAF9" '
        f'font-size="10" font-weight="600" letter-spacing="1">HEEL</text>'
    )

    return f"""
<svg viewBox="0 0 160 310" xmlns="http://www.w3.org/2000/svg"
     style="width:100%;max-width:180px;display:block;margin:auto">
  <path d="{foot_path}" fill="#0D1B2A" stroke="#1565C0" stroke-width="2.5"/>
  <line x1="34" y1="120" x2="128" y2="118" stroke="#1e2d44" stroke-width="1" stroke-dasharray="4,3"/>
  <line x1="38" y1="200" x2="122" y2="198" stroke="#1e2d44" stroke-width="1" stroke-dasharray="4,3"/>
  {dots_html}
  {labels}
  <circle cx="12" cy="292" r="5" fill="#43A047"/>
  <text x="20" y="296" fill="#888" font-size="8">Low</text>
  <circle cx="48" cy="292" r="5" fill="#FB8C00"/>
  <text x="56" y="296" fill="#888" font-size="8">Mid</text>
  <circle cx="82" cy="292" r="5" fill="#E53935"/>
  <text x="90" y="296" fill="#888" font-size="8">High</text>
</svg>"""


def _hw_load_bar(label: str, frac: float, color: str,
                 connected: bool = True) -> str:
    """Horizontal load bar HTML for regional distribution."""
    pct   = frac * 100
    bar_w = int(frac * 100)
    if not connected:
        return (
            f'<div style="margin:6px 0">'
            f'<div style="display:flex;justify-content:space-between;'
            f'font-size:0.78rem;color:#555;margin-bottom:3px">'
            f'<span>{label}</span><span style="color:#444">N/C</span></div>'
            f'<div style="background:#1A1F2E;border-radius:4px;height:10px">'
            f'<div style="width:0%;background:#333;height:100%;border-radius:4px"></div>'
            f'</div></div>'
        )
    return (
        f'<div style="margin:6px 0">'
        f'<div style="display:flex;justify-content:space-between;'
        f'font-size:0.82rem;color:#ccc;margin-bottom:3px">'
        f'<span>{label}</span>'
        f'<span style="color:{color};font-weight:700">{pct:.1f}%</span></div>'
        f'<div style="background:#1A1F2E;border-radius:4px;height:12px">'
        f'<div style="width:{bar_w}%;background:{color};height:100%;'
        f'border-radius:4px;transition:width 0.4s ease"></div>'
        f'</div></div>'
    )


def _hw_metric_card(label: str, value: str, sub: str = "",
                    color: str = "#E0E0E0", border: str = "#2A3050",
                    icon: str = "") -> str:
    return (
        f'<div style="background:#0D1B2A;border:1px solid {border};'
        f'border-radius:10px;padding:12px 16px;margin:4px 0;min-height:72px">'
        f'<div style="color:#90CAF9;font-size:0.68rem;text-transform:uppercase;'
        f'letter-spacing:1.2px;margin-bottom:4px">{icon} {label}</div>'
        f'<div style="font-size:1.45rem;font-weight:700;color:{color};'
        f'line-height:1.2">{value}</div>'
        f'{"<div style=color:#888;font-size:0.75rem;margin-top:2px>" + sub + "</div>" if sub else ""}'
        f'</div>'
    )


def _activity_class(accel_mag: float, gyro_mag: float,
                    cadence: float) -> tuple:
    """Classify activity from IMU data. Returns (label, icon, color)."""
    if accel_mag < 0.05 and gyro_mag < 2.0:
        return "STANDING / STATIC",  "🧍", "#607D8B"
    elif cadence > 80:
        return "RUNNING",            "🏃", "#E53935"
    elif cadence > 40:
        return "WALKING",            "🚶", "#43A047"
    elif accel_mag > 0.3:
        return "ACTIVE / DYNAMIC",   "⚡", "#FB8C00"
    else:
        return "LOW ACTIVITY",       "💤", "#78909C"


def page_live_hardware():
    """
    Live ESP32-S3 single LEFT-foot sensor dashboard.
    Anatomically correct: FOREFOOT/TOES = top, HEEL = bottom.
    Sensors: FSR1 (forefoot), FSR2 (heel), TMP117 (temperature), MPU6050 (IMU).
    Units: ADC counts (raw), proxy-kPa (labelled, uncalibrated), degC, g.
    No bilateral / left-vs-right charts -- single insole prototype.
    """
    import time as _time
    import math as _math

    _header("Live Hardware &nbsp;|&nbsp; LEFT Foot &middot; ESP32-S3 &middot; FSR + TMP117 + MPU6050")

    # ── lazy imports ──────────────────────────────────────────────────────────
    try:
        from hardware.esp32_receiver   import get_receiver
        from hardware.hardware_adapter import HardwareAdapter
        from src.hardware_input        import FSR_REGION_MAP, make_mock_packet
    except ImportError as e:
        st.error(
            f"Hardware modules not found: {e}\n\n"
            "Make sure you are running from the `SoleSense/` directory and the "
            "`hardware/` folder exists."
        )
        return

    # ── session state init ────────────────────────────────────────────────────
    if _BASELINE_KEY  not in st.session_state: st.session_state[_BASELINE_KEY]  = None
    if _LOAD_HIST_KEY not in st.session_state: st.session_state[_LOAD_HIST_KEY] = []
    if _RISK_HIST_KEY not in st.session_state: st.session_state[_RISK_HIST_KEY] = []
    if _HOTSPOT_KEY   not in st.session_state:
        st.session_state[_HOTSPOT_KEY] = {"region": None, "since": None, "duration": 0.0}

    # ── sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            '<div style="background:#0D1B2A;border:1px solid #1565C0;'
            'border-radius:8px;padding:12px 14px;margin-bottom:12px">'
            '<span style="color:#42A5F5;font-size:0.9rem;font-weight:700">'
            '🔌 Hardware Settings</span></div>',
            unsafe_allow_html=True,
        )
        receiver_port = st.number_input("Receiver Port", value=5005,
                                        min_value=1024, max_value=65535,
                                        step=1, key="hw_port")
        window_s  = st.slider("Analysis window (s)", 1.0, 10.0, 5.0, 0.5, key="hw_win")
        refresh_s = st.slider("Dashboard refresh (s)", 1, 10, 2, 1, key="hw_ref")
        mock_mode = st.checkbox("🧪 Mock mode (no hardware)", value=False, key="hw_mock")

        st.divider()
        if st.button("📐 Set Temp Baseline (current reading)", key="hw_set_bl"):
            st.session_state[_BASELINE_KEY] = None  # force re-capture next cycle

        st.divider()
        st.markdown(
            '<div style="color:#90CAF9;font-size:0.8rem">'
            '<b>Setup:</b><br>'
            '1. Set <code>SERVER_IP</code> in <code>firmware/config.h</code><br>'
            '2. Flash ESP32-S3<br>'
            '3. Power the insole<br>'
            '4. Data appears below ↓</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="disc">⚠ EXPERIMENTAL — Not for clinical use.</div>',
            unsafe_allow_html=True,
        )

    # ── start receiver ────────────────────────────────────────────────────────
    receiver = get_receiver(host="0.0.0.0", port=int(receiver_port))
    adapter  = HardwareAdapter(window_s=window_s)

    # ── build or mock packet stream ───────────────────────────────────────────
    if mock_mode:
        import random
        base_t   = int(_time.time() * 1000)
        t_now    = _time.time()
        packets  = []
        for i in range(int(window_s * 20)):
            phase   = (i / max(window_s * 20, 1)) * 2 * _math.pi * 3
            ff_base = 420 + int(180 * abs(_math.sin(phase)))
            hl_base = 380 + int(200 * abs(_math.cos(phase)))
            packets.append(make_mock_packet(
                timestamp   = base_t + i * 50,
                fsr1        = max(0, min(4095, ff_base + random.randint(-30, 30))),
                fsr2        = max(0, min(4095, hl_base + random.randint(-30, 30))),
                fsr3        = 0,
                fsr4        = 0,
                temperature = 31.4 + random.uniform(-0.05, 0.05),
                ax          = 0.03 + 0.1 * _math.sin(phase),
                ay          = -0.02 + 0.08 * _math.cos(phase),
                az          = 0.98,
                gx          = 1.2 * _math.sin(phase * 0.7),
                gy          = -0.8 * _math.cos(phase * 0.5),
                gz          = 0.3,
                received_at = t_now - (window_s - i * (window_s / max(window_s * 20, 1))),
            ))
        status = {
            "connected": True, "packet_rate_hz": 20.0,
            "total_received": len(packets), "total_errors": 0,
            "buffer_size": len(packets), "last_received_s": 0.0,
        }
        latest = packets[-1] if packets else None
    else:
        packets = receiver.recent_packets(n=int(window_s * 20))
        status  = receiver.status()
        latest  = receiver.latest_packet()

    conn      = status["connected"]
    conn_col  = C["normal"] if conn else C["alert"]
    rate_hz   = status.get("packet_rate_hz", 0.0)
    total_rx  = status.get("total_received", 0)
    last_s    = status.get("last_received_s", None)
    last_str  = f"{last_s:.1f} s ago" if last_s is not None else "—"

    import socket as _socket
    try:
        laptop_ip = _socket.gethostbyname(_socket.gethostname())
    except Exception:
        laptop_ip = "check: ipconfig (Win) / ifconfig (Mac/Linux)"

    # ═══════════════════════════════════════════════════════════════════════════
    #  DEVICE / Wi-Fi STATUS STRIP
    # ═══════════════════════════════════════════════════════════════════════════
    conn_dot  = "🟢" if conn else "🔴"
    conn_text = "CONNECTED" if conn else "WAITING FOR ESP32-S3…"

    has_temp = latest is not None and latest.get("temperature") is not None
    has_imu  = latest is not None and (
        abs(latest.get("ax", 0)) + abs(latest.get("ay", 0)) + abs(latest.get("az", 0)) > 0.001
    )
    fsr1_ok  = latest is not None and latest.get("fsr1", 0) > 0
    fsr2_ok  = latest is not None and latest.get("fsr2", 0) > 0

    def _sensor_badge(label, ok):
        col = "#43A047" if ok else "#444"
        dot = "●" if ok else "○"
        return (f'<span style="color:{col};font-size:0.78rem;margin-right:12px">'
                f'{dot} {label}</span>')

    st.markdown(
        f'<div style="background:#0A1628;border:1px solid {conn_col};'
        f'border-radius:10px;padding:10px 18px;margin-bottom:14px;'
        f'display:flex;align-items:center;flex-wrap:wrap;gap:8px;">'
        f'<span style="font-size:1.3rem">{conn_dot}</span>'
        f'<span style="color:{conn_col};font-weight:800;font-size:1rem;margin-right:16px">'
        f'{conn_text}</span>'
        + _sensor_badge("FSR1 (Forefoot)", fsr1_ok)
        + _sensor_badge("FSR2 (Heel)",     fsr2_ok)
        + _sensor_badge("TMP117 (Temp)",   has_temp)
        + _sensor_badge("MPU6050 (IMU)",   has_imu)
        + f'<span style="margin-left:auto;color:#607D8B;font-size:0.8rem">'
        f'Port <b style="color:#90CAF9">{int(receiver_port)}</b> &nbsp;|&nbsp; '
        f'Rate <b style="color:#90CAF9">{rate_hz:.1f} Hz</b> &nbsp;|&nbsp; '
        f'Rx <b style="color:#90CAF9">{total_rx:,}</b> &nbsp;|&nbsp; '
        f'Last <b style="color:#90CAF9">{last_str}</b>'
        f'</span></div>',
        unsafe_allow_html=True,
    )

    if mock_mode:
        st.info("🧪 **Mock mode** — synthetic data for demonstration. "
                "Uncheck to connect real ESP32-S3 hardware.")

    if not conn and not mock_mode:
        st.markdown(
            f'<div style="background:#0D1B2A;border:1px solid #1565C0;'
            f'border-radius:10px;padding:14px 20px;margin-bottom:12px">'
            f'<b style="color:#42A5F5">📡 Waiting for ESP32-S3</b><br>'
            f'<span style="color:#90CAF9;font-size:0.88rem">'
            f'Receiver on port <b>{int(receiver_port)}</b> — '
            f'set <code>SERVER_IP = "{laptop_ip}"</code> in firmware '
            f'<code>config.h</code> and power the insole.</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown("""
**Setup checklist:**
1. Flash `firmware/solesense_esp32s3/` to your ESP32-S3
2. Edit `config.h` — set `WIFI_SSID`, `WIFI_PASSWORD`, and `SERVER_IP`
3. Power the insole — it streams at 20 Hz automatically
4. This page auto-refreshes
""")
        _time.sleep(int(refresh_s))
        st.rerun()
        return

    # ── unpack latest packet ───────────────────────────────────────────────────
    if latest:
        fsr1_adc = int(latest.get("fsr1", 0))
        fsr2_adc = int(latest.get("fsr2", 0))
        temp_c   = latest.get("temperature")
        ax_now   = latest.get("ax", 0.0)
        ay_now   = latest.get("ay", 0.0)
        az_now   = latest.get("az", 0.0)
        gx_now   = latest.get("gx", 0.0)
        gy_now   = latest.get("gy", 0.0)
        gz_now   = latest.get("gz", 0.0)
    else:
        fsr1_adc = fsr2_adc = 0
        temp_c   = None
        ax_now = ay_now = az_now = 0.0
        gx_now = gy_now = gz_now = 0.0

    total_adc     = fsr1_adc + fsr2_adc
    ff_frac       = fsr1_adc / total_adc if total_adc > 0 else 0.0
    hl_frac       = fsr2_adc / total_adc if total_adc > 0 else 0.0
    accel_mag_now = _math.sqrt(ax_now**2 + ay_now**2 + az_now**2)
    gyro_mag_now  = _math.sqrt(gx_now**2 + gy_now**2 + gz_now**2)

    # ── window-level arrays ────────────────────────────────────────────────────
    ff_arr    = np.array([p.get("fsr1", 0) for p in packets], dtype=float)
    hl_arr    = np.array([p.get("fsr2", 0) for p in packets], dtype=float)
    total_arr = ff_arr + hl_arr
    n_pkt     = len(packets)

    ff_mean_adc  = float(ff_arr.mean())   if n_pkt else 0.0
    hl_mean_adc  = float(hl_arr.mean())   if n_pkt else 0.0
    tot_mean_adc = float(total_arr.mean()) if n_pkt else 0.0
    tot_peak_adc = float(total_arr.max())  if n_pkt else 0.0

    ff_mean_pkpa  = _adc_to_proxy(ff_mean_adc)
    hl_mean_pkpa  = _adc_to_proxy(hl_mean_adc)
    tot_mean_pkpa = _adc_to_proxy(tot_mean_adc)
    tot_peak_pkpa = _adc_to_proxy(tot_peak_adc)
    cur_tot_pkpa  = _adc_to_proxy(float(total_adc))

    frame_dur = 1.0 / 20.0
    pti_ff    = float(np.sum(ff_arr))    * frame_dur * (_PROXY_SCALE / FSR_ADC_MAX_DISPLAY)
    pti_hl    = float(np.sum(hl_arr))    * frame_dur * (_PROXY_SCALE / FSR_ADC_MAX_DISPLAY)
    pti_total = float(np.sum(total_arr)) * frame_dur * (_PROXY_SCALE / FSR_ADC_MAX_DISPLAY)

    persist_thr = FSR_ADC_MAX_DISPLAY * 0.30
    pers_ff     = float(np.mean(ff_arr    > persist_thr)) if n_pkt else 0.0
    pers_hl     = float(np.mean(hl_arr    > persist_thr)) if n_pkt else 0.0
    pers_total  = float(np.mean(total_arr > persist_thr * 2)) if n_pkt else 0.0

    if n_pkt > 0:
        st.session_state[_LOAD_HIST_KEY].append(tot_mean_adc)
        if len(st.session_state[_LOAD_HIST_KEY]) > 2000:
            st.session_state[_LOAD_HIST_KEY] = st.session_state[_LOAD_HIST_KEY][-2000:]

    # ── feature row for risk engine ────────────────────────────────────────────
    feature_row = adapter.to_feature_row(packets) if n_pkt >= 2 else None
    if feature_row is not None:
        rr = compute_risk(feature_row)
        st.session_state[_RISK_HIST_KEY].append(rr.risk_score)
        if len(st.session_state[_RISK_HIST_KEY]) > 500:
            st.session_state[_RISK_HIST_KEY] = st.session_state[_RISK_HIST_KEY][-500:]
    else:
        rr = None

    # ── hotspot state ──────────────────────────────────────────────────────────
    hs    = st.session_state[_HOTSPOT_KEY]
    now_t = _time.time()
    if ff_frac > 0.6:
        dominant_region = "Forefoot"
        hs_reason       = f"Forefoot carries {ff_frac*100:.0f}% of total load"
    elif hl_frac > 0.6:
        dominant_region = "Heel"
        hs_reason       = f"Heel carries {hl_frac*100:.0f}% of total load"
    elif tot_peak_adc > FSR_ADC_MAX_DISPLAY * 0.7:
        dominant_region = "Peak load zone"
        hs_reason       = f"Peak load {tot_peak_adc:.0f} ADC ({tot_peak_pkpa:.0f} {_PROXY_ABBR})"
    else:
        dominant_region = None
        hs_reason       = "Load within normal distribution"

    if dominant_region and dominant_region == hs.get("region"):
        hs["duration"] = now_t - (hs.get("since") or now_t)
    else:
        hs["region"]   = dominant_region
        hs["since"]    = now_t
        hs["duration"] = 0.0

    # ═══════════════════════════════════════════════════════════════════════════
    #  OVERALL STATUS BANNER
    # ═══════════════════════════════════════════════════════════════════════════
    lc        = LEVEL_COLOR[rr.risk_level] if rr else C["neutral"]
    lvl       = rr.risk_level              if rr else "COLLECTING…"
    lvl_icon  = LEVEL_EMOJI.get(lvl, "⏳")
    n_factors = len(rr.contributing_factors) if rr else 0
    risk_score = rr.risk_score if rr else 0.0
    led_col   = {"NORMAL": "#43A047", "MONITOR": "#FB8C00",
                 "ALERT": "#E53935"}.get(lvl, "#607D8B")

    st.markdown(
        f'<div style="background:linear-gradient(135deg,{led_col}22 0%,#0A1628 60%);'
        f'border:2px solid {lc};border-radius:14px;padding:18px 24px;'
        f'margin-bottom:18px;display:flex;align-items:center;gap:20px;flex-wrap:wrap">'
        f'<div style="width:22px;height:22px;border-radius:50%;background:{led_col};'
        f'box-shadow:0 0 12px {led_col};flex-shrink:0"></div>'
        f'<div style="flex:1">'
        f'<div style="color:{lc};font-size:1.8rem;font-weight:900;'
        f'letter-spacing:2px;line-height:1">{lvl_icon} {lvl}</div>'
        f'<div style="color:#90CAF9;font-size:0.88rem;margin-top:4px">'
        f'SoleSense Risk Indicator: '
        f'<b style="color:{lc};font-size:1.2rem">{risk_score:.1f}</b>/100 &nbsp;·&nbsp; '
        f'{n_factors} factor{"s" if n_factors != 1 else ""} active &nbsp;·&nbsp; '
        f'LEFT foot · single-insole prototype</div>'
        f'</div>'
        f'<div style="text-align:center;background:#0D1B2A;border-radius:10px;'
        f'padding:10px 20px;border:1px solid {lc}">'
        f'<div style="font-size:2.2rem;font-weight:900;color:{lc}">{risk_score:.0f}</div>'
        f'<div style="color:#888;font-size:0.72rem">/ 100</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # ═══════════════════════════════════════════════════════════════════════════
    #  SECTION 1 — Foot Map, Load Distribution, Top Metrics
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sh">① Left Foot Pressure Map &amp; Load Distribution</div>',
                unsafe_allow_html=True)

    col_foot, col_load, col_metrics = st.columns([1, 1.4, 1.6])

    with col_foot:
        st.markdown(
            '<div style="background:#0A1628;border:1px solid #1e2d44;'
            'border-radius:12px;padding:14px;text-align:center">'
            '<div style="color:#90CAF9;font-size:0.72rem;text-transform:uppercase;'
            'letter-spacing:1.5px;margin-bottom:8px">LEFT FOOT</div>'
            + _hw_foot_svg(forefoot=fsr1_adc, heel=fsr2_adc)
            + '<div style="color:#607D8B;font-size:0.7rem;margin-top:8px">'
            'Dot size ∝ relative load<br>Colour: green→amber→red</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    with col_load:
        st.markdown(
            '<div style="background:#0A1628;border:1px solid #1e2d44;'
            'border-radius:12px;padding:16px 18px">'
            '<div style="color:#90CAF9;font-size:0.72rem;text-transform:uppercase;'
            'letter-spacing:1.5px;margin-bottom:12px">LOAD DISTRIBUTION</div>'
            + _hw_load_bar("🦶 Forefoot (FSR1)", ff_frac, "#1E88E5", connected=True)
            + _hw_load_bar("⚙ Midfoot",          0.0,     "#607D8B", connected=False)
            + _hw_load_bar("👟 Heel (FSR2)",      hl_frac, "#42A5F5", connected=True)
            + f'<div style="border-top:1px solid #1e2d44;margin-top:12px;'
            f'padding-top:10px">'
            f'<div style="color:#607D8B;font-size:0.72rem">⚙ Midfoot sensor not connected (N/C)</div>'
            f'<div style="color:#607D8B;font-size:0.72rem;margin-top:2px">'
            f'FSR1 ADC: <b style="color:#90CAF9">{fsr1_adc}</b> &nbsp;|&nbsp; '
            f'FSR2 ADC: <b style="color:#90CAF9">{fsr2_adc}</b> &nbsp;|&nbsp; '
            f'Total: <b style="color:#90CAF9">{total_adc}</b></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    with col_metrics:
        m1, m2 = st.columns(2)
        cadence_est = feature_row.get("cadence_steps_per_min", 0.0) if feature_row is not None else 0.0
        stance_est  = feature_row.get("stance_time_s", 0.0)         if feature_row is not None else 0.0
        with m1:
            st.markdown(
                _hw_metric_card("Peak Load", f"{tot_peak_pkpa:.0f}",
                                sub=_PROXY_LABEL, color="#42A5F5",
                                border="#1565C0", icon="📈")
                + _hw_metric_card("Avg Load", f"{tot_mean_pkpa:.0f}",
                                  sub=_PROXY_LABEL, color="#90CAF9",
                                  border="#2A3050", icon="📊")
                + _hw_metric_card("Current", f"{cur_tot_pkpa:.0f}",
                                  sub=_PROXY_LABEL, color=C["accent"],
                                  border="#2A3050", icon="⚡"),
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown(
                _hw_metric_card("Forefoot Avg", f"{ff_mean_pkpa:.0f}",
                                sub=f"{_PROXY_ABBR} · FSR1", color="#1E88E5",
                                border="#1565C0", icon="🦶")
                + _hw_metric_card("Heel Avg", f"{hl_mean_pkpa:.0f}",
                                  sub=f"{_PROXY_ABBR} · FSR2", color="#42A5F5",
                                  border="#2A3050", icon="👟")
                + _hw_metric_card("Cadence (est.)", f"{cadence_est:.0f}",
                                  sub="steps/min (load-onset)", color="#90CAF9",
                                  border="#2A3050", icon="🚶"),
                unsafe_allow_html=True,
            )

    # ═══════════════════════════════════════════════════════════════════════════
    #  SECTION 2 — Load Over Time
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sh">② Pressure / Load Over Time</div>',
                unsafe_allow_html=True)

    if n_pkt > 1:
        t_axis   = [i * frame_dur for i in range(n_pkt)]
        ff_pkpa  = [_adc_to_proxy(v) for v in ff_arr]
        hl_pkpa  = [_adc_to_proxy(v) for v in hl_arr]
        tot_pkpa = [_adc_to_proxy(v) for v in total_arr]

        fig_ts = go.Figure()
        fig_ts.add_trace(go.Scatter(
            x=t_axis, y=ff_pkpa, mode="lines", name="Forefoot (FSR1)",
            line=dict(color="#1E88E5", width=2, shape="spline"),
            hovertemplate="t=%{x:.2f}s<br>Forefoot: %{y:.0f} p-kPa<extra></extra>",
        ))
        fig_ts.add_trace(go.Scatter(
            x=t_axis, y=hl_pkpa, mode="lines", name="Heel (FSR2)",
            line=dict(color="#42A5F5", width=2, shape="spline"),
            hovertemplate="t=%{x:.2f}s<br>Heel: %{y:.0f} p-kPa<extra></extra>",
        ))
        fig_ts.add_trace(go.Scatter(
            x=t_axis, y=tot_pkpa, mode="lines", name="Total",
            fill="tozeroy", fillcolor="rgba(0,176,255,0.08)",
            line=dict(color=C["accent"], width=2.5, shape="spline"),
            hovertemplate="t=%{x:.2f}s<br>Total: %{y:.0f} p-kPa<extra></extra>",
        ))
        thr_pkpa = _PROXY_SCALE * 0.30
        fig_ts.add_hline(
            y=thr_pkpa, line_dash="dash", line_color=C["monitor"],
            annotation_text="Elevated threshold (30% scale)",
            annotation_font_color=C["monitor"], annotation_position="right",
        )
        _chart_layout(fig_ts, height=260,
                      title=dict(
                          text=f"Load Over Time — last {window_s:.0f}s window  "
                               f"<span style='font-size:11px;color:#607D8B'>"
                               f"(proxy kPa = ADC/4095 × 600, uncalibrated)</span>",
                          font=dict(size=13)),
                      margin=(44, 35, 50, 80))
        fig_ts.update_layout(
            yaxis_title=f"Load ({_PROXY_ABBR})",
            xaxis_title="Time (s)",
            legend=dict(orientation="h", y=-0.22, font=dict(size=11)),
        )
        st.plotly_chart(fig_ts, use_container_width=True)
    else:
        st.info("Collecting samples…")

    # ═══════════════════════════════════════════════════════════════════════════
    #  SECTION 3 — Pressure-Time Exposure & Persistence
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sh">③ Pressure-Time Exposure &amp; Persistence</div>',
                unsafe_allow_html=True)

    pe1, pe2, pe3, pe4, pe5, pe6 = st.columns(6)
    pti_col  = C["alert"] if pti_total > _PROXY_SCALE * 0.5 * window_s else C["normal"]
    def pers_col(p):
        return C["alert"] if p > 0.7 else (C["monitor"] if p > 0.4 else C["normal"])

    pe1.markdown(_hw_metric_card("Forefoot PTI", f"{pti_ff:.1f}",
                                 sub="p-kPa·s (proxy)", color="#1E88E5",
                                 border="#1565C0", icon="🦶"),
                 unsafe_allow_html=True)
    pe2.markdown(_hw_metric_card("Heel PTI", f"{pti_hl:.1f}",
                                 sub="p-kPa·s (proxy)", color="#42A5F5",
                                 border="#2A3050", icon="👟"),
                 unsafe_allow_html=True)
    pe3.markdown(_hw_metric_card("Total PTI", f"{pti_total:.1f}",
                                 sub="p-kPa·s (proxy)", color=pti_col,
                                 border="#2A3050", icon="Σ"),
                 unsafe_allow_html=True)
    pe4.markdown(_hw_metric_card("Forefoot Persist.", f"{pers_ff*100:.0f}%",
                                 sub="% samples elevated", color=pers_col(pers_ff),
                                 border="#2A3050", icon="⏱"),
                 unsafe_allow_html=True)
    pe5.markdown(_hw_metric_card("Heel Persist.", f"{pers_hl*100:.0f}%",
                                 sub="% samples elevated", color=pers_col(pers_hl),
                                 border="#2A3050", icon="⏱"),
                 unsafe_allow_html=True)
    pe6.markdown(_hw_metric_card("Overall Persist.", f"{pers_total*100:.0f}%",
                                 sub="% samples elevated", color=pers_col(pers_total),
                                 border="#2A3050", icon="📊"),
                 unsafe_allow_html=True)

    reg_fig = go.Figure()
    reg_fig.add_trace(go.Bar(
        x=["Forefoot (FSR1)", "Midfoot (N/C)", "Heel (FSR2)"],
        y=[ff_mean_pkpa, 0.0, hl_mean_pkpa],
        marker_color=["#1E88E5", "#2A3050", "#42A5F5"],
        marker_line_color=["#42A5F5", "#333", "#90CAF9"],
        marker_line_width=1.5,
        text=[f"{ff_mean_pkpa:.0f}", "N/C", f"{hl_mean_pkpa:.0f}"],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{x}<br>%{y:.1f} p-kPa<extra></extra>",
        name="Avg Load",
    ))
    reg_fig.add_trace(go.Bar(
        x=["Forefoot (FSR1)", "Midfoot (N/C)", "Heel (FSR2)"],
        y=[pers_ff * 100, 0.0, pers_hl * 100],
        marker_color=["rgba(30,136,229,0.35)", "rgba(0,0,0,0)", "rgba(66,165,245,0.35)"],
        marker_line_width=0,
        name="Persistence %",
        yaxis="y2",
        hovertemplate="%{x}<br>Persistence: %{y:.0f}%<extra></extra>",
    ))
    _chart_layout(reg_fig, height=260,
                  title=dict(text="Window Average Load by Region  (bars = p-kPa, overlay = persistence %)",
                             font=dict(size=12)),
                  margin=(44, 35, 60, 20))
    reg_fig.update_layout(
        barmode="overlay",
        yaxis=dict(title=f"Avg Load ({_PROXY_ABBR})", gridcolor="#1e2330"),
        yaxis2=dict(title="Persistence %", overlaying="y", side="right",
                    range=[0, 110], gridcolor="#1e2330", showgrid=False),
        showlegend=False,
        annotations=[dict(
            text="⚠ Proxy values — not calibrated kPa", x=0.5, y=-0.18,
            xref="paper", yref="paper", showarrow=False,
            font=dict(size=10, color="#607D8B"), align="center",
        )],
    )
    st.plotly_chart(reg_fig, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════════
    #  SECTION 4 — Temperature
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sh">④ Temperature (TMP117)</div>',
                unsafe_allow_html=True)

    temp_pkts = [p for p in packets if p.get("temperature") is not None]
    temp_vals = [p["temperature"] for p in temp_pkts]

    if temp_vals:
        t_cur  = temp_c if temp_c is not None else temp_vals[-1]
        t_mean = float(np.mean(temp_vals))
        t_std  = float(np.std(temp_vals)) if len(temp_vals) > 1 else 0.0

        if st.session_state[_BASELINE_KEY] is None:
            st.session_state[_BASELINE_KEY] = round(t_mean, 2)
        baseline  = st.session_state[_BASELINE_KEY]
        deviation = t_cur - baseline

        dev_col   = (C["alert"] if abs(deviation) > 1.5 else
                     C["monitor"] if abs(deviation) > 0.5 else C["normal"])
        trend_dir = "▲" if deviation > 0.1 else ("▼" if deviation < -0.1 else "→")
        trend_col = C["alert"] if deviation > 1.0 else (
                    C["monitor"] if deviation > 0.3 else C["normal"])

        tc1, tc2, tc3, tc4 = st.columns(4)
        tc1.markdown(_hw_metric_card("Current Temp", f"{t_cur:.2f} °C",
                                     sub="TMP117 reading", color=C["monitor"],
                                     border="#E65100", icon="🌡️"),
                     unsafe_allow_html=True)
        tc2.markdown(_hw_metric_card("Session Baseline", f"{baseline:.2f} °C",
                                     sub="set at session start", color="#90CAF9",
                                     border="#2A3050", icon="📐"),
                     unsafe_allow_html=True)
        tc3.markdown(_hw_metric_card("Deviation", f"{deviation:+.2f} °C",
                                     sub="current − baseline", color=dev_col,
                                     border="#2A3050", icon="Δ"),
                     unsafe_allow_html=True)
        tc4.markdown(_hw_metric_card("Trend", f"{trend_dir} {abs(deviation):.2f} °C",
                                     sub=f"σ = {t_std:.3f} °C (window)",
                                     color=trend_col, border="#2A3050", icon="📈"),
                     unsafe_allow_html=True)

        if len(temp_vals) > 2:
            fig_temp = go.Figure()
            t_t_axis = [i * frame_dur for i in range(len(temp_vals))]
            fig_temp.add_hrect(y0=baseline - 0.5, y1=baseline + 0.5,
                               fillcolor="rgba(67,160,71,0.07)", line_width=0)
            fig_temp.add_trace(go.Scatter(
                x=t_t_axis, y=temp_vals, mode="lines+markers",
                line=dict(color=C["monitor"], width=2.5, shape="spline"),
                marker=dict(size=3),
                fill="tozeroy", fillcolor="rgba(251,140,0,0.08)",
                hovertemplate="t=%{x:.2f}s<br>Temp: %{y:.3f} °C<extra></extra>",
                name="Temperature",
            ))
            fig_temp.add_hline(
                y=baseline, line_dash="dot", line_color="#43A047",
                annotation_text=f"Baseline {baseline:.2f} °C",
                annotation_font_color="#43A047", annotation_position="right",
            )
            _chart_layout(fig_temp, height=200,
                          title=dict(text="Temperature Over Window (°C) — TMP117",
                                     font=dict(size=13)),
                          margin=(40, 35, 50, 80))
            fig_temp.update_layout(yaxis_title="Temperature (°C)",
                                   xaxis_title="Time (s)")
            st.plotly_chart(fig_temp, use_container_width=True)
    else:
        st.markdown(
            '<div style="background:#1A1F2E;border:1px solid #2A3050;'
            'border-radius:10px;padding:18px;color:#607D8B">'
            '🌡️ TMP117 not reporting — check wiring and firmware config.</div>',
            unsafe_allow_html=True,
        )

    # ═══════════════════════════════════════════════════════════════════════════
    #  SECTION 5 — Gait Analysis (LEFT FOOT · MPU6050)
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sh">⑤ Gait Analysis — LEFT FOOT (MPU6050)</div>',
                unsafe_allow_html=True)

    imu_pkts = [p for p in packets
                if abs(p.get("ax", 0)) + abs(p.get("ay", 0)) + abs(p.get("az", 0)) > 0.001]

    if imu_pkts:
        # ── raw IMU arrays ────────────────────────────────────────────────────
        ax_v = np.array([p.get("ax", 0.0) for p in imu_pkts])
        ay_v = np.array([p.get("ay", 0.0) for p in imu_pkts])
        az_v = np.array([p.get("az", 0.0) for p in imu_pkts])
        gx_v = np.array([p.get("gx", 0.0) for p in imu_pkts])
        gy_v = np.array([p.get("gy", 0.0) for p in imu_pkts])
        gz_v = np.array([p.get("gz", 0.0) for p in imu_pkts])
        am_v = np.sqrt(ax_v**2 + ay_v**2 + az_v**2)   # total accel magnitude
        gm_v = np.sqrt(gx_v**2 + gy_v**2 + gz_v**2)   # total gyro magnitude

        # ── derived scalars ────────────────────────────────────────────────────
        accel_mean     = float(am_v.mean())
        accel_std      = float(am_v.std())
        accel_peak     = float(am_v.max())
        gyro_mean      = float(gm_v.mean())
        # deviation from gravity baseline (1 g when stationary)
        dynamic_accel  = float(np.mean(np.abs(am_v - 1.0)))

        cadence_est_imu = (feature_row.get("cadence_steps_per_min", 0.0)
                           if feature_row is not None else 0.0)
        stance_est_imu  = (feature_row.get("stance_time_s", 0.0)
                           if feature_row is not None else 0.0)
        step_time_std   = (feature_row.get("step_time_std_s", 0.0)
                           if feature_row is not None else 0.0)

        # ── step count estimate from FSR load-onset events (this window) ────────
        step_count_est = max(0, int(round(cadence_est_imu * (window_s / 60.0))))

        # ── session total step counter (accumulates across all refreshes) ────────
        _STEP_TOTAL_KEY    = "hw_total_steps"
        _STEP_LAST_WIN_KEY = "hw_last_window_steps"
        if _STEP_TOTAL_KEY    not in st.session_state: st.session_state[_STEP_TOTAL_KEY]    = 0
        if _STEP_LAST_WIN_KEY not in st.session_state: st.session_state[_STEP_LAST_WIN_KEY] = 0
        # Only add newly detected steps (avoid counting the same window twice)
        new_steps = max(0, step_count_est - st.session_state[_STEP_LAST_WIN_KEY])
        st.session_state[_STEP_TOTAL_KEY]    += new_steps
        st.session_state[_STEP_LAST_WIN_KEY]  = step_count_est
        session_total_steps = st.session_state[_STEP_TOTAL_KEY]

        # ── movement intensity (0–100 normalised from dynamic accel) ──────────
        # 0 = completely static (|A-1g|=0), 100 = very high motion (|A-1g|>1g)
        movement_intensity = min(100.0, dynamic_accel * 100.0)

        # ── gait variability (coefficient of variation of |A|) ─────────────────
        gait_cv = (accel_std / accel_mean * 100.0) if accel_mean > 0 else 0.0

        # ── activity classification ────────────────────────────────────────────
        act_label, act_icon, act_col = _activity_class(
            dynamic_accel, gyro_mean, cadence_est_imu)

        # ── gait session baseline (accel magnitude history) ───────────────────
        _GAIT_HIST_KEY = "hw_gait_accel_hist"
        if _GAIT_HIST_KEY not in st.session_state:
            st.session_state[_GAIT_HIST_KEY] = []
        st.session_state[_GAIT_HIST_KEY].append(float(accel_mean))
        if len(st.session_state[_GAIT_HIST_KEY]) > 600:
            st.session_state[_GAIT_HIST_KEY] = st.session_state[_GAIT_HIST_KEY][-600:]

        gait_hist = st.session_state[_GAIT_HIST_KEY]
        gait_baseline_val = float(np.mean(gait_hist[:min(20, len(gait_hist))]))
        gait_current_val  = float(np.mean(gait_hist[-min(10, len(gait_hist)):]))
        gait_deviation    = ((gait_current_val - gait_baseline_val)
                             / max(gait_baseline_val, 0.001) * 100.0)

        # ── gait trend (STABLE / CHANGING / DEVIATING) ────────────────────────
        if abs(gait_deviation) < 5.0:
            gait_trend       = "STABLE"
            gait_trend_icon  = "→"
            gait_trend_color = "#43A047"
        elif abs(gait_deviation) < 15.0:
            gait_trend       = "CHANGING"
            gait_trend_icon  = "⤴" if gait_deviation > 0 else "⤵"
            gait_trend_color = "#FB8C00"
        else:
            gait_trend       = "DEVIATING"
            gait_trend_icon  = "▲" if gait_deviation > 0 else "▼"
            gait_trend_color = "#E53935"

        # ── GAIT ANALYSIS interpretation card ─────────────────────────────────
        if act_label in ("STANDING / STATIC", "LOW ACTIVITY"):
            gait_card_level  = "NORMAL"
            gait_card_color  = "#43A047"
            gait_card_dot    = "🟢"
            gait_card_text   = (
                "Foot is at rest. No significant movement detected. "
                "Place foot on the ground and walk to see gait analysis."
            )
        elif gait_trend == "STABLE" and gait_cv < 15.0:
            gait_card_level  = "NORMAL"
            gait_card_color  = "#43A047"
            gait_card_dot    = "🟢"
            gait_card_text   = (
                f"Movement pattern is consistent with the current session baseline. "
                f"Cadence is {cadence_est_imu:.0f} steps/min with stable rhythm "
                f"(variability CV = {gait_cv:.1f}%)."
            )
        elif gait_trend == "CHANGING" or 15.0 <= gait_cv < 30.0:
            gait_card_level  = "MONITOR"
            gait_card_color  = "#FB8C00"
            gait_card_dot    = "🟡"
            gait_card_text   = (
                f"Movement pattern shows a moderate deviation from the session baseline "
                f"({gait_deviation:+.1f}%). Gait rhythm has some irregularity "
                f"(CV = {gait_cv:.1f}%). Continue monitoring over the next few minutes."
            )
        else:
            gait_card_level  = "MONITOR"
            gait_card_color  = "#E53935"
            gait_card_dot    = "🔴"
            gait_card_text   = (
                f"Movement pattern is notably different from the session baseline "
                f"({gait_deviation:+.1f}%). High gait variability detected "
                f"(CV = {gait_cv:.1f}%). Check for fatigue, discomfort, or altered gait."
            )

        # Reliability note for cadence
        cadence_reliable = step_count_est >= 2 and cadence_est_imu > 0

        # ══════════════════════════════════════════════════════════════════════
        #  ROW A — GAIT ANALYSIS card + Activity + Trend
        # ══════════════════════════════════════════════════════════════════════
        ga_card_col, ga_meta_col = st.columns([1.6, 1])

        with ga_card_col:
            st.markdown(
                f'<div style="background:linear-gradient(135deg,{gait_card_color}18 0%,'
                f'#0A1628 70%);border:2px solid {gait_card_color};border-radius:14px;'
                f'padding:18px 22px;height:100%">'
                f'<div style="font-size:0.68rem;text-transform:uppercase;'
                f'letter-spacing:1.8px;color:#90CAF9;margin-bottom:6px">'
                f'GAIT ANALYSIS CARD — LEFT FOOT</div>'
                f'<div style="font-size:1.55rem;font-weight:900;color:{gait_card_color};'
                f'letter-spacing:1px;margin-bottom:8px">'
                f'{gait_card_dot} {gait_card_level}</div>'
                f'<div style="color:#D0D8F0;font-size:0.9rem;line-height:1.55">'
                f'{gait_card_text}</div>'
                f'<div style="margin-top:12px;display:flex;gap:12px;flex-wrap:wrap">'
                f'<span style="background:#0D1B2A;border:1px solid {act_col};'
                f'border-radius:20px;padding:3px 12px;color:{act_col};'
                f'font-size:0.78rem;font-weight:700">{act_icon} {act_label}</span>'
                f'<span style="background:#0D1B2A;border:1px solid {gait_trend_color};'
                f'border-radius:20px;padding:3px 12px;color:{gait_trend_color};'
                f'font-size:0.78rem;font-weight:700">'
                f'{gait_trend_icon} Trend: {gait_trend}</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

        with ga_meta_col:
            st.markdown(
                _hw_metric_card("Total Steps (session)",
                                f"{session_total_steps:,}",
                                sub=f"this window: ~{step_count_est} · load-onset detection",
                                color="#42A5F5", border="#1565C0", icon="👣")
                + _hw_metric_card("Cadence",
                                  f"{cadence_est_imu:.0f} spm" if cadence_reliable else "< 2 steps",
                                  sub="steps/min · load-onset detection",
                                  color="#64B5F6" if cadence_reliable else "#607D8B",
                                  border="#2A3050", icon="🚶")
                + _hw_metric_card("Gait vs Baseline",
                                  f"{gait_deviation:+.1f}%",
                                  sub="current vs session start",
                                  color=gait_trend_color, border="#2A3050", icon="📐"),
                unsafe_allow_html=True,
            )

        st.markdown("")   # vertical spacer

        # ══════════════════════════════════════════════════════════════════════
        #  ROW B — Key gait metrics (5 cards)
        # ══════════════════════════════════════════════════════════════════════
        mb1, mb2, mb3, mb4, mb5 = st.columns(5)

        mb1.markdown(
            _hw_metric_card("|Accel| mean", f"{accel_mean:.3f} g",
                            sub="total magnitude · MPU6050",
                            color="#42A5F5", border="#1565C0", icon="📡"),
            unsafe_allow_html=True,
        )
        mb2.markdown(
            _hw_metric_card("Dynamic Accel", f"{dynamic_accel:.3f} g",
                            sub="deviation from 1 g gravity",
                            color="#64B5F6", border="#2A3050", icon="⚡"),
            unsafe_allow_html=True,
        )
        intensity_col = (C["alert"] if movement_intensity > 60
                         else C["monitor"] if movement_intensity > 30
                         else C["normal"])
        mb3.markdown(
            _hw_metric_card("Movement Intensity", f"{movement_intensity:.0f} / 100",
                            sub="0 = still · 100 = very active",
                            color=intensity_col, border="#2A3050", icon="💪"),
            unsafe_allow_html=True,
        )
        gait_cv_col = (C["alert"] if gait_cv > 30
                       else C["monitor"] if gait_cv > 15
                       else C["normal"])
        mb4.markdown(
            _hw_metric_card("Gait Variability CV", f"{gait_cv:.1f}%",
                            sub="CV of |accel| · lower = steadier",
                            color=gait_cv_col, border="#2A3050", icon="〰️"),
            unsafe_allow_html=True,
        )
        mb5.markdown(
            _hw_metric_card("Stance Time (est.)", f"{stance_est_imu:.2f} s" if stance_est_imu > 0 else "—",
                            sub="mean weight-bearing per step",
                            color="#90CAF9", border="#2A3050", icon="⏱"),
            unsafe_allow_html=True,
        )

        # ══════════════════════════════════════════════════════════════════════
        #  ROW C — Step timing card (only when reliably calculable)
        # ══════════════════════════════════════════════════════════════════════
        if cadence_reliable and step_time_std > 0:
            step_time_mean_s = 60.0 / cadence_est_imu if cadence_est_imu > 0 else 0.0
            stride_time_s    = step_time_mean_s * 2.0   # stride = 2 steps
            st.markdown(
                f'<div style="background:#0A1628;border:1px solid #1e2d44;'
                f'border-radius:10px;padding:12px 18px;margin-bottom:8px;'
                f'display:flex;gap:20px;flex-wrap:wrap;align-items:center">'
                f'<div style="color:#90CAF9;font-size:0.68rem;text-transform:uppercase;'
                f'letter-spacing:1.5px;white-space:nowrap">Step / Stride Timing</div>'
                f'<div style="color:#42A5F5;font-size:0.88rem">'
                f'Step time: <b>{step_time_mean_s:.2f} s</b></div>'
                f'<div style="color:#64B5F6;font-size:0.88rem">'
                f'Stride time (est.): <b>{stride_time_s:.2f} s</b></div>'
                f'<div style="color:#90CAF9;font-size:0.88rem">'
                f'Step-time std: <b>{step_time_std:.3f} s</b></div>'
                f'<div style="color:{"#FB8C00" if step_time_std > 0.15 else "#43A047"};'
                f'font-size:0.88rem">'
                f'Variability: <b>{"HIGH ⚠" if step_time_std > 0.15 else "NORMAL ✓"}</b></div>'
                f'<div style="color:#607D8B;font-size:0.75rem;margin-left:auto">'
                f'Derived from FSR load-onset · single foot only</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # ══════════════════════════════════════════════════════════════════════
        #  ROW D — Acceleration chart (all axes + magnitude) — EXISTING, improved
        # ══════════════════════════════════════════════════════════════════════
        t_imu_axis = [i * frame_dur for i in range(len(imu_pkts))]

        fig_imu = go.Figure()
        # background zone for gravity reference band
        fig_imu.add_hrect(y0=0.9, y1=1.1,
                          fillcolor="rgba(67,160,71,0.06)", line_width=0,
                          annotation_text="gravity band ±0.1 g",
                          annotation_font_color="#2E7D32",
                          annotation_font_size=9,
                          annotation_position="top right")
        for vals, name, color, width, dash in [
            (ax_v, "AX — forward/back (g)",  "#42A5F5", 1.4, "solid"),
            (ay_v, "AY — side/side (g)",     "#66BB6A", 1.4, "solid"),
            (az_v, "AZ — up/down (g)",       "#FFA726", 1.4, "solid"),
            (am_v, "|A| — total magnitude (g)", "#FFFFFF", 2.8, "solid"),
        ]:
            fig_imu.add_trace(go.Scatter(
                x=t_imu_axis, y=vals.tolist(), mode="lines", name=name,
                line=dict(color=color, width=width, shape="spline", dash=dash),
                hovertemplate=(
                    "Time: %{x:.2f} s<br>"
                    + name.split(" ")[0] + ": %{y:.4f} g<br>"
                    "<i>(%{y:.4f} × 9.81 = " + "</i><extra></extra>"
                ),
            ))
        fig_imu.add_hline(y=1.0, line_dash="dot", line_color="#2E7D32",
                          line_width=1.5,
                          annotation_text="1 g  (gravity when stationary)",
                          annotation_font_color="#4CAF50",
                          annotation_font_size=10,
                          annotation_position="right")
        fig_imu.add_hline(y=0.0, line_dash="dot", line_color="#37474F",
                          line_width=1)
        _chart_layout(fig_imu, height=270,
                      title=dict(
                          text="Foot Acceleration — LEFT FOOT  "
                               "<span style='font-size:11px;color:#607D8B'>"
                               "MPU6050 · units: g  (1 g = 9.81 m/s²) · "
                               "stationary foot ≈ |A| = 1 g</span>",
                          font=dict(size=13)),
                      margin=(50, 45, 55, 90))
        fig_imu.update_layout(
            yaxis=dict(title="Acceleration (g)", gridcolor="#1e2330",
                       zeroline=False),
            xaxis=dict(title="Time (s)", gridcolor="#1e2330"),
            legend=dict(orientation="h", y=-0.28, font=dict(size=11),
                        bgcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(fig_imu, use_container_width=True)

        # ══════════════════════════════════════════════════════════════════════
        #  ROW E — Angular velocity chart — EXISTING, improved
        # ══════════════════════════════════════════════════════════════════════
        fig_gyro = go.Figure()
        for vals, name, color, width in [
            (gx_v, "GX — roll rate (°/s)",  "#42A5F5", 1.4),
            (gy_v, "GY — pitch rate (°/s)", "#66BB6A", 1.4),
            (gz_v, "GZ — yaw rate (°/s)",   "#FFA726", 1.4),
            (gm_v, "|G| — total rate (°/s)","#FFFFFF", 2.6),
        ]:
            fig_gyro.add_trace(go.Scatter(
                x=t_imu_axis, y=vals.tolist(), mode="lines", name=name,
                line=dict(color=color, width=width, shape="spline"),
                hovertemplate=(
                    "Time: %{x:.2f} s<br>"
                    + name.split(" ")[0] + ": %{y:.3f} °/s<extra></extra>"
                ),
            ))
        fig_gyro.add_hline(y=0.0, line_dash="dot", line_color="#37474F",
                           line_width=1)
        _chart_layout(fig_gyro, height=240,
                      title=dict(
                          text="Foot Rotation Rate — LEFT FOOT  "
                               "<span style='font-size:11px;color:#607D8B'>"
                               "MPU6050 · units: °/s · "
                               "zero = no rotation</span>",
                          font=dict(size=13)),
                      margin=(50, 45, 55, 90))
        fig_gyro.update_layout(
            yaxis=dict(title="Angular velocity (°/s)", gridcolor="#1e2330",
                       zeroline=False),
            xaxis=dict(title="Time (s)", gridcolor="#1e2330"),
            legend=dict(orientation="h", y=-0.28, font=dict(size=11),
                        bgcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(fig_gyro, use_container_width=True)

        # ══════════════════════════════════════════════════════════════════════
        #  ROW F — Movement intensity sparkline (new — vs session baseline)
        # ══════════════════════════════════════════════════════════════════════
        if len(gait_hist) > 4:
            gh_x = list(range(len(gait_hist)))
            fig_gh = go.Figure()
            fig_gh.add_hrect(y0=0.95, y1=1.05,
                             fillcolor="rgba(67,160,71,0.07)", line_width=0)
            fig_gh.add_hline(
                y=gait_baseline_val, line_dash="dot", line_color="#43A047",
                line_width=1.5,
                annotation_text=f"Baseline {gait_baseline_val:.3f} g",
                annotation_font_color="#4CAF50",
                annotation_font_size=10,
                annotation_position="right",
            )
            fig_gh.add_trace(go.Scatter(
                x=gh_x, y=gait_hist,
                mode="lines", fill="tozeroy",
                fillcolor="rgba(66,165,245,0.08)",
                line=dict(color="#42A5F5", width=2.0, shape="spline"),
                hovertemplate="Reading %{x}<br>|Accel| mean: %{y:.4f} g<extra></extra>",
                name="|Accel| mean",
            ))
            _chart_layout(fig_gh, height=190,
                          title=dict(
                              text="Movement Intensity — Session History  "
                                   "<span style='font-size:11px;color:#607D8B'>"
                                   "mean |A| per window · baseline = session start</span>",
                              font=dict(size=12)),
                          margin=(44, 38, 55, 90))
            fig_gh.update_layout(
                yaxis=dict(title="|Accel| mean (g)", gridcolor="#1e2330"),
                xaxis=dict(title="Window #", gridcolor="#1e2330"),
                showlegend=False,
            )
            st.plotly_chart(fig_gh, use_container_width=True)

    else:
        st.markdown(
            '<div style="background:#1A1F2E;border:1px solid #2A3050;'
            'border-radius:10px;padding:20px;color:#607D8B;font-size:0.9rem">'
            '📡 <b>MPU6050 IMU not reporting data.</b><br>'
            '<span style="font-size:0.82rem">Check wiring (SDA→GPIO8, SCL→GPIO9) '
            'and firmware config. I²C address: 0x68 (AD0→GND).</span>'
            '</div>',
            unsafe_allow_html=True,
        )


    # ═══════════════════════════════════════════════════════════════════════════
    #  SECTION 6 — Regional Hotspot
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sh">⑥ Regional Hotspot</div>',
                unsafe_allow_html=True)

    hs_region   = hs.get("region")
    hs_duration = hs.get("duration", 0.0)

    if hs_region:
        hs_col     = C["alert"] if hs_duration > 10 else C["monitor"]
        hs_dur_s   = f"{hs_duration:.0f} s"
        hs_dur_lbl = " ⚠️ prolonged" if hs_duration > 10 else ""
        st.markdown(
            f'<div style="background:#0D1B2A;border:1px solid {hs_col};'
            f'border-radius:12px;padding:16px 20px;margin-bottom:12px">'
            f'<div style="color:{hs_col};font-size:1.1rem;font-weight:800">'
            f'🔥 Hotspot: {hs_region}{hs_dur_lbl}</div>'
            f'<div style="color:#ccc;margin-top:6px;font-size:0.9rem">'
            f'<b>Reason:</b> {hs_reason}</div>'
            f'<div style="color:#888;margin-top:4px;font-size:0.85rem">'
            f'Duration: <b style="color:{hs_col}">{hs_dur_s}</b></div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="background:#0D1B2A;border:1px solid #2A3050;'
            'border-radius:12px;padding:16px 20px;margin-bottom:12px">'
            '<div style="color:#43A047;font-size:1rem;font-weight:700">'
            '✅ No hotspot detected</div>'
            '<div style="color:#888;margin-top:6px;font-size:0.85rem">'
            'Load distribution within normal range.</div></div>',
            unsafe_allow_html=True,
        )

    # ═══════════════════════════════════════════════════════════════════════════
    #  SECTION 7 — Personal Baseline Comparison
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sh">⑦ Personal Baseline Comparison</div>',
                unsafe_allow_html=True)

    load_history = st.session_state[_LOAD_HIST_KEY]
    risk_history = st.session_state[_RISK_HIST_KEY]

    if len(load_history) > 10:
        session_baseline_load = float(np.mean(load_history[:min(40, len(load_history))]))
        current_window_load   = float(np.mean(load_history[-min(20, len(load_history)):]))
        load_dev_pct          = ((current_window_load - session_baseline_load)
                                  / max(session_baseline_load, 1) * 100)
        load_dev_col = (C["alert"]   if abs(load_dev_pct) > 30 else
                        C["monitor"] if abs(load_dev_pct) > 15 else C["normal"])

        bl1, bl2, bl3, bl4 = st.columns(4)
        bl1.markdown(_hw_metric_card("Session Baseline Load",
                                     f"{_adc_to_proxy(session_baseline_load):.0f}",
                                     sub=f"{_PROXY_ABBR} · first 2 s", color="#90CAF9",
                                     border="#2A3050", icon="📐"),
                     unsafe_allow_html=True)
        bl2.markdown(_hw_metric_card("Current Window Load",
                                     f"{_adc_to_proxy(current_window_load):.0f}",
                                     sub=f"{_PROXY_ABBR} · last {window_s:.0f} s",
                                     color=C["accent"], border="#2A3050", icon="📊"),
                     unsafe_allow_html=True)
        bl3.markdown(_hw_metric_card("Deviation",
                                     f"{load_dev_pct:+.1f}%",
                                     sub="positive = higher than baseline",
                                     color=load_dev_col, border="#2A3050", icon="Δ"),
                     unsafe_allow_html=True)
        if risk_history:
            session_mean_risk = float(np.mean(risk_history))
            risk_mean_level = ("ALERT" if session_mean_risk >= 60 else
                               "MONITOR" if session_mean_risk >= 30 else "NORMAL")
            bl4.markdown(_hw_metric_card("Session Mean Risk",
                                         f"{session_mean_risk:.1f}/100",
                                         sub=f"over {len(risk_history)} readings",
                                         color=LEVEL_COLOR.get(risk_mean_level, C["normal"]),
                                         border="#2A3050", icon="📈"),
                         unsafe_allow_html=True)

        if len(risk_history) > 2:
            fig_rh = go.Figure()
            rh_x   = list(range(len(risk_history)))
            fig_rh.add_hrect(y0=0,  y1=30,  fillcolor="rgba(67,160,71,0.07)",  line_width=0)
            fig_rh.add_hrect(y0=30, y1=60,  fillcolor="rgba(251,140,0,0.07)",  line_width=0)
            fig_rh.add_hrect(y0=60, y1=100, fillcolor="rgba(229,57,53,0.07)",  line_width=0)
            fig_rh.add_hline(y=30, line_dash="dash", line_color=C["monitor"],
                             annotation_text="MONITOR", annotation_font_color=C["monitor"],
                             annotation_position="right")
            fig_rh.add_hline(y=60, line_dash="dash", line_color=C["alert"],
                             annotation_text="ACTION", annotation_font_color=C["alert"],
                             annotation_position="right")
            fig_rh.add_trace(go.Scatter(
                x=rh_x, y=risk_history, mode="lines", fill="tozeroy",
                fillcolor="rgba(21,101,192,0.12)",
                line=dict(color=C["accent"], width=2.2, shape="spline"),
                hovertemplate="Reading %{x}<br>Risk: %{y:.1f}/100<extra></extra>",
            ))
            _chart_layout(fig_rh, height=200,
                          title=dict(text="Risk Score — Session History",
                                     font=dict(size=13)),
                          margin=(40, 35, 50, 80))
            fig_rh.update_layout(yaxis=dict(range=[0, 100], title="Risk Score"),
                                  xaxis_title="Reading #")
            st.plotly_chart(fig_rh, use_container_width=True)

        if len(load_history) > 4:
            lh_pkpa = [_adc_to_proxy(v) for v in load_history]
            lh_base = _adc_to_proxy(session_baseline_load)
            fig_lh  = go.Figure()
            fig_lh.add_hline(y=lh_base, line_dash="dot", line_color="#43A047",
                              annotation_text=f"Baseline {lh_base:.0f} {_PROXY_ABBR}",
                              annotation_font_color="#43A047", annotation_position="right")
            fig_lh.add_trace(go.Scatter(
                y=lh_pkpa, mode="lines", fill="tozeroy",
                fillcolor="rgba(0,176,255,0.07)",
                line=dict(color="#1E88E5", width=1.8, shape="spline"),
                hovertemplate="Reading %{x}<br>Load: %{y:.0f} p-kPa<extra></extra>",
            ))
            _chart_layout(fig_lh, height=180,
                          title=dict(text=f"Session Load History ({_PROXY_ABBR})",
                                     font=dict(size=12)),
                          margin=(36, 35, 50, 80))
            fig_lh.update_layout(yaxis_title=f"Load ({_PROXY_ABBR})",
                                  xaxis_title="Reading #")
            st.plotly_chart(fig_lh, use_container_width=True)
    else:
        st.info("Collecting session baseline — keep the insole active for a few seconds…")

    # ═══════════════════════════════════════════════════════════════════════════
    #  SECTION 8 — Explainable Risk Breakdown & Insights
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sh">⑧ Risk Breakdown &amp; Insights</div>',
                unsafe_allow_html=True)

    if rr is None:
        st.info("Collecting data… need at least 2 packets for risk analysis.")
    else:
        lc = LEVEL_COLOR[rr.risk_level]
        ri1, ri2 = st.columns([1, 2])
        with ri1:
            st.plotly_chart(gauge(rr.risk_score, "Risk Indicator"),
                            use_container_width=True)
        with ri2:
            if not rr.contributing_factors:
                st.markdown(
                    '<div style="background:#162618;border:1px solid #43A047;'
                    'border-radius:8px;padding:14px 18px;color:#81C784;font-size:0.95rem">'
                    '✅ <b>All clear.</b> No risk factors currently triggered. '
                    'Load, pressure, and gait are within normal ranges.</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div style="color:#ccc;font-size:0.88rem;margin-bottom:8px">'
                    f'<b style="color:{lc}">{len(rr.contributing_factors)} '
                    f'factor{"s" if len(rr.contributing_factors) != 1 else ""} '
                    f'contributing</b> to the risk score:</div>',
                    unsafe_allow_html=True,
                )
            _risk_factor_rows(rr)

        rec_icon = "💡" if rr.risk_level == "NORMAL" else (
                   "⚠️" if rr.risk_level == "MONITOR" else "🚨")
        st.markdown(
            f'<div style="background:#0D1B2A;border-left:4px solid {lc};'
            f'border-radius:6px;padding:14px 18px;color:#ddd;margin-top:14px">'
            f'{rec_icon} <b>Recommended Action:</b><br>'
            f'<span style="color:#ccc">{rr.recommended_action}</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="background:#1A1F2E;border-left:3px solid #607D8B;'
            'border-radius:4px;padding:8px 14px;color:#78909C;'
            'font-size:0.78rem;margin-top:8px">'
            '⚙ <b>Single LEFT-foot prototype:</b> Bilateral asymmetry rules '
            'are inactive — they require two insoles. All single-foot rules '
            '(peak load, PTI, forefoot/heel overload, gait variability, '
            'persistence) are fully active.</div>',
            unsafe_allow_html=True,
        )

    # ═══════════════════════════════════════════════════════════════════════════
    #  LED / ALERT STATUS & DISCLAIMER FOOTER
    # ═══════════════════════════════════════════════════════════════════════════
    led_state = rr.risk_level if rr else "COLLECTING"
    led_map   = {
        "NORMAL":     ("🟢 LED: GREEN — Normal",           "#43A047"),
        "MONITOR":    ("🟡 LED: AMBER — Monitor",          "#FB8C00"),
        "ALERT":      ("🔴 LED: RED — Action Indicated",   "#E53935"),
        "COLLECTING": ("⚪ LED: OFF — Collecting data",    "#607D8B"),
    }
    led_text, led_c = led_map.get(led_state, led_map["COLLECTING"])

    st.markdown(
        f'<div style="background:#0A1628;border:1px solid {led_c};'
        f'border-radius:10px;padding:12px 20px;margin-top:16px;'
        f'display:flex;align-items:center;gap:16px;flex-wrap:wrap">'
        f'<span style="color:{led_c};font-size:1.1rem;font-weight:800">'
        f'{led_text}</span>'
        f'<span style="color:#607D8B;font-size:0.8rem;margin-left:auto">'
        f'ESP32 on-board LED mirrors this state via firmware alert.cpp</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="disc" style="margin-top:12px">'
        '⚠ EXPERIMENTAL PROTOTYPE — Not for clinical use. '
        'FSR values are uncalibrated ADC-based proxies, not clinical kPa. '
        'SoleSense does not diagnose any medical condition. '
        'All thresholds are demo values only.</div>',
        unsafe_allow_html=True,
    )

    # ── auto-refresh ──────────────────────────────────────────────────────────
    _time.sleep(int(refresh_s))
    st.rerun()



# ═════════════════════════════════════════════════════════════════════════════
#  Navigation & entry point
# ═════════════════════════════════════════════════════════════════════════════

def main():
    _css()

    # Sidebar navigation
    with st.sidebar:
        st.markdown(
            '<div style="background:linear-gradient(135deg,#1565C0 0%,#0D47A1 100%);'
            'border-radius:10px;padding:14px 18px;margin-bottom:18px;">'
            '<span style="color:white;font-size:1.3rem;font-weight:900;'
            'letter-spacing:3px">👟 SOLESENSE</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        page = st.radio(
            "Navigation",
            ["🏠  Quick Analysis",
             "📊  Dataset Explorer",
             "📡  Live Hardware"],
            label_visibility="collapsed",
        )
        st.markdown("---")

    if page == "🏠  Quick Analysis":
        page_quick_analysis()
    elif page == "📊  Dataset Explorer":
        page_dataset_explorer()
    else:
        page_live_hardware()

    st.markdown(
        '<div class="footer">SoleSense · Demo Prototype · '
        'StepUP-P150 Dataset · University of New Brunswick 2023–2024</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__" or True:
    main()
