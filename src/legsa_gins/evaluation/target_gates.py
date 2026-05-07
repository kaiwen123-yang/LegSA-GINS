"""N4G diagnostic target gates.

中文说明：target gates 只控制 ready_for_factor_stacking 诊断，不构成性能 claim。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


GATES = {
    "horizontal_rmse_m": 2.0,
    "up_rmse_m": 3.0,
    "yaw_rmse_deg": 2.0,
    "roll_rmse_deg_strict": 1.0,
    "pitch_rmse_deg_strict": 1.0,
    "roll_rmse_deg_relaxed": 1.6,
    "pitch_rmse_deg_relaxed": 1.6,
}


def evaluate_target_gates(summary: dict[str, Any]) -> dict[str, Any]:
    h_ok = _le(summary.get("horizontal_rmse_m"), GATES["horizontal_rmse_m"])
    up_ok = _le(summary.get("up_rmse_m"), GATES["up_rmse_m"])
    yaw_ok = _le(summary.get("yaw_rmse_deg"), GATES["yaw_rmse_deg"])
    roll_strict_ok = _le(summary.get("roll_rmse_deg"), GATES["roll_rmse_deg_strict"])
    pitch_strict_ok = _le(summary.get("pitch_rmse_deg"), GATES["pitch_rmse_deg_strict"])
    roll_relaxed_ok = _le(summary.get("roll_rmse_deg"), GATES["roll_rmse_deg_relaxed"])
    pitch_relaxed_ok = _le(summary.get("pitch_rmse_deg"), GATES["pitch_rmse_deg_relaxed"])
    strict_pass = all([h_ok, up_ok, yaw_ok, roll_strict_ok, pitch_strict_ok])
    relaxed_attitude_pass = all([h_ok, up_ok, yaw_ok, roll_relaxed_ok, pitch_relaxed_ok])
    return {
        "gates": GATES,
        "horizontal_gate_pass": h_ok,
        "up_gate_pass": up_ok,
        "yaw_gate_pass": yaw_ok,
        "roll_strict_gate_pass": roll_strict_ok,
        "pitch_strict_gate_pass": pitch_strict_ok,
        "roll_relaxed_gate_pass": roll_relaxed_ok,
        "pitch_relaxed_gate_pass": pitch_relaxed_ok,
        "target_gate_pass": strict_pass,
        "target_gate_relaxed_attitude_pass": relaxed_attitude_pass,
        "ready_for_factor_stacking": strict_pass,
        "numerical_performance_claim": False,
    }


def _le(value: Any, threshold: float) -> bool:
    return isinstance(value, (int, float)) and float(value) <= threshold


def write_gate_report(report: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

