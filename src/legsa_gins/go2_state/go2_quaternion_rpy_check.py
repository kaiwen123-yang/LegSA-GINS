"""Quaternion/RPY consistency checks for N7A Go2 attitude weak prior.

中文说明：只有 Go2 quaternion 与 rpy 内部一致时，roll/pitch weak prior 才允许
进入 EKF；这里不读取 trace 或 final_v23 输出。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.datasets.by2.unitree_imu_semantics import quaternion_wxyz_to_rpy


def _as_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _wrap_rad(value: float) -> float:
    return (value + math.pi) % (2.0 * math.pi) - math.pi


def _norm_quat(values: list[float]) -> list[float] | None:
    norm = math.sqrt(sum(item * item for item in values))
    if norm <= 0.0:
        return None
    return [item / norm for item in values]


def _max_delta(rows: list[dict[str, Any]], order: str) -> float | None:
    deltas: list[float] = []
    for row in rows:
        raw = [_as_float(row.get(field)) for field in ["quat_w", "quat_x", "quat_y", "quat_z"]]
        rpy = [_as_float(row.get(field)) for field in ["roll_rad", "pitch_rad", "yaw_rad"]]
        if any(value is None for value in raw + rpy):
            continue
        if order == "wxyz":
            quat = _norm_quat([float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3])])
        else:
            quat = _norm_quat([float(raw[3]), float(raw[0]), float(raw[1]), float(raw[2])])
        if quat is None:
            continue
        derived = quaternion_wxyz_to_rpy(quat)
        deltas.extend(abs(_wrap_rad(derived[index] - float(rpy[index]))) for index in range(3))
    return max(deltas) if deltas else None


def check_quaternion_rpy(rows: list[dict[str, Any]], *, threshold_rad: float = 0.05) -> dict[str, Any]:
    wxyz_delta = _max_delta(rows, "wxyz")
    xyzw_delta = _max_delta(rows, "xyzw")
    selected = "wxyz"
    selected_delta = wxyz_delta
    if selected_delta is None or (xyzw_delta is not None and xyzw_delta < selected_delta):
        selected = "xyzw_diagnostic_only"
        selected_delta = xyzw_delta
    status = "passed" if selected == "wxyz" and selected_delta is not None and selected_delta <= threshold_rad else "suspicious"
    return {
        "quaternion_order_selected": selected,
        "max_quat_rpy_delta_rad": selected_delta,
        "wxyz_max_quat_rpy_delta_rad": wxyz_delta,
        "xyzw_diagnostic_max_quat_rpy_delta_rad": xyzw_delta,
        "rpy_consistency_status": status,
        "go2_rpy_unit": "rad",
        "activation_allowed_for_attitude_prior": status == "passed",
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }


def write_quaternion_rpy_report(rows: list[dict[str, Any]], output_path: str | Path) -> dict[str, Any]:
    report = check_quaternion_rpy(rows)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
