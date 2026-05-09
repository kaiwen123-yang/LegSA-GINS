"""Metric namespace classifier for N4H4R3C parity-vs-absolute audits.

中文说明：本模块只拆分评价指标命名空间，不修改 solver，不调参，不删除 epoch。
port-vs-final_v23 NAV parity 不是 absolute performance。
"""

from __future__ import annotations

from enum import Enum
import json
from pathlib import Path
from typing import Any


class MetricNamespace(str, Enum):
    PORT_VS_FINAL_V23_NAV_PARITY = "port_vs_final_v23_nav_parity"
    PORT_VS_TRACE_ABSOLUTE = "port_vs_trace_absolute"
    FINAL_V23_VS_TRACE_ABSOLUTE = "final_v23_vs_trace_absolute"
    EXTERNAL_CLEAN_KFGINS_VS_TRACE_ABSOLUTE = "external_clean_kfgins_vs_trace_absolute"
    PORT_VS_GNSS_MEASUREMENT_SANITY = "port_vs_gnss_measurement_sanity"
    WRITER_COPY_GUARD = "writer_copy_guard"
    INVALID_REFERENCE_LEAKAGE = "invalid/reference_leakage"
    EVIDENCE_MISSING = "evidence_missing"


ABSOLUTE_NAMESPACES = {
    MetricNamespace.PORT_VS_TRACE_ABSOLUTE.value,
    MetricNamespace.FINAL_V23_VS_TRACE_ABSOLUTE.value,
    MetricNamespace.EXTERNAL_CLEAN_KFGINS_VS_TRACE_ABSOLUTE.value,
}


def _load_report(metric_report_or_path: Any) -> dict[str, Any]:
    if isinstance(metric_report_or_path, dict):
        return metric_report_or_path
    if isinstance(metric_report_or_path, (str, Path)):
        path = Path(metric_report_or_path)
        if path.exists() and path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {"raw_path": str(path), "evidence_status": "json_decode_failed"}
            return loaded if isinstance(loaded, dict) else {"loaded_value": loaded}
        return {"raw_path": str(metric_report_or_path)}
    return {"loaded_value": metric_report_or_path}


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for key, item in value.items():
            strings.append(str(key))
            strings.extend(_string_values(item))
        return strings
    if isinstance(value, (list, tuple, set)):
        strings = []
        for item in value:
            strings.extend(_string_values(item))
        return strings
    if value is None:
        return []
    return [str(value)]


def _text(value: Any) -> str:
    return " ".join(_string_values(value)).lower()


def _field_text(report: dict[str, Any], names: list[str]) -> str:
    values: list[Any] = []
    for name in names:
        if name in report:
            values.append(report[name])
    return _text(values)


def _existing_namespace(report: dict[str, Any]) -> str | None:
    value = report.get("namespace") or report.get("metric_namespace")
    if isinstance(value, MetricNamespace):
        return value.value
    if isinstance(value, str):
        return value
    return None


def _infer_solver_role(report: dict[str, Any], namespace: str) -> str:
    explicit = report.get("solver_output_role") or report.get("estimate_role") or report.get("nav_role") or report.get("role")
    if isinstance(explicit, str) and explicit:
        return explicit
    if namespace == MetricNamespace.FINAL_V23_VS_TRACE_ABSOLUTE.value:
        return "final_v23_nav"
    if namespace == MetricNamespace.EXTERNAL_CLEAN_KFGINS_VS_TRACE_ABSOLUTE.value:
        return "external_clean_kfgins_nav"
    if namespace == MetricNamespace.PORT_VS_FINAL_V23_NAV_PARITY.value:
        return "port_nav"
    if namespace == MetricNamespace.PORT_VS_TRACE_ABSOLUTE.value:
        return "port_nav"
    return "evidence_missing"


def _infer_reference_role(report: dict[str, Any], namespace: str) -> str:
    explicit = report.get("reference_role") or report.get("evaluation_reference_role")
    if isinstance(explicit, str) and explicit:
        return explicit
    if namespace == MetricNamespace.PORT_VS_FINAL_V23_NAV_PARITY.value:
        return "dual_final_v23_nav_eval_only"
    if namespace in ABSOLUTE_NAMESPACES:
        return "trace_reference_trajectory_eval_only"
    if namespace == MetricNamespace.PORT_VS_GNSS_MEASUREMENT_SANITY.value:
        return "clean_gnss_measurement_sanity"
    if namespace == MetricNamespace.WRITER_COPY_GUARD.value:
        return "writer_source_guard"
    if namespace == MetricNamespace.INVALID_REFERENCE_LEAKAGE.value:
        return "reference_built_from_port_output"
    return "evidence_missing"


