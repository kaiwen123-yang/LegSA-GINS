from __future__ import annotations

import importlib.util
import inspect
import json
import math
import sys
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest
import yaml


REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h7c.py"
SCRIPT = REPO / "scripts/paper_rebuild/evaluate_hartley_h7c.py"
CONTRACT = REPO / (
    "configs/paper_rebuild/horizontal_literature/hartley/stage_payload/"
    "04_METHOD_CONTRACTS/H7C_SOURCE_RECOVERY_CONTRACT.yaml"
)
CLAIM = REPO / (
    "docs/paper_rebuild/horizontal_literature/hartley/stage_payload/"
    "11_REPORT/LSE01_FINAL_CLAIM_BOUNDARY.md"
)


def _load_h7c():
    specification = importlib.util.spec_from_file_location("_test_hartley_h7c", MODULE)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


h7c = _load_h7c()


def _contract() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_freezes_exact_hypotheses_without_assuming_h5() -> None:
    hypotheses = _contract()["frozen_hypotheses"]
    assert hypotheses["H1"]["statement"] == (
        "trace_vrtk2 is a derived/exported view of user_io-out-poi_geodetic"
    )
    assert hypotheses["H2"]["statement"] == "reference physical point is FP_POI"
    assert hypotheses["H3"]["statement"] == (
        "YPR represents ENU0-to-FP_POI orientation"
    )
    assert "full ECEF-to-FP_POI quaternion" in hypotheses["H4"]["statement"]
    assert hypotheses["H5"]["statement"].endswith("T_FP_POI_from_GO2_BODY_IMU")
    assert hypotheses["H5"]["initial_state"] == "UNPROVEN"
    assert hypotheses["H5"]["availability_assumed"] is False
    assert hypotheses["H5"]["conclusion_frozen_as_available"] is False


def test_initial_global_zero_and_v2_cumulative_counters_are_both_literal() -> None:
    freeze = _contract()["reference_access_freeze"]
    assert freeze["initial_pre_access_freeze"]["trace_open_count"] == 0
    assert freeze["initial_pre_access_freeze"]["reference_output_open_count"] == 0
    assert freeze["initial_pre_access_freeze"]["reference_rows_read"] == 0
    failure = freeze["v1_path_resolution_failure"]["cumulative_counters_at_failure"]
    assert failure["trace_open_count"] == 1
    assert failure["reference_output_open_count"] == 7
    assert failure["reference_rows_read"] == 0
    correction = freeze["v2_path_correction_freeze"]
    assert correction["zero_additional_raw_opens_between_v1_failure_and_v2_freeze"] is True
    assert correction["scientific_extrinsic_search_execution_count"] == 0


def test_contract_canonical_config_hash_is_self_consistent() -> None:
    contract = _contract()
    assert h7c.compute_contract_config_hash(contract) == contract["config_hash"]["value"]


def test_proof_classification_set_is_exact() -> None:
    assert set(_contract()["proof_classifications"]["allowed"]) == {
        "SOURCE_EXPLICIT",
        "DETERMINISTIC_FIELD_MAPPING",
        "NUMERICAL_IDENTITY_CROSSCHECK",
        "UNPROVEN",
        "CONTRADICTED",
    }


def test_raw_allowlist_has_exact_sibling_capture_layout() -> None:
    raw = _contract()["raw_access_allowlist"]
    rows = {row["name"]: row for row in raw["files"]}
    assert len(rows) == raw["exact_file_count"] == 10
    prefix = raw["capture_stem_relative_path"]
    assert rows[h7c.RAW_FILENAMES[8]]["relative_path"] == f"{prefix}.fpl"
    assert rows[h7c.RAW_FILENAMES[9]]["relative_path"] == f"{prefix}.bag"
    assert rows[h7c.RAW_FILENAMES[0]]["relative_path"].startswith(prefix + "/")
    assert raw["layout_provenance"]["tracked_source_sha256"] == (
        "c60b6d61cb2d1aae5431a3b973c8ea67f391df85964201c6ad03463b144dfa5a"
    )


