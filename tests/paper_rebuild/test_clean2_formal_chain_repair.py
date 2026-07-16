from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.clean2_case_provider import _read_base_gnss
from legsa_gins.paper_rebuild.clean2_runner import (
    Clean2RunError,
    _classify_technical_failure,
    create_executable_source_manifest,
    require_structural_gate,
    validate_clean2_formal_manifest,
)


def test_executable_source_manifest_binds_exact_tracked_target_set(tmp_path):
    repo = tmp_path / "repo"
    (repo / "cpp/legsa_v23_port_core/src").mkdir(parents=True)
    (repo / "cpp/CMakeLists.txt").write_text("project(test)\n", encoding="utf-8")
    (repo / "cpp/legsa_v23_port_core/src/core.cpp").write_text("int x = 0;\n", encoding="utf-8")
    executable = tmp_path / "solver"
    executable.write_bytes(b"solver")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "clean2@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "CLEAN2 Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "cpp"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "freeze"], cwd=repo, check=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    manifest = create_executable_source_manifest(
        output_path=tmp_path / "source-manifest.json",
        code_root=repo,
        executable=executable,
        expected_code_commit=commit,
    )
    assert set(manifest["source_files"]) == {
        "cpp/CMakeLists.txt",
        "cpp/legsa_v23_port_core/src/core.cpp",
    }
    assert manifest["source_file_count"] == 2


def test_fresh_15_column_c00_appends_explicit_validity_without_token_drift(tmp_path):
    source = tmp_path / "fresh.gnss"
    first15 = [str(value) for value in range(1, 16)]
    source.write_text(" ".join(first15) + "\n", encoding="utf-8")
    rows, payload, audit = _read_base_gnss(source)
    assert rows == [tuple([*first15, "1", "1", "1"])]
    assert payload.decode().strip().split()[:15] == first15
    assert audit["source_column_count"] == 15
    assert audit["first15_token_parity"] is True
    assert audit["first15_numerical_parity"] is True


