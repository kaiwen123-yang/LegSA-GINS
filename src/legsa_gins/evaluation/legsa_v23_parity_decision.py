"""N4H4D LegSA-v23 clean replay parity decision helpers.

中文说明：这里只给工程 parity/gap screen 结论，不生成论文性能 claim，
不放宽 yaw > 2 deg，也不把 roll/pitch relaxed 写成 strict pass。
"""

from __future__ import annotations

from typing import Any


TARGET_GATES = {
    "horizontal_rmse_m": 2.0,
    "up_rmse_m": 3.0,
    "yaw_rmse_deg": 2.0,
    "roll_strict_rmse_deg": 1.0,
    "pitch_strict_rmse_deg": 1.0,
    "roll_relaxed_rmse_deg": 1.6,
    "pitch_relaxed_rmse_deg": 1.6,
}

EXTERNAL_CLEAN_REFERENCE = {
    "horizontal_rmse_m": 0.3460851160719829,
    "up_rmse_m": 0.7940342899951961,
    "yaw_rmse_deg": 1.979182806966782,
    "roll_rmse_deg": 1.0200759961634018,
    "pitch_rmse_deg": 1.522164831263277,
}


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def metric_deltas(summary: dict[str, Any], reference: dict[str, Any]) -> dict[str, float | None]:
    """中文说明：计算 LegSA-v23 与 external clean replay 的指标差值。"""

    deltas: dict[str, float | None] = {}
    for field in ["horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg", "roll_rmse_deg", "pitch_rmse_deg"]:
        current = _number(summary.get(field))
        baseline = _number(reference.get(field))
        deltas[field] = None if current is None or baseline is None else current - baseline
    return deltas


def gate_status(summary: dict[str, Any]) -> dict[str, bool]:
    """中文说明：严格门限和 relaxed 门限分开记录，yaw 不能超过 2 deg。"""

    horizontal = _number(summary.get("horizontal_rmse_m"))
    up = _number(summary.get("up_rmse_m"))
    yaw = _number(summary.get("yaw_rmse_deg"))
    roll = _number(summary.get("roll_rmse_deg"))
    pitch = _number(summary.get("pitch_rmse_deg"))
    return {
        "horizontal_gate_pass": horizontal is not None and horizontal <= TARGET_GATES["horizontal_rmse_m"],
        "up_gate_pass": up is not None and up <= TARGET_GATES["up_rmse_m"],
        "yaw_gate_pass": yaw is not None and yaw <= TARGET_GATES["yaw_rmse_deg"],
        "roll_strict_gate_pass": roll is not None and roll <= TARGET_GATES["roll_strict_rmse_deg"],
        "pitch_strict_gate_pass": pitch is not None and pitch <= TARGET_GATES["pitch_strict_rmse_deg"],
        "roll_relaxed_gate_pass": roll is not None and roll <= TARGET_GATES["roll_relaxed_rmse_deg"],
        "pitch_relaxed_gate_pass": pitch is not None and pitch <= TARGET_GATES["pitch_relaxed_rmse_deg"],
    }


def classify_parity(summary: dict[str, Any], external_clean: dict[str, Any] | None = None) -> dict[str, Any]:
    """中文说明：分类为 passed/near_gate/failed；passed 仍只是工程 parity candidate。"""

    reference = external_clean or EXTERNAL_CLEAN_REFERENCE
    gates = gate_status(summary)
    deltas = metric_deltas(summary, reference)
    horizontal_delta = deltas.get("horizontal_rmse_m")
    up_delta = deltas.get("up_rmse_m")
    yaw_delta = deltas.get("yaw_rmse_deg")
    close_to_external = bool(
        isinstance(horizontal_delta, (int, float))
        and abs(horizontal_delta) <= 0.5
        and isinstance(up_delta, (int, float))
        and abs(up_delta) <= 0.8
        and isinstance(yaw_delta, (int, float))
        and abs(yaw_delta) <= 0.5
    )
    relaxed_attitude = gates["roll_relaxed_gate_pass"] and gates["pitch_relaxed_gate_pass"]
    position_up_pass = gates["horizontal_gate_pass"] and gates["up_gate_pass"]
    yaw = _number(summary.get("yaw_rmse_deg"))

    if position_up_pass and gates["yaw_gate_pass"] and relaxed_attitude and close_to_external:
        status = "parity_passed"
    elif position_up_pass and yaw is not None and 2.0 < yaw <= 2.2 and relaxed_attitude:
        status = "parity_near_gate"
    else:
        status = "parity_failed"

    return {
        "parity_classification": status,
        "parity_candidate": status == "parity_passed",
        "gate_status": gates,
        "external_clean_deltas": deltas,
        "close_to_external_clean_replay": close_to_external,
        "roll_pitch_relaxed_not_strict": bool(
            relaxed_attitude and not (gates["roll_strict_gate_pass"] and gates["pitch_strict_gate_pass"])
        ),
        "yaw_over_2_allowed_as_pass": False,
        "engineering_baseline_parity_only": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def make_decision(summary: dict[str, Any], external_clean: dict[str, Any] | None = None) -> dict[str, Any]:
    """中文说明：生成 N4H4D 决策对象，失败时后续由 gap screen 决定下一阶段。"""

    decision = classify_parity(summary, external_clean)
    decision.update(
        {
            "phase": "N4H4D",
            "decision_scope": "engineering_baseline_parity_gap_screen",
            "paper_performance_claim_allowed": False,
            "proposed_factor_claim_allowed": False,
            "next_stage_if_passed": "N4H4E_visual_validation_if_parity_passed",
            "next_stage_if_failed": "gap_screen_recommended_next_stage",
        }
    )
    return decision
