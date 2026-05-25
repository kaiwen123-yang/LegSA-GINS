"""N9C0C LegSA full algorithm materialization and minimum rerun.

This stage is intentionally runner/config/reporting glue. It composes the
existing port-core runtime switches for Raw Doppler, source-aware weighting,
Go2 proprioceptive observations, and selected same-case feedback without
changing EKF/FGO math.
"""

from __future__ import annotations

import csv
import json
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from legsa_gins.reporting.by2_algorithm_runner import (
    ALGORITHM_SPECS,
    FORMAL_ALGORITHMS,
    repo_to_wsl,
    resolve_port_core_executable,
    write_json,
)
from legsa_gins.reporting.by2_n9b1c2_selected_feedback_same_case_mapping import (
    generate_same_case_feedback_observations,
)
from legsa_gins.reporting.by2_n9b1f_real_legsa_algorithm_runner import (
    _convert_eval_nav,
    _convert_std,
    _metrics_from_summary,
)


STAGE = "N9C0C_LEGSA_FULL_ALGORITHM_MATERIALIZATION_AND_MINIMUM_RERUN"
FULL_RUNTIME_NAME = "LEGSA_FULL_ALGORITHM_MINIMUM_RERUN"
ALGORITHM_ID = "LegSA_full_EKF"
DISPLAY_NAME = "LegSA full EKF"
CLASSIFICATION = "LegSA_full_EKF_with_available_feedback_FGO"
NORMAL_CASE_ID = "FULL_normal_repeat"
EXPECTED_MINIMUM_CASE_COUNT = 17


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    batch: str
    source_config: Path
    feedback_observations: Path
    eval_command_template: Path
    stage_group: str
    baseline_eval_nav: Path | None = None
    clean_gnss_wsl: str | None = None

    @property
    def safe_id(self) -> str:
        return self.case_id.replace("/", "__")


def default_stage_root(workspace_root: Path) -> Path:
    return workspace_root / "by2-huitu" / STAGE


def default_full_runtime_root(workspace_root: Path) -> Path:
    return workspace_root / "by2-huitu" / "N9B2_FULL_MATRIX" / FULL_RUNTIME_NAME


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in keys})


def _write_table_pair(path_stem: Path, rows: list[dict[str, Any]]) -> None:
    write_json(path_stem.with_suffix(".json"), rows)
    _write_csv(path_stem.with_suffix(".csv"), rows)


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _write_summary(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def _prepare_roots(stage_root: Path, full_root: Path) -> None:
    for root in [
        stage_root / "00_supervisor",
        stage_root / "01_plan",
        stage_root / "feasibility_audit",
        stage_root / "runner_mapping",
        stage_root / "runtime_configs",
        stage_root / "normal_smoke",
        stage_root / "minimum_cases",
        stage_root / "official_eval",
        stage_root / "selected_feedback",
        stage_root / "reports",
        stage_root / "matrix",
        stage_root / "summary",
        stage_root / "validation",
        stage_root / "logs",
        full_root / "runtime_configs",
        full_root / "normal_smoke",
        full_root / "minimum_cases",
        full_root / "official_eval",
        full_root / "selected_feedback",
        full_root / "logs",
    ]:
        root.mkdir(parents=True, exist_ok=True)


def _case_specs(workspace_root: Path, full_root: Path) -> list[CaseSpec]:
    matrix = workspace_root / "by2-huitu" / "N9B2_FULL_MATRIX"
    batch0 = matrix / "BATCH0_SMOKE"
    cases = [
        CaseSpec(
            case_id=NORMAL_CASE_ID,
            batch="BATCH0_SMOKE",
            source_config=batch0 / "runtime_configs" / "B0_normal_repeat_formal" / "Go2_joint_EKF.runtime_config.yaml",
            feedback_observations=full_root / "selected_feedback" / NORMAL_CASE_ID / "FGO_FEEDBACK_OBSERVATIONS.csv",
            eval_command_template=batch0
            / "official_eval"
            / "B0_normal_repeat_formal"
            / "Go2_joint_EKF"
            / "command.json",
            baseline_eval_nav=batch0
            / "solver_outputs"
            / "B0_normal_repeat_formal"
            / "baseline_no_feedback_EKF"
            / "EVAL_NAV.csv",
            stage_group="normal_smoke",
        )
    ]
    for case_id in [
        "A_outage_20s",
        "B_gnss_downsample_every10",
        "E_position_std_inflation_x10",
        "E_yaw_std_inflation_x10",
    ]:
        base = matrix / "BATCH1_DETERMINISTIC"
        cases.append(
            CaseSpec(
                case_id=case_id,
                batch="BATCH1_DETERMINISTIC",
                source_config=base / "runtime_configs" / case_id / "Go2_joint_EKF.runtime_config.yaml",
                feedback_observations=base
                / "selected_feedback_dependencies"
                / case_id
                / "same_case_feedback_plan"
                / "FGO_FEEDBACK_OBSERVATIONS.csv",
                eval_command_template=base / "official_eval" / case_id / "selected_feedback_EKF" / "command.json",
                stage_group="minimum_cases",
            )
        )
    for batch_name, case_name in [
        ("BATCH2_POSITION_NOISE", "C_position_noise_medium"),
        ("BATCH3_POSITION_SPIKE", "D_position_spike_medium"),
        ("BATCH4_YAW_NOISE", "H_dual_yaw_noise_medium"),
    ]:
        base = matrix / batch_name
        for seed in range(3):
            seed_id = f"seed_{seed}"
            cases.append(
                CaseSpec(
                    case_id=f"{case_name}/{seed_id}",
                    batch=batch_name,
                    source_config=base / "runtime_configs" / case_name / seed_id / "Go2_joint_EKF.runtime_config.yaml",
                    feedback_observations=base
                    / "selected_feedback_dependencies"
                    / case_name
                    / seed_id
                    / "same_case_feedback_plan"
                    / "FGO_FEEDBACK_OBSERVATIONS.csv",
                    eval_command_template=base / "official_eval" / case_name / seed_id / "selected_feedback_EKF" / "command.json",
                    stage_group="minimum_cases",
                )
            )
    batch6 = matrix / "BATCH6_MIXED"
    for case_name, seed_id in [
        ("M_mixed_A", "seed_0"),
        ("M_mixed_C", "seed_0"),
        ("M_mixed_D", "seed_0"),
        ("M_mixed_F", "seedless"),
    ]:
        cases.append(
            CaseSpec(
                case_id=f"{case_name}/{seed_id}",
                batch="BATCH6_MIXED",
                source_config=batch6 / case_name / seed_id / "runtime_configs" / "Go2_joint_EKF.runtime_config.yaml",
                feedback_observations=batch6
                / case_name
                / seed_id
                / "selected_feedback_dependencies"
                / "same_case_feedback"
                / "FGO_FEEDBACK_OBSERVATIONS.csv",
                eval_command_template=batch6 / case_name / seed_id / "official_eval" / "selected_feedback_EKF" / "command.json",
                stage_group="minimum_cases",
            )
        )
    return cases


def _parse_config_values(config_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not config_path.exists():
        return values
    pattern = re.compile(r"^([A-Za-z0-9_]+):\s*(.*)$")
    for raw_line in config_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        match = pattern.match(line)
        if not match:
            continue
        value = match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        values[match.group(1)] = value
    return values


def _flag(values: dict[str, str], key: str) -> bool:
    return str(values.get(key, "")).lower() == "true"


def _materialize_config(case: CaseSpec, config_path: Path, output_dir: Path) -> dict[str, Any]:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    source_text = case.source_config.read_text(encoding="utf-8", errors="ignore") if case.source_config.exists() else ""
    feedback_wsl = repo_to_wsl(case.feedback_observations)
    output_wsl = repo_to_wsl(output_dir)
    overrides = [
        "",
        "# N9C0C LegSA_full_EKF materialization overrides.",
        f"case_id: \"{case.case_id}\"",
        f"ablation_variant: {ALGORITHM_SPECS[ALGORITHM_ID].ablation_variant}",
        f"outputpath: \"{output_wsl}\"",
        "enable_raw_doppler: true",
        "enable_source_aware_weighting: true",
        "source_aware_trace_enabled: true",
        "source_aware_go2_attitude_roll_pitch_enabled: true",
        "source_aware_go2_attitude_roll_pitch_lsim_enabled: true",
        "source_aware_go2_attitude_roll_pitch_oim_enabled: true",
        "source_aware_go2_horizontal_velocity_enabled: true",
        "source_aware_go2_horizontal_velocity_lsim_enabled: true",
        "source_aware_go2_horizontal_velocity_oim_enabled: true",
        "enable_go2_attitude_weak_prior: true",
        "enable_go2_horizontal_velocity_prior: true",
        "enable_go2_proprioceptive_joint_factor: true",
        "enable_fgo_feedback: true",
        f"fgo_feedback_path: \"{feedback_wsl}\"",
        "fgo_feedback_mode: pseudo_measurement",
        "fgo_feedback_position_enabled: false",
        "fgo_feedback_velocity_enabled: true",
        "fgo_feedback_attitude_enabled: true",
        "fgo_feedback_no_future_data_required: true",
        "same_case_feedback_required: true",
        "clean_feedback_for_degraded_case: false",
        f"degradation_execution: {str(case.stage_group == 'minimum_cases').lower()}",
        "full_matrix_execution: false",
        "paper_performance_claim: false",
        "no_outperform_final_v23_claim: true",
        "trace_solver_input: false",
        "final_v23_output_solver_input: false",
        "final_v23_solver_input: false",
        "output_only_correction: false",
        "bad_epoch_deletion_for_metric: false",
    ]
    config_path.write_text(source_text.rstrip() + "\n" + "\n".join(overrides) + "\n", encoding="utf-8")
    values = _parse_config_values(config_path)
    flags = _config_flag_row(case, config_path, values)
    return flags


def _config_flag_row(case: CaseSpec, config_path: Path, values: dict[str, str]) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "stage_group": case.stage_group,
        "runtime_config": str(config_path),
        "source_config": str(case.source_config),
        "source_config_exists": case.source_config.exists(),
        "same_case_feedback": True,
        "same_case_feedback_path": str(case.feedback_observations),
        "same_case_feedback_exists": case.feedback_observations.exists(),
        "raw_doppler_enabled": _flag(values, "enable_raw_doppler"),
        "source_aware_enabled": _flag(values, "enable_source_aware_weighting"),
        "go2_legged_aux_enabled": all(
            _flag(values, key)
            for key in [
                "enable_go2_attitude_weak_prior",
                "enable_go2_horizontal_velocity_prior",
                "enable_go2_proprioceptive_joint_factor",
            ]
        ),
        "selected_feedback_enabled": _flag(values, "enable_fgo_feedback"),
        "same_case_feedback_required": _flag(values, "same_case_feedback_required"),
        "sliding_window_fgo_or_feedback_enabled": _flag(values, "enable_fgo_feedback"),
        "trace_solver_input": _flag(values, "trace_solver_input"),
        "final_v23_solver_input": _flag(values, "final_v23_solver_input")
        or _flag(values, "final_v23_output_solver_input"),
        "output_substitution": _flag(values, "output_only_correction"),
    }


def _run_wsl_command(command: list[str], timeout: int = 900) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["wsl", "bash", "-lc", shlex.join(command)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _generate_normal_feedback(workspace_root: Path, case: CaseSpec) -> dict[str, Any]:
    if case.feedback_observations.exists():
        return {
            "case_id": case.case_id,
            "status": "existing",
            "output_observations": str(case.feedback_observations),
            "same_case_feedback": True,
        }
    clean_gnss_wsl = case.clean_gnss_wsl or _parse_config_values(case.source_config).get("gnsspath")
    if not case.baseline_eval_nav or not case.baseline_eval_nav.exists() or not clean_gnss_wsl:
        return {
            "case_id": case.case_id,
            "status": "blocked",
            "blocked_reason": "baseline EVAL_NAV or clean GNSS dependency missing",
            "same_case_feedback": True,
        }
    output_report = case.feedback_observations.parent / "OBSERVATION_BUILD_REPORT.json"
    try:
        if Path(clean_gnss_wsl).exists():
            report = generate_same_case_feedback_observations(
                case_id=case.case_id,
                baseline_eval_nav=case.baseline_eval_nav,
                gnss_path=Path(clean_gnss_wsl),
                output_observations=case.feedback_observations,
                output_report=output_report,
            )
            report["status"] = "generated"
            return report
    except OSError:
        pass
    code = (
        "from pathlib import Path;"
        "from legsa_gins.reporting.by2_n9b1c2_selected_feedback_same_case_mapping import "
        "generate_same_case_feedback_observations;"
        "generate_same_case_feedback_observations("
        f"case_id={case.case_id!r},"
        f"baseline_eval_nav=Path({repo_to_wsl(case.baseline_eval_nav)!r}),"
        f"gnss_path=Path({clean_gnss_wsl!r}),"
        f"output_observations=Path({repo_to_wsl(case.feedback_observations)!r}),"
        f"output_report=Path({repo_to_wsl(output_report)!r}))"
    )
    completed = _run_wsl_command(["bash", "-lc", f"cd {shlex.quote(repo_to_wsl(workspace_root))} && PYTHONPATH=src python3 -c {shlex.quote(code)}"])
    (case.feedback_observations.parent / "generation_stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (case.feedback_observations.parent / "generation_stderr.txt").write_text(completed.stderr, encoding="utf-8")
    report = _read_json(output_report, {}) or {}
    report.update(
        {
            "case_id": case.case_id,
            "status": "generated" if completed.returncode == 0 and case.feedback_observations.exists() else "failed",
            "returncode": completed.returncode,
            "same_case_feedback": True,
            "output_observations": str(case.feedback_observations),
            "trace_solver_input": False,
            "final_v23_solver_input": False,
        }
    )
    return report


def _run_solver(workspace_root: Path, case: CaseSpec, config_path: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    probe = resolve_port_core_executable(workspace_root)
    exe = probe.get("selected_path")
    command = [exe or "legsa_v23_port_core_demo", "--config", repo_to_wsl(config_path), "--output-dir", repo_to_wsl(output_dir)]
    command_record = {
        "algorithm": ALGORITHM_ID,
        "case_id": case.case_id,
        "command": command,
        "runtime_config": str(config_path),
        "runtime_config_wsl": repo_to_wsl(config_path),
        "output_dir": str(output_dir),
        "output_dir_wsl": repo_to_wsl(output_dir),
        "runner_probe": probe,
        "runner_surface": "legsa_v23_port_core_demo --config <runtime_config> --output-dir <output_dir>",
        "dry_run": False,
        "executed_solver": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "full_matrix_execution": False,
    }
    write_json(output_dir / "solver_command.json", command_record)
    write_json(
        output_dir / "source_role.json",
        {
            "algorithm": ALGORITHM_ID,
            "case_id": case.case_id,
            "trace_role": "evaluation_only_not_solver_input",
            "final_v23_role": "reference_only_not_solver_input",
            "same_case_feedback": True,
        },
    )
    write_json(
        output_dir / "output_lineage.json",
        {
            "algorithm": ALGORITHM_ID,
            "case_id": case.case_id,
            "classification": CLASSIFICATION,
            "runner": "legsa_v23_port_core_demo",
            "config_path": str(config_path),
            "feedback_observations": str(case.feedback_observations),
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "output_only_correction": False,
            "paper_performance_claim": False,
        },
    )
    if not exe:
        return {
            "case_id": case.case_id,
            "algorithm": ALGORITHM_ID,
            "run_status": "blocked",
            "blocked_reason": "legsa_v23_port_core_demo executable missing",
            "runner_probe": probe,
        }
    if not case.feedback_observations.exists():
        return {
            "case_id": case.case_id,
            "algorithm": ALGORITHM_ID,
            "run_status": "blocked",
            "blocked_reason": "same-case feedback observations missing",
            "runner_probe": probe,
        }
    completed = _run_wsl_command(command)
    (output_dir / "logs").mkdir(exist_ok=True)
    (output_dir / "logs" / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "logs" / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    write_json(output_dir / "exit_status.json", {"returncode": completed.returncode})
    manifest = _read_json(output_dir / "RUN_MANIFEST.json", {}) or {}
    return {
        "case_id": case.case_id,
        "algorithm": ALGORITHM_ID,
        "run_status": "completed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "runner_probe": probe,
        "manifest": manifest,
        "command": command_record,
        "outputs": {
            name: str(output_dir / name)
            for name in ["LegSA_PORT_NAV.nav", "LegSA_PORT_STD.csv", "EVAL_NAV.csv", "RUN_MANIFEST.json"]
            if (output_dir / name).exists()
        },
    }


def _run_official_eval(case: CaseSpec, solver_output_dir: Path, official_dir: Path) -> dict[str, Any]:
    official_dir.mkdir(parents=True, exist_ok=True)
    template = _read_json(case.eval_command_template, {}) or {}
    command_template = template.get("command", [])
    if len(command_template) < 2:
        return {"case_id": case.case_id, "algorithm": ALGORITHM_ID, "official_eval_status": "blocked", "blocked_reason": "template command missing"}
    if not (solver_output_dir / "EVAL_NAV.csv").exists() or not (solver_output_dir / "LegSA_PORT_STD.csv").exists():
        return {"case_id": case.case_id, "algorithm": ALGORITHM_ID, "official_eval_status": "blocked", "blocked_reason": "NAV/STD output missing"}
    try:
        trace_path = command_template[command_template.index("--trace") + 1]
    except (ValueError, IndexError):
        return {"case_id": case.case_id, "algorithm": ALGORITHM_ID, "official_eval_status": "blocked", "blocked_reason": "trace path missing in template"}
    eval_script = command_template[1]
    nav_dst = official_dir / "converted_eval_nav_official.nav"
    std_dst = official_dir / "converted_std_official.txt"
    nav_meta = _convert_eval_nav(solver_output_dir / "EVAL_NAV.csv", nav_dst)
    std_meta = _convert_std(solver_output_dir / "LegSA_PORT_STD.csv", solver_output_dir / "EVAL_NAV.csv", std_dst)
    command = [
        "python3",
        eval_script,
        "--trace",
        trace_path,
        "--nav",
        repo_to_wsl(nav_dst),
        "--std",
        repo_to_wsl(std_dst),
        "--outdir",
        repo_to_wsl(official_dir),
        "--base_time",
        "1772784000.0",
        "--yaw_truth_mode",
        "enu",
    ]
    write_json(
        official_dir / "command.json",
        {
            "case_id": case.case_id,
            "algorithm": ALGORITHM_ID,
            "command": command,
            "trace_is_evaluation_only": True,
            "final_v23_reference_only": False,
        },
    )
    write_json(
        official_dir / "role.json",
        {
            "case_id": case.case_id,
            "algorithm": ALGORITHM_ID,
            "trace_role": "evaluation_only",
            "solver_input_trace": False,
            "solver_input_final_v23": False,
        },
    )
    completed = _run_wsl_command(command)
    (official_dir / "run_stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (official_dir / "run_stderr.txt").write_text(completed.stderr, encoding="utf-8")
    summary = _read_json(official_dir / "summary.json", {}) or {}
    metrics = _metrics_from_summary(summary)
    return {
        "case_id": case.case_id,
        "algorithm": ALGORITHM_ID,
        "official_eval_status": "completed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "summary": summary,
        "metrics": metrics,
        "nav_conversion": nav_meta,
        "std_conversion": std_meta,
        "trace_is_evaluation_only": True,
    }


def _module_verification(case_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    raw_active = (
        manifest.get("enable_raw_doppler") is True
        and manifest.get("raw_doppler_solver_enabled") is True
        and manifest.get("raw_doppler_provider_status") == "available"
        and int(manifest.get("raw_doppler_update_count") or 0) > 0
    )
    source_active = manifest.get("source_aware_weighting_enabled") is True and int(manifest.get("source_aware_trace_rows") or 0) > 0
    go2_active = (
        manifest.get("go2_proprioceptive_joint_factor_enabled") is True
        and int(manifest.get("go2_proprioceptive_joint_factor_update_count") or 0) > 0
        and int(manifest.get("go2_attitude_weak_prior_update_count") or 0) > 0
        and int(manifest.get("go2_horizontal_velocity_prior_update_count") or 0) > 0
    )
    feedback_active = (
        manifest.get("fgo_feedback_enabled") is True
        and manifest.get("fgo_feedback_provider_status") == "available"
        and int(manifest.get("feedback_update_count") or 0) > 0
        and manifest.get("fgo_feedback_no_future_data") is True
        and manifest.get("fgo_feedback_output_substitution") is False
        and manifest.get("fgo_feedback_direct_nav_override") is False
    )
    return {
        "case_id": case_id,
        "raw_doppler_active": raw_active,
        "raw_doppler_provider_status": manifest.get("raw_doppler_provider_status"),
        "raw_doppler_update_count": manifest.get("raw_doppler_update_count"),
        "source_aware_active": source_active,
        "source_aware_trace_rows": manifest.get("source_aware_trace_rows"),
        "go2_legged_aux_active": go2_active,
        "go2_joint_update_count": manifest.get("go2_proprioceptive_joint_factor_update_count"),
        "go2_attitude_update_count": manifest.get("go2_attitude_weak_prior_update_count"),
        "go2_horizontal_velocity_update_count": manifest.get("go2_horizontal_velocity_prior_update_count"),
        "selected_feedback_active": feedback_active,
        "fgo_feedback_provider_status": manifest.get("fgo_feedback_provider_status"),
        "feedback_update_count": manifest.get("feedback_update_count"),
        "feedback_accept_count": manifest.get("feedback_accept_count"),
        "feedback_reject_count": manifest.get("feedback_reject_count"),
        "trace_solver_input": manifest.get("trace_solver_input") is True,
        "final_v23_solver_input": manifest.get("final_v23_output_solver_input") is True,
        "output_substitution": manifest.get("output_only_correction") is True
        or manifest.get("fgo_feedback_output_substitution") is True,
        "direct_nav_override": manifest.get("fgo_feedback_direct_nav_override") is True,
        "complete_nine_factor_fgo_claim": False,
        "classification": CLASSIFICATION,
        "module_verification_passed": raw_active and source_active and go2_active and feedback_active,
    }


def _status_row(case: CaseSpec, solver: dict[str, Any], eval_result: dict[str, Any], verification: dict[str, Any]) -> dict[str, Any]:
    metrics = eval_result.get("metrics", {}) if isinstance(eval_result, dict) else {}
    sane = (
        solver.get("run_status") == "completed"
        and eval_result.get("official_eval_status") == "completed"
        and verification.get("module_verification_passed") is True
        and metrics.get("horizontal_rmse_m") is not None
        and metrics.get("yaw_rmse_deg") is not None
        and float(metrics["horizontal_rmse_m"]) < 20.0
        and float(metrics["yaw_rmse_deg"]) < 30.0
    )
    return {
        "case_id": case.case_id,
        "batch": case.batch,
        "stage_group": case.stage_group,
        "algorithm": ALGORITHM_ID,
        "solver_status": solver.get("run_status"),
        "solver_returncode": solver.get("returncode"),
        "official_eval_status": eval_result.get("official_eval_status"),
        "official_eval_returncode": eval_result.get("returncode"),
        "module_verification_passed": verification.get("module_verification_passed"),
        "same_order_sanity": sane,
        "trace_solver_input": verification.get("trace_solver_input"),
        "final_v23_solver_input": verification.get("final_v23_solver_input"),
        "output_substitution": verification.get("output_substitution"),
        "horizontal_rmse_m": metrics.get("horizontal_rmse_m"),
        "up_rmse_m": metrics.get("up_rmse_m"),
        "yaw_rmse_deg": metrics.get("yaw_rmse_deg"),
        "row_count": metrics.get("row_count"),
        "blocked_reason": solver.get("blocked_reason") or eval_result.get("blocked_reason") or "",
    }


def run_n9c0c(
    workspace_root: Path,
    *,
    stage_root: Path | None = None,
    full_root: Path | None = None,
    execute: bool = True,
    run_official_eval: bool = True,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    stage_root = stage_root or default_stage_root(workspace_root)
    full_root = full_root or default_full_runtime_root(workspace_root)
    _prepare_roots(stage_root, full_root)
    cases = _case_specs(workspace_root, full_root)
    normal_case = cases[0]
    minimum_cases = cases[1:]
    runner_probe = resolve_port_core_executable(workspace_root)
    spec = ALGORITHM_SPECS.get(ALGORITHM_ID)
    feasible = spec is not None and ALGORITHM_ID in FORMAL_ALGORITHMS and bool(runner_probe.get("exists"))
    feasibility_rows = [
        {
            "capability": "runner_algorithm_mapping",
            "required": True,
            "status": "pass" if spec is not None and ALGORITHM_ID in FORMAL_ALGORITHMS else "missing",
            "evidence": "by2_algorithm_runner FORMAL_ALGORITHMS and ALGORITHM_SPECS",
        },
        {
            "capability": "port_core_config_surface",
            "required": True,
            "status": "pass" if runner_probe.get("exists") else "blocked",
            "evidence": runner_probe.get("selected_path") or "legsa_v23_port_core_demo missing",
        },
        {
            "capability": "same_case_feedback_dependencies",
            "required": True,
            "status": "pass" if all(case.feedback_observations.exists() for case in minimum_cases) else "partial",
            "evidence": "existing N9B2 selected_feedback_dependencies for degraded minimum cases",
        },
        {
            "capability": "complete_nine_factor_fgo_claim",
            "required": False,
            "status": "not_claimed",
            "evidence": "N9C0B found incomplete current active nine-factor FGO row-level evidence",
        },
    ]
    feasibility_report = {
        "stage": STAGE,
        "generated_at": _now(),
        "classification": "feasible_with_runner_mapping_only" if feasible else "infeasible_current_code",
        "ready_for_materialization": feasible,
        "algorithm_math_change_required": False,
        "runner_probe": runner_probe,
        "checks": feasibility_rows,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "paper_performance_claim": False,
    }
    write_json(stage_root / "reports" / "N9C0C_FEASIBILITY_AUDIT_REPORT.json", feasibility_report)
    _write_table_pair(stage_root / "matrix" / "N9C0C_FULL_ALGORITHM_FEASIBILITY_MATRIX", feasibility_rows)
    _write_summary(
        stage_root / "summary" / "n9c0c_feasibility_audit.md",
        "N9C0C Feasibility Audit",
        [
            f"- Classification: {feasibility_report['classification']}",
            f"- Ready for materialization: {feasibility_report['ready_for_materialization']}",
            "- Algorithm math change required: False",
            "- Complete nine-factor FGO claim: not claimed",
        ],
    )
    spec_rows = [
        {
            "algorithm_id": ALGORITHM_ID,
            "display_name": DISPLAY_NAME,
            "original_components": "Raw_Doppler_EKF;source_aware_EKF;Go2_joint_EKF;selected_feedback_EKF",
            "raw_doppler_enabled": True,
            "source_aware_enabled": True,
            "go2_legged_aux_enabled": True,
            "selected_feedback_enabled": True,
            "same_case_feedback_required": True,
            "output_role": "final_algorithm_candidate",
            "classification": CLASSIFICATION,
            "complete_nine_factor_fgo_claim": False,
            "ready_for_paper_claims": False,
        }
    ]
    spec_report = {"stage": STAGE, "generated_at": _now(), "rows": spec_rows}
    write_json(stage_root / "reports" / "N9C0C_FULL_ALGORITHM_SPEC_REPORT.json", spec_report)
    _write_table_pair(stage_root / "matrix" / "N9C0C_FULL_ALGORITHM_SPEC", spec_rows)
    mapping_rows = [
        {
            "algorithm": "Go2_joint_EKF",
            "raw_doppler": True,
            "source_aware": True,
            "go2_joint": True,
            "feedback": False,
            "role": "existing cumulative branch without selected feedback",
        },
        {
            "algorithm": "selected_feedback_EKF",
            "raw_doppler": False,
            "source_aware": False,
            "go2_joint": False,
            "feedback": True,
            "role": "existing feedback branch only",
        },
        {
            "algorithm": ALGORITHM_ID,
            "raw_doppler": True,
            "source_aware": True,
            "go2_joint": True,
            "feedback": True,
            "role": "N9C0C final algorithm candidate mapping",
        },
    ]
    write_json(
        stage_root / "reports" / "N9C0C_RUNNER_MAPPING_REPORT.json",
        {
            "stage": STAGE,
            "generated_at": _now(),
            "algorithm": ALGORITHM_ID,
            "mapping_status": "mapped" if feasible else "blocked",
            "tracked_mapping_only": True,
            "algorithm_math_changed": False,
            "rows": mapping_rows,
        },
    )
    _write_table_pair(stage_root / "matrix" / "N9C0C_RUNNER_MAPPING_DIFF", mapping_rows)
    if not feasible:
        return _write_terminal_reports(stage_root, full_root, feasibility_report, spec_report, [], [], [], [], [])

    config_rows: list[dict[str, Any]] = []
    feedback_rows: list[dict[str, Any]] = []
    normal_status_rows: list[dict[str, Any]] = []
    normal_metric_rows: list[dict[str, Any]] = []
    minimum_status_rows: list[dict[str, Any]] = []
    minimum_metric_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    verification_rows: list[dict[str, Any]] = []

    feedback_rows.append(_generate_normal_feedback(workspace_root, normal_case))
    for case in cases:
        group_root = full_root / case.stage_group / case.safe_id / ALGORITHM_ID
        config_path = full_root / "runtime_configs" / case.safe_id / f"{ALGORITHM_ID}.runtime_config.yaml"
        config_rows.append(_materialize_config(case, config_path, group_root))
    write_json(
        stage_root / "reports" / "N9C0C_RUNTIME_CONFIG_MATERIALIZATION_REPORT.json",
        {"stage": STAGE, "generated_at": _now(), "rows": config_rows, "config_count": len(config_rows)},
    )
    _write_table_pair(stage_root / "matrix" / "N9C0C_RUNTIME_CONFIG_INDEX", config_rows)
    write_json(
        stage_root / "selected_feedback" / "N9C0C_SELECTED_FEEDBACK_DEPENDENCY_REPORT.json",
        {"stage": STAGE, "generated_at": _now(), "rows": feedback_rows},
    )
    if not execute:
        return _write_terminal_reports(stage_root, full_root, feasibility_report, spec_report, config_rows, [], [], [], [])

    normal_output = full_root / "normal_smoke" / normal_case.safe_id / ALGORITHM_ID
    normal_config = full_root / "runtime_configs" / normal_case.safe_id / f"{ALGORITHM_ID}.runtime_config.yaml"
    normal_solver = _run_solver(workspace_root, normal_case, normal_config, normal_output)
    normal_eval = (
        _run_official_eval(normal_case, normal_output, full_root / "official_eval" / normal_case.safe_id / ALGORITHM_ID)
        if run_official_eval and normal_solver.get("run_status") == "completed"
        else {"case_id": normal_case.case_id, "algorithm": ALGORITHM_ID, "official_eval_status": "skipped"}
    )
    normal_verification = _module_verification(normal_case.case_id, normal_solver.get("manifest", {}) or {})
    verification_rows.append(normal_verification)
    normal_status = _status_row(normal_case, normal_solver, normal_eval, normal_verification)
    normal_status_rows.append(normal_status)
    if normal_eval.get("metrics"):
        normal_metric_rows.append({"case_id": normal_case.case_id, "algorithm": ALGORITHM_ID, **normal_eval["metrics"]})
    write_json(
        stage_root / "reports" / "N9C0C_NORMAL_SMOKE_EXECUTION_REPORT.json",
        {"stage": STAGE, "generated_at": _now(), "solver": normal_solver, "official_eval": normal_eval, "verification": normal_verification},
    )
    _write_table_pair(stage_root / "matrix" / "N9C0C_NORMAL_SMOKE_STATUS", normal_status_rows)
    _write_table_pair(stage_root / "matrix" / "N9C0C_NORMAL_SMOKE_METRICS", normal_metric_rows)
    _write_summary(
        stage_root / "summary" / "n9c0c_normal_smoke_summary.md",
        "N9C0C Normal Smoke Summary",
        [
            f"- Solver status: {normal_status['solver_status']}",
            f"- Official eval status: {normal_status['official_eval_status']}",
            f"- Module verification passed: {normal_status['module_verification_passed']}",
            f"- Same-order sanity: {normal_status['same_order_sanity']}",
        ],
    )
    normal_passed = normal_status["same_order_sanity"] is True
    if normal_passed:
        for case in minimum_cases:
            output_dir = full_root / "minimum_cases" / case.safe_id / ALGORITHM_ID
            config_path = full_root / "runtime_configs" / case.safe_id / f"{ALGORITHM_ID}.runtime_config.yaml"
            solver = _run_solver(workspace_root, case, config_path, output_dir)
            eval_result = (
                _run_official_eval(case, output_dir, full_root / "official_eval" / case.safe_id / ALGORITHM_ID)
                if run_official_eval and solver.get("run_status") == "completed"
                else {"case_id": case.case_id, "algorithm": ALGORITHM_ID, "official_eval_status": "skipped"}
            )
            verification = _module_verification(case.case_id, solver.get("manifest", {}) or {})
            verification_rows.append(verification)
            status = _status_row(case, solver, eval_result, verification)
            minimum_status_rows.append(status)
            if eval_result.get("metrics"):
                minimum_metric_rows.append({"case_id": case.case_id, "algorithm": ALGORITHM_ID, **eval_result["metrics"]})
    else:
        for case in minimum_cases:
            minimum_status_rows.append(
                {
                    "case_id": case.case_id,
                    "batch": case.batch,
                    "stage_group": case.stage_group,
                    "algorithm": ALGORITHM_ID,
                    "solver_status": "skipped",
                    "official_eval_status": "skipped",
                    "module_verification_passed": False,
                    "same_order_sanity": False,
                    "blocked_reason": "normal smoke failed",
                }
            )
            minimum_metric_rows.append(
                {
                    "case_id": case.case_id,
                    "algorithm": ALGORITHM_ID,
                    "metrics_status": "skipped_normal_smoke_failed",
                }
            )
    write_json(
        stage_root / "reports" / "N9C0C_MINIMUM_RERUN_EXECUTION_REPORT.json",
        {
            "stage": STAGE,
            "generated_at": _now(),
            "normal_smoke_passed": normal_passed,
            "minimum_case_count": len(minimum_cases),
            "status_rows": minimum_status_rows,
            "full_matrix_execution": False,
        },
    )
    _write_table_pair(stage_root / "matrix" / "N9C0C_MINIMUM_RERUN_STATUS", minimum_status_rows)
    _write_table_pair(stage_root / "matrix" / "N9C0C_MINIMUM_RERUN_METRICS", minimum_metric_rows)
    _write_summary(
        stage_root / "summary" / "n9c0c_minimum_rerun_summary.md",
        "N9C0C Minimum Rerun Summary",
        [
            f"- Normal smoke passed: {normal_passed}",
            f"- Minimum cases requested: {len(minimum_cases)}",
            f"- Minimum cases completed: {sum(row.get('solver_status') == 'completed' for row in minimum_status_rows)}",
            "- Full N9B2 matrix execution: False",
        ],
    )
    review_rows = _build_review_rows(config_rows, normal_status_rows, minimum_status_rows, verification_rows)
    return _write_terminal_reports(
        stage_root,
        full_root,
        feasibility_report,
        spec_report,
        config_rows,
        normal_status_rows,
        minimum_status_rows,
        review_rows,
        verification_rows,
    )


def _build_review_rows(
    config_rows: list[dict[str, Any]],
    normal_status_rows: list[dict[str, Any]],
    minimum_status_rows: list[dict[str, Any]],
    verification_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "check": "module_flags_enabled_in_config",
            "status": "pass"
            if all(
                row.get("raw_doppler_enabled")
                and row.get("source_aware_enabled")
                and row.get("go2_legged_aux_enabled")
                and row.get("selected_feedback_enabled")
                for row in config_rows
            )
            else "fail",
            "evidence": "N9C0C_RUNTIME_CONFIG_INDEX",
        },
        {
            "check": "same_case_feedback_policy",
            "status": "pass" if all(row.get("same_case_feedback_exists") for row in config_rows) else "fail",
            "evidence": "N9C0C_RUNTIME_CONFIG_INDEX",
        },
        {
            "check": "normal_smoke_completed",
            "status": "pass" if any(row.get("same_order_sanity") is True for row in normal_status_rows) else "fail",
            "evidence": "N9C0C_NORMAL_SMOKE_STATUS",
        },
        {
            "check": "minimum_rerun_completed",
            "status": "pass"
            if len(minimum_status_rows) == EXPECTED_MINIMUM_CASE_COUNT
            and all(row.get("same_order_sanity") is True for row in minimum_status_rows)
            else "fail",
            "evidence": "N9C0C_MINIMUM_RERUN_STATUS",
        },
        {
            "check": "no_trace_or_final_v23_solver_input",
            "status": "pass"
            if not any(row.get("trace_solver_input") or row.get("final_v23_solver_input") for row in verification_rows)
            else "fail",
            "evidence": "RUN_MANIFEST safety flags",
        },
        {
            "check": "no_complete_nine_factor_fgo_claim",
            "status": "pass",
            "evidence": CLASSIFICATION,
        },
    ]


def _write_terminal_reports(
    stage_root: Path,
    full_root: Path,
    feasibility_report: dict[str, Any],
    spec_report: dict[str, Any],
    config_rows: list[dict[str, Any]],
    normal_status_rows: list[dict[str, Any]],
    minimum_status_rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    verification_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if not review_rows:
        review_rows = _build_review_rows(config_rows, normal_status_rows, minimum_status_rows, verification_rows)
    normal_passed = any(row.get("same_order_sanity") is True for row in normal_status_rows)
    minimum_passed = (
        len(minimum_status_rows) == EXPECTED_MINIMUM_CASE_COUNT
        and all(row.get("same_order_sanity") is True for row in minimum_status_rows)
    )
    feasible = feasibility_report.get("ready_for_materialization") is True
    if not feasible:
        decision = "N9C0C_full_algorithm_infeasible_current_code"
        ready_n9c0d = False
        recommended = "human_decision_reframe_as_ablation_study_or_implement_full_algorithm"
    elif normal_passed and minimum_passed:
        decision = "N9C0C_legsa_full_algorithm_materialized_minimum_rerun_passed"
        ready_n9c0d = True
        recommended = "N9C0D_LEGSA_FULL_ALGORITHM_FULL_MATRIX_EXPANSION"
    else:
        decision = "N9C0C_legsa_full_algorithm_materialized_but_minimum_rerun_failed"
        ready_n9c0d = False
        recommended = "fix_full_algorithm_runner_or_config"
    validation_issues = [row for row in review_rows if row.get("status") != "pass"]
    review_report = {
        "stage": STAGE,
        "generated_at": _now(),
        "rows": review_rows,
        "module_verification_rows": verification_rows,
        "classification": CLASSIFICATION,
        "complete_nine_factor_fgo_claim": False,
    }
    write_json(stage_root / "reports" / "N9C0C_FULL_ALGORITHM_REVIEW_REPORT.json", review_report)
    _write_table_pair(stage_root / "matrix" / "N9C0C_FULL_ALGORITHM_REVIEW", review_rows)
    _write_summary(
        stage_root / "summary" / "n9c0c_full_algorithm_review.md",
        "N9C0C Full Algorithm Review",
        [f"- {row['check']}: {row['status']}" for row in review_rows],
    )
    validation_report = {
        "stage": STAGE,
        "generated_at": _now(),
        "status": "pass" if not validation_issues else "fail",
        "issues": validation_issues,
        "ready_for_N9C0D_legsa_full_algorithm_full_matrix_expansion": ready_n9c0d,
        "ready_for_N9C1_consolidated_figure_generation": False,
        "ready_for_paper_claims": False,
        "ready_for_N9B2_execution": False,
        "ready_for_full_N9B_execution": False,
        "full_matrix_execution": False,
        "figure_generation": False,
        "paper_performance_claim": False,
    }
    decision_report = {
        "stage": STAGE,
        "generated_at": _now(),
        "decision": decision,
        "classification": CLASSIFICATION,
        "ready_for_N9C0D_legsa_full_algorithm_full_matrix_expansion": ready_n9c0d,
        "ready_for_N9C1_consolidated_figure_generation": False,
        "ready_for_paper_claims": False,
        "ready_for_N9B2_execution": False,
        "ready_for_full_N9B_execution": False,
        "recommended_next_stage": recommended,
        "normal_smoke_passed": normal_passed,
        "minimum_rerun_passed": minimum_passed,
        "complete_nine_factor_fgo_claim": False,
        "output_root": str(stage_root),
        "full_algorithm_runtime_root": str(full_root),
        "validation_status": validation_report["status"],
    }
    write_json(stage_root / "reports" / "N9C0C_VALIDATION_REPORT.json", validation_report)
    write_json(stage_root / "reports" / "N9C0C_DECISION_REPORT.json", decision_report)
    _write_summary(
        stage_root / "summary" / "n9c0c_next_stage_recommendation.md",
        "N9C0C Next Stage Recommendation",
        [
            f"- Decision: {decision}",
            f"- Ready for N9C0D: {ready_n9c0d}",
            "- Ready for N9C1 consolidated figure generation: False",
            "- Ready for paper claims: False",
            f"- Recommended next stage: {recommended}",
        ],
    )
    return {
        "feasibility_report": feasibility_report,
        "spec_report": spec_report,
        "config_rows": config_rows,
        "normal_status_rows": normal_status_rows,
        "minimum_status_rows": minimum_status_rows,
        "review_report": review_report,
        "validation_report": validation_report,
        "decision_report": decision_report,
    }
