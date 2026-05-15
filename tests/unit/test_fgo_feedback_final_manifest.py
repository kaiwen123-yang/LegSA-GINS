"""Unit tests for N8J final manifest.

中文说明：manifest 要记录 runtime 输出已生成但不提交。
"""

from types import SimpleNamespace

from legsa_gins.fgo_feedback.fgo_feedback_final_manifest import build_final_feedback_manifest


def test_final_manifest_records_runtime_boundary():
    bundle = SimpleNamespace(
        policy_summaries={
            "n8j_selected_conservative_feedback": {
                "feedback_accept_count": 4,
                "feedback_reject_count": 2,
                "runtime_outputs_generated": True,
                "nav_generated": True,
                "std_generated": True,
                "eval_nav_generated": True,
                "run_manifest_generated": True,
            }
        },
        gate_reports={"n8j_selected_conservative_feedback": {"reject_reasons": {"attitude_correction_gate": 2}, "no_future_data": True}},
        observation_reports={"n8j_selected_conservative_feedback": {"feedback_rows": 6}},
    )
    manifest = build_final_feedback_manifest(bundle=bundle, selected_policy={"policy_name": "n8i_selected_conservative_feedback", "window_duration_s": 5.0, "stride_s": 1.0, "feedback_mode": "horizontal_velocity_attitude_feedback"}, figure_manifest={"all_required_figures_nonempty": True})
    assert manifest["runtime_outputs_generated"] is True
    assert manifest["runtime_artifacts_committed"] is False
    assert manifest["position_feedback_enabled"] is False
