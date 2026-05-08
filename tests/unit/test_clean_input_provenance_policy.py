"""中文说明：clean provenance policy 不允许 noisy artifact 冒充 clean nominal。"""

from legsa_gins.evaluation.clean_status_yaw_replay import DEFAULT_CLEAN_POLICY
from legsa_gins.source_audit.clean_input_provenance_policy import make_clean_input_provenance_policy_report


def test_clean_input_provenance_policy_flags() -> None:
    report = make_clean_input_provenance_policy_report(
        {"clean_input_policy": DEFAULT_CLEAN_POLICY},
        {"clean_replay_parity_status": "passed", "noisy_artifact_has_gaussian_yaw_noise": True},
    )
    assert report["actual_dual_final_v23_artifact_likely_has_gaussian_yaw_noise_1p5_deg"] is True
    assert report["clean_replay_is_not_historical_exact_final_v23_artifact"] is True
    assert report["paper_should_not_call_noisy_actual_clean_nominal"] is True
    assert report["trace_solver_input"] is False
    assert report["output_only_correction"] is False
    assert report["numerical_performance_claim"] is False
