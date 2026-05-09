"""Compare N4H4R3C parity and absolute metric namespaces.

中文说明：本模块只比较已经生成的评价报告命名空间，防止把
port-vs-final_v23 parity 误写成 absolute performance；不修改 solver。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.legsa_v23_port_metric_namespace import (
    MetricNamespace,
    classify_metric_namespace,
)


def _load(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    path = Path(value)
    if path.exists() and path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _metric(report: dict[str, Any], key: str) -> float | None:
    value = report.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _available(report: dict[str, Any]) -> bool:
    if not report:
        return False
    status = report.get("absolute_trace_evaluation_status") or report.get("evidence_status")
    if status == "evidence_missing":
        return False
    return isinstance(report.get("aligned_count", report.get("count")), int) and int(report.get("aligned_count", report.get("count"))) > 0


def _close(port_abs: dict[str, Any], final_abs: dict[str, Any]) -> bool:
    thresholds = {
        "horizontal_rmse_m": 0.5,
        "up_rmse_m": 0.8,
        "yaw_rmse_deg": 0.5,
        "roll_rmse_deg": 0.5,
        "pitch_rmse_deg": 0.5,
    }
    for key, threshold in thresholds.items():
        a = _metric(port_abs, key)
        b = _metric(final_abs, key)
        if a is None or b is None or abs(a - b) > threshold:
            return False
    return True


def _external_absolute_baseline(external_clean_baseline: dict[str, Any]) -> dict[str, Any]:
    baseline = dict(external_clean_baseline)
    baseline.setdefault("namespace", MetricNamespace.EXTERNAL_CLEAN_KFGINS_VS_TRACE_ABSOLUTE.value)
    baseline.setdefault("solver_output_role", "external_clean_kfgins_nav")
    baseline.setdefault("reference_role", "trace_reference_trajectory_eval_only")
    return baseline


def _detect_r3b_misuse(
    port_vs_finalv23: dict[str, Any],
    external_clean_baseline: dict[str, Any],
) -> bool:
    parity_ns = classify_metric_namespace(port_vs_finalv23)["namespace"]
    external_ns = classify_metric_namespace(external_clean_baseline)["namespace"]
    if external_clean_baseline.get("compared_metric_namespace") == MetricNamespace.PORT_VS_FINAL_V23_NAV_PARITY.value:
        return True
    if external_clean_baseline.get("r3b_external_closeness_failed") is not None:
        return parity_ns == MetricNamespace.PORT_VS_FINAL_V23_NAV_PARITY.value
    return bool(
        parity_ns == MetricNamespace.PORT_VS_FINAL_V23_NAV_PARITY.value
        and external_ns == MetricNamespace.EXTERNAL_CLEAN_KFGINS_VS_TRACE_ABSOLUTE.value
        and external_clean_baseline.get("used_for_r3b_external_closeness_check", False)
    )


def compare_parity_and_absolute(
    port_vs_finalv23: dict[str, Any] | str | Path,
    port_vs_trace: dict[str, Any] | str | Path | None,
    finalv23_vs_trace: dict[str, Any] | str | Path | None,
    external_clean_baseline: dict[str, Any] | str | Path | None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Compare A/B/C metric namespaces without mixing parity and absolute metrics."""

    parity = _load(port_vs_finalv23)
    port_abs = _load(port_vs_trace)
    final_abs = _load(finalv23_vs_trace)
    external = _external_absolute_baseline(_load(external_clean_baseline) if external_clean_baseline else {})

    parity_to_finalv23_small = bool(parity.get("parity_small"))
    port_absolute_available = _available(port_abs)
    finalv23_absolute_available = _available(final_abs)
    finalv23_absolute_reproduced = bool(final_abs.get("official_summary_reproduced"))
    port_absolute_close = bool(
        port_absolute_available
        and finalv23_absolute_available
        and finalv23_absolute_reproduced
        and _close(port_abs, final_abs)
    )
    external_clean_comparison_valid = bool(
        port_absolute_available
        and classify_metric_namespace(port_abs)["namespace"] == MetricNamespace.PORT_VS_TRACE_ABSOLUTE.value
        and classify_metric_namespace(external)["namespace"]
        == MetricNamespace.EXTERNAL_CLEAN_KFGINS_VS_TRACE_ABSOLUTE.value
    )
    r3b_misuse = _detect_r3b_misuse(parity, external)

    if not parity_to_finalv23_small:
        corrected = "port_parity_failed"
    elif not port_absolute_available or not finalv23_absolute_available:
        corrected = "parity_to_finalv23_passed_absolute_missing"
    elif port_absolute_close:
        corrected = "backbone_parity_passed"
    else:
        corrected = "evaluator_or_reference_mismatch"

    blocking_issues: list[str] = []
    if corrected == "parity_to_finalv23_passed_absolute_missing":
        blocking_issues.append("absolute_trace_evaluation_missing")
    elif corrected == "evaluator_or_reference_mismatch":
        blocking_issues.append("port_absolute_not_close_to_final_v23_absolute")
    elif corrected == "port_parity_failed":
        blocking_issues.append("port_vs_final_v23_nav_parity_failed")
    if r3b_misuse:
        blocking_issues.append("r3b_external_closeness_metric_namespace_misuse")

    report = {
        "phase": "N4H4R3C",
        "parity_to_finalv23_small": parity_to_finalv23_small,
        "port_absolute_available": port_absolute_available,
        "finalv23_absolute_available": finalv23_absolute_available,
        "finalv23_absolute_reproduced": finalv23_absolute_reproduced,
        "port_absolute_close_to_finalv23_absolute": port_absolute_close,
        "external_clean_comparison_valid": external_clean_comparison_valid,
        "r3b_external_closeness_comparison_valid": bool(external_clean_comparison_valid and not r3b_misuse),
        "r3b_external_closeness_misuse_detected": r3b_misuse,
        "corrected_parity_status": corrected,
        "blocking_issues": blocking_issues,
        "metric_namespaces": {
            "A": classify_metric_namespace(parity)["namespace"],
            "B": classify_metric_namespace(port_abs)["namespace"] if port_abs else MetricNamespace.EVIDENCE_MISSING.value,
            "C": classify_metric_namespace(final_abs)["namespace"] if final_abs else MetricNamespace.EVIDENCE_MISSING.value,
            "external_clean": classify_metric_namespace(external)["namespace"],
        },
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "no_outperform_final_v23_claim": True,
    }
    if output_dir is not None:
        _write_json(Path(output_dir) / "PORT_PARITY_VS_ABSOLUTE_COMPARISON_REPORT.json", report)
    return report
