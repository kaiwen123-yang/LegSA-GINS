import json
import hashlib
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from legsa_gins.paper_rebuild.horizontal_literature import phase4_runner
from legsa_gins.paper_rebuild.horizontal_literature.ext04_wu2025 import (
    FAR_POLICY_IDENTITY,
    POLICY_IDENTITY,
    REPRODUCTION_LEVEL,
    SENSITIVITY_POLICIES,
)
from legsa_gins.paper_rebuild.horizontal_literature.phase4_runner import (
    AUTHORIZED_WORKERS,
    EXPECTED_HEADING_ROWS,
    EXPECTED_PAIR_COUNT,
    EXPECTED_BRANCH,
    EXPECTED_COMMIT_SUBJECT,
    EXECUTION_LOCK_SCHEMA,
    ARTIFACT_ROOT_IDENTITY_SCHEMA,
    ARTIFACT_ROOT_IDENTITY_NAME,
    CANONICAL_ARCHIVE_NAME,
    NATIVE_FILE_NAMES,
    APPROVED_TRACKED_PATHS,
    POLICY_ORDER,
    POST_FILE_NAMES,
    POST_NATIVE_R1_IDENTITY,
    POST_R1_FILE_NAMES,
    PREEXISTING_MANIFEST_SHA256,
    R2_EXECUTION_LOCK_NAME,
    R2_REPORT_NAME,
    R2_STATUS_NAME,
    R3_REPORT_NAME,
    R3_STATUS_NAME,
    R4_REPORT_NAME,
    R4_STATUS_NAME,
    R5_REPORT_NAME,
    R5_STATUS_NAME,
    R6_REPORT_NAME,
    R6_STATUS_NAME,
    Phase4RunnerError,
    SYSTEM_MODES,
    _invalid_policy_rows,
    _jsonable,
    _fixed_rtklib_proxy_matches,
    _fresh_reproduction_commands,
    _artifact_root_identity_payload,
    _canonical_archive_preserves_pending,
    _load_r1_post_summary,
    _prepare_fresh_artifact_root,
    _required_sha256,
    _resource_probe,
    _read_part,
    _scrub_runtime,
    _write_part,
    _validate_committed_provenance_state,
    _validate_committed_worktree_status,
    _validated_external_file,
    finalize_r1_pending_reports,
    finalize_canonical_after_review,
    load_contract,
    load_paths,
    preflight_phase4,
    validate_native_freeze,
    validate_post_native_freeze,
    validate_post_native_r1_freeze,
)
from legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend import RawxEpoch


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LOCAL_PATHS = REPOSITORY_ROOT / "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"


def test_contract_closes_declared_policy_and_output_inventory():
    contract = load_contract()
    assert contract["implemented_policy_identity"] == POLICY_IDENTITY
    assert contract["implemented_reproduction_level"] == REPRODUCTION_LEVEL
    assert contract["paper_exact_policy_status"] == "NOT_IMPLEMENTED_UNDER_SPECIFIED"
    assert contract["runtime_topology"]["native_files"] == NATIVE_FILE_NAMES
    assert contract["runtime_topology"]["post_native_files"] == POST_FILE_NAMES
    assert contract["runtime_topology"]["post_native_r1"]["files"] == (
        POST_R1_FILE_NAMES
    )
    assert contract["post_native_diagnostics"]["rtklib"][
        "corrected_revision"
    ] == POST_NATIVE_R1_IDENTITY
    assert contract["execution_provenance"]["committed_mode"][
        "exact_commit_subject"
    ] == EXPECTED_COMMIT_SUBJECT
    assert contract["execution_provenance"]["committed_mode"][
        "execution_lock_schema"
    ] == EXECUTION_LOCK_SCHEMA
    assert contract["execution_provenance"]["fresh_artifact_root"][
        "role"
    ] == "PHASE4_OUTPUT_AND_REPORT_LAYOUT_ONLY"
    assert contract["runtime_topology"]["canonical_transaction"][
        "exact_path_install"
    ] == "CAS_TEMP_FSYNC_SAME_DIRECTORY_REPLACE"
    assert contract["runtime_topology"]["canonical_transaction"][
        "two_file_recovery"
    ] == "ARCHIVE_BACKED_IDEMPOTENT_RESUME"
    assert contract["runtime_topology"]["canonical_transaction"][
        "pre_mutation_freeze_validation"
    ] == ["NATIVE", "ORIGINAL_POST_NATIVE", "CORRECTED_R1_POST_NATIVE"]
    assert contract["runtime_topology"]["canonical_transaction"][
        "deterministic_temporary_paths_inspected_before_mutation"
    ] is True
    assert contract["runtime_topology"]["canonical_transaction"][
        "archive_writer"
    ] == "FINAL_DIRECTORY_EXCLUSIVE_MKDIR_DIRECT_XB_FSYNC_MANIFEST_LAST"
    assert contract["runtime_topology"]["canonical_transaction"][
        "archive_nested_atomic_helper_used"
    ] is False
    assert contract["declared_par_policy"]["primary_gates"][
        "objective_equivalence"
    ]["acceptance_convention"] == "SECOND_OVER_BEST_GE_THRESHOLD"
    assert contract["declared_par_policy"]["primary_gates"][
        "objective_equivalence"
    ]["prompt_literal_conflict"].startswith("BEST_OVER_SECOND_GE_3_IS_IMPOSSIBLE")
    assert len(contract["declared_par_policy"][
        "sensitivity_one_at_a_time_no_selection"
    ]) == 7
    assert contract["algorithm"]["timeout_clock"] == "PARENT_PROCESS_CPU_TIME"
    comparison = contract["parallel_execution"][
        "determinism_comparison_excludes_only"
    ]
    assert comparison["runtime_fields"] == [
        "runtime_seconds", "subset_runtime_seconds", "mode_runtime_seconds",
    ]
    assert "branch_and_bound_nodes_expanded" in comparison[
        "incomplete_timeout_progress_fields"
    ]
    assert contract["parallel_execution"]["internal_epoch_shard_writer"] == (
        "DIRECT_O_EXCL_COMPLETE_WRITE_FLUSH_FSYNC_SELF_HASHED_ENVELOPE"
    )


def test_policy_mode_epoch_row_conservation_constants():
    assert POLICY_ORDER == (
        FAR_POLICY_IDENTITY, POLICY_IDENTITY,
        *(policy.policy_identity for policy in SENSITIVITY_POLICIES),
    )
    assert len(POLICY_ORDER) == 9
    assert len(SYSTEM_MODES) == 3
    assert EXPECTED_PAIR_COUNT == 1509
    assert EXPECTED_HEADING_ROWS == 1509 * 9 * 3
    assert AUTHORIZED_WORKERS == 16


def test_invalid_epoch_conserves_all_policy_rows_and_labels():
    epoch = RawxEpoch(100.0, 2200, 18, 0, 1, ())
    rows = _invalid_policy_rows(
        system_mode="GPS_DUAL_FREQUENCY", epoch_index=7, epoch=epoch,
        failure_code="SYNTHETIC_FAILURE", failure_detail="unit test",
        mode_runtime_seconds=0.1,
    )
    assert [row["policy_identity"] for row in rows] == list(POLICY_ORDER)
    assert all(row["solution_state"] == "INVALID" for row in rows)
    assert all(row["ambiguity_correctness_known"] is False for row in rows)
    assert all(row["failure_code"] == "SYNTHETIC_FAILURE" for row in rows)


def test_scientific_determinism_scrubber_removes_only_runtime_fields():
    value = {
        "epoch_index": 1, "runtime_seconds": 0.1,
        "nested": [{"mode_runtime_seconds": 0.2, "best_objective": 3.0}],
    }
    scrubbed = _scrub_runtime(value)
    assert scrubbed == {"epoch_index": 1, "nested": [{"best_objective": 3.0}]}


def test_determinism_scrubber_excludes_only_uncertified_timeout_progress():
    def payload(nodes, frontier, best):
        return {
            "solution_state": "INVALID",
            "failure_code": "SEARCH_TIMEOUT",
            "active_ambiguity_identities": ["GPS:G02:GPS_L1:pivot=G01"],
            "best_integer_ambiguities": [best],
            "search_certificate": {
                "termination_reason": "SEARCH_TIMEOUT",
                "global_optimum_certified": False,
                "runtime_budget_exhausted": True,
                "branch_and_bound_nodes_expanded": nodes,
                "frontier_lower_bound_at_termination": frontier,
                "best_total_objective": float(best),
                "lambda_seed_count_requested": 8,
                "candidate_cap_applied": False,
            },
        }

    left = _scrub_runtime(payload(10, 1.0, 20))
    right = _scrub_runtime(payload(99, 9.0, 40))
    assert left == right
    assert left["solution_state"] == "INVALID"
    assert left["search_certificate"]["termination_reason"] == "SEARCH_TIMEOUT"
    assert left["search_certificate"]["global_optimum_certified"] is False
    changed_state = payload(10, 1.0, 20)
    changed_state["solution_state"] = "FAR_REJECTED"
    assert _scrub_runtime(changed_state) != left

    certified = payload(10, 1.0, 20)
    certified["solution_state"] = "FAR_REJECTED"
    certified["failure_code"] = "DECLARED_POLICY_GATES_NOT_SATISFIED"
    certified["search_certificate"].update({
        "termination_reason": "GLOBAL_BOUND_CERTIFIED",
        "global_optimum_certified": True,
        "runtime_budget_exhausted": False,
    })
    certified_scrubbed = _scrub_runtime(certified)
    assert certified_scrubbed["best_integer_ambiguities"] == [20]
    assert certified_scrubbed["search_certificate"][
        "branch_and_bound_nodes_expanded"
    ] == 10


def test_epoch_shard_exclusive_create_and_fail_closed_validation(tmp_path):
    payload = {
        "schema_version": "horizontal_literature.phase4.epoch_part.payload.v1",
        "epoch_index": 0, "gps_week": 2200, "gps_tow_seconds": 100.0,
        "modes": [{"system_mode": mode} for mode in SYSTEM_MODES],
    }
    path = tmp_path / "epoch_0000.json"
    _write_part(path, "fingerprint", payload)
    assert _read_part(path, "fingerprint", 0) == payload
    with pytest.raises(Phase4RunnerError, match="no-replace collision"):
        _write_part(path, "fingerprint", payload)

    corrupt = tmp_path / "epoch_0001.json"
    payload_one = {**payload, "epoch_index": 1}
    _write_part(corrupt, "fingerprint", payload_one)
    envelope = json.loads(corrupt.read_text(encoding="utf-8"))
    envelope["payload"]["gps_week"] = 2201
    corrupt.write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(Phase4RunnerError, match="payload hash mismatch"):
        _read_part(corrupt, "fingerprint", 1)

    partial = tmp_path / "epoch_0002.json"
    partial.write_text('{"schema_version":', encoding="utf-8")
    with pytest.raises(Phase4RunnerError, match="partial or unreadable"):
        _read_part(partial, "fingerprint", 2)


def test_rtklib_uses_exact_frozen_plus_2ms_proxy_key_without_search():
    proxies = {
        0: {
            "gps_week": 2408, "gps_tow_seconds": 460873.998,
            "rawx_itow_ms": 460873998, "proxy_itow_ms": 460874000,
            "hpposecef_offset_receiver1_ms": 2,
            "hpposecef_offset_receiver2_ms": 2,
        },
        1: {
            "gps_week": 2408, "gps_tow_seconds": 460874.198,
            "rawx_itow_ms": 460874198, "proxy_itow_ms": 460874200,
            "hpposecef_offset_receiver1_ms": 2,
            "hpposecef_offset_receiver2_ms": 2,
        },
    }
    exact = {"gps_week": 2408, "gps_tow_seconds": 460874.000}
    near_but_forbidden = {"gps_week": 2408, "gps_tow_seconds": 460874.199}
    matches, matched_raw, missing_raw = _fixed_rtklib_proxy_matches(
        [exact, near_but_forbidden], proxies,
    )
    assert matches == [(exact, proxies[0])]
    assert matched_raw == {(2408, 460873.998)}
    assert missing_raw == [(2408, 460874.198)]


