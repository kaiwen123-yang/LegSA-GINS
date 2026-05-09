"""N4H4D5 feedback/update/covariance isolation matrix."""

from __future__ import annotations

import json
import math
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .legsa_v23_clean_replay_evaluator import evaluate_legsa_clean_replay, load_dual_official_reference
from .legsa_v23_clean_replay_runner import build_clean_replay_config, check_runtime_outputs


VARIANTS = {
    "baseline_current": {},
    "no_feedback": {"feedback": "no_feedback"},
    "pos_vel_only_feedback": {"feedback": "pos_vel_only"},
    "attitude_only_feedback": {"feedback": "attitude_only"},
    "no_attitude_feedback": {"feedback": "no_attitude_feedback"},
    "no_bias_scale_feedback": {"feedback": "no_bias_scale_feedback"},
    "delayed_feedback_every_5_updates": {"feedback": "delayed_feedback_every_5_updates"},
    "dx_phi_clamp_5deg_diagnostic": {"feedback": "dx_phi_clamp_5deg_diagnostic"},
    "dx_phi_clamp_1deg_diagnostic": {"feedback": "dx_phi_clamp_1deg_diagnostic"},
    "inflate_attitude_10x": {"covariance": "inflate_attitude_10x"},
    "inflate_attitude_100x": {"covariance": "inflate_attitude_100x"},
    "inflate_measurement_R_10x": {"covariance": "inflate_measurement_R_10x"},
    "inflate_yaw_R_10x": {"covariance": "inflate_yaw_R_10x"},
    "inflate_position_R_10x": {"covariance": "inflate_position_R_10x"},
    "inflate_velocity_R_10x": {"covariance": "inflate_velocity_R_10x"},
    "no_yaw_update": {"update": "no_yaw"},
    "no_velocity_update": {"update": "no_velocity"},
    "no_position_update": {"update": "no_position"},
    "position_velocity_only": {"update": "position_velocity"},
    "position_yaw_only": {"update": "position_yaw"},
    "velocity_yaw_only": {"update": "velocity_yaw"},
}

METRICS = ["horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg", "roll_rmse_deg", "pitch_rmse_deg"]


def _metric(summary: dict[str, Any], key: str) -> float:
    value = summary.get(key)
    return float(value) if isinstance(value, (int, float)) and math.isfinite(float(value)) else float("inf")


def _score(summary: dict[str, Any]) -> float:
    return (
        min(_metric(summary, "horizontal_rmse_m"), 1.0e6) / 100.0
        + min(_metric(summary, "up_rmse_m"), 1.0e6) / 100.0
        + min(_metric(summary, "yaw_rmse_deg"), 1.0e6) / 10.0
        + min(_metric(summary, "roll_rmse_deg"), 1.0e6) / 10.0
        + min(_metric(summary, "pitch_rmse_deg"), 1.0e6) / 10.0
    )


