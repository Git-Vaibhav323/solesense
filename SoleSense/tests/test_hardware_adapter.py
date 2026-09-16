"""
SoleSense — tests/test_hardware_adapter.py
===========================================
Tests for the hardware integration layer:
  - sensor_schema   : JSON parsing, validation, FsrPacket helpers
  - hardware_adapter: feature row generation, bilateral fallback, gait estimates

Run with:
    cd f:/Dataset/SoleSense
    python -m pytest tests/test_hardware_adapter.py -v
"""

import time
import math
import pytest
import pandas as pd

from hardware.sensor_schema import (
    FsrPacket, ImuPacket, SensorPacket,
    parse_packet, PacketValidationError,
    mock_packet, FSR_REGIONS, FSR_ADC_MAX,
)
from hardware.hardware_adapter import (
    HardwareAdapter, FSR_SCALE_KPA, NOT_AVAILABLE_BILATERAL,
)


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _make_raw(fsr=None, temp=31.0, imu=True, t=1000):
    """Build a minimal valid raw JSON dict as the ESP32 would send."""
    fsr = fsr or {
        "forefoot_medial":  420,
        "forefoot_lateral": 380,
        "midfoot":          210,
        "heel":             510,
    }
    d = {"t": t, "fsr": fsr, "temp": temp}
    if imu:
        d["imu"] = {"ax": 0.03, "ay": -0.02, "az": 0.98,
                    "gx": 1.2, "gy": -0.8, "gz": 0.3}
    else:
        d["imu"] = None
    return d


def _make_packets(n=100, vary=True):
    """Return a list of n SensorPackets with received_at set for the adapter."""
    now = time.time()
    packets = []
    for i in range(n):
        fm = 420 + (i % 10) * 5 if vary else 420
        fl = 380 + (i % 8)  * 4 if vary else 380
        mf = 210 + (i % 6)  * 3 if vary else 210
        hl = 510 + (i % 12) * 6 if vary else 510
        p = SensorPacket(
            t=i * 50,
            fsr=FsrPacket(forefoot_medial=fm, forefoot_lateral=fl,
                          midfoot=mf, heel=hl),
            temp=31.4 + (i % 5) * 0.1,
            imu=ImuPacket(ax=0.03, ay=-0.02, az=0.98,
                          gx=1.2, gy=-0.8, gz=0.3),
            received_at=now - (n - i) * 0.05,
        )
        packets.append(p)
    return packets


# ═══════════════════════════════════════════════════════════════════════════
#  1. FsrPacket helpers
# ═══════════════════════════════════════════════════════════════════════════

class TestFsrPacket:

    def test_total(self):
        f = FsrPacket(100, 200, 50, 150)
        assert f.total() == 500

    def test_total_zero(self):
        f = FsrPacket(0, 0, 0, 0)
        assert f.total() == 0

    def test_fractions_sum_to_one(self):
        f = FsrPacket(100, 200, 50, 150)
        fracs = f.fractions()
        assert pytest.approx(sum(fracs.values()), abs=1e-6) == 1.0

    def test_fractions_zero_load(self):
        f = FsrPacket(0, 0, 0, 0)
        fracs = f.fractions()
        assert all(v == 0.0 for v in fracs.values())

    def test_forefoot_fraction(self):
        f = FsrPacket(forefoot_medial=200, forefoot_lateral=200,
                      midfoot=0, heel=0)
        assert pytest.approx(f.forefoot_fraction()) == 1.0

    def test_rearfoot_fraction(self):
        f = FsrPacket(forefoot_medial=0, forefoot_lateral=0,
                      midfoot=0, heel=500)
        assert pytest.approx(f.rearfoot_fraction()) == 1.0

    def test_peak(self):
        f = FsrPacket(100, 900, 50, 300)
        assert f.peak() == 900

    def test_mean(self):
        f = FsrPacket(100, 200, 300, 400)
        assert pytest.approx(f.mean()) == 250.0

    def test_fractions_keys(self):
        f = FsrPacket(100, 100, 100, 100)
        assert set(f.fractions().keys()) == set(FSR_REGIONS)

    def test_fractions_values_between_0_and_1(self):
        f = FsrPacket(420, 380, 210, 510)
        for v in f.fractions().values():
            assert 0.0 <= v <= 1.0


