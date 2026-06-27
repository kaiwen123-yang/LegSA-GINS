#!/usr/bin/env python3
"""Map frozen PAPER10 modes to the BY2 port-core runner for M0 smoke.

中文说明：adapter 只生成 M0 smoke runtime config 并调用正式
``legsa_v23_port_core_demo --config --output-dir`` 入口；不运行 full matrix，
不使用 trace/final_v23/LegSA/benchmark 输出作为 solver 输入。
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.paper10m0_method_mode_loader import (
    load_all,
    resolve_effective_feature_flags,
    validate_mode_safety,
)
from scripts.paper10m0_output_contract_validator import validate_smoke_output


MODE_TO_FORMAL_ALGORITHM = {
    "basic_dual_baseline": "source_backed_EKF",
    "strong_dual_yaw_baseline": "source_backed_EKF",
    "legsa_without_qm": "Go2_joint_EKF",
    "legsa_full_candidate_with_qm": "LegSA_full_EKF",
}


@dataclass(frozen=True)
class Paper10M0Paths:
    code_root: Path
    project_root: Path
    runtime_root: Path
    by2_imu: Path
    by2_gnss: Path
    by2_body: Path
    by2_trace: Path | None
    raw_doppler_provider: Path | None
    go2_attitude_provider: Path | None
    go2_horizontal_velocity_provider: Path | None
    go2_joint_provider: Path | None


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def provider_status_from_paths(paths: Paper10M0Paths) -> dict[str, bool]:
    return {
        "raw_doppler": bool(paths.raw_doppler_provider and paths.raw_doppler_provider.is_file()),
        "go2_roll_pitch": bool(paths.go2_attitude_provider and paths.go2_attitude_provider.is_file()),
        "go2_horizontal_velocity": bool(
            paths.go2_horizontal_velocity_provider and paths.go2_horizontal_velocity_provider.is_file()
        ),
        "go2_joint_factor": bool(paths.go2_joint_provider and paths.go2_joint_provider.is_file()),
        "go2_readiness_motion_metadata": False,
        "multi_state_qm": True,
    }


def build_runtime_config(
    method_mode_id: str,
    mode: dict[str, Any],
    effective_flags: dict[str, bool],
    output_dir: Path,
    paths: Paper10M0Paths,
    config_sha256: str,
) -> str:
    raw_path = paths.raw_doppler_provider if effective_flags.get("enable_raw_doppler") else None
    attitude_path = paths.go2_attitude_provider if effective_flags.get("enable_go2_roll_pitch_prior") else None
    hv_path = (
        paths.go2_horizontal_velocity_provider
        if effective_flags.get("enable_go2_horizontal_velocity_prior")
        else None
    )
    joint_path = paths.go2_joint_provider if effective_flags.get("enable_go2_joint_factor") else None
    source_aware = bool(effective_flags.get("enable_source_aware"))
    qm = bool(effective_flags.get("enable_multi_state_qm"))
    fgo_feedback = False
    basic = method_mode_id == "basic_dual_baseline"
    strong = method_mode_id == "strong_dual_yaw_baseline"
    algorithm_id = {
        "basic_dual_baseline": "Basic_Dual_Yaw_EKF",
        "strong_dual_yaw_baseline": "source_backed_EKF",
        "legsa_without_qm": "LegSA_without_QM_EKF",
        "legsa_full_candidate_with_qm": "LegSA_full_candidate_with_qm_EKF",
    }[method_mode_id]
    lines = [
        "# PAPER10M0 runtime-only smoke config.",
        "# Generated outside Git-tracked source; local paths must not be exported.",
        f"run_label: PAPER10M0_{method_mode_id}_BY2_smoke",
        f"algorithm_id: {algorithm_id}",
        f"method_mode_id: {method_mode_id}",
        f"algorithm_role: {mode.get('role', '')}",
        f"ablation_variant: PAPER10M0_{method_mode_id}_smoke",
        f'imupath: "{paths.by2_imu}"',
        f'gnsspath: "{paths.by2_gnss}"',
        f'outputpath: "{output_dir}"',
        "clean_input_provenance_label: BY2_high_level_statusyaw_smoke_readonly",
        "config_policy_evidence_status: PAPER10M0_method_mode_runner_adapter",
        f"paper10m0_smoke: true",
        f"paper10m0_config_sha256: {config_sha256}",
        "paper10m1_full_matrix: false",
        "run_allowed_now: false",
        "imudatalen: 7",
        "imudatarate: 500",
        "starttime: 66.0",
        "endtime: 76.0",
        "initpos: [ 39.98482973, 116.34312609, 41.80208107 ]",
        "initvel: [ 0.0, 0.0, 0.0 ]",
        "initatt: [ 0.0, 0.0, 0.688505 ]",
        "initgyrbias: [ 0.0, 0.0, 0.0 ]",
        "initaccbias: [ 0.0, 0.0, 0.0 ]",
        "initgyrscale: [ 0.0, 0.0, 0.0 ]",
        "initaccscale: [ 0.0, 0.0, 0.0 ]",
        "initposstd: [ 10.0, 10.0, 10.0 ]",
        "initvelstd: [ 1.0, 1.0, 1.0 ]",
        "initattstd: [ 2.0, 2.0, 2.0 ]",
        "arw: [0.985, 0.985, 0.985]",
        "vrw: [0.077, 0.077, 0.077]",
        "gbstd: [9.38, 9.38, 9.38]",
        "abstd: [77.8, 77.8, 77.8]",
        "gsstd: [0.0, 0.0, 0.0]",
        "asstd: [0.0, 0.0, 0.0]",
        "corrtime: 1.0",
        "antlever: [ 0.0, 0.0, -0.25 ]",
        "initbgstd: [9.38, 9.38, 9.38]",
        "initbastd: [77.8, 77.8, 77.8]",
        "initsgstd: [0.0, 0.0, 0.0]",
        "initsastd: [0.0, 0.0, 0.0]",
        f"enable_basic_dual_yaw_baseline: {_bool_text(basic)}",
        f"enable_dual_yaw_update: {_bool_text(basic or strong)}",
        "basic_dual_yaw_fixed_std_deg: 1.5",
        "basic_dual_yaw_residual_sign: official_ref_sign_minus",
        f"enable_receiver_velocity_update: {_bool_text(not basic)}",
        "receiver_velocity_stress_mode: none",
        "receiver_velocity_std_scale: 1.0",
        f"enable_raw_doppler: {_bool_text(bool(raw_path))}",
        f'raw_doppler_factor_path: "{raw_path or ""}"',
        "raw_doppler_factor_source: RTKLIB_DOPPLER_PROVIDER_PAPER10M0_ALIGNED",
        "raw_doppler_time_tolerance_sec: 0.08",
        "raw_doppler_min_sat: 5",
        "raw_doppler_residual_gate_mps: 3.0",
        "raw_doppler_R_scale: 1.0",
        "raw_doppler_mode: doppler_ls_velocity",
        f"enable_source_aware_weighting: {_bool_text(source_aware)}",
        "source_aware_policy_version: n6b_conservative_innovation_covariance",
        f"source_aware_mode: {'lsim_oim' if source_aware else 'off'}",
        "source_aware_use_innovation_covariance: true",
        "source_aware_deadband_normalized: 1.5",
        "source_aware_moderate_normalized: 2.5",
        "source_aware_strong_normalized: 4.0",
        "source_aware_receiver_position_cap: 5.0",
        "source_aware_receiver_velocity_cap: 8.0",
        "source_aware_dual_yaw_cap: 10.0",
        "source_aware_raw_doppler_cap: 15.0",
        "source_aware_go2_attitude_cap: 10.0",
        "source_aware_go2_horizontal_velocity_cap: 10.0",
        "source_aware_global_cap: 25.0",
        "source_aware_max_R_scale: 25.0",
        "source_aware_reject_extreme: false",
        "source_aware_no_R_shrink: true",
        f"source_aware_trace_enabled: {_bool_text(source_aware)}",
        "source_aware_enable_rolling_innovation_baseline: true",
        "source_aware_rolling_window_size: 31",
        "source_aware_rolling_mad_floor: 0.5",
        f"source_aware_go2_attitude_roll_pitch_enabled: {_bool_text(bool(attitude_path))}",
        f"source_aware_go2_attitude_roll_pitch_lsim_enabled: {_bool_text(bool(attitude_path))}",
        f"source_aware_go2_attitude_roll_pitch_oim_enabled: {_bool_text(bool(attitude_path))}",
        f"source_aware_go2_horizontal_velocity_enabled: {_bool_text(bool(hv_path))}",
        f"source_aware_go2_horizontal_velocity_lsim_enabled: {_bool_text(bool(hv_path))}",
        f"source_aware_go2_horizontal_velocity_oim_enabled: {_bool_text(bool(hv_path))}",
        f"enable_go2_attitude_weak_prior: {_bool_text(bool(attitude_path))}",
        f'go2_attitude_prior_path: "{attitude_path or ""}"',
        "go2_attitude_prior_time_tolerance_sec: 0.02",
        "go2_attitude_prior_std_roll_deg: 1.6",
        "go2_attitude_prior_std_pitch_deg: 1.6",
        "go2_attitude_prior_sourceaware: true",
        "go2_attitude_prior_diagnostic_only: false",
        f"enable_go2_horizontal_velocity_prior: {_bool_text(bool(hv_path))}",
        f"enable_go2_velocity_prior_diagnostic: {_bool_text(bool(hv_path))}",
        f'go2_horizontal_velocity_prior_path: "{hv_path or ""}"',
        "go2_horizontal_velocity_prior_std_scale: 1.0",
        "go2_horizontal_velocity_prior_vertical_disabled: true",
        "go2_horizontal_velocity_prior_source_aware_enabled: true",
        "go2_horizontal_velocity_prior_mode: horizontal_2d",
        "go2_horizontal_velocity_strength_policy: n7c6_hv1",
        f"enable_go2_proprioceptive_joint_factor: {_bool_text(bool(joint_path))}",
        f'go2_proprioceptive_joint_factor_path: "{joint_path or ""}"',
        "go2_proprioceptive_joint_factor_mode: sequential_equivalent",
        "go2_proprioceptive_joint_factor_policy: joint_rp1p6deg_hv1p0",
        "go2_proprioceptive_source_aware_enabled: true",
        "go2_position_prior_enabled: false",
        "go2_velocity_prior_enabled: false",
        "go2_yaw_prior_enabled: false",
        "go2_vertical_velocity_prior_enabled: false",
        "enable_go2_yaw_rate_prior_diagnostic: false",
        f"enable_go2_readiness_lsim_metadata: false",
        f"source_aware_go2_readiness_lsim_enabled: false",
        f"enable_multi_state_qm: {_bool_text(qm)}",
        f"multi_state_qm_mode: {'QM05_CONSERVATIVE_FULL' if qm else 'QM00_OFF'}",
        f"multi_state_qm_trace_enabled: {_bool_text(qm)}",
        "multi_state_qm_trace_only: false",
        "qm_downweight_threshold: 2.0",
        "qm_reject_threshold: 3.5",
        "qm_hold_enter_count: 3",
        "qm_hold_length: 3",
        "qm_recovery_count: 2",
        "qm_fallback_enter_count: 2",
        "qm_fallback_exit_count: 2",
        "qm_fallback_max_duration: 3",
        f"enable_fgo_feedback: {_bool_text(fgo_feedback)}",
        'fgo_feedback_path: ""',
        "fgo_feedback_position_enabled: false",
        "fgo_feedback_velocity_enabled: false",
        "fgo_feedback_attitude_enabled: false",
        "qa_passive_logging_enabled: false",
        "enable_qa_fallback: false",
        "qa_active_mode: false",
        "diagnostic_only: false",
        "diagnostic_stress_only: false",
        "proposed_factor_claim: false",
        "paper_performance_claim: false",
        "no_outperform_final_v23_claim: true",
        "trace_solver_input: false",
        "final_v23_output_solver_input: false",
        "legsa_output_solver_input: false",
        "benchmark_output_solver_input: false",
        "per_case_tuning: false",
        "output_only_correction: false",
        "bad_epoch_deletion_for_metric: false",
        "fgo: false",
    ]
    return "\n".join(lines) + "\n"


def _runtime_metadata(method_mode_id: str, mode: dict[str, Any], effective_flags: dict[str, bool], config_sha256: str) -> dict[str, Any]:
    return {
        "method_mode_id": method_mode_id,
        "config_sha256": config_sha256,
        "paper10m0_smoke": True,
        "paper10m1_full_matrix": False,
        "no_trace_online": True,
        "trace_online": False,
        "final_v23_output_input": False,
        "legsa_output_input": False,
        "benchmark_output_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "qa_fallback_final_method": False,
        "benchmark_code_allowed_in_solver": False,
        "feature_flags": effective_flags,
        "claim_level": mode.get("claim_level", ""),
    }


def write_smoke_sidecar_outputs(
    output_dir: Path,
    method_mode_id: str,
    mode: dict[str, Any],
    effective_flags: dict[str, bool],
    config_sha256: str,
) -> None:
    metadata = _runtime_metadata(method_mode_id, mode, effective_flags, config_sha256)
    _write_json(output_dir / "FEATURE_FLAGS.json", metadata)
    _write_json(
        output_dir / "DATASET_ROLE_DUMP.json",
        {
            "dataset": "BY2",
            "dataset_role": "main_dataset",
            "trace": "evaluation_only_reference_not_solver_input",
            "go2_body_state": "auxiliary_weak_prior_or_metadata_not_truth",
            "receiver_imu_data": "receiver_imu_not_go2_body_imu",
            "paper10m0_smoke": True,
        },
    )
    _write_json(
        output_dir / "FORBIDDEN_INPUT_CHECK.json",
        {
            "trace_used_online": False,
            "final_v23_output_used_as_input": False,
            "legsa_output_used_as_input": False,
            "benchmark_output_used_as_input": False,
            "qa_fallback_as_final_method": False,
            "per_case_tuning_used": False,
            "output_only_correction_used": False,
        },
    )
    _write_json(output_dir / "PAPER10M0_RUNNER_CONFIG.json", metadata)


def run_smoke_row(
    *,
    row_id: str,
    method_mode_id: str,
    mode: dict[str, Any],
    config_sha256: str,
    paths: Paper10M0Paths,
    port_core_exe: Path | None = None,
) -> dict[str, Any]:
    provider_status = provider_status_from_paths(paths)
    effective_flags = resolve_effective_feature_flags(mode, provider_status)
    safety_issues = validate_mode_safety(mode, effective_flags)
    output_dir = paths.runtime_root / row_id / method_mode_id
    output_dir.mkdir(parents=True, exist_ok=True)
    config_text = build_runtime_config(method_mode_id, mode, effective_flags, output_dir, paths, config_sha256)
    config_path = output_dir / "runtime_config" / "paper10m0_runtime_config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config_text, encoding="utf-8")
    selected_exe = port_core_exe or paths.code_root / "build" / "cpp" / "legsa_v23_port_core_demo"
    command = [str(selected_exe), "--config", str(config_path), "--output-dir", str(output_dir)]
    start = time.time()
    if safety_issues:
        completed = None
        status = "blocked"
        blocker = "; ".join(safety_issues)
    elif not selected_exe.is_file():
        completed = None
        status = "blocked"
        blocker = "legsa_v23_port_core_demo missing; run CMake build first"
    else:
        completed = subprocess.run(
            command,
            cwd=paths.code_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        (output_dir / "logs").mkdir(exist_ok=True)
        (output_dir / "logs" / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (output_dir / "logs" / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
        status = "solver_completed" if completed.returncode == 0 else "solver_failed"
        blocker = "" if completed.returncode == 0 else (completed.stderr[-1000:] or completed.stdout[-1000:])
    runtime_seconds = time.time() - start
    if status == "solver_completed":
        write_smoke_sidecar_outputs(output_dir, method_mode_id, mode, effective_flags, config_sha256)
    validation = validate_smoke_output(
        output_dir,
        source_trace_required=bool(effective_flags.get("enable_source_aware")),
        qm_trace_required=bool(effective_flags.get("enable_multi_state_qm")),
    )
    if status == "solver_completed" and validation["status"] != "pass":
        status = "output_contract_failed"
        blocker = validation["blocker"]
    return {
        "row_id": row_id,
        "method_mode_id": method_mode_id,
        "case_id": "BY2_NORMAL_CLEAN_SMOKE",
        "runner_launched": completed is not None,
        "solver_completed": status in {"solver_completed"},
        "evaluator_completed": status in {"solver_completed"},
        **validation,
        "runtime_seconds": f"{runtime_seconds:.3f}",
        "status": "pass" if status == "solver_completed" else "fail",
        "blocker": blocker,
        "notes": "PAPER10M0 smoke only; no PAPER10M1/full matrix.",
        "runner_command_alias": "legsa_v23_port_core_demo --config <PAPER10M0_SMOKE_RUNTIME_ROOT>/.../paper10m0_runtime_config.yaml --output-dir <PAPER10M0_SMOKE_RUNTIME_ROOT>/...",
        "runtime_output_alias": f"<PAPER10M0_SMOKE_RUNTIME_ROOT>/{row_id}/{method_mode_id}",
        "runtime_config_alias": f"<PAPER10M0_SMOKE_RUNTIME_ROOT>/{row_id}/{method_mode_id}/runtime_config/paper10m0_runtime_config.yaml",
        "effective_feature_flags": effective_flags,
        "config_sha256": _sha256_text(config_text),
    }


def run_all_smoke_rows(paths: Paper10M0Paths) -> list[dict[str, Any]]:
    loaded = load_all(paths.code_root)
    results: list[dict[str, Any]] = []
    for index, method_mode_id in enumerate(loaded["method_modes"], start=1):
        row_id = f"PAPER10M0_SMOKE_{index:02d}"
        frozen = loaded["method_modes"][method_mode_id]
        results.append(
            run_smoke_row(
                row_id=row_id,
                method_mode_id=method_mode_id,
                mode=frozen.data,
                config_sha256=loaded["config_sha256"],
                paths=paths,
            )
        )
    return results


def main(argv: list[str] | None = None) -> int:
    print("paper10m0_runner_adapter provides library functions; use scripts/experiments/run_paper10m0_runner_mapping_smoke.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