def _run_variant(
    name: str,
    modes: dict[str, str],
    clean_root: str | Path,
    dual_reference: dict[str, Any],
    out: Path,
    exe: str | Path,
    allow_run: bool,
    timeout_s: float = 120.0,
) -> dict[str, Any]:
    config = build_clean_replay_config(clean_root, out, out / "config")
    run_report: dict[str, Any] = {"run_status": "not_run_without_allow_run"}
    summary: dict[str, Any] = {key: None for key in METRICS}
    manifest: dict[str, Any] = {}
    if allow_run and config.get("config_status") == "config_written":
        command = [
            str(exe),
            "--config",
            str(config["config_path"]),
            "--output-dir",
            str(out),
            "--debug-output-dir",
            str(out / "debug"),
            "--diagnostic-run-label",
            name,
            "--diagnostic-feedback-mode",
            modes.get("feedback", "normal"),
            "--diagnostic-update-block-mode",
            modes.get("update", "all"),
            "--diagnostic-covariance-mode",
            modes.get("covariance", "normal"),
        ]
        try:
            completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout_s)
            run_report = {
                "run_status": "completed" if completed.returncode == 0 else "failed",
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-1000:],
                "stderr_tail": completed.stderr[-1000:],
                "variant_timeout_seconds": timeout_s,
            }
        except subprocess.TimeoutExpired as exc:
            # 中文说明：D5 diagnostic variant 可能因闭环被故意破坏而极慢；
            # 超时本身作为诊断证据记录，不能伪装成通过或性能结果。
            run_report = {
                "run_status": "timeout",
                "returncode": None,
                "stdout_tail": (exc.stdout or "")[-1000:] if isinstance(exc.stdout, str) else "",
                "stderr_tail": (exc.stderr or "")[-1000:] if isinstance(exc.stderr, str) else "",
                "variant_timeout_seconds": timeout_s,
            }
        outputs = check_runtime_outputs(out)
        manifest = outputs.get("manifest", {})
        if run_report.get("run_status") == "completed" and dual_reference.get("dual_reference_status") == "reference_loaded":
            summary = evaluate_legsa_clean_replay(out / "EVAL_NAV.csv", dual_reference["reference_rows"], out)["summary"]
    return {
        "variant": name,
        "modes": modes,
        "summary": summary,
        "run_report": run_report,
        "manifest": manifest,
        "update_counts": {
            "propagation_count": manifest.get("propagation_count", 0),
            "measurement_update_count": manifest.get("measurement_update_count", 0),
            "yaw_reject_count": manifest.get("yaw_reject_count", 0),
        },
        "diagnostic_only": True,
        "not_for_performance_claim": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def classify_feedback_matrix(variant_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """中文说明：选择诊断上最有解释力的 variant；不产生正式改进结论。"""

    baseline = variant_reports.get("baseline_current", {}).get("summary", {})
    baseline_score = _score(baseline)
    ranked = sorted(((name, _score(report.get("summary", {}))) for name, report in variant_reports.items()), key=lambda item: item[1])
    best = ranked[0][0] if ranked else "evidence_missing"
    def improved(name: str, metric: str, ratio: float = 0.5) -> bool:
        return _metric(variant_reports.get(name, {}).get("summary", {}), metric) < _metric(baseline, metric) * ratio
    return {
        "best_diagnostic_variant": best,
        "ranked_scores": [{"variant": name, "score": score} for name, score in ranked],
        "attitude_feedback_primary_issue": bool(improved("no_attitude_feedback", "roll_rmse_deg") or improved("no_attitude_feedback", "pitch_rmse_deg")),
        "gain_or_R_scaling_issue": bool(improved("inflate_measurement_R_10x", "roll_rmse_deg") or improved("inflate_measurement_R_10x", "yaw_rmse_deg")),
        "velocity_update_primary_issue": bool(improved("no_velocity_update", "horizontal_rmse_m")),
        "yaw_update_primary_issue": bool(improved("no_yaw_update", "yaw_rmse_deg")),
        "position_update_primary_issue": bool(improved("no_position_update", "horizontal_rmse_m")),
        "feedback_overcorrection_confirmed": bool(
            improved("dx_phi_clamp_5deg_diagnostic", "roll_rmse_deg") or improved("dx_phi_clamp_1deg_diagnostic", "roll_rmse_deg")
        ),
        "mechanization_primary_issue": False,
        "diagnostic_only": True,
        "not_for_performance_claim": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def run_feedback_isolation_matrix(
    clean_root: str | Path,
    dual_root: str | Path,
    output_dir: str | Path,
    exe: str | Path,
    allow_run: bool = False,
    timeout_s: float = 120.0,
    parallel_workers: int = 4,
) -> dict[str, Any]:
    """中文说明：运行 D5 feedback/update/covariance diagnostic variants，输出 runtime-only matrix。"""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    dual_reference = load_dual_official_reference(dual_root)
    reports = {}
    max_workers = max(1, min(parallel_workers, len(VARIANTS)))
    # 中文说明：各 variant 写入独立 runtime-only 目录，可并行；它们仍是诊断结果，不是性能实验。
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(
                _run_variant,
                name,
                modes,
                clean_root,
                dual_reference,
                out / name,
                exe,
                allow_run,
                timeout_s,
            ): name
            for name, modes in VARIANTS.items()
        }
        for future in as_completed(future_map):
            name = future_map[future]
            try:
                reports[name] = future.result()
            except Exception as exc:  # pragma: no cover - defensive runtime evidence path
                reports[name] = {
                    "variant": name,
                    "summary": {key: None for key in METRICS},
                    "run_report": {"run_status": "failed_exception", "error": str(exc), "variant_timeout_seconds": timeout_s},
                    "diagnostic_only": True,
                    "not_for_performance_claim": True,
                    "trace_solver_input": False,
                    "final_v23_output_substitution": False,
                    "output_only_correction": False,
                    "bad_epoch_deletion_for_metric": False,
                    "numerical_performance_claim": False,
                }
    classification = classify_feedback_matrix(reports)
    matrix = {
        "phase": "N4H4D5",
        "variant_summaries": reports,
        "variant_timeout_seconds": timeout_s,
        "parallel_workers": max_workers,
        **classification,
    }
    (out / "FEEDBACK_ISOLATION_MATRIX_REPORT.json").write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return matrix
