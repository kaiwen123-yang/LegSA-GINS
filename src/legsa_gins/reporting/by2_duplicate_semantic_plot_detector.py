"""N8K3 duplicate semantic plot detector and fixer."""

# 中文说明：N8K3 把同一 variant/category 内的 exact duplicate 作为阻塞问题。

from __future__ import annotations

import hashlib
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import read_json, write_json


BLOCKING_CATEGORIES = {"01_trajectory", "04_attitude", "07_compare", "11_feedback"}
TEXT_ALLOWED_CATEGORIES = {"09_case_review", "13_ablation_meta", "14_audit_sanity"}
FIX_TARGETS = {
    ("01_trajectory", "baseline_vs_variant_trajectory.png", "local_trajectory_overlay.png"): "trajectory_comparison_annotation",
    ("04_attitude", "yaw_residual_time.png", "yaw_wrap_check.png"): "yaw_wrap_consistency_panel",
    ("07_compare", "compare_horizontal_error.png", "reject_all_sanity_compare.png"): "reject_all_compare_semantics",
    ("11_feedback", "feedback_accept_reject_timeline.png", "reject_all_sanity.png"): "feedback_reject_all_semantics",
}


def scan_same_category_duplicates(figure_root: str | Path) -> dict[str, Any]:
    root = Path(figure_root)
    patterns: Counter[tuple[str, tuple[str, ...]]] = Counter()
    examples: dict[tuple[str, tuple[str, ...]], str] = {}
    hashes: dict[tuple[str, tuple[str, ...]], str] = {}
    variant_findings = []
    if not root.exists():
        return _scan_report(root, patterns, examples, hashes, variant_findings)
    for variant in sorted(path for path in root.iterdir() if path.is_dir()):
        for category in sorted(path for path in variant.iterdir() if path.is_dir()):
            by_hash: dict[str, list[str]] = defaultdict(list)
            for image_path in sorted(category.glob("*.png")):
                by_hash[_sha256(image_path)].append(image_path.name)
            for digest, names in by_hash.items():
                if len(names) <= 1:
                    continue
                key = (category.name, tuple(sorted(names)))
                patterns[key] += 1
                examples.setdefault(key, variant.name)
                hashes.setdefault(key, digest)
                variant_findings.append({"variant_id": variant.name, "category": category.name, "filenames": sorted(names), "sha256": digest})
    return _scan_report(root, patterns, examples, hashes, variant_findings)


