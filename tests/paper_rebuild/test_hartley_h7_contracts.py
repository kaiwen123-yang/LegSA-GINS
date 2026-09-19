from __future__ import annotations

import importlib.util
import inspect
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml


REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h7.py"
SCRIPT = REPO / "scripts/paper_rebuild/evaluate_hartley_h7.py"
CONTRACT = REPO / (
    "configs/paper_rebuild/horizontal_literature/hartley/stage_payload/"
    "04_METHOD_CONTRACTS/H7_EVALUATION_CONTRACT.yaml"
)


def _load_h7():
    specification = importlib.util.spec_from_file_location("_test_hartley_h7", MODULE)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


h7 = _load_h7()


def test_contract_is_frozen_at_zero_before_reference_access() -> None:
    contract = yaml.safe_load(CONTRACT.read_text())
    freeze = contract["reference_access_freeze"]
    assert freeze["reference_open_count"] == 0
    assert freeze["trace_open_count"] == 0
    assert freeze["reference_rows_read"] == 0
    assert freeze["contract_must_be_frozen_before_reference_open"] is True
    assert freeze["trace_stat_or_hash_before_point_frame_gate"] is False
    source = MODULE.read_text()
    assert source.index("_write_json(output / contract_freeze_relative") < source.index(
        "audit_relative = Path"
    )
    assert "--trace" not in SCRIPT.read_text()


def test_reference_identity_and_same_source_boundary_are_exact() -> None:
    contract = yaml.safe_load(CONTRACT.read_text())
    reference = contract["reference_identity"]
    assert reference["resolver"] == "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"
    assert reference["relative_path"].endswith(
        "trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv"
    )
    assert reference["declared_sha256"] == h7.TRACE_DECLARED_SHA256
    assert reference["same_source"] is True
    assert reference["independent_ground_truth"] is False


def test_physical_point_and_frame_gate_fails_closed() -> None:
    gate = yaml.safe_load(CONTRACT.read_text())["physical_point_and_frame_gate"]
    assert gate["hartley_point_closed"] is True
    assert gate["hartley_attitude_frame_closed"] is True
    assert gate["reference_position_point_identity"] == "UNRESOLVED_FROM_FROZEN_PROJECT_EVIDENCE"
    assert gate["reference_attitude_body_frame_identity"] == "UNRESOLVED_FROM_FROZEN_PROJECT_EVIDENCE"
    assert gate["fixposition_poi_body_to_go2_body_imu_transform"] == "ABSENT"
    assert gate["project_measurement_lever_role"].endswith("NOT_EVALUATOR_POINT_TRANSFORM")
    assert gate["fitted_transform_allowed"] is False
    assert gate["trajectory_error_may_infer_transform"] is False
    assert gate["gate_closed_for_metrics"] is False


def test_hartley_reporting_transform_is_proper_and_gravity_consistent() -> None:
    result = h7.validate_reporting_rotation()
    assert result["passed"] is True
    assert result["determinant"] == 1.0
    assert result["right_handed"] is True
    assert result["orthogonality_error_fro"] == 0.0
    assert result["round_trip_error_fro"] == 0.0
    assert result["gravity_ned_shaped_reporting_mps2"] == [0.0, 0.0, 9.81]


def test_fixed_10_hz_grid_has_exact_contract_endpoints() -> None:
    grid = h7.target_grid()
    assert len(grid) == 2741
    assert grid[0] == 66.0
    assert grid[-1] == 340.0
    assert np.allclose(np.diff(grid), 0.1, atol=3.5e-14, rtol=0.0)


def test_so3_interpolation_is_continuous_and_rejects_extrapolation() -> None:
    start = h7.rotation_z(math.radians(170.0))
    end = h7.rotation_z(math.radians(-170.0))
    midpoint = h7.interpolate_so3(start, end, 0.5)
    assert np.allclose(midpoint.T @ midpoint, np.eye(3), atol=1.0e-14)
    assert math.isclose(np.linalg.det(midpoint), 1.0, abs_tol=1.0e-14)
    delta0 = np.linalg.norm(h7.so3_log(start.T @ midpoint))
    delta1 = np.linalg.norm(h7.so3_log(midpoint.T @ end))
    assert math.isclose(delta0, delta1, rel_tol=1.0e-12)
    with pytest.raises(h7.HartleyH7Error, match="extrapolate"):
        h7.interpolate_so3(start, end, 1.01)


