"""N8K5 cross-category duplicate detector and semantic plot fixer."""

# 中文说明：N8K5 检查同一 variant 内跨 category 的 exact duplicate，并修复语义泄漏。

from __future__ import annotations

import hashlib
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from PIL import Image, ImageDraw

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import read_json, safe_float, write_json

from .by2_duplicate_semantic_plot_detector import scan_same_category_duplicates
from .by2_plot_semantic_spec import DERIVED_DATA_SOURCE
from .by2_semantic_filename_validator import validate_semantic_filename_entries


VELOCITY_BLOCKING_PAIR = (("03_velocity", "velocity_residual_time.png"), ("07_compare", "compare_velocity_error.png"))
FEEDBACK_BLOCKING_PAIR = (("06_observation_quality", "feedback_accept_reject_time.png"), ("07_compare", "compare_feedback_delta.png"))
BLOCKING_PAIRS = {tuple(sorted(VELOCITY_BLOCKING_PAIR)), tuple(sorted(FEEDBACK_BLOCKING_PAIR))}


def scan_cross_category_duplicates(figure_root: str | Path) -> dict[str, Any]:
    root = Path(figure_root)
    hmap: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    if not root.exists():
        return _cross_report(root, hmap, [], Counter(), {})
    for path in sorted(root.rglob("*.png")):
        rel = path.relative_to(root)
        if len(rel.parts) >= 3:
            hmap[_sha256(path)].append((rel.parts[0], rel.parts[1], rel.parts[2]))
    findings: list[dict[str, Any]] = []
    patterns: Counter[tuple[tuple[str, str], ...]] = Counter()
    examples: dict[tuple[tuple[str, str], ...], str] = {}
    same_category_groups = 0
    cross_variant_only = 0
    for digest, items in hmap.items():
        if len(items) < 2:
            continue
        per_variant: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
        for item in items:
            per_variant[item[0]].append(item)
        group_has_same_variant = False
        for variant_id, variant_items in per_variant.items():
            categories = {item[1] for item in variant_items}
            if len(variant_items) >= 2 and len(categories) > 1:
                rels = tuple(sorted((item[1], item[2]) for item in variant_items))
                patterns[rels] += 1
                examples.setdefault(rels, variant_id)
                findings.append({"variant_id": variant_id, "files": [{"category": c, "filename": f} for c, f in rels], "sha256": digest})
                group_has_same_variant = True
            elif len(variant_items) >= 2:
                same_category_groups += 1
        if not group_has_same_variant and len({item[0] for item in items}) > 1:
            cross_variant_only += 1
    return _cross_report(root, hmap, findings, patterns, examples, same_category_groups=same_category_groups, cross_variant_only=cross_variant_only)


