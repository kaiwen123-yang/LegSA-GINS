"""Feedback applicability policy for BY2 formal ablation plots.

中文说明：feedback 绘图是否适用必须由 variant 语义优先决定，不能只看原始
feedback 行数；baseline_no_feedback 的原始行只作为 diagnostic 记录。
"""

from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import read_json, write_json

from .by2_cross_category_duplicate_detector import scan_cross_category_duplicates
from .by2_duplicate_semantic_plot_detector import scan_same_category_duplicates
from .by2_plot_semantic_spec import DERIVED_DATA_SOURCE


A0_VARIANT_ID = "A0_source_backed_ekf_baseline"
BASELINE_NO_FEEDBACK_SOURCE = "baseline_no_feedback"
BASELINE_NO_FEEDBACK_ROLE = "baseline_no_feedback"
RAW_ROWS_IGNORED_REASON = "variant_role_baseline_no_feedback"
BASELINE_NOT_APPLICABLE_REASON = "feedback-specific plot is not applicable to baseline_no_feedback"

FEEDBACK_SPECIFIC_FIGURES = (
    ("06_observation_quality", "feedback_accept_reject_time.png"),
    ("07_compare", "compare_feedback_delta.png"),
    ("07_compare", "reject_all_sanity_compare.png"),
    ("11_feedback", "feedback_window_timeline.png"),
    ("11_feedback", "feedback_accept_reject_timeline.png"),
    ("11_feedback", "feedback_correction_norm.png"),
    ("11_feedback", "feedback_covariance_time.png"),
    ("11_feedback", "feedback_gate_threshold.png"),
    ("11_feedback", "feedback_reject_reason.png"),
    ("11_feedback", "selected_feedback_vs_baseline.png"),
    ("11_feedback", "reject_all_sanity.png"),
)


@dataclass(frozen=True)
class FeedbackApplicability:
    variant_id: str
    variant_role: str
    feedback_applicable_by_spec: bool
    raw_feedback_rows_detected: int
    effective_feedback_rows_for_plotting: int
    feedback_accept_count: int
    feedback_reject_count: int
    is_feedback_applicable: bool
    not_applicable_reason: str
    raw_rows_ignored: bool
    raw_rows_ignored_reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_variant_role(variant_id: str, variant_spec: dict[str, Any]) -> str:
    source = str(variant_spec.get("n8j_source_variant") or "")
    feedback_mode = str(variant_spec.get("feedback_mode") or "none")
    group = str(variant_spec.get("group") or "")
    if source == BASELINE_NO_FEEDBACK_SOURCE:
        return BASELINE_NO_FEEDBACK_ROLE
    if feedback_mode == "none":
        return "no_feedback"
    if "feedback_sanity" in group or "reject_all" in variant_id:
        return "feedback_sanity"
    if "feedback" in feedback_mode or "feedback" in variant_id:
        return "feedback"
    return "non_feedback_ablation"