def test_committed_provenance_accepts_exact_lock_and_rejects_unrelated_drift():
    hashes = {path: f"hash-{index}" for index, path in enumerate(APPROVED_TRACKED_PATHS)}
    runtime_fingerprint = "runtime-content-fingerprint"
    lock = {
        "schema_version": EXECUTION_LOCK_SCHEMA,
        "task_start_head": "82b8035863ab3f40a694d4ac0ce55c9166671941",
        "branch": EXPECTED_BRANCH,
        "required_descendant_commit_count": 1,
        "required_commit_subject": EXPECTED_COMMIT_SUBJECT,
        "approved_diff_paths": list(APPROVED_TRACKED_PATHS),
        "approved_file_sha256": dict(sorted(hashes.items())),
        "runtime_content_fingerprint": runtime_fingerprint,
        "preexisting_manifest_sha256": PREEXISTING_MANIFEST_SHA256,
        "artifact_root_policy": "EXPLICIT_FRESH_PHASE4_OUTPUT_ONLY",
    }
    accepted = _validate_committed_provenance_state(
        branch=EXPECTED_BRANCH, execution_head="f" * 40,
        ancestor_ok=True, descendant_count=1,
        commit_subject=EXPECTED_COMMIT_SUBJECT,
        diff_paths=APPROVED_TRACKED_PATHS, dirty_approved_paths=[],
        lock=lock, approved_hashes=hashes,
        runtime_content_fingerprint=runtime_fingerprint,
    )
    assert accepted["approved_paths_clean"] is True
    with pytest.raises(Phase4RunnerError, match="diff scope drift"):
        _validate_committed_provenance_state(
            branch=EXPECTED_BRANCH, execution_head="f" * 40,
            ancestor_ok=True, descendant_count=1,
            commit_subject=EXPECTED_COMMIT_SUBJECT,
            diff_paths=(*APPROVED_TRACKED_PATHS, "unrelated.txt"),
            dirty_approved_paths=[], lock=lock, approved_hashes=hashes,
            runtime_content_fingerprint=runtime_fingerprint,
        )
    with pytest.raises(Phase4RunnerError, match="unrelated dirty drift"):
        _validate_committed_worktree_status([(" M", "unrelated.txt")])


def test_local_paths_resolve_only_named_phase4_stage_when_available():
    if not LOCAL_PATHS.is_file():
        pytest.skip("machine-local clean paths config is absent")
    paths = load_paths(LOCAL_PATHS)
    assert paths.native_root.name == "C00"
    assert paths.native_root.parent.name == "05_EXT04_WU2025_MODULE"
    assert paths.final_report.name == "PHASE4_EXT04_C00_REPORT.md"
    assert paths.final_status.name == "PHASE4_STATUS.json"
    assert paths.post_r1_root.name == POST_NATIVE_R1_IDENTITY
    assert paths.r1_report.name == "PHASE4_EXT04_C00_R1_REPORT.md"
    assert paths.r1_status.name == "PHASE4_STATUS_R1.json"
    assert paths.r2_report.name == R2_REPORT_NAME
    assert paths.r2_status.name == R2_STATUS_NAME
    assert paths.r3_report.name == R3_REPORT_NAME
    assert paths.r3_status.name == R3_STATUS_NAME
    assert paths.r4_report.name == R4_REPORT_NAME
    assert paths.r4_status.name == R4_STATUS_NAME
    assert paths.r5_report.name == R5_REPORT_NAME
    assert paths.r5_status.name == R5_STATUS_NAME
    assert paths.r6_report.name == R6_REPORT_NAME
    assert paths.r6_status.name == R6_STATUS_NAME
    assert paths.execution_lock.name == R2_EXECUTION_LOCK_NAME
    assert paths.paper_pdf.name == "EXT04_WU2025_PAPER.pdf"


def test_fresh_artifact_root_changes_only_phase4_outputs_and_resumes_exactly(tmp_path):
    if not LOCAL_PATHS.is_file():
        pytest.skip("machine-local clean paths config is absent")
    configured = load_paths(LOCAL_PATHS)
    fresh = tmp_path / "fresh-phase4"
    overridden = load_paths(LOCAL_PATHS, artifact_root=fresh)
    assert overridden.stage_root == fresh
    assert overridden.configured_stage_root == configured.stage_root
    assert overridden.clean_root == configured.clean_root
    assert overridden.raw_root == configured.raw_root
    assert overridden.raw_hash_lock == configured.raw_hash_lock
    assert overridden.rtklib_root == configured.rtklib_root
    assert overridden.native_root.is_relative_to(fresh)
    assert overridden.execution_lock == configured.execution_lock
    identity = {
        "schema_version": ARTIFACT_ROOT_IDENTITY_SCHEMA,
        "sentinel": "exact-test-identity",
    }
    checked = _prepare_fresh_artifact_root(
        overridden, identity, resume=False, initialize=False,
    )
    assert checked["initialized"] is False
    assert not fresh.exists()
    initialized = _prepare_fresh_artifact_root(
        overridden, identity, resume=False, initialize=True,
    )
    assert initialized["initialized"] is True
    assert (fresh / ARTIFACT_ROOT_IDENTITY_NAME).is_file()
    assert overridden.native_root.is_dir()
    assert overridden.report_root.is_dir()
    resumed = _prepare_fresh_artifact_root(
        overridden, identity, resume=True, initialize=False,
    )
    assert resumed["state"] == "VALIDATED_RESUME"
    with pytest.raises(Phase4RunnerError, match="identity mismatch"):
        _prepare_fresh_artifact_root(
            overridden, {**identity, "sentinel": "drift"},
            resume=True, initialize=False,
        )


def test_artifact_root_rejects_symlink_and_nonempty_unbound_root(tmp_path):
    if not LOCAL_PATHS.is_file():
        pytest.skip("machine-local clean paths config is absent")
    target = tmp_path / "target"
    target.mkdir()
    symlink = tmp_path / "symlink"
    symlink.symlink_to(target, target_is_directory=True)
    paths = load_paths(LOCAL_PATHS, artifact_root=symlink)
    with pytest.raises(Phase4RunnerError, match="symlink"):
        _prepare_fresh_artifact_root(
            paths, {"schema_version": ARTIFACT_ROOT_IDENTITY_SCHEMA},
            resume=False, initialize=False,
        )


