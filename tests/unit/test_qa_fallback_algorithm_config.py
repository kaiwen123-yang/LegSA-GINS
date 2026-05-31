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


def test_qa10b_literature_inspired_baselines_are_config_variants_only(tmp_path) -> None:
    for algorithm in [
        "robust_innovation_reject_EKF",
        "nis_adaptive_R_EKF",
        "doppler_consistency_gate_EKF",
    ]:
        assert algorithm in FORMAL_ALGORITHMS
        spec = ALGORITHM_SPECS[algorithm]
        assert spec.role == "literature_inspired_baseline"
        assert spec.complete_nine_factor_fgo_claim is False
        assert spec.component_flags["go2_joint"] is False
        assert spec.component_flags["feedback"] is False

        config = build_algorithm_config_text(
            ROOT,
            algorithm,
            tmp_path / algorithm,
            {"imupath": "/clean/CLEAN.imu", "gnsspath": "/clean/CLEAN.gnss"},
        )
        assert f"algorithm_id: {algorithm}" in config
        assert "qa_passive_logging_enabled: false" in config
        assert "enable_qa_fallback: false" in config
        assert "qa_active_mode: false" in config
        assert "enable_source_aware_weighting: true" in config
        assert "source_aware_use_innovation_covariance: true" in config
        assert "source_aware_trace_enabled: true" in config
        assert "trace_solver_input: false" in config
        assert "final_v23_output_solver_input: false" in config
        assert "output_only_correction: false" in config
        assert "paper_performance_claim: false" in config


def test_qa10b_doppler_baseline_is_the_only_new_variant_with_raw_doppler(tmp_path) -> None:
    doppler = build_algorithm_config_text(
        ROOT,
        "doppler_consistency_gate_EKF",
        tmp_path / "doppler",
        {"imupath": "/clean/CLEAN.imu", "gnsspath": "/clean/CLEAN.gnss"},
    )
    nis = build_algorithm_config_text(
        ROOT,
        "nis_adaptive_R_EKF",
        tmp_path / "nis",
        {"imupath": "/clean/CLEAN.imu", "gnsspath": "/clean/CLEAN.gnss"},
    )

    assert "enable_raw_doppler: true" in doppler
    assert "raw_doppler_residual_gate_mps: 3.0" in doppler
    assert "enable_raw_doppler: false" in nis
