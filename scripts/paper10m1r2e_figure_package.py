#!/usr/bin/env python3
"""Figure classification helpers for PAPER10M1R2E.

The M1R2E package does not copy generated figure binaries into Git. It reviews
existing figure indexes and render-QA rows, then assigns each figure to a paper
location candidate: main text, appendix, diagnostic-only, or rejected/needs
replot.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable


MAIN_TEXT_IDS = {
    "method_mode_horizontal_rmse_boxplot",
    "legsa_full_vs_basic_horizontal_delta_by_case",
    "legsa_full_vs_strong_horizontal_delta_by_case",
    "legsa_full_vs_no_qm_horizontal_delta_by_case",
    "qm_state_count_by_degradation_type",
    "source_aware_update_count_by_source",
    "source_aware_r_scale_by_degradation_type",
    "D30_D41_yaw_family_rmse_heatmap",
    "D60_multisource_bad_optimistic_then_recovery_representative_panel",
    "D60_multisource_bad_optimistic_then_recovery_ablation_panel",
    "module_contribution_horizontal_delta_bar",
    "module_contribution_by_family_heatmap",
    "module_help_hurt_same_order_count_bar",
}

DIAGNOSTIC_IDS = {
    "go2_joint_removed_delta_by_case",
    "fgo_feedback_removed_delta_by_case",
    "clean_yaw_rmse_original_m1r2c_vs_r1",
    "bad_a1_accept_downweight_reject_by_degradation_type",
    "missing_output_contract_panel",
}

APPENDIX_KEYWORDS = (
    "heatmap",
    "boxplot",
    "runtime",
    "terminal_status",
    "forbidden_input",
    "raw_doppler",
    "go2_roll_pitch",
    "go2_horizontal_velocity",
    "yaw_wrap",
    "clean_yaw",
    "D01_",
    "D18_",
    "D24_",
    "D35_",
    "D50_",
)


def classify_figure(figure_id: str, render_status: str = "PASS") -> tuple[str, str, str]:
    """Return (bucket, paper_location, rationale)."""

    if render_status != "PASS":
        return (
            "rejected_or_needs_replot",
            "replot_required",
            "Render QA did not pass; do not use without repair.",
        )
    if figure_id in DIAGNOSTIC_IDS:
        return (
            "diagnostic_only",
            "diagnostic_only",
            "Figure is useful for audit or alias/no-effect explanation, not a paper claim.",
        )
    if figure_id in MAIN_TEXT_IDS:
        return (
            "main_text_candidate",
            "main_text_candidate_with_replot",
            "High-level method/module or representative sanity figure suitable for final formatting.",
        )
    if any(key in figure_id for key in APPENDIX_KEYWORDS):
        return (
            "appendix_candidate",
            "appendix",
            "Detailed metric, runtime, or family-level evidence is better suited to appendix.",
        )
    return (
        "appendix_candidate",
        "appendix_or_review_pack",
        "Review figure is valid but not essential for main-text narrative.",
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def classify_figure_index(stage_id: str, index_path: Path, render_qa_path: Path) -> list[dict[str, str]]:
    render = {row["figure_id"]: row for row in read_csv(render_qa_path)}
    rows: list[dict[str, str]] = []
    for row in read_csv(index_path):
        qa = render.get(row["figure_id"], {})
        status = qa.get("render_status", "MISSING_RENDER_QA")
        bucket, location, rationale = classify_figure(row["figure_id"], status)
        rows.append(
            {
                "source_stage": stage_id,
                "figure_id": row.get("figure_id", ""),
                "plot_type": row.get("plot_type", ""),
                "case_count": row.get("case_count", ""),
                "row_count": row.get("row_count", ""),
                "source_png": row.get("figure_path_png", ""),
                "source_pdf": row.get("figure_path_pdf", ""),
                "render_status": status,
                "has_nan_inf": qa.get("has_nan_inf", row.get("has_nan_inf", "")),
                "local_path_leak": qa.get("local_path_leak", ""),
                "m1r2e_bucket": bucket,
                "paper_location_recommendation": location,
                "required_replot": "true" if "candidate" in bucket else "false",
                "rationale": rationale,
            }
        )
    return rows
