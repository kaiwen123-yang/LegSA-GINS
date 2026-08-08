"""Prepare, resume, and execute the canonical541 exact-input run plan.

This module never evaluates performance.  It binds provider bytes, method
flags, runtime configuration and the executable before launching a solver.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

from .ablation_registry import (
    ABLATION_METHODS, validate_canonical_ablation_config,
    validate_tracked_ablation_contract,
)
from .full_method_registry import (
    FEATURE_FIELDS, FULL_METHODS, MethodProfile,
    validate_canonical_full_config, validate_tracked_method_contract,
)
from .provider_generator import (
    ProviderBundle, load_case_bundle, resolve_provider_index, sha256_file,
)
from .run_registry import build_logical_queues, resolve_execution_aliases
from .runner import (
    TERMINAL_STATUSES, CanonicalRunnerError, _as_bool, _expected_solver_inputs,
    build_runtime_config, materialize_method_bound_inputs, run_unique_execution,
    scientific_runtime_config_hash, actual_rendered_runtime_config_sha256,
    validate_terminal_output,
)
from ..manifest import git_code_state
from .authorization import validate_attempt_root


class ExecutionPlanError(RuntimeError):
    pass


PROFILE_BY_METHOD = {row.method_id: row for row in (*FULL_METHODS, *ABLATION_METHODS)}
REPRESENTATIVE_PROFILES = tuple(dict.fromkeys(row.signature for row in (*FULL_METHODS, *ABLATION_METHODS)))


def _profile_representatives() -> tuple[MethodProfile, ...]:
    output: list[MethodProfile] = []
    seen: set[tuple[bool, ...]] = set()
    for profile in (*FULL_METHODS, *ABLATION_METHODS):
        if profile.signature not in seen:
            output.append(profile); seen.add(profile.signature)
    if len(output) != 11:
        raise ExecutionPlanError("canonical matrix must have eleven effective profiles")
    return tuple(output)


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_atomic(path: str | Path, rows: Iterable[Mapping[str, Any]]) -> Path:
    destination = Path(path); items = [dict(row) for row in rows]
    if not items:
        raise ExecutionPlanError(f"cannot write empty registry: {destination.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp_{os.getpid()}")
    with temporary.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(items[0]), extrasaction="ignore", lineterminator="\n")
        writer.writeheader(); writer.writerows(items)
    os.replace(temporary, destination)
    return destination


def normalize_case_row(row: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(row)
    for key in ("case_index", "seed_value"):
        if output.get(key) not in (None, ""):
            output[key] = int(output[key])
    for key in (
        "requires_randomness", "seed_effective", "independent_realization", "trace_eval_only",
        "final_v23_output_solver_input_allowed", "legsa_output_solver_input_allowed",
        "go2_truth_claim_allowed", "synthetic_data_used", "semisynthetic_data_used",
    ):
        output[key] = _as_bool(output.get(key, False))
    if output.get("anchor_time_s") not in (None, ""):
        output["anchor_time_s"] = float(output["anchor_time_s"])
    return output


def _provider_index_rows(case_root: Path) -> list[dict[str, Any]]:
    payload = json.loads((case_root / "02_PROVIDERS/provider_index.json").read_text(encoding="utf-8"))
    rows = payload.get("provider_files")
    if not isinstance(rows, list) or len(rows) != 8:
        raise ExecutionPlanError(f"provider index does not contain eight sources: {case_root.name}")
    return [dict(row) for row in rows]


def validate_provider_gate(*, stage_root: str | Path, provider_root: str | Path,
                           case_manifest: str | Path) -> dict[str, Any]:
    """Recompute all 4,328 aggregate provider rows and pointer semantics."""

    stage = validate_attempt_root(stage_root)
    providers = Path(provider_root).resolve(strict=True)
    finalized = (providers / "FINALIZED").resolve(strict=True)
    ready_root = stage / "06_PROVIDER_READY"
    gate_path = ready_root / "PROVIDER_GATE.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    cases = [normalize_case_row(row) for row in read_csv(case_manifest)]
    ready_path = ready_root / "CANONICAL541_PROVIDER_READY_MANIFEST.csv"
    effect_path = ready_root / "CANONICAL541_EFFECT_VALIDATION_RESULTS.csv"
    sha_path = ready_root / "PROVIDER_SHA256_MANIFEST.csv"
    ready_rows = read_csv(ready_path); effect_rows = read_csv(effect_path); sha_rows = read_csv(sha_path)
    if (
        len(cases) != 541 or len(ready_rows) != 541
        or len(effect_rows) != 541 or len(sha_rows) != 541 * 8
        or gate.get("provider_generation") != 541 or gate.get("effect_validation") != 541
        or gate.get("provider_ready") != 541 or gate.get("provider_sha_rows") != 541 * 8
        or gate.get("provider_sha_closure") is not True or gate.get("passed") is not True
        or gate.get("ready_manifest_sha256") != sha256_file(ready_path)
        or gate.get("effect_result_sha256") != sha256_file(effect_path)
    ):
        raise ExecutionPlanError("aggregate provider gate count/hash contract failed")
    expected_case_ids = [str(row["case_id"]) for row in cases]
    if [row.get("case_id") for row in ready_rows] != expected_case_ids:
        raise ExecutionPlanError("provider-ready manifest case order/identity drift")
    if [row.get("case_id") for row in effect_rows] != expected_case_ids:
        raise ExecutionPlanError("effect-validation manifest case order/identity drift")
    aggregate = {(row["case_id"], row["source"]): row for row in sha_rows}
    if len(aggregate) != 541 * 8:
        raise ExecutionPlanError("provider SHA manifest contains duplicate rows")
    recomputed = 0
    for case_id, ready_row, effect_row in zip(expected_case_ids, ready_rows, effect_rows):
        root = (finalized / case_id).resolve(strict=True)
        ready = json.loads((root / "04_PROVIDER_READY/provider_ready_manifest.json").read_text(encoding="utf-8"))
        effect = json.loads((root / "03_EFFECT_VALIDATION/effect_validation_summary.json").read_text(encoding="utf-8"))
        if (
            ready.get("case_id") != case_id or ready.get("provider_ready") is not True
            or ready.get("effect_validation_passed") is not True
            or effect.get("passed") is not True
            or (root / "03_EFFECT_VALIDATION/validation_pass.flag").read_text(encoding="utf-8") != "PASS\n"
            or (root / "04_PROVIDER_READY/provider_ready.flag").read_text(encoding="utf-8") != "PASS\n"
            or not _as_bool(ready_row.get("provider_ready"))
            or not _as_bool(ready_row.get("effect_validation_passed"))
            or not _as_bool(effect_row.get("passed"))
        ):
            raise ExecutionPlanError(f"case provider/effect gate failed: {case_id}")
        resolved = resolve_provider_index(root)
        index_rows = _provider_index_rows(root)
        for index_row in index_rows:
            source = str(index_row["source"]); path = resolved[source]
            aggregate_row = aggregate.get((case_id, source))
            if aggregate_row is None:
                raise ExecutionPlanError(f"provider SHA aggregate missing: {case_id}/{source}")
            if (
                aggregate_row.get("sha256") != sha256_file(path)
                or int(aggregate_row.get("size_bytes", -1)) != path.stat().st_size
                or aggregate_row.get("semantic_sha256") != str(index_row["semantic_sha256"])
                or aggregate_row.get("storage_mode") != str(index_row["storage_mode"])
                or Path(str(aggregate_row.get("resolved_path", ""))).resolve(strict=True) != path
            ):
                raise ExecutionPlanError(f"provider aggregate/pointer closure failed: {case_id}/{source}")
            recomputed += 1
    return {
        "provider_generation": 541, "effect_validation": 541, "provider_ready": 541,
        "provider_sha_rows_recomputed": recomputed, "pointer_semantics_valid": True,
        "trace_open_count": 0, "raw_mutation": 0, "passed": recomputed == 541 * 8,
        "provider_gate_sha256": sha256_file(gate_path),
        "ready_manifest_sha256": sha256_file(ready_path),
        "effect_manifest_sha256": sha256_file(effect_path),
        "provider_sha_manifest_sha256": sha256_file(sha_path),
    }


def _method_manifest_valid(path: Path, *, profile: MethodProfile,
                           case_bundle: ProviderBundle) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("method_id") != profile.method_id
        or payload.get("effective_profile") != profile.effective_profile
        or payload.get("effective_flags") != dict(profile.flags)
        or payload.get("full_case_bundle_hashes") != case_bundle.hashes()
    ):
        raise ExecutionPlanError("prepared method-bound manifest identity drift")
    _expected_solver_inputs(payload)
    return payload


def _ensure_method_bound_inputs(
    *, base: ProviderBundle, case_bundle: ProviderBundle, profile: MethodProfile,
    destination: Path, case_provider_paths: Mapping[str, Path], shared_gnss_root: Path,
) -> dict[str, Any]:
    manifest = destination / "METHOD_BOUND_INPUT_MANIFEST.json"
    if manifest.is_file():
        return _method_manifest_valid(manifest, profile=profile, case_bundle=case_bundle)
    if destination.exists():
        raise ExecutionPlanError(f"incomplete method-bound input directory: {destination}")
    temporary = destination.with_name(f".{destination.name}.tmp_{os.getpid()}")
    if temporary.exists():
        raise ExecutionPlanError(f"owned preparation temporary already exists: {temporary}")
    materialize_method_bound_inputs(
        base=base, case_bundle=case_bundle, profile=profile, output_root=temporary,
        case_provider_paths=case_provider_paths, shared_gnss_root=shared_gnss_root,
    )
    os.replace(temporary, destination)
    return _method_manifest_valid(manifest, profile=profile, case_bundle=case_bundle)


def _provider_protocol_paths(repo: Path, base_provider_root: Path) -> tuple[Path, Path, Path]:
    clean = base_provider_root / "FINAL_V23_CLEAN_CLEAN2R2A/FINAL_V23_CLEAN_INPUT_MANIFEST.json"
    auxiliary = base_provider_root / "FRESH_AUXILIARIES_CLEAN2R2A/CLEAN1R2R1_AUXILIARY_MANIFEST.json"
    protocol = repo / "configs/paper_rebuild/clean1_by2_clean_protocol.yaml"
    return clean.resolve(strict=True), auxiliary.resolve(strict=True), protocol.resolve(strict=True)


def validate_code_freeze_gate(*, stage_root: Path, executable: Path,
                              code_freeze_commit: str) -> dict[str, Any]:
    path = stage_root / "01_GIT_FREEZE/CANONICAL541_CODE_FREEZE.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("stage_id") != "CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX"
        or payload.get("code_freeze_commit") != code_freeze_commit
        or payload.get("executable_sha256") != sha256_file(executable)
        or payload.get("provider_generation_count_at_freeze") != 0
        or payload.get("formal_solver_run_count_at_freeze") != 0
        or payload.get("trace_open_count_at_freeze") != 0
        or payload.get("passed") is not True
    ):
        raise ExecutionPlanError("CANONICAL541 code-freeze evidence gate failed")
    return payload


def prepare_execution_plan(
    *, repo_root: str | Path, stage_root: str | Path, provider_root: str | Path,
    base_provider_root: str | Path, base: ProviderBundle, executable: str | Path,
    code_freeze_commit: str,
) -> dict[str, Any]:
    repo = Path(repo_root).resolve(strict=True); stage = validate_attempt_root(stage_root)
    provider = Path(provider_root).resolve(strict=True); executable_path = Path(executable).resolve(strict=True)
    commit, dirty = git_code_state(repo)
    if dirty or commit != code_freeze_commit:
        raise ExecutionPlanError("execution plan requires exact clean code freeze")
    validate_code_freeze_gate(
        stage_root=stage, executable=executable_path,
        code_freeze_commit=code_freeze_commit,
    )
    validate_tracked_method_contract(repo / "configs/paper_rebuild/methods.yaml")
    validate_tracked_ablation_contract(repo / "configs/paper_rebuild/clean2r2a_ablation_2pow4.yaml")
    validate_canonical_full_config(repo / "configs/paper_rebuild/canonical_by2_full_method_modes.yaml")
    validate_canonical_ablation_config(repo / "configs/paper_rebuild/canonical_by2_internal_ablation_modes.yaml")
    case_manifest = stage / "02_MATRIX_SPEC_LOCK/CANONICAL541_CASE_MANIFEST.csv"
    provider_gate = validate_provider_gate(stage_root=stage, provider_root=provider, case_manifest=case_manifest)
    cases = [normalize_case_row(row) for row in read_csv(case_manifest)]
    full_rows, ablation_rows = build_logical_queues(cases); logical_source = [*full_rows, *ablation_rows]
    for row in logical_source:
        row["provider_ready"] = True
    registry_root = stage / "07_FULL_ALGORITHM_REGISTRY"
    prepared_root = registry_root / "PREPARED_EXECUTION_INPUTS"
    shared_gnss = prepared_root / "SHARED_GNSS_BY_HASH"
    prepared_root.mkdir(parents=True, exist_ok=True); shared_gnss.mkdir(parents=True, exist_ok=True)
    clean_manifest, auxiliary_manifest, provider_protocol = _provider_protocol_paths(
        repo, Path(base_provider_root).resolve(strict=True),
    )
    representatives = _profile_representatives()
    method_bound_hashes: dict[tuple[str, str], str] = {}
    runtime_hashes: dict[tuple[str, str], str] = {}
    manifest_by_case_signature: dict[tuple[str, tuple[bool, ...]], Path] = {}
    profile_by_signature = {profile.signature: profile for profile in representatives}
    for case in cases:
        case_id = str(case["case_id"]); case_root = provider / "FINALIZED" / case_id
        case_bundle = load_case_bundle(case_root, base=base)
        provider_paths = resolve_provider_index(case_root)
        for signature, profile in profile_by_signature.items():
            directory = prepared_root / "METHOD_BOUND" / case_id / profile.effective_profile
            payload = _ensure_method_bound_inputs(
                base=base, case_bundle=case_bundle, profile=profile, destination=directory,
                case_provider_paths=provider_paths, shared_gnss_root=shared_gnss,
            )
            manifest_path = directory / "METHOD_BOUND_INPUT_MANIFEST.json"
            manifest_by_case_signature[(case_id, signature)] = manifest_path
            for candidate in (*FULL_METHODS, *ABLATION_METHODS):
                if candidate.signature != signature:
                    continue
                pair = (candidate.method_id, case_id)
                method_bound_hashes[pair] = str(payload["method_bound_bundle_sha256"])
                template = build_runtime_config(
                    profile=candidate, clean_input_manifest=clean_manifest,
                    auxiliary_manifest=auxiliary_manifest, provider_protocol=provider_protocol,
                    method_bound_manifest=payload,
                    output_dir=stage / ("08_FULL_ALGORITHM_RUNS" if candidate.method_id.startswith("F") else "10_INTERNAL_ABLATION_RUNS") / "PLAN_PLACEHOLDER",
                    case_id=case_id, run_id="PLAN_PLACEHOLDER",
                )
                runtime_hashes[pair] = scientific_runtime_config_hash(template)
    executable_hash = sha256_file(executable_path)
    logical, unique = resolve_execution_aliases(
        logical_source, method_bound_provider_hashes=method_bound_hashes,
        runtime_config_hashes=runtime_hashes, executable_hash=executable_hash,
    )
    logical_by_id = {str(row["logical_id"]): row for row in logical}
    configs_root = prepared_root / "RUNTIME_CONFIGS"; configs_root.mkdir(parents=True, exist_ok=True)
    for record in unique:
        source = logical_by_id[str(record["canonical_logical_id"])]
        profile = PROFILE_BY_METHOD[str(source["method_id"])]
        matrix = str(source["matrix"]); case_id = str(source["case_id"])
        output_root = stage / ("08_FULL_ALGORITHM_RUNS" if matrix == "full_algorithm" else "10_INTERNAL_ABLATION_RUNS") / str(record["run_id"])
        method_manifest = manifest_by_case_signature[(case_id, profile.signature)]
        method_payload = json.loads(method_manifest.read_text(encoding="utf-8"))
        config_text = build_runtime_config(
            profile=profile, clean_input_manifest=clean_manifest,
            auxiliary_manifest=auxiliary_manifest, provider_protocol=provider_protocol,
            method_bound_manifest=method_payload, output_dir=output_root,
            case_id=case_id, run_id=str(record["run_id"]),
        )
        if scientific_runtime_config_hash(config_text) != record["runtime_config_hash"]:
            raise ExecutionPlanError("prepared runtime scientific hash differs from alias key")
        rendered_hash = actual_rendered_runtime_config_sha256(config_text)
        prior_rendered_hash = method_payload.get("actual_rendered_runtime_config_sha256")
        if prior_rendered_hash not in (None, rendered_hash):
            raise ExecutionPlanError("method-bound actual rendered runtime config hash drift")
        if prior_rendered_hash is None:
            method_payload["actual_rendered_runtime_config_sha256"] = rendered_hash
            temporary_manifest = method_manifest.with_name(f".{method_manifest.name}.tmp_{os.getpid()}")
            temporary_manifest.write_text(json.dumps(method_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            os.replace(temporary_manifest, method_manifest)
        config_path = configs_root / f"{record['run_id']}.yaml"
        if config_path.is_file():
            if config_path.read_text(encoding="utf-8") != config_text:
                raise ExecutionPlanError("prepared runtime config changed across resume")
        else:
            config_path.write_text(config_text, encoding="utf-8")
        record.update({
            "matrix": matrix, "effective_profile": profile.effective_profile,
            "case_family": source.get("case_family", ""),
            "degradation_type_id": source.get("degradation_type_id", ""),
            "seed_index": source.get("seed_index", ""),
            "output_root": str(output_root), "repo_root": str(repo),
            "runtime_config_template_path": str(config_path.resolve(strict=True)),
            "runtime_config_template_hash": sha256_file(config_path),
            "actual_rendered_runtime_config_sha256": rendered_hash,
            "runtime_config_file_hash": "", "runtime_config_path": "",
            "method_bound_manifest_path": str(method_manifest.resolve(strict=True)),
            "method_bound_manifest_hash": sha256_file(method_manifest),
            "code_freeze_commit": code_freeze_commit, "terminal_status": "PENDING",
            **{field: profile.flags[field] for field in FEATURE_FIELDS},
        })
    unique_by_run = {str(row["run_id"]): row for row in unique}
    for row in logical:
        owner = unique_by_run[str(row["run_id"])]
        row.update(
            provider_ready=True, output_root=owner["output_root"],
            method_bound_manifest_hash=owner["method_bound_manifest_hash"],
        )
    full_resolved = [row for row in logical if row["matrix"] == "full_algorithm"]
    ablation_resolved = [row for row in logical if row["matrix"] == "internal_ablation"]
    write_csv_atomic(stage / "07_FULL_ALGORITHM_REGISTRY/FULL_ALGORITHM_QUEUE.csv", full_resolved)
    write_csv_atomic(stage / "09_INTERNAL_ABLATION_REGISTRY/INTERNAL_ABLATION_QUEUE.csv", ablation_resolved)
    unique_path = write_csv_atomic(stage / "07_FULL_ALGORITHM_REGISTRY/CANONICAL541_UNIQUE_RUN_REGISTRY.csv", unique)
    plan = {
        "schema_version": "paper_rebuild.canonical541_execution_plan.v1",
        "code_freeze_commit": code_freeze_commit, "executable_path": str(executable_path),
        "executable_sha256": executable_hash, "logical_row_count": len(logical),
        "full_logical_row_count": len(full_resolved), "ablation_logical_row_count": len(ablation_resolved),
        "unique_run_count": len(unique), "effective_profile_count": len(representatives),
        "c00_logical_row_count": sum(row["case_id"] == "C00_clean_normal" for row in logical),
        "c00_unique_run_count": sum(row["case_id"] == "C00_clean_normal" for row in unique),
        "provider_gate": provider_gate, "unique_registry_sha256": sha256_file(unique_path),
        "trace_open_count": 0, "metric_driven_rerun": False, "passed": True,
    }
    if (plan["logical_row_count"], plan["full_logical_row_count"], plan["ablation_logical_row_count"],
            plan["effective_profile_count"], plan["c00_logical_row_count"], plan["c00_unique_run_count"]) != (7033, 2164, 4869, 11, 13, 11):
        raise ExecutionPlanError("canonical execution plan count closure failed")
    (registry_root / "EXECUTION_PLAN.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    return plan


def _normalize_registry_row(row: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(row)
    for field in (*FEATURE_FIELDS, "formal", "execution_alias", "provider_ready",
                  "seed_effective", "independent_realization", "trace_used_online",
                  "per_case_tuning", "metric_driven_rerun"):
        if field in output:
            output[field] = _as_bool(output[field])
    for field in ("run_order", "logical_order", "logical_alias_count", "case_index"):
        if output.get(field) not in (None, ""):
            output[field] = int(output[field])
    return output


def load_execution_plan(
    *, stage_root: str | Path, repo_root: str | Path, executable: str | Path,
    code_freeze_commit: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    stage = validate_attempt_root(stage_root); repo = Path(repo_root).resolve(strict=True)
    plan_path = stage / "07_FULL_ALGORITHM_REGISTRY/EXECUTION_PLAN.json"
    unique_path = stage / "07_FULL_ALGORITHM_REGISTRY/CANONICAL541_UNIQUE_RUN_REGISTRY.csv"
    full_path = stage / "07_FULL_ALGORITHM_REGISTRY/FULL_ALGORITHM_QUEUE.csv"
    ablation_path = stage / "09_INTERNAL_ABLATION_REGISTRY/INTERNAL_ABLATION_QUEUE.csv"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    unique = [_normalize_registry_row(row) for row in read_csv(unique_path)]
    logical = [_normalize_registry_row(row) for row in (*read_csv(full_path), *read_csv(ablation_path))]
    commit, dirty = git_code_state(repo)
    binary = Path(executable).resolve(strict=True)
    validate_code_freeze_gate(
        stage_root=stage, executable=binary,
        code_freeze_commit=code_freeze_commit,
    )
    if (
        dirty or commit != code_freeze_commit or plan.get("code_freeze_commit") != code_freeze_commit
        or Path(str(plan.get("executable_path", ""))).resolve(strict=True) != binary
        or plan.get("executable_sha256") != sha256_file(binary)
        or plan.get("unique_registry_sha256") != sha256_file(unique_path)
        or len(unique) != plan.get("unique_run_count") or len(logical) != 7033
        or sum(row["matrix"] == "full_algorithm" for row in logical) != 2164
        or sum(row["matrix"] == "internal_ablation" for row in logical) != 4869
    ):
        raise ExecutionPlanError("prepared execution plan identity/count closure failed")
    for row in unique:
        if row.get("executable_hash") != plan["executable_sha256"]:
            raise ExecutionPlanError("unique run executable hash differs from plan")
        template = Path(str(row["runtime_config_template_path"])).resolve(strict=True)
        method_manifest = Path(str(row["method_bound_manifest_path"])).resolve(strict=True)
        if (sha256_file(template) != row["runtime_config_template_hash"]
                or sha256_file(method_manifest) != row["method_bound_manifest_hash"]
                or scientific_runtime_config_hash(template.read_text(encoding="utf-8")) != row["runtime_config_hash"]
                or actual_rendered_runtime_config_sha256(template.read_text(encoding="utf-8"))
                   != row.get("actual_rendered_runtime_config_sha256")):
            raise ExecutionPlanError("prepared config/method-bound bytes drifted")
        method_payload = json.loads(method_manifest.read_text(encoding="utf-8"))
        if method_payload.get("actual_rendered_runtime_config_sha256") != row.get("actual_rendered_runtime_config_sha256"):
            raise ExecutionPlanError("method-bound rendered config hash differs from plan")
        _expected_solver_inputs(method_payload)
    return plan, unique, logical


def storage_projection(*, unique_runs: Iterable[Mapping[str, Any]], stage_root: str | Path,
                       clean_ablation_runtime_root: str | Path) -> dict[str, Any]:
    unique = tuple(unique_runs); reference = Path(clean_ablation_runtime_root).resolve(strict=True)
    sample_sizes = [
        sum(path.stat().st_size for path in run.rglob("*") if path.is_file())
        for run in sorted(path for path in reference.iterdir() if path.is_dir())
    ]
    if len(sample_sizes) != 18:
        raise ExecutionPlanError("storage projection requires exact 18-run A1 structural reference")
    average = sum(sample_sizes) / len(sample_sizes)
    evaluation_reference = reference.parent / "08_OFFLINE_EVALUATION"
    evaluation_sizes = [
        sum(path.stat().st_size for path in run.rglob("*") if path.is_file())
        for run in sorted(path for path in evaluation_reference.iterdir() if path.is_dir())
    ] if evaluation_reference.is_dir() else []
    if len(evaluation_sizes) != 18:
        raise ExecutionPlanError("storage projection requires exact 18-run A1 evaluation reference")
    evaluation_average = sum(evaluation_sizes) / len(evaluation_sizes)
    projected_runtime = int(average * len(unique) * 1.20)
    projected_evaluation = int(evaluation_average * len(unique) * 1.20)
    projected = projected_runtime + projected_evaluation
    usage = shutil.disk_usage(validate_attempt_root(stage_root))
    report = {
        "unique_run_count": len(unique), "reference_run_count": 18,
        "reference_average_bytes": int(average),
        "reference_evaluation_average_bytes": int(evaluation_average),
        "projection_safety_factor": 1.20,
        "projected_runtime_bytes": projected_runtime,
        "projected_evaluation_bytes": projected_evaluation,
        "projected_total_bytes": projected, "available_bytes": usage.free,
        "projected_fits": usage.free > projected, "case_reduction_allowed": False,
    }
    if not report["projected_fits"]:
        raise ExecutionPlanError("insufficient storage for full unique execution projection")
    return report


def _attempt_config(template: Path, destination: Path, output_root: Path) -> Path:
    payload = yaml.safe_load(template.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ExecutionPlanError("prepared runtime config is not a mapping")
    payload["outputpath"] = str(output_root)
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        if destination.read_text(encoding="utf-8") != text:
            raise ExecutionPlanError("attempt runtime config changed across resume")
    else:
        destination.write_text(text, encoding="utf-8")
    return destination.resolve(strict=True)


def _attempt_directories(row: Mapping[str, Any]) -> Path:
    output = Path(str(row["output_root"]))
    return output.parent / ".attempts" / str(row["run_id"])


def _validate_attempt_result(
    result: Mapping[str, Any], *, row: Mapping[str, Any], attempt_number: int,
    attempt_root: Path, output_root: Path,
) -> None:
    """Reject reconstructed or cross-run attempt metadata before any resume."""

    required = {
        "run_id": str(row["run_id"]), "method_id": str(row["method_id"]),
        "case_id": str(row["case_id"]), "attempt": attempt_number,
        "attempt_root": str(attempt_root.resolve(strict=False)),
        "output_root": str(output_root.resolve(strict=False)),
        "metric_driven_rerun": False,
    }
    mismatches = [key for key, value in required.items() if result.get(key) != value]
    if mismatches:
        raise ExecutionPlanError(
            f"attempt-result identity drift for {row['run_id']}:" + ",".join(mismatches)
        )


def _promote_terminal_attempt(
    *, row: Mapping[str, Any], attempt_root: Path, output_root: Path,
) -> dict[str, Any]:
    """Atomically promote one terminal attempt and bind its runtime config path."""

    if output_root.exists():
        raise ExecutionPlanError("both attempt and promoted terminal output exist")
    os.replace(attempt_root, output_root)
    config = (output_root / "CANONICAL541_RUNTIME_CONFIG.yaml").resolve(strict=True)
    proof_path = output_root / "CANONICAL541_EXECUTION_PROOF.json"
    formal_path = output_root / "CANONICAL541_FORMAL_RUN_MANIFEST.json"
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    if proof.get("runtime_config_hash") != sha256_file(config):
        raise ExecutionPlanError("promoted runtime config hash differs from execution proof")
    proof["runtime_config_path"] = str(config)
    proof_bytes = (json.dumps(proof, indent=2, sort_keys=True) + "\n").encode("utf-8")
    proof_path.write_bytes(proof_bytes)
    formal_path.write_bytes(proof_bytes)
    attempt_result_path = output_root / "ATTEMPT_RESULT.json"
    attempt_result = json.loads(attempt_result_path.read_text(encoding="utf-8"))
    attempt_result["runtime_config_path"] = str(config)
    attempt_result["runtime_config_hash"] = sha256_file(config)
    attempt_result_path.write_text(
        json.dumps(attempt_result, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    return _load_terminal_row(row)


def _load_terminal_row(row: Mapping[str, Any]) -> dict[str, Any]:
    output = Path(str(row["output_root"]))
    proof = json.loads((output / "CANONICAL541_EXECUTION_PROOF.json").read_text(encoding="utf-8"))
    config = (output / "CANONICAL541_RUNTIME_CONFIG.yaml").resolve(strict=True)
    if (proof.get("runtime_config_path") != str(config)
            or proof.get("runtime_config_hash") != sha256_file(config)):
        raise ExecutionPlanError("terminal runtime config path/hash closure failed")
    updated = dict(row)
    updated.update(
        terminal_status=proof["terminal_status"],
        runtime_config_path=proof["runtime_config_path"],
        runtime_config_file_hash=proof["runtime_config_hash"],
    )
    validate_terminal_output(updated)
    return updated


def _run_one_with_retry(
    row: Mapping[str, Any], *, executable: Path, raw_root: Path,
    clean_root: Path, repo_root: Path, timeout_seconds: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    output = Path(str(row["output_root"]))
    if output.is_dir():
        return _load_terminal_row(row), []
    profile = PROFILE_BY_METHOD[str(row["method_id"])]
    attempts_root = _attempt_directories(row)
    attempts_root.mkdir(parents=True, exist_ok=True)
    attempt_records: list[dict[str, Any]] = []
    for attempt_number in (1, 2):
        attempt_root = attempts_root / f"attempt_{attempt_number:02d}"
        result_path = attempt_root / "ATTEMPT_RESULT.json"
        if result_path.is_file():
            result = json.loads(result_path.read_text(encoding="utf-8"))
            _validate_attempt_result(
                result, row=row, attempt_number=attempt_number,
                attempt_root=attempt_root, output_root=output,
            )
            attempt_records.append(result)
            if result.get("terminal_status") in TERMINAL_STATUSES:
                return _promote_terminal_attempt(
                    row=row, attempt_root=attempt_root, output_root=output,
                ), attempt_records
            if attempt_number == 1 and (
                result.get("terminal_status") == "TECHNICAL_FAILURE_RETRYABLE"
                and result.get("retry_authorized") is True
            ):
                continue
            raise ExecutionPlanError(
                f"BLOCKED_CANONICAL541_UNEXPLAINED_TECHNICAL_FAILURE:"
                f"{row['run_id']}:attempt_{attempt_number:02d}_{result.get('terminal_status')}"
            )
        if attempt_root.exists():
            # 中文说明：没有终态 sidecar 的 partial attempt 必须保留并 fail closed；
            # 不能把未知中断自动解释成一次可重试技术失败。
            raise ExecutionPlanError(
                f"BLOCKED_CANONICAL541_UNEXPLAINED_TECHNICAL_FAILURE:"
                f"{row['run_id']}:partial_attempt_{attempt_number:02d}"
            )
        if attempt_number == 2:
            previous_path = attempts_root / "attempt_01/ATTEMPT_RESULT.json"
            if not previous_path.is_file():
                raise ExecutionPlanError("attempt_02 lacks an explicit attempt_01 authorization")
            previous = json.loads(previous_path.read_text(encoding="utf-8"))
            if not (
                previous.get("terminal_status") == "TECHNICAL_FAILURE_RETRYABLE"
                and previous.get("retry_authorized") is True
            ):
                raise ExecutionPlanError("attempt_02 is not authorized by attempt_01")
        attempt_root.mkdir(parents=False, exist_ok=False)
        attempt_config = _attempt_config(
            Path(str(row["runtime_config_template_path"])).resolve(strict=True),
            attempt_root / "CANONICAL541_RUNTIME_CONFIG.yaml", attempt_root,
        )
        proof = run_unique_execution(
            executable=executable, runtime_config=attempt_config,
            method_bound_manifest=row["method_bound_manifest_path"], output_root=attempt_root,
            profile=profile, case_id=str(row["case_id"]), run_id=str(row["run_id"]),
            raw_root=raw_root, clean_root=clean_root, repo_root=repo_root,
            expected_executable_hash=str(row["executable_hash"]),
            expected_runtime_config_hash=sha256_file(attempt_config),
            expected_scientific_config_hash=str(row["runtime_config_hash"]),
            expected_method_bound_manifest_hash=str(row["method_bound_manifest_hash"]),
            timeout_seconds=timeout_seconds,
        )
        proof["runtime_config_path"] = str(attempt_config)
        # The execution proof was written before this immutable path annotation.
        proof_bytes = (json.dumps(proof, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (attempt_root / "CANONICAL541_EXECUTION_PROOF.json").write_bytes(proof_bytes)
        (attempt_root / "CANONICAL541_FORMAL_RUN_MANIFEST.json").write_bytes(proof_bytes)
        result = {
            "run_id": row["run_id"], "method_id": row["method_id"], "case_id": row["case_id"],
            "attempt": attempt_number, "terminal_status": proof["terminal_status"],
            "failure_type": proof["failure_type"], "returncode": proof["returncode"],
            "technical_retry": attempt_number == 2,
            "retry_authorized": proof["terminal_status"] == "TECHNICAL_FAILURE_RETRYABLE" and attempt_number == 1,
            "runtime_config_hash": proof["runtime_config_hash"],
            "scientific_runtime_contract_sha256": proof["scientific_runtime_contract_sha256"],
            "actual_rendered_runtime_config_sha256": proof["actual_rendered_runtime_config_sha256"],
            "executable_hash": proof["executable_hash"], "runtime_seconds": proof["runtime_seconds"],
            "metric_driven_rerun": False,
            "attempt_root": str(attempt_root.resolve(strict=False)),
            "output_root": str(output.resolve(strict=False)),
            "runtime_config_path": str(attempt_config),
        }
        (attempt_root / "ATTEMPT_RESULT.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        attempt_records.append(result)
        if proof["terminal_status"] in TERMINAL_STATUSES:
            return _promote_terminal_attempt(
                row=row, attempt_root=attempt_root, output_root=output,
            ), attempt_records
        if proof["terminal_status"] != "TECHNICAL_FAILURE_RETRYABLE":
            raise ExecutionPlanError(f"BLOCKED_CANONICAL541_UNEXPLAINED_TECHNICAL_FAILURE:{row['run_id']}")
    raise ExecutionPlanError(f"BLOCKED_CANONICAL541_UNEXPLAINED_TECHNICAL_FAILURE:{row['run_id']}:retry_exhausted")


def rebuild_attempt_registry(*, stage_root: str | Path) -> list[dict[str, Any]]:
    stage = validate_attempt_root(stage_root); rows: list[dict[str, Any]] = []
    for parent in (stage / "08_FULL_ALGORITHM_RUNS/.attempts", stage / "10_INTERNAL_ABLATION_RUNS/.attempts"):
        if not parent.exists():
            continue
        for path in sorted(parent.glob("*/attempt_*/ATTEMPT_RESULT.json")):
            row = json.loads(path.read_text(encoding="utf-8"))
            if row.get("attempt_root") != str(path.parent.resolve(strict=True)):
                raise ExecutionPlanError("attempt registry attempt_root drift")
            rows.append(row)
    for parent in (stage / "08_FULL_ALGORITHM_RUNS", stage / "10_INTERNAL_ABLATION_RUNS"):
        if not parent.exists():
            continue
        for path in sorted(parent.glob("RUN_*/ATTEMPT_RESULT.json")):
            row = json.loads(path.read_text(encoding="utf-8"))
            if row.get("output_root") != str(path.parent.resolve(strict=True)):
                raise ExecutionPlanError("attempt registry output_root drift")
            rows.append(row)
    rows.sort(key=lambda row: (str(row["run_id"]), int(row["attempt"])))
    if rows:
        write_csv_atomic(stage / "07_FULL_ALGORITHM_REGISTRY/CANONICAL541_RUN_ATTEMPTS.csv", rows)
    return rows


def persist_execution_status(*, stage_root: str | Path, unique_rows: Sequence[Mapping[str, Any]],
                             logical_rows: Sequence[Mapping[str, Any]]) -> None:
    stage = validate_attempt_root(stage_root)
    by_run = {str(row["run_id"]): row for row in unique_rows}
    resolved_logical = []
    for source in logical_rows:
        row = dict(source); unique = by_run[str(row["run_id"])]
        row["terminal_status"] = unique.get("terminal_status", "PENDING")
        row["output_root"] = unique["output_root"]
        resolved_logical.append(row)
    unique_path = write_csv_atomic(stage / "07_FULL_ALGORITHM_REGISTRY/CANONICAL541_UNIQUE_RUN_REGISTRY.csv", unique_rows)
    write_csv_atomic(stage / "07_FULL_ALGORITHM_REGISTRY/FULL_ALGORITHM_QUEUE.csv",
                     [row for row in resolved_logical if row["matrix"] == "full_algorithm"])
    write_csv_atomic(stage / "09_INTERNAL_ABLATION_REGISTRY/INTERNAL_ABLATION_QUEUE.csv",
                     [row for row in resolved_logical if row["matrix"] == "internal_ablation"])
    plan_path = stage / "07_FULL_ALGORITHM_REGISTRY/EXECUTION_PLAN.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["unique_registry_sha256"] = sha256_file(unique_path)
    plan["terminal_unique_run_count"] = sum(row.get("terminal_status") in TERMINAL_STATUSES for row in unique_rows)
    temporary = plan_path.with_name(f".{plan_path.name}.tmp_{os.getpid()}")
    temporary.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, plan_path)


def execute_unique_selection(
    *, selected_run_ids: Iterable[str], unique_rows: Sequence[Mapping[str, Any]],
    logical_rows: Sequence[Mapping[str, Any]], stage_root: str | Path,
    executable: str | Path, raw_root: str | Path, clean_root: str | Path,
    repo_root: str | Path, code_freeze_commit: str, jobs: int,
    timeout_seconds: int = 1800,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not 1 <= jobs <= 16:
        raise ExecutionPlanError("solver jobs must be 1..16")
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[name] = "1"
    repo = Path(repo_root).resolve(strict=True); binary = Path(executable).resolve(strict=True)
    commit, dirty = git_code_state(repo)
    if dirty or commit != code_freeze_commit:
        raise ExecutionPlanError("formal execution requires exact clean code freeze")
    selected = set(str(value) for value in selected_run_ids)
    by_run = {str(row["run_id"]): dict(row) for row in unique_rows}
    executable_hashes = {str(row["executable_hash"]) for row in unique_rows}
    if len(executable_hashes) != 1 or executable_hashes != {sha256_file(binary)}:
        raise ExecutionPlanError("execution plan does not bind one exact executable SHA256")
    if not selected.issubset(by_run):
        raise ExecutionPlanError("execution selection references unknown run IDs")
    records: list[dict[str, Any]] = []
    failures: list[BaseException] = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(
                _run_one_with_retry, by_run[run_id], executable=binary,
                raw_root=Path(raw_root).resolve(strict=True), clean_root=Path(clean_root).resolve(strict=True),
                repo_root=repo, timeout_seconds=timeout_seconds,
            ): run_id
            for run_id in sorted(selected, key=lambda value: int(by_run[value]["run_order"]))
        }
        for future in as_completed(futures):
            try:
                updated, _ = future.result(); by_run[str(updated["run_id"])] = updated; records.append(updated)
            except BaseException as exc:
                failures.append(exc)
    updated_rows = [by_run[str(row["run_id"])] for row in unique_rows]
    persist_execution_status(stage_root=stage_root, unique_rows=updated_rows, logical_rows=logical_rows)
    rebuild_attempt_registry(stage_root=stage_root)
    commit_after, dirty_after = git_code_state(repo)
    if dirty_after or commit_after != code_freeze_commit or sha256_file(binary) != next(iter(executable_hashes)):
        raise ExecutionPlanError("code/executable changed during formal execution")
    if failures:
        raise failures[0]
    return updated_rows, records


def matrix_terminal_gate(*, matrix: str, unique_rows: Sequence[Mapping[str, Any]],
                         logical_rows: Sequence[Mapping[str, Any]], output_path: str | Path) -> dict[str, Any]:
    selected = [row for row in logical_rows if row["matrix"] == matrix]
    by_run = {str(row["run_id"]): row for row in unique_rows}
    expected_count = 2164 if matrix == "full_algorithm" else 4869
    terminal = [row for row in selected if by_run[str(row["run_id"])].get("terminal_status") in TERMINAL_STATUSES]
    report = {
        "matrix": matrix, "logical_row_count": len(selected), "terminal_logical_row_count": len(terminal),
        "unique_run_count": len({str(row["run_id"]) for row in selected}),
        "unknown_or_missing": len(selected) - len(terminal), "metric_read_count": 0,
        "trace_used_online": False, "passed": len(selected) == len(terminal) == expected_count,
    }
    destination = Path(output_path); destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not report["passed"]:
        raise ExecutionPlanError(f"{matrix} logical terminal gate failed")
    return report
