"""N5C raw Doppler ablation runner/evaluator helpers.

中文说明：本模块只生成 runtime-only config 并运行诊断消融；dual/final_v23 只作为
评价参考，不进入 LegSA solver。
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.legsa_v23_port_clean_replay_evaluator import evaluate_port_clean_replay
from legsa_gins.raw_gnss.raw_doppler_activation_evaluator import find_clean_config, find_clean_gnss


METRIC_KEYS = ["horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg", "roll_rmse_deg", "pitch_rmse_deg"]


def _read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    return json.loads(source.read_text(encoding="utf-8"))


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_ablation_variant_config(base_config: str | Path, variant: dict[str, Any], output_path: str | Path) -> Path:
    """Write a runtime-only config for one ablation variant."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    content = Path(base_config).read_text(encoding="utf-8", errors="ignore")
    variant_id = str(variant["variant_id"])
    # 中文说明：receiver-native velocity 与 raw Doppler velocity 是两类不同观测；
    # 关闭 receiver velocity 仅用于诊断隔离，不是最终 proposed 设置。
    lines = [
        "",
        "# N5C runtime-only raw Doppler ablation config.",
        f"ablation_variant: {variant_id}",
        f"raw_doppler_diagnostic_variant_label: {variant_id}",
        f"enable_receiver_velocity_update: {str(bool(variant['enable_receiver_velocity_update'])).lower()}",
        f"enable_raw_doppler: {str(bool(variant['enable_raw_doppler'])).lower()}",
        f"diagnostic_only: {str(bool(variant['diagnostic_only'])).lower()}",
        "proposed_factor_claim: false",
        "paper_performance_claim: false",
        "no_outperform_final_v23_claim: true",
    ]
    if variant["enable_raw_doppler"]:
        # 中文说明：R_scale screen 是诊断筛查，不是用结果挑选正式调参。
        lines.extend(
            [
                f'raw_doppler_factor_path: "{variant["raw_doppler_factor_path"]}"',
                "raw_doppler_factor_source: RTKLIB_DOPPLER_PROVIDER",
                "raw_doppler_time_tolerance_sec: 0.08",
                "raw_doppler_min_sat: 5",
                "raw_doppler_residual_gate_mps: 3.0",
                f"raw_doppler_R_scale: {float(variant['raw_doppler_R_scale'])}",
                "raw_doppler_mode: doppler_ls_velocity",
            ]
        )
    target.write_text(content + "\n".join(lines) + "\n", encoding="utf-8")
    return target


