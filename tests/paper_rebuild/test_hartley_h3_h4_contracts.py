from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PAYLOAD = (
    REPO_ROOT
    / "docs/paper_rebuild/horizontal_literature/hartley/stage_payload"
)
CONFIG_PAYLOAD = (
    REPO_ROOT
    / "configs/paper_rebuild/horizontal_literature/hartley/stage_payload"
)
SOURCE_REGISTRY = DOC_PAYLOAD / "00_SOURCE_REGISTRY"
IMPLEMENTATION = DOC_PAYLOAD / "06_IMPLEMENTATION"
REPORT = DOC_PAYLOAD / "11_REPORT"
CONTRACTS = CONFIG_PAYLOAD / "04_METHOD_CONTRACTS"

PROFILE_PATH = CONTRACTS / "GO2_IMU_ALLAN_90MIN_RECOVERED_V1.yaml"
H5_PROFILE_PATH = CONTRACTS / "HARTLEY_FUTURE_H5_IMU_PROFILE_CONTRACT.yaml"
BACKEND_REGISTRY_PATH = IMPLEMENTATION / "HARTLEY_BACKEND_IDENTITY_REGISTRY.yaml"
NOISE_REGISTRY_PATH = IMPLEMENTATION / "HARTLEY_NOISE_UNIT_AND_DIMENSION_REGISTRY.csv"
H5_GATE_PATH = IMPLEMENTATION / "HARTLEY_FUTURE_H5_PARAMETER_GATE.yaml"
PROFILE_STATUS_PATH = REPORT / "LSE01_GO2_ALLAN_PROFILE_STATUS.json"

REQUIRED_STATIC_ARTIFACTS = {
    SOURCE_REGISTRY / "GO2_IMU_ALLAN_RECOVERED_PROVENANCE.md",
    PROFILE_PATH,
    H5_PROFILE_PATH,
    IMPLEMENTATION / "HARTLEY_IJRR2020_IMPLEMENTATION_REGISTRY.csv",
    IMPLEMENTATION / "HARTLEY_EQUATION_TO_CODE_MAP_H3.csv",
    BACKEND_REGISTRY_PATH,
    NOISE_REGISTRY_PATH,
    H5_GATE_PATH,
    REPORT / "LSE01_GO2_ALLAN_PROFILE_SUPPLEMENT.md",
    PROFILE_STATUS_PATH,
}

EXPECTED_DENSITIES = {
    "gyro_measurement_white_noise_density": (
        2.865130e-4,
        "rad/s/sqrt(Hz)",
        8.208969916900001e-8,
        "rad^2/s",
        "gyro_measurement",
    ),
    "accelerometer_measurement_white_noise_density": (
        1.285395e-3,
        "m/s^2/sqrt(Hz)",
        1.652240306025e-6,
        "m^2/s^3",
        "accelerometer_measurement",
    ),
    "gyro_bias_random_walk_density": (
        2.996871e-5,
        "rad/s^2/sqrt(Hz)",
        8.981235790641001e-10,
        "rad^2/s^3",
        "gyro_bias_random_walk",
    ),
    "accelerometer_bias_random_walk_density": (
        1.594412e-4,
        "m/s^3/sqrt(Hz)",
        2.542149625744e-8,
        "m^2/s^5",
        "accelerometer_bias_random_walk",
    ),
}

HISTORICAL_H0_REPORT_HASHES = {
    "LSE01_H0_H2_REPORT.md": (
        "6acde6b5ace54ef5dfddee27ad9d07f65a216bc9507a4f0f4204c3b24a5b07fb"
    ),
    "LSE01_H0_H2_STATUS.json": (
        "83ddb52a79c86a10f8b9744b5536b8548a39c27e14885c68eada5cfd29209eec"
    ),
}


def _yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows, path
    assert all(None not in row for row in rows), path
    return rows


def test_required_allan_and_backend_static_artifacts_exist_and_parse() -> None:
    assert all(path.is_file() for path in REQUIRED_STATIC_ARTIFACTS)
    for path in REQUIRED_STATIC_ARTIFACTS:
        if path.suffix in {".yaml", ".yml"}:
            _yaml(path)
        elif path.suffix == ".json":
            _json(path)
        elif path.suffix == ".csv":
            _csv_rows(path)
        else:
            assert path.read_text(encoding="utf-8").strip()