def test_fpl_and_bag_are_metadata_only() -> None:
    raw = _contract()["raw_access_allowlist"]
    assert raw["fpl_bag_trajectory_values_allowed"] is False
    assert set(raw["allowed_fpl_bag_information"]) == {
        "schema", "topic", "frame", "static_transform", "output_configuration",
        "naming", "timestamp", "export_provenance",
    }


def test_guard_rejects_raw_identity_before_freeze_verification(tmp_path: Path) -> None:
    path = tmp_path / "source.csv"
    path.write_text("x\n")
    guard = h7c.ReferenceAccessGuard(tmp_path)
    with pytest.raises(h7c.HartleyH7CError, match="forbidden before H7C contract freeze"):
        guard.identity(path)


def test_exclusive_write_fsync_path_is_non_overwriting(tmp_path: Path) -> None:
    target = tmp_path / "nested/value.json"
    h7c.write_exclusive(target, b"first\n")
    with pytest.raises(FileExistsError):
        h7c.write_exclusive(target, b"second\n")
    assert target.read_bytes() == b"first\n"


def test_decimal_token_cells_accept_adjacent_printed_values_without_tolerance() -> None:
    assert h7c.decimal_tokens_serialization_compatible(
        "91.03944280055524", "91.03944280055525"
    )
    assert h7c.decimal_tokens_serialization_compatible(
        "1772784055.927869", "1772784055.9278693"
    )
    low, high, sign = h7c.decimal_token_interval("1.20")
    assert (low, high, sign) == (Decimal("1.195"), Decimal("1.205"), 0)


def test_decimal_token_cells_reject_nonintersecting_or_opposite_sign_values() -> None:
    assert not h7c.decimal_tokens_serialization_compatible("1.00", "1.02")
    assert not h7c.decimal_tokens_serialization_compatible("-0.0", "0.0")
    source = inspect.getsource(h7c.decimal_tokens_serialization_compatible)
    assert "tolerance" not in source
    assert "float(" not in source


def test_quaternion_xyzw_order_and_normalization_are_explicit() -> None:
    half = math.sqrt(0.5)
    rotation = h7c.quaternion_xyzw_to_rotation([0.0, 0.0, half, half])
    assert np.allclose(rotation, h7c.rotation_z(math.pi / 2.0), atol=1.0e-15)
    with pytest.raises(h7c.HartleyH7CError, match="normalization"):
        h7c.quaternion_xyzw_to_rotation([0.0, 0.0, 1.0, 1.0])


def test_official_fp_a_tf_frame_a_parent_frame_b_child_and_wxyz_semantics() -> None:
    half = math.sqrt(0.5)
    edge = h7c.fp_a_tf_wxyz_to_parent_from_child(
        "FP_POI", "FP_VRTK", [1.0, 2.0, 3.0], [half, 0.0, 0.0, half]
    )
    assert edge["parent_frame"] == "FP_POI"
    assert edge["child_frame"] == "FP_VRTK"
    assert edge["transform_convention"] == "T_parent_from_child"
    assert edge["input_quaternion_order"] == "wxyz"
    expected = h7c.rigid_transform(h7c.rotation_z(math.pi / 2.0), [1.0, 2.0, 3.0])
    assert np.allclose(edge["transform_parent_from_child"], expected, atol=1.0e-15)


def test_body_alias_fails_closed_without_source_explicit_provenance() -> None:
    with pytest.raises(h7c.HartleyH7CError, match="UNPROVEN"):
        h7c.resolve_body_alias({"alias": "BODY", "canonical_frame": "FP_POI"})
    assert h7c.resolve_body_alias({
        "alias": "BODY",
        "canonical_frame": "GO2_BODY_IMU",
        "source_explicit_provenance": "measured installation record row 1",
        "proof_classification": "SOURCE_EXPLICIT",
    }) == "GO2_BODY_IMU"


def test_direction_explicit_transform_inverse_and_composition() -> None:
    a_from_b = h7c.rigid_transform(h7c.rotation_z(0.3), [1.0, 2.0, 3.0])
    b_from_c = h7c.rigid_transform(h7c.rotation_z(-0.2), [-1.0, 0.5, 2.0])
    a_from_c = h7c.compose_rigid_transforms(a_from_b, b_from_c)
    point_c = np.asarray([0.2, -0.1, 0.7, 1.0])
    assert np.allclose(a_from_c @ point_c, a_from_b @ (b_from_c @ point_c))
    assert np.allclose(h7c.invert_rigid_transform(a_from_b) @ a_from_b, np.eye(4))


