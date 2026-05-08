"""Update-isolation matrix for N4H4D1 diagnostics.

中文说明：运行带诊断开关的 variants，只用于定位 propagation/update/feedback 问题；
这些 variants 不是性能结果，也不允许写成 improvement。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.legsa_v23_clean_replay_evaluator import (
    evaluate_legsa_clean_replay,
    load_dual_official_reference,
)
from legsa_gins.evaluation.legsa_v23_clean_replay_runner import build_clean_replay_config, check_runtime_outputs


VARIANTS: dict[str, list[str]] = {
    "all_updates_current": [],
    "propagation_only": ["--disable-measurement-update"],
    "position_only": ["--disable-velocity-update", "--disable-yaw-update"],
    "velocity_only": ["--disable-position-update", "--disable-yaw-update"],
    "yaw_only": ["--disable-position-update", "--disable-velocity-update"],
    "position_velocity_only": ["--disable-yaw-update"],
    "position_yaw_only": ["--disable-velocity-update"],
    "velocity_yaw_only": ["--disable-position-update"],
    "all_updates_no_state_feedback": ["--disable-state-feedback"],
}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def classify_isolation_matrix(variant_summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """中文说明：根据 variants 的发散模式给出问题来源，不做调参建议。"""

    def metric(name: str, field: str) -> float:
        value = variant_summaries.get(name, {}).get("summary", {}).get(field)
        return float(value) if isinstance(value, (int, float)) else 0.0

    prop_roll = metric("propagation_only", "roll_rmse_deg")
    prop_pitch = metric("propagation_only", "pitch_rmse_deg")
    prop_h = metric("propagation_only", "horizontal_rmse_m")
    all_h = metric("all_updates_current", "horizontal_rmse_m")
    no_feedback_h = metric("all_updates_no_state_feedback", "horizontal_rmse_m")
    position_h = metric("position_only", "horizontal_rmse_m")
    yaw_yaw = metric("yaw_only", "yaw_rmse_deg")

    categories: list[str] = []
    if max(prop_roll, prop_pitch) > 10.0 or prop_h > 10.0:
        categories.append("likely_mechanization_or_initialization_issue")
    if prop_h <= 10.0 and all_h > 10.0:
        categories.append("likely_update_or_feedback_issue")
    if position_h > max(prop_h, 1.0) * 2.0 and position_h > 10.0:
        categories.append("likely_position_update_sign_or_lever_issue")
    if yaw_yaw > 10.0:
        categories.append("likely_yaw_update_or_feedback_issue")
    if all_h > 10.0 and no_feedback_h <= max(prop_h, 10.0):
        categories.append("likely_state_feedback_sign_issue")
    if not categories:
        categories.append("evidence_missing")

    priority = [
        "likely_mechanization_or_initialization_issue",
        "likely_state_feedback_sign_issue",
        "likely_update_or_feedback_issue",
        "likely_yaw_update_or_feedback_issue",
        "likely_position_update_sign_or_lever_issue",
        "evidence_missing",
    ]
    recommended = next((item for item in priority if item in categories), categories[0])
    return {
        "recommended_issue_source": recommended,
        "divergence_categories": categories,
        "diagnostic_only": True,
        "not_for_performance_claim": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def run_update_isolation_matrix(
    clean_root: str | Path,
    dual_root: str | Path,
    output_dir: str | Path,
    exe: str | Path,
    allow_run: bool = False,
) -> dict[str, Any]:
    """中文说明：运行 A-I variants；所有输出落在 runtime-only output_dir/isolation。"""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    dual_reference = load_dual_official_reference(dual_root)
    variant_reports: dict[str, dict[str, Any]] = {}
    for label, switches in VARIANTS.items():
        variant_dir = out / label
        debug_dir = variant_dir / "debug"
        config_report = build_clean_replay_config(clean_root, variant_dir, variant_dir / "config")
        run_report: dict[str, Any] = {"run_status": "not_run_without_allow_run"}
        summary: dict[str, Any] = {
            "count": 0,
            "horizontal_rmse_m": None,
            "up_rmse_m": None,
            "yaw_rmse_deg": None,
            "roll_rmse_deg": None,
            "pitch_rmse_deg": None,
        }
        manifest: dict[str, Any] = {}
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
                label,
                *switches,
            ]
            completed = subprocess.run(command, check=False, capture_output=True, text=True)
            run_report = {
                "run_status": "completed" if completed.returncode == 0 else "failed",
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-1000:],
                "stderr_tail": completed.stderr[-1000:],
            }
            outputs = check_runtime_outputs(variant_dir)
            manifest = outputs.get("manifest", {})
            if (
                completed.returncode == 0
                and outputs.get("runtime_output_status") == "outputs_ready"
                and dual_reference.get("dual_reference_status") == "reference_loaded"
            ):
                evaluation = evaluate_legsa_clean_replay(variant_dir / "EVAL_NAV.csv", dual_reference["reference_rows"], variant_dir)
                summary = evaluation["summary"]
        variant_reports[label] = {
            "diagnostic_only": True,
            "not_for_performance_claim": True,
            "switches": switches,
            "config_report": config_report,
            "run_report": run_report,
            "manifest": manifest,
            "summary": summary,
            "trace_solver_input": False,
            "final_v23_output_substitution": False,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
            "numerical_performance_claim": False,
        }

    classification = classify_isolation_matrix(variant_reports)
    report = {
        "phase": "N4H4D1",
        "variant_summaries": variant_reports,
        **classification,
    }
    _write_json(out / "UPDATE_ISOLATION_MATRIX_REPORT.json", report)
    return report

