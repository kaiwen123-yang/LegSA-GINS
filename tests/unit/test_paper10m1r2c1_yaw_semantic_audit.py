import math

from legsa_gins.evaluation.yaw_semantic_audit import (
    YawReference,
    audit_transform_candidates,
    classify_clean_yaw_gate,
    transform_yaw_deg,
)


def test_yaw_transform_candidates_include_lateral_minus_90():
    assert transform_yaw_deg(91.0, "body_heading_from_lateral_baseline_minus_90") == 1.0
    assert transform_yaw_deg(350.0, "plus_90_deg") == 80.0


def test_candidate_audit_finds_minus_90_on_toy_data():
    nav = [{"time": 0.0, "yaw_deg": 1.0}, {"time": 1.0, "yaw_deg": 2.0}]
    ref = YawReference(
        name="provider_status_yaw_observation",
        rows=[{"time": 0.0, "yaw_deg": 91.0}, {"time": 1.0, "yaw_deg": 92.0}],
        role="source_observation_not_truth",
    )
    rows = audit_transform_candidates(nav, ref)
    best = min(rows, key=lambda row: float(row["yaw_rmse_deg"]))
    assert best["yaw_transform_candidate"] == "minus_90_deg"
    assert math.isclose(float(best["yaw_rmse_deg"]), 0.0)


def test_clean_yaw_gate_blocks_trace_failures():
    gate = classify_clean_yaw_gate(
        [
            {
                "method_mode_id": "strong_dual_yaw_baseline",
                "trace_heading_to_math_rmse_deg": 15.0,
                "best_provider_reference_rmse_deg": 55.0,
            }
        ]
    )
    assert gate["gate_status"] == "BLOCKED_SOLVER_PROVIDER_YAW_SEMANTIC_FAILURE"
    assert gate["evaluator_only_repair"] is False