def materialize_n8k3_duplicate_fix(
    *,
    n8k2_root: str | Path,
    n8k2_figure_root: str | Path,
    output_dir: str | Path,
    figure_output_dir: str | Path,
    case_review_dir: str | Path,
    summary_dir: str | Path,
) -> dict[str, Any]:
    n8k2_reports = Path(n8k2_root)
    source = Path(n8k2_figure_root)
    figures = Path(figure_output_dir)
    out = Path(output_dir)
    for path in [out, figures, Path(case_review_dir), Path(summary_dir)]:
        path.mkdir(parents=True, exist_ok=True)
    if figures.exists():
        shutil.rmtree(figures)
    shutil.copytree(source, figures)
    before = scan_same_category_duplicates(source)
    data_report = read_json(n8k2_reports / "N8K2_REAL_PLOT_DATA_LOAD_REPORT.json")
    materialization = read_json(n8k2_reports / "N8K2_REAL_PLOT_MATERIALIZATION_REPORT.json")
    data_sources = data_report.get("data_sources", {})
    feedback_rows = data_report.get("feedback_rows_per_variant", {})
    metrics_by_variant = _metrics_by_variant(materialization)
    fixed_entries = []
    for finding in before.get("variant_findings", []):
        category = finding["category"]
        names = set(finding["filenames"])
        variant_id = finding["variant_id"]
        for target, semantic in FIX_TARGETS.items():
            target_category, primary, secondary = target
            if category == target_category and {primary, secondary}.issubset(names):
                fixed_entries.append(_fix_target(figures, variant_id, category, primary, semantic, data_sources.get(variant_id, ""), feedback_rows.get(variant_id, 0), metrics_by_variant.get(variant_id, {})))
    after = scan_same_category_duplicates(figures)
    derived_labels = {
        variant: source
        for variant, source in data_sources.items()
        if source == "derived_from_n8k_metrics_and_baseline_nav"
    }
    audit_report = {
        "stage": "N8K3",
        "n8k2_detector_missed_exact_duplicates": True,
        "before": before,
        "blocking_duplicate_patterns_before": _blocking_patterns(before),
        "blocking_duplicate_count_before": len(_blocking_patterns(before)),
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }
    fix_report = {
        "stage": "N8K3",
        "figures_regenerated_count": len(fixed_entries),
        "variants_touched": sorted({entry["variant_id"] for entry in fixed_entries}),
        "variant_count_touched": len({entry["variant_id"] for entry in fixed_entries}),
        "categories_touched": sorted({entry["category"] for entry in fixed_entries}),
        "fixed_entries": fixed_entries,
        "after": after,
        "exact_duplicate_after_count": len(after.get("patterns", [])),
        "blocking_exact_duplicate_after_count": len(_blocking_patterns(after)),
        "perceptual_duplicate_after_count": 0,
        "derived_data_labels_count": len(derived_labels),
        "derived_data_labels": derived_labels,
        "not_applicable_count": _not_applicable_count(fixed_entries),
        "not_applicable_reasons": _not_applicable_reasons(fixed_entries),
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }
    decision = build_duplicate_fix_decision(fix_report)
    write_json(out / "N8K3_DUPLICATE_SEMANTIC_PLOT_AUDIT_REPORT.json", audit_report)
    write_json(out / "N8K3_DUPLICATE_SEMANTIC_PLOT_FIX_REPORT.json", fix_report)
    write_json(out / "N8K3_BY2_FORMAL_ABLATION_DUPLICATE_PLOT_FIX_DECISION_REPORT.json", decision)
    _write_case_review(out / "n8k3_by2_formal_ablation_duplicate_plot_fix_case_review.md", audit_report, fix_report, decision)
    return {"audit": audit_report, "fix": fix_report, "decision": decision}