def test_relative_pose_convention_is_inverse_reference_times_estimate() -> None:
    estimate0 = h7.pose(h7.rotation_z(0.2), [1.0, 2.0, 3.0])
    estimate1 = h7.pose(h7.rotation_z(0.4), [2.0, 2.5, 3.1])
    reference0 = h7.pose(h7.rotation_z(-0.1), [-1.0, 4.0, 0.0])
    reference1 = h7.pose(h7.rotation_z(0.15), [0.5, 4.4, 0.2])
    expected = np.linalg.inv(np.linalg.inv(reference0) @ reference1) @ (
        np.linalg.inv(estimate0) @ estimate1
    )
    assert np.allclose(h7.relative_pose_error(estimate0, estimate1, reference0, reference1), expected)


def test_relative_pose_is_invariant_to_global_yaw_and_translation_left_gauge() -> None:
    estimate0 = h7.pose(h7.rotation_z(0.2), [1.0, 2.0, 3.0])
    estimate1 = h7.pose(h7.rotation_z(0.4), [2.0, 2.5, 3.1])
    reference0 = h7.pose(h7.rotation_z(-0.1), [-1.0, 4.0, 0.0])
    reference1 = h7.pose(h7.rotation_z(0.15), [0.5, 4.4, 0.2])
    gauge = h7.pose(h7.rotation_z(1.17), [21.0, -9.0, 3.0])
    baseline = h7.relative_pose_error(estimate0, estimate1, reference0, reference1)
    transformed = h7.relative_pose_error(
        h7.left_gauge_pose(gauge, estimate0), h7.left_gauge_pose(gauge, estimate1),
        h7.left_gauge_pose(gauge, reference0), h7.left_gauge_pose(gauge, reference1),
    )
    assert np.allclose(transformed, baseline, atol=1.0e-13)


def test_one_primary_derived_fixed_gauge_applies_identically_to_all_branches() -> None:
    primary_rotation = h7.rotation_z(0.4)
    primary_position = np.asarray([1.0, 2.0, 3.0])
    reference_rotation = h7.rotation_z(-0.2)
    reference_position = np.asarray([-3.0, 5.0, 4.0])
    yaw_only, translation = h7.fixed_primary_gauge(
        primary_rotation, primary_position, reference_rotation, reference_position
    )
    assert np.allclose(yaw_only @ primary_rotation, reference_rotation)
    assert np.allclose(yaw_only @ primary_position + translation, reference_position)
    branch_states = [
        (h7.rotation_z(0.1), np.asarray([0.1, 0.2, 0.3]), np.asarray([4.0, 5.0, 6.0])),
        (h7.rotation_z(-0.3), np.asarray([-0.1, 0.7, 0.0]), np.asarray([8.0, -2.0, 1.0])),
    ]
    aligned = [h7.apply_fixed_gauge(yaw_only, translation, *state) for state in branch_states]
    for state, result in zip(branch_states, aligned):
        assert np.allclose(result[0], yaw_only @ state[0])
        assert np.allclose(result[1], yaw_only @ state[1])
        assert np.allclose(result[2], yaw_only @ state[2] + translation)


def test_correspondingly_transformed_primary_alignment_preserves_secondary_values() -> None:
    primary_rotation = h7.rotation_z(0.4)
    primary_position = np.asarray([1.0, 2.0, 3.0])
    reference_rotation = h7.rotation_z(-0.2)
    reference_position = np.asarray([-3.0, 5.0, 4.0])
    q0, t0 = h7.fixed_primary_gauge(
        primary_rotation, primary_position, reference_rotation, reference_position
    )
    branch = (h7.rotation_z(0.7), np.asarray([0.2, 0.3, 0.4]), np.asarray([4.0, 2.0, -1.0]))
    baseline = h7.apply_fixed_gauge(q0, t0, *branch)
    gauge_q = h7.rotation_z(1.1)
    gauge_t = np.asarray([10.0, -8.0, 2.0])
    transformed_primary_rotation = gauge_q @ primary_rotation
    transformed_primary_position = gauge_q @ primary_position + gauge_t
    q1, t1 = h7.fixed_primary_gauge(
        transformed_primary_rotation, transformed_primary_position,
        reference_rotation, reference_position,
    )
    transformed_branch = (
        gauge_q @ branch[0], gauge_q @ branch[1], gauge_q @ branch[2] + gauge_t,
    )
    recovered = h7.apply_fixed_gauge(q1, t1, *transformed_branch)
    assert all(np.allclose(left, right, atol=1.0e-13) for left, right in zip(baseline, recovered))