def test_fresh_root_lifecycle_reaches_r1_finalizer_without_absence_recheck(
    tmp_path, monkeypatch,
):
    if not LOCAL_PATHS.is_file():
        pytest.skip("machine-local clean paths config is absent")
    test_clean = tmp_path / "clean"
    (test_clean / "stages").mkdir(parents=True)
    runtime_fingerprint = "c" * 64
    source_fingerprint = "d" * 64
    fresh = (
        test_clean / "stages"
        / f"REPRO_PHASE4_EXT04_WU2025_C00_{runtime_fingerprint[:16]}"
    )
    paths = replace(
        load_paths(LOCAL_PATHS, artifact_root=fresh), clean_root=test_clean,
    )
    input_root = tmp_path / "inputs"
    input_root.mkdir()
    lock = input_root / "PHASE4_EXT04_EXECUTION_LOCK_R2F.json"
    lock.write_text('{"fixture":"exact-lock"}\n', encoding="utf-8")
    lock_sha = hashlib.sha256(lock.read_bytes()).hexdigest()
    manifest = input_root / "EXT04_PREEXISTING_STAGE_HASH_MANIFEST.sha256"
    manifest.write_text("hash-only-fixture\n", encoding="utf-8")
    manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
    identity = _artifact_root_identity_payload(
        paths, source_fingerprint=source_fingerprint,
        runtime_content_fingerprint=runtime_fingerprint,
        execution_head="82b8035863ab3f40a694d4ac0ce55c9166671941",
        execution_lock_sha256=lock_sha,
        preexisting_manifest_path=manifest,
        preexisting_manifest_sha256=manifest_sha,
    )

    checked = _prepare_fresh_artifact_root(
        paths, identity, resume=False, initialize=False,
    )
    assert checked["state"] == "VALIDATED_ABSENT_NOT_INITIALIZED"
    assert not fresh.exists()
    initialized = _prepare_fresh_artifact_root(
        paths, identity, resume=False, initialize=True,
    )
    assert initialized["state"] == "INITIALIZED_FROM_ABSENT"

    attempt = paths.native_root / ".EXT04_ATTEMPT_fixture"
    attempt.mkdir()
    (attempt / "RESOURCE_DETERMINISM_AND_EQUIVALENCE_PROBE.json").write_text(
        '{"state":"PROBE_COMPLETE"}\n', encoding="utf-8",
    )
    assert _prepare_fresh_artifact_root(
        paths, identity, resume=True, initialize=False,
    )["state"] == "VALIDATED_RESUME"

    native_summary = {
        "unsupported_submodes": [
            "UNSUPPORTED_SUBMODE_NO_GALILEO_BROADCAST_EPHEMERIS",
        ],
        "policy_summary": [], "row_counts": {}, "resource_probe": {},
        "worker_determinism": {}, "EXT01_core_equivalence": {},
    }
    for key in ("native_summary", "native_freeze"):
        path = paths.native_root / NATIVE_FILE_NAMES[key]
        path.write_text(
            json.dumps(native_summary if key == "native_summary" else {
                "state": "NATIVE_FROZEN",
            }),
            encoding="utf-8",
        )
    (paths.native_root / POST_FILE_NAMES["post_native_freeze"]).write_text(
        '{"state":"ORIGINAL_POST_FROZEN"}\n', encoding="utf-8",
    )
    paths.post_r1_root.mkdir()
    (paths.post_r1_root / POST_R1_FILE_NAMES["post_native_freeze"]).write_text(
        '{"state":"R1_POST_FROZEN"}\n', encoding="utf-8",
    )
    assert _prepare_fresh_artifact_root(
        paths, identity, resume=True, initialize=False,
    )["identity_sha256"] == initialized["identity_sha256"]

    post_summary = {
        "proxy_summary": {
            "accepted_proxy_row_count": 0,
            "proxy_inconsistent_above_30_deg_count": 0,
            "groups": [],
        },
        "trace_summary": [], "fractional_phase_group_count": 0,
        "rtklib_diagnostic": {"status": "COMPLETE", "matched_proxy_count": 653},
    }
    monkeypatch.setattr(
        phase4_runner, "validate_native_freeze",
        lambda _root: {"state": "NATIVE_FROZEN"},
    )
    monkeypatch.setattr(
        phase4_runner, "validate_post_native_freeze",
        lambda _root: {"state": "ORIGINAL_POST_FROZEN"},
    )
    monkeypatch.setattr(
        phase4_runner, "validate_post_native_r1_freeze",
        lambda _root: {"state": "R1_POST_FROZEN"},
    )
    monkeypatch.setattr(
        phase4_runner, "_load_r1_post_summary", lambda _root: post_summary,
    )
    monkeypatch.setattr(
        phase4_runner, "_terminal_scientific_status",
        lambda _native, _post: (
            phase4_runner.PASS_POOR, {"FAR_and_primary_PAR_accepted_count": 0},
        ),
    )
    monkeypatch.setattr(
        phase4_runner, "_method_preservation_proof",
        lambda _preflight: {"unchanged": True, "changed_paths": []},
    )
    monkeypatch.setattr(
        phase4_runner, "_failed_r5_canonical_attempt_evidence",
        lambda _report_root: {
            "identity": "FAILED_R5_CANONICAL_ARCHIVE_PUBLICATION_ATTEMPT",
            "preserved_byte_for_byte": True,
        },
    )
    resumed = _prepare_fresh_artifact_root(
        paths, identity, resume=True, initialize=False,
    )
    preflight = SimpleNamespace(
        paths=paths, contract=load_contract(),
        code_commit="82b8035863ab3f40a694d4ac0ce55c9166671941",
        task_start_head="82b8035863ab3f40a694d4ac0ce55c9166671941",
        execution_head="82b8035863ab3f40a694d4ac0ce55c9166671941",
        provenance_mode="DEVELOPMENT_TASK_START_HEAD_BOUNDED_ADDITIONS",
        source_fingerprint=source_fingerprint,
        runtime_content_fingerprint=runtime_fingerprint,
        execution_lock_evidence={
            "path": str(lock), "sha256": lock_sha, "validated": True,
        },
        preexisting_manifest_path=manifest,
        preexisting_manifest_sha256=manifest_sha,
        artifact_root_evidence=resumed,
    )
    commands = _fresh_reproduction_commands(preflight)
    assert fresh.exists()
    assert commands["artifact_root"] == str(fresh)
    assert commands["artifact_root_filesystem_probed_during_rendering"] is False
    result = finalize_r1_pending_reports(
        preflight, focused_tests="PASS", full_tests="PASS",
        focused_test_summary="fixture focused PASS",
        full_test_summary="fixture full PASS",
    )
    assert result["review_gate"] == "PENDING_SEVENTH_INDEPENDENT_REVIEW"
    assert paths.r6_report.is_file()
    assert paths.r6_status.is_file()
    assert json.loads(paths.r6_status.read_text(encoding="utf-8"))[
        "exact_reproduction_commands"
    ]["artifact_root_filesystem_probed_during_rendering"] is False
    assert _prepare_fresh_artifact_root(
        paths, identity, resume=True, initialize=False,
    )["identity_sha256"] == initialized["identity_sha256"]
    with pytest.raises(Phase4RunnerError, match="not absent or empty"):
        _prepare_fresh_artifact_root(
            paths, identity, resume=False, initialize=False,
        )
    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "unexpected").write_text("collision", encoding="utf-8")
    paths = load_paths(LOCAL_PATHS, artifact_root=nonempty)
    with pytest.raises(Phase4RunnerError, match="not absent or empty"):
        _prepare_fresh_artifact_root(
            paths, {"schema_version": ARTIFACT_ROOT_IDENTITY_SCHEMA},
            resume=False, initialize=False,
        )