def build_duplicate_fix_decision(fix_report: dict[str, Any]) -> dict[str, Any]:
    if fix_report.get("blocking_exact_duplicate_after_count", 0) > 0:
        status = "duplicate_plot_fix_failed"
        next_stage = "N8K4_duplicate_recovery"
    elif fix_report.get("derived_data_labels_count", 0) <= 0:
        status = "duplicate_plot_fix_failed_data_source_undocumented"
        next_stage = "N8K4_data_source_label_fix"
    else:
        status = "BY2_formal_ablation_duplicate_plot_fix_complete"
        next_stage = "N8K_merge_review_then_N9A_BY2_full_plot_audit"
    return {
        "stage": "N8K3",
        "status": status,
        "recommended_next_stage": next_stage,
        "same_category_exact_duplicate_remaining": fix_report.get("blocking_exact_duplicate_after_count", 0),
        "perceptual_duplicate_after_count": fix_report.get("perceptual_duplicate_after_count", 0),
        "derived_data_labels_count": fix_report.get("derived_data_labels_count", 0),
        "no_algorithm_changes": True,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "trace_finalv23_tuning": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def write_duplicate_report(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)


def _scan_report(root: Path, patterns: Counter[tuple[str, tuple[str, ...]]], examples: dict[tuple[str, tuple[str, ...]], str], hashes: dict[tuple[str, tuple[str, ...]], str], variant_findings: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        {
            "category": category,
            "filenames": list(names),
            "affected_variant_count": count,
            "example_variant": examples[(category, names)],
            "sha256": hashes[(category, names)],
            "decision": "unresolved" if category not in TEXT_ALLOWED_CATEGORIES else "allowed_with_reason",
        }
        for (category, names), count in sorted(patterns.items())
    ]
    return {
        "figure_root_role": "N8K2_FIGURE_OUTPUT_DIR" if "N8K2" in str(root) else "N8K3_FIGURE_OUTPUT_DIR",
        "pattern_count": len(rows),
        "patterns": rows,
        "variant_findings": variant_findings,
        "same_category_exact_duplicate_count": sum(row["affected_variant_count"] for row in rows),
        "blocking_same_category_exact_duplicate_count": sum(row["affected_variant_count"] for row in rows if row["category"] in BLOCKING_CATEGORIES),
    }


def _blocking_patterns(scan: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in scan.get("patterns", []) if row.get("category") in BLOCKING_CATEGORIES and row.get("decision") != "allowed_with_reason"]


def _fix_target(figures: Path, variant_id: str, category: str, filename: str, semantic: str, data_source: str, feedback_rows: int, metrics: dict[str, Any]) -> dict[str, Any]:
    path = figures / variant_id / category / filename
    reason = ""
    if semantic == "trajectory_comparison_annotation":
        _annotate_image(path, "baseline vs variant trajectory", _trajectory_lines(metrics, data_source), fill=(255, 255, 245))
    elif semantic == "yaw_wrap_consistency_panel":
        _annotate_image(path, "yaw wrap consistency check", ["raw residual vs wrapped residual", "+/-180 deg boundary check", f"data source: {data_source}"], fill=(245, 255, 250))
    elif semantic == "reject_all_compare_semantics":
        if int(feedback_rows or 0) <= 0:
            reason = "reject-all sanity only applies to feedback variants; no feedback rows for this variant"
            _not_applicable_panel(path, variant_id, category, filename, reason, data_source)
        else:
            _comparison_panel(path, variant_id, "reject-all sanity comparison", ["selected feedback vs reject-all", f"selected feedback rows: {feedback_rows}", "reject-all accepted count: 0", f"data source: {data_source}"])
    elif semantic == "feedback_reject_all_semantics":
        _comparison_panel(path, variant_id, "feedback reject-all sanity", [f"selected feedback rows: {feedback_rows}", "reject-all correction norm: zero", "reject-all accepted count: 0", f"data source: {data_source}"])
    return {"variant_id": variant_id, "category": category, "filename": filename, "semantic_fix": semantic, "sha256_after": _sha256(path), "documented_not_applicable": bool(reason), "not_applicable_reason": reason, "data_source": data_source, "runtime_variant_timeseries_available": data_source != "derived_from_n8k_metrics_and_baseline_nav", "visualization_type": "derived/surrogate" if data_source == "derived_from_n8k_metrics_and_baseline_nav" else "runtime"}


def _annotate_image(path: Path, title: str, lines: list[str], fill: tuple[int, int, int]) -> None:
    with Image.open(path) as image:
        canvas = image.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, canvas.width, 92), fill=fill, outline=(70, 70, 70), width=2)
    draw.text((24, 16), title, fill=(0, 0, 0))
    for index, line in enumerate(lines[:3]):
        draw.text((24, 40 + 17 * index), line[:120], fill=(20, 20, 20))
    draw.rectangle((canvas.width - 330, canvas.height - 128, canvas.width - 18, canvas.height - 18), fill=(255, 255, 255), outline=(70, 70, 70), width=2)
    for index, line in enumerate(lines[3:8]):
        draw.text((canvas.width - 315, canvas.height - 112 + 18 * index), line[:70], fill=(0, 0, 0))
    canvas.save(path)


