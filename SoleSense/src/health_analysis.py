"""
SoleSense — src/health_analysis.py
=====================================
Stateful health analysis engine for the Live Hardware dashboard.

Converts raw sensor packets into a PersonalisedFootReport that answers:
  1. WHERE is the concern?
  2. WHAT is abnormal?
  3. HOW SEVERE is the deviation from normal?
  4. HOW LONG has it persisted?
  5. IS IT GETTING BETTER OR WORSE?
  6. IS IT DIFFERENT FROM THE USER'S PERSONAL BASELINE?
  7. WHAT ACTION SHOULD THE USER TAKE?
  8. HAS THE CONDITION IMPROVED AFTER THE ALERT?

Architecture
------------
  Raw packets from SoleSenseReceiver
      ↓
  HealthAnalysisEngine.update(packets)   ← called every dashboard refresh
      ↓
  PersonalisedFootReport                  ← single dataclass, all derived indicators
      ↓
  render_health_analysis(report, st)      ← all Streamlit rendering lives here

⚠ NOT a medical device. All thresholds are experimental prototype values.
  This system does not diagnose any medical condition.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
#  Configurable thresholds — edit here, nowhere else
# ─────────────────────────────────────────────────────────────────────────────

# FSR scaling (must match hardware_input.py)
FSR_ADC_MAX:   int   = 4095
FSR_SCALE_KPA: float = 600.0

# Load thresholds (as fraction of max possible)
LOAD_ELEVATED_FRAC:    float = 0.25   # >25% of full-scale = "elevated"
LOAD_HIGH_FRAC:        float = 0.55   # >55% = "high"
FOREFOOT_OVERLOAD_FRAC: float = 0.65  # forefoot carrying >65% of total = overload
HEEL_OVERLOAD_FRAC:     float = 0.70  # heel carrying >70% of total = overload

# Persistence classification
TRANSIENT_SECS:   float = 30.0    # < 30 s   → TRANSIENT
REPEATED_SECS:    float = 120.0   # 30–120 s → REPEATED
PERSISTENT_SECS:  float = 300.0   # > 5 min  → PERSISTENT (MONITOR trigger)

# Temperature thresholds (°C, absolute deviation from personal baseline)
TEMP_DEVIATION_MONITOR:  float = 0.8   # > 0.8 °C above baseline → MONITOR
TEMP_DEVIATION_ACTION:   float = 1.5   # > 1.5 °C → contributes to ACTION
TEMP_RISING_RATE:        float = 0.03  # °C/min — gradual rise threshold

# Personal baseline warm-up — need at least N seconds before baseline is valid
BASELINE_WARMUP_S:      float = 30.0
# How many seconds of recent history used for "current" readings
CURRENT_WINDOW_S:       float = 10.0
# Rolling baseline window (most recent calm period)
BASELINE_WINDOW_S:      float = 60.0

# Motion / activity thresholds (acceleration magnitude in g)
ACCEL_REST_MAX:   float = 0.12   # < 0.12 g → REST
ACCEL_WALK_MIN:   float = 0.12   # ≥ 0.12 g → WALKING/ACTIVE
ACCEL_HIGH_MIN:   float = 0.60   # ≥ 0.60 g → HIGH ACTIVITY

# Sensor quality
STALE_PACKET_S:   float = 5.0    # > 5 s since last packet → STALE
NOISY_FSR_RANGE:  int   = 50     # if min/max spread < 50 ADC at full load → suspicious
VALID_TEMP_MIN:   float = 15.0   # below → sensor error
VALID_TEMP_MAX:   float = 45.0   # above → sensor error

# ACTION trigger: persistence_secs >= this AND load is elevated AND temp deviates
ACTION_PERSIST_SECS:  float = PERSISTENT_SECS
ACTION_NEED_TEMP_DEV: float = TEMP_DEVIATION_MONITOR  # temp must also deviate for ACTION

# Recovery: how many seconds of reduced load counts as "recovering"
RECOVERY_SECS: float = 20.0


# ─────────────────────────────────────────────────────────────────────────────
#  Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SensorQuality:
    fsr1_ok:    bool = True
    fsr2_ok:    bool = True
    temp1_ok:   bool = True
    temp2_ok:   bool = False   # second sensor may not be present
    mpu_ok:     bool = True
    stale:      bool = False
    overall_ok: bool = True
    detail:     str  = ""


@dataclass
class LoadDistribution:
    forefoot_pct: float = 0.0   # 0–100
    heel_pct:     float = 0.0
    dominant_region: str = "balanced"
    baseline_forefoot_pct: float = 0.0
    baseline_heel_pct:     float = 0.0
    forefoot_deviation_pct: float = 0.0   # current − baseline, percentage points
    heel_deviation_pct:     float = 0.0
    peak_load_pct:    float = 0.0   # current max FSR as % of FSR_SCALE_KPA
    session_peak_pct: float = 0.0
    avg_load_pct:     float = 0.0


@dataclass
class PressureTimeExposure:
    region:           str   = "forefoot"
    current_load_pct: float = 0.0
    baseline_pct:     float = 0.0
    deviation_pct:    float = 0.0
    duration_s:       float = 0.0
    state:            str   = "normal"    # normal / elevated / persistent
    classification:   str   = "normal"   # transient / repeated / persistent


@dataclass
class TemperatureAnalysis:
    temp1_c:        Optional[float] = None
    temp2_c:        Optional[float] = None
    baseline_c:     Optional[float] = None
    deviation_c:    float = 0.0
    trend:          str   = "stable"    # stable / rising / falling / persistently_elevated
    persistence_s:  float = 0.0
    state:          str   = "normal"    # normal / monitor / action


@dataclass
class MotionContext:
    activity:     str   = "unknown"   # rest / standing / walking / active
    steps:        int   = 0
    cadence_spm:  float = 0.0
    intensity:    str   = "low"       # low / normal / high
    accel_mag:    float = 0.0
    step_std_s:   float = 0.0


@dataclass
class PersonalBaseline:
    valid:                 bool  = False
    pressure_baseline_pct: float = 0.0
    temp_baseline_c:       Optional[float] = None
    accel_baseline_g:      float = 0.0
    press_deviation_pct:   float = 0.0
    temp_deviation_c:      float = 0.0
    accel_deviation_pct:   float = 0.0
    overall_deviation:     str   = "within baseline"


@dataclass
class RegionalConcern:
    region:          str   = "none"
    pressure_state:  str   = "normal"
    exposure_state:  str   = "normal"
    temp_deviation_c: float = 0.0
    baseline_dev_pct: float = 0.0
    persistence_s:   float = 0.0
    confidence:      str   = "low data"


@dataclass
class RecoveryRecord:
    trigger_time:      float = 0.0
    before_load_pct:   float = 0.0
    before_temp_c:     Optional[float] = None
    current_load_pct:  float = 0.0
    current_temp_c:    Optional[float] = None
    recovering:        bool  = False
    improved:          bool  = False
    detail:            str   = ""


@dataclass
class TimelineEvent:
    wall_time:  float = 0.0
    label:      str   = ""
    status:     str   = "NORMAL"   # NORMAL / MONITOR / ACTION / RECOVERING


@dataclass
class SessionSummary:
    monitoring_secs:   float = 0.0
    steps:             int   = 0
    peak_load_pct:     float = 0.0
    avg_load_pct:      float = 0.0
    highest_region:    str   = "forefoot"
    temp1_min:         Optional[float] = None
    temp1_max:         Optional[float] = None
    persist_events:    int   = 0
    monitor_events:    int   = 0
    action_events:     int   = 0
    session_trend:     str   = "stable"


@dataclass
class PersonalisedFootReport:
    # ── Overall status ──────────────────────────────────────────────────────
    status:         str = "NORMAL"   # NORMAL / MONITOR / ACTION
    region:         str = "none"
    primary_reason: str = ""
    secondary_signal: str = ""
    recommendation: str = ""
    trend_5min:     str = "stable"   # improving / stable / worsening

    # ── Sub-analyses ────────────────────────────────────────────────────────
    quality:     SensorQuality         = field(default_factory=SensorQuality)
    load:        LoadDistribution      = field(default_factory=LoadDistribution)
    exposure:    PressureTimeExposure  = field(default_factory=PressureTimeExposure)
    temperature: TemperatureAnalysis   = field(default_factory=TemperatureAnalysis)
    motion:      MotionContext         = field(default_factory=MotionContext)
    baseline:    PersonalBaseline      = field(default_factory=PersonalBaseline)
    concern:     RegionalConcern       = field(default_factory=RegionalConcern)
    recovery:    Optional[RecoveryRecord] = None

    # ── Session-level ────────────────────────────────────────────────────────
    session:     SessionSummary        = field(default_factory=SessionSummary)
    events:      list                  = field(default_factory=list)

    # ── Explainable factor flags (for the factor panel) ────────────────────
    flag_pressure:     str = "normal"   # normal / elevated / high
    flag_exposure:     str = "normal"
    flag_temperature:  str = "normal"
    flag_temp_trend:   str = "stable"
    flag_motion:       str = "normal"
    flag_baseline_dev: str = "normal"
    flag_persistence:  str = "none"     # none / transient / repeated / persistent


# ─────────────────────────────────────────────────────────────────────────────
#  HealthAnalysisEngine — stateful, call update() every refresh
# ─────────────────────────────────────────────────────────────────────────────

class HealthAnalysisEngine:
    """
    Stateful analysis engine.  Instantiate once and store in st.session_state.
    Call update(packets) on every dashboard refresh.

    Parameters
    ----------
    session_start : float   wall-clock time the session started
    """

    def __init__(self, session_start: Optional[float] = None):
        self._start     = session_start or time.time()
        self._steps     = 0

        # Rolling histories (wall-clock keyed)
        self._press_hist:  deque = deque(maxlen=4000)   # (t, load_pct)
        self._temp_hist:   deque = deque(maxlen=4000)   # (t, temp_c)
        self._status_hist: deque = deque(maxlen=600)    # (t, status_str)

        # Baseline accumulators
        self._baseline_press_samples: list = []
        self._baseline_temp_samples:  list = []
        self._baseline_frozen = False
        self._baseline_press: Optional[float] = None
        self._baseline_temp:  Optional[float] = None
        self._baseline_accel: Optional[float] = None

        # Persistence tracking
        self._elevated_since:  Optional[float] = None   # wall-clock
        self._temp_elevated_since: Optional[float] = None

        # Session stats
        self._session_peak_pct: float = 0.0
        self._session_loads:    list  = []
        self._monitor_events:   int   = 0
        self._action_events:    int   = 0
        self._persist_events:   int   = 0

        # Recovery tracking
        self._last_action_time:  Optional[float] = None
        self._last_action_load:  Optional[float] = None
        self._last_action_temp:  Optional[float] = None
        self._recovery_active:   bool = False
        self._recovery_start_load: float = 0.0

        # Event timeline
        self._events: list[TimelineEvent] = []
        self._last_logged_status: str = ""

        # Step counting
        self._in_stance: bool = False
        self._last_step_t: float = 0.0
        self._step_times:  deque = deque(maxlen=20)

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, packets: list[dict],
               last_received_s: Optional[float] = None) -> PersonalisedFootReport:
        """
        Process the latest window of packets and return a full report.
        Call every dashboard refresh.
        """
        report = PersonalisedFootReport()
        now    = time.time()

        # ── 1. Sensor quality ─────────────────────────────────────────────────
        report.quality = self._check_quality(packets, last_received_s, now)

        if not packets:
            report.status = "NORMAL"
            report.primary_reason = "No sensor data yet."
            report.recommendation = "Continue normal monitoring."
            return report

        # ── 2. Extract current readings ───────────────────────────────────────
        latest  = packets[-1]
        fsr1    = float(latest.get("fsr1", 0))
        fsr2    = float(latest.get("fsr2", 0))
        total   = fsr1 + fsr2
        temp1   = latest.get("temperature")
        temp2   = latest.get("temperature2")
        ax      = latest.get("ax", 0.0)
        ay      = latest.get("ay", 0.0)
        az      = latest.get("az", 0.0)

        load_pct   = (total / (2 * FSR_ADC_MAX)) * 100.0  # 0–100%
        accel_mag  = math.sqrt(ax**2 + ay**2 + az**2)

        ff_pct = (fsr1 / total * 100) if total > 0 else 50.0
        hl_pct = (fsr2 / total * 100) if total > 0 else 50.0

        # packet-time "now" — use received_at of latest packet so historical
        # windows correctly compute elapsed persistence durations
        pkt_now = latest.get("received_at", now)

        # Compute window averages
        win_loads  = np.array([(p.get("fsr1",0)+p.get("fsr2",0))/(2*FSR_ADC_MAX)*100
                               for p in packets])
        win_ff     = np.array([(p.get("fsr1",0)/(p.get("fsr1",0)+p.get("fsr2",0)+1e-9)*100)
                               for p in packets])
        win_hl     = np.array([(p.get("fsr2",0)/(p.get("fsr1",0)+p.get("fsr2",0)+1e-9)*100)
                               for p in packets])
        win_accel  = np.array([math.sqrt(p.get("ax",0)**2+p.get("ay",0)**2+p.get("az",0)**2)
                               for p in packets])
        win_temps  = [p.get("temperature") for p in packets if p.get("temperature") is not None]

        # ── 3. Accumulate histories ───────────────────────────────────────────
        self._press_hist.append((pkt_now, load_pct))
        if temp1 is not None and VALID_TEMP_MIN <= temp1 <= VALID_TEMP_MAX:
            self._temp_hist.append((pkt_now, temp1))
        self._session_loads.append(load_pct)
        if load_pct > self._session_peak_pct:
            self._session_peak_pct = load_pct

        # ── 4. Step counting ─────────────────────────────────────────────────
        threshold_pct = LOAD_ELEVATED_FRAC * 100.0
        is_stance     = load_pct > threshold_pct
        if not self._in_stance and is_stance:
            self._steps += 1
            if self._last_step_t > 0:
                self._step_times.append(now - self._last_step_t)
            self._last_step_t = now
        self._in_stance = is_stance

        step_std = float(np.std(list(self._step_times))) if len(self._step_times) >= 3 else 0.0
        window_s_dur = len(packets) / 20.0
        cadence = (len([p for p in packets
                        if (p.get("fsr1",0)+p.get("fsr2",0))/(2*FSR_ADC_MAX)*100 > threshold_pct])
                   / window_s_dur * 60.0) if window_s_dur > 0 else 0.0

        # ── 5. Personal baseline ──────────────────────────────────────────────
        elapsed = now - self._start
        report.baseline = self._update_baseline(load_pct, temp1, accel_mag, elapsed)

        # ── 6. Load distribution ──────────────────────────────────────────────
        report.load = LoadDistribution(
            forefoot_pct = float(np.mean(win_ff)),
            heel_pct     = float(np.mean(win_hl)),
            dominant_region  = "forefoot" if float(np.mean(win_ff)) > float(np.mean(win_hl)) else "heel",
            baseline_forefoot_pct = self._baseline_press or 50.0,
            baseline_heel_pct     = 100.0 - (self._baseline_press or 50.0),
            forefoot_deviation_pct = float(np.mean(win_ff)) - (self._baseline_press or float(np.mean(win_ff))),
            heel_deviation_pct     = float(np.mean(win_hl)) - (100.0 - (self._baseline_press or float(np.mean(win_hl)))),
            peak_load_pct    = load_pct,
            session_peak_pct = self._session_peak_pct,
            avg_load_pct     = float(np.mean(self._session_loads)) if self._session_loads else 0.0,
        )

        # ── 7. Pressure-time exposure + persistence ───────────────────────────
        # ── 7. Pressure-time exposure + persistence ───────────────────────────────
        # Use the timestamp of the latest packet as "now" for persistence
        # so that historical packet windows produce correct durations.
        pkt_now  = latest.get("received_at", now)
        elevated = load_pct > LOAD_ELEVATED_FRAC * 100.0
        if elevated:
            if self._elevated_since is None:
                self._elevated_since = pkt_now
        else:
            if self._elevated_since is not None:
                dur = pkt_now - self._elevated_since
                if dur >= PERSISTENT_SECS:
                    self._persist_events += 1
            self._elevated_since = None

        elev_secs = (pkt_now - self._elevated_since) if self._elevated_since else 0.0
        bl_press  = (self._baseline_press or float(np.mean(win_loads)))
        dev_pp    = load_pct - bl_press

        if elev_secs >= PERSISTENT_SECS:
            exp_state  = "persistent"
            exp_class  = "persistent"
        elif elev_secs >= REPEATED_SECS:
            exp_state  = "elevated"
            exp_class  = "repeated"
        elif elev_secs >= TRANSIENT_SECS:
            exp_state  = "elevated"
            exp_class  = "transient"
        else:
            exp_state  = "normal"
            exp_class  = "normal"

        report.exposure = PressureTimeExposure(
            region           = report.load.dominant_region,
            current_load_pct = load_pct,
            baseline_pct     = bl_press,
            deviation_pct    = dev_pp,
            duration_s       = elev_secs,
            state            = exp_state,
            classification   = exp_class,
        )

        # ── 8. Temperature analysis ───────────────────────────────────────────
        report.temperature = self._analyse_temperature(temp1, temp2, pkt_now)

        # ── 9. Motion context ─────────────────────────────────────────────────
        mean_accel = float(win_accel.mean())
        if mean_accel < ACCEL_REST_MAX:
            activity  = "standing" if load_pct > LOAD_ELEVATED_FRAC * 100 else "rest"
            intensity = "low"
        elif mean_accel >= ACCEL_HIGH_MIN:
            activity  = "active"
            intensity = "high"
        else:
            activity  = "walking"
            intensity = "normal"

        report.motion = MotionContext(
            activity    = activity,
            steps       = self._steps,
            cadence_spm = cadence,
            intensity   = intensity,
            accel_mag   = mean_accel,
            step_std_s  = step_std,
        )

        # ── 10. Baseline deviation ────────────────────────────────────────────
        if report.baseline.valid:
            bl_dev = abs(dev_pp)
            if bl_dev > 20:
                report.baseline.overall_deviation = "notably above baseline"
            elif bl_dev > 10:
                report.baseline.overall_deviation = "slightly above baseline"
            else:
                report.baseline.overall_deviation = "within baseline"

        # ── 11. Regional concern ──────────────────────────────────────────────
        concern_region = report.load.dominant_region
        report.concern = RegionalConcern(
            region           = f"LEFT {concern_region.upper()}",
            pressure_state   = exp_state,
            exposure_state   = exp_class,
            temp_deviation_c = report.temperature.deviation_c,
            baseline_dev_pct = dev_pp,
            persistence_s    = elev_secs,
            confidence       = "high data consistency" if report.quality.overall_ok
                               else "low — sensor data quality issues",
        )

        # ── 12. Activity-context-aware flag filtering ─────────────────────────
        # During REST, pressure readings are expected to be low — don't alarm
        in_rest = activity == "rest"

        # ── 13. Explainable factor flags ──────────────────────────────────────
        report.flag_pressure    = (
            "high" if load_pct > LOAD_HIGH_FRAC * 100 else
            ("elevated" if load_pct > LOAD_ELEVATED_FRAC * 100 else "normal")
        )
        report.flag_exposure    = exp_state
        report.flag_temperature = report.temperature.state
        report.flag_temp_trend  = report.temperature.trend
        report.flag_motion      = intensity
        report.flag_baseline_dev = (
            "elevated" if (report.baseline.valid and abs(dev_pp) > 10) else "normal"
        )
        report.flag_persistence = exp_class

        # ── 14. Overall status fusion ─────────────────────────────────────────
        report.status, report.primary_reason, report.secondary_signal = \
            self._fuse_status(report, in_rest, elev_secs)

        # ── 15. Recommendation ────────────────────────────────────────────────
        report.recommendation = _recommendation_text(report.status)

        # ── 16. Recovery tracking ─────────────────────────────────────────────
        report.recovery = self._update_recovery(report.status, load_pct, temp1, pkt_now)

        # ── 17. 5-min trend ───────────────────────────────────────────────────
        report.trend_5min = self._compute_trend_5min(pkt_now)

        # ── 18. Session summary ───────────────────────────────────────────────
        report.session = self._build_session_summary(pkt_now)
        report.events  = list(self._events[-20:])  # last 20 events

        # ── 19. Log events ────────────────────────────────────────────────────
        self._log_event(report.status, load_pct, report.motion.activity, pkt_now)

        # ── 20. Status history ────────────────────────────────────────────────
        self._status_hist.append((pkt_now, report.status))

        return report

    # ── Personal baseline ─────────────────────────────────────────────────────

    def _update_baseline(self, load_pct, temp1, accel_mag, elapsed) -> PersonalBaseline:
        bl = PersonalBaseline()

        # Accumulate during warmup period, freeze after
        if not self._baseline_frozen:
            self._baseline_press_samples.append(load_pct)
            if temp1 is not None and VALID_TEMP_MIN <= temp1 <= VALID_TEMP_MAX:
                self._baseline_temp_samples.append(temp1)
            if elapsed >= BASELINE_WARMUP_S and len(self._baseline_press_samples) >= 20:
                self._baseline_press = float(np.mean(self._baseline_press_samples))
                self._baseline_temp  = (float(np.mean(self._baseline_temp_samples))
                                        if self._baseline_temp_samples else None)
                self._baseline_accel = accel_mag
                self._baseline_frozen = True

        if self._baseline_press is not None:
            bl.valid                 = True
            bl.pressure_baseline_pct = self._baseline_press
            bl.temp_baseline_c       = self._baseline_temp
            bl.accel_baseline_g      = self._baseline_accel or accel_mag
            bl.press_deviation_pct   = load_pct - self._baseline_press
            bl.temp_deviation_c      = ((temp1 - self._baseline_temp)
                                        if temp1 is not None and self._baseline_temp else 0.0)
            bl.accel_deviation_pct   = ((accel_mag - bl.accel_baseline_g)
                                        / (bl.accel_baseline_g + 1e-6) * 100.0)

        return bl

    # ── Temperature analysis ──────────────────────────────────────────────────

    def _analyse_temperature(self, temp1, temp2, now) -> TemperatureAnalysis:
        ta = TemperatureAnalysis(temp1_c=temp1, temp2_c=temp2)

        valid_t1 = temp1 is not None and VALID_TEMP_MIN <= temp1 <= VALID_TEMP_MAX
        if not valid_t1:
            return ta

        ta.baseline_c = self._baseline_temp

        if self._baseline_temp:
            ta.deviation_c = temp1 - self._baseline_temp
        else:
            ta.deviation_c = 0.0

        # Trend from temperature history
        if len(self._temp_hist) >= 10:
            recent   = [v for t, v in self._temp_hist if now - t <= 300]   # 5 min
            if len(recent) >= 6:
                first_half = np.mean(recent[:len(recent)//2])
                second_half = np.mean(recent[len(recent)//2:])
                delta = second_half - first_half
                if delta > 0.5:
                    ta.trend = "rising"
                elif delta < -0.5:
                    ta.trend = "falling"
                else:
                    ta.trend = "stable"

                if ta.deviation_c > TEMP_DEVIATION_MONITOR and ta.trend in ("stable", "rising"):
                    ta.trend = "persistently_elevated"
        else:
            ta.trend = "stable"

        # Elevation persistence
        elevated_t = (temp1 > (self._baseline_temp or temp1) + TEMP_DEVIATION_MONITOR
                      if self._baseline_temp else False)
        if elevated_t:
            if self._temp_elevated_since is None:
                self._temp_elevated_since = now
            ta.persistence_s = now - self._temp_elevated_since
        else:
            self._temp_elevated_since = None
            ta.persistence_s = 0.0

        # State
        if ta.deviation_c >= TEMP_DEVIATION_ACTION or ta.persistence_s >= PERSISTENT_SECS:
            ta.state = "action"
        elif ta.deviation_c >= TEMP_DEVIATION_MONITOR or ta.trend == "persistently_elevated":
            ta.state = "monitor"
        else:
            ta.state = "normal"

        return ta

    # ── Status fusion ─────────────────────────────────────────────────────────

    def _fuse_status(self, report: PersonalisedFootReport,
                     in_rest: bool, elev_secs: float):
        load_pct   = report.load.peak_load_pct
        temp_state = report.temperature.state
        exp_class  = report.exposure.classification

        # During rest, suppress pressure alerts
        if in_rest:
            primary = "Sensor in rest state — no active loading."
            return "NORMAL", primary, "Continue monitoring."

        # ACTION: persistent loading + temperature deviation
        if (elev_secs >= ACTION_PERSIST_SECS
                and temp_state in ("monitor", "action")
                and report.quality.overall_ok):
            self._action_events += 1
            primary   = (f"Persistent elevated regional loading "
                         f"({int(elev_secs//60)} min {int(elev_secs%60)} s) "
                         f"with thermal deviation.")
            secondary = (f"Temperature deviation: "
                         f"{report.temperature.deviation_c:+.1f} °C above baseline."
                         if report.baseline.valid else
                         "Temperature elevated relative to current reading.")
            return "ACTION", primary, secondary

        # ACTION: extreme persistent loading alone
        if (elev_secs >= ACTION_PERSIST_SECS * 1.5
                and load_pct > LOAD_HIGH_FRAC * 100
                and report.quality.overall_ok):
            self._action_events += 1
            primary = (f"Sustained high regional loading for "
                       f"{int(elev_secs//60)} min {int(elev_secs%60)} s.")
            secondary = "No significant temperature deviation detected."
            return "ACTION", primary, secondary

        # MONITOR: meaningful persistence
        if elev_secs >= PERSISTENT_SECS:
            self._monitor_events += 1
            primary = (f"Elevated regional loading for "
                       f"{int(elev_secs//60)} min {int(elev_secs%60)} s.")
            secondary = ("Temperature within baseline." if temp_state == "normal"
                         else f"Temperature also deviating ({report.temperature.deviation_c:+.1f}°C).")
            return "MONITOR", primary, secondary

        # MONITOR: temperature alone
        if temp_state in ("monitor", "action"):
            self._monitor_events += 1
            primary   = (f"Thermal deviation: "
                         f"{report.temperature.deviation_c:+.1f}°C above baseline.")
            secondary = f"Trend: {report.temperature.trend.replace('_',' ')}."
            return "MONITOR", primary, secondary

        # MONITOR: notable baseline deviation (pressure)
        if (report.baseline.valid
                and abs(report.exposure.deviation_pct) > 20
                and load_pct > LOAD_ELEVATED_FRAC * 100):
            primary = (f"Pressure pattern {report.exposure.deviation_pct:+.0f}% "
                       f"above personal baseline.")
            secondary = f"Thermal indicator: {temp_state}."
            return "MONITOR", primary, secondary

        # NORMAL
        primary = "No current abnormal pattern detected."
        secondary = "All indicators within expected range."
        return "NORMAL", primary, secondary

    # ── Recovery tracking ─────────────────────────────────────────────────────

    def _update_recovery(self, status, load_pct, temp1, now) -> Optional[RecoveryRecord]:
        if status == "ACTION":
            if self._last_action_time is None:
                self._last_action_time  = now
                self._last_action_load  = load_pct
                self._last_action_temp  = temp1
                self._recovery_active   = False
            return None

        if self._last_action_time is None:
            return None

        rec = RecoveryRecord(
            trigger_time     = self._last_action_time,
            before_load_pct  = self._last_action_load or load_pct,
            before_temp_c    = self._last_action_temp,
            current_load_pct = load_pct,
            current_temp_c   = temp1,
        )

        load_reduced = load_pct < (self._last_action_load or 100) * 0.75
        if load_reduced:
            if not self._recovery_active:
                self._recovery_active   = True
                self._recovery_start_load = load_pct
            rec.recovering = True
            rec.improved   = load_pct < (self._last_action_load or 100) * 0.60
            rec.detail = (f"Regional loading has decreased from "
                          f"{self._last_action_load:.0f}% to {load_pct:.0f}% "
                          f"following the alert.")
        else:
            rec.detail = "Loading has not yet decreased following the alert."

        return rec

    # ── 5-min trend ───────────────────────────────────────────────────────────

    def _compute_trend_5min(self, now: float) -> str:
        recent = [(t, v) for t, v in self._press_hist if now - t <= 300]
        if len(recent) < 20:
            return "stable"
        first_q = np.mean([v for _, v in recent[:len(recent)//3]])
        last_q  = np.mean([v for _, v in recent[-len(recent)//3:]])
        delta   = last_q - first_q
        if delta > 5:
            return "worsening"
        elif delta < -5:
            return "improving"
        return "stable"

    # ── Session summary ───────────────────────────────────────────────────────

    def _build_session_summary(self, pkt_now: float) -> SessionSummary:
        temps  = [v for _, v in self._temp_hist]
        return SessionSummary(
            monitoring_secs = pkt_now - self._start,
            steps           = self._steps,
            peak_load_pct   = self._session_peak_pct,
            avg_load_pct    = float(np.mean(self._session_loads)) if self._session_loads else 0.0,
            highest_region  = "forefoot",
            temp1_min       = min(temps) if temps else None,
            temp1_max       = max(temps) if temps else None,
            persist_events  = self._persist_events,
            monitor_events  = self._monitor_events,
            action_events   = self._action_events,
            session_trend   = self._compute_trend_5min(pkt_now),
        )

    # ── Sensor quality ────────────────────────────────────────────────────────

    def _check_quality(self, packets, last_received_s, now) -> SensorQuality:
        q = SensorQuality()
        issues = []

        if not packets:
            q.overall_ok = False
            q.detail     = "No packets received."
            return q

        latest = packets[-1]

        # Stale check
        if last_received_s is not None and last_received_s > STALE_PACKET_S:
            q.stale      = True
            q.overall_ok = False
            issues.append(f"Data stale ({last_received_s:.0f} s since last packet)")

        # FSR validity
        fsr1 = latest.get("fsr1", -1)
        fsr2 = latest.get("fsr2", -1)
        if fsr1 < 0 or fsr1 > FSR_ADC_MAX:
            q.fsr1_ok = False; issues.append("FSR1 out of range")
        if fsr2 < 0 or fsr2 > FSR_ADC_MAX:
            q.fsr2_ok = False; issues.append("FSR2 out of range")

        # Temperature validity
        t1 = latest.get("temperature")
        if t1 is not None:
            if not (VALID_TEMP_MIN <= t1 <= VALID_TEMP_MAX):
                q.temp1_ok = False; issues.append(f"TEMP1 value {t1:.1f}°C out of range")
        t2 = latest.get("temperature2")
        if t2 is not None:
            q.temp2_ok = VALID_TEMP_MIN <= t2 <= VALID_TEMP_MAX

        # IMU check
        if all(abs(latest.get(a, 0.0)) < 1e-6 for a in ("ax","ay","az","gx","gy","gz")):
            q.mpu_ok = False; issues.append("MPU6050 all zeros — check connection")

        q.overall_ok = q.fsr1_ok and q.fsr2_ok and not q.stale
        q.detail     = "; ".join(issues) if issues else "All sensors nominal"
        return q

    # ── Event log ─────────────────────────────────────────────────────────────

    def _log_event(self, status, load_pct, activity, now):
        if status == self._last_logged_status:
            return
        label = {
            "NORMAL":  "Loading within normal range",
            "MONITOR": "Elevated loading detected",
            "ACTION":  "Action threshold reached",
        }.get(status, status)
        if activity == "walking":
            if status == "NORMAL" and self._last_logged_status == "":
                label = "Walking detected"
        if (self._last_logged_status in ("ACTION", "MONITOR")
                and status == "NORMAL"):
            label = "Loading reduced — returning to normal"
            status = "RECOVERING"
        self._events.append(TimelineEvent(
            wall_time = now,
            label     = label,
            status    = status,
        ))
        self._last_logged_status = status if status != "RECOVERING" else "NORMAL"

    def reset(self):
        """Reset session. Call when user starts a new monitoring session."""
        self.__init__()


# ─────────────────────────────────────────────────────────────────────────────
#  Recommendation text
# ─────────────────────────────────────────────────────────────────────────────

def _recommendation_text(status: str) -> str:
    if status == "NORMAL":
        return "Continue normal monitoring."
    elif status == "MONITOR":
        return ("Continue monitoring the affected region. "
                "If the pattern persists, reduce loading and consider "
                "appropriate clinical follow-up.")
    else:  # ACTION
        return ("Reduce loading on the affected region. "
                "Follow the configured prototype alert/offloading guidance "
                "and seek clinical advice if an abnormality persists or is "
                "accompanied by concerning symptoms. "
                "⚠ This is a prototype indicator, not a clinical assessment.")


# ─────────────────────────────────────────────────────────────────────────────
#  Streamlit rendering  (import app colour palette as C)
# ─────────────────────────────────────────────────────────────────────────────

def render_health_analysis(report: PersonalisedFootReport, C: dict):
    """
    Render the full health analysis into the Streamlit app.
    Pass the existing C colour palette dict from app.py.
    """
    import streamlit as st
    import plotly.graph_objects as go

    STATUS_COLOR = {
        "NORMAL":     C["normal"],
        "MONITOR":    C["monitor"],
        "ACTION":     C["alert"],
        "RECOVERING": C["accent"],
    }
    STATUS_ICON = {
        "NORMAL":     "🟢",
        "MONITOR":    "🟡",
        "ACTION":     "🔴",
        "RECOVERING": "🔵",
    }

    sc = STATUS_COLOR.get(report.status, C["neutral"])
    si = STATUS_ICON.get(report.status, "⚪")

    # ═════════════════════════════════════════════════════════════════════════
    # BLOCK 1 — Sensor Quality
    # ═════════════════════════════════════════════════════════════════════════
    q = report.quality
    with st.expander("🔍 Sensor Data Quality", expanded=not q.overall_ok):
        qc1, qc2, qc3 = st.columns(3)
        def _qbadge(ok, label):
            ic = "✓" if ok else "✗"
            cl = C["normal"] if ok else C["alert"]
            return f'<span style="color:{cl};font-weight:700">{ic} {label}</span>'

        qc1.markdown(
            _qbadge(q.fsr1_ok,  "FSR1 (Forefoot)") + "<br>" +
            _qbadge(q.fsr2_ok,  "FSR2 (Heel)"),
            unsafe_allow_html=True)
        qc2.markdown(
            _qbadge(q.temp1_ok, "TEMP1") + "<br>" +
            _qbadge(q.temp2_ok, "TEMP2"),
            unsafe_allow_html=True)
        qc3.markdown(
            _qbadge(q.mpu_ok,   "MPU6050") + "<br>" +
            _qbadge(not q.stale,"Data fresh"),
            unsafe_allow_html=True)

        if not q.overall_ok:
            st.warning(f"⚠ Data quality issue: {q.detail}  "
                       f"Analysis confidence is reduced.")
        else:
            st.caption(f"✓ {q.detail}")

    # ═════════════════════════════════════════════════════════════════════════
    # BLOCK 2 — Overall Foot Status (hero card)
    # ═════════════════════════════════════════════════════════════════════════
    trend_arrow = {"improving": "↗ Improving", "worsening": "↘ Worsening",
                   "stable": "→ Stable"}.get(report.trend_5min, "→ Stable")

    st.markdown(
        f'<div style="background:#0D1B2A;border:3px solid {sc};border-radius:14px;'
        f'padding:22px 28px;margin:10px 0 18px 0">'
        f'<div style="font-size:2.4rem;font-weight:900;color:{sc}">'
        f'{si}  FOOT STATUS: {report.status}</div>'
        f'<div style="color:white;font-size:1.05rem;margin:8px 0 4px 0">'
        f'{report.primary_reason}</div>'
        f'<div style="color:#90CAF9;font-size:0.9rem">{report.secondary_signal}</div>'
        f'<div style="margin-top:12px;display:flex;gap:24px">'
        f'<span style="color:#888;font-size:0.85rem">Region: '
        f'<b style="color:#90CAF9">{report.concern.region}</b></span>'
        f'<span style="color:#888;font-size:0.85rem">Trend: '
        f'<b style="color:#90CAF9">{trend_arrow}</b></span>'
        f'<span style="color:#888;font-size:0.85rem">Activity: '
        f'<b style="color:#90CAF9">{report.motion.activity.upper()}</b></span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # ═════════════════════════════════════════════════════════════════════════
    # BLOCK 3 — Explainable factor panel
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sh">① Explainable Analysis</div>',
                unsafe_allow_html=True)

    def _factor_row(label, state, detail):
        color_map = {
            "normal": C["normal"], "elevated": C["monitor"],
            "high": C["alert"],    "persistent": C["alert"],
            "repeated": C["monitor"], "transient": C["neutral"],
            "stable": C["normal"], "rising": C["alert"],
            "falling": C["accent"], "persistently_elevated": C["alert"],
            "monitor": C["monitor"], "action": C["alert"],
            "low": C["normal"],    "none": C["normal"],
        }
        ic = {"normal":"🟢","stable":"🟢","low":"🟢","none":"🟢",
              "elevated":"🟡","repeated":"🟡","transient":"🟡","monitor":"🟡",
              "high":"🔴","persistent":"🔴","persistently_elevated":"🔴",
              "action":"🔴","rising":"🔴","worsening":"🔴"
              }.get(state, "⚪")
        c = color_map.get(state, C["neutral"])
        return (f'<div style="display:flex;justify-content:space-between;'
                f'padding:6px 0;border-bottom:1px solid #1e2330">'
                f'<span style="color:#C8D4F0">{label}</span>'
                f'<span style="color:{c};font-weight:700">{ic} {state.replace("_"," ").upper()}</span>'
                f'</div>'
                f'<div style="color:#607D8B;font-size:0.78rem;padding-bottom:6px">{detail}</div>')

    lp   = report.load
    exp  = report.exposure
    temp = report.temperature

    factors_html = (
        _factor_row("PRESSURE",
            report.flag_pressure,
            f"Current: {lp.peak_load_pct:.0f}% | "
            f"Forefoot: {lp.forefoot_pct:.0f}% | Heel: {lp.heel_pct:.0f}%") +
        _factor_row("PRESSURE-TIME EXPOSURE",
            report.flag_exposure,
            f"Duration elevated: {exp.duration_s/60:.1f} min | "
            f"Classification: {exp.classification}") +
        _factor_row("TEMPERATURE",
            report.flag_temperature,
            (f"TEMP1: {temp.temp1_c:.1f}C | "
             f"Baseline: {'%.1fC' % temp.baseline_c if temp.baseline_c is not None else 'warming up'} | "
             f"Dev: {temp.deviation_c:+.1f}C")
            if temp.temp1_c is not None else "Temperature sensor not connected") +
        _factor_row("TEMPERATURE TREND",
            report.flag_temp_trend,
            f"5-min trend: {temp.trend.replace('_', ' ')} | "
            f"Persistence: {temp.persistence_s/60:.1f} min") +
        _factor_row("MOTION",
            report.flag_motion,
            f"Activity: {report.motion.activity} | "
            f"Steps: {report.motion.steps} | "
            f"Cadence: {report.motion.cadence_spm:.0f} spm") +
        _factor_row("BASELINE DEVIATION",
            report.flag_baseline_dev,
            (f"Pressure {exp.deviation_pct:+.0f}% from personal baseline | "
             f"{report.baseline.overall_deviation}")
            if report.baseline.valid else "Baseline still warming up") +
        _factor_row("PERSISTENCE",
            report.flag_persistence,
            f"Elevated for: {exp.duration_s:.0f} s | State: {exp.classification}")
    )
    st.markdown(
        f'<div style="background:#0D1B2A;border:1px solid #2A3050;'
        f'border-radius:10px;padding:16px 20px">{factors_html}</div>',
        unsafe_allow_html=True,
    )

    # ═════════════════════════════════════════════════════════════════════════
    # BLOCK 4 — Load Distribution + Peak Load
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sh">② Regional Load Distribution</div>',
                unsafe_allow_html=True)

    lc1, lc2, lc3, lc4 = st.columns(4)
    for col, lbl, val, color in [
        (lc1, "Forefoot Load", f"{lp.forefoot_pct:.0f}%", C["left"]),
        (lc2, "Heel Load",     f"{lp.heel_pct:.0f}%",     C["right"]),
        (lc3, "Peak Load",     f"{lp.peak_load_pct:.0f}%", C["monitor"]),
        (lc4, "Session Peak",  f"{lp.session_peak_pct:.0f}%", C["alert"]),
    ]:
        col.markdown(
            f'<div class="hwc"><h4>{lbl}</h4>'
            f'<p style="color:{color}">{val}</p></div>',
            unsafe_allow_html=True,
        )

    # Gauge bars for forefoot / heel
    fig_load = go.Figure()
    fig_load.add_trace(go.Bar(
        x=["Forefoot (FSR1)", "Heel (FSR2)"],
        y=[lp.forefoot_pct, lp.heel_pct],
        marker_color=[C["left"], C["right"]],
        text=[f"{lp.forefoot_pct:.0f}%", f"{lp.heel_pct:.0f}%"],
        textposition="outside",
    ))
    if report.baseline.valid:
        fig_load.add_hline(y=report.baseline.pressure_baseline_pct,
                           line_dash="dash", line_color="#607D8B",
                           annotation_text="Personal baseline",
                           annotation_font_color="#607D8B")
    fig_load.update_layout(
        height=220, yaxis=dict(range=[0, 105], title="Load %"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="white", margin=dict(t=20, b=20, l=20, r=20),
        showlegend=False,
    )
    fig_load.update_xaxes(gridcolor="#252b3b")
    fig_load.update_yaxes(gridcolor="#252b3b")
    st.plotly_chart(fig_load, use_container_width=True)

    # Interpretation
    if lp.forefoot_pct > FOREFOOT_OVERLOAD_FRAC * 100:
        st.markdown(
            f'<div style="color:{C["monitor"]};font-size:0.88rem">'
            f'⚠ Load concentration: FOREFOOT — '
            f'{lp.forefoot_pct:.0f}% of total load is on the forefoot region.</div>',
            unsafe_allow_html=True)
    elif lp.heel_pct > HEEL_OVERLOAD_FRAC * 100:
        st.markdown(
            f'<div style="color:{C["monitor"]};font-size:0.88rem">'
            f'⚠ Load concentration: HEEL — '
            f'{lp.heel_pct:.0f}% of total load is on the heel region.</div>',
            unsafe_allow_html=True)

    # Peak vs session peak comparison
    if lp.peak_load_pct > 0.90 * lp.session_peak_pct and lp.session_peak_pct > 10:
        st.caption("Current loading is approaching the highest observed loading during this session.")
    elif lp.session_peak_pct > 10:
        st.caption(f"Current loading ({lp.peak_load_pct:.0f}%) is below today's session peak ({lp.session_peak_pct:.0f}%).")

    # ═════════════════════════════════════════════════════════════════════════
    # BLOCK 5 — Pressure-Time Exposure
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sh">③ Pressure-Time Exposure</div>',
                unsafe_allow_html=True)

    ec1, ec2, ec3 = st.columns(3)
    ec1.markdown(
        f'<div class="mc"><h4>Current Load</h4>'
        f'<p style="color:{C["left"]}">{exp.current_load_pct:.0f}%</p></div>'
        f'<div class="mc"><h4>Baseline Load</h4>'
        f'<p style="color:#90CAF9">'
        f'{"%.0f%%" % exp.baseline_pct if report.baseline.valid else "—"}</p></div>',
        unsafe_allow_html=True)
    ec2.markdown(
        f'<div class="mc"><h4>Deviation</h4>'
        f'<p style="color:{C["monitor"] if abs(exp.deviation_pct)>10 else C["neutral"]}">'
        f'{exp.deviation_pct:+.0f}%</p></div>'
        f'<div class="mc"><h4>Duration Elevated</h4>'
        f'<p>{exp.duration_s/60:.1f} min</p></div>',
        unsafe_allow_html=True)
    exp_color = {
        "normal": C["normal"], "elevated": C["monitor"],
        "persistent": C["alert"]
    }.get(exp.state, C["neutral"])
    ec3.markdown(
        f'<div class="mc"><h4>Exposure State</h4>'
        f'<p style="color:{exp_color}">{exp.state.upper()}</p></div>'
        f'<div class="mc"><h4>Classification</h4>'
        f'<p style="color:{exp_color}">{exp.classification.upper()}</p></div>',
        unsafe_allow_html=True)

    if exp.duration_s > 0:
        st.caption(
            f"{report.concern.region.replace('_',' ').title()} loading "
            f"has remained above the personal baseline for "
            f"{exp.duration_s/60:.1f} minutes.")

    # ═════════════════════════════════════════════════════════════════════════
    # BLOCK 6 — Temperature Deviation + Thermal Trend
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sh">④ Temperature Analysis</div>',
                unsafe_allow_html=True)

    if not temp.temp1_c:
        st.info("Temperature sensor (DS18B20) not connected or not yet sending data.")
    else:
        tc1, tc2, tc3, tc4 = st.columns(4)
        tc1.markdown(
            f'<div class="mc"><h4>TEMP1 Current</h4>'
            f'<p style="color:{C["monitor"]}">{temp.temp1_c:.1f} °C</p></div>',
            unsafe_allow_html=True)
        tc2.markdown(
            f'<div class="mc"><h4>Baseline</h4>'
            f'<p style="color:#90CAF9">'
            f'{"%.1f °C" % temp.baseline_c if temp.baseline_c else "Warming up…"}</p></div>',
            unsafe_allow_html=True)
        dev_col = C["alert"] if abs(temp.deviation_c) >= TEMP_DEVIATION_ACTION else \
                  C["monitor"] if abs(temp.deviation_c) >= TEMP_DEVIATION_MONITOR else C["normal"]
        tc3.markdown(
            f'<div class="mc"><h4>Deviation</h4>'
            f'<p style="color:{dev_col}">{temp.deviation_c:+.1f} °C</p></div>',
            unsafe_allow_html=True)
        trend_label = temp.trend.replace("_", " ").title()
        trend_col   = C["alert"] if "elevated" in temp.trend or temp.trend == "rising" \
                      else C["normal"]
        tc4.markdown(
            f'<div class="mc"><h4>Trend</h4>'
            f'<p style="color:{trend_col}">{trend_label}</p></div>',
            unsafe_allow_html=True)

        if temp.temp2_c:
            st.caption(f"TEMP2: {temp.temp2_c:.1f} °C  |  "
                       f"Gradient: {(temp.temp1_c - temp.temp2_c):+.1f}°C between sensors")

        # Interpretation text
        if temp.deviation_c >= TEMP_DEVIATION_MONITOR:
            st.markdown(
                f'<div style="color:{C["monitor"]};font-size:0.88rem;margin-top:4px">'
                f'Thermal deviation indicator: temperature is '
                f'{temp.deviation_c:+.1f}°C above the personal baseline. '
                f'Trend: {trend_label.lower()}.</div>',
                unsafe_allow_html=True)
        elif temp.deviation_c < -TEMP_DEVIATION_MONITOR:
            st.caption("Temperature is returning toward the personal baseline.")

    # ═════════════════════════════════════════════════════════════════════════
    # BLOCK 7 — Personal Baseline
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sh">⑤ Personal Baseline Deviation</div>',
                unsafe_allow_html=True)

    bl = report.baseline
    if not bl.valid:
        st.info(f"Baseline still accumulating — need {BASELINE_WARMUP_S:.0f} s of data. "
                f"Keep the sensor active.")
    else:
        bc1, bc2, bc3 = st.columns(3)
        press_dev_col = C["monitor"] if abs(bl.press_deviation_pct) > 10 else C["normal"]
        temp_dev_col  = C["monitor"] if abs(bl.temp_deviation_c) > TEMP_DEVIATION_MONITOR else C["normal"]
        accel_dev_col = C["monitor"] if abs(bl.accel_deviation_pct) > 20 else C["normal"]

        bc1.markdown(
            f'<div class="mc"><h4>Pressure Deviation</h4>'
            f'<p style="color:{press_dev_col}">{bl.press_deviation_pct:+.0f}%</p></div>',
            unsafe_allow_html=True)
        bc2.markdown(
            f'<div class="mc"><h4>Temperature Deviation</h4>'
            f'<p style="color:{temp_dev_col}">'
            f'{"%.1f°C" % bl.temp_deviation_c if bl.temp_baseline_c else "N/A"}</p></div>',
            unsafe_allow_html=True)
        bc3.markdown(
            f'<div class="mc"><h4>Motion Deviation</h4>'
            f'<p style="color:{accel_dev_col}">{bl.accel_deviation_pct:+.0f}%</p></div>',
            unsafe_allow_html=True)

        dev_label = bl.overall_deviation
        if dev_label == "within baseline":
            st.caption("✓ Current measurements remain close to the user's normal pattern.")
        else:
            st.caption(f"⚠ Current measurements {dev_label}.")

    # ═════════════════════════════════════════════════════════════════════════
    # BLOCK 8 — Motion / Gait Context
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sh">⑥ Motion & Activity Context</div>',
                unsafe_allow_html=True)

    mc = report.motion
    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(f'<div class="mc"><h4>Activity</h4>'
                f'<p style="color:#90CAF9">{mc.activity.upper()}</p></div>',
                unsafe_allow_html=True)
    m2.markdown(f'<div class="mc"><h4>Steps (session)</h4>'
                f'<p>{mc.steps}</p></div>',
                unsafe_allow_html=True)
    m3.markdown(f'<div class="mc"><h4>Cadence</h4>'
                f'<p>{mc.cadence_spm:.0f} spm</p></div>',
                unsafe_allow_html=True)
    m4.markdown(f'<div class="mc"><h4>Intensity</h4>'
                f'<p style="color:{C["monitor"] if mc.intensity=="high" else C["normal"]}">'
                f'{mc.intensity.upper()}</p></div>',
                unsafe_allow_html=True)

    if mc.activity == "rest":
        st.caption("Sensor is at rest — pressure analysis paused to avoid misleading alerts.")
    elif mc.activity == "standing":
        st.caption("Standing detected — evaluating sustained regional loading.")
    elif mc.activity == "walking":
        st.caption("Walking detected — evaluating repeated loading and gait pattern.")

    # ═════════════════════════════════════════════════════════════════════════
    # BLOCK 9 — Regional Concern card
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sh">⑦ Regional Foot-Risk Indicator</div>',
                unsafe_allow_html=True)

    cc = report.concern
    cc_color = STATUS_COLOR.get(report.status, C["neutral"])
    cc_icon  = STATUS_ICON.get(report.status, "⚪")

    st.markdown(
        f'<div style="background:#0D1B2A;border:2px solid {cc_color};'
        f'border-radius:12px;padding:18px 22px">'
        f'<b style="color:{cc_color};font-size:1.1rem">'
        f'{cc_icon} REGIONAL CONCERN: {cc.region}</b><br><br>'
        f'<table style="width:100%;color:#C8D4F0;font-size:0.88rem">'
        f'<tr><td>Pressure state</td>'
        f'<td style="color:{C["monitor"] if cc.pressure_state!="normal" else C["normal"]};font-weight:700">'
        f'{cc.pressure_state.upper()}</td></tr>'
        f'<tr><td>Pressure exposure</td>'
        f'<td style="color:{C["monitor"] if cc.exposure_state not in ("normal","transient") else C["neutral"]};font-weight:700">'
        f'{cc.exposure_state.upper()}</td></tr>'
        f'<tr><td>Temperature deviation</td>'
        f'<td style="color:{C["monitor"] if abs(cc.temp_deviation_c)>=TEMP_DEVIATION_MONITOR else C["normal"]};font-weight:700">'
        f'{cc.temp_deviation_c:+.1f}°C</td></tr>'
        f'<tr><td>Baseline deviation</td>'
        f'<td style="color:{C["monitor"] if abs(cc.baseline_dev_pct)>10 else C["normal"]};font-weight:700">'
        f'{cc.baseline_dev_pct:+.0f}%</td></tr>'
        f'<tr><td>Persistence</td>'
        f'<td>{cc.persistence_s/60:.1f} min</td></tr>'
        f'<tr><td>Confidence</td>'
        f'<td style="color:#90CAF9">{cc.confidence}</td></tr>'
        f'</table></div>',
        unsafe_allow_html=True,
    )

    # ═════════════════════════════════════════════════════════════════════════
    # BLOCK 10 — Recovery / Response to Alert
    # ═════════════════════════════════════════════════════════════════════════
    if report.recovery:
        rec = report.recovery
        st.markdown('<div class="sh">⑧ Response to Alert</div>',
                    unsafe_allow_html=True)
        r_color = C["normal"] if rec.improved else C["monitor"]
        st.markdown(
            f'<div style="background:#0D1B2A;border:2px solid {r_color};'
            f'border-radius:10px;padding:16px 20px">'
            f'<b style="color:{r_color}">{"✓ Recovery Detected" if rec.recovering else "⚠ Loading Not Yet Reduced"}</b>'
            f'<br><br>'
            f'<table style="color:#C8D4F0;font-size:0.88rem;width:100%">'
            f'<tr><td>Before alert</td><td>{rec.before_load_pct:.0f}% load | '
            f'{"%.1f°C" % rec.before_temp_c if rec.before_temp_c else "N/A"}</td></tr>'
            f'<tr><td>Current</td><td>{rec.current_load_pct:.0f}% load | '
            f'{"%.1f°C" % rec.current_temp_c if rec.current_temp_c else "N/A"}</td></tr>'
            f'</table>'
            f'<div style="color:#90CAF9;margin-top:10px;font-size:0.88rem">{rec.detail}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ═════════════════════════════════════════════════════════════════════════
    # BLOCK 11 — Action / Recommendation
    # ═════════════════════════════════════════════════════════════════════════
    rec_color = STATUS_COLOR.get(report.status, C["neutral"])
    st.markdown(
        f'<div style="background:#1A1F2E;border-left:4px solid {rec_color};'
        f'border-radius:6px;padding:14px 18px;margin:14px 0">'
        f'<b style="color:white">💡 Recommended Action</b><br>'
        f'<span style="color:#C8D4F0;font-size:0.9rem">{report.recommendation}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ═════════════════════════════════════════════════════════════════════════
    # BLOCK 12 — Event Timeline
    # ═════════════════════════════════════════════════════════════════════════
    if report.events:
        st.markdown('<div class="sh">⑨ Event Timeline</div>',
                    unsafe_allow_html=True)
        ev_html = (
            '<table style="width:100%;color:#C8D4F0;font-size:0.83rem;'
            'border-collapse:collapse">'
            '<tr style="color:#607D8B;border-bottom:1px solid #2A3050">'
            '<th align="left" style="padding:4px 8px">TIME</th>'
            '<th align="left" style="padding:4px 8px">EVENT</th>'
            '<th align="left" style="padding:4px 8px">STATUS</th></tr>'
        )
        for ev in reversed(report.events[-12:]):
            import datetime
            t_str = datetime.datetime.fromtimestamp(ev.wall_time).strftime("%H:%M:%S")
            ev_color = STATUS_COLOR.get(ev.status,  C["neutral"])
            ev_icon  = STATUS_ICON.get(ev.status, "⚪")
            ev_html += (
                f'<tr style="border-bottom:1px solid #1e2330">'
                f'<td style="padding:4px 8px;color:#607D8B">{t_str}</td>'
                f'<td style="padding:4px 8px">{ev.label}</td>'
                f'<td style="padding:4px 8px;color:{ev_color};font-weight:700">'
                f'{ev_icon} {ev.status}</td></tr>'
            )
        ev_html += '</table>'
        st.markdown(
            f'<div style="background:#0D1B2A;border:1px solid #2A3050;'
            f'border-radius:10px;padding:12px 16px">{ev_html}</div>',
            unsafe_allow_html=True,
        )

    # ═════════════════════════════════════════════════════════════════════════
    # BLOCK 13 — Session Summary
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sh">⑩ Session Summary</div>',
                unsafe_allow_html=True)
    ss = report.session
    s1, s2, s3, s4 = st.columns(4)
    s1.markdown(
        f'<div class="mc"><h4>Monitoring Time</h4>'
        f'<p>{ss.monitoring_secs/60:.1f} min</p></div>'
        f'<div class="mc"><h4>Steps</h4>'
        f'<p>{ss.steps}</p></div>',
        unsafe_allow_html=True)
    s2.markdown(
        f'<div class="mc"><h4>Peak Load</h4>'
        f'<p style="color:{C["alert"]}">{ss.peak_load_pct:.0f}%</p></div>'
        f'<div class="mc"><h4>Average Load</h4>'
        f'<p>{ss.avg_load_pct:.0f}%</p></div>',
        unsafe_allow_html=True)
    s3.markdown(
        f'<div class="mc"><h4>Temp Range</h4>'
        f'<p>{"%.1f–%.1f°C" % (ss.temp1_min, ss.temp1_max) if ss.temp1_min else "N/A"}</p></div>'
        f'<div class="mc"><h4>Persistent Events</h4>'
        f'<p style="color:{C["monitor"] if ss.persist_events>0 else C["normal"]}">'
        f'{ss.persist_events}</p></div>',
        unsafe_allow_html=True)
    trend_col = C["alert"] if ss.session_trend=="worsening" else \
                C["normal"] if ss.session_trend=="improving" else C["neutral"]
    s4.markdown(
        f'<div class="mc"><h4>Monitor Events</h4>'
        f'<p style="color:{C["monitor"] if ss.monitor_events>0 else C["normal"]}">'
        f'{ss.monitor_events}</p></div>'
        f'<div class="mc"><h4>Session Trend</h4>'
        f'<p style="color:{trend_col}">{ss.session_trend.upper()}</p></div>',
        unsafe_allow_html=True)

    # Disclaimer
    st.markdown(
        '<div class="disc">⚠ EXPERIMENTAL PROTOTYPE — Not a medical device. '
        'This system does not diagnose any medical condition. '
        'All thresholds are demo values only.</div>',
        unsafe_allow_html=True,
    )
