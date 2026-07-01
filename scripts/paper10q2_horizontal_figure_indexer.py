#!/usr/bin/env python3
"""Figure-organization helpers for PAPER10Q2.

Q2 indexes existing horizontal-comparison figures and plans later organization.
It does not copy figure binaries into Git and does not generate new plots.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def figure_review_rows(method_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in method_rows:
        method_id = str(row.get("method_id", ""))
        if not method_id:
            continue
        recommendation = str(row.get("paper_location_recommendation", "diagnostic_only"))
        rows.append(
            {
                "figure_id": f"HC_{method_id}_SUMMARY_INDEX",
                "method_id": method_id,
                "source_stage": str(row.get("source_stage", "")),
                "existing_figure_index_available": str(row.get("render_QA_available", "false")),
                "normal_folder_plan": f"normal_condition/{method_id}/",
                "degraded_folder_plan": f"degraded_experiment/{method_id}/",
                "claim_level": recommendation,
                "paper_candidate": "main_text" if recommendation == "main_text_candidate" else recommendation,
                "needs_replot": str(row.get("replot_required", "false")),
                "notes": "Index/plan only; no figure binary copied by Q2.",
            }
        )
    return rows


def normal_organization_rows(method_rows: list[dict[str, Any]], windows_root_available: bool, g_root_available: bool) -> list[dict[str, str]]:
    return [
        {
            "method_id": str(row.get("method_id", "")),
            "planned_relative_folder": f"normal_condition/{row.get('method_id', '')}/",
            "required_files": "README_SUMMARY_CN.md;METHOD_EVIDENCE_TABLE.csv;FIGURE_INDEX.csv;CLAIM_BOUNDARY.md;PAPER_WRITABLE_TEXT_CN.md;FORBIDDEN_TEXT_CN.md",
            "windows_export_available": str(windows_root_available).lower(),
            "g_drive_target_available": str(g_root_available).lower(),
            "copy_status": "PLAN_ONLY_NO_COPY_IN_Q2",
        }
        for row in method_rows
        if row.get("method_id")
    ]


def degraded_organization_rows(method_rows: list[dict[str, Any]], windows_root_available: bool, g_root_available: bool) -> list[dict[str, str]]:
    return [
        {
            "method_id": str(row.get("method_id", "")),
            "planned_relative_folder": f"degraded_experiment/{row.get('method_id', '')}/",
            "required_files": "README_SUMMARY_CN.md;METHOD_EVIDENCE_TABLE.csv;FIGURE_INDEX.csv;CLAIM_BOUNDARY.md;PAPER_WRITABLE_TEXT_CN.md;FORBIDDEN_TEXT_CN.md",
            "windows_export_available": str(windows_root_available).lower(),
            "g_drive_target_available": str(g_root_available).lower(),
            "copy_status": "PLAN_ONLY_NO_COPY_IN_Q2",
        }
        for row in method_rows
        if row.get("method_id")
    ]


def replot_rows(method_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in method_rows:
        if str(row.get("replot_required", "false")).lower() == "true" or str(row.get("render_QA_available", "false")).lower() != "true":
            out.append(
                {
                    "method_id": str(row.get("method_id", "")),
                    "source_stage": str(row.get("source_stage", "")),
                    "replot_required": str(row.get("replot_required", "true")),
                    "reason": str(row.get("notes", "Missing render QA or needs paper-format figure.")),
                    "rerun_solver_required": "false",
                }
            )
    return out


def figure_package_summary(
    *,
    method_count: int,
    main_count: int,
    appendix_count: int,
    diagnostic_count: int,
    windows_root: Path,
    g_root: Path,
) -> str:
    return "\n".join(
        [
            "# HORIZONTAL_FIGURE_PACKAGE_SUMMARY",
            "",
            f"- Method/evidence rows indexed: {method_count}.",
            f"- Main-text candidates: {main_count}.",
            f"- Appendix candidates: {appendix_count}.",
            f"- Diagnostic-only candidates: {diagnostic_count}.",
            f"- Windows organization target available: {windows_root.exists()}.",
            f"- G-drive figure organization target available: {g_root.exists()}.",
            "- Q2 generated figure indexes and organization plans only; no figure binaries were copied into Git.",
        ]
    )