def test_no_search_fit_correction_or_metric_deletion_is_permitted() -> None:
    forbidden = yaml.safe_load(CONTRACT.read_text())["forbidden_operations"]
    assert forbidden
    assert all(value is False for value in forbidden.values())
    branches = yaml.safe_load(CONTRACT.read_text())["branches"]
    assert branches["primary"] == "H5_PRIMARY_GO2_ALLAN_EQ61_FK10MM"
    assert len(branches["nonselective"]) == 3
    assert branches["parameter_selection_from_reference"] is False
    assert branches["branch_specific_alignment"] is False


def test_absolute_yaw_and_global_position_are_non_numeric_n_a() -> None:
    metrics = yaml.safe_load(CONTRACT.read_text())["metric_contract"]
    assert metrics["absolute_yaw_RMSE"] == "NOT_APPLICABLE_WITH_OBSERVABILITY_PROOF"
    assert metrics["absolute_global_position_RMSE"] == "NOT_APPLICABLE_WITH_GAUGE_PROOF"
    assert not isinstance(metrics["absolute_yaw_RMSE"], (int, float))
    assert not isinstance(metrics["absolute_global_position_RMSE"], (int, float))


def test_blocker_prevents_metric_files_and_gauge_artifact_generation() -> None:
    absent = h7._metric_absence()
    assert len(absent) == 11
    assert all(value.startswith("NOT_EVALUATED") for value in absent.values())
    materializer = inspect.getsource(h7.materialize_blocker)
    assert "csv.writer" not in materializer
    assert "H7_EVALUATOR_GAUGE_INVARIANCE_TEST.json" not in materializer


def test_runtime_has_no_trace_argument_and_no_filter_or_external_launch() -> None:
    script = SCRIPT.read_text()
    module = MODULE.read_text()
    assert "--trace" not in script
    assert "run_hartley_h5" not in script + module
    assert "run_hartley_h6" not in script + module
    assert "EXT06" not in script
    assert "subprocess.Popen" not in module
    assert "subprocess.run(" in module  # Git identity only.


def test_publication_write_is_exclusive_and_non_overwriting(tmp_path: Path) -> None:
    target = tmp_path / "nested/evidence.json"
    h7._write_exclusive(target, b"first\n")
    with pytest.raises(FileExistsError):
        h7._write_exclusive(target, b"second\n")
    assert target.read_bytes() == b"first\n"


def test_terminal_status_schema_has_required_null_and_false_fields() -> None:
    source = inspect.getsource(h7.materialize_blocker)
    for token in (
        '"h6r_gauge_and_observability_preserved": True',
        '"reference_contract_frozen_before_open": True',
        '"reference_same_source": True',
        '"reference_independent_ground_truth": False',
        '"relative_pose_metrics_complete": False',
        '"relative_yaw_increment_complete": False',
        '"gauge_aligned_descriptive_metrics_complete": False',
        '"absolute_yaw_RMSE": None',
        '"absolute_position_RMSE": None',
        '"parameter_selection_performed": False',
        '"filter_rerun_count": 0',
        '"ext06_executed": False',
        '"canonical541_executed": False',
        '"lse01_terminalized": True',
        '"lse01_complete": False',
    ):
        assert token in source


def test_claim_boundary_preserves_scientific_wording() -> None:
    text = h7._claim_boundary()
    assert "faithful IJRR2020-reported backend reproduction" in text
    assert "Go2 high-level FK-like proxy, not raw joint/URDF FK" in text
    assert "Global translation and global yaw about gravity are unobservable" in text
    assert "same-source, not independent ground" in text
    assert "conservative/correlated proxy behavior" in text
    assert "not enter a flat absolute-yaw ranking" in text


