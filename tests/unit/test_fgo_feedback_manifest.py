"""中文说明：单测 RUN_MANIFEST feedback 边界字段。"""

from legsa_gins.fgo_feedback.fgo_feedback_manifest import validate_feedback_manifest


def test_feedback_manifest_required_flags():
    manifest = {
        "fgo_feedback_enabled": True,
        "fgo_feedback_mode": "pseudo_measurement",
        "feedback_update_count": 1,
        "feedback_accept_count": 1,
        "feedback_reject_count": 0,
        "feedback_position_enabled": False,
        "feedback_velocity_enabled": True,
        "feedback_attitude_enabled": True,
        "fgo_feedback_output_substitution": False,
        "fgo_feedback_direct_nav_override": False,
        "fgo_feedback_no_future_data": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
    assert validate_feedback_manifest(manifest) is True
