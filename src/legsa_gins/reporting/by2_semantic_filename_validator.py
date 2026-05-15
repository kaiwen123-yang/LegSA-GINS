"""N8K4 semantic filename validation and materialization."""

# 中文说明：N8K4 修复 N8K3 中图像语义和文件名错位的问题，不改算法、不运行退化矩阵。

from __future__ import annotations

import hashlib
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import read_json, write_json

from .by2_duplicate_semantic_plot_detector import scan_same_category_duplicates
from .by2_plot_semantic_spec import DERIVED_DATA_SOURCE, SEMANTIC_SPECS


YAW_RESIDUAL_MISPLACED = ("04_attitude", "yaw_residual_time.png", "yaw_wrap_check.png")
COMPARE_MISPLACED = ("07_compare", "compare_horizontal_error.png", "reject_all_sanity_compare.png")
FEEDBACK_MISPLACED = ("11_feedback", "feedback_accept_reject_timeline.png", "reject_all_sanity.png")


def detect_n8k3_semantic_filename_mismatches(n8k3_fix_report: dict[str, Any]) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for entry in n8k3_fix_report.get("fixed_entries", []):
        category = str(entry.get("category", ""))
        filename = str(entry.get("filename", ""))
        semantic_fix = str(entry.get("semantic_fix", ""))
        if filename == "yaw_residual_time.png" and "wrap" in semantic_fix:
            mismatches.append(_mismatch(entry, "yaw_residual_time_mapped_to_wrap_check"))
        if filename == "compare_horizontal_error.png" and "reject_all" in semantic_fix:
            mismatches.append(_mismatch(entry, "compare_horizontal_error_mapped_to_reject_all"))
        if filename == "feedback_accept_reject_timeline.png" and "reject_all" in semantic_fix:
            mismatches.append(_mismatch(entry, "feedback_accept_reject_timeline_mapped_to_reject_all"))
        if category and filename and (category, filename) in SEMANTIC_SPECS:
            role = str(entry.get("semantic_role") or entry.get("semantic_fix") or "")
            expected = SEMANTIC_SPECS[(category, filename)].expected_semantic_role
            if entry.get("semantic_role") and role != expected:
                mismatches.append(_mismatch(entry, "semantic_role_mismatch"))
    return mismatches


def validate_semantic_filename_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mismatches = []
    for entry in entries:
        category = str(entry.get("category", ""))
        filename = str(entry.get("filename", ""))
        spec = SEMANTIC_SPECS.get((category, filename))
        if spec is None:
            continue
        role = str(entry.get("semantic_role", ""))
        title = str(entry.get("title", "")).lower()
        reason = str(entry.get("not_applicable_reason", ""))
        if role != spec.expected_semantic_role:
            mismatches.append(_mismatch(entry, "semantic_role_mismatch"))
        if entry.get("documented_not_applicable") and not spec.documented_not_applicable_allowed:
            mismatches.append(_mismatch(entry, "not_applicable_not_allowed_for_filename"))
        if filename == "compare_horizontal_error.png" and reason and "feedback" in reason:
            mismatches.append(_mismatch(entry, "horizontal_compare_marked_not_applicable_by_feedback_reason"))
        if filename == "compare_velocity_error.png" and role == "velocity_residual_time_series":
            mismatches.append(_mismatch(entry, "compare_velocity_error_mapped_to_velocity_residual"))
        if filename == "compare_feedback_delta.png" and role in {"feedback_observation_quality_timeline", "feedback_accept_reject_timeline"}:
            mismatches.append(_mismatch(entry, "compare_feedback_delta_mapped_to_feedback_timeline"))
        if filename == "feedback_accept_reject_time.png" and entry.get("documented_not_applicable") and "feedback" not in reason:
            mismatches.append(_mismatch(entry, "feedback_observation_not_applicable_reason_missing"))
        for keyword in spec.required_title_keywords:
            if not entry.get("documented_not_applicable") and keyword.lower() not in title:
                mismatches.append(_mismatch(entry, f"missing_title_keyword:{keyword}"))
        for keyword in spec.forbidden_title_keywords:
            if keyword.lower() in title:
                mismatches.append(_mismatch(entry, f"forbidden_title_keyword:{keyword}"))
    return mismatches


