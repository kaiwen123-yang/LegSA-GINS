#!/usr/bin/env python3
"""Lock M1R2A-CLEAN from current external spec and current fresh providers."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from legsa_gins.paper_rebuild.canonical541.ablation_registry import build_ablation_queue, validate_tracked_ablation_contract
from legsa_gins.paper_rebuild.canonical541.case_manifest import build_case_manifest
from legsa_gins.paper_rebuild.canonical541.full_method_registry import build_full_queue, validate_tracked_method_contract
from legsa_gins.paper_rebuild.canonical541.matrix_spec import (
    EXTERNAL_SOURCE_SPEC_SHA256, load_and_crosscheck_source_specs,
    parameter_provenance_rows, registry_sha256, verify_preserved_generator_source,
)
from legsa_gins.paper_rebuild.canonical541.provider_generator import load_current_fresh_bundle, sha256_file
from legsa_gins.paper_rebuild.raw_doppler_parity import (
    EXPECTED_ACTUAL_FULL_SHA256, EXPECTED_SOLVER_SEMANTIC_SHA256,
    compute_raw_doppler_solver_semantic_sha256,
)
from legsa_gins.paper_rebuild.canonical541.seed_anchor import (
    anchor_context_from_fresh_bundle, realize_all_anchors, seed_manifest,
)
from legsa_gins.paper_rebuild.canonical541.authorization import (
    PROTOCOL_ID, RUNTIME_ROLE, STAGE_ID, validate_attempt_root,
)
from legsa_gins.paper_rebuild.manifest import git_code_state


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    items = list(rows); path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(items[0]) if items else ["empty"]
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader(); writer.writerows(items)


def load_local(path: Path) -> dict[str, Path]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")); values = payload.get("paths")
    if not isinstance(values, dict): raise SystemExit("local config paths missing")
    return {key: Path(str(value)).expanduser().resolve() for key, value in values.items()}


EXPECTED_BASE_HASHES = {
    "imu": "a46fe2b50a5a99d550392f42e3952c871a7562c6d5625ea1b377691009ab643b",
    "gnss": "f4070ba795825cc243402e4acb551c62c6aad109e7040582bf57781226420e22",
    "raw_doppler": EXPECTED_ACTUAL_FULL_SHA256,
    "go2_roll_pitch": "2329770b8e9bc61c02fbf943e2e5fd9ea233d6fd8a3550f7a22410a536155c7a",
    "go2_horizontal_velocity": "f390c8e51f1bec1162c0f6c628ebbcd0449923cfbf9211bebb36004dc2b2aab0",
}
EXPECTED_RAW_LOCK_SHA256 = "f6e5d7965d17857e5b4a846501883f4675f2331a1164fab3de9e5ba9470f1ad7"

ATTEMPT_PRE_FREEZE_DESTINATIONS = (
    "01_COMPACT_READINESS_RUN",
    "05_PROVIDER_GENERATION",
    "06_PROVIDER_READY",
    "07_FULL_ALGORITHM_REGISTRY/PREPARED_EXECUTION_INPUTS",
    "08_FULL_ALGORITHM_RUNS",
    "10_INTERNAL_ABLATION_RUNS",
    "11_OUTPUT_SEAL",
)
GLOBAL_PRE_FREEZE_FILE_NAMES = {
    "KF_GINS_NAVRESULT.NAV", "KF_GINS_STD.TXT", "RUN_MANIFEST.JSON",
    "RUN_PROOF.JSON", "CANONICAL541_EXECUTION_PROOF.JSON",
    "CANONICAL541_FORMAL_RUN_MANIFEST.JSON",
    "OUTPUT_HASH_MANIFEST.CSV", "OUTPUT_SEAL_MANIFEST.CSV",
    "OUTPUT_SEAL_JOURNAL.JSON", "SOLVER_READ_LEDGER.JSON",
    "EVALUATOR_READ_LEDGER.JSON", "SOLVER_FILE_OPEN_TRACE.RAW",
    "EVALUATOR_FILE_OPEN_TRACE.RAW",
}


def verify_active_base_provider(paths: Mapping[str, Path]) -> dict[str, Any]:
    """Fail closed on the exact current A1 freeze before reading provider rows."""

    gate_path = paths["base_provider_gate"].resolve(strict=True)
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    expected_gate_parent = (paths["clean_root"] / "stages" /
        "CLEAN2R2A1_RAW_DOPPLER_CANONICAL_PARITY_AND_CLEAN_ABLATION_RESUME" /
        "04_BASE_PROVIDER").resolve(strict=True)
    if gate_path.parent != expected_gate_parent or gate_path.name != "CLEAN2R2A1_ACTIVE_PROVIDER_FREEZE.json":
        raise SystemExit("active provider gate is not the exact CLEAN2R2A1 freeze")
    required = {
        "passed": True,
        "terminal_status": "PASS_CLEAN2R2A1_MINIMUM_SUFFICIENT_PROVIDER_PARITY",
        "provider_stage_id": "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD",
        "provider_protocol_id": "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION",
        "old_provider_solver_input": False,
        "trace_open_count": 0,
        "provider_payload_modified_after_generation": False,
    }
    if any(gate.get(key) != value for key, value in required.items()):
        raise SystemExit("active provider freeze contract mismatch")
    if gate.get("actual_provider_hashes") != EXPECTED_BASE_HASHES:
        raise SystemExit("active provider freeze hashes mismatch")
    if gate.get("raw_doppler_solver_semantic_sha256") != EXPECTED_SOLVER_SEMANTIC_SHA256:
        raise SystemExit("active provider semantic Raw Doppler hash mismatch")
    root = paths["base_provider_root"].resolve(strict=True)
    if Path(gate.get("active_provider_root", "")).resolve(strict=True) != root:
        raise SystemExit("active provider root identity mismatch")
    clean = root / "FINAL_V23_CLEAN_CLEAN2R2A"
    auxiliary = root / "FRESH_AUXILIARIES_CLEAN2R2A"
    actual_paths = {
        "imu": clean / "FINAL_V23_CLEAN_FRESH.imu",
        "gnss": clean / "FINAL_V23_CLEAN_FRESH.gnss",
        "raw_doppler": auxiliary / "clean_final_v23_time_basis/RAW_DOPPLER_VELOCITY.csv",
        "go2_roll_pitch": auxiliary / "clean_final_v23_time_basis/GO2_ATTITUDE_WEAK_PRIORS.csv",
        "go2_horizontal_velocity": auxiliary / "clean_final_v23_time_basis/GO2_HORIZONTAL_VELOCITY_WEAK_PRIORS.csv",
    }
    actual = {role: sha256_file(path.resolve(strict=True)) for role, path in actual_paths.items()}
    if actual != EXPECTED_BASE_HASHES:
        raise SystemExit("current provider bytes differ from A1 freeze")
    if compute_raw_doppler_solver_semantic_sha256(actual_paths["raw_doppler"]) != EXPECTED_SOLVER_SEMANTIC_SHA256:
        raise SystemExit("current Raw Doppler solver-semantic hash mismatch")
    clean_manifest = json.loads((clean / "FINAL_V23_CLEAN_INPUT_MANIFEST.json").read_text(encoding="utf-8"))
    raw_hashes = clean_manifest.get("raw_source_hashes")
    if not isinstance(raw_hashes, dict) or len(raw_hashes) != 22 or gate.get("raw_verified_count", 22) != 22:
        raise SystemExit("current provider does not bind exact 22 raw sources")
    raw_lock = (paths["clean_root"] / "01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK.csv").resolve(strict=True)
    if sha256_file(raw_lock) != EXPECTED_RAW_LOCK_SHA256:
        raise SystemExit("RAW_FILE_HASH_LOCK identity mismatch")
    with raw_lock.open("r", encoding="utf-8-sig", newline="") as handle:
        lock_rows = {row["relative_path"]: row["sha256"] for row in csv.DictReader(handle)}
    if any(lock_rows.get(name) != digest for name, digest in raw_hashes.items()):
        raise SystemExit("A1 provider raw hashes do not close against current raw lock")
    return {
        "passed": True, "gate_path": str(gate_path), "gate_sha256": sha256_file(gate_path),
        "base_provider_root": str(root), "actual_provider_hashes": actual,
        "raw_doppler_solver_semantic_sha256": EXPECTED_SOLVER_SEMANTIC_SHA256,
        "raw_lock_sha256": EXPECTED_RAW_LOCK_SHA256, "raw_verified_count": 22,
        "old_provider_solver_input": False, "trace_open_count": 0,
    }


def load_base(paths: Mapping[str, Path]):
    verify_active_base_provider(paths)
    root = paths["base_provider_root"]
    clean = root / "FINAL_V23_CLEAN_CLEAN2R2A"
    auxiliary = root / "FRESH_AUXILIARIES_CLEAN2R2A"
    manifest = json.loads((clean / "FINAL_V23_CLEAN_INPUT_MANIFEST.json").read_text(encoding="utf-8"))
    return load_current_fresh_bundle(
        imu_path=clean / "FINAL_V23_CLEAN_FRESH.imu", gnss15_path=clean / "FINAL_V23_CLEAN_FRESH.gnss",
        raw_doppler_path=auxiliary / "clean_final_v23_time_basis/RAW_DOPPLER_VELOCITY.csv",
        go2_rp_path=auxiliary / "clean_final_v23_time_basis/GO2_ATTITUDE_WEAK_PRIORS.csv",
        go2_hv_path=auxiliary / "clean_final_v23_time_basis/GO2_HORIZONTAL_VELOCITY_WEAK_PRIORS.csv",
        dual_yaw_audit_path=auxiliary / "providers/dual_yaw_provider.csv",
        source_quality_path=auxiliary / "providers/SOURCE_QUALITY_METADATA.csv",
        raw_input_hashes=manifest["raw_source_hashes"],
    )


def _external_provider_origin(external_provider_root: Path) -> dict[str, Any]:
    try:
        external = external_provider_root.resolve(strict=True)
    except FileNotFoundError as exc:
        raise SystemExit("external provider origin is missing") from exc
    if external.name != "05_PROVIDER_GENERATION":
        raise SystemExit("external provider origin must be the old 05_PROVIDER_GENERATION root")
    try:
        finalized = (external / "FINALIZED").resolve(strict=True)
        gate_path = (external.parent / "06_PROVIDER_READY/PROVIDER_GATE.json").resolve(strict=True)
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise SystemExit("external provider gate is missing or unreadable") from exc
    required = {
        "passed": True, "provider_generation": 541, "provider_ready": 541,
        "effect_validation": 541, "provider_sha_rows": 4328,
        "provider_sha_closure": True, "raw_mutation": 0, "trace_open_count": 0,
    }
    try:
        bound_finalized = Path(str(gate["finalized_provider_root"])).resolve(strict=True)
    except (KeyError, FileNotFoundError) as exc:
        raise SystemExit("external provider gate lacks finalized-provider binding") from exc
    if bound_finalized != finalized or any(gate.get(key) != value for key, value in required.items()):
        raise SystemExit("external provider gate contract mismatch")
    return {
        "role": "READ_ONLY_PROVIDER_REUSE_ORIGIN_NOT_ATTEMPT_OWNED",
        "path": str(external),
        "finalized_provider_root": str(finalized),
        "provider_gate_path": str(gate_path),
        "provider_gate_sha256": sha256_file(gate_path),
        **required,
    }


def _attempt_owned_pre_freeze_state(
    output: Path, external_provider_root: Path,
) -> dict[str, Any]:
    """Reject only execution artifacts owned by the new attempt.

    ``external_provider_root`` is the immutable CLEAN2 provider-reuse origin.  Its
    existing ``FINALIZED`` tree is evidence to bind later, not evidence that this
    CLEAN3 attempt generated a provider before its solver freeze.
    """

    attempt = validate_attempt_root(output)
    external = external_provider_root.resolve(strict=True)
    try:
        external.relative_to(attempt)
    except ValueError:
        pass
    else:
        raise SystemExit("external provider reuse origin must not be attempt-owned")
    destination_artifacts = sorted(
        path.relative_to(attempt).as_posix()
        for name in ATTEMPT_PRE_FREEZE_DESTINATIONS
        for root in (attempt / name,)
        if root.exists()
        for path in (root, *root.rglob("*"))
    )
    misplaced_artifacts = sorted(
        path.relative_to(attempt).as_posix()
        for path in attempt.rglob("*")
        if path.is_file()
        and (
            path.name.upper() in GLOBAL_PRE_FREEZE_FILE_NAMES
            or "TRACE" in path.name.upper()
            or "READ_LEDGER" in path.name.upper()
            or ("SEAL" in path.name.upper()
                and ("MANIFEST" in path.name.upper() or "JOURNAL" in path.name.upper()))
        )
    )
    if destination_artifacts or misplaced_artifacts:
        raise SystemExit(
            "code-freeze evidence must precede all attempt-owned readiness/providers/"
            "prepared inputs/formal runs/seals/trace ledgers"
        )
    return {
        "attempt_owned_readiness_artifact_count": 0,
        "attempt_owned_provider_artifact_count": 0,
        "attempt_owned_prepared_input_artifact_count": 0,
        "attempt_owned_formal_artifact_count": 0,
        "attempt_owned_output_seal_artifact_count": 0,
        "attempt_owned_misplaced_execution_artifact_count": 0,
        "attempt_owned_trace_ledger_count": 0,
        "external_provider_origin": _external_provider_origin(external),
    }


def _expected_code_freeze(
    *, executable: Path, code_freeze_commit: str,
    ownership_state: Mapping[str, Any],
) -> dict[str, Any]:
    binary = executable.resolve(strict=True)
    if not binary.is_absolute():
        raise SystemExit("code-freeze executable path must be absolute")
    return {
        "schema_version": "paper_rebuild.canonical541_code_freeze.v1",
        "stage_id": STAGE_ID, "protocol_id": PROTOCOL_ID,
        "runtime_role": RUNTIME_ROLE,
        "code_freeze_commit": code_freeze_commit,
        "executable_path": str(binary), "executable_sha256": sha256_file(binary),
        "provider_generation_count_at_freeze": 0,
        "formal_solver_run_count_at_freeze": 0, "trace_open_count_at_freeze": 0,
        "degraded_provider_generation_started_before_freeze": False,
        "formal_solver_run_started_before_freeze": False,
        "worktree_clean": True, **dict(ownership_state), "passed": True,
    }


def _initialize_code_freeze(
    *, output: Path, external_provider_root: Path, executable: Path,
    code_freeze_commit: str,
) -> dict[str, Any]:
    """Create or validate the exact attempt-owned solver freeze."""

    freeze_root = output / "01_GIT_FREEZE"
    freeze_path = freeze_root / "CANONICAL541_CODE_FREEZE.json"
    if freeze_path.is_file():
        freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
        ownership = {
            key: 0 for key in (
                "attempt_owned_readiness_artifact_count",
                "attempt_owned_provider_artifact_count",
                "attempt_owned_prepared_input_artifact_count",
                "attempt_owned_formal_artifact_count",
                "attempt_owned_output_seal_artifact_count",
                "attempt_owned_misplaced_execution_artifact_count",
                "attempt_owned_trace_ledger_count",
            )
        }
        ownership["external_provider_origin"] = _external_provider_origin(
            external_provider_root
        )
        expected = _expected_code_freeze(
            executable=executable, code_freeze_commit=code_freeze_commit,
            ownership_state=ownership,
        )
        if freeze != expected:
            raise SystemExit("existing code-freeze evidence differs from current bytes")
        return freeze
    state = _attempt_owned_pre_freeze_state(output, external_provider_root)
    freeze_root.mkdir(parents=True, exist_ok=True)
    freeze = _expected_code_freeze(
        executable=executable, code_freeze_commit=code_freeze_commit,
        ownership_state=state,
    )
    freeze_path.write_text(
        json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return freeze


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--local-config", required=True); parser.add_argument("--output-root")
    parser.add_argument("--code-freeze-commit", required=True); parser.add_argument("--executable", required=True)
    args = parser.parse_args(); repo = Path(__file__).resolve().parents[2]
    local = Path(args.local_config).resolve(strict=True); paths = load_local(local)
    configured_output = validate_attempt_root(paths["runtime_root"])
    if args.output_root:
        output = validate_attempt_root(args.output_root)
        if output != configured_output:
            raise SystemExit("--output-root must exactly equal local-config runtime_root")
    else:
        output = configured_output
    executable = Path(args.executable).resolve(strict=True)
    commit, dirty = git_code_state(repo)
    if dirty or commit != args.code_freeze_commit:
        raise SystemExit("matrix lock requires exact clean code-freeze commit")
    freeze = _initialize_code_freeze(
        output=output, external_provider_root=paths["provider_root"],
        executable=executable, code_freeze_commit=args.code_freeze_commit,
    )
    freeze_root = output / "01_GIT_FREEZE"
    snapshot_root = freeze_root / "TRACKED_CONFIG_SNAPSHOTS"; snapshot_root.mkdir(exist_ok=True)
    snapshot_names = (
        "canonical_by2_degradation_541.yaml", "canonical_by2_seed_anchor_policy.yaml",
        "canonical_by2_effect_validation.yaml", "canonical_by2_full_method_modes.yaml",
        "canonical_by2_internal_ablation_modes.yaml",
    )
    snapshot_rows = []
    for name in snapshot_names:
        source = repo / "configs/paper_rebuild" / name; destination = snapshot_root / name
        if destination.is_file() and destination.read_bytes() != source.read_bytes():
            raise SystemExit(f"tracked config snapshot drift: {name}")
        if not destination.exists(): shutil.copyfile(source, destination)
        snapshot_rows.append({"relative_path": name, "sha256": sha256_file(destination), "size_bytes": destination.stat().st_size})
    snapshot_manifest = snapshot_root / "TRACKED_CONFIG_SNAPSHOT_MANIFEST.csv"
    if not snapshot_manifest.exists():
        write_csv(snapshot_manifest, snapshot_rows)
    else:
        with snapshot_manifest.open("r", encoding="utf-8-sig", newline="") as handle:
            recorded = list(csv.DictReader(handle))
        expected = [{key: str(value) for key, value in row.items()} for row in snapshot_rows]
        if recorded != expected:
            raise SystemExit("tracked config snapshot manifest closure failed")
    spec = paths["clean_root"] / "00_CONTEXT/DEGRADATION_MATRIX_SPEC.csv"
    preserved_source = verify_preserved_generator_source(repo)
    registry = load_and_crosscheck_source_specs(spec)
    base_gate = verify_active_base_provider(paths)
    base = load_base(paths); context, go2_report = anchor_context_from_fresh_bundle(base, go2_body_raw=str(paths["by2_go2_body"]))
    go2_parser = repo / "src/legsa_gins/go2_state/go2_body_state_parser.py"
    go2_report["shared_source_provenance"] = {
        "tracked_path": go2_parser.relative_to(repo).as_posix(),
        "code_commit": commit, "sha256": sha256_file(go2_parser),
        "symbol": "standardize_go2_body_state", "role": "motion_metadata_not_truth",
    }
    anchors = realize_all_anchors(context); cases = build_case_manifest(anchors)
    parameter_rows = parameter_provenance_rows(registry)
    for row in parameter_rows:
        row["git_object_id"] = preserved_source["git_object_id"] if int(row["source_layer"]) == 3 else ""
    parameter_rows.append({
        "degradation_type_id": "ALL", "field": "__anchor_context_parser__",
        "value_json": json.dumps("motion_metadata_not_truth"), "source_layer": 4,
        "source_path": go2_report["shared_source_provenance"]["tracked_path"],
        "source_commit": commit, "symbol": "standardize_go2_body_state",
        "source_sha256": go2_report["shared_source_provenance"]["sha256"],
        "fallback_used": False, "git_object_id": "",
    })
    provider_handler = repo / "src/legsa_gins/paper_rebuild/canonical541/provider_generator.py"
    parameter_rows.append({
        "degradation_type_id": "D40", "field": "__current_schema_mapping__",
        "value_json": json.dumps({
            "rel_acc_field_available": False,
            "unit_aliasing_forbidden": True,
            "baseline_length_solver_visible": False,
            "rel_acc_no_active_path": True,
            "solver_runtime_input_expected_invariant": True,
            "solver_visible_mapping": "none_audit_only_baseline_metadata",
        }, sort_keys=True, separators=(",", ":")),
        "source_layer": 4, "source_path": provider_handler.relative_to(repo).as_posix(),
        "source_commit": commit, "symbol": "apply_degradation:D40_schema_adapter",
        "source_sha256": sha256_file(provider_handler), "fallback_used": False,
        "git_object_id": "",
    })
    validate_tracked_method_contract(repo / "configs/paper_rebuild/methods.yaml")
    validate_tracked_ablation_contract(repo / "configs/paper_rebuild/clean2r2a_ablation_2pow4.yaml")
    lock = output / "02_MATRIX_SPEC_LOCK"; seeds_root = output / "03_SEEDS_AND_ANCHORS"; effect = output / "04_EFFECT_RULES"
    for directory in (lock, seeds_root, effect): directory.mkdir(parents=True, exist_ok=True)
    stage_snapshots = {
        lock / "canonical_by2_degradation_541.yaml": repo / "configs/paper_rebuild/canonical_by2_degradation_541.yaml",
        lock / "canonical_by2_full_method_modes.yaml": repo / "configs/paper_rebuild/canonical_by2_full_method_modes.yaml",
        lock / "canonical_by2_internal_ablation_modes.yaml": repo / "configs/paper_rebuild/canonical_by2_internal_ablation_modes.yaml",
        seeds_root / "canonical_by2_seed_anchor_policy.yaml": repo / "configs/paper_rebuild/canonical_by2_seed_anchor_policy.yaml",
        effect / "canonical_by2_effect_validation.yaml": repo / "configs/paper_rebuild/canonical_by2_effect_validation.yaml",
    }
    stage_snapshot_rows = []
    for destination, source in stage_snapshots.items():
        if destination.is_file() and destination.read_bytes() != source.read_bytes():
            raise SystemExit(f"stage config snapshot drift: {destination.name}")
        if not destination.exists():
            shutil.copyfile(source, destination)
        stage_snapshot_rows.append({
            "stage_relative_path": destination.relative_to(output).as_posix(),
            "tracked_relative_path": source.relative_to(repo).as_posix(),
            "sha256": sha256_file(destination), "size_bytes": destination.stat().st_size,
            "code_commit": commit,
        })
    stage_snapshot_manifest = freeze_root / "STAGE_CONFIG_SNAPSHOT_MANIFEST.csv"
    if not stage_snapshot_manifest.exists():
        write_csv(stage_snapshot_manifest, stage_snapshot_rows)
    else:
        with stage_snapshot_manifest.open("r", encoding="utf-8-sig", newline="") as handle:
            recorded = list(csv.DictReader(handle))
        expected = [{key: str(value) for key, value in row.items()} for row in stage_snapshot_rows]
        if recorded != expected:
            raise SystemExit("stage config snapshot manifest closure failed")
    write_csv(lock / "CANONICAL_BY2_DEGRADATION_TYPE_REGISTRY.csv", ({
        "degradation_type_id": row.type_id, "degradation_type_name": row.name,
        "family": row.family, "parameters_json": json.dumps(row.parameters, sort_keys=True, separators=(",", ":")),
        "affected_sources": ";".join(row.affected_sources), "effect_validation_rule_id": row.effect_validation_rule_id,
    } for row in registry))
    write_csv(seeds_root / "CANONICAL_BY2_RANDOM_SEED_MANIFEST.csv", seed_manifest())
    write_csv(seeds_root / "CANONICAL_BY2_ANCHOR_SELECTION_MANIFEST.csv", anchors)
    (seeds_root / "CANONICAL541_ANCHOR_SOURCE_PROVENANCE.json").write_text(
        json.dumps(go2_report, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    (seeds_root / "CANONICAL541_ANCHOR_SELECTION_REPORT.md").write_text(
        "# Canonical541 anchor selection\n\n"
        "- Horizontal speed source: fresh Go2 horizontal-velocity weak-prior metadata.\n"
        "- Go2 role: source-only motion metadata, never truth.\n"
        f"- Fallback anchors: {sum(row['selection_status'] != 'selected' for row in anchors)}/9.\n"
        "- Trace, final_v23 output, and LegSA output used for selection: no.\n",
        encoding="utf-8",
    )
    write_csv(lock / "CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv", cases)
    (lock / "CANONICAL541_CASE_MANIFEST.csv").write_bytes(
        (lock / "CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv").read_bytes()
    )
    write_csv(lock / "CANONICAL_BY2_CASE_FAMILY_SUMMARY.csv", ({"family": family, "case_count": sum(row["case_family"] == family for row in cases)} for family in sorted({row["case_family"] for row in cases})))
    write_csv(lock / "FROZEN_GENERATOR_SOURCE_MAP.csv", parameter_rows)
    write_csv(lock / "PARAMETER_PROVENANCE_REGISTRY.csv", parameter_rows)
    write_csv(effect / "CANONICAL_BY2_EFFECT_VALIDATION_RULES.csv", ({"rule_id": row.effect_validation_rule_id, "degradation_type_id": row.type_id, "independent_recompute_required": True} for row in registry))
    write_csv(lock / "FULL_ALGORITHM_QUEUE_DRAFT.csv", build_full_queue(cases))
    write_csv(lock / "INTERNAL_ABLATION_QUEUE_DRAFT.csv", build_ablation_queue(cases))
    anchor_policy_source = repo / "configs/paper_rebuild/canonical_by2_seed_anchor_policy.yaml"
    (seeds_root / "CANONICAL_BY2_ANCHOR_SELECTION_POLICY.yaml").write_bytes(anchor_policy_source.read_bytes())
    (lock / "CANONICAL_BY2_CASE_SPEC_SCHEMA.json").write_text(json.dumps({"schema_version": "canonical541.case.v1", "required": list(cases[0]), "additionalProperties": True}, indent=2) + "\n", encoding="utf-8")
    (lock / "CANONICAL_BY2_CASE_COUNT_DECISION.md").write_text("# Canonical BY2 case count\n\n60 controlled degradation types x 9 seeds + one clean case = 541 canonical cases.\nThese are not 60 real scenarios.\n", encoding="utf-8")
    report = {"external_source_spec": "clean://00_CONTEXT/DEGRADATION_MATRIX_SPEC.csv", "external_source_sha256": sha256_file(spec),
              "expected_external_source_sha256": EXTERNAL_SOURCE_SPEC_SHA256, "tracked_migration_crosscheck": True,
              "registry_sha256": registry_sha256(registry), "type_count": 60, "seed_count": 9,
              "case_count": len(cases), "placeholder_count": 0, "go2_anchor_source_report": go2_report,
              "base_provider_gate": base_gate, "old_provider_solver_input": False,
              "trace_used": False, "performance_evidence_read": False, "passed": True}
    (lock / "CLEAN_SOURCE_SPEC_MIGRATION_REPORT.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (lock / "PARAMETER_PROVENANCE_REPORT.json").write_text(json.dumps({
        "row_count": len(parameter_rows), "fallback_used_count": 0,
        "preserved_generator_source": preserved_source,
        "anchor_parser_source": go2_report["shared_source_provenance"], "passed": True,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (lock / "PARAMETER_PROVENANCE_REPORT.md").write_text(
        "# Canonical541 parameter provenance\n\n"
        f"- Registry rows: {len(parameter_rows)}\n"
        "- Source priority: current spec, tracked config/tests, preserved effect-validated generator, master fallback.\n"
        "- Canonical fallback used: 0 fields.\n"
        "- Runtime performance payload read: no.\n",
        encoding="utf-8",
    )
    (lock / "CLEAN_SOURCE_SPEC_MIGRATION_REPORT.md").write_text(
        "# Canonical541 clean source-spec migration\n\n"
        "- D01-D60 type count: 60; controlled seeds: 9; clean case: 1.\n"
        "- Preserved generator use: static source laws only; runtime performance payload: not read.\n"
        f"- Preserved Git object: `{preserved_source['git_object_id']}`.\n"
        "- Trace and algorithm outputs used for spec/anchor selection: no.\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__": main()
