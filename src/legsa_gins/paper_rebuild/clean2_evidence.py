"""Fail-closed CLEAN2 output sealing, invariance audits, and final export.

This module deliberately has no trace-path argument.  Formal output sealing is
complete before the offline evaluator is allowed to open the evaluation trace.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from .clean2_run_registry import read_run_registry
from .evidence import BY2_RAW_RELATIVE_PATHS, assert_export_text_is_redacted
from .manifest import sha256_file, write_json_atomic


STAGE_ID = "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18"
PROTOCOL_ID = "CLEAN_REAL_DATA_FINAL_V23"
FORMAL_MANIFEST_NAME = "CLEAN2_FORMAL_RUN_MANIFEST.json"
FORMAL_MANIFEST_SCHEMA = "paper_rebuild.clean2_formal_run_manifest.v1"
COMPLETE_SEAL_SCHEMA = "paper_rebuild.clean2_complete_output_seal.v2"
TERMINAL_GATE_SCHEMA = "paper_rebuild.clean2_terminal_gate.v1"
TERMINAL_DECISION = (
    "PASS_CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18_FRESH_EVIDENCE_READY_FOR_HUMAN_REVIEW"
)
EXPECTED_STAGE_DIRNAME = STAGE_ID
FINAL_ZIP_PREFIX = "LegSA_GINS_CLEAN2_FINAL_"
DEFAULT_MAX_EXPORT_BYTES = 512 * 1024 * 1024

REGISTRY_IDENTITY_FIELDS = (
    "run_id",
    "case_id",
    "result_namespace",
    "structural_method",
    "ablation_id",
    "feature_RD",
    "feature_SA",
    "feature_RP",
    "feature_HV",
    "provider_bundle_hash",
    "runtime_config_hash",
    "executable_hash",
    "run_order",
    "formal",
    "alias_roles",
)
PROVIDER_HASH_ROLES = frozenset(
    {
        "imu",
        "gnss",
        "case_gnss",
        "dual_yaw",
        "raw_doppler",
        "go2_roll_pitch",
        "go2_horizontal_velocity",
    }
)
REQUIRED_OUTPUT_ROLES = {
    "exact_nav": "KF_GINS_Navresult.nav",
    "exact_std": "KF_GINS_STD.txt",
    "gnss_action_trace": "PORT_GNSS_UPDATE_TRACE.csv",
}
SOURCE_AWARE_OUTPUT_ROLE = "source_aware_trace"
SOURCE_AWARE_OUTPUT_NAME = "SOURCE_AWARE_WEIGHT_TRACE.csv"
FORBIDDEN_ZERO_COUNTERS = (
    "selected_fgo_feedback_update_count",
    "nine_factor_fgo_update_count",
    "qa_fallback_count",
    "multi_state_qm_update_count",
    "contact_fk_update_count",
)
MODULE_COUNTER_FIELDS = (
    "position_update_count",
    "receiver_velocity_update_count",
    "dual_yaw_update_count",
    "raw_doppler_update_count",
    "source_aware_evaluation_count",
    "source_aware_weight_changed_count",
    "go2_roll_pitch_update_count",
    "go2_horizontal_velocity_update_count",
    *FORBIDDEN_ZERO_COUNTERS,
)
ACTION_COUNTER_FIELDS = (
    "yaw_attempt_count",
    "yaw_normal_count",
    "yaw_downweight_count",
    "yaw_reject_count",
    "yaw_accepted_count",
    "raw_doppler_reject_count",
    "go2_roll_pitch_reject_count",
    "go2_horizontal_velocity_reject_count",
)

PROTOCOL_EXPORT_NAMES = frozenset(
    {
        "ACTIVE_CONTEXT.md",
        "DATA_ROLES.md",
        "METHOD_SCOPE.md",
        "EXPERIMENT_PROTOCOL.md",
        "LEGACY_DENYLIST.md",
        "CLAIM_BOUNDARY.md",
        "CLEAN2_PROTOCOL.md",
        "clean2_ablation_2pow4.yaml",
        "clean2_classic18_active_mapping.yaml",
        "clean2_execution_protocol.yaml",
        "clean2_formal_manifest_schema.yaml",
        "methods.yaml",
        "final_v23_parity_contract.yaml",
    }
)
REQUIRED_PROTOCOL_EXPORT_NAMES = frozenset(
    {
        "clean2_ablation_2pow4.yaml",
        "clean2_classic18_active_mapping.yaml",
        "clean2_execution_protocol.yaml",
        "clean2_formal_manifest_schema.yaml",
        "methods.yaml",
        "final_v23_parity_contract.yaml",
    }
)
CASE_EXPORT_NAMES = (
    "CASE_PERTURBATION_LEDGER.csv",
    "CASE_PROVIDER_MANIFEST.json",
    "CASE_PROVIDER_HASHES.csv",
    "CASE_POLICY_REPORT.json",
)
AGGREGATE_EXPORT_NAMES = (
    "CLEAN2_C00_FACTORIAL_RESULTS.csv",
    "CLEAN2_C00_MODULE_MAIN_EFFECTS.csv",
    "CLEAN2_C00_PAIRWISE_INTERACTIONS.csv",
    "CLEAN2_C00_FACTORIAL_INTERPRETATION.md",
    "CLEAN2_CANONICAL_CLASSIC18_18x4.csv",
    "CLEAN2_CASE_METHOD_DELTAS.csv",
    "CLEAN2_FAMILY_SEED_AGGREGATES.csv",
    "CLEAN2_SENTINEL_LOO_RESULTS.csv",
    "CLEAN2_SENTINEL_MODULE_MARGINAL_LOSS.csv",
    "CLEAN2_PERTURBATION_ACTION_SUMMARY.csv",
    "CLEAN2_SOURCE_AWARE_RESPONSE_SUMMARY.csv",
    "CLEAN2_FAILURE_AND_FINITE_OUTPUT_SUMMARY.csv",
    "CLEAN2_AGGREGATE_CROSSCHECK.json",
)
BASE_EXPORT_NAMES = (
    "CLEAN2_BASE_PROVIDER_MANIFEST.json",
    "CLEAN2_BASE_PROVIDER_HASHES.csv",
)
TERMINAL_ARTIFACT_RELATIVE_PATHS = {
    "case_provider_index": "05_CASE_PROVIDERS/CLASSIC18_PROVIDER_INDEX.json",
    "registry": "06_RUN_REGISTRY/CLEAN2_RUN_REGISTRY.csv",
    "attempts": "06_RUN_REGISTRY/CLEAN2_RUN_ATTEMPTS.csv",
    "attempts_audit": "13_AUDITS/CLEAN2_RUN_ATTEMPTS_AUDIT.json",
    "complete_output_seal": "08_OUTPUT_SEAL/CLEAN2_COMPLETE_OUTPUT_SEAL.json",
    "solver_artifact_index": "08_OUTPUT_SEAL/CLEAN2_SOLVER_ARTIFACT_INDEX.json",
    "offline_evaluation_index": "09_OFFLINE_EVALUATION/CLEAN2_OFFLINE_EVALUATION_INDEX.json",
    "raw_pre_provider": "03_RAW_AUDITS/CLEAN2_RAW_PRE_PROVIDER_CHECKPOINT.json",
    "raw_post_provider": "03_RAW_AUDITS/CLEAN2_RAW_POST_PROVIDER_CHECKPOINT.json",
    "raw_post_run": "03_RAW_AUDITS/CLEAN2_RAW_POST_RUN_CHECKPOINT.json",
    "c00_structural_gate": "13_AUDITS/CLEAN2_C00_STRUCTURAL_GATE.json",
    "invariants": "13_AUDITS/CLEAN2_FORMAL_INVARIANTS.json",
    "aggregate": "11_CLASSIC18_ANALYSIS/CLEAN2_AGGREGATE_CROSSCHECK.json",
    "figure_manifest": "12_DIAGNOSTIC_FIGURES/CLEAN2_FIGURE_MANIFEST.csv",
    "figure_qa": "12_DIAGNOSTIC_FIGURES/CLEAN2_FIGURE_RENDER_QA.json",
    "review": "13_AUDITS/CLEAN2_FINAL_REVIEW.json",
    "full_report_json": "14_FINAL_EVIDENCE/CLEAN2_FULL_REPORT.json",
    "full_report_md": "14_FINAL_EVIDENCE/CLEAN2_FULL_REPORT.md",
}
EXPLICIT_AUDIT_EXPORT_ROLES = (
    "attempts_audit",
    "c00_structural_gate",
    "invariants",
)
FIGURE_NAMES = tuple(
    f"{index:02d}_{name}"
    for index, name in enumerate(
        (
            "clean_factorial_yaw_main_effects",
            "clean_factorial_position_main_effects",
            "clean_pairwise_interactions",
            "classic18_yaw_penalty_heatmap",
            "classic18_horizontal_penalty_heatmap",
            "classic18_up_penalty_heatmap",
            "seeded_family_yaw_penalties",
            "seeded_family_worst_case",
            "C01_outage_yaw_error_and_actions",
            "C07_baseline_spike_yaw_error_and_actions",
            "C11_yaw_spike_yaw_error_and_actions",
            "C15_mixed_yaw_error_and_actions",
            "LegSA_source_aware_scale_perturbed_epochs",
            "schemeC_accept_downweight_reject_by_case",
            "sentinel_leave_one_out_yaw",
            "sentinel_leave_one_out_position",
            "method_degradation_ratio_panel",
            "clean_vs_controlled_claim_boundary_panel",
        ),
        start=1,
    )
)
TEXT_EXPORT_SUFFIXES = frozenset({".csv", ".json", ".md", ".txt", ".yaml", ".yml"})
FORBIDDEN_EXPORT_SUFFIXES = frozenset(
    {".nav", ".exe", ".so", ".a", ".o", ".bag", ".fpl", ".ubx", ".obs", ".rtcm"}
)


class Clean2EvidenceError(RuntimeError):
    """The output seal, invariant proof, or explicit export failed closed."""


@dataclass(frozen=True)
class EvidenceMember:
    """One explicitly selected final-archive member."""

    source: Path
    archive_path: str
    category: str


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _json_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _safe_relative(raw: Any, *, label: str) -> PurePosixPath:
    value = str(raw).replace("\\", "/")
    relative = PurePosixPath(value)
    if (
        not value
        or relative.is_absolute()
        or ".." in relative.parts
        or "." in relative.parts
        or re.match(r"^[A-Za-z]:/", value)
    ):
        raise Clean2EvidenceError(f"{label} must be a safe relative POSIX path")
    return relative


def _assert_no_symlink_chain(path: Path, root: Path) -> None:
    """Reject a symlink in the selected path itself or below the trusted root."""

    if root.is_symlink():
        raise Clean2EvidenceError("Trusted evidence/runtime root is a symlink")
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise Clean2EvidenceError("Selected path is outside its trusted root") from exc
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise Clean2EvidenceError("Selected evidence/artifact path contains a symlink")


def _resolve_run_file(run_root: Path, raw_relative: Any, *, label: str) -> Path:
    relative = _safe_relative(raw_relative, label=label)
    candidate = run_root.joinpath(*relative.parts)
    _assert_no_symlink_chain(candidate, run_root)
    resolved = candidate.resolve(strict=True)
    if run_root.resolve(strict=True) not in resolved.parents or not resolved.is_file():
        raise Clean2EvidenceError(f"{label} escaped the isolated formal run or is not a file")
    return resolved


def _validate_sha_mapping(
    value: Any, *, label: str, exact_keys: frozenset[str] | None = None, exact_count: int | None = None
) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise Clean2EvidenceError(f"{label} must be a mapping")
    normalized = {str(key): str(item) for key, item in value.items()}
    if exact_keys is not None and set(normalized) != set(exact_keys):
        raise Clean2EvidenceError(f"{label} roles differ from the frozen contract")
    if exact_count is not None and len(normalized) != exact_count:
        raise Clean2EvidenceError(f"{label} count differs from the frozen contract")
    if not normalized or any(not _is_sha256(item) for item in normalized.values()):
        raise Clean2EvidenceError(f"{label} contains an invalid SHA-256")
    return normalized


def _load_formal_schema() -> Mapping[str, Any]:
    schema_path = (
        Path(__file__).resolve().parents[3]
        / "configs/paper_rebuild/clean2_formal_manifest_schema.yaml"
    )
    if not schema_path.is_file():
        raise Clean2EvidenceError("CLEAN2 formal manifest schema is missing")
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - production dependency guard
        raise Clean2EvidenceError("PyYAML is required for CLEAN2 manifest validation") from exc
    payload = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise Clean2EvidenceError("CLEAN2 formal manifest schema is not a mapping")
    return payload


def _validate_against_formal_schema(manifest: Mapping[str, Any]) -> None:
    try:
        import jsonschema  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - production dependency guard
        raise Clean2EvidenceError("jsonschema is required for CLEAN2 manifest validation") from exc
    # The environment's Draft7 validator resolves local #/$defs JSON pointers and
    # validates all CLEAN2 keywords used here; unknown 2020 annotation keywords are
    # harmless.  Manual semantic checks below additionally bind registry and bytes.
    errors = sorted(
        jsonschema.Draft7Validator(_load_formal_schema()).iter_errors(dict(manifest)),
        key=lambda error: tuple(str(item) for item in error.absolute_path),
    )
    if errors:
        detail = ";".join(
            f"{'/'.join(str(item) for item in error.absolute_path) or '<root>'}:{error.message}"
            for error in errors[:12]
        )
        raise Clean2EvidenceError("CLEAN2 formal wrapper schema validation failed: " + detail)


def _counter_signature(manifest: Mapping[str, Any]) -> dict[str, int]:
    module = manifest.get("module_update_counts")
    actions = manifest.get("counters")
    if not isinstance(module, Mapping) or set(module) != set(MODULE_COUNTER_FIELDS):
        raise Clean2EvidenceError("CLEAN2 module counter fields differ from the frozen contract")
    if not isinstance(actions, Mapping) or set(actions) != set(ACTION_COUNTER_FIELDS):
        raise Clean2EvidenceError("CLEAN2 action counter fields differ from the frozen contract")
    combined = {str(key): value for key, value in {**dict(module), **dict(actions)}.items()}
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in combined.values()):
        raise Clean2EvidenceError("CLEAN2 counters must be non-negative integers")
    if combined["yaw_attempt_count"] != (
        combined["yaw_normal_count"]
        + combined["yaw_downweight_count"]
        + combined["yaw_reject_count"]
    ):
        raise Clean2EvidenceError("CLEAN2 yaw action counters do not sum to attempts")
    if combined["yaw_accepted_count"] != (
        combined["yaw_normal_count"] + combined["yaw_downweight_count"]
    ) or combined["dual_yaw_update_count"] != combined["yaw_accepted_count"]:
        raise Clean2EvidenceError("CLEAN2 accepted-yaw counters are inconsistent")
    if any(combined[field] != 0 for field in FORBIDDEN_ZERO_COUNTERS):
        raise Clean2EvidenceError("CLEAN2 forbidden FGO/QM/QA/contact counter is nonzero")
    return {key: int(value) for key, value in sorted(combined.items())}


def _validate_module_semantics(manifest: Mapping[str, Any]) -> None:
    counters = _counter_signature(manifest)
    structural = str(manifest["structural_method"])
    expected_receiver = structural != "basic_dual_yaw_EKF"
    expected_yaw = structural != "single_antenna_EKF"
    expected = {
        "receiver_velocity_update_count": expected_receiver,
        "yaw_attempt_count": expected_yaw,
        "raw_doppler_update_count": bool(manifest["feature_RD"]),
        "source_aware_evaluation_count": bool(manifest["feature_SA"]),
        "go2_roll_pitch_update_count": bool(manifest["feature_RP"]),
        "go2_horizontal_velocity_update_count": bool(manifest["feature_HV"]),
    }
    if counters["position_update_count"] <= 0:
        raise Clean2EvidenceError("CLEAN2 position module did not activate")
    for field, active in expected.items():
        if (counters[field] > 0) is not active:
            raise Clean2EvidenceError(f"CLEAN2 module counter differs from feature semantics: {field}")
    if not manifest["feature_SA"] and counters["source_aware_weight_changed_count"] != 0:
        raise Clean2EvidenceError("Source-aware changed counter is nonzero while SA is disabled")


def _validate_registry_binding(manifest: Mapping[str, Any], row: Mapping[str, Any]) -> None:
    mismatches = [field for field in REGISTRY_IDENTITY_FIELDS if manifest.get(field) != row.get(field)]
    if mismatches:
        raise Clean2EvidenceError(
            "CLEAN2 formal wrapper differs from registry: " + ",".join(sorted(mismatches))
        )
    controlled = not str(row["case_id"]).startswith("C00_")
    expected = {
        "schema_version": FORMAL_MANIFEST_SCHEMA,
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        "data_mode": "real_base_controlled_degradation" if controlled else "real_by2_raw",
        "result_namespace": (
            "BY2_CONTROLLED_DUAL_YAW_DEGRADATION"
            if controlled
            else "BY2_REAL_CLEAN_MODULE_ABLATION"
        ),
        "synthetic_data_used": False,
        "semisynthetic_data_used": controlled,
        "code_worktree_dirty_at_run": False,
        "trace_used_online": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0,
        "legacy_provider_input_count": 0,
        "legacy_row_input_count": 0,
        "legacy_aggregate_input_count": 0,
        "status_fallback_used": False,
        "paper_performance_claim": False,
        "solver_returncode": 0,
        "terminal_status": "PASS",
        "formal": True,
        "source_aware_trace_expected": bool(row["feature_SA"]),
    }
    bad = [field for field, value in expected.items() if manifest.get(field) != value]
    if bad:
        raise Clean2EvidenceError(
            "CLEAN2 formal wrapper safety/identity field mismatch: " + ",".join(sorted(bad))
        )
    if not isinstance(manifest.get("code_commit"), str) or re.fullmatch(
        r"[0-9a-f]{40}", str(manifest["code_commit"])
    ) is None:
        raise Clean2EvidenceError("CLEAN2 code commit is not a full Git SHA")


def _validate_output_artifacts(
    run_root: Path, manifest: Mapping[str, Any]
) -> list[dict[str, Any]]:
    output_files = manifest.get("output_files")
    output_hashes = manifest.get("output_hashes")
    if not isinstance(output_files, Mapping) or not isinstance(output_hashes, Mapping):
        raise Clean2EvidenceError("CLEAN2 output_files/output_hashes must be role mappings")
    if set(output_files) != set(output_hashes):
        raise Clean2EvidenceError("CLEAN2 output file/hash roles differ")
    for role, expected_name in REQUIRED_OUTPUT_ROLES.items():
        if role not in output_files or Path(str(output_files[role])).name != expected_name:
            raise Clean2EvidenceError(f"CLEAN2 required output role is missing or misnamed: {role}")
    source_aware = bool(manifest["feature_SA"])
    if source_aware:
        if (
            SOURCE_AWARE_OUTPUT_ROLE not in output_files
            or Path(str(output_files[SOURCE_AWARE_OUTPUT_ROLE])).name != SOURCE_AWARE_OUTPUT_NAME
        ):
            raise Clean2EvidenceError("CLEAN2 SA run lacks its source-aware trace")
    elif SOURCE_AWARE_OUTPUT_ROLE in output_files:
        raise Clean2EvidenceError("CLEAN2 non-SA run unexpectedly lists a source-aware trace")
    rows: list[dict[str, Any]] = []
    seen_relative: set[str] = set()
    for role in sorted(output_files):
        relative = _safe_relative(output_files[role], label=f"output_files.{role}")
        relative_text = relative.as_posix()
        if relative_text in seen_relative:
            raise Clean2EvidenceError("CLEAN2 output roles alias the same artifact")
        seen_relative.add(relative_text)
        expected_hash = output_hashes[role]
        if not _is_sha256(expected_hash):
            raise Clean2EvidenceError(f"CLEAN2 output hash is invalid: {role}")
        path = _resolve_run_file(run_root, relative_text, label=f"output_files.{role}")
        if path.stat().st_size <= 0:
            raise Clean2EvidenceError(f"CLEAN2 listed output is empty: {role}")
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            raise Clean2EvidenceError(f"CLEAN2 listed output changed or hash is false: {role}")
        rows.append(
            {
                "role": str(role),
                "relative_path": f"{run_root.name}/{relative_text}",
                "sha256": actual_hash,
                "size_bytes": path.stat().st_size,
            }
        )
    if output_hashes.get("solver_manifest") != manifest.get("solver_manifest_sha256"):
        raise Clean2EvidenceError("CLEAN2 solver-manifest hash binding differs")
    return rows


def _validate_formal_wrapper(
    run_root: Path, manifest_path: Path, row: Mapping[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int]]:
    _assert_no_symlink_chain(manifest_path, run_root)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise Clean2EvidenceError("CLEAN2 formal wrapper is not a JSON object")
    manifest = dict(payload)
    _validate_against_formal_schema(manifest)
    _validate_registry_binding(manifest, row)
    raw_hashes = _validate_sha_mapping(
        manifest.get("raw_source_hashes"), label="raw_source_hashes", exact_count=22
    )
    if set(raw_hashes) != set(BY2_RAW_RELATIVE_PATHS):
        raise Clean2EvidenceError("CLEAN2 raw hash path set differs from the frozen BY2 22")
    _validate_sha_mapping(
        manifest.get("provider_hashes"),
        label="provider_hashes",
        exact_keys=PROVIDER_HASH_ROLES,
    )
    # Wrappers are required final-export members, so absolute/private paths are
    # forbidden at creation/seal time rather than discovered only at packaging.
    try:
        assert_export_text_is_redacted(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        )
    except Exception as exc:
        raise Clean2EvidenceError("CLEAN2 formal wrapper is not export-redacted") from exc
    _validate_module_semantics(manifest)
    files = _validate_output_artifacts(run_root, manifest)
    return manifest, files, _counter_signature(manifest)


def seal_formal_outputs(
    *,
    registry_path: str | Path,
    runtime_root: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Validate and rehash all 110 wrappers/artifacts without a trace path."""

    registry_source = Path(registry_path).resolve(strict=True)
    rows = read_run_registry(registry_source)
    runtime_path = Path(runtime_root)
    if runtime_path.is_symlink():
        raise Clean2EvidenceError("CLEAN2 runtime root is a symlink")
    runtime = runtime_path.resolve(strict=True)
    if not runtime.is_dir():
        raise Clean2EvidenceError("CLEAN2 runtime root is not a directory")
    destination = Path(output_path)
    if destination.exists() or destination.is_symlink():
        raise Clean2EvidenceError("CLEAN2 complete seal output must be fresh")
    sealed_runs: list[dict[str, Any]] = []
    code_commits: set[str] = set()
    executable_hashes: set[str] = set()
    for row in rows:
        run_root_raw = runtime / str(row["run_id"])
        _assert_no_symlink_chain(run_root_raw, runtime)
        run_root = run_root_raw.resolve(strict=True)
        if run_root.parent != runtime or not run_root.is_dir():
            raise Clean2EvidenceError("Formal run root is not one isolated direct child")
        manifest_path = run_root / FORMAL_MANIFEST_NAME
        if not manifest_path.is_file():
            raise Clean2EvidenceError("Formal CLEAN2 wrapper manifest is missing")
        manifest, file_rows, counters = _validate_formal_wrapper(run_root, manifest_path, row)
        code_commits.add(str(manifest["code_commit"]))
        executable_hashes.add(str(manifest["executable_hash"]))
        sealed_runs.append(
            {
                "run_id": row["run_id"],
                "run_order": row["run_order"],
                "case_id": row["case_id"],
                "result_namespace": row["result_namespace"],
                "structural_method": row["structural_method"],
                "ablation_id": row["ablation_id"],
                "feature_RD": row["feature_RD"],
                "feature_SA": row["feature_SA"],
                "feature_RP": row["feature_RP"],
                "feature_HV": row["feature_HV"],
                "registry_row_sha256": _json_digest(
                    {field: row[field] for field in REGISTRY_IDENTITY_FIELDS}
                ),
                "manifest_relative_path": f"{row['run_id']}/{FORMAL_MANIFEST_NAME}",
                "manifest_sha256": sha256_file(manifest_path),
                "code_commit": manifest["code_commit"],
                "runtime_config_hash": manifest["runtime_config_hash"],
                "executable_hash": manifest["executable_hash"],
                "provider_bundle_hash": manifest["provider_bundle_hash"],
                "raw_source_hashes_sha256": _json_digest(manifest["raw_source_hashes"]),
                "provider_hashes_sha256": _json_digest(manifest["provider_hashes"]),
                "module_counters": counters,
                "terminal_status": "PASS",
                "files": file_rows,
            }
        )
    if len(code_commits) != 1 or len(executable_hashes) != 1:
        raise Clean2EvidenceError("CLEAN2 runs do not share one code commit/executable hash")
    payload = {
        "schema_version": COMPLETE_SEAL_SCHEMA,
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        "registry_sha256": sha256_file(registry_source),
        "registry_path_alias": "<CLEAN2_STAGE>/06_RUN_REGISTRY/CLEAN2_RUN_REGISTRY.csv",
        "runtime_root_alias": "<CLEAN2_STAGE>/07_FORMAL_RUNS",
        "code_commit": next(iter(code_commits)),
        "executable_hash": next(iter(executable_hashes)),
        "unique_formal_run_count": len(sealed_runs),
        "formal_wrapper_manifest_count": len(sealed_runs),
        "output_artifact_count": sum(len(run["files"]) for run in sealed_runs),
        "all_runs_terminal_pass": len(sealed_runs) == 110,
        "all_outputs_hash_sealed": True,
        "all_listed_artifacts_rehashed": True,
        "registry_identity_bound": True,
        "trace_open_count_before_seal": 0,
        "trace_used_online": False,
        "performance_metric_read_before_seal": False,
        "runs": sealed_runs,
        "passed": len(sealed_runs) == 110,
    }
    if not payload["passed"]:
        raise Clean2EvidenceError("CLEAN2 complete output seal does not contain 110 runs")
    write_json_atomic(destination, payload)
    return payload


def validate_complete_output_seal(
    path: str | Path,
    *,
    runtime_root: str | Path | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate seal structure and optionally rehash every bound runtime artifact."""

    seal_path = Path(path).resolve(strict=True)
    payload = json.loads(seal_path.read_text(encoding="utf-8"))
    required = {
        "schema_version": COMPLETE_SEAL_SCHEMA,
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        "unique_formal_run_count": 110,
        "formal_wrapper_manifest_count": 110,
        "all_runs_terminal_pass": True,
        "all_outputs_hash_sealed": True,
        "all_listed_artifacts_rehashed": True,
        "registry_identity_bound": True,
        "trace_open_count_before_seal": 0,
        "trace_used_online": False,
        "performance_metric_read_before_seal": False,
        "passed": True,
    }
    if any(payload.get(key) != value for key, value in required.items()):
        raise Clean2EvidenceError("CLEAN2 complete output seal failed validation")
    for field in ("registry_sha256", "executable_hash"):
        if not _is_sha256(payload.get(field)):
            raise Clean2EvidenceError(f"CLEAN2 complete output seal has invalid {field}")
    if re.fullmatch(r"[0-9a-f]{40}", str(payload.get("code_commit") or "")) is None:
        raise Clean2EvidenceError("CLEAN2 complete output seal has invalid code commit")
    runs = payload.get("runs")
    if not isinstance(runs, list) or len(runs) != 110:
        raise Clean2EvidenceError("CLEAN2 complete output seal run list is incomplete")
    if [row.get("run_order") for row in runs if isinstance(row, Mapping)] != list(range(1, 111)):
        raise Clean2EvidenceError("CLEAN2 sealed run order differs from 1..110")
    if len({row.get("run_id") for row in runs if isinstance(row, Mapping)}) != 110:
        raise Clean2EvidenceError("CLEAN2 sealed run ids are duplicated")
    for row in runs:
        if not isinstance(row, Mapping) or row.get("terminal_status") != "PASS":
            raise Clean2EvidenceError("CLEAN2 sealed run is not terminal PASS")
        for field in (
            "registry_row_sha256",
            "manifest_sha256",
            "runtime_config_hash",
            "executable_hash",
            "provider_bundle_hash",
            "raw_source_hashes_sha256",
            "provider_hashes_sha256",
        ):
            if not _is_sha256(row.get(field)):
                raise Clean2EvidenceError(f"CLEAN2 sealed run has invalid {field}")
        files = row.get("files")
        if not isinstance(files, list) or not files:
            raise Clean2EvidenceError("CLEAN2 sealed run file list is empty")
        basenames = {
            Path(str(item.get("relative_path"))).name
            for item in files
            if isinstance(item, Mapping)
        }
        required_names = set(REQUIRED_OUTPUT_ROLES.values())
        if bool(row.get("feature_SA")):
            required_names.add(SOURCE_AWARE_OUTPUT_NAME)
        if not required_names.issubset(basenames):
            raise Clean2EvidenceError("CLEAN2 sealed run lacks a required output artifact")
        for item in files:
            if (
                not isinstance(item, Mapping)
                or not _is_sha256(item.get("sha256"))
                or not isinstance(item.get("size_bytes"), int)
                or item["size_bytes"] <= 0
            ):
                raise Clean2EvidenceError("CLEAN2 sealed file row is invalid")
            _safe_relative(item.get("relative_path"), label="sealed relative_path")
    registry_by_id: dict[str, dict[str, Any]] | None = None
    if registry_path is not None:
        registry_source = Path(registry_path).resolve(strict=True)
        if sha256_file(registry_source) != payload["registry_sha256"]:
            raise Clean2EvidenceError("CLEAN2 registry changed after output seal")
        registry_rows = read_run_registry(registry_source)
        registry_by_id = {str(row["run_id"]): row for row in registry_rows}
        for sealed, registry in zip(runs, registry_rows):
            expected = _json_digest(
                {field: registry[field] for field in REGISTRY_IDENTITY_FIELDS}
            )
            if sealed.get("registry_row_sha256") != expected or sealed.get("run_id") != registry["run_id"]:
                raise Clean2EvidenceError("CLEAN2 seal no longer binds the supplied registry")
    if runtime_root is not None:
        runtime_path = Path(runtime_root)
        if runtime_path.is_symlink():
            raise Clean2EvidenceError("CLEAN2 runtime root is a symlink")
        runtime = runtime_path.resolve(strict=True)
        for sealed in runs:
            run_root_raw = runtime / str(sealed["run_id"])
            _assert_no_symlink_chain(run_root_raw, runtime)
            run_root = run_root_raw.resolve(strict=True)
            manifest_path = _resolve_run_file(
                run_root,
                FORMAL_MANIFEST_NAME,
                label="sealed formal manifest",
            )
            if sha256_file(manifest_path) != sealed["manifest_sha256"]:
                raise Clean2EvidenceError("CLEAN2 formal wrapper changed after seal")
            if registry_by_id is not None:
                registry_row = registry_by_id.get(str(sealed["run_id"]))
                if registry_row is None:
                    raise Clean2EvidenceError("CLEAN2 sealed run is absent from the registry")
                manifest, current_files, current_counters = _validate_formal_wrapper(
                    run_root, manifest_path, registry_row
                )
                if (
                    current_files != sealed["files"]
                    or current_counters != sealed.get("module_counters")
                    or manifest["runtime_config_hash"] != sealed["runtime_config_hash"]
                    or manifest["provider_bundle_hash"] != sealed["provider_bundle_hash"]
                ):
                    raise Clean2EvidenceError("CLEAN2 seal contents differ from revalidated wrapper")
            for artifact in sealed["files"]:
                relative = PurePosixPath(str(artifact["relative_path"]))
                if not relative.parts or relative.parts[0] != sealed["run_id"]:
                    raise Clean2EvidenceError("CLEAN2 sealed file is not bound to its run id")
                candidate = _resolve_run_file(
                    run_root,
                    PurePosixPath(*relative.parts[1:]).as_posix(),
                    label="sealed output artifact",
                )
                if sha256_file(candidate) != artifact["sha256"] or candidate.stat().st_size != artifact["size_bytes"]:
                    raise Clean2EvidenceError("CLEAN2 output artifact changed after seal")
    return payload


def sealed_output_hash(
    seal: Mapping[str, Any], *, run_id: str, relative_name: str
) -> str:
    matches: list[str] = []
    for run in seal["runs"]:
        if run["run_id"] != run_id:
            continue
        for artifact in run["files"]:
            if Path(str(artifact["relative_path"])).name == relative_name:
                matches.append(str(artifact["sha256"]))
    if len(matches) != 1:
        raise Clean2EvidenceError("Sealed solver output hash is missing or ambiguous")
    return matches[0]


def assert_method_case_output_invariance(
    outputs_by_case: Mapping[str, Sequence[str | Path]],
    *,
    failure_status: str,
    counters_by_case: Mapping[str, Mapping[str, int]] | None = None,
) -> dict[str, Any]:
    """Require supplied NAV/STD bytes and optional counter maps to be identical."""

    if len(outputs_by_case) < 2:
        raise Clean2EvidenceError("Output invariance audit requires at least two cases")
    signatures: dict[str, tuple[str, ...]] = {}
    artifact_count: int | None = None
    for case_id, paths in outputs_by_case.items():
        resolved = [Path(path).resolve(strict=True) for path in paths]
        if not resolved or any(not path.is_file() or path.is_symlink() for path in resolved):
            raise Clean2EvidenceError("Output invariance case has missing/symlink artifacts")
        if artifact_count is None:
            artifact_count = len(resolved)
        elif len(resolved) != artifact_count:
            raise Clean2EvidenceError("Output invariance cases list different artifact counts")
        signatures[str(case_id)] = tuple(sha256_file(path) for path in resolved)
    if len(set(signatures.values())) != 1:
        raise Clean2EvidenceError(failure_status)
    counters_identical = True
    if counters_by_case is not None:
        if set(counters_by_case) != set(outputs_by_case):
            raise Clean2EvidenceError("Output/counter invariance case sets differ")
        counter_signatures = {_json_digest(dict(value)) for value in counters_by_case.values()}
        counters_identical = len(counter_signatures) == 1
        if not counters_identical:
            raise Clean2EvidenceError(failure_status)
    return {
        "case_count": len(signatures),
        "artifact_count_per_case": artifact_count,
        "bit_identical": True,
        "counters_identical": counters_identical,
        "passed": True,
    }


def assert_position_velocity_case_isolation(
    gnss_by_case: Mapping[str, str | Path],
) -> dict[str, Any]:
    """Compare time/position/std/receiver-velocity/std tokens exactly to C00."""

    if len(gnss_by_case) != 18:
        raise Clean2EvidenceError("Position/velocity isolation requires all 18 case inputs")
    c00_keys = [key for key in gnss_by_case if str(key).startswith("C00_")]
    if len(c00_keys) != 1:
        raise Clean2EvidenceError("Position/velocity isolation lacks one C00 input")

    def projection(path: str | Path) -> tuple[tuple[str, ...], ...]:
        source = Path(path)
        if source.is_symlink():
            raise Clean2EvidenceError("Case GNSS isolation input is a symlink")
        rows: list[tuple[str, ...]] = []
        for line in source.resolve(strict=True).read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            fields = stripped.replace(",", " ").split()
            if len(fields) < 18:
                raise Clean2EvidenceError("Case GNSS input is not the explicit-validity schema")
            # Columns 0..12 are time, position/std, and receiver velocity/std;
            # explicit position_valid/velocity_valid are columns 15/16 and are
            # equally forbidden from changing in a yaw-only case.
            rows.append(tuple([*fields[:13], fields[15], fields[16]]))
        if not rows:
            raise Clean2EvidenceError("Case GNSS isolation input has no data rows")
        return tuple(rows)

    baseline = projection(gnss_by_case[c00_keys[0]])
    for case_id, path in gnss_by_case.items():
        if projection(path) != baseline:
            raise Clean2EvidenceError("FAIL_CLEAN2_POSITION_VELOCITY_SOURCE_ISOLATION")
    return {
        "case_count": 18,
        "row_count": len(baseline),
        "position_velocity_fields_bit_identical": True,
        "passed": True,
    }


def audit_clean2_formal_invariants(
    *,
    registry_path: str | Path,
    runtime_root: str | Path,
    complete_output_seal_path: str | Path,
    solver_artifact_index_path: str | Path,
    offline_evaluation_index_path: str | Path,
    case_provider_index_path: str | Path,
) -> dict[str, Any]:
    """Audit all exact post-run invariants from sealed artifacts and wrappers."""

    rows = read_run_registry(registry_path)
    seal = validate_complete_output_seal(
        complete_output_seal_path,
        runtime_root=runtime_root,
        registry_path=registry_path,
    )
    runtime = Path(runtime_root).resolve(strict=True)
    from .clean2_evaluator import (
        load_and_crosscheck_evaluation_index,
        load_solver_artifact_index,
        validate_sealed_solver_artifact_index,
    )

    solver_artifacts = load_solver_artifact_index(
        solver_artifact_index_path, expected_runtime_root=runtime
    )
    artifact_validation = validate_sealed_solver_artifact_index(
        artifact_index=solver_artifacts,
        complete_output_seal_path=complete_output_seal_path,
        require_action_traces=True,
    )
    evaluation_summaries, evaluation_crosscheck = (
        load_and_crosscheck_evaluation_index(
            offline_evaluation_index_path,
            expected_solver_artifact_index_sha256=solver_artifacts.metadata[
                "index_sha256"
            ],
            expected_complete_output_seal_sha256=sha256_file(
                complete_output_seal_path
            ),
            expected_solver_artifacts=solver_artifacts,
        )
    )
    if (
        artifact_validation.get("nav_std_artifact_count") != 220
        or artifact_validation.get("passed") is not True
        or len(evaluation_summaries) != 110
        or evaluation_crosscheck.get("passed") is not True
    ):
        raise Clean2EvidenceError("CLEAN2 sealed/evaluated artifact chain is incomplete")
    manifests: dict[str, dict[str, Any]] = {}
    for row in rows:
        path = runtime / str(row["run_id"]) / FORMAL_MANIFEST_NAME
        manifest = json.loads(path.read_text(encoding="utf-8"))
        _validate_formal_wrapper(path.parent, path, row)
        manifests[str(row["run_id"])] = manifest

    def case_code(row: Mapping[str, Any]) -> str:
        return str(row["case_id"]).split("_", 1)[0]

    def output_paths(row: Mapping[str, Any]) -> list[Path]:
        manifest = manifests[str(row["run_id"])]
        return [
            _resolve_run_file(runtime / str(row["run_id"]), manifest["output_files"][role], label=role)
            for role in ("exact_nav", "exact_std")
        ]

    single_rows = [row for row in rows if row["structural_method"] == "single_antenna_EKF"]
    if len(single_rows) != 18:
        raise Clean2EvidenceError("Single-method invariance does not cover C00..C17")
    single = assert_method_case_output_invariance(
        {case_code(row): output_paths(row) for row in single_rows},
        counters_by_case={
            case_code(row): _counter_signature(manifests[str(row["run_id"])])
            for row in single_rows
        },
        failure_status="FAIL_CLEAN2_DUAL_YAW_CASE_LEAKED_INTO_SINGLE_BASELINE",
    )
    basic_rows = [
        row
        for row in rows
        if row["structural_method"] == "basic_dual_yaw_EKF"
        and case_code(row) in {"C00", "C10", "C14"}
    ]
    if len(basic_rows) != 3:
        raise Clean2EvidenceError("Basic fixed-std audit lacks C00/C10/C14")
    basic = assert_method_case_output_invariance(
        {case_code(row): output_paths(row) for row in basic_rows},
        counters_by_case={
            case_code(row): _counter_signature(manifests[str(row["run_id"])])
            for row in basic_rows
        },
        failure_status="CLEAN2 basic fixed-1.5deg semantics invariant failed",
    )
    c00_ab = {
        str(row["ablation_id"]): row
        for row in rows
        if str(row["case_id"]).startswith("C00_") and row["ablation_id"] in {"AB0000", "AB1111"}
    }
    if set(c00_ab) != {"AB0000", "AB1111"}:
        raise Clean2EvidenceError("CLEAN2 C00 strong/full alias rows are missing")
    if (
        set(str(c00_ab["AB0000"]["alias_roles"]).split(";"))
        .isdisjoint({"canonical_strong"})
        or set(str(c00_ab["AB1111"]["alias_roles"]).split(";"))
        .isdisjoint({"canonical_LegSA"})
        or any(c00_ab[key]["structural_method"] != "strong_dual_yaw_EKF" for key in c00_ab)
    ):
        raise Clean2EvidenceError("CLEAN2 C00 strong/full alias identity drifted")
    for manifest in manifests.values():
        _validate_module_semantics(manifest)
    from .clean2_case_provider import validate_case_provider_index

    _, cases_by_id = validate_case_provider_index(
        case_provider_index_path, expected_code_commit=str(seal["code_commit"])
    )
    cases = list(cases_by_id.values())
    gnss_by_case = {
        str(item["case_id"]): str(item["gnss_path"])
        for item in cases
        if isinstance(item, Mapping) and "case_id" in item and "gnss_path" in item
    }
    isolation = assert_position_velocity_case_isolation(gnss_by_case)
    return {
        "schema_version": "paper_rebuild.clean2_formal_invariants.v2",
        "case_provider_index_sha256": sha256_file(case_provider_index_path),
        "run_registry_sha256": sha256_file(registry_path),
        "complete_output_seal_sha256": sha256_file(complete_output_seal_path),
        "solver_artifact_index_sha256": sha256_file(solver_artifact_index_path),
        "offline_evaluation_index_sha256": sha256_file(offline_evaluation_index_path),
        "unique_formal_run_count": len(rows),
        "single_C00_C17_NAV_STD_counters": single,
        "basic_C00_C10_C14_fixed_std_NAV_STD_counters": basic,
        "position_velocity_case_isolation": isolation,
        "C00_AB0000_canonical_strong_alias": True,
        "C00_AB1111_canonical_LegSA_alias": True,
        "module_counter_run_count": len(manifests),
        "solver_artifact_index_run_count": len(solver_artifacts),
        "offline_evaluation_summary_count": len(evaluation_summaries),
        "offline_evaluation_independent_row_recomputation_count": evaluation_crosscheck[
            "independent_row_recomputation_count"
        ],
        "forbidden_counter_nonzero_count": 0,
        "trace_open_count": 0,
        "passed": all(
            (
                len(rows)
                == len(seal["runs"])
                == len(solver_artifacts)
                == len(evaluation_summaries)
                == 110,
                single.get("passed") is True,
                basic.get("passed") is True,
                isolation.get("passed") is True,
                len(manifests) == 110,
                artifact_validation.get("passed") is True,
                evaluation_crosscheck.get("passed") is True,
            )
        ),
    }


def _terminal_json(path: Path, *, label: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise Clean2EvidenceError(f"{label} is not a JSON object")
    return dict(payload)


def _validate_raw_terminal_checkpoint(path: Path, *, phase: str) -> dict[str, Any]:
    payload = _terminal_json(path, label=f"raw {phase} checkpoint")
    hashes = payload.get("verified_hashes")
    if (
        payload.get("schema_version") != "paper_rebuild.final_v23_external_raw_checkpoint.v1"
        or payload.get("audit_phase") != phase
        or payload.get("expected") != 22
        or payload.get("verified") != 22
        or payload.get("missing") != 0
        or payload.get("mismatch") != 0
        or payload.get("symlink_escape") != 0
        or payload.get("raw_mutation") != 0
        or payload.get("passed") is not True
        or not isinstance(hashes, Mapping)
        or set(hashes) != set(BY2_RAW_RELATIVE_PATHS)
        or any(not _is_sha256(value) for value in hashes.values())
        or not _is_sha256(payload.get("raw_hash_lock_sha256"))
        or payload.get("trace_provider_or_solver_input") is not False
    ):
        raise Clean2EvidenceError(f"CLEAN2 raw {phase} checkpoint is not 22/22 PASS")
    return payload


def _validate_attempt_ledger(path: Path, registry_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    from .clean2_runner import ATTEMPT_FIELDS, validate_attempt_rows

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ATTEMPT_FIELDS:
            raise Clean2EvidenceError("CLEAN2 attempt ledger columns/order drifted")
        rows = list(reader)
    expected_ids = {str(row["run_id"]) for row in registry_rows}
    computed = validate_attempt_rows(
        rows,
        registry_rows=registry_rows,
        required_run_ids=expected_ids,
    )
    by_run: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_run.setdefault(str(row["run_id"]), []).append(row)
    if set(by_run) != expected_ids:
        raise Clean2EvidenceError("CLEAN2 attempt ledger does not cover exactly 110 registry runs")
    registry_order = {str(row["run_id"]): int(row["run_order"]) for row in registry_rows}
    retry_count = 0
    for run_id, attempts in by_run.items():
        attempts.sort(key=lambda row: int(row["attempt_number"]))
        if (
            len(attempts) not in {1, 2}
            or [int(row["attempt_number"]) for row in attempts] != list(range(1, len(attempts) + 1))
            or any(int(row["run_order"]) != registry_order[run_id] for row in attempts)
            or attempts[-1]["terminal_status"] != "PASS"
            or int(attempts[-1]["returncode"]) != 0
        ):
            raise Clean2EvidenceError("CLEAN2 attempt history is not terminal PASS")
        if len(attempts) == 1:
            if str(attempts[0]["technical_retry"]).casefold() not in {"false", "0"}:
                raise Clean2EvidenceError("Single CLEAN2 attempt is mislabeled as a retry")
        else:
            retry_count += 1
            if (
                attempts[0]["terminal_status"] != "RETRYABLE_TECHNICAL_FAILURE"
                or not attempts[0]["retry_reason"]
                or str(attempts[0]["technical_retry"]).casefold() not in {"false", "0"}
                or str(attempts[1]["technical_retry"]).casefold() not in {"true", "1"}
                or attempts[1]["retry_reason"] != attempts[0]["retry_reason"]
            ):
                raise Clean2EvidenceError("CLEAN2 retry lacks one explicit technical-failure chain")
    expected_computed = {
        "run_count": len(by_run),
        "attempt_count": len(rows),
        "technical_retry_run_count": retry_count,
        "all_terminal_pass": True,
        "metric_driven_rerun": False,
        "passed": len(by_run) == 110,
    }
    if computed != expected_computed:
        raise Clean2EvidenceError("CLEAN2 attempt audit recomputation changed")
    return expected_computed


def _validate_terminal_attempt_audit(
    *,
    registry_path: Path,
    attempts_path: Path,
    audit_path: Path,
    registry_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Recompute all 110 attempt chains and require the exact terminal audit."""

    computed = _validate_attempt_ledger(attempts_path, registry_rows)
    persisted = _terminal_json(audit_path, label="terminal attempt audit")
    expected = {
        "schema_version": "paper_rebuild.clean2_terminal_attempt_audit.v1",
        "stage_id": STAGE_ID,
        "registry_sha256": sha256_file(registry_path),
        "attempts_sha256": sha256_file(attempts_path),
        **computed,
    }
    if persisted != expected:
        raise Clean2EvidenceError(
            "CLEAN2 registry/attempt-ledger/attempt-audit three-way binding failed"
        )
    return computed, persisted


def _validate_terminal_reports(
    *,
    review_path: Path,
    full_report_json_path: Path,
    full_report_md_path: Path,
    expected_review_hashes: Mapping[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    review = _terminal_json(review_path, label="CLEAN2 final review")
    decision = str(review.get("decision") or review.get("verdict") or "")
    if (
        review.get("schema_version") != "paper_rebuild.clean2_final_review.v1"
        or review.get("stage_id") != STAGE_ID
        or review.get("read_only_review") is not True
        or review.get("passed") is not True
        or decision != "APPROVED_FOR_HUMAN_REVIEW"
        or review.get("reviewed_artifact_hashes") != dict(expected_review_hashes)
    ):
        raise Clean2EvidenceError("CLEAN2 final read-only review is absent, stale, or not approved")
    report = _terminal_json(full_report_json_path, label="CLEAN2 full report")
    if (
        report.get("stage_id") != STAGE_ID
        or report.get("terminal_decision") != TERMINAL_DECISION
        or report.get("passed") is not True
        or report.get("classic18_controlled_not_real_scenarios") is not True
        or report.get("universal_superiority_established") is not False
        or report.get("BY3_XB_60x9_executed") is not False
    ):
        raise Clean2EvidenceError("CLEAN2 full report does not carry the frozen terminal decision")
    markdown = full_report_md_path.read_text(encoding="utf-8")
    required_lines = (
        "This stage does not establish universal superiority.",
        "Classic-18 is a controlled dual-yaw degradation pilot.",
        "BY3/XB and the 60x9 matrix remain unexecuted.",
    )
    if TERMINAL_DECISION not in markdown or any(line not in markdown for line in required_lines):
        raise Clean2EvidenceError("CLEAN2 Markdown report lacks the terminal decision/claim boundary")
    return review, report


def _terminal_artifact(
    stage: Path, path: str | Path, *, role: str
) -> tuple[Path, dict[str, Any]]:
    raw = Path(path)
    _assert_no_symlink_chain(raw, stage)
    source = raw.resolve(strict=True)
    expected_relative = TERMINAL_ARTIFACT_RELATIVE_PATHS.get(role)
    if expected_relative is None or source != stage / expected_relative or not source.is_file():
        raise Clean2EvidenceError(f"CLEAN2 terminal artifact escaped its exact stage identity: {role}")
    return source, {
        "relative_path": source.relative_to(stage).as_posix(),
        "sha256": sha256_file(source),
        "size_bytes": source.stat().st_size,
    }


def _validate_c00_structural_alias_rows(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[str, str, str, str]:
    """Freeze the actual four-process C00 identity and CLEAN1 reference aliases."""

    expected = (
        ("single_antenna_EKF", "", (False, False, False, False), "canonical_single_antenna_EKF"),
        ("basic_dual_yaw_EKF", "", (False, False, False, False), "canonical_basic_dual_yaw_EKF"),
        ("strong_dual_yaw_EKF", "AB0000", (False, False, False, False), "canonical_strong"),
        ("strong_dual_yaw_EKF", "AB1111", (True, True, True, True), "canonical_LegSA"),
    )
    reference_methods = (
        "single_antenna_EKF",
        "basic_dual_yaw_EKF",
        "strong_dual_yaw_EKF",
        "LegSA_Paper_V1",
    )
    if len(rows) != len(expected):
        raise Clean2EvidenceError("CLEAN2 C00 structural gate lacks four registry roles")
    for row, (structural, ablation, features, required_alias) in zip(rows, expected):
        aliases = set(str(row.get("alias_roles") or "").split(";"))
        actual_features = tuple(
            row.get(field) for field in ("feature_RD", "feature_SA", "feature_RP", "feature_HV")
        )
        if (
            not str(row.get("case_id") or "").startswith("C00_")
            or row.get("structural_method") != structural
            or row.get("ablation_id") != ablation
            or actual_features != features
            or required_alias not in aliases
            or "C00_structural_gate" not in aliases
            or row.get("formal") is not True
        ):
            raise Clean2EvidenceError("CLEAN2 C00 structural alias/feature identity drifted")
    return reference_methods


def _validate_terminal_c00_structural_gate(
    *,
    stage: Path,
    runtime_root: Path,
    gate_path: Path,
    registry_rows: Sequence[Mapping[str, Any]],
    case_provider_index_path: Path,
    code_commit: str,
) -> dict[str, Any]:
    """Rebuild the C00 gate without requiring live HEAD to equal code freeze.

    The report-only commit is allowed to move HEAD.  The executable, its frozen
    source-file bytes, four current wrappers/NAV/STD/counters, and current
    CLEAN1 reference artifacts remain exact-hash requirements.
    """

    from .clean2_runner import _compare_nav_std, _load_clean1_reference_index, phase_rows
    from .paths import load_yaml_mapping

    gate = _terminal_json(gate_path, label="CLEAN2 C00 structural gate")
    c00_rows = phase_rows(registry_rows, "structural_gate")
    reference_methods = _validate_c00_structural_alias_rows(c00_rows)

    source_manifest_path = stage / "01_GIT_FREEZE/CLEAN2_EXECUTABLE_SOURCE_MANIFEST.json"
    clean1_reference_path = stage / "01_GIT_FREEZE/CLEAN1R2R1_STRUCTURAL_REFERENCE.json"
    for artifact in (source_manifest_path, clean1_reference_path):
        _assert_no_symlink_chain(artifact, stage)
        if not artifact.is_file():
            raise Clean2EvidenceError("CLEAN2 structural freeze artifact is missing")

    bindings_by_run: dict[str, dict[str, Any]] = {}
    code_roots: set[Path] = set()
    executable_paths: set[Path] = set()
    for row in c00_rows:
        run_root = runtime_root / str(row["run_id"])
        binding_path = run_root / "runtime_config/RUN_BINDINGS.json"
        _assert_no_symlink_chain(binding_path, runtime_root)
        binding = _terminal_json(binding_path, label="CLEAN2 C00 run bindings")
        bindings_by_run[str(row["run_id"])] = binding
        code_root_raw = Path(str(binding.get("code_root") or ""))
        executable_raw = Path(str(binding.get("executable_path") or ""))
        if code_root_raw.is_symlink() or executable_raw.is_symlink():
            raise Clean2EvidenceError("CLEAN2 C00 code/executable binding is a symlink")
        code_roots.add(code_root_raw.resolve(strict=True))
        executable_paths.add(executable_raw.resolve(strict=True))
        if (
            binding.get("code_commit") != code_commit
            or Path(str(binding.get("executable_source_manifest_path") or "")).resolve(strict=True)
            != source_manifest_path
            or binding.get("executable_source_manifest_hash") != sha256_file(source_manifest_path)
            or Path(str(binding.get("case_provider_index_path") or "")).resolve(strict=True)
            != case_provider_index_path
            or binding.get("case_provider_index_hash") != sha256_file(case_provider_index_path)
        ):
            raise Clean2EvidenceError("CLEAN2 C00 frozen run binding drifted")
    if len(code_roots) != 1 or len(executable_paths) != 1:
        raise Clean2EvidenceError("CLEAN2 C00 executable/code-root identities differ")
    code_root = next(iter(code_roots))
    executable = next(iter(executable_paths))

    source_manifest = _terminal_json(
        source_manifest_path, label="CLEAN2 executable/source manifest"
    )
    source_files = source_manifest.get("source_files")
    if (
        source_manifest.get("schema_version")
        != "paper_rebuild.clean2_executable_source_manifest.v1"
        or source_manifest.get("stage_id") != STAGE_ID
        or source_manifest.get("code_commit") != code_commit
        or source_manifest.get("code_worktree_dirty") is not False
        or source_manifest.get("executable_path") != str(executable)
        or source_manifest.get("executable_hash") != sha256_file(executable)
        or source_manifest.get("terminal_status") != "PASS"
        or not isinstance(source_files, Mapping)
        or source_manifest.get("source_file_count") != len(source_files)
        or not source_files
    ):
        raise Clean2EvidenceError("CLEAN2 executable/source freeze identity drifted")
    for relative_text, expected_hash in source_files.items():
        relative = _safe_relative(relative_text, label="executable source file")
        source_file = code_root.joinpath(*relative.parts)
        if source_file.is_symlink():
            raise Clean2EvidenceError("CLEAN2 executable source file is a symlink")
        resolved_source = source_file.resolve(strict=True)
        if (
            code_root not in resolved_source.parents
            or not resolved_source.is_file()
            or sha256_file(resolved_source) != expected_hash
        ):
            raise Clean2EvidenceError("CLEAN2 executable source bytes changed after freeze")
    executable_hash = sha256_file(executable)
    source_manifest_hash = sha256_file(source_manifest_path)
    if any(
        row.get("executable_hash") != executable_hash
        or bindings_by_run[str(row["run_id"])].get("executable_hash") != executable_hash
        for row in c00_rows
    ):
        raise Clean2EvidenceError("CLEAN2 C00 executable hash differs from registry/bindings")

    reference_payload, references = _load_clean1_reference_index(clean1_reference_path)
    parity_path = code_root / "configs/paper_rebuild/final_v23_parity_contract.yaml"
    parity_snapshot = stage / "02_PROTOCOLS/final_v23_parity_contract.yaml"
    if (
        parity_path.is_symlink()
        or parity_snapshot.is_symlink()
        or sha256_file(parity_path) != sha256_file(parity_snapshot)
    ):
        raise Clean2EvidenceError("CLEAN2 frozen parity contract changed")
    tolerance = load_yaml_mapping(parity_path)["clean1r2r1_parity_tolerance"]
    counter_fields = (
        "position_update_count", "receiver_velocity_update_count", "dual_yaw_attempt_count",
        "dual_yaw_accepted_count", "yaw_NORMAL", "yaw_DOWNWEIGHT", "yaw_REJECT",
        "raw_doppler_update_count", "source_aware_evaluation_count",
        "source_aware_weight_changed_count", "go2_roll_pitch_update_count",
        "go2_horizontal_velocity_update_count", "selected_fgo_feedback_update_count",
        "nine_factor_fgo_update_count", "qa_fallback_count", "multi_state_qm_update_count",
        "contact_fk_update_count",
    )
    comparisons: list[dict[str, Any]] = []
    for row, method in zip(c00_rows, reference_methods):
        run_root = runtime_root / str(row["run_id"])
        wrapper_path = run_root / FORMAL_MANIFEST_NAME
        manifest, _, _ = _validate_formal_wrapper(run_root, wrapper_path, row)
        if (
            manifest.get("code_commit") != code_commit
            or manifest.get("executable_hash") != executable_hash
            or manifest.get("executable_source_manifest_hash") != source_manifest_hash
        ):
            raise Clean2EvidenceError("CLEAN2 C00 formal wrapper freeze binding drifted")
        current_nav = _resolve_run_file(
            run_root, manifest["output_files"]["exact_nav"], label="C00 exact NAV"
        )
        current_std = _resolve_run_file(
            run_root, manifest["output_files"]["exact_std"], label="C00 exact STD"
        )
        current_solver_path = _resolve_run_file(
            run_root, manifest["output_files"]["solver_manifest"], label="C00 solver manifest"
        )
        current_solver = _terminal_json(current_solver_path, label="C00 solver manifest")
        reference = references[method]
        reference_solver = _terminal_json(
            Path(reference["solver_manifest_path"]), label="CLEAN1 solver reference"
        )
        try:
            counters_exact = all(
                int(current_solver[field]) == int(reference_solver[field])
                for field in counter_fields
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise Clean2EvidenceError("C00 structural counter set is incomplete") from exc
        numeric = _compare_nav_std(
            current_nav,
            Path(reference["nav_path"]),
            current_std,
            Path(reference["std_path"]),
            tolerance,
        )
        comparisons.append(
            {
                "method": method,
                "run_id": row["run_id"],
                "wrapper_sha256": sha256_file(wrapper_path),
                "current_nav_sha256": sha256_file(current_nav),
                "current_std_sha256": sha256_file(current_std),
                "reference_nav_sha256": reference["nav_sha256"],
                "reference_std_sha256": reference["std_sha256"],
                "counter_fields": list(counter_fields),
                "counters_exact": counters_exact,
                "numeric": numeric,
                "passed": counters_exact and numeric["passed"],
            }
        )
    expected = {
        "schema_version": "paper_rebuild.clean2_c00_structural_gate.v1",
        "stage_id": STAGE_ID,
        "code_commit": code_commit,
        "code_worktree_dirty": False,
        "registry_sha256": sha256_file(stage / TERMINAL_ARTIFACT_RELATIVE_PATHS["registry"]),
        "case_provider_index_sha256": sha256_file(case_provider_index_path),
        "executable_sha256": executable_hash,
        "executable_source_manifest_sha256": source_manifest_hash,
        "clean1_reference_index_sha256": reference_payload["index_sha256"],
        "parity_contract_sha256": sha256_file(parity_path),
        "comparison_count": len(comparisons),
        "comparisons": comparisons,
        "trace_open_count": 0,
        "performance_metric_read": False,
        "solver_input_from_clean1_outputs": False,
        "performance_reuse": False,
        "C00_structural_parity": all(row["passed"] for row in comparisons),
        "passed": all(row["passed"] for row in comparisons),
    }
    expected["binding_digest"] = _json_digest(expected)
    if gate != expected or expected["comparison_count"] != 4 or expected["passed"] is not True:
        raise Clean2EvidenceError("BLOCKED_CLEAN2_C00_STRUCTURAL_PARITY_FAILED")
    return {
        "comparison_count": 4,
        "code_commit": code_commit,
        "executable_sha256": executable_hash,
        "executable_source_file_count": len(source_files),
        "clean1_reference_index_sha256": reference_payload["index_sha256"],
        "passed": True,
    }


def _validate_terminal_invariants(
    *, artifacts: Mapping[str, Path], runtime_root: Path
) -> dict[str, Any]:
    """Require the persisted invariant object to equal a fresh full recomputation."""

    persisted = _terminal_json(artifacts["invariants"], label="formal invariants")
    recomputed = audit_clean2_formal_invariants(
        registry_path=artifacts["registry"],
        runtime_root=runtime_root,
        complete_output_seal_path=artifacts["complete_output_seal"],
        solver_artifact_index_path=artifacts["solver_artifact_index"],
        offline_evaluation_index_path=artifacts["offline_evaluation_index"],
        case_provider_index_path=artifacts["case_provider_index"],
    )
    if persisted != recomputed or recomputed.get("passed") is not True:
        raise Clean2EvidenceError("CLEAN2 formal invariants are not terminal PASS")
    return recomputed


def _validate_terminal_offline_chain_identity(
    offline: Mapping[str, Any], *, artifacts: Mapping[str, Path]
) -> list[Mapping[str, Any]]:
    """Bind the offline index to the current registry, attempts, audit, and seal."""

    results = offline.get("results")
    if (
        offline.get("schema_version") != "paper_rebuild.clean2_offline_evaluation_index.v2"
        or offline.get("run_count") != 110
        or offline.get("passed") is not True
        or offline.get("all_110_outputs_validated_before_trace") is not True
        or offline.get("all_outputs_sealed_before_trace") is not True
        or offline.get("all_110_attempt_histories_validated_before_trace") is not True
        or offline.get("terminal_attempt_audit_validated_before_trace") is not True
        or offline.get("trace_used_online") is not False
        or offline.get("exact_evaluator_sha256")
        != "aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da"
        or offline.get("trace_sha256")
        != "ee3ee42dea3ada196dfdbcc78fd07524f91b4ce4fb94d9d6482a3e7d4b34aa4c"
        or offline.get("solver_artifact_index_sha256")
        != sha256_file(artifacts["solver_artifact_index"])
        or offline.get("complete_output_seal_sha256")
        != sha256_file(artifacts["complete_output_seal"])
        or offline.get("registry_sha256") != sha256_file(artifacts["registry"])
        or offline.get("run_attempts_sha256") != sha256_file(artifacts["attempts"])
        or offline.get("run_attempts_audit_sha256")
        != sha256_file(artifacts["attempts_audit"])
        or not isinstance(results, list)
        or len(results) != 110
        or not all(isinstance(row, Mapping) for row in results)
    ):
        raise Clean2EvidenceError("CLEAN2 offline evaluation index is stale or incomplete")
    return list(results)


def _terminal_semantic_checks(
    *,
    stage: Path,
    runtime_root: Path,
    artifacts: Mapping[str, Path],
) -> dict[str, Any]:
    registry_rows = read_run_registry(artifacts["registry"])
    from .clean2_case_provider import validate_case_provider_index

    seal = validate_complete_output_seal(
        artifacts["complete_output_seal"],
        runtime_root=runtime_root,
        registry_path=artifacts["registry"],
    )
    attempts, _ = _validate_terminal_attempt_audit(
        registry_path=artifacts["registry"],
        attempts_path=artifacts["attempts"],
        audit_path=artifacts["attempts_audit"],
        registry_rows=registry_rows,
    )
    case_index, _ = validate_case_provider_index(
        artifacts["case_provider_index"], expected_code_commit=str(seal["code_commit"])
    )
    try:
        structural_gate = _validate_terminal_c00_structural_gate(
            stage=stage,
            runtime_root=runtime_root,
            gate_path=artifacts["c00_structural_gate"],
            registry_rows=registry_rows,
            case_provider_index_path=artifacts["case_provider_index"],
            code_commit=str(seal["code_commit"]),
        )
    except Clean2EvidenceError:
        raise
    except (OSError, TypeError, ValueError, KeyError, RuntimeError) as exc:
        raise Clean2EvidenceError(
            "BLOCKED_CLEAN2_C00_STRUCTURAL_PARITY_FAILED"
        ) from exc
    base_evidence = case_index.get("base_provider_evidence")
    if not isinstance(base_evidence, Mapping):
        raise Clean2EvidenceError("CLEAN2 case index lacks base-provider evidence")
    for field, name in (
        ("export_safe_base_manifest_path", "CLEAN2_BASE_PROVIDER_MANIFEST.json"),
        ("export_safe_base_hashes_path", "CLEAN2_BASE_PROVIDER_HASHES.csv"),
    ):
        expected = stage / "04_BASE_PROVIDER" / name
        if Path(str(base_evidence.get(field) or "")).resolve(strict=True) != expected:
            raise Clean2EvidenceError("CLEAN2 sanitized base-provider snapshot path drifted")
    artifact_index = _terminal_json(
        artifacts["solver_artifact_index"], label="solver artifact index"
    )
    unsigned_index = {
        key: value for key, value in artifact_index.items() if key != "binding_digest"
    }
    if (
        artifact_index.get("schema_version") != "paper_rebuild.clean2_solver_artifact_index.v1"
        or artifact_index.get("stage_id") != STAGE_ID
        or artifact_index.get("run_count") != 110
        or artifact_index.get("passed") is not True
        or artifact_index.get("registry_sha256") != sha256_file(artifacts["registry"])
        or artifact_index.get("complete_output_seal_sha256")
        != sha256_file(artifacts["complete_output_seal"])
        or artifact_index.get("runtime_root") != str(runtime_root.resolve(strict=True))
        or artifact_index.get("binding_digest") != _json_digest(unsigned_index)
        or not isinstance(artifact_index.get("runs"), list)
        or len(artifact_index["runs"]) != 110
    ):
        raise Clean2EvidenceError("CLEAN2 solver artifact index is stale or incomplete")
    from .clean2_evaluator import (
        load_and_crosscheck_evaluation_index,
        load_solver_artifact_index,
        validate_sealed_solver_artifact_index,
    )

    try:
        solver_artifacts = load_solver_artifact_index(
            artifacts["solver_artifact_index"], expected_runtime_root=runtime_root
        )
        solver_artifact_crosscheck = validate_sealed_solver_artifact_index(
            artifact_index=solver_artifacts,
            complete_output_seal_path=artifacts["complete_output_seal"],
            require_action_traces=True,
        )
    except (OSError, TypeError, ValueError, KeyError, RuntimeError) as exc:
        raise Clean2EvidenceError(
            "CLEAN2 solver artifact index failed terminal revalidation"
        ) from exc
    if (
        len(solver_artifacts) != 110
        or solver_artifact_crosscheck.get("nav_std_artifact_count") != 220
        or solver_artifact_crosscheck.get("passed") is not True
    ):
        raise Clean2EvidenceError(
            "CLEAN2 solver artifact index failed terminal revalidation"
        )
    offline = _terminal_json(
        artifacts["offline_evaluation_index"], label="offline evaluation index"
    )
    offline_results = _validate_terminal_offline_chain_identity(
        offline, artifacts=artifacts
    )
    expected_run_ids = {str(row["run_id"]) for row in seal["runs"]}
    if {str(row.get("run_id")) for row in offline_results if isinstance(row, Mapping)} != expected_run_ids:
        raise Clean2EvidenceError("CLEAN2 offline evaluation run ids differ from the output seal")
    # 终态 gate 不能只信任汇总索引中的 passed 标志；重新读取 110 份压缩误差序列，
    # 并逐项复算 summary、coverage、final error 及 gzip hash 绑定。
    try:
        _, evaluation_crosscheck = load_and_crosscheck_evaluation_index(
            artifacts["offline_evaluation_index"],
            expected_solver_artifact_index_sha256=sha256_file(
                artifacts["solver_artifact_index"]
            ),
            expected_complete_output_seal_sha256=sha256_file(
                artifacts["complete_output_seal"]
            ),
            expected_registry_sha256=sha256_file(artifacts["registry"]),
            expected_run_attempts_sha256=sha256_file(artifacts["attempts"]),
            expected_run_attempts_audit_sha256=sha256_file(
                artifacts["attempts_audit"]
            ),
            expected_solver_artifacts=solver_artifacts,
        )
    except (OSError, TypeError, ValueError, KeyError, RuntimeError) as exc:
        raise Clean2EvidenceError(
            "CLEAN2 offline evaluation artifacts failed terminal revalidation"
        ) from exc
    if (
        evaluation_crosscheck.get("run_count") != 110
        or evaluation_crosscheck.get("independent_row_recomputation_count") != 110
        or evaluation_crosscheck.get("passed") is not True
    ):
        raise Clean2EvidenceError(
            "CLEAN2 offline evaluation artifacts failed terminal revalidation"
        )
    raw = {
        phase: _validate_raw_terminal_checkpoint(artifacts[f"raw_{phase}"], phase=phase)
        for phase in ("pre_provider", "post_provider", "post_run")
    }
    raw_hash_maps = {
        json.dumps(payload["verified_hashes"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for payload in raw.values()
    }
    raw_lock_hashes = {payload["raw_hash_lock_sha256"] for payload in raw.values()}
    if len(raw_hash_maps) != 1 or len(raw_lock_hashes) != 1:
        raise Clean2EvidenceError("CLEAN2 raw checkpoints differ across provider/run phases")
    invariants = _validate_terminal_invariants(
        artifacts=artifacts, runtime_root=runtime_root
    )
    aggregate = _terminal_json(artifacts["aggregate"], label="aggregate crosscheck")
    if (
        aggregate.get("passed") is not True
        or aggregate.get("unique_summary_count") != 110
        or aggregate.get("factorial_row_count") != 16
        or aggregate.get("canonical_row_count") != 72
        or aggregate.get("sentinel_LOO_extra_count") != 24
        or aggregate.get("finite_output_count") != 110
        or not isinstance(aggregate.get("independent_table_recomputation"), Mapping)
        or aggregate["independent_table_recomputation"].get("passed") is not True
        or not isinstance(aggregate.get("independent_row_recomputation"), Mapping)
        or aggregate["independent_row_recomputation"].get("passed") is not True
    ):
        raise Clean2EvidenceError("FAIL_CLEAN2_AGGREGATE_CROSSCHECK")
    analysis_hash_paths = {
        "factorial": stage / "10_ABLATION_ANALYSIS/CLEAN2_C00_FACTORIAL_RESULTS.csv",
        "main_effects": stage / "10_ABLATION_ANALYSIS/CLEAN2_C00_MODULE_MAIN_EFFECTS.csv",
        "interactions": stage / "10_ABLATION_ANALYSIS/CLEAN2_C00_PAIRWISE_INTERACTIONS.csv",
        "interpretation": stage / "10_ABLATION_ANALYSIS/CLEAN2_C00_FACTORIAL_INTERPRETATION.md",
        "canonical": stage / "11_CLASSIC18_ANALYSIS/CLEAN2_CANONICAL_CLASSIC18_18x4.csv",
        "deltas": stage / "11_CLASSIC18_ANALYSIS/CLEAN2_CASE_METHOD_DELTAS.csv",
        "family": stage / "11_CLASSIC18_ANALYSIS/CLEAN2_FAMILY_SEED_AGGREGATES.csv",
        "sentinel": stage / "11_CLASSIC18_ANALYSIS/CLEAN2_SENTINEL_LOO_RESULTS.csv",
        "marginal": stage / "11_CLASSIC18_ANALYSIS/CLEAN2_SENTINEL_MODULE_MARGINAL_LOSS.csv",
        "actions": stage / "11_CLASSIC18_ANALYSIS/CLEAN2_PERTURBATION_ACTION_SUMMARY.csv",
        "source_aware": stage / "11_CLASSIC18_ANALYSIS/CLEAN2_SOURCE_AWARE_RESPONSE_SUMMARY.csv",
        "failure": stage / "11_CLASSIC18_ANALYSIS/CLEAN2_FAILURE_AND_FINITE_OUTPUT_SUMMARY.csv",
    }
    table_hashes = aggregate["independent_table_recomputation"].get("table_sha256")
    if not isinstance(table_hashes, Mapping) or set(table_hashes) != set(analysis_hash_paths):
        raise Clean2EvidenceError("CLEAN2 aggregate table hash set is incomplete")
    for key, table_path in analysis_hash_paths.items():
        _assert_no_symlink_chain(table_path, stage)
        if not table_path.is_file() or sha256_file(table_path) != table_hashes[key]:
            raise Clean2EvidenceError("CLEAN2 analysis table changed after aggregate crosscheck")
    figure_qa = _terminal_json(artifacts["figure_qa"], label="figure render QA")
    if (
        figure_qa.get("passed") is not True
        or figure_qa.get("rendered_png_count") != 18
        or figure_qa.get("rendered_pdf_count") != 18
        or figure_qa.get("all_x_ranges_valid") is not True
        or not isinstance(figure_qa.get("semantic_checks"), Mapping)
        or len(figure_qa["semantic_checks"]) != 18
        or not all(figure_qa["semantic_checks"].values())
    ):
        raise Clean2EvidenceError("CLEAN2 figure render QA is incomplete")
    with artifacts["figure_manifest"].open("r", encoding="utf-8-sig", newline="") as handle:
        figure_rows = list(csv.DictReader(handle))
    if (
        len(figure_rows) != 18
        or {str(row.get("figure_id")) for row in figure_rows} != set(FIGURE_NAMES)
        or any(str(row.get("semantic_qa")).casefold() != "true" for row in figure_rows)
    ):
        raise Clean2EvidenceError("CLEAN2 figure manifest is incomplete")
    for row in figure_rows:
        figure_id = str(row["figure_id"])
        for suffix, field in ((".png", "png_sha256"), (".pdf", "pdf_sha256")):
            figure_path = stage / "12_DIAGNOSTIC_FIGURES" / f"{figure_id}{suffix}"
            _assert_no_symlink_chain(figure_path, stage)
            if (
                not figure_path.is_file()
                or not _is_sha256(row.get(field))
                or sha256_file(figure_path) != row[field]
            ):
                raise Clean2EvidenceError("CLEAN2 rendered figure changed after QA")
    expected_review_hashes = {
        "case_provider_index": sha256_file(artifacts["case_provider_index"]),
        "c00_structural_gate": sha256_file(artifacts["c00_structural_gate"]),
        "run_registry": sha256_file(artifacts["registry"]),
        "run_attempts": sha256_file(artifacts["attempts"]),
        "run_attempts_audit": sha256_file(artifacts["attempts_audit"]),
        "complete_output_seal": sha256_file(artifacts["complete_output_seal"]),
        "solver_artifact_index": sha256_file(artifacts["solver_artifact_index"]),
        "offline_evaluation_index": sha256_file(artifacts["offline_evaluation_index"]),
        "raw_pre_provider": sha256_file(artifacts["raw_pre_provider"]),
        "raw_post_provider": sha256_file(artifacts["raw_post_provider"]),
        "raw_post_run": sha256_file(artifacts["raw_post_run"]),
        "formal_invariants": sha256_file(artifacts["invariants"]),
        "aggregate_crosscheck": sha256_file(artifacts["aggregate"]),
        "figure_manifest": sha256_file(artifacts["figure_manifest"]),
        "figure_render_qa": sha256_file(artifacts["figure_qa"]),
    }
    _validate_terminal_reports(
        review_path=artifacts["review"],
        full_report_json_path=artifacts["full_report_json"],
        full_report_md_path=artifacts["full_report_md"],
        expected_review_hashes=expected_review_hashes,
    )
    return {
        "unique_formal_run_count": int(seal["unique_formal_run_count"]),
        "attempts": attempts,
        "raw_pre_provider": "22/22",
        "raw_post_provider": "22/22",
        "raw_post_run": "22/22",
        "C00_structural_parity": structural_gate,
        "solver_artifact_index_run_count": len(solver_artifacts),
        "offline_evaluation_independent_row_recomputation_count": evaluation_crosscheck[
            "independent_row_recomputation_count"
        ],
        "invariants": True,
        "aggregate_crosscheck": True,
        "figure_render_QA": True,
        "final_review": "APPROVED_FOR_HUMAN_REVIEW",
        "passed": True,
    }


def build_clean2_terminal_gate_manifest(
    *,
    stage_root: str | Path,
    runtime_root: str | Path,
    case_provider_index_path: str | Path,
    registry_path: str | Path,
    attempts_path: str | Path,
    attempts_audit_path: str | Path,
    complete_output_seal_path: str | Path,
    solver_artifact_index_path: str | Path,
    offline_evaluation_index_path: str | Path,
    raw_pre_provider_checkpoint_path: str | Path,
    raw_post_provider_checkpoint_path: str | Path,
    raw_post_run_checkpoint_path: str | Path,
    c00_structural_gate_path: str | Path,
    invariants_path: str | Path,
    aggregate_crosscheck_path: str | Path,
    figure_manifest_path: str | Path,
    figure_qa_path: str | Path,
    review_path: str | Path,
    full_report_json_path: str | Path,
    full_report_md_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Build the sole terminal-gate manifest only after every PASS artifact revalidates."""

    stage_raw = Path(stage_root)
    if stage_raw.is_symlink():
        raise Clean2EvidenceError("CLEAN2 terminal gate requires a non-symlink stage root")
    stage = stage_raw.resolve(strict=True)
    if stage.name != EXPECTED_STAGE_DIRNAME:
        raise Clean2EvidenceError("CLEAN2 terminal gate requires the exact stage root")
    runtime_raw = Path(runtime_root)
    if runtime_raw.is_symlink():
        raise Clean2EvidenceError("CLEAN2 terminal gate runtime root is a symlink")
    runtime = runtime_raw.resolve(strict=True)
    if runtime != stage / "07_FORMAL_RUNS":
        raise Clean2EvidenceError("CLEAN2 terminal gate runtime root drifted")
    specifications = {
        "case_provider_index": case_provider_index_path,
        "registry": registry_path,
        "attempts": attempts_path,
        "attempts_audit": attempts_audit_path,
        "complete_output_seal": complete_output_seal_path,
        "solver_artifact_index": solver_artifact_index_path,
        "offline_evaluation_index": offline_evaluation_index_path,
        "raw_pre_provider": raw_pre_provider_checkpoint_path,
        "raw_post_provider": raw_post_provider_checkpoint_path,
        "raw_post_run": raw_post_run_checkpoint_path,
        "c00_structural_gate": c00_structural_gate_path,
        "invariants": invariants_path,
        "aggregate": aggregate_crosscheck_path,
        "figure_manifest": figure_manifest_path,
        "figure_qa": figure_qa_path,
        "review": review_path,
        "full_report_json": full_report_json_path,
        "full_report_md": full_report_md_path,
    }
    paths: dict[str, Path] = {}
    rows: dict[str, Any] = {}
    for role, path in specifications.items():
        paths[role], rows[role] = _terminal_artifact(stage, path, role=role)
    checks = _terminal_semantic_checks(stage=stage, runtime_root=runtime, artifacts=paths)
    payload = {
        "schema_version": TERMINAL_GATE_SCHEMA,
        "stage_id": STAGE_ID,
        "terminal_decision": TERMINAL_DECISION,
        "runtime_root_alias": "<CLEAN2_STAGE>/07_FORMAL_RUNS",
        "artifacts": rows,
        "checks": checks,
        "passed": True,
    }
    destination = Path(output_path)
    if destination.exists() or destination.is_symlink() or destination.resolve(strict=False) != stage / "14_FINAL_EVIDENCE/CLEAN2_TERMINAL_GATE.json":
        raise Clean2EvidenceError("CLEAN2 terminal gate output path is not fresh/exact")
    write_json_atomic(destination, payload)
    return payload


def validate_clean2_terminal_gate(
    path: str | Path, *, stage_root: str | Path
) -> dict[str, Any]:
    """Rehash and semantically revalidate every terminal dependency before export."""

    stage_raw = Path(stage_root)
    source_raw = Path(path)
    if stage_raw.is_symlink() or source_raw.is_symlink():
        raise Clean2EvidenceError("CLEAN2 terminal gate/stage path is a symlink")
    stage = stage_raw.resolve(strict=True)
    source = source_raw.resolve(strict=True)
    payload = _terminal_json(source, label="CLEAN2 terminal gate")
    artifacts = payload.get("artifacts")
    if (
        stage.name != EXPECTED_STAGE_DIRNAME
        or source != stage / "14_FINAL_EVIDENCE/CLEAN2_TERMINAL_GATE.json"
        or payload.get("schema_version") != TERMINAL_GATE_SCHEMA
        or payload.get("stage_id") != STAGE_ID
        or payload.get("terminal_decision") != TERMINAL_DECISION
        or payload.get("passed") is not True
        or not isinstance(artifacts, Mapping)
    ):
        raise Clean2EvidenceError("CLEAN2 terminal gate identity is invalid")
    resolved: dict[str, Path] = {}
    for role, row in artifacts.items():
        if not isinstance(row, Mapping):
            raise Clean2EvidenceError("CLEAN2 terminal gate artifact row is malformed")
        relative = _safe_relative(row.get("relative_path"), label=f"terminal.{role}")
        if relative.as_posix() != TERMINAL_ARTIFACT_RELATIVE_PATHS.get(str(role)):
            raise Clean2EvidenceError("CLEAN2 terminal gate artifact identity drifted")
        candidate = stage.joinpath(*relative.parts)
        _assert_no_symlink_chain(candidate, stage)
        candidate = candidate.resolve(strict=True)
        if (
            stage not in candidate.parents
            or not candidate.is_file()
            or sha256_file(candidate) != row.get("sha256")
            or candidate.stat().st_size != row.get("size_bytes")
        ):
            raise Clean2EvidenceError("CLEAN2 terminal gate artifact changed")
        resolved[str(role)] = candidate
    required = {
        "case_provider_index", "registry", "attempts", "attempts_audit", "complete_output_seal",
        "solver_artifact_index", "offline_evaluation_index", "raw_pre_provider",
        "raw_post_provider", "raw_post_run", "c00_structural_gate", "invariants", "aggregate",
        "figure_manifest", "figure_qa", "review", "full_report_json", "full_report_md",
    }
    if set(resolved) != required:
        raise Clean2EvidenceError("CLEAN2 terminal gate artifact role set drifted")
    checks = _terminal_semantic_checks(
        stage=stage,
        runtime_root=stage / "07_FORMAL_RUNS",
        artifacts=resolved,
    )
    if payload.get("checks") != checks:
        raise Clean2EvidenceError("CLEAN2 terminal gate semantic checks changed")
    return payload


def _member(stage: Path, path: Path, category: str) -> EvidenceMember:
    _assert_no_symlink_chain(path, stage)
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or stage.resolve(strict=True) not in resolved.parents:
        raise Clean2EvidenceError("Explicit evidence member is missing or escaped stage root")
    return EvidenceMember(
        source=resolved,
        archive_path=path.relative_to(stage).as_posix(),
        category=category,
    )


def _direct_files(directory: Path) -> list[Path]:
    if directory.is_symlink() or not directory.is_dir():
        raise Clean2EvidenceError(f"Required evidence directory is missing/symlink: {directory.name}")
    return sorted((path for path in directory.iterdir() if path.is_file()), key=lambda path: path.name)


def _find_one_direct(stage: Path, directories: Sequence[str], name: str, category: str) -> EvidenceMember:
    matches = [stage / directory / name for directory in directories if (stage / directory / name).is_file()]
    if len(matches) != 1:
        raise Clean2EvidenceError(f"Explicit evidence file is missing/ambiguous: {name}")
    return _member(stage, matches[0], category)


def _required_terminal_audit_export_members(stage: Path) -> list[EvidenceMember]:
    """Select exact terminal audits that name-based discovery could omit or duplicate."""

    members = [
        _member(
            stage,
            stage / TERMINAL_ARTIFACT_RELATIVE_PATHS[role],
            "terminal_audit_dependency",
        )
        for role in EXPLICIT_AUDIT_EXPORT_ROLES
    ]
    if len({member.archive_path for member in members}) != len(members):
        raise Clean2EvidenceError("CLEAN2 exact terminal audit export members are duplicated")
    return members


def select_clean2_export_members(stage_root: str | Path) -> list[EvidenceMember]:
    """Select the terminal package via named directories/files, never root recursion."""

    raw_stage = Path(stage_root)
    if raw_stage.is_symlink():
        raise Clean2EvidenceError("CLEAN2 evidence stage root is a symlink")
    stage = raw_stage.resolve(strict=True)
    if stage.name != EXPECTED_STAGE_DIRNAME:
        raise Clean2EvidenceError("Refusing unsafe/root-recursive evidence selection")
    members: list[EvidenceMember] = []

    protocols = stage / "02_PROTOCOLS"
    protocol_files = [path for path in _direct_files(protocols) if path.name in PROTOCOL_EXPORT_NAMES]
    selected_names = {path.name for path in protocol_files}
    if not REQUIRED_PROTOCOL_EXPORT_NAMES.issubset(selected_names):
        raise Clean2EvidenceError("CLEAN2 protocol/config snapshot allowlist is incomplete")
    members.extend(_member(stage, path, "protocol_snapshot") for path in protocol_files)

    for name in (
        "CLEAN2_RAW_PRE_PROVIDER_CHECKPOINT.json",
        "CLEAN2_RAW_POST_PROVIDER_CHECKPOINT.json",
        "CLEAN2_RAW_POST_RUN_CHECKPOINT.json",
    ):
        members.append(
            _member(stage, stage / "03_RAW_AUDITS" / name, "raw_integrity_checkpoint")
        )

    base = stage / "04_BASE_PROVIDER"
    base_candidates = [base / name for name in BASE_EXPORT_NAMES]
    if any(not path.is_file() for path in base_candidates):
        raise Clean2EvidenceError("CLEAN2 sanitized base-provider snapshot is incomplete")
    members.extend(_member(stage, path, "base_provider_manifest") for path in base_candidates)

    cases_root = stage / "05_CASE_PROVIDERS"
    if cases_root.is_symlink() or not cases_root.is_dir():
        raise Clean2EvidenceError("CLEAN2 case-provider evidence directory is missing/symlink")
    case_dirs = sorted(
        (
            path
            for path in cases_root.iterdir()
            if path.is_dir() and re.match(r"^C(?:0[0-9]|1[0-7])(?:_|$)", path.name)
        ),
        key=lambda path: path.name,
    )
    if len(case_dirs) != 18 or len({path.name.split("_", 1)[0] for path in case_dirs}) != 18:
        raise Clean2EvidenceError("CLEAN2 export requires exactly 18 case-provider directories")
    for case_dir in case_dirs:
        if case_dir.is_symlink():
            raise Clean2EvidenceError("CLEAN2 case-provider evidence directory is a symlink")
        for name in CASE_EXPORT_NAMES:
            path = case_dir / name
            if not path.is_file():
                raise Clean2EvidenceError(f"CLEAN2 case export evidence missing: {case_dir.name}/{name}")
            members.append(_member(stage, path, "case_provider_manifest_or_ledger"))

    registry_path = stage / "06_RUN_REGISTRY/CLEAN2_RUN_REGISTRY.csv"
    members.append(_member(stage, registry_path, "run_registry"))
    attempts_path = stage / "06_RUN_REGISTRY/CLEAN2_RUN_ATTEMPTS.csv"
    members.append(_member(stage, attempts_path, "run_attempt_ledger"))
    registry_rows = read_run_registry(registry_path)

    runs_root = stage / "07_FORMAL_RUNS"
    if runs_root.is_symlink() or not runs_root.is_dir():
        raise Clean2EvidenceError("CLEAN2 formal-run evidence directory is missing/symlink")
    run_manifests: list[Path] = []
    for row in registry_rows:
        path = runs_root / str(row["run_id"]) / FORMAL_MANIFEST_NAME
        if not path.is_file():
            raise Clean2EvidenceError(f"CLEAN2 export lacks formal wrapper: {row['run_id']}")
        run_manifests.append(path)
    if len(run_manifests) != 110:
        raise Clean2EvidenceError("CLEAN2 export requires exactly 110 formal wrappers")
    members.extend(_member(stage, path, "formal_run_manifest") for path in run_manifests)

    seal = stage / "08_OUTPUT_SEAL/CLEAN2_COMPLETE_OUTPUT_SEAL.json"
    members.append(_member(stage, seal, "output_seal"))
    for optional in (
        "CLEAN2_OUTPUT_HASHES.csv",
        "CLEAN2_FORMAL_OUTPUT_HASHES.csv",
        "CLEAN2_COMPLETE_OUTPUT_SEAL.sha256",
    ):
        path = stage / "08_OUTPUT_SEAL" / optional
        if path.is_file():
            members.append(_member(stage, path, "output_hash_index"))

    sentinel_codes = {"C01", "C04", "C07", "C10", "C11", "C15"}
    sentinel_rows = [
        row
        for row in registry_rows
        if str(row["case_id"]).split("_", 1)[0] in sentinel_codes
        and row["structural_method"] == "LegSA_Paper_V1"
        and not row["ablation_id"]
    ]
    if len(sentinel_rows) != 6:
        raise Clean2EvidenceError("CLEAN2 sentinel full-LegSA registry rows are incomplete")
    for row in sentinel_rows:
        path = stage / "09_OFFLINE_EVALUATION" / str(row["run_id"]) / "error_series.csv.gz"
        members.append(_member(stage, path, "sentinel_full_legsa_error_series"))

    for name in AGGREGATE_EXPORT_NAMES:
        members.append(
            _find_one_direct(stage, ("10_ABLATION_ANALYSIS", "11_CLASSIC18_ANALYSIS"), name, "aggregate")
        )

    figures = stage / "12_DIAGNOSTIC_FIGURES"
    for name in FIGURE_NAMES:
        for suffix in (".png", ".pdf"):
            members.append(_member(stage, figures / f"{name}{suffix}", "diagnostic_figure"))
    for name in ("CLEAN2_FIGURE_MANIFEST.csv", "CLEAN2_FIGURE_RENDER_QA.json"):
        members.append(_member(stage, figures / name, "diagnostic_figure_audit"))

    explicit_audit_names = {
        Path(TERMINAL_ARTIFACT_RELATIVE_PATHS[role]).name
        for role in EXPLICIT_AUDIT_EXPORT_ROLES
    }
    audits = [
        path
        for path in _direct_files(stage / "13_AUDITS")
        if path.name.startswith("CLEAN2_")
        and path.suffix.casefold() in TEXT_EXPORT_SUFFIXES
        and ("AUDIT" in path.name or "REVIEW" in path.name)
        and path.name not in explicit_audit_names
    ]
    if not any("REVIEW" in path.name for path in audits):
        raise Clean2EvidenceError("CLEAN2 final audit/reviewer evidence is incomplete")
    members.extend(_member(stage, path, "audit_or_review") for path in audits)
    members.extend(_required_terminal_audit_export_members(stage))
    for name in (
        "CLEAN2_FULL_REPORT.md",
        "CLEAN2_FULL_REPORT.json",
        "CLEAN2_TERMINAL_GATE.json",
    ):
        members.append(_member(stage, stage / "14_FINAL_EVIDENCE" / name, "final_report"))
    return validate_export_members(members)


def validate_export_members(
    members: Sequence[EvidenceMember], *, max_uncompressed_bytes: int = DEFAULT_MAX_EXPORT_BYTES
) -> list[EvidenceMember]:
    """Reject payload/path/privacy leaks in an already explicit member set."""

    if not members:
        raise Clean2EvidenceError("CLEAN2 final export member set is empty")
    if max_uncompressed_bytes <= 0:
        raise Clean2EvidenceError("CLEAN2 final export size limit is invalid")
    archive_paths: set[str] = set()
    normalized: list[EvidenceMember] = []
    total = 0
    for member in members:
        archive = _safe_relative(member.archive_path, label="archive_path").as_posix()
        if archive in archive_paths:
            raise Clean2EvidenceError("CLEAN2 final export has a duplicate archive path")
        archive_paths.add(archive)
        source = Path(member.source)
        if source.is_symlink() or not source.is_file():
            raise Clean2EvidenceError("CLEAN2 final export source is missing or a symlink")
        lowered_parts = {part.casefold() for part in PurePosixPath(archive).parts}
        lowered_name = PurePosixPath(archive).name.casefold()
        suffix = source.suffix.casefold()
        if lowered_parts.intersection({"raw", "build", "legacy", "failed_attempts"}):
            raise Clean2EvidenceError("CLEAN2 final export includes a forbidden tree")
        if suffix in FORBIDDEN_EXPORT_SUFFIXES or re.search(r"(?:^|_)std(?:\.|_|$)", lowered_name):
            raise Clean2EvidenceError("CLEAN2 final export includes NAV/STD/build/executable/raw payload")
        if lowered_name in {"run_manifest.json", "solver_run_manifest.json"}:
            raise Clean2EvidenceError("CLEAN2 final export includes a non-wrapper solver manifest")
        if "case_gnss_input" in lowered_name or "case_dual_yaw_provider" in lowered_name:
            raise Clean2EvidenceError("CLEAN2 final export includes a case-provider payload")
        if suffix == ".gz" and PurePosixPath(archive).name != "error_series.csv.gz":
            raise Clean2EvidenceError("CLEAN2 final export includes an unapproved compressed payload")
        if suffix in TEXT_EXPORT_SUFFIXES:
            try:
                text = source.read_text(encoding="utf-8")
                assert_export_text_is_redacted(text)
            except Exception as exc:
                raise Clean2EvidenceError(f"CLEAN2 export text failed privacy scan: {archive}") from exc
        total += source.stat().st_size
        if total > max_uncompressed_bytes:
            raise Clean2EvidenceError("CLEAN2 final export exceeds the 512 MiB preflight limit")
        normalized.append(EvidenceMember(source.resolve(strict=True), archive, member.category))
    return sorted(normalized, key=lambda member: member.archive_path)


def _evidence_manifest_bytes(members: Sequence[EvidenceMember]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=["archive_path", "category", "sha256", "size_bytes"],
        lineterminator="\n",
    )
    writer.writeheader()
    for member in members:
        writer.writerow(
            {
                "archive_path": member.archive_path,
                "category": member.category,
                "sha256": sha256_file(member.source),
                "size_bytes": member.source.stat().st_size,
            }
        )
    return output.getvalue().encode("utf-8")


def write_evidence_manifest(
    *, members: Sequence[EvidenceMember], output_path: str | Path
) -> Path:
    """Write only an explicit member manifest; directory recursion is unsupported."""

    validated = validate_export_members(members)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(_evidence_manifest_bytes(validated))
    return destination


def build_clean2_final_zip(
    *,
    stage_root: str | Path,
    export_root: str | Path,
    terminal_gate_path: str | Path | None = None,
    timestamp: str | None = None,
    max_size_bytes: int = DEFAULT_MAX_EXPORT_BYTES,
) -> dict[str, Any]:
    """Create exactly one final archive after all allowlist/privacy/size gates pass."""

    export_raw = Path(export_root)
    if export_raw.is_symlink():
        raise Clean2EvidenceError("CLEAN2 export root is a symlink")
    export = export_raw.resolve(strict=True)
    if not export.is_dir():
        raise Clean2EvidenceError("CLEAN2 export root is not a directory")
    existing = [
        path
        for path in export.iterdir()
        if path.name.startswith(FINAL_ZIP_PREFIX) and path.name.endswith(".zip")
    ]
    if existing:
        raise Clean2EvidenceError("A CLEAN2 final ZIP already exists; second ZIP is forbidden")
    if terminal_gate_path is None:
        raise Clean2EvidenceError("CLEAN2 final ZIP requires the terminal PASS gate")
    validate_clean2_terminal_gate(terminal_gate_path, stage_root=stage_root)
    if timestamp is None:
        now = datetime.now().astimezone()
        sign = "P" if now.utcoffset() is not None and now.utcoffset().total_seconds() >= 0 else "M"
        offset = now.strftime("%z").lstrip("+-") or "0000"
        timestamp = now.strftime("%Y%m%dT%H%M%S") + sign + offset
    if re.fullmatch(r"[0-9]{8}T[0-9]{6}[PM][0-9]{4}", timestamp) is None:
        raise Clean2EvidenceError("CLEAN2 final ZIP timestamp is invalid")
    selected = validate_export_members(
        select_clean2_export_members(stage_root),
        max_uncompressed_bytes=max_size_bytes,
    )
    manifest_bytes = _evidence_manifest_bytes(selected)
    total_uncompressed = sum(member.source.stat().st_size for member in selected) + len(manifest_bytes)
    if total_uncompressed > max_size_bytes:
        raise Clean2EvidenceError("CLEAN2 final export exceeds the uncompressed size limit")
    archive_name = f"{FINAL_ZIP_PREFIX}{timestamp}.zip"
    archive_path = export / archive_name
    fd, temp_name = tempfile.mkstemp(prefix=f".{archive_name}.", suffix=".partial", dir=export)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as handle:
            for member in selected:
                handle.write(member.source, member.archive_path)
            handle.writestr("EVIDENCE_MANIFEST.csv", manifest_bytes)
        if temp_path.stat().st_size > max_size_bytes:
            raise Clean2EvidenceError("CLEAN2 final ZIP exceeds the compressed size limit")
        with zipfile.ZipFile(temp_path, "r") as handle:
            if handle.testzip() is not None:
                raise Clean2EvidenceError("CLEAN2 final ZIP integrity test failed")
            names = handle.namelist()
            if len(names) != len(set(names)) or set(names) != {
                *(member.archive_path for member in selected),
                "EVIDENCE_MANIFEST.csv",
            }:
                raise Clean2EvidenceError("CLEAN2 final ZIP member set differs from its allowlist")
            if sum(info.file_size for info in handle.infolist()) > max_size_bytes:
                raise Clean2EvidenceError("CLEAN2 final ZIP exceeds the uncompressed size limit")
            if handle.read("EVIDENCE_MANIFEST.csv") != manifest_bytes:
                raise Clean2EvidenceError("CLEAN2 embedded evidence manifest differs")
            expected_hashes = {
                row["archive_path"]: row["sha256"]
                for row in csv.DictReader(io.StringIO(manifest_bytes.decode("utf-8")))
            }
            for name, expected_hash in expected_hashes.items():
                digest = hashlib.sha256()
                with handle.open(name, "r") as member_handle:
                    while True:
                        chunk = member_handle.read(4 * 1024 * 1024)
                        if not chunk:
                            break
                        digest.update(chunk)
                if digest.hexdigest() != expected_hash:
                    raise Clean2EvidenceError("CLEAN2 ZIP member differs from evidence manifest")
        if archive_path.exists() or archive_path.is_symlink():
            raise Clean2EvidenceError("CLEAN2 final ZIP destination appeared during build")
        os.replace(temp_path, archive_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return {
        "schema_version": "paper_rebuild.clean2_final_export.v1",
        "archive_name": archive_name,
        "archive_sha256": sha256_file(archive_path),
        "archive_size_bytes": archive_path.stat().st_size,
        "uncompressed_member_bytes": total_uncompressed,
        "evidence_member_count": len(selected) + 1,
        "evidence_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "single_final_zip": True,
        "raw_payload_count": 0,
        "full_NAV_STD_payload_count": 0,
        "build_or_executable_count": 0,
        "legacy_payload_count": 0,
        "failed_attempt_payload_count": 0,
        "passed": True,
    }
