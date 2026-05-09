"""Absolute trace/reference evaluation for N4H4R3C.

中文说明：trace/reference 只用于 evaluation，不进入 solver；本模块不修改输出、
不做 output-only correction、不删 epoch。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.legsa_v23_port_final_v23_parity_eval import load_nav_rows
from legsa_gins.evaluation.legsa_v23_port_metric_namespace import MetricNamespace
from legsa_gins.evaluation.trajectory_metrics import load_trace_reference, summary_metrics
from legsa_gins.evaluation.yaw_evaluator_parity import compute_errors_for_transforms, normalize_nav_rows


DUAL_FINAL_V23_OFFICIAL_SUMMARY = {
    "horizontal_rmse_m": 0.3527090758847838,
    "up_rmse_m": 0.8178104428183638,
    "yaw_rmse_deg": 1.813898158169119,
    "roll_rmse_deg": 1.024555363681649,
    "pitch_rmse_deg": 1.5238205432000829,
}


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_trace_rows(trace_path_or_reference: str | Path | list[dict[str, Any]] | dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    if isinstance(trace_path_or_reference, list):
        return trace_path_or_reference, "provided_reference_rows"
    if isinstance(trace_path_or_reference, dict):
        rows = trace_path_or_reference.get("reference_rows") or trace_path_or_reference.get("trace_rows") or []
        source = str(trace_path_or_reference.get("reference_source", "provided_reference_bundle"))
        if isinstance(rows, (str, Path)):
            loaded_rows, loaded_source = _load_trace_rows(rows)
            return loaded_rows, f"{source}:{loaded_source}"
        return list(rows), source
    path = Path(trace_path_or_reference)
    if not path.exists():
        return [], "evidence_missing"
    if path.suffix.lower() == ".json":
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return [], "json_decode_failed"
        if isinstance(loaded, dict):
            rows = loaded.get("reference_rows") or loaded.get("trace_rows") or loaded.get("rows") or []
            return list(rows), "json_reference_rows"
        if isinstance(loaded, list):
            return loaded, "json_list_reference_rows"
        return [], "json_reference_rows_missing"
    try:
        return load_trace_reference(path), "trace_csv"
    except (KeyError, ValueError):
        return load_nav_rows(path), "nav_like_trace_csv"


def _namespace_for_role(role: str) -> str:
    lowered = role.lower()
    if "external" in lowered or "kfgins" in lowered:
        return MetricNamespace.EXTERNAL_CLEAN_KFGINS_VS_TRACE_ABSOLUTE.value
    if "final" in lowered or "dual" in lowered:
        return MetricNamespace.FINAL_V23_VS_TRACE_ABSOLUTE.value
    return MetricNamespace.PORT_VS_TRACE_ABSOLUTE.value


def _output_name_for_role(role: str) -> str:
    namespace = _namespace_for_role(role)
    if namespace == MetricNamespace.FINAL_V23_VS_TRACE_ABSOLUTE.value:
        return "FINALV23_VS_TRACE_ABSOLUTE_REPRO_REPORT.json"
    if namespace == MetricNamespace.EXTERNAL_CLEAN_KFGINS_VS_TRACE_ABSOLUTE.value:
        return "EXTERNAL_CLEAN_KFGINS_VS_TRACE_ABSOLUTE_REPORT.json"
    return "PORT_VS_TRACE_ABSOLUTE_REPORT.json"


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1))
    return ordered[index]


def _add_available_stats(summary: dict[str, Any], errors: list[dict[str, float]]) -> None:
    up_abs = [abs(row["up_error_m"]) for row in errors]
    roll_abs = [abs(row["roll_error_deg"]) for row in errors]
    pitch_abs = [abs(row["pitch_error_deg"]) for row in errors]
    yaw_abs = [abs(row["yaw_error_deg"]) for row in errors]
    horizontal = [abs(row["horizontal_error_m"]) for row in errors]
    count = len(errors)
    summary.update(
        {
            "up_p95_m": _p95(up_abs),
            "roll_p95_deg": _p95(roll_abs),
            "pitch_p95_deg": _p95(pitch_abs),
            "up_max_m": max(up_abs) if up_abs else None,
            "yaw_max_deg": max(yaw_abs) if yaw_abs else None,
            "roll_max_deg": max(roll_abs) if roll_abs else None,
            "pitch_max_deg": max(pitch_abs) if pitch_abs else None,
            "horizontal_2m_pass_ratio": (sum(value <= 2.0 for value in horizontal) / count) if count else None,
            "up_3m_pass_ratio": (sum(value <= 3.0 for value in up_abs) / count) if count else None,
            "yaw_2deg_pass_ratio": (sum(value <= 2.0 for value in yaw_abs) / count) if count else None,
            "roll_1_6deg_pass_ratio": (sum(value <= 1.6 for value in roll_abs) / count) if count else None,
            "pitch_1_6deg_pass_ratio": (sum(value <= 1.6 for value in pitch_abs) / count) if count else None,
        }
    )


def _official_reproduced(summary: dict[str, Any]) -> bool:
    thresholds = {
        "horizontal_rmse_m": 0.05,
        "up_rmse_m": 0.08,
        "yaw_rmse_deg": 0.25,
        "roll_rmse_deg": 0.12,
        "pitch_rmse_deg": 0.12,
    }
    for key, threshold in thresholds.items():
        value = summary.get(key)
        expected = DUAL_FINAL_V23_OFFICIAL_SUMMARY[key]
        if not isinstance(value, (int, float)) or abs(float(value) - expected) > threshold:
            return False
    return True


def _missing_report(output_dir: str | Path, role: str, trace_source: str) -> dict[str, Any]:
    namespace = _namespace_for_role(role)
    report = {
        "phase": "N4H4R3C",
        "namespace": namespace,
        "solver_output_role": role,
        "reference_role": "trace_reference_trajectory_eval_only",
        "absolute_trace_evaluation_status": "evidence_missing",
        "trace_reference_source": trace_source,
        "absolute_performance_metric": namespace != MetricNamespace.PORT_VS_FINAL_V23_NAV_PARITY.value,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "no_outperform_final_v23_claim": True,
    }
    _write_json(Path(output_dir) / _output_name_for_role(role), report)
    return report


def evaluate_nav_vs_trace(
    nav_path: str | Path | list[dict[str, Any]],
    std_path: str | Path | None,
    trace_path_or_reference: str | Path | list[dict[str, Any]] | dict[str, Any] | None,
    output_dir: str | Path,
    role: str,
    *,
    yaw_profile_name: str = "direct_identity",
    est_transform: str = "identity",
    ref_transform: str = "identity",
) -> dict[str, Any]:
    """Evaluate one NAV stream against trace/reference as an absolute metric."""

    if trace_path_or_reference is None:
        return _missing_report(output_dir, role, "evidence_missing")
    trace_rows, trace_source = _load_trace_rows(trace_path_or_reference)
    if not trace_rows:
        return _missing_report(output_dir, role, trace_source)

    nav_rows = load_nav_rows(nav_path)
    errors = compute_errors_for_transforms(
        nav_rows,
        trace_rows,
        est_transform=est_transform,
        ref_transform=ref_transform,
        max_dt=0.05,
    )
    summary = summary_metrics(errors)
    _add_available_stats(summary, errors)
    namespace = _namespace_for_role(role)
    final_role = namespace == MetricNamespace.FINAL_V23_VS_TRACE_ABSOLUTE.value
    official_reproduced = _official_reproduced(summary) if final_role else None
    normalized = normalize_nav_rows(nav_rows)
    times = [row["timestamp"] for row in normalized]
    report = {
        "phase": "N4H4R3C",
        "namespace": namespace,
        "solver_output_role": role,
        "reference_role": "trace_reference_trajectory_eval_only",
        "trace_reference_source": trace_source,
        "std_available": bool(std_path and Path(std_path).exists()),
        "nav_count": len(nav_rows),
        "trace_reference_count": len(trace_rows),
        "count": summary["count"],
        "aligned_count": summary["count"],
        "first_time": min(times) if times else None,
        "last_time": max(times) if times else None,
        "horizontal_rmse_m": summary.get("horizontal_rmse_m"),
        "up_rmse_m": summary.get("up_rmse_m"),
        "yaw_rmse_deg": summary.get("yaw_rmse_deg"),
        "roll_rmse_deg": summary.get("roll_rmse_deg"),
        "pitch_rmse_deg": summary.get("pitch_rmse_deg"),
        "horizontal_p95_m": summary.get("horizontal_p95_m"),
        "up_p95_m": summary.get("up_p95_m"),
        "yaw_p95_deg": summary.get("yaw_p95_deg"),
        "roll_p95_deg": summary.get("roll_p95_deg"),
        "pitch_p95_deg": summary.get("pitch_p95_deg"),
        "horizontal_max_m": summary.get("horizontal_max_m"),
        "up_max_m": summary.get("up_max_m"),
        "yaw_max_deg": summary.get("yaw_max_deg"),
        "roll_max_deg": summary.get("roll_max_deg"),
        "pitch_max_deg": summary.get("pitch_max_deg"),
        "horizontal_2m_pass_ratio": summary.get("horizontal_2m_pass_ratio"),
        "up_3m_pass_ratio": summary.get("up_3m_pass_ratio"),
        "yaw_2deg_pass_ratio": summary.get("yaw_2deg_pass_ratio"),
        "roll_1_6deg_pass_ratio": summary.get("roll_1_6deg_pass_ratio"),
        "pitch_1_6deg_pass_ratio": summary.get("pitch_1_6deg_pass_ratio"),
        "yaw_profile_name": yaw_profile_name,
        "est_transform": est_transform,
        "ref_transform": ref_transform,
        "absolute_trace_evaluation_status": "available" if summary["count"] else "evidence_missing",
        "absolute_performance_metric": True,
        "official_dual_final_v23_summary_target": DUAL_FINAL_V23_OFFICIAL_SUMMARY if final_role else None,
        "official_summary_reproduced": official_reproduced,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "trace_evaluation_only": True,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "no_outperform_final_v23_claim": True,
    }
    _write_json(Path(output_dir) / _output_name_for_role(role), report)
    return report