def _formal_manifest() -> dict:
    output_roles = {
        "legsa_nav": "attempts/attempt_1/LegSA_PORT_NAV.nav",
        "legsa_std": "attempts/attempt_1/LegSA_PORT_STD.csv",
        "evaluator_nav": "attempts/attempt_1/EVAL_NAV.csv",
        "exact_nav": "attempts/attempt_1/KF_GINS_Navresult.nav",
        "exact_std": "attempts/attempt_1/KF_GINS_STD.txt",
        "exact_imu_error": "attempts/attempt_1/KF_GINS_IMU_ERR.txt",
        "solver_manifest": "attempts/attempt_1/RUN_MANIFEST.json",
        "gnss_action_trace": "attempts/attempt_1/PORT_GNSS_UPDATE_TRACE.csv",
        "file_open_trace": "attempts/attempt_1/SOLVER_FILE_OPEN_TRACE.raw",
        "file_open_audit": "attempts/attempt_1/SOLVER_FILE_OPEN_AUDIT.json",
    }
    modules = {
        "position_update_count": 274, "receiver_velocity_update_count": 274,
        "dual_yaw_update_count": 268, "raw_doppler_update_count": 0,
        "source_aware_evaluation_count": 0, "source_aware_weight_changed_count": 0,
        "go2_roll_pitch_update_count": 0, "go2_horizontal_velocity_update_count": 0,
        "selected_fgo_feedback_update_count": 0, "nine_factor_fgo_update_count": 0,
        "qa_fallback_count": 0, "multi_state_qm_update_count": 0, "contact_fk_update_count": 0,
    }
    return {
        "schema_version": "paper_rebuild.clean2_formal_run_manifest.v1",
        "stage_id": "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18",
        "protocol_id": "CLEAN_REAL_DATA_FINAL_V23", "run_id": "R003_C00_AB0000",
        "case_id": "C00_clean_normal", "result_namespace": "BY2_REAL_CLEAN_MODULE_ABLATION",
        "data_mode": "real_by2_raw", "role": "ablation_configuration",
        "structural_method": "strong_dual_yaw_EKF", "ablation_id": "AB0000",
        "feature_RD": False, "feature_SA": False, "feature_RP": False, "feature_HV": False,
        "run_order": 3, "formal": True, "alias_roles": "canonical_strong",
        "code_commit": "a" * 40, "code_worktree_dirty_at_run": False,
        "runtime_config_hash": "1" * 64, "executable_hash": "2" * 64,
        "executable_source_manifest_hash": "3" * 64, "provider_bundle_hash": "4" * 64,
        "provider_hashes": {key: str(index) * 64 for index, key in enumerate(("imu", "gnss", "case_gnss", "dual_yaw", "raw_doppler", "go2_roll_pitch", "go2_horizontal_velocity"), start=1)},
        "raw_source_hashes": {f"raw/{index}": "8" * 64 for index in range(22)},
        "source_manifest_hashes": {key: "9" * 64 for key in ("clean_input", "auxiliary_bundle", "case_provider", "case_provider_index", "historical_formal_schema", "clean2_formal_schema")},
        "actual_solver_input_paths": {"propagation_imu": "provider://fresh/imu", "case_gnss": "provider://case/gnss"},
        "synthetic_data_used": False, "semisynthetic_data_used": False,
        "trace_used_online": False, "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False, "LegSA_output_solver_input": False,
        "per_case_tuning": False, "output_only_correction": False,
        "epoch_deleted_for_metric": False, "old_runtime_input_count": 0,
        "legacy_provider_input_count": 0, "legacy_row_input_count": 0,
        "legacy_aggregate_input_count": 0, "status_fallback_used": False,
        "paper_performance_claim": False, "module_update_counts": modules,
        "counters": {"yaw_attempt_count": 274, "yaw_normal_count": 228, "yaw_downweight_count": 40, "yaw_reject_count": 6, "yaw_accepted_count": 268, "raw_doppler_reject_count": 0, "go2_roll_pitch_reject_count": 0, "go2_horizontal_velocity_reject_count": 0},
        "file_read_audit": {
            "schema_version": "paper_rebuild.clean2_solver_file_open_audit.v1",
            "stage_id": "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18",
            "run_id": "R003_C00_AB0000", "run_order": 3,
            "strace_available": True, "strace_sha256": "a" * 64,
            "required_input_roles": ["case_gnss", "propagation_imu", "runtime_config"],
            "required_input_open_counts": {"case_gnss": 1, "propagation_imu": 1, "runtime_config": 1},
            "missing_required_input_roles": [], "opened_path_count": 10,
            "raw_root_open_count": 0, "trace_open_count": 0,
            "trace_used_online": False, "private_absolute_paths_recorded": False,
            "passed": True,
        },
        "output_health": {
            "nav_row_count": 274, "std_row_count": 274,
            "nav_column_count": 11, "std_column_count": 22,
            "nav_std_timestamp_abs_max_sec": 0.0, "row_count_exact": True,
            "timestamps_exact": True, "time_monotonic": True,
            "finite_output": True, "passed": True,
        },
        "source_aware_trace_expected": False, "output_files": output_roles,
        "output_hashes": {key: "a" * 64 for key in output_roles},
        "solver_manifest_sha256": "b" * 64, "solver_returncode": 0,
        "runtime_seconds": 1.0, "terminal_status": "PASS",
    }


def test_formal_wrapper_schema_is_seal_ready_and_export_safe(repo_root):
    manifest = _formal_manifest()
    validate_clean2_formal_manifest(
        manifest, repo_root / "configs/paper_rebuild/clean2_formal_manifest_schema.yaml"
    )
    manifest["output_files"]["exact_nav"] = "/private/KF_GINS_Navresult.nav"
    with pytest.raises(Clean2RunError, match="schema failure|unsafe output path"):
        validate_clean2_formal_manifest(
            manifest, repo_root / "configs/paper_rebuild/clean2_formal_manifest_schema.yaml"
        )


def test_structural_gate_cannot_be_forged_by_pass_boolean(tmp_path, monkeypatch):
    expected = {"schema_version": "gate", "passed": True, "binding_digest": "bound"}
    monkeypatch.setattr(
        "legsa_gins.paper_rebuild.clean2_runner._structural_gate_payload",
        lambda **kwargs: expected,
    )
    path = tmp_path / "gate.json"
    path.write_text(json.dumps({"passed": True}), encoding="utf-8")
    with pytest.raises(Clean2RunError, match="STRUCTURAL_PARITY"):
        require_structural_gate(path)
    path.write_text(json.dumps(expected), encoding="utf-8")
    assert require_structural_gate(path) == expected


def test_retry_classification_requires_explicit_transient_evidence():
    assert _classify_technical_failure(1, "deterministic config validation failed") == ""
    assert _classify_technical_failure(124, "") == ""
    assert _classify_technical_failure(-11, "") == "process_crash"
    assert _classify_technical_failure(139, "") == "process_crash"
    assert _classify_technical_failure(1, "stale file handle") == "I/O_transient"
    assert _classify_technical_failure(1, "cannot allocate memory") == "resource_exhaustion"
    assert _classify_technical_failure(1, "lost PTY") == "lost_PTY"
