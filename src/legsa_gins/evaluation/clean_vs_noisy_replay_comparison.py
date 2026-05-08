"""Compare clean status-yaw replay with noisy historical dual_final_v23 evidence.

中文说明：本模块只比较 clean/noisy baseline replay provenance 与指标；不把
noisy artifact 写成 clean nominal，也不生成 proposed solver 性能结论。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.actual_vs_replay_yaw_path import compare_input_yaw_paths, compare_nav_yaw_paths


NOISY_N4H2D_FRESH_REPLAY_SUMMARY = {
    "horizontal_rmse_m": 0.3460851160719829,
    "up_rmse_m": 0.7940342899951961,
    "yaw_rmse_deg": 1.979182806966782,
    "roll_rmse_deg": 1.0200759961634018,
    "pitch_rmse_deg": 1.522164831263277,
}


def _write_json(path: str | Path, data: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def classify_clean_replay_parity(summary: dict[str, Any]) -> str:
    """Classify clean replay status without relaxing the yaw gate."""

    horizontal = summary.get("horizontal_rmse_m")
    up = summary.get("up_rmse_m")
    yaw = summary.get("yaw_rmse_deg")
    if not isinstance(horizontal, (int, float)) or not isinstance(up, (int, float)) or not isinstance(yaw, (int, float)):
        return "evidence_missing"
    if float(horizontal) > 2.0 or float(up) > 3.0:
        return "failed_position_or_up"
    if float(yaw) <= 2.0:
        return "passed"
    if float(yaw) <= 2.2:
        return "near_gate"
    return "failed_yaw"


def compare_clean_vs_noisy_replay(
    *,
    clean_summary: dict[str, Any],
    noisy_summary: dict[str, Any] | None = None,
    clean_input_gnss: str | Path | None = None,
    noisy_input_gnss: str | Path | None = None,
    clean_nav: str | Path | None = None,
    noisy_nav: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Compare metrics and optional input/NAV yaw paths for clean vs noisy evidence."""

    noisy = dict(noisy_summary or NOISY_N4H2D_FRESH_REPLAY_SUMMARY)
    input_report = (
        compare_input_yaw_paths(noisy_input_gnss, clean_input_gnss)
        if clean_input_gnss is not None and noisy_input_gnss is not None
        else {"input_yaw_diff_rmse_deg": None, "evidence_status": "evidence_missing"}
    )
    nav_report = (
        compare_nav_yaw_paths(noisy_nav, clean_nav)
        if clean_nav is not None and noisy_nav is not None
        else {"nav_yaw_diff_rmse_deg": None, "evidence_status": "evidence_missing"}
    )

    def delta(metric: str) -> float | None:
        clean = clean_summary.get(metric)
        old = noisy.get(metric)
        if isinstance(clean, (int, float)) and isinstance(old, (int, float)):
            return float(clean) - float(old)
        return None

    status = classify_clean_replay_parity(clean_summary)
    report = {
        "phase": "N4H2G",
        "clean_vs_noisy_input_yaw_diff_rmse_deg": input_report.get("input_yaw_diff_rmse_deg"),
        "clean_vs_noisy_nav_yaw_diff_rmse_deg": nav_report.get("nav_yaw_diff_rmse_deg"),
        "input_yaw_path_report": input_report,
        "nav_yaw_path_report": nav_report,
        "noisy_summary": noisy,
        "clean_summary": clean_summary,
        "metric_delta_horizontal": delta("horizontal_rmse_m"),
        "metric_delta_up": delta("up_rmse_m"),
        "metric_delta_yaw": delta("yaw_rmse_deg"),
        "metric_delta_roll": delta("roll_rmse_deg"),
        "metric_delta_pitch": delta("pitch_rmse_deg"),
        "clean_replay_gate_pass": status == "passed",
        "clean_replay_yaw_gate_pass": isinstance(clean_summary.get("yaw_rmse_deg"), (int, float))
        and float(clean_summary["yaw_rmse_deg"]) <= 2.0,
        "clean_replay_parity_status": status,
        "noisy_artifact_has_gaussian_yaw_noise": True,
        "clean_input_has_synthetic_yaw_noise": False,
        "noisy_artifact_clean_nominal_claim_allowed": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    if output_dir is not None:
        _write_json(Path(output_dir) / "CLEAN_VS_NOISY_REPLAY_COMPARISON_REPORT.json", report)
    return report