def test_go2_to_fp_poi_pose_conversion_uses_declared_inverse_direction() -> None:
    world_from_go2 = h7c.rigid_transform(np.eye(3), [10.0, 0.0, 0.0])
    fp_from_go2 = h7c.rigid_transform(np.eye(3), [1.0, 0.0, 0.0])
    world_from_fp = h7c.convert_go2_pose_to_fp_poi(world_from_go2, fp_from_go2)
    assert np.allclose(world_from_fp[:3, 3], [9.0, 0.0, 0.0])


def test_relative_pose_metrics_use_translation_and_so3_geodesic_angle() -> None:
    identity = h7c.rigid_transform(np.eye(3), [0.0, 0.0, 0.0])
    moved = h7c.rigid_transform(h7c.rotation_z(0.2), [1.0, 0.0, 0.0])
    result = h7c.relative_pose_metrics(identity, moved, identity, moved)
    assert result == {
        "translation_error_m": 0.0,
        "rotation_geodesic_error_rad": 0.0,
        "rotation_geodesic_error_deg": 0.0,
    }


def test_rotation_angle_is_conjugation_invariant_for_outcome_b_diagnostic() -> None:
    relative = h7c.rotation_z(0.7)
    fixed = h7c.quaternion_xyzw_to_rotation([0.2, -0.1, 0.3, math.sqrt(0.86)])
    conjugated = h7c.conjugated_rotation(relative, fixed)
    assert math.isclose(
        h7c.so3_geodesic_angle(relative),
        h7c.so3_geodesic_angle(conjugated),
        abs_tol=1.0e-14,
    )


def test_one_primary_fixed_gauge_applies_unchanged_to_all_branches() -> None:
    yaw, translation = h7c.fixed_primary_yaw_translation_gauge(
        h7c.rotation_z(0.4), [1.0, 2.0, 3.0],
        h7c.rotation_z(-0.2), [-3.0, 5.0, 4.0],
    )
    primary = h7c.rigid_transform(h7c.rotation_z(0.4), [1.0, 2.0, 3.0])
    branch = h7c.rigid_transform(h7c.rotation_z(0.8), [2.0, -1.0, 0.5])
    assert np.allclose(
        h7c.apply_fixed_gauge_to_pose(yaw, translation, primary)[:3, 3],
        [-3.0, 5.0, 4.0],
    )
    expected_branch = h7c.rigid_transform(yaw, translation) @ branch
    assert np.allclose(
        h7c.apply_fixed_gauge_to_pose(yaw, translation, branch), expected_branch
    )


def test_outcome_a_logic_and_status_are_unit_only_and_exact() -> None:
    states = {f"H{index}": "SOURCE_EXPLICIT" for index in range(1, 5)}
    assert h7c.classify_h7c_outcome(
        states, unique_extrinsic_proven=True, extrinsic_search_exhausted=True
    ) == h7c.PASS_A
    status = h7c.status_for_outcome(h7c.PASS_A)
    assert status["go2_to_fp_poi_extrinsic_proven"] is True
    assert status["lse01_full_reference_relative_pose_evaluation_complete"] is True
    assert status["lse01_complete"] is True
    assert status["ready_for_ext06"] is True
    assert status["ext06_executed"] is False
    assert status["absolute_yaw_RMSE"] is None
    assert status["absolute_global_position_RMSE"] is None


def test_outcome_b_logic_and_required_status_are_exact() -> None:
    states = {
        "H1": "DETERMINISTIC_FIELD_MAPPING_PLUS_NUMERICAL_IDENTITY_CROSSCHECK",
        "H2": "SOURCE_EXPLICIT", "H3": "SOURCE_EXPLICIT", "H4": "SOURCE_EXPLICIT",
    }
    assert h7c.classify_h7c_outcome(
        states, unique_extrinsic_proven=False, extrinsic_search_exhausted=True
    ) == h7c.PASS_B
    status = h7c.status_for_outcome(h7c.PASS_B)
    required = _contract()["outcome_b_required_status"]
    for key, value in required.items():
        assert status[key] == value
    assert status["parameter_selection_performed"] is False