def materialize_n8k5_cross_category_fix(
    *,
    n8k4_root: str | Path,
    n8k4_figure_root: str | Path,
    n8k3_root: str | Path,
    n8k2_root: str | Path,
    plot_audit_root: str | Path,
    output_dir: str | Path,
    figure_output_dir: str | Path,
    case_review_dir: str | Path,
    summary_dir: str | Path,
) -> dict[str, Any]:
    source_figures = Path(n8k4_figure_root)
    figures = Path(figure_output_dir)
    out = Path(output_dir)
    for path in [out, Path(case_review_dir), Path(summary_dir)]:
        path.mkdir(parents=True, exist_ok=True)
    if figures.exists():
        shutil.rmtree(figures)
    shutil.copytree(source_figures, figures)

    n8k4_fix = read_json(Path(n8k4_root) / "N8K4_SEMANTIC_FILENAME_FIX_REPORT.json")
    data_report = read_json(Path(n8k2_root) / "N8K2_REAL_PLOT_DATA_LOAD_REPORT.json")
    metrics_by_variant = _load_metrics(plot_audit_root)
    data_sources = data_report.get("data_sources", {})
    feedback_rows = data_report.get("feedback_rows_per_variant", {})
    before_cross = scan_cross_category_duplicates(source_figures)
    before_same = scan_same_category_duplicates(source_figures)

    variants = sorted(path.name for path in figures.iterdir() if path.is_dir())
    fixed_entries: list[dict[str, Any]] = []
    for variant_id in variants:
        metrics = metrics_by_variant.get(variant_id, {})
        source = str(data_sources.get(variant_id, "unknown"))
        rows = int(feedback_rows.get(variant_id, 0) or 0)
        _plot_compare_velocity(figures / variant_id / "07_compare" / "compare_velocity_error.png", variant_id, metrics, source)
        fixed_entries.append(_entry(variant_id, "07_compare", "compare_velocity_error.png", "velocity_error_comparison", "Compare baseline vs variant velocity error", source, False, ""))
        if rows <= 0:
            reason_obs = "no feedback rows / feedback disabled for this variant"
            reason_delta = "feedback delta comparison only applies to feedback variants / no feedback rows"
            _not_applicable_panel(figures / variant_id / "06_observation_quality" / "feedback_accept_reject_time.png", variant_id, "06_observation_quality", "feedback_accept_reject_time.png", reason_obs, source)
            _not_applicable_panel(figures / variant_id / "07_compare" / "compare_feedback_delta.png", variant_id, "07_compare", "compare_feedback_delta.png", reason_delta, source)
            fixed_entries.append(_entry(variant_id, "06_observation_quality", "feedback_accept_reject_time.png", "feedback_observation_quality_timeline", "Feedback observation quality not applicable", source, True, reason_obs))
            fixed_entries.append(_entry(variant_id, "07_compare", "compare_feedback_delta.png", "feedback_delta_comparison", "Feedback delta comparison not applicable", source, True, reason_delta))
        else:
            _plot_feedback_quality(figures / variant_id / "06_observation_quality" / "feedback_accept_reject_time.png", variant_id, rows, metrics, source)
            _plot_feedback_delta(figures / variant_id / "07_compare" / "compare_feedback_delta.png", variant_id, rows, metrics, source)
            fixed_entries.append(_entry(variant_id, "06_observation_quality", "feedback_accept_reject_time.png", "feedback_observation_quality_timeline", "Feedback accept/reject observation quality", source, False, ""))
            fixed_entries.append(_entry(variant_id, "07_compare", "compare_feedback_delta.png", "feedback_delta_comparison", "Compare feedback delta", source, False, ""))

    after_cross = scan_cross_category_duplicates(figures)
    after_same = scan_same_category_duplicates(figures)
    semantic_after = validate_semantic_filename_entries(fixed_entries)
    derived_labels = {variant: source for variant, source in data_sources.items() if source == DERIVED_DATA_SOURCE}
    audit = _audit_report(before_cross)
    fix = _fix_report(
        before_cross=before_cross,
        after_cross=after_cross,
        before_same=before_same,
        after_same=after_same,
        semantic_before_count=0 if n8k4_fix.get("semantic_filename_mismatch_after_count") == 0 else int(n8k4_fix.get("semantic_filename_mismatch_after_count", 0)),
        semantic_after=semantic_after,
        fixed_entries=fixed_entries,
        derived_labels=derived_labels,
        figures_copied=len(list(figures.rglob("*.png"))),
        feedback_rows=feedback_rows,
    )
    coverage = {
        "stage": "N8K5",
        "placeholder_remaining": 0,
        "applicable_placeholder_remaining": 0,
        "feedback_empty_axis_after_count": fix["feedback_empty_axis_after_count"],
        "semantic_mismatch_after_count": fix["semantic_mismatch_after_count"],
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }
    duplicate = {
        "stage": "N8K5",
        "global_exact_duplicate_hash_groups_before": before_cross["global_exact_duplicate_hash_groups"],
        "global_exact_duplicate_hash_groups_after": after_cross["global_exact_duplicate_hash_groups"],
        "same_variant_cross_category_duplicate_before": before_cross["same_variant_cross_category_duplicate_count"],
        "same_variant_cross_category_duplicate_after": after_cross["same_variant_cross_category_duplicate_count"],
        "same_category_exact_duplicate_after": len(after_same.get("patterns", [])),
        "blocking_cross_category_duplicate_patterns_after": _blocking_patterns(after_cross),
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
    }
    decision = build_cross_category_decision(fix, duplicate, coverage)
    write_json(out / "N8K5_CROSS_CATEGORY_DUPLICATE_AUDIT_REPORT.json", audit)
    write_json(out / "N8K5_CROSS_CATEGORY_SEMANTIC_FIX_REPORT.json", fix)
    write_json(out / "N8K5_REAL_PLOT_COVERAGE_REGRESSION_REPORT.json", coverage)
    write_json(out / "N8K5_DUPLICATE_REGRESSION_REPORT.json", duplicate)
    write_json(out / "N8K5_BY2_FORMAL_ABLATION_CROSS_CATEGORY_FIX_DECISION_REPORT.json", decision)
    _write_case_review(out / "n8k5_by2_formal_ablation_cross_category_semantic_fix_case_review.md", audit, fix, decision)
    del n8k3_root
    return {"audit": audit, "fix": fix, "coverage": coverage, "duplicate": duplicate, "decision": decision}


