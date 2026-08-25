"""Gate-ordered G0--G4 exact-route transaction.

Nothing in this module reads trace/reference or another method's output.  The
only conditional navigation launch is the single official BY2 C00 after the
sample, both adapters, config/time contract, and TDCP activation all pass.
"""

from __future__ import annotations

import bisect
import copy
import csv
import dataclasses
import datetime as dt
import decimal
import json
import os
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from legsa_gins.paper_rebuild.manifest import (
    ManifestContractError,
    read_hash_lock,
    verify_raw_sources,
)
from legsa_gins.paper_rebuild.paths import PathContractError, load_yaml_mapping

from .config_contract import (
    ConfigContractError,
    derive_by2_config,
    derive_official_sample_config,
)
from .constants import (
    CANDIDATE_ID,
    CLASSIFICATION_LABELS,
    GO2_SAMPLE_RATE_HZ,
    OFFICIAL_CONFIG_RELATIVE,
    OFFICIAL_REFERENCE_MEMBER_BASENAME,
    OFFICIAL_SAMPLE_RELATIVE,
    POOR_APPLICABILITY_STATUS,
    RAW_HASH_LOCK_SHA256,
    STAGE_NAME,
    STAGE_RELATIVE_LAYOUT,
    SUCCESS_STATUS,
    TERMINAL_STATUSES,
)
from .imu_adapter import ImuAdapterError, adapt_go2_imu
from .matlab import (
    MatlabRuntimeError,
    build_matlab_batch_command,
    discover_matlab_candidates,
    render_environment_probe,
    render_official_run_script,
    render_tdcp_probe_script,
    parse_environment_probe,
    run_matlab_script,
    validate_matlab_environment,
    wsl_to_windows_path,
    write_harness_files,
)
from .outputs import (
    OutputContractError,
    compare_sample_runs,
    freeze_native_solution,
    read_official_solution,
    summarize_solution,
)
from .publication import (
    PublicationError,
    assert_no_symlink_components,
    assert_outside_protected_roots,
    publish_compact_stage,
    validate_exact_destination,
)
from .rinex_adapter import (
    RinexAdapterError,
    convert_gnss1_raw_to_rinex,
    epoch_signal_rows,
)
from .source import (
    AccessLedger,
    CoreCleanlinessGuard,
    ForbiddenInputError,
    SourceIdentityError,
    materialize_runtime_source_mirror,
    sha256_file,
    verify_source_identity,
    write_json,
)
from .time_contract import (
    GpsTime,
    NANOSECONDS,
    WEEK_SECONDS,
    RinexEpoch,
    TimeContractError,
    extract_same_receiver_time_events,
    gpst_calendar_to_gps,
    gps_to_gpst_calendar,
    normalize_rinex_epochs,
    official_epoch_acceptance_audit,
    parse_rinex_epochs,
    prove_single_constant_normalization,
)


class TransactionError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class TransactionOptions:
    repository_root: Path
    paths_config: Path
    ginav_root: Path
    matlab_executable: Path
    scratch_root: Path
    destination_stage_root: Path
    paper_root: Path
    legacy_freeze_root: Path
    publish: bool = True
    sample_timeout_seconds: float = 3600.0
    probe_timeout_seconds: float = 1800.0
    c00_timeout_seconds: float = 3600.0


def _write_yaml(path: Path, payload: Mapping[str, Any]) -> Path:
    # JSON is a strict YAML-1.2 subset and avoids a runtime PyYAML dependency.
    return write_json(path, payload)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name) for name in fieldnames})
    return path