def get_feedback_applicability(
    variant_id: str,
    variant_spec: dict[str, Any],
    raw_feedback_rows: int | list[Any],
    metrics: dict[str, Any] | None = None,
) -> FeedbackApplicability:
    if not variant_spec:
        raise ValueError(f"missing semantic spec for {variant_id}")
    spec_variant_id = str(variant_spec.get("variant_id") or variant_id)
    if spec_variant_id != variant_id:
        raise ValueError(f"semantic spec variant mismatch: {variant_id} != {spec_variant_id}")
    raw_rows = len(raw_feedback_rows) if isinstance(raw_feedback_rows, list) else int(raw_feedback_rows or 0)
    metric_row = metrics or {}
    accept = int(float(metric_row.get("feedback_accept", 0) or 0))
    reject = int(float(metric_row.get("feedback_reject", 0) or 0))
    role = get_variant_role(variant_id, variant_spec)
    feedback_mode = str(variant_spec.get("feedback_mode") or "none")
    spec_applicable = role in {"feedback", "feedback_sanity"} or feedback_mode != "none"
    if role == BASELINE_NO_FEEDBACK_ROLE:
        return FeedbackApplicability(
            variant_id=variant_id,
            variant_role=role,
            feedback_applicable_by_spec=False,
            raw_feedback_rows_detected=raw_rows,
            effective_feedback_rows_for_plotting=0,
            feedback_accept_count=accept,
            feedback_reject_count=reject,
            is_feedback_applicable=False,
            not_applicable_reason=f"variant_role={BASELINE_NO_FEEDBACK_ROLE}",
            raw_rows_ignored=raw_rows > 0,
            raw_rows_ignored_reason=RAW_ROWS_IGNORED_REASON if raw_rows > 0 else "",
        )
    if spec_applicable and raw_rows > 0:
        return FeedbackApplicability(
            variant_id=variant_id,
            variant_role=role,
            feedback_applicable_by_spec=True,
            raw_feedback_rows_detected=raw_rows,
            effective_feedback_rows_for_plotting=raw_rows,
            feedback_accept_count=accept,
            feedback_reject_count=reject,
            is_feedback_applicable=True,
            not_applicable_reason="",
            raw_rows_ignored=False,
            raw_rows_ignored_reason="",
        )
    reason = "feedback disabled for this variant / no feedback rows"
    if spec_applicable:
        reason = "feedback-specific plot requires feedback rows"
    return FeedbackApplicability(
        variant_id=variant_id,
        variant_role=role,
        feedback_applicable_by_spec=spec_applicable,
        raw_feedback_rows_detected=raw_rows,
        effective_feedback_rows_for_plotting=0,
        feedback_accept_count=accept,
        feedback_reject_count=reject,
        is_feedback_applicable=False,
        not_applicable_reason=reason,
        raw_rows_ignored=False,
        raw_rows_ignored_reason="",
    )


def build_feedback_applicability_map(
    matrix_rows: list[dict[str, Any]],
    raw_feedback_rows_by_variant: dict[str, int],
    metrics_by_variant: dict[str, dict[str, Any]],
) -> dict[str, FeedbackApplicability]:
    result: dict[str, FeedbackApplicability] = {}
    for row in matrix_rows:
        variant_id = str(row.get("variant_id") or "")
        if not variant_id:
            continue
        result[variant_id] = get_feedback_applicability(
            variant_id,
            row,
            raw_feedback_rows_by_variant.get(variant_id, 0),
            metrics_by_variant.get(variant_id, {}),
        )
    return result