def test_outcome_c_lineage_contradiction_wins_and_closes_readiness() -> None:
    terminal = h7c.classify_h7c_outcome(
        {"H1": "CONTRADICTED"},
        unique_extrinsic_proven=False,
        extrinsic_search_exhausted=False,
    )
    assert terminal == h7c.BLOCKED_LINEAGE
    status = h7c.status_for_outcome(terminal)
    assert status["lse01_complete"] is False
    assert status["ready_for_ext06"] is False
    assert status["ext06_executed"] is False


def test_unclosed_hypotheses_cannot_invent_outcome_b() -> None:
    with pytest.raises(h7c.HartleyH7CError, match="H1-H4 must close"):
        h7c.classify_h7c_outcome(
            {"H1": "UNPROVEN"},
            unique_extrinsic_proven=False,
            extrinsic_search_exhausted=True,
        )


def test_measurement_lever_is_rejected_without_endpoint_direction_proof() -> None:
    result = h7c.validate_extrinsic_candidate({
        "translation_m": [0.03, 0.03, -0.30],
        "rotation_xyzw": [0.0, 0.0, 0.0, 1.0],
        "unique": False,
        "source_proven": False,
    })
    assert result["accepted"] is False
    assert {"from_frame", "to_frame", "convention", "direction"}.issubset(
        result["missing_fields"]
    )


def test_extrinsic_candidate_rejects_rmse_trajectory_and_go2_onboard_evidence() -> None:
    base = {
        "from_frame": "GO2_BODY_IMU",
        "to_frame": "FP_POI",
        "translation_m": [0.1, 0.2, 0.3],
        "rotation_xyzw": [0.0, 0.0, 0.0, 1.0],
        "convention": "T_to_from_from",
        "direction": "T_FP_POI_from_GO2_BODY_IMU",
        "applicable_configuration_and_time": "BY2 capture",
        "unique": True,
        "source_proven": True,
    }
    for forbidden in (
        "rmse_selection_used",
        "trajectory_fitting_used",
        "go2_onboard_pose_used",
        "go2_onboard_yaw_used",
    ):
        result = h7c.validate_extrinsic_candidate({**base, forbidden: True})
        assert result["accepted"] is False
        assert result["forbidden_evidence"] == [forbidden]
    assert h7c.validate_extrinsic_candidate(base)["accepted"] is True


def test_h5_native_freeze_identities_are_frozen_without_payload_duplication() -> None:
    h5 = _contract()["frozen_h5_outputs"]
    rows = [h5["primary_branch"], *h5["nonselective_branches"]]
    assert len(rows) == 4
    assert all(len(row["native_freeze_sha256"]) == 64 for row in rows)
    assert all(row["native_freeze_size"] == 1918 for row in rows)
    assert h5["filter_rerun_allowed"] is False
    assert h5["branch_selection_from_reference"] is False


def test_only_three_contradiction_terminals_are_contract_authorized() -> None:
    assert _contract()["outcome_logic"]["C"]["terminals"] == [
        h7c.BLOCKED_LINEAGE,
        h7c.BLOCKED_FRAME_GRAPH,
        h7c.BLOCKED_EXTRINSIC,
    ]


def test_required_lineage_and_report_names_are_exact() -> None:
    assert h7c.REQUIRED_FIELD_MAP_CSV_RELATIVE.name == (
        "TRACE_TO_POI_GEODETIC_FIELD_MAP.csv"
    )
    assert h7c.REQUIRED_LINEAGE_IDENTITY_RELATIVE.name == (
        "TRACE_TO_POI_GEODETIC_IDENTITY.json"
    )
    assert h7c.REQUIRED_LINEAGE_PROOF_RELATIVE.name == "REFERENCE_LINEAGE_PROOF.md"
    assert h7c.FINAL_REPORT_RELATIVE == Path("11_REPORT/LSE01_H7C_FINAL_REPORT.md")
    assert h7c.FINAL_STATUS_RELATIVE == Path("11_REPORT/LSE01_H7C_FINAL_STATUS.json")
    assert h7c.FINAL_CLAIM_RELATIVE == Path("11_REPORT/LSE01_FINAL_CLAIM_BOUNDARY.md")


