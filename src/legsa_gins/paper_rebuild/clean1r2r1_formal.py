"""CLEAN1R2R1 fresh auxiliaries, four-method execution, and offline evaluation.

This module deliberately keeps the clean final_v23 15-column IMU/GNSS bundle
immutable.  The maintained CLEAN1 generator is reused only to materialize the
source-backed Raw Doppler and Go2 weak-prior auxiliaries.  Its compatibility
IMU/GNSS products are audit-only and can never be selected by this runner.
"""

from __future__ import annotations

import csv
import bisect
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import time
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .evidence import BY2_TRACE_RELATIVE_PATH, parse_strace_openat_paths
from .final_v23_clean_parity import (
    METHOD_FEATURES,
    active_runtime_config,
    load_clean_bundle,
)
from .formal_generation import generate_formal_clean1_inputs
from .formal_provider import RAW_DOPPLER_ANCHOR_ACTIVE_SHA256
from .manifest import git_code_state, sha256_file, write_json_atomic
from .paths import CleanPaths, guard_path, is_within, load_yaml_mapping
from .subprocess_guard import run_process_group


STAGE_ID = "CLEAN1R2R1_CLEAN_REAL_FINAL_V23_PARITY_AND_FOUR_METHOD_EXECUTION"
PROTOCOL_ID = "CLEAN_REAL_DATA_FINAL_V23"
CASE_ID = "CLEAN1_BY2_CLEAN_NORMAL"
METHOD_ORDER = (
    "single_antenna_EKF",
    "basic_dual_yaw_EKF",
    "strong_dual_yaw_EKF",
    "LegSA_Paper_V1",
)
RUN_DIRECTORIES = (
    "01_single_antenna_EKF",
    "02_basic_dual_yaw_EKF",
    "03_strong_dual_yaw_EKF",
    "04_LegSA_Paper_V1",
)
EVALUATOR_NAV_NAME = "KF_GINS_Navresult.nav"
EVALUATOR_STD_NAME = "KF_GINS_STD.txt"
COUNTER_FIELDS = (
    "position_update_count",
    "receiver_velocity_update_count",
    "dual_yaw_attempt_count",
    "dual_yaw_normal_count",
    "dual_yaw_downweight_count",
    "dual_yaw_reject_count",
    "dual_yaw_accepted_count",
    "raw_doppler_update_count",
    "source_aware_evaluation_count",
    "source_aware_weight_changed_count",
    "go2_roll_pitch_update_count",
    "go2_horizontal_velocity_update_count",
    "fgo_count",
    "qm_count",
    "qa_count",
    "contact_fk_count",
)


class Clean1R2R1FormalError(RuntimeError):
    """The bounded formal chain failed closed."""


def _json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Clean1R2R1FormalError(f"invalid JSON evidence: {source.name}") from exc
    if not isinstance(payload, dict):
        raise Clean1R2R1FormalError(f"JSON evidence is not an object: {source.name}")
    return payload


def _canonical_hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(value), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _is_git_commit(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def validate_active_raw_doppler_anchor(
    path: str | Path,
    reproducible_build: Mapping[str, Any],
) -> str:
    """Bind the rebased active CSV to the frozen current-clean content hash."""

    expected = reproducible_build.get("expected_active_raw_doppler_sha256")
    if expected != RAW_DOPPLER_ANCHOR_ACTIVE_SHA256:
        raise Clean1R2R1FormalError("active Raw Doppler anchor identity drifted")
    actual = sha256_file(path)
    if actual != expected:
        raise Clean1R2R1FormalError("BLOCKED_CLEAN2_BASE_PROVIDER_PARITY_FAILED")
    return actual


def _artifact(root: Path, entry: Mapping[str, Any], role: str) -> Path:
    relative = entry.get("relative_path")
    if not isinstance(relative, str) or relative.startswith("/") or ".." in Path(relative).parts:
        raise Clean1R2R1FormalError(f"unsafe auxiliary artifact path: {role}")
    candidate = (root / relative).resolve(strict=True)
    if root.resolve(strict=True) not in candidate.parents or not candidate.is_file():
        raise Clean1R2R1FormalError(f"auxiliary artifact escaped its root: {role}")
    return candidate


def rebase_auxiliary_time_csv(
    source: str | Path,
    destination: str | Path,
    *,
    offset_seconds: float,
) -> dict[str, Any]:
    """Create an attempt-owned copy on the archived final_v23 time basis.

    The maintained V1 helper writes seconds since the source UTC midnight,
    while exact final_v23 subtracts its archived +08:00 base time.  Only the
    active ``time`` column is rebased; raw-Doppler ``source_time`` and every
    observation/covariance/status field remain byte-identical strings.
    """

    input_path = Path(source).resolve(strict=True)
    output_path = Path(destination)
    if not math.isfinite(offset_seconds) or offset_seconds <= 0.0:
        raise Clean1R2R1FormalError("invalid auxiliary time-basis offset")
    if output_path.exists():
        raise Clean1R2R1FormalError("rebased auxiliary output already exists")
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or ())
        rows = list(reader)
    if not rows or "time" not in fieldnames:
        raise Clean1R2R1FormalError("auxiliary CSV lacks a non-empty time column")
    input_times: list[float] = []
    output_times: list[float] = []
    source_time_before = [row.get("source_time") for row in rows]
    decimal_offset = Decimal(str(offset_seconds))
    for row in rows:
        try:
            original_decimal = Decimal(str(row["time"]))
            rebased_decimal = original_decimal - decimal_offset
            original = float(original_decimal)
            rebased = float(rebased_decimal)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise Clean1R2R1FormalError("auxiliary CSV has an invalid time value") from exc
        if not math.isfinite(original) or not math.isfinite(rebased):
            raise Clean1R2R1FormalError("auxiliary CSV time is non-finite")
        input_times.append(original)
        output_times.append(rebased)
        row["time"] = f"{rebased_decimal:.12f}"
    if any(b <= a for a, b in zip(output_times, output_times[1:])):
        raise Clean1R2R1FormalError("rebased auxiliary time is not strictly increasing")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.name + ".tmp")
    if temporary.exists():
        raise Clean1R2R1FormalError("rebased auxiliary temporary output already exists")
    try:
        with temporary.open("x", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(output_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    source_time_after = [row.get("source_time") for row in rows]
    return {
        "row_count": len(rows),
        "input_time_start_seconds": input_times[0],
        "input_time_end_seconds": input_times[-1],
        "output_time_start_seconds": output_times[0],
        "output_time_end_seconds": output_times[-1],
        "offset_subtracted_seconds": offset_seconds,
        "time_column_only_transformed": True,
        "source_time_column_present": "source_time" in fieldnames,
        "source_time_column_preserved": source_time_before == source_time_after,
        "input_sha256": sha256_file(input_path),
        "output_sha256": sha256_file(output_path),
    }


def _first_column_times(path: Path) -> list[float]:
    times: list[float] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "%")):
            continue
        times.append(float(stripped.replace(",", " ").split()[0]))
    if not times or any(b <= a for a, b in zip(times, times[1:])):
        raise Clean1R2R1FormalError("clean common GNSS time column is invalid")
    return times


def _csv_times(path: Path) -> list[float]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    try:
        times = [float(row["time"]) for row in rows]
    except (KeyError, TypeError, ValueError) as exc:
        raise Clean1R2R1FormalError("active auxiliary time column is invalid") from exc
    if not times or any(b <= a for a, b in zip(times, times[1:])):
        raise Clean1R2R1FormalError("active auxiliary time is not strictly increasing")
    return times


def _nearest_match_count(reference_times: Sequence[float], provider_times: Sequence[float], tolerance: float) -> int:
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise Clean1R2R1FormalError("auxiliary match tolerance is invalid")
    count = 0
    for value in reference_times:
        index = bisect.bisect_left(provider_times, value)
        candidates = []
        if index < len(provider_times):
            candidates.append(abs(provider_times[index] - value))
        if index:
            candidates.append(abs(provider_times[index - 1] - value))
        if candidates and min(candidates) <= tolerance:
            count += 1
    return count


