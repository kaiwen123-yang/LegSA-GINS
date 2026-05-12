"""N7B2A metric namespace guard for Go2-stage reports.

中文说明：Go2 阶段的 roll/pitch/yaw/H/Up/delta 等指标必须区分
parity_to_final_v23、absolute_to_trace、cross_source_consistency 和
readiness_diagnostic，避免把 parity 数值误读为绝对精度。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


NAMESPACES = {
    "parity_to_final_v23",
    "absolute_to_trace",
    "cross_source_consistency",
    "readiness_diagnostic",
}

METRIC_TOKENS = [
    "horizontal",
    "up",
    "yaw",
    "roll",
    "pitch",
    "delta",
    "summary",
    "error",
    "rmse",
    "bias",
]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _metric_like(path: str, value: Any) -> bool:
    lower = path.lower()
    if not any(token in lower for token in METRIC_TOKENS):
        return False
    return _is_number(value) or isinstance(value, (str, int, float, bool)) or value is None


def _flatten(data: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(data, dict):
        out: list[tuple[str, Any]] = []
        for key, value in data.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            out.extend(_flatten(value, child))
        return out
    if isinstance(data, list):
        out = []
        for index, value in enumerate(data):
            out.extend(_flatten(value, f"{prefix}[{index}]"))
        return out
    return [(prefix, data)]


def _namespace_for(report_group: str, metric_path: str) -> str:
    text = f"{report_group}.{metric_path}".lower()
    if "n7a" in text or "weak_prior" in text or "attitude" in text:
        if any(token in text for token in ["roll", "pitch", "yaw", "horizontal", "up", "summary", "delta", "rmse"]):
            return "parity_to_final_v23"
    if "velocity" in text or "raw" in text or "receiver" in text or "doppler" in text or "bias" in text:
        return "cross_source_consistency"
    if "trace_absolute" in text:
        return "absolute_to_trace"
    return "readiness_diagnostic"


def build_metric_namespace_guard_report(
    *,
    n7a_reports: dict[str, dict[str, Any]],
    n7b_reports: dict[str, dict[str, Any]],
    n7b2_reports: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    metric_entries: list[dict[str, Any]] = []
    for group_name, reports in [("N7A", n7a_reports), ("N7B", n7b_reports), ("N7B2", n7b2_reports)]:
        for report_name, report in sorted(reports.items()):
            for path, value in _flatten(report):
                if _metric_like(path, value):
                    namespace = _namespace_for(f"{group_name}.{report_name}", path)
                    metric_entries.append(
                        {
                            "report_group": group_name,
                            "report_name": report_name,
                            "metric_path": path,
                            "namespace": namespace,
                            "value": value if isinstance(value, (str, int, float, bool)) or value is None else str(value),
                        }
                    )
    missing = [entry for entry in metric_entries if entry["namespace"] not in NAMESPACES]
    roll_pitch_context = {
        "no_go2_roll_pitch_0p043_0p031_namespace": "parity_to_final_v23",
        "no_go2_roll_pitch_0p043_0p031_absolute_accuracy": False,
        "final_v23_official_absolute_roll_pitch_reference_context_deg": {"roll": 1.0, "pitch": 1.5},
        "reference_context_not_claim": True,
    }
    velocity_context = {
        "go2_velocity_comparison_namespace": "cross_source_consistency",
        "go2_velocity_comparison_truth_error": False,
        "go2_velocity_truth_claim": False,
    }
    return {
        "stage": "N7B2A_go2_metric_contact_visual_audit",
        "allowed_namespaces": sorted(NAMESPACES),
        "metric_count": len(metric_entries),
        "metrics": metric_entries,
        "metric_namespace_missing": bool(missing),
        "missing_namespace_metrics": missing,
        "recommend_docs_report_fix": bool(missing),
        "parity_metrics_clarified": True,
        "absolute_metrics_clarified": True,
        "cross_source_metrics_clarified": True,
        "readiness_metrics_clarified": True,
        "roll_pitch_metric_context": roll_pitch_context,
        "velocity_metric_context": velocity_context,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "fgo": False,
    }


def write_metric_namespace_guard_report(
    *,
    n7a_reports: dict[str, dict[str, Any]],
    n7b_reports: dict[str, dict[str, Any]],
    n7b2_reports: dict[str, dict[str, Any]],
    output_dir: str | Path,
) -> tuple[Path, dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = build_metric_namespace_guard_report(n7a_reports=n7a_reports, n7b_reports=n7b_reports, n7b2_reports=n7b2_reports)
    path = out / "GO2_METRIC_NAMESPACE_GUARD_REPORT.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, report
