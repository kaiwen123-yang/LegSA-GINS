"""N4H4D6 bias/scale feedback and covariance diagnostic variant matrix."""

from __future__ import annotations

import json
import math
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .legsa_v23_clean_replay_evaluator import evaluate_legsa_clean_replay, load_dual_official_reference
from .legsa_v23_clean_replay_runner import build_clean_replay_config, check_runtime_outputs


VARIANTS: dict[str, dict[str, str]] = {
    "normal": {},
    "pos_vel_only": {"feedback": "pos_vel_only"},
    "pos_vel_attitude_only": {"feedback": "pos_vel_attitude_only"},
    "no_bias_scale_feedback": {"feedback": "no_bias_scale_feedback"},
    "no_bias_feedback": {"feedback": "no_bias_feedback"},
    "no_scale_feedback": {"feedback": "no_scale_feedback"},
    "no_gyrbias_feedback": {"feedback": "no_gyrbias_feedback"},
    "no_accbias_feedback": {"feedback": "no_accbias_feedback"},
    "no_gyrscale_feedback": {"feedback": "no_gyrscale_feedback"},
    "no_accscale_feedback": {"feedback": "no_accscale_feedback"},
    "no_imu_error_feedback": {"feedback": "no_imu_error_feedback"},
    "no_attitude_no_bias_scale": {"feedback": "no_attitude_no_bias_scale"},
    "zero_phi_bias_scale_cross_cov": {"covariance": "zero_phi_bias_scale_cross_cov"},
    "zero_bias_scale_cross_cov": {"covariance": "zero_bias_scale_cross_cov"},
    "shrink_bias_scale_P_10x": {"covariance": "shrink_bias_scale_P_10x"},
    "shrink_bias_scale_P_100x": {"covariance": "shrink_bias_scale_P_100x"},
    "zero_bias_scale_process_noise": {"covariance": "zero_bias_scale_process_noise"},
    "inflate_bias_scale_process_noise_10x": {"covariance": "inflate_bias_scale_process_noise_10x"},
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
    timeout_s: float,
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
            f"n4h4d6_{name}",
            "--diagnostic-feedback-mode",
            modes.get("feedback", "normal"),
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


def classify_bias_scale_variant_matrix(variant_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline = variant_reports.get("normal", {}).get("summary", {})
    ranked = sorted(((name, _score(report.get("summary", {}))) for name, report in variant_reports.items()), key=lambda item: item[1])
    best = ranked[0][0] if ranked else "evidence_missing"

    def improved(name: str, metric: str, ratio: float = 0.5) -> bool:
        return _metric(variant_reports.get(name, {}).get("summary", {}), metric) < _metric(baseline, metric) * ratio

    bias_scale_primary = bool(
        improved("no_bias_scale_feedback", "horizontal_rmse_m")
        or improved("no_imu_error_feedback", "horizontal_rmse_m")
        or improved("pos_vel_attitude_only", "horizontal_rmse_m")
    )
    return {
        "best_diagnostic_variant": best,
        "ranked_scores": [{"variant": name, "score": score} for name, score in ranked],
        "bias_scale_feedback_primary_suspect": bias_scale_primary,
        "bias_feedback_suspect": bool(improved("no_bias_feedback", "horizontal_rmse_m")),
        "scale_feedback_suspect": bool(improved("no_scale_feedback", "horizontal_rmse_m")),
        "gyrbias_feedback_suspect": bool(improved("no_gyrbias_feedback", "horizontal_rmse_m")),
        "accbias_feedback_suspect": bool(improved("no_accbias_feedback", "horizontal_rmse_m")),
        "gyrscale_feedback_suspect": bool(improved("no_gyrscale_feedback", "horizontal_rmse_m")),
        "accscale_feedback_suspect": bool(improved("no_accscale_feedback", "horizontal_rmse_m")),
        "cross_covariance_coupling_suspect": bool(
            improved("zero_phi_bias_scale_cross_cov", "roll_rmse_deg")
            or improved("zero_bias_scale_cross_cov", "roll_rmse_deg")
        ),
        "covariance_initialization_suspect": bool(
            improved("shrink_bias_scale_P_10x", "roll_rmse_deg")
            or improved("shrink_bias_scale_P_100x", "roll_rmse_deg")
        ),
        "pos_vel_attitude_only_improves_over_normal": bool(improved("pos_vel_attitude_only", "horizontal_rmse_m")),
        "pos_vel_only_expected_from_d5": True,
        "diagnostic_only": True,
        "not_for_performance_claim": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def run_bias_scale_variant_matrix(
    clean_root: str | Path,
    dual_root: str | Path,
    output_dir: str | Path,
    exe: str | Path,
    allow_run: bool = False,
    timeout_s: float = 120.0,
    parallel_workers: int = 4,
) -> dict[str, Any]:
    """中文说明：运行 D6 bias/scale feedback/covariance variants；所有输出 runtime-only。"""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    dual_reference = load_dual_official_reference(dual_root)
    reports: dict[str, dict[str, Any]] = {}
    max_workers = max(1, min(parallel_workers, len(VARIANTS)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_run_variant, name, modes, clean_root, dual_reference, out / name, exe, allow_run, timeout_s): name
            for name, modes in VARIANTS.items()
        }
        for future in as_completed(future_map):
            name = future_map[future]
            try:
                reports[name] = future.result()
            except Exception as exc:  # pragma: no cover
                reports[name] = {
                    "variant": name,
                    "summary": {key: None for key in METRICS},
                    "run_report": {"run_status": "failed_exception", "error": str(exc)},
                    "diagnostic_only": True,
                    "not_for_performance_claim": True,
                    "trace_solver_input": False,
                    "final_v23_output_substitution": False,
                    "output_only_correction": False,
                    "bad_epoch_deletion_for_metric": False,
                    "numerical_performance_claim": False,
                }
    classification = classify_bias_scale_variant_matrix(reports)
    matrix = {
        "phase": "N4H4D6",
        "variant_summaries": reports,
        "variant_timeout_seconds": timeout_s,
        "parallel_workers": max_workers,
        **classification,
    }
    (out / "BIAS_SCALE_VARIANT_MATRIX_REPORT.json").write_text(
        json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return matrix
