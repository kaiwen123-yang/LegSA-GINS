"""Real, trace-closed Phase-1 EXT01/C00 orchestration."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import yaml

from legsa_gins.paper_rebuild.manifest import read_hash_lock, sha256_file, verify_raw_sources

from .ext01_clambda import body_yaw_from_ned_baseline, solve_clambda
from .shared_raw_backend import (
    RawBackendError,
    RtklibBroadcastProvider,
    SignalIdentity,
    TrackingContinuity,
    build_gps_l1_double_difference_model,
    gps_l1_code_eligible,
    gps_l1_code_spp,
    pair_epochs,
    reconstruct_ubx_stream,
    strict_raw_tracking_eligible,
)


BLOCKED_RAW = "BLOCKED_PHASE1_EXT01_C00_RAW_ROOT_UNAVAILABLE"
BLOCKED_HASH_LOCK = "BLOCKED_PHASE1_EXT01_C00_RAW_HASH_LOCK_UNAVAILABLE"
BLOCKED_EXTERNAL = "BLOCKED_PHASE1_EXT01_C00_EXTERNAL_PROVIDER_UNAVAILABLE"
PASS_STATUS = "PASS_PHASE1_SHARED_RAW_BACKEND_AND_EXT01_C00_READY_FOR_REVIEW"
STAGE_NAME = "CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON"
BY2_RELATIVE = Path("BY2_BY3/2026-03-06/fixption数据/2026.3.6/by2/vrtk2_a87c6e_2026-03-06-08-00-54_minimal")
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_ROOT = REPOSITORY_ROOT / "configs/paper_rebuild/horizontal_literature"
RTKLIB_COMMIT = "180043ee24b6d2b168f98b64be15f69d50046b1a"
RTKLIB_REMOTE = "https://github.com/tomojitakasu/RTKLIB.git"
RTKLIB_LICENSE_SHA256 = "219747832d49ee958457b2934080ab8d94bd9d8e45fcb1c36f89776fd2c5ed8a"

OUTPUT_RELATIVE_PATHS = {
    "execution_contract": "00_CONTRACTS/EXECUTION_CONTRACT_V1.md",
    "external_method_contracts": "00_CONTRACTS/EXTERNAL_METHOD_CONTRACTS_V1.yaml",
    "heading_stream_schema": "00_CONTRACTS/STANDARD_HEADING_STREAM_SCHEMA_V1.yaml",
    "compatibility_registry": "00_CONTRACTS/CASE_METHOD_COMPATIBILITY_V1.csv",
    "raw_observation_audit": "01_SHARED_RAW_BACKEND/RAW_OBSERVATION_AUDIT.json",
    "epoch_pairing_summary": "01_SHARED_RAW_BACKEND/EPOCH_PAIRING_SUMMARY.csv",
    "signal_availability_summary": "01_SHARED_RAW_BACKEND/SIGNAL_AVAILABILITY_SUMMARY.csv",
    "tracking_continuity_summary": "01_SHARED_RAW_BACKEND/TRACKING_CONTINUITY_SUMMARY.csv",
    "dd_observation_diagnostics": "01_SHARED_RAW_BACKEND/DD_OBSERVATION_DIAGNOSTICS.csv",
    "stochastic_contract": "01_SHARED_RAW_BACKEND/STOCHASTIC_MODEL_CONTRACT.yaml",
    "ext01_heading_results": "02_EXT01_CLAMBDA/C00/EXT01_C00_NATIVE_HEADING_RESULTS.csv",
    "ext01_failure_ledger": "02_EXT01_CLAMBDA/C00/EXT01_C00_FAILURE_LEDGER.csv",
    "ext01_runtime": "02_EXT01_CLAMBDA/C00/EXT01_C00_RUNTIME.csv",
    "native_summary": "06_NATIVE_C00/EXT01_C00_NATIVE_SUMMARY.json",
    "baseline_summary": "06_NATIVE_C00/EXT01_C00_BASELINE_SUMMARY.csv",
    "ambiguity_summary": "06_NATIVE_C00/EXT01_C00_AMBIGUITY_SUMMARY.csv",
    "phase1_report": "11_REPORT/PHASE1_EXT01_C00_REPORT.md",
    "phase1_status": "11_REPORT/PHASE1_STATUS.json",
}

INTERMEDIATE_RELATIVE_PATHS = {
    f"gnss{receiver}_reconstructed_{suffix}":
        f"01_SHARED_RAW_BACKEND/gnss{receiver}_reconstructed.{suffix}"
    for receiver in (1, 2) for suffix in ("ubx", "obs", "nav")
}

CONTRACT_INPUTS = {
    "execution_contract": "EXECUTION_CONTRACT_V1.md",
    "external_method_contracts": "EXTERNAL_METHOD_CONTRACTS_V1.yaml",
    "heading_stream_schema": "STANDARD_HEADING_STREAM_SCHEMA_V1.yaml",
    "compatibility_registry": "CASE_METHOD_COMPATIBILITY_V1.csv",
}


class Phase1RunnerError(ValueError):
    pass


@dataclass(frozen=True)
class Phase1Paths:
    code_root: Path
    project_root: Path
    raw_root: Path
    by2_fix_root: Path
    clean_root: Path
    receiver1_raw: Path
    receiver2_raw: Path
    raw_hash_lock: Path
    stage_root: Path
    output_files: dict[str, Path]
    rtklib_root: Path
    convbin: Path
    rtklib_bridge: Path
    lambda_library: Path
    bridge_root: Path


def _terminal(status: str) -> dict[str, Any]:
    return {
        "status": status, "phase": "PHASE1", "method_id": "EXT01_CLAMBDA",
        "case_id": "C00", "evaluation": "NOT_EVALUATED",
        "paired_epoch_count": None, "success_row_count": None,
        "failure_row_count": None, "conservation": "NOT_EVALUATED",
        "output_files": "NOT_PRODUCED",
    }


def _configured_path(mapping: Mapping[str, Any], key: str) -> Path:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise Phase1RunnerError(f"missing local path: {key}")
    return Path(value).expanduser().resolve(strict=False)


def load_paths(config_path: Path) -> Phase1Paths:
    """Resolve all machine-local paths exclusively from the ignored YAML."""
    config_path = config_path.resolve(strict=True)
    value = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "paper_rebuild.paths.v1":
        raise Phase1RunnerError("invalid CLEAN3R4 path schema")
    mapping = value.get("paths")
    if not isinstance(mapping, dict):
        raise Phase1RunnerError("missing paths mapping")
    code_root = _configured_path(mapping, "code_root")
    raw_root = _configured_path(mapping, "raw_root")
    by2 = _configured_path(mapping, "by2_fix_root")
    clean = _configured_path(mapping, "clean_root")
    try:
        project_root = raw_root.parents[1]
        raw_root.relative_to(project_root)
        by2.relative_to(raw_root)
        clean.relative_to(project_root)
    except (ValueError, IndexError) as exc:
        raise Phase1RunnerError("configured roots violate project containment") from exc
    if code_root != REPOSITORY_ROOT:
        raise Phase1RunnerError("code_root does not resolve to this repository")
    if raw_root != project_root / "data/raw":
        raise Phase1RunnerError("raw_root is not the locked project data/raw path")
    if by2 != raw_root / BY2_RELATIVE:
        raise Phase1RunnerError("by2_fix_root is not the exact authorized BY2 path")
    if clean != project_root / "clean_rebuild_202607":
        raise Phase1RunnerError("clean_root is not the exact authorized clean root")
    stage = clean / "stages" / STAGE_NAME
    return Phase1Paths(
        code_root, project_root, raw_root, by2, clean,
        by2 / "gnss1-raw.csv", by2 / "gnss2-raw.csv",
        clean / "01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK.csv", stage,
        {name: stage / relative for name, relative in OUTPUT_RELATIVE_PATHS.items()},
        _configured_path(mapping, "horizontal_literature_rtklib_root"),
        _configured_path(mapping, "horizontal_literature_convbin"),
        _configured_path(mapping, "horizontal_literature_rtklib_bridge"),
        _configured_path(mapping, "horizontal_literature_lambda_library"),
        _configured_path(mapping, "horizontal_literature_bridge_root"),
    )


def validate_sources_before_output(paths: Phase1Paths) -> dict[str, Any] | None:
    required_dirs = (paths.project_root, paths.raw_root, paths.by2_fix_root)
    if (any(not path.is_dir() for path in required_dirs)
            or any(not path.is_file() for path in (paths.receiver1_raw, paths.receiver2_raw))):
        return _terminal(BLOCKED_RAW)
    if not paths.raw_hash_lock.is_file():
        return _terminal(BLOCKED_HASH_LOCK)
    if (not paths.rtklib_root.is_dir() or not paths.bridge_root.is_dir()
            or any(not path.is_file() for path in (
                paths.convbin, paths.rtklib_bridge, paths.lambda_library
            ))):
        return _terminal(BLOCKED_EXTERNAL)
    if paths.stage_root.exists():
        raise Phase1RunnerError("authorized output root must be absent before Phase 1")
    return None


def _external_dependency_audit(paths: Phase1Paths) -> dict[str, Any]:
    """Verify the pinned upstream tree and hash the external thin adapter."""
    def git(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments], cwd=paths.rtklib_root, text=True,
            capture_output=True, check=False,
        )

    head = git("rev-parse", "HEAD")
    remote = git("remote", "get-url", "origin")
    diff = git("diff", "--no-ext-diff", "--quiet", "--")
    staged_diff = git("diff", "--cached", "--no-ext-diff", "--quiet", "--")
    status = git("status", "--short")
    license_path = paths.rtklib_root / "LICENSE.txt"
    if (head.returncode != 0 or head.stdout.strip() != RTKLIB_COMMIT
            or remote.returncode != 0 or remote.stdout.strip() != RTKLIB_REMOTE
            or diff.returncode != 0 or staged_diff.returncode != 0
            or status.returncode != 0
            or status.stdout.splitlines() != ["?? app/consapp/convbin/gcc/convbin"]
            or not license_path.is_file()
            or sha256_file(license_path) != RTKLIB_LICENSE_SHA256):
        raise Phase1RunnerError("external RTKLIB source identity does not match the frozen dependency")
    adapter_sources: dict[str, str] = {}
    for filename in ("legsa_rtklib_bridge.c", "legsa_rtklib_bridge.h", "Makefile", "README.md"):
        path = paths.bridge_root / filename
        if not path.is_file():
            raise Phase1RunnerError(f"missing external bridge source: {filename}")
        adapter_sources[filename] = sha256_file(path)
    return {
        "name": "RTKLIB", "version": "2.4.3_b34", "remote": RTKLIB_REMOTE,
        "commit": RTKLIB_COMMIT, "license": "BSD-2-Clause",
        "license_sha256": RTKLIB_LICENSE_SHA256,
        "upstream_source_patch": "none", "upstream_tracked_diff_clean": True,
        "upstream_status_short": status.stdout.splitlines() if status.returncode == 0 else [],
        "local_thin_adapter": {
            "role": ["multi_rinex_broadcast_state", "ephemeris_audit", "c_abi"],
            "source_hashes": adapter_sources,
        },
        "reused_parts": [
            "convbin", "broadcast_ephemeris", "satellite_clock",
            "satellite_position", "signal_frequency", "lambda_reduction",
            "lambda_integer_search_seed",
        ],
        "ordinary_moving_baseline_used_as_ext01": False,
    }


def runtime_manifest_template(paths: Phase1Paths, config_hash: str, code_commit: str) -> dict[str, Any]:
    return {
        "schema_version": "horizontal_literature.phase1_manifest.v1",
        "phase": "PHASE1", "method_id": "EXT01_CLAMBDA", "case_id": "C00",
        "data_mode": "real_by2_raw", "raw_source_hashes": {}, "provider_hashes": {},
        "raw_hash_lock_path": str(paths.raw_hash_lock), "raw_hash_lock_sha256": None,
        "raw_hashes_validated": False, "synthetic_data_used": False,
        "semisynthetic_data_used": False, "trace_used_online": False,
        "receiver_imu_as_body_imu": False, "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False, "per_case_tuning": False,
        "output_only_correction": False, "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0, "code_commit": code_commit,
        "config_hash": config_hash, "implementation_source_hashes": {},
        "stochastic_contract_hash": None,
        "satellite_state_provider_identity": "RTKLIB_BROADCAST_EPHEMERIS",
        "rtklib_position_solution_used_as_solver_input": False,
        "external_dependency": {
            "name": "RTKLIB", "version": "2.4.3_b34",
            "remote": "https://github.com/tomojitakasu/RTKLIB.git",
            "commit": "180043ee24b6d2b168f98b64be15f69d50046b1a",
            "license": "BSD-2-Clause", "upstream_source_patch": "none",
            "ordinary_moving_baseline_used_as_ext01": False,
        },
        "canonical541_accessed": False,
        "paper_source_hashes": {
            "P01": "e9e19c60d1f651994c878678f530d288a82eb707e26770ce48b449774317aec4",
            "P23": "734e256229dada2bb1c10a3f290527681a2d2bfa14b3540dd00473e927848546",
            "P25": "11a514002e93bf659ee0245de55030a2d2d614768838dced64de8621670b407a",
        },
        "ubx_specification_hash": "3d6539cd5ab3efe1254c54e4dba25d17421bfe48ac96e633e602d8d214c13668",
        "output_hashes": {}, "paired_epoch_count": None, "success_row_count": None,
        "intermediate_artifact_hashes": {}, "intermediate_artifact_paths": {},
        "failure_row_count": None, "conservation": "NOT_EVALUATED",
        "evaluation": "NOT_EVALUATED",
        "output_paths": {name: str(path) for name, path in paths.output_files.items()},
    }


def _raw_relatives(paths: Phase1Paths) -> tuple[str, str]:
    return tuple(str(path.relative_to(paths.raw_root)).replace("\\", "/")
                 for path in (paths.receiver1_raw, paths.receiver2_raw))  # type: ignore[return-value]


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fields})


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, tuple, dict, np.ndarray)):
        return json.dumps(np.asarray(value).tolist() if isinstance(value, np.ndarray) else value,
                          sort_keys=True, separators=(",", ":"))
    if value is None:
        return ""
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_convbin(convbin: Path, ubx: Path, observation: Path, navigation: Path) -> list[str]:
    command = [str(convbin), "-r", "ubx", "-v", "3.04", "-od", "-os", "-oi",
               "-ot", "-ol", "-o", str(observation), "-n", str(navigation), str(ubx)]
    completed = subprocess.run(command, cwd=ubx.parent, text=True, capture_output=True,
                               check=False, timeout=300)
    if completed.returncode != 0 or not navigation.is_file() or navigation.stat().st_size == 0:
        raise Phase1RunnerError(f"convbin navigation generation failed: {completed.stderr.strip()}")
    return command


def _ecef_vector_to_ned(vector: Sequence[float], position: Sequence[float]) -> np.ndarray:
    x, y, z = np.asarray(position, dtype=float)
    longitude = math.atan2(y, x)
    horizontal = math.hypot(x, y)
    latitude = math.atan2(z, horizontal * (1.0 - 6.6943799901413165e-3))
    for _ in range(8):
        sine = math.sin(latitude)
        radius = 6_378_137.0 / math.sqrt(1.0 - 6.6943799901413165e-3 * sine * sine)
        latitude = math.atan2(z + 6.6943799901413165e-3 * radius * sine, horizontal)
    slat, clat, slon, clon = math.sin(latitude), math.cos(latitude), math.sin(longitude), math.cos(longitude)
    rotation = np.array([[-slat * clon, -slat * slon, clat],
                         [-slon, clon, 0.0],
                         [-clat * clon, -clat * slon, -slat]])
    result = rotation @ np.asarray(vector, dtype=float)
    if result.shape != (3,) or np.any(~np.isfinite(result)):
        raise Phase1RunnerError("invalid ECEF-to-NED baseline transform")
    return result


def _percentiles(values: Iterable[float]) -> dict[str, float | int | None]:
    array = np.asarray([value for value in values if math.isfinite(value)], dtype=float)
    if not array.size:
        return {"count": 0, **{key: None for key in (
            "min", "p05", "median", "mean", "std", "p95", "p99", "max"
        )}}
    return {
        "count": int(array.size),
        "min": float(np.min(array)), "p05": float(np.percentile(array, 5)),
        "median": float(np.median(array)), "mean": float(np.mean(array)),
        "std": float(np.std(array)), "p95": float(np.percentile(array, 95)),
        "p99": float(np.percentile(array, 99)), "max": float(np.max(array)),
    }


def _signal_counts(reconstructions: Sequence[Any]) -> list[dict[str, Any]]:
    counts: Counter[tuple[int, int, int, int]] = Counter()
    satellites: dict[tuple[int, int, int, int], set[int]] = {}
    epochs: Counter[tuple[int, int, int, int]] = Counter()
    for receiver, reconstruction in enumerate(reconstructions, 1):
        for epoch in reconstruction.rawx_epochs:
            seen: set[tuple[int, int, int, int]] = set()
            for measurement in epoch.measurements:
                identity = measurement.identity
                key = (receiver, identity.gnss_id, identity.sig_id, identity.freq_id)
                counts[key] += 1
                satellites.setdefault(key, set()).add(identity.sv_id)
                seen.add(key)
            for key in seen:
                epochs[key] += 1
    return [{"receiver": key[0], "gnss_id": key[1], "sig_id": key[2],
             "freq_id": key[3], "satellite_count": len(satellites[key]),
             "epoch_count": epochs[key], "measurement_count": count}
            for key, count in sorted(counts.items())]


def _circular_heading_statistics(values: Iterable[float]) -> dict[str, Any]:
    array = np.asarray([value for value in values if math.isfinite(value)], dtype=float)
    if not array.size:
        return {"count": 0, "circular_mean": None, "circular_std": None,
                "resultant_length": None, "wrapped_values": _percentiles(())}
    radians = np.radians(array)
    sine, cosine = float(np.mean(np.sin(radians))), float(np.mean(np.cos(radians)))
    resultant = min(1.0, math.hypot(sine, cosine))
    circular_mean = math.degrees(math.atan2(sine, cosine))
    circular_std = math.degrees(math.sqrt(max(0.0, -2.0 * math.log(max(resultant, 1e-15)))))
    return {
        "count": int(array.size), "circular_mean": circular_mean,
        "circular_std": circular_std, "resultant_length": resultant,
        "wrapped_values": _percentiles(array),
    }


def _success_continuity(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    success_times = sorted(
        float(row["gps_week"]) * 604800.0 + float(row["gps_tow_seconds"])
        for row in results if row.get("status") == "SUCCESS"
    )
    if len(success_times) < 2:
        return {"success_epoch_count": len(success_times), "maximum_gap_seconds": None,
                "gap_statistics_seconds": _percentiles(())}
    gaps = np.diff(np.asarray(success_times, dtype=float))
    return {"success_epoch_count": len(success_times),
            "maximum_gap_seconds": float(np.max(gaps)),
            "gap_statistics_seconds": _percentiles(gaps)}


def _nav_sat_elevation_audit(reconstruction: Any, pairs: Sequence[Any],
                             diagnostics: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare broadcast geometry with the nearest NAV-SAT diagnostic epoch."""
    nav_epochs = tuple(reconstruction.nav_sat_epochs)
    residuals: list[float] = []
    offsets: list[float] = []
    for (receiver1, _receiver2), diagnostic in zip(pairs, diagnostics):
        computed = diagnostic.get("_computed_elevations_deg")
        if not computed or not nav_epochs:
            continue
        target_ms = round(float(receiver1.gps_tow_seconds) * 1000.0)
        nav_epoch = min(nav_epochs, key=lambda epoch: abs(epoch.itow_ms - target_ms))
        offset_ms = float(nav_epoch.itow_ms - target_ms)
        if abs(offset_ms) > 10.0:
            continue
        offsets.append(offset_ms)
        nav_by_sat = {
            (entry.identity.gnss_id, entry.identity.sv_id): float(entry.elevation_deg)
            for entry in nav_epoch.satellites
        }
        for identity_text, elevation_deg in computed.items():
            gnss_id, sv_id, _sig_id, _freq_id = (int(value) for value in identity_text.split(":"))
            if (gnss_id, sv_id) in nav_by_sat:
                residuals.append(float(elevation_deg) - nav_by_sat[(gnss_id, sv_id)])
    absolute = np.abs(np.asarray(residuals, dtype=float))
    statistics = _percentiles(absolute)
    maximum = statistics["max"]
    return {
        "match_policy": "nearest_NAV_SAT_within_10_ms_diagnostic_only",
        "matched_satellite_count": len(residuals),
        "time_offset_ms": _percentiles(offsets),
        "signed_residual_deg": _percentiles(residuals),
        "absolute_residual_deg": statistics,
        "sanity_threshold_deg": 2.0,
        "sanity_pass": bool(maximum is not None and float(maximum) <= 2.0),
    }


