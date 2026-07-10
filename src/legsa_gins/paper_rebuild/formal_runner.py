"""CLEAN1 fixed-order formal runner, separate from the CLEAN0 smoke runner."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from .evaluator import load_frozen_evaluator
from .evidence import BY2_RAW_RELATIVE_PATHS, parse_strace_openat_paths
from .formal_manifest import assert_formal_run_manifest
from .formal_provider import FormalProviderBundle, load_formal_provider_bundle
from .manifest import git_code_state, sha256_file, sha256_text, write_json_atomic
from .methods import (
    FORMAL_METHOD_ORDER,
    FORBIDDEN_DEFAULT_FIELDS,
    MethodCatalog,
    canonical_config_hash,
    load_method_catalog,
)
from .paths import CleanPaths, guard_path, is_within, legacy_reason, load_clean_paths
from .protocol import (
    CASE_ID,
    DATA_MODE,
    PROTOCOL_ID,
    STAGE_ID,
    build_common_covariance_contract,
    load_clean1_protocol,
    load_frozen_window,
)
from .subprocess_guard import run_process_group


RUN_DIRECTORY_NAMES = (
    "01_single_antenna_EKF",
    "02_basic_dual_yaw_EKF",
    "03_strong_dual_yaw_EKF",
    "04_LegSA_Paper_V1",
)


class FormalRunError(RuntimeError):
    """A formal comparison gate or solver execution failed closed."""


def _quote(value: str | Path) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _hash_mapping(value: Mapping[str, Any]) -> str:
    return sha256_text(json.dumps(dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _environment_hash() -> str:
    payload = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
    }
    return _hash_mapping(payload)


def _solver_file_open_crosscheck(
    strace_path: Path,
    destination: Path,
    *,
    paths: CleanPaths,
    output_root: Path,
    expected_provider_paths: Mapping[str, str],
) -> dict[str, Any]:
    opened = parse_strace_openat_paths(strace_path, cwd=paths.code_root)
    expected = {role: Path(value).resolve(strict=True) for role, value in expected_provider_paths.items()}
    provider_opened = [path for path in opened if is_within(path, paths.provider_root)]
    counts = {
        role: sum(path == expected_path for path in provider_opened)
        for role, expected_path in expected.items()
    }
    missing = sorted(role for role, count in counts.items() if count == 0)
    expected_set = set(expected.values())
    unexpected_provider = sorted(
        {
            path.relative_to(paths.provider_root).as_posix()
            for path in provider_opened
            if path not in expected_set
        }
    )
    raw_reads = sorted(
        {
            path.relative_to(paths.raw_root).as_posix()
            for path in opened
            if is_within(path, paths.raw_root)
        }
    )
    unexpected_clean = sorted(
        {
            path.relative_to(paths.clean_root).as_posix()
            for path in opened
            if is_within(path, paths.clean_root)
            and not is_within(path, paths.provider_root)
            and not is_within(path, output_root)
        }
    )
    legacy_read_count = sum(legacy_reason(path) is not None for path in opened)
    report = {
        "schema_version": "paper-rebuild-solver-file-open-crosscheck-v1",
        "strace_available": True,
        "strace_sha256": sha256_file(strace_path),
        "expected_provider_role_open_counts": counts,
        "missing_expected_provider_roles": missing,
        "unexpected_provider_relative_paths": unexpected_provider,
        "raw_root_read_relative_paths": raw_reads,
        "unexpected_clean_root_relative_paths": unexpected_clean,
        "legacy_path_read_count": legacy_read_count,
        "opened_path_count": len(opened),
        "passed": not missing and not unexpected_provider and not raw_reads and not unexpected_clean and legacy_read_count == 0,
    }
    write_json_atomic(destination, report)
    if not report["passed"]:
        raise FormalRunError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    return report


def _assert_clean1_blocked_evaluator_gate(paths: CleanPaths, evaluator_path: Path) -> None:
    """CLEAN1 is blocked-only: no external frozen YAML may unlock solver execution."""

    payload = load_frozen_evaluator(evaluator_path, require_ready=False)
    sidecar = evaluator_path.with_suffix(".sha256")
    if not sidecar.is_file():
        raise FormalRunError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    sidecar_fields = sidecar.read_text(encoding="utf-8").strip().split()
    tracked_contract = paths.code_root / "configs/paper_rebuild/evaluator_contract.yaml"
    if (
        len(sidecar_fields) < 1
        or sidecar_fields[0] != sha256_file(evaluator_path)
        or not tracked_contract.is_file()
        or payload.get("tracked_contract_sha256") != sha256_file(tracked_contract)
    ):
        raise FormalRunError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    expected_blocked = {
        "reference_point_contract_proven": False,
        "reference_attitude_frame_contract_proven": False,
        "formal_metrics_authorized": False,
        "terminal_status": "BLOCKED_CLEAN1_EVALUATOR_CONTRACT_FAILED",
        "method_output_read_during_freeze": False,
    }
    if any(payload.get(field) != value for field, value in expected_blocked.items()):
        raise FormalRunError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    raise FormalRunError("BLOCKED_CLEAN1_EVALUATOR_CONTRACT_FAILED")


def _assert_solver_common_manifest(
    solver_manifest: Mapping[str, Any],
    common: Mapping[str, Any],
    window: Mapping[str, Any],
) -> None:
    """Prove that the C++ post-parse values equal the tracked common contract."""

    exact = {
        "receiver_velocity_stress_mode": common["receiver_velocity_stress_mode"],
        "raw_doppler_mode": common["raw_doppler_mode"],
        "source_aware_policy_version": common["source_aware_policy"],
        "source_aware_mode": common["source_aware_mode"],
        "source_aware_method_family": common["source_aware_method_family"],
        "source_aware_policy_branch_id": common[
            "source_aware_effective_policy_branch"
        ],
        "go2_horizontal_velocity_prior_mode": common["go2_horizontal_velocity_prior_mode"],
    }
    booleans = {
        "diagnostic_stress_only": common["diagnostic_stress_only"],
        "source_aware_use_innovation_covariance": common[
            "source_aware_use_innovation_covariance"
        ],
        "source_aware_reject_extreme": common["source_aware_reject_extreme"],
        "source_aware_no_R_shrink": common["source_aware_no_R_shrink"],
        "source_aware_trace_enabled": common["source_aware_trace_enabled"],
        "source_aware_enable_rolling_innovation_baseline": common[
            "source_aware_enable_rolling_innovation_baseline"
        ],
        "go2_attitude_prior_sourceaware_enabled": common[
            "go2_attitude_prior_source_aware_enabled"
        ],
        "go2_horizontal_velocity_prior_source_aware_enabled": common[
            "go2_horizontal_velocity_source_aware_enabled"
        ],
        "go2_horizontal_velocity_adaptive_std_enabled": common[
            "go2_horizontal_velocity_adaptive_std_enabled"
        ],
        "go2_horizontal_velocity_prior_vertical_disabled": not common[
            "go2_vertical_velocity_enabled"
        ],
    }
    integers = {
        "receiver_velocity_additive_noise_seed": common[
            "receiver_velocity_additive_noise_seed"
        ],
        "raw_doppler_min_sat": common["raw_doppler_min_sat"],
        "source_aware_rolling_window_size": common[
            "source_aware_rolling_window_size"
        ],
    }
    numerics = {
        "receiver_velocity_std_scale": common["receiver_velocity_std_scale"],
        "receiver_velocity_outage_start_sec": common[
            "receiver_velocity_outage_start_seconds"
        ],
        "receiver_velocity_outage_duration_sec": common[
            "receiver_velocity_outage_duration_seconds"
        ],
        "receiver_velocity_additive_noise_std_mps": common[
            "receiver_velocity_additive_noise_std_mps"
        ],
        "yaw_std_min_deg": common["yaw_std_min_deg"],
        "yaw_std_soft_deg": common["yaw_std_soft_deg"],
        "yaw_std_hard_deg": common["yaw_std_hard_deg"],
        "yaw_res_soft_deg": common["yaw_residual_soft_deg"],
        "yaw_res_hard_deg": common["yaw_residual_hard_deg"],
        "yaw_downweight_scale": common["yaw_downweight_scale"],
        "raw_doppler_time_tolerance_sec": common[
            "raw_doppler_time_tolerance_seconds"
        ],
        "raw_doppler_residual_gate_mps": common["raw_doppler_residual_gate_mps"],
        "raw_doppler_R_scale": common["raw_doppler_R_scale"],
        "go2_attitude_prior_std_roll_deg": common["go2_roll_pitch_std_deg"],
        "go2_attitude_prior_std_pitch_deg": common["go2_roll_pitch_std_deg"],
        "go2_attitude_prior_time_tolerance_sec": common[
            "go2_roll_pitch_time_tolerance_seconds"
        ],
        "go2_velocity_prior_time_tolerance_sec": common[
            "go2_horizontal_velocity_time_tolerance_seconds"
        ],
        "go2_horizontal_velocity_prior_std_scale": common[
            "go2_horizontal_velocity_std_scale"
        ],
        "source_aware_max_R_scale": common["source_aware_max_R_scale"],
        "source_aware_global_cap": common["source_aware_global_cap"],
        "source_aware_deadband_normalized": common[
            "source_aware_deadband_normalized"
        ],
        "source_aware_moderate_normalized": common[
            "source_aware_moderate_normalized"
        ],
        "source_aware_strong_normalized": common["source_aware_strong_normalized"],
        "source_aware_rolling_mad_floor": common["source_aware_rolling_mad_floor"],
        "source_aware_method_k0": common["source_aware_method_k0"],
        "source_aware_method_k1": common["source_aware_method_k1"],
        "source_aware_method_c": common["source_aware_method_c"],
        "source_aware_method_alpha": common["source_aware_method_alpha"],
        "source_aware_method_phi": common["source_aware_method_phi"],
        "source_aware_method_base_gain": common["source_aware_method_base_gain"],
    }
    for field, expected in exact.items():
        if solver_manifest.get(field) != expected:
            raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")
    for field, expected in booleans.items():
        if solver_manifest.get(field) is not expected:
            raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")
    for field, expected in integers.items():
        value = solver_manifest.get(field)
        if isinstance(value, bool) or value != int(expected):
            raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")
    for field, expected in numerics.items():
        try:
            actual = float(solver_manifest[field])
        except (KeyError, TypeError, ValueError) as exc:
            raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH") from exc
        if not math.isclose(actual, float(expected), rel_tol=1.0e-12, abs_tol=1.0e-12):
            raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")

    initialization = window.get("common_initialization")
    if not isinstance(initialization, Mapping):
        raise FormalRunError("BLOCKED_CLEAN1_WINDOW_OR_INITIALIZATION_CONTRACT_FAILED")
    expected_scalars = {
        "starttime": window["t_start"],
        "endtime": window["t_end"],
        "imudatalen": common["imu_data_columns"],
        "imudatarate": common["imu_data_rate_hz"],
        "correlation_time_h": common["correlation_time_h"],
    }
    for field, expected in expected_scalars.items():
        try:
            actual = float(solver_manifest[field])
        except (KeyError, TypeError, ValueError) as exc:
            raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH") from exc
        if not math.isclose(actual, float(expected), rel_tol=1.0e-12, abs_tol=1.0e-12):
            raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")
    if solver_manifest.get("common_initialization_source") != window.get(
        "common_initialization_hash"
    ):
        raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")

    expected_sequences = {
        "init_position_geodetic_deg_m": initialization["position_geodetic_deg_m"],
        "init_velocity_ned_mps": initialization["velocity_ned_mps"],
        "init_attitude_deg": [
            *initialization["roll_pitch_deg"],
            initialization["yaw_ned_deg"],
        ],
        "init_gyro_bias_deg_h": common["init_gyro_bias"],
        "init_accel_bias_mgal": common["init_accel_bias"],
        "init_gyro_scale_ppm": common["init_gyro_scale"],
        "init_accel_scale_ppm": common["init_accel_scale"],
        "init_position_std_m": common["init_position_std_m"],
        "init_velocity_std_mps": common["init_velocity_std_mps"],
        "init_attitude_std_deg": common["init_attitude_std_deg"],
        "init_gyro_bias_std_deg_h": common["init_gyro_bias_std_deg_h"],
        "init_accel_bias_std_mgal": common["init_accel_bias_std_mgal"],
        "init_gyro_scale_std_ppm": common["init_gyro_scale_std_ppm"],
        "init_accel_scale_std_ppm": common["init_accel_scale_std_ppm"],
        "angle_random_walk_deg_sqrt_h": common["angle_random_walk_deg_sqrt_h"],
        "velocity_random_walk_mps_sqrt_h": common[
            "velocity_random_walk_mps_sqrt_h"
        ],
        "gyro_bias_std_deg_h": common["gyro_bias_std_deg_h"],
        "accel_bias_std_mgal": common["accel_bias_std_mgal"],
        "gyro_scale_std_ppm": common["gyro_scale_std_ppm"],
        "accel_scale_std_ppm": common["accel_scale_std_ppm"],
        "antlever_m": common["antenna_lever_m"],
        "common_initialization_covariance_diagonal_internal": initialization[
            "covariance_diagonal"
        ],
    }
    for field, expected in expected_sequences.items():
        actual = solver_manifest.get(field)
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")
        for actual_value, expected_value in zip(actual, expected):
            try:
                actual_numeric = float(actual_value)
            except (TypeError, ValueError) as exc:
                raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH") from exc
            if not math.isclose(
                actual_numeric,
                float(expected_value),
                rel_tol=1.0e-12,
                abs_tol=1.0e-18,
            ):
                raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")

    expected_source_configs = common.get("source_aware_sources")
    actual_source_configs = solver_manifest.get("source_aware_source_configs")
    if (
        not isinstance(expected_source_configs, Mapping)
        or not isinstance(actual_source_configs, Mapping)
        or set(actual_source_configs) != set(expected_source_configs)
    ):
        raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")
    for source_name, expected_config in expected_source_configs.items():
        if not isinstance(expected_config, Mapping) or actual_source_configs.get(
            source_name
        ) != dict(expected_config):
            raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")

    expected_caps = {
        "receiver_position": float(common["source_aware_receiver_position_cap"]),
        "receiver_velocity": float(common["source_aware_receiver_velocity_cap"]),
        "dual_antenna_yaw": float(common["source_aware_dual_yaw_cap"]),
        "raw_doppler_velocity": float(common["source_aware_raw_doppler_cap"]),
        "go2_attitude_roll_pitch": float(common["source_aware_go2_attitude_cap"]),
        "go2_horizontal_velocity": float(
            common["source_aware_go2_horizontal_velocity_cap"]
        ),
        "global": float(common["source_aware_global_cap"]),
    }
    actual_caps = solver_manifest.get("source_caps")
    if not isinstance(actual_caps, Mapping) or set(actual_caps) != set(expected_caps):
        raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")
    for field, expected in expected_caps.items():
        try:
            actual = float(actual_caps[field])
        except (TypeError, ValueError) as exc:
            raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH") from exc
        if not math.isclose(actual, expected, rel_tol=1.0e-12, abs_tol=1.0e-12):
            raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")


def _assert_solver_forbidden_manifest(solver_manifest: Mapping[str, Any]) -> None:
    false_fields = (
        "paper_performance_claim",
        "final_v23_output_solver_input",
        "LegSA_output_solver_input",
        "trace_used_online",
        "synthetic_data_used",
        "semisynthetic_data_used",
        "receiver_imu_as_body_imu",
        "per_case_tuning",
        "output_only_correction",
        "epoch_deleted_for_metric",
        "status_fallback_used",
        "legacy_provider_used",
        "trace_used_for_initialization",
        "method_specific_initialization",
        "evaluation_reference_point_match_established",
        "reference_point_compensation_applied",
        "go2_position_truth_claim",
        "go2_velocity_truth_claim",
        "go2_yaw_truth_claim",
        "go2_contact_truth_claim",
    )
    zero_fields = (
        "old_runtime_input_count",
        "legacy_provider_input_count",
        "legacy_row_input_count",
        "legacy_aggregate_input_count",
    )
    if any(solver_manifest.get(field) is not False for field in false_fields):
        raise FormalRunError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    if any(solver_manifest.get(field) != 0 for field in zero_fields):
        raise FormalRunError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    expected_identity = {
        "clean1_formal_mode": True,
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        "case_id": CASE_ID,
        "data_mode": DATA_MODE,
        "common_initialization": True,
        "common_initialization_dual_yaw_used": True,
        "propagation_imu_source": "hash_locked_go2_body",
        "solver_output_reference_point": "propagation_imu_reference_point",
    }
    if any(solver_manifest.get(field) != value for field, value in expected_identity.items()):
        raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")


def build_effective_method_metadata(
    catalog: MethodCatalog,
    bundle: FormalProviderBundle,
    window: Mapping[str, Any],
    evaluator_contract_path: str | Path,
    protocol_payload: Mapping[str, Any],
    *,
    code_commit: str,
    executable_hash: str,
) -> dict[str, dict[str, Any]]:
    """Build path-free comparable metadata; only methods.yaml fields may differ."""

    evaluator_hash = sha256_file(evaluator_contract_path)
    initialization_hash = str(window.get("common_initialization_hash") or "")
    if len(initialization_hash) != 64:
        initialization_hash = _hash_mapping(window["common_initialization"])
    solver_common = protocol_payload.get("solver_common")
    dual_yaw = protocol_payload.get("dual_yaw")
    if not isinstance(solver_common, Mapping) or not isinstance(dual_yaw, Mapping):
        raise FormalRunError("Tracked protocol lacks solver_common/dual_yaw")
    common = {
        "dataset": "BY2",
        "case_id": CASE_ID,
        "code_commit": code_commit,
        "provider_bundle_hash": bundle.provider_bundle_hash,
        "window_contract_hash": sha256_file(window["_contract_path"]),
        "common_initialization_hash": initialization_hash,
        "base_parameters_hash": _hash_mapping(solver_common),
        "frame_contract_hash": _hash_mapping({"dual_yaw": dual_yaw, "evaluator": "frozen_contract"}),
        "antenna_geometry_hash": _hash_mapping(dual_yaw),
        "evaluator_contract_hash": evaluator_hash,
        "numerical_precision": solver_common["numerical_precision"],
        "executable_hash": executable_hash,
        "environment_hash": _environment_hash(),
        "timeout_seconds": int(solver_common["timeout_seconds"]),
    }
    effective: dict[str, dict[str, Any]] = {}
    for index, method_id in enumerate(FORMAL_METHOD_ORDER, start=1):
        method = catalog.method(method_id)
        effective[method_id] = {
            **common,
            **{field: catalog.payload["defaults"][field] for field in FORBIDDEN_DEFAULT_FIELDS},
            "algorithm_id": method_id,
            "method_role": method["role"],
            "run_id": RUN_DIRECTORY_NAMES[index - 1],
            "run_label": RUN_DIRECTORY_NAMES[index - 1],
            "output_dir_alias": f"<RUNTIME_ROOT>/{RUN_DIRECTORY_NAMES[index - 1]}",
            "enable_basic_dual_yaw_baseline": method_id == "basic_dual_yaw_EKF",
            "basic_dual_yaw_fixed_std_deg": (
                method.get("yaw_contract", {}).get("fixed_std_deg", "NOT_METHOD_SPECIFIC")
            ),
            **catalog.features(method_id),
        }
    return effective


def build_formal_runtime_config(
    method_id: str,
    catalog: MethodCatalog,
    bundle: FormalProviderBundle,
    window: Mapping[str, Any],
    protocol_payload: Mapping[str, Any],
    output_dir: Path,
) -> str:
    """Create one runtime-only config from frozen contracts and fresh provider paths."""

    if method_id not in FORMAL_METHOD_ORDER:
        raise FormalRunError("Method is outside the frozen CLEAN1 set")
    features = catalog.features(method_id)
    init = window["common_initialization"]
    common = protocol_payload["solver_common"]
    expected_covariance = build_common_covariance_contract(common)
    if init.get("covariance_contract") != expected_covariance or init.get("covariance_diagonal") != expected_covariance["covariance_diagonal_internal"]:
        raise FormalRunError("BLOCKED_CLEAN1_WINDOW_OR_INITIALIZATION_CONTRACT_FAILED")
    raw = bundle.raw_doppler_report
    raw_path = bundle.artifacts["raw_doppler_provider"] if features["enable_raw_doppler"] else None
    go2_attitude = bundle.artifacts["go2_attitude_prior"] if features["enable_go2_roll_pitch_prior"] else None
    go2_velocity = (
        bundle.artifacts["go2_horizontal_velocity_prior"]
        if features["enable_go2_horizontal_velocity_prior"]
        else None
    )
    init_pos = init["position_geodetic_deg_m"]
    init_vel = init["velocity_ned_mps"]
    init_att = [*init["roll_pitch_deg"], init["yaw_ned_deg"]]
    lines = [
        "# CLEAN1 runtime-only config generated from frozen tracked contracts.",
        "clean1_formal_mode: true",
        f"stage_id: {STAGE_ID}",
        f"protocol_id: {PROTOCOL_ID}",
        f"case_id: {CASE_ID}",
        f"data_mode: {DATA_MODE}",
        f"run_id: {RUN_DIRECTORY_NAMES[FORMAL_METHOD_ORDER.index(method_id)]}",
        f"run_label: {RUN_DIRECTORY_NAMES[FORMAL_METHOD_ORDER.index(method_id)]}",
        f"algorithm_id: {method_id}",
        f"imupath: {_quote(bundle.artifacts['imu_runtime_input'])}",
        f"gnsspath: {_quote(bundle.artifacts['gnss_runtime_input'])}",
        f"outputpath: {_quote(output_dir)}",
        "propagation_imu_source: hash_locked_go2_body",
        "solver_output_reference_point: propagation_imu_reference_point",
        "antlever_config_source: runtime_config_antlever",
        "evaluation_reference_point_match_established: false",
        "reference_point_compensation_applied: false",
        "common_initialization: true",
        "common_initialization_dual_yaw_used: true",
        "trace_used_for_initialization: false",
        "method_specific_initialization: false",
        f"common_initialization_source: {window['common_initialization_hash']}",
        f"imudatalen: {int(common['imu_data_columns'])}",
        f"imudatarate: {int(common['imu_data_rate_hz'])}",
        f"starttime: {float(window['t_start']):.12g}",
        f"endtime: {float(window['t_end']):.12g}",
        "initpos: [ " + ", ".join(f"{float(value):.12g}" for value in init_pos) + " ]",
        "initvel: [ " + ", ".join(f"{float(value):.12g}" for value in init_vel) + " ]",
        "initatt: [ " + ", ".join(f"{float(value):.12g}" for value in init_att) + " ]",
        "initgyrbias: [ " + ", ".join(map(str, common["init_gyro_bias"])) + " ]",
        "initaccbias: [ " + ", ".join(map(str, common["init_accel_bias"])) + " ]",
        "initgyrscale: [ " + ", ".join(map(str, common["init_gyro_scale"])) + " ]",
        "initaccscale: [ " + ", ".join(map(str, common["init_accel_scale"])) + " ]",
        "initposstd: [ " + ", ".join(map(str, common["init_position_std_m"])) + " ]",
        "initvelstd: [ " + ", ".join(map(str, common["init_velocity_std_mps"])) + " ]",
        "initattstd: [ " + ", ".join(map(str, common["init_attitude_std_deg"])) + " ]",
        "arw: [ " + ", ".join(map(str, common["angle_random_walk_deg_sqrt_h"])) + " ]",
        "vrw: [ " + ", ".join(map(str, common["velocity_random_walk_mps_sqrt_h"])) + " ]",
        "gbstd: [ " + ", ".join(map(str, common["gyro_bias_std_deg_h"])) + " ]",
        "abstd: [ " + ", ".join(map(str, common["accel_bias_std_mgal"])) + " ]",
        "gsstd: [ " + ", ".join(map(str, common["gyro_scale_std_ppm"])) + " ]",
        "asstd: [ " + ", ".join(map(str, common["accel_scale_std_ppm"])) + " ]",
        f"corrtime: {float(common['correlation_time_h']):.12g}",
        "antlever: [ " + ", ".join(map(str, common["antenna_lever_m"])) + " ]",
        "initbgstd: [ " + ", ".join(map(str, common["init_gyro_bias_std_deg_h"])) + " ]",
        "initbastd: [ " + ", ".join(map(str, common["init_accel_bias_std_mgal"])) + " ]",
        "initsgstd: [ " + ", ".join(map(str, common["init_gyro_scale_std_ppm"])) + " ]",
        "initsastd: [ " + ", ".join(map(str, common["init_accel_scale_std_ppm"])) + " ]",
    ]
    for feature, enabled in features.items():
        lines.append(f"{feature}: {'true' if enabled else 'false'}")
    lines.extend(
        [
            "basic_dual_yaw_fixed_std_deg: 1.5",
            f"raw_doppler_factor_path: {_quote(raw_path) if raw_path else ''}",
            f"raw_doppler_factor_source: {raw['raw_doppler_backend_id']}",
            f"raw_doppler_backend_id: {raw['raw_doppler_backend_id']}",
            "raw_doppler_backend_source_files: " + _quote(json.dumps(raw["raw_doppler_backend_source_files"], sort_keys=True)),
            "raw_doppler_backend_source_hashes: " + _quote(json.dumps(raw["raw_doppler_backend_source_hashes"], sort_keys=True)),
            f"helper_executable_hash: {raw['helper_executable_hash']}",
            f"obs_source_hash: {raw['obs_source_hash']}",
            f"nav_source_hash: {raw['nav_source_hash']}",
            f"conversion_config_hash: {raw['conversion_config_hash']}",
            f"covariance_policy: {raw['covariance_policy']}",
            f"raw_doppler_min_sat: {int(common['raw_doppler_min_sat'])}",
            f"raw_doppler_mode: {common['raw_doppler_mode']}",
            f"raw_doppler_time_tolerance_sec: {float(common['raw_doppler_time_tolerance_seconds']):.12g}",
            f"raw_doppler_residual_gate_mps: {float(common['raw_doppler_residual_gate_mps']):.12g}",
            f"raw_doppler_R_scale: {float(common['raw_doppler_R_scale']):.12g}",
            "rtklib_position_solution_used_as_solver_input: false",
            "nav_pvt_velocity_used_as_raw_doppler: false",
            "gnss_velocity_used_as_raw_doppler: false",
            "status_fallback_used: false",
            "legacy_provider_used: false",
            f"source_aware_policy_version: {common['source_aware_policy']}",
            f"source_aware_mode: {common['source_aware_mode']}",
            f"source_aware_max_R_scale: {float(common['source_aware_max_R_scale']):.12g}",
            f"source_aware_global_cap: {float(common['source_aware_global_cap']):.12g}",
            f"source_aware_use_innovation_covariance: {'true' if common['source_aware_use_innovation_covariance'] else 'false'}",
            f"source_aware_deadband_normalized: {float(common['source_aware_deadband_normalized']):.12g}",
            f"source_aware_moderate_normalized: {float(common['source_aware_moderate_normalized']):.12g}",
            f"source_aware_strong_normalized: {float(common['source_aware_strong_normalized']):.12g}",
            f"source_aware_receiver_position_cap: {float(common['source_aware_receiver_position_cap']):.12g}",
            f"source_aware_receiver_velocity_cap: {float(common['source_aware_receiver_velocity_cap']):.12g}",
            f"source_aware_dual_yaw_cap: {float(common['source_aware_dual_yaw_cap']):.12g}",
            f"source_aware_raw_doppler_cap: {float(common['source_aware_raw_doppler_cap']):.12g}",
            f"source_aware_go2_attitude_cap: {float(common['source_aware_go2_attitude_cap']):.12g}",
            f"source_aware_go2_horizontal_velocity_cap: {float(common['source_aware_go2_horizontal_velocity_cap']):.12g}",
            f"source_aware_reject_extreme: {'true' if common['source_aware_reject_extreme'] else 'false'}",
            f"source_aware_no_R_shrink: {'true' if common['source_aware_no_R_shrink'] else 'false'}",
            f"source_aware_trace_enabled: {'true' if common['source_aware_trace_enabled'] else 'false'}",
            f"source_aware_enable_rolling_innovation_baseline: {'true' if common['source_aware_enable_rolling_innovation_baseline'] else 'false'}",
            f"source_aware_rolling_window_size: {int(common['source_aware_rolling_window_size'])}",
            f"source_aware_rolling_mad_floor: {float(common['source_aware_rolling_mad_floor']):.12g}",
            f"source_aware_method_family: {common['source_aware_method_family']}",
            f"source_aware_method_k0: {float(common['source_aware_method_k0']):.12g}",
            f"source_aware_method_k1: {float(common['source_aware_method_k1']):.12g}",
            f"source_aware_method_c: {float(common['source_aware_method_c']):.12g}",
            f"source_aware_method_alpha: {float(common['source_aware_method_alpha']):.12g}",
            f"source_aware_method_phi: {float(common['source_aware_method_phi']):.12g}",
            f"source_aware_method_base_gain: {float(common['source_aware_method_base_gain']):.12g}",
            f"go2_attitude_prior_path: {_quote(go2_attitude) if go2_attitude else ''}",
            f"go2_attitude_prior_std_roll_deg: {float(common['go2_roll_pitch_std_deg']):.12g}",
            f"go2_attitude_prior_std_pitch_deg: {float(common['go2_roll_pitch_std_deg']):.12g}",
            f"go2_attitude_prior_time_tolerance_sec: {float(common['go2_roll_pitch_time_tolerance_seconds']):.12g}",
            f"go2_attitude_prior_sourceaware: {'true' if common['go2_attitude_prior_source_aware_enabled'] else 'false'}",
            f"go2_horizontal_velocity_prior_path: {_quote(go2_velocity) if go2_velocity else ''}",
            "go2_horizontal_velocity_prior_vertical_disabled: true",
            f"go2_horizontal_velocity_prior_mode: {common['go2_horizontal_velocity_prior_mode']}",
            f"go2_velocity_prior_time_tolerance_sec: {float(common['go2_horizontal_velocity_time_tolerance_seconds']):.12g}",
            f"go2_horizontal_velocity_prior_std_scale: {float(common['go2_horizontal_velocity_std_scale']):.12g}",
            f"go2_horizontal_velocity_prior_source_aware_enabled: {'true' if common['go2_horizontal_velocity_source_aware_enabled'] else 'false'}",
            f"go2_horizontal_velocity_adaptive_std_enabled: {'true' if common['go2_horizontal_velocity_adaptive_std_enabled'] else 'false'}",
            "go2_position_prior_enabled: false",
            "go2_velocity_prior_enabled: false",
            "go2_yaw_prior_enabled: false",
            "go2_vertical_velocity_prior_enabled: false",
            "go2_position_truth_claim: false",
            "go2_velocity_truth_claim: false",
            "go2_yaw_truth_claim: false",
            "go2_contact_truth_claim: false",
            f"receiver_velocity_stress_mode: {common['receiver_velocity_stress_mode']}",
            f"receiver_velocity_std_scale: {float(common['receiver_velocity_std_scale']):.12g}",
            f"receiver_velocity_outage_start_sec: {float(common['receiver_velocity_outage_start_seconds']):.12g}",
            f"receiver_velocity_outage_duration_sec: {float(common['receiver_velocity_outage_duration_seconds']):.12g}",
            f"receiver_velocity_additive_noise_std_mps: {float(common['receiver_velocity_additive_noise_std_mps']):.12g}",
            f"receiver_velocity_additive_noise_seed: {int(common['receiver_velocity_additive_noise_seed'])}",
            f"diagnostic_stress_only: {'true' if common['diagnostic_stress_only'] else 'false'}",
            f"yaw_std_min_deg: {float(common['yaw_std_min_deg']):.12g}",
            f"yaw_std_soft_deg: {float(common['yaw_std_soft_deg']):.12g}",
            f"yaw_std_hard_deg: {float(common['yaw_std_hard_deg']):.12g}",
            f"yaw_res_soft_deg: {float(common['yaw_residual_soft_deg']):.12g}",
            f"yaw_res_hard_deg: {float(common['yaw_residual_hard_deg']):.12g}",
            f"yaw_downweight_scale: {float(common['yaw_downweight_scale']):.12g}",
            "enable_selected_fgo_feedback: false",
            "enable_no_feedback_fgo: false",
            "enable_active_nine_factor_fgo: false",
            "enable_multi_state_qm: false",
            "enable_qa_fallback: false",
            "enable_go2_joint_factor: false",
            "enable_contact_fk_factor: false",
            "trace_used_online: false",
            "receiver_imu_as_body_imu: false",
            "synthetic_data_used: false",
            "semisynthetic_data_used: false",
            "final_v23_output_solver_input: false",
            "LegSA_output_solver_input: false",
            "per_case_tuning: false",
            "output_only_correction: false",
            "epoch_deleted_for_metric: false",
            "old_runtime_input_count: 0",
            "legacy_provider_input_count: 0",
            "legacy_row_input_count: 0",
            "legacy_aggregate_input_count: 0",
            "paper_performance_claim: false",
        ]
    )
    source_configs = common.get("source_aware_sources")
    if not isinstance(source_configs, Mapping):
        raise FormalRunError("Tracked source-aware per-source contract is missing")
    for source_name, source_config in source_configs.items():
        if not isinstance(source_config, Mapping):
            raise FormalRunError("Tracked source-aware per-source contract is invalid")
        for field in ("enabled", "lsim_enabled", "oim_enabled"):
            value = source_config.get(field)
            if not isinstance(value, bool):
                raise FormalRunError("Tracked source-aware per-source flag is invalid")
            lines.append(
                f"source_aware_{source_name}_{field}: {'true' if value else 'false'}"
            )
    return "\n".join(lines) + "\n"


class FormalFourMethodRunner:
    """Run exactly four methods, sequentially, only after every pre-run gate."""

    def __init__(
        self,
        local_config: str | Path,
        *,
        window_contract: str | Path,
        evaluator_contract: str | Path,
        protocol_config: str | Path,
        methods_config: str | Path,
        attempt_ledger: str | Path,
    ):
        self.paths: CleanPaths = load_clean_paths(local_config)
        self.window_path = Path(window_contract).resolve(strict=True)
        self.evaluator_path = Path(evaluator_contract).resolve(strict=True)
        self.protocol = load_clean1_protocol(protocol_config)
        self.catalog = load_method_catalog(methods_config)
        self.attempt_ledger = Path(attempt_ledger)
        self.attempt_session_id = uuid.uuid4().hex
        self.prior_attempt_rows: list[dict[str, Any]] = []
        if self.attempt_ledger.is_file():
            with self.attempt_ledger.open("r", encoding="utf-8", newline="") as handle:
                self.prior_attempt_rows = list(csv.DictReader(handle))

    def run(self) -> list[dict[str, Any]]:
        # The evaluator gate is deliberately first: a blocked point contract creates no run directory.
        _assert_clean1_blocked_evaluator_gate(self.paths, self.evaluator_path)
        window = load_frozen_window(self.window_path)
        bundle = load_formal_provider_bundle(self.paths)
        code_commit, dirty = git_code_state(self.paths.code_root)
        if dirty or code_commit != bundle.generator_code_commit:
            raise FormalRunError("BLOCKED_CLEAN1_GIT_OR_CODE_FREEZE_FAILED")
        executable = guard_path(
            self.paths.port_core_exe,
            role="CLEAN1 port-core executable",
            allowed_root=self.paths.code_root,
            must_exist=True,
            regular_file=True,
        )
        if self.paths.runtime_root.exists():
            raise FormalRunError("Fresh CLEAN1 runtime root already exists")
        self.paths.runtime_root.parent.mkdir(parents=True, exist_ok=True)
        runtime_attempt = guard_path(
            self.paths.runtime_root.parent
            / f".{self.paths.runtime_root.name}.attempt-{uuid.uuid4().hex}",
            role="CLEAN1 formal runtime attempt",
            allowed_root=self.paths.clean_root,
        )
        runtime_attempt.mkdir(parents=False, exist_ok=False)
        rows: list[dict[str, Any]] = []
        manifests: list[dict[str, Any]] = []
        timeout_seconds = int(self.protocol.payload["solver_common"]["timeout_seconds"])
        for index, method_id in enumerate(FORMAL_METHOD_ORDER):
            output = runtime_attempt / RUN_DIRECTORY_NAMES[index]
            output.mkdir()
            runtime_config = output / "runtime_config" / "CLEAN1_RUNTIME_CONFIG.yaml"
            runtime_config.parent.mkdir()
            config_text = build_formal_runtime_config(
                method_id,
                self.catalog,
                bundle,
                window,
                self.protocol.payload,
                output,
            )
            runtime_config.write_text(config_text, encoding="utf-8")
            command = [str(executable), "--config", str(runtime_config), "--output-dir", str(output)]
            expected_actual_paths = {
                "propagation_imu": str(bundle.artifacts["imu_runtime_input"]),
                "gnss_position_receiver_velocity_dual_yaw": str(bundle.artifacts["gnss_runtime_input"]),
            }
            features = self.catalog.features(method_id)
            if features["enable_raw_doppler"]:
                expected_actual_paths["raw_doppler_velocity"] = str(bundle.artifacts["raw_doppler_provider"])
            if features["enable_go2_roll_pitch_prior"]:
                expected_actual_paths["go2_roll_pitch_weak_prior"] = str(bundle.artifacts["go2_attitude_prior"])
            if features["enable_go2_horizontal_velocity_prior"]:
                expected_actual_paths["go2_horizontal_velocity_weak_prior"] = str(
                    bundle.artifacts["go2_horizontal_velocity_prior"]
                )
            logs = output / "logs"
            logs.mkdir()
            strace = shutil.which("strace")
            strace_path = logs / "SOLVER_FILE_OPEN_TRACE.raw"
            executed_command = (
                [strace, "-f", "-qq", "-yy", "-s", "4096", "-e", "trace=openat", "-o", str(strace_path), *command]
                if strace
                else command
            )
            started = time.monotonic()
            completed = run_process_group(
                executed_command,
                cwd=self.paths.code_root,
                timeout_seconds=timeout_seconds,
                timeout_message="solver attempt timeout; entire process group terminated",
                launch_failure_message="solver attempt launch failure",
            )
            failure_class = {
                0: "",
                124: "timeout",
                127: "launch_failure",
            }.get(completed.returncode, "solver_nonzero_returncode")
            elapsed = time.monotonic() - started
            (logs / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
            (logs / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
            solver_manifest_path = output / "RUN_MANIFEST.json"
            if completed.returncode != 0 or not solver_manifest_path.is_file():
                rows.append({"attempt": index + 1, "algorithm_id": method_id, "returncode": completed.returncode, "failure_class": failure_class or "manifest_missing", "terminal_success": False, "metric_driven_rerun": False})
                self._write_attempts(rows)
                raise FormalRunError("BLOCKED_CLEAN1_FOUR_METHOD_SET_INCOMPLETE")
            if strace:
                solver_file_open = _solver_file_open_crosscheck(
                    strace_path,
                    logs / "SOLVER_FILE_OPEN_CROSSCHECK.json",
                    paths=self.paths,
                    output_root=output,
                    expected_provider_paths=expected_actual_paths,
                )
            else:
                solver_file_open = {
                    "schema_version": "paper-rebuild-solver-file-open-crosscheck-v1",
                    "strace_available": False,
                    "fallback": "explicit_input_registry_static_dependency_audit",
                    "passed": True,
                }
                write_json_atomic(logs / "SOLVER_FILE_OPEN_CROSSCHECK.json", solver_file_open)
            solver_manifest = json.loads(solver_manifest_path.read_text(encoding="utf-8"))
            _assert_solver_forbidden_manifest(solver_manifest)
            _assert_solver_common_manifest(
                solver_manifest, self.protocol.payload["solver_common"], window
            )
            if (
                solver_manifest.get("algorithm_id") != method_id
                or solver_manifest.get("run_id") != RUN_DIRECTORY_NAMES[index]
                or solver_manifest.get("phase") != STAGE_ID
            ):
                raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")
            expected_features = self.catalog.features(method_id)
            solver_feature_values = {
                "enable_dual_yaw": solver_manifest.get("enable_dual_yaw_update"),
                "enable_receiver_velocity": solver_manifest.get("enable_receiver_velocity_update"),
                "enable_raw_doppler": solver_manifest.get("enable_raw_doppler"),
                "enable_source_aware": solver_manifest.get("source_aware_weighting_enabled"),
                "enable_go2_roll_pitch_prior": solver_manifest.get("go2_attitude_weak_prior_enabled"),
                "enable_go2_horizontal_velocity_prior": solver_manifest.get("go2_horizontal_velocity_prior_enabled"),
            }
            if solver_feature_values != expected_features:
                raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")
            if solver_manifest.get("enable_basic_dual_yaw_baseline") is not (
                method_id == "basic_dual_yaw_EKF"
            ):
                raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")
            if method_id == "basic_dual_yaw_EKF" and float(
                solver_manifest.get("basic_dual_yaw_fixed_std_deg", -1.0)
            ) != 1.5:
                raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")
            (output / "SOLVER_RUN_MANIFEST.json").write_text(
                json.dumps(solver_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            output_files = {
                "nav": "LegSA_PORT_NAV.nav",
                "std": "LegSA_PORT_STD.csv",
                "eval_nav": "EVAL_NAV.csv",
            }
            missing = [name for name in output_files.values() if not (output / name).is_file()]
            if missing:
                raise FormalRunError("BLOCKED_CLEAN1_FOUR_METHOD_SET_INCOMPLETE")
            output_hashes = {role: sha256_file(output / name) for role, name in output_files.items()}
            counters = solver_manifest.get("module_update_counts")
            actual_roles = dict(solver_manifest.get("actual_solver_input_roles") or {})
            actual_paths = dict(solver_manifest.get("actual_solver_input_paths") or {})
            safe_paths = {
                "propagation_imu": bundle.provider_relpaths["imu_runtime_input"],
                "gnss_position_receiver_velocity_dual_yaw": bundle.provider_relpaths["gnss_runtime_input"],
            }
            if self.catalog.features(method_id)["enable_raw_doppler"]:
                safe_paths["raw_doppler_velocity"] = bundle.provider_relpaths["raw_doppler_provider"]
            if self.catalog.features(method_id)["enable_go2_roll_pitch_prior"]:
                safe_paths["go2_roll_pitch_weak_prior"] = bundle.provider_relpaths["go2_attitude_prior"]
            if self.catalog.features(method_id)["enable_go2_horizontal_velocity_prior"]:
                safe_paths["go2_horizontal_velocity_weak_prior"] = bundle.provider_relpaths["go2_horizontal_velocity_prior"]
            if set(actual_roles) != set(safe_paths):
                raise FormalRunError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
            if actual_paths != expected_actual_paths:
                raise FormalRunError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
            with (output / "SOLVER_ACTUAL_INPUT_LEDGER.csv").open(
                "w", encoding="utf-8", newline=""
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["read_order", "path_alias", "relative_path", "role", "sha256", "reader_component", "file_open_crosscheck_sha256"],
                )
                writer.writeheader()
                for read_order, role in enumerate(safe_paths, start=1):
                    provider_role = {
                        "propagation_imu": "imu_runtime_input",
                        "gnss_position_receiver_velocity_dual_yaw": "gnss_runtime_input",
                        "raw_doppler_velocity": "raw_doppler_provider",
                        "go2_roll_pitch_weak_prior": "go2_attitude_prior",
                        "go2_horizontal_velocity_weak_prior": "go2_horizontal_velocity_prior",
                    }[role]
                    writer.writerow(
                        {
                            "read_order": read_order,
                            "path_alias": "<PROVIDER_ROOT>",
                            "relative_path": safe_paths[role],
                            "role": role,
                            "sha256": bundle.provider_hashes[provider_role],
                            "reader_component": "legsa_v23_port_core",
                            "file_open_crosscheck_sha256": sha256_file(
                                logs / "SOLVER_FILE_OPEN_CROSSCHECK.json"
                            ),
                        }
                    )
            manifest = {
                "schema_version": "paper-rebuild-formal-run-manifest-v1",
                "stage_id": STAGE_ID,
                "protocol_id": PROTOCOL_ID,
                "case_id": CASE_ID,
                "data_mode": DATA_MODE,
                "run_id": RUN_DIRECTORY_NAMES[index],
                "algorithm_id": method_id,
                "method_role": self.catalog.method(method_id)["role"],
                "code_commit": code_commit,
                "code_worktree_dirty_at_run": False,
                "executable_hash": sha256_file(executable),
                "runtime_config_hash": sha256_text(config_text),
                "methods_yaml_hash": self.catalog.source_sha256,
                "window_contract_hash": sha256_file(self.window_path),
                "evaluator_contract_hash": sha256_file(self.evaluator_path),
                "raw_source_hashes": bundle.raw_source_hashes,
                "provider_hashes": bundle.provider_hashes,
                "provider_generator_commit": bundle.generator_code_commit,
                "provider_generation_config_hash": bundle.generator_config_hash,
                "local_path_config_hash": bundle.local_path_config_hash,
                "actual_solver_input_paths": safe_paths,
                "actual_solver_input_roles": list(safe_paths),
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
                "legacy_provider_input_count": 0,
                "legacy_row_input_count": 0,
                "legacy_aggregate_input_count": 0,
                "status_fallback_used": False,
                "go2_position_truth_claim": False,
                "go2_velocity_truth_claim": False,
                "go2_yaw_truth_claim": False,
                "go2_contact_truth_claim": False,
                "common_initialization": True,
                "common_initialization_dual_yaw_used": True,
                "solver_returncode": completed.returncode,
                "runtime_seconds": round(elapsed, 6),
                "module_update_counts": counters,
                "output_files": output_files,
                "output_hashes": output_hashes,
                "terminal_status": "PASS",
                "paper_performance_claim": False,
            }
            assert_formal_run_manifest(manifest, self.catalog, require_pass=True)
            write_json_atomic(output / "FORMAL_RUN_MANIFEST.json", manifest)
            manifests.append(manifest)
            rows.append({"attempt": index + 1, "algorithm_id": method_id, "returncode": completed.returncode, "failure_class": "", "terminal_success": True, "metric_driven_rerun": False})
            self._write_attempts(rows)
        if len(manifests) != 4:
            raise FormalRunError("BLOCKED_CLEAN1_FOUR_METHOD_SET_INCOMPLETE")
        runtime_attempt.rename(self.paths.runtime_root)
        return manifests

    def _write_attempts(self, rows: list[dict[str, Any]]) -> None:
        current_methods = [str(row.get("algorithm_id") or "") for row in rows]
        if current_methods != list(FORMAL_METHOD_ORDER[: len(rows)]):
            raise FormalRunError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")
        self.attempt_ledger.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.attempt_ledger.with_name(
            f".{self.attempt_ledger.name}.tmp-{uuid.uuid4().hex}"
        )
        with temporary.open("x", encoding="utf-8", newline="") as handle:
            fieldnames = ["session_id", "attempt", "algorithm_id", "returncode", "failure_class", "terminal_success", "metric_driven_rerun"]
            writer = csv.DictWriter(
                handle,
                fieldnames=fieldnames,
            )
            writer.writeheader()
            for prior in self.prior_attempt_rows:
                writer.writerow({field: prior.get(field, "") for field in fieldnames})
            for row in rows:
                writer.writerow({"session_id": self.attempt_session_id, **row})
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.attempt_ledger)
        directory_fd = os.open(self.attempt_ledger.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
