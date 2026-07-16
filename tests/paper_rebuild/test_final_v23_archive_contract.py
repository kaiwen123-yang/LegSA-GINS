from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.paper_rebuild import finalize_clean1r2_blocked as finalizer


def test_archive_contract_is_exact_and_fail_closed() -> None:
    contract = finalizer.load_contract()
    assert contract["archive_identity"]["sha256"] == finalizer.ARCHIVE_SHA256
    assert contract["archive_identity"]["exact_tag"] == "final-v23-freeze"
    assert contract["archive_identity"]["exact_tag_commit"] == finalizer.TAG_COMMIT
    assert contract["terminal_status"] == finalizer.TERMINAL_STATUS
    assert contract["clean_execution_eligible"] is False
    assert contract["execution_status"]["current_solver_process_count"] == 0
    assert contract["execution_status"]["current_formal_run_count"] == 0


def _write_tag_fixture(root: Path) -> Path:
    log = root / finalizer.TAG_LOG_RELATIVE
    tag_root = root / finalizer.TAG_SOURCE_RELATIVE
    source = tag_root / "tree/src/kf-gins/gi_engine.cpp"
    source.parent.mkdir(parents=True)
    source.write_text("exact tag source\n", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    runner = tag_root / "tag_source/scripts/run_final_mainline.py"
    note = tag_root / "tag_source/docs/final_mainline_config.md"
    runner.parent.mkdir(parents=True)
    note.parent.mkdir(parents=True)
    runner.write_text("runner\n", encoding="utf-8")
    note.write_text("config note\n", encoding="utf-8")
    runner_hash = hashlib.sha256(runner.read_bytes()).hexdigest()
    note_hash = hashlib.sha256(note.read_bytes()).hexdigest()
    log.mkdir(parents=True)
    terminal_payload = {
                "terminal_decision": "APPROVED_EXACT_FINAL_V23_SOLVER_TAG_SOURCE_RECOVERY",
                "tag_name": finalizer.TAG_NAME,
                "tag_commit": finalizer.TAG_COMMIT,
                "archive_sha256": finalizer.ARCHIVE_SHA256,
                "gates": {
                    "archive_pre_post_sha_stat_unchanged": True,
                    "tag_verified": True,
                    "tag_ref_unique": True,
                    "tag_commit_exact": True,
                    "git_fsck_full_no_reflogs_pass": True,
                    "selected_source_regular_blob_only": True,
                    "required_tag_paths_present": True,
                    "required_solver_writer_paths_present": True,
                    "dependency_roots_unique": True,
                    "static_build_source_closure": True,
                    "archive_static_ancillary_bindings_unique": True,
                    "missing_tag_ancillary_roles_recorded": True,
                    "missing_tag_ancillary_role_count": 2,
                    "failed_attempt_quarantines_excluded": True,
                    "archive_working_tree_head_used": False,
                    "solver_or_binary_executed": False,
                    "fsck_non_dangling_diagnostic_count": 0,
                },
                "missing_from_tag_ancillary_roles": [
                    "bin/process_data.py",
                    "bin/evaluate_nav_trace_kfgins_v2.py",
                ],
                "blockers": [],
            }
    provenance_payload = {
                "git": {
                    "tag_name": finalizer.TAG_NAME,
                    "peeled_commit": finalizer.TAG_COMMIT,
                },
                "archive": {
                    "expected_sha256": finalizer.ARCHIVE_SHA256,
                    "invariant": {
                        "sha256_unchanged": True,
                        "stat_unchanged": True,
                    },
                },
                "execution_boundary": {
                    "solver_built": False,
                    "solver_run": False,
                    "trace_read": False,
                    "performance_result_read": False,
                },
            }
    for parent in (log, tag_root):
        parent.mkdir(parents=True, exist_ok=True)
        (parent / "FINAL_V23_TAG_SOURCE_RECOVERY_MANIFEST.json").write_text(
            json.dumps(terminal_payload), encoding="utf-8"
        )
        (parent / "TAG_PROVENANCE.json").write_text(
            json.dumps(provenance_payload), encoding="utf-8"
        )
    manifest = root / finalizer.TAG_SOURCE_RELATIVE / "TAG_SOURCE_MANIFEST.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "tag_commit": finalizer.TAG_COMMIT,
                "rows": [
                    {
                        "path": "src/kf-gins/gi_engine.cpp",
                        "sha256": digest,
                        "logical_role": "solver_core",
                        "selection_reason": "test",
                        "materialized_relative": "tree/src/kf-gins/gi_engine.cpp",
                    },
                    {
                        "path": "scripts/run_final_mainline.py",
                        "sha256": runner_hash,
                        "logical_role": "runtime_runner",
                        "selection_reason": "test",
                        "materialized_relative": "tag_source/scripts/run_final_mainline.py",
                    },
                    {
                        "path": "docs/final_mainline_config.md",
                        "sha256": note_hash,
                        "logical_role": "runtime_config_note",
                        "selection_reason": "test",
                        "materialized_relative": "tag_source/docs/final_mainline_config.md",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    ancillary_rows = [
        {
            "logical_path": "bin/process_data.py",
            "tag_status": "MISSING_FROM_TAG_ANCILLARY_ROLE",
            "archive_static_candidate_count": 1,
            "archive_static_sha256": finalizer.CORE_HASHES["process_data"],
            "archive_static_binding_status": "UNIQUE_STATIC_MEMBER_REFERENCE_ONLY",
            "archive_static_materialized_into_tag_source": False,
        },
        {
            "logical_path": "bin/evaluate_nav_trace_kfgins_v2.py",
            "tag_status": "MISSING_FROM_TAG_ANCILLARY_ROLE",
            "archive_static_candidate_count": 1,
            "archive_static_sha256": finalizer.CORE_HASHES["evaluator"],
            "archive_static_binding_status": "UNIQUE_STATIC_MEMBER_REFERENCE_ONLY",
            "archive_static_materialized_into_tag_source": False,
        },
        {
            "logical_path": "scripts/run_final_mainline.py",
            "tag_status": "PRESENT_IN_TAG",
            "materialized_into_tag_source": True,
            "tag_sha256": runner_hash,
        },
        {
            "logical_path": "docs/final_mainline_config.md",
            "tag_status": "PRESENT_IN_TAG",
            "materialized_into_tag_source": True,
            "tag_sha256": note_hash,
        },
    ]
    (tag_root / "TAG_ANCILLARY_ROLE_MAP.json").write_text(
        json.dumps({"tag_commit": finalizer.TAG_COMMIT, "rows": ancillary_rows}),
        encoding="utf-8",
    )
    (tag_root / "TAG_ANCILLARY_ROLE_MAP.csv").write_text(
        "logical_path,tag_status\n", encoding="utf-8"
    )
    conflict_rows = [
        {
            "path": "src/kf-gins/gi_engine.cpp",
            "tag_commit": finalizer.TAG_COMMIT,
            "tag_sha256": digest,
            "archive_working_tree_sha256": digest,
            "comparison_status": "HASH_MATCH",
        },
        {
            "path": "scripts/run_final_mainline.py",
            "tag_commit": finalizer.TAG_COMMIT,
            "tag_sha256": runner_hash,
            "archive_working_tree_sha256": runner_hash,
            "comparison_status": "HASH_MATCH",
        },
        {
            "path": "docs/final_mainline_config.md",
            "tag_commit": finalizer.TAG_COMMIT,
            "tag_sha256": note_hash,
            "archive_working_tree_sha256": note_hash,
            "comparison_status": "HASH_MATCH",
        },
    ]
    (tag_root / "WORKING_TREE_VS_TAG_CONFLICT_MAP.json").write_text(
        json.dumps({"tag_commit": finalizer.TAG_COMMIT, "rows": conflict_rows}),
        encoding="utf-8",
    )
    (tag_root / "WORKING_TREE_VS_TAG_CONFLICT_MAP.csv").write_text(
        "path,comparison_status\n"
        "src/kf-gins/gi_engine.cpp,HASH_MATCH\n"
        "scripts/run_final_mainline.py,HASH_MATCH\n"
        "docs/final_mainline_config.md,HASH_MATCH\n",
        encoding="utf-8",
    )
    return source


def test_exact_tag_manifest_binds_materialized_file_hash(tmp_path: Path) -> None:
    source = _write_tag_fixture(tmp_path)
    proof = finalizer._validate_tag_proof(tmp_path)
    assert proof["terminal"]["terminal_decision"].startswith("APPROVED_")
    source.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(finalizer.FinalizationError, match="materialization mismatch"):
        finalizer._validate_tag_proof(tmp_path)