def _make_scratch_root(
    requested: Path, *, protected_roots: Sequence[Path]
) -> Path:
    root = requested.expanduser()
    try:
        assert_no_symlink_components(root.parent, allow_missing_leaf=False)
        assert_no_symlink_components(root, allow_missing_leaf=True)
        assert_outside_protected_roots(root, protected_roots)
    except PublicationError as exc:
        raise TransactionError(str(exc)) from exc
    if os.path.lexists(root):
        raise TransactionError(f"non-overwriting scratch root exists: {root}")
    root.mkdir(exist_ok=False)
    selected = root.resolve(strict=True)
    try:
        filesystem = subprocess.run(
            ["findmnt", "-n", "-o", "FSTYPE", "-T", str(selected)],
            check=True, capture_output=True, text=True, timeout=15,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise TransactionError(f"cannot verify scratch filesystem: {exc}") from exc
    if filesystem != "ext4":
        raise TransactionError(
            f"LC02 runtime scratch must be Linux-local ext4, got {filesystem!r}"
        )
    return selected


def _create_stage_layout(scratch_root: Path) -> Path:
    stage = scratch_root / STAGE_NAME
    stage.mkdir(parents=True, exist_ok=False)
    for relative in STAGE_RELATIVE_LAYOUT:
        (stage / relative).mkdir(exist_ok=False)
    return stage


def _stage_dir(stage: Path, name: str) -> Path:
    if name not in STAGE_RELATIVE_LAYOUT:
        raise TransactionError(f"unknown LC02 stage directory: {name}")
    return stage / name


def _write_cleanliness(stage: Path, runs: Sequence[Mapping[str, Any]]) -> Path:
    destination = (
        _stage_dir(stage, "00_SOURCE_AND_ENVIRONMENT")
        / "GINAV_CORE_CLEANLINESS_BEFORE_AFTER.json"
    )
    combined = [dict(item) for item in runs]
    known: dict[str, dict[str, Any]] = {}
    for item in combined:
        run_id = str(item.get("run_id") or "")
        if not run_id:
            raise TransactionError("source-cleanliness proof has no run_id")
        if run_id in known:
            raise TransactionError(f"duplicate source-cleanliness run_id: {run_id}")
        known[run_id] = item

    for proof_path in stage.rglob("GINAV_CORE_CLEANLINESS_BEFORE_AFTER.json"):
        if proof_path == destination:
            continue
        try:
            item = json.loads(proof_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise TransactionError(
                f"malformed source-cleanliness proof: {proof_path}: {exc}"
            ) from exc
        if not isinstance(item, Mapping):
            raise TransactionError(
                f"source-cleanliness proof is not an object: {proof_path}"
            )
        run_id = str(item.get("run_id") or "")
        if not run_id:
            raise TransactionError(
                f"source-cleanliness proof has no run_id: {proof_path}"
            )
        item_dict = dict(item)
        if run_id in known:
            if known[run_id] != item_dict:
                raise TransactionError(
                    f"conflicting source-cleanliness proof for run_id: {run_id}"
                )
            continue
        combined.append(item_dict)
        known[run_id] = item_dict

    # The caller's in-memory ledger must learn about proofs recovered from
    # failed candidate/run directories so terminal provenance cannot omit them.
    if isinstance(runs, list):
        runs[:] = combined
    return write_json(
        destination,
        {
            "schema_version": "ginav2021.core_cleanliness_all_runs.v1",
            "runs": combined,
            "run_count": len(combined),
            "source_patch_count": 0,
            "pass": bool(combined) and all(item.get("pass") for item in combined),
        },
    )


def _git_head(repository_root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=30,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise TransactionError(f"cannot resolve LegSA code commit: {exc}") from exc


def _implementation_hashes(repository_root: Path) -> dict[str, str]:
    relatives = [
        Path("scripts/paper_rebuild/run_lc02_ginav2021.py"),
        Path(
            "configs/paper_rebuild/horizontal_literature/ginav2021/"
            "GINAV2021_RUNTIME_CONTRACT.yaml"
        ),
    ]
    package = (
        repository_root
        / "src/legsa_gins/paper_rebuild/horizontal_literature/ginav2021"
    )
    relatives.extend(
        path.relative_to(repository_root) for path in sorted(package.glob("*.py"))
    )
    return {
        relative.as_posix(): sha256_file(repository_root / relative)
        for relative in relatives
    }


def _initial_provenance(options: TransactionOptions) -> dict[str, Any]:
    implementation_hashes = _implementation_hashes(options.repository_root)
    return {
        "schema_version": "ginav2021.consolidated_provenance.v1",
        "data_mode": "source_environment_only",
        "dataset_role": "PRE_BY2_SOURCE_AND_ENVIRONMENT_GATE",
        "raw_source_hashes": {},
        "provider_hashes": {},
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
        "code_commit": _git_head(options.repository_root),
        "implementation_file_sha256": implementation_hashes,
        "runtime_contract_hash": implementation_hashes[
            "configs/paper_rebuild/horizontal_literature/ginav2021/"
            "GINAV2021_RUNTIME_CONTRACT.yaml"
        ],
        "config_hash": None,
        "official_source_identity": None,
        "matlab_environment": None,
        "converter_identity": None,
        "gate_execution_counts": {
            "G0_matlab_candidate_attempts": 0,
            "G1_official_sample_runs": 0,
            "G2_gnss_adapter_runs": 0,
            "G2_imu_adapter_runs": 0,
            "G3_tdcp_probe_runs": 0,
            "G4_BY2_C00_runs": 0,
        },
        "source_cleanliness_run_ids": [],
        "representative_cases_executed": False,
        "comparison_executed": False,
        "trace_evaluation_executed": False,
    }


def _write_consolidated_provenance(
    stage: Path,
    *,
    status: str,
    provenance: Mapping[str, Any],
    access_audit: Mapping[str, Any],
    cleanliness_runs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    run_ids = [
        str(item.get("run_id")) for item in cleanliness_runs
        if item.get("run_id")
    ]
    gate_counts = copy.deepcopy(dict(provenance["gate_execution_counts"]))
    gate_counts.update({
        "G0_matlab_candidate_attempts": sum(
            run_id.startswith("G0_MATLAB_ENVIRONMENT_candidate_")
            for run_id in run_ids
        ),
        "G1_official_sample_runs": sum(
            run_id.startswith("G1_OFFICIAL_SAMPLE_RUN_") for run_id in run_ids
        ),
        "G3_tdcp_probe_runs": sum(
            run_id == "G3_TDCP_ACTIVATION_PROBE" for run_id in run_ids
        ),
        "G4_BY2_C00_runs": sum(
            run_id == "G4_BY2_C00_SINGLE_RECURSIVE_RUN" for run_id in run_ids
        ),
    })
    payload = {
        **copy.deepcopy(dict(provenance)),
        "gate_execution_counts": gate_counts,
        "terminal_status": status,
        "file_access_audit": dict(access_audit),
        "source_cleanliness_run_ids": run_ids,
        "source_cleanliness_run_count": len(cleanliness_runs),
        "pass": bool(access_audit.get("pass")),
    }
    write_json(
        _stage_dir(stage, "11_REPORT") / "GINAV_CONSOLIDATED_PROVENANCE.json",
        payload,
    )
    return payload


def _terminal_payload(
    status: str,
    *,
    stage: Path,
    provenance: Mapping[str, Any],
    access_audit: Mapping[str, Any] | None = None,
    detail: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in TERMINAL_STATUSES:
        raise TransactionError(f"unregistered LC02 terminal status: {status}")
    formal_admission = bool(
        (extra or {}).get("formal_lc02_admission", status == SUCCESS_STATUS)
    )
    payload: dict[str, Any] = {
        "schema_version": "ginav2021.transaction_terminal.v1",
        "candidate_id": CANDIDATE_ID,
        "classification_labels": list(CLASSIFICATION_LABELS),
        "terminal_status": status,
        "scientific_terminal_status": status,
        "scratch_stage_root": str(stage),
        "formal_lc02_slot": "FILLED" if formal_admission else "VACANT",
        "formal_lc02_admission": formal_admission,
        "transaction_complete": False,
        "representative_cases_executed": False,
        "comparison_executed": False,
        "trace_evaluation_executed": False,
        "file_access_audit_available": access_audit is not None,
        "file_access_audit": dict(access_audit) if access_audit is not None else None,
        "trace_open_count": (
            int(access_audit.get("trace_open_count", 0))
            if access_audit is not None else None
        ),
        "reference_open_count": (
            int(access_audit.get("reference_open_count", 0))
            if access_audit is not None else None
        ),
        "gnss2_open_count": (
            int(access_audit.get("gnss2_open_count", 0))
            if access_audit is not None else None
        ),
        "other_method_open_count": (
            int(access_audit.get("other_method_open_count", 0))
            if access_audit is not None else None
        ),
        "forbidden_open_count": (
            int(access_audit.get("forbidden_open_count", 0))
            if access_audit is not None else None
        ),
        "unauthorized_runtime_read_count": (
            int(access_audit.get("unauthorized_runtime_read_count", 0))
            if access_audit is not None else None
        ),
        "LC01_execution_count": 0,
        "other_method_execution_count": 0,
        "canonical541_execution_count": 0,
        "data_mode": provenance["data_mode"],
        "dataset_role": provenance["dataset_role"],
        "raw_source_hashes": copy.deepcopy(provenance["raw_source_hashes"]),
        "provider_hashes": copy.deepcopy(provenance["provider_hashes"]),
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
        "code_commit": provenance["code_commit"],
        "config_hash": provenance.get("config_hash"),
        "consolidated_provenance_path": (
            "11_REPORT/GINAV_CONSOLIDATED_PROVENANCE.json"
        ),
    }
    if detail:
        payload["detail"] = detail
    if extra:
        payload.update(extra)
    write_json(_stage_dir(stage, "11_REPORT") / "LC02_GINAV2021_TRANSACTION_STATUS.json", payload)
    return payload


def _expected_publication_destination(clean_root: Path) -> Path:
    return (
        clean_root / "stages" / "CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON"
        / STAGE_NAME
    )


def _finalize_terminal(
    status: str,
    *,
    stage: Path,
    access_audit: Mapping[str, Any],
    provenance: Mapping[str, Any],
    cleanliness_runs: Sequence[Mapping[str, Any]],
    publish: bool,
    destination: Path,
    clean_root: Path,
    protected_roots: Sequence[Path],
    path_aliases: Mapping[Path, str],
    detail: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Freeze and, when requested, publish every scientific terminal path."""

    report_dir = _stage_dir(stage, "11_REPORT")
    write_json(report_dir / "GINAV_FORBIDDEN_INPUT_AUDIT.json", access_audit)
    consolidated = _write_consolidated_provenance(
        stage, status=status, provenance=provenance,
        access_audit=access_audit, cleanliness_runs=cleanliness_runs,
    )
    payload_extra = {
        **dict(extra or {}),
        "artifact_publication_requested": publish,
        "publication_destination_stage_root": str(destination),
    }
    payload = _terminal_payload(
        status, stage=stage, provenance=consolidated,
        access_audit=access_audit, detail=detail,
        extra=payload_extra,
    )
    if not publish:
        payload["artifact_publication_complete"] = False
        payload["artifact_publication"] = "NOT_REQUESTED"
        payload["transaction_complete"] = True
        payload["publication"] = {
            "schema_version": "ginav2021.compact_publication.v2",
            "requested": False,
            "artifact_publication": "NOT_REQUESTED",
            "pass": True,
        }
    else:
        payload["artifact_publication_complete"] = False
        payload["artifact_publication"] = "PENDING"
        payload["publication"] = {
            "schema_version": "ginav2021.compact_publication.v2",
            "requested": True,
            "artifact_publication": "PENDING",
            "pass": False,
        }
        write_json(report_dir / "LC02_GINAV2021_TRANSACTION_STATUS.json", payload)
        try:
            publication = publish_compact_stage(
                stage, destination, terminal_status=status,
                final_status_payload=payload,
                expected_destination_stage_root=destination,
                clean_root=clean_root, protected_roots=protected_roots,
                path_aliases=path_aliases,
            )
        except (OSError, PublicationError) as exc:
            publication = dict(getattr(exc, "report", {}) or {})
            publication.update({
                "schema_version": "ginav2021.compact_publication.v2",
                "destination_stage_root": str(destination),
                "requested": True,
                "artifact_publication": "FAILED",
                "pass": False,
                "error": str(exc),
                "scientific_terminal_status_unchanged": True,
            })
        payload["publication"] = publication
        payload["artifact_publication_complete"] = bool(publication["pass"])
        payload["artifact_publication"] = (
            "COMPLETE" if publication["pass"] else "FAILED"
        )
        payload["transaction_complete"] = bool(publication["pass"])
        if not publication["pass"]:
            payload["scientific_formal_lc02_admission"] = payload[
                "formal_lc02_admission"
            ]
            payload["formal_lc02_admission"] = False
            payload["formal_lc02_slot"] = "VACANT"
    consolidated["artifact_publication"] = payload["artifact_publication"]
    consolidated["transaction_complete"] = payload["transaction_complete"]
    write_json(report_dir / "GINAV_CONSOLIDATED_PROVENANCE.json", consolidated)
    write_json(report_dir / "GINAV_PUBLICATION_PARITY.json", payload["publication"])
    write_json(report_dir / "LC02_GINAV2021_TRANSACTION_STATUS.json", payload)
    return payload


def _load_local_paths(
    options: TransactionOptions, *, verify_raw_availability: bool
) -> dict[str, Path]:
    data = load_yaml_mapping(options.paths_config)
    values = data.get("paths")
    if not isinstance(values, Mapping):
        raise TransactionError("local paths config has no paths mapping")
    required = {
        "code_root", "raw_root", "by2_fix_root", "by2_go2_body", "clean_root",
        "horizontal_literature_rtklib_root", "horizontal_literature_convbin",
    }
    missing = required - set(values)
    if missing:
        raise TransactionError("local paths config is missing: " + ",".join(sorted(missing)))
    paths = {key: Path(str(values[key])).expanduser().resolve(strict=False) for key in required}
    if paths["code_root"].resolve(strict=True) != options.repository_root.resolve(strict=True):
        raise TransactionError("local code_root is not the authorized worktree")
    if verify_raw_availability and (
        not paths["raw_root"].is_dir() or not paths["by2_fix_root"].is_dir()
    ):
        raise TransactionError("locked BY2 raw roots are unavailable")
    return paths


def _parse_7z_slt_members(text: str) -> tuple[dict[str, Any], ...]:
    """Parse metadata-only ``7z l -slt`` output without opening members."""

    separator_seen = False
    current: dict[str, str] = {}
    records: list[dict[str, Any]] = []

    def finish() -> None:
        if not current:
            return
        raw_path = current.get("Path", "")
        normalized = raw_path.replace("\\", "/")
        pure = PurePosixPath(normalized)
        if (
            not raw_path or pure.is_absolute() or ".." in pure.parts
            or re.match(r"^[A-Za-z]:", normalized) or normalized.startswith("//")
        ):
            raise TransactionError(f"unsafe official archive member path: {raw_path!r}")
        attributes = current.get("Attributes", "")
        is_directory = "D" in attributes
        link_fields = {
            key: value for key, value in current.items()
            if "link" in key.casefold() or "reparse" in key.casefold()
        }
        if any(value not in {"", "-"} for value in link_fields.values()):
            raise TransactionError(f"official archive link member is forbidden: {raw_path}")
        if current.get("Encrypted", "-") not in {"", "-"}:
            raise TransactionError(f"official archive encrypted member is forbidden: {raw_path}")
        try:
            size = int(current.get("Size", "0") or 0)
        except ValueError as exc:
            raise TransactionError(f"invalid official archive member size: {raw_path}") from exc
        records.append(
            {
                "path": pure.as_posix(),
                "bytes": size,
                "attributes": attributes,
                "directory": is_directory,
                "encrypted": False,
                "link_or_reparse": False,
            }
        )
        current.clear()

    for raw in text.splitlines():
        line = raw.rstrip("\r\n")
        if line.strip() == "----------":
            separator_seen = True
            continue
        if not separator_seen:
            continue
        if not line.strip():
            finish()
            continue
        if " = " in line:
            key, value = line.split(" = ", 1)
            current[key] = value
    finish()
    if not separator_seen or not records:
        raise TransactionError("7z metadata listing has no archive members")
    folded = [str(item["path"]).casefold() for item in records]
    if len(folded) != len(set(folded)):
        raise TransactionError("official archive has case-fold duplicate member paths")
    return tuple(records)


def _classify_sample_archive_members(
    members: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    files = [item for item in members if not item.get("directory")]

    def paths(predicate: Any) -> list[str]:
        return sorted(str(item["path"]) for item in files if predicate(str(item["path"])))

    observations = paths(
        lambda value: Path(value).suffix.casefold().endswith("o")
        and "cpt" in Path(value).name.casefold()
        and "base" not in Path(value).name.casefold()
    )
    bds_navigation = paths(lambda value: Path(value).suffix.casefold().endswith("c"))
    mixed_navigation = paths(lambda value: Path(value).suffix.casefold().endswith("p"))
    navigation = bds_navigation if bds_navigation else mixed_navigation
    imu = paths(
        lambda value: Path(value).suffix.casefold() == ".csv"
        and "imu" in Path(value).name.casefold()
    )
    references = paths(
        lambda value: Path(value).name.casefold()
        == OFFICIAL_REFERENCE_MEMBER_BASENAME.casefold()
    )
    ubx = paths(lambda value: Path(value).suffix.casefold() == ".ubx")
    serialized_outputs = paths(
        lambda value: Path(value).suffix.casefold() in {".pos", ".sol", ".out"}
        or "result" in {part.casefold() for part in PurePosixPath(value).parts}
    )
    if len(observations) != 1 or len(navigation) != 1 or len(imu) != 1:
        raise TransactionError(
            "official sample archive source roles are ambiguous: "
            f"obs={len(observations)}, nav={len(navigation)}, imu={len(imu)}"
        )
    if len(references) != 1:
        raise TransactionError(
            "official sample archive reference-member inventory is not exactly one"
        )
    if serialized_outputs:
        raise TransactionError(
            "official sample archive unexpectedly bundles serialized solution output"
        )
    return {
        "schema_version": "ginav2021.official_sample_archive_inventory.v1",
        "member_count": len(members),
        "file_member_count": len(files),
        "members": [dict(item) for item in members],
        "selected_observation_member": observations[0],
        "selected_navigation_member": navigation[0],
        "selected_imu_member": imu[0],
        "reference_member_paths": references,
        "reference_member_count": len(references),
        "reference_member_opened": False,
        "ubx_member_paths": ubx,
        "ubx_member_count": len(ubx),
        "ubx_member_opened": False,
        "bundled_serialized_output_paths": serialized_outputs,
        "bundled_serialized_output_count": len(serialized_outputs),
        "bundled_serialized_output_present": False,
        "inventory_operation": "7z_list_slt_metadata_only",
        "pass": True,
    }


def _inventory_sample_archive(
    archive: Path, extractor: str, ledger: AccessLedger
) -> dict[str, Any]:
    ledger.record(archive, role="OFFICIAL_GINAV_SAMPLE_ARCHIVE")
    command = (extractor, "l", "-slt", str(archive))
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise TransactionError(
            "official sample metadata listing failed: "
            + (result.stderr or result.stdout).strip()
        )
    inventory = _classify_sample_archive_members(_parse_7z_slt_members(result.stdout))
    return {**inventory, "archive_sha256": sha256_file(archive), "command": list(command)}


def _extract_sample(
    archive: Path,
    destination: Path,
    ledger: AccessLedger,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    executable = shutil.which("7z") or shutil.which("7zz")
    if executable is None:
        raise TransactionError("7z extractor is unavailable for official sample")
    if destination.exists():
        raise TransactionError(f"sample extraction root already exists: {destination}")
    destination.mkdir(parents=True, exist_ok=False)
    selected_members = tuple(
        str(inventory[key]) for key in (
            "selected_observation_member", "selected_navigation_member",
            "selected_imu_member",
        )
    )
    command = (
        executable, "x", str(archive), f"-o{destination}", "-y", "-spd",
        *selected_members,
    )
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise TransactionError(f"official sample extraction failed: {result.stderr.strip()}")
    extracted = tuple(sorted(
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*") if path.is_file()
    ))
    if extracted != tuple(sorted(selected_members)):
        raise ForbiddenInputError(
            "official sample exact-member extraction conservation failed"
        )
    return {
        "extractor": executable,
        "command": list(command),
        "reference_member_excluded_without_open": True,
        "reference_member_open_count": 0,
        "ubx_members_excluded_without_open": True,
        "ubx_member_open_count": 0,
        "selected_members": list(selected_members),
        "extracted_members": list(extracted),
    }


def _resolve_sample_inputs(
    root: Path, inventory: Mapping[str, Any]
) -> dict[str, Path]:
    obs = root / str(inventory["selected_observation_member"])
    nav = root / str(inventory["selected_navigation_member"])
    imu = root / str(inventory["selected_imu_member"])
    if not all(path.is_file() for path in (obs, nav, imu)):
        raise TransactionError("official sample exact selected inputs are missing")
    if len({obs.parent, imu.parent, nav.parent}) != 1:
        raise TransactionError("official sample inputs do not share one data_dir")
    return {"observation": obs, "navigation": nav, "imu": imu,
            "data_dir": obs.parent}


def _run_official(
    *,
    run_id: str,
    run_root: Path,
    ginav_root: Path,
    matlab_executable: Path,
    config_path: Path,
    observation_path: Path,
    navigation_path: Path,
    imu_path: Path,
    timeout_seconds: float,
    access_ledger: AccessLedger,
) -> dict[str, Any]:
    windows = matlab_executable.suffix.casefold() == ".exe"
    for declared_input in (
        config_path, observation_path, navigation_path, imu_path
    ):
        access_ledger.authorize_runtime_read(Path(declared_input).resolve(strict=True))
        if windows:
            access_ledger.authorize_runtime_read(wsl_to_windows_path(declared_input))
    access_ledger.record(config_path, role="GINAV_DERIVED_CONFIGURATION")
    access_ledger.record(observation_path, role="GINAV_RINEX_OBSERVATION")
    access_ledger.record(navigation_path, role="GINAV_BROADCAST_NAVIGATION")
    access_ledger.record(imu_path, role="GINAV_BODY_IMU")
    mirror = run_root / "source_mirror"
    mirror_manifest = materialize_runtime_source_mirror(ginav_root, mirror)
    harness = run_root / "matlab_harness"
    fopen_log = run_root / "MATLAB_FOPEN_LEDGER.tsv"
    main = render_official_run_script(
        mirror_root=mirror, harness_root=harness, config_path=config_path,
        observation_path=observation_path, navigation_path=navigation_path,
        imu_path=imu_path, windows=windows,
    )
    script = write_harness_files(
        harness, main_script=main, fopen_log=fopen_log, windows=windows
    )
    guard = CoreCleanlinessGuard(run_id, ginav_root, mirror, mirror_manifest)
    try:
        with guard:
            result = run_matlab_script(
                matlab_executable, script, timeout_seconds=timeout_seconds
            )
    except (OSError, MatlabRuntimeError) as exc:
        # A process/runtime failure is still a completed cleanliness-guarded
        # official attempt. Preserve it as a normal failed run so callers can
        # emit the correct gate status and before/after proof.
        result = {
            "command": list(build_matlab_batch_command(matlab_executable, script)),
            "batch_invocation": "-nosplash -r function invocation",
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
            "runtime_seconds": None,
            "pass": False,
        }
    cleanliness = guard.report()
    write_json(run_root / "GINAV_CORE_CLEANLINESS_BEFORE_AFTER.json", cleanliness)
    if not fopen_log.is_file():
        raise ForbiddenInputError(f"{run_id} MATLAB fopen ledger is missing")
    access_ledger.import_matlab_fopen_log(fopen_log)
    outputs = tuple((mirror / "result").glob("*.pos"))
    native_path: Path | None = None
    if len(outputs) == 1:
        native_path = run_root / outputs[0].name
        shutil.copy2(outputs[0], native_path)
        if sha256_file(native_path) != sha256_file(outputs[0]):
            raise TransactionError(f"{run_id} native-output freeze parity failed")
    return {
        **result,
        "run_id": run_id,
        "source_mirror_manifest": mirror_manifest,
        "core_cleanliness": cleanliness,
        "native_output_path": str(native_path) if native_path else None,
        "native_output_count": len(outputs),
        "file_access_audit": access_ledger.audit(),
    }


def _matlab_environment(
    *,
    stage: Path,
    ginav_root: Path,
    executable: Path,
    probe_id: str = "selected",
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", probe_id):
        raise MatlabRuntimeError("unsafe MATLAB environment probe identifier")
    root = (
        _stage_dir(stage, "00_SOURCE_AND_ENVIRONMENT")
        / f"matlab_probe_runtime_{probe_id}"
    )
    root.mkdir(parents=True, exist_ok=False)
    mirror = root / "source_mirror"
    mirror_manifest = materialize_runtime_source_mirror(ginav_root, mirror)
    harness = root / "matlab_harness"
    output = root / "MATLAB_ENVIRONMENT_RAW.tsv"
    windows = executable.suffix.casefold() == ".exe"
    main = render_environment_probe(output, mirror_root=mirror, windows=windows)
    script = write_harness_files(
        harness, main_script=main, fopen_log=root / "MATLAB_FOPEN_LEDGER.tsv",
        windows=windows,
    )
    guard = CoreCleanlinessGuard(
        f"G0_MATLAB_ENVIRONMENT_{probe_id}", ginav_root, mirror, mirror_manifest
    )
    invocation: dict[str, Any]
    try:
        with guard:
            invocation = run_matlab_script(executable, script, timeout_seconds=300)
    except (OSError, MatlabRuntimeError) as exc:
        invocation = {
            "command": list(build_matlab_batch_command(executable, script)),
            "batch_invocation": "-nosplash -r function invocation",
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
            "runtime_seconds": None,
            "pass": False,
        }
    finally:
        # If MATLAB fails, the official source/mirror proof is still frozen
        # before the environment blocker is raised.
        if guard.before is not None and guard.after is not None:
            write_json(root / "GINAV_CORE_CLEANLINESS_BEFORE_AFTER.json", guard.report())
    write_json(root / "MATLAB_ENVIRONMENT_INVOCATION.json", invocation)
    if not invocation["pass"] or not output.is_file():
        raise MatlabRuntimeError(
            "licensed MATLAB environment probe failed: "
            + str(invocation.get("stderr") or invocation.get("stdout") or "")
        )
    payload = parse_environment_probe(output)
    validate_matlab_environment(
        payload,
        expected_source_root=(
            wsl_to_windows_path(mirror) if windows else str(mirror.resolve())
        ),
    )
    environment = {
        "schema_version": "ginav2021.matlab_environment.v1",
        "executable_path": str(executable),
        "executable_sha256": sha256_file(executable),
        "platform_route": "WINDOWS_MATLAB_FROM_WSL" if windows else "NATIVE_LINUX_MATLAB",
        "batch_invocation": invocation["command"],
        "locale": payload.get("locale"),
        "version": payload.get("version"),
        "release": payload.get("release"),
        "computer": payload.get("computer"),
        "arch": payload.get("arch"),
        "java_version": payload.get("java_version"),
        "usejava_jvm": payload.get("usejava_jvm"),
        "usejava_awt": payload.get("usejava_awt"),
        "usejava_desktop": payload.get("usejava_desktop"),
        "display_capable_route": bool(payload.get("usejava_awt")),
        "headless_batch": True,
        "required_toolbox_policy": "base_MATLAB_and_graphics_only_for_SPP_INS_LC",
        "required_function_availability": payload.get("required_function_availability"),
        "installed_products": payload.get("installed_products"),
        "license_modified_or_activated": False,
        "pass": True,
    }
    return environment, guard.report()


def _run_sample_regression(
    *,
    stage: Path,
    ginav_root: Path,
    matlab_executable: Path,
    timeout_seconds: float,
    access_ledger: AccessLedger,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    section = _stage_dir(stage, "01_OFFICIAL_SAMPLE_REGRESSION")
    archive = ginav_root / OFFICIAL_SAMPLE_RELATIVE
    official_config = ginav_root / OFFICIAL_CONFIG_RELATIVE
    summaries: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    cleanliness: list[dict[str, Any]] = []
    extractor = shutil.which("7z") or shutil.which("7zz")
    if extractor is None:
        raise TransactionError("7z extractor is unavailable for official sample")
    archive_inventory = _inventory_sample_archive(
        archive, extractor, access_ledger
    )
    write_json(
        section / "OFFICIAL_SAMPLE_ARCHIVE_INVENTORY.json",
        archive_inventory,
    )
    for index in (1, 2):
        run_root = section / f"pristine_run_{index}"
        run_root.mkdir(exist_ok=False)
        extraction = _extract_sample(
            archive, run_root / "sample_data", access_ledger, archive_inventory
        )
        inputs = _resolve_sample_inputs(run_root / "sample_data", archive_inventory)
        derived = run_root / "GINav_SPP_LC_CPT.ini"
        config_contract = derive_official_sample_config(
            official_config, derived, inputs["data_dir"]
        )
        run = _run_official(
            run_id=f"G1_OFFICIAL_SAMPLE_RUN_{index}", run_root=run_root,
            ginav_root=ginav_root, matlab_executable=matlab_executable,
            config_path=derived, observation_path=inputs["observation"],
            navigation_path=inputs["navigation"], imu_path=inputs["imu"],
            timeout_seconds=timeout_seconds, access_ledger=access_ledger,
        )
        cleanliness.append(run["core_cleanliness"])
        if not run["pass"] or run["native_output_count"] != 1:
            raise TransactionError(f"official sample pristine run {index} failed")
        rows = read_official_solution(run["native_output_path"])
        summary = summarize_solution(rows)
        summary.update(
            {
                "run_index": index,
                "runtime_seconds": run["runtime_seconds"],
                "observation_path": str(inputs["observation"]),
                "observation_sha256": sha256_file(inputs["observation"]),
                "navigation_path": str(inputs["navigation"]),
                "navigation_sha256": sha256_file(inputs["navigation"]),
                "imu_path": str(inputs["imu"]),
                "imu_sha256": sha256_file(inputs["imu"]),
                "output_path": run["native_output_path"],
                "output_sha256": sha256_file(run["native_output_path"]),
                "config_contract": config_contract,
                "extraction": extraction,
                "file_access_audit": run["file_access_audit"],
            }
        )
        summaries.append(summary)
        runs.append({"rows": rows, "run": run})
    determinism = compare_sample_runs(runs[0]["rows"], runs[1]["rows"])
    write_json(section / "OFFICIAL_SAMPLE_DETERMINISM.json", determinism)
    status = {
        "schema_version": "ginav2021.official_sample_regression_status.v1",
        "status": "PASS" if determinism["pass"] else "FAIL",
        "official_sample_sha256": sha256_file(archive),
        "pristine_run_count": 2,
        "reference_member_present_in_archive": (
            archive_inventory["reference_member_count"] == 1
        ),
        "official_serialized_output_bundled": archive_inventory[
            "bundled_serialized_output_present"
        ],
        "archive_inventory_path": "OFFICIAL_SAMPLE_ARCHIVE_INVENTORY.json",
        "reference_member_extracted": False,
        "reference_member_opened": False,
        "old_repository_result_opened": False,
        "summaries": summaries,
        "pass": determinism["pass"],
    }
    write_json(section / "OFFICIAL_SAMPLE_REGRESSION_STATUS.json", status)
    summary_rows = []
    for item in summaries:
        summary_rows.append(
            {
                "run_index": item["run_index"], "row_count": item["row_count"],
                "alignment_week": item["alignment_week"],
                "alignment_sow": item["alignment_sow"],
                "gnss_lc_update_count": item["internal_spp_fed_lc_update_count"],
                "ins_only_propagation_count": item["ins_only_propagation_count"],
                "finite_state_rate": item["finite_state_rate"],
                "finite_covariance_rate": item["finite_covariance_rate"],
                "runtime_seconds": item["runtime_seconds"],
                "scientific_digest_sha256": item["scientific_digest_sha256"],
            }
        )
    _write_csv(
        section / "OFFICIAL_SAMPLE_OUTPUT_SUMMARY.csv", summary_rows,
        tuple(summary_rows[0]),
    )
    report = f"""# Official GINav sample regression

Status: `{'PASS' if determinism['pass'] else 'FAIL'}`.

The unmodified pinned source was run twice from pristine source/data roots.  The
only official configuration change was `data_dir`.  The archive reference
`{OFFICIAL_REFERENCE_MEMBER_BASENAME}` and tracked historical `result/*.pos`
were not opened.  Both runs had {summaries[0]['row_count']} rows and scientific
digest `{summaries[0]['scientific_digest_sha256']}`.
"""
    (section / "OFFICIAL_SAMPLE_REGRESSION_REPORT.md").write_text(report, encoding="utf-8")
    if not determinism["pass"]:
        raise TransactionError("official sample two-run determinism failed")
    return status, cleanliness


def _write_gnss_artifacts(stage: Path, audit: Mapping[str, Any]) -> None:
    section = _stage_dir(stage, "02_BY2_GNSS_ADAPTER")
    write_json(section / "BY2_GNSS1_RINEX_AUDIT.json", audit)
    rinex = audit["rinex"]
    contract = {
        "schema_version": "ginav2021.by2_gnss1_rinex_contract.v1",
        "source": "gnss1-raw.csv_RAWX_SFRBX_navigation_material",
        "GNSS1_only": True,
        "GNSS2_used": False,
        "external_PVT_measurement_interface_used": False,
        "converter": audit["converter"],
        "command": audit["command"],
        "rinex_version": rinex["rinex_version"],
        "selected_navsys": rinex["selected_navsys"],
        "selected_nfreq": rinex["selected_nfreq"],
        "selection_rule": rinex["selection_rule"],
        "accuracy_based_selection": False,
        "pass": True,
    }
    _write_yaml(section / "BY2_GNSS1_RINEX_CONTRACT.yaml", contract)
    rows = epoch_signal_rows(rinex)
    _write_csv(section / "BY2_GNSS1_EPOCH_AND_SIGNAL_SUMMARY.csv", rows, tuple(rows[0]))


def _write_imu_artifacts(stage: Path, audit: Mapping[str, Any]) -> None:
    section = _stage_dir(stage, "03_BY2_IMU_ADAPTER")
    write_json(section / "BY2_GINAV_IMU_AUDIT.json", audit)
    contract = {
        "schema_version": "ginav2021.by2_imu_contract.v1",
        "data_identity": audit["data_identity"],
        "allowed_fields": ["timestamp", "imu_state.gyroscope", "imu_state.accelerometer"],
        "forbidden_fields_materialized": False,
        "source_frame": "FLU",
        "official_frame": "RFU",
        "map": "[R,F,U]=[-L,F,U]",
        "data_format": 2,
        "increment_rule": "current_sample_times_dt",
        "first_sample_output": "skipped_no_prior_interval",
        "sample_rate_hz": GO2_SAMPLE_RATE_HZ,
        "sqrt_dt_preprocessing": False,
        "raw_source_mutated": False,
        "runtime_csv_committed": False,
        "pass": audit["pass"],
    }
    _write_yaml(section / "BY2_GINAV_IMU_CONTRACT.yaml", contract)


def _read_imu_gps_total_nanoseconds(path: Path) -> tuple[int, ...]:
    """Read the official time columns without a binary64 round trip."""

    totals: list[int] = []
    week_ns = WEEK_SECONDS * NANOSECONDS
    with path.open("r", encoding="ascii", errors="strict", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not {"gps_week", "gps_sow"}.issubset(
            reader.fieldnames
        ):
            raise ConfigContractError("prepared IMU CSV is missing GPS week/SOW")
        for row_number, row in enumerate(reader, start=2):
            try:
                week = int(row["gps_week"])
                sow = decimal.Decimal(row["gps_sow"])
            except (KeyError, TypeError, ValueError, decimal.InvalidOperation) as exc:
                raise ConfigContractError(
                    f"prepared IMU time is invalid at CSV row {row_number}"
                ) from exc
            sow_ns_decimal = sow * NANOSECONDS
            sow_ns = int(sow_ns_decimal)
            if (
                week < 0
                or sow_ns_decimal != decimal.Decimal(sow_ns)
                or not 0 <= sow_ns < week_ns
            ):
                raise ConfigContractError(
                    f"prepared IMU week/SOW is out of range at CSV row {row_number}"
                )
            total = week * week_ns + sow_ns
            if totals and total <= totals[-1]:
                raise ConfigContractError(
                    "prepared IMU GPS timestamps are not strictly increasing"
                )
            totals.append(total)
    if not totals:
        raise ConfigContractError("prepared IMU CSV has no data rows")
    return tuple(totals)


def _datetime_gpst_total_nanoseconds(value: dt.datetime) -> int:
    if value.tzinfo is not None:
        value = value.astimezone(dt.timezone.utc).replace(tzinfo=None)
    gps = gpst_calendar_to_gps(
        value.year, value.month, value.day, value.hour, value.minute,
        decimal.Decimal(value.second)
        + decimal.Decimal(value.microsecond) / decimal.Decimal(1_000_000),
    )
    return gps.week * WEEK_SECONDS * NANOSECONDS + gps.sow_nanoseconds


def _gps_overlap_datetimes(
    epochs: Sequence[RinexEpoch], imu_csv: Path
) -> tuple[dt.datetime, dt.datetime]:
    imu_totals = _read_imu_gps_total_nanoseconds(imu_csv)
    first_imu_total = imu_totals[0]
    last_imu_total = imu_totals[-1]
    first_obs = (
        epochs[0].gps_time.week * WEEK_SECONDS * NANOSECONDS
        + epochs[0].gps_time.sow_nanoseconds
    )
    last_obs = (
        epochs[-1].gps_time.week * WEEK_SECONDS * NANOSECONDS
        + epochs[-1].gps_time.sow_nanoseconds
    )
    start_total = max(first_imu_total, first_obs)
    end_total = min(last_imu_total, last_obs)
    start_total = ((start_total + NANOSECONDS - 1) // NANOSECONDS) * NANOSECONDS
    end_total = (end_total // NANOSECONDS) * NANOSECONDS
    if start_total >= end_total:
        raise ConfigContractError("prepared GNSS/IMU streams have no integer-grid overlap")

    def convert(total: int) -> dt.datetime:
        week, sow_ns = divmod(total, WEEK_SECONDS * NANOSECONDS)
        year, month, day, hour, minute, second = gps_to_gpst_calendar(
            GpsTime(int(week), int(sow_ns))
        )
        if second != second.to_integral_value():
            raise ConfigContractError("overlap bound is not an integer GPST second")
        return dt.datetime(year, month, day, hour, minute, int(second))

    return convert(start_total), convert(end_total)


def _official_run_epoch_inventory(
    epochs: Sequence[RinexEpoch],
    imu_csv: Path,
    *,
    start_time_gpst: dt.datetime,
    end_time_gpst: dt.datetime,
    sample_rate_hz: int,
) -> dict[str, Any]:
    """Inventory epochs reachable by official read/match/reject predicates."""

    if sample_rate_hz <= 0:
        raise ConfigContractError("official IMU sample rate must be positive")
    start_total = _datetime_gpst_total_nanoseconds(start_time_gpst)
    end_total = _datetime_gpst_total_nanoseconds(end_time_gpst)
    if start_total > end_total:
        raise ConfigContractError("official run epoch inventory has a reversed window")
    imu_all = _read_imu_gps_total_nanoseconds(imu_csv)
    imu_totals = tuple(value for value in imu_all if start_total <= value <= end_total)
    if not imu_totals:
        raise ConfigContractError("official run window contains no prepared IMU rows")

    def epoch_total(epoch: RinexEpoch) -> int:
        return (
            epoch.gps_time.week * WEEK_SECONDS * NANOSECONDS
            + epoch.gps_time.sow_nanoseconds
        )

    in_window = tuple(
        epoch for epoch in epochs if start_total <= epoch_total(epoch) <= end_total
    )
    # decode_obsb materializes observations only for event flags 0--2 and 6.
    decoded = tuple(
        epoch for epoch in in_window
        if epoch.satellite_count is not None
        and epoch.satellite_count > 0
        and epoch.event_flag in {0, 1, 2, 6}
    )
    integer_epochs = tuple(
        epoch for epoch in decoded if epoch.accepted_by_official_processor
    )
    tolerance_ns = decimal.Decimal("0.501") * NANOSECONDS / sample_rate_hz
    matched = 0
    for epoch in integer_epochs:
        target = epoch_total(epoch)
        insertion = bisect.bisect_left(imu_totals, target)
        nearby: list[int] = []
        if insertion < len(imu_totals):
            nearby.append(imu_totals[insertion])
        if insertion:
            nearby.append(imu_totals[insertion - 1])
        if nearby and min(abs(value - target) for value in nearby) < tolerance_ns:
            matched += 1

    return {
        "schema_version": "ginav2021.official_run_epoch_inventory.v1",
        "rinex_total_epoch_count": len(epochs),
        "input_gnss_epoch_count": len(in_window),
        "official_decoded_observation_epoch_count": len(decoded),
        "in_window_non_observation_event_count": len(in_window) - len(decoded),
        "in_window_integer_epoch_count": len(integer_epochs),
        "in_window_noninteger_rejected_count": len(decoded) - len(integer_epochs),
        "accepted_official_gnss_epoch_count": matched,
        "in_window_integer_unmatched_imu_count": len(integer_epochs) - matched,
        "prepared_imu_total_row_count": len(imu_all),
        "prepared_imu_in_window_row_count": len(imu_totals),
        "config_start_gpst": start_time_gpst.isoformat(sep=" "),
        "config_end_gpst": end_time_gpst.isoformat(sep=" "),
        "official_match_predicate": "abs(imu_time-observation_time)<0.501/sample_rate",
        "official_match_tolerance_seconds": float(tolerance_ns / NANOSECONDS),
        "official_noninteger_rejection": "obsr_(1).time.sec~=0",
        "official_duplicate_observation_rejection": True,
        "one_second_interval_unchanged": True,
        "conservation_pass": (
            len(in_window) == len(decoded) + (len(in_window) - len(decoded))
            and len(decoded) == len(integer_epochs) + (len(decoded) - len(integer_epochs))
            and len(integer_epochs) == matched + (len(integer_epochs) - matched)
        ),
    }


def _probe_summary(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "epoch_index", "gps_week", "gps_sow",
            "common_phase_satellites", "tdcp_equation_count",
            "robust_retained_count", "threshold_pass", "official_tdcp_flag",
            "prior_spp_available", "prior_spp_status", "spp_status",
            "spp_satellite_count", "spp_pair_available",
            "tdcp_velocity_attempted", "alignment_attempted",
            "alignment_result",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise TransactionError(
                "TDCP probe CSV is missing columns: " + ",".join(sorted(missing))
            )
        rows = list(reader)
    if not rows:
        raise TransactionError("TDCP probe produced no eligible integer epochs")

    def truth(row: Mapping[str, str], key: str) -> bool:
        value = str(row.get(key, "")).strip().casefold()
        if value not in {"0", "1", "false", "true"}:
            raise TransactionError(
                f"TDCP probe boolean {key} has invalid value: {value!r}"
            )
        return value in {"1", "true"}

    def integer(row: Mapping[str, str], key: str) -> int:
        try:
            value = int(str(row[key]).strip())
        except (KeyError, TypeError, ValueError) as exc:
            raise TransactionError(
                f"TDCP probe integer {key} is invalid"
            ) from exc
        return value

    try:
        spp_valid = sum(integer(row, "spp_status") != 0 for row in rows)
        prior_spp = sum(truth(row, "prior_spp_available") for row in rows)
        spp_pairs = sum(truth(row, "spp_pair_available") for row in rows)
        tdcp_attempts = sum(
            truth(row, "tdcp_velocity_attempted") for row in rows
        )
        alignment_attempts = sum(
            truth(row, "alignment_attempted") for row in rows
        )
        threshold_passes = sum(truth(row, "threshold_pass") for row in rows)
        tdcp_flags = sum(truth(row, "official_tdcp_flag") for row in rows)
        aligned_rows = [row for row in rows if truth(row, "alignment_result")]
        max_common = max(integer(row, "common_phase_satellites") for row in rows)
        max_equations = max(integer(row, "tdcp_equation_count") for row in rows)
        max_retained = max(integer(row, "robust_retained_count") for row in rows)
    except TransactionError:
        raise
    except (TypeError, ValueError) as exc:
        raise TransactionError(f"TDCP probe CSV is malformed: {exc}") from exc

    if alignment_attempts != len(rows):
        raise TransactionError(
            "TDCP probe did not record official ins_align invocation for every "
            "eligible epoch"
        )
    if tdcp_attempts != prior_spp:
        raise TransactionError(
            "TDCP velocity-attempt count does not conserve prior SPP availability"
        )
    if any(
        truth(row, "alignment_result")
        and not (
            truth(row, "official_tdcp_flag")
            and truth(row, "threshold_pass")
            and truth(row, "spp_pair_available")
        )
        for row in rows
    ):
        raise TransactionError(
            "official alignment result lacks its source TDCP/SPP prerequisites"
        )
    return {
        "schema_version": "ginav2021.tdcp_alignment_activation_summary.v1",
        "eligible_integer_epoch_count": len(rows),
        "max_common_phase_satellites": max_common,
        "max_tdcp_equation_count": max_equations,
        "max_robust_retained_count": max_retained,
        "threshold_literal": "dot(vn,vn)>3",
        "threshold_pass_count": threshold_passes,
        "official_tdcp_flag_count": tdcp_flags,
        "prior_spp_available_epoch_count": prior_spp,
        "spp_pair_available_epoch_count": spp_pairs,
        "tdcp_velocity_attempt_count": tdcp_attempts,
        "internal_spp_valid_epoch_count": spp_valid,
        "internal_spp_invalid_epoch_count": len(rows) - spp_valid,
        "internal_spp_outcome_conservation_pass": (
            spp_valid + (len(rows) - spp_valid) == len(rows)
        ),
        "alignment_attempt_count": alignment_attempts,
        "alignment_attempt_covers_every_eligible_epoch": True,
        "alignment_result_count": len(aligned_rows),
        "alignment_activated": bool(aligned_rows),
        "first_alignment_epoch_index": (
            int(aligned_rows[0]["epoch_index"]) if aligned_rows else None
        ),
        "first_alignment_gps_week": (
            int(aligned_rows[0]["gps_week"]) if aligned_rows else None
        ),
        "first_alignment_gps_sow": (
            float(aligned_rows[0]["gps_sow"]) if aligned_rows else None
        ),
        "initial_roll_pitch_source": "hardcoded_zero_by_official_ins_align",
        "initial_yaw_source": "official_TDCP_velocity_vel2yaw_only",
        "alternative_yaw_substitution_used": False,
        "dual_antenna_yaw_used": False,
        "go2_orientation_used": False,
        "trace_yaw_used": False,
        "manual_yaw_used": False,
        "official_source_supported_alternative_alignment_routes": [],
    }


def _write_config_artifacts(stage: Path, contract: Mapping[str, Any]) -> None:
    section = _stage_dir(stage, "04_BY2_CONFIG_AND_TIME_CONTRACT")
    _write_yaml(section / "BY2_GINAV_CONFIG_CONTRACT.yaml", contract)
    rows = contract["diff_rows"]
    _write_csv(
        section / "BY2_GINAV_CONFIG_DIFF.csv", rows,
        ("field", "official_value", "derived_value", "changed", "change_allowed",
         "official_line", "provenance"),
    )


def _zero_native_output_terminal() -> str:
    """A zero-file C00 after a successful G3 activation is fail-closed."""

    return "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE"


def _activation_terminal(activation: Mapping[str, Any]) -> tuple[str, str] | None:
    """Route a completed source-exact probe without tuning or fallback yaw."""

    if (
        int(activation.get("internal_spp_valid_epoch_count") or 0) == 0
        or int(activation.get("spp_pair_available_epoch_count") or 0) == 0
    ):
        return (
            "UNSUPPORTED_LC02_GINAV_BY2_INSUFFICIENT_INTERNAL_SPP",
            "source-exact probe found zero or no pairwise-available internal SPP epochs",
        )
    if (
        int(activation.get("official_tdcp_flag_count") or 0) == 0
        or int(activation.get("threshold_pass_count") or 0) == 0
    ):
        return (
            "UNSUPPORTED_LC02_GINAV_BY2_TDCP_ALIGNMENT_CONDITION_NOT_MET",
            "pairwise internal SPP was available, but the literal official "
            "TDCP dot(vn,vn)>3 activation condition was never satisfied",
        )
    if not activation.get("alignment_activated"):
        return (
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
            "official SPP and TDCP threshold prerequisites were observed, but "
            "ins_align did not activate; fail-closed contract violation",
        )
    return None


def run_transaction(options: TransactionOptions) -> dict[str, Any]:
    local = _load_local_paths(options, verify_raw_availability=False)
    protected_roots = (
        options.repository_root.resolve(strict=True),
        local["clean_root"].resolve(strict=True),
        local["raw_root"].resolve(strict=False),
        options.paper_root.expanduser().resolve(strict=False),
        options.legacy_freeze_root.expanduser().resolve(strict=False),
    )
    expected_destination = _expected_publication_destination(
        local["clean_root"].resolve(strict=True)
    )
    try:
        publication_target = validate_exact_destination(
            options.destination_stage_root,
            expected_destination=expected_destination,
            clean_root=local["clean_root"],
            other_protected_roots=(
                options.repository_root, local["raw_root"], options.paper_root,
                options.legacy_freeze_root,
            ),
        )
    except PublicationError as exc:
        raise TransactionError(str(exc)) from exc
    root = _make_scratch_root(
        options.scratch_root, protected_roots=protected_roots
    )
    stage = _create_stage_layout(root)
    all_cleanliness: list[dict[str, Any]] = []
    global_access = AccessLedger()
    source_dir = _stage_dir(stage, "00_SOURCE_AND_ENVIRONMENT")
    provenance = _initial_provenance(options)
    path_aliases = {
        options.repository_root: "<CODE_ROOT>",
        options.ginav_root: "<GINAV_ROOT>",
        options.scratch_root: "<SCRATCH_ROOT>",
        stage: "<SCRATCH_STAGE_ROOT>",
        publication_target: "<STAGE_ROOT>",
        local["clean_root"]: "<CLEAN_ROOT>",
        local["raw_root"]: "<RAW_ROOT>",
        options.paper_root: "<PAPER_ROOT>",
        options.legacy_freeze_root: "<LEGACY_FREEZE_ROOT>",
        options.matlab_executable: "<MATLAB_EXECUTABLE>",
        local["horizontal_literature_rtklib_root"]: "<RTKLIB_ROOT>",
        local["horizontal_literature_convbin"]: "<CONVBIN_EXECUTABLE>",
    }

    def finalize(
        status: str,
        *,
        detail: str | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return _finalize_terminal(
            status, stage=stage, access_audit=global_access.audit(),
            provenance=provenance, cleanliness_runs=all_cleanliness,
            publish=options.publish, destination=publication_target,
            clean_root=local["clean_root"], protected_roots=protected_roots,
            path_aliases=path_aliases, detail=detail,
            extra=extra,
        )

    try:
        source_lock = verify_source_identity(options.ginav_root)
        provenance["official_source_identity"] = {
            "commit": source_lock["commit"], "tree_oid": source_lock["tree_oid"],
            "tracked_source_clean": source_lock["tracked_source_clean"],
            "named_file_sha256": {
                key: value.get("sha256")
                for key, value in source_lock["named_files"].items()
            },
        }
        write_json(source_dir / "GINAV_SOURCE_LOCK.json", source_lock)
    except (OSError, SourceIdentityError) as exc:
        return finalize(
            "BLOCKED_LC02_GINAV_SOURCE_IDENTITY_MISMATCH", detail=str(exc)
        )

    candidates = discover_matlab_candidates(options.matlab_executable)
    for index, candidate in enumerate(candidates, start=1):
        path_aliases[candidate] = f"<MATLAB_CANDIDATE_{index}>"
        install_root = candidate.parent.parent
        if install_root != Path(install_root.anchor):
            path_aliases[install_root] = (
                f"<MATLAB_INSTALL_ROOT_{index}>"
            )
    if not candidates:
        write_json(
            source_dir / "GINAV_MATLAB_DISCOVERY_ATTEMPTS.json",
            {"candidates": [], "selected": None},
        )
        return finalize(
            "BLOCKED_LC02_GINAV_MATLAB_RUNTIME_UNAVAILABLE",
            detail="no installed licensed MATLAB executable candidate",
        )
    matlab_executable: Path | None = None
    environment: dict[str, Any] | None = None
    discovery_attempts: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        provenance["gate_execution_counts"]["G0_matlab_candidate_attempts"] += 1
        try:
            candidate_environment, cleanliness = _matlab_environment(
                stage=stage, ginav_root=options.ginav_root, executable=candidate,
                probe_id=f"candidate_{index}",
            )
            all_cleanliness.append(cleanliness)
            matlab_executable = candidate
            environment = candidate_environment
            discovery_attempts.append(
                {"candidate": str(candidate), "pass": True, "selected": True}
            )
            break
        except SourceIdentityError as exc:
            proof_path = (
                source_dir / f"matlab_probe_runtime_candidate_{index}"
                / "GINAV_CORE_CLEANLINESS_BEFORE_AFTER.json"
            )
            if proof_path.is_file():
                all_cleanliness.append(
                    json.loads(proof_path.read_text(encoding="utf-8"))
                )
            _write_cleanliness(stage, all_cleanliness)
            return finalize(
                "BLOCKED_LC02_GINAV_SOURCE_IDENTITY_MISMATCH",
                detail=str(exc),
            )
        except (OSError, ValueError, MatlabRuntimeError) as exc:
            attempt_root = source_dir / f"matlab_probe_runtime_candidate_{index}"
            proof_path = attempt_root / "GINAV_CORE_CLEANLINESS_BEFORE_AFTER.json"
            invocation_path = attempt_root / "MATLAB_ENVIRONMENT_INVOCATION.json"
            if not proof_path.is_file() or not invocation_path.is_file():
                _write_cleanliness(stage, all_cleanliness)
                return finalize(
                    "BLOCKED_LC02_GINAV_SOURCE_IDENTITY_MISMATCH",
                    detail=(
                        "MATLAB candidate attempt lacks complete official-source "
                        f"cleanliness/error evidence: candidate_{index}: {exc}"
                    ),
                )
            all_cleanliness.append(
                json.loads(proof_path.read_text(encoding="utf-8"))
            )
            invocation = json.loads(invocation_path.read_text(encoding="utf-8"))
            discovery_attempts.append(
                {
                    "candidate": str(candidate), "pass": False,
                    "selected": False, "error": str(exc),
                    "full_matlab_error": invocation,
                }
            )
    write_json(
        source_dir / "GINAV_MATLAB_DISCOVERY_ATTEMPTS.json",
        {"candidates": discovery_attempts, "selected": str(matlab_executable or "")},
    )
    if matlab_executable is None or environment is None:
        if discovery_attempts:
            _write_cleanliness(stage, all_cleanliness)
        return finalize(
            "BLOCKED_LC02_GINAV_MATLAB_RUNTIME_UNAVAILABLE",
            detail="; ".join(
                str(item.get("error") or "candidate unavailable")
                for item in discovery_attempts
            ),
        )
    write_json(source_dir / "GINAV_MATLAB_ENVIRONMENT.json", environment)
    provenance["matlab_environment"] = {
        "executable_sha256": environment["executable_sha256"],
        "version": environment["version"], "release": environment["release"],
        "platform_route": environment["platform_route"],
    }

    try:
        provenance["data_mode"] = "official_sample_regression"
        provenance["dataset_role"] = "OFFICIAL_SOFTWARE_REGRESSION_NOT_BY2_EVIDENCE"
        provenance["raw_source_hashes"] = {
            "official_sample_archive": source_lock["named_files"][
                OFFICIAL_SAMPLE_RELATIVE.as_posix()
            ]["sha256"]
        }
        provenance["provider_hashes"] = {
            "official_sample_config": source_lock["named_files"][
                OFFICIAL_CONFIG_RELATIVE.as_posix()
            ]["sha256"]
        }
        provenance["config_hash"] = provenance["provider_hashes"][
            "official_sample_config"
        ]
        sample_status, cleanliness = _run_sample_regression(
            stage=stage, ginav_root=options.ginav_root,
            matlab_executable=matlab_executable,
            timeout_seconds=options.sample_timeout_seconds,
            access_ledger=global_access,
        )
        all_cleanliness.extend(cleanliness)
        provenance["gate_execution_counts"]["G1_official_sample_runs"] = 2
        for summary in sample_status["summaries"]:
            run_key = f"official_sample_pristine_run_{summary['run_index']}"
            provenance["provider_hashes"].update({
                f"{run_key}_observation": summary["observation_sha256"],
                f"{run_key}_navigation": summary["navigation_sha256"],
                f"{run_key}_imu": summary["imu_sha256"],
                f"{run_key}_output": summary["output_sha256"],
            })
    except SourceIdentityError as exc:
        _write_cleanliness(stage, all_cleanliness)
        return finalize(
            "BLOCKED_LC02_GINAV_SOURCE_IDENTITY_MISMATCH",
            detail=str(exc),
        )
    except (OSError, ValueError, TransactionError, MatlabRuntimeError,
            OutputContractError, ForbiddenInputError) as exc:
        _write_cleanliness(stage, all_cleanliness)
        return finalize(
            "BLOCKED_LC02_GINAV_OFFICIAL_SAMPLE_REGRESSION_FAILURE",
            detail=str(exc),
        )
    _write_cleanliness(stage, all_cleanliness)

    try:
        local = _load_local_paths(options, verify_raw_availability=True)
        provenance["data_mode"] = "real_by2_raw"
        provenance["dataset_role"] = "REAL_BY2_NATIVE_INPUT_ADAPTER_AND_C00"
        provenance["raw_source_hashes"] = {}
        provenance["provider_hashes"] = {}
        provenance["config_hash"] = None
        raw_lock_path = local["clean_root"] / "01_RAW_HASH_LOCK" / "RAW_FILE_HASH_LOCK.csv"
        if sha256_file(raw_lock_path) != RAW_HASH_LOCK_SHA256:
            raise RinexAdapterError("clean raw hash lock identity mismatch")
        lock = read_hash_lock(raw_lock_path)
        gnss_raw = (local["by2_fix_root"] / "gnss1-raw.csv").resolve(strict=True)
        if local["raw_root"] not in gnss_raw.parents:
            raise RinexAdapterError("GNSS1 raw source escapes the locked raw root")
        gnss_relative = gnss_raw.relative_to(local["raw_root"]).as_posix()
        verify_raw_sources(local["raw_root"], [gnss_relative], lock)
        provenance["raw_source_hashes"].update({
            "RAW_FILE_HASH_LOCK.csv": sha256_file(raw_lock_path),
            "gnss1-raw.csv": sha256_file(gnss_raw),
        })
        global_access.record(gnss_raw, role="GNSS1_RAWX_SFRBX_SOURCE")
        gnss_audit = convert_gnss1_raw_to_rinex(
            gnss_raw, rtklib_root=local["horizontal_literature_rtklib_root"],
            convbin=local["horizontal_literature_convbin"],
            output_root=_stage_dir(stage, "02_BY2_GNSS_ADAPTER") / "runtime",
            ledger=global_access,
        )
        provenance["gate_execution_counts"]["G2_gnss_adapter_runs"] = 1
        provenance["converter_identity"] = gnss_audit["converter"]
        provenance["provider_hashes"].update({
            "BY2_GNSS1_RINEX_OBSERVATION": gnss_audit["rinex"]["observation_sha256"],
            "BY2_GNSS1_RINEX_NAVIGATION": gnss_audit["rinex"]["navigation_sha256"],
            "BY2_GNSS1_RECONSTRUCTED_UBX": gnss_audit["ubx_sha256"],
        })
        _write_gnss_artifacts(stage, gnss_audit)
    except (OSError, ValueError, ManifestContractError, PathContractError,
            RinexAdapterError, ForbiddenInputError) as exc:
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_GNSS_ADAPTER_FAILURE", detail=str(exc)
        )

    try:
        go2 = local["by2_go2_body"].resolve(strict=True)
        go2_relative = go2.relative_to(local["raw_root"]).as_posix()
        verify_raw_sources(local["raw_root"], [go2_relative], lock)
        provenance["raw_source_hashes"]["Go2_by2_complete_source"] = sha256_file(go2)
        imu_csv = _stage_dir(stage, "03_BY2_IMU_ADAPTER") / "BY2_GINAV_IMU.csv"
        imu_audit = adapt_go2_imu(go2, imu_csv, ledger=global_access)
        provenance["gate_execution_counts"]["G2_imu_adapter_runs"] = 1
        provenance["provider_hashes"]["BY2_GINAV_IMU_FORMAT2"] = sha256_file(imu_csv)
        _write_imu_artifacts(stage, imu_audit)
    except (OSError, ValueError, ManifestContractError, ImuAdapterError,
            ForbiddenInputError) as exc:
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_IMU_ADAPTER_FAILURE", detail=str(exc)
        )

    time_section = _stage_dir(stage, "04_BY2_CONFIG_AND_TIME_CONTRACT")
    literal_observation = Path(gnss_audit["observation_path"])
    try:
        epochs = parse_rinex_epochs(literal_observation)
        literal_acceptance = official_epoch_acceptance_audit(epochs)
    except (OSError, TimeContractError) as exc:
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_GNSS_ADAPTER_FAILURE",
            detail=str(exc),
        )
    normalization_error: str | None = None
    proof: dict[str, Any] | None = None
    normalized_rows: Sequence[Mapping[str, Any]] = ()
    selected_observation = literal_observation
    try:
        ubx_path = Path(gnss_audit["ubx_path"])
        global_access.record(ubx_path, role="GNSS1_RECONSTRUCTED_UBX_TIME_ONLY")
        ubx_stream = ubx_path.read_bytes()
        rawx_times, pvt_times = extract_same_receiver_time_events(ubx_stream)
        proof = prove_single_constant_normalization(rawx_times, pvt_times, epochs)
        selected_observation = time_section / "BY2_GNSS1_NORMALIZED.rnx"
        normalized_rows = normalize_rinex_epochs(
            literal_observation, selected_observation, proof
        )
    except (OSError, TimeContractError) as exc:
        normalization_error = str(exc)
        if literal_acceptance["literal_accepted_epoch_count"] == 0:
            acceptance = {
                **literal_acceptance,
                "normalization_proven": False,
                "normalization_error": normalization_error,
                "normalized_accepted_epoch_count": 0,
                "selected_official_epoch_count": 0,
            }
            write_json(time_section / "BY2_GINAV_OFFICIAL_EPOCH_ACCEPTANCE_AUDIT.json", acceptance)
            _write_yaml(
                time_section / "BY2_GINAV_TIME_NORMALIZATION_CONTRACT.yaml",
                {
                    "relation_proven": False,
                    "candidate_offset_search_performed": False,
                    "historical_2ms_assumed": False,
                    "error": normalization_error,
                },
            )
            _write_csv(
                time_section / "BY2_GINAV_TIME_NORMALIZATION_LEDGER.csv", [],
                ("epoch_index", "gps_week", "rawx_sow_seconds",
                 "authoritative_integer_sow_seconds", "normalization_offset_nanoseconds",
                 "normalized_sow_seconds"),
            )
            return finalize(
                "UNSUPPORTED_LC02_GINAV_BY2_NONINTEGER_EPOCH_POLICY",
                detail=normalization_error,
            )
    if proof is not None:
        _write_yaml(
            time_section / "BY2_GINAV_TIME_NORMALIZATION_CONTRACT.yaml",
            {key: value for key, value in proof.items() if key != "ledger"},
        )
        _write_csv(
            time_section / "BY2_GINAV_TIME_NORMALIZATION_LEDGER.csv",
            normalized_rows, tuple(normalized_rows[0]),
        )
    else:
        _write_yaml(
            time_section / "BY2_GINAV_TIME_NORMALIZATION_CONTRACT.yaml",
            {
                "relation_proven": False,
                "normalization_applied": False,
                "candidate_offset_search_performed": False,
                "literal_epochs_selected": True,
                "error": normalization_error,
            },
        )
        _write_csv(
            time_section / "BY2_GINAV_TIME_NORMALIZATION_LEDGER.csv", [],
            ("epoch_index", "gps_week", "rawx_sow_seconds",
             "authoritative_integer_sow_seconds", "normalization_offset_nanoseconds",
             "normalized_sow_seconds"),
        )
    try:
        selected_epochs = parse_rinex_epochs(selected_observation)
    except (OSError, TimeContractError) as exc:
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
            detail=f"selected time contract is unreadable: {exc}",
        )
    selected_acceptance = official_epoch_acceptance_audit(selected_epochs)
    acceptance = {
        **literal_acceptance,
        "normalization_proven": proof is not None,
        "normalization_error": normalization_error,
        "normalized_accepted_epoch_count": (
            selected_acceptance["literal_accepted_epoch_count"] if proof else None
        ),
        "selected_official_epoch_count": selected_acceptance["literal_accepted_epoch_count"],
        "candidate_offset_search_performed": False,
        "historical_2ms_assumed": False,
    }
    write_json(time_section / "BY2_GINAV_OFFICIAL_EPOCH_ACCEPTANCE_AUDIT.json", acceptance)
    if acceptance["selected_official_epoch_count"] <= 0:
        return finalize(
            "UNSUPPORTED_LC02_GINAV_BY2_NONINTEGER_EPOCH_POLICY",
            detail="selected official epoch acceptance is zero",
        )

    try:
        start_time, end_time = _gps_overlap_datetimes(selected_epochs, imu_csv)
        by2_config = time_section / "BY2_GINAV_SPP_LC.ini"
        config_contract = derive_by2_config(
            options.ginav_root / OFFICIAL_CONFIG_RELATIVE, by2_config,
            data_directory=stage, site_name="by2_gnss1",
            start_time_gpst=start_time, end_time_gpst=end_time,
            navsys=gnss_audit["rinex"]["selected_navsys"],
            nfreq=int(gnss_audit["rinex"]["selected_nfreq"]),
            project_repository_root=options.repository_root,
        )
        provenance["config_hash"] = sha256_file(by2_config)
        provenance["provider_hashes"].update({
            "BY2_GINAV_SELECTED_OBSERVATION": sha256_file(selected_observation),
            "BY2_GINAV_DERIVED_CONFIG": provenance["config_hash"],
        })
        _write_config_artifacts(stage, config_contract)
        run_epoch_inventory = _official_run_epoch_inventory(
            selected_epochs, imu_csv,
            start_time_gpst=start_time, end_time_gpst=end_time,
            sample_rate_hz=GO2_SAMPLE_RATE_HZ,
        )
        if not run_epoch_inventory["conservation_pass"]:
            raise ConfigContractError("official run epoch inventory did not conserve")
        acceptance["configured_run_inventory"] = run_epoch_inventory
        write_json(
            time_section / "BY2_GINAV_OFFICIAL_EPOCH_ACCEPTANCE_AUDIT.json",
            acceptance,
        )
        if run_epoch_inventory["accepted_official_gnss_epoch_count"] <= 0:
            raise ConfigContractError(
                "configured official run has no integer GNSS epoch matched to IMU"
            )
    except (OSError, ValueError, ConfigContractError) as exc:
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE", detail=str(exc)
        )

    probe_section = _stage_dir(stage, "05_BY2_ACTIVATION_PROBE")
    probe_csv = probe_section / "BY2_GINAV_TDCP_ALIGNMENT_PROBE.csv"
    guard: CoreCleanlinessGuard | None = None
    try:
        probe_runtime = probe_section / "runtime"
        probe_runtime.mkdir(exist_ok=False)
        mirror = probe_runtime / "source_mirror"
        mirror_manifest = materialize_runtime_source_mirror(options.ginav_root, mirror)
        harness = probe_runtime / "matlab_harness"
        fopen_log = probe_runtime / "MATLAB_FOPEN_LEDGER.tsv"
        windows = matlab_executable.suffix.casefold() == ".exe"
        for declared_input in (
            by2_config, selected_observation,
            Path(gnss_audit["navigation_path"]), imu_csv,
        ):
            global_access.authorize_runtime_read(
                Path(declared_input).resolve(strict=True)
            )
            if windows:
                global_access.authorize_runtime_read(
                    wsl_to_windows_path(declared_input)
                )
        main = render_tdcp_probe_script(
            mirror_root=mirror, harness_root=harness, config_path=by2_config,
            observation_path=selected_observation,
            navigation_path=gnss_audit["navigation_path"], imu_path=imu_csv,
            output_csv=probe_csv,
            windows=windows,
        )
        script = write_harness_files(
            harness, main_script=main, fopen_log=fopen_log, windows=windows
        )
        guard = CoreCleanlinessGuard(
            "G3_TDCP_ACTIVATION_PROBE", options.ginav_root, mirror, mirror_manifest
        )
        with guard:
            provenance["gate_execution_counts"]["G3_tdcp_probe_runs"] = 1
            probe_result = run_matlab_script(
                matlab_executable, script, timeout_seconds=options.probe_timeout_seconds
            )
        all_cleanliness.append(guard.report())
        if not fopen_log.is_file():
            raise ForbiddenInputError("G3 TDCP probe MATLAB fopen ledger is missing")
        global_access.import_matlab_fopen_log(fopen_log)
        if not probe_result["pass"] or not probe_csv.is_file():
            raise TransactionError("official TDCP activation probe failed")
        activation = _probe_summary(probe_csv)
        activation["configured_run_epoch_inventory"] = run_epoch_inventory
        activation["probe_covers_every_eligible_integer_epoch"] = (
            activation["eligible_integer_epoch_count"]
            == run_epoch_inventory["accepted_official_gnss_epoch_count"]
        )
        if not activation["probe_covers_every_eligible_integer_epoch"]:
            raise TransactionError(
                "TDCP probe/official epoch inventory conservation failed: "
                f"{activation['eligible_integer_epoch_count']} != "
                f"{run_epoch_inventory['accepted_official_gnss_epoch_count']}"
            )
        activation["matlab_runtime_seconds"] = probe_result["runtime_seconds"]
        activation["file_access_audit"] = global_access.audit()
        write_json(probe_section / "BY2_GINAV_ALIGNMENT_ACTIVATION_SUMMARY.json", activation)
    except SourceIdentityError as exc:
        if guard is not None and guard.before is not None and guard.after is not None:
            if not any(
                item.get("run_id") == "G3_TDCP_ACTIVATION_PROBE"
                for item in all_cleanliness
            ):
                all_cleanliness.append(guard.report())
        _write_cleanliness(stage, all_cleanliness)
        return finalize(
            "BLOCKED_LC02_GINAV_SOURCE_IDENTITY_MISMATCH",
            detail=str(exc),
        )
    except (OSError, ValueError, TransactionError, MatlabRuntimeError,
            ForbiddenInputError) as exc:
        if guard is not None and guard.before is not None and guard.after is not None:
            if not any(
                item.get("run_id") == "G3_TDCP_ACTIVATION_PROBE"
                for item in all_cleanliness
            ):
                all_cleanliness.append(guard.report())
        activation = {
            "schema_version": "ginav2021.tdcp_alignment_activation_summary.v1",
            "alignment_activated": False,
            "probe_execution_failure": str(exc),
            "alternative_yaw_substitution_used": False,
        }
        write_json(probe_section / "BY2_GINAV_ALIGNMENT_ACTIVATION_SUMMARY.json", activation)
        _write_cleanliness(stage, all_cleanliness)
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
            detail=f"activation probe could not complete: {exc}",
        )
    _write_cleanliness(stage, all_cleanliness)
    activation_terminal = _activation_terminal(activation)
    if activation_terminal is not None:
        return finalize(activation_terminal[0], detail=activation_terminal[1])

    # Conditional G4: exactly one MATLAB process and one recursive official run.
    c00_section = _stage_dir(stage, "06_BY2_C00_NATIVE")
    c00_runtime = c00_section / "runtime"
    c00_ledger = global_access
    try:
        c00_runtime.mkdir(exist_ok=False)
        provenance["gate_execution_counts"]["G4_BY2_C00_runs"] = 1
        c00_result = _run_official(
            run_id="G4_BY2_C00_SINGLE_RECURSIVE_RUN", run_root=c00_runtime,
            ginav_root=options.ginav_root, matlab_executable=matlab_executable,
            config_path=by2_config, observation_path=selected_observation,
            navigation_path=Path(gnss_audit["navigation_path"]), imu_path=imu_csv,
            timeout_seconds=options.c00_timeout_seconds, access_ledger=c00_ledger,
        )
        all_cleanliness.append(c00_result["core_cleanliness"])
        if not c00_result["pass"]:
            _write_cleanliness(stage, all_cleanliness)
            return finalize(
                "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
                detail=(
                    "conditional official C00 MATLAB process failed: "
                    + str(c00_result.get("stderr") or "")
                    + "\n"
                    + str(c00_result.get("stdout") or "")
                ).strip(),
            )
        if c00_result["native_output_count"] == 0:
            _write_cleanliness(stage, all_cleanliness)
            return finalize(
                _zero_native_output_terminal(),
                detail=(
                    "conditional official C00 returned zero but produced no "
                    "native solution file after G3 activation"
                ),
            )
        if c00_result["native_output_count"] != 1:
            raise OutputContractError("C00 did not produce exactly one native solution")
        input_counts = {
            "official_run_epoch_inventory": run_epoch_inventory,
            "input_gnss_epoch_count": run_epoch_inventory["input_gnss_epoch_count"],
            "accepted_official_gnss_epoch_count": run_epoch_inventory[
                "accepted_official_gnss_epoch_count"
            ],
            "internal_spp_valid_count": activation["internal_spp_valid_epoch_count"],
            "internal_spp_invalid_count": activation["internal_spp_invalid_epoch_count"],
            "internal_spp_valid_count_source": (
                "full_eligible_epoch_source_exact_probe_spp_status_nonzero"
            ),
            "internal_spp_invalid_count_source": (
                "full_eligible_epoch_source_exact_probe_spp_status_zero"
            ),
            "internal_spp_outcome_conservation_pass": (
                activation["internal_spp_outcome_conservation_pass"]
                and activation["eligible_integer_epoch_count"]
                == run_epoch_inventory["accepted_official_gnss_epoch_count"]
            ),
            "gnss_outage_count_source": "official_GNSS_outage_warning_ledger",
            "one_matlab_process": True,
            "one_recursive_ginav_run": True,
            "epoch_level_parallelism": False,
        }
        native_summary = freeze_native_solution(
            c00_result["native_output_path"], c00_section,
            matlab_result=c00_result, input_counts=input_counts,
            provenance=provenance,
            normalization_root=_stage_dir(stage, "07_NATIVE_OUTPUT_NORMALIZATION"),
        )
        # Source-derived warning counts complete the requested native ledger.
        failure_path = c00_section / "GINAV_BY2_C00_FAILURE_LEDGER.csv"
        with failure_path.open("r", encoding="utf-8", newline="") as handle:
            failures = list(csv.DictReader(handle))
        outage_count = sum("GNSS outage" in row["message"] for row in failures)
        unavailable_count = sum("GNSS unavailable" in row["message"] for row in failures)
        native_summary["gnss_outage_count"] = outage_count
        native_summary["gnss_unavailable_warning_count"] = unavailable_count
        native_summary["other_warning_failure_count"] = (
            len(failures) - outage_count - unavailable_count
        )
        native_summary["warning_ledger_classification_conservation_pass"] = (
            outage_count + unavailable_count
            + native_summary["other_warning_failure_count"] == len(failures)
        )
        native_summary["native_output_status_conservation_pass"] = (
            native_summary["alignment_output_count"]
            + native_summary["internal_spp_fed_lc_update_count"]
            + native_summary["ins_only_propagation_count"]
            == native_summary["row_count"]
        )
        if not (
            native_summary["internal_spp_outcome_conservation_pass"]
            and native_summary["warning_ledger_classification_conservation_pass"]
            and native_summary["native_output_status_conservation_pass"]
        ):
            raise OutputContractError("C00 native count conservation failed")
        native_summary["forbidden_path_audit"] = global_access.audit()
        write_json(c00_section / "GINAV_BY2_C00_NATIVE_SUMMARY.json", native_summary)
    except SourceIdentityError as exc:
        _write_cleanliness(stage, all_cleanliness)
        return finalize(
            "BLOCKED_LC02_GINAV_SOURCE_IDENTITY_MISMATCH",
            detail=str(exc),
        )
    except ForbiddenInputError as exc:
        _write_cleanliness(stage, all_cleanliness)
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
            detail=f"C00 forbidden-input audit failed: {exc}",
        )
    except (OSError, ValueError, TransactionError, MatlabRuntimeError,
            OutputContractError) as exc:
        _write_cleanliness(stage, all_cleanliness)
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
            detail=f"C00 native-output contract failed: {exc}",
        )

    _write_cleanliness(stage, all_cleanliness)
    access_audit = global_access.audit()
    write_json(_stage_dir(stage, "11_REPORT") / "GINAV_FORBIDDEN_INPUT_AUDIT.json", access_audit)
    terminal = str(native_summary["terminal_status"])
    final_report = f"""# GINav 2021 LC02 exact-route transaction

Terminal status: `{terminal}`

The pinned official SPP/INS LC route passed the two-run official sample
regression, GNSS1-only RINEX and Go2 format-2 adapters, literal/source-proven
time gate, and official TDCP alignment probe before the one C00 process was
launched.  Native output was frozen before any reference access.  Trace,
reference, LC01, other methods, Canonical-541, representative cases, and
comparison remained unexecuted.
"""
    (_stage_dir(stage, "11_REPORT") / "LC02_GINAV2021_FINAL_REPORT.md").write_text(
        final_report, encoding="utf-8"
    )
    return finalize(
        terminal,
        extra={
            "BY2_C00_complete": native_summary["BY2_C00_complete"],
            "formal_lc02_admission": native_summary["formal_lc02_admission"],
            "formal_lc02_slot": native_summary["formal_lc02_slot"],
            "official_route_initialized": native_summary["official_route_initialized"],
            "finite_lc_segment_produced": native_summary["finite_lc_segment_produced"],
            "native_summary_path": str(c00_section / "GINAV_BY2_C00_NATIVE_SUMMARY.json"),
            "forbidden_path_audit_pass": access_audit["pass"],
        },
    )