def _clean_time_basis_contract(clean_manifest: Path) -> dict[str, Any]:
    payload = _json(clean_manifest)
    try:
        offset = float(payload["archive_base_time_offset_from_utc_midnight_seconds"])
        base_time = float(payload["base_time_unix_seconds"])
        utc_midnight = float(payload["source_utc_day_midnight_unix_seconds"])
        relative = str(payload["time_audit_relative_path"])
    except (KeyError, TypeError, ValueError) as exc:
        raise Clean1R2R1FormalError("clean input lacks the archived time-basis contract") from exc
    audit_path = (clean_manifest.parent / relative).resolve(strict=True)
    if clean_manifest.parent not in audit_path.parents:
        raise Clean1R2R1FormalError("clean input time audit escaped its attempt root")
    audit = _json(audit_path)
    window = audit.get("runtime_window_seconds")
    if (
        not math.isfinite(offset)
        or abs(offset - 28800.0) > 1.0e-9
        or abs((utc_midnight + offset) - base_time) > 1.0e-6
        or audit.get("archive_base_time_offset_from_utc_midnight_seconds") != offset
        or not isinstance(window, list)
        or len(window) != 2
        or [float(value) for value in window] != [66.0, 340.0]
    ):
        raise Clean1R2R1FormalError("clean input time-basis proof does not match exact final_v23")
    return {
        "source_utc_day_midnight_unix_seconds": utc_midnight,
        "final_v23_base_time_unix_seconds": base_time,
        "offset_subtracted_seconds": offset,
        "runtime_window_seconds": [66.0, 340.0],
        "time_audit_sha256": sha256_file(audit_path),
    }


def auxiliary_generation_plan() -> dict[str, Any]:
    """Return the fixed read/output roles used by the maintained generator."""

    return {
        "actual_raw_read_roles": (
            "gnss1_status",
            "gnss2_status",
            "gnss1_raw",
            "go2_body",
        ),
        "active_auxiliary_roles": (
            "raw_doppler_provider",
            "go2_attitude_prior",
            "go2_horizontal_velocity_prior",
        ),
        "common_solver_base_roles": ("imu_runtime_input", "gnss_runtime_input"),
        "trace_read_during_generation": False,
        "compatibility_generated_imu_gnss_solver_eligible": False,
        "semisynthetic_data_used": False,
    }


