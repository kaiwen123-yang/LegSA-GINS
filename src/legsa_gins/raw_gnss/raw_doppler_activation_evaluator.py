"""Run the N5B raw Doppler EKF activation trial.

中文说明：trial 只在 provider factor 合法时启用 raw Doppler；baseline replay 和 raw
Doppler replay 均为诊断，不构成 paper performance claim。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def find_clean_config(clean_root: str | Path) -> Path | None:
    root = Path(clean_root)
    if not root.exists():
        return None
    preferred = root / "kf-gins-n4h2g-clean-replay.yaml"
    if preferred.exists():
        return preferred
    matches = sorted(root.glob("*.yaml")) + sorted(root.glob("*.yml"))
    return matches[0] if matches else None


def find_clean_gnss(clean_root: str | Path) -> Path | None:
    root = Path(clean_root)
    preferred = root / "CLEAN_STATUS_YAW.gnss"
    if preferred.exists():
        return preferred
    matches = sorted(root.glob("*.gnss"))
    return matches[0] if matches else None


def write_raw_doppler_config(base_config: str | Path, factor_csv: str | Path, output_path: str | Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    content = Path(base_config).read_text(encoding="utf-8", errors="ignore")
    # 中文说明：runtime-only config copy 启用 raw Doppler velocity factor，不修改 tracked config。
    content += "\n# N5B runtime-only raw Doppler velocity factor activation.\n"
    content += "enable_raw_doppler: true\n"
    content += f'raw_doppler_factor_path: "{Path(factor_csv)}"\n'
    content += "raw_doppler_factor_source: RTKLIB_DOPPLER_PROVIDER\n"
    content += "raw_doppler_time_tolerance_sec: 0.08\n"
    content += "raw_doppler_min_sat: 5\n"
    content += "raw_doppler_residual_gate_mps: 3.0\n"
    content += "raw_doppler_R_scale: 1.0\n"
    content += "raw_doppler_mode: doppler_ls_velocity\n"
    target.write_text(content, encoding="utf-8")
    return target


def _run_demo(exe: str | Path, config: str | Path, output_dir: str | Path) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    command = [str(exe), "--config", str(config), "--output-dir", str(out)]
    proc = subprocess.run(command, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=240)
    manifest_path = out / "RUN_MANIFEST.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "manifest_path": str(manifest_path) if manifest_path.exists() else "",
        "manifest": manifest,
    }


def _summary(run: dict[str, Any]) -> dict[str, Any]:
    manifest = run.get("manifest", {})
    return {
        "returncode": run.get("returncode"),
        "raw_doppler_solver_enabled": manifest.get("raw_doppler_solver_enabled", False),
        "raw_doppler_update_count": manifest.get("raw_doppler_update_count", 0),
        "measurement_update_count": manifest.get("measurement_update_count", 0),
        "position_update_count": manifest.get("position_update_count", 0),
        "velocity_update_count": manifest.get("velocity_update_count", 0),
        "yaw_update_count": manifest.get("yaw_update_count", 0),
        "paper_performance_claim": manifest.get("paper_performance_claim", False),
    }


def run_n5b_activation_trial(
    *,
    clean_root: str | Path,
    factor_build_report: dict[str, Any],
    output_dir: str | Path,
    exe: str | Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    out = Path(output_dir)
    baseline_dir = out / "baseline_replay"
    raw_dir = out / "raw_doppler_enabled_replay"
    blockers: list[str] = []
    clean_config = find_clean_config(clean_root)
    if not factor_build_report.get("raw_doppler_solver_activation_allowed", False):
        blockers.append("factor_build_not_activation_allowed")
    if clean_config is None:
        blockers.append("clean_replay_config_missing")
    factor_csv = factor_build_report.get("factor_csv_path", "")
    if factor_csv and not Path(factor_csv).exists():
        blockers.append("factor_csv_missing")
    if not Path(exe).exists():
        blockers.append("cpp_demo_executable_missing")

    baseline_run: dict[str, Any] = {"returncode": None, "manifest": {}}
    raw_run: dict[str, Any] = {"returncode": None, "manifest": {}}
    if not blockers:
        baseline_run = _run_demo(exe, clean_config, baseline_dir)
        raw_config = write_raw_doppler_config(clean_config, factor_csv, out / "runtime_configs" / "n5b_raw_doppler_enabled.yaml")
        raw_run = _run_demo(exe, raw_config, raw_dir)
        if baseline_run["returncode"] != 0:
            blockers.append("baseline_replay_failed")
        if raw_run["returncode"] != 0:
            blockers.append("raw_doppler_replay_failed")

    raw_manifest = raw_run.get("manifest", {})
    update_count = int(raw_manifest.get("raw_doppler_update_count", 0) or 0)
    solver_enabled = bool(raw_manifest.get("raw_doppler_solver_enabled", False))
    if not blockers and solver_enabled and update_count > 0:
        status = "completed_enabled"
        next_stage = "N5C_raw_doppler_ablation_protocol"
    elif factor_build_report.get("factor_csv_generated") and update_count == 0:
        status = "activation_failed_update_alignment_or_loader"
        next_stage = "N5B2_raw_doppler_time_alignment_fix"
        blockers.append("raw_doppler_update_count_zero")
    else:
        status = "blocked"
        next_stage = "N5B2_data_availability_recheck"
    comparison = {
        "baseline_summary": _summary(baseline_run),
        "raw_doppler_diagnostic_summary": _summary(raw_run),
        "diagnostic_delta": {
            "raw_minus_baseline_measurement_update_count": _summary(raw_run)["measurement_update_count"] - _summary(baseline_run)["measurement_update_count"],
            "raw_doppler_update_count": update_count,
        },
        "metric_namespace": "R3C_diagnostic_delta_not_paper_performance",
        "paper_performance_claim": False,
    }
    trial = {
        "real_activation_status": status,
        "raw_doppler_solver_enabled": solver_enabled,
        "raw_doppler_update_count": update_count,
        "raw_doppler_reject_count": raw_manifest.get("raw_doppler_reject_count", 0),
        "raw_doppler_factor_epoch_count": raw_manifest.get("raw_doppler_factor_epoch_count", raw_manifest.get("raw_doppler_epoch_count", 0)),
        "raw_doppler_factor_valid_epoch_count": raw_manifest.get("raw_doppler_factor_valid_epoch_count", 0),
        "raw_doppler_factor_source": raw_manifest.get("raw_doppler_factor_source", "none"),
        "baseline_run": {k: baseline_run.get(k) for k in ("command", "returncode", "stdout_tail", "stderr_tail", "manifest_path")},
        "raw_doppler_run": {k: raw_run.get(k) for k in ("command", "returncode", "stdout_tail", "stderr_tail", "manifest_path")},
        "recommended_next_stage": next_stage,
        "blocker_reasons": sorted(set(blockers)),
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "rtklib_position_solution_used_as_solver_input": False,
        "nav_pvt_velocity_used_as_raw_doppler": False,
        "gnss_velocity_used_as_raw_doppler": False,
    }
    return trial, comparison
