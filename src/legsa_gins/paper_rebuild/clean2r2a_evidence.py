"""CLEAN2R2A terminal audits, manifest/sidecar closure, and one final ZIP."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import shutil
import stat
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Iterable

from .clean2r2a_run_registry import build_clean_run_registry
from .clean2r2a_runner import (
    CANONICAL_PROVIDER_PROTOCOL_RELATIVE,
    CANONICAL_PROVIDER_PROTOCOL_SHA256,
    FORMAL_SCHEMA_NAME,
    METHOD_ORDER,
    mechanism_evidence,
    run_directory,
    validate_counters,
    validate_formal_wrapper,
    validate_output_seal,
    validate_solver_manifest,
    TECHNICAL_FAILURE_CLASSES,
    validate_canonical_provider_protocol,
)
from .manifest import sha256_file, write_json_atomic
from .clean2r2a_evaluator import revalidate_offline_evaluation


STAGE_ID = "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD"
TERMINAL_STATUS = "PASS_CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_FRESH_EVIDENCE_READY_FOR_HUMAN_REVIEW"


class Clean2R2AEvidenceError(RuntimeError):
    """Terminal evidence did not close."""


def _registry_closes(actual: list[dict[str, str]], contract: Path) -> bool:
    expected = build_clean_run_registry(contract)
    if len(actual) != len(expected) or not expected:
        return False
    identity_fields = (
        "run_order", "run_id", "stage_id", "case_id", "data_mode",
        "configuration_id", "algorithm_id", "role", "backbone_method_id",
        "bit_string", "canonical_equivalent_method_id",
        "enable_dual_yaw", "enable_receiver_velocity", "enable_raw_doppler",
        "enable_source_aware", "enable_go2_roll_pitch_prior",
        "enable_go2_horizontal_velocity_prior", "synthetic_data_used",
        "semisynthetic_data_used", "trace_used_online", "per_case_tuning",
        "metric_driven_rerun", "profile_identity_hash",
    )
    return all(
        all(str(observed.get(field)) == str(frozen.get(field)) for field in identity_fields)
        for observed, frozen in zip(actual, expected, strict=True)
    )


def _attempts_close(attempts: list[dict[str, str]]) -> tuple[bool, int]:
    by_method: dict[str, list[dict[str, str]]] = {}
    for row in attempts:
        by_method.setdefault(row.get("method_id", ""), []).append(row)
    if set(by_method) != set(METHOD_ORDER):
        return False, 0
    retry_count = 0
    for method_id, rows in by_method.items():
        if not 1 <= len(rows) <= 2:
            return False, 0
        rows.sort(key=lambda row: int(row["attempt"]))
        if [int(row["attempt"]) for row in rows] != list(range(1, len(rows) + 1)):
            return False, 0
        if any(row.get("metric_driven_rerun") != "False" for row in rows):
            return False, 0
        if any(row.get("failure_class") != "success" for row in rows[-1:]):
            return False, 0
        if rows[-1].get("terminal_success") != "True" or rows[-1].get("returncode") != "0":
            return False, 0
        if len(rows) == 2:
            retry_count += 1
            if (
                rows[0].get("technical_failure") != "True"
                or rows[0].get("failure_class") not in TECHNICAL_FAILURE_CLASSES
                or rows[0].get("retry_authorized") != "True"
                or rows[1].get("technical_retry") != "True"
                or rows[0].get("runtime_config_hash") != rows[1].get("runtime_config_hash")
                or rows[0].get("executable_hash") != rows[1].get("executable_hash")
            ):
                return False, 0
    return True, retry_count


def initialize_stage_documents(
    *, stage_root: str | Path, repo_root: str | Path, code_freeze_commit: str,
) -> dict[str, Any]:
    stage = Path(stage_root).resolve(strict=True)
    repo = Path(repo_root).resolve(strict=True)
    validate_canonical_provider_protocol(repo, repo / CANONICAL_PROVIDER_PROTOCOL_RELATIVE)
    authorization = {
        "schema_version": "paper_rebuild.clean2r2a_authorization.v1",
        "stage_id": STAGE_ID, "dataset": "BY2", "data_mode": "real_clean",
        "canonical_data_mode": "real_by2_raw", "clean_ablation_authorized": True,
        "degradation_execution_authorized": False, "full_matrix_authorized": False,
        "by3_authorized": False, "xb_authorized": False, "fgo_authorized": False,
        "qm_qa_contact_authorized": False, "formal_run_count": 18,
        "degradation_run_count": 0, "D01_D60_audit_count": 0,
    }
    write_json_atomic(stage / "00_AUTHORIZATION" / "CLEAN2R2A_AUTHORIZATION.json", authorization)
    (stage / "00_AUTHORIZATION" / "CLEAN2R2A_AUTHORIZATION.md").write_text(
        "# CLEAN2R2A authorization\n\nOnly the 18-run BY2 real-clean module ablation is authorized. "
        "No degradation definition, audit, provider, or solver run belongs to this stage.\n",
        encoding="utf-8",
    )
    freeze = {
        "schema_version": "paper_rebuild.clean2r2a_git_freeze.v1",
        "stage_id": STAGE_ID, "branch": "stage/clean2r2-by2-ablation-full-60x9",
        "code_freeze_commit": code_freeze_commit, "clean1_merge_commit": "eddc536b36d87c760bd7c6a3184f2ff724a8ea78",
        "provider_generated_before_freeze": False, "formal_solver_run_before_freeze": False,
        "trace_opened_before_freeze": False,
    }
    write_json_atomic(stage / "01_GIT_FREEZE" / "CLEAN2R2A_GIT_FREEZE.json", freeze)
    snapshots = (
        "configs/paper_rebuild/clean2r2a_ablation_2pow4.yaml",
        "configs/paper_rebuild/clean2r2a_execution_protocol.yaml",
        "configs/paper_rebuild/clean2r2a_statistical_contract.yaml",
        "configs/paper_rebuild/clean2r2a_formal_manifest_schema.yaml",
        CANONICAL_PROVIDER_PROTOCOL_RELATIVE.as_posix(),
        "configs/paper_rebuild/final_v23_parity_contract.yaml",
        "configs/paper_rebuild/methods.yaml",
    )
    for relative in snapshots:
        source = repo / relative
        shutil.copy2(source, stage / "02_PROTOCOLS" / source.name)
    write_json_atomic(stage / "02_PROTOCOLS" / "PROTOCOL_SNAPSHOT_MANIFEST.json", {
        "schema_version": "paper_rebuild.clean2r2a_protocol_snapshot.v1",
        "files": {Path(relative).name: sha256_file(repo / relative) for relative in snapshots},
        "degradation_spec_read": False, "classic18_config_read": False,
    })
    return freeze


def audit_terminal_stage(
    stage_root: str | Path,
    *,
    local_config: str | Path,
    exact_evaluator: str | Path,
) -> dict[str, Any]:
    stage = Path(stage_root).resolve(strict=True)
    sealed_rows = validate_output_seal(stage)
    raw_names = (
        "RAW_22_PRE_CODE_FREEZE.json", "RAW_22_PRE_PROVIDER.json",
        "RAW_22_POST_PROVIDER.json", "RAW_22_POST_RUN.json",
    )
    raw = [json.loads((stage / "03_RAW_AUDITS" / name).read_text(encoding="utf-8")) for name in raw_names]
    raw_mutations = [
        json.loads((stage / "03_RAW_AUDITS" / name).read_text(encoding="utf-8"))
        for name in (
            "RAW_PRE_POST_PROVIDER_MUTATION_AUDIT.json",
            "RAW_PRE_POST_RUN_MUTATION_AUDIT.json",
        )
    ]
    provider = json.loads((stage / "04_BASE_PROVIDER" / "CLEAN2R2A_BASE_PROVIDER_PARITY.json").read_text(encoding="utf-8"))
    provider_report_path = stage / "04_BASE_PROVIDER" / "CLEAN2R2A_BASE_PROVIDER_PARITY.json"
    source_quality = provider.get("source_quality_metadata", {})
    provider_closure = (
        provider.get("passed") is True
        and provider.get("provider_root_exact") is True
        and len(provider.get("raw_source_hashes", {})) == 22
        and isinstance(source_quality, dict)
        and sha256_file(Path(str(source_quality.get("path", ""))).resolve(strict=True))
        == source_quality.get("sha256")
        and sha256_file(Path(str(provider.get("clean_input_manifest_path", ""))).resolve(strict=True))
        == provider.get("clean_input_manifest_sha256")
        and sha256_file(Path(str(provider.get("auxiliary_manifest_path", ""))).resolve(strict=True))
        == provider.get("auxiliary_manifest_sha256")
        and provider.get("provider_protocol_sha256") == CANONICAL_PROVIDER_PROTOCOL_SHA256
        and provider.get("provider_protocol_relative_path") == CANONICAL_PROVIDER_PROTOCOL_RELATIVE.as_posix()
    )
    structural = json.loads((stage / "11_AUDITS" / "CLEAN2R2A_C00_STRUCTURAL_GATE.json").read_text(encoding="utf-8"))
    aggregate = json.loads((stage / "08_OFFLINE_EVALUATION" / "CLEAN2R2A_AGGREGATE_CROSSCHECK.json").read_text(encoding="utf-8"))
    evaluation_revalidation = revalidate_offline_evaluation(
        stage_root=stage,
        local_config=local_config,
        exact_evaluator=exact_evaluator,
        write_report=False,
    )
    figures = json.loads((stage / "10_DIAGNOSTIC_FIGURES" / "CLEAN2R2A_FIGURE_RENDER_QA.json").read_text(encoding="utf-8"))
    attempts = list(csv.DictReader((stage / "05_RUN_REGISTRY" / "CLEAN2R2A_RUN_ATTEMPTS.csv").open("r", encoding="utf-8", newline="")))
    registry = list(csv.DictReader((stage / "05_RUN_REGISTRY" / "CLEAN2R2A_CLEAN_RUN_REGISTRY.csv").open("r", encoding="utf-8", newline="")))
    schema_path = stage / "02_PROTOCOLS" / FORMAL_SCHEMA_NAME
    wrappers: list[dict[str, Any]] = []
    formal_closure = True
    clean_provider_payload = json.loads(
        Path(str(provider["clean_input_manifest_path"])).read_text(encoding="utf-8")
    )
    auxiliary_provider_payload = json.loads(
        Path(str(provider["auxiliary_manifest_path"])).read_text(encoding="utf-8")
    )
    expected_provider_hashes = {
        "clean_input_manifest": provider["clean_input_manifest_sha256"],
        "auxiliary_manifest": provider["auxiliary_manifest_sha256"],
        **provider["actual_hashes"],
        "source_quality_metadata": provider["source_quality_metadata"]["sha256"],
    }
    expected_generation = {
        "base_generator_code_commit": clean_provider_payload["generator_code_commit"],
        "base_generation_config_sha256": clean_provider_payload["generation_config_sha256"],
        "base_contract_sha256": clean_provider_payload["contract_sha256"],
        "auxiliary_code_freeze_commit": auxiliary_provider_payload["code_freeze_commit"],
        "auxiliary_bundle_hash": auxiliary_provider_payload["bundle_hash"],
        "provider_protocol_sha256": auxiliary_provider_payload["provider_protocol_sha256"],
    }
    for method in METHOD_ORDER:
        run_root = stage / "06_FORMAL_RUNS" / run_directory(method)
        wrapper = json.loads((run_root / "CLEAN2R2A_FORMAL_RUN_MANIFEST.json").read_text(encoding="utf-8"))
        validate_formal_wrapper(wrapper, schema_path)
        formal_closure = formal_closure and wrapper.get("formal_schema_hash") == sha256_file(schema_path)
        formal_closure = formal_closure and wrapper.get("base_provider_parity_sha256") == sha256_file(provider_report_path)
        formal_closure = formal_closure and wrapper.get("provider_hashes") == expected_provider_hashes
        formal_closure = formal_closure and wrapper.get("raw_source_hashes") == provider.get("raw_source_hashes")
        formal_closure = formal_closure and wrapper.get("provider_generation") == expected_generation
        formal_closure = formal_closure and wrapper.get("local_config_hash") == sha256_file(local_config)
        solver_manifest_path = run_root / "RUN_MANIFEST.json"
        solver_manifest = json.loads(solver_manifest_path.read_text(encoding="utf-8"))
        validate_solver_manifest(method, run_directory(method), solver_manifest)
        formal_closure = formal_closure and wrapper.get("solver_manifest_sha256") == sha256_file(solver_manifest_path)
        formal_closure = formal_closure and wrapper.get("module_counters") == validate_counters(method, solver_manifest)
        formal_closure = formal_closure and wrapper.get("mechanism_evidence") == mechanism_evidence(method, solver_manifest)
        for relative, digest in wrapper.get("output_hashes", {}).items():
            candidate = (run_root / relative).resolve(strict=True)
            formal_closure = formal_closure and run_root in candidate.parents and sha256_file(candidate) == digest
        for entry in wrapper.get("actual_solver_inputs", {}).values():
            candidate = Path(str(entry["path"])).resolve(strict=True)
            formal_closure = formal_closure and sha256_file(candidate) == entry["sha256"]
        wrappers.append(wrapper)
    attempts_close, technical_retry_count = _attempts_close(attempts)
    protocol_snapshot = json.loads(
        (stage / "02_PROTOCOLS" / "PROTOCOL_SNAPSHOT_MANIFEST.json").read_text(encoding="utf-8")
    )
    canonical_snapshot = stage / "02_PROTOCOLS" / CANONICAL_PROVIDER_PROTOCOL_RELATIVE.name
    protocol_snapshot_closes = (
        protocol_snapshot.get("files", {}).get(CANONICAL_PROVIDER_PROTOCOL_RELATIVE.name)
        == CANONICAL_PROVIDER_PROTOCOL_SHA256
        and sha256_file(canonical_snapshot) == CANONICAL_PROVIDER_PROTOCOL_SHA256
    )
    expected_stage_dirs = {
        "00_AUTHORIZATION", "01_GIT_FREEZE", "02_PROTOCOLS", "03_RAW_AUDITS",
        "04_BASE_PROVIDER", "05_RUN_REGISTRY", "06_FORMAL_RUNS", "07_OUTPUT_SEAL",
        "08_OFFLINE_EVALUATION", "09_FACTORIAL_ANALYSIS", "10_DIAGNOSTIC_FIGURES",
        "11_AUDITS", "12_FINAL_EVIDENCE",
    }
    actual_stage_dirs = {path.name for path in stage.iterdir() if path.is_dir()}
    formal_run_dirs = {
        path.name for path in (stage / "06_FORMAL_RUNS").iterdir()
        if path.is_dir() and not path.name.startswith(".")
    }
    clean_scope_proven = (
        actual_stage_dirs == expected_stage_dirs
        and formal_run_dirs == {run_directory(method) for method in METHOD_ORDER}
        and all(wrapper.get("case_id") == "CLEAN1_BY2_CLEAN_NORMAL" for wrapper in wrappers)
        and protocol_snapshot.get("degradation_spec_read") is False
        and protocol_snapshot.get("classic18_config_read") is False
        and protocol_snapshot_closes
    )
    forbidden_counts = {
        name: sum(int(wrapper["module_counters"][name]) for wrapper in wrappers)
        for name in ("fgo_count", "qm_count", "qa_count", "contact_fk_count")
    }
    gates = {
        "raw_checkpoints_22_22": len(raw) == 4 and all(item.get("verified") == 22 and item.get("passed") is True for item in raw),
        "raw_immutable": all(item.get("raw_mutation") == 0 and item.get("passed") is True for item in raw_mutations),
        "base_provider_parity": provider_closure,
        "canonical_provider_protocol": protocol_snapshot_closes,
        "ablation_variants_16": len([row for row in registry if str(row["configuration_id"]).startswith("AB")]) == 16,
        "structural_methods_2": sum(row.get("role") == "structural_baseline" for row in registry) == 2,
        "run_registry_exact": _registry_closes(registry, stage / "02_PROTOCOLS" / "clean2r2a_ablation_2pow4.yaml"),
        "unique_formal_runs_18": len(wrappers) == 18 and len({row["algorithm_id"] for row in wrappers}) == 18,
        "formal_schema_and_provenance_closure": formal_closure,
        "attempt_registry_closure": attempts_close,
        "all_terminal_pass": all(row.get("terminal_status") == "PASS" for row in wrappers),
        "all_outputs_finite": all(row.get("structure", {}).get("finite") is True for row in wrappers),
        "all_outputs_sealed_before_trace": bool(sealed_rows) and all(row.get("sealed_before_trace") == "True" for row in sealed_rows),
        "clean_structural_gate": structural.get("passed") is True,
        "strong_final_v23_identity": any(row.get("method_id") == "AB0000" and row.get("passed") is True for row in structural.get("rows", [])),
        "full_legsa_identity": any(row.get("method_id") == "AB1111" and row.get("passed") is True for row in structural.get("rows", [])),
        "module_counters_match": formal_closure,
        "aggregate_crosscheck": aggregate.get("passed") is True and evaluation_revalidation.get("passed") is True,
        "offline_evaluation_full_revalidation": evaluation_revalidation.get("passed") is True,
        "figure_qa": figures.get("passed") is True,
        "trace_online_false": all(row.get("trace_used_online") is False and row.get("trace_open_count") == 0 for row in wrappers),
        "legacy_input_false": all(row.get("old_runtime_input_count") == 0 for row in wrappers),
        "metric_rerun_false": attempts_close and all(row.get("metric_driven_rerun") == "False" for row in attempts),
        "degradation_run_count_zero": clean_scope_proven,
        "D01_D60_audit_count_zero": clean_scope_proven,
        "out_of_scope_counts_zero": all(value == 0 for value in forbidden_counts.values()),
    }
    if not all(gates.values()):
        raise Clean2R2AEvidenceError("terminal gate failed: " + ",".join(key for key, value in gates.items() if not value))
    report = {
        "schema_version": "paper_rebuild.clean2r2a_full_report.v1",
        "stage_id": STAGE_ID, "terminal_status": TERMINAL_STATUS,
        "gates": gates, "formal_run_count": 18, "technical_retry_count": technical_retry_count,
        "degradation_run_count": 0, "D01_D60_audit_count": 0,
        "trace_used_online": False, "legacy_solver_input": False,
        "synthetic_data_used": False, "semisynthetic_data_used": False,
        "forbidden_module_counts": forbidden_counts,
        "claim_boundary": {
            "controlled_clean_module_ablation": True,
            "degradation_robustness_claim": False, "universal_superiority_claim": False,
            "independent_ground_truth": False, "paper_final_figures": False,
        },
    }
    write_json_atomic(stage / "11_AUDITS" / "CLEAN2R2A_PASS_GATES.json", gates)
    write_json_atomic(stage / "11_AUDITS" / "CLEAN2R2A_FULL_REPORT.json", report)
    (stage / "11_AUDITS" / "CLEAN2R2A_FULL_REPORT.md").write_text(
        "# CLEAN2R2A full report\n\n"
        f"Terminal status: `{TERMINAL_STATUS}`.\n\n"
        "Fresh BY2 clean input produced 18 sealed formal outputs. Trace was opened only after the output seal for same-source offline evaluation.\n\n"
        "No degradation definition was read, audited, constructed, or executed. No FGO, multi-state QM, QA fallback, or contact/FK factor was used.\n",
        encoding="utf-8",
    )
    return report


def _copy_payloads(stage: Path, staging: Path) -> None:
    direct_roots = (
        "00_AUTHORIZATION", "01_GIT_FREEZE", "02_PROTOCOLS", "03_RAW_AUDITS",
        "05_RUN_REGISTRY", "07_OUTPUT_SEAL", "09_FACTORIAL_ANALYSIS",
        "10_DIAGNOSTIC_FIGURES", "11_AUDITS",
    )
    for name in direct_roots:
        shutil.copytree(stage / name, staging / name)
    provider_out = staging / "04_BASE_PROVIDER"
    provider_out.mkdir()
    for path in sorted(item for item in (stage / "04_BASE_PROVIDER").rglob("*") if item.is_file()):
        if any(part in {"tools", "raw_doppler_backend", ".compat-builder"} for part in path.relative_to(stage / "04_BASE_PROVIDER").parts):
            continue
        target = provider_out / path.relative_to(stage / "04_BASE_PROVIDER")
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, target)
    run_out = staging / "06_FORMAL_RUNS"; run_out.mkdir()
    keep_run_names = {
        "CLEAN2R2A_RUNTIME_CONFIG.yaml", "RUN_MANIFEST.json", "CLEAN2R2A_FORMAL_RUN_MANIFEST.json",
        "PORT_GNSS_UPDATE_TRACE.csv", "SOURCE_AWARE_WEIGHT_TRACE.csv",
    }
    for method in METHOD_ORDER:
        source = stage / "06_FORMAL_RUNS" / run_directory(method)
        target = run_out / run_directory(method); target.mkdir()
        for name in keep_run_names:
            if (source / name).is_file(): shutil.copy2(source / name, target / name)
    eval_out = staging / "08_OFFLINE_EVALUATION"; eval_out.mkdir()
    for path in sorted(item for item in (stage / "08_OFFLINE_EVALUATION").rglob("*") if item.is_file()):
        relative = path.relative_to(stage / "08_OFFLINE_EVALUATION")
        if path.name == "EVALUATOR_FILE_OPEN_TRACE.raw":
            continue
        target = eval_out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.name == "error_series.csv":
            target = target.with_suffix(".csv.gz")
            with path.open("rb") as source_handle, target.open("wb") as raw_handle:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw_handle, mtime=0) as compressed:
                    shutil.copyfileobj(source_handle, compressed)
        else:
            shutil.copy2(path, target)


def _manifest_rows(staging: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(item for item in staging.rglob("*") if item.is_file()):
        relative = path.relative_to(staging).as_posix()
        if relative in {"EVIDENCE_MANIFEST.csv", "EVIDENCE_MANIFEST.sha256"}:
            continue
        source_class = "current_fresh_runtime_evidence" if relative.startswith(("06_", "08_")) else "current_stage_evidence"
        rows.append({"archive_path": relative, "size_bytes": path.stat().st_size,
                     "sha256": sha256_file(path), "role": relative.split("/", 1)[0],
                     "source_class": source_class})
    return rows


def finalize_evidence_zip(
    *, stage_root: str | Path, export_root: str | Path, timestamp: str,
    local_config: str | Path, exact_evaluator: str | Path,
) -> dict[str, Any]:
    stage = Path(stage_root).resolve(strict=True)
    export = Path(export_root).resolve(strict=True)
    if stage.name != STAGE_ID or stage.parent.name != "stages":
        raise Clean2R2AEvidenceError("finalizer stage root identity mismatch")
    expected_export = (stage.parents[2] / "export").resolve(strict=False)
    if export != expected_export or export.is_symlink():
        raise Clean2R2AEvidenceError("export root is not the exact project export directory")
    terminal = audit_terminal_stage(
        stage, local_config=local_config, exact_evaluator=exact_evaluator,
    )
    if (
        terminal.get("terminal_status") != TERMINAL_STATUS
        or not terminal.get("gates")
        or not all(terminal["gates"].values())
    ):
        raise Clean2R2AEvidenceError("terminal PASS gate is not closed")
    final_root = stage / "12_FINAL_EVIDENCE" / "FINALIZED"
    if final_root.exists() or list(export.glob("LegSA_GINS_CLEAN2R2A_FINAL_*.zip")):
        raise Clean2R2AEvidenceError("terminal evidence or CLEAN2R2A ZIP already exists")
    staging = stage / "12_FINAL_EVIDENCE" / f".staging_{uuid.uuid4().hex}"
    staging.mkdir()
    _copy_payloads(stage, staging)
    rows = _manifest_rows(staging)
    manifest = staging / "EVIDENCE_MANIFEST.csv"
    with manifest.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("archive_path", "size_bytes", "sha256", "role", "source_class"))
        writer.writeheader(); writer.writerows(rows)
    manifest_hash = sha256_file(manifest)
    sidecar = staging / "EVIDENCE_MANIFEST.sha256"
    sidecar.write_text(f"{manifest_hash}  EVIDENCE_MANIFEST.csv\n", encoding="utf-8", newline="")
    if sidecar.read_text(encoding="utf-8") != f"{manifest_hash}  EVIDENCE_MANIFEST.csv\n":
        raise Clean2R2AEvidenceError("stage sidecar format mismatch")
    for row in rows:
        path = staging / row["archive_path"]
        if path.stat().st_size != int(row["size_bytes"]) or sha256_file(path) != row["sha256"]:
            raise Clean2R2AEvidenceError("stage manifest payload closure failed")
    zip_path = export / f"LegSA_GINS_CLEAN2R2A_FINAL_{timestamp}.zip"
    zip_sha = zip_path.with_suffix(zip_path.suffix + ".sha256")
    if zip_path.exists() or zip_sha.exists():
        raise Clean2R2AEvidenceError("exact CLEAN2R2A ZIP target already exists")
    attempt_token = uuid.uuid4().hex
    temporary_zip = export / f".{zip_path.name}.{attempt_token}.tmp"
    temporary_sha = export / f".{zip_sha.name}.{attempt_token}.tmp"
    fixed_time = (2026, 7, 18, 0, 0, 0)
    with zipfile.ZipFile(temporary_zip, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in staging.rglob("*") if item.is_file()):
            relative = path.relative_to(staging).as_posix()
            info = zipfile.ZipInfo(relative, fixed_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(temporary_zip, "r") as archive:
        if archive.testzip() is not None:
            raise Clean2R2AEvidenceError("ZIP integrity test failed")
        names = archive.namelist()
        if len(names) != len(rows) + 2 or len(set(names)) != len(names):
            raise Clean2R2AEvidenceError("ZIP entry closure failed")
        zip_manifest = archive.read("EVIDENCE_MANIFEST.csv")
        zip_sidecar = archive.read("EVIDENCE_MANIFEST.sha256").decode("utf-8")
        if hashlib.sha256(zip_manifest).hexdigest() != manifest_hash or zip_sidecar != f"{manifest_hash}  EVIDENCE_MANIFEST.csv\n":
            raise Clean2R2AEvidenceError("ZIP sidecar check failed")
        for row in rows:
            payload = archive.read(row["archive_path"])
            if len(payload) != int(row["size_bytes"]) or hashlib.sha256(payload).hexdigest() != row["sha256"]:
                raise Clean2R2AEvidenceError("ZIP manifest payload closure failed")
    zip_hash = sha256_file(temporary_zip)
    temporary_sha.write_text(f"{zip_hash}  {zip_path.name}\n", encoding="utf-8", newline="")
    promoted_stage = False
    try:
        os.replace(staging, final_root)
        promoted_stage = True
        os.replace(temporary_zip, zip_path)
        os.replace(temporary_sha, zip_sha)
    except Exception:
        if zip_path.exists() and not temporary_zip.exists():
            os.replace(zip_path, temporary_zip)
        if zip_sha.exists() and not temporary_sha.exists():
            os.replace(zip_sha, temporary_sha)
        if promoted_stage and final_root.exists() and not staging.exists():
            os.replace(final_root, staging)
        raise
    return {
        "terminal_status": TERMINAL_STATUS, "finalized_root": str(final_root),
        "manifest_rows": len(rows), "manifest_sha256": manifest_hash,
        "stage_sidecar_check": True, "zip_path": str(zip_path), "zip_sha256": zip_hash,
        "zip_size_bytes": zip_path.stat().st_size, "zip_entry_count": len(rows) + 2,
        "zip_integrity_test": True, "stage_manifest_matches_zip": True,
        "zip_manifest_closure": True, "zip_sidecar_check": True,
    }