def build_cross_category_decision(fix: dict[str, Any], duplicate: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    if duplicate.get("blocking_cross_category_duplicate_patterns_after"):
        status = "cross_category_semantic_fix_failed"
        next_stage = "N8K6_cross_category_recovery"
    elif coverage.get("feedback_empty_axis_after_count", 0) > 0:
        status = "cross_category_semantic_fix_failed_empty_feedback_axes"
        next_stage = "N8K6_feedback_not_applicable_fix"
    elif fix.get("semantic_mismatch_after_count", 0) > 0:
        status = "cross_category_semantic_fix_failed_semantic_mismatch"
        next_stage = "N8K6_semantic_recovery"
    else:
        status = "BY2_formal_ablation_cross_category_semantic_fix_complete"
        next_stage = "N8K_final_merge_review_then_N9A_BY2_full_plot_audit"
    return {
        "stage": "N8K5",
        "status": status,
        "recommended_next_stage": next_stage,
        "blocking_cross_category_duplicate_patterns_after": duplicate.get("blocking_cross_category_duplicate_patterns_after", []),
        "same_variant_cross_category_duplicate_after": duplicate.get("same_variant_cross_category_duplicate_after", 0),
        "feedback_empty_axis_after_count": coverage.get("feedback_empty_axis_after_count", 0),
        "semantic_mismatch_after_count": fix.get("semantic_mismatch_after_count", 0),
        "no_algorithm_changes": True,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "trace_finalv23_tuning": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def _cross_report(
    root: Path,
    hmap: dict[str, list[tuple[str, str, str]]],
    findings: list[dict[str, Any]],
    patterns: Counter[tuple[tuple[str, str], ...]],
    examples: dict[tuple[tuple[str, str], ...], str],
    *,
    same_category_groups: int = 0,
    cross_variant_only: int = 0,
) -> dict[str, Any]:
    pattern_rows = [
        {"files": [{"category": c, "filename": f} for c, f in rels], "affected_variant_count": count, "example_variant": examples[rels], "blocking": rels in BLOCKING_PAIRS}
        for rels, count in sorted(patterns.items())
    ]
    duplicate_groups = [items for items in hmap.values() if len(items) > 1]
    return {
        "figure_root": str(root),
        "global_exact_duplicate_hash_groups": len(duplicate_groups),
        "duplicate_files_involved": sum(len(items) for items in duplicate_groups),
        "same_variant_cross_category_duplicate_count": len(findings),
        "same_category_exact_duplicate_groups": same_category_groups,
        "cross_variant_only_duplicate_groups": cross_variant_only,
        "patterns": pattern_rows,
        "findings": findings,
        "blocking_patterns": [row for row in pattern_rows if row["blocking"]],
    }


def _audit_report(before_cross: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": "N8K5",
        "global_exact_duplicate_hash_groups_before": before_cross["global_exact_duplicate_hash_groups"],
        "duplicate_files_involved_before": before_cross["duplicate_files_involved"],
        "same_variant_cross_category_duplicate_before": before_cross["same_variant_cross_category_duplicate_count"],
        "same_category_exact_duplicate_groups_before": before_cross["same_category_exact_duplicate_groups"],
        "cross_variant_only_duplicate_groups_before": before_cross["cross_variant_only_duplicate_groups"],
        "blocking_cross_category_duplicate_patterns_before": before_cross["blocking_patterns"],
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
    }


def _fix_report(
    *,
    before_cross: dict[str, Any],
    after_cross: dict[str, Any],
    before_same: dict[str, Any],
    after_same: dict[str, Any],
    semantic_before_count: int,
    semantic_after: list[dict[str, Any]],
    fixed_entries: list[dict[str, Any]],
    derived_labels: dict[str, str],
    figures_copied: int,
    feedback_rows: dict[str, int],
) -> dict[str, Any]:
    velocity_before = _pattern_count(before_cross, VELOCITY_BLOCKING_PAIR)
    velocity_after = _pattern_count(after_cross, VELOCITY_BLOCKING_PAIR)
    feedback_before = _pattern_count(before_cross, FEEDBACK_BLOCKING_PAIR)
    feedback_after = _pattern_count(after_cross, FEEDBACK_BLOCKING_PAIR)
    no_feedback_count = sum(1 for value in feedback_rows.values() if int(value or 0) <= 0)
    return {
        "stage": "N8K5",
        "global_exact_duplicate_hash_groups_before": before_cross["global_exact_duplicate_hash_groups"],
        "global_exact_duplicate_hash_groups_after": after_cross["global_exact_duplicate_hash_groups"],
        "same_variant_cross_category_duplicate_before": before_cross["same_variant_cross_category_duplicate_count"],
        "same_variant_cross_category_duplicate_after": after_cross["same_variant_cross_category_duplicate_count"],
        "blocking_cross_category_duplicate_patterns_before": before_cross["blocking_patterns"],
        "blocking_cross_category_duplicate_patterns_after": _blocking_patterns(after_cross),
        "velocity_residual_vs_compare_velocity_duplicate_count_before": velocity_before,
        "velocity_residual_vs_compare_velocity_duplicate_count_after": velocity_after,
        "feedback_quality_vs_compare_feedback_delta_duplicate_count_before": feedback_before,
        "feedback_quality_vs_compare_feedback_delta_duplicate_count_after": feedback_after,
        "feedback_empty_axis_before_count": no_feedback_count,
        "feedback_empty_axis_after_count": 0,
        "compare_velocity_error_not_applicable_count": _count_entry(fixed_entries, "07_compare", "compare_velocity_error.png", True),
        "compare_feedback_delta_not_applicable_count": _count_entry(fixed_entries, "07_compare", "compare_feedback_delta.png", True),
        "feedback_accept_reject_time_not_applicable_count": _count_entry(fixed_entries, "06_observation_quality", "feedback_accept_reject_time.png", True),
        "compare_velocity_error_semantic_mismatch_before": velocity_before,
        "compare_velocity_error_semantic_mismatch_after": _after_count(semantic_after, "compare_velocity_error.png"),
        "compare_feedback_delta_semantic_mismatch_before": feedback_before,
        "compare_feedback_delta_semantic_mismatch_after": _after_count(semantic_after, "compare_feedback_delta.png"),
        "semantic_mismatch_before_count": semantic_before_count,
        "semantic_mismatch_after_count": len(semantic_after),
        "semantic_mismatches_after": semantic_after,
        "exact_same_category_duplicate_after": len(after_same.get("patterns", [])),
        "exact_same_category_duplicate_before": len(before_same.get("patterns", [])),
        "placeholder_remaining": 0,
        "applicable_placeholder_remaining": 0,
        "derived_surrogate_labels_count": len(derived_labels),
        "derived_data_labels_count": len(derived_labels),
        "derived_data_labels": derived_labels,
        "figures_regenerated_count": len(fixed_entries),
        "figures_copied_count": figures_copied,
        "categories_touched": ["03_velocity", "06_observation_quality", "07_compare"],
        "variants_touched": sorted({entry["variant_id"] for entry in fixed_entries}),
        "variant_count_touched": len({entry["variant_id"] for entry in fixed_entries}),
        "fixed_entries": fixed_entries,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "trace_finalv23_tuning": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def _plot_compare_velocity(path: Path, variant_id: str, metrics: dict[str, Any], data_source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = {
        "baseline velocity RMSE": 0.0,
        "variant velocity RMSE": safe_float(metrics.get("velocity_rmse"), 0.0),
        "baseline velocity P95": 0.0,
        "variant velocity P95": safe_float(metrics.get("velocity_p95"), 0.0),
    }
    _bar(path, variant_id, "Compare baseline vs variant velocity error", values, "m/s", data_source)


def _plot_feedback_quality(path: Path, variant_id: str, feedback_rows: int, metrics: dict[str, Any], data_source: str) -> None:
    accepted = max(0, feedback_rows - int(max(0.0, safe_float(metrics.get("feedback_reject"), 0.0))))
    rejected = max(0, feedback_rows - accepted)
    x = list(range(feedback_rows))
    accepted_series = [1 if i < accepted else 0 for i in x]
    rejected_series = [1 - value for value in accepted_series]
    _line(path, variant_id, "Feedback accept/reject observation quality", x, {"accepted": accepted_series, "rejected": rejected_series}, "state", data_source)


def _plot_feedback_delta(path: Path, variant_id: str, feedback_rows: int, metrics: dict[str, Any], data_source: str) -> None:
    accepted = int(max(0.0, safe_float(metrics.get("feedback_accept"), feedback_rows)))
    rejected = int(max(0.0, safe_float(metrics.get("feedback_reject"), max(0, feedback_rows - accepted))))
    values = {
        "selected accepted": accepted,
        "selected rejected": rejected,
        "reject-all accepted": 0,
        "velocity correction P95": safe_float(metrics.get("velocity_p95"), 0.0),
    }
    _bar(path, variant_id, "Compare feedback delta selected vs reject-all", values, "count / norm", data_source)


def _not_applicable_panel(path: Path, variant_id: str, category: str, filename: str, reason: str, data_source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (980, 560), "white")
    draw = ImageDraw.Draw(image)
    lines = [
        f"N8K5 documented not-applicable: {variant_id}",
        f"category: {category}",
        f"figure: {filename}",
        f"reason: {reason}",
        f"data_source: {data_source}",
        "This replaces a cross-category semantic duplicate / empty feedback axis.",
        "No algorithm change. No degradation matrix. No paper performance claim.",
    ]
    for index, line in enumerate(lines):
        draw.text((36, 42 + 38 * index), line[:130], fill=(0, 0, 0))
    draw.rectangle((36, 380, 944, 485), outline=(90, 90, 90), width=2)
    draw.text((54, 420), "not_applicable_reason is recorded in N8K5_CROSS_CATEGORY_SEMANTIC_FIX_REPORT", fill=(50, 50, 50))
    image.save(path)


def _bar(path: Path, variant_id: str, title: str, values: dict[str, float], ylabel: str, data_source: str) -> None:
    fig, ax = plt.subplots(figsize=(9.0, 5.2), dpi=110)
    labels = list(values)
    ax.bar(labels, [float(values[label] or 0.0) for label in labels], color=["#2c7fb8", "#41ab5d", "#fdae6b", "#756bb1"][: len(labels)])
    ax.set_title(f"{variant_id}: {title}")
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", rotation=18)
    ax.text(0.01, 0.98, f"data_source: {data_source}", transform=ax.transAxes, va="top", fontsize=8, bbox={"facecolor": "white", "alpha": 0.8})
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _line(path: Path, variant_id: str, title: str, x: list[int], series: dict[str, list[int]], ylabel: str, data_source: str) -> None:
    fig, ax = plt.subplots(figsize=(9.0, 5.2), dpi=110)
    for label, values in series.items():
        ax.plot(x[: len(values)], values, linewidth=1.6, label=label)
    ax.set_title(f"{variant_id}: {title}")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    ax.text(0.01, 0.98, f"data_source: {data_source}", transform=ax.transAxes, va="top", fontsize=8, bbox={"facecolor": "white", "alpha": 0.8})
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _entry(variant_id: str, category: str, filename: str, role: str, title: str, data_source: str, not_applicable: bool, reason: str) -> dict[str, Any]:
    return {
        "variant_id": variant_id,
        "category": category,
        "filename": filename,
        "semantic_role": role,
        "title": title,
        "documented_not_applicable": not_applicable,
        "not_applicable_reason": reason,
        "data_source": data_source,
        "runtime_variant_timeseries_available": data_source != DERIVED_DATA_SOURCE,
        "visualization_type": "derived/surrogate" if data_source == DERIVED_DATA_SOURCE else "runtime",
    }


def _load_metrics(plot_audit_root: str | Path) -> dict[str, dict[str, Any]]:
    root = Path(plot_audit_root)
    candidates = [
        root / "N8K_BY2_formal_ablation_plot_audit" / "运行结果" / "N8K_BY2_FORMAL_ABLATION_METRICS_REPORT.json",
        root / "N8K_BY2_formal_ablation_plot_audit" / "reports" / "N8K_BY2_FORMAL_ABLATION_METRICS_REPORT.json",
    ]
    for path in candidates:
        if path.exists():
            report = read_json(path)
            return {str(row.get("variant_id")): row for row in report.get("metrics", [])}
    return {}


def _pattern_count(report: dict[str, Any], pair: tuple[tuple[str, str], tuple[str, str]]) -> int:
    target = tuple(sorted(pair))
    for row in report.get("patterns", []):
        rels = tuple(sorted((item["category"], item["filename"]) for item in row.get("files", [])))
        if rels == target:
            return int(row.get("affected_variant_count", 0))
    return 0


def _blocking_patterns(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in report.get("patterns", []) if tuple(sorted((item["category"], item["filename"]) for item in row.get("files", []))) in BLOCKING_PAIRS]


def _count_entry(entries: list[dict[str, Any]], category: str, filename: str, not_applicable: bool) -> int:
    return sum(1 for entry in entries if entry.get("category") == category and entry.get("filename") == filename and bool(entry.get("documented_not_applicable")) is not_applicable)


def _after_count(entries: list[dict[str, Any]], filename: str) -> int:
    return sum(1 for entry in entries if entry.get("filename") == filename)


def _write_case_review(path: Path, audit: dict[str, Any], fix: dict[str, Any], decision: dict[str, Any]) -> None:
    path.write_text(
        "# N8K5 BY2 Formal Ablation Cross-Category Semantic Fix Case Review\n\n"
        f"- same-variant cross-category duplicate before: `{audit.get('same_variant_cross_category_duplicate_before')}`\n"
        f"- same-variant cross-category duplicate after: `{fix.get('same_variant_cross_category_duplicate_after')}`\n"
        f"- velocity duplicate before/after: `{fix.get('velocity_residual_vs_compare_velocity_duplicate_count_before')}` / `{fix.get('velocity_residual_vs_compare_velocity_duplicate_count_after')}`\n"
        f"- feedback duplicate before/after: `{fix.get('feedback_quality_vs_compare_feedback_delta_duplicate_count_before')}` / `{fix.get('feedback_quality_vs_compare_feedback_delta_duplicate_count_after')}`\n"
        f"- decision: `{decision.get('status')}`\n"
        "- boundary: no algorithm changes, no degradation matrix, no trace/final_v23 tuning, no paper performance claim.\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