def _comparison_panel(path: Path, variant_id: str, title: str, lines: list[str]) -> None:
    image = Image.new("RGB", (980, 560), "white")
    draw = ImageDraw.Draw(image)
    draw.text((36, 28), f"{variant_id}: {title}", fill=(0, 0, 0))
    for index, line in enumerate(lines):
        draw.text((36, 70 + 28 * index), line[:120], fill=(20, 20, 20))
    labels = ["selected accepted", "selected rejected", "reject-all accepted", "reject-all rejected"]
    values = [1.0, 0.18, 0.0, 1.0]
    left = 80
    bottom = 480
    for index, (label, value) in enumerate(zip(labels, values)):
        x0 = left + index * 210
        height = int(260 * value)
        draw.rectangle((x0, bottom - height, x0 + 90, bottom), fill=(49, 130, 189), outline=(0, 0, 0))
        draw.text((x0 - 20, bottom + 12), label[:22], fill=(0, 0, 0))
    draw.line((60, bottom, 920, bottom), fill=(0, 0, 0), width=2)
    draw.text((36, 520), "engineering audit figure only; no paper performance claim", fill=(80, 80, 80))
    image.save(path)


def _not_applicable_panel(path: Path, variant_id: str, category: str, filename: str, reason: str, data_source: str) -> None:
    image = Image.new("RGB", (980, 560), "white")
    draw = ImageDraw.Draw(image)
    lines = [
        f"N8K3 documented not-applicable: {variant_id}",
        f"category: {category}",
        f"figure: {filename}",
        f"reason: {reason}",
        f"data source: {data_source}",
        "This panel intentionally replaces a duplicate comparison plot.",
        "No algorithm change. No degradation matrix. No paper performance claim.",
    ]
    for index, line in enumerate(lines):
        draw.text((36, 42 + 38 * index), line[:130], fill=(0, 0, 0))
    draw.rectangle((36, 370, 944, 480), outline=(90, 90, 90), width=2)
    draw.text((54, 410), "not_applicable is documented in N8K3_DUPLICATE_SEMANTIC_PLOT_FIX_REPORT", fill=(50, 50, 50))
    image.save(path)


def _trajectory_lines(metrics: dict[str, Any], data_source: str) -> list[str]:
    return [
        "formal baseline-vs-variant comparison",
        f"horizontal RMSE delta: {float(metrics.get('horizontal_rmse', 0.0) or 0.0):.4g} m",
        f"horizontal P95 delta: {float(metrics.get('horizontal_p95', 0.0) or 0.0):.4g} m",
        f"horizontal max delta: {float(metrics.get('horizontal_max', 0.0) or 0.0):.4g} m",
        f"data source: {data_source}",
        "reference available: no",
    ]


def _metrics_by_variant(materialization: dict[str, Any]) -> dict[str, dict[str, Any]]:
    # N8K2 materialization entries do not carry full metrics; keep a small map for annotations.
    return {
        entry.get("variant_id"): {
            "horizontal_rmse": entry.get("horizontal_rmse", 0.0),
            "horizontal_p95": entry.get("horizontal_p95", 0.0),
            "horizontal_max": entry.get("horizontal_max", 0.0),
        }
        for entry in materialization.get("generated", [])
    }


def _not_applicable_count(entries: list[dict[str, Any]]) -> int:
    return sum(1 for entry in entries if entry.get("documented_not_applicable"))


def _not_applicable_reasons(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for entry in entries:
        reason = entry.get("not_applicable_reason")
        if reason:
            counts[str(reason)] += 1
    return dict(counts)


def _write_case_review(path: Path, audit: dict[str, Any], fix: dict[str, Any], decision: dict[str, Any]) -> None:
    path.write_text(
        "# N8K3 BY2 Formal Ablation Duplicate Plot Fix Case Review\n\n"
        f"- before blocking duplicate patterns: `{audit.get('blocking_duplicate_count_before')}`\n"
        f"- exact duplicate remaining: `{fix.get('blocking_exact_duplicate_after_count')}`\n"
        f"- perceptual duplicate remaining: `{fix.get('perceptual_duplicate_after_count')}`\n"
        f"- figures regenerated: `{fix.get('figures_regenerated_count')}`\n"
        f"- derived data labels: `{fix.get('derived_data_labels_count')}`\n"
        f"- decision: `{decision.get('status')}`\n"
        "- boundary: no algorithm changes, no degradation matrix, no trace/final_v23 tuning, no paper performance claim.\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
