"""Package trusted-direct Canonical-541 evidence without terminal-audit inputs.

This route trusts the already-created output seal and current generated
analysis artifacts.  It deliberately does not resolve or hash raw, provider,
prepared-input, or runtime-output payload paths.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import yaml

from .authorization import validate_attempt_root
from .evidence import PayloadSpec, create_final_zip, finalize_curated_evidence, sha256_file
from .plots import FIGURE_SPECS, render_diagnostic_figures


class TrustedDirectEvidenceError(RuntimeError):
    """Raised when trusted-direct generated evidence is incomplete."""


TERMINAL_STATUSES = {"COMPLETED_EVALUABLE", "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF"}
ANALYSIS_FILES = {
    "full_rows": "FULL_ALGORITHM_ROW_RESULTS.csv.gz",
    "ablation_rows": "INTERNAL_ABLATION_ROW_RESULTS.csv.gz",
    "paired_deltas": "PAIRED_METHOD_DELTAS.csv.gz",
    "recovery_metrics": "RECOVERY_METRICS.csv",
    "finite_failure": "FINITE_AND_FAILURE_SUMMARY.csv",
    "worst_cases": "WORST_CASES.csv",
}
MECHANISM_FILES = {
    "source_aware_actions": "SOURCE_AWARE_ACTIONS.csv.gz",
    "schemec_actions": "SCHEMEC_ACTIONS.csv",
}
ANALYSIS_SUPPORT = (
    "FULL_ALGORITHM_METHOD_SUMMARY.csv", "FULL_ALGORITHM_FAMILY_SUMMARY.csv",
    "FULL_ALGORITHM_DEGRADATION_TYPE_SUMMARY.csv",
    "INTERNAL_ABLATION_METHOD_SUMMARY.csv", "INTERNAL_ABLATION_FAMILY_SUMMARY.csv",
    "INTERNAL_ABLATION_DEGRADATION_TYPE_SUMMARY.csv", "SEED_SIGN_CONSISTENCY.csv",
    "BOOTSTRAP_INTERVALS.csv", "METHOD_CLEAN_PENALTIES.csv", "AGGREGATE_CROSSCHECK.json",
)
MECHANISM_SUPPORT: tuple[str, ...] = ()
REGISTRY_PATHS = (
    "07_FULL_ALGORITHM_REGISTRY/FULL_ALGORITHM_QUEUE.csv",
    "07_FULL_ALGORITHM_REGISTRY/CANONICAL541_UNIQUE_RUN_REGISTRY.csv",
    "07_FULL_ALGORITHM_REGISTRY/PROVIDER_CONFIG_EXECUTABLE_HASH_REGISTRY.csv",
    "07_FULL_ALGORITHM_REGISTRY/PREPARATION_STATUS.json",
    "07_FULL_ALGORITHM_REGISTRY/EXECUTION_PLAN.json",
    "09_INTERNAL_ABLATION_REGISTRY/INTERNAL_ABLATION_QUEUE.csv",
)
SEAL_PATHS = (
    "11_OUTPUT_SEAL/OUTPUT_HASH_MANIFEST.csv",
    "11_OUTPUT_SEAL/OUTPUT_SEAL_JOURNAL.json",
    "11_OUTPUT_SEAL/UNIQUE_RUN_TERMINAL_REGISTRY.csv",
    "11_OUTPUT_SEAL/LOGICAL_RESULT_TERMINAL_REGISTRY.csv",
    "11_OUTPUT_SEAL/RUN_ATTEMPTS.csv",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file() or path.is_symlink():
        raise TrustedDirectEvidenceError(f"required generated CSV missing/non-regular: {path}")
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        if not reader.fieldnames or not rows:
            raise TrustedDirectEvidenceError(f"generated CSV is empty or schema-less: {path}")
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise TrustedDirectEvidenceError(f"required generated JSON missing/non-regular: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TrustedDirectEvidenceError(f"generated JSON is not an object: {path}")
    return payload


def _truth(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "pass"}


def _require_exact_counts(payload: Mapping[str, Any], expected: Mapping[str, int], label: str) -> None:
    mismatches = {key: (payload.get(key), value) for key, value in expected.items()
                  if payload.get(key) != value}
    if mismatches:
        raise TrustedDirectEvidenceError(f"{label} count closure failed: {mismatches}")


def _validate_plan_and_registries(stage: Path) -> None:
    full = _read_csv(stage / REGISTRY_PATHS[0])
    unique = _read_csv(stage / REGISTRY_PATHS[1])
    hashes = _read_csv(stage / REGISTRY_PATHS[2])
    status = _read_json(stage / REGISTRY_PATHS[3])
    plan = _read_json(stage / REGISTRY_PATHS[4])
    ablation = _read_csv(stage / REGISTRY_PATHS[5])
    if (len(full), len(ablation), len(unique), len(hashes)) != (2164, 4869, 5951, 5951):
        raise TrustedDirectEvidenceError("generated registry rows do not close at 2164/4869/5951/5951")
    _require_exact_counts(plan, {"logical_row_count": 7033, "full_logical_row_count": 2164,
                                 "ablation_logical_row_count": 4869, "unique_run_count": 5951},
                          "execution plan")
    if plan.get("passed") is not True:
        raise TrustedDirectEvidenceError("execution plan is unresolved")
    if status.get("method_bound_completed") != 5951 or status.get("unique_runs_planned") != 5951:
        raise TrustedDirectEvidenceError("preparation status is not closed at 5951")


def _validate_sealed_terminal_registries(stage: Path) -> dict[str, Any]:
    root = stage / "11_OUTPUT_SEAL"
    manifest = root / "OUTPUT_HASH_MANIFEST.csv"
    journal = _read_json(root / "OUTPUT_SEAL_JOURNAL.json")
    _require_exact_counts(journal, {"unique_run_count": 5951, "logical_result_count": 7033,
                                    "full_algorithm_logical_rows": 2164,
                                    "internal_ablation_logical_rows": 4869}, "output seal")
    if (journal.get("passed") is not True or journal.get("all_hashes_recorded") is not True
            or journal.get("all_logical_rows_terminal") is not True
            or journal.get("sealed_before_offline_trace") is not True
            or journal.get("trace_open_count_before_seal") != 0):
        raise TrustedDirectEvidenceError("output seal is not terminal and trace-safe")
    files = {
        "manifest_sha256": manifest,
        "unique_registry_sha256": root / "UNIQUE_RUN_TERMINAL_REGISTRY.csv",
        "logical_registry_sha256": root / "LOGICAL_RESULT_TERMINAL_REGISTRY.csv",
        "run_attempts_sha256": root / "RUN_ATTEMPTS.csv",
    }
    for field, path in files.items():
        if journal.get(field) != sha256_file(path):
            raise TrustedDirectEvidenceError(f"sealed generated artifact hash drift: {path.name}")
    unique = _read_csv(files["unique_registry_sha256"])
    logical = _read_csv(files["logical_registry_sha256"])
    attempts = _read_csv(files["run_attempts_sha256"])
    manifest_rows = _read_csv(manifest)
    if (len(unique) != 5951 or len(logical) != 7033
            or len(attempts) != journal.get("run_attempt_count")
            or len(manifest_rows) != journal.get("file_count")):
        raise TrustedDirectEvidenceError("sealed registry row count drift")
    run_ids = [str(row.get("run_id", "")) for row in unique]
    logical_ids = [str(row.get("logical_id", row.get("logical_row_id", ""))) for row in logical]
    run_id_set = set(run_ids)
    if ("" in run_ids or len(run_id_set) != 5951 or "" in logical_ids
            or len(set(logical_ids)) != 7033
            or any(str(row.get("run_id", "")) not in run_id_set for row in logical)
            or any(str(row.get("terminal_status", "")) not in TERMINAL_STATUSES for row in (*unique, *logical))):
        raise TrustedDirectEvidenceError("sealed terminal registries contain unresolved or duplicate identities")
    required = {"run_id", "relative_path", "terminal_status", "sealed_before_trace", "sha256", "size_bytes"}
    if not required.issubset(manifest_rows[0]) or any(
        not row["relative_path"] or "\\" in row["relative_path"]
        or Path(row["relative_path"]).is_absolute() or ".." in Path(row["relative_path"]).parts
        or row["run_id"] not in run_id_set or not _truth(row["sealed_before_trace"])
        or row["terminal_status"] not in TERMINAL_STATUSES
        or not row["size_bytes"].isdigit() or len(row["sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in row["sha256"])
        for row in manifest_rows
    ):
        raise TrustedDirectEvidenceError("output proof manifest contains unsafe or unresolved rows")
    return {"unique_terminal_count": 5951, "logical_terminal_count": 7033,
            "output_manifest_row_count": len(manifest_rows), "runtime_payload_rehash_count": 0}


def _load_analysis_tables(stage: Path) -> dict[str, list[dict[str, str]]]:
    analysis = stage / "13_RESULT_ANALYSIS"
    mechanism = stage / "14_MECHANISM_ANALYSIS"
    tables = {key: _read_csv(analysis / name) for key, name in ANALYSIS_FILES.items()}
    tables.update({key: _read_csv(mechanism / name) for key, name in MECHANISM_FILES.items()})
    for name in ANALYSIS_SUPPORT:
        path = analysis / name
        _read_json(path) if path.suffix == ".json" else _read_csv(path)
    for name in MECHANISM_SUPPORT:
        rows = _read_csv(mechanism / name)
        if not all(_truth(row.get("passed", row.get("invariant_pass", False))) for row in rows):
            raise TrustedDirectEvidenceError("source isolation analysis is unresolved")
    full, ablation = tables["full_rows"], tables["ablation_rows"]
    if (len(full), len(ablation)) != (2164, 4869):
        raise TrustedDirectEvidenceError("analysis rows do not close at 7033")
    for label, rows, methods in (("full", full, {f"F{i:02d}" for i in range(1, 5)}),
                                  ("ablation", ablation, {f"A{i:02d}" for i in range(1, 10)})):
        counts = Counter(str(row.get("method_id", "")) for row in rows)
        logical_ids = [str(row.get("logical_id", row.get("logical_row_id", ""))) for row in rows]
        cases = {str(row.get("case_id", "")) for row in rows}
        if (set(counts) != methods or set(counts.values()) != {541}
                or len(cases) != 541 or "C00_clean_normal" not in cases or "" in logical_ids
                or len(set(logical_ids)) != len(rows)
                or any(str(row.get("terminal_status", "")) not in TERMINAL_STATUSES for row in rows)):
            raise TrustedDirectEvidenceError(f"{label} analysis is missing or unresolved")
    for relative in ("12_OFFLINE_EVALUATION/AGGREGATE_CROSSCHECK.json",
                     "13_RESULT_ANALYSIS/AGGREGATE_CROSSCHECK.json"):
        if _read_json(stage / relative).get("passed") is not True:
            raise TrustedDirectEvidenceError(f"generated crosscheck has not passed: {relative}")
    tables["logical_unique"] = []
    for matrix, rows in (("full_algorithm", full), ("internal_ablation", ablation)):
        ids = {str(row.get("run_id", "")) for row in rows}
        if "" in ids:
            raise TrustedDirectEvidenceError(f"{matrix} analysis lacks run identity")
        tables["logical_unique"].append({"matrix": matrix, "logical_row_count": len(rows),
                                          "unique_execution_count": len(ids),
                                          "execution_alias_count": len(rows) - len(ids)})
    return tables


def _table_hashes(stage: Path, tables: Mapping[str, Any]) -> dict[str, str]:
    hashes = {key: sha256_file(stage / "13_RESULT_ANALYSIS" / name)
              for key, name in ANALYSIS_FILES.items()}
    hashes.update({key: sha256_file(stage / "14_MECHANISM_ANALYSIS" / name)
                   for key, name in MECHANISM_FILES.items()})
    encoded = json.dumps(tables["logical_unique"], sort_keys=True, separators=(",", ":")).encode()
    hashes["logical_unique"] = hashlib.sha256(encoded).hexdigest()
    return hashes


def _ensure_figures(stage: Path, attempt_id: str, tables: Mapping[str, Any]) -> dict[str, Any]:
    root = stage / "15_DIAGNOSTIC_FIGURES"
    final = root / "FINALIZED"
    expected = {f"{stem}.{suffix}" for stem, _ in FIGURE_SPECS for suffix in ("png", "pdf")}
    if final.is_dir() and not final.is_symlink():
        qa = _read_json(final / "FIGURE_RENDER_QA.json")
    else:
        root.mkdir(parents=True, exist_ok=True)
        staging = root / f".staging_{attempt_id}"
        try:
            qa = render_diagnostic_figures(tables=tables, output_root=staging,
                                           table_hashes=_table_hashes(stage, tables))
            if qa.get("passed") is not True:
                raise TrustedDirectEvidenceError("diagnostic figure QA failed")
            os.replace(staging, final)
        except Exception:
            if staging.exists() and staging.name == f".staging_{attempt_id}":
                shutil.rmtree(staging)
            raise
    entries = tuple(final.iterdir())
    if any(not path.is_file() or path.is_symlink() for path in entries):
        raise TrustedDirectEvidenceError("finalized diagnostic figures contain a non-regular entry")
    actual = {path.name for path in entries}
    if (qa.get("passed") is not True or qa.get("figure_count") != 25
            or actual != expected | {"FIGURE_RENDER_QA.json"}):
        raise TrustedDirectEvidenceError("finalized diagnostic figure set is incomplete")
    return qa


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise TrustedDirectEvidenceError(f"immutable direct closure already exists: {path}")
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)


def _generated_payloads(stage: Path, closure: Path) -> list[PayloadSpec]:
    relative_paths = [*REGISTRY_PATHS, *SEAL_PATHS,
                      "12_OFFLINE_EVALUATION/AGGREGATE_CROSSCHECK.json"]
    relative_paths += [f"13_RESULT_ANALYSIS/{name}" for name in (*ANALYSIS_FILES.values(), *ANALYSIS_SUPPORT)]
    relative_paths += [f"14_MECHANISM_ANALYSIS/{name}" for name in (*MECHANISM_FILES.values(), *MECHANISM_SUPPORT)]
    optional = ("13_RESULT_ANALYSIS/REPRESENTATIVE_WORST_ERROR_SERIES.csv.gz",
                "13_RESULT_ANALYSIS/REPRESENTATIVE_RECOVERY_ERROR_SERIES.csv.gz")
    relative_paths += [name for name in optional if (stage / name).is_file()]
    figure_root = stage / "15_DIAGNOSTIC_FIGURES/FINALIZED"
    relative_paths += [path.relative_to(stage).as_posix() for path in sorted(figure_root.iterdir()) if path.is_file()]
    relative_paths.append(closure.relative_to(stage).as_posix())
    payloads = []
    for relative in relative_paths:
        source = stage / relative
        if not source.is_file() or source.is_symlink():
            raise TrustedDirectEvidenceError(f"required curated generated artifact missing: {relative}")
        lower = source.suffix.lower()
        if relative.startswith(("05_PROVIDER_GENERATION/", "08_FULL_ALGORITHM_RUNS/", "10_INTERNAL_ABLATION_RUNS/")) or lower in {".nav", ".std", ".imu", ".gnss"}:
            raise TrustedDirectEvidenceError(f"forbidden payload selected for direct evidence: {relative}")
        head = Path(relative).parts[0]
        role = {"07_FULL_ALGORITHM_REGISTRY": "generated_registry_and_plan",
                "09_INTERNAL_ABLATION_REGISTRY": "generated_registry_and_plan",
                "11_OUTPUT_SEAL": "output_seal_and_proof_registry",
                "12_OFFLINE_EVALUATION": "offline_evaluation_crosscheck",
                "13_RESULT_ANALYSIS": "result_analysis",
                "14_MECHANISM_ANALYSIS": "mechanism_analysis",
                "15_DIAGNOSTIC_FIGURES": "finalized_diagnostic_figure"}.get(head, "direct_evidence_closure")
        payloads.append(PayloadSpec(source, relative, role, "current_generated_artifact"))
    return payloads


def _bind_local_config(local_config: str | Path, stage_root: str | Path,
                       export_root: str | Path) -> tuple[Path, Path]:
    config = Path(local_config).resolve(strict=True)
    payload = yaml.safe_load(config.read_text(encoding="utf-8"))
    paths = payload.get("paths") if isinstance(payload, dict) else None
    if not isinstance(paths, dict) or "runtime_root" not in paths or "export_root" not in paths:
        raise TrustedDirectEvidenceError("local config lacks runtime_root/export_root")
    stage = validate_attempt_root(stage_root)
    expected_stage = validate_attempt_root(paths["runtime_root"])
    export = Path(export_root).resolve(strict=True)
    expected_export = Path(str(paths["export_root"])).resolve(strict=True)
    if stage != expected_stage or export != expected_export:
        raise TrustedDirectEvidenceError("supplied stage/export root does not match local config")
    return stage, export


def package_trusted_direct(*, local_config: str | Path, stage_root: str | Path,
                           export_root: str | Path, attempt_id: str,
                           timestamp: str) -> dict[str, Any]:
    """Create one generated-artifact-only evidence directory and final ZIP."""

    if not re.fullmatch(r"\d{8}T\d{6}P0800", timestamp):
        raise TrustedDirectEvidenceError("timestamp must be YYYYMMDDTHHMMSSP0800")
    if not attempt_id or not re.fullmatch(r"[A-Za-z0-9_-]+", attempt_id):
        raise TrustedDirectEvidenceError("attempt_id contains unsafe characters")
    stage, export = _bind_local_config(local_config, stage_root, export_root)
    _validate_plan_and_registries(stage)
    seal = _validate_sealed_terminal_registries(stage)
    tables = _load_analysis_tables(stage)
    figures = _ensure_figures(stage, attempt_id, tables)
    closure_path = stage / "DIRECT_EVIDENCE_CLOSURE.json"
    _atomic_json(closure_path, {
        "schema_version": "paper_rebuild.canonical541.trusted_direct_evidence_closure.v1",
        "packaging_route": "TRUSTED_DIRECT_GENERATED_ARTIFACTS_ONLY",
        "payload_hash_scope": "generated_artifacts_only",
        "raw_payload_rehash_performed": False,
        "provider_payload_rehash_performed": False,
        "input_payload_rehash_performed": False,
        "runtime_output_payload_rehash_performed": False,
        "terminal_audit_read": False,
        "raw_checkpoint_read": False,
        "readiness_or_governance_sidecar_read": False,
        "terminal_registry_counts": seal,
        "analysis_logical_row_count": 7033,
        "figure_count": figures["figure_count"],
        "passed": True,
    })
    payloads = _generated_payloads(stage, closure_path)
    evidence = finalize_curated_evidence(stage_evidence_root=stage / "17_FINAL_EVIDENCE",
                                         attempt_id=attempt_id, payloads=payloads)
    zip_path = export / f"LegSA_GINS_CANONICAL541_FINAL_{timestamp}.zip"
    archive = create_final_zip(finalized_root=stage / "17_FINAL_EVIDENCE/FINALIZED",
                               zip_path=zip_path)
    return {"terminal_status": "PASS_CANONICAL541_TRUSTED_DIRECT_EVIDENCE_CLOSURE",
            "closure_path": str(closure_path), "payload_count": len(payloads),
            "evidence": evidence, "archive": archive, "passed": True}
