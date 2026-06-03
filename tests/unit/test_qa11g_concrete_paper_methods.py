from pathlib import Path

from legsa_gins.reporting.by2_algorithm_runner import (
    ALGORITHM_SPECS,
    FORMAL_ALGORITHMS,
    QA11G_CLASSIC5_METHODS,
    QA11G_CONCRETE_PAPER_10_METHODS,
    QA11G_METHOD_SOURCE_BINDINGS,
    QA11G_RECENT5_METHODS,
    build_algorithm_config_text,
)


ROOT = Path(__file__).resolve().parents[2]


def test_qa11g_registers_concrete_paper_10_methods() -> None:
    assert len(QA11G_CLASSIC5_METHODS) == 5
    assert len(QA11G_RECENT5_METHODS) == 5
    assert len(QA11G_CONCRETE_PAPER_10_METHODS) == 10
    assert len(set(QA11G_CONCRETE_PAPER_10_METHODS)) == 10
    assert set(QA11G_METHOD_SOURCE_BINDINGS) == set(QA11G_CONCRETE_PAPER_10_METHODS)
    for algorithm in QA11G_CONCRETE_PAPER_10_METHODS:
        assert algorithm in FORMAL_ALGORITHMS
        spec = ALGORITHM_SPECS[algorithm]
        binding = QA11G_METHOD_SOURCE_BINDINGS[algorithm]
        assert spec.role == "concrete_paper_sourced_external_baseline"
        assert spec.status == "qa11g_concrete_paper_sourced_by2_reimplementation"
        assert spec.solver_execution_allowed is True
        assert spec.complete_nine_factor_fgo_claim is False
        assert spec.component_flags == {
            "raw_doppler": False,
            "source_aware": True,
            "go2_joint": False,
            "feedback": False,
        }
        assert binding["title"]
        assert binding["authors"]
        assert binding["venue"]
        assert str(binding["doi_or_url"]).startswith(("https://doi.org/", "https://"))
        assert binding["exact_reproduction"] is False
        assert binding["reimplementation_label"] in {
            "CLASSIC_METHOD_BASELINE",
            "RECENT_PAPER_DERIVED_BY2_REIMPLEMENTATION",
        }


def test_qa11g_recent5_are_2020_to_2026_concrete_sources() -> None:
    forbidden = {
        "recent_method_family",
        "generic literature-inspired",
        "method-inspired",
        "representative family",
        "design-only",
        "RECENT_PAPER_MOTIVATED_VARIANT",
    }
    for algorithm in QA11G_RECENT5_METHODS:
        binding = QA11G_METHOD_SOURCE_BINDINGS[algorithm]
        assert 2020 <= int(binding["year"]) <= 2026
        haystack = " ".join(str(value) for value in binding.values()).lower()
        for label in forbidden:
            assert label.lower() not in haystack


def test_qa11g_configs_freeze_source_binding_without_trace_or_final_v23(tmp_path) -> None:
    for algorithm in QA11G_CONCRETE_PAPER_10_METHODS:
        config = build_algorithm_config_text(
            ROOT,
            algorithm,
            tmp_path / algorithm,
            {"imupath": "/clean/CLEAN.imu", "gnsspath": "/clean/CLEAN.gnss"},
        )
        binding = QA11G_METHOD_SOURCE_BINDINGS[algorithm]
        assert f"algorithm_id: {algorithm}" in config
        assert "enable_source_aware_weighting: true" in config
        assert f"qa11g_paper_source_id: {binding['source_id']}" in config
        assert f"qa11g_concrete_paper_year: {binding['year']}" in config
        assert f"qa11g_reimplementation_label: {binding['reimplementation_label']}" in config
        assert "source_verification_status: verified_concrete_doi_or_url" in config
        assert "trace_solver_input: false" in config
        assert "trace_tuning: false" in config
        assert "final_v23_output_solver_input: false" in config
        assert "final_v23_tuning: false" in config
        assert "receiver_imu_data_as_body_imu: false" in config
        assert "exact_reproduction: false" in config
        assert "paper_performance_claim: false" in config