# ═══════════════════════════════════════════════════════════════════════════
#  2. ImuPacket helpers
# ═══════════════════════════════════════════════════════════════════════════

class TestImuPacket:

    def test_accel_magnitude_unit_vector(self):
        imu = ImuPacket(ax=1.0, ay=0.0, az=0.0)
        assert pytest.approx(imu.accel_magnitude()) == 1.0

    def test_accel_magnitude_all_axes(self):
        imu = ImuPacket(ax=1.0, ay=1.0, az=1.0)
        assert pytest.approx(imu.accel_magnitude(), rel=1e-5) == math.sqrt(3)

    def test_gyro_magnitude_zero(self):
        imu = ImuPacket()
        assert imu.gyro_magnitude() == 0.0

    def test_gyro_magnitude(self):
        imu = ImuPacket(gx=3.0, gy=4.0, gz=0.0)
        assert pytest.approx(imu.gyro_magnitude()) == 5.0


# ═══════════════════════════════════════════════════════════════════════════
#  3. parse_packet — valid inputs
# ═══════════════════════════════════════════════════════════════════════════

class TestParsePacketValid:

    def test_full_packet(self):
        raw = _make_raw()
        pkt = parse_packet(raw)
        assert isinstance(pkt, SensorPacket)
        assert pkt.t == 1000
        assert pkt.fsr.forefoot_medial == 420
        assert pkt.fsr.heel == 510
        assert pytest.approx(pkt.temp) == 31.0
        assert pkt.imu is not None
        assert pytest.approx(pkt.imu.az, rel=1e-3) == 0.98

    def test_no_temperature(self):
        raw = _make_raw(temp=None)
        raw["temp"] = None
        pkt = parse_packet(raw)
        assert pkt.temp is None
        assert not pkt.has_temperature

    def test_no_imu(self):
        raw = _make_raw(imu=False)
        pkt = parse_packet(raw)
        assert pkt.imu is None
        assert not pkt.has_imu

    def test_fsr_values_clamped_to_adc_max(self):
        raw = _make_raw(fsr={
            "forefoot_medial":  9999,   # over ADC max → clamped
            "forefoot_lateral": 380,
            "midfoot":          210,
            "heel":             510,
        })
        pkt = parse_packet(raw)
        assert pkt.fsr.forefoot_medial == FSR_ADC_MAX

    def test_fsr_negative_clamped_to_zero(self):
        raw = _make_raw(fsr={
            "forefoot_medial":  -100,
            "forefoot_lateral": 380,
            "midfoot":          210,
            "heel":             510,
        })
        pkt = parse_packet(raw)
        assert pkt.fsr.forefoot_medial == 0

    def test_timestamp_as_string_int(self):
        raw = _make_raw(t="98765")
        pkt = parse_packet(raw)
        assert pkt.t == 98765

    def test_all_fsr_regions_present(self):
        raw = _make_raw()
        pkt = parse_packet(raw)
        for region in FSR_REGIONS:
            assert hasattr(pkt.fsr, region)


# ═══════════════════════════════════════════════════════════════════════════
#  4. parse_packet — invalid / malformed inputs
# ═══════════════════════════════════════════════════════════════════════════

