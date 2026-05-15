"""N8J fixed selected feedback policy.

中文说明：N8J 锁定 N8I 选出的 feedback policy，不再搜索或调 gate/covariance。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fgo_feedback_visual_loader import read_json, write_json


SELECTED_POLICY_NAME = "n8i_selected_conservative_feedback"


def selected_feedback_policy() -> dict[str, Any]:
    return {
        "stage": "N8J",
        "policy_name": SELECTED_POLICY_NAME,
        "feedback_mode": "horizontal_velocity_attitude_feedback",
        "position_feedback_enabled": False,
        "horizontal_velocity_feedback_enabled": True,
        "attitude_feedback_enabled": True,
        "gate_policy": "combined_conservative_gate",
        "covariance_policy": "inflation_auto_from_residual_proxy",
        "window_duration_s": 5.0,
        "stride_s": 1.0,
        "no_future_data_required": True,
        "output_substitution": False,
        "direct_nav_override": False,
        "trace_tuning": False,
        "final_v23_tuning": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
        "selected_policy_locked_from_n8i": True,
    }


def build_selected_policy_report(n8i_root: str | Path | None = None) -> dict[str, Any]:
    policy = selected_feedback_policy()
    n8i_decision = read_json(Path(n8i_root) / "N8I_FEEDBACK_ABLATION_GATE_COVARIANCE_DECISION_REPORT.json") if n8i_root else {}
    policy["n8i_selected_policy_match"] = _matches_n8i(policy, n8i_decision)
    policy["n8i_decision_status"] = n8i_decision.get("status", "")
    policy["n8i_recommended_next_stage"] = n8i_decision.get("recommended_next_stage", "")
    policy["hidden_policy_change"] = not policy["n8i_selected_policy_match"] if n8i_decision else False
    return policy


def _matches_n8i(policy: dict[str, Any], n8i_decision: dict[str, Any]) -> bool:
    if not n8i_decision:
        return True
    return (
        n8i_decision.get("selected_gate_policy") == policy["gate_policy"]
        and n8i_decision.get("selected_covariance_policy") == policy["covariance_policy"]
        and n8i_decision.get("selected_window_policy") == "window_5s_stride_1s"
        and n8i_decision.get("selected_feedback_policy") == "primary_hv_att_conservative_gate"
        and n8i_decision.get("selected_feedback_mode") == policy["feedback_mode"]
    )


def write_selected_policy_report(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
