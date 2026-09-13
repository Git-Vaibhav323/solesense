"""
SoleSense Hardware — sensor_schema.py
======================================
Single source of truth for the ESP32-S3 JSON packet format.

Every layer (receiver, adapter, tests, dashboard) imports from here.
If the firmware JSON schema changes, only this file needs updating.

Packet example (as sent by ESP32-S3 over HTTP POST):
{
    "t":    123456789,
    "fsr":  {
        "forefoot_medial":  412,
        "forefoot_lateral": 605,
        "midfoot":          278,
        "heel":             531
    },
    "temp": 31.42,
    "imu":  {
        "ax":  0.0312,
        "ay": -0.0198,
        "az":  0.9871,
        "gx":  1.240,
        "gy": -0.810,
        "gz":  0.320
    }
}

Field notes
-----------
t       : ESP32 millis() timestamp (ms since boot). The Python receiver
          adds a wall-clock `received_at` timestamp on arrival.
fsr.*   : Baseline-subtracted ADC counts (0–4095). NOT calibrated kPa.
          Treated as relative load proxies. The adapter converts them
          to a 0–1 fraction for use in the risk engine.
temp    : °C from TMP117. null if sensor unavailable.
imu.*   : ax/ay/az in g; gx/gy/gz in °/s. null if MPU6050 unavailable.
"""

from __future__ import annotations
from typing import Optional
from dataclasses import dataclass, field


# ── FSR anatomical region names ───────────────────────────────────────────────
# Must match FSR1_NAME..FSR4_NAME in firmware config.h
FSR_REGIONS = ["forefoot_medial", "forefoot_lateral", "midfoot", "heel"]

# ADC max value (12-bit ESP32-S3)
FSR_ADC_MAX = 4095


# ── Dataclasses mirroring the JSON schema ─────────────────────────────────────

@dataclass
class FsrPacket:
    forefoot_medial:  int = 0
    forefoot_lateral: int = 0
    midfoot:          int = 0
    heel:             int = 0

    def as_dict(self) -> dict:
        return {
            "forefoot_medial":  self.forefoot_medial,
            "forefoot_lateral": self.forefoot_lateral,
            "midfoot":          self.midfoot,
            "heel":             self.heel,
        }

    def total(self) -> int:
        """Sum of all four FSR readings."""
        return (self.forefoot_medial + self.forefoot_lateral
                + self.midfoot + self.heel)

    def fractions(self) -> dict[str, float]:
        """
        Each region's fraction of total load (0–1).
        Returns zeros if total is zero (no load on insole).
        """
        total = self.total()
        if total == 0:
            return {r: 0.0 for r in FSR_REGIONS}
        return {
            "forefoot_medial":  self.forefoot_medial  / total,
            "forefoot_lateral": self.forefoot_lateral / total,
            "midfoot":          self.midfoot          / total,
            "heel":             self.heel             / total,
        }

    def forefoot_fraction(self) -> float:
        """Combined forefoot (medial + lateral) as fraction of total."""
        total = self.total()
        if total == 0:
            return 0.0
        return (self.forefoot_medial + self.forefoot_lateral) / total

    def rearfoot_fraction(self) -> float:
        """Heel fraction of total."""
        total = self.total()
        if total == 0:
            return 0.0
        return self.heel / total

    def midfoot_fraction(self) -> float:
        total = self.total()
        if total == 0:
            return 0.0
        return self.midfoot / total

    def peak(self) -> int:
        """Highest single FSR reading."""
        return max(self.forefoot_medial, self.forefoot_lateral,
                   self.midfoot, self.heel)

    def mean(self) -> float:
        return self.total() / 4.0


@dataclass
class ImuPacket:
    ax: float = 0.0   # acceleration x, g
    ay: float = 0.0   # acceleration y, g
    az: float = 0.0   # acceleration z, g
    gx: float = 0.0   # gyroscope x, °/s
    gy: float = 0.0   # gyroscope y, °/s
    gz: float = 0.0   # gyroscope z, °/s

    def accel_magnitude(self) -> float:
        """√(ax²+ay²+az²) in g."""
        return (self.ax**2 + self.ay**2 + self.az**2) ** 0.5

    def gyro_magnitude(self) -> float:
        """√(gx²+gy²+gz²) in °/s."""
        return (self.gx**2 + self.gy**2 + self.gz**2) ** 0.5


