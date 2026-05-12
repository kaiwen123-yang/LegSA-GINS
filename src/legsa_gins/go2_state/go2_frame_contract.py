"""Frame contract for N7A Go2 roll/pitch weak prior.

中文说明：Go2 body frame 是 FLU；process_data 里的 IMU 输入已做 FLU->FRD。
N7A 不使用 trace 选择符号，只做内部一致性和小角连续性检查。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


SIGN_CANDIDATES = {
    "direct_roll_pitch": (1.0, 1.0),
    "roll_neg_pitch_direct": (-1.0, 1.0),
    "roll_direct_pitch_neg": (1.0, -1.0),
    "roll_neg_pitch_neg": (-1.0, -1.0),
}


def _as_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[int(0.95 * (len(ordered) - 1))]


def _candidate_stats(rows: list[dict[str, Any]], roll_sign: float, pitch_sign: float) -> dict[str, Any]:
    roll = [roll_sign * value for value in (_as_float(row.get("roll_rad")) for row in rows) if value is not None]
    pitch = [pitch_sign * value for value in (_as_float(row.get("pitch_rad")) for row in rows) if value is not None]
    jumps = [abs(b - a) for series in [roll, pitch] for a, b in zip(series, series[1:])]
    max_abs = max([abs(value) for value in roll + pitch], default=None)
    return {
        "max_abs_roll_pitch_rad": max_abs,
        "p95_step_delta_rad": _p95(jumps),
        "small_angle_continuity_ok": (max_abs is not None and max_abs < 1.2 and (_p95(jumps) or 0.0) < 0.25),
    }


def build_frame_contract_report(
    rows: list[dict[str, Any]],
    quaternion_report: dict[str, Any],
) -> dict[str, Any]:
    candidates = {
        name: _candidate_stats(rows, roll_sign, pitch_sign)
        for name, (roll_sign, pitch_sign) in SIGN_CANDIDATES.items()
    }
    direct_ok = bool(candidates["direct_roll_pitch"]["small_angle_continuity_ok"])
    quat_ok = bool(quaternion_report.get("activation_allowed_for_attitude_prior"))
    activation_allowed = quat_ok and direct_ok
    blocker_reasons: list[str] = []
    if not quat_ok:
        blocker_reasons.append("quaternion_rpy_internal_consistency_failed")
    if not direct_ok:
        blocker_reasons.append("roll_pitch_small_angle_continuity_failed")
    return {
        "go2_body_frame": "FLU",
        "process_data_imu_frame_policy": "Go2_FLU_to_FRD_already_done_for_IMU_input",
        "roll_pitch_sign_candidate_selected": "direct_roll_pitch" if activation_allowed else "unresolved",
        "sign_candidate_diagnostics": candidates,
        "selection_uses_trace": False,
        "selection_uses_final_v23_output": False,
        "activation_allowed": activation_allowed,
        "blocker_reasons": blocker_reasons,
        "recommended_next_stage": "N7B_go2_attitude_frame_resolution" if not activation_allowed else "N7A_attitude_prior_activation",
        "go2_position_as_global_truth": False,
    }


def write_frame_contract_report(
    rows: list[dict[str, Any]],
    quaternion_report: dict[str, Any],
    output_path: str | Path,
) -> dict[str, Any]:
    report = build_frame_contract_report(rows, quaternion_report)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
