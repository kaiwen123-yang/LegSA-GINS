"""N4H4R3 source-backed port clean replay parity decision.

中文说明：这里只做工程骨架 parity 判定；不把 final_v23 输出作为 solver input，
不做论文性能 claim，也不把 R3 结果写成创新因子结果。
"""

from __future__ import annotations

from typing import Any


EXTERNAL_CLEAN_REFERENCE = {
    "horizontal_rmse_m": 0.3460851160719829,
    "up_rmse_m": 0.7940342899951961,
    "yaw_rmse_deg": 1.979182806966782,
    "roll_rmse_deg": 1.0200759961634018,
    "pitch_rmse_deg": 1.522164831263277,
}


def _metric(summary: dict[str, Any], name: str) -> float | None:
    value = summary.get(name)
    return float(value) if isinstance(value, (int, float)) else None


def _ok(value: float | None, threshold: float) -> bool:
    return value is not None and value <= threshold


def make_port_parity_decision(
    summary: dict[str, Any],
    gap_screen: dict[str, Any] | None = None,
    external_clean: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Classify R3 clean replay without relaxing yaw beyond 2 degrees."""

    external = external_clean or EXTERNAL_CLEAN_REFERENCE
    h = _metric(summary, "horizontal_rmse_m")
    up = _metric(summary, "up_rmse_m")
    yaw = _metric(summary, "yaw_rmse_deg")
    roll = _metric(summary, "roll_rmse_deg")
    pitch = _metric(summary, "pitch_rmse_deg")

    deltas = {
        "horizontal_rmse_m": None if h is None else h - external["horizontal_rmse_m"],
        "up_rmse_m": None if up is None else up - external["up_rmse_m"],
        "yaw_rmse_deg": None if yaw is None else yaw - external["yaw_rmse_deg"],
        "roll_rmse_deg": None if roll is None else roll - external["roll_rmse_deg"],
        "pitch_rmse_deg": None if pitch is None else pitch - external["pitch_rmse_deg"],
    }
    gate_status = {
        "horizontal_gate_pass": _ok(h, 2.0),
        "up_gate_pass": _ok(up, 3.0),
        "yaw_gate_pass": _ok(yaw, 2.0),
        "roll_strict_pass": _ok(roll, 1.0),
        "pitch_strict_pass": _ok(pitch, 1.0),
        "roll_relaxed_pass": _ok(roll, 1.6),
        "pitch_relaxed_pass": _ok(pitch, 1.6),
    }
    external_close = {
        "horizontal_close_to_external": deltas["horizontal_rmse_m"] is not None
        and abs(deltas["horizontal_rmse_m"]) <= 0.5,
        "up_close_to_external": deltas["up_rmse_m"] is not None and abs(deltas["up_rmse_m"]) <= 0.8,
        "yaw_close_to_external": deltas["yaw_rmse_deg"] is not None and abs(deltas["yaw_rmse_deg"]) <= 0.5,
    }

    passed = (
        gate_status["horizontal_gate_pass"]
        and gate_status["up_gate_pass"]
        and gate_status["yaw_gate_pass"]
        and gate_status["roll_relaxed_pass"]
        and gate_status["pitch_relaxed_pass"]
        and all(external_close.values())
    )
    near_gate = (
        not passed
        and gate_status["horizontal_gate_pass"]
        and gate_status["up_gate_pass"]
        and yaw is not None
        and 2.0 < yaw <= 2.2
        and gate_status["roll_relaxed_pass"]
        and gate_status["pitch_relaxed_pass"]
    )

    if passed:
        parity_classification = "parity_passed"
        recommended = "N4H4E_visual_validation_for_source_backed_port"
    elif near_gate:
        parity_classification = "parity_near_gate"
        recommended = "N4H4R3_near_gate_review_and_visual_check"
    else:
        parity_classification = "parity_failed"
        recommended = (gap_screen or {}).get("recommended_next_stage", "N4H4R3_filter_math_gap_fix")

    return {
        "phase": "N4H4R3",
        "parity_classification": parity_classification,
        "parity_passed": parity_classification == "parity_passed",
        "parity_near_gate": parity_classification == "parity_near_gate",
        "parity_failed": parity_classification == "parity_failed",
        "gate_status": gate_status,
        "external_clean_reference": external,
        "delta_vs_external_clean_replay": deltas,
        "external_close_status": external_close,
        "recommended_next_stage": recommended,
        "blocking_issues": (gap_screen or {}).get("blocking_issues", []),
        "engineering_backbone_parity_only": True,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "raw_doppler": False,
        "go2_prior": False,
        "lsim_oim": False,
        "fgo": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