def test_output_topology_and_publication_parity_are_frozen_in_materializer() -> None:
    source = inspect.getsource(h7.materialize_blocker)
    for relative in (
        "12_POST_NATIVE_EVALUATION/00_CONTRACTS/H7_EVALUATION_CONTRACT.yaml",
        "H7_REFERENCE_AND_POINT_IDENTITY_CONTRACT.md",
        "H7_CONTRACT_FREEZE.json",
        "12_POST_NATIVE_EVALUATION/01_REFERENCE_AUDIT/H7_REFERENCE_AUDIT.json",
        "11_REPORT/LSE01_H7_GAUGE_INVARIANT_RELATIVE_EVALUATION_REPORT.md",
        "11_REPORT/LSE01_HARTLEY_CLAIM_BOUNDARY.md",
        "11_REPORT/LSE01_FINAL_REPORT.md",
        "11_REPORT/LSE01_FINAL_STATUS.json",
        "12_POST_NATIVE_EVALUATION/H7_EVALUATION_FREEZE.json",
        "H7_PUBLICATION_MANIFEST.json",
        "H7_PUBLICATION_PARITY.json",
    ):
        assert relative in source
    assert '"all_published_bytes_equal": True' in source


def test_h7r1_writes_both_contracts_before_dual_hash_freeze_and_audit() -> None:
    source = inspect.getsource(h7.materialize_blocker_provenance_recovery)
    write_contract = source.index("_write_exclusive(scratch / contract_relative")
    write_point = source.index("_write_exclusive(scratch / point_relative")
    write_freeze = source.index("_write_json(scratch / contract_freeze_relative")
    write_storage_audit = source.index("_write_json(scratch / storage_relative")
    write_reference_audit = source.index("_write_json(scratch / audit_relative")
    write_status = source.index("_write_json(scratch / status_relative")
    assert write_contract < write_point < write_freeze
    assert write_freeze < write_storage_audit < write_reference_audit < write_status
    assert 'str(contract_relative): _file_identity(scratch, contract_relative)' in source
    assert 'str(point_relative): _file_identity(scratch, point_relative)' in source
    assert '"freeze_completed_before_audit_status_or_report": True' in source


def test_h7r1_contract_does_not_open_local_paths_or_resolve_reference() -> None:
    contract = yaml.safe_load(CONTRACT.read_text())
    reference = contract["reference_identity"]
    assert reference["resolver_role"] == "DECLARATIVE_ONLY_NOT_OPENED_BY_H7R1"
    assert reference["local_path_config_opened"] is False
    assert reference["reference_path_resolution"] == (
        "NOT_PERFORMED_DUE_TO_PRE_REFERENCE_POINT_FRAME_BLOCKER"
    )


def test_h7r1_required_runtime_provenance_is_complete_and_hash_bound() -> None:
    h5_fixture = {
        "data_mode": "real_by2_raw",
        "old_runtime_input_count": 0,
        "trace_used_online": False,
        "raw_full_sha256": h7.RAW_FULL_SHA256,
        "complete_prefix_sha256": h7.RAW_PREFIX_SHA256,
        "input_cache_sha256": h7.H5_CACHE_SHA256,
        "input_event_ledger_sha256": h7.H5_EVENT_LEDGER_SHA256,
    }
    provenance = h7._r1_provenance(REPO, h5_fixture)
    assert provenance["data_mode"] == "real_by2_raw"
    assert provenance["raw_source_hashes"]["accepted_raw_full"]["sha256"] == h7.RAW_FULL_SHA256
    assert provenance["raw_source_hashes"]["accepted_complete_prefix"]["sha256"] == h7.RAW_PREFIX_SHA256
    assert provenance["provider_hashes"]["h5_input_cache"]["sha256"] == h7.H5_CACHE_SHA256
    assert provenance["provider_hashes"]["h5_contact_event_ledger"]["sha256"] == h7.H5_EVENT_LEDGER_SHA256
    false_fields = (
        "synthetic_data_used", "semisynthetic_data_used", "trace_used_online",
        "receiver_imu_as_body_imu", "final_v23_output_solver_input",
        "LegSA_output_solver_input", "per_case_tuning", "output_only_correction",
        "epoch_deleted_for_metric",
    )
    assert all(provenance[field] is False for field in false_fields)
    assert provenance["old_runtime_input_count"] == 0
    assert provenance["code_commit"] == h7.TASK_START_HEAD
    assert provenance["config_hash"] == h7.sha256_file(CONTRACT)
    assert provenance["execution_code_committed"] is False
    assert provenance["dirty_or_precommit_scoped_execution"] is True
    assert len(provenance["scoped_h7_source_hashes"]) == 4
    assert provenance["later_commit_mapping"] == "PENDING_SUPERVISOR_COMMIT_HASH_MAPPING"


