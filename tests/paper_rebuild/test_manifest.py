from __future__ import annotations

import csv
from pathlib import Path

from legsa_gins.paper_rebuild.manifest import (
    REQUIRED_RUN_FIELDS,
    read_hash_lock,
    sha256_file,
    validate_run_manifest,
    verify_raw_sources,
)
from legsa_gins.paper_rebuild.paths import load_yaml_mapping
from legsa_gins.paper_rebuild.runner import APPROVED_METHODS


def _manifest(digest: str) -> dict[str, object]:
    return {
        "schema_version": "paper-rebuild-run-manifest-v1",
        "run_id": "basic",
        "algorithm_id": "basic_dual_yaw_EKF",
        "case_id": "BY2_CLEAN_SMOKE",
        "data_mode": "real_by2_raw",
        "raw_source_hashes": {"BY2/source.csv": digest},
        "provider_hashes": {"gnss_runtime_input": digest},
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "trace_used_online": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0,
        "code_commit": "0123456789abcdef",
        "code_worktree_dirty_at_run": False,
        "config_hash": digest,
        "provider_generator_commit": "0123456789abcdef",
        "provider_generation_config_hash": digest,
        "local_path_config_hash": digest,
        "terminal_status": "PASS",
    }


def test_hash_lock_and_manifest_contract(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    source = raw / "BY2" / "source.csv"
    source.parent.mkdir(parents=True)
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    digest = sha256_file(source)
    lock_path = tmp_path / "RAW_FILE_HASH_LOCK.csv"
    with lock_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["relative_path", "size_bytes", "sha256"])
        writer.writeheader()
        writer.writerow({"relative_path": "BY2/source.csv", "size_bytes": source.stat().st_size, "sha256": digest})
    lock = read_hash_lock(lock_path)
    assert verify_raw_sources(raw, ["BY2/source.csv"], lock) == {"BY2/source.csv": digest}
    assert validate_run_manifest(_manifest(digest), require_pass=True) == []


def test_manifest_fails_closed_on_forbidden_flags(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"bytes")
    manifest = _manifest(sha256_file(source))
    manifest["trace_used_online"] = True
    manifest["old_runtime_input_count"] = 1
    manifest["code_worktree_dirty_at_run"] = True
    issues = validate_run_manifest(manifest, require_pass=True)
    assert "forbidden_flag_not_false:trace_used_online" in issues
    assert "old_runtime_input_count_must_be_zero" in issues
    assert "code_worktree_dirty_at_run_must_be_false" in issues


def test_tracked_config_contracts_match_clean_runner() -> None:
    root = Path(__file__).resolve().parents[2]
    schema = load_yaml_mapping(root / "configs" / "paper_rebuild" / "manifest_schema.yaml")
    assert set(REQUIRED_RUN_FIELDS).issubset(schema["required"])
    assert schema["properties"]["schema_version"]["const"] == "paper-rebuild-run-manifest-v1"
    methods = load_yaml_mapping(root / "configs" / "paper_rebuild" / "methods.yaml")
    assert set(methods["methods"]) == set(APPROVED_METHODS)
    path_example = load_yaml_mapping(
        root / "configs" / "paper_rebuild" / "DATA_PATHS.local.example.yaml"
    )
    assert set(path_example["paths"]) == {
        "code_root",
        "raw_root",
        "by2_fix_root",
        "by2_go2_body",
        "clean_root",
        "provider_root",
        "runtime_root",
    }
