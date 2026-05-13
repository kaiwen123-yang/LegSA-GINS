"""N7C5 foot kinematic velocity candidate mining.

中文说明：foot kinematic velocity 是候选本体观测，不在 N7C5 激活进 EKF；
它只用 Go2 foot/body/contact 和 cross-source consistency 做诊断，不读取 trace/final_v23 调参。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


FOOT_KINEMATIC_FIELDS = [
    "time",
    "candidate_vn",
    "candidate_ve",
    "candidate_vd",
    "weight_sum",
    "stance_foot_count",
    "slip_risk",
    "go2_vn",
    "go2_ve",
    "receiver_vn",
    "receiver_ve",
    "raw_vn",
    "raw_ve",
    "residual_to_go2",
    "residual_to_receiver",
    "residual_to_raw",
]


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _nearest(rows: list[dict[str, Any]], time_value: float, start: int, tol: float) -> tuple[dict[str, Any] | None, int]:
    if not rows:
        return None, start
    idx = max(0, min(start, len(rows) - 1))
    while idx + 1 < len(rows) and abs(_f(rows[idx + 1].get("time"), 0.0) - time_value) <= abs(_f(rows[idx].get("time"), 0.0) - time_value):
        idx += 1
    return (rows[idx] if abs(_f(rows[idx].get("time"), 0.0) - time_value) <= tol else None), idx


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _rotation_body_to_nav(roll: float, pitch: float, yaw: float) -> list[list[float]]:
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ]


def _mat_vec(mat: list[list[float]], vec: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(sum(mat[i][j] * vec[j] for j in range(3)) for i in range(3))  # type: ignore[return-value]


def _residual(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float:
    if a is None or b is None:
        return math.nan
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _rmse(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return math.sqrt(sum(value * value for value in finite) / len(finite)) if finite else math.nan


def _mean(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return sum(finite) / len(finite) if finite else math.nan


def _corr(xs: list[float], ys: list[float]) -> float:
    pairs = [(x, y) for x, y in zip(xs, ys) if math.isfinite(x) and math.isfinite(y)]
    if len(pairs) < 3:
        return math.nan
    mx = sum(x for x, _ in pairs) / len(pairs)
    my = sum(y for _, y in pairs) / len(pairs)
    vx = sum((x - mx) ** 2 for x, _ in pairs)
    vy = sum((y - my) ** 2 for _, y in pairs)
    if vx <= 0 or vy <= 0:
        return math.nan
    return sum((x - mx) * (y - my) for x, y in pairs) / math.sqrt(vx * vy)


def build_go2_foot_kinematic_velocity_candidate(
    *,
    go2_rows: list[dict[str, Any]],
    contact_rows: list[dict[str, Any]],
    go2_velocity_rows: list[dict[str, Any]],
    receiver_velocity_rows: list[dict[str, Any]],
    raw_doppler_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    contacts = sorted(contact_rows, key=lambda row: _f(row.get("time"), 0.0))
    go2_vel = sorted(go2_velocity_rows, key=lambda row: _f(row.get("time"), 0.0))
    recv = sorted(receiver_velocity_rows, key=lambda row: _f(row.get("time"), 0.0))
    raw = sorted(raw_doppler_rows, key=lambda row: _f(row.get("time"), 0.0))
    ci = gi = ri = rdi = 0
    out: list[dict[str, Any]] = []
    for row in sorted(go2_rows, key=lambda item: _f(item.get("aligned_time", item.get("time")), 0.0)):
        time_value = _f(row.get("aligned_time", row.get("time")), 0.0)
        contact, ci = _nearest(contacts, time_value, ci, 0.08)
        go2v, gi = _nearest(go2_vel, time_value, gi, 0.08)
        recvv, ri = _nearest(recv, time_value, ri, 0.25)
        rawv, rdi = _nearest(raw, time_value, rdi, 0.25)
        omega = (_f(row.get("gyro_x"), 0.0), _f(row.get("gyro_y"), 0.0), _f(row.get("gyro_z"), 0.0))
        rot = _rotation_body_to_nav(_f(row.get("roll_rad"), 0.0), _f(row.get("pitch_rad"), 0.0), _f(row.get("yaw_rad"), 0.0))
        weighted = [0.0, 0.0, 0.0]
        weight_sum = 0.0
        stance_count = 0
        foot_speeds: list[float] = []
        for foot in range(4):
            weight = _f((contact or {}).get(f"foot_{foot}_contact_probability"), math.nan)
            if not math.isfinite(weight):
                force = _f(row.get(f"foot_force_{foot}"), 0.0)
                weight = max(0.0, min(1.0, force / 120.0))
            r = tuple(_f(row.get(f"foot_position_body_{3 * foot + axis}"), math.nan) for axis in range(3))
            v = tuple(_f(row.get(f"foot_speed_body_{3 * foot + axis}"), math.nan) for axis in range(3))
            if not all(math.isfinite(value) for value in (*r, *v)):
                continue
            foot_speeds.append(math.sqrt(sum(value * value for value in v)))
            if weight < 0.20:
                continue
            oxr = _cross(omega, r)  # type: ignore[arg-type]
            body = tuple(-(v[i] + oxr[i]) for i in range(3))
            nav = _mat_vec(rot, body)  # type: ignore[arg-type]
            for axis in range(3):
                weighted[axis] += weight * nav[axis]
            weight_sum += weight
            stance_count += int(weight >= 0.50)
        if weight_sum <= 0.20:
            continue
        cand = (weighted[0] / weight_sum, weighted[1] / weight_sum, weighted[2] / weight_sum)
        cand2 = (cand[0], cand[1])
        go2pair = (_f(go2v.get("vn"), math.nan), _f(go2v.get("ve"), math.nan)) if go2v else None
        recvpair = (_f(recvv.get("vn"), math.nan), _f(recvv.get("ve"), math.nan)) if recvv else None
        rawpair = (_f(rawv.get("vn"), math.nan), _f(rawv.get("ve"), math.nan)) if rawv else None
        slip_risk = min(1.0, _mean(foot_speeds) / 1.5 if foot_speeds else 1.0)
        out.append(
            {
                "time": time_value,
                "candidate_vn": cand[0],
                "candidate_ve": cand[1],
                "candidate_vd": cand[2],
                "weight_sum": weight_sum,
                "stance_foot_count": stance_count,
                "slip_risk": slip_risk,
                "go2_vn": go2pair[0] if go2pair else "",
                "go2_ve": go2pair[1] if go2pair else "",
                "receiver_vn": recvpair[0] if recvpair else "",
                "receiver_ve": recvpair[1] if recvpair else "",
                "raw_vn": rawpair[0] if rawpair else "",
                "raw_ve": rawpair[1] if rawpair else "",
                "residual_to_go2": _residual(cand2, go2pair),
                "residual_to_receiver": _residual(cand2, recvpair),
                "residual_to_raw": _residual(cand2, rawpair),
            }
        )
    residual_receiver = [_f(row.get("residual_to_receiver"), math.nan) for row in out]
    residual_raw = [_f(row.get("residual_to_raw"), math.nan) for row in out]
    residual_go2 = [_f(row.get("residual_to_go2"), math.nan) for row in out]
    availability = len(out) / len(go2_rows) if go2_rows else 0.0
    plausible = availability > 0.20 and (_rmse(residual_receiver) < 2.0 or _rmse(residual_raw) < 2.0)
    activation = "ready_for_N7C6" if plausible and _mean([_f(row.get("slip_risk"), 1.0) for row in out]) < 0.75 else ("diagnostic_only" if out else "false")
    report = {
        "stage": "N7C5_go2_full_proprioceptive_factor_mining",
        "candidate_generated": bool(out),
        "row_count": len(out),
        "availability_ratio": availability,
        "stance_foot_count_mean": _mean([_f(row.get("stance_foot_count"), math.nan) for row in out]),
        "fused_velocity_availability": availability,
        "rmse_to_receiver": _rmse(residual_receiver),
        "rmse_to_raw": _rmse(residual_raw),
        "rmse_to_go2_velocity": _rmse(residual_go2),
        "bias_to_receiver": _mean(residual_receiver),
        "bias_to_raw": _mean(residual_raw),
        "correlation_with_receiver_vn": _corr([_f(row.get("candidate_vn"), math.nan) for row in out], [_f(row.get("receiver_vn"), math.nan) for row in out]),
        "correlation_with_raw_vn": _corr([_f(row.get("candidate_vn"), math.nan) for row in out], [_f(row.get("raw_vn"), math.nan) for row in out]),
        "slip_risk_mean": _mean([_f(row.get("slip_risk"), math.nan) for row in out]),
        "physical_plausibility": "plausible" if plausible else "needs_more_evidence",
        "activation_candidate": activation,
        "not_truth": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "no_trace_tuning": True,
        "no_final_v23_tuning": True,
        "paper_performance_claim": False,
        "fgo": False,
    }
    return out, report


def write_go2_foot_kinematic_velocity_outputs(output_dir: str | Path, rows: list[dict[str, Any]], report: dict[str, Any]) -> tuple[Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "GO2_FOOT_KINEMATIC_VELOCITY_TIMESERIES.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FOOT_KINEMATIC_FIELDS)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in FOOT_KINEMATIC_FIELDS} for row in rows])
    report_path = out / "GO2_FOOT_KINEMATIC_VELOCITY_CANDIDATE_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, report_path