def test_recovered_profile_has_exact_identity_metadata_and_limitations() -> None:
    profile = _yaml(PROFILE_PATH)
    assert profile["profile_id"] == "GO2_IMU_ALLAN_90MIN_RECOVERED_V1"
    assert profile["evidence_label"] == (
        "THESIS_AND_CONTEMPORANEOUS_TERMINAL_RECORD_CROSS_CONFIRMED"
    )
    metadata = profile["dataset_metadata"]
    assert metadata == {
        "platform": "Unitree Go2 body IMU",
        "condition": "stationary",
        "reported_duration": {"minutes": 90, "seconds": 5400},
        "reported_approximate_sample_count": "about 2.4 million",
        "axis_policy": "ARITHMETIC_MEAN_OF_X_Y_Z",
        "exact_sampling_rate_claim_allowed": False,
    }
    assert profile["provenance_limitations"] == {
        "original_static_csv_available": False,
        "original_fitting_script_available": False,
        "exact_per_axis_values_available": False,
        "exact_Allan_curve_recomputable": False,
        "exact_fitting_implementation_auditable": False,
        "numeric_average_axis_profile_recovered": True,
        "raw_artifact_reproducibility_claim_allowed": False,
    }


def test_recovered_densities_units_and_psds_square_exactly_once() -> None:
    profile = _yaml(PROFILE_PATH)
    entries = profile["continuous_noise_density_asd"]
    assert set(entries) == set(EXPECTED_DENSITIES)
    for role, (density, unit, psd, psd_unit, qc_block) in EXPECTED_DENSITIES.items():
        entry = entries[role]
        assert entry["value"] == density
        assert entry["unit"] == unit
        assert entry["continuous_psd_value"] == psd
        assert entry["continuous_psd_value"] == pytest.approx(
            entry["value"] ** 2, rel=5.0e-16, abs=0.0
        )
        assert entry["continuous_psd_unit"] == psd_unit
        assert entry["qc_block"] == qc_block

    qc = profile["qc_construction_contract"]
    assert qc["density_input_cpp_type"] == "ContinuousNoiseDensity"
    assert qc["density_semantics"] == "CONTINUOUS_AMPLITUDE_SPECTRAL_DENSITY"
    assert qc["psd_output_cpp_type"] == "ContinuousNoisePsd"
    assert qc["discrete_process_covariance_cpp_type"] == "Eigen_MatrixXd"
    assert qc["discrete_process_covariance_api_quantity"] == "Qd"
    assert qc["conversion_function"] == "continuousPsdFromDensity"
    assert qc["rule"] == "SQUARE_EACH_CONTINUOUS_DENSITY_EXACTLY_ONCE"
    assert qc["sqrt_dt_preprocessing_before_qc"] is False
    assert qc["dt_preprocessing_before_qc"] is False
    assert qc["double_squaring_allowed"] is False
    assert qc["continuous_psd_is_qc_input"] is True
    sample = qc["discrete_sample_standard_deviation"]
    assert sample["cpp_type"] == "DiscreteSampleStd"
    assert sample["api_name"] == "discreteSampleStdFromDensity"
    assert sample["role"] == "EXPLICIT_SYNTHETIC_SAMPLER_CONVERSION_ONLY"
    assert sample["qc_input"] is False
    assert sample["may_not_be_fed_back_into_qc"] is True


def test_bias_instability_values_are_diagnostic_only() -> None:
    diagnostics = _yaml(PROFILE_PATH)["bias_instability_diagnostics"]
    assert diagnostics["semantic_role"] == "IMU_CHARACTERIZATION_DIAGNOSTIC_ONLY"
    assert diagnostics["accelerometer_bias_instability"] == {
        "value": 7.781688e-4,
        "unit": "m/s^2",
    }
    assert diagnostics["gyro_bias_instability"] == {
        "value": 4.550529e-5,
        "unit": "rad/s",
    }
    assert diagnostics["replaces_bias_random_walk_density"] is False
    assert diagnostics["is_initial_bias_standard_deviation"] is False


