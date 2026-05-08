"""Diagnostic update/feedback variant matrix for N4H4D2.

中文说明：这些 variants 只在 diagnostic_mode 下运行，用来定位公式符号/反馈侧问题；
它们不是性能实验，也不能替代 baseline solver。
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.legsa_v23_clean_replay_evaluator import (
    evaluate_legsa_clean_replay,
    load_dual_official_reference,
)
from legsa_gins.evaluation.legsa_v23_clean_replay_runner import build_clean_replay_config, check_runtime_outputs
from legsa_gins.evaluation.legsa_v23_runtime_debug_trace import read_csv_rows
from legsa_gins.evaluation.legsa_v23_update_residual_diagnostics import analyze_update_residuals


VARIANTS = [
    "baseline_current",
    "position_residual_sign_flip",
    "position_H_phi_sign_flip",
    "position_no_H_phi",
    "velocity_residual_sign_flip",
    "yaw_residual_sign_flip",
    "yaw_H_sign_flip",
    "state_feedback_pos_vel_add",
    "state_feedback_phi_negative",
    "state_feedback_phi_right_multiply",
    "state_feedback_no_phi",
    "ekf_update_residual_sign_flip",
]

METRICS = ["horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg", "roll_rmse_deg", "pitch_rmse_deg"]


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _metric(summary: dict[str, Any], key: str) -> float:
    value = summary.get(key)
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return float("inf")


def _score(summary: dict[str, Any]) -> float:
    weights = {
        "horizontal_rmse_m": 1.0 / 100.0,
        "up_rmse_m": 1.0 / 100.0,
        "yaw_rmse_deg": 1.0 / 10.0,
        "roll_rmse_deg": 1.0 / 10.0,
        "pitch_rmse_deg": 1.0 / 10.0,
    }
    return sum(min(_metric(summary, key), 1.0e6) * weight for key, weight in weights.items())


def _improvement_count(candidate: dict[str, Any], baseline: dict[str, Any]) -> int:
    count = 0
    for key in METRICS:
        base_value = _metric(baseline, key)
        cand_value = _metric(candidate, key)
        if math.isfinite(base_value) and cand_value < base_value * 0.8:
            count += 1
    return count


def classify_variant_matrix(variant_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """中文说明：选择最强诊断候选；只产生 D3 线索，不产生 pass/performance claim。"""

    baseline = variant_reports.get("baseline_current", {}).get("summary", {})
    baseline_score = _score(baseline)
    ranked = sorted(
        ((name, _score(report.get("summary", {}))) for name, report in variant_reports.items()),
        key=lambda item: item[1],
    )
    best_name = ranked[0][0] if ranked else "evidence_missing"
    if best_name == "baseline_current" and len(ranked) > 1:
        best_nonbaseline = ranked[1][0]
    else:
        best_nonbaseline = best_name
    best_nonbaseline_summary = variant_reports.get(best_nonbaseline, {}).get("summary", {})
    best_nonbaseline_score = _score(best_nonbaseline_summary)
    candidate_fix_detected = bool(
        best_nonbaseline != "baseline_current"
        and best_nonbaseline_score < baseline_score * 0.6
        and _improvement_count(best_nonbaseline_summary, baseline) >= 2
    )
    improved_variants = [
        name
        for name, report in variant_reports.items()
        if name != "baseline_current" and _improvement_count(report.get("summary", {}), baseline) >= 2
    ]
    return {
        "best_candidate_variant": best_nonbaseline if candidate_fix_detected else best_name,
        "candidate_fix_detected": candidate_fix_detected,
        "candidate_fix_variant": best_nonbaseline if candidate_fix_detected else None,
        "multi_issue_or_coupled_issue": len(improved_variants) > 1,
        "improved_variants": improved_variants,
        "ranked_scores": [{"variant": name, "score": score} for name, score in ranked],
        "diagnostic_only": True,
        "not_for_performance_claim": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def _run_variant(
    variant: str,
    clean_root: str | Path,
    dual_reference: dict[str, Any],
    variant_dir: Path,
    exe: str | Path,
    allow_run: bool,
) -> dict[str, Any]:
    debug_dir = variant_dir / "debug"
    config_report = build_clean_replay_config(clean_root, variant_dir, variant_dir / "config")
    summary: dict[str, Any] = {
        "count": 0,
        "horizontal_rmse_m": None,
        "up_rmse_m": None,
        "yaw_rmse_deg": None,
        "roll_rmse_deg": None,
        "pitch_rmse_deg": None,
    }
    run_report: dict[str, Any] = {"run_status": "not_run_without_allow_run", "returncode": None}
    manifest: dict[str, Any] = {}
    residual_report: dict[str, Any] = {"update_count_analyzed": 0, "yaw_reject_ratio": 0.0}
    if allow_run and config_report.get("config_status") == "config_written":
        command = [
            str(exe),
            "--config",
            str(config_report["config_path"]),
            "--output-dir",
            str(variant_dir),
            "--debug-output-dir",
            str(debug_dir),
            "--debug-max-updates",
            "30",
            "--diagnostic-run-label",
            variant,
            "--diagnostic-model-variant",
            variant,
        ]
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        run_report = {
            "run_status": "completed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-1200:],
            "stderr_tail": completed.stderr[-1200:],
        }
        outputs = check_runtime_outputs(variant_dir)
        manifest = outputs.get("manifest", {})
        first_updates = read_csv_rows(debug_dir / "FIRST_UPDATES.csv")
        residual_report = analyze_update_residuals(first_updates)
        if (
            completed.returncode == 0
            and outputs.get("runtime_output_status") == "outputs_ready"
            and dual_reference.get("dual_reference_status") == "reference_loaded"
        ):
            evaluation = evaluate_legsa_clean_replay(variant_dir / "EVAL_NAV.csv", dual_reference["reference_rows"], variant_dir)
            summary = evaluation["summary"]
    return {
        "variant": variant,
        "diagnostic_only": True,
        "not_for_performance_claim": True,
        "config_report": config_report,
        "run_report": run_report,
        "manifest": manifest,
        "summary": summary,
        "yaw_mode_counts": {
            "NORMAL": manifest.get("yaw_normal_count", 0),
            "DOWNWEIGHT": manifest.get("yaw_downweight_count", 0),
            "REJECT": manifest.get("yaw_reject_count", 0),
        },
        "update_counts": {
            "propagation_count": manifest.get("propagation_count", 0),
            "measurement_update_count": manifest.get("measurement_update_count", 0),
            "position_update_count": manifest.get("position_update_count", 0),
            "velocity_update_count": manifest.get("velocity_update_count", 0),
            "yaw_update_count": manifest.get("yaw_update_count", 0),
        },
        "residual_diagnostics": {
            "position_residual_norm_p95_m": residual_report.get("position_residual_norm_p95_m"),
            "velocity_residual_norm_p95_mps": residual_report.get("velocity_residual_norm_p95_mps"),
            "yaw_reject_ratio": residual_report.get("yaw_reject_ratio"),
        },
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def run_variant_matrix(
    clean_root: str | Path,
    dual_root: str | Path,
    output_dir: str | Path,
    exe: str | Path,
    allow_run: bool = False,
) -> dict[str, Any]:
    """中文说明：运行 baseline + 诊断 variants；所有输出写 runtime-only output_dir。"""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    dual_reference = load_dual_official_reference(dual_root)
    variant_reports: dict[str, dict[str, Any]] = {}
    for variant in VARIANTS:
        variant_reports[variant] = _run_variant(
            variant=variant,
            clean_root=clean_root,
            dual_reference=dual_reference,
            variant_dir=out / variant,
            exe=exe,
            allow_run=allow_run,
        )
    classification = classify_variant_matrix(variant_reports)
    report = {
        "phase": "N4H4D2",
        "variant_summaries": variant_reports,
        **classification,
    }
    _write_json(out / "UPDATE_FEEDBACK_VARIANT_MATRIX_REPORT.json", report)
    return report