def test_external_lock_hash_is_explicit_and_path_independent(tmp_path):
    lock = tmp_path / "external-lock.json"
    lock.write_text('{"schema_version":"test"}\n', encoding="utf-8")
    digest = hashlib.sha256(lock.read_bytes()).hexdigest()
    observed_path, observed_hash = _validated_external_file(
        lock, digest, label="execution lock",
    )
    assert observed_path == lock
    assert observed_hash == digest
    with pytest.raises(Phase4RunnerError, match="SHA-256 mismatch"):
        _validated_external_file(lock, "0" * 64, label="execution lock")
    with pytest.raises(Phase4RunnerError, match="exact SHA-256"):
        _required_sha256("short", "execution lock")


def test_canonical_exact_path_archive_cas_and_partial_recovery(
    tmp_path, monkeypatch,
):
    if not LOCAL_PATHS.is_file():
        pytest.skip("machine-local clean paths config is absent")
    stage = tmp_path / "stage"
    report_root = stage / "11_REPORT"
    native_root = stage / "05_EXT04_WU2025_MODULE/C00"
    report_root.mkdir(parents=True)
    native_root.mkdir(parents=True)
    lock = report_root / "PHASE4_EXT04_EXECUTION_LOCK_R2F.json"
    lock.write_text('{"fixture":"final-lock"}\n', encoding="utf-8")
    lock_sha = hashlib.sha256(lock.read_bytes()).hexdigest()
    base = load_paths(LOCAL_PATHS)
    paths = replace(
        base,
        configured_stage_root=stage, stage_root=stage,
        artifact_root_overridden=False, native_root=native_root,
        report_root=report_root,
        final_report=report_root / "PHASE4_EXT04_C00_REPORT.md",
        final_status=report_root / "PHASE4_STATUS.json",
        post_r1_root=native_root / POST_NATIVE_R1_IDENTITY,
        r1_report=report_root / "PHASE4_EXT04_C00_R1_REPORT.md",
        r1_status=report_root / "PHASE4_STATUS_R1.json",
        r2_report=report_root / R2_REPORT_NAME,
        r2_status=report_root / R2_STATUS_NAME,
        r3_report=report_root / R3_REPORT_NAME,
        r3_status=report_root / R3_STATUS_NAME,
        r4_report=report_root / R4_REPORT_NAME,
        r4_status=report_root / R4_STATUS_NAME,
        r5_report=report_root / R5_REPORT_NAME,
        r5_status=report_root / R5_STATUS_NAME,
        r6_report=report_root / R6_REPORT_NAME,
        r6_status=report_root / R6_STATUS_NAME,
        canonical_archive_root=report_root / CANONICAL_ARCHIVE_NAME,
        execution_lock=lock,
    )
    payloads = {
        "original_report": b"original report\n",
        "original_status": b'{"state":"original"}\n',
        "R1_report": b"R1 report\n",
        "R1_status": b'{"state":"R1"}\n',
        "R2_report": b"R2 report\n",
        "R2_status": b'{"state":"R2"}\n',
        "R3_report": b"R3 report\n",
        "R3_status": b'{"state":"R3"}\n',
        "R4_report": b"R4 report\n",
        "R4_status": b'{"state":"R4"}\n',
        "R5_report": b"R5 report\n",
        "R5_status": b'{"state":"R5"}\n',
        "R6_report": b"R6 report\n",
        "R6_status": (
            json.dumps({
                "schema_version": "horizontal_literature.phase4.status_r6.v1",
                "review_gate": "PENDING_SEVENTH_INDEPENDENT_REVIEW",
                "terminal_status": phase4_runner.PASS_POOR,
            }, sort_keys=True) + "\n"
        ).encode("utf-8"),
    }
    source_paths = {
        "original_report": paths.final_report,
        "original_status": paths.final_status,
        "R1_report": paths.r1_report,
        "R1_status": paths.r1_status,
        "R2_report": paths.r2_report,
        "R2_status": paths.r2_status,
        "R3_report": paths.r3_report,
        "R3_status": paths.r3_status,
        "R4_report": paths.r4_report,
        "R4_status": paths.r4_status,
        "R5_report": paths.r5_report,
        "R5_status": paths.r5_status,
        "R6_report": paths.r6_report,
        "R6_status": paths.r6_status,
    }
    for name, path in source_paths.items():
        path.write_bytes(payloads[name])
    expected = {
        name: hashlib.sha256(payload).hexdigest()
        for name, payload in payloads.items()
    }
    for constant, key in (
        ("ORIGINAL_PENDING_REPORT_SHA256", "original_report"),
        ("ORIGINAL_PENDING_STATUS_SHA256", "original_status"),
        ("R1_PENDING_REPORT_SHA256", "R1_report"),
        ("R1_PENDING_STATUS_SHA256", "R1_status"),
        ("R2_PENDING_REPORT_SHA256", "R2_report"),
        ("R2_PENDING_STATUS_SHA256", "R2_status"),
        ("R3_PENDING_REPORT_SHA256", "R3_report"),
        ("R3_PENDING_STATUS_SHA256", "R3_status"),
        ("R4_PENDING_REPORT_SHA256", "R4_report"),
        ("R4_PENDING_STATUS_SHA256", "R4_status"),
        ("R5_PENDING_REPORT_SHA256", "R5_report"),
        ("R5_PENDING_STATUS_SHA256", "R5_status"),
    ):
        monkeypatch.setattr(phase4_runner, constant, expected[key])

    failed_r5 = report_root / phase4_runner.FAILED_R5_CANONICAL_ATTEMPT_NAME
    failed_r5.mkdir()
    for index in range(phase4_runner.FAILED_R5_CANONICAL_ATTEMPT_FILE_COUNT):
        (failed_r5 / f"failed-{index:02d}.bin").write_bytes(
            f"immutable-failed-R5-{index}\n".encode("ascii")
        )
    failed_files = sorted(failed_r5.iterdir(), key=lambda item: item.name)
    failed_bytes = sum(item.stat().st_size for item in failed_files)
    failed_digest = hashlib.sha256()
    for item in failed_files:
        failed_digest.update(item.name.encode("utf-8"))
        failed_digest.update(b"\0")
        failed_digest.update(hashlib.sha256(item.read_bytes()).hexdigest().encode("ascii"))
        failed_digest.update(b"\0")
    monkeypatch.setattr(
        phase4_runner, "FAILED_R5_CANONICAL_ATTEMPT_BYTES", failed_bytes,
    )
    monkeypatch.setattr(
        phase4_runner, "FAILED_R5_CANONICAL_ATTEMPT_AGGREGATE_SHA256",
        failed_digest.hexdigest(),
    )
    failed_r5_snapshot = {
        item.name: hashlib.sha256(item.read_bytes()).hexdigest()
        for item in failed_files
    }

    native_freeze_path = native_root / NATIVE_FILE_NAMES["native_freeze"]
    native_freeze_path.write_text('{"fixture":"native-freeze"}\n', encoding="utf-8")
    original_post_freeze_path = native_root / POST_FILE_NAMES["post_native_freeze"]
    original_post_freeze_path.write_text(
        '{"fixture":"original-post-freeze"}\n', encoding="utf-8",
    )
    paths.post_r1_root.mkdir()
    r1_payloads = {
        key: f"fixture {key}\n".encode("utf-8")
        for key in phase4_runner.POST_R1_FREEZE_HASH_KEYS
    }
    r1_summary = {
        "schema_version": "horizontal_literature.phase4.post_native_r1_summary.v1",
        "revision_identity": POST_NATIVE_R1_IDENTITY,
        "rtklib_diagnostic": {"matched_proxy_count": 653},
    }
    r1_payloads["post_native_summary"] = (
        json.dumps(r1_summary, sort_keys=True) + "\n"
    ).encode("utf-8")
    for key, content in r1_payloads.items():
        (paths.post_r1_root / POST_R1_FILE_NAMES[key]).write_bytes(content)
    r1_freeze_path = paths.post_r1_root / POST_R1_FILE_NAMES["post_native_freeze"]
    r1_freeze = {
        "schema_version": "horizontal_literature.phase4.post_native_r1_freeze.v2",
        "revision_identity": POST_NATIVE_R1_IDENTITY,
        "native_source_fingerprint": "fixture-native-source",
        "native_freeze_sha256": hashlib.sha256(
            native_freeze_path.read_bytes()
        ).hexdigest(),
        "original_post_freeze_sha256": hashlib.sha256(
            original_post_freeze_path.read_bytes()
        ).hexdigest(),
        "original_pending_report_sha256": expected["original_report"],
        "original_pending_status_sha256": expected["original_status"],
        "original_pending_report_state": "PRESENT_AND_HASH_PINNED",
        "original_post_preserved": True,
        "original_post_superseded_only_for_RTKLIB_metrics": True,
        "post_native_hashes": {
            key: hashlib.sha256(content).hexdigest()
            for key, content in r1_payloads.items()
        },
        "native_files_mutated": False,
        "phase_bias_calibration": False,
    }
    r1_freeze_path.write_text(
        json.dumps(r1_freeze, sort_keys=True) + "\n", encoding="utf-8",
    )

    validation_calls = {"native": 0, "post": 0}

    def validated(name, value):
        def check(_root):
            validation_calls[name] += 1
            return value
        return check

    monkeypatch.setattr(
        phase4_runner, "validate_native_freeze",
        validated("native", {"source_fingerprint": "fixture-native-source"}),
    )
    monkeypatch.setattr(
        phase4_runner, "validate_post_native_freeze",
        validated("post", {"state": "POST_FROZEN"}),
    )
    preflight = SimpleNamespace(
        paths=paths,
        execution_lock_evidence={
            "path": str(lock), "sha256": lock_sha, "validated": True,
        },
    )
    review = "Independent reviewer PASS for exact canonical publication."
    review_sha = hashlib.sha256(review.encode("utf-8")).hexdigest()
    sources = phase4_runner._canonical_expected_sources(preflight, expected)
    approved_for_test = phase4_runner._canonical_approved_payloads(
        preflight, r6_report_bytes=payloads["R6_report"],
        r6_status_bytes=payloads["R6_status"], reviewer_summary=review,
        reviewer_summary_sha256=review_sha,
        lock={"path": str(lock), "sha256": lock_sha},
    )
    manifest_for_test = phase4_runner._canonical_archive_manifest(
        preflight, sources=sources, reviewer_summary=review,
        reviewer_summary_sha256=review_sha,
        lock={"path": str(lock), "sha256": lock_sha},
        approved_report=approved_for_test[0],
        approved_status=approved_for_test[1],
    )

    # A mid-archive failure leaves a manifest-less immutable directory and
    # cannot alter either canonical target or be resumed under the same ID.
    injected_archive = report_root / "PHASE4_EXT04_PENDING_ARCHIVE_R6_INJECTED"
    canonical_before_injection = (
        paths.final_report.read_bytes(), paths.final_status.read_bytes(),
    )
    direct_writer = phase4_runner._direct_exclusive_archive_write
    injected_calls = {"count": 0}

    def fail_mid_archive(path, payload, *, expected_sha256, label):
        injected_calls["count"] += 1
        if injected_calls["count"] == 4:
            raise Phase4RunnerError("injected direct archive failure")
        direct_writer(
            path, payload, expected_sha256=expected_sha256, label=label,
        )

    monkeypatch.setattr(
        phase4_runner, "_direct_exclusive_archive_write", fail_mid_archive,
    )
    with pytest.raises(Phase4RunnerError, match="injected direct archive failure"):
        phase4_runner._install_canonical_archive(
            injected_archive, sources=sources, manifest=manifest_for_test,
            approved_report=approved_for_test[0],
            approved_status=approved_for_test[1],
        )
    assert injected_archive.is_dir()
    assert not (injected_archive / "ARCHIVE_MANIFEST.json").exists()
    assert (
        paths.final_report.read_bytes(), paths.final_status.read_bytes(),
    ) == canonical_before_injection
    monkeypatch.setattr(
        phase4_runner, "_direct_exclusive_archive_write", direct_writer,
    )
    with pytest.raises(Phase4RunnerError, match="new identity required"):
        phase4_runner._install_canonical_archive(
            injected_archive, sources=sources, manifest=manifest_for_test,
            approved_report=approved_for_test[0],
            approved_status=approved_for_test[1],
        )

    write_order = []

    def record_direct_write(path, payload, *, expected_sha256, label):
        write_order.append(Path(path).name)
        direct_writer(
            path, payload, expected_sha256=expected_sha256, label=label,
        )

    monkeypatch.setattr(
        phase4_runner, "_direct_exclusive_archive_write", record_direct_write,
    )

    def forbidden_nested_atomic(*_args, **_kwargs):
        raise AssertionError("R6 archive called forbidden nested atomic helper")

    monkeypatch.setattr(
        phase4_runner.phase2, "_atomic_write_bytes", forbidden_nested_atomic,
    )
    monkeypatch.setattr(
        phase4_runner.phase2, "_atomic_install_noreplace",
        forbidden_nested_atomic,
    )
    monkeypatch.setattr(
        phase4_runner.phase2, "_windows_dotnet_move_noreplace",
        forbidden_nested_atomic,
    )
    result = finalize_canonical_after_review(
        preflight, reviewer_verdict="APPROVED", reviewer_summary=review,
        reviewer_summary_sha256=review_sha,
        expected_pending_sha256=expected,
    )
    assert result["review_gate"] == "APPROVED"
    assert result["canonical_final_report"] == str(paths.final_report)
    assert result["canonical_final_status"] == str(paths.final_status)
    assert write_order[-1] == "ARCHIVE_MANIFEST.json"
    assert len(write_order) == len(payloads) + 3
    assert json.loads(paths.final_status.read_text(encoding="utf-8"))[
        "review_gate"
    ] == "APPROVED"
    manifest = json.loads(
        (paths.canonical_archive_root / "ARCHIVE_MANIFEST.json").read_text(
            encoding="utf-8",
        )
    )
    for name, original in payloads.items():
        archived = paths.canonical_archive_root / manifest[
            "pending_files"
        ][name]["archive_name"]
        assert archived.read_bytes() == original
    assert len(manifest["pending_files"]) == 14
    assert len(manifest["approved_payloads"]) == 2
    assert phase4_runner._failed_r5_canonical_attempt_evidence(report_root)[
        "preserved_byte_for_byte"
    ] is True
    assert {
        item.name: hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(failed_r5.iterdir(), key=lambda value: value.name)
    } == failed_r5_snapshot
    assert _canonical_archive_preserves_pending(
        report_root, {
            "original_report": expected["original_report"],
            "original_status": expected["original_status"],
        },
    )
    assert min(validation_calls.values()) >= 2
    validate_post_native_r1_freeze(paths.native_root)

    again = finalize_canonical_after_review(
        preflight, reviewer_verdict="APPROVED", reviewer_summary=review,
        reviewer_summary_sha256=review_sha,
        expected_pending_sha256=expected,
    )
    assert again["transaction_states"] == {
        "report": "ALREADY_APPROVED", "status": "ALREADY_APPROVED",
    }

    paths.final_status.write_bytes(payloads["original_status"])
    recovered = finalize_canonical_after_review(
        preflight, reviewer_verdict="APPROVED", reviewer_summary=review,
        reviewer_summary_sha256=review_sha,
        expected_pending_sha256=expected,
    )
    assert recovered["transaction_states"] == {
        "report": "ALREADY_APPROVED", "status": "INSTALLED",
    }

    approved_report = paths.final_report.read_bytes()
    approved_status = paths.final_status.read_bytes()
    paths.final_report.write_bytes(payloads["original_report"])
    reverse = finalize_canonical_after_review(
        preflight, reviewer_verdict="APPROVED", reviewer_summary=review,
        reviewer_summary_sha256=review_sha,
        expected_pending_sha256=expected,
    )
    assert reverse["transaction_states"] == {
        "report": "INSTALLED", "status": "ALREADY_APPROVED",
    }

    # Every retry revalidates the complete R1 freeze before either target can
    # move, including the frozen corrected summary payload itself.
    paths.final_report.write_bytes(payloads["original_report"])
    summary_path = paths.post_r1_root / POST_R1_FILE_NAMES["post_native_summary"]
    summary_original = summary_path.read_bytes()
    summary_path.write_bytes(b'{"corrupt":"R1-summary"}\n')
    targets_before = (paths.final_report.read_bytes(), paths.final_status.read_bytes())
    with pytest.raises(Phase4RunnerError, match="post-native R1 hash mismatch"):
        finalize_canonical_after_review(
            preflight, reviewer_verdict="APPROVED", reviewer_summary=review,
            reviewer_summary_sha256=review_sha,
            expected_pending_sha256=expected,
        )
    assert (paths.final_report.read_bytes(), paths.final_status.read_bytes()) == targets_before
    summary_path.write_bytes(summary_original)

    freeze_original = r1_freeze_path.read_bytes()
    corrupted_freeze = dict(r1_freeze)
    corrupted_freeze["native_files_mutated"] = True
    r1_freeze_path.write_text(
        json.dumps(corrupted_freeze, sort_keys=True) + "\n", encoding="utf-8",
    )
    with pytest.raises(Phase4RunnerError, match="invalid post-native R1 freeze"):
        finalize_canonical_after_review(
            preflight, reviewer_verdict="APPROVED", reviewer_summary=review,
            reviewer_summary_sha256=review_sha,
            expected_pending_sha256=expected,
        )
    assert (paths.final_report.read_bytes(), paths.final_status.read_bytes()) == targets_before
    r1_freeze_path.write_bytes(freeze_original)

    # An unknown CAS temp is rejected even when that target already
    # contains its approved payload.
    paths.final_report.write_bytes(approved_report)
    assert paths.final_status.read_bytes() == approved_status
    report_temp = phase4_runner._canonical_cas_temporary(
        paths.final_report, approved_report,
    )
    report_temp.write_bytes(b"unknown CAS temp\n")
    with pytest.raises(Phase4RunnerError, match="CAS temporary hash mismatch"):
        finalize_canonical_after_review(
            preflight, reviewer_verdict="APPROVED", reviewer_summary=review,
            reviewer_summary_sha256=review_sha,
            expected_pending_sha256=expected,
        )
    assert paths.final_report.read_bytes() == approved_report
    assert paths.final_status.read_bytes() == approved_status
    report_temp.unlink()

    paths.final_status.write_bytes(b"unexpected collision\n")
    with pytest.raises(Phase4RunnerError, match="CAS source hash mismatch"):
        finalize_canonical_after_review(
            preflight, reviewer_verdict="APPROVED", reviewer_summary=review,
            reviewer_summary_sha256=review_sha,
            expected_pending_sha256=expected,
        )
    missing = dict(expected)
    missing.pop("R6_status")
    with pytest.raises(Phase4RunnerError, match="inventory drift"):
        finalize_canonical_after_review(
            preflight, reviewer_verdict="APPROVED", reviewer_summary=review,
            reviewer_summary_sha256=review_sha,
            expected_pending_sha256=missing,
        )