def _tracking_epoch(continuity: TrackingContinuity, receiver: int, epoch: Any) -> dict[str, Any]:
    flags = [continuity.update(receiver, epoch, measurement) for measurement in epoch.measurements]
    return {
        "pseudorange_valid": all(item.pseudorange_valid for item in flags) if flags else False,
        "carrier_valid": all(item.carrier_valid for item in flags) if flags else False,
        "lock_reset": any(item.lock_reset for item in flags),
        "half_cycle_valid": all(item.half_cycle_valid for item in flags) if flags else False,
        "half_cycle_subtracted": any(item.half_cycle_subtracted for item in flags),
        "receiver_clock_reset": any(item.receiver_clock_reset for item in flags),
        "cycle_slip": any(item.cycle_slip for item in flags),
        "arc_reset": any(item.arc_reset for item in flags),
    }


def _identity(identity: SignalIdentity | None) -> str:
    if identity is None:
        return ""
    return f"{identity.gnss_id}:{identity.sv_id}:{identity.sig_id}:{identity.freq_id}"


def _code_from_exception(exc: Exception) -> str:
    text = str(exc).upper()
    if "SPP" in text:
        return "SPP_UNAVAILABLE"
    if "DD MODEL" in text or "SATELLITE" in text or "REFERENCE" in text:
        return "DD_MODEL_UNAVAILABLE"
    if "POSITIVE DEFINITE" in text or "RANK" in text or "GLS" in text:
        return "FLOAT_SOLUTION_INVALID"
    return "EPOCH_PROCESSING_ERROR"