def generate_fresh_auxiliaries(
    paths: CleanPaths,
    *,
    clean_input_manifest: str | Path,
    output_root: str | Path,
    expected_code_commit: str,
    provider_protocol: str | Path,
    rtklib_source_root: str | Path | None = None,
    materialize_pinned_rtklib: bool = False,
    timeout_seconds: int = 900,
    generator: Callable[..., dict[str, Any]] = generate_formal_clean1_inputs,
) -> dict[str, Any]:
    """Generate only fresh auxiliaries while retaining the sealed 15-col base."""

    if not _is_git_commit(expected_code_commit):
        raise Clean1R2R1FormalError("expected code-freeze commit is invalid")
    commit_before, dirty_before = git_code_state(paths.code_root)
    if dirty_before or commit_before != expected_code_commit:
        raise Clean1R2R1FormalError("auxiliary generation requires the exact clean code freeze")
    clean = load_clean_bundle(clean_input_manifest)
    common_before = {
        "imu_runtime_input": sha256_file(clean.imu_path),
        "gnss_runtime_input": sha256_file(clean.gnss_path),
    }
    destination = guard_path(
        output_root,
        role="CLEAN1R2R1 auxiliary root",
        allowed_root=paths.clean_root,
    )
    if destination.exists():
        raise Clean1R2R1FormalError("fresh auxiliary root already exists")
    protocol = load_yaml_mapping(provider_protocol)
    generation = protocol.get("provider_generation")
    if not isinstance(generation, Mapping):
        raise Clean1R2R1FormalError("tracked provider-generation contract is missing")
    solver_common = protocol.get("solver_common")
    if not isinstance(solver_common, Mapping):
        raise Clean1R2R1FormalError("tracked solver-common auxiliary contract is missing")
    # V1 is a maintained helper compatibility identity only.  Its generated
    # IMU/GNSS are quarantined below and never become CLEAN1R2R1 solver input.
    generated = generator(
        replace(paths, provider_root=destination),
        expected_code_commit=expected_code_commit,
        rtklib_source_root=rtklib_source_root,
        materialize_pinned_rtklib=materialize_pinned_rtklib,
        timeout_seconds=timeout_seconds,
        provider_generation=dict(generation),
        stage_id="CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION",
        protocol_id="CLEAN1_BY2_CLEAN_NORMAL_V1",
    )
    if generated.get("trace_used_online") is not False or generated.get("semisynthetic_data_used") is not False:
        raise Clean1R2R1FormalError("auxiliary generator reported trace or semisynthetic input")
    artifacts = generated.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise Clean1R2R1FormalError("maintained auxiliary artifact map is missing")
    helper_manifest_path = destination / "CLEAN_INPUT_MANIFEST.json"
    helper_manifest = _json(helper_manifest_path)
    if helper_manifest != generated:
        raise Clean1R2R1FormalError("maintained helper manifest differs from generator result")
    dual_yaw_path = _artifact(
        destination, artifacts["dual_yaw_provider"], "dual_yaw_provider"
    )
    dual_yaw_hash = sha256_file(dual_yaw_path)
    if generated.get("provider_hashes", {}).get("dual_yaw_provider") != dual_yaw_hash:
        raise Clean1R2R1FormalError("maintained helper dual-yaw hash binding is missing")
    active_roles = auxiliary_generation_plan()["active_auxiliary_roles"]
    source_active_paths = {role: _artifact(destination, artifacts[role], role) for role in active_roles}
    time_basis = _clean_time_basis_contract(clean.manifest_path)
    tolerances = {
        "raw_doppler_provider": float(solver_common["raw_doppler_time_tolerance_seconds"]),
        "go2_attitude_prior": float(solver_common["go2_roll_pitch_time_tolerance_seconds"]),
        "go2_horizontal_velocity_prior": float(solver_common["go2_horizontal_velocity_time_tolerance_seconds"]),
    }
    starttime, endtime = time_basis["runtime_window_seconds"]
    common_gnss_times = [
        value for value in _first_column_times(clean.gnss_path)
        if value > starttime and value <= endtime
    ]
    if not common_gnss_times:
        raise Clean1R2R1FormalError("clean final_v23 runtime window has no GNSS candidates")
    rebased_root = destination / "clean_final_v23_time_basis"
    active_paths: dict[str, Path] = {}
    role_time_audits: dict[str, dict[str, Any]] = {}
    for role in active_roles:
        source = source_active_paths[role]
        active = rebased_root / source.name
        audit = rebase_auxiliary_time_csv(
            source,
            active,
            offset_seconds=float(time_basis["offset_subtracted_seconds"]),
        )
        provider_times = _csv_times(active)
        tolerance = tolerances[role]
        match_count = _nearest_match_count(common_gnss_times, provider_times, tolerance)
        audit.update({
            "source_path": str(source),
            "active_path": str(active),
            "active_time_basis": "seconds_since_archived_final_v23_base_time",
            "source_time_basis": "seconds_since_source_utc_midnight",
            "match_tolerance_seconds": tolerance,
            "common_gnss_candidate_count": len(common_gnss_times),
            "common_gnss_match_count": match_count,
            "common_gnss_match_ratio": match_count / len(common_gnss_times),
            "runtime_window_overlap": provider_times[0] <= endtime and provider_times[-1] >= starttime,
        })
        audit["passed"] = bool(
            audit["time_column_only_transformed"]
            and audit["source_time_column_preserved"]
            and audit["runtime_window_overlap"]
            and match_count > 0
        )
        if not audit["passed"]:
            raise Clean1R2R1FormalError(f"auxiliary time-basis activation gate failed: {role}")
        active_paths[role] = active
        role_time_audits[role] = audit
    # Classic-18 consumes the helper's source-backed A1 vector, but on the
    # clean final_v23 time base. Rebase time only; every scientific field stays
    # byte-identical to the helper payload.
    active_dual_yaw_path = rebased_root / "DUAL_YAW_PROVIDER.csv"
    dual_yaw_time_audit = rebase_auxiliary_time_csv(
        dual_yaw_path,
        active_dual_yaw_path,
        offset_seconds=float(time_basis["offset_subtracted_seconds"]),
    )
    dual_yaw_times = _csv_times(active_dual_yaw_path)
    dual_yaw_tolerance = float(generation["dual_yaw_match_tolerance_seconds"])
    dual_yaw_match_count = _nearest_match_count(
        common_gnss_times, dual_yaw_times, dual_yaw_tolerance
    )
    dual_yaw_time_audit.update(
        {
            "source_path": str(dual_yaw_path),
            "active_path": str(active_dual_yaw_path),
            "source_time_basis": "seconds_since_source_utc_midnight",
            "active_time_basis": "seconds_since_archived_final_v23_base_time",
            "match_tolerance_seconds": dual_yaw_tolerance,
            "common_gnss_candidate_count": len(common_gnss_times),
            "common_gnss_match_count": dual_yaw_match_count,
            "runtime_window_overlap": dual_yaw_times[0] <= endtime
            and dual_yaw_times[-1] >= starttime,
        }
    )
    dual_yaw_time_audit["passed"] = bool(
        dual_yaw_time_audit["time_column_only_transformed"]
        and dual_yaw_time_audit["source_time_column_preserved"]
        and dual_yaw_time_audit["runtime_window_overlap"]
        and dual_yaw_match_count > 0
    )
    if not dual_yaw_time_audit["passed"]:
        raise Clean1R2R1FormalError("Classic-18 dual-yaw time-basis activation gate failed")
    time_basis["source_time_basis"] = "seconds_since_source_utc_midnight"
    time_basis["active_time_basis"] = "seconds_since_archived_final_v23_base_time"
    time_basis["common_gnss_candidate_count"] = len(common_gnss_times)
    time_basis["roles"] = role_time_audits
    time_basis["passed"] = True
    active_hashes = {role: sha256_file(path) for role, path in active_paths.items()}
    common_after = {
        "imu_runtime_input": sha256_file(clean.imu_path),
        "gnss_runtime_input": sha256_file(clean.gnss_path),
    }
    if common_before != common_after:
        raise Clean1R2R1FormalError("sealed clean final_v23 common input changed during auxiliary generation")
    commit_after, dirty_after = git_code_state(paths.code_root)
    if dirty_after or commit_after != expected_code_commit:
        raise Clean1R2R1FormalError("code state changed during auxiliary generation")
    raw = generated.get("raw_doppler_backend")
    if not isinstance(raw, Mapping) or raw.get("raw_doppler_backend_lineage_proven") is not True:
        raise Clean1R2R1FormalError("fresh Raw Doppler backend lineage is not proven")
    reproducible_build = raw.get("raw_doppler_reproducible_build")
    if not isinstance(reproducible_build, Mapping):
        raise Clean1R2R1FormalError(
            "fresh Raw Doppler reproducible-build contract is missing"
        )
    active_raw_hash = validate_active_raw_doppler_anchor(
        active_paths["raw_doppler_provider"], reproducible_build
    )
    if active_hashes["raw_doppler_provider"] != active_raw_hash:
        raise Clean1R2R1FormalError("active Raw Doppler hash binding changed")
    role_time_audits["raw_doppler_provider"].update(
        {
            "expected_active_sha256": RAW_DOPPLER_ANCHOR_ACTIVE_SHA256,
            "active_hash_parity": True,
        }
    )
    actual_reads = generated.get("actual_source_read_set")
    if not isinstance(actual_reads, list) or len(actual_reads) != 4:
        raise Clean1R2R1FormalError("auxiliary actual raw read set is not the fixed four-source set")
    if any("trace" in str(row.get("relative_path", "")).casefold() for row in actual_reads if isinstance(row, Mapping)):
        raise Clean1R2R1FormalError("trace entered fresh auxiliary generation")
    payload = {
        "schema_version": "paper_rebuild.clean1r2r1_auxiliary_bundle.v1",
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        "case_id": CASE_ID,
        "data_mode": "real_by2_raw",
        "code_freeze_commit": expected_code_commit,
        "clean_input_manifest_path": str(clean.manifest_path),
        "clean_input_manifest_sha256": sha256_file(clean.manifest_path),
        "common_solver_base": {
            "imu_runtime_input": {"path": str(clean.imu_path), "sha256": common_after["imu_runtime_input"]},
            "gnss_runtime_input": {"path": str(clean.gnss_path), "sha256": common_after["gnss_runtime_input"], "columns": 15},
        },
        "auxiliary_artifacts": {
            role: {"path": str(path), "sha256": active_hashes[role]}
            for role, path in active_paths.items()
        },
        "auxiliary_time_basis": time_basis,
        "raw_source_hashes": generated.get("raw_source_hashes"),
        "actual_source_read_set": actual_reads,
        "raw_doppler_backend": dict(raw),
        "compatibility_helper_identity": "maintained_CLEAN1_V1_auxiliary_generator",
        "classic18_dual_yaw_provider": {
            "path": str(active_dual_yaw_path),
            "sha256": sha256_file(active_dual_yaw_path),
            "helper_source_path": str(dual_yaw_path),
            "helper_source_sha256": dual_yaw_hash,
            "helper_manifest_path": str(helper_manifest_path),
            "helper_manifest_sha256": sha256_file(helper_manifest_path),
            "helper_provider_bundle_hash": generated["provider_bundle_hash"],
            "generator_config_hash": generated["generator_config_hash"],
            "generator_code_commit": generated["generator_code_commit"],
            "source_backed": True,
            "solver_eligible": False,
            "time_basis_audit": dual_yaw_time_audit,
        },
        "compatibility_generated_imu_gnss": {
            "solver_eligible": False,
            "reason": "CLEAN1R2R1 uses sealed FINAL_V23_CLEAN_FRESH 15-column common base",
        },
        "compatibility_helper_auxiliaries": {
            role: {
                "path": str(source_active_paths[role]),
                "sha256": sha256_file(source_active_paths[role]),
                "solver_eligible": False,
                "reason": "UTC-midnight time basis; preserved as helper output before deterministic rebase",
            }
            for role in active_roles
        },
        "trace_open_count": None,
        "trace_open_audit_sealed": False,
        "trace_used_online": False,
        "trace_read_during_generation": False,
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "legacy_input_payload_used": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "old_runtime_input_count": 0,
        "plan": auxiliary_generation_plan(),
    }
    payload["bundle_hash"] = _canonical_hash(
        {
            **common_after,
            **active_hashes,
            "classic18_dual_yaw_provider": sha256_file(active_dual_yaw_path),
            "raw_doppler_backend": _canonical_hash(dict(raw)),
            "auxiliary_time_basis": _canonical_hash(time_basis),
        }
    )
    manifest_path = write_json_atomic(destination / "CLEAN1R2R1_AUXILIARY_MANIFEST.json", payload)
    with (destination / "CLEAN1R2R1_AUXILIARY_SOURCE_LEDGER.csv").open(
        "x", encoding="utf-8", newline=""
    ) as handle:
        fields = ["read_order", "relative_path", "role", "expected_sha256", "trace_source"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, row in enumerate(actual_reads, start=1):
            writer.writerow({
                "read_order": index,
                "relative_path": row["relative_path"],
                "role": row["role"],
                "expected_sha256": row["expected_sha256"],
                "trace_source": False,
            })
    payload["manifest_path"] = str(manifest_path)
    return payload


def seal_auxiliary_file_open_audit(
    *,
    auxiliary_manifest: str | Path,
    strace_path: str | Path,
    raw_root: str | Path,
    code_root: str | Path,
) -> dict[str, Any]:
    """Close actual raw opens after the generator process exits under strace."""

    manifest_path = Path(auxiliary_manifest).resolve(strict=True)
    payload = _json(manifest_path)
    if payload.get("trace_open_audit_sealed") is not False or payload.get("trace_open_count") is not None:
        raise Clean1R2R1FormalError("auxiliary file-open audit was already sealed")
    raw = Path(raw_root).resolve(strict=True)
    opened = parse_strace_openat_paths(strace_path, cwd=code_root)
    raw_opened = [path for path in opened if is_within(path, raw)]
    actual_reads = payload.get("actual_source_read_set")
    if not isinstance(actual_reads, list):
        raise Clean1R2R1FormalError("auxiliary actual source ledger is missing")
    expected = {
        str(row["relative_path"]): (raw / str(row["relative_path"])).resolve(strict=True)
        for row in actual_reads
        if isinstance(row, Mapping)
    }
    counts = {
        relative: sum(path == source for path in raw_opened)
        for relative, source in expected.items()
    }
    unexpected = sorted(
        path.relative_to(raw).as_posix()
        for path in set(raw_opened)
        if path not in set(expected.values())
    )
    trace_path = (raw / BY2_TRACE_RELATIVE_PATH).resolve(strict=True)
    trace_count = sum(path == trace_path for path in raw_opened)
    missing = sorted(relative for relative, count in counts.items() if count == 0)
    audit = {
        "schema_version": "paper_rebuild.clean1r2r1_auxiliary_file_open_audit.v1",
        "strace_sha256": sha256_file(strace_path),
        "expected_raw_open_counts": counts,
        "missing_expected_raw_opens": missing,
        "unexpected_raw_root_relative_paths": unexpected,
        "trace_open_count": trace_count,
        "trace_opened_by_auxiliary_generator": trace_count > 0,
        "passed": not missing and not unexpected and trace_count == 0,
    }
    if not audit["passed"]:
        raise Clean1R2R1FormalError("auxiliary generator file-open audit failed")
    audit_path = write_json_atomic(manifest_path.parent / "CLEAN1R2R1_AUXILIARY_FILE_OPEN_AUDIT.json", audit)
    payload["trace_open_count"] = 0
    payload["trace_open_audit_sealed"] = True
    payload["file_open_audit_sha256"] = sha256_file(audit_path)
    payload["file_open_trace_sha256"] = sha256_file(strace_path)
    write_json_atomic(manifest_path, payload)
    return audit


def validate_auxiliary_bundle(path: str | Path) -> dict[str, Any]:
    payload = _json(path)
    expected = {
        "schema_version": "paper_rebuild.clean1r2r1_auxiliary_bundle.v1",
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        "case_id": CASE_ID,
        "data_mode": "real_by2_raw",
        "trace_open_count": 0,
        "trace_open_audit_sealed": True,
        "trace_used_online": False,
        "trace_read_during_generation": False,
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "legacy_input_payload_used": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "old_runtime_input_count": 0,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise Clean1R2R1FormalError("auxiliary evidence boundary mismatch")
    audit_path = Path(path).resolve(strict=True).parent / "CLEAN1R2R1_AUXILIARY_FILE_OPEN_AUDIT.json"
    if not audit_path.is_file() or sha256_file(audit_path) != payload.get("file_open_audit_sha256"):
        raise Clean1R2R1FormalError("auxiliary file-open audit is missing or changed")
    for section, roles in (
        ("common_solver_base", ("imu_runtime_input", "gnss_runtime_input")),
        ("auxiliary_artifacts", auxiliary_generation_plan()["active_auxiliary_roles"]),
    ):
        entries = payload.get(section)
        if not isinstance(entries, Mapping) or set(entries) != set(roles):
            raise Clean1R2R1FormalError(f"auxiliary manifest {section} role mismatch")
        for role in roles:
            entry = entries[role]
            source = Path(str(entry.get("path", ""))).resolve(strict=True)
            if sha256_file(source) != entry.get("sha256"):
                raise Clean1R2R1FormalError(f"auxiliary/common artifact changed: {role}")
    if payload["common_solver_base"]["gnss_runtime_input"].get("columns") != 15:
        raise Clean1R2R1FormalError("formal common GNSS is not the sealed 15-column input")
    time_basis = payload.get("auxiliary_time_basis")
    if not isinstance(time_basis, Mapping) or time_basis.get("passed") is not True:
        raise Clean1R2R1FormalError("auxiliary time-basis audit is missing or failed")
    try:
        offset = float(time_basis["offset_subtracted_seconds"])
        utc_midnight = float(time_basis["source_utc_day_midnight_unix_seconds"])
        final_base = float(time_basis["final_v23_base_time_unix_seconds"])
        window = [float(value) for value in time_basis["runtime_window_seconds"]]
    except (KeyError, TypeError, ValueError) as exc:
        raise Clean1R2R1FormalError("auxiliary time-basis audit fields are invalid") from exc
    if (
        abs(offset - 28800.0) > 1.0e-9
        or abs((utc_midnight + offset) - final_base) > 1.0e-6
        or window != [66.0, 340.0]
        or time_basis.get("source_time_basis") != "seconds_since_source_utc_midnight"
        or time_basis.get("active_time_basis") != "seconds_since_archived_final_v23_base_time"
    ):
        raise Clean1R2R1FormalError("auxiliary time basis is not exact clean final_v23")
    common_gnss = Path(payload["common_solver_base"]["gnss_runtime_input"]["path"]).resolve(strict=True)
    common_times = [value for value in _first_column_times(common_gnss) if value > window[0] and value <= window[1]]
    if int(time_basis.get("common_gnss_candidate_count", -1)) != len(common_times):
        raise Clean1R2R1FormalError("auxiliary time-basis GNSS candidate count changed")
    role_audits = time_basis.get("roles")
    expected_tolerances = {
        "raw_doppler_provider": 0.05,
        "go2_attitude_prior": 0.02,
        "go2_horizontal_velocity_prior": 0.08,
    }
    helper_entries = payload.get("compatibility_helper_auxiliaries")
    if not isinstance(role_audits, Mapping) or set(role_audits) != set(expected_tolerances):
        raise Clean1R2R1FormalError("auxiliary role time-basis audit mismatch")
    if not isinstance(helper_entries, Mapping) or set(helper_entries) != set(expected_tolerances):
        raise Clean1R2R1FormalError("compatibility helper auxiliary map mismatch")
    for role, tolerance in expected_tolerances.items():
        audit = role_audits[role]
        if not isinstance(audit, Mapping) or audit.get("passed") is not True:
            raise Clean1R2R1FormalError(f"auxiliary role time-basis gate failed: {role}")
        source = Path(str(helper_entries[role].get("path", ""))).resolve(strict=True)
        active = Path(str(payload["auxiliary_artifacts"][role].get("path", ""))).resolve(strict=True)
        if (
            helper_entries[role].get("solver_eligible") is not False
            or sha256_file(source) != helper_entries[role].get("sha256")
            or sha256_file(source) != audit.get("input_sha256")
            or sha256_file(active) != audit.get("output_sha256")
            or str(source) != audit.get("source_path")
            or str(active) != audit.get("active_path")
            or abs(float(audit.get("offset_subtracted_seconds", math.nan)) - offset) > 1.0e-9
            or abs(float(audit.get("match_tolerance_seconds", math.nan)) - tolerance) > 1.0e-12
            or audit.get("time_column_only_transformed") is not True
            or audit.get("source_time_column_preserved") is not True
            or audit.get("runtime_window_overlap") is not True
        ):
            raise Clean1R2R1FormalError(f"auxiliary role rebase provenance mismatch: {role}")
        if role == "raw_doppler_provider":
            raw_backend = payload.get("raw_doppler_backend")
            reproducible_build = (
                raw_backend.get("raw_doppler_reproducible_build")
                if isinstance(raw_backend, Mapping)
                else None
            )
            if not isinstance(reproducible_build, Mapping):
                raise Clean1R2R1FormalError(
                    "active Raw Doppler reproducible-build contract is missing"
                )
            active_hash = validate_active_raw_doppler_anchor(
                active, reproducible_build
            )
            if (
                audit.get("expected_active_sha256")
                != RAW_DOPPLER_ANCHOR_ACTIVE_SHA256
                or audit.get("active_hash_parity") is not True
                or active_hash != payload["auxiliary_artifacts"][role].get("sha256")
            ):
                raise Clean1R2R1FormalError(
                    "active Raw Doppler parity audit is incomplete"
                )
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            source_reader = csv.DictReader(handle)
            source_fields = list(source_reader.fieldnames or ())
            source_rows = list(source_reader)
        with active.open("r", encoding="utf-8-sig", newline="") as handle:
            active_reader = csv.DictReader(handle)
            active_fields = list(active_reader.fieldnames or ())
            active_rows = list(active_reader)
        if source_fields != active_fields or len(source_rows) != len(active_rows):
            raise Clean1R2R1FormalError(f"auxiliary role rebase schema changed: {role}")
        for source_row, active_row in zip(source_rows, active_rows):
            for field in source_fields:
                if field == "time":
                    if abs((float(source_row[field]) - offset) - float(active_row[field])) > 1.0e-9:
                        raise Clean1R2R1FormalError(f"auxiliary role time rebase changed: {role}")
                elif source_row[field] != active_row[field]:
                    raise Clean1R2R1FormalError(f"auxiliary role non-time field changed: {role}/{field}")
        active_times = _csv_times(active)
        match_count = _nearest_match_count(common_times, active_times, tolerance)
        if (
            match_count <= 0
            or match_count != int(audit.get("common_gnss_match_count", -1))
            or len(active_times) != int(audit.get("row_count", -1))
            or abs(active_times[0] - float(audit.get("output_time_start_seconds", math.nan))) > 1.0e-9
            or abs(active_times[-1] - float(audit.get("output_time_end_seconds", math.nan))) > 1.0e-9
        ):
            raise Clean1R2R1FormalError(f"auxiliary role activation coverage changed: {role}")
    dual = payload.get("classic18_dual_yaw_provider")
    if dual is None:
        # Historical CLEAN1R2R1 bundles predate the CLEAN2-only active dual
        # sidecar. They remain valid current structural evidence, but the
        # CLEAN2 case-provider gate separately requires the new binding.
        expected_bundle = _canonical_hash(
            {
                **{
                    role: payload["common_solver_base"][role]["sha256"]
                    for role in ("imu_runtime_input", "gnss_runtime_input")
                },
                **{
                    role: payload["auxiliary_artifacts"][role]["sha256"]
                    for role in auxiliary_generation_plan()["active_auxiliary_roles"]
                },
                "raw_doppler_backend": _canonical_hash(dict(payload["raw_doppler_backend"])),
                "auxiliary_time_basis": _canonical_hash(dict(time_basis)),
            }
        )
        if payload.get("bundle_hash") != expected_bundle:
            raise Clean1R2R1FormalError("Historical auxiliary bundle hash no longer closes")
        return payload
    if not isinstance(dual, Mapping) or dual.get("source_backed") is not True:
        raise Clean1R2R1FormalError("Classic-18 active dual-yaw binding is missing")
    dual_source = Path(str(dual.get("helper_source_path") or "")).resolve(strict=True)
    dual_active = Path(str(dual.get("path") or "")).resolve(strict=True)
    dual_audit = dual.get("time_basis_audit")
    if (
        not isinstance(dual_audit, Mapping)
        or dual_audit.get("passed") is not True
        or dual.get("solver_eligible") is not False
        or sha256_file(dual_source) != dual.get("helper_source_sha256")
        or sha256_file(dual_active) != dual.get("sha256")
        or sha256_file(dual_source) != dual_audit.get("input_sha256")
        or sha256_file(dual_active) != dual_audit.get("output_sha256")
        or str(dual_source) != dual_audit.get("source_path")
        or str(dual_active) != dual_audit.get("active_path")
        or abs(float(dual_audit.get("offset_subtracted_seconds", math.nan)) - offset) > 1.0e-9
        or dual_audit.get("time_column_only_transformed") is not True
        or dual_audit.get("source_time_column_preserved") is not True
    ):
        raise Clean1R2R1FormalError("Classic-18 dual-yaw rebase provenance mismatch")
    with dual_source.open("r", encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    with dual_active.open("r", encoding="utf-8-sig", newline="") as handle:
        active_rows = list(csv.DictReader(handle))
    if len(source_rows) != len(active_rows) or not source_rows:
        raise Clean1R2R1FormalError("Classic-18 dual-yaw rebase row count changed")
    for source_row, active_row in zip(source_rows, active_rows):
        if set(source_row) != set(active_row):
            raise Clean1R2R1FormalError("Classic-18 dual-yaw rebase schema changed")
        for field in source_row:
            if field == "time":
                if abs((float(source_row[field]) - offset) - float(active_row[field])) > 1.0e-9:
                    raise Clean1R2R1FormalError("Classic-18 dual-yaw time rebase changed")
            elif source_row[field] != active_row[field]:
                raise Clean1R2R1FormalError("Classic-18 dual-yaw non-time field changed")
    dual_times = _csv_times(dual_active)
    dual_tolerance = float(dual_audit.get("match_tolerance_seconds", math.nan))
    if (
        _nearest_match_count(common_times, dual_times, dual_tolerance)
        != int(dual_audit.get("common_gnss_match_count", -1))
        or len(dual_times) != int(dual_audit.get("row_count", -1))
    ):
        raise Clean1R2R1FormalError("Classic-18 dual-yaw activation coverage changed")
    expected_bundle = _canonical_hash(
        {
            **{
                role: payload["common_solver_base"][role]["sha256"]
                for role in ("imu_runtime_input", "gnss_runtime_input")
            },
            **{
                role: payload["auxiliary_artifacts"][role]["sha256"]
                for role in auxiliary_generation_plan()["active_auxiliary_roles"]
            },
            "classic18_dual_yaw_provider": dual["sha256"],
            "raw_doppler_backend": _canonical_hash(dict(payload["raw_doppler_backend"])),
            "auxiliary_time_basis": _canonical_hash(dict(time_basis)),
        }
    )
    if payload.get("bundle_hash") != expected_bundle:
        raise Clean1R2R1FormalError("Auxiliary bundle hash no longer closes")
    return payload


def _solver_extra_config(auxiliary: Mapping[str, Any], solver_common: Mapping[str, Any]) -> dict[str, Any]:
    raw = auxiliary["raw_doppler_backend"]
    config: dict[str, Any] = {
        "raw_doppler_factor_source": raw["raw_doppler_backend_id"],
        "raw_doppler_backend_id": raw["raw_doppler_backend_id"],
        "raw_doppler_backend_source_files": json.dumps(raw["raw_doppler_backend_source_files"], sort_keys=True),
        "raw_doppler_backend_source_hashes": json.dumps(raw["raw_doppler_backend_source_hashes"], sort_keys=True),
        "helper_executable_hash": raw["helper_executable_hash"],
        "obs_source_hash": raw["obs_source_hash"],
        "nav_source_hash": raw["nav_source_hash"],
        "conversion_config_hash": raw["conversion_config_hash"],
        "covariance_policy": raw["covariance_policy"],
        "raw_doppler_min_sat": int(solver_common["raw_doppler_min_sat"]),
        "raw_doppler_mode": solver_common["raw_doppler_mode"],
        "raw_doppler_time_tolerance_sec": solver_common["raw_doppler_time_tolerance_seconds"],
        "raw_doppler_residual_gate_mps": solver_common["raw_doppler_residual_gate_mps"],
        "raw_doppler_R_scale": solver_common["raw_doppler_R_scale"],
        "rtklib_position_solution_used_as_solver_input": False,
        "nav_pvt_velocity_used_as_raw_doppler": False,
        "gnss_velocity_used_as_raw_doppler": False,
        "source_aware_policy_version": solver_common["source_aware_policy"],
        "source_aware_mode": solver_common["source_aware_mode"],
        "go2_attitude_prior_std_roll_deg": solver_common["go2_roll_pitch_std_deg"],
        "go2_attitude_prior_std_pitch_deg": solver_common["go2_roll_pitch_std_deg"],
        "go2_attitude_prior_time_tolerance_sec": solver_common["go2_roll_pitch_time_tolerance_seconds"],
        "go2_attitude_prior_sourceaware": solver_common["go2_attitude_prior_source_aware_enabled"],
        "go2_velocity_prior_time_tolerance_sec": solver_common["go2_horizontal_velocity_time_tolerance_seconds"],
        "go2_horizontal_velocity_prior_std_scale": solver_common["go2_horizontal_velocity_std_scale"],
        "go2_horizontal_velocity_prior_source_aware_enabled": solver_common["go2_horizontal_velocity_source_aware_enabled"],
        "go2_horizontal_velocity_adaptive_std_enabled": solver_common["go2_horizontal_velocity_adaptive_std_enabled"],
        "go2_position_prior_enabled": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
    }
    direct = (
        "source_aware_max_R_scale", "source_aware_global_cap",
        "source_aware_use_innovation_covariance", "source_aware_deadband_normalized",
        "source_aware_moderate_normalized", "source_aware_strong_normalized",
        "source_aware_receiver_position_cap", "source_aware_receiver_velocity_cap",
        "source_aware_dual_yaw_cap", "source_aware_raw_doppler_cap",
        "source_aware_go2_attitude_cap", "source_aware_go2_horizontal_velocity_cap",
        "source_aware_reject_extreme", "source_aware_no_R_shrink",
        "source_aware_trace_enabled", "source_aware_enable_rolling_innovation_baseline",
        "source_aware_rolling_window_size", "source_aware_rolling_mad_floor",
        "source_aware_method_family", "source_aware_method_k0", "source_aware_method_k1",
        "source_aware_method_c", "source_aware_method_alpha", "source_aware_method_phi",
        "source_aware_method_base_gain",
    )
    for field in direct:
        config[field] = solver_common[field]
    sources = solver_common.get("source_aware_sources")
    if not isinstance(sources, Mapping):
        raise Clean1R2R1FormalError("source-aware per-source contract is missing")
    for source, source_config in sources.items():
        if not isinstance(source_config, Mapping):
            raise Clean1R2R1FormalError("source-aware per-source contract is invalid")
        for field in ("enabled", "lsim_enabled", "oim_enabled"):
            config[f"source_aware_{source}_{field}"] = source_config[field]
    return config


def normalize_runtime_config(text: str) -> str:
    """Remove only run/output identity for strong-vs-parity contract comparison."""

    ignored = {"outputpath", "run_id", "run_label"}
    rows = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key = line.split(":", 1)[0].strip()
        if key not in ignored:
            rows.append(line.strip())
    return "\n".join(sorted(rows)) + "\n"


def module_counters(manifest: Mapping[str, Any]) -> dict[str, int]:
    def number(field: str) -> int:
        value = manifest.get(field, 0)
        if isinstance(value, bool):
            raise Clean1R2R1FormalError(f"invalid boolean module counter: {field}")
        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise Clean1R2R1FormalError(f"invalid module counter: {field}") from exc
        if result < 0:
            raise Clean1R2R1FormalError(f"negative module counter: {field}")
        return result

    normal = number("yaw_NORMAL")
    downweight = number("yaw_DOWNWEIGHT")
    reject = number("yaw_REJECT")
    attempt = number("dual_yaw_attempt_count") if "dual_yaw_attempt_count" in manifest else number("yaw_update_count")
    accepted = number("dual_yaw_accepted_count") if "dual_yaw_accepted_count" in manifest else number("dual_yaw_update_count")
    if attempt != normal + downweight + reject:
        raise Clean1R2R1FormalError("dual-yaw action counts do not close")
    if accepted != normal + downweight:
        raise Clean1R2R1FormalError("dual-yaw accepted count does not close")
    counters = {
        "position_update_count": number("position_update_count"),
        "receiver_velocity_update_count": number("receiver_velocity_update_count"),
        "dual_yaw_attempt_count": attempt,
        "dual_yaw_normal_count": normal,
        "dual_yaw_downweight_count": downweight,
        "dual_yaw_reject_count": reject,
        "dual_yaw_accepted_count": accepted,
        "raw_doppler_update_count": number("raw_doppler_update_count"),
        "source_aware_evaluation_count": number("source_aware_evaluation_count"),
        "source_aware_weight_changed_count": number("source_aware_weight_changed_count"),
        "go2_roll_pitch_update_count": number("go2_roll_pitch_update_count"),
        "go2_horizontal_velocity_update_count": number("go2_horizontal_velocity_update_count"),
        "fgo_count": number("selected_fgo_feedback_update_count") + number("nine_factor_fgo_update_count"),
        "qm_count": number("multi_state_qm_update_count"),
        "qa_count": number("qa_fallback_count"),
        "contact_fk_count": number("contact_fk_update_count"),
    }
    if set(counters) != set(COUNTER_FIELDS):
        raise AssertionError("internal counter registry drift")
    return counters


def _validate_run_manifest(manifest: Mapping[str, Any], method_id: str, run_id: str) -> dict[str, int]:
    expected = METHOD_FEATURES[method_id]
    feature_values = {
        "dual": manifest.get("enable_dual_yaw_update"),
        "receiver": manifest.get("enable_receiver_velocity_update"),
        "raw": manifest.get("enable_raw_doppler"),
        "source_aware": manifest.get("source_aware_weighting_enabled"),
        "go2_roll_pitch": manifest.get("go2_attitude_weak_prior_enabled"),
        "go2_horizontal": manifest.get("go2_horizontal_velocity_prior_enabled"),
    }
    fixed = {
        "clean_final_v23_parity_mode": True,
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        "case_id": CASE_ID,
        "data_mode": "real_by2_raw",
        "algorithm_id": method_id,
        "run_id": run_id,
        "trace_used_online": False,
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0,
    }
    if feature_values != expected or any(manifest.get(key) != value for key, value in fixed.items()):
        raise Clean1R2R1FormalError(f"formal solver manifest mismatch: {method_id}")
    counters = module_counters(manifest)
    if method_id != "LegSA_Paper_V1" and any(counters[field] != 0 for field in (
        "raw_doppler_update_count", "source_aware_evaluation_count",
        "source_aware_weight_changed_count", "go2_roll_pitch_update_count",
        "go2_horizontal_velocity_update_count",
    )):
        raise Clean1R2R1FormalError("proposed-module counter is nonzero outside LegSA")
    if method_id == "LegSA_Paper_V1" and any(counters[field] <= 0 for field in (
        "raw_doppler_update_count", "source_aware_evaluation_count",
        "go2_roll_pitch_update_count", "go2_horizontal_velocity_update_count",
    )):
        raise Clean1R2R1FormalError("LegSA proposed modules were not effectively activated")
    if any(counters[field] != 0 for field in ("fgo_count", "qm_count", "qa_count", "contact_fk_count")):
        raise Clean1R2R1FormalError("out-of-scope module counter is nonzero")
    return counters


def _assert_parity_gate(report: Mapping[str, Any]) -> None:
    if (
        report.get("active_port_clean_final_v23_parity") is not True
        or report.get("strong_equals_clean_final_v23") is not True
        or report.get("terminal_status") != "PASS_FINAL_V23_CLEAN_PARITY_ANCHOR"
        or report.get("trace_opened") is not False
    ):
        raise Clean1R2R1FormalError("four methods are forbidden before clean final_v23 parity passes")


def run_four_methods(
    *,
    repo_root: str | Path,
    executable: str | Path,
    clean_input_manifest: str | Path,
    auxiliary_manifest: str | Path,
    parity_report: str | Path,
    parity_active_config: str | Path,
    provider_protocol: str | Path,
    runtime_root: str | Path,
    code_freeze_commit: str,
    timeout_seconds: int = 1800,
    command_runner: Callable[..., Any] = run_process_group,
) -> dict[str, Any]:
    """Run exactly four separate processes and seal every output before return."""

    if not _is_git_commit(code_freeze_commit):
        raise Clean1R2R1FormalError("code-freeze commit is invalid")
    repo = Path(repo_root).resolve(strict=True)
    commit_before, dirty_before = git_code_state(repo)
    if dirty_before or commit_before != code_freeze_commit:
        raise Clean1R2R1FormalError("four methods require the exact clean code freeze")
    binary = Path(executable).resolve(strict=True)
    clean = load_clean_bundle(clean_input_manifest)
    auxiliary = validate_auxiliary_bundle(auxiliary_manifest)
    parity = _json(parity_report)
    _assert_parity_gate(parity)
    if parity.get("active_code_commit") != code_freeze_commit:
        raise Clean1R2R1FormalError("passing parity report is not bound to the code freeze")
    if parity.get("active_executable_sha256") != sha256_file(binary):
        raise Clean1R2R1FormalError("formal executable differs from the passing parity executable")
    if parity.get("same_fresh_imu_sha256") != sha256_file(clean.imu_path) or parity.get("same_fresh_gnss_sha256") != sha256_file(clean.gnss_path):
        raise Clean1R2R1FormalError("formal common base differs from the passing parity anchor")
    if auxiliary.get("code_freeze_commit") != code_freeze_commit:
        raise Clean1R2R1FormalError("auxiliaries were not generated at the code freeze")
    common = auxiliary["common_solver_base"]
    if common["imu_runtime_input"]["sha256"] != sha256_file(clean.imu_path) or common["gnss_runtime_input"]["sha256"] != sha256_file(clean.gnss_path):
        raise Clean1R2R1FormalError("auxiliary bundle common base differs from the parity input")
    protocol = load_yaml_mapping(provider_protocol)
    solver_common = protocol.get("solver_common")
    if not isinstance(solver_common, Mapping):
        raise Clean1R2R1FormalError("tracked solver-common auxiliary contract is missing")
    root = Path(runtime_root)
    if root.exists():
        raise Clean1R2R1FormalError("fresh four-method runtime root already exists")
    root.mkdir(parents=True)
    extra = _solver_extra_config(auxiliary, solver_common)
    aux_paths = {
        "raw_doppler": auxiliary["auxiliary_artifacts"]["raw_doppler_provider"]["path"],
        "go2_roll_pitch": auxiliary["auxiliary_artifacts"]["go2_attitude_prior"]["path"],
        "go2_horizontal_velocity": auxiliary["auxiliary_artifacts"]["go2_horizontal_velocity_prior"]["path"],
    }
    parity_config_text = Path(parity_active_config).resolve(strict=True).read_text(encoding="utf-8")
    index_rows: list[dict[str, Any]] = []
    hash_rows: list[dict[str, Any]] = []
    strong_counters: dict[str, int] | None = None
    for order, (method_id, directory) in enumerate(zip(METHOD_ORDER, RUN_DIRECTORIES), start=1):
        output = root / directory
        output.mkdir()
        config = output / "CLEAN1R2R1_RUNTIME_CONFIG.yaml"
        config_text = active_runtime_config(
            clean.imu_path,
            clean.gnss_path,
            output,
            method_id=method_id,
            auxiliary_paths=aux_paths if method_id == "LegSA_Paper_V1" else {},
            extra_config=extra if method_id == "LegSA_Paper_V1" else {},
            run_id=directory,
        )
        config.write_text(config_text, encoding="utf-8")
        if method_id == "strong_dual_yaw_EKF" and normalize_runtime_config(config_text) != normalize_runtime_config(parity_config_text):
            raise Clean1R2R1FormalError("strong runtime contract differs from the passing active parity config")
        logs = output / "logs"
        logs.mkdir()
        command = [
            str(binary), "--config", str(config), "--output-dir", str(output),
            "--debug-update-timeline", "--debug-output-dir", str(output),
            "--debug-max-rows", "1000000",
        ]
        started = time.monotonic()
        completed = command_runner(
            command,
            cwd=repo,
            timeout_seconds=timeout_seconds,
            timeout_message="four-method solver timeout; process group terminated",
            launch_failure_message="four-method solver launch failure",
        )
        (logs / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (logs / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise Clean1R2R1FormalError(f"BLOCKED_CLEAN1R2R1_FOUR_METHOD_EXECUTION_FAILED: {method_id} returncode={completed.returncode}")
        solver_manifest_path = output / "RUN_MANIFEST.json"
        nav = output / EVALUATOR_NAV_NAME
        std = output / EVALUATOR_STD_NAME
        update_trace = output / "PORT_GNSS_UPDATE_TRACE.csv"
        if not all(path.is_file() for path in (solver_manifest_path, nav, std, update_trace)):
            raise Clean1R2R1FormalError(f"formal evaluator-compatible output set incomplete: {method_id}")
        solver_manifest = _json(solver_manifest_path)
        counters = _validate_run_manifest(solver_manifest, method_id, directory)
        if method_id == "strong_dual_yaw_EKF":
            expected = parity.get("counter_audit", {}).get("active")
            if not isinstance(expected, Mapping):
                raise Clean1R2R1FormalError("passing parity report lacks strong counters")
            comparison = {
                field: counters[field]
                for field in (
                    "position_update_count", "receiver_velocity_update_count",
                    "dual_yaw_attempt_count", "dual_yaw_normal_count",
                    "dual_yaw_downweight_count", "dual_yaw_reject_count",
                    "dual_yaw_accepted_count",
                )
            }
            if comparison != {field: int(expected[field]) for field in comparison}:
                raise Clean1R2R1FormalError("strong counters differ from clean final_v23 parity anchor")
            strong_counters = counters
        wrapper = {
            "schema_version": "paper_rebuild.clean1r2r1_formal_run.v1",
            "stage_id": STAGE_ID,
            "protocol_id": PROTOCOL_ID,
            "case_id": CASE_ID,
            "data_mode": "real_by2_raw",
            "method_order": order,
            "algorithm_id": method_id,
            "run_id": directory,
            "code_freeze_commit": code_freeze_commit,
            "executable_sha256": sha256_file(binary),
            "clean_input_manifest_sha256": sha256_file(clean.manifest_path),
            "common_imu_sha256": sha256_file(clean.imu_path),
            "common_gnss_sha256": sha256_file(clean.gnss_path),
            "runtime_config_sha256": sha256_file(config),
            "solver_manifest_sha256": sha256_file(solver_manifest_path),
            "module_counters": counters,
            "runtime_seconds": time.monotonic() - started,
            "trace_used_online": False,
            "legacy_solver_input": False,
            "terminal_success": True,
        }
        wrapper_path = write_json_atomic(output / "CLEAN1R2R1_FORMAL_RUN_MANIFEST.json", wrapper)
        index_rows.append({
            "method_order": order, "algorithm_id": method_id, "run_id": directory,
            "returncode": completed.returncode, "terminal_success": True,
            "formal_manifest_sha256": sha256_file(wrapper_path),
        })
        for role, path in (
            ("nav", nav), ("std", std), ("solver_manifest", solver_manifest_path),
            ("formal_manifest", wrapper_path), ("runtime_config", config), ("update_trace", update_trace),
        ):
            hash_rows.append({
                "method_order": order, "algorithm_id": method_id, "output_role": role,
                "relative_path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path), "frozen_before_any_evaluation": True,
            })
    if strong_counters is None:
        raise Clean1R2R1FormalError("strong method did not run")
    commit_after, dirty_after = git_code_state(repo)
    if dirty_after or commit_after != code_freeze_commit:
        raise Clean1R2R1FormalError("code state changed during four-method execution")
    with (root / "FOUR_METHOD_RUN_INDEX.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(index_rows[0]))
        writer.writeheader(); writer.writerows(index_rows)
    with (root / "FOUR_METHOD_OUTPUT_HASHES.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(hash_rows[0]))
        writer.writeheader(); writer.writerows(hash_rows)
    report = {
        "schema_version": "paper_rebuild.clean1r2r1_four_method_execution.v1",
        "stage_id": STAGE_ID,
        "method_order": list(METHOD_ORDER),
        "formal_method_count": 4,
        "formal_run_count": 4,
        "all_runs_terminal_pass": True,
        "same_executable": True,
        "same_common_imu": True,
        "same_common_gnss_15col": True,
        "strong_equals_clean_final_v23": True,
        "all_outputs_sealed_before_evaluation": True,
        "trace_opened": False,
        "trace_used_online": False,
        "module_counters_match": True,
        "strong_module_counters": strong_counters,
        "terminal_status": "READY_FOR_EXACT_ARCHIVED_OFFLINE_EVALUATION",
    }
    write_json_atomic(root / "FOUR_METHOD_EXECUTION_REPORT.json", report)
    return report


def validate_four_method_seal(runtime_root: str | Path) -> list[dict[str, str]]:
    root = Path(runtime_root).resolve(strict=True)
    seal = root / "FOUR_METHOD_OUTPUT_HASHES.csv"
    report = _json(root / "FOUR_METHOD_EXECUTION_REPORT.json")
    if report.get("all_outputs_sealed_before_evaluation") is not True or report.get("trace_opened") is not False:
        raise Clean1R2R1FormalError("four-method outputs were not sealed before evaluation")
    with seal.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 4 * 6 or [row["algorithm_id"] for row in rows[::6]] != list(METHOD_ORDER):
        raise Clean1R2R1FormalError("four-method output seal is incomplete or out of order")
    for row in rows:
        path = (root / row["relative_path"]).resolve(strict=True)
        if root not in path.parents or sha256_file(path) != row["sha256"]:
            raise Clean1R2R1FormalError("sealed formal output changed before evaluation")
        if row.get("frozen_before_any_evaluation") != "True":
            raise Clean1R2R1FormalError("formal output was not marked frozen before evaluation")
    return rows


def _run_exact_evaluator(
    evaluator: Path, trace: Path, nav: Path, std: Path, outdir: Path,
    *, base_time: float, timeout_seconds: int,
) -> None:
    command = [
        sys.executable, str(evaluator), "--trace", str(trace), "--nav", str(nav),
        "--std", str(std), "--outdir", str(outdir), "--base_time", str(base_time),
        "--yaw_truth_mode", "enu",
    ]
    completed = subprocess.run(
        command, check=False, capture_output=True, text=True, timeout=timeout_seconds,
        start_new_session=True,
    )
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "evaluator.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (outdir / "evaluator.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0 or not (outdir / "summary.json").is_file() or not (outdir / "error_series.csv").is_file():
        raise Clean1R2R1FormalError("exact archived evaluator failed")


def _rmse(values: Sequence[float]) -> float:
    return math.sqrt(sum(value * value for value in values) / len(values))


def _nav_row_count(path: Path) -> int:
    count = 0
    for line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "%")):
            continue
        try:
            [float(value) for value in stripped.replace(",", " ").split()]
        except ValueError:
            continue
        count += 1
    return count


def _crosscheck_error_series(path: Path, summary: Mapping[str, Any]) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise Clean1R2R1FormalError("exact evaluator returned no row errors")
    mapping = {
        "north_rmse_m": ("position", "north_rmse_m", "err_n_m"),
        "east_rmse_m": ("position", "east_rmse_m", "err_e_m"),
        "up_rmse_m": ("position", "up_rmse_m", "err_u_m"),
        "horizontal_rmse_m": ("position", "horizontal_rmse_m", "horizontal_err_m"),
        "roll_rmse_deg": ("attitude", "roll_rmse_deg", "roll_err_deg"),
        "pitch_rmse_deg": ("attitude", "pitch_rmse_deg", "pitch_err_deg"),
        "yaw_rmse_deg": ("attitude", "yaw_rmse_deg", "yaw_err_deg"),
    }
    checks: dict[str, Any] = {}
    passed = True
    for name, (section, field, column) in mapping.items():
        computed = _rmse([float(row[column]) for row in rows])
        reported = float(summary[section][field])
        difference = abs(computed - reported)
        check = {"computed": computed, "reported": reported, "absolute_difference": difference, "passed": difference <= 1.0e-10}
        checks[name] = check
        passed = passed and check["passed"]
    return {"row_count": len(rows), "checks": checks, "passed": passed}


def evaluate_four_methods_offline(
    *,
    runtime_root: str | Path,
    exact_evaluator: str | Path,
    evaluator_sha256: str,
    trace: str | Path,
    trace_sha256: str,
    exact_nav: str | Path,
    exact_std: str | Path,
    output_root: str | Path,
    base_time: float = 1772784000.0,
    timeout_seconds: int = 900,
) -> dict[str, Any]:
    """Open trace only after all four current outputs are hash-sealed."""

    sealed = validate_four_method_seal(runtime_root)
    runtime = Path(runtime_root).resolve(strict=True)
    evaluator = Path(exact_evaluator).resolve(strict=True)
    reference = Path(trace).resolve(strict=True)
    if sha256_file(evaluator) != evaluator_sha256 or sha256_file(reference) != trace_sha256:
        raise Clean1R2R1FormalError("exact evaluator or offline trace hash mismatch")
    destination = Path(output_root)
    if destination.exists():
        raise Clean1R2R1FormalError("fresh offline evaluation root already exists")
    destination.mkdir(parents=True)
    summary_rows: list[dict[str, Any]] = []
    combined_errors: list[dict[str, Any]] = []
    crosschecks: dict[str, Any] = {}
    targets = [("exact_clean_final_v23", Path(exact_nav).resolve(strict=True), Path(exact_std).resolve(strict=True))]
    for method, directory in zip(METHOD_ORDER, RUN_DIRECTORIES):
        targets.append((method, runtime / directory / EVALUATOR_NAV_NAME, runtime / directory / EVALUATOR_STD_NAME))
    summaries: dict[str, Any] = {}
    formal_wrappers: dict[str, Any] = {}
    for method, nav, std in targets:
        method_root = destination / ("00_exact_clean_final_v23" if method == "exact_clean_final_v23" else RUN_DIRECTORIES[METHOD_ORDER.index(method)])
        _run_exact_evaluator(evaluator, reference, nav, std, method_root, base_time=base_time, timeout_seconds=timeout_seconds)
        summary = _json(method_root / "summary.json")
        summaries[method] = summary
        crosschecks[method] = _crosscheck_error_series(method_root / "error_series.csv", summary)
        if not crosschecks[method]["passed"]:
            raise Clean1R2R1FormalError("aggregate crosscheck failed")
        if method != "exact_clean_final_v23":
            wrapper = _json(runtime / RUN_DIRECTORIES[METHOD_ORDER.index(method)] / "CLEAN1R2R1_FORMAL_RUN_MANIFEST.json")
            formal_wrappers[method] = wrapper
            with (method_root / "error_series.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                combined_errors.extend({"algorithm_id": method, **row} for row in csv.DictReader(handle))
            meta = summary["meta"]
            output_count = _nav_row_count(nav)
            matched_count = int(meta["num_samples"])
            summary_rows.append({
                "method_order": METHOD_ORDER.index(method) + 1,
                "algorithm_id": method,
                "terminal_success": wrapper.get("terminal_success"),
                "output_epoch_count": output_count,
                "matched_epoch_count": matched_count,
                "unmatched_epoch_count": output_count - matched_count,
                "coverage_ratio": matched_count / output_count if output_count else 0.0,
                "time_start": meta["time_start"], "time_end": meta["time_end"],
                "horizontal_rmse_m": summary["position"]["horizontal_rmse_m"],
                "up_rmse_m": summary["position"]["up_rmse_m"],
                "roll_rmse_deg": summary["attitude"]["roll_rmse_deg"],
                "pitch_rmse_deg": summary["attitude"]["pitch_rmse_deg"],
                "yaw_rmse_deg": summary["attitude"]["yaw_rmse_deg"],
                "module_counters_json": json.dumps(wrapper["module_counters"], sort_keys=True),
            })
    with (destination / "FOUR_METHOD_SUMMARY.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0])); writer.writeheader(); writer.writerows(summary_rows)
    with (destination / "MATCH_COVERAGE.csv").open("x", encoding="utf-8", newline="") as handle:
        fields = ["method_order", "algorithm_id", "output_epoch_count", "matched_epoch_count",
                  "unmatched_epoch_count", "coverage_ratio", "time_start", "time_end", "coverage_role"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for row in summary_rows:
            writer.writerow({"method_order": row["method_order"], "algorithm_id": row["algorithm_id"],
                             "output_epoch_count": row["output_epoch_count"],
                             "matched_epoch_count": row["matched_epoch_count"],
                             "unmatched_epoch_count": row["unmatched_epoch_count"],
                             "coverage_ratio": row["coverage_ratio"],
                             "time_start": row["time_start"], "time_end": row["time_end"],
                             "coverage_role": "exact_archived_evaluator_overlap"})
    with (destination / "ROW_LEVEL_ERRORS.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(combined_errors[0])); writer.writeheader(); writer.writerows(combined_errors)
    strong = summaries["strong_dual_yaw_EKF"]
    exact = summaries["exact_clean_final_v23"]
    comparison_rows = []
    for section, fields in (("position", ("horizontal_rmse_m", "up_rmse_m")), ("attitude", ("roll_rmse_deg", "pitch_rmse_deg", "yaw_rmse_deg"))):
        for field in fields:
            comparison_rows.append({"metric": field, "exact_clean_final_v23": exact[section][field],
                                    "strong_dual_yaw_EKF": strong[section][field],
                                    "difference": float(strong[section][field]) - float(exact[section][field]),
                                    "implementation_parity_gate_source": "ACTIVE_PORT_CLEAN_FINAL_V23_PARITY_REPORT.json"})
    exact_meta, strong_meta = exact["meta"], strong["meta"]
    for field in ("num_samples", "time_start", "time_end"):
        exact_value, strong_value = exact_meta[field], strong_meta[field]
        comparison_rows.append({"metric": field, "exact_clean_final_v23": exact_value,
                                "strong_dual_yaw_EKF": strong_value,
                                "difference": float(strong_value) - float(exact_value),
                                "implementation_parity_gate_source": "ACTIVE_PORT_CLEAN_FINAL_V23_PARITY_REPORT.json"})
    four_report = _json(runtime / "FOUR_METHOD_EXECUTION_REPORT.json")
    for field, value in four_report["strong_module_counters"].items():
        comparison_rows.append({"metric": field, "exact_clean_final_v23": value,
                                "strong_dual_yaw_EKF": value, "difference": 0,
                                "implementation_parity_gate_source": "passing parity counter audit plus fresh strong rerun"})
    with (destination / "FINAL_V23_PARITY_COMPARISON.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison_rows[0])); writer.writeheader(); writer.writerows(comparison_rows)
    aggregate = {
        "schema_version": "paper_rebuild.clean1r2r1_aggregate_metrics.v1",
        "reference_identity": "Fixposition-derived same-source offline evaluation reference",
        "independent_ground_truth": False,
        "position_same_source_mounting_caveat": True,
        "trace_used_online": False,
        "trace_opened_only_after_four_outputs_sealed": True,
        "exact_evaluator_sha256": evaluator_sha256,
        "output_seal_sha256": sha256_file(runtime / "FOUR_METHOD_OUTPUT_HASHES.csv"),
        "methods": {
            method: {**summaries[method], "module_counters": formal_wrappers[method]["module_counters"]}
            for method in METHOD_ORDER
        },
        "paper_performance_claim": False,
    }
    write_json_atomic(destination / "AGGREGATE_METRICS.json", aggregate)
    overall = {
        "schema_version": "paper_rebuild.clean1r2r1_aggregate_crosscheck.v1",
        "method_crosschecks": crosschecks,
        "method_order": list(METHOD_ORDER),
        "all_outputs_sealed_before_trace_open": True,
        "trace_offline_only": True,
        "passed": all(item["passed"] for item in crosschecks.values()),
    }
    write_json_atomic(destination / "AGGREGATE_CROSSCHECK.json", overall)
    write_json_atomic(destination / "OFFLINE_EVALUATION_MANIFEST.json", {
        "schema_version": "paper_rebuild.clean1r2r1_offline_evaluation.v1",
        "exact_evaluator_sha256": evaluator_sha256, "trace_sha256": trace_sha256,
        "sealed_output_row_count": len(sealed), "trace_opened_after_seal_validation": True,
        "trace_used_online": False, "old_metric_evidence_used": False,
        "terminal_status": "PASS_EXACT_ARCHIVED_OFFLINE_EVALUATION",
    })
    return overall
