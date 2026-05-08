"""Actual dual_final_v23 vs N4H2 replay yaw-path diagnostics.

中文说明：本模块只比较 runtime input/NAV 的 yaw 路径差异；不读取 trace 作为
solver input，不修改 solver output，不做 output-only correction。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any


GNSS_15_COLUMNS = [
    "time",
    "lat",
    "lon",
    "height",
    "std_n",
    "std_e",
    "std_d",
    "vn",
    "ve",
    "vd",
    "std_vn",
    "std_ve",
    "std_vd",
    "yaw",
    "yaw_std",
]

EARTH_RADIUS_M = 6378137.0


def wrap_deg180(angle: float) -> float:
    wrapped = (float(angle) + 180.0) % 360.0 - 180.0
    if wrapped == 180.0:
        return -180.0
    return wrapped


def wrap_deg360(angle: float) -> float:
    return float(angle) % 360.0


def _rmse(values: list[float]) -> float | None:
    if not values:
        return None
    return math.sqrt(sum(value * value for value in values) / len(values))


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _missing_as(value: float | None, fallback: float) -> float:
    return fallback if value is None else value


def _as_rows(value: str | Path | list[dict[str, Any]], parser) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return value
    return parser(value)


def parse_15col_gnss(path: str | Path) -> list[dict[str, float]]:
    """Parse whitespace/comma separated 15-column KF-GINS `.gnss` input."""

    rows: list[dict[str, float]] = []
    previous_time: float | None = None
    with Path(path).open("r", encoding="utf-8-sig", errors="ignore") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            parts = [part for part in text.replace(",", " ").split() if part]
            if parts and parts[0].lower() == "time":
                continue
            if len(parts) != len(GNSS_15_COLUMNS):
                raise ValueError(f"{path}:{line_number} expected 15 columns, got {len(parts)}")
            values = [float(part) for part in parts]
            row = dict(zip(GNSS_15_COLUMNS, values))
            row["timestamp"] = row["time"]
            if previous_time is not None and row["time"] < previous_time:
                raise ValueError(f"{path}:{line_number} time must be monotonic")
            previous_time = row["time"]
            rows.append(row)
    return rows


def parse_kfgins_nav(path: str | Path) -> list[dict[str, float]]:
    """Parse KF_GINS_Navresult.nav without filtering or correction."""

    rows: list[dict[str, float]] = []
    previous_time: float | None = None
    with Path(path).open("r", encoding="utf-8", errors="ignore") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            parts = [part for part in text.replace(",", " ").split() if part]
            if len(parts) != 11:
                raise ValueError(f"{path}:{line_number} expected 11 columns, got {len(parts)}")
            week, time, lat, lon, height, vn, ve, vd, roll, pitch, yaw = [float(part) for part in parts]
            if previous_time is not None and time < previous_time:
                raise ValueError(f"{path}:{line_number} time must be monotonic")
            previous_time = time
            rows.append(
                {
                    "week": week,
                    "time": time,
                    "timestamp": time,
                    "lat": lat,
                    "lon": lon,
                    "height": height,
                    "vn": vn,
                    "ve": ve,
                    "vd": vd,
                    "roll": roll,
                    "pitch": pitch,
                    "yaw": yaw,
                }
            )
    return rows


def nearest_align(
    rows_a: list[dict[str, Any]],
    rows_b: list[dict[str, Any]],
    time_key: str,
    tolerance: float,
) -> list[tuple[dict[str, Any], dict[str, Any], float]]:
    """Nearest-neighbor align two sorted row streams by time key."""

    if not rows_a or not rows_b:
        return []
    b_index = 0
    pairs: list[tuple[dict[str, Any], dict[str, Any], float]] = []
    rows_a_sorted = sorted(rows_a, key=lambda row: float(row[time_key]))
    rows_b_sorted = sorted(rows_b, key=lambda row: float(row[time_key]))
    for row_a in rows_a_sorted:
        target = float(row_a[time_key])
        while (
            b_index + 1 < len(rows_b_sorted)
            and abs(float(rows_b_sorted[b_index + 1][time_key]) - target)
            <= abs(float(rows_b_sorted[b_index][time_key]) - target)
        ):
            b_index += 1
        row_b = rows_b_sorted[b_index]
        dt = target - float(row_b[time_key])
        if abs(dt) <= tolerance:
            pairs.append((row_a, row_b, dt))
    return pairs


def _horizontal_diff_m(row_a: dict[str, Any], row_b: dict[str, Any]) -> float:
    lat_a = float(row_a.get("lat", row_a.get("lat_deg")))
    lat_b = float(row_b.get("lat", row_b.get("lat_deg")))
    lon_a = float(row_a.get("lon", row_a.get("lon_deg")))
    lon_b = float(row_b.get("lon", row_b.get("lon_deg")))
    ref_lat = math.radians((lat_a + lat_b) * 0.5)
    dn = math.radians(lat_a - lat_b) * EARTH_RADIUS_M
    de = math.radians(lon_a - lon_b) * EARTH_RADIUS_M * math.cos(ref_lat)
    return math.hypot(dn, de)


def _velocity_diff_mps(row_a: dict[str, Any], row_b: dict[str, Any]) -> float:
    return math.sqrt(
        (float(row_a["vn"]) - float(row_b["vn"])) ** 2
        + (float(row_a["ve"]) - float(row_b["ve"])) ** 2
        + (float(row_a["vd"]) - float(row_b["vd"])) ** 2
    )


def compare_input_yaw_paths(
    actual_input: str | Path | list[dict[str, Any]],
    replay_input: str | Path | list[dict[str, Any]],
    *,
    tolerance: float = 0.05,
) -> dict[str, Any]:
    """Compare actual dual input.gnss with N4H2 replay input.gnss."""

    actual_rows = _as_rows(actual_input, parse_15col_gnss)
    replay_rows = _as_rows(replay_input, parse_15col_gnss)
    pairs = nearest_align(actual_rows, replay_rows, "time", tolerance)
    yaw_diffs = [wrap_deg180(float(a["yaw"]) - float(b["yaw"])) for a, b, _ in pairs]
    yaw_std_diffs = [float(a["yaw_std"]) - float(b["yaw_std"]) for a, b, _ in pairs]
    position_diffs = [_horizontal_diff_m(a, b) for a, b, _ in pairs]
    velocity_diffs = [_velocity_diff_mps(a, b) for a, b, _ in pairs]
    yaw_rmse = _rmse(yaw_diffs)
    pos_rmse = _rmse(position_diffs)
    vel_rmse = _rmse(velocity_diffs)
    if not pairs:
        status = "evidence_missing"
    elif _missing_as(yaw_rmse, 999.0) <= 3.0 and _missing_as(pos_rmse, 999.0) <= 1.0 and _missing_as(vel_rmse, 999.0) <= 0.5:
        status = "input_paths_match"
    elif _missing_as(yaw_rmse, 999.0) > 10.0:
        status = "input_yaw_mismatch"
    else:
        status = "input_paths_close_with_residual"
    return {
        "aligned_count": len(pairs),
        "actual_count": len(actual_rows),
        "replay_count": len(replay_rows),
        "input_yaw_diff_rmse_deg": yaw_rmse,
        "input_yaw_diff_mean_deg": _mean(yaw_diffs),
        "input_yaw_std_diff_mean_deg": _mean(yaw_std_diffs),
        "input_position_diff_rmse_m": pos_rmse,
        "input_velocity_diff_rmse_mps": vel_rmse,
        "input_path_parity_status": status,
        "trace_solver_input": False,
        "output_only_correction": False,
        "numerical_performance_claim": False,
    }


def compare_nav_yaw_paths(
    actual_nav: str | Path | list[dict[str, Any]],
    replay_nav: str | Path | list[dict[str, Any]],
    *,
    tolerance: float = 0.05,
) -> dict[str, Any]:
    """Compare actual final_v23 NAV with N4H2 replay NAV."""

    actual_rows = _as_rows(actual_nav, parse_kfgins_nav)
    replay_rows = _as_rows(replay_nav, parse_kfgins_nav)
    pairs = nearest_align(actual_rows, replay_rows, "time", tolerance)
    yaw_diffs = [wrap_deg180(float(a["yaw"]) - float(b["yaw"])) for a, b, _ in pairs]
    position_diffs = [_horizontal_diff_m(a, b) for a, b, _ in pairs]
    roll_diffs = [wrap_deg180(float(a["roll"]) - float(b["roll"])) for a, b, _ in pairs]
    pitch_diffs = [wrap_deg180(float(a["pitch"]) - float(b["pitch"])) for a, b, _ in pairs]
    yaw_rmse = _rmse(yaw_diffs)
    pos_rmse = _rmse(position_diffs)
    if not pairs:
        status = "evidence_missing"
    elif _missing_as(pos_rmse, 999.0) <= 1.0 and _missing_as(yaw_rmse, 0.0) > 30.0:
        status = "position_close_yaw_diverged"
    elif _missing_as(yaw_rmse, 999.0) <= 3.0:
        status = "nav_yaw_paths_match"
    else:
        status = "nav_paths_diverged"
    return {
        "aligned_count": len(pairs),
        "actual_count": len(actual_rows),
        "replay_count": len(replay_rows),
        "nav_yaw_diff_rmse_deg": yaw_rmse,
        "nav_yaw_diff_mean_deg": _mean(yaw_diffs),
        "nav_position_diff_rmse_m": pos_rmse,
        "nav_roll_diff_rmse_deg": _rmse(roll_diffs),
        "nav_pitch_diff_rmse_deg": _rmse(pitch_diffs),
        "nav_path_parity_status": status,
        "trace_solver_input": False,
        "output_only_correction": False,
        "numerical_performance_claim": False,
    }


def _candidate_transform_rmse(input_yaws: list[float], nav_yaws: list[float], transform: str) -> float | None:
    diffs: list[float] = []
    for input_yaw, nav_yaw in zip(input_yaws, nav_yaws):
        if transform == "identity":
            expected = input_yaw
        elif transform == "heading_to_math":
            expected = 90.0 - input_yaw
        elif transform == "neg":
            expected = -input_yaw
        elif transform == "plus180":
            expected = input_yaw + 180.0
        else:
            expected = input_yaw
        diffs.append(wrap_deg180(nav_yaw - expected))
    return _rmse(diffs)


def compare_input_to_nav_yaw(
    input_rows: str | Path | list[dict[str, Any]],
    nav_rows: str | Path | list[dict[str, Any]],
    *,
    tolerance: float = 0.05,
) -> dict[str, Any]:
    """Classify how NAV yaw relates to input.gnss yaw."""

    input_data = _as_rows(input_rows, parse_15col_gnss)
    nav_data = _as_rows(nav_rows, parse_kfgins_nav)
    pairs = nearest_align(input_data, nav_data, "time", tolerance)
    input_yaws = [float(row["yaw"]) for row, _, _ in pairs]
    nav_yaws = [float(row["yaw"]) for _, row, _ in pairs]
    direct_rmse = _candidate_transform_rmse(input_yaws, nav_yaws, "identity")
    heading_math_rmse = _candidate_transform_rmse(input_yaws, nav_yaws, "heading_to_math")
    neg_rmse = _candidate_transform_rmse(input_yaws, nav_yaws, "neg")
    plus180_rmse = _candidate_transform_rmse(input_yaws, nav_yaws, "plus180")
    transform_candidates = {
        "identity": direct_rmse,
        "heading_to_math": heading_math_rmse,
        "neg": neg_rmse,
        "plus180": plus180_rmse,
    }
    best_transform = min(
        (item for item in transform_candidates.items() if item[1] is not None),
        key=lambda item: float(item[1]),
        default=(None, None),
    )
    if not pairs:
        classification = "evidence_missing"
    elif direct_rmse is not None and direct_rmse <= 5.0:
        classification = "nav_tracks_input_yaw"
    elif best_transform[0] not in {None, "identity"} and best_transform[1] is not None and best_transform[1] <= 5.0:
        classification = "nav_applies_yaw_transform"
    else:
        classification = "nav_ignores_or_reinitializes_yaw"
    return {
        "aligned_count": len(pairs),
        "input_nav_yaw_diff_rmse_deg": direct_rmse,
        "input_nav_yaw_diff_mean_deg": _mean(
            [wrap_deg180(nav - input_yaw) for input_yaw, nav in zip(input_yaws, nav_yaws)]
        ),
        "transform_candidate_rmse_deg": transform_candidates,
        "best_transform_candidate": best_transform[0],
        "best_transform_rmse_deg": best_transform[1],
        "classification": classification,
        "trace_solver_input": False,
        "output_only_correction": False,
        "numerical_performance_claim": False,
    }


def make_actual_vs_replay_yaw_path_report(
    actual_input: str | Path | list[dict[str, Any]],
    replay_input: str | Path | list[dict[str, Any]],
    actual_nav: str | Path | list[dict[str, Any]],
    replay_nav: str | Path | list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the full actual-vs-replay yaw path report."""

    input_report = compare_input_yaw_paths(actual_input, replay_input)
    nav_report = compare_nav_yaw_paths(actual_nav, replay_nav)
    actual_input_nav = compare_input_to_nav_yaw(actual_input, actual_nav)
    replay_input_nav = compare_input_to_nav_yaw(replay_input, replay_nav)
    input_matches = input_report.get("input_path_parity_status") in {
        "input_paths_match",
        "input_paths_close_with_residual",
    }
    nav_differs = nav_report.get("nav_path_parity_status") in {
        "position_close_yaw_diverged",
        "nav_paths_diverged",
    }
    likely_input_generation = input_report.get("input_path_parity_status") == "input_yaw_mismatch"
    likely_runtime_config = bool(input_matches and nav_differs)
    likely_convention = bool(
        actual_input_nav.get("classification") != replay_input_nav.get("classification")
        and replay_input_nav.get("classification") == "nav_tracks_input_yaw"
    )
    if likely_input_generation:
        likely = "likely_input_generation_difference"
    elif likely_convention:
        likely = "likely_runtime_yaw_update_convention_difference"
    elif likely_runtime_config:
        likely = "likely_runtime_yaw_update_or_config_difference"
    else:
        likely = "evidence_inconclusive"
    return {
        "phase": "N4H2C-runtime",
        "actual_input_vs_replay_input_yaw": input_report,
        "actual_nav_vs_replay_nav_yaw": nav_report,
        "actual_input_vs_actual_nav_yaw": actual_input_nav,
        "replay_input_vs_replay_nav_yaw": replay_input_nav,
        "likely_path_difference": likely,
        "likely_runtime_yaw_update_or_config_difference": likely_runtime_config,
        "likely_runtime_yaw_update_convention_difference": likely_convention,
        "likely_input_generation_difference": likely_input_generation,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }
