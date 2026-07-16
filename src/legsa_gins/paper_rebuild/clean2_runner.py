"""Fail-closed CLEAN2 runtime-config materialization and formal process runner."""

from __future__ import annotations

import concurrent.futures
import csv
import json
import math
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from .clean2_run_registry import (
    CANONICAL_FEATURES,
    REGISTRY_FIELDS,
    read_run_registry,
    validate_run_registry_rows,
    write_run_registry,
)
from .clean2_case_provider import validate_case_provider_index
from .evidence import BY2_TRACE_RELATIVE_PATH, parse_strace_openat_paths
from .final_v23_clean_parity import _ned_delta as _frozen_ned_delta
from .manifest import git_code_state, sha256_file, sha256_text, write_json_atomic
from .methods import load_method_catalog
from .paths import is_within, load_yaml_mapping
from .subprocess_guard import run_process_group


STAGE_ID = "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18"
PROTOCOL_ID = "CLEAN_REAL_DATA_FINAL_V23"
MAX_JOBS = 12
DEFAULT_JOBS = 8
CLEAN1_CODE_FREEZE_COMMIT = "5c807633f699238aa2244a0496881dff71550273"
CLEAN1_REPORT_COMMIT = "a3909830288b29a8576626408c0eea700abea5ef"
CLEAN1_EVIDENCE_MANIFEST_SHA256 = (
    "5e19451ba5ea2e5f9d09c023990fcbf30b5ee6ab2ff413518ae5c3f211c4adcf"
)
CLEAN1_FULL_REPORT_SHA256 = (
    "f7f21ea6095aa2fa27cfec3814e0a18babe7cdb0ffbfbda79ac250a163d351ab"
)
CLEAN1_STAGE_ID = "CLEAN1R2R1_CLEAN_REAL_FINAL_V23_PARITY_AND_FOUR_METHOD_EXECUTION"
CLEAN1_METHOD_ORDER = (
    "single_antenna_EKF",
    "basic_dual_yaw_EKF",
    "strong_dual_yaw_EKF",
    "LegSA_Paper_V1",
)
CLEAN1_RUN_DIRECTORIES = (
    "01_single_antenna_EKF",
    "02_basic_dual_yaw_EKF",
    "03_strong_dual_yaw_EKF",
    "04_LegSA_Paper_V1",
)
ATTEMPT_FIELDS = (
    "run_id",
    "run_order",
    "attempt_number",
    "technical_retry",
    "retry_reason",
    "metric_driven_rerun",
    "returncode",
    "runtime_seconds",
    "terminal_status",
)
_ATTEMPT_LEDGER_LOCK = threading.Lock()
REQUIRED_OUTPUT_NAMES = (
    "LegSA_PORT_NAV.nav",
    "LegSA_PORT_STD.csv",
    "EVAL_NAV.csv",
    "KF_GINS_Navresult.nav",
    "KF_GINS_STD.txt",
    "KF_GINS_IMU_ERR.txt",
    "RUN_MANIFEST.json",
    "PORT_GNSS_UPDATE_TRACE.csv",
    "SOLVER_FILE_OPEN_TRACE.raw",
    "SOLVER_FILE_OPEN_AUDIT.json",
)
BASE_OUTPUT_ROLE_NAMES = {
    "legsa_nav": "LegSA_PORT_NAV.nav",
    "legsa_std": "LegSA_PORT_STD.csv",
    "evaluator_nav": "EVAL_NAV.csv",
    "exact_nav": "KF_GINS_Navresult.nav",
    "exact_std": "KF_GINS_STD.txt",
    "exact_imu_error": "KF_GINS_IMU_ERR.txt",
    "solver_manifest": "RUN_MANIFEST.json",
    "gnss_action_trace": "PORT_GNSS_UPDATE_TRACE.csv",
    "file_open_trace": "SOLVER_FILE_OPEN_TRACE.raw",
    "file_open_audit": "SOLVER_FILE_OPEN_AUDIT.json",
}
SOURCE_AWARE_OUTPUT_ROLE = "source_aware_trace"
SOURCE_AWARE_OUTPUT_NAME = "SOURCE_AWARE_WEIGHT_TRACE.csv"
PHASE_ORDER = (
    "structural_gate",
    "factorial_remaining",
    "controlled_canonical",
    "sentinel_loo",
)


class Clean2RunError(RuntimeError):
    """Formal execution or runtime-config isolation failed closed."""


def _yaml_bool(value: bool) -> str:
    return "true" if value else "false"


def _quote(value: str | Path) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _parse_flat_keys(text: str) -> dict[str, int]:
    keys: dict[str, int] = {}
    for index, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key = stripped.split(":", 1)[0].strip()
        if not re.fullmatch(r"[A-Za-z0-9_]+", key):
            continue
        if key in keys:
            raise Clean2RunError(f"Base runtime config contains duplicate key: {key}")
        keys[key] = index
    return keys


def _rewrite_flat_config(text: str, updates: Mapping[str, str]) -> str:
    lines = text.splitlines()
    key_lines = _parse_flat_keys(text)
    for key, rendered in updates.items():
        replacement = f"{key}: {rendered}"
        if key in key_lines:
            lines[key_lines[key]] = replacement
        else:
            lines.append(replacement)
    return "\n".join(lines) + "\n"


def _same_frozen_value(actual: Any, expected: Any) -> bool:
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        return actual == expected
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isclose(
            float(actual), float(expected), rel_tol=0.0, abs_tol=1.0e-12
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            _same_frozen_value(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def _validate_frozen_base_template(
    text: str,
    *,
    parity_contract_path: str | Path,
    clean1_protocol_path: str | Path,
) -> dict[str, str]:
    """Validate the complete final_v23/LegSA runtime contract before rewriting paths.

    final_v23 state/noise/scheme-C values come from the parity contract.  The
    auxiliary tolerances and source-aware/Go2 policy come from the tracked
    CLEAN1 protocol that produced the approved four-method base template.
    """

    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:
        raise Clean2RunError("PyYAML is required to audit the CLEAN2 base template") from exc
    payload = yaml.safe_load(text)
    if not isinstance(payload, Mapping):
        raise Clean2RunError("CLEAN2 base runtime config is not a mapping")
    parity_path = Path(parity_contract_path).resolve(strict=True)
    protocol_path = Path(clean1_protocol_path).resolve(strict=True)
    parity = load_yaml_mapping(parity_path)
    protocol = load_yaml_mapping(protocol_path)
    timing = parity["time_contract"]
    initialization = parity["runtime_initialization"]
    filter_contract = parity["filter_contract"]
    common = protocol["solver_common"]
    expected: dict[str, Any] = {
        "starttime": timing["starttime_seconds"],
        "endtime": timing["endtime_seconds"],
        "initpos": initialization["initpos_deg_deg_m"],
        "initvel": initialization["initvel_ned_mps"],
        "initatt": initialization["initatt_rpy_deg"],
        "imudatalen": common["imu_data_columns"],
        "imudatarate": common["imu_data_rate_hz"],
        "initgyrbias": common["init_gyro_bias"],
        "initaccbias": common["init_accel_bias"],
        "initgyrscale": common["init_gyro_scale"],
        "initaccscale": common["init_accel_scale"],
        "initposstd": common["init_position_std_m"],
        "initvelstd": common["init_velocity_std_mps"],
        "initattstd": common["init_attitude_std_deg"],
        "initbgstd": common["init_gyro_bias_std_deg_h"],
        "initbastd": common["init_accel_bias_std_mgal"],
        "initsgstd": common["init_gyro_scale_std_ppm"],
        "initsastd": common["init_accel_scale_std_ppm"],
        "arw": common["angle_random_walk_deg_sqrt_h"],
        "vrw": common["velocity_random_walk_mps_sqrt_h"],
        "gbstd": common["gyro_bias_std_deg_h"],
        "abstd": common["accel_bias_std_mgal"],
        "gsstd": common["gyro_scale_std_ppm"],
        "asstd": common["accel_scale_std_ppm"],
        "corrtime": common["correlation_time_h"],
        "antlever": filter_contract["antlever_frd_m"],
        "basic_dual_yaw_fixed_std_deg": 1.5,
        "yaw_std_min_deg": filter_contract["scheme_C"]["yaw_std_min_deg"],
        "yaw_std_soft_deg": filter_contract["scheme_C"]["yaw_std_soft_deg"],
        "yaw_std_hard_deg": filter_contract["scheme_C"]["yaw_std_hard_deg"],
        "yaw_res_soft_deg": filter_contract["scheme_C"]["yaw_res_soft_deg"],
        "yaw_res_hard_deg": filter_contract["scheme_C"]["yaw_res_hard_deg"],
        "yaw_downweight_scale": filter_contract["scheme_C"]["yaw_downweight_scale"],
        "raw_doppler_min_sat": common["raw_doppler_min_sat"],
        "raw_doppler_mode": common["raw_doppler_mode"],
        "raw_doppler_time_tolerance_sec": common["raw_doppler_time_tolerance_seconds"],
        "raw_doppler_residual_gate_mps": common["raw_doppler_residual_gate_mps"],
        "raw_doppler_R_scale": common["raw_doppler_R_scale"],
        "go2_attitude_prior_std_roll_deg": common["go2_roll_pitch_std_deg"],
        "go2_attitude_prior_std_pitch_deg": common["go2_roll_pitch_std_deg"],
        "go2_attitude_prior_time_tolerance_sec": common["go2_roll_pitch_time_tolerance_seconds"],
        "go2_attitude_prior_sourceaware": common["go2_attitude_prior_source_aware_enabled"],
        "go2_velocity_prior_time_tolerance_sec": common["go2_horizontal_velocity_time_tolerance_seconds"],
        "go2_horizontal_velocity_prior_std_scale": common["go2_horizontal_velocity_std_scale"],
        "go2_horizontal_velocity_prior_mode": common["go2_horizontal_velocity_prior_mode"],
        "go2_horizontal_velocity_prior_source_aware_enabled": common["go2_horizontal_velocity_source_aware_enabled"],
        "go2_horizontal_velocity_adaptive_std_enabled": common["go2_horizontal_velocity_adaptive_std_enabled"],
        "receiver_velocity_stress_mode": common["receiver_velocity_stress_mode"],
        "receiver_velocity_std_scale": common["receiver_velocity_std_scale"],
        "receiver_velocity_outage_start_sec": common["receiver_velocity_outage_start_seconds"],
        "receiver_velocity_outage_duration_sec": common["receiver_velocity_outage_duration_seconds"],
        "receiver_velocity_additive_noise_std_mps": common["receiver_velocity_additive_noise_std_mps"],
        "receiver_velocity_additive_noise_seed": common["receiver_velocity_additive_noise_seed"],
        "diagnostic_stress_only": common["diagnostic_stress_only"],
        "trace_used_online": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
    }
    source_aware_field_map = {
        "source_aware_policy_version": "source_aware_policy",
        "source_aware_mode": "source_aware_mode",
        "source_aware_max_R_scale": "source_aware_max_R_scale",
        "source_aware_global_cap": "source_aware_global_cap",
        "source_aware_use_innovation_covariance": "source_aware_use_innovation_covariance",
        "source_aware_deadband_normalized": "source_aware_deadband_normalized",
        "source_aware_moderate_normalized": "source_aware_moderate_normalized",
        "source_aware_strong_normalized": "source_aware_strong_normalized",
        "source_aware_receiver_position_cap": "source_aware_receiver_position_cap",
        "source_aware_receiver_velocity_cap": "source_aware_receiver_velocity_cap",
        "source_aware_dual_yaw_cap": "source_aware_dual_yaw_cap",
        "source_aware_raw_doppler_cap": "source_aware_raw_doppler_cap",
        "source_aware_go2_attitude_cap": "source_aware_go2_attitude_cap",
        "source_aware_go2_horizontal_velocity_cap": "source_aware_go2_horizontal_velocity_cap",
        "source_aware_reject_extreme": "source_aware_reject_extreme",
        "source_aware_no_R_shrink": "source_aware_no_R_shrink",
        "source_aware_trace_enabled": "source_aware_trace_enabled",
        "source_aware_enable_rolling_innovation_baseline": "source_aware_enable_rolling_innovation_baseline",
        "source_aware_rolling_window_size": "source_aware_rolling_window_size",
        "source_aware_rolling_mad_floor": "source_aware_rolling_mad_floor",
        "source_aware_method_family": "source_aware_method_family",
        "source_aware_method_k0": "source_aware_method_k0",
        "source_aware_method_k1": "source_aware_method_k1",
        "source_aware_method_c": "source_aware_method_c",
        "source_aware_method_alpha": "source_aware_method_alpha",
        "source_aware_method_phi": "source_aware_method_phi",
        "source_aware_method_base_gain": "source_aware_method_base_gain",
    }
    expected.update({runtime: common[source] for runtime, source in source_aware_field_map.items()})
    for source, flags in common["source_aware_sources"].items():
        for flag in ("enabled", "lsim_enabled", "oim_enabled"):
            expected[f"source_aware_{source}_{flag}"] = flags[flag]
    for field, value in expected.items():
        if field not in payload or not _same_frozen_value(payload.get(field), value):
            raise Clean2RunError(f"Frozen CLEAN2 base field drifted: {field}")
    return {
        "parity_contract_sha256": sha256_file(parity_path),
        "clean1_protocol_sha256": sha256_file(protocol_path),
        "validated_field_count": str(len(expected)),
    }


def _canonical_role(row: Mapping[str, Any]) -> bool:
    return not bool(str(row.get("ablation_id") or ""))


def validate_registry_method_semantics(
    row: Mapping[str, Any], methods_config: str | Path
) -> None:
    catalog = load_method_catalog(methods_config)
    structural = str(row["structural_method"])
    features = tuple(bool(row[f"feature_{module}"]) for module in ("RD", "SA", "RP", "HV"))
    if _canonical_role(row):
        if structural not in CANONICAL_FEATURES or features != CANONICAL_FEATURES[structural]:
            raise Clean2RunError("Canonical CLEAN2 row differs from methods.yaml")
        method_features = catalog.features(structural)
        expected = (
            method_features["enable_raw_doppler"],
            method_features["enable_source_aware"],
            method_features["enable_go2_roll_pitch_prior"],
            method_features["enable_go2_horizontal_velocity_prior"],
        )
        if features != expected:
            raise Clean2RunError("Canonical CLEAN2 feature vector differs from methods.yaml")
    elif structural != "strong_dual_yaw_EKF" or not re.fullmatch(
        r"AB[01]{4}", str(row["ablation_id"])
    ):
        raise Clean2RunError("Ablation row must retain the strong structural backbone")


def build_clean2_runtime_config(
    base_template_text: str,
    row: Mapping[str, Any],
    *,
    gnss_path: str | Path,
    shared_provider_paths: Mapping[str, str | Path],
    output_dir: str | Path,
    methods_config: str | Path,
    parity_contract_path: str | Path,
    clean1_protocol_path: str | Path,
) -> str:
    """Rewrite only identity, case input, output, and four frozen feature flags."""

    _validate_frozen_base_template(
        base_template_text,
        parity_contract_path=parity_contract_path,
        clean1_protocol_path=clean1_protocol_path,
    )
    validate_registry_method_semantics(row, methods_config)
    case_id = str(row["case_id"])
    controlled = not case_id.startswith("C00_")
    ablation = not _canonical_role(row)
    structural = str(row["structural_method"])
    if not re.match(r"^C(?:0[0-9]|1[0-7])_", case_id):
        raise Clean2RunError("CLEAN2 case id must begin C00..C17")
    expected_namespace = (
        "BY2_CONTROLLED_DUAL_YAW_DEGRADATION"
        if controlled
        else "BY2_REAL_CLEAN_MODULE_ABLATION"
    )
    if row["result_namespace"] != expected_namespace:
        raise Clean2RunError("CLEAN2 result namespace does not match the case")
    rd, sa, rp, hv = (
        bool(row["feature_RD"]),
        bool(row["feature_SA"]),
        bool(row["feature_RP"]),
        bool(row["feature_HV"]),
    )
    enable_dual_yaw = structural != "single_antenna_EKF"
    enable_receiver_velocity = structural != "basic_dual_yaw_EKF"
    expected_shared = {"imu", "raw_doppler", "go2_roll_pitch", "go2_horizontal_velocity"}
    if set(shared_provider_paths) != expected_shared:
        raise Clean2RunError("Fresh shared provider paths are incomplete")
    resolved_shared = {
        role: Path(path).resolve(strict=True) for role, path in shared_provider_paths.items()
    }
    updates = {
        "clean2_formal_mode": "true",
        "clean1_formal_mode": "false",
        "clean_final_v23_parity_mode": "true",
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        "case_id": case_id,
        "data_mode": "real_base_controlled_degradation" if controlled else "real_by2_raw",
        "result_namespace": expected_namespace,
        "role": "ablation_configuration" if ablation else "canonical_method",
        "structural_method": structural,
        "ablation_id": _quote(row["ablation_id"]),
        "run_id": str(row["run_id"]),
        "run_label": str(row["run_id"]),
        "algorithm_id": structural,
        "imupath": _quote(resolved_shared["imu"]),
        "gnsspath": _quote(Path(gnss_path).resolve(strict=True)),
        "outputpath": _quote(Path(output_dir).resolve(strict=False)),
        "feature_RD": _yaml_bool(rd),
        "feature_SA": _yaml_bool(sa),
        "feature_RP": _yaml_bool(rp),
        "feature_HV": _yaml_bool(hv),
        "enable_dual_yaw": _yaml_bool(enable_dual_yaw),
        "enable_receiver_velocity": _yaml_bool(enable_receiver_velocity),
        "enable_raw_doppler": _yaml_bool(rd),
        "enable_source_aware": _yaml_bool(sa),
        "enable_go2_roll_pitch_prior": _yaml_bool(rp),
        "enable_go2_horizontal_velocity_prior": _yaml_bool(hv),
        "raw_doppler_factor_path": _quote(resolved_shared["raw_doppler"]),
        "go2_attitude_prior_path": _quote(resolved_shared["go2_roll_pitch"]),
        "go2_horizontal_velocity_prior_path": _quote(resolved_shared["go2_horizontal_velocity"]),
        "synthetic_data_used": "false",
        "semisynthetic_data_used": _yaml_bool(controlled),
        "trace_used_online": "false",
        "receiver_imu_as_body_imu": "false",
        "final_v23_output_solver_input": "false",
        "LegSA_output_solver_input": "false",
        "per_case_tuning": "false",
        "output_only_correction": "false",
        "epoch_deleted_for_metric": "false",
        "old_runtime_input_count": "0",
        "legacy_provider_input_count": "0",
        "legacy_row_input_count": "0",
        "legacy_aggregate_input_count": "0",
        "paper_performance_claim": "false",
    }
    return _rewrite_flat_config(base_template_text, updates)


def validate_executable_source_manifest(
    path: str | Path,
    *,
    code_root: str | Path,
    executable: str | Path,
    expected_code_commit: str,
) -> dict[str, Any]:
    source = Path(path).resolve(strict=True)
    payload = json.loads(source.read_text(encoding="utf-8"))
    root = Path(code_root).resolve(strict=True)
    exe = Path(executable).resolve(strict=True)
    commit, dirty = git_code_state(root)
    if dirty or commit != expected_code_commit:
        raise Clean2RunError("Executable/source validation requires the exact clean code freeze")
    expected_sources = _tracked_executable_source_files(root)
    expected = {
        "schema_version": "paper_rebuild.clean2_executable_source_manifest.v1",
        "stage_id": STAGE_ID,
        "code_commit": expected_code_commit,
        "code_worktree_dirty": False,
        "executable_path": str(exe),
        "executable_hash": sha256_file(exe),
        "terminal_status": "PASS",
        "source_file_count": len(expected_sources),
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise Clean2RunError("Executable/source manifest identity mismatch")
    source_files = payload.get("source_files")
    if not isinstance(source_files, Mapping) or dict(source_files) != expected_sources:
        raise Clean2RunError("Executable/source manifest does not bind the exact tracked target source set")
    return {**payload, "manifest_sha256": sha256_file(source)}


def _tracked_executable_source_files(code_root: Path) -> dict[str, str]:
    """Hash the complete tracked CMake/port-core source set for the formal executable."""

    listed = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--",
            "cpp/CMakeLists.txt",
            "cpp/legsa_v23_port_core",
        ],
        cwd=code_root,
        check=False,
        capture_output=True,
    )
    if listed.returncode != 0:
        raise Clean2RunError("Cannot enumerate the tracked CLEAN2 executable source set")
    relatives = sorted(
        value.decode("utf-8") for value in listed.stdout.split(b"\0") if value
    )
    if "cpp/CMakeLists.txt" not in relatives or not any(
        value.startswith("cpp/legsa_v23_port_core/src/") for value in relatives
    ):
        raise Clean2RunError("Tracked CLEAN2 executable source set is incomplete")
    result: dict[str, str] = {}
    for relative in relatives:
        candidate = (code_root / relative).resolve(strict=True)
        if not is_within(candidate, code_root) or not candidate.is_file():
            raise Clean2RunError("Tracked executable source escaped the clean code root")
        result[relative] = sha256_file(candidate)
    return result


def create_executable_source_manifest(
    *,
    output_path: str | Path,
    code_root: str | Path,
    executable: str | Path,
    expected_code_commit: str,
) -> dict[str, Any]:
    """Create the complete source/executable freeze only from a clean exact commit."""

    root = Path(code_root).resolve(strict=True)
    exe = Path(executable).resolve(strict=True)
    commit, dirty = git_code_state(root)
    if dirty or commit != expected_code_commit:
        raise Clean2RunError("Executable freeze requires the exact clean code-freeze commit")
    destination = Path(output_path)
    if destination.exists() or destination.is_symlink():
        raise Clean2RunError("Executable/source manifest destination must be fresh")
    payload = {
        "schema_version": "paper_rebuild.clean2_executable_source_manifest.v1",
        "stage_id": STAGE_ID,
        "code_commit": commit,
        "code_worktree_dirty": False,
        "executable_path": str(exe),
        "executable_hash": sha256_file(exe),
        "source_files": _tracked_executable_source_files(root),
        "terminal_status": "PASS",
    }
    payload["source_file_count"] = len(payload["source_files"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(destination, payload)
    return validate_executable_source_manifest(
        destination,
        code_root=root,
        executable=exe,
        expected_code_commit=expected_code_commit,
    )


def _load_case_provider_index(
    path: str | Path, *, expected_code_commit: str
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    # 中文说明：case-provider 模块拥有唯一的完整复验器；runner 不再维护一份
    # 容易漏掉 ledger/policy/hash-table 的弱化副本。
    payload, result = validate_case_provider_index(
        path,
        expected_code_commit=expected_code_commit,
    )
    base = payload.get("base_provider_evidence")
    if not isinstance(base, Mapping):
        raise Clean2RunError("Classic-18 index lacks base provider evidence")
    raw_root_value = base.get("raw_root_path")
    if not isinstance(raw_root_value, str) or not raw_root_value.strip():
        raise Clean2RunError("Classic-18 base provider evidence lacks the raw root")
    raw_root_source = Path(raw_root_value)
    if raw_root_source.is_symlink():
        raise Clean2RunError("Classic-18 base provider evidence has a symlink raw root")
    raw_root = raw_root_source.resolve(strict=True)
    if not raw_root.is_dir():
        raise Clean2RunError("Classic-18 base provider evidence has an invalid raw root")
    provider_paths = base.get("shared_provider_paths")
    provider_hashes = base.get("provider_hashes")
    if not isinstance(provider_paths, Mapping) or not isinstance(provider_hashes, Mapping):
        raise Clean2RunError("Classic-18 index lacks provider paths/hashes")
    for role in ("imu", "raw_doppler", "go2_roll_pitch", "go2_horizontal_velocity"):
        provider_path = Path(str(provider_paths.get(role) or "")).resolve(strict=True)
        if sha256_file(provider_path) != provider_hashes.get(role):
            raise Clean2RunError("Fresh shared provider changed after case freeze")
    base_gnss = Path(str(base.get("base_gnss_path") or "")).resolve(strict=True)
    if sha256_file(base_gnss) != provider_hashes.get("gnss"):
        raise Clean2RunError("Fresh base GNSS changed after case freeze")
    raw_hashes = base.get("raw_source_hashes")
    if not isinstance(raw_hashes, Mapping) or len(raw_hashes) != 22 or not all(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
        for value in raw_hashes.values()
    ):
        raise Clean2RunError("Classic-18 index does not bind exact raw 22 hashes")
    return payload, result


def materialize_runtime_configs(
    *,
    registry_path: str | Path,
    base_runtime_config: str | Path,
    case_provider_index: str | Path,
    methods_config: str | Path,
    runtime_root: str | Path,
    code_root: str | Path,
    expected_code_freeze_commit: str,
    executable: str | Path,
    executable_source_manifest: str | Path,
    parity_contract: str | Path,
    clean1_protocol: str | Path,
    clean2_formal_schema: str | Path,
    historical_formal_schema: str | Path,
) -> list[dict[str, Any]]:
    """Create all 110 isolated configs, then replace registry hashes before execution."""

    registry_source = Path(registry_path).resolve(strict=True)
    rows = read_run_registry(registry_source)
    root = Path(code_root).resolve(strict=True)
    commit, dirty = git_code_state(root)
    if dirty or commit != expected_code_freeze_commit:
        raise Clean2RunError("Runtime materialization requires the exact clean code freeze")
    executable_path = Path(executable).resolve(strict=True)
    executable_hash = sha256_file(executable_path)
    if any(row["executable_hash"] != executable_hash for row in rows):
        raise Clean2RunError("Registry executable hash differs before materialization")
    executable_manifest = validate_executable_source_manifest(
        executable_source_manifest,
        code_root=root,
        executable=executable_path,
        expected_code_commit=expected_code_freeze_commit,
    )
    base_config_path = Path(base_runtime_config).resolve(strict=True)
    base_text = base_config_path.read_text(encoding="utf-8")
    template_audit = _validate_frozen_base_template(
        base_text,
        parity_contract_path=parity_contract,
        clean1_protocol_path=clean1_protocol,
    )
    index_payload, case_index = _load_case_provider_index(
        case_provider_index, expected_code_commit=expected_code_freeze_commit
    )
    clean2_schema_path = Path(clean2_formal_schema).resolve(strict=True)
    historical_schema_path = Path(historical_formal_schema).resolve(strict=True)
    destination = Path(runtime_root).resolve(strict=False)
    if destination.exists():
        raise Clean2RunError("Fresh CLEAN2 runtime root already exists")
    destination.mkdir(parents=True, exist_ok=False)
    for row in rows:
        case = case_index[row["case_id"]]
        if case.get("provider_bundle_hash") != row["provider_bundle_hash"]:
            raise Clean2RunError("Registry/provider bundle hash mismatch")
        run_root = destination / str(row["run_id"])
        config_dir = run_root / "runtime_config"
        config_dir.mkdir(parents=True, exist_ok=False)
        config_path = config_dir / "CLEAN2_RUNTIME_CONFIG.yaml"
        config_text = build_clean2_runtime_config(
            base_text,
            row,
            gnss_path=case["gnss_path"],
            shared_provider_paths=index_payload["base_provider_evidence"]["shared_provider_paths"],
            output_dir=run_root,
            methods_config=methods_config,
            parity_contract_path=parity_contract,
            clean1_protocol_path=clean1_protocol,
        )
        config_path.write_text(config_text, encoding="utf-8")
        row["runtime_config_hash"] = sha256_file(config_path)
        case_manifest_path = Path(case["manifest_path"]).resolve(strict=True)
        case_manifest = json.loads(case_manifest_path.read_text(encoding="utf-8"))
        write_json_atomic(
            config_dir / "RUN_BINDINGS.json",
            {
                "schema_version": "paper_rebuild.clean2_run_bindings.v1",
                "registry_identity": dict(row),
                "code_root": str(root),
                "code_commit": expected_code_freeze_commit,
                "runtime_config_path": str(config_path),
                "runtime_config_hash": row["runtime_config_hash"],
                "executable_path": str(executable_path),
                "executable_hash": executable_hash,
                "executable_source_manifest_path": str(Path(executable_source_manifest).resolve(strict=True)),
                "executable_source_manifest_hash": executable_manifest["manifest_sha256"],
                "case_provider_index_path": index_payload["index_path"],
                "case_provider_index_hash": index_payload["index_sha256"],
                "case_provider_manifest_path": str(case_manifest_path),
                "case_provider_manifest_hash": sha256_file(case_manifest_path),
                "case_gnss_path": case["gnss_path"],
                "case_gnss_hash": case["gnss_sha256"],
                "dual_yaw_path": case["dual_yaw_path"],
                "dual_yaw_hash": case["dual_yaw_sha256"],
                "shared_provider_paths": index_payload["base_provider_evidence"]["shared_provider_paths"],
                "provider_hashes": index_payload["base_provider_evidence"]["provider_hashes"],
                "raw_root_path": index_payload["base_provider_evidence"]["raw_root_path"],
                "raw_source_hashes": index_payload["base_provider_evidence"]["raw_source_hashes"],
                "source_manifest_hashes": {
                    "clean_input": case_manifest["clean_input_manifest_sha256"],
                    "auxiliary_bundle": case_manifest["auxiliary_bundle_manifest_sha256"],
                    "case_provider": sha256_file(case_manifest_path),
                    "case_provider_index": index_payload["index_sha256"],
                    "historical_formal_schema": sha256_file(historical_schema_path),
                    "clean2_formal_schema": sha256_file(clean2_schema_path),
                },
                "clean2_formal_schema_path": str(clean2_schema_path),
                "historical_formal_schema_path": str(historical_schema_path),
                "base_template_path": str(base_config_path),
                "base_template_sha256": sha256_file(base_config_path),
                "base_template_audit": template_audit,
                "provider_bundle_hash": row["provider_bundle_hash"],
                "passed": True,
            },
        )
    validate_run_registry_rows(rows)
    write_run_registry(registry_source, rows)
    write_json_atomic(
        destination / "RUNTIME_CONFIG_MATERIALIZATION.json",
        {
            "schema_version": "paper_rebuild.clean2_runtime_config_materialization.v1",
            "stage_id": STAGE_ID,
            "config_count": len(rows),
            "registry_path_alias": "<CLEAN2_STAGE>/06_RUN_REGISTRY/CLEAN2_RUN_REGISTRY.csv",
            "all_configs_materialized_before_solver": True,
            "code_commit": expected_code_freeze_commit,
            "code_worktree_dirty": False,
            "executable_hash": executable_hash,
            "executable_source_manifest_hash": executable_manifest["manifest_sha256"],
            "case_provider_index_hash": index_payload["index_sha256"],
            "base_template_audit": template_audit,
            "clean2_formal_schema_hash": sha256_file(clean2_schema_path),
            "historical_formal_schema_hash": sha256_file(historical_schema_path),
            "per_case_tuning": False,
            "trace_read_count": 0,
            "passed": True,
        },
    )
    return rows


def _load_run_bindings(
    run_root: Path,
    row: Mapping[str, Any],
    *,
    code_root: Path,
    raw_root: Path,
    expected_code_commit: str,
    executable: Path,
    executable_source_manifest: str | Path,
) -> dict[str, Any]:
    path = run_root / "runtime_config" / "RUN_BINDINGS.json"
    payload = json.loads(path.resolve(strict=True).read_text(encoding="utf-8"))
    commit, dirty = git_code_state(code_root)
    if dirty or commit != expected_code_commit:
        raise Clean2RunError("Formal execution code state differs from CLEAN2 freeze")
    if payload.get("registry_identity") != dict(row):
        raise Clean2RunError("Run bindings no longer match the registry row")
    if (
        payload.get("code_commit") != expected_code_commit
        or payload.get("runtime_config_hash") != row["runtime_config_hash"]
        or sha256_file(payload["runtime_config_path"]) != row["runtime_config_hash"]
        or sha256_file(executable) != row["executable_hash"]
        or payload.get("provider_bundle_hash") != row["provider_bundle_hash"]
        or Path(str(payload.get("raw_root_path") or "")).resolve(strict=True)
        != raw_root.resolve(strict=True)
    ):
        raise Clean2RunError("Run binding hash/commit mismatch")
    executable_manifest = validate_executable_source_manifest(
        executable_source_manifest,
        code_root=code_root,
        executable=executable,
        expected_code_commit=expected_code_commit,
    )
    if executable_manifest["manifest_sha256"] != payload.get("executable_source_manifest_hash"):
        raise Clean2RunError("Executable/source manifest changed after materialization")
    for path_field, hash_field in (
        ("case_provider_index_path", "case_provider_index_hash"),
        ("case_provider_manifest_path", "case_provider_manifest_hash"),
        ("case_gnss_path", "case_gnss_hash"),
        ("dual_yaw_path", "dual_yaw_hash"),
        ("base_template_path", "base_template_sha256"),
    ):
        if sha256_file(payload[path_field]) != payload.get(hash_field):
            raise Clean2RunError(f"Bound formal input changed: {path_field}")
    for role, provider_path in payload["shared_provider_paths"].items():
        if sha256_file(provider_path) != payload["provider_hashes"].get(role):
            raise Clean2RunError(f"Fresh provider changed after runtime materialization: {role}")
    if len(payload.get("raw_source_hashes") or {}) != 22:
        raise Clean2RunError("Run bindings lost exact raw 22 hashes")
    return payload


def validate_clean2_formal_manifest(
    payload: Mapping[str, Any], schema_path: str | Path
) -> None:
    try:
        import jsonschema  # type: ignore[import-not-found]
    except ImportError as exc:
        raise Clean2RunError("jsonschema is required for CLEAN2 formal manifests") from exc
    schema = load_yaml_mapping(schema_path)
    validator_class = getattr(jsonschema, "Draft202012Validator", jsonschema.Draft7Validator)
    errors = sorted(
        validator_class(schema).iter_errors(dict(payload)),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        details = "; ".join(
            f"{'/'.join(map(str, error.absolute_path)) or '<root>'}:{error.message}"
            for error in errors[:8]
        )
        raise Clean2RunError("CLEAN2 formal manifest schema failure: " + details)
    output_files = payload["output_files"]
    output_hashes = payload["output_hashes"]
    if set(output_files) != set(output_hashes):
        raise Clean2RunError("CLEAN2 formal output role/hash sets differ")
    expected_output_names = dict(BASE_OUTPUT_ROLE_NAMES)
    if payload["feature_SA"]:
        expected_output_names[SOURCE_AWARE_OUTPUT_ROLE] = SOURCE_AWARE_OUTPUT_NAME
    if set(output_files) != set(expected_output_names) or any(
        Path(str(output_files[role])).name != name
        for role, name in expected_output_names.items()
    ):
        raise Clean2RunError("CLEAN2 formal output role/name set differs from the frozen contract")
    for value in output_files.values():
        relative = Path(str(value))
        if relative.is_absolute() or ".." in relative.parts:
            raise Clean2RunError("CLEAN2 formal wrapper contains an unsafe output path")
    file_audit = payload["file_read_audit"]
    expected_read_roles = {"runtime_config", "propagation_imu", "case_gnss"}
    if payload["feature_RD"]:
        expected_read_roles.add("raw_doppler")
    if payload["feature_RP"]:
        expected_read_roles.add("go2_roll_pitch")
    if payload["feature_HV"]:
        expected_read_roles.add("go2_horizontal_velocity")
    counts = file_audit.get("required_input_open_counts")
    if (
        file_audit.get("passed") is not True
        or file_audit.get("raw_root_open_count") != 0
        or file_audit.get("trace_open_count") != 0
        or file_audit.get("trace_used_online") is not False
        or set(file_audit.get("required_input_roles") or ()) != expected_read_roles
        or not isinstance(counts, Mapping)
        or set(counts) != expected_read_roles
        or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in counts.values())
        or file_audit.get("missing_required_input_roles") != []
        or file_audit.get("strace_sha256") != output_hashes["file_open_trace"]
    ):
        raise Clean2RunError("CLEAN2 formal file-read audit differs from the frozen contract")
    health = payload["output_health"]
    if (
        health.get("passed") is not True
        or health.get("nav_column_count") != 11
        or health.get("std_column_count") != 22
        or health.get("nav_row_count") != health.get("std_row_count")
        or health.get("row_count_exact") is not True
        or health.get("timestamps_exact") is not True
        or health.get("time_monotonic") is not True
        or health.get("finite_output") is not True
        or float(health.get("nav_std_timestamp_abs_max_sec", math.inf)) > 1.0e-12
    ):
        raise Clean2RunError("CLEAN2 formal NAV/STD structural health failed")
    if payload["counters"]["yaw_attempt_count"] != (
        payload["counters"]["yaw_normal_count"]
        + payload["counters"]["yaw_downweight_count"]
        + payload["counters"]["yaw_reject_count"]
    ):
        raise Clean2RunError("CLEAN2 yaw action counters do not close")
    if payload["counters"]["yaw_accepted_count"] != payload["module_update_counts"]["dual_yaw_update_count"]:
        raise Clean2RunError("CLEAN2 yaw accepted/module counters differ")


def _required_solver_outputs(attempt_root: Path, *, source_aware: bool) -> dict[str, Path]:
    roles = {role: attempt_root / name for role, name in BASE_OUTPUT_ROLE_NAMES.items()}
    if source_aware:
        roles[SOURCE_AWARE_OUTPUT_ROLE] = attempt_root / SOURCE_AWARE_OUTPUT_NAME
    for role, path in roles.items():
        if not path.is_file() or path.stat().st_size == 0:
            raise Clean2RunError(f"Required CLEAN2 solver output is missing/empty: {role}")
    return roles


def _expected_solver_file_reads(
    row: Mapping[str, Any], bindings: Mapping[str, Any]
) -> dict[str, Path]:
    expected = {
        "runtime_config": Path(bindings["runtime_config_path"]).resolve(strict=True),
        "propagation_imu": Path(bindings["shared_provider_paths"]["imu"]).resolve(strict=True),
        "case_gnss": Path(bindings["case_gnss_path"]).resolve(strict=True),
    }
    if row["feature_RD"]:
        expected["raw_doppler"] = Path(
            bindings["shared_provider_paths"]["raw_doppler"]
        ).resolve(strict=True)
    if row["feature_RP"]:
        expected["go2_roll_pitch"] = Path(
            bindings["shared_provider_paths"]["go2_roll_pitch"]
        ).resolve(strict=True)
    if row["feature_HV"]:
        expected["go2_horizontal_velocity"] = Path(
            bindings["shared_provider_paths"]["go2_horizontal_velocity"]
        ).resolve(strict=True)
    return expected


def _write_solver_file_open_audit(
    *,
    strace_path: Path,
    attempt_root: Path,
    row: Mapping[str, Any],
    bindings: Mapping[str, Any],
    raw_root: Path,
    command_cwd: Path,
) -> dict[str, Any]:
    """Bind actual openat evidence without exporting any private absolute path."""

    if not strace_path.is_file() or strace_path.stat().st_size == 0:
        raise Clean2RunError("CLEAN2 solver file-open trace is missing or empty")
    opened = parse_strace_openat_paths(strace_path, cwd=command_cwd)
    expected = _expected_solver_file_reads(row, bindings)
    counts = {
        role: sum(path == expected_path for path in opened)
        for role, expected_path in expected.items()
    }
    missing = sorted(role for role, count in counts.items() if count <= 0)
    raw = raw_root.resolve(strict=True)
    raw_opened = [path for path in opened if is_within(path, raw)]
    # resolve(strict=False) only canonicalizes the frozen pathname; it does not
    # open/stat the evaluation-only trace during solver execution.
    trace = (raw / BY2_TRACE_RELATIVE_PATH).resolve(strict=False)
    trace_open_count = sum(path == trace for path in opened)
    report = {
        "schema_version": "paper_rebuild.clean2_solver_file_open_audit.v1",
        "stage_id": STAGE_ID,
        "run_id": row["run_id"],
        "run_order": int(row["run_order"]),
        "strace_available": True,
        "strace_sha256": sha256_file(strace_path),
        "required_input_roles": sorted(expected),
        "required_input_open_counts": counts,
        "missing_required_input_roles": missing,
        "opened_path_count": len(opened),
        "raw_root_open_count": len(raw_opened),
        "trace_open_count": trace_open_count,
        "trace_used_online": False,
        "private_absolute_paths_recorded": False,
        "passed": not missing and not raw_opened and trace_open_count == 0,
    }
    audit_path = write_json_atomic(attempt_root / BASE_OUTPUT_ROLE_NAMES["file_open_audit"], report)
    if not report["passed"]:
        raise Clean2RunError("FAIL_CLEAN2_EVIDENCE_CONTAMINATION")
    if sha256_file(strace_path) != report["strace_sha256"] or not audit_path.is_file():
        raise Clean2RunError("CLEAN2 solver file-open audit hash binding failed")
    return report


def _strict_numeric_output(
    path: Path, *, expected_columns: int, time_index: int, label: str
) -> tuple[list[list[float]], list[float]]:
    rows: list[list[float]] = []
    times: list[float] = []
    with path.open("r", encoding="utf-8", errors="strict") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "%")):
                continue
            try:
                values = [float(value) for value in stripped.replace(",", " ").split()]
            except ValueError as exc:
                raise Clean2RunError(f"{label} has a non-numeric row {line_number}") from exc
            if len(values) != expected_columns or not all(math.isfinite(value) for value in values):
                raise Clean2RunError(
                    f"{label} row {line_number} must contain {expected_columns} finite columns"
                )
            rows.append(values)
            times.append(values[time_index])
    if not rows:
        raise Clean2RunError(f"{label} contains zero data rows")
    if any(right <= left for left, right in zip(times, times[1:])):
        raise Clean2RunError(f"{label} timestamps are not strictly increasing")
    return rows, times


def _formal_numeric_output_health(outputs: Mapping[str, Path]) -> dict[str, Any]:
    nav_rows, nav_times = _strict_numeric_output(
        outputs["exact_nav"], expected_columns=11, time_index=1, label="CLEAN2 exact NAV"
    )
    std_rows, std_times = _strict_numeric_output(
        outputs["exact_std"], expected_columns=22, time_index=0, label="CLEAN2 exact STD"
    )
    if len(nav_rows) != len(std_rows):
        raise Clean2RunError("CLEAN2 exact NAV/STD row counts differ")
    time_abs_max = max(abs(left - right) for left, right in zip(nav_times, std_times))
    if time_abs_max > 1.0e-12:
        raise Clean2RunError("CLEAN2 exact NAV/STD timestamps differ")
    return {
        "nav_row_count": len(nav_rows),
        "std_row_count": len(std_rows),
        "nav_column_count": 11,
        "std_column_count": 22,
        "nav_std_timestamp_abs_max_sec": time_abs_max,
        "row_count_exact": True,
        "timestamps_exact": True,
        "time_monotonic": True,
        "finite_output": True,
        "passed": True,
    }


def _validate_solver_manifest(
    solver: Mapping[str, Any], row: Mapping[str, Any], bindings: Mapping[str, Any]
) -> tuple[dict[str, int], dict[str, int]]:
    controlled = not str(row["case_id"]).startswith("C00_")
    expected = {
        "schema_version": "legsa-v23-port-core-run-manifest-v2",
        "clean1_formal_mode": False,
        "clean2_formal_mode": True,
        "clean_final_v23_parity_mode": True,
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        "case_id": row["case_id"],
        "run_id": row["run_id"],
        "result_namespace": row["result_namespace"],
        "structural_method": row["structural_method"],
        "ablation_id": row["ablation_id"],
        "feature_RD": row["feature_RD"],
        "feature_SA": row["feature_SA"],
        "feature_RP": row["feature_RP"],
        "feature_HV": row["feature_HV"],
        "data_mode": "real_base_controlled_degradation" if controlled else "real_by2_raw",
        "synthetic_data_used": False,
        "semisynthetic_data_used": controlled,
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
    }
    if any(solver.get(key) != value for key, value in expected.items()):
        mismatches = [key for key, value in expected.items() if solver.get(key) != value]
        raise Clean2RunError("Solver manifest identity/safety mismatch: " + ",".join(mismatches))
    actual_paths = solver.get("actual_solver_input_paths")
    if not isinstance(actual_paths, Mapping):
        raise Clean2RunError("Solver manifest lacks actual input paths")
    expected_actual = {
        "propagation_imu": str(Path(bindings["shared_provider_paths"]["imu"]).resolve(strict=True)),
        "gnss_position_receiver_velocity_dual_yaw": str(Path(bindings["case_gnss_path"]).resolve(strict=True)),
    }
    if row["feature_RD"]:
        expected_actual["raw_doppler_velocity"] = str(Path(bindings["shared_provider_paths"]["raw_doppler"]).resolve(strict=True))
    if row["feature_RP"]:
        expected_actual["go2_roll_pitch_weak_prior"] = str(Path(bindings["shared_provider_paths"]["go2_roll_pitch"]).resolve(strict=True))
    if row["feature_HV"]:
        expected_actual["go2_horizontal_velocity_weak_prior"] = str(Path(bindings["shared_provider_paths"]["go2_horizontal_velocity"]).resolve(strict=True))
    if dict(actual_paths) != expected_actual:
        raise Clean2RunError("Solver actual input paths differ from fresh provider bindings")
    module_fields = (
        "position_update_count", "receiver_velocity_update_count", "dual_yaw_update_count",
        "raw_doppler_update_count", "source_aware_evaluation_count",
        "source_aware_weight_changed_count", "go2_roll_pitch_update_count",
        "go2_horizontal_velocity_update_count", "selected_fgo_feedback_update_count",
        "nine_factor_fgo_update_count", "qa_fallback_count", "multi_state_qm_update_count",
        "contact_fk_update_count",
    )
    modules = {field: int(solver[field]) for field in module_fields}
    if any(modules[field] != 0 for field in (
        "selected_fgo_feedback_update_count", "nine_factor_fgo_update_count", "qa_fallback_count",
        "multi_state_qm_update_count", "contact_fk_update_count",
    )):
        raise Clean2RunError("CLEAN2 out-of-scope module counter is nonzero")
    counters = {
        "yaw_attempt_count": int(solver["dual_yaw_attempt_count"]),
        "yaw_normal_count": int(solver["yaw_NORMAL"]),
        "yaw_downweight_count": int(solver["yaw_DOWNWEIGHT"]),
        "yaw_reject_count": int(solver["yaw_REJECT"]),
        "yaw_accepted_count": int(solver["dual_yaw_accepted_count"]),
        "raw_doppler_reject_count": int(solver["raw_doppler_reject_count"]),
        "go2_roll_pitch_reject_count": int(solver["go2_attitude_weak_prior_reject_count"]),
        "go2_horizontal_velocity_reject_count": int(solver["go2_velocity_prior_reject_count"]),
    }
    return modules, counters


def _write_formal_wrapper(
    *,
    run_root: Path,
    attempt_root: Path,
    row: Mapping[str, Any],
    bindings: Mapping[str, Any],
    runtime_seconds: float,
) -> dict[str, Any]:
    outputs = _required_solver_outputs(attempt_root, source_aware=bool(row["feature_SA"]))
    solver_path = outputs["solver_manifest"]
    solver = json.loads(solver_path.read_text(encoding="utf-8"))
    modules, counters = _validate_solver_manifest(solver, row, bindings)
    file_read_audit = json.loads(outputs["file_open_audit"].read_text(encoding="utf-8"))
    expected_file_audit = {
        "schema_version": "paper_rebuild.clean2_solver_file_open_audit.v1",
        "stage_id": STAGE_ID,
        "run_id": row["run_id"],
        "run_order": int(row["run_order"]),
        "strace_available": True,
        "raw_root_open_count": 0,
        "trace_open_count": 0,
        "trace_used_online": False,
        "private_absolute_paths_recorded": False,
        "passed": True,
    }
    if any(file_read_audit.get(key) != value for key, value in expected_file_audit.items()):
        raise Clean2RunError("CLEAN2 solver file-open audit identity/safety mismatch")
    if file_read_audit.get("strace_sha256") != sha256_file(outputs["file_open_trace"]):
        raise Clean2RunError("CLEAN2 solver strace hash differs from file-open audit")
    output_health = _formal_numeric_output_health(outputs)
    output_files = {
        role: path.relative_to(run_root).as_posix() for role, path in outputs.items()
    }
    output_hashes = {role: sha256_file(path) for role, path in outputs.items()}
    provider_hashes = {
        **dict(bindings["provider_hashes"]),
        "case_gnss": bindings["case_gnss_hash"],
        "dual_yaw": bindings["dual_yaw_hash"],
    }
    controlled = not str(row["case_id"]).startswith("C00_")
    manifest = {
        "schema_version": "paper_rebuild.clean2_formal_run_manifest.v1",
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        **{key: row[key] for key in (
            "run_id", "case_id", "result_namespace", "structural_method", "ablation_id",
            "feature_RD", "feature_SA", "feature_RP", "feature_HV", "run_order", "formal", "alias_roles",
        )},
        "data_mode": "real_base_controlled_degradation" if controlled else "real_by2_raw",
        "role": "ablation_configuration" if row["ablation_id"] else "canonical_method",
        "code_commit": bindings["code_commit"],
        "code_worktree_dirty_at_run": False,
        "runtime_config_hash": row["runtime_config_hash"],
        "executable_hash": row["executable_hash"],
        "executable_source_manifest_hash": bindings["executable_source_manifest_hash"],
        "provider_bundle_hash": row["provider_bundle_hash"],
        "provider_hashes": provider_hashes,
        "raw_source_hashes": dict(bindings["raw_source_hashes"]),
        "source_manifest_hashes": dict(bindings["source_manifest_hashes"]),
        # Export-safe aliases only; actual paths stay in ignored RUN_BINDINGS/solver manifest.
        "actual_solver_input_paths": {
            "propagation_imu": "provider://fresh/imu",
            "case_gnss": "provider://case/CASE_GNSS_INPUT.extended",
            **({"raw_doppler": "provider://fresh/raw_doppler"} if row["feature_RD"] else {}),
            **({"go2_roll_pitch": "provider://fresh/go2_roll_pitch"} if row["feature_RP"] else {}),
            **({"go2_horizontal_velocity": "provider://fresh/go2_horizontal_velocity"} if row["feature_HV"] else {}),
        },
        "synthetic_data_used": False,
        "semisynthetic_data_used": controlled,
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
        "module_update_counts": modules,
        "counters": counters,
        "file_read_audit": file_read_audit,
        "output_health": output_health,
        "source_aware_trace_expected": bool(row["feature_SA"]),
        "output_files": output_files,
        "output_hashes": output_hashes,
        "solver_manifest_sha256": sha256_file(solver_path),
        "solver_returncode": 0,
        "runtime_seconds": runtime_seconds,
        "terminal_status": "PASS",
    }
    validate_clean2_formal_manifest(manifest, bindings["clean2_formal_schema_path"])
    path = write_json_atomic(run_root / "CLEAN2_FORMAL_RUN_MANIFEST.json", manifest)
    if sha256_file(path) == "":
        raise Clean2RunError("CLEAN2 formal wrapper write failed")
    return manifest


def phase_rows(rows: Sequence[Mapping[str, Any]], phase: str) -> list[dict[str, Any]]:
    bounds = {
        "structural_gate": (1, 4),
        "factorial_remaining": (5, 18),
        "controlled_canonical": (19, 86),
        "sentinel_loo": (87, 110),
    }
    if phase not in bounds:
        raise Clean2RunError(f"Unknown CLEAN2 execution phase: {phase}")
    low, high = bounds[phase]
    return [dict(row) for row in rows if low <= int(row["run_order"]) <= high]


def _numeric_rows(path: Path, expected_columns: int) -> list[list[float]]:
    rows: list[list[float]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            values = [float(value) for value in stripped.replace(",", " ").split()]
            if len(values) != expected_columns or not all(math.isfinite(value) for value in values):
                raise Clean2RunError("Structural parity input has invalid numeric rows")
            rows.append(values)
    if not rows:
        raise Clean2RunError("Structural parity input is empty")
    return rows


def _wrap_delta(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def _compare_nav_std(
    current_nav: Path, reference_nav: Path, current_std: Path, reference_std: Path,
    tolerance: Mapping[str, Any],
) -> dict[str, Any]:
    def rmse(values: Sequence[float]) -> float:
        return math.sqrt(sum(value * value for value in values) / len(values))

    current = _numeric_rows(current_nav, 11)
    reference = _numeric_rows(reference_nav, 11)
    current_s = _numeric_rows(current_std, 22)
    reference_s = _numeric_rows(reference_std, 22)
    if len(current) != len(reference) or len(current_s) != len(reference_s) or len(current) != len(current_s):
        raise Clean2RunError("C00 structural row counts differ")
    time_max = max(abs(left[1] - right[1]) for left, right in zip(current, reference))
    std_time_max = max(abs(left[0] - right[0]) for left, right in zip(current_s, reference_s))
    horizontal: list[float] = []
    up: list[float] = []
    velocity: list[float] = []
    roll: list[float] = []
    pitch: list[float] = []
    yaw: list[float] = []
    for left, right in zip(current, reference):
        # 中文说明：结构 parity 必须复用 CLEAN1 冻结的 BLH->ECEF->NED
        # 公式，不能用小角度局部比例近似替代。
        north, east, up_value = _frozen_ned_delta(
            {"lat": right[2], "lon": right[3], "height": right[4]},
            {"lat": left[2], "lon": left[3], "height": left[4]},
        )
        horizontal.append(math.hypot(north, east))
        up.append(up_value)
        velocity.append(math.sqrt(sum((left[index] - right[index]) ** 2 for index in (5, 6, 7))))
        roll.append(_wrap_delta(left[8] - right[8]))
        pitch.append(_wrap_delta(left[9] - right[9]))
        yaw.append(_wrap_delta(left[10] - right[10]))
    # 与冻结 CLEAN1 parity 完全相同：先在每一行 21 个 STD 分量中取
    # max(|active-reference| / max(1, |reference|))，再对这些 row maxima 求 RMSE/max。
    normalized_std = [
        max(
            abs(left[index] - right[index]) / max(1.0, abs(right[index]))
            for index in range(1, 22)
        )
        for left, right in zip(current_s, reference_s)
    ]
    attitude_all = [abs(value) for values in (roll, pitch, yaw) for value in values]
    result = {
        "row_count": len(current),
        "row_count_exact": True,
        "timestamp_abs_max_sec": max(time_max, std_time_max),
        "horizontal_rmse_m": rmse(horizontal),
        "horizontal_max_m": max(horizontal),
        "up_rmse_m": rmse(up),
        "up_max_m": max(abs(value) for value in up),
        "velocity_3d_rmse_mps": rmse(velocity),
        "velocity_3d_max_mps": max(velocity),
        "roll_rmse_deg": rmse(roll),
        "pitch_rmse_deg": rmse(pitch),
        "yaw_rmse_deg": rmse(yaw),
        "attitude_max_abs_deg": max(attitude_all),
        "std_max_normalized_rmse": rmse(normalized_std),
        "std_max_normalized_max": max(normalized_std),
        "std_normalization_definition": "per_row_max_abs_diff_div_max_1_abs_reference_then_rmse_and_max",
    }
    gate_fields = (
        "timestamp_abs_max_sec",
        "horizontal_rmse_m", "horizontal_max_m", "up_rmse_m", "up_max_m",
        "velocity_3d_rmse_mps", "velocity_3d_max_mps", "roll_rmse_deg",
        "pitch_rmse_deg", "yaw_rmse_deg", "attitude_max_abs_deg",
        "std_max_normalized_rmse", "std_max_normalized_max",
    )
    result["gate_fields"] = list(gate_fields)
    result["passed"] = all(
        float(result[field]) <= float(tolerance[field]) for field in gate_fields
    )
    return result


def _clean1_evidence_rows(evidence_root: Path) -> tuple[Path, dict[str, dict[str, str]]]:
    manifest_path = (evidence_root / "EVIDENCE_MANIFEST.csv").resolve(strict=True)
    if sha256_file(manifest_path) != CLEAN1_EVIDENCE_MANIFEST_SHA256:
        raise Clean2RunError("CLEAN1 current evidence manifest hash differs from the frozen anchor")
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_path = {str(row.get("relative_path") or ""): row for row in rows}
    if len(by_path) != len(rows):
        raise Clean2RunError("CLEAN1 evidence manifest contains duplicate paths")
    return manifest_path, by_path


def _validate_clean1_reference_artifact(
    *, evidence_root: Path, evidence_rows: Mapping[str, Mapping[str, str]], relative: str
) -> Path:
    row = evidence_rows.get(relative)
    if not isinstance(row, Mapping):
        raise Clean2RunError("CLEAN1 structural artifact is absent from current evidence manifest")
    path = (evidence_root / relative).resolve(strict=True)
    if not is_within(path, evidence_root) or not path.is_file():
        raise Clean2RunError("CLEAN1 structural artifact escaped current evidence root")
    if (
        sha256_file(path) != row.get("sha256")
        or path.stat().st_size != int(str(row.get("size_bytes") or "-1"))
        or str(row.get("active_evidence")).casefold() != "true"
        or str(row.get("legacy_payload")).casefold() != "false"
        or str(row.get("semisynthetic_formal_evidence")).casefold() != "false"
    ):
        raise Clean2RunError("CLEAN1 current structural artifact manifest row is invalid")
    return path


def _build_clean1_structural_reference(*, evidence_root: str | Path) -> dict[str, Any]:
    """Validate and describe the approved CLEAN1R2R1 structural artifacts."""

    root = Path(evidence_root).resolve(strict=True)
    if root.name != "CLEAN1R2R1_FINAL" or not root.is_dir():
        raise Clean2RunError("CLEAN1 structural reference must use the approved final evidence root")
    evidence_manifest, evidence_rows = _clean1_evidence_rows(root)
    report_path = (root / "CLEAN1R2R1_FULL_REPORT.json").resolve(strict=True)
    if sha256_file(report_path) != CLEAN1_FULL_REPORT_SHA256:
        raise Clean2RunError("CLEAN1 full report hash differs from the frozen current anchor")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    expected_terminal = (
        "PASS_CLEAN1R2R1_CLEAN_FINAL_V23_PARITY_AND_FOUR_METHOD_"
        "FRESH_EVIDENCE_READY_FOR_HUMAN_REVIEW"
    )
    if (
        report.get("stage_id") != CLEAN1_STAGE_ID
        or report.get("terminal_status") != expected_terminal
        or report.get("git", {}).get("code_freeze_commit") != CLEAN1_CODE_FREEZE_COMMIT
        or report.get("git", {}).get("report_commit") != CLEAN1_REPORT_COMMIT
        or report.get("four_method_execution", {}).get("method_order") != list(CLEAN1_METHOD_ORDER)
        or report.get("four_method_execution", {}).get("all_runs_terminal_pass") is not True
        or report.get("four_method_execution", {}).get("trace_used_online") is not False
        or report.get("pass_gates", {}).get("legacy_solver_input") is not False
        or report.get("pass_gates", {}).get("semisynthetic_formal_evidence") is not False
    ):
        raise Clean2RunError("CLEAN1 full report does not authorize the structural reference")
    methods: dict[str, dict[str, Any]] = {}
    forbidden = (
        "selected_fgo_feedback_update_count",
        "nine_factor_fgo_update_count",
        "qa_fallback_count",
        "multi_state_qm_update_count",
        "contact_fk_update_count",
    )
    for order, (directory, method) in enumerate(
        zip(CLEAN1_RUN_DIRECTORIES, CLEAN1_METHOD_ORDER), start=1
    ):
        prefix = f"04_FOUR_METHOD_RUNTIME/{directory}"
        paths = {
            role: _validate_clean1_reference_artifact(
                evidence_root=root,
                evidence_rows=evidence_rows,
                relative=f"{prefix}/{filename}",
            )
            for role, filename in {
                "nav": "KF_GINS_Navresult.nav",
                "std": "KF_GINS_STD.txt",
                "solver_manifest": "RUN_MANIFEST.json",
                "formal_manifest": "CLEAN1R2R1_FORMAL_RUN_MANIFEST.json",
            }.items()
        }
        formal = json.loads(paths["formal_manifest"].read_text(encoding="utf-8"))
        solver = json.loads(paths["solver_manifest"].read_text(encoding="utf-8"))
        if (
            formal.get("stage_id") != CLEAN1_STAGE_ID
            or formal.get("protocol_id") != PROTOCOL_ID
            or formal.get("algorithm_id") != method
            or formal.get("method_order") != order
            or formal.get("code_freeze_commit") != CLEAN1_CODE_FREEZE_COMMIT
            or formal.get("terminal_success") is not True
            or formal.get("trace_used_online") is not False
            or formal.get("legacy_solver_input") is not False
            or formal.get("data_mode") != "real_by2_raw"
            or formal.get("solver_manifest_sha256") != sha256_file(paths["solver_manifest"])
            or solver.get("stage_id") != CLEAN1_STAGE_ID
            or solver.get("protocol_id") != PROTOCOL_ID
            or solver.get("algorithm_id") != method
            or solver.get("clean1_formal_mode") is not True
            or solver.get("clean_final_v23_parity_mode") is not True
            or solver.get("synthetic_data_used") is not False
            or solver.get("semisynthetic_data_used") is not False
            or solver.get("trace_used_online") is not False
            or solver.get("old_runtime_input_count") != 0
            or any(int(solver.get(field, -1)) != 0 for field in forbidden)
        ):
            raise Clean2RunError("CLEAN1 current formal structural reference failed identity checks")
        methods[method] = {
            **{f"{role}_path": str(path) for role, path in paths.items()},
            **{f"{role}_sha256": sha256_file(path) for role, path in paths.items()},
        }
    payload = {
        "schema_version": "paper_rebuild.clean1r2r1_structural_reference.v2",
        "clean1_code_freeze_commit": CLEAN1_CODE_FREEZE_COMMIT,
        "clean1_report_commit": CLEAN1_REPORT_COMMIT,
        "evidence_manifest_path": str(evidence_manifest),
        "evidence_manifest_sha256": CLEAN1_EVIDENCE_MANIFEST_SHA256,
        "full_report_path": str(report_path),
        "full_report_sha256": CLEAN1_FULL_REPORT_SHA256,
        "solver_input": False,
        "performance_reuse": False,
        "methods": methods,
        "passed": True,
    }
    return payload


def freeze_clean1_structural_reference(
    *, evidence_root: str | Path, output_path: str | Path
) -> dict[str, Any]:
    """Write one reference index only after rebuilding it from approved evidence."""

    payload = _build_clean1_structural_reference(evidence_root=evidence_root)
    destination = Path(output_path)
    if destination.exists() or destination.is_symlink():
        raise Clean2RunError("CLEAN1 structural reference destination must be fresh")
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(destination, payload)
    return payload


def _load_clean1_reference_index(path: str | Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    source = Path(path).resolve(strict=True)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != "paper_rebuild.clean1r2r1_structural_reference.v2"
        or payload.get("clean1_code_freeze_commit") != CLEAN1_CODE_FREEZE_COMMIT
        or payload.get("clean1_report_commit") != CLEAN1_REPORT_COMMIT
        or payload.get("evidence_manifest_sha256") != CLEAN1_EVIDENCE_MANIFEST_SHA256
        or payload.get("full_report_sha256") != CLEAN1_FULL_REPORT_SHA256
        or payload.get("solver_input") is not False
        or payload.get("performance_reuse") is not False
        or payload.get("passed") is not True
    ):
        raise Clean2RunError("CLEAN1 structural reference index identity mismatch")
    methods = payload.get("methods")
    expected_methods = {
        "single_antenna_EKF", "basic_dual_yaw_EKF", "strong_dual_yaw_EKF", "LegSA_Paper_V1"
    }
    if not isinstance(methods, Mapping) or set(methods) != expected_methods:
        raise Clean2RunError("CLEAN1 structural reference method set mismatch")
    normalized: dict[str, dict[str, Any]] = {}
    for method, entry in methods.items():
        if not isinstance(entry, Mapping):
            raise Clean2RunError("CLEAN1 structural reference entry is invalid")
        for role in ("nav", "std", "solver_manifest", "formal_manifest"):
            artifact = Path(str(entry.get(f"{role}_path") or "")).resolve(strict=True)
            if sha256_file(artifact) != entry.get(f"{role}_sha256"):
                raise Clean2RunError("CLEAN1 structural reference artifact hash changed")
        normalized[str(method)] = dict(entry)
    evidence_root = Path(str(payload.get("evidence_manifest_path") or "")).resolve(strict=True).parent
    frozen = _build_clean1_structural_reference(evidence_root=evidence_root)
    if frozen != {key: value for key, value in payload.items() if key != "index_sha256"}:
        raise Clean2RunError("CLEAN1 structural reference differs from current approved evidence")
    payload["index_sha256"] = sha256_file(source)
    return payload, normalized


def _structural_gate_payload(
    *, registry_path: str | Path, runtime_root: str | Path, executable: str | Path,
    executable_source_manifest: str | Path, case_provider_index: str | Path,
    code_root: str | Path, expected_code_freeze_commit: str,
    clean1_reference_index: str | Path, parity_contract: str | Path,
) -> dict[str, Any]:
    code = Path(code_root).resolve(strict=True)
    commit, dirty = git_code_state(code)
    if dirty or commit != expected_code_freeze_commit:
        raise Clean2RunError("C00 gate code state differs from CLEAN2 freeze")
    all_rows = read_run_registry(registry_path)
    rows = phase_rows(all_rows, "structural_gate")
    runtime = Path(runtime_root).resolve(strict=True)
    _validate_completed_phase(runtime, "structural_gate", all_rows)
    executable_path = Path(executable).resolve(strict=True)
    executable_manifest = validate_executable_source_manifest(
        executable_source_manifest, code_root=code, executable=executable_path,
        expected_code_commit=expected_code_freeze_commit,
    )
    index_payload, _ = _load_case_provider_index(
        case_provider_index, expected_code_commit=expected_code_freeze_commit
    )
    reference_payload, references = _load_clean1_reference_index(clean1_reference_index)
    parity_path = Path(parity_contract).resolve(strict=True)
    tolerance = load_yaml_mapping(parity_path)["clean1r2r1_parity_tolerance"]
    method_by_order = (
        "single_antenna_EKF", "basic_dual_yaw_EKF", "strong_dual_yaw_EKF", "LegSA_Paper_V1"
    )
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
    for row, method in zip(rows, method_by_order):
        run_root = runtime / row["run_id"]
        wrapper_path = (run_root / "CLEAN2_FORMAL_RUN_MANIFEST.json").resolve(strict=True)
        wrapper = json.loads(wrapper_path.read_text(encoding="utf-8"))
        bindings = json.loads((run_root / "runtime_config" / "RUN_BINDINGS.json").read_text(encoding="utf-8"))
        validate_clean2_formal_manifest(wrapper, bindings["clean2_formal_schema_path"])
        current_nav = (run_root / wrapper["output_files"]["exact_nav"]).resolve(strict=True)
        current_std = (run_root / wrapper["output_files"]["exact_std"]).resolve(strict=True)
        current_solver_path = (run_root / wrapper["output_files"]["solver_manifest"]).resolve(strict=True)
        current_solver = json.loads(current_solver_path.read_text(encoding="utf-8"))
        reference = references[method]
        reference_solver = json.loads(Path(reference["solver_manifest_path"]).read_text(encoding="utf-8"))
        counter_exact = all(int(current_solver[field]) == int(reference_solver[field]) for field in counter_fields)
        numeric = _compare_nav_std(
            current_nav, Path(reference["nav_path"]), current_std, Path(reference["std_path"]), tolerance
        )
        comparisons.append({
            "method": method,
            "run_id": row["run_id"],
            "wrapper_sha256": sha256_file(wrapper_path),
            "current_nav_sha256": sha256_file(current_nav),
            "current_std_sha256": sha256_file(current_std),
            "reference_nav_sha256": reference["nav_sha256"],
            "reference_std_sha256": reference["std_sha256"],
            "counter_fields": list(counter_fields),
            "counters_exact": counter_exact,
            "numeric": numeric,
            "passed": counter_exact and numeric["passed"],
        })
    payload = {
        "schema_version": "paper_rebuild.clean2_c00_structural_gate.v1",
        "stage_id": STAGE_ID,
        "code_commit": expected_code_freeze_commit,
        "code_worktree_dirty": False,
        "registry_sha256": sha256_file(registry_path),
        "case_provider_index_sha256": index_payload["index_sha256"],
        "executable_sha256": sha256_file(executable_path),
        "executable_source_manifest_sha256": executable_manifest["manifest_sha256"],
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
    payload["binding_digest"] = sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return payload


def produce_structural_gate(output_path: str | Path, **kwargs: Any) -> dict[str, Any]:
    destination = Path(output_path)
    if destination.exists() or destination.is_symlink():
        raise Clean2RunError("CLEAN2 structural gate destination must be fresh")
    payload = _structural_gate_payload(**kwargs)
    if not payload["passed"]:
        raise Clean2RunError("BLOCKED_CLEAN2_C00_STRUCTURAL_PARITY_FAILED")
    write_json_atomic(destination, payload)
    return payload


def require_structural_gate(path: str | Path, **kwargs: Any) -> dict[str, Any]:
    actual = json.loads(Path(path).resolve(strict=True).read_text(encoding="utf-8"))
    expected = _structural_gate_payload(**kwargs)
    if actual != expected or actual.get("passed") is not True:
        raise Clean2RunError("BLOCKED_CLEAN2_C00_STRUCTURAL_PARITY_FAILED")
    return actual


def _classify_technical_failure(returncode: int, stderr: str, stdout: str = "") -> str:
    """Return a retryable class only for explicit transient evidence."""

    lowered = (stderr + "\n" + stdout).casefold()
    # 中文说明：人工授权没有把 timeout 列入可重试原因。超时可能是确定性
    # hang，必须终止本阶段；只有显式 signal crash/I/O/resource/lost-PTY 可重试。
    if returncode == 124 or "process group terminated after timeout" in lowered:
        return ""
    # subprocess uses a negative return code when a signal terminated the
    # child. Shell-style 128+signal codes are accepted only for the standard
    # signal range; an ordinary positive solver error remains non-retryable.
    if returncode < 0 or 129 <= returncode <= 159:
        return "process_crash"
    if any(value in lowered for value in ("resource temporarily unavailable", "out of memory", "cannot allocate memory")):
        return "resource_exhaustion"
    if any(value in lowered for value in ("input/output error", "stale file handle")):
        return "I/O_transient"
    if any(value in lowered for value in ("lost pty", "broken pipe")):
        return "lost_PTY"
    return ""


def _phase_health_from_manifest(
    run_root: Path, formal_manifest: Mapping[str, Any]
) -> dict[str, Any]:
    health = dict(formal_manifest["output_health"])
    return {
        "nav_relative_path": formal_manifest["output_files"]["exact_nav"],
        "formal_manifest_relative_path": "CLEAN2_FORMAL_RUN_MANIFEST.json",
        "formal_manifest_sha256": sha256_file(run_root / "CLEAN2_FORMAL_RUN_MANIFEST.json"),
        "file_open_audit_relative_path": formal_manifest["output_files"]["file_open_audit"],
        "file_open_audit_sha256": formal_manifest["output_hashes"]["file_open_audit"],
        **health,
    }


def _execute_one(
    row: Mapping[str, Any], *, executable: Path, runtime_root: Path, timeout_seconds: int,
    attempts_path: Path, code_root: Path, raw_root: Path, expected_code_commit: str,
    executable_source_manifest: str | Path,
) -> dict[str, Any]:
    run_root = runtime_root / str(row["run_id"])
    config = run_root / "runtime_config" / "CLEAN2_RUNTIME_CONFIG.yaml"
    if sha256_file(config) != row["runtime_config_hash"]:
        raise Clean2RunError("Runtime config changed after registry materialization")
    bindings = _load_run_bindings(
        run_root,
        row,
        code_root=code_root,
        raw_root=raw_root,
        expected_code_commit=expected_code_commit,
        executable=executable,
        executable_source_manifest=executable_source_manifest,
    )
    strace = shutil.which("strace")
    if strace is None:
        raise Clean2RunError("BLOCKED_CLEAN2_FORMAL_EXECUTION_FAILED: strace is required")
    first_failure_reason = ""
    for attempt_number in (1, 2):
        attempt_root = run_root / "attempts" / f"attempt_{attempt_number}"
        attempt_root.mkdir(parents=True, exist_ok=False)
        strace_path = attempt_root / BASE_OUTPUT_ROLE_NAMES["file_open_trace"]
        solver_command = [
            str(executable), "--config", str(config), "--output-dir", str(attempt_root),
            "--debug-update-timeline", "--debug-output-dir", str(attempt_root),
        ]
        executed_command = [
            strace,
            "-f",
            "-qq",
            "-yy",
            "-s",
            "4096",
            "-e",
            "trace=openat",
            "-o",
            str(strace_path),
            *solver_command,
        ]
        started = time.monotonic()
        completed = run_process_group(
            executed_command,
            cwd=executable.parent,
            timeout_seconds=timeout_seconds,
            timeout_message="CLEAN2 solver timeout; process group terminated",
            launch_failure_message="CLEAN2 solver launch failure",
        )
        elapsed = time.monotonic() - started
        retry_reason = _classify_technical_failure(
            completed.returncode, completed.stderr, completed.stdout
        )
        success = completed.returncode == 0
        (attempt_root / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (attempt_root / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
        if success:
            try:
                _write_solver_file_open_audit(
                    strace_path=strace_path,
                    attempt_root=attempt_root,
                    row=row,
                    bindings=bindings,
                    raw_root=raw_root,
                    command_cwd=executable.parent,
                )
                formal_manifest = _write_formal_wrapper(
                    run_root=run_root,
                    attempt_root=attempt_root,
                    row=row,
                    bindings=bindings,
                    runtime_seconds=elapsed,
                )
                health = _phase_health_from_manifest(run_root, formal_manifest)
            except Exception:
                _append_attempt_row(
                    attempts_path,
                    {
                        "run_id": row["run_id"], "run_order": row["run_order"],
                        "attempt_number": attempt_number, "technical_retry": attempt_number == 2,
                        "retry_reason": first_failure_reason, "metric_driven_rerun": False,
                        "returncode": completed.returncode, "runtime_seconds": elapsed,
                        "terminal_status": "VALIDATION_FAILURE_NO_RETRY",
                    },
                )
                raise
            _append_attempt_row(
                attempts_path,
                {
                    "run_id": row["run_id"], "run_order": row["run_order"],
                    "attempt_number": attempt_number, "technical_retry": attempt_number == 2,
                    "retry_reason": first_failure_reason, "metric_driven_rerun": False,
                    "returncode": 0, "runtime_seconds": elapsed, "terminal_status": "PASS",
                },
            )
            return health
        terminal = "RETRYABLE_TECHNICAL_FAILURE" if retry_reason else "NONRETRYABLE_FAILURE"
        _append_attempt_row(
            attempts_path,
            {
                "run_id": row["run_id"], "run_order": row["run_order"],
                "attempt_number": attempt_number, "technical_retry": attempt_number == 2,
                "retry_reason": retry_reason or first_failure_reason,
                "metric_driven_rerun": False, "returncode": completed.returncode,
                "runtime_seconds": elapsed, "terminal_status": terminal,
            },
        )
        if attempt_number == 2 or not retry_reason:
            raise Clean2RunError("BLOCKED_CLEAN2_FORMAL_EXECUTION_FAILED")
        first_failure_reason = retry_reason
    raise Clean2RunError("BLOCKED_CLEAN2_FORMAL_EXECUTION_FAILED")


def _write_attempt_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    existing: list[dict[str, Any]] = []
    if path.is_file():
        with path.open("r", encoding="utf-8", newline="") as handle:
            existing = list(csv.DictReader(handle))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ATTEMPT_FIELDS))
        writer.writeheader()
        writer.writerows([*existing, *rows])


def _append_attempt_row(path: Path, row: Mapping[str, Any]) -> None:
    """Persist each attempt before any later process can fail; serialize parallel writers."""

    with _ATTEMPT_LEDGER_LOCK:
        _write_attempt_rows(path, [row])


def _attempt_bool(value: Any, *, field: str) -> bool:
    if value in {True, "true", "True"}:
        return True
    if value in {False, "false", "False"}:
        return False
    raise Clean2RunError(f"Attempt ledger boolean is invalid: {field}")


def validate_attempt_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    registry_rows: Sequence[Mapping[str, Any]] | None = None,
    required_run_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Require one terminal PASS per config and at most one authorized retry."""

    allowed_retry_reasons = {
        "process_crash",
        "I/O_transient",
        "resource_exhaustion",
        "lost_PTY",
    }
    registry_by_id = (
        {str(row["run_id"]): row for row in registry_rows}
        if registry_rows is not None
        else None
    )
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        run_id = str(row.get("run_id") or "")
        if not run_id or (registry_by_id is not None and run_id not in registry_by_id):
            raise Clean2RunError("Attempt ledger run_id is empty or absent from registry")
        if _attempt_bool(row.get("metric_driven_rerun"), field="metric_driven_rerun"):
            raise Clean2RunError("Metric-driven rerun is forbidden")
        grouped.setdefault(run_id, []).append(row)
    if required_run_ids is not None and set(grouped) != set(required_run_ids):
        raise Clean2RunError("Attempt ledger terminal run set differs from the required phase prefix")

    retry_count = 0
    for run_id, attempts in grouped.items():
        if registry_by_id is not None and any(
            int(str(row.get("run_order") or "0"))
            != int(registry_by_id[run_id]["run_order"])
            for row in attempts
        ):
            raise Clean2RunError("Attempt ledger run_order differs from registry")
        numbers = [int(str(row.get("attempt_number") or "0")) for row in attempts]
        if numbers not in ([1], [1, 2]):
            raise Clean2RunError("Formal attempts must be exactly [1] or [1,2]")
        first = attempts[0]
        if _attempt_bool(first.get("technical_retry"), field="technical_retry"):
            raise Clean2RunError("First formal attempt cannot be marked as a retry")
        first_reason = str(first.get("retry_reason") or "")
        first_status = str(first.get("terminal_status") or "")
        first_return = int(str(first.get("returncode") or "0"))
        if len(attempts) == 1:
            if first_reason or first_status != "PASS" or first_return != 0:
                raise Clean2RunError("Single formal attempt is not a terminal PASS")
            continue
        retry_count += 1
        second = attempts[1]
        if (
            first_reason not in allowed_retry_reasons
            or first_status != "RETRYABLE_TECHNICAL_FAILURE"
            or first_return == 0
            or not _attempt_bool(second.get("technical_retry"), field="technical_retry")
            or str(second.get("retry_reason") or "") != first_reason
            or str(second.get("terminal_status") or "") != "PASS"
            or int(str(second.get("returncode") or "0")) != 0
        ):
            raise Clean2RunError("Formal retry chain is not one authorized technical retry then PASS")
    return {
        "run_count": len(grouped),
        "attempt_count": len(rows),
        "technical_retry_run_count": retry_count,
        "all_terminal_pass": True,
        "metric_driven_rerun": False,
        "passed": True,
    }


def write_terminal_attempt_audit(
    *, registry_path: str | Path, attempts_path: str | Path, output_path: str | Path
) -> dict[str, Any]:
    registry = read_run_registry(registry_path)
    with Path(attempts_path).resolve(strict=True).open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    required = {str(row["run_id"]) for row in registry}
    audit = validate_attempt_rows(
        rows,
        registry_rows=registry,
        required_run_ids=required,
    )
    if audit["run_count"] != 110:
        raise Clean2RunError("CLEAN2 terminal attempt audit does not contain 110 runs")
    payload = {
        "schema_version": "paper_rebuild.clean2_terminal_attempt_audit.v1",
        "stage_id": STAGE_ID,
        "registry_sha256": sha256_file(registry_path),
        "attempts_sha256": sha256_file(attempts_path),
        **audit,
    }
    destination = Path(output_path)
    if destination.exists() or destination.is_symlink():
        raise Clean2RunError("CLEAN2 terminal attempt audit destination must be fresh")
    write_json_atomic(destination, payload)
    return payload


def _phase_health_path(runtime_root: Path, phase: str) -> Path:
    return runtime_root / f"PHASE_{phase.upper()}_HEALTH.json"


def _phase_result_digest(results: Sequence[Mapping[str, Any]]) -> str:
    return sha256_text(json.dumps(list(results), sort_keys=True, separators=(",", ":")))


def _validate_completed_phase(
    runtime_root: Path,
    phase: str,
    registry_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    expected_rows = phase_rows(registry_rows, phase)
    path = _phase_health_path(runtime_root, phase).resolve(strict=True)
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = payload.get("results")
    if (
        payload.get("schema_version") != "paper_rebuild.clean2_phase_health.v2"
        or payload.get("phase") != phase
        or payload.get("run_count") != len(expected_rows)
        or payload.get("health_checks_only") is not True
        or payload.get("performance_metric_read") is not False
        or payload.get("trace_open_count") != 0
        or payload.get("passed") is not True
        or not isinstance(results, list)
        or payload.get("results_sha256") != _phase_result_digest(results)
    ):
        raise Clean2RunError(f"CLEAN2 predecessor phase health is invalid: {phase}")
    expected_identity = [
        (str(row["run_id"]), int(row["run_order"])) for row in expected_rows
    ]
    actual_identity = [
        (str(row.get("run_id") or ""), int(row.get("run_order") or 0))
        for row in results
        if isinstance(row, Mapping)
    ]
    if actual_identity != expected_identity:
        raise Clean2RunError(f"CLEAN2 predecessor wrapper set/order differs: {phase}")
    registry_by_id = {str(row["run_id"]): row for row in expected_rows}
    for result in results:
        run_id = str(result["run_id"])
        run_root = runtime_root / run_id
        manifest_path = (run_root / "CLEAN2_FORMAL_RUN_MANIFEST.json").resolve(strict=True)
        if sha256_file(manifest_path) != result.get("formal_manifest_sha256"):
            raise Clean2RunError(f"CLEAN2 predecessor wrapper hash changed: {phase}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        bindings = json.loads(
            (run_root / "runtime_config" / "RUN_BINDINGS.json").read_text(encoding="utf-8")
        )
        validate_clean2_formal_manifest(manifest, bindings["clean2_formal_schema_path"])
        outputs: dict[str, Path] = {}
        for role, relative_value in manifest["output_files"].items():
            relative = Path(str(relative_value))
            candidate = run_root / relative
            if candidate.is_symlink():
                raise Clean2RunError(f"CLEAN2 predecessor output is a symlink: {phase}")
            artifact = candidate.resolve(strict=True)
            if not is_within(artifact, run_root) or not artifact.is_file():
                raise Clean2RunError(f"CLEAN2 predecessor output escaped the run root: {phase}")
            if sha256_file(artifact) != manifest["output_hashes"].get(role):
                raise Clean2RunError(f"CLEAN2 predecessor output hash changed: {phase}")
            outputs[str(role)] = artifact
        recomputed_health = _formal_numeric_output_health(outputs)
        if recomputed_health != manifest.get("output_health"):
            raise Clean2RunError(f"CLEAN2 predecessor NAV/STD health changed: {phase}")
        row = registry_by_id[run_id]
        identity_fields = (
            "run_id", "case_id", "result_namespace", "structural_method", "ablation_id",
            "feature_RD", "feature_SA", "feature_RP", "feature_HV", "run_order", "formal",
            "alias_roles",
        )
        if any(manifest.get(field) != row.get(field) for field in identity_fields):
            raise Clean2RunError(f"CLEAN2 predecessor wrapper/registry mismatch: {phase}")
        audit_path = (run_root / manifest["output_files"]["file_open_audit"]).resolve(strict=True)
        if sha256_file(audit_path) != result.get("file_open_audit_sha256"):
            raise Clean2RunError(f"CLEAN2 predecessor file-read audit hash changed: {phase}")
        expected_result = {
            "run_id": run_id,
            "run_order": int(row["run_order"]),
            **_phase_health_from_manifest(run_root, manifest),
        }
        if dict(result) != expected_result:
            raise Clean2RunError(f"CLEAN2 predecessor health/wrapper binding changed: {phase}")
    return payload


def _require_phase_predecessors(
    runtime_root: Path,
    phase: str,
    registry_rows: Sequence[Mapping[str, Any]],
) -> None:
    index = PHASE_ORDER.index(phase)
    for predecessor in PHASE_ORDER[:index]:
        _validate_completed_phase(runtime_root, predecessor, registry_rows)


def _assert_target_phase_fresh(
    runtime_root: Path,
    phase: str,
    selected_rows: Sequence[Mapping[str, Any]],
    attempts_path: Path,
) -> None:
    health_path = _phase_health_path(runtime_root, phase)
    if health_path.exists() or health_path.is_symlink():
        raise Clean2RunError("CLEAN2 target phase health already exists")
    attempted: set[str] = set()
    if attempts_path.is_file():
        with attempts_path.open("r", encoding="utf-8", newline="") as handle:
            attempted = {str(row.get("run_id") or "") for row in csv.DictReader(handle)}
    for row in selected_rows:
        run_root = runtime_root / str(row["run_id"])
        if (
            str(row["run_id"]) in attempted
            or (run_root / "attempts").exists()
            or (run_root / "attempts").is_symlink()
            or (run_root / "CLEAN2_FORMAL_RUN_MANIFEST.json").exists()
        ):
            raise Clean2RunError("CLEAN2 target phase is not fresh")


def execute_prepared_phase(
    *,
    registry_path: str | Path,
    runtime_root: str | Path,
    executable: str | Path,
    phase: str,
    attempts_path: str | Path,
    jobs: int = DEFAULT_JOBS,
    timeout_seconds: int = 900,
    structural_gate_report: str | Path | None = None,
    code_root: str | Path,
    raw_root: str | Path,
    expected_code_freeze_commit: str,
    executable_source_manifest: str | Path,
    case_provider_index: str | Path,
    clean1_reference_index: str | Path | None = None,
    parity_contract: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Execute one phase using structural health only; metric access is absent by design."""

    if not 1 <= jobs <= MAX_JOBS:
        raise Clean2RunError("CLEAN2 jobs must be within 1..12")
    if phase != "structural_gate":
        if structural_gate_report is None or clean1_reference_index is None or parity_contract is None:
            raise Clean2RunError("Remaining CLEAN2 phases require the C00 structural gate report")
    rows = read_run_registry(registry_path)
    selected = phase_rows(rows, phase)
    executable_path = Path(executable).resolve(strict=True)
    if any(row["executable_hash"] != sha256_file(executable_path) for row in selected):
        raise Clean2RunError("CLEAN2 executable hash differs from the registry")
    runtime = Path(runtime_root).resolve(strict=True)
    code = Path(code_root).resolve(strict=True)
    raw = Path(raw_root).resolve(strict=True)
    attempts_file = Path(attempts_path)
    _require_phase_predecessors(runtime, phase, rows)
    _assert_target_phase_fresh(runtime, phase, selected, attempts_file)
    if phase != "structural_gate":
        require_structural_gate(
            structural_gate_report,
            registry_path=registry_path,
            runtime_root=runtime,
            executable=executable_path,
            executable_source_manifest=executable_source_manifest,
            case_provider_index=case_provider_index,
            code_root=code,
            expected_code_freeze_commit=expected_code_freeze_commit,
            clean1_reference_index=clean1_reference_index,
            parity_contract=parity_contract,
        )
    results: list[dict[str, Any]] = []
    phase_jobs = 1 if phase == "structural_gate" else jobs
    with concurrent.futures.ThreadPoolExecutor(max_workers=phase_jobs) as pool:
        futures = {
            pool.submit(
                _execute_one,
                row,
                executable=executable_path,
                runtime_root=runtime,
                timeout_seconds=timeout_seconds,
                attempts_path=attempts_file,
                code_root=code,
                raw_root=raw,
                expected_code_commit=expected_code_freeze_commit,
                executable_source_manifest=executable_source_manifest,
            ): row
            for row in selected
        }
        for future in concurrent.futures.as_completed(futures):
            row = futures[future]
            health = future.result()
            results.append({"run_id": row["run_id"], "run_order": row["run_order"], **health})
    results.sort(key=lambda row: int(row["run_order"]))
    with attempts_file.open("r", encoding="utf-8", newline="") as handle:
        attempt_rows = list(csv.DictReader(handle))
    phase_index = PHASE_ORDER.index(phase)
    required_prefix = {
        str(row["run_id"])
        for predecessor in PHASE_ORDER[: phase_index + 1]
        for row in phase_rows(rows, predecessor)
    }
    validate_attempt_rows(
        attempt_rows,
        registry_rows=rows,
        required_run_ids=required_prefix,
    )
    health_payload = {
        "schema_version": "paper_rebuild.clean2_phase_health.v2",
        "phase": phase,
        "run_count": len(results),
        "health_checks_only": True,
        "performance_metric_read": False,
        "trace_open_count": 0,
        "results": results,
        "results_sha256": _phase_result_digest(results),
        "passed": len(results) == len(selected),
    }
    write_json_atomic(_phase_health_path(runtime, phase), health_payload)
    _validate_completed_phase(runtime, phase, rows)
    return results
