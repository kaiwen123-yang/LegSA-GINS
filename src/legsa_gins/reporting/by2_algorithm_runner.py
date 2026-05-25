"""Runtime-only BY2 formal LegSA algorithm runner wrapper.

The wrapper calls the existing ``legsa_v23_port_core_demo --config`` surface.
It does not implement EKF/FGO math and deliberately does not use the diagnostic
``legsa_gins --run-filter-csv`` path for formal algorithms.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FORMAL_ALGORITHMS = [
    "source_backed_EKF",
    "baseline_no_feedback_EKF",
    "Raw_Doppler_EKF",
    "source_aware_EKF",
    "Go2_joint_EKF",
    "selected_feedback_EKF",
    "LegSA_full_EKF",
]

REPO_RELATIVE_REQUIRED_INPUTS = {
    "raw_doppler": Path("运行结果") / "N5B_rtklib_doppler_provider_activation" / "RAW_DOPPLER_VELOCITY_FACTORS.csv",
    "go2_attitude": Path("运行结果")
    / "N7C6_go2_proprioceptive_joint_factor"
    / "priors"
    / "joint_rp1p6deg_hv1p0"
    / "GO2_PROPRIOCEPTIVE_ATTITUDE_PRIORS.csv",
    "go2_horizontal_velocity": Path("运行结果")
    / "N7C6_go2_proprioceptive_joint_factor"
    / "priors"
    / "joint_rp1p6deg_hv1p0"
    / "GO2_PROPRIOCEPTIVE_HORIZONTAL_VELOCITY_PRIORS.csv",
    "go2_joint": Path("运行结果")
    / "N7C6_go2_proprioceptive_joint_factor"
    / "priors"
    / "joint_rp1p6deg_hv1p0"
    / "GO2_PROPRIOCEPTIVE_FACTOR_PRIORS.csv",
    "selected_feedback": Path("运行结果")
    / "N8J_feedback_final_validation"
    / "variants"
    / "n8j_selected_conservative_feedback"
    / "FGO_FEEDBACK_OBSERVATIONS.csv",
}

BASE_CONFIG_CANDIDATES = [
    Path("运行结果")
    / "N8J_feedback_final_validation"
    / "variants"
    / "baseline_no_feedback"
    / "config"
    / "legsa_v23_port_clean_replay.conf",
    Path("运行结果")
    / "N8J_feedback_final_validation"
    / "variants"
    / "n8j_selected_conservative_feedback"
    / "config"
    / "legsa_v23_port_clean_replay.conf",
    Path("运行结果")
    / "N5B_rtklib_doppler_provider_activation"
    / "runtime_configs"
    / "n5b_raw_doppler_enabled.yaml",
]


@dataclass(frozen=True)
class AlgorithmRunnerSpec:
    algorithm: str
    ablation_variant: str
    component_flags: dict[str, bool]
    status: str = "runnable_with_wrapper"


ALGORITHM_SPECS = {
    "source_backed_EKF": AlgorithmRunnerSpec(
        algorithm="source_backed_EKF",
        ablation_variant="n9b1f_source_backed_EKF_normal",
        component_flags={
            "raw_doppler": False,
            "source_aware": False,
            "go2_joint": False,
            "feedback": False,
        },
    ),
    "baseline_no_feedback_EKF": AlgorithmRunnerSpec(
        algorithm="baseline_no_feedback_EKF",
        ablation_variant="n9b1f_baseline_no_feedback_EKF_normal",
        component_flags={
            "raw_doppler": False,
            "source_aware": False,
            "go2_joint": False,
            "feedback": False,
        },
    ),
    "Raw_Doppler_EKF": AlgorithmRunnerSpec(
        algorithm="Raw_Doppler_EKF",
        ablation_variant="n9b1f_Raw_Doppler_EKF_normal",
        component_flags={
            "raw_doppler": True,
            "source_aware": False,
            "go2_joint": False,
            "feedback": False,
        },
    ),
    "source_aware_EKF": AlgorithmRunnerSpec(
        algorithm="source_aware_EKF",
        ablation_variant="n9b1f_source_aware_EKF_normal",
        component_flags={
            "raw_doppler": True,
            "source_aware": True,
            "go2_joint": False,
            "feedback": False,
        },
    ),
    "Go2_joint_EKF": AlgorithmRunnerSpec(
        algorithm="Go2_joint_EKF",
        ablation_variant="n9b1f_Go2_joint_EKF_normal",
        component_flags={
            "raw_doppler": True,
            "source_aware": True,
            "go2_joint": True,
            "feedback": False,
        },
    ),
    "selected_feedback_EKF": AlgorithmRunnerSpec(
        algorithm="selected_feedback_EKF",
        ablation_variant="n9b1f_selected_feedback_EKF_normal",
        component_flags={
            "raw_doppler": False,
            "source_aware": False,
            "go2_joint": False,
            "feedback": True,
        },
    ),
    "LegSA_full_EKF": AlgorithmRunnerSpec(
        algorithm="LegSA_full_EKF",
        ablation_variant="n9c0c_LegSA_full_EKF",
        component_flags={
            "raw_doppler": True,
            "source_aware": True,
            "go2_joint": True,
            "feedback": True,
        },
    ),
}


def repo_to_wsl(path: str | Path) -> str:
    text = str(path)
    if re.match(r"^[A-Za-z]:", text):
        return f"/mnt/{text[0].lower()}{text[2:].replace(chr(92), '/')}"
    return text.replace(chr(92), "/")


def running_inside_wsl() -> bool:
    return Path("/proc/sys/kernel/osrelease").exists() and (
        "microsoft" in Path("/proc/sys/kernel/osrelease").read_text(encoding="utf-8", errors="ignore").lower()
    )


def read_json(path: str | Path, default: Any = None) -> Any:
    source = Path(path)
    if not source.exists():
        return default
    try:
        return json.loads(source.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def first_existing(paths: list[Path]) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def find_base_config(workspace_root: Path) -> Path | None:
    return first_existing([workspace_root / rel for rel in BASE_CONFIG_CANDIDATES])


def parse_yaml_like(path: Path) -> dict[str, str]:
    kv: dict[str, str] = {}
    if not path.exists():
        return kv
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
            value = value[1:-1]
        kv[key.strip()] = value
    return kv


def load_base_config_values(workspace_root: Path) -> tuple[dict[str, str], Path | None]:
    base = find_base_config(workspace_root)
    values = parse_yaml_like(base) if base else {}
    return values, base


def resolve_port_core_executable(workspace_root: Path, data_paths_local: Path | None = None) -> dict[str, Any]:
    env_value = os.environ.get("LEGSA_PORT_CORE_EXE")
    candidates: list[str] = []
    if env_value:
        candidates.append(env_value)
    workspace_binary = workspace_root / "build" / "cpp" / "legsa_v23_port_core_demo"
    candidates.append(repo_to_wsl(workspace_binary))
    candidates.append(str(workspace_binary))
    local_doc = data_paths_local or workspace_root / "docs" / "codex_context" / "DATA_PATHS.local.md"
    if local_doc.exists():
        text = local_doc.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"<WSL_ALGO_REPO>\s*\n([^\n`]+)", text)
        if match:
            wsl_repo = match.group(1).strip().rstrip("/")
            if wsl_repo.startswith("/"):
                candidates.append(f"{wsl_repo}/build/cpp/legsa_v23_port_core_demo")
            else:
                candidates.append(str(Path(wsl_repo) / "build" / "cpp" / "legsa_v23_port_core_demo"))

    probe_rows = []
    selected = None
    in_wsl = running_inside_wsl()
    for item in dict.fromkeys(candidates):
        if item.startswith("/"):
            probe_cmd = f"test -x {shlex.quote(item)}"
            if in_wsl:
                check = subprocess.run(["bash", "-lc", probe_cmd], check=False)
            else:
                check = subprocess.run(["wsl", "bash", "-lc", probe_cmd], check=False)
            exists = check.returncode == 0
        else:
            exists = Path(item).exists()
        probe_rows.append({"path": item, "exists": exists})
        if exists and selected is None:
            selected = item
    return {
        "runner_id": "legsa_v23_port_core_demo",
        "selected_path": selected,
        "exists": selected is not None,
        "candidate_paths": probe_rows,
        "supports_config_output_dir": selected is not None,
        "formal_runner_surface": "legsa_v23_port_core_demo --config <path> --output-dir <dir>",
    }


def validate_algorithm_inputs(workspace_root: Path, algorithm: str, base_values: dict[str, str]) -> list[str]:
    spec = ALGORITHM_SPECS[algorithm]
    missing: list[str] = []
    if not base_values.get("imupath"):
        missing.append("imupath from locked clean replay config")
    if not base_values.get("gnsspath"):
        missing.append("gnsspath from locked clean replay config")
    if spec.component_flags["raw_doppler"] and not (workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["raw_doppler"]).exists():
        missing.append(str(REPO_RELATIVE_REQUIRED_INPUTS["raw_doppler"]))
    if spec.component_flags["go2_joint"]:
        for key in ["go2_attitude", "go2_horizontal_velocity", "go2_joint"]:
            if not (workspace_root / REPO_RELATIVE_REQUIRED_INPUTS[key]).exists():
                missing.append(str(REPO_RELATIVE_REQUIRED_INPUTS[key]))
    if spec.component_flags["feedback"] and not (workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["selected_feedback"]).exists():
        missing.append(str(REPO_RELATIVE_REQUIRED_INPUTS["selected_feedback"]))
    return missing


def _base_config_lines(base_values: dict[str, str], output_dir_wsl: str) -> list[str]:
    def value(key: str, fallback: str) -> str:
        return base_values.get(key, fallback)

    return [
        "run_label: N4H4R3_clean_replay",
        f'imupath: "{value("imupath", "")}"',
        f'gnsspath: "{value("gnsspath", "")}"',
        f'outputpath: "{output_dir_wsl}"',
        "clean_input_provenance_label: clean_status_yaw_no_synthetic_noise",
        "config_policy_evidence_status: n9b1f_locked_normal_runtime_config",
        "imudatalen: 7",
        "imudatarate: 500",
        "starttime: 66.0",
        "endtime: 340.0",
        f"initpos: {value('initpos', '[ 39.98482973, 116.34312609, 41.80208107 ]')}",
        f"initvel: {value('initvel', '[ 0.0, 0.0, 0.0 ]')}",
        f"initatt: {value('initatt', '[ 0.0, 0.0, 0.688505 ]')}",
        f"initgyrbias: {value('initgyrbias', '[ 0.0, 0.0, 0.0 ]')}",
        f"initaccbias: {value('initaccbias', '[ 0.0, 0.0, 0.0 ]')}",
        f"initgyrscale: {value('initgyrscale', '[ 0.0, 0.0, 0.0 ]')}",
        f"initaccscale: {value('initaccscale', '[ 0.0, 0.0, 0.0 ]')}",
        f"initposstd: {value('initposstd', '[ 10.0, 10.0, 10.0 ]')}",
        f"initvelstd: {value('initvelstd', '[ 1.0, 1.0, 1.0 ]')}",
        f"initattstd: {value('initattstd', '[ 2.0, 2.0, 2.0 ]')}",
        f"arw: {value('arw', '[0.985, 0.985, 0.985]')}",
        f"vrw: {value('vrw', '[0.077, 0.077, 0.077]')}",
        f"gbstd: {value('gbstd', '[9.38, 9.38, 9.38]')}",
        f"abstd: {value('abstd', '[77.8, 77.8, 77.8]')}",
        f"gsstd: {value('gsstd', '[0.0, 0.0, 0.0]')}",
        f"asstd: {value('asstd', '[0.0, 0.0, 0.0]')}",
        "corrtime: 1.0",
        f"antlever: {value('antlever', '[ 0.0, 0.0, -0.25 ]')}",
        "initbgstd: [9.38, 9.38, 9.38]",
        "initbastd: [77.8, 77.8, 77.8]",
        "initsgstd: [0.0, 0.0, 0.0]",
        "initsastd: [0.0, 0.0, 0.0]",
    ]


def build_algorithm_config_text(workspace_root: Path, algorithm: str, output_dir: Path, base_values: dict[str, str]) -> str:
    spec = ALGORITHM_SPECS[algorithm]
    output_dir_wsl = repo_to_wsl(output_dir)
    raw_path = repo_to_wsl(workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["raw_doppler"])
    go2_attitude = repo_to_wsl(workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["go2_attitude"])
    go2_velocity = repo_to_wsl(workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["go2_horizontal_velocity"])
    go2_joint = repo_to_wsl(workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["go2_joint"])
    feedback = repo_to_wsl(workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["selected_feedback"])

    lines = _base_config_lines(base_values, output_dir_wsl)
    lines.extend(
        [
            "",
            "# N9B1F runtime-only formal LegSA runner config.",
            f"ablation_variant: {spec.ablation_variant}",
            "enable_receiver_velocity_update: true",
            "receiver_velocity_stress_mode: none",
            "receiver_velocity_std_scale: 1.0",
            "receiver_velocity_outage_start_sec: 0.0",
            "receiver_velocity_outage_duration_sec: 0.0",
            "receiver_velocity_additive_noise_std_mps: 0.0",
            "receiver_velocity_additive_noise_seed: 20260510",
            f"enable_raw_doppler: {str(spec.component_flags['raw_doppler']).lower()}",
            f'raw_doppler_factor_path: "{raw_path if spec.component_flags["raw_doppler"] else ""}"',
            "raw_doppler_factor_source: RTKLIB_DOPPLER_PROVIDER",
            "raw_doppler_time_tolerance_sec: 0.08",
            "raw_doppler_min_sat: 5",
            "raw_doppler_residual_gate_mps: 3.0",
            "raw_doppler_R_scale: 1.0",
            "raw_doppler_mode: doppler_ls_velocity",
            f"enable_source_aware_weighting: {str(spec.component_flags['source_aware']).lower()}",
            "source_aware_policy_version: n6b_conservative_innovation_covariance",
            "source_aware_mode: lsim_oim",
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
            f"source_aware_trace_enabled: {str(spec.component_flags['source_aware']).lower()}",
            "source_aware_enable_rolling_innovation_baseline: true",
            "source_aware_rolling_window_size: 31",
            "source_aware_rolling_mad_floor: 0.5",
            f"source_aware_go2_attitude_roll_pitch_enabled: {str(spec.component_flags['go2_joint']).lower()}",
            f"source_aware_go2_attitude_roll_pitch_lsim_enabled: {str(spec.component_flags['go2_joint']).lower()}",
            f"source_aware_go2_attitude_roll_pitch_oim_enabled: {str(spec.component_flags['go2_joint']).lower()}",
            f"source_aware_go2_horizontal_velocity_enabled: {str(spec.component_flags['go2_joint']).lower()}",
            f"source_aware_go2_horizontal_velocity_lsim_enabled: {str(spec.component_flags['go2_joint']).lower()}",
            f"source_aware_go2_horizontal_velocity_oim_enabled: {str(spec.component_flags['go2_joint']).lower()}",
            f"enable_go2_attitude_weak_prior: {str(spec.component_flags['go2_joint']).lower()}",
            f'go2_attitude_prior_path: "{go2_attitude if spec.component_flags["go2_joint"] else ""}"',
            "go2_attitude_prior_time_tolerance_sec: 0.02",
            "go2_attitude_prior_std_roll_deg: 1.6",
            "go2_attitude_prior_std_pitch_deg: 1.6",
            "go2_attitude_prior_sourceaware: true",
            "go2_attitude_prior_diagnostic_only: false",
            f"enable_go2_horizontal_velocity_prior: {str(spec.component_flags['go2_joint']).lower()}",
            f'go2_horizontal_velocity_prior_path: "{go2_velocity if spec.component_flags["go2_joint"] else ""}"',
            "go2_horizontal_velocity_prior_std_scale: 1.0",
            "go2_horizontal_velocity_prior_vertical_disabled: true",
            "go2_horizontal_velocity_prior_source_aware_enabled: true",
            "go2_horizontal_velocity_prior_mode: horizontal_2d",
            "go2_horizontal_velocity_strength_policy: n7c6_hv1",
            f"enable_go2_proprioceptive_joint_factor: {str(spec.component_flags['go2_joint']).lower()}",
            f'go2_proprioceptive_joint_factor_path: "{go2_joint if spec.component_flags["go2_joint"] else ""}"',
            "go2_proprioceptive_joint_factor_mode: sequential_equivalent",
            "go2_proprioceptive_joint_factor_policy: joint_rp1p6deg_hv1p0",
            "go2_proprioceptive_source_aware_enabled: true",
            "enable_go2_velocity_prior_diagnostic: false",
            'go2_velocity_prior_diagnostic_path: ""',
            "go2_position_prior_enabled: false",
            "go2_velocity_prior_enabled: false",
            "go2_yaw_prior_enabled: false",
            "go2_vertical_velocity_prior_enabled: false",
            "enable_go2_yaw_rate_prior_diagnostic: false",
            'go2_yaw_rate_prior_diagnostic_path: ""',
            f"enable_fgo_feedback: {str(spec.component_flags['feedback']).lower()}",
            f'fgo_feedback_path: "{feedback if spec.component_flags["feedback"] else ""}"',
            "fgo_feedback_mode: pseudo_measurement",
            "fgo_feedback_position_enabled: false",
            f"fgo_feedback_velocity_enabled: {str(spec.component_flags['feedback']).lower()}",
            f"fgo_feedback_attitude_enabled: {str(spec.component_flags['feedback']).lower()}",
            "fgo_feedback_covariance_scale: 1.0",
            "fgo_feedback_max_position_correction_m: 6.0",
            "fgo_feedback_max_velocity_correction_mps: 0.5",
            "fgo_feedback_max_attitude_correction_deg: 4.0",
            "fgo_feedback_min_interval_s: 0.5",
            "fgo_feedback_no_future_data_required: true",
            "diagnostic_only: false",
            "diagnostic_stress_only: false",
            "proposed_factor_claim: false",
            "paper_performance_claim: false",
            "no_outperform_final_v23_claim: true",
            "trace_solver_input: false",
            "final_v23_output_solver_input: false",
            "output_only_correction: false",
            "bad_epoch_deletion_for_metric: false",
            "fgo: false",
        ]
    )
    return "\n".join(lines) + "\n"


def write_algorithm_config(workspace_root: Path, algorithm: str, config_path: Path, output_dir: Path) -> dict[str, Any]:
    base_values, base_path = load_base_config_values(workspace_root)
    missing = validate_algorithm_inputs(workspace_root, algorithm, base_values)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(build_algorithm_config_text(workspace_root, algorithm, output_dir, base_values), encoding="utf-8")
    return {
        "algorithm": algorithm,
        "config_path": str(config_path),
        "config_path_wsl": repo_to_wsl(config_path),
        "base_config_path": str(base_path) if base_path else None,
        "missing_inputs": missing,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }


def append_case_level_overrides(config_path: Path, overrides: dict[str, str | None]) -> None:
    """Append explicit case-level input overrides to a generated runtime config."""
    clean = {key: value for key, value in overrides.items() if value not in {None, ""}}
    if not clean:
        return
    lines = ["", "# Case-level N9B input overrides."]
    for key, value in sorted(clean.items()):
        lines.append(f'{key}: "{str(value)}"')
    with config_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def build_solver_command_record(
    algorithm: str,
    runtime_config: str | Path,
    output_dir: str | Path,
    *,
    workspace_root: Path,
    port_core_exe: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    probe = resolve_port_core_executable(workspace_root)
    exe = port_core_exe or probe.get("selected_path") or "legsa_v23_port_core_demo"
    command = [exe, "--config", repo_to_wsl(runtime_config), "--output-dir", repo_to_wsl(output_dir)]
    return {
        "algorithm": algorithm,
        "command": command,
        "runner_surface": "legsa_v23_port_core_demo --config <runtime_config> --output-dir <output_dir>",
        "runtime_config": str(runtime_config),
        "runtime_config_wsl": repo_to_wsl(runtime_config),
        "output_dir": str(output_dir),
        "output_dir_wsl": repo_to_wsl(output_dir),
        "runner_probe": probe,
        "dry_run": dry_run,
        "executed_solver": False if dry_run else None,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "normal_parity_mode": False,
        "future_solver_entry": False,
    }


def run_formal_algorithm(
    workspace_root: Path,
    algorithm: str,
    output_dir: Path,
    *,
    port_core_exe: str | None = None,
    dry_run: bool = False,
    runtime_config: Path | None = None,
    case_overrides: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    if algorithm not in ALGORITHM_SPECS:
        raise ValueError(f"unsupported algorithm: {algorithm}")
    output_dir.mkdir(parents=True, exist_ok=True)
    if runtime_config:
        runtime_config = Path(runtime_config)
        clean_overrides = {key: value for key, value in (case_overrides or {}).items() if value not in {None, ""}}
        core_overrides = {
            "imupath": clean_overrides.get("imu_source_override"),
            "gnsspath": clean_overrides.get("gnss_input_override"),
            "outputpath": repo_to_wsl(output_dir),
            "fgo_feedback_path": clean_overrides.get("feedback_input_override"),
        }
        clean_core_overrides = {key: value for key, value in core_overrides.items() if value not in {None, ""}}
        effective_config = output_dir / "config" / "runtime_config.yaml"
        effective_config.parent.mkdir(parents=True, exist_ok=True)
        if runtime_config.exists():
            effective_config.write_text(runtime_config.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        else:
            effective_config.write_text("", encoding="utf-8")
        append_case_level_overrides(effective_config, clean_core_overrides)
        append_case_level_overrides(effective_config, clean_overrides)
        config_info = {
            "algorithm": algorithm,
            "config_path": str(effective_config),
            "config_path_wsl": repo_to_wsl(effective_config),
            "base_config_path": str(runtime_config),
            "missing_inputs": [],
            "case_overrides": clean_overrides,
            "core_config_overrides": clean_core_overrides,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "case_level_runtime_config": True,
            "source_runtime_config_copied": True,
        }
    else:
        config_info = write_algorithm_config(workspace_root, algorithm, output_dir / "config" / "runtime_config.yaml", output_dir)
        append_case_level_overrides(Path(config_info["config_path"]), case_overrides or {})
    probe = resolve_port_core_executable(workspace_root)
    exe = port_core_exe or probe.get("selected_path")
    if not exe:
        return {
            "algorithm": algorithm,
            "run_status": "blocked",
            "blocked_reason": "legsa_v23_port_core_demo executable missing",
            "config": config_info,
            "runner_probe": probe,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
        }
    command_record = build_solver_command_record(
        algorithm,
        config_info["config_path"],
        output_dir,
        workspace_root=workspace_root,
        port_core_exe=exe,
        dry_run=dry_run,
    )
    if case_overrides:
        command_record["case_overrides"] = {key: value for key, value in case_overrides.items() if value not in {None, ""}}
    command = command_record["command"]
    write_json(output_dir / "solver_command.json", command_record)
    write_json(
        output_dir / "source_role.json",
        {
            "algorithm": algorithm,
            "trace_role": "evaluation_only_not_solver_input",
            "final_v23_role": "reference_only_not_solver_input",
            "runner": "legsa_v23_port_core_demo",
        },
    )
    write_json(
        output_dir / "output_lineage.json",
        {
            "algorithm": algorithm,
            "runner": "legsa_v23_port_core_demo",
            "config_path": str(config_info["config_path"]),
            "output_dir": str(output_dir),
            "diagnostic_generic_filter_core": False,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "output_only_correction": False,
        },
    )
    if config_info["missing_inputs"]:
        return {
            "algorithm": algorithm,
            "run_status": "blocked",
            "blocked_reason": "missing locked normal inputs",
            "missing_inputs": config_info["missing_inputs"],
            "config": config_info,
            "runner_probe": probe,
            "command": command_record,
        }
    if dry_run:
        return {
            "algorithm": algorithm,
            "run_status": "dry_run",
            "returncode": None,
            "config": config_info,
            "runner_probe": probe,
            "command": command_record,
        }
    shell_argv = ["bash", "-lc", shlex.join(command)] if running_inside_wsl() else ["wsl", "bash", "-lc", shlex.join(command)]
    completed = subprocess.run(
        shell_argv,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    (output_dir / "logs").mkdir(exist_ok=True)
    (output_dir / "logs" / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "logs" / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    manifest = read_json(output_dir / "RUN_MANIFEST.json", {})
    return {
        "algorithm": algorithm,
        "run_status": "completed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "config": config_info,
        "runner_probe": probe,
        "command": command_record,
        "manifest": manifest,
        "outputs": {
            name: str(output_dir / name)
            for name in ["LegSA_PORT_NAV.nav", "LegSA_PORT_STD.csv", "EVAL_NAV.csv", "RUN_MANIFEST.json"]
            if (output_dir / name).exists()
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--algorithm", choices=FORMAL_ALGORITHMS, required=True)
    parser.add_argument("--case-id", default="normal_condition")
    parser.add_argument("--imu-source", default=None)
    parser.add_argument("--gnss-input", default=None)
    parser.add_argument("--receiver-input", default=None)
    parser.add_argument("--velocity-input", default=None)
    parser.add_argument("--yaw-input", default=None)
    parser.add_argument("--raw-doppler-input", default=None)
    parser.add_argument("--go2-input", default=None)
    parser.add_argument("--feedback-input", default=None)
    parser.add_argument("--source-aware-input", default=None)
    parser.add_argument("--config-json", "--runtime-config", default=None)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-epochs", default=None)
    parser.add_argument("--normal-parity-mode", action="store_true")
    parser.add_argument("--workspace-root", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace_root = Path(args.workspace_root).resolve() if args.workspace_root else Path.cwd().resolve()
    result = run_formal_algorithm(
        workspace_root,
        args.algorithm,
        Path(args.output_dir),
        dry_run=args.dry_run,
        runtime_config=Path(args.config_json) if args.config_json else None,
        case_overrides={
            "case_id": args.case_id,
            "imu_source_override": args.imu_source,
            "gnss_input_override": args.gnss_input,
            "receiver_input_override": args.receiver_input,
            "velocity_input_override": args.velocity_input,
            "yaw_input_override": args.yaw_input,
            "raw_doppler_input_override": args.raw_doppler_input,
            "go2_input_override": args.go2_input,
            "feedback_input_override": args.feedback_input,
            "source_aware_input_override": args.source_aware_input,
            "max_epochs": args.max_epochs,
        },
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result.get("run_status") in {"completed", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