class TestParsePacketInvalid:

    def test_missing_timestamp(self):
        raw = _make_raw()
        del raw["t"]
        with pytest.raises(PacketValidationError, match="'t'"):
            parse_packet(raw)

    def test_invalid_timestamp(self):
        raw = _make_raw()
        raw["t"] = "not_a_number"
        with pytest.raises(PacketValidationError):
            parse_packet(raw)

    def test_missing_fsr(self):
        raw = _make_raw()
        del raw["fsr"]
        with pytest.raises(PacketValidationError, match="fsr"):
            parse_packet(raw)

    def test_fsr_not_dict(self):
        raw = _make_raw()
        raw["fsr"] = "bad"
        with pytest.raises(PacketValidationError):
            parse_packet(raw)

    def test_missing_fsr_region(self):
        raw = _make_raw()
        del raw["fsr"]["heel"]
        with pytest.raises(PacketValidationError, match="heel"):
            parse_packet(raw)

    def test_fsr_value_not_numeric(self):
        raw = _make_raw()
        raw["fsr"]["forefoot_medial"] = "heavy"
        with pytest.raises(PacketValidationError):
            parse_packet(raw)

    def test_empty_dict(self):
        with pytest.raises(PacketValidationError):
            parse_packet({})

    def test_malformed_imu_silently_drops(self):
        raw = _make_raw()
        raw["imu"] = {"ax": "bad", "ay": 0, "az": 0,
                      "gx": 0, "gy": 0, "gz": 0}
        pkt = parse_packet(raw)
        # malformed imu → imu is None (silent drop)
        assert pkt.imu is None

    def test_malformed_temp_silently_drops(self):
        raw = _make_raw()
        raw["temp"] = "hot"
        pkt = parse_packet(raw)
        assert pkt.temp is None


# ═══════════════════════════════════════════════════════════════════════════
#  5. mock_packet
# ═══════════════════════════════════════════════════════════════════════════

class TestMockPacket:

    def test_mock_returns_sensor_packet(self):
        p = mock_packet(t=999)
        assert isinstance(p, SensorPacket)
        assert p.t == 999

    def test_mock_has_all_sensors(self):
        p = mock_packet()
        assert p.has_temperature
        assert p.has_imu
        assert p.fsr.total() > 0


# ═══════════════════════════════════════════════════════════════════════════
#  6. HardwareAdapter — feature row output
# ═══════════════════════════════════════════════════════════════════════════

