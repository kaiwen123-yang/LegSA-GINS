"""BY2 lateral-baseline yaw conversion helpers.

The production convention is source-lineage based: build a short baseline from
GNSS2 minus GNSS1, convert the lateral antenna baseline to solver-visible body
yaw, and never choose the sign from trace RMSE.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def wrap360(angle_deg: float) -> float:
    return float(angle_deg) % 360.0


def circular_diff_deg(a_deg: float, b_deg: float) -> float:
    return (float(a_deg) - float(b_deg) + 180.0) % 360.0 - 180.0


@dataclass(frozen=True)
class LateralYawConversion:
    rel_n_m: float
    rel_e_m: float
    rel_d_m: float
    baseline_length_m: float
    baseline_heading_deg: float
    yaw_baseline_deg: float
    body_yaw_deg: float
    yaw_std_deg: float
    gnss_order: str = "GNSS2-GNSS1"
    baseline_vector_definition: str = "GNSS2 minus GNSS1 status relpos short baseline"
    baseline_heading_formula: str = "atan2(rel_e, rel_n)"
    lateral_conversion_formula: str = "body_yaw=wrap360(90-wrap360(-atan2(rel_e,rel_n)))"
    lateral_offset_sign: str = "baseline_heading_plus_90_equivalent"
    trace_used_for_generation: bool = False
    rmse_selected_sign: bool = False


def convert_gnss2_minus_gnss1_to_body_yaw(
    *,
    gnss1_rel_n_m: float,
    gnss1_rel_e_m: float,
    gnss1_rel_d_m: float,
    gnss2_rel_n_m: float,
    gnss2_rel_e_m: float,
    gnss2_rel_d_m: float,
    yaw_std_deg: float = 1.5,
) -> LateralYawConversion:
    rel_n = float(gnss2_rel_n_m) - float(gnss1_rel_n_m)
    rel_e = float(gnss2_rel_e_m) - float(gnss1_rel_e_m)
    rel_d = float(gnss2_rel_d_m) - float(gnss1_rel_d_m)
    baseline = math.sqrt(rel_n * rel_n + rel_e * rel_e + rel_d * rel_d)
    if baseline <= 1.0e-12:
        baseline_heading = 0.0
        yaw_baseline = 0.0
    else:
        baseline_heading = wrap360(math.degrees(math.atan2(rel_e, rel_n)))
        yaw_baseline = wrap360(-math.degrees(math.atan2(rel_e, rel_n)))
    body_yaw = wrap360(90.0 - yaw_baseline)
    return LateralYawConversion(
        rel_n_m=rel_n,
        rel_e_m=rel_e,
        rel_d_m=rel_d,
        baseline_length_m=baseline,
        baseline_heading_deg=baseline_heading,
        yaw_baseline_deg=yaw_baseline,
        body_yaw_deg=body_yaw,
        yaw_std_deg=float(yaw_std_deg),
    )