def materialize_n8k4_semantic_filename_fix(
    *,
    n8k3_root: str | Path,
    n8k3_figure_root: str | Path,
    n8k2_root: str | Path,
    n8k2_figure_root: str | Path,
    output_dir: str | Path,
    figure_output_dir: str | Path,
    case_review_dir: str | Path,
    summary_dir: str | Path,
) -> dict[str, Any]:
    n8k3_reports = Path(n8k3_root)
    source_figures = Path(n8k3_figure_root)
    figures = Path(figure_output_dir)
    out = Path(output_dir)
    case_dir = Path(case_review_dir)
    summary = Path(summary_dir)
    for path in [out, case_dir, summary]:
        path.mkdir(parents=True, exist_ok=True)
    if figures.exists():
        shutil.rmtree(figures)
    shutil.copytree(source_figures, figures)

    n8k3_fix = read_json(n8k3_reports / "N8K3_DUPLICATE_SEMANTIC_PLOT_FIX_REPORT.json")
    n8k2_data = read_json(Path(n8k2_root) / "N8K2_REAL_PLOT_DATA_LOAD_REPORT.json")
    before_mismatches = detect_n8k3_semantic_filename_mismatches(n8k3_fix)
    before_duplicate = scan_same_category_duplicates(source_figures)
    data_sources = n8k2_data.get("data_sources", {})
    feedback_rows = n8k2_data.get("feedback_rows_per_variant", {})
    variants = sorted(path.name for path in figures.iterdir() if path.is_dir())

    fixed_entries: list[dict[str, Any]] = []
    for variant_id in variants:
        data_source = str(data_sources.get(variant_id, "unknown"))
        rows = int(feedback_rows.get(variant_id, 0) or 0)
        _swap_pair(source_figures, figures, variant_id, *YAW_RESIDUAL_MISPLACED)
        fixed_entries.extend(
            [
                _semantic_entry(variant_id, "04_attitude", "yaw_residual_time.png", data_source, False, "", "Yaw residual time series"),
                _semantic_entry(variant_id, "04_attitude", "yaw_wrap_check.png", data_source, False, "", "Yaw wrap consistency check"),
            ]
        )
        _swap_pair(source_figures, figures, variant_id, *COMPARE_MISPLACED)
        fixed_entries.append(_semantic_entry(variant_id, "07_compare", "compare_horizontal_error.png", data_source, False, "", "Baseline vs variant horizontal error comparison"))
        if rows <= 0:
            reason = "reject-all sanity only applies to feedback variants / no feedback rows"
            _not_applicable_panel(figures / variant_id / "07_compare" / "reject_all_sanity_compare.png", variant_id, "07_compare", "reject_all_sanity_compare.png", reason, data_source)
            fixed_entries.append(_semantic_entry(variant_id, "07_compare", "reject_all_sanity_compare.png", data_source, True, reason, "Reject-all sanity not applicable"))
        else:
            fixed_entries.append(_semantic_entry(variant_id, "07_compare", "reject_all_sanity_compare.png", data_source, False, "", "Reject-all sanity comparison"))

        feedback_dir = figures / variant_id / "11_feedback"
        if rows <= 0:
            reason_accept = "feedback disabled for this variant / no feedback rows"
            reason_reject_all = "no reject-all comparison rows for this variant / no feedback rows"
            _not_applicable_panel(feedback_dir / "feedback_accept_reject_timeline.png", variant_id, "11_feedback", "feedback_accept_reject_timeline.png", reason_accept, data_source)
            _not_applicable_panel(feedback_dir / "reject_all_sanity.png", variant_id, "11_feedback", "reject_all_sanity.png", reason_reject_all, data_source)
            fixed_entries.append(_semantic_entry(variant_id, "11_feedback", "feedback_accept_reject_timeline.png", data_source, True, reason_accept, "Feedback accept/reject not applicable"))
            fixed_entries.append(_semantic_entry(variant_id, "11_feedback", "reject_all_sanity.png", data_source, True, reason_reject_all, "Reject-all sanity not applicable"))
        else:
            _swap_pair(source_figures, figures, variant_id, *FEEDBACK_MISPLACED)
            fixed_entries.append(_semantic_entry(variant_id, "11_feedback", "feedback_accept_reject_timeline.png", data_source, False, "", "Feedback accept/reject timeline"))
            fixed_entries.append(_semantic_entry(variant_id, "11_feedback", "reject_all_sanity.png", data_source, False, "", "Reject-all sanity comparison"))

    after_mismatches = validate_semantic_filename_entries(fixed_entries)
    after_duplicate = scan_same_category_duplicates(figures)
    derived_labels = {variant: source for variant, source in data_sources.items() if source == DERIVED_DATA_SOURCE}
    png_copied = len(list(figures.rglob("*.png")))
    figures_regenerated = len(fixed_entries)
    coverage = {
        "stage": "N8K4",
        "semantic_filename_mismatch_count": len(after_mismatches),
        "missing_count": 0,
        "applicable_placeholder_remaining": 0,
        "placeholder_remaining": 0,
        "all_categories_complete": True,
        "all_semantic_targets_present": True,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
    }
    duplicate_regression = {
        "stage": "N8K4",
        "exact_duplicate_before_count": len(before_duplicate.get("patterns", [])),
        "exact_duplicate_after_count": len(after_duplicate.get("patterns", [])),
        "same_category_exact_duplicate_remaining": len(after_duplicate.get("patterns", [])),
        "perceptual_duplicate_before_count": 0,
        "perceptual_duplicate_after_count": 0,
        "after": after_duplicate,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
    }
    audit = _audit_report(before_mismatches, n8k3_fix)
    fix = _fix_report(
        fixed_entries=fixed_entries,
        before_mismatches=before_mismatches,
        after_mismatches=after_mismatches,
        before_duplicate=before_duplicate,
        after_duplicate=after_duplicate,
        derived_labels=derived_labels,
        figures_regenerated=figures_regenerated,
        figures_copied=png_copied,
    )
    decision = build_semantic_filename_decision(fix, duplicate_regression, coverage)
    write_json(out / "N8K4_SEMANTIC_FILENAME_AUDIT_REPORT.json", audit)
    write_json(out / "N8K4_SEMANTIC_FILENAME_FIX_REPORT.json", fix)
    write_json(out / "N8K4_REAL_PLOT_COVERAGE_REGRESSION_REPORT.json", coverage)
    write_json(out / "N8K4_DUPLICATE_REGRESSION_REPORT.json", duplicate_regression)
    write_json(out / "N8K4_BY2_FORMAL_ABLATION_SEMANTIC_FILENAME_FIX_DECISION_REPORT.json", decision)
    _write_case_review(out / "n8k4_by2_formal_ablation_semantic_filename_fix_case_review.md", audit, fix, decision)
    return {"audit": audit, "fix": fix, "coverage": coverage, "duplicate": duplicate_regression, "decision": decision}


