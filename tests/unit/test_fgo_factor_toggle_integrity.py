"""Tests for N8C2 factor toggle integrity.

中文说明：验证 policy/sensitivity 变体能形成 toggle 完整性证据。
"""

from legsa_gins.fgo.fgo_factor_toggle_integrity import build_factor_toggle_integrity


def test_toggle_integrity_accepts_policy_and_sensitivity_variants() -> None:
    ablations = {
        "variants": [
            {"variant": "raw_doppler_off", "real_solver_rerun": True, "raw_doppler_policy": "raw_doppler_off"},
            {"variant": "go2_joint_off", "real_solver_rerun": True, "go2_policy": "go2_joint_off"},
            {"variant": "candidate_foot_kinematic_diagnostic", "real_solver_rerun": True},
            {"variant": "candidate_yawrate_between_diagnostic", "real_solver_rerun": True},
            {"variant": "candidate_relative_odometry_diagnostic", "real_solver_rerun": True},
            {"variant": "candidate_stack_diagnostic", "real_solver_rerun": True},
        ]
    }
    sensitivity = {"variants": [{"variant": "receiver_velocity_off_raw_on", "real_solver_rerun": True}]}
    report = build_factor_toggle_integrity(ablation_summary=ablations, sensitivity_report=sensitivity, state_count=5)
    assert report["status"] == "toggle_integrity_passed"
    assert not report["trace_weight_tuning"]