def test_noise_registry_preserves_density_psd_and_sample_interfaces() -> None:
    rows = _csv_rows(NOISE_REGISTRY_PATH)
    by_role = {row["quantity_role"]: row for row in rows}
    for role, (density, unit, psd, psd_unit, qc_block) in EXPECTED_DENSITIES.items():
        row = by_role[role]
        assert row["api_interface"] == "ContinuousNoiseDensity"
        assert float(row["value"]) == density
        assert row["unit"] == unit
        assert float(row["continuous_psd_value"]) == psd
        assert row["continuous_psd_unit"] == psd_unit
        assert row["qc_block"] == qc_block
        assert row["square_count"] == "1"
        assert row["sqrt_dt_preprocessing"] == "false"
        assert row["qc_input"] == "true"
    discrete = by_role["discrete_sample_standard_deviation"]
    assert discrete["api_interface"] == "DiscreteSampleStd"
    assert discrete["qc_input"] == "false"
    assert "NEVER_FEED" in discrete["semantic_boundary"]
    for role in ("accelerometer_bias_instability", "gyro_bias_instability"):
        assert by_role[role]["semantic_boundary"] == (
            "IMU_CHARACTERIZATION_DIAGNOSTIC_ONLY"
        )
        assert by_role[role]["qc_input"] == "false"
    paper_contact = by_role["paper_table1_contact_linear_velocity_noise_std"]
    assert paper_contact["api_interface"] == "PaperTable1DiscreteStd"
    assert float(paper_contact["value"]) == 0.05
    assert paper_contact["qc_input"] == "false"
    assert "NOT_CONTINUOUS_ASD" in paper_contact["semantic_boundary"]
    paper_family = by_role["paper_table1_stochastic_parameter_family"]
    assert paper_family["qc_block"] == (
        "FIVE_PROCESS_EQ61_QBAR_PLUS_ONE_MEASUREMENT_R"
    )
    assert "ENCODER_ANGLE_MAPPED_THROUGH_FOOT_JACOBIAN" in paper_family[
        "semantic_boundary"
    ]
    mixed = by_role["h5_primary_go2_imu_paper_contact_adapter"]
    assert mixed["api_interface"] == (
        "HartleyInEkf::eq61ProcessCovarianceGo2ImuPaperContact"
    )
    encoder = by_role["paper_table1_joint_encoder_noise_std"]
    assert encoder["api_interface"] == "PaperTable1DiscreteStd"
    assert float(encoder["value"]) == 1.0
    assert encoder["unit"] == "deg"
    assert encoder["qc_input"] == "false"
    assert encoder["qc_block"] == "MEASUREMENT_R_VIA_FOOT_JACOBIAN"
    assert "NO_DEG_TO_M_SCALAR" in encoder["semantic_boundary"]
    encoder_r = by_role["paper_table1_joint_encoder_measurement_covariance"]
    assert encoder_r["api_interface"] == (
        "contactMeasurementCovarianceFromPaperTable1JointEncoder"
    )
    assert encoder_r["unit"] == "m^2"
    assert encoder_r["qc_input"] == "false"
    fk = by_role["h5_primary_fk_measurement_std"]
    assert fk["api_interface"] == "MeasurementStdMeters"
    assert fk["qc_input"] == "false"
    assert "NEVER_ENTERS_QC" in fk["semantic_boundary"]


def test_method_contract_selects_eq61_production_and_separates_all_backends() -> None:
    method = _yaml(CONTRACTS / "HARTLEY_METHOD_CONTRACT.yaml")
    target = method["discretization_target"]
    assert target["selected_policy"] == "HARTLEY_IJRR2020_REPORTED_BACKEND"
    assert target["identities_may_not_be_conflated"] is True
    policies = target["policies"]
    assert set(policies) == {
        "HARTLEY_IJRR2020_REPORTED_BACKEND",
        "EXACT_QD_REFERENCE_DIAGNOSTIC",
        "OFFICIAL_CPP_EARLY_REGRESSION",
    }
    production = policies["HARTLEY_IJRR2020_REPORTED_BACKEND"]
    assert production["primary_backend"] is True
    assert production["deterministic_state"] == "EXACT_EQ_50_GAMMA_0_1_2"
    assert production["state_transition"] == (
        "ANALYTICAL_RIGHT_INVARIANT_PHI_EQS_58_OR_60"
    )
    assert production["discrete_process_covariance"] == (
        "APPROXIMATION_EQ_61_PHI_QBAR_K_PHI_TRANSPOSE_DT"
    )
    assert production["exact_integral"] is False
    diagnostic = policies["EXACT_QD_REFERENCE_DIAGNOSTIC"]
    assert diagnostic["diagnostic_reference"] is True
    assert "EQ_52" in diagnostic["discrete_process_covariance"]
    assert diagnostic["article_reported_result_path"] is False
    early = policies["OFFICIAL_CPP_EARLY_REGRESSION"]
    assert early["deterministic_state"] == "FROZEN_R_VELOCITY_POSITION_APPROXIMATION"
    assert early["state_transition"] == "PHI_EQUALS_I_PLUS_A_DT"
    assert early["discrete_process_covariance"] == "OFFICIAL_MAPPED_Q_APPROXIMATION"
    assert early["event_lifecycle"] == "OFFICIAL_EVENT_LIFECYCLE"
    historical = target["historical_h0_h2_future_plan"]
    assert historical["selected_policy_at_h0_h2_close"] == (
        "FULL_IJRR_MATHEMATICAL_TARGET"
    )
    assert historical["historical_report_rewritten"] is False


def test_backend_registry_freezes_exact_api_identities_and_tolerances() -> None:
    registry = _yaml(BACKEND_REGISTRY_PATH)
    identities = registry["backend_identities"]
    assert identities["identities_may_not_be_conflated"] is True
    assert identities["HARTLEY_IJRR2020_REPORTED_BACKEND"][
        "discrete_process_covariance"
    ] == "IJRR_EQ_61_PAPER_REPORTED_APPROXIMATION"
    assert identities["EXACT_QD_REFERENCE_DIAGNOSTIC"][
        "discrete_process_covariance"
    ] == "IJRR_EQ_52_INDEPENDENT_HIGH_ACCURACY_INTEGRAL"
    assert identities["OFFICIAL_CPP_EARLY_REGRESSION"]["state_transition"] == (
        "PHI_EQUALS_I_PLUS_A_DT"
    )
    implementation = registry["implementation"]
    assert implementation["backend_class"] == "HartleyInEkf"
    assert "continuousPsdFromDensity" in implementation[
        "public_noise_interface_functions"
    ]
    assert "discreteSampleStdFromDensity" in implementation[
        "public_noise_interface_functions"
    ]
    assert "isotropicMeasurementCovariance" in implementation[
        "public_noise_interface_functions"
    ]
    assert "contactMeasurementCovarianceFromPaperTable1JointEncoder" in implementation[
        "public_noise_interface_functions"
    ]
    for symbol in (
        "eq61MappedQbarPaperTable1",
        "eq61ProcessCovariancePaperTable1",
        "eq61MappedQbarGo2ImuPaperContact",
        "eq61ProcessCovarianceGo2ImuPaperContact",
    ):
        assert symbol in implementation["mathematical_api"]
    noise = registry["noise_interface_types"]
    assert noise["paper_table1_semantics"] == (
        "PAPER_NATIVE_DISCRETE_STD_FIVE_PROCESS_EQ61_QBAR_PLUS_ONE_"
        "ENCODER_MEASUREMENT_R"
    )
    assert noise["paper_table1_contact_std_m_per_s"] == 0.05
    assert noise["paper_table1_joint_encoder_std_deg"] == 1.0
    assert noise["paper_table1_joint_encoder_measurement_covariance_api"] == (
        "contactMeasurementCovarianceFromPaperTable1JointEncoder"
    )
    assert noise["paper_table1_joint_encoder_mapping"] == (
        "R_EQUALS_J_SIGMA_RAD_SQUARED_I_J_TRANSPOSE"
    )
    assert noise["paper_table1_joint_encoder_deg_to_meter_scalar_allowed"] is False
    assert noise["paper_table1_contact_reinterpreted_as_continuous_asd"] is False
    assert noise["fk_measurement_enters_qc"] is False
    for key in ("public_header", "implementation_source", "cpp_tests", "validation_tool"):
        assert (REPO_ROOT / implementation[key]).is_file(), key

    tolerances = registry["preregistered_validation_tolerances"]
    assert tolerances == {
        "exp_log_rotation_frobenius": {
            "normal": 2.0e-11,
            "near_pi_stress": 2.0e-9,
        },
        "gamma_psi_oracle_relative_error": {
            "normal": 2.0e-11,
            "stress": 2.0e-9,
        },
        "small_angle_branch_continuity": {"normal": 5.0e-12},
        "adjoint_conjugation_relative_error": {
            "normal": 5.0e-11,
            "stress": 2.0e-9,
        },
        "eq50_rotation_geodesic_rad": {
            "normal": 2.0e-10,
            "stress": 2.0e-8,
        },
        "eq50_velocity_position_mixed_error": {
            "normal": 2.0e-10,
            "stress": 2.0e-8,
        },
        "eq58_vs_eq60_relative_frobenius": {
            "normal": 1.0e-11,
            "stress": 1.0e-9,
        },
        "five_point_invariant_error_fd_phi_max_abs": {
            "finite_difference_h": 1.0e-5,
            "normal": 2.0e-7,
            "stress": 2.0e-5,
        },
        "five_point_invariant_error_fd_phi_block_relative": {
            "finite_difference_h": 1.0e-5,
            "normal": 1.0e-6,
            "stress": 5.0e-5,
        },
        "zero_dt_phi_identity_max_abs": {"normal": 5.0e-12},
        "eq52_gauss_legendre64_vs_dop853_relative_frobenius": {
            "normal": 2.0e-8,
            "stress": 2.0e-6,
            "oracle_method": "SCIPY_DOP853",
            "oracle_rtol": 1.0e-12,
            "oracle_atol": 1.0e-14,
        },
        "covariance_normalized_asymmetry": {
            "normal": 1.0e-12,
            "stress": 1.0e-10,
        },
        "covariance_psd_minimum_eigenvalue": {
            "normal_lower_bound": "-1.0e-12 * max(1, lambda_max)",
            "stress_lower_bound": "-1.0e-10 * max(1, lambda_max)",
        },
        "lifecycle_direct_map_max_abs": {
            "normal": 2.0e-12,
            "stress": 1.0e-10,
        },
        "gauge_state_and_bias_after_inverse_gauge": {
            "normal": 2.0e-9,
            "stress": 2.0e-7,
        },
        "gauge_covariance_relative_frobenius": {
            "normal": 2.0e-8,
            "stress": 2.0e-6,
        },
        "official_sequence_state_max_abs_or_geodesic": {"normal": 5.0e-8},
        "official_sequence_covariance_relative_frobenius": {"normal": 2.0e-7},
        "official_rounded_stdout_fields": {"normal": 5.0e-6},
    }
    observability = registry["ideal_observability_tolerances"]
    assert observability["rank_tolerance"] == "max(1.0e-12,1.0e-9*sigma_max)"
    assert observability["rank_tolerance_multipliers"] == [0.1, 1.0, 10.0]
    assert observability["O_times_G_residual_max"] == 1.0e-9
    assert observability["gauge_nullspace_residual_max"] == 1.0e-7
    assert observability["maximum_principal_angle_deg"] == 1.0e-5


def test_implementation_and_equation_maps_point_to_real_exact_symbols() -> None:
    implementation_rows = _csv_rows(
        IMPLEMENTATION / "HARTLEY_IJRR2020_IMPLEMENTATION_REGISTRY.csv"
    )
    assert {row["backend_identity"] for row in implementation_rows} == {
        "HARTLEY_IJRR2020_REPORTED_BACKEND",
        "EXACT_QD_REFERENCE_DIAGNOSTIC",
        "OFFICIAL_CPP_EARLY_REGRESSION",
    }
    assert all(row["implementation_status"] == "IMPLEMENTED" for row in implementation_rows)
    for row in implementation_rows:
        assert (REPO_ROOT / row["code_path"]).is_file()
        source = (REPO_ROOT / row["code_path"]).read_text(encoding="utf-8")
        assert row["code_symbol"] in source

    equation_rows = _csv_rows(IMPLEMENTATION / "HARTLEY_EQUATION_TO_CODE_MAP_H3.csv")
    by_operation = {row["mathematical_operation"]: row for row in equation_rows}
    assert {
        "so3_exp_log",
        "gamma_0_1_2",
        "psi_1_2",
        "sek3_exp_log_adjoint",
        "eq50_exact_mean",
        "continuous_A_L_Qc",
        "analytical_right_invariant_phi",
        "eq61_process_covariance",
        "eq52_process_covariance_diagnostic",
        "contact_measurement_and_correction",
        "contact_augmentation_eq32",
        "contact_removal_eq30",
        "paper_table1_typed_qbar_qd_adapter",
        "paper_table1_joint_encoder_measurement_covariance",
        "h5_go2_imu_paper_contact_mixed_adapter",
    } <= set(by_operation)
    for row in equation_rows:
        path = REPO_ROOT / row["code_path"]
        assert path.is_file()
        assert row["code_symbol"] in path.read_text(encoding="utf-8")


def test_h5_runs_fk_semantics_and_reference_independent_selection_are_frozen() -> None:
    contract = _yaml(H5_PROFILE_PATH)
    assert contract["contract_status"] == "PREREGISTERED_NOT_EXECUTED"
    assert contract["production_backend"] == "HARTLEY_IJRR2020_REPORTED_BACKEND"
    assert contract["backend_mean"] == "EXACT_EQ_50_GAMMA_0_1_2"
    assert contract["backend_transition"] == (
        "ANALYTICAL_RIGHT_INVARIANT_PHI_EQS_58_OR_60"
    )
    assert contract["backend_process_covariance"] == (
        "PAPER_REPORTED_APPROXIMATION_EQ_61"
    )
    runs = contract["run_identities"]
    assert set(runs) == {
        "H5_PRIMARY_GO2_ALLAN_RECOVERED",
        "H5_PAPER_TABLE1_PARAMETER_REGRESSION",
        "H5_FK_PROXY_SENSITIVITY",
    }
    assert all(run["execution_status"] == "PREREGISTERED_NOT_EXECUTED" for run in runs.values())
    assert runs["H5_PRIMARY_GO2_ALLAN_RECOVERED"]["sigma_fk_m"] == 0.010
    assert runs["H5_PRIMARY_GO2_ALLAN_RECOVERED"]["primary"] is True
    primary = runs["H5_PRIMARY_GO2_ALLAN_RECOVERED"]
    contact_process = primary["contact_process_parameter"]
    assert contact_process == {
        "cpp_type": "PaperTable1DiscreteStd",
        "field": "contact_linear_velocity_noise_std_m_per_s",
        "value": 0.05,
        "unit": "m/s",
        "semantics": "PAPER_NATIVE_DISCRETE_STD",
        "adapter": "HartleyInEkf::eq61MappedQbarGo2ImuPaperContact",
        "qd_adapter": "HartleyInEkf::eq61ProcessCovarianceGo2ImuPaperContact",
        "mapping": "SQUARE_ONCE_IN_QBAR_THEN_MULTIPLY_BY_DT_IN_EQ61",
        "reinterpret_as_continuous_asd": False,
        "enter_continuous_qc": False,
    }
    assert primary["fk_measurement_cpp_type"] == "MeasurementStdMeters"
    assert primary["fk_enters_process_qc"] is False
    assert runs["H5_PAPER_TABLE1_PARAMETER_REGRESSION"][
        "imu_parameter_interface"
    ] == "PaperTable1DiscreteStd"
    assert runs["H5_PAPER_TABLE1_PARAMETER_REGRESSION"][
        "reinterpret_as_continuous_asd"
    ] is False
    assert runs["H5_PAPER_TABLE1_PARAMETER_REGRESSION"]["qbar_adapter"] == (
        "HartleyInEkf::eq61MappedQbarPaperTable1"
    )
    paper_measurement = runs["H5_PAPER_TABLE1_PARAMETER_REGRESSION"][
        "joint_encoder_measurement_parameter"
    ]
    assert paper_measurement == {
        "cpp_field": "joint_encoder_noise_std_deg",
        "cpp_type": "PaperTable1DiscreteStd",
        "covariance_api": (
            "contactMeasurementCovarianceFromPaperTable1JointEncoder"
        ),
        "covariance_mapping": "R_EQUALS_J_SIGMA_RAD_SQUARED_I_J_TRANSPOSE",
        "foot_position_jacobian_unit": "m/rad",
        "no_deg_to_meter_scalar": True,
        "role": "MEASUREMENT_R_ONLY",
        "unit": "deg",
        "value": 1.0,
    }
    assert runs["H5_FK_PROXY_SENSITIVITY"]["sigma_fk_m"] == [0.005, 0.010, 0.020]
    assert runs["H5_FK_PROXY_SENSITIVITY"]["covariance_m2"] == {
        "sigma_0p005": "2.5e-5_I3",
        "sigma_0p010": "1.0e-4_I3",
        "sigma_0p020": "4.0e-4_I3",
    }
    fk = contract["fk_proxy_semantics"]
    assert fk["h0_h2_repeatability_result"]["role"] == (
        "GO2_FK_PROXY_REPEATABILITY_LOWER_BOUND"
    )
    assert fk["h0_h2_repeatability_result"]["future_filter_primary"] is False
    assert fk["physical_proxy_covariance"]["primary_sigma_m"] == 0.010
    assert fk["selection_using_reference_accuracy"] is False
    assert fk["selection_using_final_odometry"] is False
    assert contract["selection_and_execution_boundary"][
        "h5_execution_authorization"
    ] == "HUMAN_AUTHORIZATION_REQUIRED"
    assert contract["selection_and_execution_boundary"][
        "ready_for_real_by2_h5"
    ] is False

    gate = _yaml(H5_GATE_PATH)
    assert gate["h5_go2_parameter_gate_closed"] is True
    assert gate["gate_closure_evidence"] == {
        "executable_check": "h5_go2_imu_paper_contact_eq61_adapter",
        "paper_table1_all_six_executable_check": (
            "paper_table1_all_six_parameter_typed_mapping"
        ),
        "paper_table1_encoder_correction_executable_check": (
            "paper_table1_joint_encoder_measurement_correction"
        ),
        "artifact": "07_SYNTHETIC_VALIDATION/GO2_ALLAN_PROFILE_DIMENSIONAL_VALIDATION.csv",
        "pass_required": True,
    }
    assert gate["production_backend"] == {
        "backend_id": "HARTLEY_IJRR2020_REPORTED_BACKEND",
        "deterministic_mean": "IJRR_EQ_50",
        "analytical_transition": "IJRR_EQS_58_OR_60",
        "discrete_process_covariance": "IJRR_EQ_61",
    }
    assert gate["go2_profile"]["numeric_average_axis_profile_recovered"] is True
    assert gate["go2_profile"]["exact_Allan_curve_recomputable"] is False
    assert gate["go2_profile"]["continuous_density_to_qc_mapping"] == {
        "square_each_density_exactly_once": True,
        "sqrt_dt_preprocessing": False,
        "discrete_sample_std_is_qc_input": False,
    }
    assert gate["fk_proxy_gate"]["repeatability_future_filter_primary"] is False
    assert gate["fk_proxy_gate"]["reference_accuracy_used_for_selection"] is False
    assert gate["fk_proxy_gate"]["final_odometry_used_for_selection"] is False
    primary_gate = gate["preregistered_runs"][0]
    assert primary_gate["contact_process_parameter"]["value"] == 0.05
    assert primary_gate["contact_process_parameter"]["semantics"] == (
        "PAPER_NATIVE_DISCRETE_STD"
    )
    assert primary_gate["contact_process_parameter"]["enters_continuous_qc"] is False
    assert primary_gate["fk_enters_process_qc"] is False
    regression_gate = gate["preregistered_runs"][1]
    assert regression_gate["all_six_table1_stochastic_parameters_retained"] is True
    assert regression_gate["joint_encoder_measurement_parameter"][
        "covariance_mapping"
    ] == "R_EQUALS_J_SIGMA_RAD_SQUARED_I_J_TRANSPOSE"
    assert regression_gate["joint_encoder_measurement_parameter"][
        "no_deg_to_meter_scalar"
    ] is True
    assert gate["gate_closure_evidence"]["paper_table1_all_six_executable_check"] == (
        "paper_table1_all_six_parameter_typed_mapping"
    )
    assert gate["gate_closure_evidence"][
        "paper_table1_encoder_correction_executable_check"
    ] == "paper_table1_joint_encoder_measurement_correction"
    assert gate["execution_boundary"]["ready_for_real_by2_h5"] is False
    assert gate["execution_boundary"]["h5_execution_authorization"] == (
        "HUMAN_AUTHORIZATION_REQUIRED"
    )


def test_current_parameter_registry_replaces_unknown_gate_with_recovered_profile() -> None:
    rows = _csv_rows(CONTRACTS / "HARTLEY_PARAMETER_SOURCE_REGISTRY.csv")
    by_parameter = {row["parameter"]: row for row in rows}
    assert "go2_imu_measurement_or_allan_provenance" not in by_parameter
    assert by_parameter["go2_imu_allan_profile"]["value"] == (
        "GO2_IMU_ALLAN_90MIN_RECOVERED_V1"
    )
    assert by_parameter["go2_imu_allan_profile"]["paper_or_code_identity"] == (
        "THESIS_AND_CONTEMPORANEOUS_TERMINAL_RECORD_CROSS_CONFIRMED"
    )
    for role, (value, unit, _, _, _) in EXPECTED_DENSITIES.items():
        assert float(by_parameter[role]["value"]) == value
        assert by_parameter[role]["unit"] == unit
        assert by_parameter[role]["paper_or_code_identity"] == (
            "GO2_IMU_ALLAN_90MIN_RECOVERED_V1"
        )
        assert by_parameter[role]["proposed_for_BY2"] == "true"
    assert by_parameter["joint_encoder_noise_std"]["value"] == "1.0"
    assert by_parameter["joint_encoder_noise_std"]["unit"] == "deg"
    assert by_parameter["joint_encoder_noise_std"][
        "paper_or_code_identity"
    ] == (
        "HARTLEY_IJRR2020_TABLE1_MEASUREMENT_R_JACOBIAN_ADAPTER_"
        "PAPER_NATIVE_DISCRETE_STD"
    )
    assert all(row["trace_tuned"] == "false" for row in rows)


def test_historical_h0_h2_terminal_report_and_status_are_byte_unchanged() -> None:
    for filename, expected in HISTORICAL_H0_REPORT_HASHES.items():
        path = REPORT / filename
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    status = _json(REPORT / "LSE01_H0_H2_STATUS.json")
    assert status["terminal_status"] == (
        "PASS_LSE01_H0_H2_HARTLEY_SOURCE_METHOD_AND_BY2_CONTRACT_READY"
    )
    assert status["tests"]["scoped_hartley"] == "50_passed"


def test_static_profile_status_is_scoped_and_all_forbidden_run_counts_are_zero() -> None:
    status = _json(PROFILE_STATUS_PATH)
    assert status["terminal_status"] == (
        "PASS_LSE01_TASK_A_GO2_ALLAN_PROFILE_REGISTERED_AND_H5_GATE_CLOSED"
    )
    assert status["go2_allan_profile_recovered"] is True
    assert status["go2_allan_exact_curve_recomputable"] is False
    assert status["h5_go2_parameter_gate_closed"] is True
    assert status["profile_registration_scope_only"] is True
    assert status["external_stage_publication_claim"] is True
    assert status["external_stage_hash_parity_verified"] is True
    assert status["full_ijrr_backend_validated"] is True
    assert status["h5_run_count"] == 0
    assert status["ready_for_real_by2_h5"] is False
    assert status["h5_execution_authorization"] == "HUMAN_AUTHORIZATION_REQUIRED"
    assert status["h5_primary_typed_adapter"]["pass"] is True
    assert status["h5_primary_typed_adapter"]["fk_enters_qc"] is False
    assert status["run_counters"] == {
        "canonical541_run_count": 0,
        "ext06_run_count": 0,
        "gauge_ensemble_real_run_count": 0,
        "real_BY2_filter_run_count": 0,
        "real_BY2_navigation_output_count": 0,
        "reference_open_count": 0,
    }


def test_new_static_artifacts_contain_no_local_paths_or_positive_run_claims() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(REQUIRED_STATIC_ARTIFACTS)
    )
    lowered = combined.lower()
    assert ("/" + "home/") not in lowered
    assert ("/" + "mnt/") not in lowered
    assert re.search(r"\b[a-z]:[\\/]", lowered) is None
    assert "UNVERIFIED_NOT_PRESENT_ACTIVE_ALLOWLIST" not in combined
    assert "exact sampling rate" not in combined.lower() or "forbidden" in combined.lower()

    prohibited_true_keys = (
        "raw_artifact_reproducibility_claim_allowed",
        "raw_artifact_reproducibility_claim",
        "exact_sampling_rate_claim_allowed",
        "real_BY2_navigation_authorized_in_h3_h4",
        "real_BY2_navigation_executed",
        "reference_opened",
        "ext06_executed",
        "canonical541_executed",
        "future_filter_primary",
        "reinterpret_as_continuous_asd",
    )
    for key in prohibited_true_keys:
        pattern = rf'(?im)^\s*["\']?{re.escape(key)}["\']?\s*:\s*true\b'
        assert re.search(pattern, combined) is None, key
