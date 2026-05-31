from pathlib import Path

from legsa_gins.reporting.by2_algorithm_runner import (
    ALGORITHM_SPECS,
    FORMAL_ALGORITHMS,
    build_algorithm_config_text,
)


ROOT = Path(__file__).resolve().parents[2]


def test_qa_fallback_is_separate_formal_candidate_not_legsa_full_relabel() -> None:
    assert "LegSA_QA_Fallback_EKF" in FORMAL_ALGORITHMS
    assert "LegSA_full_EKF" in FORMAL_ALGORITHMS
    assert ALGORITHM_SPECS["LegSA_QA_Fallback_EKF"].role == "new_algorithm_candidate"
    assert ALGORITHM_SPECS["LegSA_QA_Fallback_EKF"].component_flags == ALGORITHM_SPECS["LegSA_full_EKF"].component_flags
    assert ALGORITHM_SPECS["LegSA_QA_Fallback_EKF"].complete_nine_factor_fgo_claim is False


def test_legsa_full_config_keeps_qa_disabled_by_default(tmp_path) -> None:
    config = build_algorithm_config_text(
        ROOT,
        "LegSA_full_EKF",
        tmp_path / "full",
        {"imupath": "/clean/CLEAN.imu", "gnsspath": "/clean/CLEAN.gnss"},
    )

    assert "algorithm_id: LegSA_full_EKF" in config
    assert "qa_passive_logging_enabled: false" in config
    assert "enable_qa_fallback: false" in config
    assert "qa_active_mode: false" in config


def test_qa_fallback_config_enables_supervisor_without_paper_claim(tmp_path) -> None:
    config = build_algorithm_config_text(
        ROOT,
        "LegSA_QA_Fallback_EKF",
        tmp_path / "qa",
        {"imupath": "/clean/CLEAN.imu", "gnsspath": "/clean/CLEAN.gnss"},
    )

    assert "algorithm_id: LegSA_QA_Fallback_EKF" in config
    assert "qa_passive_logging_enabled: true" in config
    assert "enable_qa_fallback: true" in config
    assert "qa_active_mode: true" in config
    assert "qa_a1_relpos_diff_valid_default: false" in config
    assert "qa_a1_quality_source: explicit_quality_missing_reject_yaw" in config
    assert "qa_recovery_max_yaw_correction_deg: 1.0" in config
    assert "qa_s1_yaw_r_scale: 2.0" in config
    assert "paper_performance_claim: false" in config
    assert "no_outperform_final_v23_claim: true" in config
    assert "trace_solver_input: false" in config
    assert "final_v23_output_solver_input: false" in config
