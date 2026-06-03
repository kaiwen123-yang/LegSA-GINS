from pathlib import Path

from legsa_gins.reporting.by2_algorithm_runner import (
    ALGORITHM_SPECS,
    FORMAL_ALGORITHMS,
    QA11F_CLASSIC5_METHODS,
    QA11F_CLASSIC5_RECENT5_ALGORITHMS,
    QA11F_RECENT5_METHODS,
    build_algorithm_config_text,
)


ROOT = Path(__file__).resolve().parents[2]


def test_qa11f_registers_classic5_recent5_only() -> None:
    assert len(QA11F_CLASSIC5_METHODS) == 5
    assert len(QA11F_RECENT5_METHODS) == 5
    assert len(QA11F_CLASSIC5_RECENT5_ALGORITHMS) == 10
    assert len(set(QA11F_CLASSIC5_RECENT5_ALGORITHMS)) == 10
    assert not any("20" in algorithm for algorithm in QA11F_CLASSIC5_RECENT5_ALGORITHMS)
    for algorithm in QA11F_CLASSIC5_RECENT5_ALGORITHMS:
        assert algorithm in FORMAL_ALGORITHMS
        spec = ALGORITHM_SPECS[algorithm]
        assert spec.role == "literature_inspired_baseline"
        assert spec.solver_execution_allowed is True
        assert spec.complete_nine_factor_fgo_claim is False
        assert spec.component_flags == {
            "raw_doppler": False,
            "source_aware": True,
            "go2_joint": False,
            "feedback": False,
        }


def test_qa11f_configs_freeze_weight_family_without_trace_or_final_v23(tmp_path) -> None:
    labels = set()
    families = set()
    for algorithm in QA11F_CLASSIC5_RECENT5_ALGORITHMS:
        config = build_algorithm_config_text(
            ROOT,
            algorithm,
            tmp_path / algorithm,
            {"imupath": "/clean/CLEAN.imu", "gnsspath": "/clean/CLEAN.gnss"},
        )
        assert f"algorithm_id: {algorithm}" in config
        assert "enable_source_aware_weighting: true" in config
        assert "source_aware_policy_version: n6b_conservative_innovation_covariance" in config
        assert "source_aware_method_family:" in config
        assert "qa_passive_logging_enabled: false" in config
        assert "enable_qa_fallback: false" in config
        assert "qa_active_mode: false" in config
        assert "enable_raw_doppler: false" in config
        assert "enable_go2_proprioceptive_joint_factor: false" in config
        assert "enable_fgo_feedback: false" in config
        assert "trace_solver_input: false" in config
        assert "final_v23_output_solver_input: false" in config
        assert "output_only_correction: false" in config
        assert "paper_performance_claim: false" in config
        assert "exact_reproduction: false" in config
        labels.add(_config_value(config, "qa11e_method_label"))
        families.add(_config_value(config, "source_aware_method_family"))
    assert labels == {
        "CLASSIC_METHOD_BASELINE",
        "PAPER_DERIVED_BY2_REIMPLEMENTATION",
        "RECENT_PAPER_MOTIVATED_VARIANT",
    }
    assert families == {
        "nis_chi_square",
        "mahalanobis_gate",
        "covariance_matching",
        "huber",
        "igg3",
        "dcs",
        "n6b_conservative_quadratic",
    }


def _config_value(config: str, key: str) -> str:
    prefix = f"{key}: "
    for line in config.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    raise AssertionError(f"missing config key: {key}")
