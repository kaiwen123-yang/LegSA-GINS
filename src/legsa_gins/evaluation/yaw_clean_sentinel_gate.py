"""Clean sentinel gate logic for PAPER10M1R2C2."""

from __future__ import annotations

import math
from typing import Any


STRICT_METHODS = {
    "strong_dual_yaw_baseline",
    "legsa_without_qm",
    "legsa_full_candidate_with_qm",
}


def _float(value: Any, default: float = math.inf) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def evaluate_clean_sentinel_gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    blockers: list[str] = []
    by_method = {row.get("method_mode_id"): row for row in rows}
    for method in STRICT_METHODS:
        yaw = _float(by_method.get(method, {}).get("yaw_rmse_deg"))
        if yaw > 5.0:
            blockers.append(f"{method} yaw_rmse_deg={yaw:.6f} > 5.0")
    basic = _float(by_method.get("basic_dual_baseline", {}).get("yaw_rmse_deg"))
    if basic > 10.0:
        blockers.append(f"basic_dual_baseline yaw_rmse_deg={basic:.6f} > 10.0")
    for row in rows:
        if str(row.get("terminal_status")) != "COMPLETED_EVALUABLE":
            blockers.append(f"{row.get('method_mode_id')} terminal_status={row.get('terminal_status')}")
        forbidden = [
            "trace_solver_input",
            "final_v23_output_solver_input",
            "legsa_output_solver_input",
            "output_only_correction_used",
            "epoch_deleted_for_metric",
        ]
        for key in forbidden:
            if str(row.get(key, "false")).lower() in {"true", "1", "yes"}:
                blockers.append(f"{row.get('method_mode_id')} forbidden field {key}=true")
    if blockers:
        return {
            "gate_status": "BLOCKED_CLEAN_YAW_REPAIR_FAILED",
            "pass": False,
            "blockers": blockers,
        }
    return {
        "gate_status": "PASS_PAPER10M1R2C2_CLEAN_SENTINEL_GATE",
        "pass": True,
        "blockers": [],
    }