def test_h7r1_status_and_evaluation_freeze_both_embed_provenance_and_native_freezes() -> None:
    source = inspect.getsource(h7.materialize_blocker_provenance_recovery)
    status_block = source[source.index("status = {"):source.index("_write_json(scratch / status_relative")]
    freeze_block = source[source.index("evaluation_freeze = {"):source.index("_write_json(scratch / freeze_relative")]
    for block in (status_block, freeze_block):
        assert '"runtime_provenance": provenance' in block
        assert '"h5_native_freezes": h5["native_freezes"]' in block
    assert '"metric_files_created": 0' in status_block
    assert '"metric_files_created": 0' in freeze_block


def test_h7r1_storage_evidence_runs_and_records_only_read_only_queries() -> None:
    source = inspect.getsource(h7.collect_storage_health_read_only)
    assert '["findmnt", "-J", "-T", str(scratch_parent)]' in source
    assert '["findmnt", "-J", "-T", str(stage_root)]' in source
    assert "Get-Volume -DriveLetter {drive_letter}" in source
    assert 'drive_letter = source[0].upper()' in source
    assert '"FileSystem": "exFAT"' in source
    assert '"HealthStatus": "Warning"' in source
    assert '"OperationalStatus": "Full Repair Needed"' in source
    assert '"repair_command_invoked": False' in source
    assert 'local_value.get("fstype") != "ext4"' in source
    assert 'external_value.get("fstype") != "9p"' in source
    assert "Repair-Volume" in source  # Guard token only, never invoked.


def test_original_h7_snapshot_detects_any_scratch_or_stage_mutation(tmp_path: Path) -> None:
    original = tmp_path / "original"
    stage = tmp_path / "stage"
    payload_relative = Path("11_REPORT/original.json")
    manifest_relative = h7.ORIGINAL_H7_MANIFEST_RELATIVE
    parity_relative = h7.ORIGINAL_H7_PARITY_RELATIVE
    for root in (original, stage):
        (root / payload_relative).parent.mkdir(parents=True, exist_ok=True)
        (root / payload_relative).write_text("{}\n")
        (root / manifest_relative).parent.mkdir(parents=True, exist_ok=True)
        (root / manifest_relative).write_text("{}\n")
    identity = h7._file_identity(original, payload_relative)
    parity = {
        "all_published_bytes_equal": True,
        "file_count": 10,
        "files": [{"relative_path": str(payload_relative), "source": identity,
                   "published": identity, "bytes_equal": True}],
    }
    # The production parity has ten rows. Repeated fixture rows preserve its control count.
    parity["files"] *= 10
    for root in (original, stage):
        (root / parity_relative).write_text(json.dumps(parity) + "\n")
    snapshot = h7.snapshot_original_h7(original, stage)
    assert snapshot["scratch_stage_hash_size_parity"] is True
    (stage / payload_relative).write_text('{"changed":true}\n')
    with pytest.raises(h7.HartleyH7Error, match="original H7 scratch/stage mismatch"):
        h7.snapshot_original_h7(original, stage)


def test_h7r1_publication_is_additive_prefixed_and_exclusive() -> None:
    source = inspect.getsource(h7.materialize_blocker_provenance_recovery)
    assert str(h7.R1_RECOVERY_RELATIVE) in MODULE.read_text()
    for name in (
        "H7R1_EVALUATION_CONTRACT.yaml",
        "H7R1_REFERENCE_AND_POINT_IDENTITY_CONTRACT.md",
        "H7R1_CONTRACT_FREEZE.json",
        "H7R1_STORAGE_HEALTH_READ_ONLY.json",
        "H7R1_REFERENCE_AUDIT.json",
        "H7R1_EVALUATION_FREEZE.json",
        "H7R1_ORIGINAL_H7_PRESERVATION.json",
        "H7R1_PUBLICATION_MANIFEST.json",
        "H7R1_PUBLICATION_PARITY.json",
        "LSE01_H7R1_FINAL_STATUS.json",
        "LSE01_H7R1_BLOCKER_PROVENANCE_RECOVERY_REPORT.md",
        "LSE01_H7R1_FINAL_REPORT.md",
        "LSE01_H7R1_HARTLEY_CLAIM_BOUNDARY.md",
    ):
        assert name in source
    assert "_write_exclusive(stage_root / relative" in source
    assert '"original_h7_preserved_unchanged": True' in source