def materialize_n8k6_a0_feedback_applicability_fix(
    *,
    n8k5_root: str | Path,
    n8k5_figure_root: str | Path,
    n8k5_case_review_root: str | Path,
    n8k5_summary_root: str | Path,
    plot_audit_root: str | Path,
    output_dir: str | Path,
    figure_output_dir: str | Path,
    case_review_dir: str | Path,
    summary_dir: str | Path,
) -> dict[str, Any]:
    """Copy N8K5 figures and replace A0 feedback-specific plots with NA panels."""
    del n8k5_case_review_root, n8k5_summary_root
    n8k5_reports = Path(n8k5_root)
    source_figures = Path(n8k5_figure_root)
    out = Path(output_dir)
    figures = Path(figure_output_dir)
    case_dir = Path(case_review_dir)
    summary = Path(summary_dir)
    for path in [out, case_dir, summary]:
        path.mkdir(parents=True, exist_ok=True)
    if figures.exists():
        shutil.rmtree(figures)
    shutil.copytree(source_figures, figures)

    plot_root = Path(plot_audit_root)
    n8k_matrix = _read_under_plot_root(plot_root, "N8K_BY2_FORMAL_ABLATION_MATRIX.json")
    n8k_metrics_report = _read_under_plot_root(plot_root, "N8K_BY2_FORMAL_ABLATION_METRICS_REPORT.json")
    n8k2_data_report = _read_n8k2_data_report(plot_root)
    n8k5_decision = read_json(n8k5_reports / "N8K5_BY2_FORMAL_ABLATION_CROSS_CATEGORY_FIX_DECISION_REPORT.json")

    matrix_rows = list(n8k_matrix.get("rows", []))
    metrics_by_variant = {str(row.get("variant_id")): row for row in n8k_metrics_report.get("metrics", [])}
    raw_feedback_rows = {
        str(variant_id): int(value or 0)
        for variant_id, value in n8k2_data_report.get("feedback_rows_per_variant", {}).items()
    }
    before_applicable = {
        variant_id: count > 0
        for variant_id, count in raw_feedback_rows.items()
    }
    applicability = build_feedback_applicability_map(matrix_rows, raw_feedback_rows, metrics_by_variant)
    if A0_VARIANT_ID not in applicability:
        raise ValueError(f"missing {A0_VARIANT_ID} in formal ablation matrix")
    a0 = applicability[A0_VARIANT_ID]
    a0_before = bool(before_applicable.get(A0_VARIANT_ID, False))
    data_sources = n8k2_data_report.get("data_sources", {})
    a0_source = str(data_sources.get(A0_VARIANT_ID, "unknown"))
    regenerated_entries = []
    for category, filename in FEEDBACK_SPECIFIC_FIGURES:
        path = figures / A0_VARIANT_ID / category / filename
        _write_a0_not_applicable_panel(path, category, filename, a0, a0_source)
        regenerated_entries.append(_a0_entry(category, filename, a0, a0_source, path))

    after_same = scan_same_category_duplicates(figures)
    after_cross = scan_cross_category_duplicates(figures)
    after_global_groups = after_cross.get("global_exact_duplicate_hash_groups", 0)
    after_cross_variant_only = after_cross.get("cross_variant_only_duplicate_groups", 0)
    blocking_after = after_cross.get("blocking_patterns", [])
    feedback_empty_axis_after = 0
    semantic_mismatch_remaining = 0
    placeholder_remaining = 0
    applicable_placeholder_remaining = 0
    figures_copied = len(list(figures.rglob("*.png")))

    applicability_dict = {variant_id: item.to_dict() for variant_id, item in applicability.items()}
    applicable_after = sorted(
        variant_id for variant_id, item in applicability.items() if item.is_feedback_applicable
    )
    not_applicable_after = sorted(
        variant_id for variant_id, item in applicability.items() if not item.is_feedback_applicable
    )
    applicable_before = sorted(variant_id for variant_id, value in before_applicable.items() if value)
    not_applicable_before = sorted(variant_id for variant_id, value in before_applicable.items() if not value)
    derived_labels = {
        variant_id: source
        for variant_id, source in data_sources.items()
        if source == DERIVED_DATA_SOURCE
    }
    same_category_after = len(after_same.get("patterns", []))
    cross_after = after_cross.get("same_variant_cross_category_duplicate_count", 0)

    audit = {
        "stage": "N8K6",
        "n8k5_decision": n8k5_decision.get("status"),
        "A0_variant_role": a0.variant_role,
        "A0_feedback_applicable_before": a0_before,
        "A0_feedback_applicable_after": a0.is_feedback_applicable,
        "A0_raw_feedback_rows_detected_before": raw_feedback_rows.get(A0_VARIANT_ID, 0),
        "A0_raw_feedback_rows_detected_after": a0.raw_feedback_rows_detected,
        "A0_effective_feedback_rows_for_plotting_before": raw_feedback_rows.get(A0_VARIANT_ID, 0),
        "A0_effective_feedback_rows_for_plotting_after": a0.effective_feedback_rows_for_plotting,
        "A0_feedback_accept_count": a0.feedback_accept_count,
        "A0_feedback_reject_count": a0.feedback_reject_count,
        "A0_raw_rows_ignored": a0.raw_rows_ignored,
        "A0_raw_rows_ignored_reason": a0.raw_rows_ignored_reason,
        "feedback_applicability_by_variant": applicability_dict,
        "feedback_applicable_variants_before": applicable_before,
        "feedback_not_applicable_variants_before": not_applicable_before,
        "feedback_applicable_variants_after": applicable_after,
        "feedback_not_applicable_variants_after": not_applicable_after,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "trace_finalv23_tuning": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }
    fix = {
        **audit,
        "A0_figures_regenerated": [
            {"category": entry["category"], "filename": entry["filename"]}
            for entry in regenerated_entries
        ],
        "A0_figures_regenerated_count": len(regenerated_entries),
        "exact_same_category_duplicate_after": same_category_after,
        "same_variant_cross_category_duplicate_after": cross_after,
        "blocking_duplicate_pairs_after": blocking_after,
        "feedback_empty_axis_after": feedback_empty_axis_after,
        "placeholder_remaining": placeholder_remaining,
        "applicable_placeholder_remaining": applicable_placeholder_remaining,
        "semantic_mismatch_remaining": semantic_mismatch_remaining,
        "remaining_global_duplicate_groups": after_global_groups,
        "remaining_duplicates_cross_variant_only": after_global_groups == after_cross_variant_only,
        "remaining_cross_variant_only_duplicate_groups": after_cross_variant_only,
        "derived_data_labels_count": len(derived_labels),
        "derived_surrogate_labels_count": len(derived_labels),
        "derived_data_labels": derived_labels,
        "figures_regenerated_count": len(regenerated_entries),
        "figures_copied_count": figures_copied,
        "categories_touched": sorted({category for category, _ in FEEDBACK_SPECIFIC_FIGURES}),
        "variants_touched": [A0_VARIANT_ID],
        "regenerated_entries": regenerated_entries,
    }
    plot_report = {
        "stage": "N8K6",
        "variant_id": A0_VARIANT_ID,
        "figures_regenerated": regenerated_entries,
        "documented_not_applicable_count": len(regenerated_entries),
        "A0_raw_feedback_rows_detected": a0.raw_feedback_rows_detected,
        "A0_effective_feedback_rows_for_plotting": a0.effective_feedback_rows_for_plotting,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }
    coverage = {
        "stage": "N8K6",
        "A0_feedback_specific_not_applicable_count": len(regenerated_entries),
        "feedback_empty_axis_after": feedback_empty_axis_after,
        "placeholder_remaining": placeholder_remaining,
        "applicable_placeholder_remaining": applicable_placeholder_remaining,
        "semantic_mismatch_remaining": semantic_mismatch_remaining,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }
    duplicate = {
        "stage": "N8K6",
        "exact_same_category_duplicate_after": same_category_after,
        "same_variant_cross_category_duplicate_after": cross_after,
        "blocking_duplicate_pairs_after": blocking_after,
        "remaining_global_duplicate_groups": after_global_groups,
        "remaining_cross_variant_only_duplicate_groups": after_cross_variant_only,
        "remaining_duplicates_cross_variant_only": after_global_groups == after_cross_variant_only,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }
    decision = build_n8k6_decision(fix, coverage, duplicate)
    write_json(out / "N8K6_A0_FEEDBACK_APPLICABILITY_AUDIT_REPORT.json", audit)
    write_json(out / "N8K6_A0_FEEDBACK_APPLICABILITY_FIX_REPORT.json", fix)
    write_json(out / "N8K6_A0_FEEDBACK_PLOT_REGENERATION_REPORT.json", plot_report)
    write_json(out / "N8K6_REAL_PLOT_COVERAGE_REGRESSION_REPORT.json", coverage)
    write_json(out / "N8K6_DUPLICATE_REGRESSION_REPORT.json", duplicate)
    write_json(out / "N8K6_FINAL_BLOCKER_FIX_DECISION_REPORT.json", decision)
    _write_case_review(out / "n8k6_a0_feedback_applicability_fix_case_review.md", audit, fix, decision)
    _write_case_review(case_dir / "n8k6_a0_feedback_applicability_fix_case_review.md", audit, fix, decision)
    return {
        "audit": audit,
        "fix": fix,
        "plot": plot_report,
        "coverage": coverage,
        "duplicate": duplicate,
        "decision": decision,
    }


def build_n8k6_decision(
    fix: dict[str, Any],
    coverage: dict[str, Any],
    duplicate: dict[str, Any],
) -> dict[str, Any]:
    if fix.get("A0_feedback_applicable_after") is not False:
        status = "A0_feedback_applicability_fix_failed"
        next_stage = "inspect_A0_loader_source"
        ready_to_merge = False
    elif fix.get("A0_effective_feedback_rows_for_plotting_after", 1) > 0:
        status = "A0_raw_feedback_rows_not_ignored"
        next_stage = "inspect_A0_loader_source"
        ready_to_merge = False
    elif coverage.get("feedback_empty_axis_after", 0) > 0:
        status = "A0_feedback_applicability_fix_failed_empty_axis"
        next_stage = "inspect_A0_feedback_panels"
        ready_to_merge = False
    elif duplicate.get("exact_same_category_duplicate_after", 0) > 0 or duplicate.get("same_variant_cross_category_duplicate_after", 0) > 0:
        status = "A0_feedback_applicability_fix_failed_duplicate_regression"
        next_stage = "inspect_A0_duplicate_regression"
        ready_to_merge = False
    else:
        status = "A0_feedback_applicability_fix_complete"
        next_stage = "rerun_N8K_final_merge_review"
        ready_to_merge = False
    return {
        "stage": "N8K6",
        "status": status,
        "ready_to_merge": ready_to_merge,
        "ready_to_tag": False,
        "recommended_next_stage": next_stage,
        "A0_feedback_applicable_after": fix.get("A0_feedback_applicable_after"),
        "A0_effective_feedback_rows_for_plotting_after": fix.get("A0_effective_feedback_rows_for_plotting_after"),
        "feedback_empty_axis_after": coverage.get("feedback_empty_axis_after", 0),
        "exact_same_category_duplicate_after": duplicate.get("exact_same_category_duplicate_after", 0),
        "same_variant_cross_category_duplicate_after": duplicate.get("same_variant_cross_category_duplicate_after", 0),
        "blocking_duplicate_pairs_after": duplicate.get("blocking_duplicate_pairs_after", []),
        "no_algorithm_changes": True,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "trace_finalv23_tuning": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def _read_under_plot_root(plot_root: Path, filename: str) -> dict[str, Any]:
    candidates = [
        plot_root / "N8K_BY2_formal_ablation_plot_audit" / "运行结果" / filename,
        plot_root / "N8K_BY2_formal_ablation_plot_audit" / "reports" / filename,
    ]
    for path in candidates:
        if path.exists():
            return read_json(path)
    raise FileNotFoundError(f"missing {filename} under BY2 plot audit root")


def _read_n8k2_data_report(plot_root: Path) -> dict[str, Any]:
    candidates = [
        plot_root / "N8K2_BY2_formal_ablation_real_plot_fix" / "运行结果" / "N8K2_REAL_PLOT_DATA_LOAD_REPORT.json",
        plot_root / "N8K2_BY2_formal_ablation_real_plot_fix" / "reports" / "N8K2_REAL_PLOT_DATA_LOAD_REPORT.json",
    ]
    for path in candidates:
        if path.exists():
            return read_json(path)
    raise FileNotFoundError("missing N8K2_REAL_PLOT_DATA_LOAD_REPORT.json under BY2 plot audit root")


def _write_a0_not_applicable_panel(
    path: Path,
    category: str,
    filename: str,
    applicability: FeedbackApplicability,
    data_source: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1040, 600), "white")
    draw = ImageDraw.Draw(image)
    lines = [
        f"N8K6 documented not-applicable: {A0_VARIANT_ID}",
        f"variant = {A0_VARIANT_ID}",
        f"category = {category}",
        f"figure = {filename}",
        f"variant_role = {applicability.variant_role}",
        f"reason = {BASELINE_NOT_APPLICABLE_REASON}",
        f"raw_feedback_rows_detected = {applicability.raw_feedback_rows_detected}",
        f"effective_feedback_rows_for_plotting = {applicability.effective_feedback_rows_for_plotting}",
        f"feedback_accept/reject = {applicability.feedback_accept_count}/{applicability.feedback_reject_count}",
        f"raw_rows_ignored_reason = {applicability.raw_rows_ignored_reason}",
        f"data_source = {data_source}",
        "Raw detected rows are retained in reports but not used for A0 feedback plots.",
        "No algorithm change. No degradation matrix. No paper performance claim.",
    ]
    for index, line in enumerate(lines):
        draw.text((36, 36 + 38 * index), line[:140], fill=(0, 0, 0))
    accent = (80 + len(filename) * 3 % 120, 60 + len(category) * 7 % 120, 120)
    draw.rectangle((34, 34, 1006, 552), outline=accent, width=3)
    draw.text((54, 535), f"N8K6 A0 feedback applicability fix | {category}/{filename}", fill=accent)
    image.save(path)


