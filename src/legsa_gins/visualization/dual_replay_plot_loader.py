"""Load dual_final_v23 and fresh replay data for visual validation.

中文说明：本模块只读取 dual_final_v23 official artifacts 与 N4H2 replay
artifacts；trace/reference 仅用于 evaluation reference reconstruction，不进入
solver input。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.actual_vs_replay_yaw_path import (
    parse_15col_gnss as _parse_15col_gnss,
)
from legsa_gins.evaluation.error_series_parity import load_official_error_series
from legsa_gins.evaluation.official_case_review_reproduction import parse_kfgins_nav as _parse_kfgins_nav
from legsa_gins.evaluation.replay_reference_mapping_audit import locate_n4h2_replay_outputs
from legsa_gins.evaluation.trajectory_metrics import EARTH_RADIUS_M


STD_COLUMNS = [
    "time",
    "std_pos_n_m",
    "std_pos_e_m",
    "std_pos_d_m",
    "std_vel_n_mps",
    "std_vel_e_mps",
    "std_vel_d_mps",
    "std_roll_deg",
    "std_pitch_deg",
    "std_yaw_deg",
    "std_gyrbias_x_dph",
    "std_gyrbias_y_dph",
    "std_gyrbias_z_dph",
    "std_accbias_x_mgal",
    "std_accbias_y_mgal",
    "std_accbias_z_mgal",
    "std_gyrscale_x_ppm",
    "std_gyrscale_y_ppm",
    "std_gyrscale_z_ppm",
    "std_accscale_x_ppm",
    "std_accscale_y_ppm",
    "std_accscale_z_ppm",
]


def _as_path(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    candidate = Path(path)
    return candidate if candidate.exists() else None


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _is_finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _check_rows(rows: list[dict[str, Any]], *, time_key: str = "timestamp") -> dict[str, Any]:
    previous: float | None = None
    monotonic = True
    finite = True
    for row in rows:
        if time_key in row:
            current = float(row[time_key])
            if previous is not None and current < previous:
                monotonic = False
            previous = current
        for value in row.values():
            if isinstance(value, (int, float)) and not math.isfinite(float(value)):
                finite = False
    return {
        "row_count": len(rows),
        "time_monotonic": monotonic,
        "no_nan_inf": finite,
    }


def wrap_deg180(angle: float) -> float:
    wrapped = (float(angle) + 180.0) % 360.0 - 180.0
    if wrapped == 180.0:
        return -180.0
    return wrapped


def parse_15col_gnss(path: str | Path) -> list[dict[str, float]]:
    return _parse_15col_gnss(path)


def parse_kfgins_nav(path: str | Path) -> list[dict[str, float]]:
    return _parse_kfgins_nav(path)


def parse_kfgins_std(path: str | Path) -> list[dict[str, float]]:
    """Parse KF_GINS_STD.txt into finite non-negative STD rows."""

    rows: list[dict[str, float]] = []
    previous_time: float | None = None
    with Path(path).open("r", encoding="utf-8", errors="ignore") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            parts = [part for part in text.replace(",", " ").split() if part]
            if parts and parts[0].lower() in {"time", "tow"}:
                continue
            if len(parts) != len(STD_COLUMNS):
                raise ValueError(f"{path}:{line_number} expected {len(STD_COLUMNS)} columns, got {len(parts)}")
            values = [float(part) for part in parts]
            if any(not math.isfinite(value) for value in values):
                raise ValueError(f"{path}:{line_number} contains NaN/Inf")
            if previous_time is not None and values[0] < previous_time:
                raise ValueError(f"{path}:{line_number} time must be monotonic non-decreasing")
            previous_time = values[0]
            for name, value in zip(STD_COLUMNS[1:], values[1:]):
                if value < 0.0:
                    raise ValueError(f"{path}:{line_number} {name} must be >= 0")
            row = dict(zip(STD_COLUMNS, values))
            row["timestamp"] = row["time"]
            rows.append(row)
    return rows


def parse_error_series(path: str | Path) -> list[dict[str, Any]]:
    return load_official_error_series(path)


def load_summary_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_error_series_csv(rows: list[dict[str, Any]], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output.write_text("", encoding="utf-8")
        return output
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output


def local_neu_from_origin(rows: list[dict[str, Any]], origin: dict[str, Any]) -> list[dict[str, float]]:
    """Convert lat/lon/height rows to local north/east/up coordinates."""

    lat0 = float(origin.get("lat_deg", origin.get("lat")))
    lon0 = float(origin.get("lon_deg", origin.get("lon")))
    h0 = float(origin.get("height_m", origin.get("height")))
    lat0_rad = math.radians(lat0)
    converted: list[dict[str, float]] = []
    for row in rows:
        lat = float(row.get("lat_deg", row.get("lat")))
        lon = float(row.get("lon_deg", row.get("lon")))
        height = float(row.get("height_m", row.get("height")))
        converted.append(
            {
                "timestamp": float(row.get("timestamp", row.get("time"))),
                "north_m": math.radians(lat - lat0) * EARTH_RADIUS_M,
                "east_m": math.radians(lon - lon0) * EARTH_RADIUS_M * math.cos(lat0_rad),
                "up_m": height - h0,
            }
        )
    return converted


def load_dual_official_artifacts(dual_root: str | Path) -> dict[str, Any]:
    """Load the official dual artifact group from a runtime-only root."""

    root = Path(dual_root)
    paths = {
        "input_gnss": root / "input.gnss",
        "nav": root / "KF_GINS_Navresult.nav",
        "std": root / "KF_GINS_STD.txt",
        "summary": root / "summary.json",
        "error_series": root / "error_series.csv",
    }
    missing = [name for name, path in paths.items() if not path.exists()]
    if missing:
        return {
            "role_alias": "DUAL_FINAL_V23_ARTIFACT_ROOT",
            "paths": {name: str(path) for name, path in paths.items()},
            "evidence_status": "evidence_missing",
            "evidence_missing": missing,
            "trace_solver_input": False,
            "output_only_correction": False,
            "solver_output_changed": False,
            "numerical_performance_claim": False,
        }
    input_rows = parse_15col_gnss(paths["input_gnss"])
    nav_rows = parse_kfgins_nav(paths["nav"])
    std_rows = parse_kfgins_std(paths["std"])
    summary = load_summary_json(paths["summary"])
    error_rows = parse_error_series(paths["error_series"])
    return {
        "role_alias": "DUAL_FINAL_V23_ARTIFACT_ROOT",
        "paths": {name: str(path) for name, path in paths.items()},
        "input_rows": input_rows,
        "nav_rows": nav_rows,
        "std_rows": std_rows,
        "summary": summary,
        "error_rows": error_rows,
        "validation": {
            "input": _check_rows(input_rows, time_key="time"),
            "nav": _check_rows(nav_rows),
            "std": _check_rows(std_rows),
            "error_series": _check_rows(error_rows),
        },
        "evidence_status": "loaded",
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }


def load_n4h2_fresh_replay_artifacts(
    n4h2_root: str | Path,
    n4h2d_output_root: str | Path | None = None,
) -> dict[str, Any]:
    """Load replay NAV/STD/input plus any existing fresh N4H2D outputs."""

    root = Path(n4h2_root)
    locations = locate_n4h2_replay_outputs(root)
    located = locations.get("located_files") or {}
    replay_nav_path = _as_path(located.get("replay_nav"))
    input_path = _as_path(located.get("input_gnss"))
    std_path = _first_existing(
        [
            root / "replay" / "kfgins_output" / "KF_GINS_STD.txt",
            root / "KF_GINS_STD.txt",
        ]
    )
    fresh_root = Path(n4h2d_output_root) if n4h2d_output_root else None
    fresh_summary_path = _as_path(fresh_root / "FRESH_REPLAY_SUMMARY.json") if fresh_root else None
    fresh_error_path = _as_path(fresh_root / "FRESH_REPLAY_ERROR_SERIES.csv") if fresh_root else None
    replay_nav = parse_kfgins_nav(replay_nav_path) if replay_nav_path else []
    replay_std = parse_kfgins_std(std_path) if std_path else []
    input_rows = parse_15col_gnss(input_path) if input_path else []
    fresh_summary = load_summary_json(fresh_summary_path) if fresh_summary_path else {}
    fresh_errors = parse_error_series(fresh_error_path) if fresh_error_path else []
    missing = [
        name
        for name, value in {
            "replay_nav": replay_nav_path,
            "input_gnss": input_path,
            "replay_std": std_path,
            "fresh_summary": fresh_summary_path,
            "fresh_error_series": fresh_error_path,
        }.items()
        if value is None
    ]
    return {
        "role_alias": "N4H2_ARTIFACTS_ROOT",
        "locations": locations,
        "paths": {
            "replay_nav": str(replay_nav_path) if replay_nav_path else None,
            "input_gnss": str(input_path) if input_path else None,
            "replay_std": str(std_path) if std_path else None,
            "fresh_summary": str(fresh_summary_path) if fresh_summary_path else None,
            "fresh_error_series": str(fresh_error_path) if fresh_error_path else None,
        },
        "replay_nav_rows": replay_nav,
        "replay_std_rows": replay_std,
        "input_rows": input_rows,
        "fresh_summary": fresh_summary,
        "fresh_error_rows": fresh_errors,
        "validation": {
            "replay_nav": _check_rows(replay_nav),
            "replay_std": _check_rows(replay_std),
            "input": _check_rows(input_rows, time_key="time"),
            "fresh_error_series": _check_rows(fresh_errors),
        },
        "evidence_status": "loaded" if replay_nav_path and fresh_summary_path and fresh_error_path else "partial_loaded",
        "evidence_missing": missing,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }

