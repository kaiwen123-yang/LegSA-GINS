from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
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
CODE_AUDIT = DOC_PAYLOAD / "02_OFFICIAL_CODE_AUDIT"
EXAMPLE_RESULTS = DOC_PAYLOAD / "05_OFFICIAL_EXAMPLE_RESULTS"
CONTRACTS = CONFIG_PAYLOAD / "04_METHOD_CONTRACTS"


EXPECTED_PAPERS = {
    "HARTLEY_IJRR2020_ARXIV1904_09251V2": {
        "doi": "10.1177/0278364919894385",
        "arxiv_id": "1904.09251",
        "version": "v2",
        "page_count": "44",
        "sha256": "b519bbd4b0182da64f3fe0ec2834e7fec89be05931f1a7cffa6dc13f999b3f5c",
        "filename": "HARTLEY_INEKF_IJRR2020_ARXIV1904.09251.pdf",
    },
    "HARTLEY_RSS2018_ARXIV1805_10410V1": {
        "doi": "10.15607/RSS.2018.XIV.050",
        "arxiv_id": "1805.10410",
        "version": "v1",
        "page_count": "9",
        "sha256": "b7c744a06116899a3c54ec632adc1bbc9396230a92b582fa899269ce0ae9311a",
        "filename": "HARTLEY_CONTACT_AIDED_INEKF_RSS2018_ARXIV1805.10410.pdf",
    },
}

EXPECTED_REPOSITORIES = {
    "HARTLEY_CPP_PRIMARY": "ef16e8a1df72f9272111a488880e3fe9d161f59f",
    "HARTLEY_MATLAB_HISTORICAL": "15f1ee79d40cb9af3875f1c4153dd17414a276b2",
    "UNITREE_GO2_ORDER_SUPPORT": "668d1ec5a05d1c38d3306bdca7d59f2ba3581a88",
}

MANDATED_CPP_FILES = {
    "include/InEKF.h",
    "include/RobotState.h",
    "include/NoiseParams.h",
    "include/LieGroup.h",
    "src/InEKF.cpp",
    "src/RobotState.cpp",
    "src/NoiseParams.cpp",
    "src/LieGroup.cpp",
    "src/examples/kinematics.cpp",
    "src/examples/landmarks.cpp",
    "CMakeLists.txt",
    "LICENSE",
    "README.md",
}

ALLOWED_CODE_CLASSIFICATIONS = {
    "EXACT",
    "ALGEBRAICALLY_EQUIVALENT",
    "NUMERICAL_APPROXIMATION",
    "PARTIAL",
    "ABSENT",
    "NOT_APPLICABLE",
}

MANDATED_OPERATIONS = {
    "state_group_representation",
    "SO3_exponential",
    "SEK3_exponential",
    "group_logarithm",
    "SEK3_adjoint",
    "orientation_mean_propagation",
    "velocity_and_position_mean_propagation",
    "bias_subtraction",
    "bias_free_continuous_invariant_error_dynamics",
    "bias_augmented_continuous_error_dynamics",
    "continuous_process_noise_mapping",
    "state_transition_discretization",
    "discrete_process_noise",
    "forward_kinematic_point_contact_observation",
    "invariant_innovation",
    "kalman_gain",
    "state_and_bias_correction",
    "covariance_correction",
    "contact_state_augmentation",
    "contact_state_removal",
    "bias_random_walk",
}

# The H0--H2 terminal report recorded a 46-file payload. Later authorized
# phases extend the same stage root, so protect that historical file set as an
# immutable required subset instead of asserting that the live payload can
# never contain more than 46 files.
HISTORICAL_H0_H2_REQUIRED_DOC_FILES = {
    "00_SOURCE_REGISTRY/OFFICIAL_CODE_REGISTRY.csv",
    "00_SOURCE_REGISTRY/OFFICIAL_SOURCE_HASHES.sha256",
    "00_SOURCE_REGISTRY/PAPER_SOURCE_REGISTRY.csv",
    "01_PAPER_REVIEW/HARTLEY_ALGORITHM_FLOW.md",
    "01_PAPER_REVIEW/HARTLEY_EQUATION_REGISTRY.csv",
    "01_PAPER_REVIEW/HARTLEY_FULL_METHOD_CARD.md",
    "01_PAPER_REVIEW/HARTLEY_IDEAL_OBSERVABILITY_DERIVATION.md",
    "01_PAPER_REVIEW/HARTLEY_OBSERVABILITY_CONTRACT.md",
    "01_PAPER_REVIEW/HARTLEY_PARAMETER_REGISTRY.csv",
    "01_PAPER_REVIEW/PAPER_VISUAL_REVIEW_LEDGER.csv",
    "02_OFFICIAL_CODE_AUDIT/HARTLEY_CODE_GAP_REGISTRY.csv",
    "02_OFFICIAL_CODE_AUDIT/HARTLEY_EQUATION_TO_CODE_MAP.csv",
    "02_OFFICIAL_CODE_AUDIT/HARTLEY_OFFICIAL_CODE_AUDIT.md",
    "03_BY2_INPUT_AUDIT/BY2_COMPLETE_RECORD_PREFIX_MANIFEST.json",
    "03_BY2_INPUT_AUDIT/BY2_FIELD_ROLE_REGISTRY.csv",
    "03_BY2_INPUT_AUDIT/BY2_FRAME_AUDIT.md",
    "03_BY2_INPUT_AUDIT/BY2_INPUT_AUDIT.md",
    "03_BY2_INPUT_AUDIT/BY2_PROJECTION_AUDIT_SUMMARY.json",
    "03_BY2_INPUT_AUDIT/BY2_TRAILING_RECORD_LEDGER.json",
    "03_BY2_INPUT_AUDIT/CONTACT_AUDIT_REPORT.md",
    "03_BY2_INPUT_AUDIT/CONTACT_FORCE_DISTRIBUTIONS.csv",
    "03_BY2_INPUT_AUDIT/CONTACT_INPUT_AUDIT.json",
    "03_BY2_INPUT_AUDIT/CONTACT_SPEED_DISTRIBUTIONS.csv",
    "03_BY2_INPUT_AUDIT/CONTACT_THRESHOLD_PROPOSAL.yaml",
    "03_BY2_INPUT_AUDIT/CONTACT_TRANSITION_AUDIT.csv",
    "03_BY2_INPUT_AUDIT/EOF_GAP_EVIDENCE.json",
    "03_BY2_INPUT_AUDIT/FK_PROXY_AUDIT.csv",
    "03_BY2_INPUT_AUDIT/FK_PROXY_AUDIT.json",
    "03_BY2_INPUT_AUDIT/FK_PROXY_COVARIANCE_ESTIMATION.csv",
    "03_BY2_INPUT_AUDIT/FK_PROXY_COVARIANCE_SUMMARY.json",
    "05_OFFICIAL_EXAMPLE_RESULTS/OFFICIAL_BUILD_REPORT.md",
    "05_OFFICIAL_EXAMPLE_RESULTS/OFFICIAL_EXAMPLE_EVENT_LEDGER.csv",
    "05_OFFICIAL_EXAMPLE_RESULTS/OFFICIAL_KINEMATICS_EXAMPLE_SUMMARY.json",
    "05_OFFICIAL_EXAMPLE_RESULTS/OFFICIAL_LANDMARK_EXAMPLE_SUMMARY.json",
    "11_REPORT/LSE01_H0_H2_REPORT.md",
    "11_REPORT/LSE01_H0_H2_STATUS.json",
}

HISTORICAL_H0_H2_REQUIRED_CONFIG_FILES = {
    "04_METHOD_CONTRACTS/BY2_FK_PROXY_CONTRACT.yaml",
    "04_METHOD_CONTRACTS/GO2_FOOT_ORDER_CONTRACT.yaml",
    "04_METHOD_CONTRACTS/HARTLEY_CONTACT_LIFECYCLE_CONTRACT.yaml",
    "04_METHOD_CONTRACTS/HARTLEY_FRAME_CONTRACT.yaml",
    "04_METHOD_CONTRACTS/HARTLEY_GAUGE_ENSEMBLE_CONTRACT.yaml",
    "04_METHOD_CONTRACTS/HARTLEY_METHOD_CONTRACT.yaml",
    "04_METHOD_CONTRACTS/HARTLEY_NUMERICAL_OBSERVABILITY_CONTRACT.yaml",
    "04_METHOD_CONTRACTS/HARTLEY_OBSERVABILITY_CONTRACT.yaml",
    "04_METHOD_CONTRACTS/HARTLEY_PARAMETER_SOURCE_REGISTRY.csv",
    "04_METHOD_CONTRACTS/HARTLEY_STATE_AND_FRAME_CONTRACT.yaml",
}


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def _source_hash_entries() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    manifest = SOURCE_REGISTRY / "OFFICIAL_SOURCE_HASHES.sha256"
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (\S.*)", line)
        assert match is not None, f"malformed SHA-256 manifest line: {line!r}"
        entries.append((match.group(1), match.group(2)))
    return entries


def test_exact_primary_paper_identities_and_consolidated_hash_manifest() -> None:
    rows = _csv_rows(SOURCE_REGISTRY / "PAPER_SOURCE_REGISTRY.csv")
    assert {row["source_id"] for row in rows} == set(EXPECTED_PAPERS)

    entries = _source_hash_entries()
    for row in rows:
        expected = EXPECTED_PAPERS[row["source_id"]]
        for field in ("doi", "arxiv_id", "version", "page_count", "sha256"):
            assert row[field] == expected[field]
        assert any(
            digest == expected["sha256"] and path.endswith(expected["filename"])
            for digest, path in entries
        ), f"paper absent from consolidated source hashes: {row['source_id']}"

    cpp_prefix = (
        "RossHartley/invariant-ekf@"
        "ef16e8a1df72f9272111a488880e3fe9d161f59f/"
    )
    hashed_cpp_files = {
        path.removeprefix(cpp_prefix)
        for _, path in entries
        if path.startswith(cpp_prefix)
    }
    assert MANDATED_CPP_FILES <= hashed_cpp_files


def test_exact_official_repository_pins_licenses_and_clean_declared_states() -> None:
    rows = _csv_rows(SOURCE_REGISTRY / "OFFICIAL_CODE_REGISTRY.csv")
    by_id = {row["source_id"]: row for row in rows}
    assert set(by_id) == set(EXPECTED_REPOSITORIES)
    for source_id, commit in EXPECTED_REPOSITORIES.items():
        row = by_id[source_id]
        assert row["commit"] == commit
        assert row["license"] == "BSD-3-Clause"
        assert row["checkout_status"] == "DETACHED_EXACT_COMMIT"
        assert row["source_status"] == "CLEAN"
        assert row["local_patch"] == "NO_LOCAL_PATCH"
        assert row["tracked_or_vendored"] == "false"


def test_equation_map_is_closed_over_required_operations_and_gap_classes() -> None:
    rows = _csv_rows(CODE_AUDIT / "HARTLEY_EQUATION_TO_CODE_MAP.csv")
    by_operation = {row["algorithmic_operation"]: row for row in rows}
    assert set(by_operation) >= MANDATED_OPERATIONS
    assert {row["classification"] for row in rows} <= ALLOWED_CODE_CLASSIFICATIONS

    for operation in (
        "velocity_and_position_mean_propagation",
        "state_transition_discretization",
        "discrete_process_noise",
    ):
        assert by_operation[operation]["classification"] == "NUMERICAL_APPROXIMATION"

    gaps = {
        row["gap_title"]: row
        for row in _csv_rows(CODE_AUDIT / "HARTLEY_CODE_GAP_REGISTRY.csv")
    }
    for gap in (
        "mean_velocity_position_discretization",
        "state_transition_discretization",
        "discrete_process_noise_mapping",
    ):
        assert gaps[gap]["classification"] == "NUMERICAL_APPROXIMATION"
        assert gaps[gap]["required_future_implementation"]
        assert gaps[gap]["required_future_tests"]

    paper_registry = {
        row["operation"]: row
        for row in _csv_rows(
            DOC_PAYLOAD / "01_PAPER_REVIEW/HARTLEY_EQUATION_REGISTRY.csv"
        )
    }
    official_discretization = paper_registry["official_discretization_behavior"]
    assert official_discretization["source_type"] == "OFFICIAL_CODE"
    assert "CURRENTLY_UNKNOWN" not in " ".join(official_discretization.values())


def test_method_state_process_update_and_contact_lifecycle_identity() -> None:
    method = _yaml(CONTRACTS / "HARTLEY_METHOD_CONTRACT.yaml")
    identity = method["reproduction_identity"]
    assert method["contract_id"] == "LSE01_HARTLEY_CONTACT_AIDED_INEKF"
    assert identity["algorithm_core"] == "FAITHFUL_ALGORITHM_REPRODUCTION"
    assert identity["by2_adaptation"] == "WITH_DECLARED_GO2_HIGH_LEVEL_FK_PROXY"
    assert identity["selected_formulation"] == {
        "navigation_frame": "WORLD_CENTRIC",
        "error_definition": "RIGHT_INVARIANT",
        "aiding": "POINT_CONTACT_FORWARD_KINEMATICS",
        "imu_biases": "ESTIMATED_EUCLIDEAN_AUGMENTATION",
        "contact_set": "SWITCHING_MULTI_POINT_CONTACTS",
    }

    state = method["state"]
    assert state["group"] == "SE_N_PLUS_2_3"
    assert state["group_elements"] == [
        "R_WB",
        "v_WB",
        "p_WB",
        "d_WC_i_FOR_EACH_CURRENT_CONTACT",
    ]
    assert state["euclidean_augmentation"] == ["b_g", "b_a"]
    assert state["covariance_dimension"] == "15_plus_3N"

    process = method["continuous_process"]
    assert set(process["equations"]) == {
        "R_dot", "v_dot", "p_dot", "d_i_dot", "b_g_dot", "b_a_dot"
    }
    assert process["deterministic_contact_position"] == "CONSTANT_WHILE_ACTIVE"
    assert process["contact_motion_noise"] == "BROWNIAN_POINT_CONTACT_VELOCITY"
    assert "RICCATI" in process["covariance"]

    measurement = method["contact_measurement"]
    assert measurement["form"] == "RIGHT_INVARIANT_FORWARD_KINEMATIC_POINT_CONTACT"
    assert measurement["active_contact_policy"] == "STACK_ALL_ACTIVE_CONTACTS"
    assert measurement["covariance_correction"] == "JOSEPH_FORM_EQ_29"

    lifecycle = _yaml(CONTRACTS / "HARTLEY_CONTACT_LIFECYCLE_CONTRACT.yaml")
    assert lifecycle["contact_model"]["type"] == "DISCRETE_SWITCHING_POINT_CONTACT"
    assert lifecycle["on_contact_add"]["reference"] == "IJRR_EQS_31_32"
    assert lifecycle["on_contact_add"]["preserve_cross_covariance"] is True
    assert lifecycle["while_contact_active"]["multi_contact_update"] == "STACK_ALL_ACTIVE_CONTACTS"
    assert lifecycle["on_contact_remove"]["reference"] == "IJRR_EQ_30"
    assert lifecycle["on_contact_remove"]["covariance_action"] == "P_new_equals_M_i_P_M_i_transpose"

    code_status = method["discretization_target"]["official_code_status"]
    assert code_status["source_type"] == "OFFICIAL_CODE"
    assert "CURRENTLY_UNKNOWN" not in str(code_status)


def test_parameter_sources_have_no_trace_tuning_or_stale_official_code_unknown() -> None:
    rows = _csv_rows(CONTRACTS / "HARTLEY_PARAMETER_SOURCE_REGISTRY.csv")
    assert rows
    assert all(row["trace_tuned"].lower() == "false" for row in rows)

    by_parameter = {row["parameter"]: row for row in rows}
    official = by_parameter["official_example_noise_defaults"]
    assert official["source_type"] == "OFFICIAL_CODE"
    assert official["used_in_official_example"].lower() == "true"
    assert "CURRENTLY_UNKNOWN" not in " ".join(official.values())

    official_rows = [row for row in rows if row["source_type"] == "OFFICIAL_CODE"]
    assert official_rows
    assert all("CURRENTLY_UNKNOWN" not in " ".join(row.values()) for row in official_rows)


def test_by2_foot_order_frame_and_fk_proxy_contracts_are_prefix_ready_without_run() -> None:
    feet = _yaml(CONTRACTS / "GO2_FOOT_ORDER_CONTRACT.yaml")
    assert feet["contract_status"] == (
        "CLOSED_THREE_WAY_AGREEMENT_REAL_BY2_COMPLETE_RECORD_PREFIX"
    )
    assert feet["data_identity"] == "REAL_BY2_COMPLETE_RECORD_PREFIX_63277"
    assert feet["raw_source_complete"] is False
    assert feet["complete_record_prefix_filter_eligible"] is True
    assert feet["native_source_order"]["labels"] == ["FR", "FL", "RR", "RL"]
    assert feet["canonical_method_order"] == ["FL", "FR", "RL", "RR"]
    assert feet["native_to_canonical_mapping"] == [1, 0, 3, 2]
    assert all(feet["source_agreement"]["hash_locked_by2_geometry"][key] is True for key in (
        "front_x_positive", "rear_x_negative", "right_y_negative", "left_y_positive"
    ))
    assert feet["filter_run_executed"] is False

    frame = _yaml(CONTRACTS / "HARTLEY_FRAME_CONTRACT.yaml")
    mapping = frame["by2_imu_mapping"]
    assert mapping["frozen_imu_install_rpy_deg"] == [-1.0, 0.0, 0.0]
    assert mapping["direction"] == "SENSOR_TO_BODY_ACTIVE_RZ_RY_RX"
    assert mapping["inverse_interpretation_selected"] is False
    checks = frame["proper_rotation_tests"]
    assert checks["determinant_plus_one"] is True
    assert checks["right_handed"] is True
    assert checks["round_trip_error_fro"] == 0.0
    assert checks["known_axis_sign_pass"] is True
    assert frame["input_only_stationary_sanity"]["selected_candidate_has_lower_residual"] is True
    assert frame["quaternion_opened"] is False
    assert frame["rpy_opened"] is False
    assert frame["reference_trace_opened"] is False
    assert frame["filter_run_executed"] is False
    assert frame["data_identity"] == "REAL_BY2_COMPLETE_RECORD_PREFIX_63277"
    assert frame["raw_source_complete"] is False
    assert frame["complete_record_prefix_filter_eligible"] is True

    proxy = _yaml(CONTRACTS / "BY2_FK_PROXY_CONTRACT.yaml")
    assert proxy["fk_proxy"]["raw_joint_encoder_urdf_fk"] is False
    assert proxy["fk_proxy"]["truth_role"] is False
    assert proxy["contact_detector_input_only_proposal"]["decision_signal"] == "foot_force"
    assert proxy["contact_detector_input_only_proposal"]["policy_id"] == (
        "FROZEN_BY2_INPUT_ONLY_CONTACT_POLICY"
    )
    assert proxy["diagnostics"]["foot_speed_body_role"] == "DIAGNOSTIC_ONLY"
    assert proxy["diagnostics"]["foot_speed_online_allowed"] is False
    assert proxy["diagnostics"]["foot_speed_changes_threshold_or_contact_state"] is False
    assert proxy["fk_proxy"]["translation_covariance_policy"] == (
        "FROZEN_BY2_INPUT_ONLY_FK_PROXY_COVARIANCE"
    )
    gate = proxy["complete_record_prefix_gate"]
    assert gate["terminal_status"] == (
        "PASS_LSE01_H0_H2_HARTLEY_SOURCE_METHOD_AND_BY2_CONTRACT_READY"
    )
    assert gate["complete_record_count"] == 63277
    assert gate["timestamped_record_starts"] == 63278
    assert gate["trailing_incomplete_record_count"] == 1
    assert gate["trailing_record_used_online"] is False
    assert gate["filter_run_executed"] is False


def test_by2_stage_payload_freezes_exact_complete_prefix_and_trailing_record() -> None:
    audit = DOC_PAYLOAD / "03_BY2_INPUT_AUDIT"
    summary = _json(audit / "BY2_PROJECTION_AUDIT_SUMMARY.json")
    eof = _json(audit / "EOF_GAP_EVIDENCE.json")
    prefix = _json(audit / "BY2_COMPLETE_RECORD_PREFIX_MANIFEST.json")
    tail = _json(audit / "BY2_TRAILING_RECORD_LEDGER.json")
    assert summary["terminal_status"] == (
        "PASS_LSE01_H0_H2_HARTLEY_SOURCE_METHOD_AND_BY2_CONTRACT_READY"
    )
    assert summary["data_identity"] == "REAL_BY2_COMPLETE_RECORD_PREFIX_63277"
    assert summary["data_status"] == "REAL_BY2_COMPLETE_RECORD_PREFIX"
    assert summary["data_mode"] == "real_by2_raw"
    assert summary["complete_record_count"] == 63277
    assert summary["timestamped_record_starts"] == 63278
    assert summary["raw_source_complete"] is False
    assert summary["complete_record_prefix_filter_eligible"] is True
    assert summary["trailing_incomplete_record_count"] == 1
    assert summary["trailing_record_used_online"] is False
    assert summary["canonical_audit_published"] is True
    assert summary["canonical_input_audit_ready"] is True
    assert summary["filter_run_executed"] is False
    for field in (
        "synthetic_data_used", "semisynthetic_data_used", "trace_used_online",
        "receiver_imu_as_body_imu", "final_v23_output_solver_input",
        "LegSA_output_solver_input", "per_case_tuning", "output_only_correction",
        "epoch_deleted_for_metric",
    ):
        assert summary[field] is False
    assert summary["old_runtime_input_count"] == 0
    assert summary["uncommitted_input_audit"] is False
    assert summary["code_base_commit"] == "70dcaa4010826e156feebe213c69c3cb187a7c03"
    assert re.fullmatch(r"[0-9a-f]{64}", summary["local_paths_config_hash"])

    assert prefix["data_identity"] == "REAL_BY2_COMPLETE_RECORD_PREFIX_63277"
    assert prefix["raw_source_sha256"] == (
        "95859de46925416f0a094f8986ef4f8cb452cab71b264702705a9f9aff95a278"
    )
    assert prefix["raw_source_size"] == 92352512
    assert prefix["raw_source_line_count"] == 4682569
    assert prefix["raw_crlf_count"] == 4682568
    assert prefix["raw_bare_lf_count"] == 1
    assert prefix["complete_record_count"] == 63277
    assert prefix["physical_record_start_count"] == 63278
    assert prefix["trailing_incomplete_record_count"] == 1
    assert prefix["complete_prefix_end_byte_offset"] == 92351234
    assert set(prefix["mandatory_field_shapes"]) == {
        "stamp.sec", "stamp.nanosec", "imu_state.gyroscope",
        "imu_state.accelerometer", "foot_force", "foot_position_body",
        "foot_speed_body",
    }
    assert prefix["audit_required_field_shapes"] == {"gait_type": 1}
    assert prefix["complete_prefix_sha256"] == (
        "03cd96cd65d7f5af30f6a0c78d37f07ae4d32c65e78531807db7192454dff097"
    )
    assert prefix["first_complete_timestamp"] == {
        "sec": 1772784044, "nanosec": 887078145, "ns": 1772784044887078145,
    }
    assert prefix["last_complete_timestamp"] == {
        "sec": 1772784350, "nanosec": 85048802, "ns": 1772784350085048802,
    }
    assert prefix["complete_prefix_duration_ns"] == 305197970657
    assert prefix["complete_prefix_duration"] == 305.197970657
    assert prefix["raw_source_complete"] is False
    assert prefix["complete_record_prefix_filter_eligible"] is True
    assert prefix["imputation_used"] is False
    assert prefix["interpolation_used"] is False
    assert prefix["raw_source_mutated"] is False

    assert tail["record_index"] == 63278
    assert tail["tail_start_byte"] == 92351234
    assert tail["tail_end_byte_exclusive"] == 92352512
    assert tail["tail_bytes"] == 1278
    assert tail["tail_sha256"] == (
        "b9489cc1de96a7115de858e853389b8cf43e5245dcf57dd6b5ce99c573d7a30b"
    )
    assert tail["start_line"] == 4682505
    assert tail["end_line"] == 4682569
    assert tail["timestamp_ns"] == 1772784350091049397
    assert tail["values"]["foot_speed_body_present_count"] == 4
    assert tail["values"]["foot_speed_body_missing_count"] == 8
    assert tail["primary_field_defects"] == ["foot_speed_body"]
    assert tail["audit_required_field_defects"] == []
    assert tail["trailing_record_used_online"] is False
    assert tail["imputation_used"] is False
    assert tail["interpolation_used"] is False
    assert tail["raw_mutated"] is False
    assert eof["projected_timestamp_count"] == 63278
    assert eof["complete_projected_messages"] == 63277
    assert eof["final_record_foot_speed_body_present_values"] == 4
    assert eof["missing_foot_speed_body_values"] == 8
    assert eof["parser_bug"] is False

    roles = _csv_rows(audit / "BY2_FIELD_ROLE_REGISTRY.csv")
    assert list(roles[0]) == [
        "field", "present", "shape", "unit", "rate", "role", "online_allowed", "reason"
    ]
    speed = next(row for row in roles if row["field"] == "foot_speed_body")
    assert speed["shape"] == "[63277,12]+final[4/12]"
    assert speed["present"] == "partial"
    assert speed["online_allowed"] == "false"
    required_forbidden = {
        "imu_state.quaternion", "imu_state.rpy", "position", "velocity", "yaw_speed",
        "GNSS", "Fixposition_trace", "A1_status_heading", "LegSA_output",
        "EXT01_output", "EXT02_output", "EXT03_output", "EXT04_output", "EXT05_output",
    }
    by_field = {row["field"]: row for row in roles}
    assert required_forbidden <= set(by_field)
    assert all(by_field[field]["online_allowed"] == "false" for field in required_forbidden)
    assert all(by_field[field]["present"] == "true" for field in (
        "imu_state.quaternion", "imu_state.rpy", "position", "velocity", "yaw_speed"
    ))
    assert all(by_field[field]["present"] == "false" for field in (
        "GNSS", "Fixposition_trace", "A1_status_heading", "LegSA_output",
        "EXT01_output", "EXT02_output", "EXT03_output", "EXT04_output", "EXT05_output",
    ))


def test_ready_prefix_payload_retains_distributions_contact_and_fk_evidence() -> None:
    audit = DOC_PAYLOAD / "03_BY2_INPUT_AUDIT"
    force = _csv_rows(audit / "CONTACT_FORCE_DISTRIBUTIONS.csv")
    assert {row["row_type"] for row in force} == {"quantiles", "histogram"}
    assert len([row for row in force if row["row_type"] == "histogram"]) == 128
    speed = _csv_rows(audit / "CONTACT_SPEED_DISTRIBUTIONS.csv")
    assert {row["force_contact_state"] for row in speed} == {
        "overall", "contact", "no_contact"
    }
    assert {row["row_type"] for row in speed} == {"quantiles", "histogram"}
    transitions = _csv_rows(audit / "CONTACT_TRANSITION_AUDIT.csv")
    assert {"per_leg_summary", "transition", "dwell"} <= {
        row["row_type"] for row in transitions
    }
    assert all("dwell_p50" in row for row in transitions)
    fk = _csv_rows(audit / "FK_PROXY_AUDIT.csv")
    assert len(fk) == 12
    for required in (
        "position_minimum", "position_p50", "position_maximum", "speed_minimum",
        "speed_p50", "speed_maximum", "force_contact_position_std",
        "force_no_contact_position_std", "candidate_discontinuity_count",
        "time_alignment_contract",
    ):
        assert required in fk[0]
    contact_json = _json(audit / "CONTACT_INPUT_AUDIT.json")
    assert set(contact_json["per_leg"]) == {"FR", "FL", "RR", "RL"}
    fk_json = _json(audit / "FK_PROXY_AUDIT.json")
    assert set(fk_json["median_position_body_by_native_leg_m"]) == {
        "FR", "FL", "RR", "RL"
    }
    assert contact_json["canonical_filter_eligible"] is True
    assert contact_json["status"] == "FROZEN_BY2_INPUT_ONLY_CONTACT_POLICY"
    assert contact_json["foot_speed_role"] == "DIAGNOSTIC_ONLY"
    assert contact_json["foot_speed_online_allowed"] is False
    assert contact_json["foot_speed_changes_threshold_or_state_classification"] is False
    for leg in contact_json["per_leg"].values():
        assert "diagnostic_no_contact_median_speed_greater_than_contact" in leg
        assert "diagnostic_no_contact_median_speed_greater_than_contact" not in leg[
            "force_only_stability_criteria"
        ]
        assert all(leg["force_only_stability_criteria"].values())
    assert fk_json["canonical_filter_eligible"] is True
    assert fk_json["translation_covariance_policy"] == (
        "FROZEN_BY2_INPUT_ONLY_FK_PROXY_COVARIANCE"
    )
    assert (audit / "CONTACT_AUDIT_REPORT.md").is_file()


def test_generated_fk_covariance_is_exact_frozen_input_only_policy() -> None:
    audit = DOC_PAYLOAD / "03_BY2_INPUT_AUDIT"
    covariance = _json(audit / "FK_PROXY_COVARIANCE_SUMMARY.json")
    rows = _csv_rows(audit / "FK_PROXY_COVARIANCE_ESTIMATION.csv")
    assert len(rows) == 12
    assert covariance["status"] == "FROZEN_BY2_INPUT_ONLY_FK_PROXY_COVARIANCE"
    assert covariance["filter_eligible"] is True
    assert covariance["all_legs_well_conditioned"] is True
    assert covariance["fallback_applied"] is False
    assert covariance["floor_dominates_all_raw_leg_covariances"] is True
    assert covariance["eigenvalue_floor_m2"] == 1.0e-8
    assert covariance["primary_scale"] == 1.0
    assert covariance["sensitivity_scales"] == [0.25, 1.0, 4.0]
    assert covariance["reference_tuned"] is False
    assert covariance["output_metric_tuned"] is False
    assert covariance["eligibility"] == {
        "both_k_minus_1_and_k_contact": True,
        "gyro_norm_strictly_below_radps": 0.05,
        "absolute_accel_norm_minus_9p81_at_most_mps2": 0.5,
        "positive_finite_dt_required": True,
        "finite_position_velocity_required": True,
    }
    policy = covariance["contact_policy"]
    assert policy["decision_signal"] == "foot_force_only"
    assert policy["off_thresholds"] == [24.8, 25.2, 23.4, 24.0]
    assert policy["on_thresholds"] == [34.2, 33.8, 30.6, 32.0]
    assert policy["minimum_dwell_samples"] == 3
    assert policy["minimum_dwell_seconds"] == 0.012035608291625977
    assert policy["transition_event_count"] == 4706
    expected_counts = {"FR": 4285, "FL": 4287, "RR": 4298, "RL": 4302}
    for leg, count in expected_counts.items():
        result = covariance["per_leg"][leg]
        assert result["residual_count"] == count
        assert result["fallback_applied"] is False
        assert result["well_conditioned"] is True
        assert np.allclose(result["selected_covariance_m2"], np.eye(3) * 1.0e-8, atol=1.0e-22)
        assert np.allclose(result["final_eigenvalues_m2"], [1.0e-8] * 3, atol=0.0)
        assert max(result["raw_symmetric_eigenvalues_m2"]) < 1.0e-8


def test_reconciled_method_frame_lifecycle_and_parameters_are_contract_ready() -> None:
    method = _yaml(CONTRACTS / "HARTLEY_METHOD_CONTRACT.yaml")
    proxy = method["by2_proxy_boundary"]
    assert proxy["proxy_frame"]["native_to_canonical_mapping"] == [1, 0, 3, 2]
    assert proxy["proxy_translation_covariance"]["value"] == (
        "FROZEN_BY2_INPUT_ONLY_FK_PROXY_COVARIANCE"
    )
    assert proxy["proxy_translation_covariance"]["filter_eligible"] is True
    assert proxy["contact_thresholds"]["policy_id"] == (
        "FROZEN_BY2_INPUT_ONLY_CONTACT_POLICY"
    )
    assert proxy["contact_thresholds"]["filter_eligible"] is True
    assert proxy["contact_thresholds"]["foot_speed_role"] == "DIAGNOSTIC_ONLY"
    frame = _yaml(CONTRACTS / "HARTLEY_STATE_AND_FRAME_CONTRACT.yaml")
    platform = frame["platform_mapping_boundary"]
    assert platform["raw_imu_sensor_to_robot_body"]["failure_token"] == (
        "BLOCKED_LSE01_SENSOR_TO_BODY_FRAME_UNRESOLVED"
    )
    assert platform["data_identity"] == "REAL_BY2_COMPLETE_RECORD_PREFIX_63277"
    assert platform["raw_source_complete"] is False
    assert platform["complete_record_prefix_filter_eligible"] is True
    assert platform["robot_body_to_hartley_body"][
        "foot_position_body_receives_imu_installation_rotation"
    ] is False
    assert platform["hartley_world_to_project_ned_reporting"]["absolute_north_observed"] is False
    assert platform["imu_install_minus_1_0_0_deg_direction"][
        "gravity_aligned_cancellation_residual_norm_mps2"
    ] < 1.0e-12
    lifecycle = _yaml(CONTRACTS / "HARTLEY_CONTACT_LIFECYCLE_CONTRACT.yaml")
    detector = lifecycle["detector_boundary"]
    assert detector["by2_force_hysteresis_thresholds"]["policy_id"] == (
        "FROZEN_BY2_INPUT_ONLY_CONTACT_POLICY"
    )
    assert detector["minimum_dwell"]["filter_eligible"] is True
    assert detector["complete_record_prefix_filter_eligible"] is True
    assert detector["trailing_record_used_online"] is False
    parameters = {
        row["parameter"]: row for row in _csv_rows(
            CONTRACTS / "HARTLEY_PARAMETER_SOURCE_REGISTRY.csv"
        )
    }
    assert parameters["go2_fk_proxy_translation_covariance"]["value"] == (
        "FROZEN_BY2_INPUT_ONLY_FK_PROXY_COVARIANCE"
    )
    assert parameters["go2_fk_proxy_translation_covariance"]["proposed_for_BY2"] == "true"
    assert parameters["go2_fk_proxy_translation_covariance_primary_scale"]["value"] == "1.0"
    assert parameters["go2_fk_proxy_translation_covariance_sensitivity_scales"]["value"] == (
        "[0.25,1.0,4.0]"
    )
    assert parameters["go2_fk_proxy_translation_covariance_primary_scale"]["trace_tuned"] == (
        "false"
    )
    assert parameters["go2_fk_proxy_translation_covariance_sensitivity_scales"]["trace_tuned"] == (
        "false"
    )
    assert parameters["go2_contact_force_on_threshold"]["source_type"] == (
        "BY2_PHYSICAL_INSTANTIATION"
    )
    assert parameters["go2_contact_force_on_threshold"]["paper_or_code_identity"] == (
        "FROZEN_BY2_INPUT_ONLY_CONTACT_POLICY"
    )
    allowed_source_types = {
        "PAPER_DIRECT", "PAPER_DERIVED", "OFFICIAL_CODE",
        "BY2_PHYSICAL_INSTANTIATION", "CURRENTLY_UNKNOWN",
    }
    assert {row["source_type"] for row in parameters.values()} <= allowed_source_types

    paper_rows = _csv_rows(
        DOC_PAYLOAD / "01_PAPER_REVIEW/HARTLEY_PARAMETER_REGISTRY.csv"
    )
    assert all(row["trace_tuned"].lower() == "false" for row in paper_rows)
    paper_official = {
        row["parameter"]: row for row in paper_rows
    }["official_example_noise_defaults"]
    assert paper_official["source_type"] == "OFFICIAL_CODE"
    assert "CURRENTLY_UNKNOWN" not in " ".join(paper_official.values())


@pytest.mark.parametrize(
    "filename",
    [
        "OFFICIAL_KINEMATICS_EXAMPLE_SUMMARY.json",
        "OFFICIAL_LANDMARK_EXAMPLE_SUMMARY.json",
    ],
)
def test_official_example_summaries_are_rc0_finite_symmetric_and_psd(filename: str) -> None:
    summary = _json(EXAMPLE_RESULTS / filename)
    assert summary["commit"] == EXPECTED_REPOSITORIES["HARTLEY_CPP_PRIMARY"]
    assert summary["local_patch"] is False
    assert summary["official_execution"]["return_code"] == 0
    diagnostics = summary["diagnostics"]
    assert diagnostics["finite_state"] is True
    assert diagnostics["finite_covariance"] is True
    assert diagnostics["covariance_symmetric_within_tolerance"] is True
    assert diagnostics["covariance_psd_with_tolerance"] is True
    assert diagnostics["covariance_max_abs_asymmetry"] <= diagnostics["covariance_symmetry_tolerance"]
    assert diagnostics["covariance_min_eigenvalue_symmetrized"] >= -diagnostics["covariance_symmetry_tolerance"]


def test_official_kinematics_lifecycle_and_landmark_parser_limitation() -> None:
    kinematics = _json(EXAMPLE_RESULTS / "OFFICIAL_KINEMATICS_EXAMPLE_SUMMARY.json")
    events = kinematics["event_counts"]
    assert events["contact_add_count"] > 0
    assert events["contact_remove_count"] > 0
    assert events["kinematic_correction_calls"] > 0
    assert events["kinematic_correction_measurements"] > 0
    active = events["final_active_contact_count"]
    dimensions = kinematics["final_state_dimensions"]
    assert dimensions["X_rows"] == dimensions["X_cols"] == 5 + active
    assert dimensions["theta_rows"] == 6
    assert dimensions["P_rows"] == dimensions["P_cols"] == 15 + 3 * active

    landmarks = _json(EXAMPLE_RESULTS / "OFFICIAL_LANDMARK_EXAMPLE_SUMMARY.json")
    assert landmarks["event_counts"]["propagation_calls"] == 0
    limitation = landmarks["upstream_parser_limitation"]
    assert limitation["present"] is True
    assert "atoi" in limitation["evidence"]
    assert "not IMU propagation" in limitation["interpretation"]


def _skew(vector: np.ndarray) -> np.ndarray:
    x, y, z = vector
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def _ideal_constant_contact_window(
    contact_count: int, times: tuple[float, ...]
) -> tuple[np.ndarray, np.ndarray, list[np.ndarray], np.ndarray]:
    """Construct one constant-contact-set ideal Hartley observability window."""
    assert 1 <= contact_count <= 4
    assert len(set(times)) >= 3
    dimension = 9 + 3 * contact_count
    gravity = np.array([0.0, 0.0, -9.81])

    # Contract ordering: [xi_R, xi_v, xi_p, xi_d_1, ..., xi_d_N].
    A = np.zeros((dimension, dimension))
    A[3:6, 0:3] = _skew(gravity)
    A[6:9, 3:6] = np.eye(3)
    assert np.allclose(A @ A @ A, 0.0)

    H = np.zeros((3 * contact_count, dimension))
    for contact in range(contact_count):
        rows = slice(3 * contact, 3 * contact + 3)
        H[rows, 6:9] = -np.eye(3)
        H[rows, 9 + 3 * contact : 12 + 3 * contact] = np.eye(3)

    transitions = [
        np.eye(dimension) + A * time + 0.5 * (A @ A) * time**2
        for time in times
    ]
    observability = np.vstack([H @ transition for transition in transitions])
    return A, H, transitions, observability


@pytest.mark.parametrize("contact_count", [1, 2, 3, 4])
def test_independent_ideal_bias_free_observability_has_exact_four_gauges(
    contact_count: int,
) -> None:
    times = (0.0, 0.013, 0.071, 0.19)
    A, H, transitions, observability = _ideal_constant_contact_window(
        contact_count, times
    )
    dimension = 9 + 3 * contact_count

    assert A.shape == (dimension, dimension)
    assert H.shape == (3 * contact_count, dimension)
    assert all(transition.shape == (dimension, dimension) for transition in transitions)
    assert observability.shape == (len(times) * 3 * contact_count, dimension)
    assert np.linalg.matrix_rank(observability, tol=1.0e-10) == 5 + 3 * contact_count
    assert dimension - np.linalg.matrix_rank(observability, tol=1.0e-10) == 4

    gauge = np.zeros((dimension, 4))
    gauge[0:3, 0] = np.array([0.0, 0.0, -1.0])  # gravity-axis yaw
    for axis in range(3):
        gauge[6 + axis, 1 + axis] = 1.0
        for contact in range(contact_count):
            gauge[9 + 3 * contact + axis, 1 + axis] = 1.0
    assert np.linalg.matrix_rank(gauge) == 4
    assert np.linalg.norm(observability @ gauge, ord="fro") <= 1.0e-12

    # This window never crosses contact augmentation/removal: one N, one H shape,
    # and one state dimension are retained at every measurement time.
    assert len({transition.shape for transition in transitions}) == 1


def test_observability_and_gauge_contracts_forbid_boundary_stacking_and_execution() -> None:
    ideal = _yaml(CONTRACTS / "HARTLEY_OBSERVABILITY_CONTRACT.yaml")
    numerical = _yaml(CONTRACTS / "HARTLEY_NUMERICAL_OBSERVABILITY_CONTRACT.yaml")
    gauge = _yaml(CONTRACTS / "HARTLEY_GAUGE_ENSEMBLE_CONTRACT.yaml")

    assert ideal["known_gauge"]["total_nullity"] == 4
    assert ideal["known_gauge"]["translation_nullity"] == 3
    assert ideal["known_gauge"]["gravity_axis_rotation_nullity"] == 1
    assert ideal["known_gauge"]["expected_generic_rank_N_contacts"] == "5_plus_3N"
    assert ideal["exact_statement"] == "GLOBAL_POSITION_AND_ROTATION_ABOUT_GRAVITY_ARE_UNOBSERVABLE"
    assert ideal["contact_boundary_rule"]["stack_across_state_dimension_change_without_map"] is False

    window = numerical["window_contract"]
    assert window["constant_state_dimension"] is True
    assert window["constant_contact_id_set"] is True
    assert window["cross_contact_add_remove_boundary"] is False
    assert window["minimum_distinct_measurement_times"] >= 3
    assert numerical["execution_status"] == {
        "run_performed_in_h0_h2": False,
        "by2_data_used": False,
        "reference_trace_used": False,
    }

    assert gauge["initial_yaw_degrees"] == [-150, -100, -50, 0, 50, 100, 150]
    assert gauge["contract_status"] == "FROZEN_NOT_EXECUTED"
    assert gauge["execution_prohibitions_in_h0_h2"] == {
        "run_filter": False,
        "open_reference_trace": False,
        "calculate_metrics": False,
    }


def test_payload_has_no_local_paths_or_forbidden_execution_authorization() -> None:
    payload_files = sorted(
        path
        for root in (DOC_PAYLOAD, CONFIG_PAYLOAD)
        for path in root.rglob("*")
        if path.is_file()
    )
    assert payload_files
    historical_doc_files = {
        path.relative_to(DOC_PAYLOAD).as_posix()
        for path in payload_files
        if path.is_relative_to(DOC_PAYLOAD)
    }
    historical_config_files = {
        path.relative_to(CONFIG_PAYLOAD).as_posix()
        for path in payload_files
        if path.is_relative_to(CONFIG_PAYLOAD)
    }
    assert (
        len(HISTORICAL_H0_H2_REQUIRED_DOC_FILES)
        + len(HISTORICAL_H0_H2_REQUIRED_CONFIG_FILES)
    ) == 46
    assert HISTORICAL_H0_H2_REQUIRED_DOC_FILES <= historical_doc_files
    assert HISTORICAL_H0_H2_REQUIRED_CONFIG_FILES <= historical_config_files
    input_audit_names = {
        path.name for path in (DOC_PAYLOAD / "03_BY2_INPUT_AUDIT").iterdir()
        if path.is_file()
    }
    assert {
        "BY2_COMPLETE_RECORD_PREFIX_MANIFEST.json",
        "BY2_TRAILING_RECORD_LEDGER.json",
        "FK_PROXY_COVARIANCE_ESTIMATION.csv",
        "FK_PROXY_COVARIANCE_SUMMARY.json",
    } <= input_audit_names
    combined = "\n".join(path.read_text(encoding="utf-8") for path in payload_files)
    lowered = combined.lower()

    assert "/home/" not in lowered
    assert "/mnt/" not in lowered
    assert re.search(r"\b[a-z]:[\\/]", lowered) is None
    assert "PARTIAL_INPUT_ONLY_DIAGNOSTIC" not in combined
    assert "UNFROZEN_DUE_TERMINAL_STREAM_COMPLETENESS_BLOCKER" not in combined
    assert combined.count("BLOCKED_LSE01_BY2_REQUIRED_FIELD_MISSING") == 1
    report = (DOC_PAYLOAD / "11_REPORT/LSE01_H0_H2_REPORT.md").read_text(
        encoding="utf-8"
    )
    assert "remains historical evidence" in report

    prohibited_true_keys = (
        "trace_online",
        "trace_used_online",
        "real_by2_hartley_run",
        "by2_filter_run",
        "filter_run",
        "run_filter",
        "ext06_work",
        "ext06_authorized",
        "horizontal18_authorized",
        "horizontal18_v2_authorized",
        "canonical_541_authorized",
        "canonical541_authorized",
    )
    for key in prohibited_true_keys:
        pattern = rf'(?im)^\s*["\']?{re.escape(key)}["\']?\s*:\s*true\b'
        assert re.search(pattern, combined) is None, key

    method = _yaml(CONTRACTS / "HARTLEY_METHOD_CONTRACT.yaml")
    assert method["h0_h2_prohibitions"] == {
        "real_by2_hartley_run": False,
        "gauge_ensemble_run": False,
        "trace_evaluation": False,
        "parameter_tuning": False,
        "ext06_work": False,
    }

    status = _json(DOC_PAYLOAD / "11_REPORT/LSE01_H0_H2_STATUS.json")
    assert status["terminal_status"] == (
        "PASS_LSE01_H0_H2_HARTLEY_SOURCE_METHOD_AND_BY2_CONTRACT_READY"
    )
    assert status["data_identity"] == "REAL_BY2_COMPLETE_RECORD_PREFIX_63277"
    assert status["data_status"] == "REAL_BY2_COMPLETE_RECORD_PREFIX"
    assert status["data_mode"] == "real_by2_raw"
    assert status["raw_source_complete"] is False
    assert status["complete_record_prefix_filter_eligible"] is True
    assert status["complete_record_count"] == 63277
    assert status["timestamped_record_starts"] == 63278
    assert status["trailing_incomplete_record_count"] == 1
    assert status["trailing_record_used_online"] is False
    assert status["foot_speed_role"] == "DIAGNOSTIC_ONLY"
    assert status["foot_speed_online_allowed"] is False
    assert status["foot_speed_online"] is False
    assert status["foot_speed_offline_fk_covariance_residual_used"] is True
    assert status["foot_speed_changes_threshold_or_state"] is False
    assert status["contact_policy"] == "FROZEN_BY2_INPUT_ONLY_CONTACT_POLICY"
    assert status["contact_contract_closed"] is True
    assert status["fk_proxy_covariance_closed"] is True
    assert status["canonical_input_audit_published"] is True
    assert status["uncommitted_input_audit"] is False
    assert status["h3_authorized"] is True
    assert status["h3_run_count"] == 0
    assert status["filter_run_count"] == 0
    assert status["gauge_ensemble_run_count"] == 0
    assert status["reference_open_count"] == 0
    assert status["trace_used_online"] is False
    assert status["tests"]["scoped_hartley"] == "50_passed"
    assert status["tests"]["full_active_suite"] == (
        "2_failed_898_passed_10_skipped_14_warnings"
    )
    assert status["tests"]["full_active_suite_no_new_failures"] is True
    assert len(status["tests"]["full_active_suite_preexisting_unrelated_failures"]) == 2
