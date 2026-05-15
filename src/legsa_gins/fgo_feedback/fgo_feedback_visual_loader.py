"""N8H visual-validation input loader.

The loader reads N8G runtime-only artifacts and emits a path-safe manifest for
tracked review code. Absolute runtime paths are kept in memory only.

中文说明：只读取 N8G 运行期产物，写出的 manifest 不记录本地绝对路径。
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REQUIRED_N8G_REPORTS = [
    "SLIDING_WINDOW_MANAGER_REPORT.json",
    "FGO_FEEDBACK_OBSERVATION_BUILD_REPORT.json",
    "FGO_FEEDBACK_COVARIANCE_POLICY_REPORT.json",
    "FGO_FEEDBACK_GATE_REPORT.json",
    "N8G_FGO_FEEDBACK_VARIANT_SUMMARIES.json",
    "N8G_FGO_FEEDBACK_COMPARISON_REPORT.json",
    "N8G_FGO_FEEDBACK_EVALUATION_REPORT.json",
    "N8G_FGO_FEEDBACK_EKF_DECISION_REPORT.json",
]

BASELINE_VARIANT = "ekf_baseline_no_fgo_feedback"
PRIMARY_FEEDBACK_VARIANT = "fgo_feedback_horizontal_velocity_attitude"
DIAGNOSTIC_PVA_VARIANT = "fgo_feedback_position_velocity_attitude_diagnostic"
REJECT_ALL_VARIANT = "fgo_feedback_reject_all_sanity"

N8G_VARIANT_ORDER = [
    BASELINE_VARIANT,
    "fgo_feedback_velocity_attitude",
    PRIMARY_FEEDBACK_VARIANT,
    DIAGNOSTIC_PVA_VARIANT,
    "fgo_feedback_velocity_only",
    "fgo_feedback_attitude_only",
    REJECT_ALL_VARIANT,
]


@dataclass
class N8HVisualInputs:
    n8g_root: Path
    reports: dict[str, dict[str, Any]]
    figure_manifest: dict[str, Any]
    variant_summaries: dict[str, dict[str, Any]]
    evaluation_by_variant: dict[str, dict[str, Any]]
    run_manifests: dict[str, dict[str, Any]]
    observations_by_variant: dict[str, list[dict[str, Any]]]
    update_trace_by_variant: dict[str, list[dict[str, Any]]]
    eval_nav_by_variant: dict[str, list[dict[str, Any]]]
    manifest: dict[str, Any]


def read_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def truthy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def stats(values: Iterable[float]) -> dict[str, float]:
    clean = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not clean:
        return {"p50": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "p50": _percentile(clean, 0.50),
        "p95": _percentile(clean, 0.95),
        "max": clean[-1],
    }


def _percentile(ordered: list[float], q: float) -> float:
    index = int(round((len(ordered) - 1) * max(0.0, min(1.0, q))))
    return ordered[index]


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append({key: _coerce_cell(value) for key, value in row.items()})
    return rows


def _coerce_cell(value: Any) -> Any:
    if value is None:
        return value
    text = str(value).strip()
    if text == "":
        return ""
    try:
        parsed = float(text)
    except ValueError:
        return text
    return parsed if math.isfinite(parsed) else text


def load_n8h_visual_inputs(n8g_root: str | Path) -> N8HVisualInputs:
    root = Path(n8g_root)
    reports = {name: read_json(root / name) for name in REQUIRED_N8G_REPORTS}
    figure_manifest = read_json(root / "N8G_FIGURE_MANIFEST.json")
    variant_report = reports["N8G_FGO_FEEDBACK_VARIANT_SUMMARIES.json"]
    evaluation_report = reports["N8G_FGO_FEEDBACK_EVALUATION_REPORT.json"]

    summaries = {
        item.get("variant_id", ""): item
        for item in variant_report.get("variants", [])
        if item.get("variant_id")
    }
    variant_ids = [variant for variant in N8G_VARIANT_ORDER if variant in summaries]
    for variant in summaries:
        if variant not in variant_ids:
            variant_ids.append(variant)

    evaluation_by_variant = {
        item.get("variant_id", ""): item
        for item in evaluation_report.get("variant_results", [])
        if item.get("variant_id")
    }
    run_manifests: dict[str, dict[str, Any]] = {}
    observations_by_variant: dict[str, list[dict[str, Any]]] = {}
    update_trace_by_variant: dict[str, list[dict[str, Any]]] = {}
    eval_nav_by_variant: dict[str, list[dict[str, Any]]] = {}
    for variant_id in variant_ids:
        variant_root = root / "variants" / variant_id
        run_root = variant_root / "run"
        run_manifests[variant_id] = read_json(run_root / "RUN_MANIFEST.json")
        observations_by_variant[variant_id] = read_csv_rows(variant_root / "FGO_FEEDBACK_OBSERVATIONS.csv")
        update_trace_by_variant[variant_id] = read_csv_rows(run_root / "FGO_FEEDBACK_UPDATE_TRACE.csv")
        eval_nav_by_variant[variant_id] = read_csv_rows(run_root / "EVAL_NAV.csv")

    manifest = build_visual_input_manifest(
        reports=reports,
        figure_manifest=figure_manifest,
        variant_summaries=summaries,
        run_manifests=run_manifests,
        observations_by_variant=observations_by_variant,
        update_trace_by_variant=update_trace_by_variant,
        eval_nav_by_variant=eval_nav_by_variant,
    )
    return N8HVisualInputs(
        n8g_root=root,
        reports=reports,
        figure_manifest=figure_manifest,
        variant_summaries=summaries,
        evaluation_by_variant=evaluation_by_variant,
        run_manifests=run_manifests,
        observations_by_variant=observations_by_variant,
        update_trace_by_variant=update_trace_by_variant,
        eval_nav_by_variant=eval_nav_by_variant,
        manifest=manifest,
    )


def build_visual_input_manifest(
    *,
    reports: dict[str, dict[str, Any]],
    figure_manifest: dict[str, Any],
    variant_summaries: dict[str, dict[str, Any]],
    run_manifests: dict[str, dict[str, Any]],
    observations_by_variant: dict[str, list[dict[str, Any]]],
    update_trace_by_variant: dict[str, list[dict[str, Any]]],
    eval_nav_by_variant: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    decision = reports.get("N8G_FGO_FEEDBACK_EKF_DECISION_REPORT.json", {})
    window = reports.get("SLIDING_WINDOW_MANAGER_REPORT.json", {})
    variant_report = reports.get("N8G_FGO_FEEDBACK_VARIANT_SUMMARIES.json", {})
    found_reports = {name: bool(payload) for name, payload in reports.items()}
    false_flags = _all_boundary_flags_false([decision, variant_report, *run_manifests.values()])
    baseline_summary = variant_summaries.get(BASELINE_VARIANT, {})
    primary_summary = variant_summaries.get(PRIMARY_FEEDBACK_VARIANT, {})
    diagnostic_summary = variant_summaries.get(DIAGNOSTIC_PVA_VARIANT, {})
    reject_summary = variant_summaries.get(REJECT_ALL_VARIANT, {})
    nav_eval_found = bool(eval_nav_by_variant.get(BASELINE_VARIANT)) and bool(eval_nav_by_variant.get(PRIMARY_FEEDBACK_VARIANT))
    return {
        "stage": "N8H",
        "source_stage": "N8G",
        "n8g_reports_found": found_reports,
        "all_required_n8g_reports_found": all(found_reports.values()),
        "feedback_observations_found": any(bool(rows) for rows in observations_by_variant.values()),
        "baseline_variant_found": bool(baseline_summary),
        "primary_feedback_variant_found": bool(primary_summary),
        "diagnostic_pva_variant_found": bool(diagnostic_summary),
        "reject_all_sanity_found": bool(reject_summary),
        "nav_eval_timeseries_found": nav_eval_found,
        "update_trace_timeseries_found": any(bool(rows) for rows in update_trace_by_variant.values()),
        "n8g_figure_manifest_found": bool(figure_manifest),
        "no_feedback_boundary_confirmed": baseline_summary.get("fgo_feedback_enabled") is False,
        "output_substitution_false": false_flags["fgo_feedback_output_substitution"],
        "direct_nav_override_false": false_flags["fgo_feedback_direct_nav_override"],
        "no_future_data_true": bool(window.get("no_future_data_verified")) and decision.get("fgo_feedback_no_future_data") is True,
        "trace_solver_input_false": false_flags["trace_solver_input"],
        "final_v23_solver_input_false": false_flags["final_v23_output_solver_input"],
        "paper_performance_claim_false": false_flags["paper_performance_claim"],
        "runtime_path_role": "n8g_runtime_root",
        "absolute_path_recorded": False,
        "rerun_missing_timeseries_requested": False,
        "rerun_missing_timeseries_performed": False,
    }


def _all_boundary_flags_false(payloads: list[dict[str, Any]]) -> dict[str, bool]:
    checks = {
        "fgo_feedback_output_substitution": True,
        "fgo_feedback_direct_nav_override": True,
        "trace_solver_input": True,
        "final_v23_output_solver_input": True,
        "paper_performance_claim": True,
    }
    for payload in payloads:
        if not payload:
            continue
        for key in checks:
            if payload.get(key) is True:
                checks[key] = False
    return checks


def write_visual_input_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    write_json(path, manifest)


def time_range(rows: list[dict[str, Any]], key: str = "time") -> list[float]:
    values = [safe_float(row.get(key)) for row in rows if key in row]
    return [min(values), max(values)] if values else []


def is_time_monotonic(rows: list[dict[str, Any]], key: str = "time") -> bool:
    values = [safe_float(row.get(key)) for row in rows if key in row]
    return all(left <= right for left, right in zip(values, values[1:]))
