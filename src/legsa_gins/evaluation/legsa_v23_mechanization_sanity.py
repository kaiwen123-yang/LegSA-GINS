"""Mechanization sanity checks for N4H4D2.

中文说明：区分短时 first-epoch 机械编排异常与长时间纯惯导自由漂移；
process_data 输入已经完成 Go2 FLU->FRD，LegSA-v23-core 不应二次转换。
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from statistics import mean
from typing import Any


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_imu(path: str | Path, max_rows: int = 5000) -> list[tuple[float, tuple[float, float, float], tuple[float, float, float]]]:
    rows: list[tuple[float, tuple[float, float, float], tuple[float, float, float]]] = []
    imu_path = Path(path)
    if not imu_path.exists() or not imu_path.is_file():
        return rows
    with imu_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            parts = line.strip().split()
            if len(parts) < 7 or parts[0].startswith("#"):
                continue
            try:
                time = float(parts[0])
                dtheta = (float(parts[1]), float(parts[2]), float(parts[3]))
                dvel = (float(parts[4]), float(parts[5]), float(parts[6]))
            except ValueError:
                continue
            rows.append((time, dtheta, dvel))
            if len(rows) >= max_rows:
                break
    return rows


def _norm(values: tuple[float, float, float] | list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def _window_mean_specific_force(
    rows: list[tuple[float, tuple[float, float, float], tuple[float, float, float]]],
    seconds: float,
) -> tuple[float, float, float]:
    if len(rows) < 2:
        return (0.0, 0.0, 0.0)
    start = rows[0][0]
    values: list[tuple[float, float, float]] = []
    previous_time = rows[0][0]
    for time, _dtheta, dvel in rows[1:]:
        if time - start > seconds:
            break
        dt = max(time - previous_time, 1.0e-6)
        values.append((dvel[0] / dt, dvel[1] / dt, dvel[2] / dt))
        previous_time = time
    if not values:
        return (0.0, 0.0, 0.0)
    return tuple(mean(item[i] for item in values) for i in range(3))  # type: ignore[return-value]


def analyze_imu_specific_force(input_snapshot_or_imu_path: dict[str, Any] | str | Path, config_snapshot: dict[str, Any]) -> dict[str, Any]:
    """中文说明：读取 process_data-compatible 7 列 IMU，检查 dvel/dt 与重力符号是否可疑。"""

    rows: list[tuple[float, tuple[float, float, float], tuple[float, float, float]]] = []
    if isinstance(input_snapshot_or_imu_path, (str, Path)):
      rows = _read_imu(input_snapshot_or_imu_path)
    first_dt = 0.0
    if len(rows) >= 2:
        first_dt = max(rows[1][0] - rows[0][0], 0.0)
    first_dtheta_norm = _norm(rows[0][1]) if rows else _float(config_snapshot.get("first_imu_dtheta_norm"))
    first_dvel_norm = _norm(rows[0][2]) if rows else _float(config_snapshot.get("first_imu_dvel_norm"))
    force_1s = _window_mean_specific_force(rows, 1.0)
    force_5s = _window_mean_specific_force(rows, 5.0)
    force_10s = _window_mean_specific_force(rows, 10.0)
    force_norm_1s = _norm(force_1s)
    z_mean = force_1s[2]
    gravity_sign_suspect = bool(rows and z_mean > 5.0)
    double_frame_transform_suspect = bool(rows and abs(force_1s[1]) > max(5.0, abs(force_1s[2]) * 0.8))
    return {
        "phase": "N4H4D2",
        "imu_rows_analyzed": len(rows),
        "first_imu_dt": first_dt,
        "first_imu_dtheta_norm": first_dtheta_norm,
        "first_imu_dvel_norm": first_dvel_norm,
        "dvel_dt_mean_first_1s": list(force_1s),
        "dvel_dt_mean_first_5s": list(force_5s),
        "dvel_dt_mean_first_10s": list(force_10s),
        "body_specific_force_norm_first_1s": force_norm_1s,
        "gravity_sign_suspect": gravity_sign_suspect,
        "double_frame_transform_suspect": double_frame_transform_suspect,
        "process_data_flu_to_frd_policy": "gyro=[gx,-gy,-gz], acc=[ax,-ay,-az]; no second conversion in LegSA-v23-core",
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
        "diagnostic_only": True,
    }


def _rows_from_csv(path: str | Path) -> list[dict[str, str]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _span_delta(rows: list[dict[str, str]], seconds: float, key: str) -> float:
    if not rows:
        return 0.0
    start_t = _float(rows[0].get("time_cur", rows[0].get("time", 0.0)))
    start_value = _float(rows[0].get(key))
    last_value = start_value
    for row in rows:
        time = _float(row.get("time_cur", row.get("time", 0.0)))
        if time - start_t > seconds:
            break
        last_value = _float(row.get(key))
    return last_value - start_value


def analyze_short_propagation_debug(first_propagations_csv: str | Path) -> dict[str, Any]:
    """中文说明：短时传播 sanity；长时间纯惯导漂移不能单独判定为 mechanization bug。"""

    rows = _rows_from_csv(first_propagations_csv)
    deltas: dict[str, dict[str, float]] = {}
    for seconds in (1.0, 5.0, 10.0):
        deltas[f"first_{int(seconds)}s"] = {
            "height_delta_m": _span_delta(rows, seconds, "height_m"),
            "roll_delta_deg": _span_delta(rows, seconds, "roll_deg"),
            "pitch_delta_deg": _span_delta(rows, seconds, "pitch_deg"),
            "yaw_delta_deg": _span_delta(rows, seconds, "yaw_deg"),
            "vel_n_delta_mps": _span_delta(rows, seconds, "vel_n"),
            "vel_e_delta_mps": _span_delta(rows, seconds, "vel_e"),
            "vel_d_delta_mps": _span_delta(rows, seconds, "vel_d"),
        }
    first_1s = deltas["first_1s"]
    immediate_attitude_jump = max(abs(first_1s["roll_delta_deg"]), abs(first_1s["pitch_delta_deg"])) > 5.0
    immediate_height_jump = abs(first_1s["height_delta_m"]) > 5.0
    covariance_issue = any(_float(row.get("cov_min_diag")) < -1.0e-9 for row in rows)
    mechanization_immediate_jump = immediate_attitude_jump or immediate_height_jump
    free_ins_long_drift_only = bool(rows and not mechanization_immediate_jump and not covariance_issue)
    return {
        "phase": "N4H4D2",
        "propagation_rows_analyzed": len(rows),
        "short_window_deltas": deltas,
        "mechanization_immediate_jump": mechanization_immediate_jump,
        "gravity_sign_suspect": False,
        "double_frame_transform_suspect": False,
        "free_ins_long_drift_only": free_ins_long_drift_only,
        "covariance_issue": covariance_issue,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
        "diagnostic_only": True,
    }


def build_mechanization_sanity_report(
    imu_path: str | Path | None,
    config_snapshot: dict[str, Any],
    first_propagations_csv: str | Path,
) -> dict[str, Any]:
    """中文说明：合并 IMU specific-force 与短时 propagation 诊断。"""

    imu_report = analyze_imu_specific_force(imu_path or "", config_snapshot)
    propagation_report = analyze_short_propagation_debug(first_propagations_csv)
    report = {
        "phase": "N4H4D2",
        "imu_specific_force": imu_report,
        "short_propagation": propagation_report,
        "immediate_gravity_or_frame_issue": bool(
            imu_report["gravity_sign_suspect"]
            or imu_report["double_frame_transform_suspect"]
            or propagation_report["mechanization_immediate_jump"]
        ),
        "long_free_ins_drift_only": bool(propagation_report["free_ins_long_drift_only"]),
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
        "diagnostic_only": True,
        "not_for_performance_claim": True,
    }
    return report