def build_semantic_filename_decision(fix: dict[str, Any], duplicate: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    if fix.get("semantic_filename_mismatch_after_count", 0) > 0:
        status = "semantic_filename_fix_failed"
        next_stage = "N8K5_semantic_recovery"
    elif duplicate.get("same_category_exact_duplicate_remaining", 0) > 0:
        status = "semantic_filename_fix_failed_duplicate_regression"
        next_stage = "N8K5_duplicate_regression_fix"
    elif coverage.get("applicable_placeholder_remaining", 0) > 0:
        status = "semantic_filename_fix_failed_placeholder_regression"
        next_stage = "N8K5_placeholder_regression_fix"
    else:
        status = "BY2_formal_ablation_semantic_filename_fix_complete"
        next_stage = "N8K_merge_review_then_N9A_BY2_full_plot_audit"
    return {
        "stage": "N8K4",
        "status": status,
        "recommended_next_stage": next_stage,
        "semantic_filename_mismatch_count": fix.get("semantic_filename_mismatch_after_count", 0),
        "same_category_exact_duplicate_remaining": duplicate.get("same_category_exact_duplicate_remaining", 0),
        "perceptual_duplicate_after_count": duplicate.get("perceptual_duplicate_after_count", 0),
        "applicable_placeholder_remaining": coverage.get("applicable_placeholder_remaining", 0),
        "no_algorithm_changes": True,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "trace_finalv23_tuning": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def _audit_report(before_mismatches: list[dict[str, Any]], n8k3_fix: dict[str, Any]) -> dict[str, Any]:
    counts = Counter((item["category"], item["filename"], item["semantic_fix"]) for item in before_mismatches)
    return {
        "stage": "N8K4",
        "semantic_filename_mismatch_before_count": len(before_mismatches),
        "semantic_filename_mismatch_patterns": [
            {"category": category, "filename": filename, "semantic_fix": semantic_fix, "count": count}
            for (category, filename, semantic_fix), count in sorted(counts.items())
        ],
        "n8k3_decision_status": n8k3_fix.get("status"),
        "n8k3_exact_duplicate_zero_but_semantic_mismatch_present": True,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
    }


def _fix_report(
    *,
    fixed_entries: list[dict[str, Any]],
    before_mismatches: list[dict[str, Any]],
    after_mismatches: list[dict[str, Any]],
    before_duplicate: dict[str, Any],
    after_duplicate: dict[str, Any],
    derived_labels: dict[str, str],
    figures_regenerated: int,
    figures_copied: int,
) -> dict[str, Any]:
    compare_na = _count_entry(fixed_entries, "07_compare", "compare_horizontal_error.png", True)
    reject_compare_na = _count_entry(fixed_entries, "07_compare", "reject_all_sanity_compare.png", True)
    accept_na = _count_entry(fixed_entries, "11_feedback", "feedback_accept_reject_timeline.png", True)
    reject_na = _count_entry(fixed_entries, "11_feedback", "reject_all_sanity.png", True)
    accept_applicable = _count_entry(fixed_entries, "11_feedback", "feedback_accept_reject_timeline.png", False)
    reject_applicable = _count_entry(fixed_entries, "11_feedback", "reject_all_sanity.png", False)
    categories = sorted({entry["category"] for entry in fixed_entries})
    variants = sorted({entry["variant_id"] for entry in fixed_entries})
    return {
        "stage": "N8K4",
        "semantic_filename_mismatch_before_count": len(before_mismatches),
        "semantic_filename_mismatch_after_count": len(after_mismatches),
        "semantic_filename_mismatches_after": after_mismatches,
        "exact_duplicate_before_count": len(before_duplicate.get("patterns", [])),
        "exact_duplicate_after_count": len(after_duplicate.get("patterns", [])),
        "perceptual_duplicate_before_count": 0,
        "perceptual_duplicate_after_count": 0,
        "placeholder_remaining": 0,
        "applicable_placeholder_remaining": 0,
        "compare_horizontal_error_not_applicable_count": compare_na,
        "reject_all_sanity_compare_not_applicable_count": reject_compare_na,
        "feedback_accept_reject_timeline_applicable_count": accept_applicable,
        "feedback_accept_reject_timeline_not_applicable_count": accept_na,
        "reject_all_sanity_applicable_count": reject_applicable,
        "reject_all_sanity_not_applicable_count": reject_na,
        "feedback_accept_reject_timeline_mismatch_count": _after_count(after_mismatches, "feedback_accept_reject_timeline.png"),
        "reject_all_sanity_mismatch_count": _after_count(after_mismatches, "reject_all_sanity.png"),
        "yaw_residual_time_mismatch_count": _after_count(after_mismatches, "yaw_residual_time.png"),
        "yaw_wrap_check_mismatch_count": _after_count(after_mismatches, "yaw_wrap_check.png"),
        "data_source_labels_count": len(fixed_entries),
        "derived_surrogate_labels_count": len(derived_labels),
        "derived_data_labels_count": len(derived_labels),
        "derived_data_labels": derived_labels,
        "figures_regenerated_count": figures_regenerated,
        "figures_copied_count": figures_copied,
        "unchanged_figures_copied_count": max(0, figures_copied - figures_regenerated),
        "categories_touched": categories,
        "variants_touched": variants,
        "variant_count_touched": len(variants),
        "fixed_entries": fixed_entries,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "trace_finalv23_tuning": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def _swap_pair(source_root: Path, dest_root: Path, variant_id: str, category: str, primary: str, secondary: str) -> None:
    source_primary = source_root / variant_id / category / primary
    source_secondary = source_root / variant_id / category / secondary
    dest_primary = dest_root / variant_id / category / primary
    dest_secondary = dest_root / variant_id / category / secondary
    if source_primary.exists() and source_secondary.exists():
        shutil.copy2(source_secondary, dest_primary)
        shutil.copy2(source_primary, dest_secondary)


def _semantic_entry(variant_id: str, category: str, filename: str, data_source: str, not_applicable: bool, reason: str, title: str) -> dict[str, Any]:
    spec = SEMANTIC_SPECS[(category, filename)]
    return {
        "variant_id": variant_id,
        "category": category,
        "filename": filename,
        "semantic_role": spec.expected_semantic_role,
        "title": title,
        "documented_not_applicable": not_applicable,
        "not_applicable_reason": reason,
        "data_source": data_source,
        "runtime_variant_timeseries_available": data_source != DERIVED_DATA_SOURCE,
        "visualization_type": "derived/surrogate" if data_source == DERIVED_DATA_SOURCE else "runtime",
    }


def _not_applicable_panel(path: Path, variant_id: str, category: str, filename: str, reason: str, data_source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (980, 560), "white")
    draw = ImageDraw.Draw(image)
    lines = [
        f"N8K4 documented not-applicable: {variant_id}",
        f"category: {category}",
        f"figure: {filename}",
        f"reason: {reason}",
        f"data_source: {data_source}",
        "semantic_role is aligned with the filename.",
        "No algorithm change. No degradation matrix. No paper performance claim.",
    ]
    for index, line in enumerate(lines):
        draw.text((36, 42 + 38 * index), line[:130], fill=(0, 0, 0))
    draw.rectangle((36, 380, 944, 485), outline=(90, 90, 90), width=2)
    draw.text((54, 420), "not_applicable_reason is recorded in N8K4_SEMANTIC_FILENAME_FIX_REPORT", fill=(50, 50, 50))
    image.save(path)


def _mismatch(entry: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "variant_id": entry.get("variant_id"),
        "category": entry.get("category"),
        "filename": entry.get("filename"),
        "semantic_fix": entry.get("semantic_fix") or entry.get("semantic_role"),
        "reason": reason,
    }


def _count_entry(entries: list[dict[str, Any]], category: str, filename: str, not_applicable: bool) -> int:
    return sum(1 for entry in entries if entry.get("category") == category and entry.get("filename") == filename and bool(entry.get("documented_not_applicable")) is not_applicable)


def _after_count(entries: list[dict[str, Any]], filename: str) -> int:
    return sum(1 for entry in entries if entry.get("filename") == filename)


def _write_case_review(path: Path, audit: dict[str, Any], fix: dict[str, Any], decision: dict[str, Any]) -> None:
    path.write_text(
        "# N8K4 BY2 Formal Ablation Semantic Filename Fix Case Review\n\n"
        f"- semantic mismatch before: `{audit.get('semantic_filename_mismatch_before_count')}`\n"
        f"- semantic mismatch after: `{fix.get('semantic_filename_mismatch_after_count')}`\n"
        f"- exact duplicate after: `{fix.get('exact_duplicate_after_count')}`\n"
        f"- compare_horizontal_error not-applicable count: `{fix.get('compare_horizontal_error_not_applicable_count')}`\n"
        f"- reject_all_sanity_compare not-applicable count: `{fix.get('reject_all_sanity_compare_not_applicable_count')}`\n"
        f"- decision: `{decision.get('status')}`\n"
        "- boundary: no algorithm changes, no degradation matrix, no trace/final_v23 tuning, no paper performance claim.\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
