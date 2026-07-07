"""Synthetic short-baseline double-difference data for DA01R2B.

The generator keeps the geometry fully controlled: ENU frame, lateral antenna
mounting, known integer ambiguities, no slips, and optional small carrier/code
noise. It does not read trace or project runtime payloads.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from .common import wrap360


BASELINE_LENGTH_M = 0.355147
GPS_L1_WAVELENGTH_M = 0.190293672798365
BODY_YAW_CASES_DEG = (0.0, 30.0, 90.0, 179.0, -179.0)
DEFAULT_SATELLITE_COUNT = 8


@dataclass(frozen=True)
class SyntheticDDCase:
    case_id: str
    body_yaw_deg: float
    noise_std_m: float
    baseline_east_m: float
    baseline_north_m: float
    baseline_up_m: float
    rows: tuple[dict[str, Any], ...]
    trace_used: bool = False
    cycle_slip: bool = False

    @property
    def baseline_enu(self) -> tuple[float, float, float]:
        return (self.baseline_east_m, self.baseline_north_m, self.baseline_up_m)

    @property
    def baseline_heading_deg(self) -> float:
        return wrap360(math.degrees(math.atan2(self.baseline_east_m, self.baseline_north_m)))


def baseline_enu_from_body_yaw(
    body_yaw_deg: float,
    *,
    baseline_length_m: float = BASELINE_LENGTH_M,
    lateral_offset_deg: float = 90.0,
) -> tuple[float, float, float]:
    """Return GNSS2-GNSS1 ENU baseline for the lateral +90 yaw rule."""

    heading_deg = wrap360(float(body_yaw_deg) - float(lateral_offset_deg))
    heading_rad = math.radians(heading_deg)
    east = float(baseline_length_m) * math.sin(heading_rad)
    north = float(baseline_length_m) * math.cos(heading_rad)
    return (east, north, 0.0)


def _satellite_los_enu(satellite_count: int) -> list[tuple[str, tuple[float, float, float], float, float]]:
    if satellite_count < 6 or satellite_count > 10:
        raise ValueError("synthetic satellite_count must be in [6, 10]")
    azimuths = [18.0, 73.0, 128.0, 201.0, 256.0, 314.0, 42.0, 166.0, 286.0, 338.0]
    elevations = [66.0, 34.0, 51.0, 27.0, 43.0, 58.0, 21.0, 72.0, 36.0, 49.0]
    sats: list[tuple[str, tuple[float, float, float], float, float]] = []
    for idx in range(satellite_count):
        az = math.radians(azimuths[idx])
        el = math.radians(elevations[idx])
        cos_el = math.cos(el)
        los = (cos_el * math.sin(az), cos_el * math.cos(az), math.sin(el))
        sats.append((f"G{idx + 1:02d}", los, elevations[idx], azimuths[idx]))
    return sats


def _known_integer(index: int, body_yaw_deg: float) -> int:
    return int(((index + 2) * 5 + round(body_yaw_deg)) % 17 - 8)


def generate_synthetic_dd_case(
    *,
    body_yaw_deg: float,
    noise_std_m: float = 0.0,
    satellite_count: int = DEFAULT_SATELLITE_COUNT,
    seed: int = 0,
    baseline_length_m: float = BASELINE_LENGTH_M,
    lateral_offset_deg: float = 90.0,
) -> SyntheticDDCase:
    """Generate one controlled DD case in ENU coordinates."""

    baseline = baseline_enu_from_body_yaw(
        body_yaw_deg,
        baseline_length_m=baseline_length_m,
        lateral_offset_deg=lateral_offset_deg,
    )
    sats = _satellite_los_enu(satellite_count)
    pivot_id, pivot_los, pivot_el, pivot_az = max(sats, key=lambda item: item[2])
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for index, (sat_id, los, elevation, azimuth) in enumerate(sats):
        if sat_id == pivot_id:
            continue
        # The sign convention matches the existing DA01 DD design row:
        # pivot LOS minus satellite LOS, dotted with GNSS2-GNSS1 baseline.
        h = tuple(p - s for p, s in zip(pivot_los, los))
        geometric_m = float(sum(h_i * b_i for h_i, b_i in zip(h, baseline)))
        integer = _known_integer(index, body_yaw_deg)
        carrier_noise = float(rng.normal(0.0, noise_std_m)) if noise_std_m else 0.0
        code_noise = float(rng.normal(0.0, noise_std_m * 3.0)) if noise_std_m else 0.0
        rows.append(
            {
                "case_id": f"yaw_{body_yaw_deg:g}_noise_{noise_std_m:g}",
                "body_yaw_deg": body_yaw_deg,
                "satellite": sat_id,
                "pivot_satellite": pivot_id,
                "satellite_count": satellite_count,
                "elevation_deg": elevation,
                "azimuth_deg": azimuth,
                "pivot_elevation_deg": pivot_el,
                "pivot_azimuth_deg": pivot_az,
                "h_east": h[0],
                "h_north": h[1],
                "h_up": h[2],
                "geometric_dd_m": geometric_m,
                "known_integer_ambiguity": integer,
                "wavelength_m": GPS_L1_WAVELENGTH_M,
                "dd_carrier_m": geometric_m + GPS_L1_WAVELENGTH_M * integer + carrier_noise,
                "dd_code_m": geometric_m + code_noise,
                "noise_std_m": noise_std_m,
                "weight": 1.0 + max(0.0, elevation) / 90.0,
                "cycle_slip": False,
                "trace_used": False,
            }
        )
    return SyntheticDDCase(
        case_id=f"yaw_{body_yaw_deg:g}_noise_{noise_std_m:g}",
        body_yaw_deg=body_yaw_deg,
        noise_std_m=noise_std_m,
        baseline_east_m=baseline[0],
        baseline_north_m=baseline[1],
        baseline_up_m=baseline[2],
        rows=tuple(rows),
    )


def generate_synthetic_suite(
    *,
    yaw_cases: tuple[float, ...] = BODY_YAW_CASES_DEG,
    noise_levels_m: tuple[float, ...] = (0.0, 0.001),
    satellite_count: int = DEFAULT_SATELLITE_COUNT,
) -> list[SyntheticDDCase]:
    cases: list[SyntheticDDCase] = []
    for yaw_index, yaw in enumerate(yaw_cases):
        for noise_index, noise in enumerate(noise_levels_m):
            cases.append(
                generate_synthetic_dd_case(
                    body_yaw_deg=yaw,
                    noise_std_m=noise,
                    satellite_count=satellite_count,
                    seed=1000 + yaw_index * 10 + noise_index,
                )
            )
    return cases


def synthetic_test_case_rows(cases: list[SyntheticDDCase]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        for row in case.rows:
            rows.append(
                {
                    "case_id": case.case_id,
                    "body_yaw_deg": case.body_yaw_deg,
                    "noise_std_m": case.noise_std_m,
                    "baseline_length_m": BASELINE_LENGTH_M,
                    "baseline_east_m": case.baseline_east_m,
                    "baseline_north_m": case.baseline_north_m,
                    "baseline_up_m": case.baseline_up_m,
                    **row,
                }
            )
    return rows
