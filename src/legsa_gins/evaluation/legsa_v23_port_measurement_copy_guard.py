"""Measurement-copy guard for N4H4R3B source-backed port audits.

中文说明：本模块只比较 port 输出与 clean GNSS 观测是否出现逐行复制迹象；
GNSS 可以作为 solver measurement，但不能作为 NAV/EVAL_NAV writer 的直接替代输出。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

EARTH_RADIUS_M = 6378137.0


def _wrap_deg(value: float) -> float:
    wrapped = (value + 180.0) % 360.0 - 180.0
    return -180.0 if wrapped == 180.0 else wrapped


def _rmse(values: list[float]) -> float | None:
    if not values:
        return None
    return math.sqrt(sum(value * value for value in values) / len(values))


def _row_from_values(values: list[str], *, csv_mode: bool = False) -> dict[str, float] | None:
    try:
        if csv_mode:
            raise ValueError
        if len(values) < 10:
            return None
        return {
            "time": float(values[0]),
            "lat_deg": float(values[1]),
            "lon_deg": float(values[2]),
            "height_m": float(values[3]),
            "vn": float(values[4]),
            "ve": float(values[5]),
            "vd": float(values[6]),
            "roll_deg": float(values[7]),
            "pitch_deg": float(values[8]),
            "yaw_deg": float(values[9]),
        }
    except ValueError:
        return None


def parse_nav_or_eval_nav(path: str | Path) -> list[dict[str, float]]:
    """Parse LegSA_PORT_NAV.nav or EVAL_NAV.csv into common rows."""

    file_path = Path(path)
    if not file_path.exists():
        return []
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    first_data = next((line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")), "")
    rows: list[dict[str, float]] = []
    if "," in first_data and any(name in first_data for name in ["time", "lat_deg"]):
        with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for raw in csv.DictReader(handle):
                try:
                    rows.append(
                        {
                            "time": float(raw.get("time") or raw.get("timestamp") or raw.get("algo_time_sec")),
                            "lat_deg": float(raw["lat_deg"]),
                            "lon_deg": float(raw["lon_deg"]),
                            "height_m": float(raw["height_m"]),
                            "vn": float(raw.get("vn", 0.0)),
                            "ve": float(raw.get("ve", 0.0)),
                            "vd": float(raw.get("vd", 0.0)),
                            "roll_deg": float(raw["roll_deg"]),
                            "pitch_deg": float(raw["pitch_deg"]),
                            "yaw_deg": float(raw["yaw_deg"]),
                        }
                    )
                except (TypeError, ValueError, KeyError):
                    continue
    else:
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            row = _row_from_values(stripped.replace(",", " ").split())
            if row:
                rows.append(row)
    rows.sort(key=lambda row: row["time"])
    return rows


def parse_clean_gnss(path: str | Path) -> list[dict[str, float]]:
    """Parse 15-column clean status-yaw GNSS measurement rows."""

    rows: list[dict[str, float]] = []
    file_path = Path(path)
    if not file_path.exists():
        return rows
    for line in file_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.replace(",", " ").split()
        if len(parts) < 15:
            continue
        try:
            lat = float(parts[1])
            lon = float(parts[2])
            if abs(lat) <= math.pi / 2 and abs(lon) <= math.pi:
                lat = math.degrees(lat)
                lon = math.degrees(lon)
            rows.append(
                {
                    "time": float(parts[0]),
                    "lat_deg": lat,
                    "lon_deg": lon,
                    "height_m": float(parts[3]),
                    "vn": float(parts[7]),
                    "ve": float(parts[8]),
                    "vd": float(parts[9]),
                    "yaw_deg": float(parts[13]),
                }
            )
        except ValueError:
            continue
    rows.sort(key=lambda row: row["time"])
    return rows


def align_nav_to_gnss(
    nav_rows: list[dict[str, float]],
    gnss_rows: list[dict[str, float]],
    tolerance: float = 0.02,
) -> list[tuple[dict[str, float], dict[str, float]]]:
    aligned: list[tuple[dict[str, float], dict[str, float]]] = []
    if not nav_rows or not gnss_rows:
        return aligned
    gnss_index = 0
    for nav in nav_rows:
        time = nav["time"]
        while (
            gnss_index + 1 < len(gnss_rows)
            and abs(gnss_rows[gnss_index + 1]["time"] - time)
            <= abs(gnss_rows[gnss_index]["time"] - time)
        ):
            gnss_index += 1
        gnss = gnss_rows[gnss_index]
        if abs(time - gnss["time"]) <= tolerance:
            aligned.append((nav, gnss))
    return aligned


def _errors(pairs: list[tuple[dict[str, float], dict[str, float]]]) -> dict[str, float | None]:
    horizontal: list[float] = []
    up: list[float] = []
    yaw: list[float] = []
    for nav, gnss in pairs:
        lat_rad = math.radians(gnss["lat_deg"])
        north = math.radians(nav["lat_deg"] - gnss["lat_deg"]) * EARTH_RADIUS_M
        east = math.radians(nav["lon_deg"] - gnss["lon_deg"]) * EARTH_RADIUS_M * math.cos(lat_rad)
        horizontal.append(math.hypot(north, east))
        up.append(nav["height_m"] - gnss["height_m"])
        yaw.append(_wrap_deg(nav["yaw_deg"] - gnss["yaw_deg"]))
    return {
        "horizontal_rmse_m": _rmse(horizontal),
        "up_rmse_m": _rmse(up),
        "yaw_rmse_deg": _rmse(yaw),
    }


def _load_writer_audit(debug_trace: str | Path | None) -> dict[str, Any]:
    if not debug_trace:
        return {}
    path = Path(debug_trace)
    if path.is_dir():
        path = path / "PORT_WRITER_SOURCE_AUDIT.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _copy_suspect(errors: dict[str, float | None], aligned_count: int, measurement_count: int) -> bool:
    if aligned_count < max(3, int(0.5 * max(1, measurement_count))):
        return False
    h = errors.get("horizontal_rmse_m")
    up = errors.get("up_rmse_m")
    yaw = errors.get("yaw_rmse_deg")
    return (
        h is not None
        and up is not None
        and yaw is not None
        and h <= 1.0e-5
        and abs(up) <= 1.0e-5
        and yaw <= 1.0e-5
    )


def analyze_measurement_copy(
    nav_path: str | Path,
    eval_nav_path: str | Path,
    clean_gnss_path: str | Path,
    debug_trace: str | Path | None = None,
) -> dict[str, Any]:
    nav_rows = parse_nav_or_eval_nav(nav_path)
    eval_rows = parse_nav_or_eval_nav(eval_nav_path)
    gnss_rows = parse_clean_gnss(clean_gnss_path)
    nav_pairs = align_nav_to_gnss(nav_rows, gnss_rows)
    eval_pairs = align_nav_to_gnss(eval_rows, gnss_rows)
    nav_errors = _errors(nav_pairs)
    eval_errors = _errors(eval_pairs)
    writer = _load_writer_audit(debug_trace)
    nav_copy = _copy_suspect(nav_errors, len(nav_pairs), len(gnss_rows))
    eval_copy = _copy_suspect(eval_errors, len(eval_pairs), len(gnss_rows))
    output_substitution = bool(
        writer.get("writer_copy_suspect")
        or writer.get("nav_writer_uses_gnss_measurement")
        or writer.get("eval_nav_writer_uses_gnss_measurement")
        or writer.get("reference_output_used")
        or writer.get("final_v23_output_used")
        or writer.get("trace_output_used")
    )
    return {
        "phase": "N4H4R3B",
        "nav_vs_gnss_aligned_count": len(nav_pairs),
        "eval_nav_vs_gnss_aligned_count": len(eval_pairs),
        "clean_gnss_count": len(gnss_rows),
        "nav_minus_gnss_horizontal_rmse_m": nav_errors["horizontal_rmse_m"],
        "nav_minus_gnss_up_rmse_m": nav_errors["up_rmse_m"],
        "nav_minus_gnss_yaw_rmse_deg": nav_errors["yaw_rmse_deg"],
        "eval_nav_minus_gnss_horizontal_rmse_m": eval_errors["horizontal_rmse_m"],
        "eval_nav_minus_gnss_up_rmse_m": eval_errors["up_rmse_m"],
        "eval_nav_minus_gnss_yaw_rmse_deg": eval_errors["yaw_rmse_deg"],
        "nav_writer_uses_nav_state": writer.get("nav_writer_uses_nav_state", True),
        "eval_nav_writer_uses_nav_state": writer.get("eval_nav_writer_uses_nav_state", True),
        "nav_writer_uses_gnss_measurement": writer.get("nav_writer_uses_gnss_measurement", False),
        "eval_nav_writer_uses_gnss_measurement": writer.get("eval_nav_writer_uses_gnss_measurement", False),
        "measurement_copy_suspect": nav_copy or eval_copy,
        "output_substitution_suspect": output_substitution,
        "engineering_backbone_parity_only": True,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
