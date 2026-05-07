"""Event-normalized algorithm time for BY2 diagnostic trials.

中文说明：kick 只辅助寻找实验段，solver 使用各自 formal start 归零后的 algo_time_sec。
"""

from __future__ import annotations

import csv
import statistics
from pathlib import Path
from typing import Any

from legsa_gins.datasets.by2.unitree_imu_semantics import (
    accel_norm,
    foot_force_delta,
    foot_speed_body_norm,
    gyro_norm,
)
from legsa_gins.time_alignment.time_domain_audit import audit_by2_time_domains


def _as_float(value: Any, default: float | None = None) -> float | None:
    if value is None or str(value).strip() == "":
        return default
    return float(value)


def _as_bool(value: Any) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(rows: list[dict[str, Any]], path: str | Path, fieldnames: list[str]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * pct))
    return ordered[max(0, min(index, len(ordered) - 1))]


def detect_go2_kick_event(
    body_state_csv: str | Path,
    *,
    zscore_threshold: float = 6.0,
    min_score: float = 3.0,
) -> dict[str, Any]:
    rows = _read_csv(body_state_csv)
    if not rows:
        return {"go2_kick_raw_time": None, "kick_score": 0.0, "detection_method": None, "evidence_status": "evidence_missing"}
    initial = rows[: max(5, min(40, len(rows) // 10 or 1))]
    acc_initial = [accel_norm(row) for row in initial]
    median_acc = statistics.median(acc_initial)
    force_deltas = [foot_force_delta(rows[index - 1] if index else None, row) for index, row in enumerate(rows)]
    force_scale = max(_percentile(force_deltas, 0.95), 1.0)
    best = {"score": -1.0, "row": rows[0], "method": "initial_fallback"}
    for index, row in enumerate(rows):
        gyro_score = gyro_norm(row) / max(min_score, 1.0)
        acc_score = abs(accel_norm(row) - median_acc) / max(min_score, 1.0)
        yaw_score = abs(_as_float(row.get("yaw_speed_radps"), 0.0) or 0.0) / max(min_score, 1.0)
        foot_speed_score = foot_speed_body_norm(row) / max(min_score, 1.0)
        force_score = force_deltas[index] / force_scale
        score = max(gyro_score, acc_score, yaw_score, foot_speed_score, force_score)
        if score > best["score"]:
            best = {"score": score, "row": row, "method": "max_motion_impulse_score"}
    raw_time = _as_float(best["row"].get("timestamp"))
    status = "detected" if float(best["score"]) >= min_score or float(best["score"]) >= zscore_threshold else "weak_candidate"
    return {
        "go2_kick_raw_time": raw_time,
        "kick_score": float(best["score"]),
        "detection_method": best["method"],
        "median_initial_acc_norm": median_acc,
        "evidence_status": status,
    }


def detect_go2_formal_motion_start(
    body_state_csv: str | Path,
    kick_report: dict[str, Any],
    *,
    sustained_window: int = 5,
    min_velocity: float = 0.02,
    min_gyro_norm: float = 0.05,
    min_foot_speed_norm: float = 0.05,
) -> dict[str, Any]:
    rows = _read_csv(body_state_csv)
    kick_time = kick_report.get("go2_kick_raw_time")
    for index, row in enumerate(rows):
        raw_time = _as_float(row.get("timestamp"))
        if raw_time is None or (kick_time is not None and raw_time <= float(kick_time)):
            continue
        window = rows[index : index + sustained_window]
        if len(window) < sustained_window:
            break
        prev = rows[index - 1] if index > 0 else None
        checks = {
            "go2_velocity_norm": all(
                (
                    ((_as_float(item.get("go2_velocity_0"), 0.0) or 0.0) ** 2
                    + (_as_float(item.get("go2_velocity_1"), 0.0) or 0.0) ** 2
                    + (_as_float(item.get("go2_velocity_2"), 0.0) or 0.0) ** 2)
                    ** 0.5
                )
                >= min_velocity
                for item in window
            ),
            "gyro_norm": all(gyro_norm(item) >= min_gyro_norm for item in window),
            "yaw_speed": all(abs(_as_float(item.get("yaw_speed_radps"), 0.0) or 0.0) >= min_gyro_norm for item in window),
            "foot_speed_body_norm": all(foot_speed_body_norm(item) >= min_foot_speed_norm for item in window),
            "foot_force_change": foot_force_delta(prev, row) > 0.0,
            "mode_or_gait_change": any(
                window[0].get(field) != item.get(field)
                for item in window[1:]
                for field in ["mode", "gait_type"]
            ),
        }
        for name, passed in checks.items():
            if passed:
                return {
                    "go2_formal_start_raw_time": raw_time,
                    "selected_feature": name,
                    "kick_used_as_search_anchor": True,
                    "evidence_status": "detected_after_kick",
                }
    fallback = _as_float(rows[0].get("timestamp")) if rows else None
    return {
        "go2_formal_start_raw_time": fallback,
        "selected_feature": "fallback_first_row_evidence_missing",
        "kick_used_as_search_anchor": True,
        "evidence_status": "evidence_missing",
    }


def _horizontal_m(lat0: float, lon0: float, lat1: float, lon1: float) -> float:
    import math

    radius = 6378137.0
    north = math.radians(lat1 - lat0) * radius
    east = math.radians(lon1 - lon0) * radius * math.cos(math.radians(lat0))
    return math.hypot(north, east)


def detect_gnss_formal_motion_start(
    gnss_status_csv: str | Path,
    *,
    min_displacement_m: float = 0.2,
    min_consecutive: int = 3,
) -> dict[str, Any]:
    rows = [row for row in _read_csv(gnss_status_csv) if _as_bool(row.get("has_position"))]
    if not rows:
        return {"gnss_formal_start_raw_time": None, "gnss_time_type": None, "selected_feature": None, "evidence_status": "evidence_missing"}
    lat0 = _as_float(rows[0].get("lat_deg"))
    lon0 = _as_float(rows[0].get("lon_deg"))
    for index in range(1, len(rows) - min_consecutive + 1):
        window = rows[index : index + min_consecutive]
        if lat0 is None or lon0 is None:
            break
        displacements = [
            _horizontal_m(lat0, lon0, _as_float(item.get("lat_deg"), lat0) or lat0, _as_float(item.get("lon_deg"), lon0) or lon0)
            for item in window
        ]
        heading_ok = all(_as_bool(item.get("heading_valid")) for item in window)
        if all(value >= min_displacement_m for value in displacements) or heading_ok:
            return {
                "gnss_formal_start_raw_time": _as_float(window[0].get("time_unix"), _as_float(window[0].get("tow"))),
                "gnss_time_type": "time_unix",
                "selected_feature": "horizontal_displacement_or_heading_valid",
                "evidence_status": "detected",
            }
    return {
        "gnss_formal_start_raw_time": _as_float(rows[0].get("time_unix"), _as_float(rows[0].get("tow"))),
        "gnss_time_type": "time_unix",
        "selected_feature": "fallback_first_position",
        "evidence_status": "weak_candidate",
    }


def normalize_time_axis(raw_time: float, start_time: float) -> float:
    return raw_time - start_time


def add_algo_time_to_csv(
    input_csv: str | Path,
    output_csv: str | Path,
    *,
    raw_time_field: str,
    start_time: float,
    end_algo_time_sec: float | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(input_csv).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        if "raw_time" not in fieldnames:
            fieldnames.append("raw_time")
        if "algo_time_sec" not in fieldnames:
            fieldnames.append("algo_time_sec")
        for raw in reader:
            raw_time = _as_float(raw.get(raw_time_field))
            if raw_time is None:
                continue
            algo_time = normalize_time_axis(raw_time, start_time)
            if algo_time < 0.0:
                continue
            if end_algo_time_sec is not None and algo_time > end_algo_time_sec:
                continue
            row = dict(raw)
            row["raw_time"] = raw_time
            row["algo_time_sec"] = algo_time
            rows.append(row)
    _write_csv(rows, output_csv, fieldnames)
    return rows


def compute_common_algorithm_window(
    go2_rows: list[dict[str, Any]],
    gnss_rows: list[dict[str, Any]],
    *,
    end_margin_sec: float = 5.0,
) -> dict[str, Any]:
    go2_times = [_as_float(row.get("algo_time_sec")) for row in go2_rows]
    gnss_times = [_as_float(row.get("algo_time_sec")) for row in gnss_rows]
    go2_times = [value for value in go2_times if value is not None]
    gnss_times = [value for value in gnss_times if value is not None]
    go2_duration = max(go2_times) if go2_times else 0.0
    gnss_duration = max(gnss_times) if gnss_times else 0.0
    end_time = min(go2_duration, gnss_duration) - end_margin_sec
    return {
        "start_algo_time_sec": 0.0,
        "go2_duration_sec": go2_duration,
        "gnss_duration_sec": gnss_duration,
        "end_margin_sec": end_margin_sec,
        "end_algo_time_sec": end_time,
        "evidence_status": "common_window_ready" if end_time > 0.0 else "evidence_missing",
    }


def make_event_normalization_report(
    *,
    go2_body_state_csv: str | Path,
    gnss_status_csv: str | Path,
    trace_csv: str | Path | None,
    end_margin_sec: float,
) -> dict[str, Any]:
    time_audit = audit_by2_time_domains(go2_body_state_csv, gnss_status_csv, trace_csv)
    kick = detect_go2_kick_event(go2_body_state_csv)
    go2_start = detect_go2_formal_motion_start(go2_body_state_csv, kick)
    gnss_start = detect_gnss_formal_motion_start(gnss_status_csv)
    go2_rows = add_algo_time_to_csv(
        go2_body_state_csv,
        Path(go2_body_state_csv).with_name("BY2_GO2_BODY_STATE_ALGO_TIME.csv"),
        raw_time_field="timestamp",
        start_time=float(go2_start["go2_formal_start_raw_time"] or 0.0),
    )
    gnss_rows = add_algo_time_to_csv(
        gnss_status_csv,
        Path(gnss_status_csv).with_name("BY2_GNSS_STATUS_ALGO_TIME.csv"),
        raw_time_field="time_unix",
        start_time=float(gnss_start["gnss_formal_start_raw_time"] or 0.0),
    )
    window = compute_common_algorithm_window(go2_rows, gnss_rows, end_margin_sec=end_margin_sec)
    report = {
        "alignment_method": "event_normalized_algorithm_time",
        "clock_sync_claim": False,
        "physical_time_offset_claim": False,
        "event_normalized_time_axis": True,
        "trace_used_for_alignment": False,
        "trace_solver_input": False,
        "go2_time_domain": time_audit["go2_raw_time_domain"],
        "gnss_time_domain": time_audit["gnss_time_domain"],
        "trace_time_domain": time_audit["trace_time_domain"],
        "go2_kick_raw_time": kick.get("go2_kick_raw_time"),
        "go2_formal_start_raw_time": go2_start.get("go2_formal_start_raw_time"),
        "gnss_formal_start_raw_time": gnss_start.get("gnss_formal_start_raw_time"),
        "start_algo_time_sec": 0.0,
        "go2_duration_sec": window["go2_duration_sec"],
        "gnss_duration_sec": window["gnss_duration_sec"],
        "end_margin_sec": end_margin_sec,
        "end_algo_time_sec": window["end_algo_time_sec"],
        "direct_time_comparison_allowed": time_audit["direct_time_comparison_allowed"],
        "event_pair_delta_raw_units_not_clock_offset": (
            (go2_start.get("go2_formal_start_raw_time") or 0.0)
            - (gnss_start.get("gnss_formal_start_raw_time") or 0.0)
        ),
        "go2_kick_report": kick,
        "go2_formal_start_report": go2_start,
        "gnss_formal_start_report": gnss_start,
        "time_domain_audit": time_audit,
        "evidence_status": window["evidence_status"],
    }
    return report

