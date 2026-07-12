"""Fresh exact-tag versus active-port parity for CLEAN1R2R1.

This module never opens the evaluation trace.  It accepts only a sealed
``clean_real_final_v23`` input manifest, builds the recovered tag source in an
attempt-owned copy, runs both solvers on the same 7/15-column files, and emits
engineering parity evidence.  Exact output is comparison material only and is
never passed to the active solver.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Iterable, Mapping, Sequence

from legsa_gins.paper_rebuild.final_v23_clean_input import load_clean_input_manifest
from legsa_gins.paper_rebuild.manifest import git_code_state


STAGE_ID = "CLEAN1R2R1_CLEAN_REAL_FINAL_V23_PARITY_AND_FOUR_METHOD_EXECUTION"
PROTOCOL_ID = "CLEAN_REAL_DATA_FINAL_V23"
CASE_ID = "CLEAN1_BY2_CLEAN_NORMAL"
TAG_NAME = "final-v23-freeze"
TAG_COMMIT = "a906c3a2e704eddbd15ceb3f98f1ba8de85dc410"
ARCHIVE_SHA256 = "45953164c53e102a4ce7e99912535b484d60420ef0de20466252446f3d76b716"
TAG_RECOVERY_MANIFEST_SHA256 = (
    "a7fa381903e44d349a60057db782cedbf3dbacd3aede6190efe6ad56ac0353d3"
)
TAG_SOURCE_MANIFEST_SHA256 = (
    "cd4792658ddbe3d0986718313952e9b84004dd6733bd3877b2858f70817c7df7"
)

REQUIRED_TAG_HASHES = {
    "CMakeLists.txt": "9f023d1e2726f8149e3eb13bafec4f64b65d3cc5146def4348a5456664c43be4",
    "src/kf_gins.cpp": "1c2ca089dd97a6daebb07d2c4b8f3ceaaa0a0b6146e125d4f659a28e7de9f8d9",
    "src/kf-gins/gi_engine.cpp": "9c47637868b399afde9432e6ae8931638b02a2a11048f61f1d1653b48303392e",
    "src/kf-gins/gi_engine.h": "97b66d3baef2d5eb139353907b184d36d1b8f4cef2659895ccb94496b6f56e9c",
    "src/kf-gins/kf_gins_types.h": "aac640a7fc746ca8b05f5ee7384a9d5141f5ec4b83f1e9c91d255e0ec1a76bab",
    "src/kf-gins/insmech.cpp": "08fddbc4ffe157fcd5d7c236ee008dad6a300a2a0f505760796c79f6ccd2b93c",
    "src/fileio/filesaver.cc": "531e5fa5c1c98fff8f87564150ca385b8a668602430b8c13f48cc7aef393c54c",
}


class FinalV23ParityError(RuntimeError):
    """Fail-closed parity/build/run error."""


@dataclass(frozen=True)
class ParityTolerances:
    """Tracked pre-output float64/format bound; never fitted to run metrics."""

    timestamp_exact_abs_sec: float = 1.0e-9
    horizontal_rmse_m: float = 0.02
    horizontal_max_m: float = 0.10
    up_rmse_m: float = 0.02
    up_max_m: float = 0.10
    velocity_3d_rmse_mps: float = 0.002
    velocity_3d_max_mps: float = 0.01
    roll_rmse_deg: float = 0.002
    pitch_rmse_deg: float = 0.002
    yaw_rmse_deg: float = 0.002
    attitude_max_abs_deg: float = 0.01
    std_max_normalized_rmse: float = 0.01
    std_max_normalized_max: float = 0.05


FROZEN_TOLERANCES = ParityTolerances()


@dataclass(frozen=True)
class CleanInputBundle:
    manifest_path: Path
    manifest: dict[str, Any]
    imu_path: Path
    gnss_path: Path


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _run(command: Sequence[str], *, cwd: Path, log_prefix: Path, timeout: int,
         failure_code: str = "BLOCKED_CLEAN1R2R1_ACTIVE_PORT_PARITY_FAILED") -> subprocess.CompletedProcess[str]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            list(command), cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise FinalV23ParityError(f"{failure_code}: command timed out: {command[0]}") from exc
    log_prefix.parent.mkdir(parents=True, exist_ok=True)
    log_prefix.with_suffix(".stdout.txt").write_text(completed.stdout, encoding="utf-8")
    log_prefix.with_suffix(".stderr.txt").write_text(completed.stderr, encoding="utf-8")
    _write_json(
        log_prefix.with_suffix(".command.json"),
        {"command": list(command), "cwd": str(cwd), "returncode": completed.returncode,
         "elapsed_seconds": time.monotonic() - started},
    )
    if completed.returncode != 0:
        raise FinalV23ParityError(f"{failure_code}: command failed ({completed.returncode}): {command[0]}")
    return completed


def load_clean_bundle(manifest_path: str | Path) -> CleanInputBundle:
    source = Path(manifest_path).resolve(strict=True)
    payload = load_clean_input_manifest(source)
    if payload.get("profile_id") != "clean_real_final_v23":
        raise FinalV23ParityError("clean profile identity mismatch")
    forbidden = {
        "trace_used_online": False,
        "yaw_noise_injection_enabled": False,
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "receiver_imu_as_body_imu": False,
        "legacy_input_payload_used": False,
        "E001_old_input_used_by_solver": False,
    }
    for field, expected in forbidden.items():
        if payload.get(field) is not expected:
            raise FinalV23ParityError(f"clean input forbidden field mismatch: {field}")
    if payload.get("trace_open_count_during_input_generation") != 0:
        raise FinalV23ParityError("clean input trace-open count is nonzero")
    root = source.parent
    imu = (root / payload["artifacts"]["imu"]["relative_path"]).resolve(strict=True)
    gnss = (root / payload["artifacts"]["gnss"]["relative_path"]).resolve(strict=True)
    return CleanInputBundle(source, payload, imu, gnss)


def validate_and_copy_exact_tag_source(tag_recovery_root: str | Path, destination: str | Path) -> dict[str, Any]:
    root = Path(tag_recovery_root).resolve(strict=True)
    terminal_path = root / "FINAL_V23_TAG_SOURCE_RECOVERY_MANIFEST.json"
    manifest_path = root / "TAG_SOURCE_MANIFEST.csv"
    if sha256_file(terminal_path) != TAG_RECOVERY_MANIFEST_SHA256:
        raise FinalV23ParityError("exact tag recovery manifest SHA256 mismatch")
    if sha256_file(manifest_path) != TAG_SOURCE_MANIFEST_SHA256:
        raise FinalV23ParityError("exact tag source manifest SHA256 mismatch")
    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
    if terminal.get("terminal_decision") != "APPROVED_EXACT_FINAL_V23_SOLVER_TAG_SOURCE_RECOVERY":
        raise FinalV23ParityError("exact tag recovery is not approved")
    if terminal.get("tag_name") != TAG_NAME or terminal.get("tag_commit") != TAG_COMMIT:
        raise FinalV23ParityError("exact tag identity mismatch")
    if terminal.get("archive_sha256") != ARCHIVE_SHA256:
        raise FinalV23ParityError("exact tag archive identity mismatch")
    source_root = root / "tag_source"
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    destination = Path(destination)
    if destination.exists():
        raise FinalV23ParityError("attempt exact-source destination already exists")
    destination.mkdir(parents=True)
    # This is a 21-MB static source closure, not a repeat of the 18-GB archive
    # inventory. A single sha256sum batch avoids slow per-entry Path.resolve on
    # drvfs while still rechecking every blob before an attempt-owned copy.
    seen: dict[str, str] = {}
    materialized_hash = hashlib.sha256()
    for row in rows:
        relative = Path(row["path"])
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or "\n" in row["path"]
            or "\r" in row["path"]
        ):
            raise FinalV23ParityError("unsafe exact tag manifest path")
        relative_text = relative.as_posix()
        seen[relative_text] = row["sha256"]
        materialized_hash.update(relative_text.encode("utf-8") + b"\0" + row["sha256"].encode("ascii") + b"\n")
    checkfile = destination.parent / f".{destination.name}.sha256-check"
    checkfile.write_text(
        "".join(f'{row["sha256"]}  {row["path"]}\n' for row in rows),
        encoding="utf-8",
    )
    try:
        checked = subprocess.run(
            ["sha256sum", "--check", "--strict", "--quiet", str(checkfile)],
            cwd=source_root,
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
        if checked.returncode != 0:
            raise FinalV23ParityError(
                "exact tag full source hash check failed: " + checked.stderr[-1000:]
            )
        copied = subprocess.run(
            ["cp", "-a", "--", str(source_root) + "/.", str(destination)],
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
        if copied.returncode != 0:
            raise FinalV23ParityError(
                "attempt-owned exact source copy failed: " + copied.stderr[-1000:]
            )
    finally:
        checkfile.unlink(missing_ok=True)
    for relative, expected in REQUIRED_TAG_HASHES.items():
        if seen.get(relative) != expected:
            raise FinalV23ParityError(f"required exact source identity mismatch: {relative}")
    return {"file_count": len(rows), "manifest_sha256": TAG_SOURCE_MANIFEST_SHA256,
            "recovery_manifest_sha256": TAG_RECOVERY_MANIFEST_SHA256,
            "required_hashes": REQUIRED_TAG_HASHES, "tag_commit": TAG_COMMIT,
            "full_blob_closure_reused_from_approved_recovery": True,
            "full_blob_hash_recheck_count": len(rows),
            "materialized_tree_hash": materialized_hash.hexdigest(),
            "attempt_owned_source_copy": True, "external_dependency_symlink_count": 0}


def validate_materialized_tag_source(source_root: Path, tag_recovery_root: str | Path) -> dict[str, Any]:
    manifest_path = Path(tag_recovery_root) / "TAG_SOURCE_MANIFEST.csv"
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    closure = hashlib.sha256()
    for row in rows:
        relative = Path(row["path"])
        closure.update(relative.as_posix().encode("utf-8") + b"\0" + row["sha256"].encode("ascii") + b"\n")
    checkfile = source_root.parent / f".{source_root.name}.post.sha256-check"
    checkfile.write_text(
        "".join(f'{row["sha256"]}  {row["path"]}\n' for row in rows),
        encoding="utf-8",
    )
    try:
        checked = subprocess.run(
            ["sha256sum", "--check", "--strict", "--quiet", str(checkfile)],
            cwd=source_root,
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
        if checked.returncode != 0:
            raise FinalV23ParityError("materialized exact source changed")
        symlinks = subprocess.run(
            ["find", str(source_root), "-type", "l", "-print", "-quit"],
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if symlinks.returncode != 0 or symlinks.stdout.strip():
            raise FinalV23ParityError("materialized exact source contains a symlink")
    finally:
        checkfile.unlink(missing_ok=True)
    return {"file_count": len(rows), "manifest_match": True, "materialized_tree_hash": closure.hexdigest()}


def exact_runtime_yaml(imu: Path, gnss: Path, output: Path) -> str:
    def q(path: Path) -> str:
        return json.dumps(str(path))
    return f"""# CLEAN1R2R1 attempt-owned exact-tag runtime adapter.
imupath: {q(imu)}
gnsspath: {q(gnss)}
outputpath: {q(output)}
gnss_format: 0
imudatalen: 7
imudatarate: 500
imudataincremental: 1
imudataformat: 0
starttime: 66.0
endtime: 340.0
initpos: [39.98482973, 116.34312609, 41.80208107]
initvel: [0.0, 0.0, 0.0]
initatt: [0.0, 0.0, 0.688505]
initgyrbias: [0.0, 0.0, 0.0]
initaccbias: [0.0, 0.0, 0.0]
initgyrscale: [0.0, 0.0, 0.0]
initaccscale: [0.0, 0.0, 0.0]
initposstd: [10.0, 10.0, 10.0]
initvelstd: [1.0, 1.0, 1.0]
initattstd: [2.0, 2.0, 2.0]
imunoise:
  arw: [0.985, 0.985, 0.985]
  vrw: [0.077, 0.077, 0.077]
  gbstd: [9.38, 9.38, 9.38]
  abstd: [77.8, 77.8, 77.8]
  gsstd: [0.0, 0.0, 0.0]
  asstd: [0.0, 0.0, 0.0]
  corrtime: 1.0
antlever: [0.03, 0.03, -0.30]
"""


METHOD_FEATURES: dict[str, dict[str, bool]] = {
    "single_antenna_EKF": {"dual": False, "receiver": True, "raw": False, "source_aware": False,
                            "go2_roll_pitch": False, "go2_horizontal": False},
    "basic_dual_yaw_EKF": {"dual": True, "receiver": False, "raw": False, "source_aware": False,
                            "go2_roll_pitch": False, "go2_horizontal": False},
    "strong_dual_yaw_EKF": {"dual": True, "receiver": True, "raw": False, "source_aware": False,
                             "go2_roll_pitch": False, "go2_horizontal": False},
    "LegSA_Paper_V1": {"dual": True, "receiver": True, "raw": True, "source_aware": True,
                       "go2_roll_pitch": True, "go2_horizontal": True},
}


def active_runtime_config(imu: Path, gnss: Path, output: Path, *,
                          method_id: str = "strong_dual_yaw_EKF",
                          auxiliary_paths: Mapping[str, str | Path] | None = None,
                          extra_config: Mapping[str, str | int | float | bool] | None = None,
                          run_id: str | None = None) -> str:
    """Build the common clean-final-v23 config for parity or four methods.

    ``auxiliary_paths`` may bind ``raw_doppler``, ``go2_roll_pitch`` and
    ``go2_horizontal_velocity`` for ``LegSA_Paper_V1``.  Lineage-specific raw
    Doppler fields remain explicit in ``extra_config``; no fallback is guessed.
    """
    if method_id not in METHOD_FEATURES:
        raise FinalV23ParityError("method is outside the frozen four-method set")
    features = METHOD_FEATURES[method_id]
    auxiliary_paths = dict(auxiliary_paths or {})
    required_auxiliary = {
        "raw": "raw_doppler", "go2_roll_pitch": "go2_roll_pitch",
        "go2_horizontal": "go2_horizontal_velocity",
    }
    for flag, role in required_auxiliary.items():
        if features[flag] and role not in auxiliary_paths:
            raise FinalV23ParityError(f"enabled method is missing auxiliary path: {role}")
    effective_run_id = run_id or ("final_v23_parity_EKF" if method_id == "strong_dual_yaw_EKF" else method_id)
    values = {
        "clean1_formal_mode": "true", "clean_final_v23_parity_mode": "true",
        "stage_id": STAGE_ID, "protocol_id": PROTOCOL_ID, "case_id": CASE_ID,
        "data_mode": "real_by2_raw", "run_id": effective_run_id,
        "run_label": effective_run_id, "algorithm_id": method_id,
        "imupath": json.dumps(str(imu)), "gnsspath": json.dumps(str(gnss)),
        "outputpath": json.dumps(str(output)), "propagation_imu_source": "hash_locked_go2_body",
        "solver_output_reference_point": "propagation_imu_reference_point",
        "antlever_config_source": "runtime_config_antlever",
        "evaluation_reference_point_match_established": "false", "reference_point_compensation_applied": "false",
        "common_initialization": "true", "common_initialization_dual_yaw_used": "true",
        "trace_used_for_initialization": "false", "method_specific_initialization": "false",
        "common_initialization_source": "final_v23_static_contract_a906c3a2",
        "imudatalen": "7", "imudatarate": "500", "starttime": "66.0", "endtime": "340.0",
        "initpos": "[39.98482973, 116.34312609, 41.80208107]", "initvel": "[0, 0, 0]",
        "initatt": "[0, 0, 0.688505]", "initgyrbias": "[0, 0, 0]",
        "initaccbias": "[0, 0, 0]", "initgyrscale": "[0, 0, 0]", "initaccscale": "[0, 0, 0]",
        "initposstd": "[10, 10, 10]", "initvelstd": "[1, 1, 1]", "initattstd": "[2, 2, 2]",
        "arw": "[0.985, 0.985, 0.985]", "vrw": "[0.077, 0.077, 0.077]",
        "gbstd": "[9.38, 9.38, 9.38]", "abstd": "[77.8, 77.8, 77.8]",
        "gsstd": "[0, 0, 0]", "asstd": "[0, 0, 0]", "corrtime": "1.0",
        "antlever": "[0.03, 0.03, -0.30]", "initbgstd": "[9.38, 9.38, 9.38]",
        "initbastd": "[77.8, 77.8, 77.8]", "initsgstd": "[0, 0, 0]", "initsastd": "[0, 0, 0]",
        "enable_dual_yaw": str(features["dual"]).lower(),
        "enable_receiver_velocity": str(features["receiver"]).lower(),
        "enable_raw_doppler": str(features["raw"]).lower(),
        "enable_source_aware": str(features["source_aware"]).lower(),
        "enable_go2_roll_pitch_prior": str(features["go2_roll_pitch"]).lower(),
        "enable_go2_horizontal_velocity_prior": str(features["go2_horizontal"]).lower(),
        "basic_dual_yaw_fixed_std_deg": "1.5",
        "raw_doppler_factor_path": json.dumps(str(auxiliary_paths.get("raw_doppler", ""))),
        "go2_attitude_prior_path": json.dumps(str(auxiliary_paths.get("go2_roll_pitch", ""))),
        "go2_horizontal_velocity_prior_path": json.dumps(str(auxiliary_paths.get("go2_horizontal_velocity", ""))),
        "go2_horizontal_velocity_prior_vertical_disabled": "true",
        "go2_horizontal_velocity_prior_mode": "horizontal_2d",
        "receiver_velocity_stress_mode": "none", "receiver_velocity_std_scale": "1.0",
        "receiver_velocity_outage_start_sec": "0", "receiver_velocity_outage_duration_sec": "0",
        "receiver_velocity_additive_noise_std_mps": "0", "diagnostic_stress_only": "false",
        "yaw_std_min_deg": "0.5", "yaw_std_soft_deg": "3", "yaw_std_hard_deg": "6",
        "yaw_res_soft_deg": "6", "yaw_res_hard_deg": "15", "yaw_downweight_scale": "2.5",
        "enable_selected_fgo_feedback": "false", "enable_no_feedback_fgo": "false",
        "enable_active_nine_factor_fgo": "false", "enable_multi_state_qm": "false",
        "enable_qa_fallback": "false", "enable_go2_joint_factor": "false", "enable_contact_fk_factor": "false",
        "go2_position_truth_claim": "false", "go2_velocity_truth_claim": "false",
        "go2_yaw_truth_claim": "false", "go2_contact_truth_claim": "false",
        "trace_used_online": "false", "receiver_imu_as_body_imu": "false", "synthetic_data_used": "false",
        "semisynthetic_data_used": "false", "final_v23_output_solver_input": "false",
        "LegSA_output_solver_input": "false", "per_case_tuning": "false", "output_only_correction": "false",
        "epoch_deleted_for_metric": "false", "old_runtime_input_count": "0",
        "legacy_provider_input_count": "0", "legacy_row_input_count": "0", "legacy_aggregate_input_count": "0",
        "status_fallback_used": "false", "legacy_provider_used": "false", "paper_performance_claim": "false",
    }
    for key, value in (extra_config or {}).items():
        if isinstance(value, bool):
            values[key] = str(value).lower()
        elif isinstance(value, Path):
            values[key] = json.dumps(str(value))
        else:
            values[key] = str(value)
    return "# CLEAN1R2R1 active common-contract config.\n" + "".join(
        f"{key}: {value}\n" for key, value in values.items()
    )


def _data_rows(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or any(ch.isalpha() for ch in stripped.split(",")[0]):
            continue
        rows.append([float(value) for value in stripped.replace(",", " ").split()])
    return rows


def load_exact_nav(path: Path) -> list[dict[str, float]]:
    rows = _data_rows(path)
    if any(len(row) != 11 for row in rows):
        raise FinalV23ParityError("exact NAV is not 11 columns")
    keys = ("time", "lat", "lon", "height", "vn", "ve", "vd", "roll", "pitch", "yaw")
    return [dict(zip(keys, row[1:])) for row in rows]


def load_active_nav(path: Path) -> list[dict[str, float]]:
    rows = _data_rows(path)
    if any(len(row) not in {10, 11} for row in rows):
        raise FinalV23ParityError(
            "active NAV is neither exact 11-column nor time+9-column format"
        )
    keys = ("time", "lat", "lon", "height", "vn", "ve", "vd", "roll", "pitch", "yaw")
    return [dict(zip(keys, row[1:] if len(row) == 11 else row)) for row in rows]


def load_exact_std(path: Path) -> list[tuple[float, list[float]]]:
    rows = _data_rows(path)
    if any(len(row) != 22 for row in rows):
        raise FinalV23ParityError("exact STD is not time+21 columns")
    return [(row[0], row[1:]) for row in rows]


def load_active_std(path: Path, nav: Sequence[Mapping[str, float]]) -> list[tuple[float, list[float]]]:
    rows = _data_rows(path)
    if len(rows) != len(nav) or any(len(row) != 22 for row in rows):
        raise FinalV23ParityError("active STD row-index+21 does not match active NAV")
    return [(float(nav[index]["time"]), row[1:]) for index, row in enumerate(rows)]


def _wrap_deg(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def _ecef(lat_deg: float, lon_deg: float, height: float) -> tuple[float, float, float]:
    a, e2 = 6378137.0, 6.69437999014e-3
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    n = a / math.sqrt(1.0 - e2 * math.sin(lat) ** 2)
    return ((n + height) * math.cos(lat) * math.cos(lon),
            (n + height) * math.cos(lat) * math.sin(lon),
            (n * (1.0 - e2) + height) * math.sin(lat))


def _ned_delta(exact: Mapping[str, float], active: Mapping[str, float]) -> tuple[float, float, float]:
    x0, y0, z0 = _ecef(exact["lat"], exact["lon"], exact["height"])
    x1, y1, z1 = _ecef(active["lat"], active["lon"], active["height"])
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    lat, lon = math.radians(exact["lat"]), math.radians(exact["lon"])
    east = -math.sin(lon) * dx + math.cos(lon) * dy
    north = -math.sin(lat) * math.cos(lon) * dx - math.sin(lat) * math.sin(lon) * dy + math.cos(lat) * dz
    up = math.cos(lat) * math.cos(lon) * dx + math.cos(lat) * math.sin(lon) * dy + math.sin(lat) * dz
    return north, east, up


def _rmse(values: Iterable[float]) -> float | None:
    values = list(values)
    return math.sqrt(sum(value * value for value in values) / len(values)) if values else None


def compare_outputs(exact_nav_path: Path, active_nav_path: Path, exact_std_path: Path,
                    active_std_path: Path, pointwise_path: Path,
                    tolerances: ParityTolerances = FROZEN_TOLERANCES) -> dict[str, Any]:
    exact_nav, active_nav = load_exact_nav(exact_nav_path), load_active_nav(active_nav_path)
    exact_std = load_exact_std(exact_std_path)
    active_std = load_active_std(active_std_path, active_nav)
    pair_count = min(len(exact_nav), len(active_nav), len(exact_std), len(active_std))
    fields = ["row", "exact_time", "active_time", "time_diff_sec", "north_diff_m", "east_diff_m",
              "up_diff_m", "horizontal_diff_m", "vn_diff_mps", "ve_diff_mps", "vd_diff_mps",
              "roll_diff_deg", "pitch_diff_deg", "yaw_diff_deg", "std_max_abs_diff", "std_max_normalized_diff"]
    pointwise_path.parent.mkdir(parents=True, exist_ok=True)
    horizontal: list[float] = []
    up: list[float] = []
    roll: list[float] = []
    pitch: list[float] = []
    yaw: list[float] = []
    velocity_norm: list[float] = []
    std_normalized: list[float] = []
    time_diffs: list[float] = []
    with gzip.open(pointwise_path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(pair_count):
            exact, active = exact_nav[index], active_nav[index]
            north, east, up_value = _ned_delta(exact, active)
            h = math.hypot(north, east)
            r = _wrap_deg(active["roll"] - exact["roll"])
            p = _wrap_deg(active["pitch"] - exact["pitch"])
            y = _wrap_deg(active["yaw"] - exact["yaw"])
            velocity = [active[name] - exact[name] for name in ("vn", "ve", "vd")]
            std_diff = [a - e for a, e in zip(active_std[index][1], exact_std[index][1])]
            std_norm = [abs(diff) / max(1.0, abs(exact_value))
                        for diff, exact_value in zip(std_diff, exact_std[index][1])]
            dt = active["time"] - exact["time"]
            writer.writerow({"row": index, "exact_time": exact["time"], "active_time": active["time"],
                             "time_diff_sec": dt, "north_diff_m": north, "east_diff_m": east,
                             "up_diff_m": up_value, "horizontal_diff_m": h, "vn_diff_mps": velocity[0],
                             "ve_diff_mps": velocity[1], "vd_diff_mps": velocity[2], "roll_diff_deg": r,
                             "pitch_diff_deg": p, "yaw_diff_deg": y,
                             "std_max_abs_diff": max(map(abs, std_diff), default=0.0),
                             "std_max_normalized_diff": max(std_norm, default=0.0)})
            horizontal.append(h); up.append(up_value); roll.append(r); pitch.append(p); yaw.append(y)
            velocity_norm.append(math.sqrt(sum(value * value for value in velocity)))
            std_normalized.append(max(std_norm, default=0.0)); time_diffs.append(abs(dt))
    metrics = {"horizontal_rmse_m": _rmse(horizontal), "horizontal_max_m": max(map(abs, horizontal), default=None),
               "up_rmse_m": _rmse(up), "up_max_m": max(map(abs, up), default=None),
               "roll_rmse_deg": _rmse(roll), "pitch_rmse_deg": _rmse(pitch), "yaw_rmse_deg": _rmse(yaw),
               "velocity_3d_rmse_mps": _rmse(velocity_norm),
               "velocity_3d_max_mps": max(velocity_norm, default=None),
               "std_max_normalized_rmse": _rmse(std_normalized),
               "std_max_normalized_max": max(std_normalized, default=None),
               "attitude_max_abs_deg": max(
                   [abs(value) for values in (roll, pitch, yaw) for value in values],
                   default=None,
               ),
               "max_abs_timestamp_diff_sec": max(time_diffs, default=None)}
    row_count_exact = len(exact_nav) == len(active_nav) == len(exact_std) == len(active_std) and bool(exact_nav)
    timestamp_exact = row_count_exact and max(time_diffs, default=math.inf) <= tolerances.timestamp_exact_abs_sec
    numerical_gate_fields = (
        "horizontal_rmse_m", "horizontal_max_m", "up_rmse_m", "up_max_m",
        "velocity_3d_rmse_mps", "velocity_3d_max_mps", "roll_rmse_deg",
        "pitch_rmse_deg", "yaw_rmse_deg", "attitude_max_abs_deg",
        "std_max_normalized_rmse", "std_max_normalized_max",
    )
    numerical_gate = all(
        metrics[name] is not None and metrics[name] <= getattr(tolerances, name)
        for name in numerical_gate_fields
    )
    return {"row_counts": {"exact_nav": len(exact_nav), "active_nav": len(active_nav),
                            "exact_std": len(exact_std), "active_std": len(active_std), "paired": pair_count},
            "row_count_exact": row_count_exact, "timestamp_exact": timestamp_exact,
            "metrics": metrics, "numerical_gate_fields": list(numerical_gate_fields),
            "nav_aggregate_gate_passed": numerical_gate,
            "velocity_and_std_gated": pair_count > 0,
            "pointwise_diff": pointwise_path.name}


def parse_exact_modes(stdout: str) -> list[str]:
    return re.findall(r"\[YAW-(NORMAL|DOWNWEIGHT|REJECT)\]", stdout)


def counter_audit(exact_modes: Sequence[str], active_manifest: Mapping[str, Any],
                  active_trace: Path, clean_gnss_path: Path) -> dict[str, Any]:
    trace_rows = list(csv.DictReader(active_trace.open("r", encoding="utf-8", newline="")))
    active_modes = [row["yaw_mode"] for row in trace_rows]
    in_window_times = [
        row[0] for row in _data_rows(clean_gnss_path) if 66.0 < row[0] <= 340.0
    ]
    exact_update_times = in_window_times[:len(exact_modes)]
    active_update_times = [float(row["gnss_time"]) for row in trace_rows]
    update_times_exact = (
        len(exact_update_times) == len(exact_modes) == len(active_update_times)
        and all(
            abs(expected_time - actual_time) <= FROZEN_TOLERANCES.timestamp_exact_abs_sec
            for expected_time, actual_time in zip(exact_update_times, active_update_times)
        )
    )
    expected = {"dual_yaw_attempt_count": len(exact_modes), "dual_yaw_normal_count": exact_modes.count("NORMAL"),
                "dual_yaw_downweight_count": exact_modes.count("DOWNWEIGHT"),
                "dual_yaw_reject_count": exact_modes.count("REJECT"),
                "dual_yaw_accepted_count": len(exact_modes) - exact_modes.count("REJECT"),
                "position_update_count": len(exact_modes), "receiver_velocity_update_count": len(exact_modes)}
    actual = {"dual_yaw_attempt_count": int(active_manifest.get("dual_yaw_attempt_count", -1)),
              "dual_yaw_normal_count": int(active_manifest.get("yaw_NORMAL", -1)),
              "dual_yaw_downweight_count": int(active_manifest.get("yaw_DOWNWEIGHT", -1)),
              "dual_yaw_reject_count": int(active_manifest.get("yaw_REJECT", -1)),
              "position_update_count": int(active_manifest.get("position_update_count", -1)),
              "receiver_velocity_update_count": int(active_manifest.get("receiver_velocity_update_count", -1))}
    actual["dual_yaw_accepted_count"] = int(
        active_manifest.get("dual_yaw_accepted_count", -1)
    )
    zero_extras = all(int(active_manifest.get(name, 0)) == 0 for name in (
        "raw_doppler_update_count", "source_aware_evaluation_count", "go2_roll_pitch_update_count",
        "go2_horizontal_velocity_update_count", "selected_fgo_feedback_update_count", "nine_factor_fgo_update_count",
        "multi_state_qm_update_count", "qa_fallback_count", "contact_fk_update_count"))
    return {"exact": expected, "active": actual, "counts_exact": expected == actual,
            "yaw_action_sequence_exact": list(exact_modes) == active_modes,
            "exact_update_timestamps": exact_update_times,
            "active_update_timestamps": active_update_times,
            "update_timestamps_exact": update_times_exact,
            "active_trace_row_count": len(trace_rows), "additional_modules_zero": zero_extras,
            "passed": expected == actual and list(exact_modes) == active_modes and update_times_exact and zero_extras}


def run_clean_final_v23_parity(*, repo_root: str | Path, tag_recovery_root: str | Path,
                               clean_input_manifest: str | Path, attempt_root: str | Path,
                               timeout_seconds: int = 1800, jobs: int = 2) -> dict[str, Any]:
    repo = Path(repo_root).resolve(strict=True)
    active_code_commit, active_worktree_dirty = git_code_state(repo)
    if active_worktree_dirty:
        raise FinalV23ParityError("active parity requires a clean Git worktree")
    attempt = Path(attempt_root)
    if attempt.exists():
        raise FinalV23ParityError("parity attempt root already exists")
    attempt.mkdir(parents=True)
    try:
        bundle = load_clean_bundle(clean_input_manifest)
    except Exception as exc:
        raise FinalV23ParityError(
            f"BLOCKED_CLEAN1R2R1_CLEAN_INPUT_GENERATION_FAILED: sealed manifest rejected: {exc}"
        ) from exc
    source = attempt / "exact_tag_source_copy"
    try:
        source_audit = validate_and_copy_exact_tag_source(tag_recovery_root, source)
    except (FinalV23ParityError, OSError, ValueError) as exc:
        raise FinalV23ParityError(
            f"BLOCKED_CLEAN1R2R1_EXACT_TAG_BUILD_FAILED: source validation failed: {exc}"
        ) from exc
    logs = attempt / "logs"
    exact_build = attempt / "exact_build"
    _run(["cmake", "-S", str(source), "-B", str(exact_build)], cwd=attempt,
         log_prefix=logs / "exact_cmake_configure", timeout=timeout_seconds,
         failure_code="BLOCKED_CLEAN1R2R1_EXACT_TAG_BUILD_FAILED")
    _run(["cmake", "--build", str(exact_build), "--target", "KF-GINS", "-j", str(jobs)], cwd=attempt,
         log_prefix=logs / "exact_cmake_build", timeout=timeout_seconds,
         failure_code="BLOCKED_CLEAN1R2R1_EXACT_TAG_BUILD_FAILED")
    exact_binary = source / "bin" / "KF-GINS"
    if not exact_binary.is_file():
        candidates = list(exact_build.rglob("KF-GINS"))
        if len(candidates) != 1:
            raise FinalV23ParityError("BLOCKED_CLEAN1R2R1_EXACT_TAG_BUILD_FAILED: fresh executable not uniquely found")
        exact_binary = candidates[0]
    exact_output = attempt / "exact_run" / "output"
    exact_output.mkdir(parents=True)
    exact_config = attempt / "exact_run" / "kf-gins.yaml"
    exact_config.write_text(exact_runtime_yaml(bundle.imu_path, bundle.gnss_path, exact_output), encoding="utf-8")
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("KF_GINS_FOOT") or key.startswith("KF_GINS_YAW"):
            env.pop(key)
    env["KF_GINS_FOOT_AWARE"] = "0"
    started = time.monotonic()
    try:
        exact = subprocess.run(
            [str(exact_binary), str(exact_config)],
            cwd=source,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FinalV23ParityError(
            f"BLOCKED_CLEAN1R2R1_EXACT_CLEAN_FINAL_V23_RUN_FAILED: {exc}"
        ) from exc
    (logs / "exact_run.stdout.txt").write_text(exact.stdout, encoding="utf-8")
    (logs / "exact_run.stderr.txt").write_text(exact.stderr, encoding="utf-8")
    if exact.returncode != 0:
        raise FinalV23ParityError(
            f"BLOCKED_CLEAN1R2R1_EXACT_CLEAN_FINAL_V23_RUN_FAILED: returncode={exact.returncode}"
        )
    exact_modes = parse_exact_modes(exact.stdout)
    exact_nav, exact_std, exact_imuerr = (exact_output / name for name in
        ("KF_GINS_Navresult.nav", "KF_GINS_STD.txt", "KF_GINS_IMU_ERR.txt"))
    if not all(path.is_file() for path in (exact_nav, exact_std, exact_imuerr)):
        raise FinalV23ParityError(
            "BLOCKED_CLEAN1R2R1_EXACT_CLEAN_FINAL_V23_RUN_FAILED: output set incomplete"
        )
    published_exact = {
        "EXACT_CLEAN_FINAL_V23_NAV.nav": exact_nav,
        "EXACT_CLEAN_FINAL_V23_STD.txt": exact_std,
        "EXACT_CLEAN_FINAL_V23_IMU_ERR.txt": exact_imuerr,
    }
    for name, source_output in published_exact.items():
        shutil.copyfile(source_output, attempt / name)
    try:
        source_tree_post_run = validate_materialized_tag_source(source, tag_recovery_root)
    except (FinalV23ParityError, OSError, ValueError, subprocess.SubprocessError) as exc:
        raise FinalV23ParityError(
            f"BLOCKED_CLEAN1R2R1_EXACT_CLEAN_FINAL_V23_RUN_FAILED: post-run source validation failed: {exc}"
        ) from exc
    exact_manifest = {"schema_version": "paper_rebuild.exact_clean_final_v23_run.v1", "stage_id": STAGE_ID,
        "tag": TAG_NAME, "tag_commit": TAG_COMMIT, "fresh_build": True, "binary_sha256": sha256_file(exact_binary),
        "source_audit": source_audit, "runtime_config_sha256": sha256_file(exact_config),
        "input_manifest_sha256": sha256_file(bundle.manifest_path), "imu_sha256": sha256_file(bundle.imu_path),
        "gnss_sha256": sha256_file(bundle.gnss_path), "data_mode": "real_by2_raw", "trace_used_online": False,
        "semisynthetic_data_used": False, "legacy_solver_input": False, "yaw_noise_injection_enabled": False,
        "yaw_measurement_std_deg": 1.5, "returncode": exact.returncode,
        "elapsed_seconds": time.monotonic() - started, "yaw_mode_count": len(exact_modes),
        "outputs": {name: {"sha256": sha256_file(attempt / name), "size": (attempt / name).stat().st_size}
                    for name in published_exact},
        "source_tree_post_run": source_tree_post_run}
    if exact_manifest["source_tree_post_run"]["materialized_tree_hash"] != source_audit["materialized_tree_hash"]:
        raise FinalV23ParityError(
            "BLOCKED_CLEAN1R2R1_EXACT_CLEAN_FINAL_V23_RUN_FAILED: exact source changed during build/run"
        )
    _write_json(attempt / "EXACT_CLEAN_FINAL_V23_RUN_MANIFEST.json", exact_manifest)
    _write_json(attempt / "EXACT_TAG_BUILD_COMPATIBILITY_AUDIT.json",
                {"compatibility_patch_applied": False, "algorithm_math_changed": False,
                 "attempt_owned_source_copy": True, "external_dependency_symlink_count": 0})

    active_build = attempt / "active_build"
    _run(["cmake", "-S", str(repo / "cpp"), "-B", str(active_build)], cwd=repo,
         log_prefix=logs / "active_cmake_configure", timeout=timeout_seconds)
    _run(["cmake", "--build", str(active_build), "--target", "legsa_v23_port_core_demo", "-j", str(jobs)], cwd=repo,
         log_prefix=logs / "active_cmake_build", timeout=timeout_seconds)
    active_binary = active_build / "legsa_v23_port_core_demo"
    active_output = attempt / "active_run" / "output"
    active_output.mkdir(parents=True)
    active_config = attempt / "active_run" / "CLEAN_FINAL_V23_RUNTIME_CONFIG.yaml"
    active_config.write_text(active_runtime_config(bundle.imu_path, bundle.gnss_path, active_output), encoding="utf-8")
    _run([str(active_binary), "--config", str(active_config), "--output-dir", str(active_output),
          "--debug-update-timeline", "--debug-output-dir", str(active_output), "--debug-max-rows", "1000000"],
         cwd=repo, log_prefix=logs / "active_run", timeout=timeout_seconds)
    active_manifest = json.loads((active_output / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    required_active = {"clean_final_v23_parity_mode": True, "algorithm_id": "strong_dual_yaw_EKF",
        "data_mode": "real_by2_raw", "trace_used_online": False, "semisynthetic_data_used": False,
        "final_v23_output_solver_input": False, "LegSA_output_solver_input": False,
        "measurement_update_order": "position_then_yaw_then_receiver_velocity_then_feedback"}
    if any(active_manifest.get(field) != value for field, value in required_active.items()):
        raise FinalV23ParityError("active strong runtime manifest does not match clean final_v23 contract")
    pointwise = attempt / "EXACT_VS_ACTIVE_POINTWISE_DIFF.csv.gz"
    active_exact_nav = active_output / "KF_GINS_Navresult.nav"
    active_exact_std = active_output / "KF_GINS_STD.txt"
    active_exact_imuerr = active_output / "KF_GINS_IMU_ERR.txt"
    if not all(path.is_file() for path in (active_exact_nav, active_exact_std, active_exact_imuerr)):
        raise FinalV23ParityError("active exact-compatible writer output set is incomplete")
    comparison = compare_outputs(
        exact_nav, active_exact_nav, exact_std, active_exact_std, pointwise
    )
    counters = counter_audit(
        exact_modes,
        active_manifest,
        active_output / "PORT_GNSS_UPDATE_TRACE.csv",
        bundle.gnss_path,
    )
    _write_json(attempt / "EXACT_VS_ACTIVE_COUNTER_AUDIT.json", counters)
    passed = bool(comparison["row_count_exact"] and comparison["timestamp_exact"] and
                  comparison["nav_aggregate_gate_passed"] and counters["passed"])
    report = {"schema_version": "paper_rebuild.active_port_clean_final_v23_parity.v1", "stage_id": STAGE_ID,
        "profile_id": "clean_real_final_v23", "parity_tolerance_freeze_id": "CLEAN1R2R1_PRE_OUTPUT_FLOAT64_FORMAT_BOUND_V1",
        "tolerances_frozen_before_outputs": asdict(FROZEN_TOLERANCES),
        "same_fresh_imu_sha256": sha256_file(bundle.imu_path), "same_fresh_gnss_sha256": sha256_file(bundle.gnss_path),
        "active_code_commit": active_code_commit, "active_worktree_dirty": False,
        "active_executable_sha256": sha256_file(active_binary),
        "active_runtime_config_sha256": sha256_file(active_config),
        "active_solver_manifest_sha256": sha256_file(active_output / "RUN_MANIFEST.json"),
        "exact_source_run": True, "active_strong_run": True, "comparison": comparison, "counter_audit": counters,
        "active_exact_writer_outputs": {
            path.name: {"sha256": sha256_file(path), "size": path.stat().st_size}
            for path in (active_exact_nav, active_exact_std, active_exact_imuerr)
        },
        "strong_equals_clean_final_v23": passed, "active_port_clean_final_v23_parity": passed,
        "terminal_status": "PASS_FINAL_V23_CLEAN_PARITY_ANCHOR" if passed else "BLOCKED_CLEAN1R2R1_ACTIVE_PORT_PARITY_FAILED",
        "historical_metric_used_for_gate": False, "trace_opened": False, "exact_output_used_as_solver_input": False}
    _write_json(attempt / "ACTIVE_PORT_CLEAN_FINAL_V23_PARITY_REPORT.json", report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--tag-recovery-root", required=True)
    parser.add_argument("--clean-input-manifest", required=True)
    parser.add_argument("--attempt-root", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        report = run_clean_final_v23_parity(repo_root=args.repo_root, tag_recovery_root=args.tag_recovery_root,
            clean_input_manifest=args.clean_input_manifest, attempt_root=args.attempt_root,
            timeout_seconds=args.timeout_seconds, jobs=args.jobs)
    except (FinalV23ParityError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        message = str(exc)
        if not message.startswith("BLOCKED_CLEAN1R2R1_"):
            message = f"BLOCKED_CLEAN1R2R1_ACTIVE_PORT_PARITY_FAILED: {message}"
        print(message)
        return 2
    print(report["terminal_status"])
    return 0 if report["active_port_clean_final_v23_parity"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