class TestHardwareAdapterFeatureRow:

    def setup_method(self):
        self.adapter = HardwareAdapter(window_s=5.0)

    def test_returns_series(self):
        pkts = _make_packets(100)
        row = self.adapter.to_feature_row(pkts)
        assert isinstance(row, pd.Series)

    def test_insufficient_data_returns_none(self):
        row = self.adapter.to_feature_row([])
        assert row is None
        row1 = self.adapter.to_feature_row([mock_packet()])
        assert row1 is None

    def test_required_risk_engine_columns_present(self):
        required = [
            "press_max_kpa", "pti_total_kpa_s",
            "asym_pti_total_kpa_s", "asym_press_mean_kpa",
            "load_frac_forefoot", "load_frac_rearfoot",
            "step_time_std_s", "gait_symmetry_index",
            "persistence_pti_total_kpa_s", "asym_load_forefoot",
        ]
        pkts = _make_packets(100)
        row  = self.adapter.to_feature_row(pkts)
        for col in required:
            assert col in row.index, f"Missing column: {col}"

    def test_bilateral_features_are_zero(self):
        """Single insole: bilateral features must be 0.0, never fabricated."""
        pkts = _make_packets(100)
        row  = self.adapter.to_feature_row(pkts)
        for col in NOT_AVAILABLE_BILATERAL:
            assert row[col] == 0.0, (
                f"Bilateral feature '{col}' must be 0.0 on single insole, "
                f"got {row[col]}"
            )

    def test_press_max_kpa_positive(self):
        pkts = _make_packets(100)
        row  = self.adapter.to_feature_row(pkts)
        assert row["press_max_kpa"] > 0

    def test_press_max_kpa_within_scale(self):
        pkts = _make_packets(100)
        row  = self.adapter.to_feature_row(pkts)
        # max possible: FSR_SCALE_KPA when all 4 FSRs at ADC max
        assert row["press_max_kpa"] <= FSR_SCALE_KPA * 4 + 1.0

    def test_load_fracs_sum_approx_one(self):
        pkts = _make_packets(100)
        row  = self.adapter.to_feature_row(pkts)
        total = (row["load_frac_forefoot"]
                 + row["load_frac_rearfoot"]
                 + row["load_frac_midfoot"]
                 + row["load_frac_toe"])
        assert pytest.approx(total, abs=0.01) == 1.0

    def test_load_fractions_between_0_and_1(self):
        pkts = _make_packets(100)
        row  = self.adapter.to_feature_row(pkts)
        for col in ["load_frac_forefoot", "load_frac_rearfoot",
                    "load_frac_midfoot", "load_frac_toe"]:
            assert 0.0 <= row[col] <= 1.0, f"{col} = {row[col]}"

    def test_persistence_between_0_and_1(self):
        pkts = _make_packets(100)
        row  = self.adapter.to_feature_row(pkts)
        assert 0.0 <= row["persistence_pti_total_kpa_s"] <= 1.0

    def test_temperature_populated_when_available(self):
        pkts = _make_packets(100)
        row  = self.adapter.to_feature_row(pkts)
        assert row["temperature_c"] > 0

    def test_temperature_zero_when_unavailable(self):
        pkts = _make_packets(100)
        for p in pkts:
            p.temp = None
        row = self.adapter.to_feature_row(pkts)
        assert row["temperature_c"] == 0.0

    def test_accel_magnitude_populated(self):
        pkts = _make_packets(100)
        row  = self.adapter.to_feature_row(pkts)
        assert row["accel_magnitude_g"] > 0

    def test_metadata_columns(self):
        pkts = _make_packets(100)
        row  = self.adapter.to_feature_row(pkts)
        assert row["subject_id"] == "HARDWARE"
        assert row["footwear"]   == "LIVE"
        assert row["trial"]      == "LIVE"
        assert row["side"]       == "Left"

    def test_pti_increases_with_more_load(self):
        """Higher FSR readings should produce higher PTI."""
        light = [SensorPacket(
            t=i * 50,
            fsr=FsrPacket(100, 100, 50, 100),
            received_at=time.time() - (100 - i) * 0.05,
        ) for i in range(100)]
        heavy = [SensorPacket(
            t=i * 50,
            fsr=FsrPacket(2000, 2000, 1000, 2000),
            received_at=time.time() - (100 - i) * 0.05,
        ) for i in range(100)]
        row_light = self.adapter.to_feature_row(light)
        row_heavy = self.adapter.to_feature_row(heavy)
        assert row_heavy["pti_total_kpa_s"] > row_light["pti_total_kpa_s"]

    def test_forefoot_dominant_when_forefoot_loaded(self):
        pkts = [SensorPacket(
            t=i * 50,
            fsr=FsrPacket(forefoot_medial=2000, forefoot_lateral=2000,
                          midfoot=10, heel=10),
            received_at=time.time() - (100 - i) * 0.05,
        ) for i in range(100)]
        row = self.adapter.to_feature_row(pkts)
        assert row["load_frac_forefoot"] > 0.8

    def test_heel_dominant_when_heel_loaded(self):
        pkts = [SensorPacket(
            t=i * 50,
            fsr=FsrPacket(forefoot_medial=10, forefoot_lateral=10,
                          midfoot=10, heel=3000),
            received_at=time.time() - (100 - i) * 0.05,
        ) for i in range(100)]
        row = self.adapter.to_feature_row(pkts)
        assert row["load_frac_rearfoot"] > 0.8


# ═══════════════════════════════════════════════════════════════════════════
#  7. HardwareAdapter feeds compute_risk without crashing
# ═══════════════════════════════════════════════════════════════════════════

