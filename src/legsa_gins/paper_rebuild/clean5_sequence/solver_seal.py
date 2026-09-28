"""C-04 immutable file inventory and Canonical-compatible terminal registries."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..manifest import sha256_file
from .runtime_config import METHODS
from .solver_validation import REQUIRED_NATIVE_OUTPUTS

# Exact first-line schema of the authorized Canonical 11_OUTPUT_SEAL registries.
UNIQUE_FIELDS = tuple("run_id,run_order,execution_key,canonical_logical_id,logical_alias_count,case_id,method_id,matrix,effective_profile,case_family,degradation_type_id,seed_index,method_bound_provider_hash,runtime_config_hash,executable_hash,formal,output_root,repo_root,runtime_config_template_path,runtime_config_template_hash,runtime_config_file_hash,runtime_config_path,actual_rendered_runtime_config_sha256,method_bound_manifest_path,method_bound_manifest_hash,scientific_code_freeze_commit,preparation_code_commit,terminal_status,position_update,dual_yaw,scheme_c,receiver_velocity,raw_doppler,source_aware,go2_rp,go2_hv".split(","))
LOGICAL_FIELDS = tuple("logical_id,matrix,method_id,method_name,effective_profile,case_id,case_index,provider_ready,formal,execution_alias,alias_of,trace_used_online,per_case_tuning,metric_driven_rerun,case_family,degradation_type_id,degradation_type_name,seed_index,seed_value,seed_effective,independent_realization,anchor_name,anchor_time_s,degradation_parameters_json,position_update,dual_yaw,scheme_c,receiver_velocity,raw_doppler,source_aware,go2_rp,go2_hv,logical_order,run_id,execution_key,method_bound_provider_hash,runtime_config_hash,executable_hash,output_root,method_bound_manifest_hash,terminal_status".split(","))
EXTRA_FIELDS = ("dataset_id", "data_mode", "synthetic_data_used", "semisynthetic_data_used",
                "frozen_parameter_hash", "code_freeze_commit", "execution_worktree",
                "exit_code", "runtime_seconds", "nav_rows", "nav_time_start", "nav_time_end",
                "degradation_parameters_json", "counters_json", "formal_manifest_path",
                "formal_manifest_sha256", "effective_starttime", "t_init", "skipped_epochs_json")
TERMINAL_STATUSES = {"COMPLETED", "technical_failure", "algorithm_failure", "counter_mismatch"}
AUDIT_FIELDS = ("trace_open_count", "bag_open_count", "fpl_open_count", "raw_open_count",
                "raw_write_open_count", "write_open_count", "write_outside_run_count")


class SealValidationError(RuntimeError):
    terminal_status = "technical_failure"


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _regular_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise SealValidationError(f"missing or symlink sealed file: {path}")
    if any(parent.is_symlink() for parent in path.parents):
        raise SealValidationError(f"symlink ancestor in sealed path: {path}")


def _degradation(metadata: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    dataset = metadata["dataset_id"]
    if dataset == "BY2H":
        return {}, {}
    if dataset != "BY2O":
        raise SealValidationError("seal requires BY2H or BY2O")
    path = Path(metadata["occlusion_window_path"])
    _regular_file(path)
    digest = sha256_file(path)
    expected = metadata["occlusion_window_sha256"]
    if digest != expected:
        raise SealValidationError("OCCLUSION_WINDOW.json SHA256 mismatch")
    payload = json.loads(path.read_text(encoding="utf-8"))
    # C-02's registered main_window and secondary_runs are copied, never detected again.
    main = payload.get("main_window")
    secondary = payload.get("secondary_runs")
    if not isinstance(main, Mapping) or not isinstance(secondary, list):
        raise SealValidationError("preregistered occlusion metadata lacks window records")
    contract_window = metadata.get("contract", {}).get("occlusion_window", {})
    if contract_window:
        if contract_window.get("report_sha256") != expected or contract_window.get("main_window") != main or contract_window.get("secondary_runs") != secondary:
            raise SealValidationError("preregistered occlusion JSON differs from frozen contract")
    params = {"start_s": main["t0"], "end_s": main["t1"],
              "source": "pre_registered_input_side_gnss2_fix_type",
              "secondary_runs": [[row["t0"], row["t1"]] for row in secondary]}
    _json(params)
    return params, {"path": str(path), "sha256": digest}


def _flags(profile: str) -> dict[str, bool]:
    from .profile_expectations import profile_flags
    return profile_flags(profile)


def _registries(records: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any],
                degradation: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    dataset, mode = metadata["dataset_id"], metadata["data_mode"]
    provider_hashes = metadata.get("provider_hashes", {})
    if not isinstance(provider_hashes, Mapping) or not provider_hashes:
        raise SealValidationError("seal lacks provider hash references")
    bundle_hash = hashlib.sha256(_json(provider_hashes).encode()).hexdigest()
    unique, logical = [], []
    for order, record in enumerate(records, 1):
        method, profile = record["method_id"], record["effective_profile"]
        run_dir = Path(record["run_dir"])
        aliases = [method] + ({"F03": ["A02"], "F04": ["A01"]}.get(method, []))
        common = {"case_id": f"CLEAN5_{dataset}_NATURAL", "case_family": "natural_sequence",
            "dataset_id": dataset, "data_mode": mode, "synthetic_data_used": False,
            "semisynthetic_data_used": False, "run_id": record["run_id"],
            "effective_profile": profile, "execution_key": record["run_id"],
            "method_bound_provider_hash": bundle_hash,
            "runtime_config_hash": record["scientific_runtime_config_hash"],
            "executable_hash": metadata["executable_sha256"],
            "formal": True, "output_root": str(run_dir),
            "terminal_status": record["terminal_status"],
            "frozen_parameter_hash": record["frozen_parameter_hash"],
            "code_freeze_commit": metadata["code_freeze_commit"],
            "execution_worktree": metadata["execution_worktree"],
            "degradation_parameters_json": _json(degradation), "counters_json": _json(record.get("counters", {})),
            "effective_starttime": record.get("effective_starttime"), "t_init": record.get("t_init"),
            "skipped_epochs_json": _json(record.get("skipped_epochs", [])),
            **{key: record.get(key, "") for key in ("exit_code", "runtime_seconds", "nav_rows", "nav_time_start", "nav_time_end")},
            **_flags(profile)}
        wrapper = run_dir / "CLEAN5_FORMAL_RUN_MANIFEST.json"
        common["formal_manifest_path"] = str(wrapper)
        common["formal_manifest_sha256"] = sha256_file(wrapper) if wrapper.is_file() else ""
        common["method_bound_manifest_hash"] = metadata.get("provider_manifest_sha256", "")
        row = {**common, "run_order": order, "canonical_logical_id": f"CLEAN5_{dataset}_NATURAL_{method}",
            "logical_alias_count": len(aliases), "method_id": method,
            "matrix": "internal_ablation" if method.startswith("A") else "full_algorithm",
            "repo_root": metadata["execution_worktree"],
            "runtime_config_template_path": record.get("rendered_config_path", ""),
            "runtime_config_template_hash": record.get("rendered_config_sha256", ""),
            "runtime_config_file_hash": record["config_hash"],
            "runtime_config_path": str(run_dir / "CLEAN5_RUNTIME_CONFIG.yaml"),
            "actual_rendered_runtime_config_sha256": record["config_hash"],
            "method_bound_manifest_path": metadata.get("provider_manifest_path", ""),
            "scientific_code_freeze_commit": metadata.get("scientific_code_freeze_commit", ""),
            "preparation_code_commit": metadata["code_freeze_commit"]}
        unique.append(row)
        for alias in aliases:
            logical.append({**common, "logical_id": f"CLEAN5_{dataset}_NATURAL_{alias}",
                "matrix": "internal_ablation" if alias.startswith("A") else "full_algorithm",
                "method_id": alias, "method_name": profile, "provider_ready": True,
                "execution_alias": alias != method, "alias_of": method if alias != method else "",
                "trace_used_online": False, "per_case_tuning": False, "metric_driven_rerun": False,
                "independent_realization": False, "logical_order": len(logical) + 1})
    return unique, logical


def _write_csv(path: Path, prefix: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    fields = tuple(prefix) + tuple(key for key in EXTRA_FIELDS if key not in prefix)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def seal_outputs(stage_root: str | Path, run_records: Sequence[Mapping[str, Any]],
                 metadata: Mapping[str, Any], audit_summaries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    stage, records = Path(stage_root).resolve(strict=True), list(run_records)
    runs_subdir = metadata.get("runs_subdir", "04_SOLVER_RUNS")
    seal_subdir = metadata.get("seal_subdir", "05_OUTPUT_SEAL")
    if (runs_subdir, seal_subdir) not in (("04_SOLVER_RUNS", "05_OUTPUT_SEAL"), ("04_SOLVER_RUNS_V2", "05_OUTPUT_SEAL_V2")):
        raise SealValidationError("unregistered run/seal namespace")
    if len(records) != 5 or [row.get("method_id") for row in records] != list(METHODS):
        raise SealValidationError("seal requires the five ordered unique run terminal records")
    if len({row["run_id"] for row in records}) != 5:
        raise SealValidationError("duplicate run identity at seal")
    dataset = metadata["dataset_id"]
    if metadata["data_mode"] != f"real_{dataset.lower()}_raw":
        raise SealValidationError("seal dataset/data_mode mismatch")
    degradation, window_reference = _degradation(metadata)
    audits = list(audit_summaries)
    if len(audits) != 5 or {item.get("run_id") for item in audits} != {row["run_id"] for row in records}:
        raise SealValidationError("seal requires exactly one solver audit per run")
    totals = {key: 0 for key in AUDIT_FIELDS}
    for audit in audits:
        for key in AUDIT_FIELDS:
            value = audit.get(key)
            if value is None:
                totals[key] = None
            elif type(value) is not int or value < 0:
                raise SealValidationError(f"solver audit has invalid count: {key}")
            elif totals[key] is not None:
                totals[key] += value
    files = []
    for record in records:
        if record["terminal_status"] not in TERMINAL_STATUSES or METHODS[record["method_id"]] != record["effective_profile"]:
            raise SealValidationError("run terminal/profile identity mismatch")
        run_dir = Path(record["run_dir"])
        if run_dir.is_symlink() or run_dir.resolve(strict=True) != stage / runs_subdir / record["run_id"]:
            raise SealValidationError("run directory escaped its sequence stage")
        if record["terminal_status"] == "COMPLETED":
            for name in (*REQUIRED_NATIVE_OUTPUTS, "CLEAN5_RUNTIME_CONFIG.yaml", "CLEAN5_FORMAL_RUN_MANIFEST.json"):
                _regular_file(run_dir / name)
        for path in sorted(run_dir.rglob("*")):
            if path.is_symlink():
                raise SealValidationError(f"symlink output cannot be sealed: {path}")
            if path.is_dir():
                continue
            _regular_file(path)
            files.append({"run_id": record["run_id"], "relative_path": path.relative_to(stage).as_posix(),
                          "size_bytes": path.stat().st_size, "sha256": sha256_file(path),
                          "terminal_status": record["terminal_status"]})
    if not files:
        raise SealValidationError("no output files available to seal")
    root = stage / seal_subdir
    root.mkdir(exist_ok=False)
    unique, logical = _registries(records, metadata, degradation)
    unique_path, logical_path = root / "UNIQUE_RUN_TERMINAL_REGISTRY.csv", root / "LOGICAL_RESULT_TERMINAL_REGISTRY.csv"
    _write_csv(unique_path, UNIQUE_FIELDS, unique)
    _write_csv(logical_path, LOGICAL_FIELDS, logical)
    payload = {"schema_version": "paper_rebuild.clean5.output_seal.v1", "stage_root": str(stage),
        "runs_subdir": runs_subdir, "seal_subdir": seal_subdir, "contract_version": metadata.get("contract_version", 1),
        "dataset_id": dataset, "data_mode": metadata["data_mode"], "synthetic_data_used": False,
        "semisynthetic_data_used": False, "sealed_at": datetime.now(timezone.utc).isoformat(),
        "unique_run_count": 5, "logical_result_count": 7, "file_count": len(files), "files": files,
        "run_terminals": {row["run_id"]: row["terminal_status"] for row in records},
        "trace_reads_before_seal": totals["trace_open_count"], "raw_write_open_count": totals["raw_write_open_count"],
        "solver_strace_totals": totals, "audits_passed": all(value == 0 for key, value in totals.items() if key != "write_open_count"),
        "code_freeze_commit": metadata["code_freeze_commit"], "execution_worktree": metadata["execution_worktree"],
        "executable_sha256": metadata["executable_sha256"], "occlusion_window_reference": window_reference,
        "provider_hashes": metadata["provider_hashes"],
        "registry_field_mapping": {
            "runtime_config_hash": "scientific_runtime_config_hash; file SHA256 is runtime_config_file_hash",
            "method_bound_provider_hash": "SHA256 of UTF8 sorted compact JSON of provider_hashes mapping, ensure_ascii=false",
            "method_bound_manifest_path_and_hash": "C-03 PROVIDER_MANIFEST.json, no method-specific regenerated provider",
            "execution_key": "CLEAN5 unique run_id", "absent_canonical_fields": "blank; no inherited case/seed/degradation identity",
            "module_flags": "frozen profile switches; actual updates are counters_json",
            "logical_aliases": "A02 uses F03 run; A01 uses F04 run"},
        "registries": [{"relative_path": str(path.relative_to(stage)), "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
                       for path in (unique_path, logical_path)]}
    seal_path = root / "OUTPUT_SEAL.json"
    with seal_path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
    validation = validate_output_seal(seal_path)
    return {"output_seal_path": str(seal_path), "output_seal_sha256": sha256_file(seal_path),
            "unique_registry_path": str(unique_path), "logical_registry_path": str(logical_path),
            "solver_strace_totals": totals, "validation": validation}


def validate_output_seal(path: str | Path) -> dict[str, Any]:
    seal_path = Path(path)
    _regular_file(seal_path)
    payload = json.loads(seal_path.read_text(encoding="utf-8"))
    stage = Path(payload["stage_root"]).resolve(strict=True)
    runs_subdir = payload.get("runs_subdir", "04_SOLVER_RUNS")
    if runs_subdir not in ("04_SOLVER_RUNS", "04_SOLVER_RUNS_V2"):
        raise SealValidationError("unregistered sealed run namespace")
    seen = set()
    for entry in [*payload["files"], *payload["registries"]]:
        relative = Path(entry["relative_path"])
        if relative.is_absolute() or ".." in relative.parts or relative.as_posix() in seen:
            raise SealValidationError("invalid or duplicate sealed relative path")
        seen.add(relative.as_posix())
        actual = stage / relative
        _regular_file(actual)
        if actual.stat().st_size != entry["size_bytes"] or sha256_file(actual) != entry["sha256"]:
            raise SealValidationError(f"sealed output changed: {relative}")
    if len(payload["files"]) != payload["file_count"]:
        raise SealValidationError("sealed file count mismatch")
    for run_id, status in payload["run_terminals"].items():
        if status == "COMPLETED":
            for name in (*REQUIRED_NATIVE_OUTPUTS, "CLEAN5_RUNTIME_CONFIG.yaml", "CLEAN5_FORMAL_RUN_MANIFEST.json"):
                if f"{runs_subdir}/{run_id}/{name}" not in seen:
                    raise SealValidationError("COMPLETED run lacks required file in seal")
    return {"passed": True, "file_count": payload["file_count"], "output_seal_sha256": sha256_file(seal_path)}
