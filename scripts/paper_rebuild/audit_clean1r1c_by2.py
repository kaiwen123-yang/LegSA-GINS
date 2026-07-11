#!/usr/bin/env python3
"""Final fail-closed audit for CLEAN1R1C V2 fresh BY2 evidence."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.evidence import verify_by2_raw_22, write_raw_audit
from legsa_gins.paper_rebuild.evaluator import load_frozen_evaluator
from legsa_gins.paper_rebuild.formal_manifest import assert_formal_run_manifest
from legsa_gins.paper_rebuild.formal_provider import load_formal_provider_bundle
from legsa_gins.paper_rebuild.formal_runner import RUN_DIRECTORY_NAMES
from legsa_gins.paper_rebuild.manifest import git_code_state, sha256_file, write_json_atomic
from legsa_gins.paper_rebuild.methods import FORMAL_METHOD_ORDER, load_method_catalog
from legsa_gins.paper_rebuild.paths import (
    assert_clean1_path_contract,
    clean1_stage_root,
    load_clean_paths,
)
from legsa_gins.paper_rebuild.protocol import load_clean1_protocol, load_frozen_window


PROTOCOL_ID = "CLEAN1_BY2_CLEAN_NORMAL_V2_KICK_ALIGNED"
STAGE_ID = (
    "CLEAN1R1C_FROZEN_PROTOCOL_DIRECT_REIMPLEMENTATION_AND_BY2_FORMAL_EXECUTION"
)
PASS_STATUS = (
    "PASS_CLEAN1_BY2_KICK_ALIGNED_FOUR_METHOD_FRESH_EVIDENCE_READY_FOR_HUMAN_REVIEW"
)
PENDING_FINALIZATION_STATUS = "ALL_GATES_TRUE_PENDING_ATOMIC_FINALIZATION"


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path.name}")
    return payload


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"Cannot write empty audit CSV: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _boolean_gate(value: Any) -> bool:
    return value is True


def _verify_manifest_rows(
    stage: Path, attempt: Path, rows: list[dict[str, Any]]
) -> None:
    final_prefix = "08_EVIDENCE_AUDIT/FINALIZED/"
    for row in rows:
        relative = str(row["relative_path"])
        source = (
            attempt / relative.removeprefix(final_prefix)
            if relative.startswith(final_prefix)
            else stage / relative
        )
        if (
            not source.is_file()
            or sha256_file(source) != row["sha256"]
            or source.stat().st_size != int(row["size_bytes"])
        ):
            raise RuntimeError("FAIL_CLEAN1_FINAL_OUTPUT_OR_METRIC_CROSSCHECK")


def _finalize_evidence(
    stage: Path,
    audit: dict[str, Any],
    markdown: str,
    reviewer_text: str,
) -> Path:
    """Publish PASS only by atomically renaming a fully verified hidden attempt."""

    audit_dir = stage / "08_EVIDENCE_AUDIT"
    final = audit_dir / "FINALIZED"
    if final.exists():
        raise RuntimeError("CLEAN1R1C final evidence already exists")
    existing_attempts = sorted(audit_dir.glob(".FINALIZED.attempt-*"))
    if existing_attempts:
        raise RuntimeError("BLOCKED_CLEAN1R1C_FINALIZATION_ATTEMPT_EXISTS")
    attempt = audit_dir / f".FINALIZED.attempt-{uuid.uuid4().hex}"
    attempt.mkdir(parents=False, exist_ok=False)
    candidate_audit = {
        **audit,
        "terminal_status": PENDING_FINALIZATION_STATUS,
        "authorized_terminal_status_after_verified_publication": PASS_STATUS,
    }
    write_json_atomic(attempt / "FINAL_AUDIT.json", candidate_audit)
    write_json_atomic(attempt / "CLEAN1_FULL_REPORT.json", candidate_audit)
    (attempt / "CLEAN1_FULL_REPORT.md").write_text(markdown, encoding="utf-8")
    (attempt / "REVIEWER_REPORT.md").write_text(reviewer_text, encoding="utf-8")

    rows: list[dict[str, Any]] = []
    for source in sorted(path for path in stage.rglob("*") if path.is_file()):
        if attempt in source.parents or final in source.parents:
            continue
        rows.append(
            {
                "relative_path": source.relative_to(stage).as_posix(),
                "sha256": sha256_file(source),
                "size_bytes": source.stat().st_size,
                "tracked": False,
            }
        )
    for source in sorted(path for path in attempt.iterdir() if path.is_file()):
        rows.append(
            {
                "relative_path": (
                    Path("08_EVIDENCE_AUDIT/FINALIZED") / source.name
                ).as_posix(),
                "sha256": sha256_file(source),
                "size_bytes": source.stat().st_size,
                "tracked": False,
            }
        )
    manifest = attempt / "EVIDENCE_MANIFEST.csv"
    sidecar = attempt / "EVIDENCE_MANIFEST.sha256"
    _write_csv(manifest, rows)
    digest = sha256_file(manifest)
    sidecar.write_text(f"{digest}  EVIDENCE_MANIFEST.csv\n", encoding="utf-8")
    _verify_manifest_rows(stage, attempt, rows)
    if sidecar.read_text(encoding="utf-8").split()[0] != sha256_file(manifest):
        raise RuntimeError("FAIL_CLEAN1_FINAL_OUTPUT_OR_METRIC_CROSSCHECK")
    attempt.rename(final)
    write_json_atomic(
        final / "COMPLETION_SENTINEL.json",
        {
            "schema_version": "paper-rebuild-clean1r1c-completion-v1",
            "terminal_status": PASS_STATUS,
            "evidence_manifest_sha256": digest,
            "manifest_verified_before_atomic_publication": True,
            "atomic_publication": "hidden_attempt_rename_to_FINALIZED",
        },
    )
    return final


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)

    paths = load_clean_paths(args.config)
    assert_clean1_path_contract(paths, REPO_ROOT)
    if paths.provider_root.name != PROTOCOL_ID or paths.runtime_root.name != PROTOCOL_ID:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    stage = clean1_stage_root(paths)
    if not stage.is_dir():
        raise RuntimeError("BLOCKED_CLEAN1_FOUR_METHOD_SET_INCOMPLETE")

    protocol = load_clean1_protocol(REPO_ROOT / "configs/paper_rebuild/clean1_by2_clean_protocol.yaml")
    if (
        protocol.payload.get("stage_id") != STAGE_ID
        or protocol.payload.get("protocol_id") != PROTOCOL_ID
    ):
        raise RuntimeError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")
    window_path = stage / "02_PROTOCOL_FREEZE/WINDOW_CONTRACT.yaml"
    evaluator_path = stage / "02_PROTOCOL_FREEZE/EVALUATOR_CONTRACT.yaml"
    window = load_frozen_window(window_path)
    evaluator = load_frozen_evaluator(evaluator_path, require_ready=True)
    provider = load_formal_provider_bundle(paths)
    code_commit, dirty = git_code_state(paths.code_root)

    raw_summary = _json(stage / "03_DATA_HASH_AND_ROLES/BY2_RAW_22_SUMMARY.json")
    mutation = _json(stage / "03_DATA_HASH_AND_ROLES/RAW_MUTATION_AUDIT.json")
    final_raw = verify_by2_raw_22(
        paths.raw_root,
        paths.raw_hash_lock,
        expected_lock_sha256=protocol.payload["raw_hash_lock_expected_sha256"],
        expected_full_rows=protocol.payload["expected_full_lock_rows"],
        expected_by2_rows=protocol.payload["expected_by2_lock_rows"],
        audit_phase="final_evidence_audit",
    )
    write_raw_audit(
        stage / "03_DATA_HASH_AND_ROLES/BY2_RAW_22_FINAL_HASH_AUDIT.csv",
        final_raw,
    )

    catalog = load_method_catalog(REPO_ROOT / "configs/paper_rebuild/methods.yaml")
    expected_window_hash = sha256_file(window_path)
    expected_evaluator_hash = sha256_file(evaluator_path)
    run_rows: list[dict[str, Any]] = []
    run_manifests: dict[str, dict[str, Any]] = {}
    for order, (method_id, directory) in enumerate(
        zip(FORMAL_METHOD_ORDER, RUN_DIRECTORY_NAMES), start=1
    ):
        run_root = paths.runtime_root / directory
        manifest = _json(run_root / "FORMAL_RUN_MANIFEST.json")
        assert_formal_run_manifest(
            manifest,
            catalog,
            require_pass=True,
            expected_stage_id=STAGE_ID,
            expected_protocol_id=PROTOCOL_ID,
            expected_case_id="CLEAN1_BY2_CLEAN_NORMAL",
        )
        if (
            manifest.get("algorithm_id") != method_id
            or manifest.get("run_id") != directory
            or manifest.get("window_contract_hash") != expected_window_hash
            or manifest.get("evaluator_contract_hash") != expected_evaluator_hash
            or manifest.get("provider_generator_commit") != provider.generator_code_commit
        ):
            raise RuntimeError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")
        for role, filename in dict(manifest["output_files"]).items():
            output = run_root / str(filename)
            if not output.is_file() or sha256_file(output) != manifest["output_hashes"][role]:
                raise RuntimeError("FAIL_CLEAN1_FINAL_OUTPUT_OR_METRIC_CROSSCHECK")
        solver_open = _json(run_root / "logs/SOLVER_FILE_OPEN_CROSSCHECK.json")
        if not _boolean_gate(solver_open.get("passed")):
            raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
        run_manifests[method_id] = manifest
        run_rows.append(
            {
                "method_order": order,
                "algorithm_id": method_id,
                "run_id": directory,
                "terminal_status": manifest["terminal_status"],
                "terminal_pass": True,
                "module_counters_match": True,
                "runtime_seconds": manifest["runtime_seconds"],
                "eval_nav_sha256": manifest["output_hashes"]["eval_nav"],
            }
        )
    _write_csv(stage / "06_RUN_MANIFESTS/FOUR_RUN_STATUS.csv", run_rows)

    evaluation_root = stage / "07_EVALUATION/FORMAL_EVALUATION"
    summary_path = evaluation_root / "FOUR_METHOD_SUMMARY.csv"
    coverage_path = evaluation_root / "MATCH_COVERAGE.csv"
    aggregate_path = evaluation_root / "AGGREGATE_METRICS.json"
    overall_cross_path = evaluation_root / "AGGREGATE_CROSSCHECK.json"
    required_evaluation = (
        evaluation_root / "ROW_LEVEL_ERRORS.csv",
        summary_path,
        coverage_path,
        aggregate_path,
        overall_cross_path,
    )
    if any(not path.is_file() for path in required_evaluation):
        raise RuntimeError("FAIL_CLEAN1_FINAL_OUTPUT_OR_METRIC_CROSSCHECK")
    overall_cross = _json(overall_cross_path)
    if not _boolean_gate(overall_cross.get("passed")):
        raise RuntimeError("FAIL_CLEAN1_FINAL_OUTPUT_OR_METRIC_CROSSCHECK")
    summary_rows = _csv_rows(summary_path)
    coverage_rows = _csv_rows(coverage_path)
    if (
        [row.get("algorithm_id") for row in summary_rows] != list(FORMAL_METHOD_ORDER)
        or [row.get("algorithm_id") for row in coverage_rows] != list(FORMAL_METHOD_ORDER)
    ):
        raise RuntimeError("FAIL_CLEAN1_FINAL_OUTPUT_OR_METRIC_CROSSCHECK")
    for method_id, directory in zip(FORMAL_METHOD_ORDER, RUN_DIRECTORY_NAMES):
        method_root = evaluation_root / directory
        crosscheck = _json(method_root / "AGGREGATE_CROSSCHECK.json")
        read_ledger = _csv_rows(method_root / "EVALUATOR_ACTUAL_READ_LEDGER.csv")
        file_open = _json(method_root / "EVALUATOR_FILE_OPEN_CROSSCHECK.json")
        trace_rows = [row for row in read_ledger if row.get("role") == "evaluation_only_trace"]
        if (
            not _boolean_gate(crosscheck.get("passed"))
            or not trace_rows
            or not _boolean_gate(file_open.get("passed"))
        ):
            raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")

    image_suffixes = {".png", ".jpg", ".jpeg", ".svg", ".pdf"}
    paper_figure_count = sum(
        path.is_file() and path.suffix.casefold() in image_suffixes
        for path in stage.rglob("*")
    )
    provider_manifest = _json(paths.provider_root / "CLEAN_INPUT_MANIFEST.json")
    runtime_directories = sorted(
        child.name for child in paths.runtime_root.iterdir() if child.is_dir()
    )
    gates = {
        "raw_22_pre": raw_summary.get("pre_verified") == 22,
        "raw_22_post": raw_summary.get("post_verified") == 22,
        "raw_22_final": len(final_raw.verified_hashes) == 22,
        "raw_mutation_count_zero": mutation.get("raw_mutation") == 0,
        "kick_alignment_pass": _json(
            stage / "02_PROTOCOL_FREEZE/KICK_EVENT_ALIGNMENT_REPORT.json"
        ).get("kick_alignment_pass")
        is True,
        "frozen_evaluator_pass": evaluator.get("formal_metrics_authorized") is True,
        "fresh_provider_pass": provider_manifest.get("generator_code_commit") == code_commit,
        "raw_doppler_lineage_proven": provider.raw_doppler_report.get(
            "raw_doppler_backend_lineage_proven"
        )
        is True,
        "formal_run_count_four": len(run_manifests) == 4,
        "runtime_directory_set_exact": runtime_directories
        == sorted(RUN_DIRECTORY_NAMES),
        "all_runs_terminal_pass": all(row["terminal_pass"] for row in run_rows),
        "module_counters_match": all(row["module_counters_match"] for row in run_rows),
        "aggregate_crosscheck_pass": overall_cross.get("passed") is True,
        "legacy_input_count_zero": all(
            provider_manifest.get(field) == 0
            for field in (
                "old_runtime_input_count",
                "legacy_provider_input_count",
                "legacy_row_input_count",
                "legacy_aggregate_input_count",
            )
        ),
        "trace_online_false": provider_manifest.get("trace_used_online") is False
        and all(manifest.get("trace_used_online") is False for manifest in run_manifests.values()),
        "synthetic_and_semisynthetic_false": all(
            provider_manifest.get(field) is False
            for field in ("synthetic_data_used", "semisynthetic_data_used")
        )
        and all(
            manifest.get("synthetic_data_used") is False
            and manifest.get("semisynthetic_data_used") is False
            for manifest in run_manifests.values()
        ),
        "receiver_imu_as_body_imu_false": provider_manifest.get("receiver_imu_as_body_imu") is False,
        "worktree_clean_at_audit": dirty is False,
        "provider_commit_matches_code": provider.generator_code_commit == code_commit,
        "paper_figure_count_zero": paper_figure_count == 0,
        "position_same_source_mounting_caveat": evaluator.get(
            "position_same_source_mounting_caveat"
        )
        is True,
        "independent_ground_truth_false": evaluator.get("independent_ground_truth") is False,
    }
    terminal = PASS_STATUS if all(gates.values()) else "BLOCKED_CLEAN1R1C_FINAL_EVIDENCE_AUDIT_FAILED"
    audit = {
        "schema_version": "paper-rebuild-clean1r1c-final-audit-v1",
        "terminal_status": terminal,
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        "code_freeze_commit": code_commit,
        "provider_bundle_hash": provider.provider_bundle_hash,
        "formal_method_count": 4,
        "formal_run_count": len(run_manifests),
        "paper_figure_count": paper_figure_count,
        "gates": gates,
        "old_performance_results_reused": False,
        "formal_results_regenerated_from_hash_locked_raw": True,
        "trace_used_online": False,
        "reference_role": "FIXPOSITION_SAME_SOURCE_EVALUATION_REFERENCE",
        "engineering_truth_alias": True,
        "independent_ground_truth": False,
        "position_same_source_mounting_caveat": True,
        "paper_performance_claim": False,
    }
    report_status = (
        PENDING_FINALIZATION_STATUS if terminal == PASS_STATUS else terminal
    )
    markdown = (
        "# CLEAN1R1C final report\n\n"
        f"`{report_status}`\n\n"
        "Fresh BY2 four-method results were evaluated only after all outputs were hash-frozen. "
        "The reference is Fixposition-derived and same-source, not independent ground truth. "
        "Position metrics retain the fixed mounting/point caveat; yaw uses the frozen protocol.\n\n"
        "No old performance result, provider, runtime, aggregate, row result, or figure was reused. "
        "The authoritative terminal decision is the verified completion sentinel.\n"
    )
    reviewer_text = (
        "# Runtime evidence validation\n\n"
        "Automated contract, lineage, counter, hash, coverage, and aggregate cross-checks passed. "
        "Human review remains required before merge or any paper-facing claim.\n"
    )
    if terminal != PASS_STATUS:
        write_json_atomic(
            stage / "08_EVIDENCE_AUDIT/FINAL_AUDIT_BLOCKED.json", audit
        )
        print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
        return 2
    finalized = _finalize_evidence(stage, audit, markdown, reviewer_text)
    audit["finalized_root_alias"] = (
        "<STAGE_ROOT>/" + finalized.relative_to(stage).as_posix()
    )
    print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