class TestAdapterRiskEngineIntegration:
    """
    End-to-end: SensorPackets → HardwareAdapter → compute_risk().
    Verifies that the adapter output is fully compatible with the risk engine.
    """

    def test_compute_risk_accepts_hardware_row(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from src.risk_engine import compute_risk, RiskResult

        pkts = _make_packets(100)
        row  = HardwareAdapter(window_s=5.0).to_feature_row(pkts)
        assert row is not None

        result = compute_risk(row)
        assert isinstance(result, RiskResult)
        assert 0.0 <= result.risk_score <= 100.0
        assert result.risk_level in ("NORMAL", "MONITOR", "ALERT")

    def test_high_load_raises_risk(self):
        from src.risk_engine import compute_risk

        # Saturate all FSRs.
        # At 4×4000 ADC, proxy press_max = (16000/4095)*600 ≈ 2344 kPa → peak_pressure triggers (weight 25).
        # Persistence will also trigger (weight 20). Total = 45/170*100 ≈ 26.5 → NORMAL.
        # We verify the score is strictly higher than a quiet insole (i.e. load IS detected).
        heavy = [SensorPacket(
            t=i * 50,
            fsr=FsrPacket(4000, 4000, 4000, 4000),
            received_at=time.time() - (200 - i) * 0.05,
        ) for i in range(200)]
        quiet = [SensorPacket(
            t=i * 50,
            fsr=FsrPacket(5, 5, 5, 5),
            received_at=time.time() - (200 - i) * 0.05,
        ) for i in range(200)]
        row_heavy = HardwareAdapter(window_s=10.0).to_feature_row(heavy)
        row_quiet = HardwareAdapter(window_s=10.0).to_feature_row(quiet)
        result_heavy = compute_risk(row_heavy)
        result_quiet = compute_risk(row_quiet)
        assert result_heavy.risk_score > result_quiet.risk_score, (
            "Saturated FSRs should produce a higher risk score than near-zero load"
        )
        # Peak pressure rule must fire — it's the primary hardware-accessible rule
        triggered_names = {f.name for f in result_heavy.factors if f.triggered}
        assert "peak_pressure" in triggered_names, (
            "peak_pressure rule must trigger at max FSR load"
        )

    def test_no_load_normal_risk(self):
        from src.risk_engine import compute_risk

        quiet = [SensorPacket(
            t=i * 50,
            fsr=FsrPacket(5, 5, 5, 5),   # near-zero load
            received_at=time.time() - (100 - i) * 0.05,
        ) for i in range(100)]
        row    = HardwareAdapter(window_s=5.0).to_feature_row(quiet)
        result = compute_risk(row)
        assert result.risk_level == "NORMAL", (
            f"Expected NORMAL with zero load, got {result.risk_level} "
            f"(score={result.risk_score})"
        )

    def test_bilateral_rules_never_trigger_single_insole(self):
        """
        Bilateral rules should never fire on single-insole hardware because
        all asym_* features are forced to 0.0.
        """
        from src.risk_engine import compute_risk

        pkts   = _make_packets(100)
        row    = HardwareAdapter(window_s=5.0).to_feature_row(pkts)
        result = compute_risk(row)

        bilateral_rule_names = {
            "loading_asymmetry", "pressure_asymmetry",
            "gait_asymmetry",    "persistence_asymmetry",
        }
        triggered = {f.name for f in result.factors if f.triggered}
        bad = bilateral_rule_names & triggered
        assert not bad, (
            f"Bilateral rules triggered on single-insole prototype: {bad}"
        )

    def test_result_has_recommended_action(self):
        from src.risk_engine import compute_risk

        pkts   = _make_packets(100)
        row    = HardwareAdapter(window_s=5.0).to_feature_row(pkts)
        result = compute_risk(row)
        assert isinstance(result.recommended_action, str)
        assert len(result.recommended_action) > 0

    def test_risk_score_bounded(self):
        from src.risk_engine import compute_risk

        for _ in range(5):
            pkts   = _make_packets(80, vary=True)
            row    = HardwareAdapter().to_feature_row(pkts)
            result = compute_risk(row)
            assert 0.0 <= result.risk_score <= 100.0