def run_ablation_variant(config_path: str | Path, exe: str | Path, build_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Run one C++ replay variant and return command/runtime metadata."""
    del build_dir  # The executable path is already fully supplied by the caller.
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    command = [str(exe), "--config", str(config_path), "--output-dir", str(out)]
    proc = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=300,
    )
    manifest_path = out / "RUN_MANIFEST.json"
    manifest = _read_json(manifest_path)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "manifest_path": str(manifest_path) if manifest_path.exists() else "",
        "manifest": manifest,
    }


def _metric_summary_missing(reason: str) -> dict[str, Any]:
    return {
        "count": 0,
        "aligned_count": 0,
        "evidence_status": reason,
        "horizontal_rmse_m": None,
        "up_rmse_m": None,
        "yaw_rmse_deg": None,
        "roll_rmse_deg": None,
        "pitch_rmse_deg": None,
        "horizontal_gate_pass": False,
        "up_gate_pass": False,
        "yaw_gate_pass": False,
        "roll_relaxed_pass": False,
        "pitch_relaxed_pass": False,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
    }


def evaluate_variant(output_dir: str | Path, dual_reference: str | Path | None, trace_reference: str | Path | None = None) -> dict[str, Any]:
    """Evaluate one variant with the existing R3C-style namespace."""
    del trace_reference
    out = Path(output_dir)
    eval_nav = out / "EVAL_NAV.csv"
    manifest = _read_json(out / "RUN_MANIFEST.json")
    if eval_nav.exists() and dual_reference and (Path(dual_reference) / "KF_GINS_Navresult.nav").exists():
        evaluation = evaluate_port_clean_replay(eval_nav, dual_reference)
        summary = evaluation["summary"]
    else:
        evaluation = {
            "phase": "N5C",
            "summary": _metric_summary_missing("reference_or_eval_nav_missing"),
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
            "paper_performance_claim": False,
            "proposed_factor_claim": False,
        }
        summary = evaluation["summary"]
    return {
        "variant_id": manifest.get("ablation_variant", Path(output_dir).name),
        "returncode": 0 if eval_nav.exists() else None,
        "summary": summary,
        "evaluation": evaluation,
        "raw_doppler_update_count": int(manifest.get("raw_doppler_update_count", 0) or 0),
        "raw_doppler_reject_count": int(manifest.get("raw_doppler_reject_count", 0) or 0),
        "raw_doppler_residual_p95": manifest.get("raw_doppler_residual_p95"),
        "raw_doppler_solver_enabled": bool(manifest.get("raw_doppler_solver_enabled", False)),
        "enable_receiver_velocity_update": bool(manifest.get("enable_receiver_velocity_update", True)),
        "enable_raw_doppler": bool(manifest.get("enable_raw_doppler", False)),
        "raw_doppler_R_scale": manifest.get("raw_doppler_R_scale"),
        "diagnostic_only": bool(manifest.get("diagnostic_only", True)),
        "proposed_factor_claim": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }


def _delta(a: dict[str, Any] | None, b: dict[str, Any] | None) -> dict[str, float | None]:
    if not a or not b:
        return {key: None for key in METRIC_KEYS}
    out: dict[str, float | None] = {}
    for key in METRIC_KEYS:
        av = a.get("summary", {}).get(key)
        bv = b.get("summary", {}).get(key)
        out[key] = (av - bv) if isinstance(av, (int, float)) and isinstance(bv, (int, float)) else None
    return out


def _score(delta: dict[str, float | None]) -> float | None:
    vals = [value for key, value in delta.items() if key in {"horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg"} and value is not None]
    return sum(vals) if vals else None


def compare_variants(variant_reports: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {report["variant_id"]: report for report in variant_reports}
    baseline = by_id.get("baseline_full")
    plus = by_id.get("baseline_plus_raw_doppler_r1")
    py_only = by_id.get("position_yaw_only")
    py_raw = by_id.get("position_yaw_plus_raw_doppler_r1")
    delta_plus = _delta(plus, baseline)
    delta_iso = _delta(py_raw, py_only)
    score = _score(delta_plus)
    degrade = any(
        (delta_plus.get(key) is not None and delta_plus[key] > limit)
        for key, limit in {"horizontal_rmse_m": 0.5, "up_rmse_m": 0.5, "yaw_rmse_deg": 0.2}.items()
    )
    beneficial = score is not None and score < -0.05 and not degrade
    neutral = score is not None and not beneficial and not degrade
    rscale = [
        {
            "variant_id": report["variant_id"],
            "raw_doppler_R_scale": report.get("raw_doppler_R_scale"),
            "summary": report.get("summary", {}),
            "raw_doppler_update_count": report.get("raw_doppler_update_count", 0),
            "diagnostic_only": report.get("variant_id") != "baseline_plus_raw_doppler_r1",
        }
        for report in variant_reports
        if report["variant_id"].startswith("baseline_plus_raw_doppler_r")
    ]
    return {
        "baseline_full_summary": baseline.get("summary", {}) if baseline else {},
        "baseline_plus_raw_doppler_summary": plus.get("summary", {}) if plus else {},
        "delta_baseline_plus_raw_doppler_minus_baseline": delta_plus,
        "position_yaw_only_summary": py_only.get("summary", {}) if py_only else {},
        "position_yaw_plus_raw_doppler_summary": py_raw.get("summary", {}) if py_raw else {},
        "velocity_isolation_delta": delta_iso,
        "R_scale_screen_summary": rscale,
        "raw_doppler_activation_consistent": bool(plus and plus.get("raw_doppler_update_count", 0) > 0),
        "raw_doppler_update_count": int(plus.get("raw_doppler_update_count", 0) if plus else 0),
        "raw_doppler_reject_count": int(plus.get("raw_doppler_reject_count", 0) if plus else 0),
        "raw_doppler_residual_p95": plus.get("raw_doppler_residual_p95") if plus else None,
        "raw_doppler_beneficial_diagnostic": beneficial,
        "raw_doppler_degrades_diagnostic": degrade,
        "raw_doppler_neutral_diagnostic": neutral,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
        "diagnostic_only": True,
    }


def run_matrix_variants(
    matrix_report: dict[str, Any],
    *,
    clean_root: str | Path,
    exe: str | Path,
    build_dir: str | Path,
    output_dir: str | Path,
    dual_reference: str | Path | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base_config = find_clean_config(clean_root)
    if base_config is None:
        raise FileNotFoundError("clean replay config missing")
    runs: list[dict[str, Any]] = []
    evals: list[dict[str, Any]] = []
    for variant in matrix_report["matrix"]:
        config_path = write_ablation_variant_config(base_config, variant, variant["config_path"])
        run = run_ablation_variant(config_path, exe, build_dir, variant["output_dir"])
        run["variant_id"] = variant["variant_id"]
        runs.append(run)
        report = evaluate_variant(variant["output_dir"], dual_reference)
        report["returncode"] = run.get("returncode")
        evals.append(report)
    _write_json(Path(output_dir) / "N5C_ABLATION_VARIANT_RUNS.json", {"runs": runs, "paper_performance_claim": False})
    _write_json(Path(output_dir) / "N5C_ABLATION_VARIANT_EVALUATIONS.json", {"variants": evals, "paper_performance_claim": False})
    return runs, evals


def load_clean_time_window(clean_root: str | Path) -> tuple[float | None, float | None]:
    config = find_clean_config(clean_root)
    if config is None:
        return None, None
    start: float | None = None
    end: float | None = None
    for line in config.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip().startswith("starttime:"):
            start = float(line.split(":", 1)[1].strip())
        if line.strip().startswith("endtime:"):
            end = float(line.split(":", 1)[1].strip())
    return start, end
