"""Summary staleness checks for N4H2D replay mapping audit.

中文说明：只读取已有 replay summary/report 元数据；不修改 solver output，不复制
artifacts，不把 trace/reference 作为 solver input。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.error_series_parity import load_official_summary


def _line_count(path: Path | None) -> int | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return None


def _read_text(path: Path) -> str:
    if not path.exists() or not path.is_file() or path.stat().st_size > 2_000_000:
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _reference_source_hint(paths: list[Path]) -> str:
    text = "\n".join(_read_text(path) for path in paths if path.exists())
    lower = text.lower()
    if "dual_final_v23" in lower or "dual official" in lower:
        return "dual_official_reference_reported"
    if "trace" in lower:
        return "trace_reference_reported"
    if "reference_role" in lower:
        return "reference_role_present"
    return "evidence_missing"


def audit_summary_staleness(
    summary_path: str | Path | None,
    nav_path: str | Path | None,
    report_paths: list[str | Path] | None = None,
) -> dict[str, Any]:
    """Audit whether an old replay summary may be stale or mapped to another reference."""

    summary = Path(summary_path) if summary_path else None
    nav = Path(nav_path) if nav_path else None
    reports = [Path(path) for path in (report_paths or []) if path]
    exists = bool(summary and summary.exists())
    size = summary.stat().st_size if exists and summary else None
    summary_mtime = summary.stat().st_mtime if exists and summary else None
    nav_mtime = nav.stat().st_mtime if nav and nav.exists() else None
    report_mtimes = [path.stat().st_mtime for path in reports if path.exists()]
    newest_dependency_mtime = max([value for value in [nav_mtime, *report_mtimes] if value is not None], default=None)
    older_than_nav_or_report = bool(
        summary_mtime is not None
        and newest_dependency_mtime is not None
        and summary_mtime < newest_dependency_mtime
    )
    parsed_summary = load_official_summary(summary) if exists and summary else {"evidence_status": "evidence_missing"}
    summary_count = parsed_summary.get("count") or parsed_summary.get("aligned_count")
    nav_count = _line_count(nav)
    count_aligns = bool(
        isinstance(summary_count, (int, float))
        and isinstance(nav_count, int)
        and abs(int(summary_count) - int(nav_count)) <= max(1, int(nav_count * 0.02))
    )
    reference_hint = _reference_source_hint(reports + ([summary] if summary else []))
    references_different_source = reference_hint == "trace_reference_reported"
    if not exists:
        status = "evidence_missing"
    elif older_than_nav_or_report or references_different_source:
        status = "stale_or_wrong_reference_suspected"
    else:
        status = "no_staleness_evidence"
    return {
        "phase": "N4H2D",
        "summary_exists": exists,
        "summary_size_bytes": size,
        "summary_mtime": summary_mtime,
        "nav_mtime": nav_mtime,
        "newest_report_mtime": max(report_mtimes) if report_mtimes else None,
        "summary_older_than_nav_or_report": older_than_nav_or_report,
        "summary_count": summary_count,
        "nav_count": nav_count,
        "summary_count_aligns_with_nav_count": count_aligns,
        "summary_reference_source_hint": reference_hint,
        "summary_references_different_reference_source": references_different_source,
        "summary_generated_before_dual_artifact_intake": None,
        "summary_staleness_status": status,
        "evidence_status": "parsed" if exists else "evidence_missing",
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }
