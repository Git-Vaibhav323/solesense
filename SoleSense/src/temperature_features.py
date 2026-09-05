"""
SoleSense Temperature Features
================================
HARDWARE ROADMAP NOTICE
-----------------------
Temperature sensing is NOT available in the current StepUP-P150 dataset.

The StepUP-P150 dataset contains only plantar pressure measurements captured
by a floor-mounted piezoresistive mat.  No temperature sensors were part of
the data collection setup.

The SoleSense hardware design includes:
    - 8 temperature sensing sites per insole
    - Bilateral left/right temperature comparison
    - Persistent temperature asymmetry monitoring

This module is a PLACEHOLDER that defines the intended feature API.
When physical SoleSense insoles become available, this module will be
implemented using real sensor data.

Temperature features intended for hardware integration:
    mean_temp_left_c          – mean plantar temperature, left foot [°C]
    mean_temp_right_c         – mean plantar temperature, right foot [°C]
    max_temp_left_c           – peak regional temperature, left [°C]
    max_temp_right_c          – peak regional temperature, right [°C]
    delta_temp_c              – bilateral temperature difference (L − R) [°C]
    asym_temp_pct             – normalized temperature asymmetry [%]
    temp_variability_left     – std of temperature across 8 sites, left [°C]
    temp_variability_right    – std of temperature across 8 sites, right [°C]
    temp_persistence_score    – rolling metric of sustained asymmetry [0–1]
    hot_zone_left             – index of highest temperature region (0–7)
    hot_zone_right            – index of highest temperature region (0–7)

Reference thresholds (experimental, NOT clinically validated):
    ΔT > 2.2 °C between symmetric sites is sometimes referenced in research
    literature as a flag for local inflammatory response.  SoleSense will use
    this as a monitoring guideline, NOT a diagnostic threshold.
"""

from typing import Dict


def extract_temperature_features(sensor_data: dict) -> Dict[str, float]:
    """
    Placeholder.  Will accept a dict of temperature readings from the
    SoleSense insole hardware and return a feature dict.

    Current behaviour: raises NotImplementedError with a clear message.
    """
    raise NotImplementedError(
        "Temperature sensing is a future SoleSense hardware feature.  "
        "The current StepUP-P150 dataset does not contain temperature data.  "
        "This function will be implemented when physical insole hardware is available."
    )


def temperature_hardware_status() -> Dict[str, str]:
    """
    Returns a status dict indicating that temperature is a hardware roadmap item.
    Used by the dashboard to display the Hardware Roadmap placeholder section.
    """
    return {
        "status": "HARDWARE_ROADMAP",
        "description": (
            "Temperature sensing will be introduced with the SoleSense physical insole.  "
            "The planned design includes 8 temperature sensing sites per foot, "
            "enabling bilateral thermal asymmetry monitoring.  "
            "This feature is not available in the current dataset-based prototype."
        ),
        "planned_sensors": "8 sites per insole (bilateral)",
        "planned_feature": "ΔT bilateral asymmetry, regional temperature mapping",
        "dataset_note": (
            "StepUP-P150 is a pure plantar pressure dataset captured with a "
            "floor-mounted piezoresistive mat.  No temperature measurements exist."
        ),
    }