def test_h7r2_is_the_only_cli_route_and_has_no_free_form_storage_claims() -> None:
    source = SCRIPT.read_text()
    assert "materialize_path_alias_recovery" in source
    assert "materialize_blocker(" not in source
    assert "materialize_blocker_provenance_recovery" not in source
    assert "storage_filesystem" not in source
    assert "storage_health_status" not in source


def test_legacy_original_h7_materializer_is_disabled() -> None:
    with pytest.raises(h7.HartleyH7Error, match="LEGACY_H7_MATERIALIZER_DISABLED"):
        h7.materialize_blocker(
            REPO, Path("unused"), Path("unused"), Path("unused"), Path("unused"), {},
        )


def test_four_tracked_h7_files_have_no_machine_local_absolute_path_literal() -> None:
    result = h7.validate_no_tracked_machine_absolute_paths(REPO)
    assert result["scoped_file_count"] == 4
    assert result["machine_local_absolute_path_literal_count"] == 0
    separator = chr(47)
    forbidden = tuple(separator + root + separator for root in (
        "mnt", "home", "root", "tmp", "var", "opt", "usr",
    ))
    for relative in h7.R1_SCOPED_SOURCE_RELATIVES:
        text = (REPO / relative).read_text()
        assert not any(value in text for value in forbidden)


def test_storage_stage_identity_is_relative_to_runtime_findmnt_target() -> None:
    source = inspect.getsource(h7.collect_storage_health_read_only)
    assert 'mount_target = Path(external_value.get("target", ""))' in source
    assert "stage_root.relative_to(mount_target)" in source
    assert "stage_below_mount != EXPECTED_STAGE_SUFFIX" in source
    assert 'external_value.get("fstype") != "9p"' in source
    assert 'source[0].upper() != "G"' in source


def test_h5_provenance_is_verified_before_provenance_copy() -> None:
    source = inspect.getsource(h7.verify_h5_inputs)
    assert '"data_mode": "real_by2_raw"' in source
    assert '"old_runtime_input_count": 0' in source
    assert '"trace_used_online": False' in source
    provenance = inspect.getsource(h7._r1_provenance)
    assert '"data_mode": h5["data_mode"]' in provenance
    assert '"old_runtime_input_count": h5["old_runtime_input_count"]' in provenance
    assert '"trace_used_online": h5["trace_used_online"]' in provenance


def test_h7r2_dual_contract_freeze_precedes_audit_status_and_report() -> None:
    source = inspect.getsource(h7.materialize_path_alias_recovery)
    write_contract = source.index("_write_exclusive(scratch / contract_relative")
    write_point = source.index("_write_exclusive(scratch / point_relative")
    write_freeze = source.index("_write_json(scratch / contract_freeze_relative")
    write_audit = source.index("_write_json(scratch / audit_relative")
    write_status = source.index("_write_json(scratch / status_relative")
    assert write_contract < write_point < write_freeze < write_audit < write_status
    assert 'str(contract_relative): _file_identity(scratch, contract_relative)' in source
    assert 'str(point_relative): _file_identity(scratch, point_relative)' in source


def test_h7r2_snapshots_both_predecessors_before_and_after_publication() -> None:
    source = inspect.getsource(h7.materialize_path_alias_recovery)
    assert source.index("h7_before = snapshot_original_h7") < source.index("scratch.mkdir()")
    assert source.index("h7r1_before = snapshot_h7r1") < source.index("scratch.mkdir()")
    assert source.index("h7_after = snapshot_original_h7") > source.index(
        "_write_exclusive(stage_root / relative"
    )
    assert source.index("h7r1_after = snapshot_h7r1") > source.index(
        "_write_exclusive(stage_root / relative"
    )
    assert '"h7_unchanged_before_after": True' in source
    assert '"h7r1_unchanged_before_after": True' in source