def test_required_field_map_uses_neutral_ypr_source_scalar_labels() -> None:
    source = inspect.getsource(h7c.materialize_required_lineage_outputs)
    assert "yaw_source_scalar" in source
    assert "pitch_source_scalar" in source
    assert "roll_source_scalar" in source
    assert "yaw_rad" not in source
    assert "unit_conversion_applied" in source


def test_final_claim_boundary_has_every_required_scientific_statement() -> None:
    text = CLAIM.read_text()
    for phrase in (
        "faithful IJRR2020-reported Hartley backend",
        "Go2 high-level FK-like proxy, not raw joint/URDF FK",
        "theoretical and structural comparison is complete",
        "Global position and global yaw about gravity are unobservable gauges",
        "Full reference performance exists only if",
        "Fixposition-derived same-source FP_POI output",
        "not independent ground truth",
        "flat absolute-yaw ranking against LegSA",
        h7c.BLOCKED_LINEAGE,
        "ready_for_ext06=false",
    ):
        assert phrase in text


def test_forbidden_operations_are_all_false() -> None:
    forbidden = _contract()["forbidden_operations"]
    assert forbidden
    assert all(value is False for value in forbidden.values())


def test_h7c_source_and_cli_have_no_filter_external_or_canonical_launch() -> None:
    source = MODULE.read_text()
    script = SCRIPT.read_text()
    assert "run_hartley_h5" not in source + script
    assert "run_hartley_h6" not in source + script
    assert "subprocess.Popen" not in source
    assert "EXT06" not in script
    assert "canonical541" not in script.casefold()


def test_tracked_h7c_files_have_no_machine_local_absolute_path_literal() -> None:
    paths = [MODULE, SCRIPT, CONTRACT, CLAIM, Path(__file__)]
    needles = tuple("/" + name + "/" for name in ("mnt", "home", "tmp", "root"))
    for path in paths:
        text = path.read_text()
        assert all(needle not in text for needle in needles), path


def test_publication_is_explicit_and_does_not_use_recursive_copy_or_glob() -> None:
    source = inspect.getsource(h7c.publish_blocked_lineage)
    assert "CORE_PUBLICATION_RELATIVES" in source
    assert "write_exclusive" in source
    assert "copytree" not in source
    assert "rglob" not in source
    assert "glob(" not in source


def test_publication_hash_and_size_parity_gate_is_exact(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    published = tmp_path / "published.bin"
    source.write_bytes(b"abcd")
    published.write_bytes(b"abcd")
    assert h7c.hash_size_parity(source, published)["bytes_equal"] is True
    published.write_bytes(b"abce")
    mismatch = h7c.hash_size_parity(source, published)
    assert mismatch["source"]["size"] == mismatch["published"]["size"] == 4
    assert mismatch["source"]["sha256"] != mismatch["published"]["sha256"]
    assert mismatch["bytes_equal"] is False


def test_blocked_metric_absence_is_literal_and_non_numeric() -> None:
    metrics = h7c._metric_absence_after_lineage_blocker()
    assert metrics
    assert all(
        value == "NOT_EVALUATED_AFTER_H1_LINEAGE_CONTRADICTION"
        for value in metrics.values()
    )
    blocked = h7c.status_for_outcome(h7c.BLOCKED_LINEAGE)
    assert blocked["absolute_yaw_RMSE"] is None
    assert blocked["absolute_global_position_RMSE"] is None


def test_cli_exposes_prepare_audit_terminal_and_publish_phases() -> None:
    text = SCRIPT.read_text()
    for command in (
        "prepare", "inventory", "schema", "freeze-field-map", "lineage",
        "freeze-serialization-contract", "serialization-lineage",
        "materialize-lineage", "finalize", "publish",
    ):
        assert f'"{command}"' in text


def test_contract_and_required_status_round_trip_as_json_compatible() -> None:
    contract = _contract()
    json.dumps(contract, sort_keys=True)
    json.dumps(h7c.status_for_outcome(h7c.PASS_A), sort_keys=True)
    json.dumps(h7c.status_for_outcome(h7c.PASS_B), sort_keys=True)
    json.dumps(h7c.status_for_outcome(h7c.BLOCKED_LINEAGE), sort_keys=True)