def _infer_namespace(report: dict[str, Any]) -> str:
    existing = _existing_namespace(report)
    if existing in {item.value for item in MetricNamespace}:
        return existing

    all_text = _text(report)
    reference_text = _field_text(
        report,
        [
            "reference_file",
            "reference_path",
            "reference_role",
            "reference_source",
            "evaluation_reference_files",
            "evaluation_reference_role",
            "reference_kind",
        ],
    )
    solver_text = _field_text(report, ["solver_output_role", "estimate_role", "nav_role", "role", "estimate_path"])

    leakage_flags = [
        "reference_built_from_port_output",
        "reference_reconstruction_depends_on_port_output",
        "port_output_reference",
    ]
    if any(report.get(flag) is True for flag in leakage_flags):
        return MetricNamespace.INVALID_REFERENCE_LEAKAGE.value
    if "reference built from port output" in all_text or "port output reference" in all_text:
        return MetricNamespace.INVALID_REFERENCE_LEAKAGE.value

    if "writer_copy_guard" in all_text or "writer copy guard" in all_text:
        return MetricNamespace.WRITER_COPY_GUARD.value

    if (
        "clean_gnss" in reference_text
        or "clean gnss" in reference_text
        or ".gnss" in reference_text
        or "gnss measurement" in reference_text
    ):
        return MetricNamespace.PORT_VS_GNSS_MEASUREMENT_SANITY.value

    if (
        "dual_final_v23" in reference_text
        or "dual final_v23" in reference_text
        or "dual_finalv23" in reference_text
        or ("kf_gins_navresult.nav" in reference_text and "trace" not in reference_text)
    ):
        return MetricNamespace.PORT_VS_FINAL_V23_NAV_PARITY.value

    if "trace" in reference_text or "reference trajectory" in reference_text or "evaluation-only reference" in reference_text:
        if "external_clean" in solver_text or "external clean" in solver_text or "kfgins" in solver_text:
            return MetricNamespace.EXTERNAL_CLEAN_KFGINS_VS_TRACE_ABSOLUTE.value
        if "final_v23" in solver_text or "finalv23" in solver_text or "dual" in solver_text:
            return MetricNamespace.FINAL_V23_VS_TRACE_ABSOLUTE.value
        return MetricNamespace.PORT_VS_TRACE_ABSOLUTE.value

    return MetricNamespace.EVIDENCE_MISSING.value


def classify_metric_namespace(metric_report_or_path: Any) -> dict[str, Any]:
    """Classify a metric report into a comparable namespace."""

    report = _load_report(metric_report_or_path)
    namespace = _infer_namespace(report)
    solver_output_role = _infer_solver_role(report, namespace)
    reference_role = _infer_reference_role(report, namespace)
    comparable_to_port_finalv23_parity = namespace == MetricNamespace.PORT_VS_FINAL_V23_NAV_PARITY.value
    comparable_to_absolute = namespace in ABSOLUTE_NAMESPACES

    if namespace == MetricNamespace.PORT_VS_FINAL_V23_NAV_PARITY.value:
        misuse_warning = "parity_metric_not_absolute_performance"
    elif namespace == MetricNamespace.INVALID_REFERENCE_LEAKAGE.value:
        misuse_warning = "reference_leakage_invalid_metric"
    elif namespace == MetricNamespace.EVIDENCE_MISSING.value:
        misuse_warning = "metric_namespace_evidence_missing"
    else:
        misuse_warning = None

    return {
        "namespace": namespace,
        "solver_output_role": solver_output_role,
        "reference_role": reference_role,
        "comparable_to_external_clean_absolute": comparable_to_absolute,
        "comparable_to_final_v23_absolute": comparable_to_absolute,
        "comparable_to_port_finalv23_parity": comparable_to_port_finalv23_parity,
        "misuse_warning": misuse_warning,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "no_outperform_final_v23_claim": True,
    }