@dataclass
class SensorPacket:
    """
    One complete sensor sample from the ESP32-S3.
    Matches the JSON schema produced by wifi_tx.cpp.
    """
    t:           int                    # ESP32 millis() timestamp
    fsr:         FsrPacket = field(default_factory=FsrPacket)
    temp:        Optional[float] = None # °C; None = sensor unavailable
    imu:         Optional[ImuPacket] = None
    received_at: Optional[float] = None # wall-clock time.time() on receipt

    @property
    def has_temperature(self) -> bool:
        return self.temp is not None

    @property
    def has_imu(self) -> bool:
        return self.imu is not None


# ── Parsing ────────────────────────────────────────────────────────────────────

class PacketValidationError(ValueError):
    """Raised when a raw JSON dict does not match the expected schema."""
    pass


def parse_packet(raw: dict) -> SensorPacket:
    """
    Parse a raw JSON dict (from Flask request.json) into a SensorPacket.
    Raises PacketValidationError on missing/invalid required fields.

    Parameters
    ----------
    raw : dict — parsed JSON from ESP32

    Returns
    -------
    SensorPacket
    """
    # ── Required: timestamp ───────────────────────────────────────────────────
    if "t" not in raw:
        raise PacketValidationError("Missing required field: 't' (timestamp)")
    try:
        t = int(raw["t"])
    except (TypeError, ValueError):
        raise PacketValidationError(f"Invalid timestamp: {raw['t']!r}")

    # ── Required: fsr ─────────────────────────────────────────────────────────
    if "fsr" not in raw or not isinstance(raw["fsr"], dict):
        raise PacketValidationError("Missing or invalid field: 'fsr'")

    fsr_raw = raw["fsr"]
    fsr_vals = {}
    for region in FSR_REGIONS:
        if region not in fsr_raw:
            raise PacketValidationError(f"Missing FSR region: '{region}'")
        try:
            val = int(fsr_raw[region])
        except (TypeError, ValueError):
            raise PacketValidationError(f"Invalid FSR value for '{region}': {fsr_raw[region]!r}")
        if not (0 <= val <= FSR_ADC_MAX):
            # Clamp rather than reject — sensor noise can briefly exceed bounds
            val = max(0, min(FSR_ADC_MAX, val))
        fsr_vals[region] = val

    fsr = FsrPacket(**fsr_vals)

    # ── Optional: temperature ─────────────────────────────────────────────────
    temp: Optional[float] = None
    if raw.get("temp") is not None:
        try:
            temp = float(raw["temp"])
        except (TypeError, ValueError):
            temp = None   # malformed → treat as unavailable

    # ── Optional: IMU ─────────────────────────────────────────────────────────
    imu: Optional[ImuPacket] = None
    if raw.get("imu") is not None and isinstance(raw["imu"], dict):
        imu_raw = raw["imu"]
        try:
            imu = ImuPacket(
                ax=float(imu_raw.get("ax", 0.0)),
                ay=float(imu_raw.get("ay", 0.0)),
                az=float(imu_raw.get("az", 0.0)),
                gx=float(imu_raw.get("gx", 0.0)),
                gy=float(imu_raw.get("gy", 0.0)),
                gz=float(imu_raw.get("gz", 0.0)),
            )
        except (TypeError, ValueError):
            imu = None

    return SensorPacket(t=t, fsr=fsr, temp=temp, imu=imu)


# ── Mock packet for pipeline testing (no hardware connected) ──────────────────

def mock_packet(t: int = 0) -> SensorPacket:
    """
    Returns a realistic-looking SensorPacket for testing the Python pipeline
    without a physical ESP32 connected.

    CLEARLY LABELLED AS MOCK DATA — never used in production hardware mode.
    """
    return SensorPacket(
        t=t,
        fsr=FsrPacket(
            forefoot_medial=420,
            forefoot_lateral=380,
            midfoot=210,
            heel=510,
        ),
        temp=31.4,
        imu=ImuPacket(ax=0.03, ay=-0.02, az=0.98,
                      gx=1.2, gy=-0.8, gz=0.3),
    )