def test_report_jsonable_converts_nested_dates_and_datetimes_to_iso_strings():
    value = {
        "publication_date": date(2025, 10, 31),
        "sealed_at": datetime(2026, 8, 16, 3, 4, 5, tzinfo=timezone.utc),
        "nested": [date(2026, 8, 17)],
    }
    converted = _jsonable(value)
    assert converted == {
        "publication_date": "2025-10-31",
        "sealed_at": "2026-08-16T03:04:05+00:00",
        "nested": ["2026-08-17"],
    }
    assert json.loads(json.dumps(converted)) == converted


def test_r1_finalizer_summary_selector_never_reads_defective_original(tmp_path):
    (tmp_path / "EXT04_C00_POST_NATIVE_SUMMARY.json").write_text(
        json.dumps({"defective_original": True}), encoding="utf-8",
    )
    r1_root = tmp_path / POST_NATIVE_R1_IDENTITY
    r1_root.mkdir()
    corrected = {
        "schema_version": "horizontal_literature.phase4.post_native_r1_summary.v1",
        "revision_identity": POST_NATIVE_R1_IDENTITY,
        "rtklib_diagnostic": {"matched_proxy_count": 653},
    }
    (r1_root / POST_R1_FILE_NAMES["post_native_summary"]).write_text(
        json.dumps(corrected), encoding="utf-8",
    )
    assert _load_r1_post_summary(tmp_path) == corrected
    corrected["revision_identity"] = "DRIFT"
    (r1_root / POST_R1_FILE_NAMES["post_native_summary"]).write_text(
        json.dumps(corrected), encoding="utf-8",
    )
    with pytest.raises(Phase4RunnerError, match="identity drift"):
        _load_r1_post_summary(tmp_path)