def _normal_diagnostics(model: Any) -> tuple[int, float]:
    try:
        design = np.column_stack((model.ambiguity_design_m, model.baseline_design))
        normal = design.T @ np.linalg.solve(model.covariance_m2, design)
        return int(np.linalg.matrix_rank(normal)), float(np.linalg.cond(normal))
    except (ValueError, np.linalg.LinAlgError):
        return 0, math.inf


def _code_commit(paths: Phase1Paths) -> str:
    completed = subprocess.run(["git", "rev-parse", "HEAD"], cwd=paths.code_root,
                               text=True, capture_output=True, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else "UNKNOWN"


def _materialize_contracts(paths: Phase1Paths) -> None:
    for key, filename in CONTRACT_INPUTS.items():
        destination = paths.output_files[key]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CONTRACT_ROOT / filename, destination)


def _process_pairs(paths: Phase1Paths, pairs: Sequence[tuple[Any, Any]], provider: Any) -> tuple[
        list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]],
        list[dict[str, Any]], list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    runtimes: list[dict[str, Any]] = []
    tracking_rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    continuity = TrackingContinuity()
    previous_position: np.ndarray | None = None
    previous_pivot: SignalIdentity | None = None
    for receiver1, receiver2 in pairs:
        started = time.perf_counter()
        key = {"gps_week": receiver1.gps_week, "gps_tow_seconds": receiver1.gps_tow_seconds,
               "method_id": "EXT01_CLAMBDA", "case_id": "C00"}
        flags1 = _tracking_epoch(continuity, 1, receiver1)
        flags2 = _tracking_epoch(continuity, 2, receiver2)
        flags = {name: (flags1[name] or flags2[name]) for name in flags1}
        for name in ("pseudorange_valid", "carrier_valid", "half_cycle_valid"):
            flags[name] = flags1[name] and flags2[name]
        tracking_rows.append({**key, **flags})
        row: dict[str, Any] = {
            **key, "status": "FAILURE", "solution_type": "invalid", "failure_code": None,
            "baseline_ned_m": None, "baseline_length_m": None,
            "baseline_heading_deg": None, "body_yaw_deg": None,
            "pivot_identity": None, "pivot_switched": False,
            "ambiguity_candidate": None, "constrained_objective": None,
            "second_objective": None, "ratio": None, "ratio_valid": False,
            "search_complete": False, "search_nodes": 0,
            "constraint_error_m": None, "residual_norm": None,
            **flags,
        }
        model = None
        solve_result = None
        common_raw_count = common_tracking_count = 0
        ephemeris_ages: list[float] = []
        ephemeris_health: list[int] = []
        computed_elevations: dict[str, float] = {}
        try:
            spp = gps_l1_code_spp(receiver1, provider, previous_position)
            previous_position = spp.position_ecef_m
            model = build_gps_l1_double_difference_model(
                receiver1, receiver2, provider, previous_position,
                previous_pivot=previous_pivot,
            )
            pivot_switched = previous_pivot is not None and model.pivot != previous_pivot
            previous_pivot = model.pivot
            raw1 = {measurement.identity for measurement in receiver1.measurements
                    if gps_l1_code_eligible(measurement)}
            raw2 = {measurement.identity for measurement in receiver2.measurements
                    if gps_l1_code_eligible(measurement)}
            tracking1 = {measurement.identity for measurement in receiver1.measurements
                         if strict_raw_tracking_eligible(measurement)}
            tracking2 = {measurement.identity for measurement in receiver2.measurements
                         if strict_raw_tracking_eligible(measurement)}
            common_raw_count = len(raw1 & raw2)
            common_tracking_count = len(tracking1 & tracking2)
            computed_elevations = {
                _identity(identity): math.degrees(elevation)
                for identity, elevation in model.elevations_rad.items()
            }
            for identity in model.elevations_rad:
                try:
                    audit = provider.ephemeris_audit(
                        identity, receiver1.gps_week, receiver1.gps_tow_seconds
                    )
                except RawBackendError:
                    continue
                ephemeris_ages.append(audit.signed_age_seconds)
                ephemeris_health.append(audit.health)
            solve_result = solve_clambda(
                model.observation_m, model.ambiguity_design_m, model.baseline_design,
                model.covariance_m2, length_m=0.350,
                lambda_bridge_path=paths.lambda_library, strict=True,
                initial_candidate_count=512, timeout_seconds=2.0,
                strict_node_limit=1_000_000,
            )
            row.update({"pivot_identity": _identity(model.pivot),
                        "pivot_switched": pivot_switched,
                        "search_nodes": solve_result.nodes_visited,
                        "search_complete": solve_result.search_complete})
            if not solve_result.search_complete or solve_result.best is None:
                row["failure_code"] = solve_result.failure_code or "SEARCH_INCOMPLETE"
            else:
                best = solve_result.best
                baseline_ned = _ecef_vector_to_ned(best.baseline, previous_position)
                beta = math.degrees(math.atan2(baseline_ned[1], baseline_ned[0]))
                residual = (model.observation_m
                            - model.ambiguity_design_m @ best.ambiguity
                            - model.baseline_design @ best.baseline)
                row.update({
                    "status": "SUCCESS", "solution_type": "fixed", "failure_code": None,
                    "baseline_ned_m": baseline_ned,
                    "baseline_length_m": float(np.linalg.norm(baseline_ned)),
                    "baseline_heading_deg": beta,
                    "body_yaw_deg": body_yaw_from_ned_baseline(baseline_ned),
                    "ambiguity_candidate": best.ambiguity,
                    "constrained_objective": best.objective,
                    "second_objective": solve_result.second.objective if solve_result.second else None,
                    "ratio": solve_result.ratio, "ratio_valid": solve_result.ratio_valid,
                    "constraint_error_m": best.constraint_error_m,
                    "residual_norm": float(np.linalg.norm(residual)),
                })
        except (RawBackendError, ValueError, np.linalg.LinAlgError) as exc:
            row["failure_code"] = _code_from_exception(exc)
        elapsed = time.perf_counter() - started
        row["runtime_seconds"] = elapsed
        results.append(row)
        if row["status"] == "FAILURE":
            failures.append({**key, "failure_code": row["failure_code"],
                             "search_nodes": row["search_nodes"],
                             "runtime_seconds": elapsed})
        runtimes.append({**key, "status": row["status"],
                         "failure_code": row["failure_code"],
                         "runtime_seconds": elapsed,
                         "search_nodes": row["search_nodes"],
                         "candidate_count": (solve_result.candidates_evaluated
                                             if solve_result is not None else 0)})
        normal_rank, condition_number = ((0, None) if model is None
                                         else _normal_diagnostics(model))
        diagnostics.append({
            **key, "status": row["status"], "failure_code": row["failure_code"],
            "pivot_identity": row["pivot_identity"],
            "dd_satellite_count": len(model.satellites) if model is not None else 0,
            "common_gps_l1_raw_count": common_raw_count,
            "common_strict_tracking_count": common_tracking_count,
            "excluded_tracking_count": max(0, common_raw_count - common_tracking_count),
            "excluded_ephemeris_health_elevation_count": max(
                0, common_tracking_count - (len(model.elevations_rad) if model is not None else 0)
            ),
            "observation_count": int(model.observation_m.size) if model is not None else 0,
            "ambiguity_dimension": int(model.ambiguity_design_m.shape[1]) if model is not None else 0,
            "normal_rank": normal_rank, "condition_number": condition_number,
            "ambiguity_reinitialized_this_epoch": True,
            "ephemeris_audit_count": len(ephemeris_ages),
            "ephemeris_age_signed_min_seconds": min(ephemeris_ages) if ephemeris_ages else None,
            "ephemeris_age_signed_max_seconds": max(ephemeris_ages) if ephemeris_ages else None,
            "ephemeris_health_max": max(ephemeris_health) if ephemeris_health else None,
            "_ephemeris_ages": ephemeris_ages,
            "_ephemeris_health": ephemeris_health,
            "_computed_elevations_deg": computed_elevations,
        })
    return results, failures, runtimes, tracking_rows, diagnostics


