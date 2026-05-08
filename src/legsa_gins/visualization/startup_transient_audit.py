"""Startup transient audit for N4H2F visual review.

中文说明：本模块只审计 fresh replay error_series 开头瞬态，不删 epoch，
不裁剪指标，不做 output-only correction。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


WINDOWS_DEFAULT = [1, 2, 5, 10, 20, 30, 60]


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _rmse(values: list[float]) -> float | None:
    if not values:
        return None
    return math.sqrt(sum(value * value for value in values) / len(values))


def _max_abs(values: list[float]) -> float | None:
    return max((abs(value) for value in values), default=None)


def _load_error_series(path: str | Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            timestamp = raw.get("timestamp") or raw.get("time") or raw.get("aligned_time")
            if timestamp is None:
                continue
            row = {
                "timestamp": _as_float(timestamp),
                "horizontal_error_m": _as_float(raw.get("horizontal_error_m")),
                "up_error_m": _as_float(raw.get("up_error_m") or raw.get("error_u") or raw.get("du")),
                "yaw_error_deg": _as_float(raw.get("yaw_error_deg") or raw.get("yaw_err_deg")),
                "roll_error_deg": _as_float(raw.get("roll_error_deg")),
                "pitch_error_deg": _as_float(raw.get("pitch_error_deg")),
            }
            rows.append(row)
    rows.sort(key=lambda item: item["timestamp"])
    return rows


def _load_summary(path: str | Path) -> dict[str, Any]:
    candidate = Path(path)
    if not candidate.exists():
        return {"evidence_status": "evidence_missing"}
    return json.loads(candidate.read_text(encoding="utf-8"))


def _metrics(rows: list[dict[str, float]]) -> dict[str, Any]:
    horizontal = [row["horizontal_error_m"] for row in rows]
    up = [row["up_error_m"] for row in rows]
    yaw = [row["yaw_error_deg"] for row in rows]
    roll = [row["roll_error_deg"] for row in rows]
    pitch = [row["pitch_error_deg"] for row in rows]
    return {
        "count": len(rows),
        "horizontal_rmse_m": _rmse(horizontal),
        "horizontal_max_m": max(horizontal, default=None),
        "up_rmse_m": _rmse(up),
        "up_max_abs_m": _max_abs(up),
        "yaw_rmse_deg": _rmse(yaw),
        "yaw_max_abs_deg": _max_abs(yaw),
        "roll_rmse_deg": _rmse(roll),
        "roll_max_abs_deg": _max_abs(roll),
        "pitch_rmse_deg": _rmse(pitch),
        "pitch_max_abs_deg": _max_abs(pitch),
    }


def _global_max(rows: list[dict[str, float]], key: str, *, absolute: bool) -> dict[str, Any]:
    if not rows:
        return {"time": None, "value": None}
    best = max(rows, key=lambda row: abs(row[key]) if absolute else row[key])
    return {"time": best["timestamp"], "value": best[key]}


def _max_jump(rows: list[dict[str, float]], key: str) -> float | None:
    if len(rows) < 2:
        return None
    return max(abs(rows[index][key] - rows[index - 1][key]) for index in range(1, len(rows)))


def analyze_startup_transient(
    error_series_csv: str | Path,
    summary_json: str | Path,
    *,
    windows: list[int] | None = None,
) -> dict[str, Any]:
    """Analyze first-window transient without deleting or cropping epochs."""

    rows = _load_error_series(error_series_csv)
    summary = _load_summary(summary_json)
    windows = windows or WINDOWS_DEFAULT
    start_time = rows[0]["timestamp"] if rows else None
    window_reports: dict[str, Any] = {}
    for window in windows:
        if start_time is None:
            selected: list[dict[str, float]] = []
        else:
            selected = [row for row in rows if row["timestamp"] - start_time <= float(window)]
        window_reports[f"first_{window}s"] = _metrics(selected)

    first_10 = window_reports.get("first_10s", {})
    yaw_jump = _max_jump(rows, "yaw_error_deg")
    startup_visible = bool(
        _as_float(first_10.get("up_max_abs_m")) > 1.5
        or _as_float(first_10.get("roll_max_abs_deg")) > 3.0
        or _as_float(first_10.get("pitch_max_abs_deg")) > 3.0
    )
    within_gate = bool(_as_float(first_10.get("up_max_abs_m")) <= 3.0 and not (yaw_jump and yaw_jump > 90.0))
    report = {
        "phase": "N4H2F",
        "startup_transient_audit_status": "computed" if rows else "evidence_missing",
        "error_series_count": len(rows),
        "summary_snapshot": summary,
        "windows": window_reports,
        "global_extrema": {
            "max_horizontal_error": _global_max(rows, "horizontal_error_m", absolute=False),
            "max_up_error_abs": _global_max(rows, "up_error_m", absolute=True),
            "max_yaw_error_abs": _global_max(rows, "yaw_error_deg", absolute=True),
            "max_roll_error_abs": _global_max(rows, "roll_error_deg", absolute=True),
            "max_pitch_error_abs": _global_max(rows, "pitch_error_deg", absolute=True),
        },
        "max_consecutive_jump": {
            "horizontal_error_m": _max_jump(rows, "horizontal_error_m"),
            "up_error_m": _max_jump(rows, "up_error_m"),
            "yaw_error_deg": yaw_jump,
            "roll_error_deg": _max_jump(rows, "roll_error_deg"),
            "pitch_error_deg": _max_jump(rows, "pitch_error_deg"),
        },
        "startup_transient_visible": startup_visible,
        "startup_transient_within_gate": within_gate,
        "convergence_region_annotation_recommended": True,
        "deletion_or_crop_allowed": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    return report


def write_startup_transient_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def update_visual_case_review_with_audits(case_review_dir: str | Path) -> dict[str, Any]:
    """Rewrite visual_case_review.md/json with any available N4H2F audit reports."""

    directory = Path(case_review_dir)
    existing_review = _load_json(directory / "visual_case_review.json")
    startup = _load_json(directory / "STARTUP_TRANSIENT_AUDIT_REPORT.json")
    yaw_std = _load_json(directory / "YAW_STD_SOURCE_AUDIT_REPORT.json")
    provenance = _load_json(directory / "PROCESS_DATA_NOISE_PROVENANCE_REPORT.json")
    variant = _load_json(directory / "ACTUAL_INPUT_YAW_VARIANT_MATCH_REPORT.json")
    metrics = existing_review.get("fresh_replay_metrics", {})
    gates = existing_review.get("target_gates", {})
    figure_list = existing_review.get("figure_list", [])
    recommended_action = "manual_review_then_merge_PR15_if_no_new_visual_issue"
    status = variant.get("actual_yaw_noise_injection_status")
    if status in {"likely_gaussian_1p5_injected", "likely_gaussian_plus_legacy_outlier"}:
        recommended_action = "manual_review_with_yaw_noise_provenance_caveat_before_N4H3"
    combined = {
        "phase": "N4H2F",
        "fresh_replay_metrics": metrics,
        "target_gates": gates,
        "figure_list": figure_list,
        "startup_transient_audit": startup,
        "yaw_std_source_audit": yaw_std,
        "process_data_noise_provenance": provenance,
        "actual_input_yaw_variant_match": variant,
        "visual_validation_ready_for_human_review": True,
        "recommended_action": recommended_action,
        "manual_review_required": True,
        "manual_visual_review_required": True,
        "solver_output_changed": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    (directory / "visual_case_review.json").write_text(
        json.dumps(combined, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    first_10 = (startup.get("windows") or {}).get("first_10s", {})
    yaw_obs = (yaw_std.get("observation_yaw_std") or {})
    lines = [
        "# N4H2F visual case review appendix",
        "",
        "This review keeps the N4H2E visual bundle diagnostic and adds startup/yaw provenance caveats.",
        "",
        "## Startup Transient Audit",
        "",
        f"- first_10s_up_max_abs_m: {first_10.get('up_max_abs_m')}",
        f"- first_10s_yaw_max_abs_deg: {first_10.get('yaw_max_abs_deg')}",
        f"- first_10s_roll_max_abs_deg: {first_10.get('roll_max_abs_deg')}",
        f"- first_10s_pitch_max_abs_deg: {first_10.get('pitch_max_abs_deg')}",
        f"- startup_transient_visible: {startup.get('startup_transient_visible')}",
        f"- startup_transient_within_gate: {startup.get('startup_transient_within_gate')}",
        "- deletion_or_crop_allowed: false",
        "",
        "## Yaw STD Source Audit",
        "",
        f"- observation_yaw_std_mean_deg: {yaw_obs.get('mean')}",
        f"- observation_yaw_std_fixed_1p5: {yaw_obs.get('is_fixed_1p5')}",
        "- yaw_std_source: process_data_input",
        f"- yaw_std_is_measurement_std_not_noise_injection: {yaw_std.get('yaw_std_is_measurement_std_not_noise_injection')}",
        f"- state_yaw_std_available: {bool(yaw_std.get('state_yaw_std'))}",
        "- yaw_std_not_used_to_relax_gate: true",
        "",
        "## Process Data Noise Provenance",
        "",
        f"- process_data_defaults: {(provenance.get('process_data_audit') or {}).get('defaults')}",
        f"- run_final_mainline_role: {(provenance.get('run_final_mainline_audit') or {}).get('script_role')}",
        f"- best_matching_yaw_variant: {variant.get('best_matching_variant')}",
        f"- actual_yaw_noise_injection_status: {variant.get('actual_yaw_noise_injection_status')}",
        f"- nominal_clean_claim_allowed: {variant.get('nominal_clean_claim_allowed')}",
        f"- evidence_missing: {variant.get('evidence_missing')}",
        "",
        "## Merge Readiness",
        "",
        "- visual_validation_ready_for_human_review: true",
        f"- recommended_action: {recommended_action}",
        "- manual_visual_review_required: true",
        "- solver_output_changed: false",
        "- trace_solver_input: false",
        "- output_only_correction: false",
        "- numerical_performance_claim: false",
        "",
        "## Metrics",
        "",
        f"- horizontal_rmse_m: {metrics.get('horizontal_rmse_m')}",
        f"- up_rmse_m: {metrics.get('up_rmse_m')}",
        f"- yaw_rmse_deg: {metrics.get('yaw_rmse_deg')}",
        f"- roll_rmse_deg: {metrics.get('roll_rmse_deg')}",
        f"- pitch_rmse_deg: {metrics.get('pitch_rmse_deg')}",
        "",
        "## Figures",
        "",
    ]
    lines.extend(f"- {figure}" for figure in figure_list)
    (directory / "visual_case_review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return combined