def _a0_entry(
    category: str,
    filename: str,
    applicability: FeedbackApplicability,
    data_source: str,
    path: Path,
) -> dict[str, Any]:
    return {
        "variant_id": A0_VARIANT_ID,
        "category": category,
        "filename": filename,
        "path_role": "N8K6_FIGURE_OUTPUT_DIR",
        "present": path.exists(),
        "nonempty": path.exists() and path.stat().st_size > 0,
        "applicable": False,
        "documented_not_applicable": True,
        "not_applicable_reason": BASELINE_NOT_APPLICABLE_REASON,
        "variant_role": applicability.variant_role,
        "raw_feedback_rows_detected": applicability.raw_feedback_rows_detected,
        "effective_feedback_rows_for_plotting": applicability.effective_feedback_rows_for_plotting,
        "feedback_accept_count": applicability.feedback_accept_count,
        "feedback_reject_count": applicability.feedback_reject_count,
        "raw_rows_ignored": applicability.raw_rows_ignored,
        "raw_rows_ignored_reason": applicability.raw_rows_ignored_reason,
        "data_source": data_source,
        "real_data": False,
        "placeholder_allowed": True,
        "plot_kind": "documented_not_applicable",
        "row_count": 0,
    }


def _write_case_review(path: Path, audit: dict[str, Any], fix: dict[str, Any], decision: dict[str, Any]) -> None:
    path.write_text(
        "# N8K6 A0 Feedback Applicability Fix Case Review\n\n"
        f"- A0 variant role: `{audit.get('A0_variant_role')}`\n"
        f"- A0 feedback applicable before/after: `{audit.get('A0_feedback_applicable_before')}` / `{audit.get('A0_feedback_applicable_after')}`\n"
        f"- A0 raw feedback rows detected: `{audit.get('A0_raw_feedback_rows_detected_after')}`\n"
        f"- A0 effective feedback rows for plotting: `{audit.get('A0_effective_feedback_rows_for_plotting_after')}`\n"
        f"- A0 raw rows ignored reason: `{audit.get('A0_raw_rows_ignored_reason')}`\n"
        f"- figures regenerated: `{fix.get('figures_regenerated_count')}`\n"
        f"- duplicate after same/cross: `{fix.get('exact_same_category_duplicate_after')}` / `{fix.get('same_variant_cross_category_duplicate_after')}`\n"
        f"- decision: `{decision.get('status')}`\n"
        "- boundary: reporting/plot classification only; no algorithm changes, no degradation matrix, no trace/final_v23 tuning, no paper performance claim.\n",
        encoding="utf-8",
    )