def _write_outputs(paths: Phase1Paths, manifest: dict[str, Any], reconstruction1: Any,
                   reconstruction2: Any, pairs: Sequence[Any], pairing_failures: Sequence[Mapping[str, Any]],
                   results: list[dict[str, Any]], failures: list[dict[str, Any]],
                   runtimes: list[dict[str, Any]], tracking: list[dict[str, Any]],
                   diagnostics: list[dict[str, Any]], convbin_commands: Sequence[Sequence[str]],
                   provider: Any) -> dict[str, Any]:
    _materialize_contracts(paths)
    result_fields = list(yaml.safe_load((CONTRACT_ROOT / CONTRACT_INPUTS["heading_stream_schema"]).read_text(
        encoding="utf-8"))["fields"])
    _write_csv(paths.output_files["ext01_heading_results"], results, result_fields)
    _write_csv(paths.output_files["ext01_failure_ledger"], failures,
               ["gps_week", "gps_tow_seconds", "method_id", "case_id", "failure_code",
                "search_nodes", "runtime_seconds"])
    _write_csv(paths.output_files["ext01_runtime"], runtimes,
               ["gps_week", "gps_tow_seconds", "method_id", "case_id", "status",
                "failure_code", "runtime_seconds", "search_nodes", "candidate_count"])
    _write_csv(paths.output_files["tracking_continuity_summary"], tracking,
               ["gps_week", "gps_tow_seconds", "method_id", "case_id",
                "pseudorange_valid", "carrier_valid", "lock_reset", "half_cycle_valid",
                "half_cycle_subtracted", "receiver_clock_reset", "cycle_slip", "arc_reset"])
    _write_csv(paths.output_files["dd_observation_diagnostics"], diagnostics,
               ["gps_week", "gps_tow_seconds", "method_id", "case_id", "status", "failure_code",
                "pivot_identity", "dd_satellite_count", "common_gps_l1_raw_count",
                "common_strict_tracking_count", "excluded_tracking_count",
                "excluded_ephemeris_health_elevation_count", "observation_count",
                "ambiguity_dimension", "normal_rank", "condition_number",
                "ambiguity_reinitialized_this_epoch", "ephemeris_audit_count",
                "ephemeris_age_signed_min_seconds", "ephemeris_age_signed_max_seconds",
                "ephemeris_health_max"])
    _write_csv(paths.output_files["signal_availability_summary"],
               _signal_counts((reconstruction1, reconstruction2)),
               ["receiver", "gnss_id", "sig_id", "freq_id", "satellite_count",
                "epoch_count", "measurement_count"])
    pairing_rows = [{"category": "EXACT_PAIR", "count": len(pairs)}]
    pairing_rows.extend({"category": key, "count": value}
                        for key, value in sorted(Counter(row["code"] for row in pairing_failures).items()))
    _write_csv(paths.output_files["epoch_pairing_summary"], pairing_rows, ["category", "count"])
    stochastic = {
        "schema_version": "horizontal_literature.stochastic.v1", "trace_tuned": False,
        "pseudorange_floor_m": 0.50, "carrier_floor_cycles": 0.004,
        "doppler_floor_hz": 0.02, "selected_group": "GPS_L1_CA",
        "rawx_semantics": {
            "pseudorange_sigma_m": "max(0.50,0.01*2^prStdev)",
            "carrier_sigma_cycles": "max(0.004,0.004*cpStdev); cpStdev=15 invalid",
            "doppler_sigma_hz": "max(0.02,0.002*2^doStdev)",
        },
        "dd_covariance": "shared_pivot_correlations_preserved",
        "reference_policy": "highest_elevation_then_locktime_then_sv_id",
        "minimum_elevation_deg": 10.0, "minimum_cno_dbhz": 20,
    }
    paths.output_files["stochastic_contract"].parent.mkdir(parents=True, exist_ok=True)
    paths.output_files["stochastic_contract"].write_text(yaml.safe_dump(stochastic, sort_keys=True),
                                                          encoding="utf-8")
    manifest["stochastic_contract_hash"] = sha256_file(paths.output_files["stochastic_contract"])
    def reconstruction_audit(reconstruction: Any) -> dict[str, Any]:
        epochs = reconstruction.rawx_epochs
        return {
            "input_cell_count": reconstruction.input_cell_count,
            "reconstructed_stream_bytes": len(reconstruction.stream),
            "reconstructed_stream_sha256": hashlib.sha256(reconstruction.stream).hexdigest(),
            "rawx_epoch_count": len(epochs),
            "rawx_gps_week_min": min(epoch.gps_week for epoch in epochs),
            "rawx_gps_week_max": max(epoch.gps_week for epoch in epochs),
            "rawx_tow_first_seconds": epochs[0].gps_tow_seconds,
            "rawx_tow_last_seconds": epochs[-1].gps_tow_seconds,
            "sfrbx_message_count": len(reconstruction.sfrbx_messages),
            "sfrbx_nonzero_reserved1_count": sum(
                message.reserved1 != 0 for message in reconstruction.sfrbx_messages
            ),
            "sfrbx_nonzero_reserved2_count": sum(
                message.reserved2 != 0 for message in reconstruction.sfrbx_messages
            ),
            "nav_sat_epoch_count": len(reconstruction.nav_sat_epochs),
            "message_counts": reconstruction.message_counts,
            "checksum_failure_count": reconstruction.checksum_failure_count,
            "discarded_byte_count": reconstruction.discarded_byte_count,
        }

    all_ephemeris_ages = [
        float(value) for row in diagnostics for value in row.get("_ephemeris_ages", ())
    ]
    all_ephemeris_health = [
        int(value) for row in diagnostics for value in row.get("_ephemeris_health", ())
    ]
    elevation_audit = _nav_sat_elevation_audit(reconstruction1, pairs, diagnostics)
    if not elevation_audit["sanity_pass"]:
        raise Phase1RunnerError("broadcast elevation does not pass the NAV-SAT diagnostic gate")
    if (not all_ephemeris_ages or not all_ephemeris_health
            or max(all_ephemeris_health) != 0
            or max(abs(value) for value in all_ephemeris_ages) > 7201.0):
        raise Phase1RunnerError("used broadcast ephemeris failed age/health sanity")
    raw_audit = {
        "receiver1": reconstruction_audit(reconstruction1),
        "receiver2": reconstruction_audit(reconstruction2),
        "raw_source_hashes": manifest["raw_source_hashes"],
        "raw_hash_lock_sha256": manifest["raw_hash_lock_sha256"],
        "raw_hashes_validated": manifest["raw_hashes_validated"],
        "exact_paired_epoch_count": len(pairs),
        "pairing_failure_count": len(pairing_failures),
        "convbin_commands": [[Path(value).name if index == 0 else value
                              for index, value in enumerate(command)] for command in convbin_commands],
        "ephemeris_counts": provider.ephemeris_counts,
        "used_ephemeris_state_count": len(all_ephemeris_ages),
        "used_ephemeris_signed_age_seconds": _percentiles(all_ephemeris_ages),
        "used_ephemeris_absolute_age_seconds": _percentiles(abs(value) for value in all_ephemeris_ages),
        "used_ephemeris_health_max": max(all_ephemeris_health) if all_ephemeris_health else None,
        "satellite_state_sanity": {
            "finite_position_velocity_clock_variance_required_by_adapter": True,
            "ecef_radius_bounds_m": [20_000_000.0, 50_000_000.0],
            "line_of_sight_unit_norm_required_by_backend": True,
        },
        "nav_sat_elevation_diagnostic": elevation_audit,
        "provider_hashes": manifest["provider_hashes"],
        "intermediate_artifact_hashes": manifest["intermediate_artifact_hashes"],
        "external_dependency": manifest["external_dependency"],
        "trace_open_count": 0,
    }
    _write_json(paths.output_files["raw_observation_audit"], raw_audit)
    success = [row for row in results if row["status"] == "SUCCESS"]
    lengths = [float(row["baseline_length_m"]) for row in success]
    headings = [float(row["body_yaw_deg"]) for row in success]
    objectives = [float(row["constrained_objective"]) for row in success]
    length_errors = np.asarray(lengths, dtype=float) - 0.350
    baseline_statistics = {
        **_percentiles(lengths),
        "rmse_to_0_350_m": (float(np.sqrt(np.mean(length_errors ** 2)))
                             if length_errors.size else None),
        "p95_absolute_error_m": (float(np.percentile(np.abs(length_errors), 95))
                                  if length_errors.size else None),
        "p99_absolute_error_m": (float(np.percentile(np.abs(length_errors), 99))
                                  if length_errors.size else None),
        "max_absolute_error_m": (float(np.max(np.abs(length_errors)))
                                  if length_errors.size else None),
        "in_gate_0_20_to_0_60_rate": (float(np.mean((np.asarray(lengths) >= 0.20)
                                                     & (np.asarray(lengths) <= 0.60)))
                                      if lengths else 0.0),
    }
    _write_csv(paths.output_files["baseline_summary"],
               [{"metric": key, "value": value} for key, value in baseline_statistics.items()],
               ["metric", "value"])
    ambiguity_statistics: dict[str, Any] = {}
    for prefix, values in (
        ("candidate_count", (row["candidate_count"] for row in runtimes)),
        ("search_nodes", (row["search_nodes"] for row in runtimes)),
        ("constrained_objective", objectives),
        ("ratio", (row["ratio"] for row in success if row["ratio"] is not None)),
        ("residual_norm", (row["residual_norm"] for row in success
                           if row["residual_norm"] is not None)),
    ):
        ambiguity_statistics.update({f"{prefix}_{key}": value
                                     for key, value in _percentiles(values).items()})
    _write_csv(paths.output_files["ambiguity_summary"],
               [{"metric": key, "value": value} for key, value in ambiguity_statistics.items()],
               ["metric", "value"])
    fixed_count = sum(row["solution_type"] == "fixed" for row in results)
    float_count = sum(row["solution_type"] == "float" for row in results)
    invalid_count = sum(row["solution_type"] == "invalid" for row in results)
    summary = {
        "data_mode": "real_by2_raw", "evaluation": "NOT_EVALUATED",
        "receiver1_input_epoch_count": len(reconstruction1.rawx_epochs),
        "receiver2_input_epoch_count": len(reconstruction2.rawx_epochs),
        "paired_epoch_count": len(pairs), "attempted_epoch_count": len(results),
        "success_row_count": len(success), "failure_row_count": len(failures),
        "fixed_row_count": fixed_count, "float_row_count": float_count,
        "invalid_row_count": invalid_count,
        "fixed_rate": fixed_count / len(pairs) if pairs else 0.0,
        "float_rate": float_count / len(pairs) if pairs else 0.0,
        "invalid_rate": invalid_count / len(pairs) if pairs else 0.0,
        "availability": len(success) / len(pairs) if pairs else 0.0,
        "baseline_length_statistics_m": baseline_statistics,
        "native_body_yaw_statistics_deg": _circular_heading_statistics(headings),
        "continuity": _success_continuity(results),
        "candidate_objective_residual_diagnostics": ambiguity_statistics,
        "runtime_statistics_seconds": _percentiles(row["runtime_seconds"] for row in runtimes),
        "failure_classification": dict(sorted(Counter(row["failure_code"] for row in failures).items())),
        "nav_sat_elevation_sanity": elevation_audit,
        "trace_used_online": False,
    }
    _write_json(paths.output_files["native_summary"], summary)
    report = (
        "# Phase 1 EXT01 C00 Native Report\n\n"
        f"Terminal: `{PASS_STATUS}`\n\n"
        f"Exact pairs: {len(pairs)}; fixed: {fixed_count}; float: {float_count}; "
        f"invalid: {invalid_count}; "
        f"availability: {summary['availability']:.6f}.\n\n"
        f"Runtime mean/P95/P99/max: "
        f"{summary['runtime_statistics_seconds']['mean']}/"
        f"{summary['runtime_statistics_seconds']['p95']}/"
        f"{summary['runtime_statistics_seconds']['p99']}/"
        f"{summary['runtime_statistics_seconds']['max']} s.\n\n"
        "The native path used GPS L1 C/A double differences, RTKLIB broadcast "
        "satellite states and standard LAMBDA reduction/seeds, followed by an exact "
        "fixed-0.350 m continuous-relaxation branch-and-bound. A timeout is retained "
        "as an invalid epoch and is never replaced.\n\n"
        "Trace remained unopened. Heading values are native descriptive outputs only; "
        "evaluation is NOT_EVALUATED.\n\n"
        "## Reproduction\n\n"
        "```bash\n"
        "python3 scripts/paper_rebuild/run_horizontal_literature_phase1.py \\\n"
        "  --paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml \\\n"
        "  --method-id EXT01_CLAMBDA --case-id C00 --trace-mode disabled\n"
        "```\n"
    )
    paths.output_files["phase1_report"].parent.mkdir(parents=True, exist_ok=True)
    paths.output_files["phase1_report"].write_text(report, encoding="utf-8")
    manifest.update(summary)
    manifest["conservation"] = "PASS"
    # Self-hashing PHASE1_STATUS.json is impossible; hash every other contract output.
    manifest["output_hashes"] = {
        key: sha256_file(path) for key, path in paths.output_files.items()
        if key != "phase1_status" and path.is_file()
    }
    manifest["status"] = PASS_STATUS
    manifest["output_files"] = {key: str(path) for key, path in paths.output_files.items()}
    _write_json(paths.output_files["phase1_status"], manifest)
    return manifest


def _execute_after_stage_created(paths: Phase1Paths, config_path: Path,
                                 raw_hashes: Mapping[str, str],
                                 external_dependency: Mapping[str, Any]) -> dict[str, Any]:
    backend_root = paths.stage_root / "01_SHARED_RAW_BACKEND"
    ubx1, ubx2 = backend_root / "gnss1_reconstructed.ubx", backend_root / "gnss2_reconstructed.ubx"
    reconstruction1 = reconstruct_ubx_stream(paths.receiver1_raw, ubx1)
    reconstruction2 = reconstruct_ubx_stream(paths.receiver2_raw, ubx2)
    navigation_paths: list[Path] = []
    convbin_commands: list[list[str]] = []
    for index, ubx in enumerate((ubx1, ubx2), 1):
        observation = backend_root / f"gnss{index}_reconstructed.obs"
        navigation = backend_root / f"gnss{index}_reconstructed.nav"
        convbin_commands.append(_run_convbin(paths.convbin, ubx, observation, navigation))
        navigation_paths.append(navigation)
    pairs, pairing_failures = pair_epochs(reconstruction1.rawx_epochs, reconstruction2.rawx_epochs)
    manifest = runtime_manifest_template(paths, config_sha256(config_path), _code_commit(paths))
    manifest["raw_source_hashes"] = raw_hashes
    manifest["raw_hash_lock_sha256"] = sha256_file(paths.raw_hash_lock)
    manifest["raw_hashes_validated"] = True
    manifest["external_dependency"] = external_dependency
    implementation_paths = (
        paths.code_root / "src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py",
        paths.code_root / "src/legsa_gins/paper_rebuild/horizontal_literature/ext01_clambda.py",
        paths.code_root / "src/legsa_gins/paper_rebuild/horizontal_literature/phase1_runner.py",
        paths.code_root / "scripts/paper_rebuild/run_horizontal_literature_phase1.py",
    )
    manifest["implementation_source_hashes"] = {
        str(path.relative_to(paths.code_root)): sha256_file(path) for path in implementation_paths
    }
    manifest["provider_hashes"] = {
        "convbin": sha256_file(paths.convbin), "rtklib_bridge": sha256_file(paths.rtklib_bridge),
        "lambda_library": sha256_file(paths.lambda_library),
        "rtklib_license": sha256_file(paths.rtklib_root / "LICENSE.txt"),
        **{f"thin_adapter_source:{name}": digest for name, digest in
           external_dependency["local_thin_adapter"]["source_hashes"].items()},
        **{f"navigation_{index}": sha256_file(path)
           for index, path in enumerate(navigation_paths, 1)},
    }
    intermediate_paths = {
        name: paths.stage_root / relative
        for name, relative in INTERMEDIATE_RELATIVE_PATHS.items()
    }
    if any(not path.is_file() for path in intermediate_paths.values()):
        raise Phase1RunnerError("a declared reconstructed intermediate is missing")
    manifest["intermediate_artifact_paths"] = {
        name: str(path) for name, path in intermediate_paths.items()
    }
    manifest["intermediate_artifact_hashes"] = {
        name: sha256_file(path) for name, path in intermediate_paths.items()
    }
    with RtklibBroadcastProvider(paths.rtklib_bridge, navigation_paths) as provider:
        results, failures, runtimes, tracking, diagnostics = _process_pairs(paths, pairs, provider)
        if not pairs or len(results) != len(pairs) or len(runtimes) != len(pairs):
            raise Phase1RunnerError("paired-epoch row conservation failed")
        if len(results) != sum(row["status"] == "SUCCESS" for row in results) + len(failures):
            raise Phase1RunnerError("success/failure conservation failed")
        return _write_outputs(paths, manifest, reconstruction1, reconstruction2, pairs,
                              pairing_failures, results, failures, runtimes, tracking,
                              diagnostics, convbin_commands, provider)


