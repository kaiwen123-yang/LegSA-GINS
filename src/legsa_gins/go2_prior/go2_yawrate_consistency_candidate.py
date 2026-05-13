"""N7C5 Go2 yaw-rate consistency candidate.

中文说明：yaw-rate 在 N7C5 只做一致性候选审查；当前 EKF 不直接激活
Go2 yaw/yaw-rate prior，稳定时也只建议后续 between-factor/FGO 候选。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _unwrap(values: list[float]) -> list[float]:
    if not values:
        return []
    out = [values[0]]
    for value in values[1:]:
        prev = out[-1]
        while value - prev > math.pi:
            value -= 2 * math.pi
        while value - prev < -math.pi:
            value += 2 * math.pi
        out.append(value)
    return out


def _rmse(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return math.sqrt(sum(value * value for value in finite) / len(finite)) if finite else math.nan


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


def build_go2_yawrate_consistency_candidate(go2_rows: list[dict[str, Any]], phase_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = sorted(go2_rows, key=lambda row: _f(row.get("aligned_time", row.get("time")), 0.0))
    times = [_f(row.get("aligned_time", row.get("time")), math.nan) for row in rows]
    yaws = _unwrap([_f(row.get("yaw_rad"), math.nan) for row in rows])
    yaw_speed = [_f(row.get("yaw_speed_radps"), math.nan) for row in rows]
    gyro_z = [_f(row.get("gyro_z"), math.nan) for row in rows]
    dyaw_dt: list[float] = []
    aligned_yaw_speed: list[float] = []
    aligned_gyro: list[float] = []
    for i in range(1, len(rows)):
        dt = times[i] - times[i - 1]
        if not math.isfinite(dt) or dt <= 0:
            continue
        dyaw_dt.append((yaws[i] - yaws[i - 1]) / dt)
        aligned_yaw_speed.append(yaw_speed[i])
        aligned_gyro.append(gyro_z[i])
    turn_count = sum(1 for row in phase_rows if row.get("phase") == "turning")
    yaw_vs_derivative = [a - b for a, b in zip(aligned_yaw_speed, dyaw_dt)]
    yaw_vs_gyro = [a - b for a, b in zip(aligned_yaw_speed, aligned_gyro)]
    stable = _rmse(yaw_vs_derivative) < 0.30 and _rmse(yaw_vs_gyro) < 0.30 and len(dyaw_dt) > 10
    return {
        "stage": "N7C5_go2_full_proprioceptive_factor_mining",
        "row_count": len(dyaw_dt),
        "turn_segment_count": turn_count,
        "yaw_speed_vs_yaw_derivative_rmse_radps": _rmse(yaw_vs_derivative),
        "yaw_speed_vs_gyro_z_rmse_radps": _rmse(yaw_vs_gyro),
        "yaw_speed_derivative_corr": _corr(aligned_yaw_speed, dyaw_dt),
        "yaw_speed_gyro_z_corr": _corr(aligned_yaw_speed, aligned_gyro),
        "stability_status": "stable" if stable else "diagnostic_only",
        "ekf_direct_yawrate_factor_supported": False,
        "recommendation": "N8A_yawrate_between_factor_candidate" if stable else "diagnostic_only",
        "go2_yaw_prior_enabled": False,
        "go2_yawrate_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "no_trace_tuning": True,
        "no_final_v23_tuning": True,
        "paper_performance_claim": False,
        "fgo": False,
    }


def write_go2_yawrate_consistency_candidate(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