def test_resource_probe_fixes_16_and_rejects_20_when_local_paths_available():
    if not LOCAL_PATHS.is_file():
        pytest.skip("machine-local clean paths config is absent")
    probe = _resource_probe(load_paths(LOCAL_PATHS))
    assert probe["selected_workers"] == 16
    assert probe["workers_16_authorized"] is True
    assert probe["workers_20_authorized"] is False


def test_preflight_hash_only_collision_and_paper_closure_when_available():
    if not LOCAL_PATHS.is_file():
        pytest.skip("machine-local clean paths config is absent")
    paths = load_paths(LOCAL_PATHS)
    manifest = paths.native_root / "EXT04_PREEXISTING_STAGE_HASH_MANIFEST.sha256"
    if not manifest.is_file():
        pytest.skip("frozen external C00 collision manifest is absent")
    preflight = preflight_phase4(
        LOCAL_PATHS, allow_native_existing=True, allow_report_existing=True,
    )
    assert preflight.code_commit == "82b8035863ab3f40a694d4ac0ce55c9166671941"
    assert preflight.paper_hashes["pdf_sha256"] == (
        "b2a06a0ce0b9ad17562e3ac996afaf037d2461f41620cdac225916370729f2a9"
    )
    assert preflight.contract["runtime_topology"]["preexisting_hash_manifest"][
        "sha256"
    ] == PREEXISTING_MANIFEST_SHA256
    assert len(preflight.runtime_source_hashes) == 10
    native_freeze = validate_native_freeze(paths.native_root)
    post_freeze = validate_post_native_freeze(paths.native_root)
    assert native_freeze["source_fingerprint"] == (
        "0dbe7a2f44f537e5f685f6aa013ec8f01f6e37b379a2a16eb2f62f6c9b62f6c0"
    )
    assert post_freeze["source_fingerprint"] == native_freeze["source_fingerprint"]
    assert post_freeze["native_hashes_revalidated"] is True
    assert post_freeze["native_files_mutated"] is False
    if paths.post_r1_root.is_dir():
        assert validate_post_native_r1_freeze(paths.native_root)[
            "original_post_preserved"
        ] is True


def test_prohibited_native_inputs_are_all_false():
    flags = load_contract()["data_flags"]
    prohibited = (
        "trace_used_online", "HPPOSECEF_solver_input",
        "status_baseline_solver_input", "Go2_yaw_solver_input",
        "EXT01_output_solver_input", "EXT02_output_solver_input",
        "EXT03_output_solver_input", "LegSA_output_solver_input",
        "RTKLIB_diagnostic_output_solver_input", "phase_bias_calibration",
    )
    assert all(flags[name] is False for name in prohibited)
    assert flags["old_runtime_input_count"] == 0


def test_cli_source_contains_no_next_phase_runner_names():
    cli = (
        REPOSITORY_ROOT
        / "scripts/paper_rebuild/run_horizontal_literature_phase4.py"
    ).read_text(encoding="utf-8")
    assert "canonical541" not in cli.lower()
    assert "classic-18" not in cli.lower()
    assert "common_backbone" not in cli.lower()