def run_phase1(config_path: Path, trace_mode: str,
               method_id: str = "EXT01_CLAMBDA", case_id: str = "C00") -> dict[str, Any]:
    if method_id != "EXT01_CLAMBDA" or case_id != "C00":
        raise Phase1RunnerError("Phase 1 method/case must be EXT01_CLAMBDA/C00")
    if trace_mode != "disabled":
        raise Phase1RunnerError("Phase 1 trace mode must be literal 'disabled'")
    paths = load_paths(config_path)
    blocked = validate_sources_before_output(paths)
    if blocked is not None:
        return blocked
    external_dependency = _external_dependency_audit(paths)
    lock = read_hash_lock(paths.raw_hash_lock)
    raw_hashes = verify_raw_sources(paths.raw_root, _raw_relatives(paths), lock)
    paths.stage_root.mkdir(parents=True, exist_ok=False)
    try:
        return _execute_after_stage_created(
            paths, config_path, raw_hashes, external_dependency
        )
    except Exception as exc:  # preserve a machine terminal for every post-mkdir failure
        terminal = _terminal("BLOCKED_PHASE1_EXT01_C00_RUNTIME_FAILURE")
        terminal.update({
            "error_type": type(exc).__name__, "error": str(exc),
            "raw_source_hashes": dict(raw_hashes), "raw_hashes_validated": True,
            "trace_used_online": False, "canonical541_accessed": False,
            "stage_root": str(paths.stage_root), "partial_stage_preserved": True,
            "produced_files": sorted(
                str(path.relative_to(paths.stage_root))
                for path in paths.stage_root.rglob("*") if path.is_file()
            ),
            "output_files": {"phase1_status": str(paths.output_files["phase1_status"])},
        })
        status_path = paths.output_files["phase1_status"]
        _write_json(status_path, terminal)
        return terminal


def config_sha256(config_path: Path) -> str:
    return hashlib.sha256(config_path.read_bytes()).hexdigest()


def terminal_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
