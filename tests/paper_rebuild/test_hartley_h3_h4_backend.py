from __future__ import annotations

import csv
import json
import re
import subprocess
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.horizontal_literature import hartley_h3_h4 as h34


REPO_ROOT = Path(__file__).resolve().parents[2]
PATHS = h34.repository_paths(REPO_ROOT)
VALIDATION = PATHS.validation_output
REPORT = PATHS.report_output


def _csv_rows(name: str) -> list[dict[str, str]]:
    with (VALIDATION / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def cpp_validation(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    build = tmp_path_factory.mktemp("hartley_h3_h4_cpp")
    commands = h34.build_backend(PATHS, build)
    parsed = h34.parse_validator_output(commands["validator"].stdout)
    return {"build": build, "commands": commands, "parsed": parsed}


def test_cpp17_eigen_backend_builds_and_direct_suite_passes(
    cpp_validation: dict[str, object],
) -> None:
    commands = cpp_validation["commands"]
    assert isinstance(commands, dict)
    assert commands["configure"].return_code == 0
    assert commands["build"].return_code == 0
    assert commands["ctest"].return_code == 0
    assert "100% tests passed" in commands["ctest"].stdout
    match = re.search(
        r"PASS_HARTLEY_CPP_BACKEND_TESTS checks=(\d+)", commands["direct"].stdout
    )
    assert match is not None and int(match.group(1)) >= 173


def test_cpp_validator_covers_all_required_math_and_synthetic_sections(
    cpp_validation: dict[str, object],
) -> None:
    parsed = cpp_validation["parsed"]
    assert isinstance(parsed, dict)
    assert len(parsed["lie"]) == 13
    lie = {row["case"]: row for row in parsed["lie"]}
    assert int(lie["nonfinite_input_rejection"]["rejection_count"]) == 21
    assert float(lie["gamma_psi_stress_oracles"]["phi_norm"]) == pytest.approx(20.0)
    assert float(lie["gamma_psi_fifty_rad_oracles"]["phi_norm"]) == pytest.approx(50.0)
    assert float(lie["gamma_psi_hundred_rad_oracles"]["phi_norm"]) == pytest.approx(100.0)
    assert float(lie["exp_log_near_pi"]["orthogonality_error"]) < 2.0e-9
    assert float(lie["exp_log_near_pi"]["determinant_error"]) < 2.0e-9
    assert len(parsed["mean"]) == 7
    stress_mean = next(
        row for row in parsed["mean"]
        if row["case"] == "one_second_twenty_rad_per_s_stress"
    )
    assert float(stress_mean["dt"]) == 1.0
    assert float(stress_mean["omega_norm"]) == pytest.approx(20.0)
    assert float(stress_mean["rotation_geodesic_error_rad"]) < float(
        stress_mean["rotation_tolerance"]
    )
    assert len(parsed["phi"]) == 30
    assert {int(row["contacts"]) for row in parsed["phi"]} == set(range(5))
    assert {float(row["dt"]) for row in parsed["phi"]} == {
        0.0, 1.0e-5, 0.004, 0.02, 0.15, 1.0
    }
    assert max(float(row["eq58_vs_eq60_relative_fro_error"]) for row in parsed["phi"]) < 1.0e-9
    assert max(float(row["zero_dt_identity_max_abs"]) for row in parsed["phi"]) < 5.0e-12
    assert len(parsed["qd"]) == 21
    assert len(parsed["eq52_matrix"]) == 20
    assert {int(row["contacts"]) for row in parsed["eq52_matrix"]} == set(range(5))
    assert len(parsed["lifecycle"]) == 5
    assert {row["case"] for row in parsed["synthetic"]} == {
        "static_four_contact_perturbed_recovery",
        "walking_switching_contacts_perturbed_recovery",
        "paper_table1_typed_bias_stochastic_propagation",
        "paper_table1_joint_encoder_measurement_correction",
        "synthetic_continuous_asd_bias_and_stochastic_propagation",
        "contact_chattering_three_sample_dwell",
        "stress_large_attitude_rate_ill_conditioned",
    }
    assert {row["case"] for row in parsed["gauge"]} == {
        "yaw_translation_family_normal",
        "yaw_translation_family_stress",
    }
    allan = {row["check"]: row for row in parsed["allan"]}
    assert allan["h5_go2_imu_paper_contact_eq61_adapter"]["fk_enters_qc"] == "false"
    table1 = allan["paper_table1_all_six_parameter_typed_mapping"]
    assert table1[
        "continuous_density_api_used"
    ] == "false"
    assert float(table1["joint_encoder_noise_std_deg"]) == 1.0
    assert table1["foot_position_jacobian_unit"] == "m_per_rad"
    assert table1["encoder_measurement_covariance_unit"] == "m2"
    assert float(table1["encoder_measurement_covariance_max_abs_error"]) < 2.0e-18
    assert all(
        row.get("pass") == "true"
        for section, rows in parsed.items()
        if section != "eq52_matrix"
        for row in rows
    )


def test_eq52_cpp_branch_matches_independent_dop853_covariance_ode(
    cpp_validation: dict[str, object],
) -> None:
    parsed = cpp_validation["parsed"]
    oracle = h34.verify_eq52_independent_oracle(parsed["eq52_matrix"])
    assert len(oracle) == 20
    assert all(row["pass"] for row in oracle)
    assert all(row["emitted_bias_state_consumed"] is False for row in oracle)
    assert all(
        row["emitted_bias_state_parsed_and_shape_checked"] is True
        for row in oracle
    )
    assert all(
        row["corrected_omega_and_acceleration_inputs_consumed"] is True
        for row in oracle
    )
    assert max(row["relative_fro_error"] for row in oracle) < 1.0e-10


def test_ideal_observability_rank_nullity_gauge_and_tolerance_sensitivity() -> None:
    rows = h34.ideal_observability_rows()
    expected = {
        1: (12, 8, 4),
        2: (15, 11, 4),
        3: (18, 14, 4),
        4: (21, 17, 4),
    }
    assert len(rows) == 4
    for row in rows:
        dimension, rank, nullity = expected[row["contacts"]]
        assert (row["dimension"], row["rank"], row["nullity"]) == (
            dimension,
            rank,
            nullity,
        )
        assert row["rank_at_0_1x"] == row["rank_at_1x"] == row["rank_at_10x"]
        assert row["o_times_g_fro_residual"] < 1.0e-9
        assert row["gauge_nullspace_residual"] < 1.0e-7
        assert row["maximum_principal_angle_rad"] < h34.OBSERVABILITY_PRINCIPAL_ANGLE_TOLERANCE_RAD
        assert row["pass"] is True


def test_noise_api_separates_density_psd_and_discrete_sample_std() -> None:
    header = (PATHS.cpp_root / "include/hartley_inekf/backend.hpp").read_text(
        encoding="utf-8"
    )
    source = (PATHS.cpp_root / "src/backend.cpp").read_text(encoding="utf-8")
    assert "struct ContinuousNoiseDensity" in header
    assert "struct ContinuousNoisePsd" in header
    assert "struct DiscreteSampleStd" in header
    assert "continuousPsdFromDensity" in header
    assert "discreteSampleStdFromDensity" in header
    propagate_body = source.split("void HartleyInEkf::propagate", 1)[1].split(
        "CorrectionDiagnostics HartleyInEkf::correctContacts", 1
    )[0]
    assert "discreteSampleStdFromDensity" not in propagate_body
    qc_body = source.split("Matrix HartleyInEkf::continuousQc", 1)[1].split(
        "Matrix HartleyInEkf::analyticalPhi", 1
    )[0]
    assert "continuousPsdFromDensity" in qc_body
    assert "sqrt" not in qc_body


def test_backend_identity_separation_is_explicit_in_api_and_artifacts() -> None:
    header = (PATHS.cpp_root / "include/hartley_inekf/backend.hpp").read_text(
        encoding="utf-8"
    )
    for identity in (
        h34.BACKEND_REPORTED,
        h34.BACKEND_EXACT_QD,
        h34.BACKEND_OFFICIAL_EARLY,
    ):
        assert identity in header
    summary = json.loads(
        (VALIDATION / "EQ61_VS_EQ52_SUMMARY.json").read_text(encoding="utf-8")
    )
    assert summary["reported_backend"] == h34.BACKEND_REPORTED
    assert summary["reference_backend"] == h34.BACKEND_EXACT_QD
    assert summary["eq61_expected_to_differ_from_eq52"] is True
    assert summary["maximum_relative_fro_difference"] > 0.0
    assert summary["maximum_eq52_oracle_relative_error"] < 1.0e-10
    assert summary["pass"] is True


def test_all_required_executable_validation_artifacts_are_nonempty_and_pass() -> None:
    required = {
        "LIE_GROUP_TEST_SUMMARY.json",
        "EXACT_MEAN_VALIDATION.csv",
        "PHI_FINITE_DIFFERENCE_VALIDATION.csv",
        "EQ61_VS_EQ52_DIAGNOSTIC.csv",
        "EQ61_VS_EQ52_SUMMARY.json",
        "GO2_ALLAN_PROFILE_DIMENSIONAL_VALIDATION.csv",
        "CONTACT_LIFECYCLE_VALIDATION.csv",
        "SYNTHETIC_STATE_RECOVERY.csv",
        "SYNTHETIC_GAUGE_EQUIVARIANCE.csv",
        "OFFICIAL_CPP_REGRESSION.csv",
        "IDEAL_OBSERVABILITY_VALIDATION.csv",
    }
    assert {path.name for path in VALIDATION.iterdir() if path.is_file()} == required
    assert all((VALIDATION / name).stat().st_size > 100 for name in required)
    for name in required:
        if name.endswith(".csv"):
            rows = _csv_rows(name)
            assert rows, name
            assert all(row["pass"].lower() == "true" for row in rows), name
        else:
            value = json.loads((VALIDATION / name).read_text(encoding="utf-8"))
            assert value["pass"] is True, name


def test_official_cpp_full_stream_regression_counts_and_residuals() -> None:
    rows = _csv_rows("OFFICIAL_CPP_REGRESSION.csv")
    by_metric = {row["metric"]: row for row in rows}
    expected_counts = {
        "rows": 59976,
        "imu_rows": 19992,
        "contact_rows": 19992,
        "kinematic_rows": 19992,
        "propagation_calls": 19992,
        "correction_calls": 19780,
        "correction_measurements": 26741,
        "additions": 34,
        "removals": 33,
        "final_active_contacts": 1,
        "final_state_dimension": 18,
    }
    for metric, expected in expected_counts.items():
        assert int(float(by_metric[metric]["official_value"])) == expected
        assert by_metric[metric]["absolute_difference"] == "0"
    assert float(
        by_metric["max_covariance_relative_frobenius_difference"][
            "absolute_difference"
        ]
    ) < 2.0e-7
    assert float(
        by_metric["official_rounded_stdout_fields"]["absolute_difference"]
    ) < 5.0e-6
    assert all(row["pass"] == "True" for row in rows)


def test_synthetic_lifecycle_recovery_gauge_and_stress_outputs() -> None:
    lifecycle = {row["case"]: row for row in _csv_rows("CONTACT_LIFECYCLE_VALIDATION.csv")}
    assert lifecycle["single_add_lower_id"]["active_ids"] == "0;2;5"
    assert lifecycle["simultaneous_remove"]["active_ids"] == "2;5"
    assert lifecycle["mixed_remove_add_same_epoch"]["active_ids"] == "0;1;3;5"
    assert all(float(row["direct_map_max_abs"]) < float(row["tolerance"])
               for row in lifecycle.values())
    recovery = {row["case"]: row for row in _csv_rows("SYNTHETIC_STATE_RECOVERY.csv")}
    walking = recovery["walking_switching_contacts_perturbed_recovery"]
    assert int(walking["flight_steps"]) == 10
    assert walking["observed_contact_counts"] == "0;1;2;3;4"
    assert float(walking["error_reduction_ratio"]) < 0.60
    static = recovery["static_four_contact_perturbed_recovery"]
    assert float(static["error_reduction_ratio"]) < 0.35
    stochastic = recovery["synthetic_continuous_asd_bias_and_stochastic_propagation"]
    assert stochastic["measurement_white_noise_injected"] == "True"
    assert stochastic["bias_random_walk_injected"] == "True"
    assert float(stochastic["state_error"]) < 0.5
    table1 = recovery["paper_table1_typed_bias_stochastic_propagation"]
    assert table1["continuous_density_api_used"] == "False"
    assert float(table1["gyro_bias_covariance_trace"]) == pytest.approx(
        float(table1["expected_each_bias_covariance_trace"]), abs=2.0e-12
    )
    encoder = recovery["paper_table1_joint_encoder_measurement_correction"]
    assert encoder["parameter_type"] == "PAPER_TABLE1_DISCRETE_STD"
    assert float(encoder["joint_encoder_noise_std_deg"]) == 1.0
    assert encoder["mapping"] == "R_EQUALS_J_SIGMA_RAD_SQUARED_I_J_TRANSPOSE"
    assert encoder["continuous_density_api_used"] == "False"
    assert float(encoder["measurement_r_mapping_max_abs_error"]) < 2.0e-18
    assert float(encoder["diagnostic_innovation_norm"]) > 1.0e-3
    assert float(encoder["final_innovation_norm"]) < float(
        encoder["initial_innovation_norm"]
    )
    assert float(encoder["nis"]) > 0.0
    dwell = recovery["contact_chattering_three_sample_dwell"]
    assert dwell["transitions_during_chatter"] == "0"
    assert dwell["accepted_transitions_after_stable_triplet"] == "1"
    assert float(
        recovery["stress_large_attitude_rate_ill_conditioned"]["covariance_min_eigenvalue"]
    ) > 0.0
    gauge = {row["case"]: row for row in _csv_rows("SYNTHETIC_GAUGE_EQUIVARIANCE.csv")}
    assert float(gauge["yaw_translation_family_normal"][
        "covariance_congruence_relative_fro_error"
    ]) < 2.0e-8
    assert float(gauge["yaw_translation_family_stress"][
        "covariance_congruence_relative_fro_error"
    ]) < 2.0e-6
    assert all(float(row["first_innovation_norm"]) > 1.0e-3 for row in gauge.values())
    assert all(row["absolute_yaw_observable"] == "False" for row in gauge.values())


def test_h3_h4_status_stops_before_real_by2_reference_and_other_methods() -> None:
    assert h34._parse_scoped_test_summary("24_passed") == {
        "raw": "24_passed",
        "syntax_valid": True,
        "caller_reported": True,
        "executed_by_generator": False,
        "passed": 24,
    }
    assert h34._parse_full_test_summary(h34.EXPECTED_FULL_TEST_RESULT)[
        "matches_expected_unchanged_failure_encoding"
    ] is True
    assert h34._parse_full_test_summary(
        "0_failed_923_passed_10_skipped_DIFFERENT_RESULT"
    )["matches_expected_unchanged_failure_encoding"] is False
    for malformed in ("24 passed", "PASS", "0_passed", "-1_passed"):
        with pytest.raises(h34.HartleyValidationError):
            h34._parse_scoped_test_summary(malformed)
    for malformed in ("PASS", "2 failed, 922 passed", "2_failed_922_passed"):
        with pytest.raises(h34.HartleyValidationError):
            h34._parse_full_test_summary(malformed)

    status = json.loads(
        (REPORT / "LSE01_H3_H4_STATUS.json").read_text(encoding="utf-8")
    )
    assert status["terminal_status"] == h34.FINAL_TERMINAL_STATUS
    assert status["terminal_pass_claimed"] is True
    assert status["go2_allan_profile_recovered"] is True
    assert status["go2_allan_exact_curve_recomputable"] is False
    assert status["h5_go2_parameter_gate_closed"] is True
    assert status["full_ijrr_backend_validated"] is True
    for key in (
        "real_BY2_filter_run_count",
        "gauge_ensemble_real_run_count",
        "reference_open_count",
        "ext06_run_count",
        "horizontal18_run_count",
        "other_method_run_count",
        "canonical541_run_count",
        "real_by2_navigation_output_csv_count",
    ):
        assert status[key] == 0
    assert status["trace_used_online"] is False
    assert status["external_stage_publication"] is True
    assert status["external_stage_hash_parity_verified"] is True
    assert status["commit_ready"] is True
    assert status["ready_for_real_by2_h5"] is False
    assert status["h5_execution_authorization"] == "HUMAN_AUTHORIZATION_REQUIRED"
    assert status["tests"]["full_paper_rebuild_no_new_failures"] is True
    assert status["tests"]["post_generation_audits_finalized_by_supervisor"] is True
    assert status["tests"]["python_compile_import"] == "PASS_4_FILES"
    assert status["tests"]["scoped_h3_h4_summary"] == {
        "passed": 24,
        "raw": "24_passed",
        "syntax_valid": True,
        "caller_reported": True,
        "executed_by_generator": False,
        "executed_by_supervisor_audit": True,
        "supervisor_verified": True,
    }
    assert status["tests"]["full_paper_rebuild_summary"][
        "matches_expected_unchanged_failure_encoding"
    ] is True
    assert status["tests"]["full_paper_rebuild_summary"][
        "executed_by_generator"
    ] is False
    assert status["tests"]["full_paper_rebuild_summary"][
        "executed_by_supervisor_audit"
    ] is True
    assert status["tests"]["full_paper_rebuild_summary"][
        "supervisor_verified"
    ] is True
    assert status["tests"]["full_paper_rebuild_no_new_failures"] is True
    assert len(
        status["tests"]["full_paper_rebuild_preexisting_unrelated_failures"]
    ) == 2
    assert status["tests"]["python_compile_import"] == "PASS_4_FILES"
    assert status["tests"]["artifact_schema_validation"] == (
        "PASS_14_JSON_14_YAML_27_CSV"
    )
    assert status["tests"]["post_generation_audits_finalized_by_supervisor"] is True
    report = (REPORT / "LSE01_H3_H4_IMPLEMENTATION_REPORT.md").read_text(
        encoding="utf-8"
    )
    assert "not a real BY2 navigation or accuracy result" in report
    assert "Supervisor/full `tests/paper_rebuild`" in report
    assert "Reference/trace opens: 0" in report


def test_validator_source_has_no_real_by2_or_reference_reader_or_output_route() -> None:
    texts = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            PATHS.cpp_root / "include/hartley_inekf/backend.hpp",
            PATHS.cpp_root / "src/backend.cpp",
            PATHS.cpp_root / "tools/validate_backend.cpp",
            REPO_ROOT
            / "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h3_h4.py",
        )
    )
    forbidden_runtime_tokens = (
        "BY2_BY3/",
        "trace.txt",
        "EVAL_NAV",
        "by2_algorithm_runner",
    )
    assert all(token not in texts for token in forbidden_runtime_tokens)
    generated_csv_names = {path.name for path in VALIDATION.glob("*.csv")}
    assert not any("NAV" in name or "navigation" in name.lower() for name in generated_csv_names)
